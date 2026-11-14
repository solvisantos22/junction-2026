"""Seeded Mars-like ground and the mission laid on it.

    python3 -m lightlag_traverse.terrain 7        # print one world as a character map

One seed gives one world: a height grid built from layered relief, impact craters with steep
walls and a breached side, a scarp with passes, and a terrain class per cell (sand in the
flats, rocks around the craters, bedrock on the heights). Science targets are placed only where
a rover can get to them and stand. The ranges below are published in `rules()`; the seed picks
values inside them. Standard library only, Python 3.9+.
"""

from __future__ import annotations

import heapq
import math
import random
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from .surface import PHYSICS, Surface

GENERATOR: Dict[str, Any] = {
    "width_m": 600.0, "height_m": 400.0, "cell_m": 5.0,
    "relief_spacing_m": [200.0, 100.0, 50.0, 25.0, 12.5],
    "relief_amplitude_m": [5.0, 2.6, 1.3, 0.6, 0.25],
    "regional_tilt": 0.008,
    "craters": [3, 5], "crater_radius_m": [22.0, 60.0], "crater_depth_ratio": [0.19, 0.24],
    "crater_rim_ratio": [0.03, 0.05], "crater_breaches": [1, 2],
    "scarp_step_m": [5.0, 8.0], "scarp_length_m": [300.0, 460.0], "scarp_passes": 2,
    "terrain_share": {"sand": 0.18, "rocks": 0.12, "bedrock": 0.15},
    "sand_max_cell_slope": 0.10,
    "initial_targets": 38, "discoveries": 8,
    "target_clusters": 5, "cluster_targets": [4, 6], "cluster_radius_m": 55.0,
    "target_values": [1, 5], "target_min_spacing_m": 15.0, "target_min_base_distance_m": 35.0,
    "deadline_share": 0.7, "deadline_window": [0.22, 0.95],
    "discovery_appear": [30, 0.68], "discovery_window_ticks": [60, 130],
}
SAFE_SHARE = 0.85          # a grid node counts as drivable below this share of max_tilt
FLAT_SLOPE = 0.12          # a target stands on ground no steeper than this


@dataclass(frozen=True)
class TraverseTarget:
    id: str
    x: float
    y: float
    value: float
    deadline_tick: Optional[int] = None
    appear_tick: int = 0


@dataclass(frozen=True)
class TraverseWorld:
    seed: int
    cell: float
    elevation_cm: Tuple[Tuple[int, ...], ...]
    terrain: Tuple[str, ...]
    base: Tuple[float, float]
    targets: Tuple[TraverseTarget, ...]
    features: Dict[str, Any] = field(default_factory=dict)   # craters and scarp, for pictures only

    @property
    def width(self) -> float:
        return (len(self.elevation_cm[0]) - 1) * self.cell

    @property
    def height(self) -> float:
        return (len(self.elevation_cm) - 1) * self.cell

    def surface(self) -> Surface:
        return Surface(self.cell, self.elevation_cm, self.terrain)


def _smooth(t: float) -> float:
    t = 0.0 if t < 0 else (1.0 if t > 1 else t)
    return t * t * (3 - 2 * t)


def value_noise(rng: random.Random, width: float, height: float, spacing: float) -> Callable[[float, float], float]:
    """Smooth noise in -1..1 with features about `spacing` metres across."""
    cols, rows = int(width // spacing) + 3, int(height // spacing) + 3
    lattice = [[rng.uniform(-1.0, 1.0) for _ in range(cols)] for _ in range(rows)]

    def at(x: float, y: float) -> float:
        fx, fy = x / spacing, y / spacing
        i, j = int(fx), int(fy)
        tx, ty = _smooth(fx - i), _smooth(fy - j)
        low, high = lattice[j], lattice[j + 1]
        a = low[i] + (low[i + 1] - low[i]) * tx
        b = high[i] + (high[i + 1] - high[i]) * tx
        return a + (b - a) * ty

    return at


def _breach_strength(crater: Dict[str, Any], dx: float, dy: float) -> float:
    angle, strength = math.atan2(dy, dx), 0.0
    for breach in crater["breaches"]:
        off = abs((angle - breach["angle"] + math.pi) % (2 * math.pi) - math.pi)
        if off < breach["half_width"]:
            strength = max(strength, 0.5 * (1 + math.cos(math.pi * off / breach["half_width"])))
    return strength


def crater_height(crater: Dict[str, Any], x: float, y: float) -> float:
    """A flat-floored bowl with a raised rim; in a breach the wall is worn down to a ramp."""
    dx, dy = x - crater["x"], y - crater["y"]
    s = math.hypot(dx, dy) / crater["radius"]
    if s > 2.2:
        return 0.0
    strength = _breach_strength(crater, dx, dy) if s > 0.2 else 0.0
    rim = crater["rim"] * math.exp(-((s - 1.0) / 0.28) ** 2) * (1.0 - 0.7 * strength)
    if s >= 1.0:
        return rim
    worn = 1.0 - crater["breach_depth"] * strength * _smooth((s - 0.2) / 0.5)
    return -crater["depth"] * (1.0 - s ** 4) * worn + rim


def scarp_height(scarp: Optional[Dict[str, Any]], x: float, y: float) -> float:
    """A step in the ground along a line: too steep to climb except where a pass widens it."""
    if scarp is None:
        return 0.0
    ax, ay = scarp["x"], scarp["y"]
    ux, uy = scarp["ux"], scarp["uy"]
    along = (x - ax) * ux + (y - ay) * uy
    across = -(x - ax) * uy + (y - ay) * ux
    half = scarp["length"] / 2
    taper = _smooth((half + 40.0 - abs(along)) / 80.0)      # the step fades out at both ends
    if taper <= 0.0:
        return 0.0
    width = scarp["half_width"]
    for position in scarp["passes"]:
        near = 1.0 - _smooth((abs(along - position) - scarp["pass_half_length"]) / 20.0)
        width = max(width, scarp["half_width"] + (scarp["pass_half_width"] - scarp["half_width"]) * near)
    return scarp["step"] * taper * (_smooth((across + width) / (2 * width)) - 0.5)


def _draw_features(rng: random.Random, g: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    width, height = g["width_m"], g["height_m"]
    craters: List[Dict[str, Any]] = []
    for _ in range(rng.randint(*g["craters"])):
        for _ in range(60):
            radius = rng.uniform(*g["crater_radius_m"])
            x = rng.uniform(1.5 * radius + 10, width - 1.5 * radius - 10)
            y = rng.uniform(1.5 * radius + 10, height - 1.5 * radius - 10)
            if all(math.hypot(x - c["x"], y - c["y"]) > 1.9 * (radius + c["radius"]) for c in craters):
                break
        else:
            continue
        breaches = [{"angle": rng.uniform(-math.pi, math.pi), "half_width": rng.uniform(0.5, 0.75)}
                    for _ in range(rng.randint(*g["crater_breaches"]))]
        craters.append({"x": round(x, 1), "y": round(y, 1), "radius": round(radius, 1),
                        "depth": radius * rng.uniform(*g["crater_depth_ratio"]),
                        "rim": radius * rng.uniform(*g["crater_rim_ratio"]),
                        "breaches": breaches, "breach_depth": rng.uniform(0.62, 0.72),
                        "sandy": rng.random() < 0.7})
    angle = rng.uniform(0, math.pi)
    scarp = {"x": width / 2 + rng.uniform(-90, 90), "y": height / 2 + rng.uniform(-60, 60),
             "ux": math.cos(angle), "uy": math.sin(angle),
             "length": rng.uniform(*g["scarp_length_m"]), "step": rng.uniform(*g["scarp_step_m"]),
             "half_width": 7.0, "pass_half_width": 38.0, "pass_half_length": 20.0}
    half = scarp["length"] / 2
    first = rng.uniform(-0.75, -0.15) * half
    scarp["passes"] = [first, first + rng.uniform(0.45, 0.8) * half][:g["scarp_passes"]]
    return craters, scarp


def _heights(rng: random.Random, g: Dict[str, Any], craters, scarp) -> List[List[float]]:
    width, height, cell = g["width_m"], g["height_m"], g["cell_m"]
    layers = [(value_noise(rng, width, height, spacing), amplitude)
              for spacing, amplitude in zip(g["relief_spacing_m"], g["relief_amplitude_m"])]
    tilt_x, tilt_y = (rng.uniform(-g["regional_tilt"], g["regional_tilt"]) for _ in range(2))
    nx, ny = int(round(width / cell)) + 1, int(round(height / cell)) + 1
    rows = []
    for j in range(ny):
        y = j * cell
        row = []
        for i in range(nx):
            x = i * cell
            z = tilt_x * (x - width / 2) + tilt_y * (y - height / 2)
            for noise, amplitude in layers:
                z += amplitude * noise(x, y)
            for crater in craters:
                z += crater_height(crater, x, y)
            z += scarp_height(scarp, x, y)
            row.append(z)
        rows.append(row)
    mean = sum(sum(row) for row in rows) / (nx * ny)
    return [[z - mean for z in row] for row in rows]


def _quantile_mask(scores: Dict[Tuple[int, int], float], share: float, total: int) -> set:
    """The cells with the highest scores, enough of them to cover `share` of the map."""
    count = int(round(share * total))
    ranked = sorted(scores, key=lambda cell: (-scores[cell], cell))
    return set(ranked[:count])


def _classes(rng: random.Random, g: Dict[str, Any], surface_heights: List[List[float]], craters) -> List[str]:
    width, height, cell = g["width_m"], g["height_m"], g["cell_m"]
    ny, nx = len(surface_heights) - 1, len(surface_heights[0]) - 1
    flat = [z for row in surface_heights for z in row]
    mean = sum(flat) / len(flat)
    spread = (sum((z - mean) ** 2 for z in flat) / len(flat)) ** 0.5 or 1.0
    sand_noise = value_noise(rng, width, height, 110.0)
    rock_noise = value_noise(rng, width, height, 45.0)
    rock_field = value_noise(rng, width, height, 80.0)
    bed_noise = value_noise(rng, width, height, 80.0)
    probe = Surface(cell, [[int(round(z * 100)) for z in row] for row in surface_heights],
                    ["r" * nx for _ in range(ny)])
    sand: Dict[Tuple[int, int], float] = {}
    rocks: Dict[Tuple[int, int], float] = {}
    bed: Dict[Tuple[int, int], float] = {}
    for j in range(ny):
        for i in range(nx):
            x, y = (i + 0.5) * cell, (j + 0.5) * cell
            z = (probe.elevation(x, y) - mean) / spread
            floor = ejecta = 0.0
            for crater in craters:
                s = math.hypot(x - crater["x"], y - crater["y"]) / crater["radius"]
                if s < 0.6 and crater["sandy"]:
                    floor = 1.0
                if 1.05 < s < 1.8:
                    ejecta = 0.9
            if probe.cell_max_slope(i, j) < g["sand_max_cell_slope"]:
                sand[(i, j)] = 0.6 * sand_noise(x, y) - 0.4 * z + floor
            rocks[(i, j)] = 0.6 * rock_noise(x, y) + 0.5 * rock_field(x, y) + ejecta
            bed[(i, j)] = 0.5 * bed_noise(x, y) + 0.5 * z
    total = nx * ny
    is_sand = _quantile_mask(sand, g["terrain_share"]["sand"], total)
    is_rocks = _quantile_mask({c: v for c, v in rocks.items() if c not in is_sand}, g["terrain_share"]["rocks"], total)
    is_bed = _quantile_mask({c: v for c, v in bed.items() if c not in is_sand and c not in is_rocks},
                            g["terrain_share"]["bedrock"], total)
    return ["".join("s" if (i, j) in is_sand else "k" if (i, j) in is_rocks else "b" if (i, j) in is_bed else "r"
                    for i in range(nx)) for j in range(ny)]


def safe_nodes(surface: Surface, limit: float) -> List[List[bool]]:
    """Grid vertices all of whose neighbouring cells are no steeper than `limit` anywhere."""
    steep = [[surface.cell_max_slope(i, j) > limit for i in range(surface.nx - 1)] for j in range(surface.ny - 1)]
    safe = []
    for j in range(surface.ny):
        row = []
        for i in range(surface.nx):
            around = [steep[b][a] for a in (i - 1, i) for b in (j - 1, j)
                      if 0 <= a < surface.nx - 1 and 0 <= b < surface.ny - 1]
            row.append(not any(around))
        safe.append(row)
    return safe


NEIGHBOURS = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
              (1, 1, math.sqrt(2)), (1, -1, math.sqrt(2)), (-1, 1, math.sqrt(2)), (-1, -1, math.sqrt(2))]


def ground_distance(surface: Surface, safe: List[List[bool]], start: Tuple[int, int]) -> Dict[Tuple[int, int], float]:
    """Metres along the grid from `start` to every node that can be reached over safe nodes."""
    distance = {start: 0.0}
    heap = [(0.0, start)]
    while heap:
        d, (i, j) = heapq.heappop(heap)
        if d > distance[(i, j)]:
            continue
        for di, dj, length in NEIGHBOURS:
            a, b = i + di, j + dj
            if 0 <= a < surface.nx and 0 <= b < surface.ny and safe[b][a]:
                nd = d + length * surface.cell
                if nd < distance.get((a, b), math.inf):
                    distance[(a, b)] = nd
                    heapq.heappush(heap, (nd, (a, b)))
    return distance


def _attempt(rng: random.Random, seed: int, g: Dict[str, Any], max_ticks: int) -> Optional[TraverseWorld]:
    width, height, cell = g["width_m"], g["height_m"], g["cell_m"]
    craters, scarp = _draw_features(rng, g)
    heights = _heights(rng, g, craters, scarp)
    elevation_cm = [[int(round(z * 100)) for z in row] for row in heights]
    terrain = _classes(rng, g, [[v / 100.0 for v in row] for row in elevation_cm], craters)
    surface = Surface(cell, elevation_cm, terrain)
    safe = safe_nodes(surface, PHYSICS["max_tilt"] * SAFE_SHARE)
    flat = safe_nodes(surface, FLAT_SLOPE)

    def clear(i: int, j: int, reach: int) -> bool:
        return all(0 <= a < surface.nx and 0 <= b < surface.ny and safe[b][a]
                   for a in range(i - reach, i + reach + 1) for b in range(j - reach, j + reach + 1))

    # The lander: flat firm ground near the middle, outside every crater.
    wish = (rng.uniform(0.3, 0.7) * width, rng.uniform(0.3, 0.7) * height)
    spots = []
    for j in range(4, surface.ny - 4):
        for i in range(4, surface.nx - 4):
            x, y = i * cell, j * cell
            if not (flat[j][i] and clear(i, j, 2) and surface.sample(x, y)[3] in "rb"):
                continue
            if any(math.hypot(x - c["x"], y - c["y"]) < 1.6 * c["radius"] for c in craters):
                continue
            spots.append((math.hypot(x - wish[0], y - wish[1]), i, j))
    if not spots:
        return None
    _, bi, bj = min(spots)
    reach = ground_distance(surface, safe, (bi, bj))
    if len(reach) < 0.55 * surface.nx * surface.ny:
        return None
    base = (bi * cell, bj * cell)

    # Where a target can stand: reachable, flat, with safe ground around it, away from the edge.
    sites = []
    for (i, j), metres in reach.items():
        x, y = i * cell, j * cell
        if (flat[j][i] and clear(i, j, 1) and 20 <= x <= width - 20 and 20 <= y <= height - 20
                and math.hypot(x - base[0], y - base[1]) >= g["target_min_base_distance_m"]):
            sites.append((i, j))
    sites.sort()
    if len(sites) < 400:
        return None

    chosen: List[Tuple[int, int]] = []

    def free(site: Tuple[int, int]) -> bool:
        return all(math.hypot((site[0] - a) * cell, (site[1] - b) * cell) >= g["target_min_spacing_m"]
                   for a, b in chosen)

    def take(pool: List[Tuple[int, int]], count: int) -> None:
        pool = list(pool)
        rng.shuffle(pool)
        for site in pool:
            if count <= 0:
                break
            if free(site):
                chosen.append(site)
                count -= 1

    wanted = g["initial_targets"] + g["discoveries"]
    for crater in craters:                               # one or two on every crater floor that can be reached
        floor = [s for s in sites if math.hypot(s[0] * cell - crater["x"], s[1] * cell - crater["y"]) < 0.5 * crater["radius"]]
        take(floor, rng.randint(1, 2))
    centres: List[Tuple[int, int]] = []
    for _ in range(g["target_clusters"]):                # science regions, spread out
        pool = rng.sample(sites, 40)
        centres.append(max(pool, key=lambda s: min([math.hypot(s[0] - c[0], s[1] - c[1]) for c in centres] or [0.0])
                           + 0.004 * reach[s]))
    for centre in centres:
        near = [s for s in sites
                if math.hypot((s[0] - centre[0]) * cell, (s[1] - centre[1]) * cell) < g["cluster_radius_m"]]
        take(near, rng.randint(*g["cluster_targets"]))
    take(sites, wanted - len(chosen))                    # the rest anywhere
    if len(chosen) < wanted:
        return None
    rng.shuffle(chosen)

    def worth(site: Tuple[int, int]) -> int:
        x, y = site[0] * cell, site[1] * cell
        value = 1 + (reach[site] > 150) + (reach[site] > 280) + (surface.sample(x, y)[3] in "sk")
        if any(math.hypot(x - c["x"], y - c["y"]) < 0.6 * c["radius"] for c in craters):
            value += 2
        if rng.random() < 0.3:
            value += rng.choice((-1, 1))
        low, high = g["target_values"]
        return max(low, min(high, value))

    targets: List[TraverseTarget] = []
    low, high = g["deadline_window"]
    for number, site in enumerate(chosen[:g["initial_targets"]], 1):
        value, deadline = worth(site), None
        draw, share = rng.uniform(low, high), rng.random()
        if share < g["deadline_share"]:
            soonest = reach[site] / 3.6 + 12                # a rover that drives straight there makes it
            deadline = int(min(max_ticks - 10, max(draw * max_ticks, soonest)))
        targets.append(TraverseTarget("t{}".format(number), site[0] * cell, site[1] * cell, float(value), deadline, 0))
    first, last = g["discovery_appear"]
    for number, site in enumerate(chosen[g["initial_targets"]:], 1):
        value = max(2, worth(site))
        appear = rng.randint(first, int(last * max_ticks))
        window, share = rng.randint(*g["discovery_window_ticks"]), rng.random()
        deadline = min(max_ticks - 5, appear + window) if share < 0.75 else None
        targets.append(TraverseTarget("d{}".format(number), site[0] * cell, site[1] * cell, float(value), deadline, appear))
    features = {"craters": craters, "scarp": scarp}
    return TraverseWorld(seed, cell, tuple(tuple(row) for row in elevation_cm), tuple(terrain), base,
                         tuple(targets), features)


def make_world(seed: int, max_ticks: int = 420, generator: Optional[Dict[str, Any]] = None) -> TraverseWorld:
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    rng = random.Random("lightlag-traverse-world:{}".format(seed))
    g = dict(GENERATOR, **(generator or {}))
    for _ in range(200):
        world = _attempt(rng, seed, g, max_ticks)
        if world is not None:
            return world
    raise RuntimeError("could not build a valid world for seed {}".format(seed))


def picture(world: TraverseWorld, step: int = 2) -> str:
    """A character map: terrain codes, # for ground too steep to drive, B the lander, digits target values."""
    surface = world.surface()
    safe = safe_nodes(surface, PHYSICS["max_tilt"] * SAFE_SHARE)
    marks = {(int(round(t.x / world.cell)), int(round(t.y / world.cell))): str(int(t.value)) if t.appear_tick == 0 else "*"
             for t in world.targets}
    marks[(int(round(world.base[0] / world.cell)), int(round(world.base[1] / world.cell)))] = "B"
    lines = []
    for j in range(surface.ny - 2, -1, -step):
        line = []
        for i in range(0, surface.nx - 1, step):
            mark = next((marks[(a, b)] for a in range(i, i + step) for b in range(j, j + step) if (a, b) in marks), None)
            line.append(mark or ("#" if not safe[j][i] else {"r": ".", "s": "~", "k": "o", "b": "="}[world.terrain[j][i]]))
        lines.append("".join(line))
    return "\n".join(lines)


if __name__ == "__main__":
    shown = make_world(int(sys.argv[1]) if len(sys.argv) > 1 else 7)
    print(picture(shown))
    heights = [v for row in shown.elevation_cm for v in row]
    print("relief {:.1f} m to {:.1f} m; {} targets, total value {:.0f}; base {}".format(
        min(heights) / 100, max(heights) / 100, len(shown.targets), sum(t.value for t in shown.targets), shown.base))
