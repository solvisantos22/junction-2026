"""Match the existing RL scaffold, adding only public visit-return feasibility."""

from collections import Counter
import math
from numbers import Integral
import time

from lightlag_rl.adapter import RLPilot, candidates
from lightlag_traverse.planning import RouteProblem


def visit_return(pilot, tick, x, y, battery, name):
    """Use the reference's approximate charging model for one visit then home.

    This reads only public rules/map and the pilot's current beliefs. It is an
    estimated feasibility test, not a proof about the noisy physical trajectory.
    In particular RouteProblem models aggregate energy within a leg.
    """
    outbound = pilot._to(name, x, y)
    home_now = pilot._to("base", x, y)
    node = pilot.nodes[name]
    base = pilot.fields.get("base")
    if node is None or base is None:
        return None
    back = (base.ticks[node] * pilot.opt["home_slack"], base.energy[node])
    if not all(math.isfinite(v) and v >= 0 for v in (*outbound, *back, *home_now)):
        return None
    target = pilot.targets[name]
    problem = RouteProblem(
        pilot.sun, float(tick), battery, [target["value"]], [target["deadline_tick"]],
        pilot.rules["sample_windows"]["late_fraction"], [outbound[0]], [outbound[1]],
        [[0.0]], [[0.0]], [back[0]], [back[1]],
        (home_now[0] * pilot.opt["home_slack"], home_now[1]), pilot.rules["sample_cost"],
        stop_ticks=pilot.opt["stop_ticks"], home_margin=int(pilot.opt["home_margin"]),
        deadline_margin=pilot.opt["deadline_margin"], floor=pilot.opt["floor"] + 1.0,
        slack=pilot.opt["leg_slack"],
    )
    value, finish = problem.score([0])
    if value < 0 or not math.isfinite(finish):
        return None
    visit = problem.visit(problem.now, problem.battery, -1, 0)
    if visit is None:
        raise RuntimeError("reference visit/score disagreement")
    return {"finish_tick": finish, "sample_tick": visit[0], "estimated_value": value,
            "after_sample_battery": visit[1], "limit_tick": problem.limit}


class FeasiblePilot(RLPilot):
    """Only the next-target candidate mask changes; navigation stays inherited."""

    def __init__(self, tools, choose):
        self.feasibility = []
        super().__init__(tools, choose)

    def _plan(self, tick, x, y, battery, steps):
        ids, features = candidates(self, tick, x, y, battery)
        checks = {name: visit_return(self, tick, x, y, battery, name) for name in ids[1:]}
        kept = [i for i, name in enumerate(ids) if name == "base" or checks[name] is not None]
        offered = tuple(ids[i] for i in kept)
        action = self.choose(offered, features[kept].copy())
        if isinstance(action, bool) or not isinstance(action, Integral) or not 0 <= int(action) < len(offered):
            raise ValueError("chooser must return a valid integer candidate index")
        target = offered[int(action)]
        self.feasibility.append({"tick": tick, "predicted_position": [x, y],
                                 "predicted_battery": battery, "original_ids": list(ids),
                                 "offered_ids": list(offered), "checks": checks,
                                 "effective_goal": target})
        self.route = [] if target == "base" else [target]
        self.need_plan = False
        self.last_plan = tick
        self.decision_count += 1


def run_episode(seed, choose, charge_aware, keep_replay=True):
    """Trusted runner adapted from Sölvi's RL adapter, with an explicit pilot type."""
    from lightlag_traverse.environment import TraverseEnvironment

    if type(charge_aware) is not bool:
        raise TypeError("charge_aware must be boolean")
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

    tools = Tools()
    started = time.monotonic()
    pilot = (FeasiblePilot if charge_aware else RLPilot)(tools, choose)
    while True:
        pilot.act()
        out = tools.advance(1)
        pilot.observe(out["packets"], out["current_tick"])
        if out["episode_complete"]:
            break
    result = env.evaluate()
    episode = {"seed": seed, "result": result, "reward": result["raw_score"] / result["max_available_value"],
               "decision_count": pilot.decision_count, "public_calls": sum(counts.values()),
               "calls_by_tool": dict(counts), "commands_by_action": dict(sent),
               "invalid_calls": invalid, "seconds": time.monotonic() - started}
    if keep_replay:
        episode["replay"] = env.replay()
    return episode, getattr(pilot, "feasibility", [])
