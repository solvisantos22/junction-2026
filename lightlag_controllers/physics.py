"""The controller's model of the published driving physics.

This re-implements the public rules (wheel-distance segments, slip by the terrain
at each segment's start, energy per wheel metre, stop at hazards) so a controller
can predict where queued commands will leave the rover. It uses slip *estimates*,
never the hidden per-seed values.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional

from .model import Rules, World

SlipOf = Callable[[str], float]


@dataclass
class DriveResult:
    x: float
    y: float
    wheel_m: float = 0.0
    energy: float = 0.0
    stopped: Optional[str] = None  # None | "hazard" | "battery"
    wheel_by_terrain: Dict[str, float] = field(default_factory=dict)


def simulate_drive(
    world: World,
    rules: Rules,
    slip_of: SlipOf,
    x: float,
    y: float,
    heading_deg: float,
    wheel_m: float,
    battery: float = math.inf,
) -> DriveResult:
    """Predict one drive command from (x, y)."""
    ux = math.cos(math.radians(heading_deg))
    uy = math.sin(math.radians(heading_deg))
    result = DriveResult(x, y)
    remaining = wheel_m
    while remaining > 1e-9:
        seg = min(rules.segment, remaining)
        terrain = world.terrain_at(result.x, result.y)
        cost_per_m = rules.terrains[terrain].drive_cost
        budget = battery - result.energy
        if cost_per_m * seg > budget + 1e-12:
            seg = max(0.0, budget / cost_per_m)
            result.stopped = "battery"
            if seg <= 1e-9:
                break
        step = seg * (1.0 - slip_of(terrain))
        nx, ny = result.x + ux * step, result.y + uy * step
        if world.blocked_segment(result.x, result.y, nx, ny):
            result.stopped = "hazard"
            break
        result.x, result.y = nx, ny
        result.wheel_m += seg
        result.energy += cost_per_m * seg
        result.wheel_by_terrain[terrain] = result.wheel_by_terrain.get(terrain, 0.0) + seg
        remaining -= seg
        if result.stopped:
            break
    return result


def wheel_for_distance(
    world: World,
    rules: Rules,
    slip_of: SlipOf,
    x: float,
    y: float,
    heading_deg: float,
    actual_m: float,
) -> float:
    """Wheel distance to command so the rover covers `actual_m` along a heading."""
    ux = math.cos(math.radians(heading_deg))
    uy = math.sin(math.radians(heading_deg))
    covered = 0.0
    wheel = 0.0
    while covered < actual_m - 1e-9:
        grip = max(0.05, 1.0 - slip_of(world.terrain_at(x, y)))
        step = rules.segment * grip
        if covered + step >= actual_m:
            wheel += (actual_m - covered) / grip
            break
        covered += step
        wheel += rules.segment
        x += ux * step
        y += uy * step
    return wheel


def path_energy(
    world: World,
    rules: Rules,
    slip_of: SlipOf,
    ax: float,
    ay: float,
    bx: float,
    by: float,
    step: float = 0.25,
) -> float:
    """Energy to drive the straight line A to B, by sampling terrain along it."""
    length = math.hypot(bx - ax, by - ay)
    if length <= 1e-9:
        return 0.0
    pieces = max(1, int(math.ceil(length / step)))
    piece = length / pieces
    energy = 0.0
    for i in range(pieces):
        t = (i + 0.5) / pieces
        terrain = world.terrain_at(ax + (bx - ax) * t, ay + (by - ay) * t)
        spec = rules.terrains[terrain]
        energy += piece * spec.drive_cost / max(0.05, 1.0 - slip_of(terrain))
    return energy
