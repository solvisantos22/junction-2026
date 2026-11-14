"""Public-only four-target KF/MPC with productive inspection scheduling.

The controller compares immediate motion, sample-and-wait, inspect-and-wait, and
a useful drive/sample prefix followed by inspections. It is a bounded heuristic:
at most four targets, one candidate first target per region, at most two probes
chosen as a batch, and no forecast of undiscovered targets or future position fixes.
Sample success is a public KF probability, not assumed truth. Only delivered
events change actual quality beliefs. Scenario plans share cached route pools and
regional value coefficient vectors rather than re-enumerating routes per belief.
Only the proposed first sample has explicit hit/miss weighting; direct and later
route samples retain the frozen MPC's planned-success approximation. Future sample
outcomes do not condition the hypothetical pose distribution. Diagnostic values are
heuristic planning values, not calibrated expected returns or optimality bounds.
"""

from dataclasses import dataclass
import itertools
import math

from lightlag_dynamic.controllers import Leg, RESERVE
from lightlag_dynamic.kf_mpc import (KalmanMPCController, P_COMMIT, P_TRY,
                                     VAR_FLOOR, inside_probability)
from .reference import ExpeditionController, posterior


MODES = ("reference", "adaptive", "no_probe", "entropy", "fixed_pair")
MAX_TARGETS = 4


@dataclass(frozen=True)
class Route:
    coefficients: tuple
    target_ids: tuple
    end_tick: int
    movement_and_sample_energy: float
    home_energy_safe: float
    sample_ticks: tuple


@dataclass
class RoutePool:
    routes: tuple
    same_region_two_target_coefficients: dict
    same_region_two_target_routes: dict
    enumerated_feasible: int


class ExpeditionControllerV2(ExpeditionController):
    def __init__(self, tools, mode="reference", fixed_pair=None):
        if mode not in MODES:
            raise ValueError(f"unknown v2 policy {mode!r}")
        super().__init__(tools, mode="reference")
        self.policy_mode = mode
        self.regions = tuple(sorted(self.beliefs))
        self.region_index = {region: index for index, region in enumerate(self.regions)}
        if mode == "fixed_pair":
            if (fixed_pair is None or len(fixed_pair) != 2 or len(set(fixed_pair)) != 2
                    or not set(fixed_pair) <= set(self.regions)):
                raise ValueError("fixed_pair needs two distinct public region names")
        elif fixed_pair is not None:
            raise ValueError("fixed_pair is only valid for the fixed_pair policy")
        self.fixed_pair = tuple(fixed_pair or ())
        self._v2_geometry = {}
        self._route_pools = {}
        self._sample_intents = {}
        self._evaluated_candidates = []

    def absorb(self, packet):
        super().absorb(packet)
        if hasattr(self, "_route_pools"):
            self._route_pools.clear()
            self._v2_geometry.clear()

    def _pending_targets(self):
        """Pending intentions are unavailable targets, never confirmed successes."""
        last_tick = self.packets[-1]["tick"]
        pending = set()
        for ack in self.acks:
            if (ack["execute_tick"] <= last_tick or ack["command_id"] in self.cancelled
                    or ack["command"]["action"] != "sample"):
                continue
            target_id = self._sample_intents.get(ack["command_id"])
            if target_id is None:
                predicted = KalmanMPCController.predict(self, ack["execute_tick"] + 1)
                targets = [target for target in self.targets.values()
                           if target["id"] not in self.packets[-1]["sampled_targets"]]
                if targets:
                    target = min(targets, key=lambda target: math.hypot(
                        target["x"] - predicted["x"], target["y"] - predicted["y"]))
                    spread = math.sqrt(max(predicted["cov"][0][0], predicted["cov"][1][1]))
                    if math.hypot(target["x"] - predicted["x"], target["y"] - predicted["y"]) \
                            <= self.radius + 3 * spread:
                        target_id = target["id"]
            if target_id is not None:
                pending.add(target_id)
        return pending

    def predict(self, slot, use_pending=True):
        state = super().predict(slot, use_pending=use_pending)
        state["sampled"] = set(self.packets[-1]["sampled_targets"])
        state["pending_samples"] = self._pending_targets() if use_pending else set()
        return state

    def _reset_planning(self, state):
        self._v2_geometry.clear()
        self._route_pools.clear()
        self._evaluated_candidates = []
        self._var0 = max(state["cov"][0][0], state["cov"][1][1], VAR_FLOOR)

    def _geometry(self, start, goal, variance):
        """Cache geometry once; the starting position variance is additive in KF legs."""
        key = (tuple(start), tuple(goal))
        if key not in self._v2_geometry:
            previous = self._var0
            self._var0 = VAR_FLOOR
            try:
                self._v2_geometry[key] = self.leg(start, goal)
            finally:
                self._var0 = previous
        leg = self._v2_geometry[key]
        if leg is None:
            return None
        return Leg(leg.commands, leg.energy, leg.energy_safe,
                   math.sqrt(max(0.0, leg.uncertainty ** 2 - VAR_FLOOR + variance)))

    def _factors(self, beliefs):
        poor, rich = self.multipliers["poor"], self.multipliers["rich"]
        return tuple(poor + (rich - poor) * beliefs[region] for region in self.regions)

    @staticmethod
    def _dot(coefficients, factors):
        return sum(a * b for a, b in zip(coefficients, factors))

    def _base_value(self, target, tick):
        return KalmanMPCController.value_at(self, target, tick)

    def _pool(self, state, slot, depth=MAX_TARGETS):
        excluded = frozenset(state["sampled"]) | frozenset(state.get("pending_samples", ()))
        variance = max(state["cov"][0][0], state["cov"][1][1], VAR_FLOOR)
        key = (state["x"], state["y"], state["battery"], state["tick"], slot,
               excluded, depth, variance)
        if key in self._route_pools:
            return self._route_pools[key]
        targets = [target for tid, target in sorted(self.targets.items()) if tid not in excluded]
        start = (state["x"], state["y"])
        budget = state["battery"] - self.idle * (self.horizon - state["tick"]) - RESERVE
        compressed, single, single_routes = {}, {}, {}
        feasible = 0
        points = [start] + [(target["x"], target["y"]) for target in targets]
        homes = [self._geometry(point, self.base, variance) for point in points]
        legs = {}

        def hop(a, b):
            if (a, b) not in legs:
                legs[(a, b)] = self._geometry(points[a], points[b], variance)
            return legs[(a, b)]

        def visit(here, tick, energy, used, ids, coefficients, sample_ticks):
            nonlocal feasible
            if len(ids) >= depth:
                return
            for index, target in enumerate(targets, 1):
                if index in used:
                    continue
                leg, home = hop(here, index), homes[index]
                if leg is None or home is None:
                    continue
                spent = energy + leg.energy + self.sample_cost
                if spent + home.energy_safe > budget:
                    continue
                sample_tick = tick + (self.wait_per_leg() if ids else 0) + len(leg.commands)
                if self.needs_confirmation(leg):
                    sample_tick += self.confirmation_ticks(leg)
                end = sample_tick + self.wait_per_leg() + len(home.commands)
                if end > self.horizon - self.home_slack():
                    continue
                values = list(coefficients)
                region = target["region"]
                values[self.region_index[region]] += self._base_value(target, sample_tick)
                values = tuple(values)
                sequence = ids + (target["id"],)
                sampling = sample_ticks + (sample_tick,)
                route = Route(values, sequence, end, spent, home.energy_safe, sampling)
                # Retain first-region alternatives for useful-prefix proposals.
                group = (values, self.targets[sequence[0]]["region"])
                previous = compressed.get(group)
                if previous is None or (end, sequence) < (previous.end_tick, previous.target_ids):
                    compressed[group] = route
                feasible += 1
                if len(sequence) == 2 and all(self.targets[tid]["region"] == region for tid in sequence):
                    value = values[self.region_index[region]]
                    previous_single = single_routes.get(region)
                    if value > single.get(region, -1) or (value == single.get(region)
                            and (previous_single is None or end < previous_single.end_tick)):
                        single[region], single_routes[region] = value, route
                visit(index, sample_tick + 1, spent, used | {index}, sequence, values, sampling)

        if state["alive"] and slot <= self.horizon and depth > 0:
            visit(0, slot, 0.0, frozenset(), (), (0.0,) * len(self.regions), ())
        pool = RoutePool(tuple(compressed.values()), single, single_routes, feasible)
        self._route_pools[key] = pool
        return pool

    def _best(self, pool, beliefs):
        factors = self._factors(beliefs)
        best, value = None, 0.0
        for route in pool.routes:
            score = self._dot(route.coefficients, factors)
            if score > value + 1e-9 or (score > 0 and abs(score - value) <= 1e-9
                                       and (best is None or (route.end_tick, route.target_ids)
                                            < (best.end_tick, best.target_ids))):
                best, value = route, score
        return best, value

    def choose(self, state, slot):
        route, _ = self._best(self._pool(state, slot), self.beliefs)
        self.plan = tuple(self.targets[tid] for tid in route.target_ids) if route else ()
        self.plan_end = route.end_tick if route else math.inf
        return self.plan

    def _available(self, state, exclude=()):
        blocked = set(exclude) | self.known_regions | self._requested_regions()
        blocked |= {self.targets[tid]["region"] for tid in state.get("pending_samples", ())}
        available = [region for region in self.regions if region not in blocked
                     and 0 < self.beliefs[region] < 1]
        if self.policy_mode == "fixed_pair":
            available = [region for region in available if region in self.fixed_pair]
        if self.policy_mode == "entropy":
            available.sort(key=lambda region: (-self._entropy(self.beliefs[region]), region))
        return available

    @staticmethod
    def _entropy(probability):
        return -probability * math.log(probability) - (1 - probability) * math.log(1 - probability)

    def _probe_sets(self, state, exclude=()):
        if self.policy_mode == "no_probe":
            return ()
        available = self._available(state, exclude)
        remaining = min(2, max(0, self.inspection_budget - len(self._requested_regions())))
        result = []
        for count in range(1, min(remaining, len(available)) + 1):
            if self.policy_mode == "entropy":
                result.append(tuple(available[:count]))
            else:
                result.extend(itertools.combinations(available, count))
        return tuple(result)

    def _signal_branches(self, beliefs, probes):
        branches = [(1.0, beliefs)]
        for region in probes:
            expanded = []
            for mass, current in branches:
                for signal in ("poor", "rich"):
                    updated, probability = posterior(current[region], signal, self.accuracy)
                    if probability:
                        after = dict(current)
                        after[region] = updated
                        expanded.append((mass * probability, after))
            branches = expanded
        return branches

    def _safe_future(self, state, next_slot, energy, position=None, covariance=None):
        future = dict(state)
        future["sampled"] = set(state["sampled"])
        future["pending_samples"] = set(state.get("pending_samples", ()))
        future["battery"] -= energy + self.idle * (next_slot - (state["tick"] + 1))
        future["tick"] = next_slot - 1
        if position is not None:
            future["x"], future["y"] = position
        if covariance is not None:
            future["cov"] = covariance
        variance = max(future["cov"][0][0], future["cov"][1][1], VAR_FLOOR)
        home = self._geometry((future["x"], future["y"]), self.base, variance)
        reserve = self.idle * (self.horizon - future["tick"]) + RESERVE
        if (next_slot > self.horizon or future["battery"] <= 0 or home is None
                or home.energy_safe + reserve > future["battery"]
                or next_slot + len(home.commands) - 1 > self.horizon - self.home_slack()):
            return None
        return future

    def _prefix(self, state, slot, target):
        start, point = (state["x"], state["y"]), (target["x"], target["y"])
        variance = max(state["cov"][0][0], state["cov"][1][1], VAR_FLOOR)
        leg = self._geometry(start, point, variance)
        if leg is None or self.needs_confirmation(leg):
            return None
        mean, cov = list(self.filter.mean), [row[:] for row in self.filter.cov]
        mean[0], mean[1], mean[2] = state["x"], state["y"], state["bias"]
        for i in (0, 1):
            for j in (0, 1):
                cov[i][j] = state["cov"][i][j]
        energy = 0.0
        for command in leg.commands:
            mean, cov, by_terrain = self.filter.propagate(
                mean, cov, command["heading_deg"], command["metres"], self.terrain_at)
            energy += sum(wheel * self.drive_cost * self.multiplier[terrain]
                          for terrain, wheel in by_terrain.items())
        xy_cov = [row[:2] for row in cov[:2]]
        chance = inside_probability(mean[:2], xy_cov, point, self.radius)
        if chance < (P_COMMIT if leg.commands else P_TRY):
            return None
        return {"target": target, "commands": list(leg.commands) + [{"action": "sample"}],
                "energy": energy + self.sample_cost, "chance": chance,
                "position": tuple(mean[:2]), "cov": xy_cov,
                "sample_tick": slot + len(leg.commands)}

    def _evaluate(self, state, slot, probes, prefix=None):
        commands = [] if prefix is None else prefix["commands"]
        # Empty inspect-first is not an option. A physical prefix always ends in a sample.
        if not commands and not probes:
            return None
        last_execute = slot + len(commands) + len(probes) - 1
        next_slot = last_execute + 2 * self.k + 1
        energy = len(probes) * self.inspection_energy + (prefix["energy"] if prefix else 0)
        future = self._safe_future(state, next_slot, energy,
                                   prefix["position"] if prefix else None,
                                   prefix["cov"] if prefix else None)
        if future is None:
            return None
        outcomes = [(1.0, dict(self.beliefs), future, 0.0)]
        if prefix:
            target, chance = prefix["target"], prefix["chance"]
            region = target["region"]
            outcomes = []
            if chance < 1:
                outcomes.append((1 - chance, dict(self.beliefs), future, 0.0))
            for quality, probability in (("poor", 1 - self.beliefs[region]),
                                         ("rich", self.beliefs[region])):
                if probability:
                    known = dict(self.beliefs)
                    known[region] = float(quality == "rich")
                    sampled = dict(future, sampled=future["sampled"] | {target["id"]})
                    credit = self._base_value(target, prefix["sample_tick"]) * self.multipliers[quality]
                    outcomes.append((chance * probability, known, sampled, credit))
        expected = 0.0
        for mass, beliefs, branch_state, credit in outcomes:
            pool = self._pool(branch_state, next_slot, MAX_TARGETS - bool(prefix))
            for signal_mass, branch_beliefs in self._signal_branches(beliefs, probes):
                _, value = self._best(pool, branch_beliefs)
                expected += mass * signal_mass * (credit + value)
        return {"kind": "overlap" if prefix and probes else "sample_wait" if prefix else "inspect_wait",
                "value": expected, "probes": tuple(probes), "prefix": prefix,
                "next_slot": next_slot,
                "commands": commands + [{"action": "inspect", "region": region} for region in probes]}

    def planning_options(self, state=None, slot=None):
        slot = self.next_slot() if slot is None else slot
        state = self.predict(slot) if state is None else state
        self._reset_planning(state)
        pool = self._pool(state, slot)
        direct, value = self._best(pool, self.beliefs)
        best = {"kind": "act", "value": value, "probes": (), "prefix": None,
                "next_slot": slot, "commands": []}
        factors = self._factors(self.beliefs)
        leaders = {}
        for route in pool.routes:
            region = self.targets[route.target_ids[0]]["region"]
            score = self._dot(route.coefficients, factors)
            previous = leaders.get(region)
            if previous is None or score > previous[0] + 1e-9 or (
                    abs(score - previous[0]) <= 1e-9 and route.end_tick < previous[1].end_tick):
                leaders[region] = (score, route)

        def consider(probes, prefix=None):
            nonlocal best
            option = self._evaluate(state, slot, probes, prefix)
            if option is not None:
                self._evaluated_candidates.append(option)
                # Strict admission: equal-value waiting/probing is not free information.
                if option["value"] > best["value"] + 1e-9:
                    best = option

        for probes in self._probe_sets(state):
            consider(probes)
        for region, (_, route) in sorted(leaders.items()):
            prefix = self._prefix(state, slot, self.targets[route.target_ids[0]])
            if prefix is None:
                continue
            consider((), prefix)
            for probes in self._probe_sets(state, exclude=(region,)):
                consider(probes, prefix)
        diagnostics = {
            "first_region_values": {region: data[0] for region, data in sorted(leaders.items())},
            "single_region_two_target_values": {
                region: pool.same_region_two_target_coefficients.get(region, 0.0) * factors[index]
                for index, region in enumerate(self.regions)},
            "single_region_two_target_plans": {
                region: {"feasible": region in pool.same_region_two_target_routes,
                         "expected_value": pool.same_region_two_target_coefficients.get(region, 0.0) * factors[index],
                         **({"targets": list(pool.same_region_two_target_routes[region].target_ids),
                             "sample_ticks": list(pool.same_region_two_target_routes[region].sample_ticks),
                             "return_tick": pool.same_region_two_target_routes[region].end_tick,
                             "movement_and_sample_energy": pool.same_region_two_target_routes[region].movement_and_sample_energy,
                             "home_energy_safe": pool.same_region_two_target_routes[region].home_energy_safe,
                             "idle_energy_to_horizon": self.idle * (self.horizon - state["tick"]),
                             "energy_reserve": RESERVE, "battery": state["battery"]}
                            if region in pool.same_region_two_target_routes else {})}
                for index, region in enumerate(self.regions)},
            "initial_pool_routes": len(pool.routes), "initial_pool_feasible_sequences": pool.enumerated_feasible,
            "route_pools_built": len(self._route_pools),
            "sample_learning": "exact only after delivered region_quality; hypothetical success/failure branches",
            "value_semantics": "heuristic: first prefix sample has hit/miss branches; direct/continuation samples assume planned success; future pose conditioning omitted",
            "planning_horizon_targets": MAX_TARGETS,
        }
        return direct, best, diagnostics

    def decide(self):
        slot = self.next_slot()
        if slot > self.horizon:
            return
        state = self.predict(slot)
        if not state["alive"]:
            return
        direct, choice, diagnostics = self.planning_options(state, slot)
        prefix = choice["prefix"]
        diagnostic = {"tick": self.tick, "slot": slot, "beliefs": dict(self.beliefs),
                      "confirmed_sampled": sorted(state["sampled"]),
                      "pending_samples": sorted(state.get("pending_samples", ())),
                      "action": choice["kind"], "probes": list(choice["probes"]),
                      "prefix_target": prefix["target"]["id"] if prefix else None,
                      "sample_success_probability": prefix["chance"] if prefix else None,
                      "predicted_next_action_slot": choice["next_slot"],
                      "chosen_expected_value": choice["value"],
                      "direct_value": self._dot(direct.coefficients, self._factors(self.beliefs)) if direct else 0,
                      "direct_plan": list(direct.target_ids) if direct else [],
                      "candidates": [{"action": option["kind"], "value": option["value"],
                                      "probes": list(option["probes"]),
                                      "prefix_target": option["prefix"]["target"]["id"] if option["prefix"] else None}
                                     for option in self._evaluated_candidates],
                      **diagnostics}
        if not self.decision_log:
            self.initial_single_region_values = diagnostics["single_region_two_target_values"]
            self.initial_single_region_plans = diagnostics["single_region_two_target_plans"]
            self.initial_first_region_values = diagnostics["first_region_values"]
        self.decision_log.append(diagnostic)
        if choice["kind"] != "act":
            before = len(self.acks)
            if self.send(choice["commands"]):
                if prefix:
                    for ack in self.acks[before:]:
                        if ack["command"]["action"] == "sample":
                            self._sample_intents[ack["command_id"]] = prefix["target"]["id"]
                self.confirm_tick = self.reserved_until()
                return
        KalmanMPCController.decide(self)


def run_policy(public_tools, name="reference", fixed_pair=None):
    controller = ExpeditionControllerV2(public_tools, mode=name, fixed_pair=fixed_pair)
    controller.run()
    return controller
