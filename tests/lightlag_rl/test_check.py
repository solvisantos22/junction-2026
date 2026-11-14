import copy
import gzip
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from lightlag_rl.model import Policy
from lightlag_rl.train import atomic_json, digest, source_pins
from tools.lightlag_rl import check


def fixture_training(path):
    """Synthetic completed metadata for testing the checker; no learning claim."""
    path.mkdir()
    initial, final = Policy(seed=17).state_dict(), Policy(seed=18).state_dict()
    atomic_json(path / "initial-policy.json", initial)
    atomic_json(path / "final-policy.json", final)
    config = {"updates": 2, "batch_size": 4, "smoke": True, "training_seeds": [1, 2],
              "train_seed": 17, "rollouts_per_map": 2, "learning_rate": .02,
              "entropy_coefficient": .01, "gradient_norm_limit": 5}
    pins = source_pins()
    atomic_json(path / "checkpoint-0002.json", {"updates_completed": 2, "config": config,
                                                "source_sha256": pins, "policy": final})
    report = {"schema": "lightlag-rl-training-v1", "status": "complete", "config": config,
              "model_api_calls": 0, "fresh_cases": 0, "updates_completed": 2, "episodes_completed": 8,
              "metrics": [{"update": 1}, {"update": 2}], "source_sha256": pins,
              "initial_policy_sha256": digest(path / "initial-policy.json"),
              "final_policy_sha256": digest(path / "final-policy.json"),
              "latest_checkpoint": "checkpoint-0002.json",
              "latest_checkpoint_sha256": digest(path / "checkpoint-0002.json")}
    atomic_json(path / "training.json", report)


class CheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="rl-check-tests-")
        cls.root = Path(cls.temporary.name)
        cls.training = cls.root / "training"
        fixture_training(cls.training)
        cls.original = cls.root / "original"
        # All actual test missions are the already-used seeds 1 and 2.
        cls.report = check.run(cls.training, cls.original, workers=1, smoke=True)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def copied(self, name):
        destination = self.root / name
        shutil.copytree(self.original, destination)
        return destination

    def test_used_seed_smoke_retains_and_audits_all_twelve_cases(self):
        result = check.audit(self.original / "report.json")
        self.assertEqual(result["cases_verified"], 12)
        self.assertTrue(result["smoke"])
        self.assertTrue(result["full_replays_match"])
        self.assertGreater(result["decisions_verified"], 0)
        self.assertEqual(len(result["summary"]["paired_map_differences"]), 2)

    def test_smoke_training_cannot_open_fresh_cases(self):
        output = self.root / "must-not-exist"
        with patch.object(check, "evaluate_job") as evaluator:
            with self.assertRaises(ValueError):
                check.run(self.training, output, smoke=False)
            evaluator.assert_not_called()
        self.assertFalse(output.exists())

    def test_home_control_is_do_nothing_with_no_position_corrections(self):
        for row in self.report["cases"]:
            if row["policy"] != "home":
                continue
            bundle = json.loads(gzip.decompress((self.original / row["artifact"]).read_bytes()))
            self.assertEqual(bundle["episode"]["replay"]["commands"], [])
            self.assertEqual(bundle["decisions"], [])
            self.assertEqual(bundle["episode"]["calls_by_tool"], {"advance": 84})

    def test_missing_or_duplicate_case_is_rejected(self):
        directory = self.copied("duplicate")
        report = copy.deepcopy(self.report)
        report["cases"][-1] = report["cases"][0]
        atomic_json(directory / "report.json", report)
        with self.assertRaises(AssertionError):
            check.audit(directory / "report.json")

    def test_rehashed_forged_reward_fails_physics_reconstruction(self):
        directory = self.copied("forged")
        report = copy.deepcopy(self.report)
        row = report["cases"][0]
        artifact = directory / row["artifact"]
        bundle = json.loads(gzip.decompress(artifact.read_bytes()))
        bundle["episode"]["reward"] = .999
        bundle["episode"]["result"]["raw_score"] = .999 * bundle["episode"]["result"]["max_available_value"]
        artifact.write_bytes(gzip.compress(json.dumps(bundle).encode(), mtime=0))
        report["cases"][0] = check.row_for(bundle, row["artifact"], digest(artifact))
        atomic_json(directory / "report.json", report)
        with self.assertRaises(AssertionError):
            check.audit(directory / "report.json")

    def test_wrong_source_hash_stops_before_generation(self):
        training = self.root / "wrong-source"
        shutil.copytree(self.training, training)
        report = json.loads((training / "training.json").read_text())
        name = next(iter(report["source_sha256"]))
        report["source_sha256"][name] = "0" * 64
        atomic_json(training / "training.json", report)
        output = self.root / "not-generated"
        with self.assertRaises(RuntimeError):
            check.run(training, output, smoke=True)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
