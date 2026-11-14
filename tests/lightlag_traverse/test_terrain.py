"""Generated worlds: repeatable, inside their published ranges, and fair to drive.

    python3 -m unittest discover -s tests/lightlag_traverse -v

Standard library only.
"""

import math
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from lightlag_traverse.surface import PHYSICS  # noqa: E402
from lightlag_traverse.terrain import (FLAT_SLOPE, GENERATOR, SAFE_SHARE, ground_distance, make_world,  # noqa: E402
                                       picture, safe_nodes)

SEEDS = (1, 2, 3, 2026)
WORLDS = {seed: make_world(seed) for seed in SEEDS}


class WorldTest(unittest.TestCase):
    def test_a_seed_always_gives_the_same_world_and_seeds_differ(self):
        again = make_world(3)
        self.assertEqual(again, WORLDS[3])
        self.assertNotEqual(WORLDS[1].elevation_cm, WORLDS[2].elevation_cm)
        self.assertNotEqual(WORLDS[1].targets, WORLDS[2].targets)
        with self.assertRaises(ValueError):
            make_world("3")

    def test_the_grid_has_the_published_size_and_terrain_shares(self):
        for seed, world in WORLDS.items():
            self.assertEqual((world.width, world.height, world.cell),
                             (GENERATOR["width_m"], GENERATOR["height_m"], GENERATOR["cell_m"]), seed)
            cells = sum(len(row) for row in world.terrain)
            self.assertEqual(cells, int(world.width / world.cell) * int(world.height / world.cell))
            for code, name in (("s", "sand"), ("k", "rocks"), ("b", "bedrock")):
                share = sum(row.count(code) for row in world.terrain) / cells
                self.assertAlmostEqual(share, GENERATOR["terrain_share"][name], places=3, msg=(seed, name))
            self.assertEqual(set("".join(world.terrain)), set("rskb"))

    def test_sand_lies_only_on_gentle_ground(self):
        for seed, world in WORLDS.items():
            surface = world.surface()
            for j, row in enumerate(world.terrain):
                for i, code in enumerate(row):
                    if code == "s":
                        self.assertLess(surface.cell_max_slope(i, j), GENERATOR["sand_max_cell_slope"], (seed, i, j))

    def test_there_is_ground_too_steep_to_drive_and_most_of_the_map_is_not(self):
        for seed, world in WORLDS.items():
            surface = world.surface()
            steep = sum(surface.cell_max_slope(i, j) > PHYSICS["max_tilt"]
                        for j in range(surface.ny - 1) for i in range(surface.nx - 1))
            share = steep / ((surface.nx - 1) * (surface.ny - 1))
            self.assertGreater(share, 0.01, seed)            # crater walls and the scarp are really there
            self.assertLess(share, 0.25, seed)


class MissionTest(unittest.TestCase):
    def test_the_target_counts_values_and_spacing_are_as_published(self):
        for seed, world in WORLDS.items():
            launch = [t for t in world.targets if t.appear_tick == 0]
            found = [t for t in world.targets if t.appear_tick > 0]
            self.assertEqual((len(launch), len(found)), (GENERATOR["initial_targets"], GENERATOR["discoveries"]), seed)
            low, high = GENERATOR["target_values"]
            self.assertTrue(all(low <= t.value <= high for t in world.targets), seed)
            self.assertEqual(len({t.id for t in world.targets}), len(world.targets))
            for a in world.targets:
                self.assertGreaterEqual(math.hypot(a.x - world.base[0], a.y - world.base[1]),
                                        GENERATOR["target_min_base_distance_m"], (seed, a.id))
                for b in world.targets:
                    if a.id < b.id:
                        self.assertGreaterEqual(math.hypot(a.x - b.x, a.y - b.y),
                                                GENERATOR["target_min_spacing_m"], (seed, a.id, b.id))

    def test_every_target_and_the_lander_stand_on_flat_ground_a_rover_can_reach(self):
        for seed, world in WORLDS.items():
            surface = world.surface()
            safe = safe_nodes(surface, PHYSICS["max_tilt"] * SAFE_SHARE)
            flat = safe_nodes(surface, FLAT_SLOPE)
            base = (int(world.base[0] / world.cell), int(world.base[1] / world.cell))
            reach = ground_distance(surface, safe, base)
            self.assertTrue(flat[base[1]][base[0]], seed)
            for target in world.targets:
                node = (int(round(target.x / world.cell)), int(round(target.y / world.cell)))
                self.assertEqual((node[0] * world.cell, node[1] * world.cell), (target.x, target.y))
                self.assertIn(node, reach, (seed, target.id))
                self.assertTrue(flat[node[1]][node[0]], (seed, target.id))
                self.assertLess(surface.slope(target.x, target.y), FLAT_SLOPE, (seed, target.id))

    def test_a_deadline_leaves_time_to_drive_there_and_discoveries_have_windows(self):
        for seed, world in WORLDS.items():
            surface = world.surface()
            safe = safe_nodes(surface, PHYSICS["max_tilt"] * SAFE_SHARE)
            reach = ground_distance(surface, safe, (int(world.base[0] / world.cell), int(world.base[1] / world.cell)))
            for target in world.targets:
                node = (int(round(target.x / world.cell)), int(round(target.y / world.cell)))
                if target.appear_tick == 0 and target.deadline_tick is not None:
                    self.assertGreaterEqual(target.deadline_tick, reach[node] / 5.0, (seed, target.id))
                if target.appear_tick:
                    first, last = GENERATOR["discovery_appear"]
                    self.assertTrue(first <= target.appear_tick <= last * 420, (seed, target.id))
                    if target.deadline_tick is not None:
                        self.assertGreater(target.deadline_tick, target.appear_tick)

    def test_the_picture_shows_the_lander_and_steep_ground(self):
        text = picture(WORLDS[2026])
        self.assertEqual(text.count("B"), 1)
        self.assertIn("#", text)
        self.assertIn("~", text)


if __name__ == "__main__":
    unittest.main()
