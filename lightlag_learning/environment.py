"""Public goal options over the inherited Traverse navigator.

The trusted runner owns the simulator and terminal grade. Observation builders
and the pilot use only public rules, map, acknowledgements and delayed telemetry.
Charging forecasts reuse the reference RouteProblem; they are estimates, not a
guarantee that real driving and charging will finish at the predicted time.
"""

from collections import Counter
from copy import deepcopy
import math
from numbers import Integral
import random
import time

from lightlag_traverse.pilot import Pilot
from lightlag_traverse.planning import RouteProblem
from lightlag_rl_feasible.adapter import visit_return


CANDIDATE_FEATURES = (
    "is_home", "time_remaining", "battery_fraction", "position_uncertainty",
    "outbound_time", "outbound_energy", "return_time", "return_energy",
    "target_value", "arrival_value", "deadline_slack", "relative_x",
    "relative_y", "open_count", "visit_duration_with_charge",
    "battery_after_sample", "round_trip_duration_with_charge",
    "round_trip_charge_wait", "round_trip_finish_slack", "charge_aware_credit",
)
GLOBAL_FEATURES = (
    "time_remaining", "battery_fraction", "position_uncertainty",
    "solar_efficiency", "solar_rate_fraction", "remaining_solar_income",
    "direct_home_duration_with_charge", "direct_home_charge_wait",
    "direct_home_model_feasible", "pending_sample_count", "sampled_count",
    "credited_public_science", "known_science_value", "sample_failure_count",
)


def _bounded(value):
    value = float(value)
    if math.isnan(value):
        raise ValueError("nonfinite public feature")
    return min(2.0, max(-2.0, value))


def estimate_goal(pilot, tick, x, y, battery, goal):
    """One public visit-plus-home forecast, or a direct-home forecast.

    No change to RouteProblem's rounding, charging steps or reference reserves.
    A science forecast includes the sample cost and its stop tick before home.
    """
    home_ticks, home_energy = pilot._to("base", x, y)
    common = dict(
        sun=pilot.sun, now=float(tick), battery=battery,
        late_fraction=pilot.rules["sample_windows"]["late_fraction"],
        start_home=(home_ticks * pilot.opt["home_slack"], home_energy),
        sample_cost=pilot.rules["sample_cost"], stop_ticks=pilot.opt["stop_ticks"],
        home_margin=int(pilot.opt["home_margin"]),
        deadline_margin=pilot.opt["deadline_margin"],
        floor=pilot.opt["floor"] + 1.0, slack=pilot.opt["leg_slack"],
    )
    if goal == "base":
        if not math.isfinite(home_ticks) or not math.isfinite(home_energy):
            return None
        problem = RouteProblem(values=[], deadlines=[], start_ticks=[], start_energy=[],
                               ticks=[], energy=[], home_ticks=[], home_energy=[], **common)
        finish = problem.home(problem.now, battery, -1)
        if finish is None:
            return None
        return {"finish": finish, "visit_duration": 0.0, "visit_battery": battery,
                "duration": finish - problem.now,
                "wait": finish - problem.now - problem.start_home[0], "credit": 0.0}
    forecast = visit_return(pilot, tick, x, y, battery, goal)
    if forecast is None:
        return None
    outward, _ = pilot._to(goal, x, y)
    back = pilot.fields["base"].ticks[pilot.nodes[goal]] * pilot.opt["home_slack"]
    whole = lambda duration: max(1, int(duration * pilot.opt["leg_slack"] + .5))
    now = int(math.ceil(tick))
    finish = forecast["finish_tick"]
    return {"finish": finish, "visit_duration": forecast["sample_tick"] - now,
            "visit_battery": forecast["after_sample_battery"], "duration": finish - now,
            "wait": finish - now - whole(outward) - int(pilot.opt["stop_ticks"]) - whole(back),
            "credit": forecast["estimated_value"]}


def build_observation(pilot, tick, x, y, sigma, battery, force_home=False):
    """Serialize public beliefs. IDs are bookkeeping, not neural embeddings.

    Time/energy scale by horizon/capacity, value by 10, counts by 46, positions
    by map dimensions. Global science values scale by 200 and remaining solar
    income by ten battery capacities. Features are bounded to [-2, 2]. Home
    stays a valid fallback even when the public return model reports failure.
    """
    horizon, capacity = pilot.horizon, pilot.capacity
    open_ids = sorted(pilot._open(tick))
    ids, rows, mask = ["base", *open_ids], [], []
    home_estimate = estimate_goal(pilot, tick, x, y, battery, "base")
    for goal in ids:
        is_home = goal == "base"
        outward, outward_energy = pilot._to(goal, x, y)
        if is_home:
            back = back_energy = value = arrival_value = 0.0
            slack = 1.0
            forecast = home_estimate
        else:
            node = pilot.nodes.get(goal)
            field = pilot.fields.get("base")
            back = field.ticks[node] if field is not None and node is not None else math.inf
            back_energy = field.energy[node] if field is not None and node is not None else math.inf
            target = pilot.targets[goal]
            value, deadline = target["value"], target["deadline_tick"]
            arrival = tick + outward + 1.0
            arrival_value = value if deadline is None or arrival <= deadline - 2 else target["late_value"]
            slack = 1.0 if deadline is None else (deadline - arrival) / horizon
            forecast = estimate_goal(pilot, tick, x, y, battery, goal)
        gx, gy = pilot._spot(goal)
        base_row = [float(is_home), (horizon-tick)/horizon, battery/capacity,
                    sigma/pilot.rules["target_radius"], outward/horizon,
                    outward_energy/capacity, back/horizon, back_energy/capacity,
                    value/10, arrival_value/10, slack, (gx-x)/pilot.surface.width,
                    (gy-y)/pilot.surface.height, len(open_ids)/46]
        extra = ([forecast["visit_duration"]/horizon, forecast["visit_battery"]/capacity,
                  forecast["duration"]/horizon, forecast["wait"]/horizon,
                  (horizon-pilot.opt["home_margin"]-forecast["finish"])/horizon,
                  forecast["credit"]/10] if forecast is not None else [0.0]*6)
        rows.append([_bounded(v) for v in base_row + extra])
        mask.append(is_home or (not force_home and forecast is not None))
    globals_ = [
        (horizon-tick)/horizon, battery/capacity, sigma/pilot.rules["target_radius"],
        pilot.efficiency, pilot.sun.rate[min(tick, horizon+1)]/pilot.rules["solar_peak"],
        pilot.sun.gained(tick, horizon)/(10*capacity),
        home_estimate["duration"]/horizon if home_estimate else 1.0,
        home_estimate["wait"]/horizon if home_estimate else 1.0,
        float(home_estimate is not None), len(pilot.pending)/46, len(pilot.sampled)/46,
        pilot.credited_science/200, sum(t["value"] for t in pilot.targets.values())/200,
        pilot.sample_failures/46,
    ]
    return {"ids": ids, "candidates": rows, "global": [_bounded(v) for v in globals_],
            "mask": mask, "tick": int(pilot.now), "planned_tick": int(tick)}


def random_choice(obs, rng=None):
    """Uniform legal-goal control; pass an episode-owned RNG for reproducibility."""
    rng = rng if rng is not None else random
    return int(rng.choice([i for i, valid in enumerate(obs["mask"]) if valid]))


def greedy_choice(obs):
    """Charge-aware credited science per visit tick, on the same option interface."""
    valid = [i for i, legal in enumerate(obs["mask"]) if legal and obs["ids"][i] != "base"]
    return max(valid, key=lambda i: obs["candidates"][i][19] /
               max(obs["candidates"][i][14], 1/420)) if valid else 0


class OptionPilot(Pilot):
    """Goal selection changes; inherited estimation and low-level driving remain."""

    def __init__(self, tools, choose):
        self.choose = choose
        self.transitions = []
        self.decision_count = 0
        self.credited_science = 0.0
        self.sample_failures = 0
        self._credited_ids = set()
        self._active = None
        self._goal = None
        self._force_home = False
        self._next_reason = "initial"
        super().__init__(tools, {"route": "optimise"})

    def _packet(self, packet):
        super()._packet(packet)
        for event in packet["events"]:
            if event["type"] == "sample_taken" and event["target_id"] not in self._credited_ids:
                target = self.targets.get(event["target_id"])
                if target is not None:
                    self.credited_science += target["value"] if event["on_time"] else target["late_value"]
                    self._credited_ids.add(event["target_id"])
            elif event["type"] == "sample_failed":
                self.sample_failures += 1

    def _close(self, obs, reason, done=False, reward=0.0):
        if self._active is not None:
            previous, action = self._active
            elapsed = obs["tick"] - previous["tick"]
            if elapsed <= 0:
                raise RuntimeError("option transitions must advance public time")
            self.transitions.append({"obs": previous, "action": action, "next_obs": deepcopy(obs),
                                     "reward": float(reward), "done": done,
                                     "elapsed_ticks": elapsed, "termination_reason": reason})
            self._active = None

    def _plan(self, tick, x, y, battery, steps):
        if self._goal is None:
            sigma = self.predict(tick)[2]
            obs = build_observation(self, tick, x, y, sigma, battery, self._force_home)
            action = self.choose(deepcopy(obs))
            if (isinstance(action, bool) or not isinstance(action, Integral)
                    or not 0 <= int(action) < len(obs["ids"]) or not obs["mask"][int(action)]):
                raise ValueError("choose must return a valid unmasked integer goal index")
            self._close(obs, self._next_reason)
            self._active = (deepcopy(obs), int(action))
            self._goal = obs["ids"][int(action)]
            self._next_reason = "active"
            self.decision_count += 1
        self.route = [] if self._goal == "base" else [self._goal]
        self.need_plan = False
        self.last_plan = tick

    def act(self):
        if not self.alive:
            return
        tick = max(self.now + self.delay + 1, self.reserved_until + 1)
        if tick > self.horizon:
            return
        x, y, _, battery = self.predict(tick)
        if self._goal != "base":
            home = estimate_goal(self, tick, x, y, battery, "base")
            if home is None or home["finish"] >= self.horizon - self.opt["home_margin"]:
                self._goal, self._force_home = None, True
                if self._next_reason != "sample_queued":
                    self._next_reason = "return_guard"
                self.need_plan = True
            elif self._goal is not None and (
                    self._goal in self.sampled or self._goal in self.pending
                    or estimate_goal(self, tick, x, y, battery, self._goal) is None):
                self._goal = None
                self._next_reason, self.need_plan = "goal_infeasible", True
        prior_ids, goal = set(self.by_id), self._goal
        super().act()
        new_ids = set(self.by_id) - prior_ids
        queued_sample = any(self.schedule[self.by_id[c]]["command"]["action"] == "sample" for c in new_ids)
        if queued_sample:
            # The acknowledgement is public. Select again next tick while this
            # sample is in flight; prediction includes its queued energy cost.
            self._goal = None
            self._next_reason, self.need_plan = "sample_queued", True
        elif goal not in (None, "base") and not self.route:
            # Preserve any downstream return override made by the inherited pilot.
            self._goal, self._force_home = None, True
            self._next_reason, self.need_plan = "navigator_return", True

    def finish(self, reward):
        x, y, sigma, battery = self.predict(self.horizon)
        obs = build_observation(self, self.horizon, x, y, sigma, battery, force_home=True)
        self._close(obs, "horizon", done=True, reward=reward)


def run_episode(seed, choose, keep_replay=False):
    """Trusted full-horizon runner; terminal official reward is the only reward."""
    from lightlag_traverse.environment import TraverseEnvironment

    env = TraverseEnvironment(seed)
    counts, sent, invalid = Counter(), Counter(), []

    class Tools:
        def _call(self, name, *args):
            counts[name] += 1
            try:
                result = getattr(env, name)(*args)
            except ValueError as error:
                invalid.append({"tool": name, "error": str(error)})
                raise
            if name == "uplink":
                sent.update(ack["command"]["action"] for ack in result)
            return result

        def rules(self): return self._call("rules")
        def map(self): return self._call("map")
        def telemetry_log(self): return self._call("telemetry_log")
        def uplink(self, commands): return self._call("uplink", commands)
        def advance(self, ticks=1): return self._call("advance", ticks)

    started = time.monotonic()
    pilot, tools = None, Tools()
    pilot = OptionPilot(tools, choose)
    while True:
        pilot.act()
        out = tools.advance(1)
        pilot.observe(out["packets"], out["current_tick"])
        if out["episode_complete"]:
            break
    result = env.evaluate()
    reward = result["raw_score"] / result["max_available_value"]
    pilot.finish(reward)
    run = {"seed": seed, "result": result, "reward": reward,
           "transitions": pilot.transitions, "decision_count": pilot.decision_count,
           "public_calls": sum(counts.values()), "calls_by_tool": dict(counts),
           "commands_by_action": dict(sent), "invalid_calls": invalid,
           "seconds": time.monotonic() - started}
    if keep_replay:
        run["replay"] = env.replay()
    return run
