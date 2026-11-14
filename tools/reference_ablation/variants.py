"""Public-data-only pilot variants. No simulator import and no canonical edits.

The cubature variant changes only heading-uncertainty propagation of the nominal
odometry displacement. It does not integrate the full terrain dynamics at every
sigma point, and must not be described as a complete nonlinear terrain filter.
"""

import math

from lightlag_traverse.pilot import Filter, Pilot
from lightlag_traverse.planning import Sun


VARIANTS = {
    "baseline": {"component": "reference", "options": {}},
    "est_cubature": {"component": "estimation", "filter": "cubature"},
    "est_process_double": {"component": "estimation", "process_scale": 2.0},
    "slip_fast": {"component": "slip", "slip_weight": 0.25},
    "slip_cautious": {"component": "slip", "options": {"slip_prior": 0.75}},
    "path_energy_low": {"component": "path", "options": {"energy_weight": 0.125}},
    "path_energy_high": {"component": "path", "options": {"energy_weight": 0.5}},
    "search_more": {"component": "search", "options": {
        "plan_steps": 450000, "replan_steps": 37500, "beam": 900, "rebeam": 180}},
    "search_frequent": {"component": "search", "options": {"replan_every": 6}},
    "deadline_earlier": {"component": "timing", "options": {"deadline_margin": 4}},
    "legs_cautious": {"component": "timing", "options": {"leg_slack": 1.05}},
    "energy_reserve_lower": {"component": "energy", "options": {"floor": 3.5}},
    "home_later": {"component": "home", "options": {"home_margin": 2.0}},
    "arrival_wider": {"component": "arrival", "options": {"arrive_m": 1.3}},
    "solar_prior_mid": {"component": "solar", "solar_prior": 0.5},
}


def cholesky3(matrix):
    """Lower square root of a positive semidefinite 3x3 covariance."""
    root = [[0.0] * 3 for _ in range(3)]
    for i in range(3):
        for j in range(i + 1):
            value = (matrix[i][j] + matrix[j][i]) / 2 - sum(root[i][k] * root[j][k] for k in range(j))
            if i == j:
                if value < -1e-8:
                    raise ValueError("non-positive covariance")
                root[i][j] = math.sqrt(max(0.0, value))
            elif root[j][j] > 1e-15:
                root[i][j] = value / root[j][j]
            elif abs(value) > 1e-8:
                raise ValueError("singular inconsistent covariance")
    return root


class CubatureFilter(Filter):
    def move(self, dx, dy, distance, heading_rad):
        root = cholesky3(self.P)
        points = []
        for col in range(3):
            for sign in (-1, 1):
                offset = [sign * math.sqrt(3) * root[row][col] for row in range(3)]
                angle = heading_rad + math.radians(offset[2])
                points.append([
                    self.x + offset[0] + dx + distance * (math.cos(angle) - math.cos(heading_rad)),
                    self.y + offset[1] + dy + distance * (math.sin(angle) - math.sin(heading_rad)),
                    self.bias + offset[2],
                ])
        mean = [sum(p[i] for p in points) / 6 for i in range(3)]
        covariance = [[sum((p[i] - mean[i]) * (p[j] - mean[j]) for p in points) / 6
                       for j in range(3)] for i in range(3)]
        q = (0.04 * distance) ** 2 + (distance * self.heading_noise) ** 2 + 0.01
        covariance[0][0] += q
        covariance[1][1] += q
        covariance[2][2] += self.walk_var
        self.x, self.y, self.bias = mean
        self.P = covariance


class ProcessScaledFilter(Filter):
    def __init__(self, x, y, sensing, scale):
        super().__init__(x, y, sensing)
        self.scale = scale

    def move(self, dx, dy, distance, heading_rad):
        super().move(dx, dy, distance, heading_rad)
        extra = (self.scale - 1) * ((0.04 * distance) ** 2 + (distance * self.heading_noise) ** 2 + 0.01)
        self.P[0][0] += extra
        self.P[1][1] += extra


def combine(names):
    result = {"component": "combined", "members": list(names), "options": {}}
    components = set()
    for name in names:
        spec = VARIANTS[name]
        if spec["component"] in components:
            raise ValueError("only one variant per component can be combined")
        components.add(spec["component"])
        for key, value in spec.items():
            if key == "component":
                continue
            if key == "options":
                if set(result[key]) & set(value):
                    raise ValueError("overlapping options")
                result[key].update(value)
            elif key in result:
                raise ValueError("overlapping variant controls")
            else:
                result[key] = value
    return result


class VariantPilot(Pilot):
    """The baseline with explicit opt-in changes and passive belief recording."""
    def __init__(self, tools, spec, options=None):
        super().__init__(tools, {**spec.get("options", {}), **(options or {})})
        if spec.get("filter") == "cubature":
            self.filter = CubatureFilter(*self.base, self.rules["sensing"])
        elif "process_scale" in spec:
            self.filter = ProcessScaledFilter(*self.base, self.rules["sensing"], spec["process_scale"])
        if "slip_weight" in spec:
            for values in self.slip_seen.values():
                values[0] = spec["slip_weight"]
        if "solar_prior" in spec:
            low, high = self.rules["solar_efficiency_range"]
            self.efficiency = low + spec["solar_prior"] * (high - low)
            self.sun = Sun(self.rules, self.efficiency)
        self.beliefs = []
        self.predictions = []

    def _packet(self, packet):
        super()._packet(packet)
        f = self.filter
        self.beliefs.append({"tick": packet["tick"], "x": f.x, "y": f.y, "bias": f.bias,
                             "sigma": f.sigma, "covariance": [list(row) for row in f.P]})

    def _decide(self, tick, x, y, sigma, battery):
        self.predictions.append({"tick": tick, "x": x, "y": y, "sigma": sigma, "battery": battery})
        return super()._decide(tick, x, y, sigma, battery)


def fly(tools, spec, options=None):
    pilot = VariantPilot(tools, spec, options)
    while True:
        pilot.act()
        out = tools.advance(1)
        pilot.observe(out["packets"], out["current_tick"])
        if out["episode_complete"]:
            return pilot
