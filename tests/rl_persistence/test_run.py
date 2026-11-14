import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.rl_persistence import run as diagnostic


def fake_episode(job, states):
    """Synthetic worker output: these tests never construct an environment."""
    decision = {"ids": ["base"], "features": [[0.] * 14], "proposed_action": 0,
                "action": 0, "prior_goal": None, "held_goal": None,
                "reason": "pass_through" if job["mode"] == "frequent" else "initial_select"}
    return {"schema": "lightlag-rl-persistence-episode-v1", **job,
            "episode": {"seed": job["seed"], "reward": .1 if job["mode"] == "frequent" else .2,
                        "result": {"tick": 420, "alive": True, "at_base": True},
                        "decision_count": 1, "invalid_calls": [], "replay": {"test_fixture": True}},
            "decisions": [decision]}


def rows_for(seeds=(1, 2)):
    return [diagnostic.row_for(fake_episode(job, {}), "fake.json.gz", "fake")
            for job in diagnostic.jobs(seeds)]


class PersistenceRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # This reads existing evidence only; no old or new training episodes run.
        cls.inputs = diagnostic.verify_inputs()

    def test_matrix_uses_visited_training_maps_and_matched_action_draws(self):
        work = diagnostic.jobs(diagnostic.SEEDS)
        self.assertEqual(len(work), 240)
        self.assertEqual(diagnostic.SEEDS, tuple(range(71000, 71006)) + tuple(range(71007, 71025)))
        for policy in diagnostic.POLICIES:
            frequent = {(j["seed"], j["draw"], j["policy_seed"]) for j in work
                        if j["policy"] == policy and j["mode"] == "frequent"}
            persistent = {(j["seed"], j["draw"], j["policy_seed"]) for j in work
                          if j["policy"] == policy and j["mode"] == "persistent"}
            self.assertEqual(frequent, persistent)
            self.assertTrue(all(rng == 1000003 * seed + draw for seed, draw, rng in frequent))
        self.assertEqual(len(self.inputs[1]), 20)

    def test_bootstrap_pairs_action_draws_within_maps(self):
        rows = rows_for()
        for row in rows:
            if row["policy"] == "initial":
                row["reward"] = float(row["draw"] if row["mode"] == "frequent" else 1 - row["draw"])
        summary = diagnostic.summarize(rows, (1, 2))
        self.assertEqual(summary["primary"]["paired_map_differences"], {"1": 0., "2": 0.})
        self.assertEqual(summary["primary"]["bootstrap_95_percentile"], [0., 0.])
        self.assertFalse(summary["screen_passes"])
        self.assertGreater(summary["contrasts"]["final"]["mean_paired_gain"], 0)
        self.assertEqual(summary, diagnostic.summarize(rows, (1, 2)))

    def test_primary_gate_rejects_home_losses_deaths_and_invalid_calls(self):
        rows = rows_for()
        self.assertTrue(diagnostic.summarize(rows, (1, 2))["screen_passes"])
        primary = [r for r in rows if r["policy"] == "initial" and r["mode"] == "persistent"]
        for row in primary[:3]:
            row["at_base"] = False
        primary[0]["alive"], primary[1]["invalid_calls"] = False, 1
        summary = diagnostic.summarize(rows, (1, 2))
        self.assertTrue(summary["gate"]["gain_at_least_03"])
        self.assertFalse(summary["gate"]["home_no_more_than_two_lower"])
        self.assertFalse(summary["gate"]["no_increased_deaths"])
        self.assertFalse(summary["gate"]["no_increased_invalid_calls"])
        with self.assertRaises(ValueError):
            diagnostic.summarize(rows[:-1] + [rows[0]], (1, 2))

    def test_freeze_precedes_first_case_and_every_trace_is_retained(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "run"
            calls = []

            def evaluate(job, states):
                freeze = json.loads((output / "freeze.json").read_text())
                report = json.loads((output / "report.json").read_text())
                self.assertEqual(freeze["seeds"], [1, 2])
                self.assertFalse(report["complete"])
                self.assertEqual(len(report["cases"]), len(calls))
                self.assertEqual(freeze["artifacts"], diagnostic.INPUT_HASHES)
                self.assertTrue(freeze["source_sha256"])
                self.assertEqual(states, self.inputs[0])
                calls.append(job)
                return fake_episode(job, states)

            with patch.object(diagnostic, "verify_inputs", return_value=self.inputs):
                report = diagnostic.run(output, workers=1, smoke=True, evaluator=evaluate)
            self.assertTrue(report["complete"])
            self.assertEqual(len(report["cases"]), 20)
            for row in report["cases"]:
                path = output / row["artifact"]
                bundle = json.loads(gzip.decompress(path.read_bytes()))
                self.assertIn("replay", bundle["episode"])
                self.assertEqual(len(bundle["decisions"]), 1)
                self.assertEqual(diagnostic.row_for(bundle, row["artifact"], diagnostic.digest(path)), row)
            with patch.object(diagnostic, "verify_inputs", return_value=self.inputs):
                with self.assertRaises(FileExistsError):
                    diagnostic.run(output, workers=1, smoke=True, evaluator=evaluate)
            self.assertEqual(len(calls), 20)

    def test_worker_failure_leaves_atomic_incomplete_progress(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "run"
            count = 0

            def evaluate(job, states):
                nonlocal count
                count += 1
                if count == 3:
                    raise ValueError("synthetic failure")
                return fake_episode(job, states)

            with patch.object(diagnostic, "verify_inputs", return_value=self.inputs):
                with self.assertRaisesRegex(ValueError, "synthetic failure"):
                    diagnostic.run(output, workers=1, smoke=True, evaluator=evaluate)
            report = json.loads((output / "report.json").read_text())
            self.assertFalse(report["complete"])
            self.assertEqual(report["status"], "incomplete")
            self.assertEqual(len(report["cases"]), 2)
            self.assertIsNone(report["summary"])
            self.assertEqual(report["error"]["type"], "ValueError")
            self.assertEqual(len(list((output / "cases").glob("*.gz"))), 2)
            self.assertFalse(list(output.glob("*.tmp")))

    def test_source_drift_prevents_completion_without_editing_real_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "run"
            pins = {"synthetic-source.py": "before"}

            def evaluate(job, states):
                pins["synthetic-source.py"] = "after"
                return fake_episode(job, states)

            with patch.object(diagnostic, "verify_inputs", return_value=self.inputs), \
                    patch.object(diagnostic, "source_pins", side_effect=lambda: dict(pins)):
                with self.assertRaisesRegex(RuntimeError, "frozen inputs changed"):
                    diagnostic.run(output, workers=1, smoke=True, evaluator=evaluate)
            report = json.loads((output / "report.json").read_text())
            self.assertEqual(len(report["cases"]), 20)
            self.assertFalse(report["complete"])
            self.assertIsNone(report["summary"])

    def test_input_tamper_stops_before_any_case_or_output_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            (path / "training.json").write_text("{}")
            with patch.object(diagnostic, "evaluate_job") as evaluator:
                with self.assertRaisesRegex(ValueError, "immutable original training input"):
                    diagnostic.run(path / "never-created", workers=1, training=path, evaluator=evaluator)
                evaluator.assert_not_called()
            self.assertFalse((path / "never-created").exists())

    def test_original_batch_hash_is_checked_before_cases(self):
        original_digest = diagnostic.digest

        def changed_batch(path):
            return "0" * 64 if Path(path).suffix == ".gz" else original_digest(path)

        with patch.object(diagnostic, "digest", side_effect=changed_batch):
            with self.assertRaisesRegex(ValueError, "batch identity/hash mismatch"):
                diagnostic.verify_inputs()

    def test_incomplete_episode_is_rejected(self):
        bundle = fake_episode(diagnostic.jobs((1,))[0], {})
        bundle["episode"]["result"]["tick"] = 419
        with self.assertRaisesRegex(ValueError, "incomplete"):
            diagnostic.row_for(bundle, "case.gz", "hash")


if __name__ == "__main__":
    unittest.main()
