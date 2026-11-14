import gzip
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from tools.lightlag_rl.audit_training import audit
from lightlag_rl.train import digest

ROOT = Path(__file__).resolve().parents[2]
SMOKE = ROOT / "docs/lightlag-rl-results/local-smoke"


class TrainingAuditTests(unittest.TestCase):
    def test_retained_smoke_reconstructs_sampling_and_both_updates(self):
        result = audit(SMOKE, smoke=True)
        self.assertEqual(result["episodes_verified"], 8)
        self.assertEqual(result["updates_reconstructed"], 2)
        self.assertGreater(result["sampled_actions_reconstructed"], 100)
        self.assertEqual(result["new_environment_cases"], 0)

    def test_rehashed_action_or_changed_checkpoint_is_rejected(self):
        for change in ("action", "checkpoint"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as temporary:
                copied = Path(temporary) / "training"
                shutil.copytree(SMOKE, copied)
                if change == "checkpoint":
                    path = copied / "checkpoint-0001.json"
                    value = json.loads(path.read_text())
                    value["policy"]["W"][0][0] += .1
                    path.write_text(json.dumps(value))
                else:
                    path = copied / "batches/update-0001.json.gz"
                    value = json.loads(gzip.decompress(path.read_bytes()))
                    decision = next(d for row in value["rows"] for d in row["trajectory"] if len(d["ids"]) > 1)
                    decision["action"] = (decision["action"] + 1) % len(decision["ids"])
                    path.write_bytes(gzip.compress(json.dumps(value).encode()))
                    report_path = copied / "training.json"
                    report = json.loads(report_path.read_text())
                    report["metrics"][0]["sha256"] = digest(path)
                    report_path.write_text(json.dumps(report))
                with self.assertRaises(AssertionError):
                    audit(copied, smoke=True)


if __name__ == "__main__":
    unittest.main()
