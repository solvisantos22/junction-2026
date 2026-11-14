"""Lightlag Traverse: one long mission across Mars-like ground, through the team's five tools.

The agent-facing surface is the team's: `rules`, `map`, `telemetry_log`, `uplink`, `advance`,
with the same commands, the same command queue behind a signal delay and the same scoring
(value of the samples, times 1 at the lander, 0.5 alive elsewhere, 0 if the battery ran out,
divided by all the value there was). What is new is the world behind them:

  * the ground is a height grid 600 m by 400 m, not a flat 40 m square;
  * slip, sideways slide and energy depend on the slope under the wheels and the terrain class;
  * ground steeper than `max_tilt` stops the rover, so crater walls and the scarp have to be
    driven around or through their passes;
  * the battery is charged by the sun, which climbs and sinks over the mission, through panels
    whose efficiency is hidden inside a published range;
  * a mission is 420 ticks and about forty-five targets, with deadlines, and more appear on the way.

`evaluate()` and `replay()` are for the evaluator only. Standard library only, Python 3.9+.
"""

from __future__ import annotations

import math
import random
from collections import deque
from copy import deepcopy
from typing import Any, Dict, List, Optional

from lightlag.model import MAX_BATCH, MAX_METRES, decode_command

from .surface import PHYSICS, TERRAIN_CODES, Surface, drive
from .terrain import GENERATOR, TraverseWorld, make_world

MISSION: Dict[str, Any] = {
    "delay_ticks": 3,
    "max_ticks": 420,
    "battery_capacity": 100.0,
    "initial_battery": 100.0,
    "idle_cost": 0.15,
    "sample_cost": 2.0,
    "target_radius": 2.5,
    "base_radius": 4.0,
    "late_fraction": 0.25,
    "solar_peak": 2.8,
    "solar_efficiency_range": [0.8, 1.0],
    "sun_margin_ticks": 56,
}

SENSING: Dict[str, float] = {
    "position_noise_m": 1.0,         # std dev, per axis, of every reported position fix
    "visual_odometry_noise": 0.05,   # std dev of the relative error of reported visual odometry
    "heading_bias_deg": 5.0,         # hidden bias at launch, uniform in +- this
    "heading_bias_walk_deg": 0.2,    # the bias takes a Gaussian random-walk step before every executed drive
    "heading_noise_deg": 1.5,        # plus independent Gaussian noise on every executed drive
}


def sun(tick: float, mission: Dict[str, Any] = MISSION) -> float:
    """Share of peak sunlight at a tick: the sun is up for the whole mission, highest at its middle."""
    margin = mission["sun_margin_ticks"]
    return math.sin(math.pi * (tick + margin) / (mission["max_ticks"] + 2 * margin))


class TraverseEnvironment:
    def __init__(self, seed: int = 0, world: Optional[TraverseWorld] = None,
                 mission: Optional[Dict[str, Any]] = None) -> None:
        if type(seed) is not int:
            raise ValueError("seed must be an integer")
        self._seed = seed
        self._mission = dict(MISSION, **(mission or {}))
        self._world = world if world is not None else make_world(seed, self._mission["max_ticks"])
        self._surface: Surface = self._world.surface()
        self._plans = {target.id: target for target in self._world.targets}
        rng = random.Random("lightlag-traverse-hidden:{}".format(seed))
        self._slip = {name: rng.uniform(*limits) for name, limits in PHYSICS["slip_base_ranges"].items()}
        self._efficiency = rng.uniform(*self._mission["solar_efficiency_range"])
        self._heading_bias = rng.uniform(-SENSING["heading_bias_deg"], SENSING["heading_bias_deg"])
        self._initial_heading_bias = self._heading_bias
        self._heading_errors: List[Dict[str, float]] = []
        self._tick = 0
        self._x, self._y = self._world.base
        self._heading = 0.0
        self._battery = float(self._mission["initial_battery"])
        self._dead = False
        self._sampled: set = set()
        self._sample_ticks: Dict[str, int] = {}
        self._commands: deque = deque()
        self._reserved_until = 0
        self._sent: List[Dict[str, Any]] = []
        self._pending_packets: deque = deque()
        initial = self._snapshot(0.0, 0.0, 0.0, [])
        initial["received_tick"] = 0          # the launch state is known, not a delayed measurement
        self._received = [initial]
        self._truth = [deepcopy(initial)]

    # ---- public tools -------------------------------------------------------------
    def rules(self) -> Dict[str, Any]:
        m = self._mission
        return {
            "version": "lightlag-traverse-v1",
            **{name: m[name] for name in ("delay_ticks", "max_ticks", "battery_capacity", "initial_battery",
                                         "idle_cost", "sample_cost", "target_radius", "base_radius",
                                         "solar_peak", "solar_efficiency_range", "sun_margin_ticks")},
            "supported_actions": ["drive", "sample", "wait"],
            "scripting_allowed": True,
            "first_execution_tick": "sent_tick + delay_ticks + 1; FIFO, one command per tick",
            "telemetry_arrival_tick": "state_tick + delay_ticks; tick 0 is the initial briefing",
            "max_commands_per_uplink": MAX_BATCH,
            "max_metres_per_drive": MAX_METRES,
            "max_advance_ticks": 5,
            "heading": ("0 degrees east (+x), 90 north (+y); each executed drive travels at the commanded "
                        "heading plus a heading error: a hidden bias, uniform in +-heading_bias_deg at launch, "
                        "which takes a Gaussian random-walk step of heading_bias_walk_deg before every executed "
                        "drive, plus independent Gaussian noise of heading_noise_deg; telemetry heading_deg "
                        "reports the commanded heading"),
            "ground": ("map() gives elevation_cm[j][i], the height in centimetres at x = i * cell_m, "
                       "y = j * cell_m, and terrain[j][i], the class code of the grid cell whose south-west "
                       "corner is that vertex. Height between vertices is bilinear inside the cell. The slope "
                       "at a point is the gradient of that bilinear surface: d/dx = ((h10 - h00) * (1 - ty) + "
                       "(h11 - h01) * ty) / cell_m and d/dy = ((h01 - h00) * (1 - tx) + (h11 - h10) * tx) / "
                       "cell_m, with tx, ty the point's fractions inside its cell and h10 the vertex to the east"),
            "physics": deepcopy(PHYSICS),
            "drive": ("a drive of M wheel metres is integrated in steps of segment_m, with the ground sampled "
                      "where each step starts: grade = slope along the travelled heading, cross = slope to the "
                      "left of it; slip = clip(slip_base[terrain] + slip_grade_gain[terrain] * max(0, grade) + "
                      "noise, 0, slip_max), with slip_base[terrain] hidden inside slip_base_ranges and fixed "
                      "for the mission, and noise one uniform draw in +-slip_noise per drive; the rover moves "
                      "step * (1 - slip) along the heading and step * side_slip_gain[terrain] * cross to the "
                      "right of it, which is downhill across the heading"),
            "safety_stop": ("a step that would leave the map, or end where the slope is steeper than max_tilt, "
                            "is not taken: the rover stops at the last safe position and every queued command "
                            "is cleared; their reserved ticks stay reserved"),
            "energy": ("each tick, in this order: the battery gains solar_peak * efficiency * sin(pi * (tick + "
                       "sun_margin_ticks) / (max_ticks + 2 * sun_margin_ticks)), capped at battery_capacity, "
                       "with efficiency hidden inside solar_efficiency_range and fixed for the mission; then "
                       "idle_cost; then the command. A drive costs drive_cost_per_wheel_m[terrain] per wheel "
                       "metre plus climb_cost_per_m per metre of height gained. A sample costs sample_cost, "
                       "also when it fails. A battery that reaches 0 ends the rover for good"),
            "sampling": ("pay sample_cost; collect the nearest unsampled active target within target_radius; "
                         "a discovered target is active from its appear tick"),
            "sample_windows": {"late_fraction": m["late_fraction"],
                               "deadline": "deadline_tick per target in map(); null means no deadline"},
            "discoveries": ("new targets appear mid-mission; a target_discovered event in the telemetry "
                            "packet for its appear tick announces it, so it arrives delay_ticks later, and "
                            "map() lists it from then on"),
            "reward": ("sum over sampled targets of value if the sample executed at or before deadline_tick, "
                       "otherwise value * late_fraction; times 1 within base_radius of the lander, 0.5 alive "
                       "elsewhere, 0 if the battery ran out; divided by the value of every target of the "
                       "mission, discovered or not; scored at max_ticks"),
            "sensing": dict(SENSING),
            "telemetry": ("one packet per tick: position = true position + Gaussian noise of position_noise_m "
                          "per axis, clipped to the map (the tick-0 briefing is exact); battery and charge "
                          "(the solar energy gained that tick) are exact; terrain is the class under the "
                          "rover and tilt the slope there; wheel_odometry is the wheel metres of the drive "
                          "and visual_odometry the ground distance moved * (1 + Gaussian noise of "
                          "visual_odometry_noise)"),
            "scoring_position": "sampling, the return to the lander and safety stops use the true position",
            "map_generator": deepcopy(GENERATOR),
        }

    def map(self) -> Dict[str, Any]:
        world = self._world
        return {
            "width": world.width, "height": world.height, "cell_m": world.cell,
            "elevation_cm": [list(row) for row in world.elevation_cm],
            "terrain": list(world.terrain),
            "terrain_codes": dict(TERRAIN_CODES),
            "base": list(world.base),
            "targets": [self._public_target(t) for t in world.targets if self._announced(t)],
        }

    def telemetry_log(self) -> List[Dict[str, Any]]:
        return deepcopy(self._received)

    def uplink(self, commands: Any) -> List[Dict[str, Any]]:
        if not isinstance(commands, list) or not 1 <= len(commands) <= MAX_BATCH:
            raise ValueError("commands must be a list of 1..{} commands".format(MAX_BATCH))
        if self._tick >= self._mission["max_ticks"]:
            raise ValueError("episode complete")
        decoded = [decode_command(command) for command in commands]
        first_tick = max(self._tick + self._mission["delay_ticks"] + 1, self._reserved_until + 1)
        if first_tick + len(decoded) - 1 > self._mission["max_ticks"]:
            raise ValueError("commands would execute beyond the episode horizon")
        acknowledgements = [
            {"command_id": len(self._sent) + index + 1, "sent_tick": self._tick,
             "execute_tick": first_tick + index, "command": command}
            for index, command in enumerate(decoded)
        ]
        self._commands.extend(deepcopy(acknowledgements))
        self._sent.extend(deepcopy(acknowledgements))
        self._reserved_until = acknowledgements[-1]["execute_tick"]
        return acknowledgements

    def advance(self, ticks: int = 1) -> Dict[str, Any]:
        if type(ticks) is not int or not 1 <= ticks <= 5:
            raise ValueError("ticks must be an integer from 1 to 5")
        arrived = []
        for _ in range(min(ticks, self._mission["max_ticks"] - self._tick)):
            self._step()
            while self._pending_packets and self._pending_packets[0]["received_tick"] <= self._tick:
                packet = self._pending_packets.popleft()
                self._received.append(packet)
                arrived.append(packet)
        return {"current_tick": self._tick,
                "episode_complete": self._tick == self._mission["max_ticks"],
                "packets": deepcopy(arrived)}

    # ---- evaluator-only -----------------------------------------------------------
    def evaluate(self) -> Dict[str, Any]:
        """Trusted evaluator API. Never expose this as an agent tool."""
        if self._tick != self._mission["max_ticks"]:
            raise ValueError("evaluation requires the fixed episode horizon")
        alive = not self._dead
        at_base = math.hypot(self._x - self._world.base[0], self._y - self._world.base[1]) <= self._mission["base_radius"]
        samples, value = [], 0.0
        for target in self._world.targets:
            if target.id not in self._sampled:
                continue
            tick = self._sample_ticks[target.id]
            on_time = target.deadline_tick is None or tick <= target.deadline_tick
            credited = target.value if on_time else target.value * self._mission["late_fraction"]
            value += credited
            samples.append({"target_id": target.id, "tick": tick, "on_time": on_time, "credited_value": credited})
        factor = (1.0 if at_base else 0.5) if alive else 0.0
        return {"tick": self._tick, "sampled_targets": sorted(self._sampled), "sampled_value": value,
                "survival_factor": factor, "raw_score": value * factor, "alive": alive, "at_base": at_base,
                "max_available_value": sum(target.value for target in self._world.targets),
                "samples": samples, "mission_profile": "traverse"}

    def replay(self) -> Dict[str, Any]:
        """Evaluator-only artifact containing hidden truth, after the horizon."""
        world = self._world
        return deepcopy({
            "version": "lightlag-traverse-replay-v1", "seed": self._seed,
            "config": dict(self._mission), "physics": PHYSICS, "sensing": SENSING,
            "world": {"width": world.width, "height": world.height, "cell_m": world.cell,
                      "elevation_cm": [list(row) for row in world.elevation_cm], "terrain": list(world.terrain),
                      "base": list(world.base), "features": world.features,
                      "targets": [self._public_target(t) for t in world.targets]},
            "hidden": {"slip_base": self._slip, "solar_efficiency": self._efficiency,
                       "initial_heading_bias_deg": self._initial_heading_bias,
                       "heading_errors": self._heading_errors},
            "commands": self._sent, "states": self._truth, "received_telemetry": self._received,
            "result": self.evaluate(),
        })

    # ---- internals ----------------------------------------------------------------
    def _announced(self, target) -> bool:
        return target.appear_tick == 0 or self._tick >= target.appear_tick + self._mission["delay_ticks"]

    def _public_target(self, target) -> Dict[str, Any]:
        late = target.value * self._mission["late_fraction"] if target.deadline_tick is not None else target.value
        return {"id": target.id, "x": target.x, "y": target.y, "value": target.value,
                "deadline_tick": target.deadline_tick, "late_value": late, "appear_tick": target.appear_tick}

    def _spend(self, amount: float) -> None:
        self._battery = max(0.0, self._battery - amount)
        if self._battery < 1e-10:
            self._battery = 0.0

    def _step(self) -> None:
        self._tick += 1
        events: List[Dict[str, Any]] = []
        wheel = visual = charge = 0.0
        if not self._dead:
            m = self._mission
            before = self._battery
            self._battery = min(m["battery_capacity"],
                                self._battery + m["solar_peak"] * self._efficiency * sun(self._tick, m))
            charge = self._battery - before
            self._spend(m["idle_cost"])
            if self._battery > 0 and self._commands and self._commands[0]["execute_tick"] == self._tick:
                queued = self._commands.popleft()
                command = queued["command"]
                events.append({"type": "command_executed", "command_id": queued["command_id"]})
                if command["action"] == "drive":
                    wheel, visual = self._drive(command, events)
                elif command["action"] == "sample":
                    self._sample(events)
            if self._battery == 0:
                self._dead = True
                self._commands.clear()
                events.append({"type": "battery_depleted"})
        snapshot = self._snapshot(wheel, visual, charge, events)
        self._truth.append(deepcopy(snapshot))
        self._pending_packets.append(self._measured(snapshot))

    def _drive(self, command: Dict[str, Any], events: List[Dict[str, Any]]):
        commanded = command["heading_deg"]
        rng = random.Random("{}:heading:{}".format(self._seed, self._tick))
        self._heading_bias += rng.gauss(0.0, SENSING["heading_bias_walk_deg"])
        error = self._heading_bias + rng.gauss(0.0, SENSING["heading_noise_deg"])
        self._heading_errors.append({"tick": self._tick, "error_deg": round(error, 6),
                                     "bias_deg": round(self._heading_bias, 6)})
        noise = random.Random("{}:drive:{}".format(self._seed, self._tick)).uniform(
            -PHYSICS["slip_noise"], PHYSICS["slip_noise"])
        moved = drive(self._surface, PHYSICS, self._x, self._y, commanded + error, command["metres"],
                      self._slip, noise, self._battery)
        self._x, self._y = moved["x"], moved["y"]
        self._spend(moved["energy"])
        self._heading = commanded          # telemetry reports the commanded heading
        if moved["stop"] in ("tilt", "map_boundary"):
            events.append({"type": "safety_stop", "reason": moved["stop"]})
            self._commands.clear()
        return moved["wheel"], moved["ground"]

    def _sample(self, events: List[Dict[str, Any]]) -> None:
        cost = self._mission["sample_cost"]
        enough = self._battery >= cost
        self._spend(cost)
        if not enough:
            events.append({"type": "sample_failed", "reason": "insufficient_energy"})
            return
        candidates = [(math.hypot(t.x - self._x, t.y - self._y), t.id) for t in self._world.targets
                      if t.id not in self._sampled and t.appear_tick <= self._tick]
        distance, target_id = min(candidates, default=(math.inf, ""))
        if distance <= self._mission["target_radius"]:
            self._sampled.add(target_id)
            self._sample_ticks[target_id] = self._tick
            deadline = self._plans[target_id].deadline_tick
            events.append({"type": "sample_taken", "target_id": target_id,
                           "on_time": deadline is None or self._tick <= deadline})
        else:
            events.append({"type": "sample_failed", "reason": "no_unsampled_target_in_range"})

    def _snapshot(self, wheel: float, visual: float, charge: float, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        for target in self._world.targets:
            if target.appear_tick and target.appear_tick == self._tick:
                events.append({"type": "target_discovered", "target": self._public_target(target)})
        _, gx, gy, code = self._surface.sample(self._x, self._y)
        return {
            "tick": self._tick, "received_tick": self._tick + self._mission["delay_ticks"],
            "position": [round(self._x, 6), round(self._y, 6)],
            "heading_deg": self._heading, "battery": round(self._battery, 6), "charge": round(charge, 6),
            "terrain": TERRAIN_CODES[code], "tilt": round(math.hypot(gx, gy), 4),
            "wheel_odometry": round(wheel, 6), "visual_odometry": round(visual, 6),
            "sampled_targets": sorted(self._sampled), "alive": not self._dead, "events": events,
        }

    def _measured(self, packet: Dict[str, Any]) -> Dict[str, Any]:
        """What the rover reports: the truth list keeps the exact copy."""
        rng = random.Random("{}:sense:{}".format(self._seed, packet["tick"]))
        sigma = SENSING["position_noise_m"]
        x, y = packet["position"]
        x = min(self._world.width, max(0.0, x + rng.gauss(0.0, sigma)))
        y = min(self._world.height, max(0.0, y + rng.gauss(0.0, sigma)))
        visual = packet["visual_odometry"]
        if visual > 0:
            visual = max(0.0, visual * (1.0 + rng.gauss(0.0, SENSING["visual_odometry_noise"])))
        return {**packet, "position": [round(x, 6), round(y, 6)], "visual_odometry": round(visual, 6)}
