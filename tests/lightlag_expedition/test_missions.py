"""Generated expedition missions obey the published geometry distribution."""

import math
import unittest

from lightlag_expedition.missions import GENERATOR, generator_rules, make_mission, _near_rect
from lightlag_expedition.model import TARGET_REGIONS


class MissionTests(unittest.TestCase):
    def test_reproducible_geometry_and_fixed_value_schedule(self):
        for seed in range(100):
            with self.subTest(seed=seed):
                mission = make_mission(seed)
                self.assertEqual(mission, make_mission(seed))
                world = mission.world
                self.assertEqual((world.width, world.height, world.base), (40, 40, (20, 20)))
                self.assertEqual((len(world.sand), len(world.hazards), len(world.targets)), (2, 2, 8))
                self.assertEqual(sum(t.value for t in world.targets), 20)
                self.assertEqual(mission.profile, "rush_noisy")
                self.assertEqual((mission.noise_level, mission.bumpiness, mission.late_fraction), (1, 0, .25))
                plans = {plan.id: plan for plan in mission.plans}
                self.assertEqual(sum(plan.appear_tick == 0 for plan in plans.values()), 6)
                for target in world.targets:
                    definition = GENERATOR["regions"][TARGET_REGIONS[target.id]]
                    distance = math.dist(world.base, (target.x, target.y))
                    self.assertGreaterEqual(distance, definition["distance_m"][0])
                    self.assertLessEqual(distance, definition["distance_m"][1])
                    if target.id.startswith("t"):
                        self.assertIn(target.value, definition["initial_values"])
                        self.assertGreaterEqual(plans[target.id].deadline_tick, definition["deadline_tick"][0])
                        self.assertLessEqual(plans[target.id].deadline_tick, definition["deadline_tick"][1])
                    self.assertTrue(1 <= target.x <= 39 and 1 <= target.y <= 39)
                    self.assertFalse(any(_near_rect(h, (target.x, target.y), 1.2) for h in world.hazards))
                self.assertEqual((plans["d1"].value, plans["d1"].appear_tick, plans["d1"].deadline_tick), (3, 10, 26))
                self.assertEqual((plans["d2"].value, plans["d2"].appear_tick, plans["d2"].deadline_tick), (3, 22, 44))
                for index, target in enumerate(world.targets):
                    for other in world.targets[:index]:
                        self.assertGreaterEqual(math.dist((target.x, target.y), (other.x, other.y)), 2)
                self.assertFalse(any(_near_rect(h, world.base, 2.5) for h in world.hazards))
                self.assertFalse(any(_near_rect(s, world.base, 1.5) for s in world.sand))
        self.assertNotEqual(make_mission(0), make_mission(1))

    def test_generator_metadata_is_copy_safe(self):
        public = generator_rules()
        public["regions"]["r1"]["distance_m"][0] = -100
        self.assertEqual(generator_rules()["regions"]["r1"]["distance_m"], [4, 7])

    def test_strict_seed(self):
        for seed in (True, 1.2, "3", None):
            with self.subTest(seed=seed), self.assertRaises(ValueError):
                make_mission(seed)


if __name__ == "__main__":
    unittest.main()
