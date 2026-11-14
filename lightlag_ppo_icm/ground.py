"""What the published map says about the ground, in the form the task adapter needs.

Everything here is read from rules() and map(): nothing hidden, no simulator object. A ground
answers three questions for the adapter:

    advance(...)   where a commanded drive is expected to end, on the published numbers (the
                   middle of each published slip range), and whether it is expected to be stopped
    rays(...)      how far it is, in each direction, to ground that stops the rover, to soft ground
                   and to ground the map marks as risky: the agent's view of its surroundings
    energy         what a tick, a wheel metre and a turn are expected to cost

RectGround is the flat 40 m family (lightlag_dynamic, its biomes and the max env): rectangles
on a plane. GridGround is Lightlag Traverse: a height grid with a terrain class per cell.
"""

import math

import numpy as np


def _rects(items):
    return np.array([[r["x1"], r["y1"], r["x2"], r["y2"]] for r in items], dtype=np.float64).reshape(-1, 4)


def _inside(rects, x, y):
    for x1, y1, x2, y2 in rects:
        if x1 <= x <= x2 and y1 <= y <= y2:
            return True
    return False


def _crosses(rects, x, y, nx, ny):
    """Does the segment touch a rectangle? The simulator's closed slab test."""
    for x1, y1, x2, y2 in rects:
        enter, leave, hit = 0.0, 1.0, True
        for origin, delta, low, high in ((x, nx - x, x1, x2), (y, ny - y, y1, y2)):
            if delta == 0:
                if not low <= origin <= high:
                    hit = False
                    break
                continue
            near, far = (low - origin) / delta, (high - origin) / delta
            if near > far:
                near, far = far, near
            enter, leave = max(enter, near), min(leave, far)
            if enter > leave:
                hit = False
                break
        if hit:
            return True
    return False


def _first_hit(rects, x, y, cos, sin):
    """Distance along each ray (cos, sin are arrays) to the first rectangle; inf when it meets none."""
    if not len(rects):
        return np.full(len(cos), np.inf)
    with np.errstate(divide="ignore", invalid="ignore"):
        ax, bx = (rects[None, :, 0] - x) / cos[:, None], (rects[None, :, 2] - x) / cos[:, None]
        ay, by = (rects[None, :, 1] - y) / sin[:, None], (rects[None, :, 3] - y) / sin[:, None]
        enter = np.maximum(np.minimum(ax, bx), np.minimum(ay, by))
        leave = np.minimum(np.maximum(ax, bx), np.maximum(ay, by))
        hit = leave >= np.maximum(enter, 0.0)
    return np.where(hit, np.maximum(enter, 0.0), np.inf).min(axis=1)


def _edge(x, y, cos, sin, width, height):
    """Distance along each ray to the edge of the map."""
    with np.errstate(divide="ignore", invalid="ignore"):
        tx = np.where(cos > 0, (width - x) / cos, np.where(cos < 0, -x / cos, np.inf))
        ty = np.where(sin > 0, (height - y) / sin, np.where(sin < 0, -y / sin, np.inf))
    return np.maximum(np.minimum(tx, ty), 0.0)


class RectGround:
    STEP = 0.5   # metres of wheel per step of the expected drive (a long drive takes four steps)

    def __init__(self, rules, public_map):
        self.width, self.height = float(public_map["width"]), float(public_map["height"])
        self.blocked = _rects(public_map.get("hazards", []))
        self.soft = _rects(public_map.get("sand", []))
        self.risky = _rects(list(public_map.get("crust_regions", [])) + list(public_map.get("rock_fields", [])))
        self.slip_mid = {name: 0.5 * (low + high) for name, (low, high) in rules["slip_ranges"].items()}
        self.slip_high = {name: float(high) for name, (low, high) in rules["slip_ranges"].items()}
        self.wheel_cost = {name: rules["drive_cost"] * factor
                           for name, factor in rules["terrain_drive_multipliers"].items()}
        self.idle = rules["idle_cost"]
        self.turn_cost = rules.get("turn_cost_per_degree", 0.0) * rules["drive_cost"]
        self.segment = rules.get("drive_integration_metres", 0.1)
        self.slip_limit = (rules.get("onboard_slip_check") or {}).get("limit")
        dunes = rules.get("dune_slip") or {}
        self.slip_per_degree = 0.5 * sum(dunes["slip_per_degree"]) if dunes else 0.0
        self.faces = [(f["x1"], f["y1"], f["x2"], f["y2"], f["slope_deg"]) for f in public_map.get("dune_faces", [])]
        self.firm_slip = self.slip_mid.get(public_map.get("default_terrain", "bedrock"), 0.0)
        self.soft_names = {"sand"}

    # ---- at a point --------------------------------------------------------------------------
    def soft_at(self, x, y):
        return _inside(self.soft, x, y)

    def risky_at(self, x, y):
        return _inside(self.risky, x, y)

    def slip_at(self, x, y, heading_deg=0.0):
        if not _inside(self.soft, x, y):
            return self.slip_mid["bedrock"]
        slope = max((s for x1, y1, x2, y2, s in self.faces if x1 <= x <= x2 and y1 <= y <= y2), default=0.0)
        return min(0.9, self.slip_mid["sand"] + self.slip_per_degree * slope)

    def tick_energy(self, tick):
        return self.idle

    def turn_energy(self, degrees, x, y):
        return self.turn_cost * degrees * (2.0 if self.turn_cost and self.soft_at(x, y) else 1.0)

    def metre_energy(self, x, y):
        """Energy per metre of ground covered from here on firm ground: for the way home."""
        return self.wheel_cost["bedrock"] / (1.0 - self.firm_slip)

    def worst_energy(self, x, y, heading_deg, wheel, turn_deg):
        """The most a drive can cost on the published numbers: every metre on the dearest ground
        (the map can call soft ground bedrock, and the belief can be off by a patch edge)."""
        dearest = max(self.wheel_cost.values())
        return wheel * dearest + self.turn_cost * turn_deg * dearest / self.wheel_cost["bedrock"]

    # ---- an expected drive ---------------------------------------------------------------------
    def advance(self, x, y, heading_deg, wheel, gr=1.0, gi=0.0, stops=True):
        """(dx, dy, wheel driven, energy, stopped) of a drive of `wheel` metres from (x, y).

        (dx, dy) is the displacement on the published numbers, along the commanded heading; the
        ground is looked up along the track corrected by the gain (gr, gi) that the belief has
        learned (a scale and a rotation). With `stops`, the drive ends where the published rules
        would end it: at a hazard or the map edge, or after one step on ground whose expected
        slip is over the onboard slip limit.
        """
        c, s = math.cos(math.radians(heading_deg)), math.sin(math.radians(heading_deg))
        ux, uy = gr * c - gi * s, gr * s + gi * c
        px, py, dx, dy, done, energy, stopped = x, y, 0.0, 0.0, 0.0, 0.0, False
        stride = max(self.STEP, wheel / 4.0)
        while done < wheel - 1e-9:
            step = min(stride, wheel - done)
            soft = _inside(self.soft, px, py)
            slip = self.slip_at(px, py) if soft else self.slip_mid["bedrock"]
            if stops and self.slip_limit is not None and slip > self.slip_limit:
                step, stopped = min(step, self.segment), True
            move = step * (1.0 - slip)
            nx, ny = px + ux * move, py + uy * move
            if stops and (not (0.0 <= nx <= self.width and 0.0 <= ny <= self.height)
                          or _crosses(self.blocked, px, py, nx, ny)):
                stopped = True
                break
            px, py = nx, ny
            dx, dy, done = dx + c * move, dy + s * move, done + step
            energy += step * self.wheel_cost["sand" if soft else "bedrock"]
            if stopped:
                break
        return dx, dy, done, energy, stopped

    # ---- the view around a point ------------------------------------------------------------------
    def rays(self, x, y, cos, sin, length):
        """Three arrays in 0..1, one entry per direction: distance to a stop, to soft ground, to
        risky ground, each as a share of `length` (1: nothing within reach)."""
        free = np.minimum(_first_hit(self.blocked, x, y, cos, sin), _edge(x, y, cos, sin, self.width, self.height))
        firm = _first_hit(self.soft, x, y, cos, sin)
        safe = _first_hit(self.risky, x, y, cos, sin)
        return tuple(np.minimum(d, length) / length for d in (free, firm, safe))


class GridGround:
    """Lightlag Traverse: heights on a grid, a terrain class per cell, a sun that charges the battery."""

    def __init__(self, rules, public_map):
        physics = rules["physics"]
        self.cell = float(public_map["cell_m"])
        self.h = np.array(public_map["elevation_cm"], dtype=np.float64) / 100.0
        codes = public_map["terrain_codes"]
        self.names = [[codes[ch] for ch in row] for row in public_map["terrain"]]
        self.ny, self.nx = self.h.shape
        self.width, self.height = float(public_map["width"]), float(public_map["height"])
        self.max_tilt = physics["max_tilt"]
        self.slip_mid = {name: 0.5 * (low + high) for name, (low, high) in physics["slip_base_ranges"].items()}
        self.grade_gain = dict(physics["slip_grade_gain"])
        self.slip_max = physics["slip_max"]
        self.wheel_cost = dict(physics["drive_cost_per_wheel_m"])
        self.climb_cost = physics["climb_cost_per_m"]
        self.idle = rules["idle_cost"]
        self.solar = rules["solar_peak"] * 0.5 * sum(rules["solar_efficiency_range"])
        self.margin, self.horizon = rules["sun_margin_ticks"], rules["max_ticks"]
        self.turn_cost = rules.get("turn_cost_per_degree", 0.0)
        self.slip_limit = (rules.get("onboard_slip_check") or {}).get("limit")
        self.segment = physics["segment_m"]
        self.STEP = max(1.0, self.cell / 4.0)
        self.risky = _rects(public_map.get("crust_regions", []))
        self.firm_slip = self.slip_mid["bedrock"]
        self.soft_names = {name for name, mid in self.slip_mid.items() if mid >= 0.2}

    def _sample(self, x, y):
        """Height gradient (gx, gy) and terrain name at a point, as the published formula gives them."""
        fx, fy = x / self.cell, y / self.cell
        i = min(self.nx - 2, max(0, int(fx)))
        j = min(self.ny - 2, max(0, int(fy)))
        tx, ty = fx - i, fy - j
        h = self.h
        h00, h10, h01, h11 = h[j, i], h[j, i + 1], h[j + 1, i], h[j + 1, i + 1]
        gx = ((h10 - h00) * (1 - ty) + (h11 - h01) * ty) / self.cell
        gy = ((h01 - h00) * (1 - tx) + (h11 - h10) * tx) / self.cell
        return gx, gy, self.names[j][i]

    def soft_at(self, x, y):
        return self._sample(x, y)[2] in self.soft_names

    def risky_at(self, x, y):
        return _inside(self.risky, x, y)

    def slip_at(self, x, y, heading_deg=0.0):
        gx, gy, name = self._sample(x, y)
        grade = gx * math.cos(math.radians(heading_deg)) + gy * math.sin(math.radians(heading_deg))
        return min(self.slip_max, self.slip_mid[name] + self.grade_gain[name] * max(0.0, grade))

    def tick_energy(self, tick):
        sun = math.sin(math.pi * (tick + self.margin) / (self.horizon + 2 * self.margin))
        return self.idle - self.solar * sun

    def turn_energy(self, degrees, x, y):
        return self.turn_cost * degrees * self.wheel_cost[self._sample(x, y)[2]] if self.turn_cost else 0.0

    def metre_energy(self, x, y):
        return self.wheel_cost["regolith"] / (1.0 - self.slip_mid["regolith"])

    def worst_energy(self, x, y, heading_deg, wheel, turn_deg):
        """The most a drive is taken to cost: the dearest ground, climbing a little steeper than here."""
        gx, gy, _ = self._sample(x, y)
        dearest = max(self.wheel_cost.values())
        climb = self.climb_cost * min(self.max_tilt, math.hypot(gx, gy) + 0.1)
        return wheel * (dearest + climb) + self.turn_cost * turn_deg * dearest

    def advance(self, x, y, heading_deg, wheel, gr=1.0, gi=0.0, stops=True):
        c, s = math.cos(math.radians(heading_deg)), math.sin(math.radians(heading_deg))
        ux, uy = gr * c - gi * s, gr * s + gi * c
        px, py, dx, dy, done, energy, stopped = x, y, 0.0, 0.0, 0.0, 0.0, False
        while done < wheel - 1e-9:
            step = min(self.STEP, wheel - done)
            gx, gy, name = self._sample(px, py)
            grade = gx * ux + gy * uy
            slip = min(self.slip_max, self.slip_mid[name] + self.grade_gain[name] * max(0.0, grade))
            if stops and self.slip_limit is not None and slip > self.slip_limit:
                step, stopped = min(step, self.segment), True
            move = step * (1.0 - slip)
            nx, ny = px + ux * move, py + uy * move
            if stops:
                if not (0.0 <= nx <= self.width and 0.0 <= ny <= self.height):
                    stopped = True
                    break
                ngx, ngy, _ = self._sample(nx, ny)
                if math.hypot(ngx, ngy) > self.max_tilt:
                    stopped = True
                    break
            px, py = nx, ny
            dx, dy, done = dx + c * move, dy + s * move, done + step
            energy += step * self.wheel_cost[name] + self.climb_cost * max(0.0, grade) * move
            if stopped:
                break
        return dx, dy, done, energy, stopped

    def rays(self, x, y, cos, sin, length):
        """As RectGround.rays, by walking each ray in quarter-cell steps."""
        step = self.cell / 4.0
        count = max(1, int(math.ceil(length / step)))
        free, firm, safe = np.full(len(cos), length), np.full(len(cos), length), np.full(len(cos), length)
        for k in range(len(cos)):
            blocked = soft = False
            for n in range(count + 1):
                d = min(length, n * step)
                px, py = x + cos[k] * d, y + sin[k] * d
                if not (0.0 <= px <= self.width and 0.0 <= py <= self.height):
                    if not blocked:
                        free[k], blocked = d, True
                    break
                gx, gy, name = self._sample(px, py)
                if not blocked and n > 0 and math.hypot(gx, gy) > self.max_tilt:
                    free[k], blocked = d, True
                if not soft and name in self.soft_names:
                    firm[k], soft = d, True
                if blocked and soft:
                    break
        risky = _first_hit(self.risky, x, y, cos, sin)
        return free / length, firm / length, np.minimum(risky, length) / length


def make_ground(rules, public_map):
    if "physics" in rules and "elevation_cm" in public_map:
        return GridGround(rules, public_map)
    return RectGround(rules, public_map)
