"""World inputs and public command validation; no hidden episode state."""

from dataclasses import asdict, dataclass
import math


SLIP_RANGES = {"bedrock": (0.0, 0.05), "sand": (0.20, 0.45)}
TERRAIN_COSTS = {"bedrock": 1.0, "sand": 2.0}
NOISE = 0.02
MAX_METRES = 5.0
MAX_BATCH = 5
SEGMENT_METRES = 0.1


def finite_number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    try:
        valid = math.isfinite(value)
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError(f"{name} must be a finite number")
    return value


@dataclass(frozen=True)
class Config:
    delay_ticks: int = 3
    max_ticks: int = 80
    initial_battery: float = 100.0
    idle_cost: float = 0.5
    drive_cost: float = 1.0
    sample_cost: float = 3.0
    target_radius: float = 0.75
    base_radius: float = 0.75

    def __post_init__(self):
        for name, minimum in (("delay_ticks", 0), ("max_ticks", 1)):
            value = getattr(self, name)
            if type(value) is not int or value < minimum:
                raise ValueError(f"{name} must be an integer >= {minimum}")
        for name in ("initial_battery", "idle_cost", "drive_cost", "sample_cost",
                     "target_radius", "base_radius"):
            value = finite_number(getattr(self, name), name)
            if value < 0 or (name != "idle_cost" and value == 0):
                raise ValueError(f"{name} is outside its positive range")


@dataclass(frozen=True)
class Rect:
    x1: float
    y1: float
    x2: float
    y2: float

    def __post_init__(self):
        for name in ("x1", "y1", "x2", "y2"):
            finite_number(getattr(self, name), name)
        if self.x1 >= self.x2 or self.y1 >= self.y2:
            raise ValueError("rectangle must have positive width and height")

    def contains(self, x, y):
        return self.x1 <= x <= self.x2 and self.y1 <= y <= self.y2

    def intersects_segment(self, x, y, next_x, next_y):
        """Closed slab intersection: even a thin obstacle blocks the full segment."""
        enter, leave = 0.0, 1.0
        for origin, delta, low, high in ((x, next_x - x, self.x1, self.x2),
                                        (y, next_y - y, self.y1, self.y2)):
            if delta == 0:
                if not low <= origin <= high:
                    return False
                continue
            near, far = sorted(((low - origin) / delta, (high - origin) / delta))
            enter, leave = max(enter, near), min(leave, far)
            if enter > leave:
                return False
        return True


@dataclass(frozen=True)
class Target:
    id: str
    x: float
    y: float
    value: float = 1.0

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id:
            raise ValueError("target id must be a nonempty string")
        for name in ("x", "y", "value"):
            finite_number(getattr(self, name), name)
        if self.value <= 0:
            raise ValueError("target value must be positive")


@dataclass(frozen=True)
class World:
    width: float = 40.0
    height: float = 40.0
    base: tuple = (20.0, 20.0)
    sand: tuple = (Rect(23, 0, 40, 40),)
    hazards: tuple = (Rect(18, 30, 22, 32),)
    targets: tuple = (Target("east", 26, 20), Target("west", 14, 20),
                      Target("north", 20, 28, 2))

    def __post_init__(self):
        for name in ("width", "height"):
            if finite_number(getattr(self, name), name) <= 0:
                raise ValueError(f"{name} must be positive")
        for name in ("base", "sand", "hazards", "targets"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        if len(self.base) != 2:
            raise ValueError("base must contain x and y")
        self._validate_point(*self.base)
        for region in self.sand + self.hazards:
            if not isinstance(region, Rect):
                raise ValueError("terrain and hazards must be rectangles")
            self._validate_point(region.x1, region.y1)
            self._validate_point(region.x2, region.y2)
        ids = set()
        for target in self.targets:
            if not isinstance(target, Target) or target.id in ids:
                raise ValueError("targets must have unique ids")
            ids.add(target.id)
            self._validate_point(target.x, target.y)
        for point in (self.base,) + tuple((t.x, t.y) for t in self.targets):
            if any(region.contains(*point) for region in self.hazards):
                raise ValueError("base and targets must be outside hazards")

    def _validate_point(self, x, y):
        finite_number(x, "x")
        finite_number(y, "y")
        if not 0 <= x <= self.width or not 0 <= y <= self.height:
            raise ValueError("point must be inside the map")

    def terrain_at(self, x, y):
        return "sand" if any(region.contains(x, y) for region in self.sand) else "bedrock"

    def public_map(self):
        return {
            "width": self.width, "height": self.height, "base": list(self.base),
            "default_terrain": "bedrock", "sand": [asdict(r) for r in self.sand],
            "hazards": [asdict(r) for r in self.hazards],
            "targets": [asdict(t) for t in self.targets],
        }


def decode_command(command):
    if not isinstance(command, dict):
        raise ValueError("each command must be an object")
    action = command.get("action")
    if action in ("wait", "sample") and set(command) == {"action"}:
        return {"action": action}
    if action != "drive" or set(command) != {"action", "heading_deg", "metres"}:
        raise ValueError("expected drive(heading_deg, metres), sample or wait with no extra fields")
    heading = finite_number(command["heading_deg"], "heading_deg")
    metres = finite_number(command["metres"], "metres")
    if not 0 < metres <= MAX_METRES:
        raise ValueError(f"metres must be in (0, {MAX_METRES}]")
    return {"action": action, "heading_deg": heading % 360, "metres": metres}
