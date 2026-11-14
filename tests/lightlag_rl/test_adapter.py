import math
from types import SimpleNamespace
import unittest

import numpy as np

from lightlag_rl.adapter import FEATURE_NAMES, RLPilot, candidates, greedy_choice, home_choice, run_episode


class PublicBeliefs:
    """No simulator or truth fields exist in this feature-only test double."""

    horizon, capacity = 420, 100
    surface = SimpleNamespace(width=600, height=400)
    rules = {"target_radius": 2.5}
    opt = {"home_slack": 1.08, "home_margin": 4.0}
    targets = {
        "good": {"value": 8, "late_value": 2, "deadline_tick": 200},
        "late": {"value": 6, "late_value": 1.5, "deadline_tick": 20},
        "unreachable": {"value": 9, "late_value": 2.25, "deadline_tick": 200},
        "too_far": {"value": 9, "late_value": 2.25, "deadline_tick": 400},
    }
    nodes = {"good": 0, "late": 1, "unreachable": 2, "too_far": 3}
    fields = {"base": SimpleNamespace(ticks=[10, 15, 20, 400], energy=[20, 30, 40, 80])}
    private_reads = []

    def predict(self, tick): return 10, 20, 1.25, 80
    def _open(self, tick): return list(self.targets)
    def _spot(self, name): return (0, 0) if name == "base" else (110, 120)
    def _to(self, name, x, y):
        return {"base": (15, 30), "good": (10, 20), "late": (12, 24),
                "unreachable": (math.inf, math.inf), "too_far": (15, 30)}[name]


class AdapterTests(unittest.TestCase):
    def test_features_need_only_public_beliefs_and_mask_unreachable_targets(self):
        ids, features = candidates(PublicBeliefs(), 40, 10, 20, 80)
        self.assertEqual(ids, ("base", "good", "late"))
        self.assertEqual(features.shape, (3, len(FEATURE_NAMES)))
        self.assertTrue(np.isfinite(features).all())
        self.assertAlmostEqual(features[1, 2], .8)
        self.assertAlmostEqual(features[1, 3], .5)
        self.assertAlmostEqual(features[1, 4], 10 / 420)
        self.assertAlmostEqual(features[1, 9], .8)
        self.assertAlmostEqual(features[2, 9], .15)
        self.assertAlmostEqual(features[1, 11], 100 / 600)
        self.assertEqual(greedy_choice(ids, features), 1)

    def test_home_remains_available_when_public_route_is_unreachable(self):
        pilot = PublicBeliefs()
        pilot._to = lambda *args: (math.inf, math.inf)
        ids, features = candidates(pilot, 418, 10, 20, 1)
        self.assertEqual(ids, ("base",))
        self.assertEqual(features[0, 4], 2)
        self.assertTrue(np.isfinite(features).all())

    def test_chooser_only_receives_ids_and_features_and_bad_indices_fail(self):
        pilot = PublicBeliefs()
        pilot.choose = lambda ids, features: len(ids)
        with self.assertRaises(ValueError):
            RLPilot._plan(pilot, 40, 10, 20, 80, 0)
        pilot.decision_count = 0
        seen = []
        pilot.choose = lambda ids, features: seen.append((ids, features.copy())) or np.int64(1)
        RLPilot._plan(pilot, 40, 10, 20, 80, 0)
        self.assertEqual(pilot.route, ["good"])
        self.assertEqual(pilot.decision_count, 1)
        self.assertEqual(pilot.last_plan, 40)
        self.assertFalse(pilot.need_plan)
        self.assertEqual(len(seen), 1)

    def test_used_seed_full_horizon_and_official_reward_match_saved_replay(self):
        calls = []

        def choose(ids, features):
            self.assertEqual(features.shape, (len(ids), 14))
            calls.append(tuple(ids))
            return greedy_choice(ids, features)

        run = run_episode(1, choose, keep_replay=True)
        result = run["result"]
        self.assertEqual(result["tick"], 420)
        self.assertEqual(run["decision_count"], len(calls))
        self.assertEqual(run["reward"], result["raw_score"] / result["max_available_value"])
        self.assertEqual(run["replay"]["result"], result)
        self.assertEqual(run["invalid_calls"], [])
        self.assertGreater(run["decision_count"], 0)

    def test_used_seed_going_home_does_not_end_the_episode_early(self):
        run = run_episode(1, home_choice)
        self.assertEqual(run["result"]["tick"], 420)
        self.assertTrue(run["result"]["alive"])
        self.assertTrue(run["result"]["at_base"])
        self.assertEqual(run["reward"], 0)
        self.assertEqual(run["calls_by_tool"]["advance"], 420)


if __name__ == "__main__":
    unittest.main()
