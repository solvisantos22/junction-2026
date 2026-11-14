"""Public-only science-belief controller over the frozen continuous KF/MPC.

This is a bounded heuristic, not an optimal continuous POMDP solver. It enumerates
sequences of at most four currently announced targets and one/two remote inspections.
Probe branches replan after their telemetry round trip, charging energy and time.
Physical sample observations update the next real plan; future sample-information
branches, undiscovered targets and future position fixes are not forecast.

All policies have the same motion estimator, route planner and four-target horizon.
``no_probe`` still learns exact qualities from samples. ``value_blind`` ignores all
qualities. ``leader_probe`` and ``entropy_probe`` use the same value-of-information
admission gate as the reference but restrict the next inspected region. The separate
``forced_leader_probe`` forces its first feasible leader inspection, then uses that gate.
"""

from dataclasses import dataclass
import itertools
import math

from lightlag_dynamic.controllers import RESERVE
from lightlag_dynamic.kf_mpc import KalmanMPCController, VAR_FLOOR


MAX_SEQUENCE = 4
MODES = ("reference", "no_probe", "value_blind", "leader_probe", "entropy_probe",
         "forced_leader_probe")


@dataclass(frozen=True)
class Plan:
    value: float
    end_tick: float
    sequence: tuple


def posterior(prior, signal, accuracy):
    """Bayes update for a symmetric binary signal; return posterior and signal mass."""
    rich_likelihood = accuracy if signal == "rich" else 1.0 - accuracy
    poor_likelihood = 1.0 - rich_likelihood
    mass = prior * rich_likelihood + (1.0 - prior) * poor_likelihood
    return (prior * rich_likelihood / mass if mass else prior), mass


class ExpeditionController(KalmanMPCController):
    """Use only rules/map/telemetry_log/uplink/advance, including for quality beliefs."""

    def __init__(self, tools, mode="reference"):
        if mode not in MODES:
            raise ValueError(f"unknown expedition policy {mode!r}")
        self.policy_mode = mode
        science = tools.rules()["science"]
        self.beliefs = {region: float(spec["prior_rich"])
                        for region, spec in science["regions"].items()}
        self.multipliers = dict(science["quality_multipliers"])
        self.inspection_budget = int(science["inspection_budget"])
        self.inspection_energy = float(science["inspection_energy"])
        self.accuracy = float(science.get("inspection_accuracy",
                                         science.get("signal_accuracy", 0.9)))
        self.known_regions = set()
        for region, quality in science.get("public_qualities", {}).items():
            self.beliefs[region] = float(quality == "rich")
            self.known_regions.add(region)
        self.inspected_regions = set()
        self._initial_reserved = set(science.get("inspection_reserved_regions", []))
        self._seen_quality_events = set()
        self._geometry_cache = {}
        self.decision_log = []
        super().__init__(tools)
        for packet in self.packets:
            self._read_quality(packet)

    def _read_quality(self, packet):
        for event in packet["events"]:
            kind = event["type"]
            if kind not in ("inspection_result", "region_quality"):
                continue
            region = event["region"]
            # Re-reading the public log must not count a fixed signal twice.
            identity = (kind, region, packet["tick"])
            if identity in self._seen_quality_events:
                continue
            self._seen_quality_events.add(identity)
            if kind == "region_quality":
                self.beliefs[region] = float(event["quality"] == "rich")
                self.known_regions.add(region)
            else:
                self.inspected_regions.add(region)
                if region not in self.known_regions:
                    self.beliefs[region], _ = posterior(self.beliefs[region],
                                                       event["signal"], self.accuracy)

    def absorb(self, packet):
        super().absorb(packet)
        self._read_quality(packet)
        self._geometry_cache.clear()

    def predict(self, slot, use_pending=True):
        state = super().predict(slot, use_pending=use_pending)
        # The frozen dynamic predictor has no inspect action. Delivered packets already
        # include its cost; subtract only acknowledged, not-yet-observed executions.
        last_tick = self.packets[-1]["tick"]
        count = sum(1 for ack in self.acks
                    if last_tick < ack["execute_tick"] < slot
                    and ack["command_id"] not in self.cancelled
                    and ack["command"]["action"] == "inspect")
        state["battery"] = max(0.0, state["battery"] - count * self.inspection_energy)
        state["alive"] = state["alive"] and state["battery"] > 0
        return state

    def _requested_regions(self):
        # Acceptance reserves the inspection even if a later safety stop cancels it.
        return self._initial_reserved | self.inspected_regions | {
            ack["command"]["region"] for ack in self.acks
            if ack["command"]["action"] == "inspect"}

    def _factor(self, target, beliefs):
        if self.policy_mode == "value_blind":
            return 1.0
        p = beliefs[target["region"]]
        return self.multipliers["poor"] * (1.0 - p) + self.multipliers["rich"] * p

    def _target_value(self, target, tick, beliefs):
        return super().value_at(target, tick) * self._factor(target, beliefs)

    def value_at(self, target, tick):
        return self._target_value(target, tick, self.beliefs)

    def _cached_leg(self, start, goal):
        key = (tuple(start), tuple(goal))
        if key not in self._geometry_cache:
            self._geometry_cache[key] = self.leg(start, goal)
        return self._geometry_cache[key]

    def _plan(self, state, slot, beliefs):
        """Frozen planner's route/resource constraints, with scenario-specific values."""
        start = (state["x"], state["y"])
        targets = [target for tid, target in sorted(self.targets.items())
                   if tid not in state["sampled"]]
        budget = state["battery"] - self.idle * (self.horizon - state["tick"]) - RESERVE
        best = Plan(0.0, math.inf, ())
        if not state["alive"] or slot > self.horizon:
            return best
        for size in range(1, min(len(targets), MAX_SEQUENCE) + 1):
            for sequence in itertools.permutations(targets, size):
                tick, value, energy, here = slot, 0.0, 0.0, start
                for index, target in enumerate(sequence):
                    point = (target["x"], target["y"])
                    hop = self._cached_leg(here, point)
                    home = self._cached_leg(point, self.base)
                    if hop is None or home is None:
                        break
                    if index:
                        tick += self.wait_per_leg()
                    tick += len(hop.commands)
                    if self.needs_confirmation(hop):
                        tick += self.confirmation_ticks(hop)
                    value += self._target_value(target, tick, beliefs)
                    tick += 1
                    energy += hop.energy + self.sample_cost
                    if energy + home.energy_safe > budget:
                        break
                    here = point
                else:
                    home = self._cached_leg(here, self.base)
                    end = tick + self.wait_per_leg() + len(home.commands) - 1
                    if end > self.horizon - self.home_slack() or energy + home.energy > budget:
                        continue
                    if value > best.value + 1e-9 or (abs(value - best.value) <= 1e-9
                                                    and end < best.end_tick):
                        best = Plan(value, end, sequence)
        return best

    def choose(self, state, slot):
        plan = self._plan(state, slot, self.beliefs)
        self.plan_end, self.plan = plan.end_tick, plan.sequence
        return plan.sequence

    def _after_inspection(self, state, slot):
        # Inspect executes at slot, its packet arrives slot+k, and the next command
        # sent on receipt executes slot+2*k+1. Predict states describe slot-1.
        next_slot = slot + 2 * self.k + 1
        after = dict(state)
        after["tick"] = next_slot - 1
        after["battery"] -= self.inspection_energy + self.idle * (next_slot - slot)
        after["alive"] = after["alive"] and after["battery"] > 0
        home = self._cached_leg((state["x"], state["y"]), self.base)
        reserve = self.idle * (self.horizon - after["tick"]) + RESERVE
        if (not after["alive"] or next_slot > self.horizon or home is None
                or after["battery"] < reserve + home.energy_safe
                or next_slot + len(home.commands) - 1 > self.horizon - self.home_slack()):
            return None
        return after, next_slot

    def _candidate_regions(self, beliefs, available, plan):
        active = {target["region"] for target in self.targets.values()}
        candidates = sorted(region for region in available if region in active
                            and 0.0 < beliefs[region] < 1.0)
        if self.policy_mode in ("leader_probe", "forced_leader_probe"):
            leader = plan.sequence[0]["region"] if plan.sequence else None
            return [leader] if leader in candidates else []
        if self.policy_mode == "entropy_probe" and candidates:
            return [max(candidates, key=lambda region: (
                -beliefs[region] * math.log(beliefs[region])
                -(1.0 - beliefs[region]) * math.log(1.0 - beliefs[region]), region))]
        return candidates

    def _inspection_options(self, state, slot, beliefs, available, remaining, direct):
        if remaining <= 0:
            return {}
        after = self._after_inspection(state, slot)
        if after is None:
            return {}
        future, next_slot = after
        options = {}
        for region in self._candidate_regions(beliefs, available, direct):
            expected = 0.0
            for signal in ("poor", "rich"):
                updated, mass = posterior(beliefs[region], signal, self.accuracy)
                if mass == 0:
                    continue
                branch = dict(beliefs, **{region: updated})
                plan = self._plan(future, next_slot, branch)
                further = self._inspection_options(future, next_slot, branch,
                                                    available - {region}, remaining - 1, plan)
                expected += mass * max([plan.value, *further.values()])
            options[region] = expected
        return options

    def inspection_options(self, state=None, slot=None):
        """Inspectable public diagnostic; values are expected future raw science."""
        slot = self.next_slot() if slot is None else slot
        state = self.predict(slot) if state is None else state
        self._var0 = max(state["cov"][0][0], state["cov"][1][1], VAR_FLOOR)
        self._geometry_cache.clear()
        direct = self._plan(state, slot, self.beliefs)
        requested = self._requested_regions()
        remaining = min(2, max(0, self.inspection_budget - len(requested)))
        options = {} if self.policy_mode in ("no_probe", "value_blind") else \
            self._inspection_options(state, slot, self.beliefs,
                                     set(self.beliefs) - requested - self.known_regions,
                                     remaining, direct)
        return direct, options

    def decide(self):
        slot = self.next_slot()
        if slot > self.horizon:
            return
        state = self.predict(slot)
        if not state["alive"]:
            return
        direct, options = self.inspection_options(state, slot)
        region = max(sorted(options), key=options.get) if options else None
        force = self.policy_mode == "forced_leader_probe" and not self._requested_regions()
        inspect = region is not None and (options[region] > direct.value + 1e-9
                                          or (force and options[region] > 0))
        self.decision_log.append({"tick": self.tick, "slot": slot,
                                  "beliefs": dict(self.beliefs), "direct_value": direct.value,
                                  "inspection_values": dict(options),
                                  "action": "inspect" if inspect else "act",
                                  "region": region if inspect else None,
                                  "plan": [target["id"] for target in direct.sequence]})
        if inspect and self.send([{"action": "inspect", "region": region}]):
            self.confirm_tick = self.reserved_until()
            return
        super().decide()


def run_policy(public_tools, name="reference"):
    controller = ExpeditionController(public_tools, mode=name)
    controller.run()
    return controller


def _policy(name):
    def run(public_tools):
        return run_policy(public_tools, name)
    run.__name__ = name
    return run


POLICIES = {name: _policy(name) for name in MODES}
