"""The dynamic environment with a selectable biome on top.

    env = make_biome_env("troy_crust", seed=7, delay=3, profile="rush_noisy")

"main_mars" (the default) adds nothing: its rules, map, telemetry and replay are identical to
lightlag_dynamic's DynamicEnvironment for the same seed, profile and delay (a test checks it).
Every other biome is published in rules()["biome"], with its numbers in rules() and its areas
in map(); only what the seed draws inside the published ranges is hidden, and that shows up in
telemetry. Biomes can be mixed with "+", for example "troy_crust+relay_pass".

This class sits on the scenario and Mars sandbox environments (manh_controllers/scenarios.py
and mars.py), which already hold most of the mechanics as test factors:

    relay_pass          the "windows" factor, plus telemetry held back to the next pass
    hidden_valley       the "slip_check" factor
    meridiani_ripples   the "vo_by_terrain" factor
    gale_rock_field     the experimental rough cells, placed in rock fields, plus wheel wear
    troy_crust          new: published crust regions with hidden soft cells
    bagnold_dunes       new: sand slip that grows with the published slope of a dune face

It relies on these private hooks of the classes below it (checked by
tests/lightlag_dynamic/test_biomes.py): _rough_cells, _roughness, _spins, _snapshot, _drive,
_announced, _slip, _world, _x, _y, _config, _mission, factors.

A sandbox option, not a rules decision. Standard library only.
"""

from dataclasses import replace
import math
import random

from lightlag import Config
from lightlag.model import Rect
from lightlag_dynamic.manh_controllers.mars import MarsEnvironment
from lightlag_dynamic.missions import NOISY_PROFILES, PROFILES, ROUGHNESS, SENSING

from .catalog import MAIN, biome_settings, describe, parse_biome


class _CrustWorld:
    """The real world, with soft cells under ground the published map calls bedrock."""

    def __init__(self, world, soft, cell_m):
        self._w, self.soft, self.cell_m = world, soft, cell_m

    def __getattr__(self, name):
        return getattr(self._w, name)

    def terrain_at(self, x, y):
        if (int(x // self.cell_m), int(y // self.cell_m)) in self.soft:
            return "sand"
        return self._w.terrain_at(x, y)


class _DuneSlip:
    """The slip table the drive loop reads, with the dune rule on sand.

    The team's drive loop looks up `slip[terrain]` once per 0.1 m step, right after it has read
    the terrain under the rover. Looking up "sand" here adds slip_per_degree times the slope of
    the dune face under the rover, so the loop itself stays untouched. Copies and iteration give
    the plain per-seed coefficients.
    """

    def __init__(self, coefficients, env):
        self.coefficients, self._env = dict(coefficients), env

    def __getitem__(self, terrain):
        value = self.coefficients[terrain]
        if terrain == "sand":
            value += self._env.slip_per_degree * self._env.slope_at(self._env._x, self._env._y)
        return value

    def __setitem__(self, terrain, value):
        self.coefficients[terrain] = value

    def __contains__(self, terrain):
        return terrain in self.coefficients

    def __len__(self):
        return len(self.coefficients)

    def __iter__(self):  # pairs, so dict(table) is the plain coefficients
        return iter(self.coefficients.items())

    def __deepcopy__(self, memo):
        return dict(self.coefficients)


def _cells_in(rects, cell_m):
    cells = set()
    for r in rects:
        for ix in range(int(round(r["x1"] / cell_m)), int(round(r["x2"] / cell_m))):
            for iy in range(int(round(r["y1"] / cell_m)), int(round(r["y2"] / cell_m))):
                cells.add((ix, iy))
    return cells


def place_regions(tag, seed, world, plans, count, size_m, clearance, cell_m=1.0):
    """Seeded rectangles on whole cells, each across the straight line from base to a target.

    A region is centred 35-65% of the way from the base to one of the targets known at launch
    (a different target for each region), then moved outward along that line until it is at
    least `clearance` metres from the base. Published in rules() as the placement rule.
    """
    rng = random.Random(f"lightlag-biome-{tag}:{seed}")
    bx, by = world.base
    launch = [t for t in world.targets if plans[t.id].appear_tick == 0]
    rng.shuffle(launch)
    regions = []
    for target in launch[:count]:
        frac = rng.uniform(0.35, 0.65)
        w, h = rng.uniform(*size_m), rng.uniform(*size_m)
        distance = math.hypot(target.x - bx, target.y - by) or 1.0
        ux, uy = (target.x - bx) / distance, (target.y - by) / distance
        along = frac * distance
        for _ in range(200):
            cx, cy = bx + ux * along, by + uy * along
            x1 = max(0.0, math.floor((cx - w / 2) / cell_m) * cell_m)
            y1 = max(0.0, math.floor((cy - h / 2) / cell_m) * cell_m)
            x2 = min(world.width, math.ceil((cx + w / 2) / cell_m) * cell_m)
            y2 = min(world.height, math.ceil((cy + h / 2) / cell_m) * cell_m)
            gap = math.hypot(max(x1 - bx, 0.0, bx - x2), max(y1 - by, 0.0, by - y2))
            if gap >= clearance and x2 - x1 >= cell_m and y2 - y1 >= cell_m:
                regions.append({"x1": x1, "y1": y1, "x2": x2, "y2": y2})
                break
            along += 0.25
    return regions


class BiomeEnvironment(MarsEnvironment):
    def __init__(self, seed=0, config=None, profile="rush_noisy", biome=MAIN, settings=None,
                 sensing=None, exact_telemetry=False, factors=None, noise_level=1.0):
        ids = parse_biome(biome)
        self.biome_ids = () if ids == (MAIN,) else ids
        self.biome_settings = biome_settings(ids, settings) if self.biome_ids else {}
        cfg = self.biome_settings
        factors = dict(factors or {})
        horizon = config.max_ticks if config is not None else PROFILES[profile][4]

        def claim(name, value):
            if name in factors:
                raise ValueError(f"the {name} factor is set by the biome; do not pass it as well")
            factors[name] = value

        self._passes = None
        if "relay_pass" in cfg:
            period, open_ = cfg["relay_pass"]["period_ticks"], cfg["relay_pass"]["open_ticks"]
            if not (type(period) is int and type(open_) is int and 1 <= open_ <= period):
                raise ValueError("relay passes need whole ticks with 1 <= open_ticks <= period_ticks")
            if open_ < period:  # open all the time is the unchanged link
                self._passes = (period, open_)
                claim("windows", (period, open_))
        if "hidden_valley" in cfg:
            c = cfg["hidden_valley"]
            limit = c["limit_long_missions"] if horizon >= c["long_mission_ticks"] else c["limit"]
            claim("slip_check", {"limit": limit})
        if "meridiani_ripples" in cfg:
            claim("vo_by_terrain", dict(cfg["meridiani_ripples"]["visual_odometry_noise_by_terrain"]))
            if sensing is None and profile not in NOISY_PROFILES:
                sensing = {name: value * noise_level for name, value in SENSING.items()}
        bumpiness = cfg["gale_rock_field"]["rough_share"] if "gale_rock_field" in cfg else 0.0
        wear = cfg.get("gale_rock_field") or {}
        self._wear_budget, self._worn_max = wear.get("budget_cells"), wear.get("worn_max_metres")
        # Read by hooks the parent constructors call, so they exist before super().__init__.
        self.rock_fields, self.crust_regions, self.dune_fields, self.dune_faces = [], [], [], []
        self.soft_cells, self.slip_per_degree, self._drives_limited = frozenset(), 0.0, 0
        super().__init__(seed=seed, config=config, profile=profile, sensing=sensing,
                         exact_telemetry=exact_telemetry, factors=factors, noise_level=noise_level,
                         bumpiness=bumpiness)
        plans = {plan.id: plan for plan in self._mission.plans}
        if "bagnold_dunes" in cfg:
            if "slip_change" in self.factors or "hidden_patches" in self.factors:
                raise ValueError("bagnold_dunes cannot be mixed with the slip_change or hidden_patches factor")
            c = cfg["bagnold_dunes"]
            # Dune fields are ordinary mapped sand, added to the published map before anything moves.
            self.dune_fields = place_regions("dunes", seed, self._mission.world, plans, c["fields"],
                                             c["field_size_m"], c["base_clearance_m"])
            world = self._mission.world
            world = replace(world, sand=world.sand + tuple(Rect(**f) for f in self.dune_fields))
            self._mission = replace(self._mission, world=world)
            self._world = world
            rng = random.Random(f"lightlag-biome-dunes:{seed}")
            self.slip_per_degree = rng.uniform(*c["slip_per_degree"])
            self.dune_faces = self._dune_faces(rng, c)
            self._slip = _DuneSlip(self._slip, self)
        if "troy_crust" in cfg:
            c = cfg["troy_crust"]
            self.crust_regions = place_regions("crust", seed, self._mission.world, plans, c["regions"],
                                               c["region_size_m"], c["base_clearance_m"], c["cell_m"])
            rng = random.Random(f"lightlag-biome-crust-cells:{seed}")
            inside = _cells_in(self.crust_regions, c["cell_m"])
            # One draw per map cell in a fixed order, so a higher soft_rate only adds cells.
            soft = set()
            for ix in range(int(math.ceil(self._mission.world.width / c["cell_m"]))):
                for iy in range(int(math.ceil(self._mission.world.height / c["cell_m"]))):
                    if rng.random() < c["soft_rate"] and (ix, iy) in inside:
                        soft.add((ix, iy))
            self.soft_cells = frozenset(soft)
            self._world = _CrustWorld(self._world, self.soft_cells, c["cell_m"])

    # ---- generators --------------------------------------------------------------------
    def _rough_cells(self, seed, mission):
        """Rough cells inside the rock fields only (the parent scatters them over the whole map)."""
        c = self.biome_settings["gale_rock_field"]
        plans = {plan.id: plan for plan in mission.plans}
        self.rock_fields = place_regions("rocks", seed, mission.world, plans, c["fields"],
                                         c["field_size_m"], c["base_clearance_m"], ROUGHNESS["cell_m"])
        inside = _cells_in(self.rock_fields, ROUGHNESS["cell_m"])
        world, size = mission.world, ROUGHNESS["cell_m"]
        rng = random.Random(f"lightlag-biome-rock-cells:{seed}")
        # Launch targets only: a hole in the rocks must not give away a later discovery.
        keep_clear = [world.base] + [(t.x, t.y) for t in world.targets if plans[t.id].appear_tick == 0]
        cells = set()
        for ix in range(int(math.ceil(world.width / size))):
            for iy in range(int(math.ceil(world.height / size))):
                draw = rng.random()
                centre = ((ix + 0.5) * size, (iy + 0.5) * size)
                if (draw < mission.bumpiness and (ix, iy) in inside
                        and all(math.dist(centre, p) > 1.5 for p in keep_clear)):
                    cells.add((ix, iy))
        return frozenset(cells)

    def _dune_faces(self, rng, c):
        """Each mapped sand patch, cut across its longer side into faces about face_width_m wide."""
        faces = []
        for r in self._mission.world.sand:
            along_x = (r.x2 - r.x1) >= (r.y2 - r.y1)
            length = (r.x2 - r.x1) if along_x else (r.y2 - r.y1)
            count = max(1, int(round(length / c["face_width_m"])))
            for i in range(count):
                a, b = i * length / count, (i + 1) * length / count
                slope = round(rng.uniform(*c["slope_deg"]) * 2) / 2
                face = ({"x1": round(r.x1 + a, 3), "y1": r.y1, "x2": round(r.x1 + b, 3), "y2": r.y2}
                        if along_x else
                        {"x1": r.x1, "y1": round(r.y1 + a, 3), "x2": r.x2, "y2": round(r.y1 + b, 3)})
                faces.append({**face, "slope_deg": slope})
        return faces

    def slope_at(self, x, y):
        """Slope in degrees of the dune face under (x, y); 0 off the dunes."""
        return max((f["slope_deg"] for f in self.dune_faces
                    if f["x1"] <= x <= f["x2"] and f["y1"] <= y <= f["y2"]), default=0.0)

    # ---- public tools ---------------------------------------------------------------------
    def rules(self):
        rules = super().rules()
        if not self.biome_ids:
            return rules
        cfg = self.biome_settings
        rules["biome"] = describe(self.biome_ids)
        placement = ("each is centred 35-65% of the way from the base to a different target known at "
                     "launch, on whole cells, at least base_clearance_m from the base")
        if "relay_pass" in cfg:
            rules["relay_passes"] = dict(cfg["relay_pass"])
        if "troy_crust" in cfg:
            rules["crust"] = {**cfg["troy_crust"], "placement": placement}
        if "gale_rock_field" in cfg:
            c = cfg["gale_rock_field"]
            rules["roughness"] = {**ROUGHNESS, "rough_share_in_fields": c["rough_share"]}
            rules["rock_fields"] = {"fields": c["fields"], "field_size_m": c["field_size_m"],
                                    "base_clearance_m": c["base_clearance_m"], "placement": placement,
                                    "rough_cells": "rough_share of the cells in a field, none within "
                                                   "1.5 m of the base or of a target known at launch"}
            rules["wheel_wear"] = {"budget_cells": c["budget_cells"], "worn_max_metres": c["worn_max_metres"],
                                   "telemetry": "wheel_wear in every packet: rough cells entered so far"}
        if "bagnold_dunes" in cfg:
            rules["dune_slip"] = {**cfg["bagnold_dunes"], "placement": placement,
                                  "dune_fields": "listed in map() and included in its sand list"}
        return rules

    def map(self):
        public = super().map()
        if self.crust_regions:
            public["crust_regions"] = [dict(r) for r in self.crust_regions]
        if "gale_rock_field" in self.biome_settings:
            public["rock_fields"] = [dict(r) for r in self.rock_fields]
        if "bagnold_dunes" in self.biome_settings:
            public["dune_fields"] = [dict(f) for f in self.dune_fields]
            public["dune_faces"] = [dict(f) for f in self.dune_faces]
        return public

    # ---- evaluator-only ---------------------------------------------------------------------
    def replay(self):
        replay = super().replay()
        if self.biome_ids:
            replay["biome"] = {
                "ids": list(self.biome_ids), "settings": self.biome_settings,
                "names": [entry["name"] for entry in describe(self.biome_ids)],
                "crust_regions": self.crust_regions, "soft_cells": [list(c) for c in sorted(self.soft_cells)],
                "rock_fields": self.rock_fields, "rough_cells": [list(c) for c in sorted(self._rough)],
                "wheel_wear": len(self._spins), "drives_limited": self._drives_limited,
                "dune_fields": self.dune_fields, "dune_faces": self.dune_faces,
                "slip_per_degree": self.slip_per_degree,
                "relay_passes": list(self._passes) if self._passes else None,
            }
        return replay

    # ---- hooks -----------------------------------------------------------------------------
    def _arrival(self, tick):
        """The first tick at or after `tick` at which a relay pass is open."""
        if self._passes:
            period, open_ = self._passes
            if tick % period >= open_:
                return (tick // period + 1) * period
        return tick

    def _announced(self, plan):
        if not self._passes:
            return super()._announced(plan)
        return plan.appear_tick == 0 or self._tick >= self._arrival(plan.appear_tick + self._config.delay_ticks)

    def _snapshot(self, wheel, visual, events):
        packet = super()._snapshot(wheel, visual, events)
        if self._passes:
            packet["received_tick"] = self._arrival(packet["received_tick"])
        if self._wear_budget is not None:
            packet["wheel_wear"] = len(self._spins)
        return packet

    def _drive(self, command, events):
        if self._wear_budget is None:
            return super()._drive(command, events)
        if len(self._spins) > self._wear_budget and command["metres"] > self._worn_max + 1e-9:
            command = dict(command, metres=self._worn_max)
            events.append({"type": "drive_limited", "reason": "wheel_wear", "metres": self._worn_max})
            self._drives_limited += 1
        before = len(self._spins)
        result = super()._drive(command, events)
        if before <= self._wear_budget < len(self._spins):
            events.append({"type": "wheels_worn", "max_metres_per_drive": self._worn_max})
        return result


def make_biome_env(biome=MAIN, seed=0, delay=3, profile="rush_noisy", horizon=None, **kw):
    """One episode of `profile` in `biome`. `kw`: settings, sensing, factors, noise_level, exact_telemetry."""
    if profile not in PROFILES:
        raise ValueError(f"unknown profile {profile!r}; use one of {', '.join(PROFILES)}")
    horizon = PROFILES[profile][4] if horizon is None else horizon
    return BiomeEnvironment(seed=seed, config=Config(delay_ticks=delay, max_ticks=horizon),
                            profile=profile, biome=biome, **kw)
