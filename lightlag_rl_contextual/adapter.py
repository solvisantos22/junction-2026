"""Context and teacher data from public beliefs, above the unchanged navigator."""

from collections import Counter
import math
import time

import numpy as np

from lightlag_rl.adapter import candidates, greedy_choice
from lightlag_rl_feasible.adapter import visit_return
from lightlag_rl_persistence import GoalChooser
from lightlag_traverse.pilot import Pilot
from .model import Policy


def context_candidates(pilot, tick, x, y, battery):
    ids, original = candidates(pilot, tick, x, y, battery)
    checks = {name: visit_return(pilot, tick, x, y, battery, name) for name in ids[1:]}
    keep = [i for i, name in enumerate(ids) if name == "base" or checks[name] is not None]
    offered = tuple(ids[i] for i in keep)
    rows = []
    for i in keep:
        name = ids[i]
        check = checks.get(name)
        charge = ([0.] * 4 if name == "base" else
                  [(check["finish_tick"] - tick) / pilot.horizon,
                   (check["sample_tick"] - tick) / pilot.horizon,
                   check["after_sample_battery"] / pilot.capacity,
                   (check["limit_tick"] - check["finish_tick"]) / pilot.horizon])
        node = pilot.nodes.get(name)
        peers = []
        for other in offered[1:]:
            if other == name:
                continue
            dt = pilot._to(other, x, y)[0] if node is None else pilot.fields[other].ticks[node]
            if math.isfinite(dt):
                peers.append((dt, checks[other]["estimated_value"]))
        onward = [sum(value / 10. / (1. + dt / 20.) for dt, value in peers) / 46.,
                  min((dt for dt, _ in peers), default=pilot.horizon) / pilot.horizon]
        rows.append([*original[i], *charge, *onward])
    local = np.clip(np.asarray(rows, dtype=float), -2., 2.)
    science = local[1:]
    mean = science.mean(axis=0) if len(science) else np.zeros(20)
    maximum = science.max(axis=0) if len(science) else np.zeros(20)
    features = np.concatenate([local, np.tile(mean, (len(local), 1)),
                               np.tile(maximum, (len(local), 1))], axis=1)
    if not np.isfinite(features).all():
        raise ValueError("nonfinite public context")
    return offered, features, checks


class ContextPilot(Pilot):
    def __init__(self, tools, choose=None, teacher=False):
        self.teacher = teacher
        self.teacher_action = None
        self.chooser = GoalChooser(self._teacher_choose if teacher else choose, persistent=True)
        self.planning = []
        self.decision_count = 0
        super().__init__(tools, {"route": "optimise"})

    def _teacher_choose(self, ids, features):
        return self.teacher_action

    def _plan(self, tick, x, y, battery, steps):
        ids, features, checks = context_candidates(self, tick, x, y, battery)
        teacher_route = None
        if self.teacher:
            if self.chooser.held_goal in ids:
                self.teacher_action = ids.index(self.chooser.held_goal)
            else:
                Pilot._plan(self, tick, x, y, battery, steps)
                teacher_route = self.route.copy()
                chosen = next((name for name in teacher_route if name in ids), "base")
                self.teacher_action = ids.index(chosen)
        action = self.chooser(ids, features)
        target = ids[action]
        self.planning.append({"tick": tick, "position": [x, y], "battery": battery,
                              "checks": checks, "teacher_route": teacher_route, "goal": target})
        self.route = [] if target == "base" else [target]
        self.need_plan = False
        self.last_plan = tick
        self.decision_count += 1


def executed_decisions(decisions):
    """A retained random proposal did not choose an action and gets no gradient."""
    return [{"ids": d["ids"], "features": d["features"], "action": d["proposed_action"]}
            for d in decisions if d["reason"] != "retain"]


def run_episode(seed, mode, policy_state=None, policy_seed=0):
    from lightlag_traverse.environment import TraverseEnvironment

    if mode not in ("policy", "teacher", "greedy", "reference"):
        raise ValueError("unknown rollout mode")
    policy = Policy.from_state(policy_state) if mode == "policy" else None
    rng = np.random.default_rng(policy_seed)
    env = TraverseEnvironment(seed)
    calls, commands, invalid = Counter(), Counter(), []

    class Tools:
        def _call(self, name, *args):
            calls[name] += 1
            try:
                result = getattr(env, name)(*args)
            except ValueError as error:
                invalid.append({"tool": name, "error": str(error)})
                raise
            if name == "uplink":
                commands.update(ack["command"]["action"] for ack in result)
            return result
        def rules(self): return self._call("rules")
        def map(self): return self._call("map")
        def telemetry_log(self): return self._call("telemetry_log")
        def uplink(self, commands): return self._call("uplink", commands)
        def advance(self, ticks=1): return self._call("advance", ticks)

    def choose(ids, features):
        return policy.choose(features, rng) if policy else greedy_choice(ids, features)

    started = time.monotonic()
    tools = Tools()
    pilot = Pilot(tools) if mode == "reference" else ContextPilot(tools, choose, teacher=mode == "teacher")
    while True:
        pilot.act()
        out = tools.advance(1)
        pilot.observe(out["packets"], out["current_tick"])
        if out["episode_complete"]:
            break
    result = env.evaluate()
    decisions = [] if mode == "reference" else pilot.chooser.decisions
    return {"seed": seed, "mode": mode, "policy_seed": policy_seed, "result": result,
            "reward": result["raw_score"] / result["max_available_value"],
            "public_calls": dict(calls), "commands_by_action": dict(commands),
            "invalid_calls": invalid, "decisions": decisions,
            "planning": [] if mode == "reference" else pilot.planning,
            "trajectory": executed_decisions(decisions), "replay": env.replay(),
            "seconds": time.monotonic() - started}
