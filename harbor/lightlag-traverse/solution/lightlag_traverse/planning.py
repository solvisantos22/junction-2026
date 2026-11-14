"""Planning for the traverse from public information only: where to drive, and in what order.

Two pieces, both built from `rules()` and `map()` and a controller's own estimates:

  * `Ground`: the height grid as a graph. An edge costs the ticks and the energy the published
    drive physics would take over it, with the slip the controller currently believes in.
    `field(goal)` is a cost-to-go from every vertex to one goal, so a rover that has drifted
    still knows the best way on from wherever it stands.
  * `plan_route`: which targets to visit and in which order, given deadlines, the time left,
    the battery and the sun. A greedy build, then local search.

Nothing here reads hidden state. Standard library only, Python 3.9+.
"""

from __future__ import annotations

import heapq
import math
import random
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .surface import TERRAIN_CODES, Surface

INF = float("inf")
STEPS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]


class Field:
    """Cost-to-go to one goal vertex: scalar cost, ticks and energy from every vertex, and the next vertex."""

    __slots__ = ("goal", "cost", "ticks", "energy", "step")

    def __init__(self, goal: int, cost: List[float], ticks: List[float], energy: List[float], step: List[int]) -> None:
        self.goal, self.cost, self.ticks, self.energy, self.step = goal, cost, ticks, energy, step


class Ground:
    def __init__(self, surface: Surface, physics: Dict[str, Any], slip_base: Dict[str, float],
                 max_metres: float = 5.0, energy_weight: float = 0.25, safe_share: float = 0.85) -> None:
        self.surface, self.physics = surface, physics
        self.nx, self.ny, self.cell = surface.nx, surface.ny, surface.cell
        self.max_metres = max_metres
        self.energy_weight = energy_weight
        self.tilt_safe = physics["max_tilt"] * safe_share
        nx, ny = self.nx, self.ny
        steep = [[surface.cell_max_slope(i, j) > self.tilt_safe for i in range(nx - 1)] for j in range(ny - 1)]
        self.safe = [False] * (nx * ny)
        for j in range(ny):
            for i in range(nx):
                self.safe[j * nx + i] = not any(
                    steep[b][a] for a in (i - 1, i) for b in (j - 1, j) if 0 <= a < nx - 1 and 0 <= b < ny - 1)
        # A vertex beside unsafe ground is allowed but costs more: the rover's position is never exact.
        self.edgy = [False] * (nx * ny)
        for j in range(ny):
            for i in range(nx):
                if self.safe[j * nx + i]:
                    self.edgy[j * nx + i] = any(
                        not (0 <= i + a < nx and 0 <= j + b < ny) or not self.safe[(j + b) * nx + i + a]
                        for a, b in STEPS)
        self.incoming: List[List[Tuple[int, float, float, float]]] = []
        self.rebuild(slip_base)

    # ---- edge costs -----------------------------------------------------------------
    def rebuild(self, slip_base: Dict[str, float]) -> None:
        """Recompute every edge with the slip values now believed."""
        self.slip_base = dict(slip_base)
        surface, physics, nx, ny, cell = self.surface, self.physics, self.nx, self.ny, self.cell
        gain, cost, climb = physics["slip_grade_gain"], physics["drive_cost_per_wheel_m"], physics["climb_cost_per_m"]
        per_code = {code: (slip_base[name], gain[name], cost[name]) for code, name in TERRAIN_CODES.items()}
        h, codes, safe, edgy = surface.h, surface.codes, self.safe, self.edgy
        weight, top = self.energy_weight, physics["slip_max"]
        incoming: List[List[Tuple[int, float, float, float]]] = [[] for _ in range(nx * ny)]
        for j in range(ny):
            for i in range(nx):
                a = j * nx + i
                if not safe[a]:
                    continue
                for di, dj in STEPS:
                    ti, tj = i + di, j + dj
                    if not (0 <= ti < nx and 0 <= tj < ny):
                        continue
                    b = tj * nx + ti
                    if not safe[b]:
                        continue
                    length = cell * (1.4142135623730951 if di and dj else 1.0)
                    rise = h[tj][ti] - h[j][i]
                    grade = rise / length if rise > 0 else 0.0
                    if di and dj:                      # a diagonal lies inside one cell
                        cells = [(min(i, ti), min(j, tj))]
                    elif di:                           # along a row: the cells above and below it
                        cells = [(min(i, ti), b2) for b2 in (j - 1, j) if 0 <= b2 < ny - 1]
                    else:
                        cells = [(a2, min(j, tj)) for a2 in (i - 1, i) if 0 <= a2 < nx - 1]
                    ticks = energy = 0.0
                    for ci, cj in cells:
                        base, grow, price = per_code[codes[cj][ci]]
                        slip = min(top, base + grow * grade)
                        wheel = length / (1.0 - slip)
                        ticks += wheel / self.max_metres
                        energy += wheel * price
                    ticks /= len(cells)
                    energy = energy / len(cells) + (climb * rise if rise > 0 else 0.0)
                    scalar = (ticks + weight * energy) * (1.5 if edgy[a] or edgy[b] else 1.0)
                    incoming[b].append((a, scalar, ticks, energy))
        self.incoming = incoming

    # ---- cost-to-go ------------------------------------------------------------------
    def node(self, x: float, y: float) -> Optional[int]:
        """The safe vertex nearest to a point, among the corners of its cell and their neighbours."""
        i0, j0 = int(round(x / self.cell)), int(round(y / self.cell))
        best, best_d = None, INF
        for reach in (0, 1, 2, 3):
            for j in range(j0 - reach, j0 + reach + 1):
                for i in range(i0 - reach, i0 + reach + 1):
                    if 0 <= i < self.nx and 0 <= j < self.ny and self.safe[j * self.nx + i]:
                        d = (i * self.cell - x) ** 2 + (j * self.cell - y) ** 2
                        if d < best_d:
                            best, best_d = j * self.nx + i, d
            if best is not None:
                return best
        return None

    def point(self, node: int) -> Tuple[float, float]:
        return (node % self.nx) * self.cell, (node // self.nx) * self.cell

    def field(self, goal: int) -> Field:
        """Dijkstra backwards from the goal: for every vertex, the cheapest way to get there."""
        count = self.nx * self.ny
        cost, ticks, energy, step = [INF] * count, [INF] * count, [INF] * count, [-1] * count
        cost[goal] = ticks[goal] = energy[goal] = 0.0
        heap = [(0.0, goal)]
        incoming = self.incoming
        while heap:
            c, n = heapq.heappop(heap)
            if c > cost[n]:
                continue
            tn, en = ticks[n], energy[n]
            for m, scalar, dt, de in incoming[n]:
                nc = c + scalar
                if nc < cost[m]:
                    cost[m], ticks[m], energy[m], step[m] = nc, tn + dt, en + de, n
                    heapq.heappush(heap, (nc, m))
        return Field(goal, cost, ticks, energy, step)

    # ---- straight lines --------------------------------------------------------------
    def straight(self, x0: float, y0: float, x1: float, y1: float, tilt: Optional[float] = None):
        """Ticks and energy to drive straight from one point to another, or None over unsafe ground."""
        distance = math.hypot(x1 - x0, y1 - y0)
        if distance < 1e-9:
            return 0.0, 0.0
        pieces = max(1, int(distance / 1.25 + 0.999))
        piece = distance / pieces
        ux, uy = (x1 - x0) / distance, (y1 - y0) / distance
        surface, physics = self.surface, self.physics
        gain, price, climb = physics["slip_grade_gain"], physics["drive_cost_per_wheel_m"], physics["climb_cost_per_m"]
        limit = self.tilt_safe if tilt is None else tilt
        wheel = energy = 0.0
        for k in range(pieces):
            at = (k + 0.5) * piece
            _, gx, gy, code = surface.sample(x0 + ux * at, y0 + uy * at)
            if gx * gx + gy * gy > limit * limit:
                return None
            name = TERRAIN_CODES[code]
            grade = gx * ux + gy * uy
            slip = min(0.9, self.slip_base[name] + gain[name] * (grade if grade > 0 else 0.0))
            turned = piece / (1.0 - slip)
            wheel += turned
            energy += turned * price[name] + (climb * grade * piece if grade > 0 else 0.0)
        return wheel / self.max_metres, energy

    def steer(self, x: float, y: float, field: Field, goal_xy: Tuple[float, float], reach: float = 14.0,
              near: float = 5.5):
        """Where to head from (x, y): the point within `reach` that makes the whole way to the goal cheapest.

        Returns (aim_x, aim_y, cost_to_go_ticks, cost_to_go_energy), or None if no safe line leaves (x, y).
        """
        best = None
        gx, gy = goal_xy
        direct = math.hypot(gx - x, gy - y)
        if direct <= reach * 1.5:
            leg = self.straight(x, y, gx, gy)
            if leg is not None:
                best = (leg[0] + self.energy_weight * leg[1], gx, gy, leg[0], leg[1])
        cell, nx, ny = self.cell, self.nx, self.ny
        i0, j0 = int(x / cell), int(y / cell)
        span = int(reach / cell) + 1
        cost, ticks, energy = field.cost, field.ticks, field.energy
        for j in range(max(0, j0 - span), min(ny, j0 + span + 2)):
            for i in range(max(0, i0 - span), min(nx, i0 + span + 2)):
                n = j * nx + i
                if cost[n] == INF:
                    continue
                px, py = i * cell, j * cell
                d = math.hypot(px - x, py - y)
                if d > reach or d < near:
                    continue                      # too far to see, or closer than one full drive
                if best is not None and cost[n] + d / self.max_metres >= best[0]:
                    continue                      # even over perfect ground this one cannot win
                leg = self.straight(x, y, px, py)
                if leg is None:
                    continue
                total = leg[0] + self.energy_weight * leg[1] + cost[n]
                if best is None or total < best[0]:
                    best = (total, px, py, leg[0] + ticks[n], leg[1] + energy[n])
        if best is None:
            return None
        return best[1], best[2], best[3], best[4]


# ------------------------------------------------------------------------------------ routes
class Sun:
    """The published sun curve, summed, so a stretch of driving can be charged in one step."""

    def __init__(self, rules: Dict[str, Any], efficiency: float) -> None:
        self.max_ticks = rules["max_ticks"]
        self.capacity = rules["battery_capacity"]
        self.idle = rules["idle_cost"]
        margin = rules["sun_margin_ticks"]
        peak = rules["solar_peak"] * efficiency
        self.rate = [peak * math.sin(math.pi * (t + margin) / (self.max_ticks + 2 * margin))
                     for t in range(self.max_ticks + 2)]
        self.total = [0.0]
        for t in range(1, self.max_ticks + 2):
            self.total.append(self.total[-1] + self.rate[t])

    def gained(self, start: float, end: float) -> float:
        """Solar energy over ticks start+1 .. end (fractions are interpolated)."""
        top = self.max_ticks + 1
        a, b = min(max(start, 0.0), top), min(max(end, 0.0), top)
        ia, ib = int(a), int(b)
        fa = self.total[ia] + (self.total[min(top, ia + 1)] - self.total[ia]) * (a - ia)
        fb = self.total[ib] + (self.total[min(top, ib + 1)] - self.total[ib]) * (b - ib)
        return fb - fa


class RouteProblem:
    """Everything `plan_route` needs, in arrays: the sites still open and what moving between them costs.

    Time is counted in whole ticks, each leg rounded to the nearest: measured on the pilot's own
    legs, the ground model's promise is right to about a tenth of a tick on average.
    """

    def __init__(self, sun: Sun, now: float, battery: float, values: Sequence[float],
                 deadlines: Sequence[Optional[float]], late_fraction: float,
                 start_ticks: Sequence[float], start_energy: Sequence[float],
                 ticks: Sequence[Sequence[float]], energy: Sequence[Sequence[float]],
                 home_ticks: Sequence[float], home_energy: Sequence[float],
                 start_home: Tuple[float, float], sample_cost: float,
                 stop_ticks: int = 1, home_margin: int = 4, deadline_margin: int = 1,
                 floor: float = 6.0, slack: float = 1.0) -> None:
        self.sun = sun
        self.count = len(values)
        self.values = list(values)
        self.late = [value * late_fraction for value in values]
        self.limit = int(sun.max_ticks - home_margin)
        self.deadlines = [self.limit + 1 if d is None else int(d) - deadline_margin for d in deadlines]
        self.now, self.battery = int(math.ceil(now)), battery
        big = 10 ** 6

        def whole(t: float) -> int:
            return big if t == INF else max(1, int(t * slack + 0.5))

        self.start_t = [whole(t) for t in start_ticks]
        self.start_e = [e * slack for e in start_energy]
        self.t = [[whole(t) for t in row] for row in ticks]
        self.e = [[e * slack for e in row] for row in energy]
        self.home_t = [whole(t) for t in home_ticks]
        self.home_e = [e * slack for e in home_energy]
        self.start_home = (whole(start_home[0]) if start_home[0] > 0.2 else 0, start_home[1] * slack)
        self.sample_cost, self.stop = sample_cost, int(stop_ticks)
        self.floor = floor
        # each site's nearest others, for moves that keep a route compact
        self.near = [sorted((s for s in range(self.count) if s != a),
                            key=lambda s: self.t[a][s] + self.t[s][a])[:10] for a in range(self.count)]

    def _leg(self, t: int, b: float, dt: int, de: float):
        """Drive one leg starting at tick t with battery b; wait for the sun first if it would run too low."""
        sun = self.sun
        total, idle, limit = sun.total, sun.idle, self.limit
        while True:
            end = t + dt
            if end > limit:
                return None
            after = b + total[end] - total[t] - idle * dt - de
            if after >= self.floor or de <= 0:
                return end, (sun.capacity if after > sun.capacity else after)
            gain = total[min(limit, t + 4)] - total[t] - idle * 4
            if gain <= 0.05:
                return None
            b = min(sun.capacity, b + gain)
            t += 4

    def score(self, order: Sequence[int]) -> Tuple[float, float]:
        """(value earned, finish tick) of visiting `order` then going home; value -1 if it cannot be done."""
        sun = self.sun
        total, idle, capacity, floor, limit = sun.total, sun.idle, sun.capacity, self.floor, self.limit
        t, b, value, last, stop = self.now, self.battery, 0.0, -1, self.stop
        for site in order:
            if last < 0:
                dt, de = self.start_t[site], self.start_e[site]
            else:
                dt, de = self.t[last][site], self.e[last][site]
            end = t + dt
            if end + stop > limit:
                return -1.0, INF
            after = b + total[end] - total[t] - idle * dt - de
            if after < floor:
                moved = self._leg(t, b, dt, de)
                if moved is None:
                    return -1.0, INF
                end, after = moved
                if end + stop > limit:
                    return -1.0, INF
            t = end + stop
            b = (capacity if after > capacity else after) + total[t] - total[end] - idle * stop - self.sample_cost
            if b < floor * 0.5:
                return -1.0, INF
            value += self.values[site] if t <= self.deadlines[site] else self.late[site]
            last = site
        dt, de = self.start_home if last < 0 else (self.home_t[last], self.home_e[last])
        if dt:
            moved = self._leg(t, b, dt, de)
            if moved is None:
                return -1.0, INF
            t = moved[0]
        return value, float(t)


def rebuild_route(problem: RouteProblem, steps: int = 100000, start: Optional[Sequence[int]] = None,
                  rng: Optional[random.Random] = None, heat: float = 1.5) -> Tuple[List[int], float]:
    """Iterated local search in the manner of Vansteenwegen and others for the orienteering problem
    with time windows: take a stretch of consecutive stops out of the route, then put sites back
    in one at a time, each where it costs least, choosing by (value gained) squared over time
    added. The square is what lets a distant cluster of valuable targets displace a string of
    cheap ones nearby: its first target is expensive, the rest then come almost free.

    `steps` is a budget of route evaluations, not seconds, so the same inputs give the same
    route on any machine. `start` is a route to begin from (the previous plan).
    """
    rng = rng or random.Random(0)
    count, near, score = problem.count, problem.near, problem.score
    used = [0]

    def look(order: Sequence[int]) -> Tuple[float, float]:
        used[0] += 1
        return score(order)

    def rate_of(value: float, finish: float) -> float:
        return value - 1e-4 * finish if value >= 0 else -1.0

    def places(order: List[int], site: int) -> List[int]:
        """Where a site may go: anywhere in a short route, beside its neighbours in a long one."""
        n = len(order)
        if n <= 8:
            return list(range(n + 1))
        spots = {0, n}
        close = near[site]
        for index, other in enumerate(order):
            if other in close:
                spots.add(index)
                spots.add(index + 1)
        return sorted(spots)

    def rebuild(order: List[int], value: float, finish: float, noise: float) -> Tuple[List[int], float, float]:
        """Insert sites until none fits: each time the one with the best gain squared per tick added."""
        while used[0] < steps:
            inside = set(order)
            best = None
            for site in range(count):
                if site in inside:
                    continue
                for position in places(order, site):
                    trial = order[:position] + [site] + order[position:]
                    new_value, new_finish = look(trial)
                    gain = new_value - value
                    if new_value < 0 or gain <= 1e-9:
                        continue
                    ratio = gain * gain / max(1.0, new_finish - finish)
                    if noise:
                        ratio *= 1.0 + noise * (rng.random() - 0.5)
                    if best is None or ratio > best[0]:
                        best = (ratio, trial, new_value, new_finish)
            if best is None:
                break
            order, value, finish = best[1], best[2], best[3]
        return order, value, finish

    def tidy(order: List[int], value: float, finish: float) -> Tuple[List[int], float, float]:
        """Move single stops and reverse stretches while that helps."""
        improved = True
        while improved and used[0] < steps:
            improved = False
            n = len(order)
            current = rate_of(value, finish)
            for i in range(n):
                site = order[i]
                rest = order[:i] + order[i + 1:]
                for j in places(rest, site):
                    if j == i:
                        continue
                    trial = rest[:j] + [site] + rest[j:]
                    new_value, new_finish = look(trial)
                    if rate_of(new_value, new_finish) > current + 1e-9:
                        order, value, finish, improved = trial, new_value, new_finish, True
                        break
                if improved:
                    break
            if improved:
                continue
            for i in range(n - 1):
                for j in range(i + 1, min(n, i + 7)):
                    trial = order[:i] + order[i:j + 1][::-1] + order[j + 1:]
                    new_value, new_finish = look(trial)
                    if rate_of(new_value, new_finish) > current + 1e-9:
                        order, value, finish, improved = trial, new_value, new_finish, True
                        break
                if improved:
                    break
        return order, value, finish

    seed = [site for site in (start or []) if 0 <= site < count]
    value, finish = look(seed)
    if value < 0:
        seed = []
        value, finish = look(seed)
    order, value, finish = rebuild(list(seed), value, finish, 0.0)
    order, value, finish = tidy(order, value, finish)
    best, best_value, best_finish = list(order), value, finish
    if not seed:                                   # a second opinion: build from nothing with noise
        for _ in range(3):
            if used[0] >= steps * 0.2:
                break
            other, other_value, other_finish = rebuild([], *look([]), 0.6)
            if rate_of(other_value, other_finish) > rate_of(best_value, best_finish):
                best, best_value, best_finish = other, other_value, other_finish
        order, value, finish = list(best), best_value, best_finish
    at, length, stale = 0, 1, 0
    while used[0] < steps and len(order) >= 1:
        n = len(order)
        at %= n
        cut = [order[(at + k) % n] for k in range(min(length, n))]
        trial = [site for site in order if site not in cut]
        trial_value, trial_finish = look(trial)
        if trial_value < 0:
            at += 1
            continue
        trial, trial_value, trial_finish = rebuild(trial, trial_value, trial_finish, 0.4)
        if rate_of(trial_value, trial_finish) > rate_of(best_value, best_finish) + 1e-9:
            trial, trial_value, trial_finish = tidy(trial, trial_value, trial_finish)
            best, best_value, best_finish = list(trial), trial_value, trial_finish
            order, value, finish = trial, trial_value, trial_finish
            length, stale = 1, 0
        else:
            stale += 1
            if rate_of(trial_value, trial_finish) >= rate_of(value, finish) - 0.5 * heat:
                order, value, finish = trial, trial_value, trial_finish      # wander a little
            if stale > 12:
                order, value, finish = list(best), best_value, best_finish
                stale = 0
        at += length
        length += 1
        if length > max(2, len(order) // 2):
            length = 1
    return best, max(0.0, best_value)


def anneal_route(problem: RouteProblem, steps: int = 100000, start: Optional[Sequence[int]] = None,
                 rng: Optional[random.Random] = None, heat: float = 1.5) -> Tuple[List[int], float]:
    """Annealing: a greedy build, then `steps` annealing moves that keep the route compact, then a last greedy
    fill. The budget is counted in moves, not seconds, so the same inputs give the same route on
    any machine. `start` is a route to begin from (the previous plan); with one, begin cooler so
    it is refined rather than shaken apart.
    """
    rng = rng or random.Random(0)
    count, near, score = problem.count, problem.near, problem.score

    def rate(order: Sequence[int]) -> float:
        value, finish = score(order)
        return value - 1e-4 * finish if value >= 0 else -1.0

    def fill(order: List[int]) -> List[int]:
        """Greedy: keep inserting the site that adds the most value per extra tick."""
        order = list(order)
        current, finish = score(order)
        if current < 0:
            return order
        while True:
            inside = set(order)
            best = None
            for site in range(count):
                if site in inside:
                    continue
                for position in range(len(order) + 1):
                    trial = order[:position] + [site] + order[position:]
                    value, end = score(trial)
                    if value <= current + 1e-9:
                        continue
                    gain = (value - current) / max(0.5, end - finish)
                    if best is None or gain > best[0]:
                        best = (gain, trial, value, end)
            if best is None:
                break
            order, current, finish = best[1], best[2], best[3]
        return order

    seed = [site for site in (start or []) if 0 <= site < count]
    if seed and rate(seed) < 0:
        seed = []
    if seed:
        best = fill(seed)
        heat *= 0.25
    else:
        best = fill([])
    best_rate = rate(best)
    current, current_rate = list(best), best_rate
    temperature = heat
    for step in range(steps):
        if step % 128 == 0:
            temperature = 0.03 + heat * (1.0 - step / steps) ** 2
        trial = list(current)
        n = len(trial)
        move = rng.random()
        if n == 0 or move < 0.30:                                  # put a site in beside one of its neighbours
            if n:
                at = rng.randrange(n)
                options = [site for site in near[trial[at]] if site not in trial]
                if not options:
                    options = [site for site in range(count) if site not in trial]
                    if not options:
                        continue
                trial.insert(at + rng.randint(0, 1), rng.choice(options))
            else:
                trial.append(rng.randrange(count))
        elif move < 0.38:                                          # ... or anywhere
            options = [site for site in range(count) if site not in trial]
            if not options:
                continue
            trial.insert(rng.randint(0, n), rng.choice(options))
        elif move < 0.50:                                          # take one out
            trial.pop(rng.randrange(n))
        elif move < 0.66 and n >= 2:                               # move one next to a neighbour of its
            site = trial.pop(rng.randrange(n))
            homes = [i for i, other in enumerate(trial) if other in near[site]]
            trial.insert((rng.choice(homes) + rng.randint(0, 1)) if homes else rng.randint(0, n - 1), site)
        elif move < 0.76 and n >= 2:                               # swap two
            i, j = rng.sample(range(n), 2)
            trial[i], trial[j] = trial[j], trial[i]
        elif move < 0.90 and n >= 2:                               # reverse a stretch
            i, j = sorted(rng.sample(range(n), 2))
            trial[i:j + 1] = trial[i:j + 1][::-1]
        else:                                                      # replace one by a neighbour left out
            at = rng.randrange(n)
            options = [site for site in near[trial[at]] if site not in trial]
            if not options:
                continue
            trial[at] = rng.choice(options)
        worth = rate(trial)
        if worth < 0:
            continue
        if worth >= current_rate or rng.random() < math.exp((worth - current_rate) / temperature):
            current, current_rate = trial, worth
            if worth > best_rate + 1e-9:
                best, best_rate = list(trial), worth
    polished = fill(best)
    if rate(polished) > best_rate:
        best = polished
    return best, max(0.0, score(best)[0])


def plan_route(problem: RouteProblem, steps: int = 100000, start: Optional[Sequence[int]] = None,
               rng: Optional[random.Random] = None, heat: float = 1.5) -> Tuple[List[int], float]:
    """A good order of sites to visit before going home, and its expected value.

    Two searches that get stuck in different places, each started from the other's best: the
    rebuild search finds which clusters are worth the trip, annealing then reorders and swaps
    within the route, and a last rebuild pass fills what that freed. The budget is counted in
    route evaluations, so the same inputs give the same route on any machine. `start` is a route
    to begin from (the previous plan).
    """
    rng = rng or random.Random(0)

    def worth(order: Sequence[int]) -> float:
        value, finish = problem.score(order)
        return value - 1e-4 * finish if value >= 0 else -1.0

    best = [site for site in (start or []) if 0 <= site < problem.count]
    if worth(best) < 0:
        best = []
    for search, share in ((rebuild_route, 0.45), (anneal_route, 0.35), (rebuild_route, 0.20)):
        found, _ = search(problem, max(200, int(steps * share)), best, rng, heat)
        if worth(found) > worth(best):
            best = found
    return best, max(0.0, problem.score(best)[0])
