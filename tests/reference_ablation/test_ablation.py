import copy
import math
import unittest

from lightlag_traverse.environment import SENSING, TraverseEnvironment
from lightlag_traverse.pilot import Filter, fly as original_fly
from lightlag_traverse.play import PublicTools
from lightlag_traverse_max.heldout import check_training_seeds
from tools.reference_ablation.run import (CONFIRMATION, DEVELOPMENT, SMOKE_OPTIONS,
                                          choose, collect, normal, summarize)
from tools.reference_ablation.variants import (VARIANTS, CubatureFilter, ProcessScaledFilter,
                                               cholesky3, combine)


class FilterTests(unittest.TestCase):
    def test_cubature_is_exact_with_no_heading_uncertainty(self):
        sensing = dict(SENSING, heading_bias_deg=0)
        a, b = Filter(2, 3, sensing), CubatureFilter(2, 3, sensing)
        a.move(4, 5, 6, .3)
        b.move(4, 5, 6, .3)
        for left, right in zip([a.x, a.y, a.bias], [b.x, b.y, b.bias]):
            self.assertAlmostEqual(left, right, places=12)
        for i in range(3):
            for j in range(3):
                self.assertAlmostEqual(a.P[i][j], b.P[i][j], places=12)

    def test_cubature_recovers_linear_limit_and_stays_positive(self):
        sensing = dict(SENSING, heading_bias_deg=.001)
        a, b = Filter(0, 0, sensing), CubatureFilter(0, 0, sensing)
        a.move(5, 0, 5, 0)
        b.move(5, 0, 5, 0)
        for i in range(3):
            for j in range(3):
                self.assertAlmostEqual(a.P[i][j], b.P[i][j], places=8)
        for tick in range(200):
            heading = .03 * tick
            b.move(5 * math.cos(heading), 5 * math.sin(heading), 5, heading)
            b.fix(b.x + .2 * math.cos(tick), b.y + .2 * math.sin(tick))
            cholesky3(b.P)
            self.assertTrue(all(math.isfinite(x) for row in b.P for x in row))

    def test_process_scale_one_matches_reference(self):
        a, b = Filter(0, 0, SENSING), ProcessScaledFilter(0, 0, SENSING, 1)
        for tick in range(10):
            for f in (a, b):
                f.move(3, 4, 5, .4)
                f.fix(3 * (tick + 1) + .2, 4 * (tick + 1) - .2)
            self.assertEqual(a.P, b.P)
            self.assertEqual((a.x, a.y, a.bias), (b.x, b.y, b.bias))


class ProtocolTests(unittest.TestCase):
    def test_seed_separation_and_reserved_guard(self):
        self.assertFalse(set(DEVELOPMENT) & set(CONFIRMATION))
        check_training_seeds(DEVELOPMENT + CONFIRMATION)
        for seed in (500, 523, 2026, 2029, 99991):
            with self.assertRaises(ValueError):
                check_training_seeds([seed])

    def test_selection_respects_components_reliability_and_cost(self):
        base = {"home_alive": 12, "deaths": 0}
        def row(gain, **changes):
            return {**base, "delta": gain, "cpu_ratio": 1.1, "invalid_calls": 0, "errors": 0, **changes}
        summary = {"table": {"baseline": base, "est_cubature": row(.02), "est_process_double": row(.01),
                    "slip_fast": row(.03), "path_energy_low": row(.04, home_alive=11),
                    "search_more": row(.05, cpu_ratio=2), "home_later": row(-.01)}}
        result = choose(summary)
        self.assertEqual(result["distinct_ranked"], ["slip_fast", "est_cubature"])
        self.assertEqual(result["primary"], "combined")
        self.assertEqual(result["configs"]["combined"]["members"], ["slip_fast", "est_cubature"])
        with self.assertRaises(ValueError):
            combine(["est_cubature", "est_process_double"])

    def test_incomplete_or_duplicate_matrix_fails(self):
        with self.assertRaises(ValueError):
            summarize([], {"baseline": {}}, [1])
        with self.assertRaises(ValueError):
            summarize([{"name": "baseline", "seed": 1}] * 2, {"baseline": {}}, [1, 2])


class BaselineTests(unittest.TestCase):
    def test_passive_wrapper_matches_original_commands_truth_and_grade(self):
        env = TraverseEnvironment(1)
        original_fly(PublicTools(env), SMOKE_OPTIONS)
        original = normal(env.replay())
        baseline_spec = copy.deepcopy(VARIANTS["baseline"])
        bundle = normal(collect({"stage": "test", "seed": 1, "name": "baseline", "spec": baseline_spec,
                                 "options": SMOKE_OPTIONS}))
        self.assertEqual(bundle["replay"], original)
        self.assertFalse(bundle["invalid"])
        self.assertIsNone(bundle["error"])
        self.assertEqual(baseline_spec, VARIANTS["baseline"])
        self.assertEqual(bundle["metrics"]["reward"], original["result"]["raw_score"] / original["result"]["max_available_value"])
        self.assertGreater(bundle["metrics"]["belief_count"], 400)


if __name__ == "__main__":
    unittest.main()
