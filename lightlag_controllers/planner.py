"""Path and route planning over the public map.

A grid search gives energy-optimal paths around hazards and through or around
costly terrain. Route choice then enumerates the few possible target orders and
keeps the best one the battery and the clock allow.
"""

from __future__ import annotations

import heapq
import itertools
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from .model import Rect, Rules, Target, World, distance, heading_to
from .physics import SlipOf, path_energy, wheel_for_distance

Point = Tuple[float, float]
BASE = "base"

_MOVES = (
    (1, 0), (0, 1), (-1, 0), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1),
    (2, 1), (1, 2), (-1, 2), (-2, 1), (-2, -1), (-1, -2), (1, -2), (2, -1),
)


class CostGrid:
    """Free cells and their neighbours, built once per map."""

    def __init__(self, world: World, cell: float = 0.5, margin: float = 0.5) -> None:
        self.world = world
        self.cell = cell
        self.margin = margin
        self.nx = max(1, int(math.ceil(world.width / cell)))
        self.ny = max(1, int(math.ceil(world.height / cell)))
        self.inflated: Tuple[Rect, ...] = tuple(h.inflate(margin) for h in world.hazards)
        edge = min(margin, cell / 2.0)
        size = self.nx * self.ny
        self.free: List[bool] = [False] * size
        self.terrain: List[str] = [world.default_terrain] * size
        near_hazard: List[bool] = [False] * size
        reach = 2.5 * cell
        watch = tuple(h.inflate(reach) for h in self.inflated)
        for ix in range(self.nx):
            for iy in range(self.ny):
                i = ix * self.ny + iy
                x, y = self.center(i)
                self.terrain[i] = world.terrain_at(x, y)
                inside = edge <= x <= world.width - edge and edge <= y <= world.height - edge
                self.free[i] = inside and not any(h.contains(x, y) for h in self.inflated)
                near_hazard[i] = any(h.contains(x, y) for h in watch)
        self.neighbors: List[List[Tuple[int, float]]] = [[] for _ in range(size)]
        for ix in range(self.nx):
            for iy in range(self.ny):
                i = ix * self.ny + iy
                if not self.free[i]:
                    continue
                ax, ay = self.center(i)
                for dx, dy in _MOVES:
                    jx, jy = ix + dx, iy + dy
                    if not (0 <= jx < self.nx and 0 <= jy < self.ny):
                        continue
                    j = jx * self.ny + jy
                    if not self.free[j]:
                        continue
                    if near_hazard[i] or near_hazard[j]:
                        bx, by = self.center(j)
                        if any(h.intersects_segment(ax, ay, bx, by) for h in self.inflated):
                            continue
                    self.neighbors[i].append((j, math.hypot(dx, dy) * cell))

    def center(self, index: int) -> Point:
        ix, iy = divmod(index, self.ny)
        return ((ix + 0.5) * self.cell, (iy + 0.5) * self.cell)

    def cell_of(self, x: float, y: float) -> int:
        ix = min(self.nx - 1, max(0, int(x / self.cell)))
        iy = min(self.ny - 1, max(0, int(y / self.cell)))
        return ix * self.ny + iy

    def nearest_free(self, x: float, y: float) -> Optional[int]:
        start = self.cell_of(x, y)
        if self.free[start]:
            return start
        sx, sy = divmod(start, self.ny)
        best: Optional[int] = None
        best_d = math.inf
        for radius in range(1, max(self.nx, self.ny)):
            for ix in range(sx - radius, sx + radius + 1):
                for iy in range(sy - radius, sy + radius + 1):
                    if max(abs(ix - sx), abs(iy - sy)) != radius:
                        continue
                    if not (0 <= ix < self.nx and 0 <= iy < self.ny):
                        continue
                    i = ix * self.ny + iy
                    if self.free[i]:
                        cx, cy = self.center(i)
                        d = math.hypot(cx - x, cy - y)
                        if d < best_d:
                            best, best_d = i, d
            if best is not None and best_d <= radius * self.cell:
                return best
        return best

    def tree(self, root: int, cost_per_m: Dict[str, float]) -> Tuple[List[float], List[int]]:
        """Dijkstra from `root`: energy to every cell and the next cell toward the root."""
        size = self.nx * self.ny
        dist = [math.inf] * size
        toward = [-1] * size
        dist[root] = 0.0
        heap: List[Tuple[float, int]] = [(0.0, root)]
        cell_cost = [cost_per_m[name] for name in self.terrain]
        while heap:
            d, i = heapq.heappop(heap)
            if d > dist[i]:
                continue
            ci = cell_cost[i]
            for j, length in self.neighbors[i]:
                nd = d + length * (ci + cell_cost[j]) / 2.0
                if nd < dist[j]:
                    dist[j] = nd
                    toward[j] = i
                    heapq.heappush(heap, (nd, j))
        return dist, toward


@dataclass(frozen=True)
class Leg:
    energy: float
    commands: int
    waypoints: Tuple[Point, ...]  # excludes the start, ends at the goal

    @property
    def reachable(self) -> bool:
        return math.isfinite(self.energy)


@dataclass(frozen=True)
class Route:
    targets: Tuple[str, ...]  # target ids in visiting order
    end_at_base: bool
    score: float
    energy: float
    commands: int


UNREACHABLE = Leg(math.inf, 0, ())


class RoutePlanner:
    def __init__(
        self, world: World, rules: Rules, cell: float = 0.5, margin: float = 0.5, terrain_margin: float = 0.5
    ) -> None:
        # Plan as if costly terrain were slightly larger than mapped. A path that
        # skirts a sand patch by centimetres ends up inside it after a little drift,
        # at twice the energy; this keeps planned paths clear of the edge.
        default_cost = rules.terrains[world.default_terrain].drive_cost
        padded = tuple(
            (rect.inflate(terrain_margin) if rules.terrains[name].drive_cost > default_cost else rect, name)
            for rect, name in world.patches
        )
        world = World(
            world.width, world.height, world.base, world.targets, world.hazards, padded, world.default_terrain
        )
        self.world = world
        self.rules = rules
        self.grid = CostGrid(world, cell, margin)
        self._keys: Dict[str, Point] = {BASE: world.base}
        for target in world.targets:
            self._keys[target.id] = (target.x, target.y)
        self._roots: Dict[str, Optional[int]] = {k: self.grid.nearest_free(x, y) for k, (x, y) in self._keys.items()}
        self._costs: Dict[str, float] = {}
        self._trees: Dict[str, Tuple[List[float], List[int]]] = {}
        self._key_legs: Dict[Tuple[str, str], Leg] = {}
        self._slip_of: SlipOf = lambda name: rules.terrains[name].slip_mid
        self.rebuilds = 0

    def update(self, slip_of: SlipOf, tolerance: float = 0.01) -> bool:
        """Refresh energy costs from slip estimates. Returns True if paths were rebuilt."""
        costs = {
            name: spec.drive_cost / max(0.05, 1.0 - slip_of(name))
            for name, spec in self.rules.terrains.items()
        }
        if self._costs and all(abs(costs[n] - self._costs[n]) <= tolerance * self._costs[n] for n in costs):
            return False
        self._costs = costs
        frozen = {name: slip_of(name) for name in self.rules.terrains}
        self._slip_of = lambda name: frozen[name]
        self._trees = {}
        self._key_legs = {}
        self.rebuilds += 1
        return True

    def _tree(self, key: str) -> Optional[Tuple[List[float], List[int]]]:
        root = self._roots[key]
        if root is None:
            return None
        if key not in self._trees:
            self._trees[key] = self.grid.tree(root, self._costs)
        return self._trees[key]

    def _clear(self, a: Point, b: Point) -> bool:
        """Straight line A to B keeps the safety margin (except around its own ends)."""
        if not self.world.in_bounds(b[0], b[1]):
            return False
        for hazard, inflated in zip(self.world.hazards, self.grid.inflated):
            touching_end = inflated.contains(a[0], a[1]) or inflated.contains(b[0], b[1])
            box = hazard if touching_end else inflated
            if box.intersects_segment(a[0], a[1], b[0], b[1]):
                return False
        return True

    def leg(self, start: Point, key: str) -> Leg:
        """Cheapest known way from `start` to a key point (base or a target)."""
        tree = self._tree(key)
        goal = self._keys[key]
        if tree is None:
            return UNREACHABLE
        dist, toward = tree
        if distance(start[0], start[1], goal[0], goal[1]) <= 1e-6:
            return Leg(0.0, 0, ())
        if self._clear(start, goal) and self._straight_is_cheap(start, goal, dist):
            points: List[Point] = [start, goal]
        else:
            cell = self.grid.nearest_free(start[0], start[1])
            if cell is None or not math.isfinite(dist[cell]):
                return UNREACHABLE
            points = [start]
            while cell != -1:
                points.append(self.grid.center(cell))
                cell = toward[cell]
            if self._clear(points[-1], goal):
                points.append(goal)
            points = self._simplify(points)
        energy = 0.0
        commands = 0
        for a, b in zip(points, points[1:]):
            energy += path_energy(self.world, self.rules, self._slip_of, a[0], a[1], b[0], b[1])
            wheel = wheel_for_distance(
                self.world, self.rules, self._slip_of, a[0], a[1], heading_to(a[0], a[1], b[0], b[1]),
                distance(a[0], a[1], b[0], b[1]),
            )
            commands += max(1, int(math.ceil(wheel / self.rules.max_drive - 1e-9)))
        return Leg(energy, commands, tuple(points[1:]))

    def _straight_is_cheap(self, start: Point, goal: Point, dist: Sequence[float]) -> bool:
        cell = self.grid.nearest_free(start[0], start[1])
        if cell is None or not math.isfinite(dist[cell]):
            return True
        straight = path_energy(self.world, self.rules, self._slip_of, start[0], start[1], goal[0], goal[1])
        return straight <= dist[cell] * 1.02 + 0.5

    def _simplify(self, points: List[Point]) -> List[Point]:
        """Drop collinear points, then cut corners where a straight line is safe and no dearer."""
        if len(points) <= 2:
            return points
        kept: List[Point] = [points[0]]
        for prev, here, nxt in zip(points, points[1:], points[2:]):
            cross = (here[0] - prev[0]) * (nxt[1] - here[1]) - (here[1] - prev[1]) * (nxt[0] - here[0])
            if abs(cross) > 1e-9:
                kept.append(here)
        kept.append(points[-1])

        def cost(a: Point, b: Point) -> float:
            return path_energy(self.world, self.rules, self._slip_of, a[0], a[1], b[0], b[1])

        out: List[Point] = [kept[0]]
        i = 0
        while i < len(kept) - 1:
            best = i + 1
            running = cost(kept[i], kept[i + 1])
            for j in range(i + 2, len(kept)):
                running += cost(kept[j - 1], kept[j])
                if self._clear(kept[i], kept[j]) and cost(kept[i], kept[j]) <= running * 1.01 + 1e-6:
                    best = j
            out.append(kept[best])
            i = best
        return out

    def key_leg(self, a: str, b: str) -> Leg:
        if (a, b) not in self._key_legs:
            self._key_legs[(a, b)] = self.leg(self._keys[a], b)
        return self._key_legs[(a, b)]

    def evaluate(
        self,
        start: Point,
        order: Sequence[str],
        end_at_base: bool,
        first_leg: Optional[Leg] = None,
    ) -> Tuple[float, int]:
        """Energy and command count for visiting `order` from `start`."""
        energy = 0.0
        commands = 0
        previous: Optional[str] = None
        for key in list(order) + ([BASE] if end_at_base else []):
            if previous is None:
                leg = first_leg if first_leg is not None else self.leg(start, key)
            else:
                leg = self.key_leg(previous, key)
            if not leg.reachable:
                return math.inf, 0
            energy += leg.energy
            commands += leg.commands
            if key != BASE:
                energy += self.rules.sample_cost
                commands += 1
            previous = key
        return energy, commands

    def best_route(
        self,
        start: Point,
        remaining: Sequence[Target],
        energy_budget: float,
        ticks_left: int,
        ticks_per_command: int = 1,
        energy_margin: float = 0.06,
        banked: float = 0.0,
        first_among: Optional[Sequence[str]] = None,
    ) -> Route:
        """Highest-scoring feasible plan: which targets, in what order, and whether to return.

        `banked` is the value already sampled. The end-of-episode factor multiplies
        it too, so giving up the return to base costs half of everything collected.
        `first_among` restricts the first target visited, when given.
        """
        values = {t.id: t.value for t in remaining}
        first_legs = {key: self.leg(start, key) for key in list(values) + [BASE]}
        best = Route((), False, banked * 0.5, 0.0, 0)
        for count in range(0, len(values) + 1):
            for order in itertools.permutations(values, count):
                if first_among is not None and (not order or order[0] not in first_among):
                    continue
                for end_at_base in (True, False):
                    if not order and not end_at_base:
                        continue
                    first_key = order[0] if order else BASE
                    energy, commands = self.evaluate(start, order, end_at_base, first_legs[first_key])
                    if energy * (1.0 + energy_margin) > energy_budget:
                        continue
                    if commands * ticks_per_command > ticks_left:
                        continue
                    score = (banked + sum(values[k] for k in order)) * (1.0 if end_at_base else 0.5)
                    candidate = Route(tuple(order), end_at_base, score, energy, commands)
                    if (candidate.score, candidate.end_at_base, -candidate.energy) > (
                        best.score, best.end_at_base, -best.energy,
                    ):
                        best = candidate
        return best
