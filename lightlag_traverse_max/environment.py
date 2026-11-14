"""Lightlag Traverse with a MAX map option: the max env's mechanics (lightlag_dynamic/biomes/maxenv.py)
switched on over Kristján's traverse world (lightlag_traverse/, not changed).

    from lightlag_traverse_max.environment import make_env
    env = make_env(seed=7, option="max")       # option="normal" is lightlag_traverse unchanged

What the MAX option adds, all published in rules(); the hidden values are drawn per seed:

  relay passes        (Relay Pass) the link is open 4 ticks of every 8. An uplink sent between passes
                      is transmitted when the next pass opens; a packet that would arrive between
                      passes arrives when the next one opens
  onboard slip check  (Hidden Valley) a drive step that slips more than 0.45 is the last of its drive,
                      and every queued command is discarded: safety_stop, reason slip_limit
  dune slopes         (Bagnold Dunes) how fast sand slip grows with the slope is hidden inside
                      [2.5, 4.5]; the normal map publishes 3.5
  crust               (Troy Crust) three crust regions, listed in map() and mapped as bedrock; each
                      5 m cell on gentle ground under them is soft sand with probability 0.10, not
                      listed
  ripples             (Meridiani Ripples) visual odometry noise by terrain: 0.03 on bedrock to 0.20 on
                      sand, the average of the two ends for a drive that changes terrain
  sensors             position fixes 2 m off instead of 1 m (sigma per axis), and wheels of a hidden
                      size (+-20%): a drive of M metres turns the wheels M x scale and spends their
                      energy, and wheel odometry still reads M
  turn cost           0.01 x the degrees turned x the drive cost per metre of the terrain underneath
  lost packets        10% of telemetry packets never arrive
  wild fixes          5% of position fixes are off by a further 3 m (sigma per axis)

Kept from the normal map: the 5 m drive limit (the max env's 2 m cap was for a 40 m map), the world,
the targets and deadlines, the sun, and the hidden slip, panel and heading values, so a seed is the
same mission on both maps. With every MAX setting off (NOTHING_ON) the class plays exactly like
TraverseEnvironment; a test checks that. Standard library only, Python 3.9+.
"""

from __future__ import annotations

import math
import random
from copy import deepcopy
from dataclasses import replace
from typing import Any, Dict, List, Optional, Tuple

from lightlag.model import MAX_BATCH, decode_command
from lightlag_traverse.environment import MISSION, SENSING, TraverseEnvironment
from lightlag_traverse.surface import PHYSICS, TERRAIN_CODES, Surface, drive
from lightlag_traverse.terrain import TraverseWorld, make_world

OPTIONS = ("normal", "max")

MAX_SETTINGS: Dict[str, Any] = {
    "relay_passes": {"period_ticks": 8, "open_ticks": 4},
    # The biome catalog keeps 0.40 for 50-tick missions and 0.45 for long ones; this one is 420 ticks.
    "slip_check_limit": 0.45,
    "sand_grade_gain_range": [2.5, 4.5],
    "crust": {"regions": 3, "region_size_m": [40.0, 80.0], "soft_rate": 0.10, "max_soft_slope": 0.10,
              "base_clearance_m": 25.0},
    "visual_odometry_noise_by_terrain": {"bedrock": 0.03, "regolith": 0.05, "rocks": 0.05, "sand": 0.20},
    "position_noise_m": 2.0,
    "wheel_scale_error": 0.20,
    "turn_cost_per_degree": 0.01,
    "packet_loss": 0.10,
    "fix_outliers": {"probability": 0.05, "sigma_m": 3.0},
}

# Every MAX mechanic off: the normal map, played by this class.
NOTHING_ON: Dict[str, Any] = {
    "relay_passes": None, "slip_check_limit": None, "sand_grade_gain_range": None, "crust": None,
    "visual_odometry_noise_by_terrain": None, "position_noise_m": SENSING["position_noise_m"],
    "wheel_scale_error": 0.0, "turn_cost_per_degree": 0.0, "packet_loss": 0.0, "fix_outliers": None,
}


def make_env(seed: int = 0, option: str = "normal", settings: Optional[Dict[str, Any]] = None,
             **kwargs: Any) -> TraverseEnvironment:
    """One traverse mission on the normal map or the MAX map. `settings` change MAX settings only."""
    if option == "normal":
        if settings:
            raise ValueError("settings belong to the max option")
        return TraverseEnvironment(seed, **kwargs)
    if option == "max":
        return MaxTraverseEnvironment(seed, settings=settings, **kwargs)
    raise ValueError("unknown map option {!r}; use one of {}".format(option, ", ".join(OPTIONS)))


def crust_layout(world: TraverseWorld, seed: int, settings: Optional[Dict[str, Any]]
                 ) -> Tuple[List[Dict[str, float]], Optional[List[str]], Optional[List[str]]]:
    """Crust regions, the true terrain rows and the published ones (None, None without a crust).

    Regions are whole grid cells, clear of the lander. Every cell inside one is published as bedrock;
    underneath it is soft sand with probability soft_rate when its steepest slope is at most
    max_soft_slope (sand lies on gentle ground only), drawn per cell, so overlapping regions agree."""
    if not settings:
        return [], None, None
    rng = random.Random("lightlag-traverse-max-crust:{}".format(seed))
    cell, width, height = world.cell, world.width, world.height
    bx, by = world.base
    regions: List[Dict[str, float]] = []
    for _ in range(settings["regions"]):
        for _attempt in range(200):
            w = max(cell, round(rng.uniform(*settings["region_size_m"]) / cell) * cell)
            h = max(cell, round(rng.uniform(*settings["region_size_m"]) / cell) * cell)
            x1 = math.floor(rng.uniform(0.0, width - w) / cell) * cell
            y1 = math.floor(rng.uniform(0.0, height - h) / cell) * cell
            gap = math.hypot(max(x1 - bx, 0.0, bx - (x1 + w)), max(y1 - by, 0.0, by - (y1 + h)))
            if gap >= settings["base_clearance_m"]:
                regions.append({"x1": x1, "y1": y1, "x2": x1 + w, "y2": y1 + h})
                break
    surface = world.surface()
    published = [list(row) for row in world.terrain]
    true = [list(row) for row in world.terrain]
    for region in regions:
        for j in range(int(round(region["y1"] / cell)), int(round(region["y2"] / cell))):
            for i in range(int(round(region["x1"] / cell)), int(round(region["x2"] / cell))):
                published[j][i] = "b"
                soft = (surface.cell_max_slope(i, j) <= settings["max_soft_slope"]
                        and random.Random("lightlag-traverse-max-soft:{}:{}:{}".format(seed, i, j)).random()
                        < settings["soft_rate"])
                true[j][i] = "s" if soft else "b"
    return regions, ["".join(row) for row in true], ["".join(row) for row in published]


class MaxTraverseEnvironment(TraverseEnvironment):
    """The traverse with the MAX mechanics. `settings` override MAX_SETTINGS (None or 0 switches one off)."""

    def __init__(self, seed: int = 0, world: Optional[TraverseWorld] = None,
                 mission: Optional[Dict[str, Any]] = None, settings: Optional[Dict[str, Any]] = None) -> None:
        if type(seed) is not int:
            raise ValueError("seed must be an integer")
        unknown = set(settings or {}) - set(MAX_SETTINGS)
        if unknown:
            raise ValueError("unknown MAX settings: {}".format(sorted(unknown)))
        self._max = deepcopy(dict(MAX_SETTINGS, **(settings or {})))
        s = self._max
        world = world if world is not None else make_world(seed, dict(MISSION, **(mission or {}))["max_ticks"])
        # MAX hidden values: their own stream, always drawn in this order, so the normal map's hidden
        # values stay as they are and switching one mechanic off leaves the others' draws alone.
        hidden = random.Random("lightlag-traverse-max-hidden:{}".format(seed))
        wheel_draw, sand_draw = hidden.uniform(-1.0, 1.0), hidden.random()
        self._wheel_scale = 1.0 + s["wheel_scale_error"] * wheel_draw
        self._physics = deepcopy(PHYSICS)
        if s["sand_grade_gain_range"]:
            low, high = s["sand_grade_gain_range"]
            self._physics["slip_grade_gain"]["sand"] = low + (high - low) * sand_draw
        self._crust_regions, true_codes, published = crust_layout(world, seed, s["crust"])
        self._sensing = dict(SENSING, position_noise_m=s["position_noise_m"])
        self.fault_events: List[Dict[str, Any]] = []
        self._turn_energy = 0.0
        self._slip_trips = 0
        self._last_drive: Optional[Tuple[int, str, str]] = None
        super().__init__(seed, world=replace(world, terrain=tuple(published)) if published else world,
                         mission=mission)
        if true_codes is not None:
            # The lander is clear of every crust region, so the launch packet is the same on the true ground.
            self._surface = Surface(world.cell, world.elevation_cm, true_codes)

    # ---- public tools -------------------------------------------------------------
    def rules(self) -> Dict[str, Any]:
        rules = super().rules()
        s = self._max
        rules["map_option"] = "max"
        rules["sensing"] = dict(self._sensing)
        changed = ["position fixes {} m off (sigma per axis)".format(s["position_noise_m"])]
        if s["relay_passes"]:
            rules["relay_passes"] = dict(s["relay_passes"], rule=(
                "the link is open only during relay passes: open_ticks ticks at the start of every period_ticks "
                "ticks (open when tick % period_ticks < open_ticks). An uplink sent between passes is "
                "transmitted when the next pass opens (its acknowledgement gives transmit_tick); a telemetry "
                "packet that would arrive between passes arrives when the next pass opens; map() lists a "
                "discovered target from the tick its packet arrives"))
            rules["first_execution_tick"] = ("transmit_tick + delay_ticks + 1, transmit_tick being the send tick "
                                             "during a pass, else the tick the next pass opens; FIFO, one "
                                             "command per tick")
            rules["telemetry_arrival_tick"] = ("state_tick + delay_ticks, or the tick the next relay pass opens "
                                               "if the link is closed then; tick 0 is the initial briefing")
            changed.append("relay passes")
        if s["slip_check_limit"] is not None:
            rules["onboard_slip_check"] = {"limit": s["slip_check_limit"], "rule": (
                "onboard fault protection: if a drive step slips more than the limit, that step is the last "
                "of the drive and every queued command is discarded; telemetry reports safety_stop with "
                "reason slip_limit")}
            changed.append("onboard slip check")
        if s["sand_grade_gain_range"]:
            rules["sand_grade_gain"] = {"range": list(s["sand_grade_gain_range"]), "rule": (
                "dune slopes: the sand entry of slip_grade_gain is hidden inside range, fixed for the "
                "mission; physics.slip_grade_gain.sand is the published 3.5")}
            changed.append("hidden sand slope gain")
        if s["crust"]:
            c = s["crust"]
            rules["crust"] = {"soft_rate": c["soft_rate"], "max_soft_slope": c["max_soft_slope"], "rule": (
                "map() lists crust_regions. Inside one the ground is mapped as bedrock, but each grid cell "
                "whose steepest slope is at most max_soft_slope is soft sand underneath with probability "
                "soft_rate, fixed by the seed and not listed. A soft cell is sand for slip, slide and energy, "
                "and telemetry terrain reports sand while the rover stands on one")}
            changed.append("crust")
        if s["visual_odometry_noise_by_terrain"]:
            rules["sensing"]["visual_odometry_noise_by_terrain"] = dict(s["visual_odometry_noise_by_terrain"])
            rules["visual_odometry_by_terrain"] = (
                "the relative noise of visual odometry is sensing.visual_odometry_noise_by_terrain for the "
                "terrain under the rover; a drive that starts and ends on different terrains gets the average")
            changed.append("visual odometry noise by terrain")
        if s["wheel_scale_error"]:
            rules["wheel_scale_error"] = {"range": s["wheel_scale_error"], "rule": (
                "the wheels' true size is hidden: scale is uniform in 1 +- range, fixed for the mission. A "
                "drive of M metres turns the wheels M * scale wheel metres, which the drive physics integrate "
                "and the energy is paid for; wheel_odometry reports the wheel metres divided by scale (M for "
                "a drive that ran to the end)")}
            changed.append("hidden wheel size")
        if s["turn_cost_per_degree"]:
            rules["turn_cost_per_degree"] = s["turn_cost_per_degree"]
            rules["turn_cost"] = ("before a drive, turning from the last commanded heading to the new one costs "
                                  "turn_cost_per_degree * the degrees turned * drive_cost_per_wheel_m of the "
                                  "terrain under the rover; the first drive turns from heading 0")
            changed.append("turn cost")
        if s["packet_loss"]:
            rules["telemetry_packet_loss"] = {"probability": s["packet_loss"],
                                              "rule": "each telemetry packet is lost with this probability"}
            changed.append("lost packets")
        if s["fix_outliers"]:
            rules["position_fix_outliers"] = dict(s["fix_outliers"], rule=(
                "with this probability a packet's position fix is off by a further Gaussian error of sigma_m "
                "per axis, clipped to the map"))
            changed.append("wild position fixes")
        rules["max_option"] = ("the traverse with the max env's mechanics: " + ", ".join(changed)
                               + ". The world, targets, deadlines, sun and drive limit are the normal map's")
        return rules

    def map(self) -> Dict[str, Any]:
        world = super().map()
        if self._max["crust"]:
            world["crust_regions"] = deepcopy(self._crust_regions)
        return world

    def uplink(self, commands: Any) -> List[Dict[str, Any]]:
        if not self._max["relay_passes"]:
            return super().uplink(commands)
        if not isinstance(commands, list) or not 1 <= len(commands) <= MAX_BATCH:
            raise ValueError("commands must be a list of 1..{} commands".format(MAX_BATCH))
        if self._tick >= self._mission["max_ticks"]:
            raise ValueError("episode complete")
        decoded = [decode_command(command) for command in commands]
        send = self._open_at(self._tick)
        first_tick = max(send + self._mission["delay_ticks"] + 1, self._reserved_until + 1)
        if first_tick + len(decoded) - 1 > self._mission["max_ticks"]:
            raise ValueError("commands would execute beyond the episode horizon")
        acknowledgements = [
            {"command_id": len(self._sent) + index + 1, "sent_tick": self._tick, "transmit_tick": send,
             "execute_tick": first_tick + index, "command": command}
            for index, command in enumerate(decoded)
        ]
        self._commands.extend(deepcopy(acknowledgements))
        self._sent.extend(deepcopy(acknowledgements))
        self._reserved_until = acknowledgements[-1]["execute_tick"]
        return acknowledgements

    # ---- evaluator-only -----------------------------------------------------------
    def replay(self) -> Dict[str, Any]:
        replay = super().replay()
        replay["max"] = deepcopy({
            "settings": self._max, "crust_regions": self._crust_regions,
            "hidden": {"wheel_scale": self._wheel_scale, "sand_grade_gain": self._physics["slip_grade_gain"]["sand"],
                       "true_terrain": list(self._surface.codes)},
            "fault_events": self.fault_events, "turn_energy": self._turn_energy, "slip_trips": self._slip_trips})
        return replay

    # ---- internals ----------------------------------------------------------------
    def _open_at(self, tick: int) -> int:
        """The first tick at or after `tick` with the link open."""
        relay = self._max["relay_passes"]
        if not relay or tick % relay["period_ticks"] < relay["open_ticks"]:
            return tick
        return (tick // relay["period_ticks"] + 1) * relay["period_ticks"]

    def _announced(self, target) -> bool:
        if not self._max["relay_passes"]:
            return super()._announced(target)
        return target.appear_tick == 0 or self._tick >= self._open_at(target.appear_tick + self._mission["delay_ticks"])

    def _step(self) -> None:
        super()._step()
        tick, packet = self._tick, self._pending_packets[-1]
        wild = self._max["fix_outliers"]
        if wild and random.Random("lightlag-traverse-max-outlier:{}:{}".format(self._seed, tick)).random() < wild["probability"]:
            rng = random.Random("lightlag-traverse-max-outlier-xy:{}:{}".format(self._seed, tick))
            x, y = packet["position"]
            x = min(self._world.width, max(0.0, x + rng.gauss(0.0, wild["sigma_m"])))
            y = min(self._world.height, max(0.0, y + rng.gauss(0.0, wild["sigma_m"])))
            self._pending_packets[-1] = {**packet, "position": [round(x, 6), round(y, 6)]}
            self.fault_events.append({"tick": tick, "fault": "fix_outlier"})
        loss = self._max["packet_loss"]
        if loss and random.Random("lightlag-traverse-max-loss:{}:{}".format(self._seed, tick)).random() < loss:
            self._pending_packets.pop()
            self.fault_events.append({"tick": tick, "fault": "packet_lost"})

    def _drive(self, command: Dict[str, Any], events: List[Dict[str, Any]]):
        """The parent's drive with the same random draws, plus the turn cost, the wheel size, the hidden
        sand gain, the true (crust) ground and the onboard slip check."""
        commanded = command["heading_deg"]
        rng = random.Random("{}:heading:{}".format(self._seed, self._tick))
        self._heading_bias += rng.gauss(0.0, self._sensing["heading_bias_walk_deg"])
        error = self._heading_bias + rng.gauss(0.0, self._sensing["heading_noise_deg"])
        self._heading_errors.append({"tick": self._tick, "error_deg": round(error, 6),
                                     "bias_deg": round(self._heading_bias, 6)})
        noise = random.Random("{}:drive:{}".format(self._seed, self._tick)).uniform(
            -PHYSICS["slip_noise"], PHYSICS["slip_noise"])
        start = TERRAIN_CODES[self._surface.sample(self._x, self._y)[3]]
        rate = self._max["turn_cost_per_degree"]
        if rate:
            turn = abs((commanded - self._heading + 180.0) % 360.0 - 180.0)
            spend = rate * turn * PHYSICS["drive_cost_per_wheel_m"][start]
            self._spend(spend)
            self._turn_energy += spend
        self._heading = commanded          # telemetry reports the commanded heading
        if self._battery <= 0:
            self._last_drive = (self._tick, start, start)
            return 0.0, 0.0
        moved = self._roll(commanded + error, command["metres"] * self._wheel_scale, noise)
        self._x, self._y = moved["x"], moved["y"]
        self._spend(moved["energy"])
        if moved["stop"] in ("tilt", "map_boundary", "slip_limit"):
            events.append({"type": "safety_stop", "reason": moved["stop"]})
            self._commands.clear()
            self._slip_trips += moved["stop"] == "slip_limit"
        self._last_drive = (self._tick, start, TERRAIN_CODES[self._surface.sample(self._x, self._y)[3]])
        return moved["wheel"] / self._wheel_scale, moved["ground"]

    def _roll(self, heading: float, metres: float, noise: float) -> Dict[str, Any]:
        """Kristján's drive(); with the slip check, one segment at a time, stopping after a step whose
        slip was above the limit (the step that measured it still happened)."""
        limit, physics = self._max["slip_check_limit"], self._physics
        if limit is None:
            return drive(self._surface, physics, self._x, self._y, heading, metres, self._slip, noise, self._battery)
        radians = math.radians(heading)
        ux, uy = math.cos(radians), math.sin(radians)
        gain, top, segment = physics["slip_grade_gain"], physics["slip_max"], physics["segment_m"]
        x, y, remaining = self._x, self._y, float(metres)
        wheel = ground = energy = 0.0
        stop = None
        while remaining > 1e-9:
            piece = min(segment, remaining)
            _, gx, gy, code = self._surface.sample(x, y)
            name = TERRAIN_CODES[code]
            grade = gx * ux + gy * uy
            slip = self._slip[name] + gain[name] * (grade if grade > 0 else 0.0) + noise
            slip = 0.0 if slip < 0 else (top if slip > top else slip)
            step = drive(self._surface, physics, x, y, heading, piece, self._slip, noise, self._battery - energy)
            x, y = step["x"], step["y"]
            wheel, ground, energy = wheel + step["wheel"], ground + step["ground"], energy + step["energy"]
            if step["stop"] is not None:
                stop = step["stop"]
                break
            remaining -= piece
            if slip > limit:
                stop = "slip_limit"
                break
        return {"x": x, "y": y, "wheel": wheel, "ground": ground, "energy": energy, "stop": stop}

    def _measured(self, packet: Dict[str, Any]) -> Dict[str, Any]:
        """The parent's measurement with the same draws, at the MAX noise, arriving at a relay pass."""
        rng = random.Random("{}:sense:{}".format(self._seed, packet["tick"]))
        sigma = self._sensing["position_noise_m"]
        x, y = packet["position"]
        x = min(self._world.width, max(0.0, x + rng.gauss(0.0, sigma)))
        y = min(self._world.height, max(0.0, y + rng.gauss(0.0, sigma)))
        visual = packet["visual_odometry"]
        if visual > 0:
            visual = max(0.0, visual * (1.0 + rng.gauss(0.0, self._visual_noise(packet["tick"]))))
        measured = {**packet, "position": [round(x, 6), round(y, 6)], "visual_odometry": round(visual, 6)}
        measured["received_tick"] = self._open_at(packet["received_tick"])
        return measured

    def _visual_noise(self, tick: int) -> float:
        by_terrain = self._max["visual_odometry_noise_by_terrain"]
        if by_terrain and self._last_drive and self._last_drive[0] == tick:
            _, start, end = self._last_drive
            return (by_terrain[start] + by_terrain[end]) / 2.0
        return self._sensing["visual_odometry_noise"]
