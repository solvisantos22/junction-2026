"""The reference controller and the scripted baselines.

All of them use the same planner and the same public information. They differ only
in the few switches of `Strategy`, so a score difference between two of them is
attributable to one behaviour:

- reference:          replays commands in transit, learns slip, one command per tick
- stale_telemetry:    same, but treats the last packet as the present
- move_and_wait:      same, but waits to see each command land before the next
- open_loop_nominal:  plans from the briefing with mid-range slip and never looks again
- stop_early:         the reference, but it stops acting after a fixed tick
- no_op:              never sends a command
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Sequence, Set, Tuple

from .estimator import SlipEstimator
from .model import Command, Packet, Rules, SentCommand, Target, World, distance, heading_to
from .physics import simulate_drive, wheel_for_distance
from .planner import BASE, Route, RoutePlanner

STOP_EVENTS = ("safety_stop", "battery_dead")


@dataclass(frozen=True)
class Strategy:
    name: str
    predict_in_transit: bool = True
    confirm_each_command: bool = False
    learn_slip: bool = True
    use_telemetry: bool = True
    stop_after_tick: Optional[int] = None
    acts: bool = True


REFERENCE = Strategy("reference")
STALE_TELEMETRY = Strategy("stale_telemetry", predict_in_transit=False)
MOVE_AND_WAIT = Strategy("move_and_wait", confirm_each_command=True)
OPEN_LOOP_NOMINAL = Strategy("open_loop_nominal", learn_slip=False, use_telemetry=False)
STOP_EARLY = Strategy("stop_early", stop_after_tick=5)
NO_OP = Strategy("no_op", acts=False)

ALL_STRATEGIES: Tuple[Strategy, ...] = (
    REFERENCE, MOVE_AND_WAIT, STALE_TELEMETRY, OPEN_LOOP_NOMINAL, STOP_EARLY, NO_OP,
)


@dataclass
class Belief:
    """Where the controller thinks the rover will be when its next command executes."""

    tick: int
    x: float
    y: float
    battery: float
    sampled: Set[str]
    error_m: float = 0.0  # rough bound on position error from unconfirmed driving
    alive: bool = True


@dataclass
class Tuning:
    cell: float = 0.5
    hazard_margin: float = 0.4
    hazard_margin_per_delay_tick: float = 0.1
    caution: float = 0.5  # how many slip half-widths to add when budgeting energy
    energy_margin: float = 0.06
    battery_reserve: float = 1.5
    replan_every: int = 4


class Controller:
    """One decision per call: commands to uplink now, and how many ticks to advance."""

    def __init__(self, strategy: Strategy = REFERENCE, tuning: Optional[Tuning] = None) -> None:
        self.strategy = strategy
        self.tuning = tuning or Tuning()
        self.name = strategy.name

    # -- lifecycle -----------------------------------------------------------------

    def reset(self, rules: Rules, world: World, briefing: Sequence[Packet]) -> None:
        self.rules = rules
        self.world = world
        self.estimator = SlipEstimator(rules, learn=self.strategy.learn_slip)
        self.sent: List[SentCommand] = []
        self.by_tick: Dict[int, Packet] = {}
        self.latest: Optional[Packet] = None
        self.dead = False
        self.route: Optional[Route] = None
        self._replan = True
        self._await_tick: Optional[int] = None
        self._last_route_tick = -10**9
        self.trace: List[Dict[str, object]] = []
        margin = self.tuning.hazard_margin + self.tuning.hazard_margin_per_delay_tick * rules.delay
        self.planner = RoutePlanner(world, rules, self.tuning.cell, margin) if self.strategy.acts else None
        self._optimist: Optional[RoutePlanner] = None
        self._probe_target: Optional[str] = None
        self._probe_deadline: Optional[int] = None
        for packet in briefing:
            self._ingest(packet, force=True)

    def on_ack(self, commands: Sequence[Command], exec_ticks: Sequence[int], sent_tick: int) -> None:
        for command, exec_tick in zip(commands, exec_ticks):
            self.sent.append(SentCommand(command, sent_tick, exec_tick))
        if self.strategy.confirm_each_command and exec_ticks:
            self._await_tick = max(exec_ticks)

    # -- telemetry -----------------------------------------------------------------

    def _ingest(self, packet: Packet, force: bool = False) -> None:
        if not (force or self.strategy.use_telemetry):
            return
        if packet.tick in self.by_tick:
            return
        self.by_tick[packet.tick] = packet
        if self.latest is None or packet.tick > self.latest.tick:
            self.latest = packet
        if not packet.alive:
            self.dead = True
        previous = self.by_tick.get(packet.tick - 1)
        if previous is not None and packet.wheel_m > 0.0:
            terrain = self._single_terrain(previous.x, previous.y, packet.x, packet.y)
            if terrain is not None:
                self.estimator.observe(terrain, packet.wheel_m, packet.moved_m)
        if any(event in STOP_EVENTS for event in packet.events):
            # A stop clears everything uplinked before that tick. Commands sent at or
            # after it were queued afterwards and still run.
            for sent in self.sent:
                if sent.sent_tick < packet.tick < sent.exec_tick:
                    sent.cancelled = True
            self._replan = True

    def _single_terrain(self, ax: float, ay: float, bx: float, by: float) -> Optional[str]:
        """Terrain of a drive from A to B, or None if it crossed a boundary."""
        length = distance(ax, ay, bx, by)
        first = self.world.terrain_at(ax, ay)
        pieces = max(1, int(math.ceil(length / 0.05)))
        for i in range(1, pieces):
            t = i / pieces
            if self.world.terrain_at(ax + (bx - ax) * t, ay + (by - ay) * t) != first:
                return None
        return first

    # -- prediction ----------------------------------------------------------------

    def _next_exec_tick(self, tick: int) -> int:
        reserved = max((s.exec_tick for s in self.sent), default=0)
        return max(tick + self.rules.delay + 1, reserved + 1)

    def believe(self, tick: int) -> Belief:
        """State just before the next command sent now would execute."""
        latest = self.latest
        assert latest is not None, "reset() must receive the briefing packet"
        target_tick = self._next_exec_tick(tick) - 1
        belief = Belief(latest.tick, latest.x, latest.y, latest.battery, set(latest.sampled), alive=latest.alive)
        if not self.strategy.predict_in_transit:
            belief.tick = target_tick
            return belief
        pending = {s.exec_tick: s for s in self.sent if not s.cancelled and s.exec_tick > latest.tick}
        slip_of = self.estimator.mean
        dropped_before: Optional[int] = None
        for t in range(latest.tick + 1, target_tick + 1):
            belief.tick = t
            belief.battery -= self.rules.idle_cost
            if belief.battery <= 0.0:
                belief.battery = 0.0
                belief.alive = False
                break
            sent = pending.get(t)
            if sent is None or (dropped_before is not None and sent.sent_tick < dropped_before):
                continue
            command = sent.command
            if command.kind == "drive":
                result = simulate_drive(
                    self.world, self.rules, slip_of, belief.x, belief.y,
                    command.heading_deg, command.metres, belief.battery,
                )
                belief.x, belief.y = result.x, result.y
                belief.battery -= result.energy
                if self.strategy.use_telemetry:
                    # An open-loop controller trusts its model, so it never hedges.
                    for terrain, wheel in result.wheel_by_terrain.items():
                        belief.error_m += wheel * (self.estimator.halfwidth(terrain) + 0.5 * self.rules.slip_noise)
                if result.stopped == "hazard":
                    dropped_before = t
            elif command.kind == "sample":
                # Published rule: a sample always costs energy, even when it fails.
                enough = belief.battery >= self.rules.sample_cost
                belief.battery = max(0.0, belief.battery - self.rules.sample_cost)
                if belief.battery <= 0.0:
                    belief.alive = False
                    break
                target = self._nearest_unsampled(belief)
                if (enough and target is not None
                        and distance(belief.x, belief.y, target.x, target.y) <= self.rules.sample_radius):
                    belief.sampled.add(target.id)
        belief.tick = target_tick
        return belief

    def _nearest_unsampled(self, belief: Belief) -> Optional[Target]:
        candidates = [t for t in self.world.targets if t.id not in belief.sampled]
        if not candidates:
            return None
        return min(candidates, key=lambda t: distance(belief.x, belief.y, t.x, t.y))

    # -- decisions -----------------------------------------------------------------

    def step(self, tick: int, new_packets: Sequence[Packet]) -> Tuple[List[Command], int]:
        for packet in new_packets:
            self._ingest(packet)
        remaining_ticks = self.rules.horizon - tick
        idle = max(1, min(self.rules.max_advance, remaining_ticks))
        if not self.strategy.acts or self.dead:
            return [], idle
        if self.strategy.stop_after_tick is not None and tick >= self.strategy.stop_after_tick:
            return [], idle
        if self._await_tick is not None:
            assert self.latest is not None
            if self.latest.tick < self._await_tick:
                arrives = self._await_tick + self.rules.delay
                return [], max(1, min(self.rules.max_advance, arrives - tick, remaining_ticks))
            self._await_tick = None
        if self._next_exec_tick(tick) > self.rules.horizon:
            return [], idle
        belief = self.believe(tick)
        if not belief.alive:
            return [], idle
        command = self._decide(belief, tick)
        if command is None:
            return [], 1
        return [command], 1

    def _ticks_per_command(self) -> int:
        return 2 * self.rules.delay + 1 if self.strategy.confirm_each_command else 1

    def _choose_route(self, belief: Belief, tick: int) -> None:
        assert self.planner is not None
        rebuilt = self.planner.update(lambda name: self.estimator.cautious(name, self.tuning.caution))
        due = tick - self._last_route_tick >= self.tuning.replan_every
        if not (self._replan or rebuilt or due or self.route is None):
            return
        remaining = [t for t in self.world.targets if t.id not in belief.sampled]
        budget = (
            belief.battery
            - self.rules.idle_cost * (self.rules.horizon - belief.tick)
            - self.tuning.battery_reserve
        )
        ticks_left = self.rules.horizon - belief.tick
        banked = sum(t.value for t in self.world.targets if t.id in belief.sampled)
        best = self.planner.best_route(
            (belief.x, belief.y), remaining, budget, ticks_left,
            self._ticks_per_command(), self.tuning.energy_margin, banked,
        )
        probe = self._probe_first_route(belief, remaining, budget, ticks_left, banked)
        if probe is not None and probe.score > best.score + 1e-9:
            best = probe
            self._replan = True  # an explicit choice to gather information; do not keep the old route
            self._probe_target = probe.targets[0]
            self._probe_deadline = None
        current = self.route
        if current is not None and not self._replan:
            keep = tuple(t for t in current.targets if t not in belief.sampled)
            energy, commands = self.planner.evaluate((belief.x, belief.y), keep, current.end_at_base)
            still_ok = (
                energy * (1.0 + self.tuning.energy_margin) <= budget
                and commands * self._ticks_per_command() <= ticks_left
            )
            kept_score = (banked + sum(t.value for t in remaining if t.id in keep)) * (
                1.0 if current.end_at_base else 0.5
            )
            if still_ok and best.score <= kept_score + 1e-9:
                best = Route(keep, current.end_at_base, kept_score, energy, commands)
        if banked > 0.0 and not best.end_at_base:
            # Ending away from base halves everything collected, so the last leg home
            # may dip into the reserve as long as the rover still survives to the end.
            energy, commands = self.planner.evaluate((belief.x, belief.y), (), True)
            if (energy <= budget + self.tuning.battery_reserve - 0.3
                    and commands * self._ticks_per_command() <= ticks_left
                    and banked > best.score + 1e-9):
                best = Route((), True, banked, energy, commands)
        self.route = best
        self._replan = False
        self._last_route_tick = tick

    def _probe_first_route(
        self, belief: Belief, remaining: Sequence[Target], budget: float, ticks_left: int, banked: float
    ) -> Optional[Route]:
        """A more ambitious route that is worth trying because it learns the unknown first.

        While a terrain's slip is still unobserved, the cautious budget may rule out a
        route that would be fine on a low-slip seed. If such a route starts with a
        target lying on the unobserved terrain, the rover learns the slip on the way
        there and can re-plan with real numbers. It is only taken when the round trip
        to that first target is affordable even under the cautious estimate, so the
        value already collected is never put at risk.
        """
        if not (self.strategy.learn_slip and self.strategy.use_telemetry):
            return None
        # Only terrains whose published range is wide enough to change the plan.
        unknown = [
            name for name, spec in self.rules.terrains.items()
            if not self.estimator.observed(name) and spec.slip_halfwidth > 0.05
        ]
        if not unknown:
            return None
        on_unknown = [t.id for t in remaining if self.world.terrain_at(t.x, t.y) in unknown]
        if not on_unknown:
            return None
        if self._optimist is None:
            self._optimist = RoutePlanner(self.world, self.rules, self.tuning.cell, self.planner.grid.margin)
        self._optimist.update(lambda name: self.estimator.cautious(name, -self.tuning.caution))
        start = (belief.x, belief.y)
        route = self._optimist.best_route(
            start, remaining, budget, ticks_left, self._ticks_per_command(),
            self.tuning.energy_margin, banked, first_among=on_unknown,
        )
        if not route.targets:
            return None
        energy, commands = self.planner.evaluate(start, route.targets[:1], True)
        safe = (
            energy * (1.0 + self.tuning.energy_margin) <= budget
            and commands * self._ticks_per_command() <= ticks_left
        )
        return route if safe else None

    def _still_probing(self, belief: Belief, tick: int) -> bool:
        """True while an ambitious route must not go past its first target.

        The route was chosen on a hopeful slip estimate. Until telemetry shows the
        real slip, only the first target is safe, so the rover waits there. The wait
        is bounded in case no clean reading ever arrives.
        """
        if self._probe_target is None:
            return False
        target = self.world.target(self._probe_target)
        assert target is not None
        if self.estimator.observed(self.world.terrain_at(target.x, target.y)):
            self._probe_target = None
            self._replan = True
            return False
        if self._probe_target not in belief.sampled:
            return False
        if self._probe_deadline is None:
            self._probe_deadline = tick + 2 * self.rules.delay + 3
        if tick >= self._probe_deadline:
            self._probe_target = None
            self._replan = True
            return False
        return True

    def _decide(self, belief: Belief, tick: int) -> Optional[Command]:
        assert self.planner is not None
        if self._still_probing(belief, tick):
            self._note(tick, belief, "hold_for_slip_reading", self._probe_target or "")
            return None
        self._choose_route(belief, tick)
        route = self.route
        assert route is not None
        goal = next((t for t in route.targets if t not in belief.sampled), None)
        here = (belief.x, belief.y)
        if goal is not None:
            target = self.world.target(goal)
            assert target is not None
            gap = distance(belief.x, belief.y, target.x, target.y)
            # A failed sample still costs energy, so allow twice the error bound.
            if gap + 2.0 * belief.error_m <= self.rules.sample_radius - 0.05:
                self._note(tick, belief, "sample", goal)
                return Command.sample()
            if gap <= 0.15:
                self._note(tick, belief, "hold_for_telemetry", goal)
                return None
            key = goal
        elif route.end_at_base:
            gap = distance(belief.x, belief.y, self.world.base[0], self.world.base[1])
            if gap <= 0.15:
                return None
            key = BASE
        else:
            return None
        leg = self.planner.leg(here, key)
        if not leg.reachable or not leg.waypoints:
            self._replan = True
            return None
        waypoint = next((w for w in leg.waypoints if distance(here[0], here[1], w[0], w[1]) > 0.1), leg.waypoints[-1])
        heading = heading_to(here[0], here[1], waypoint[0], waypoint[1])
        wheel = wheel_for_distance(
            self.world, self.rules, self.estimator.mean, here[0], here[1], heading,
            distance(here[0], here[1], waypoint[0], waypoint[1]),
        )
        wheel = min(self.rules.max_drive, wheel)
        if wheel < 0.02:
            return None
        self._note(tick, belief, "drive", key)
        return Command.drive(heading, wheel)

    def _note(self, tick: int, belief: Belief, action: str, goal: str) -> None:
        self.trace.append({
            "tick": tick, "action": action, "goal": goal,
            "for_tick": belief.tick,  # the tick this belief is about
            "believed": (round(belief.x, 3), round(belief.y, 3)),
            "seen_tick": self.latest.tick if self.latest else None,
            "error_m": round(belief.error_m, 3),
            "slip": self.estimator.snapshot(),
        })


def make(strategy: Strategy, tuning: Optional[Tuning] = None, **overrides: object) -> Controller:
    return Controller(replace(strategy, **overrides) if overrides else strategy, tuning)
