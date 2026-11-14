"""Mission profiles: the public rule family plus one hidden instance per seed.

A mission is the physical World the team's simulator already understands, plus a
schedule saying when each target appears and until which tick it is worth full value.
"""

from dataclasses import asdict, dataclass, replace
import math
import random

from lightlag.model import Rect, Target, World

LATE_FRACTION = 0.25

# name: (random_map, windows, discoveries, generator, default horizon)
PROFILES = {
    "static": (False, False, False, None, 80),        # the team's map and rules, unchanged
    "windows": (False, True, False, None, 80),        # the team's map, targets with deadlines
    "random": (True, False, False, "standard", 80),   # a seeded map, no deadlines or discoveries
    "dynamic": (True, True, True, "standard", 80),    # seeded map, deadlines, mid-mission discoveries
    "rush": (True, True, True, "rush", 50),           # shorter mission, more, closer targets, tighter windows
    "noisy": (False, False, False, None, 80),         # the team's map with noisy sensing and heading drift
    "rush_noisy": (True, True, True, "rush", 50),     # rush with noisy sensing and heading drift
}

# Profiles whose telemetry is noisy and whose drives drift (see SENSING). Same maps as their
# noiseless twins for the same seed: "noisy" is "static", "rush_noisy" is "rush".
NOISY_PROFILES = ("noisy", "rush_noisy")

# Published sensing and drift model. All of it is listed in rules(); the seed fixes the draws.
SENSING = {
    "position_noise_m": 0.3,         # std dev, per axis, of every reported position fix
    "visual_odometry_noise": 0.05,   # std dev of the relative error of reported visual odometry
    "heading_bias_deg": 5.0,         # each episode starts with a hidden bias, uniform in +-5 degrees
    "heading_bias_walk_deg": 0.5,    # the bias then drifts: a random-walk step per executed drive
    "heading_noise_deg": 1.5,        # plus independent heading noise on every executed drive
}

# Deadlines for the "windows" profile on the team's fixed map: the last tick at which a
# sample command can execute and still earn full value. This is a difficulty dial.
FIXED_DEADLINES = {"north": 10, "west": 16, "east": 26}

# Experimental and off by default: bumpy ground. The map is split into 1 m cells; a seeded
# share of them (`bumpiness`) is rough and listed in map(). Entering a rough cell during a drive
# can make the wheels spin in place (wheel metres and energy spent, no progress) and gives the
# rover a small sideways jolt. Not part of any profile until the team decides.
ROUGHNESS = {
    "cell_m": 1.0,
    "spin_chance": 0.4,            # chance that entering a rough cell spins the wheels
    "spin_wheel_m": [0.3, 1.2],    # wheel metres lost to one spin, uniform in this range
    "jolt_m": 0.1,                 # std dev of the sideways jolt on entering a rough cell
}

# Published generator ranges for random maps. The seed only picks values inside them.
GENERATORS = {
    "standard": {
        "base": [20.0, 20.0],
        "sand_patches": 2, "sand_size_m": [8, 16],
        "hazards": 2, "hazard_size_m": [[2, 4], [1, 2.5]], "hazard_distance_m": [4, 13],
        "initial_targets": 3, "initial_distance_m": [5, 11], "initial_values": [1, 2, 3],
        "initial_deadline_tick": [18, 55],
        "discoveries": [1, 2], "discovery_appear_tick": [8, 32], "discovery_distance_m": [4, 10],
        "discovery_values": [2, 3], "discovery_window_ticks": [10, 18],
        "min_spacing_m": 3.5, "hazard_clearance_m": 1.2,
    },
    "rush": {
        "base": [20.0, 20.0],
        "sand_patches": 2, "sand_size_m": [6, 12],
        "hazards": 2, "hazard_size_m": [[2, 4], [1, 2.5]], "hazard_distance_m": [4, 10],
        "initial_targets": 5, "initial_distance_m": [3, 9], "initial_values": [1, 2],
        "initial_deadline_tick": [10, 32],
        "discoveries": [1, 2], "discovery_appear_tick": [6, 24], "discovery_distance_m": [3, 8],
        "discovery_values": [2, 3], "discovery_window_ticks": [6, 12],
        "min_spacing_m": 3.0, "hazard_clearance_m": 1.2,
    },
}

@dataclass(frozen=True)
class TargetPlan:
    id: str
    value: float
    deadline_tick: object = None  # int, or None for no window
    appear_tick: int = 0          # 0: known at launch; later: discovered mid-mission


@dataclass(frozen=True)
class Mission:
    profile: str
    world: World
    plans: tuple
    late_fraction: float = LATE_FRACTION
    noise_level: float = 1.0   # multiplies every SENSING value on the noisy profiles
    bumpiness: float = 0.0     # experimental: share of rough 1 m cells (see ROUGHNESS); 0 = off

    @property
    def sensing(self):
        if self.profile not in NOISY_PROFILES:
            return None
        return {name: value * self.noise_level for name, value in SENSING.items()}

    @property
    def roughness(self):
        return {**ROUGHNESS, "rough_fraction": self.bumpiness} if self.bumpiness > 0 else None

    def public_rules(self):
        random_map, windows, discoveries, generator, horizon = PROFILES[self.profile]
        return {
            "mission_profile": self.profile,
            "random_map": random_map,
            "sample_windows_enabled": windows,
            "discoveries_enabled": discoveries,
            "map_generator": GENERATORS[generator] if generator else None,
            "profile_default_horizon": horizon,
            "sensing": self.sensing,
            "noise_level": self.noise_level if self.profile in NOISY_PROFILES else None,
            "roughness": self.roughness,
        }

    def to_dict(self):
        return {"profile": self.profile, "late_fraction": self.late_fraction,
                "noise_level": self.noise_level, "bumpiness": self.bumpiness,
                "targets": [asdict(plan) for plan in self.plans]}


def make_mission(profile, seed, horizon=80, noise_level=1.0, bumpiness=0.0):
    mission = _make_mission(profile, seed, horizon)
    if not (0 <= noise_level <= 10 and 0 <= bumpiness <= 1):
        raise ValueError("noise_level must be in 0..10 and bumpiness in 0..1")
    return replace(mission, noise_level=float(noise_level), bumpiness=float(bumpiness))


def _make_mission(profile, seed, horizon=80):
    if profile not in PROFILES:
        raise ValueError(f"unknown profile {profile!r}; use one of {', '.join(PROFILES)}")
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    random_map, windows, discoveries, generator, _ = PROFILES[profile]
    if not random_map:
        world = World()
        plans = tuple(TargetPlan(t.id, t.value, FIXED_DEADLINES.get(t.id) if windows else None)
                      for t in world.targets)
        return Mission(profile, world, plans)
    rng = random.Random(f"lightlag-dynamic-map:{seed}")
    for _ in range(1000):
        mission = _random_mission(rng, profile, windows, discoveries, horizon, GENERATORS[generator])
        if mission is not None:
            return mission
    raise RuntimeError(f"could not generate a valid map for seed {seed}")


def _near_rect(rect, point, margin):
    x, y = point
    return rect.x1 - margin <= x <= rect.x2 + margin and rect.y1 - margin <= y <= rect.y2 + margin


def _random_mission(rng, profile, windows, discoveries, horizon, g):
    """Draw every random value in a fixed order, then apply the profile's switches.

    The same seed therefore gives the same geometry under "random" and "dynamic".
    """
    base = tuple(g["base"])
    sand = []
    for _ in range(g["sand_patches"]):
        w, h = rng.uniform(*g["sand_size_m"]), rng.uniform(*g["sand_size_m"])
        x1, y1 = rng.uniform(0, 40 - w), rng.uniform(0, 40 - h)
        sand.append(Rect(round(x1, 2), round(y1, 2), round(x1 + w, 2), round(y1 + h, 2)))
    hazards = []
    for _ in range(g["hazards"]):
        w, h = rng.uniform(*g["hazard_size_m"][0]), rng.uniform(*g["hazard_size_m"][1])
        if rng.random() < 0.5:
            w, h = h, w
        d, a = rng.uniform(*g["hazard_distance_m"]), rng.uniform(0, 2 * math.pi)
        cx, cy = base[0] + d * math.cos(a), base[1] + d * math.sin(a)
        hazards.append(Rect(round(cx - w / 2, 2), round(cy - h / 2, 2),
                            round(cx + w / 2, 2), round(cy + h / 2, 2)))

    def draw_point(distance_range):
        d, a = rng.uniform(*distance_range), rng.uniform(0, 2 * math.pi)
        return (round(base[0] + d * math.cos(a), 2), round(base[1] + d * math.sin(a), 2))

    initial = [(draw_point(g["initial_distance_m"]), rng.choice(g["initial_values"]),
                rng.randint(*g["initial_deadline_tick"])) for _ in range(g["initial_targets"])]
    count = rng.choice(g["discoveries"])
    found = []
    for _ in range(max(g["discoveries"])):
        point = draw_point(g["discovery_distance_m"])
        appear = rng.randint(*g["discovery_appear_tick"])
        found.append((point, rng.choice(g["discovery_values"]), appear,
                      appear + rng.randint(*g["discovery_window_ticks"])))
    found = found[:count]

    # Validity checks; on failure the caller draws again.
    if any(_near_rect(r, base, 1.5) for r in sand):
        return None
    if any(r.x1 < 0.5 or r.y1 < 0.5 or r.x2 > 39.5 or r.y2 > 39.5 or _near_rect(r, base, 2.5)
           for r in hazards):
        return None
    points = [base]
    # Check every drawn point, used or not, so validity never depends on the profile.
    candidates = [p for p, _, _ in initial] + [p for p, *_ in found]
    for p in candidates:
        if not (1 <= p[0] <= 39 and 1 <= p[1] <= 39):
            return None
        if any(_near_rect(r, p, g["hazard_clearance_m"]) for r in hazards):
            return None
        if any(math.dist(p, q) < g["min_spacing_m"] for q in points):
            return None
        points.append(p)

    targets, plans = [], []
    for i, (p, value, deadline) in enumerate(initial, 1):
        targets.append(Target(f"t{i}", p[0], p[1], value))
        plans.append(TargetPlan(f"t{i}", value, deadline if windows else None, 0))
    if discoveries:
        for j, (p, value, appear, deadline) in enumerate(found, 1):
            if appear + 1 > horizon:
                continue
            targets.append(Target(f"d{j}", p[0], p[1], value))
            plans.append(TargetPlan(f"d{j}", value, deadline if windows else None, appear))
    world = World(sand=tuple(sand), hazards=tuple(hazards), targets=tuple(targets))
    return Mission(profile, world, tuple(plans))
