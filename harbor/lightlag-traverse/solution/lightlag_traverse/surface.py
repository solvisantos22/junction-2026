"""The ground and the drive physics of the traverse, as published.

Everything here is public: `rules()` gives the numbers and `map()` the grid. The simulator
runs a drive through `drive()` with the hidden values; a controller can run the same function
with its own estimates, so nobody has to guess how the published formulas are applied.
Standard library only, Python 3.9+.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

TERRAIN_CODES = {"b": "bedrock", "r": "regolith", "s": "sand", "k": "rocks"}

# Published physics. `rules()` returns this table unchanged.
PHYSICS: Dict[str, Any] = {
    "segment_m": 0.25,                  # a drive is integrated in steps of this many wheel metres
    "max_tilt": 0.36,                   # rise over run (about 20 degrees); steeper ground stops the rover
    "slip_base_ranges": {"bedrock": [0.01, 0.05], "regolith": [0.05, 0.12],
                         "sand": [0.15, 0.35], "rocks": [0.12, 0.24]},
    "slip_grade_gain": {"bedrock": 0.8, "regolith": 1.5, "sand": 3.5, "rocks": 1.2},
    "slip_noise": 0.02,                 # one uniform draw in +-this per executed drive
    "slip_max": 0.95,
    "side_slip_gain": {"bedrock": 0.1, "regolith": 0.3, "sand": 0.8, "rocks": 0.2},
    "drive_cost_per_wheel_m": {"bedrock": 0.30, "regolith": 0.36, "sand": 0.50, "rocks": 0.60},
    "climb_cost_per_m": 2.0,            # energy per metre of height gained; descending returns nothing
}


class Surface:
    """A height grid with bilinear interpolation, and one terrain class per grid cell.

    `elevation_cm[j][i]` is the height in centimetres at x = i * cell, y = j * cell.
    `terrain[j][i]` is the class code of the cell with that vertex as its south-west corner.
    """

    def __init__(self, cell: float, elevation_cm: Sequence[Sequence[int]], terrain: Sequence[str]) -> None:
        self.cell = float(cell)
        self.h: List[List[float]] = [[value / 100.0 for value in row] for row in elevation_cm]
        self.ny, self.nx = len(self.h), len(self.h[0])
        if self.ny < 2 or self.nx < 2 or any(len(row) != self.nx for row in self.h):
            raise ValueError("the elevation grid must be rectangular, at least 2 by 2")
        if len(terrain) != self.ny - 1 or any(len(row) != self.nx - 1 for row in terrain):
            raise ValueError("terrain needs one code per grid cell")
        self.codes: List[str] = [str(row) for row in terrain]
        self.width = (self.nx - 1) * self.cell
        self.height = (self.ny - 1) * self.cell

    def inside(self, x: float, y: float) -> bool:
        return 0.0 <= x <= self.width and 0.0 <= y <= self.height

    def locate(self, x: float, y: float) -> Tuple[int, int, float, float]:
        """The cell (i, j) holding the point and the point's fractions inside it."""
        fx, fy = x / self.cell, y / self.cell
        i = min(self.nx - 2, max(0, int(fx)))
        j = min(self.ny - 2, max(0, int(fy)))
        return i, j, fx - i, fy - j

    def sample(self, x: float, y: float) -> Tuple[float, float, float, str]:
        """Height, d(height)/dx, d(height)/dy and terrain code at a point."""
        cell = self.cell
        fx, fy = x / cell, y / cell
        i = min(self.nx - 2, max(0, int(fx)))
        j = min(self.ny - 2, max(0, int(fy)))
        tx, ty = fx - i, fy - j
        low, high = self.h[j], self.h[j + 1]
        h00, h10, h01, h11 = low[i], low[i + 1], high[i], high[i + 1]
        height = (h00 * (1 - tx) + h10 * tx) * (1 - ty) + (h01 * (1 - tx) + h11 * tx) * ty
        gx = ((h10 - h00) * (1 - ty) + (h11 - h01) * ty) / cell
        gy = ((h01 - h00) * (1 - tx) + (h11 - h10) * tx) / cell
        return height, gx, gy, self.codes[j][i]

    def elevation(self, x: float, y: float) -> float:
        return self.sample(x, y)[0]

    def slope(self, x: float, y: float) -> float:
        _, gx, gy, _ = self.sample(x, y)
        return math.hypot(gx, gy)

    def terrain(self, x: float, y: float) -> str:
        return TERRAIN_CODES[self.sample(x, y)[3]]

    def cell_max_slope(self, i: int, j: int) -> float:
        """The steepest slope anywhere in cell (i, j). On a bilinear patch that is at a corner."""
        low, high, cell = self.h[j], self.h[j + 1], self.cell
        h00, h10, h01, h11 = low[i], low[i + 1], high[i], high[i + 1]
        south, north = (h10 - h00) / cell, (h11 - h01) / cell
        west, east = (h01 - h00) / cell, (h11 - h10) / cell
        return max(math.hypot(south, west), math.hypot(south, east),
                   math.hypot(north, west), math.hypot(north, east))


def drive(surface: Surface, physics: Dict[str, Any], x: float, y: float, heading_deg: float, metres: float,
          slip_base: Dict[str, float], noise: float = 0.0, battery: Optional[float] = None) -> Dict[str, Any]:
    """One drive command: `metres` of wheel travel at `heading_deg` from (x, y).

    Per step of `segment_m` wheel metres, with the ground sampled where the step starts:
      grade  = slope along the heading (rise over run), cross = slope to the left of it
      slip   = clip(slip_base[terrain] + slip_grade_gain[terrain] * max(0, grade) + noise, 0, slip_max)
      the rover moves segment * (1 - slip) along the heading and
      segment * side_slip_gain[terrain] * cross to the right (downhill across the heading)
      energy = segment * drive_cost_per_wheel_m[terrain] + climb_cost_per_m * max(0, height gained)
    The step is refused, and the drive ends, if it would leave the map (`stop` = "map_boundary")
    or end on ground steeper than `max_tilt` (`stop` = "tilt"). With a `battery`, the drive also
    ends when the battery is spent (`stop` = "battery").

    Returns the end position, wheel and ground metres, the energy used and `stop` (None if the
    whole command ran).
    """
    radians = math.radians(heading_deg)
    ux, uy = math.cos(radians), math.sin(radians)
    segment_full = physics["segment_m"]
    gain, side, cost = physics["slip_grade_gain"], physics["side_slip_gain"], physics["drive_cost_per_wheel_m"]
    climb, slip_max, max_tilt = physics["climb_cost_per_m"], physics["slip_max"], physics["max_tilt"]
    width, height = surface.width, surface.height
    remaining = float(metres)
    wheel = ground = energy = 0.0
    stop = None
    here, gx, gy, code = surface.sample(x, y)
    while remaining > 1e-9:
        segment = min(segment_full, remaining)
        name = TERRAIN_CODES[code]
        grade = gx * ux + gy * uy
        cross = -gx * uy + gy * ux
        slip = slip_base[name] + gain[name] * (grade if grade > 0 else 0.0) + noise
        slip = 0.0 if slip < 0 else (slip_max if slip > slip_max else slip)
        forward = segment * (1.0 - slip)
        sideways = segment * side[name] * cross
        next_x = x + ux * forward + uy * sideways
        next_y = y + uy * forward - ux * sideways
        if not (0.0 <= next_x <= width and 0.0 <= next_y <= height):
            stop = "map_boundary"
            break
        there, next_gx, next_gy, next_code = surface.sample(next_x, next_y)
        if math.hypot(next_gx, next_gy) > max_tilt:
            stop = "tilt"
            break
        spent = segment * cost[name] + climb * (there - here if there > here else 0.0)
        if battery is not None and spent >= battery - energy:
            energy = battery
            wheel += segment
            ground += math.hypot(next_x - x, next_y - y)
            x, y = next_x, next_y
            stop = "battery"
            break
        energy += spent
        wheel += segment
        ground += math.hypot(next_x - x, next_y - y)
        remaining -= segment
        x, y, here, gx, gy, code = next_x, next_y, there, next_gx, next_gy, next_code
    return {"x": x, "y": y, "wheel": wheel, "ground": ground, "energy": energy, "stop": stop}
