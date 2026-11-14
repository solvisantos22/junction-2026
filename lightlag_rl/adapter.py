"""Public-information target selection over an unchanged Traverse navigator.

The learned component selects a next target or base when the pilot replans.
Estimation, steering, timing, energy protection and command handling remain in
the existing Pilot. This is a hybrid controller, not learned low-level driving.
The actor receives only candidate IDs and the fourteen public-data features.
The in-process boundary is auditable; it is not a security sandbox.
"""

from __future__ import annotations

from collections import Counter
import math
from numbers import Integral
import time
from typing import Callable, Tuple

import numpy as np

from lightlag_traverse.pilot import Pilot


FEATURE_NAMES = (
    "is_home", "time_remaining", "battery_fraction", "position_uncertainty",
    "outbound_time", "outbound_energy", "return_time", "return_energy",
    "target_value", "arrival_value", "deadline_slack", "relative_x",
    "relative_y", "open_count",
)
Choose = Callable[[Tuple[str, ...], np.ndarray], int]


def _bounded(value):
    """Finite, bounded features, including a representation of unreachable home."""
    value = float(value)
    if math.isnan(value):
        raise ValueError("a public candidate feature is NaN")
    return min(2.0, max(-2.0, value))


def candidates(pilot, tick, x, y, battery):
    """Build actor inputs using only the pilot's public map and beliefs.

    Times use the mission horizon; energy uses capacity; uncertainty uses the
    public sampling radius; values use 10; positions use map width/height; open
    target count uses 46. All features are clipped to [-2, 2]. The mask excludes
    sampled/pending/unreachable targets and applies the stock greedy planner's
    public time-to-target-and-home criterion. It does not query simulator truth.
    Home is always present, including when the public model cannot route there.
    """
    horizon, capacity = pilot.horizon, pilot.capacity
    width, height = pilot.surface.width, pilot.surface.height
    sigma = pilot.predict(tick)[2]
    open_ids = sorted(pilot._open(tick))
    home_field = pilot.fields.get("base")
    ids, rows = [], []
    for name in ("base", *open_ids):
        home = name == "base"
        outbound_ticks, outbound_energy = pilot._to(name, x, y)
        if home:
            back_ticks, back_energy, value, arrival_value, slack = 0.0, 0.0, 0.0, 0.0, 1.0
        else:
            node = pilot.nodes[name]
            if home_field is None or node is None:
                continue
            back_ticks, back_energy = home_field.ticks[node], home_field.energy[node]
            if not all(math.isfinite(v) for v in (outbound_ticks, outbound_energy, back_ticks, back_energy)):
                continue
            arrival = tick + outbound_ticks + 1.0
            if arrival + back_ticks * pilot.opt["home_slack"] > horizon - pilot.opt["home_margin"]:
                continue
            target = pilot.targets[name]
            value = target["value"]
            deadline = target["deadline_tick"]
            arrival_value = value if deadline is None or arrival <= deadline - 2 else target["late_value"]
            slack = 1.0 if deadline is None else (deadline - arrival) / horizon
        gx, gy = pilot._spot(name)
        rows.append([
            float(home), (horizon - tick) / horizon, battery / capacity,
            sigma / pilot.rules["target_radius"], outbound_ticks / horizon,
            outbound_energy / capacity, back_ticks / horizon, back_energy / capacity,
            value / 10.0, arrival_value / 10.0, slack, (gx - x) / width,
            (gy - y) / height, len(open_ids) / 46.0,
        ])
        ids.append(name)
    features = np.asarray([[_bounded(v) for v in row] for row in rows], dtype=np.float64)
    return tuple(ids), features


class RLPilot(Pilot):
    """The only replaced decision is which next target the navigator pursues."""

    def __init__(self, tools, choose: Choose):
        self.choose = choose
        self.decision_count = 0
        # Keep the ordinary replan cadence for every learned/control chooser.
        # The overridden method below performs no route-search iterations.
        super().__init__(tools, {"route": "optimise"})

    def _plan(self, tick, x, y, battery, steps):
        ids, features = candidates(self, tick, x, y, battery)
        action = self.choose(ids, features)
        if isinstance(action, bool) or not isinstance(action, Integral) or not 0 <= int(action) < len(ids):
            raise ValueError("chooser must return a valid integer candidate index")
        target = ids[int(action)]
        self.route = [] if target == "base" else [target]
        self.need_plan = False
        self.last_plan = tick
        self.decision_count += 1


def greedy_choice(ids, features):
    """Value-per-tick control with the same candidates and navigator cadence.

    This comparator is not claimed to be byte-identical to the stock greedy
    pilot: the stock pilot requests another plan every tick when its route is
    empty, while every chooser here retains the ordinary replan cadence.
    The denominator uses the fixed, unmodified Traverse horizon of 420 ticks.
    """
    if len(ids) == 1:
        return 0
    scores = features[:, 9] / (features[:, 4] + 1.0 / 420.0)
    scores = scores.copy()
    scores[0] = -np.inf
    return int(np.argmax(scores))


def home_choice(ids, features):
    return 0


def run_episode(seed: int, choose: Choose, keep_replay: bool = False):
    """Trusted episode runner. Truth is used only for the terminal evaluation.

    The chooser sees no environment object, seed or evaluator reward. Errors
    propagate instead of being converted to low-scoring training samples.
    """
    from lightlag_traverse.environment import TraverseEnvironment

    env = TraverseEnvironment(seed)
    counts = Counter()
    invalid = []
    sent = Counter()

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
    pilot = RLPilot(tools, choose)
    while True:
        pilot.act()
        out = tools.advance(1)
        pilot.observe(out["packets"], out["current_tick"])
        if out["episode_complete"]:
            break
    result = env.evaluate()
    run = {
        "seed": seed, "result": result,
        "reward": result["raw_score"] / result["max_available_value"],
        "decision_count": pilot.decision_count, "public_calls": sum(counts.values()),
        "calls_by_tool": dict(counts), "commands_by_action": dict(sent),
        "invalid_calls": invalid, "seconds": time.monotonic() - started,
    }
    if keep_replay:
        run["replay"] = env.replay()
    return run
