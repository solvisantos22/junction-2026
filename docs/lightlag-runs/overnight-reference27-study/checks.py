"""Focused checks for the additional candidate's fixed plan and comparisons."""

import importlib.util
from pathlib import Path
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "AGENTS.md").exists())
SPEC = importlib.util.spec_from_file_location(
    "overnight_reference27", ROOT / "tools/lightlag_experiments/overnight_reference27.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class SupplementChecks(unittest.TestCase):
    def test_fixed_plan_has_48_distinct_cells_and_fixed_reruns(self):
        plan = runner.plan()
        cells = {(r["set"], r["profile"], r["seed"]) for r in plan}
        self.assertEqual(len(plan), 48)
        self.assertEqual(len(cells), 48)
        self.assertTrue(set(runner.RERUN_CELLS) <= cells)
        self.assertNotIn("fresh", {r["set"] for r in plan})

    def test_changed_environment_blocks_baseline_reuse(self):
        prior = {"lightlag/environment.py": "old", runner.MANH_PATH: "old"}
        current = {"lightlag/environment.py": "different", runner.MANH_PATH: "new"}
        with self.assertRaises(RuntimeError):
            runner.compatible_dependencies(prior, current)
        current["lightlag/environment.py"] = "old"
        self.assertEqual(runner.compatible_dependencies(prior, current), ["lightlag/environment.py"])

    def test_failed_pair_has_no_fabricated_score(self):
        new = [{"set": "historical", "profile": "rush", "seed": seed,
                "status": "ok" if score is not None else "execution_error",
                "normalized_score": score, "raw_score": score,
                "policy_calls": 4 if score is not None else None,
                "alive": True if score is not None else None,
                "at_base": True if score is not None else None}
               for seed, score in ((501, 0.75), (502, None))]
        baseline = [{"set": "historical", "profile": "rush", "seed": seed,
                     "policy": "old", "status": "ok", "normalized_score": 0.5,
                     "raw_score": 0.5} for seed in (501, 502)]
        group = runner.paired_statistics(new, baseline, "old")[0]
        self.assertEqual(group["complete_pairs"], 1)
        self.assertEqual(group["incomplete_pairs"], 1)
        self.assertEqual(group["mean_candidate27_minus_baseline"], 0.25)

    def test_source_abort_preserves_an_execution_error(self):
        outcome = {"status": "execution_error", "error": {"type": "ValueError", "message": "original"},
                   "episode": None}
        runner.mark_source_failure(outcome, {"type": "SourceMismatch", "message": "source changed"})
        self.assertEqual(outcome["status"], "source_mismatch")
        self.assertEqual(outcome["execution_error"]["message"], "original")
        self.assertEqual(outcome["error"]["type"], "SourceMismatch")


if __name__ == "__main__":
    unittest.main()
