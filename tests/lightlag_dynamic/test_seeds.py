"""Discriminative-seed finder: the declared criteria, and one calibration seed end to end."""

import importlib.util
import unittest

HAVE_NUMPY = importlib.util.find_spec("numpy") is not None


def _cell(selectors, blind, cautious, stale, window, home=True):
    row = lambda share, ok=True: {"share": share, "alive": ok, "at_base": ok, "crash": None}
    cell = {key: row(share, home) for key, share in zip(("19", "20", "21", "24"), selectors)}
    cell.update(blind=row(blind), cautious=row(cautious), stale_telemetry=row(stale), window_blind=row(window))
    return cell


@unittest.skipUnless(HAVE_NUMPY, "the Manh controllers need numpy")
class CriteriaTest(unittest.TestCase):
    def test_tiers(self):
        from lightlag_dynamic.manh_controllers.seeds import judge
        v = judge(_cell((1.0, 1.0, 0.95, 0.9), 0.5, 0.6, 0.0, 0.4))
        self.assertTrue(v["feedback"] and v["tier1"] and v["tier2"])
        self.assertAlmostEqual(v["gap1"], 0.3)
        self.assertAlmostEqual(v["gap2"], 0.3)
        v = judge(_cell((1.0,) * 4, 0.5, 0.5, 0.0, 0.7))  # ignoring the new rules is enough
        self.assertTrue(v["tier1"])
        self.assertFalse(v["tier2"])
        self.assertFalse(judge(_cell((1.0, 1.0, 1.0, 0.89), 0.1, 0.1, 0.0, 0.0))["feedback"])
        self.assertFalse(judge(_cell((1.0,) * 4, 0.1, 0.1, 0.0, 0.0, home=False))["feedback"])
        self.assertFalse(judge(_cell((1.0,) * 4, 0.61, 0.1, 0.0, 0.0))["tier1"])


@unittest.skipUnless(HAVE_NUMPY, "the Manh controllers need numpy")
class CalibrationTest(unittest.TestCase):
    def test_seed_500(self):
        # The Harbor pilot seed: every feedback controller solves it, the shortcuts do not,
        # but a controller that ignores deadlines and discoveries still earns 71%.
        from lightlag_dynamic.manh_controllers.seeds import report, score
        cells = score([500], ["rush"], 3, workers=1)
        cell = cells[("rush", 500)]
        self.assertEqual(cell["features"], {"targets_at_launch": 5, "discoveries": 1, "deadlines": 6,
                                            "total_value": 7})
        self.assertAlmostEqual(cell["1"]["share"], 1.0)
        self.assertTrue(cell["verdict"]["tier1"])
        self.assertFalse(cell["verdict"]["tier2"])
        self.assertIn("Tier 1: 1. Tier 2: 0.", report(cells, ["rush"], 3))


if __name__ == "__main__":
    unittest.main()
