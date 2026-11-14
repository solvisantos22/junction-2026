"""Snapshot-only reconstruction, tamper detection and exception/cost preservation."""

import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from lightlag_expedition.reference import run_policy
from lightlag_expedition.service import ExpeditionService, ToolError
from tools.expedition_experiments.audit import audit, task_digest
from tools.expedition_experiments.prepare import prepare


def write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True, allow_nan=False) + "\n")


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.task, self.trial = self.root / "task", self.root / "trial"
        self.artifacts = self.trial / "artifacts/evaluator"
        # Fixture provenance only: do not run Git from the audit or its tests.
        with patch("tools.expedition_experiments.prepare.subprocess.check_output",
                   side_effect=["0" * 40 + "\n", b""]):
            self.manifest = prepare(self.task, seed=0, mission_seed=0)
        service = ExpeditionService(0, artifact_dir=self.artifacts)
        with self.assertRaises(ToolError):
            service.uplink([{"action": "inspect", "region": "r1"},
                            {"action": "drive", "heading_deg": float("inf"), "metres": 1}])
        run_policy(service)
        protected = service.finish()
        self.assertGreater(protected["raw_score"], 0)
        with self.assertRaises(ToolError):
            service.rules()
        verifier = self.trial / "verifier"
        verifier.mkdir()
        (verifier / "reward.txt").write_text(format(protected["reward"], ".6f") + "\n")
        write_json(verifier / "expedition-details.json", protected)
        write_json(self.trial / "lock.json", {"task": {"digest": task_digest(self.manifest["task_sha256"])}})
        self.harbor = {"started_at": "2026-11-14T00:00:00Z", "finished_at": "2026-11-14T00:01:00Z",
                       "exception_info": None, "verifier_environment_mode": "separate",
                       "agent_info": {"name": "opencode", "model_info": {"provider": "test", "name": "fixture"}},
                       "agent_result": {"cost_usd": .125, "n_input_tokens": 12, "n_output_tokens": 8,
                                        "model_usage": {"test/fixture": {"cost_usd": .125}}},
                       "verifier_result": {"rewards": {"reward": float(format(protected["reward"], ".6f"))}}}
        write_json(self.trial / "result.json", self.harbor)

    def tearDown(self):
        self.temporary.cleanup()

    def test_complete_snapshot_public_errors_and_protected_grades_reconstruct(self):
        result = audit(self.task, self.artifacts, self.trial)
        self.assertTrue(result["passed"], result)
        self.assertTrue(all(result["checks"].values()))
        self.assertEqual(result["reconstruction"]["reproduced_tool_errors"], 2)
        self.assertEqual(result["reconstruction"]["post_closure_calls"], 1)
        self.assertGreater(result["reconstruction"]["public_tool_calls"], 60)
        self.assertEqual(result["reported_cost_usd"], .125)
        self.assertEqual(len(result["evidence_sha256"]), 7)
        self.assertEqual(result["provenance"]["task_files_verified"], 33)
        self.assertEqual(result["provenance"]["copied_source_files_verified"], 23)
        self.assertEqual(result["provenance"]["source_hashes_declared_without_retained_bytes"],
                         ["tools/expedition_experiments/prepare.py"])

    def test_replay_uses_snapshot_not_current_modules_or_lightlag_repo_override(self):
        with patch("lightlag_expedition.environment.ExpeditionEnvironment.__init__", side_effect=RuntimeError("current simulator used")), \
                patch.dict("os.environ", {"LIGHTLAG_REPO": str(self.root / "nonexistent")}):
            result = audit(self.task, self.artifacts, self.trial)
        self.assertTrue(result["passed"], result)

    def test_task_and_copied_source_hash_changes_fail(self):
        source = self.task / "environment/simulator/lightlag_expedition/environment.py"
        original = source.read_bytes()
        source.write_bytes(original + b"\n# changed\n")
        result = audit(self.task, self.artifacts, self.trial)
        self.assertFalse(result["passed"])
        self.assertIn("task hash mismatch", " ".join(result["issues"]))
        source.write_bytes(original)
        manifest = json.loads((self.task / "experiment.json").read_text())
        manifest["source_sha256"]["lightlag_expedition/environment.py"] = "0" * 64
        write_json(self.task / "experiment.json", manifest)
        result = audit(self.task, self.artifacts, self.trial)
        self.assertFalse(result["passed"])
        self.assertIn("source copy hash mismatch", " ".join(result["issues"]))

    def test_transcript_replay_score_and_verifier_tampering_are_detected(self):
        for kind in ("transcript", "replay", "result", "reward", "details"):
            with self.subTest(kind=kind):
                trial = self.root / ("tampered-" + kind)
                shutil.copytree(self.trial, trial)
                artifacts = trial / "artifacts/evaluator"
                if kind == "transcript":
                    path = artifacts / "transcript.jsonl"
                    rows = [json.loads(line) for line in path.read_text().splitlines()]
                    rows[0]["error"] = "different rejection"
                    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
                elif kind in ("replay", "result"):
                    path = artifacts / (kind + ".json")
                    data = json.loads(path.read_text())
                    if kind == "replay":
                        data["states"][5]["battery"] += 1
                    else:
                        data["raw_score"] += 1
                    write_json(path, data)
                elif kind == "reward":
                    (trial / "verifier/reward.txt").write_text("0.999999\n")
                else:
                    path = trial / "verifier/expedition-details.json"
                    data = json.loads(path.read_text()); data["raw_score"] += 1
                    write_json(path, data)
                result = audit(self.task, artifacts, trial)
                self.assertFalse(result["passed"], result)
                self.assertEqual(result["reported_cost_usd"], .125)

    def test_exceptions_and_costs_survive_missing_evidence(self):
        self.harbor["exception_info"] = {"exception_type": "AgentTimeout", "exception_message": "test fixture"}
        write_json(self.trial / "result.json", self.harbor)
        (self.artifacts / "replay.json").unlink()
        result = audit(self.task, self.artifacts, self.trial)
        self.assertFalse(result["passed"])
        self.assertEqual(result["reported_cost_usd"], .125)
        self.assertEqual(result["harbor"]["agent_result"], self.harbor["agent_result"])
        self.assertEqual(result["harbor"]["exception_info"], self.harbor["exception_info"])
        self.assertGreaterEqual(len(result["issues"]), 2)

    def test_harbor_digest_and_unknown_model_cost_are_not_silently_accepted(self):
        write_json(self.trial / "lock.json", {"task": {"digest": "sha256:" + "0" * 64}})
        self.harbor["agent_result"]["cost_usd"] = None
        write_json(self.trial / "result.json", self.harbor)
        result = audit(self.task, self.artifacts, self.trial)
        self.assertFalse(result["passed"])
        self.assertIn("Harbor task digest mismatch", " ".join(result["issues"]))
        self.assertIn("reported model cost is missing", " ".join(result["issues"]))
        self.assertEqual(result["harbor"]["agent_result"]["model_usage"], self.harbor["agent_result"]["model_usage"])

    def test_artifacts_only_scope_is_explicit(self):
        result = audit(self.task, self.artifacts)
        self.assertTrue(result["passed"], result)
        self.assertNotIn("harbor_task_digest", result["checks"])
        self.assertIn("No Harbor trial directory", " ".join(result["limits"]))


if __name__ == "__main__":
    unittest.main()
