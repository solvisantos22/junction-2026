"""The way home, for the home guard: a cost-to-go field over the published map.

    field = HomeField(ground, base, base_radius)
    field.left(x, y, reach)      -> (ground metres, wheel metres, heading of the first leg, metres of sand)
    field.waypoint(x, y, reach)  -> where the next drive home should aim, at most `reach` away
    field.learn_trip()           -> a drive was stopped by the onboard slip check: sand stops every step

Built from the published map only, and only for the flat 40 m family (RectGround); the traverse has
its own pilots. The grid is half a metre. A cell is closed when its centre lies within `clearance`
of a hazard, which is more than half a cell's diagonal, so a straight line between two open
neighbours never touches a hazard. A metre of ground costs the energy the published numbers expect
(the wheel cost over one minus the middle of the slip range). Ground where an unexpected stop is
possible costs `stop_penalty` times that: soft ground whose published slip range reaches over the
onboard slip check, and ground the map marks as risky (crust that can hide soft cells, rock
fields). The way home goes around such ground when the detour is cheap enough and across it when
not. Where the straight line to the base touches none of it, the way home is that line.

Sand that trips the slip check stops every drive step on it (the sand of a map shares one hidden
slip), and the queue is cleared each time, so a rover on it moves one step, about 6 cm, per round
trip of the link: with relay passes, per pass. A rover that drives onto such sand can lose the
rest of the mission. So where the published slip range of sand reaches over the slip check, and
elsewhere from the first stop the check makes (field.learn_trip()), sand is taken to stop every
step (`sand_stops`): a metre of sand, or of ground within `clearance` of it, costs `trip_penalty`
times as much, so the way home keeps clear of sand whenever the map leaves a way around, and
`into_sand` tells the guard which drives would enter it. Crust and rock fields keep `stop_penalty`.
"""

import heapq
import math

import numpy as np

from .ground import RectGround, _crosses


class HomeField:
    def __init__(self, ground, base, base_radius, cell=0.5, clearance=0.4, stop_penalty=2.0, trip_penalty=25.0):
        if not isinstance(ground, RectGround):
            raise ValueError("the home guard is built for the flat 40 m family (lightlag_dynamic, its biomes, "
                             "the max env); the traverse is not supported")
        self.ground, self.base, self.cell = ground, (float(base[0]), float(base[1])), float(cell)
        self.settle = 0.5 * float(base_radius)     # inside this the rover is taken to be home
        self.nx, self.ny = int(math.ceil(ground.width / cell)), int(math.ceil(ground.height / cell))
        self.blocked = ground.blocked.copy()
        if len(self.blocked):
            self.blocked[:, :2] -= 0.05            # a hair of margin for the straight lines
            self.blocked[:, 2:] += 0.05
        limit = ground.slip_limit
        self.sand_stops = limit is not None and ground.slip_high.get("sand", 0.0) > limit
        soft = ground.soft if self.sand_stops else np.zeros((0, 4))
        self.unsure = np.concatenate([soft, ground.risky]).reshape(-1, 4)
        self.near = ground.blocked + np.array([-0.5, -0.5, 0.5, 0.5]) if len(ground.blocked) else ground.blocked
        self.clearance, self.stop_penalty = float(clearance), float(stop_penalty)
        self.trip_penalty = float(trip_penalty)
        self._solved = None                        # built the first time the straight line will not do

    def learn_trip(self):
        """The onboard slip check stopped a drive: from now on sand is taken to stop every step."""
        if self.sand_stops:
            return
        self.sand_stops = True
        self.unsure = np.concatenate([self.ground.soft, self.ground.risky]).reshape(-1, 4)
        self._solved = None

    # ---- queries ------------------------------------------------------------------------------
    def home(self, x, y):
        return math.hypot(self.base[0] - x, self.base[1] - y) <= self.settle

    def straight(self, x, y):
        """Is the straight line to the base clear of hazards and of ground that can stop the rover?"""
        bx, by = self.base
        return not (_crosses(self.blocked, x, y, bx, by) or _crosses(self.unsure, x, y, bx, by))

    def may_stop(self, x, y, nx, ny):
        """Can a drive from (x, y) to (nx, ny) be stopped where the published numbers do not expect
        it: across ground that can trip the slip check or hide soft cells, or close past a hazard?"""
        return bool(_crosses(self.unsure, x, y, nx, ny) or _crosses(self.near, x, y, nx, ny))

    def into_sand(self, x, y, nx, ny):
        """Where sand stops every step: does a drive from (x, y) to (nx, ny) touch sand?"""
        return self.sand_stops and bool(_crosses(self.ground.soft, x, y, nx, ny))

    def left(self, x, y, reach):
        """(ground metres, wheel metres, heading of the first leg in degrees, ground metres on sand)
        of the way home from (x, y), on the expected slip; (0, 0, None, 0) when the rover is home."""
        if self.home(x, y):
            return 0.0, 0.0, None, 0.0
        per_wheel = 1.0 - self.ground.slip_at(x, y)
        if self.straight(x, y):
            d = math.hypot(self.base[0] - x, self.base[1] - y)
            sand = d if self.ground.soft_at(x, y) else 0.0   # only when sand cannot stop the rover
            return d, d / per_wheel, math.degrees(math.atan2(self.base[1] - y, self.base[0] - x)), sand
        solved = self._solve()
        k = self._cell(x, y)
        if solved["ground"][k] == math.inf:       # walled in on the map: take the straight line
            d = math.hypot(self.base[0] - x, self.base[1] - y)
            sand = d if _crosses(self.ground.soft, x, y, *self.base) else 0.0
            return d, d / per_wheel, math.degrees(math.atan2(self.base[1] - y, self.base[0] - x)), sand
        cx, cy = self._centre(k)
        first = math.hypot(cx - x, cy - y)
        wx, wy = self.waypoint(x, y, reach)
        heading = math.degrees(math.atan2(wy - y, wx - x)) if (wx, wy) != (x, y) else 0.0
        sand = (first if self.ground.soft_at(x, y) else 0.0) + solved["sand"][k]
        return first + solved["ground"][k], first / per_wheel + solved["wheel"][k], heading, sand

    def waypoint(self, x, y, reach):
        """The point the next drive home aims at: the base if it is in a straight line and within
        reach, else the furthest point of the field's way home that is within reach and in a
        straight line from (x, y)."""
        bx, by = self.base
        if self.straight(x, y) and math.hypot(bx - x, by - y) <= reach:
            return bx, by
        if self.straight(x, y):
            d = math.hypot(bx - x, by - y)
            return x + (bx - x) * reach / d, y + (by - y) * reach / d
        solved = self._solve()
        k = self._cell(x, y)
        best, first = self._centre(k), True
        while solved["next"][k] >= 0:
            n = solved["next"][k]
            cx, cy = self._centre(n)
            if math.hypot(cx - x, cy - y) > reach or _crosses(self.blocked, x, y, cx, cy):
                break
            if not first and not solved["sandy"][n] and self.into_sand(x, y, cx, cy):
                break                              # a short cut across sand that the way home goes around
            best, k, first = (cx, cy), n, False
        if solved["next"][k] < 0 and self.straight(*best) and math.hypot(bx - x, by - y) <= reach \
                and not _crosses(self.blocked, x, y, bx, by):
            return bx, by
        return best

    # ---- the grid -----------------------------------------------------------------------------
    def _centre(self, k):
        i, j = divmod(k, self.ny)
        return (i + 0.5) * self.cell, (j + 0.5) * self.cell

    def _cell(self, x, y):
        """The cell under (x, y), or the nearest open one when that is closed (the rover hugs a hazard)."""
        solved = self._solve()
        i = min(self.nx - 1, max(0, int(x / self.cell)))
        j = min(self.ny - 1, max(0, int(y / self.cell)))
        if not solved["closed"][i * self.ny + j]:
            return i * self.ny + j
        best = None
        for r in range(1, max(self.nx, self.ny)):
            for a in range(max(0, i - r), min(self.nx, i + r + 1)):
                for b in range(max(0, j - r), min(self.ny, j + r + 1)):
                    k = a * self.ny + b
                    if not solved["closed"][k]:
                        cx, cy = self._centre(k)
                        d = math.hypot(cx - x, cy - y)
                        if best is None or d < best[0]:
                            best = (d, k)
            if best is not None:
                return best[1]
        return i * self.ny + j

    def _solve(self):
        if self._solved is not None:
            return self._solved
        g, nx, ny, cell = self.ground, self.nx, self.ny, self.cell
        xs, ys = (np.arange(nx) + 0.5) * cell, (np.arange(ny) + 0.5) * cell
        X, Y = np.meshgrid(xs, ys, indexing="ij")

        def inside(rects, pad=0.0):
            mask = np.zeros((nx, ny), dtype=bool)
            for x1, y1, x2, y2 in rects:
                mask |= (X >= x1 - pad) & (X <= x2 + pad) & (Y >= y1 - pad) & (Y <= y2 + pad)
            return mask

        closed = inside(g.blocked, self.clearance) | (X > g.width) | (Y > g.height)
        soft = inside(g.soft)
        slip = np.where(soft, g.slip_mid.get("sand", g.firm_slip), g.slip_mid.get("bedrock", g.firm_slip))
        for x1, y1, x2, y2, slope in g.faces:
            on = soft & (X >= x1) & (X <= x2) & (Y >= y1) & (Y <= y2)
            slip = np.where(on, np.minimum(0.9, np.maximum(slip, g.slip_mid["sand"] + g.slip_per_degree * slope)), slip)
        wheel_cost = np.where(soft, g.wheel_cost.get("sand", g.wheel_cost["bedrock"]), g.wheel_cost["bedrock"])
        per_wheel = 1.0 / (1.0 - slip)                      # wheel metres per metre of ground
        cost = wheel_cost * per_wheel * np.where(inside(self.unsure), self.stop_penalty, 1.0)
        sandy = inside(g.soft, self.clearance)               # sand, and the cells whose edges touch it
        if self.sand_stops:
            cost = cost * np.where(sandy, self.trip_penalty, 1.0)

        n = nx * ny
        closed_f, cost_f, wheel_f = closed.ravel().tolist(), cost.ravel().tolist(), per_wheel.ravel().tolist()
        soft_f = soft.ravel().tolist()
        dist, nxt = [math.inf] * n, [-1] * n
        bx, by = self.base
        reach = max(self.settle, 0.75 * cell)
        heap = []
        for i in range(max(0, int((bx - reach) / cell) - 1), min(nx, int((bx + reach) / cell) + 2)):
            for j in range(max(0, int((by - reach) / cell) - 1), min(ny, int((by + reach) / cell) + 2)):
                k = i * ny + j
                cx, cy = (i + 0.5) * cell, (j + 0.5) * cell
                if not closed_f[k] and math.hypot(cx - bx, cy - by) <= reach:
                    dist[k] = 0.0
                    heap.append((0.0, k))
        heapq.heapify(heap)
        moves = [(di, dj, cell * math.hypot(di, dj)) for di in (-1, 0, 1) for dj in (-1, 0, 1) if di or dj]
        while heap:
            d, k = heapq.heappop(heap)
            if d > dist[k]:
                continue
            i, j = divmod(k, ny)
            for di, dj, length in moves:
                a, b = i + di, j + dj
                if 0 <= a < nx and 0 <= b < ny:
                    m = a * ny + b
                    if closed_f[m]:
                        continue
                    if di and dj and (closed_f[a * ny + j] or closed_f[i * ny + b]):
                        continue                              # no cutting a closed corner
                    nd = d + length * 0.5 * (cost_f[k] + cost_f[m])
                    if nd < dist[m]:
                        dist[m], nxt[m] = nd, k
                        heapq.heappush(heap, (nd, m))
        ground_left, wheel_left, sand_left = [math.inf] * n, [math.inf] * n, [math.inf] * n
        for k in sorted(range(n), key=dist.__getitem__):
            if dist[k] == math.inf:
                break
            if nxt[k] < 0:
                ground_left[k] = wheel_left[k] = sand_left[k] = 0.0
                continue
            m = nxt[k]
            (ax, ay), (cx, cy) = self._centre(k), self._centre(m)
            length = math.hypot(cx - ax, cy - ay)
            ground_left[k] = ground_left[m] + length
            wheel_left[k] = wheel_left[m] + length * 0.5 * (wheel_f[k] + wheel_f[m])
            sand_left[k] = sand_left[m] + length * 0.5 * (soft_f[k] + soft_f[m])
        self._solved = {"closed": closed_f, "next": nxt, "cost": dist, "ground": ground_left, "wheel": wheel_left,
                        "sand": sand_left, "sandy": sandy.ravel().tolist()}
        return self._solved
