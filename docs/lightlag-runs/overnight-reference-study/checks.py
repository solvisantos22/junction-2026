"""Narrow runner checks; fixtures stay inside this new study directory."""

import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "AGENTS.md").exists())
SPEC = importlib.util.spec_from_file_location(
    "overnight_references", ROOT / "tools/lightlag_experiments/overnight_references.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class RunnerChecks(unittest.TestCase):
    def temporary(self):
        return tempfile.TemporaryDirectory(dir=Path(__file__).parent)

    def test_existing_destination_is_untouched(self):
        with self.temporary() as directory:
            path = Path(directory)
            sentinel = path / "sentinel.txt"
            sentinel.write_text("preserve")
            with self.assertRaises(FileExistsError):
                runner.claim_output(path)
            self.assertEqual(sentinel.read_text(), "preserve")
            self.assertEqual(sorted(p.name for p in path.iterdir()), ["sentinel.txt"])

    def test_failed_execution_has_null_score_and_is_not_retried(self):
        calls = []

        def fail():
            calls.append(1)
            raise ValueError("synthetic execution failure")

        outcome = runner.attempt_episode(fail)
        self.assertEqual(calls, [1])
        self.assertEqual(outcome["status"], "execution_error")
        self.assertIsNone(outcome["episode"])
        self.assertEqual(outcome["error"]["type"], "ValueError")
        row = runner.episode_row({"set": "fresh", "profile": "rush", "seed": 3000,
                                  "policy": "kf_mpc"}, outcome, "error.json")
        for key in ("raw_score", "normalized_score", "alive", "at_base", "policy_calls"):
            self.assertIsNone(row[key])

    def test_source_mismatch_stops_before_execution(self):
        with self.temporary() as directory:
            path = Path(directory)
            (path / "source.py").write_text("changed")
            with self.assertRaises(runner.SourceMismatch):
                runner.verify_hashes(path, {"source.py": runner.sha256(b"original")})

    def test_replay_check_rejects_same_score_different_trajectory(self):
        expected = {"states": [{"tick": 1, "battery": 9}], "result": {"raw_score": 1}}
        episode = {"replay": {"states": [{"tick": 1, "battery": 8}],
                              "result": {"raw_score": 1}},
                   "result": {"raw_score": 1, "max_available_value": 2},
                   "tool_calls": {"policy": 4}}
        result = {"raw_score": 1, "max_available_value": 2, "tool_calls": 4}
        check = runner.compare_reference(episode, expected, result, "0.500000")
        self.assertFalse(check["replay_equal"])
        self.assertTrue(check["result_equal"])
        self.assertFalse(check["passed"])

    def test_error_pair_is_not_in_score_denominator(self):
        rows = []
        for seed, old, candidate in [(3000, 0.5, 0.75), (3001, 0.4, None)]:
            for policy, score in [(runner.ORIGINAL, old), (runner.CANDIDATE, candidate)]:
                rows.append({"set": "fresh", "profile": "rush", "seed": seed,
                             "policy": policy, "normalized_score": score,
                             "raw_score": None if score is None else score * 10,
                             "status": "execution_error" if score is None else "ok",
                             "alive": None if score is None else True,
                             "at_base": None if score is None else True,
                             "policy_calls": None if score is None else 4})
        group = runner.paired_statistics(rows)[0]
        self.assertEqual(group["complete_pairs"], 1)
        self.assertEqual(group["incomplete_pairs"], 1)
        self.assertEqual(group["mean_candidate_minus_original"], 0.25)
        self.assertEqual(group["candidate_wins"], 1)


if __name__ == "__main__":
    unittest.main()
