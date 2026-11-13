"""Controller-side view of a Lightlag episode: only what the public tools reveal.

Nothing here reads simulator internals. `Rules` and `World` are built from the
public `rules()` and `map()` results by `adapter.py`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple


@dataclass(frozen=True)
class Rect:
    x0: float
    y0: float
    x1: float
    y1: float

    def contains(self, x: float, y: float) -> bool:
        return self.x0 <= x <= self.x1 and self.y0 <= y <= self.y1

    def inflate(self, margin: float) -> "Rect":
        return Rect(self.x0 - margin, self.y0 - margin, self.x1 + margin, self.y1 + margin)

    def intersects_segment(self, ax: float, ay: float, bx: float, by: float) -> bool:
        """True if the closed segment A-B touches this closed rectangle (Liang-Barsky)."""
        dx, dy = bx - ax, by - ay
        t0, t1 = 0.0, 1.0
        for p, q in ((-dx, ax - self.x0), (dx, self.x1 - ax), (-dy, ay - self.y0), (dy, self.y1 - ay)):
            if p == 0.0:
                if q < 0.0:
                    return False
                continue
            t = q / p
            if p < 0.0:
                if t > t1:
                    return False
                if t > t0:
                    t0 = t
            else:
                if t < t0:
                    return False
                if t < t1:
                    t1 = t
        return True


@dataclass(frozen=True)
class Target:
    id: str
    x: float
    y: float
    value: float


@dataclass(frozen=True)
class TerrainSpec:
    name: str
    slip_min: float
    slip_max: float
    drive_cost: float  # energy per wheel metre

    @property
    def slip_mid(self) -> float:
        return (self.slip_min + self.slip_max) / 2.0

    @property
    def slip_halfwidth(self) -> float:
        return (self.slip_max - self.slip_min) / 2.0


@dataclass(frozen=True)
class Rules:
    """Published rules. Defaults mirror the core design's starting values."""

    delay: int = 3
    horizon: int = 80
    battery: float = 100.0
    idle_cost: float = 0.5
    sample_cost: float = 3.0
    sample_radius: float = 0.75
    base_radius: float = 0.75
    max_drive: float = 5.0
    max_uplink: int = 5
    max_advance: int = 5
    segment: float = 0.1
    slip_noise: float = 0.02
    terrains: Dict[str, TerrainSpec] = field(
        default_factory=lambda: {
            "bedrock": TerrainSpec("bedrock", 0.0, 0.05, 1.0),
            "sand": TerrainSpec("sand", 0.20, 0.45, 2.0),
        }
    )


@dataclass(frozen=True)
class World:
    width: float
    height: float
    base: Tuple[float, float]
    targets: Tuple[Target, ...]
    hazards: Tuple[Rect, ...] = ()
    patches: Tuple[Tuple[Rect, str], ...] = ()  # later patches win
    default_terrain: str = "bedrock"

    def terrain_at(self, x: float, y: float) -> str:
        name = self.default_terrain
        for rect, terrain in self.patches:
            if rect.contains(x, y):
                name = terrain
        return name

    def in_bounds(self, x: float, y: float) -> bool:
        return 0.0 <= x <= self.width and 0.0 <= y <= self.height

    def blocked_segment(self, ax: float, ay: float, bx: float, by: float) -> bool:
        """True if moving A to B would leave the world or touch a hazard."""
        if not self.in_bounds(bx, by):
            return True
        return any(h.intersects_segment(ax, ay, bx, by) for h in self.hazards)

    def target(self, target_id: str) -> Optional[Target]:
        for target in self.targets:
            if target.id == target_id:
                return target
        return None


@dataclass(frozen=True)
class Packet:
    """One telemetry packet, describing the rover at `tick` (which is in the past)."""

    tick: int
    x: float
    y: float
    battery: float
    terrain: str = ""
    wheel_m: float = 0.0  # wheel odometry during that tick
    moved_m: float = 0.0  # visual odometry during that tick
    sampled: Tuple[str, ...] = ()
    alive: bool = True
    events: Tuple[str, ...] = ()


@dataclass(frozen=True)
class Command:
    kind: str  # "drive" | "sample" | "wait"
    heading_deg: float = 0.0
    metres: float = 0.0

    @staticmethod
    def drive(heading_deg: float, metres: float) -> "Command":
        return Command("drive", heading_deg % 360.0, metres)

    @staticmethod
    def sample() -> "Command":
        return Command("sample")

    @staticmethod
    def wait() -> "Command":
        return Command("wait")


@dataclass
class SentCommand:
    command: Command
    sent_tick: int
    exec_tick: int
    cancelled: bool = False


def distance(ax: float, ay: float, bx: float, by: float) -> float:
    return math.hypot(bx - ax, by - ay)


def heading_to(ax: float, ay: float, bx: float, by: float) -> float:
    """Heading in degrees from A to B. Zero points east, 90 points north."""
    return math.degrees(math.atan2(by - ay, bx - ax)) % 360.0
