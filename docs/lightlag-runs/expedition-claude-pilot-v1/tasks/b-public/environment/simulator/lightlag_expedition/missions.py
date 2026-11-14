"""Seeded regional geometry, independent of episode qualities and rover physics."""

from copy import deepcopy
import math
import random

from lightlag.model import Rect, Target, World
from lightlag_dynamic.missions import Mission, TargetPlan

from .model import REGIONS


GENERATOR = {
    "name": "expedition-regional-v1", "width": 40, "height": 40, "base": [20.0, 20.0],
    "regional_bearing_offsets_deg": [0, 120, 240],
    "global_rotation_deg": [0, 360], "target_bearing_jitter_deg": [-30, 30],
    "regions": {
        "r1": {"distance_m": [4, 7], "initial_values": [2, 2], "deadline_tick": [18, 32]},
        "r2": {"distance_m": [6, 10], "initial_values": [3, 3], "deadline_tick": [26, 44]},
        "r3": {"distance_m": [5, 9], "initial_values": [2, 2], "deadline_tick": [22, 40]},
    },
    "discoveries": [
        {"id": "d1", "region": "r2", "value": 3, "appear_tick": 10, "deadline_tick": 26},
        {"id": "d2", "region": "r3", "value": 3, "appear_tick": 22, "deadline_tick": 44},
    ],
    "sand_patches": 2, "sand_size_m": [6, 12], "sand_base_clearance_m": 1.5,
    "hazards": 2, "hazard_size_m": [[2, 4], [1, 2.5]], "hazard_distance_m": [4, 10],
    "min_spacing_m": 2.0, "hazard_clearance_m": 1.2, "hazard_base_clearance_m": 2.5,
    "target_edge_clearance_m": 1.0, "hazard_edge_clearance_m": 0.5,
    "clearance_metric": "axis-aligned expanded rectangles; target spacing is Euclidean",
    "coordinate_decimals": 2, "max_mission_attempts": 1000, "max_component_attempts": 100,
    "sampling": "uniform continuous ranges; integer inclusive deadlines; reject invalid geometry",
}


def generator_rules():
    return deepcopy(GENERATOR)


def _near_rect(rect, point, margin):
    x, y = point
    return rect.x1 - margin <= x <= rect.x2 + margin and rect.y1 - margin <= y <= rect.y2 + margin


def make_mission(mission_seed=0):
    if type(mission_seed) is not int:
        raise ValueError("mission_seed must be an integer")
    rng = random.Random(f"lightlag-expedition-map:{mission_seed}")
    for _ in range(GENERATOR["max_mission_attempts"]):
        mission = _draw_mission(rng)
        if mission is not None:
            return mission
    raise RuntimeError(f"could not generate expedition geometry for seed {mission_seed}")


def _draw_mission(rng):
    g, base = GENERATOR, tuple(GENERATOR["base"])
    rotation = rng.uniform(0, 360)
    points, targets, plans = [], [], []
    specifications = []
    for index, region in enumerate(REGIONS):
        definition = g["regions"][region]
        for offset, value in enumerate(definition["initial_values"]):
            specifications.append((f"t{index * 2 + offset + 1}", region, value, 0,
                                   rng.randint(*definition["deadline_tick"])))
    specifications.extend((d["id"], d["region"], d["value"], d["appear_tick"], d["deadline_tick"])
                          for d in g["discoveries"])
    for target_id, region, value, appear, deadline in specifications:
        for _ in range(g["max_component_attempts"]):
            distance = rng.uniform(*g["regions"][region]["distance_m"])
            bearing = rotation + 120 * REGIONS.index(region) + rng.uniform(*g["target_bearing_jitter_deg"])
            angle = math.radians(bearing)
            point = (round(base[0] + distance * math.cos(angle), 2),
                     round(base[1] + distance * math.sin(angle), 2))
            # Rounding must not move a target outside its published radial range.
            low, high = g["regions"][region]["distance_m"]
            if not low <= math.dist(base, point) <= high:
                continue
            if any(math.dist(point, other) < g["min_spacing_m"] for other in points):
                continue
            points.append(point)
            targets.append(Target(target_id, *point, value))
            plans.append(TargetPlan(target_id, value, deadline, appear))
            break
        else:
            return None

    sand = []
    for _ in range(g["sand_patches"]):
        for _ in range(g["max_component_attempts"]):
            width, height = rng.uniform(*g["sand_size_m"]), rng.uniform(*g["sand_size_m"])
            x, y = rng.uniform(0, 40 - width), rng.uniform(0, 40 - height)
            rect = Rect(round(x, 2), round(y, 2), round(x + width, 2), round(y + height, 2))
            if not _near_rect(rect, base, g["sand_base_clearance_m"]):
                sand.append(rect)
                break
        else:
            return None

    hazards = []
    for _ in range(g["hazards"]):
        for _ in range(g["max_component_attempts"]):
            width, height = (rng.uniform(*bounds) for bounds in g["hazard_size_m"])
            if rng.random() < .5:
                width, height = height, width
            distance, angle = rng.uniform(*g["hazard_distance_m"]), rng.uniform(0, 2 * math.pi)
            x, y = base[0] + distance * math.cos(angle), base[1] + distance * math.sin(angle)
            rect = Rect(round(x - width / 2, 2), round(y - height / 2, 2),
                        round(x + width / 2, 2), round(y + height / 2, 2))
            margin = g["hazard_edge_clearance_m"]
            if rect.x1 < margin or rect.y1 < margin or rect.x2 > 40 - margin or rect.y2 > 40 - margin:
                continue
            if _near_rect(rect, base, g["hazard_base_clearance_m"]):
                continue
            if any(_near_rect(rect, point, g["hazard_clearance_m"]) for point in points):
                continue
            hazards.append(rect)
            break
        else:
            return None
    return Mission("rush_noisy", World(sand=tuple(sand), hazards=tuple(hazards), targets=tuple(targets)),
                   tuple(plans), late_fraction=.25, noise_level=1.0, bumpiness=0.0)


make_expedition_mission = make_mission
