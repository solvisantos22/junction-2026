"""Seeded public missions, with no performance-based filtering or hidden state."""

import random

VERSION = "stereo-survey-v1"
PROFILES = {"compact": 6, "expanded": 8}


def generate(seed, profile="compact"):
    opportunities = PROFILES[profile]
    rng = random.Random(seed)
    horizon = 3 * opportunities + 1
    passes = sorted(set([*range(7, horizon, 8), horizon - 1]))
    cells = [{"id": f"cell-{row}-{column}", "x": 5 + 10 * column,
              "y": 5 + 10 * row, "weight": rng.randint(1, 5)}
             for row in range(4) for column in range(5)]
    mission = {
        "version": VERSION, "profile": profile, "horizon": horizon,
        "cells": cells, "images": [], "platforms": [],
        "stereo": {"min_angle": 15, "max_angle": 55,
                   "max_time_gap": 9, "max_gsd_ratio": 1.5},
    }
    for platform in range(2):
        name = f"camera-{platform}"
        mission["platforms"].append({
            "id": name, "battery": 14 if profile == "compact" else 20,
            "memory": 3, "capture_energy": 2, "transmit_energy": 1,
            "slew_rate": 30, "slew_energy_angle": 30,
            "initial_tick": -4, "initial_pointing": [0, 0, -1],
            "downlinks": [{"tick": tick, "capacity": 2} for tick in passes],
        })
        for opportunity in range(opportunities):
            progress = opportunity / (opportunities - 1)
            camera_x = (-15 + 70 * progress) if platform == 0 else (65 - 70 * progress)
            camera_y = 8 if platform == 0 else 32
            available = [c for c in cells if (c["x"] - camera_x) ** 2 + (c["y"] - camera_y) ** 2 <= 55 ** 2]
            for option, center in enumerate(rng.sample(available, 2)):
                half_width = rng.choice([9, 14, 19])
                half_height = rng.choice([9, 14])
                cx, cy = center["x"] + rng.randint(-2, 2), center["y"] + rng.randint(-2, 2)
                mission["images"].append({
                    "id": f"p{platform}-t{opportunity:02d}-v{option}",
                    "platform": name, "tick": 3 * opportunity,
                    "camera": [round(camera_x, 8), camera_y, 40],
                    "footprint": [cx - half_width, cy - half_height, cx + half_width, cy + half_height],
                    "gsd": half_width / 10,
                })
    return mission
