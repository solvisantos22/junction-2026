"""Audit integrity on constructed tool histories, without model or Docker calls.

These fixtures do not claim that the frozen model policy produced the history.
They test the auditor's declared replay/record consistency boundary, not runtime
attestation or code-generation provenance.
"""

import copy
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools.rule_transfer.audit import audit
from tools.rule_transfer.runner import make_service
from tools.rule_transfer.study import KINDS, POLICY, ROOT, gate, summarize


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normal(value):
    return json.loads(json.dumps(value))


class AuditIntegrityTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="rule-transfer-audit-tests-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.report_path = self.root / "report.json"
        (self.root / "cases").mkdir()
        source_names = ("tools/rule_transfer/runner.py", "tools/rule_transfer/worker.py",
                        "lightlag_shift/rule_change.py")
        sources = {name: digest(ROOT / name) for name in source_names}
        self.report = {"protocol": {
            "start": 3200, "count": 1, "kinds": list(KINDS), "model_calls": 0,
            "policy_path": str(POLICY.relative_to(ROOT)), "policy_sha256": digest(POLICY),
            "source_sha256": sources, "docker_image_id": "synthetic-test-image",
        }, "cases": []}
        self.bundles = []
        for policy in ("saved_opus", "prepared"):
            for kind in KINDS:
                service = make_service(3200, kind)
                transcript = []
                for method, arguments in (
                    ("rules", {}), ("map", {}),
                    ("uplink", {"commands": [{"action": "drive", "heading_deg": 0, "metres": 1}]}),
                    ("advance", {"ticks": 5}),
                ):
                    record = {"n": len(transcript) + 1, "tool": method,
                              "arguments": arguments, "tick_before": service._tick}
                    result = service.call(method, arguments)
                    record.update(ok=True, result=normal(result), tick_after=service._tick)
                    transcript.append(record)
                evaluation = normal(service.finish())
                result = {
                    "seed": 3200, "kind": kind, "status": "returned", "errors": [],
                    "evaluation": evaluation, "normalized_score": evaluation["raw_score"] / evaluation["max_available_value"],
                    "final_tick": 50, "public_calls": len(transcript), "invalid_calls": 0,
                    "model_calls": 0, "policy_sha256": digest(POLICY),
                    "image_id": "synthetic-test-image",
                    "runner_sha256": sources["tools/rule_transfer/runner.py"],
                    "worker_sha256": sources["tools/rule_transfer/worker.py"],
                }
                bundle = {"policy": policy, "kind": kind, "seed": 3200, "result": result,
                          "transcript": transcript, "replay": normal(service._env.replay()), "stderr": ""}
                row = {"policy": policy, "kind": kind, "seed": 3200, "result": copy.deepcopy(result),
                       "artifact": f"cases/{policy}-{kind}.json.gz"}
                self.report["cases"].append(row)
                self.bundles.append(bundle)
                self.write_bundle(len(self.bundles) - 1)
        self.report["summary"] = summarize(self.report["cases"])
        self.report["gate"] = gate(self.report["cases"], self.report["summary"])
        self.write_report()

    def write_bundle(self, index):
        row = self.report["cases"][index]
        path = self.root / row["artifact"]
        path.write_bytes(gzip.compress(json.dumps(self.bundles[index]).encode(), mtime=0))
        row["sha256"] = digest(path)

    def write_report(self):
        self.report_path.write_text(json.dumps(self.report))

    def test_valid_histories_reconstruct_every_case_and_summary(self):
        checked = audit(self.report_path)
        self.assertEqual(checked["cases_verified"], 10)
        self.assertEqual(checked["public_calls_reconstructed"], 40)
        self.assertTrue(checked["full_replays_match"])
        self.assertTrue(checked["summary_independently_recomputed"])

    def test_changed_artifact_without_updated_hash_is_rejected(self):
        path = self.root / self.report["cases"][0]["artifact"]
        path.write_bytes(path.read_bytes() + b"unexpected")
        with self.assertRaisesRegex(AssertionError, "artifact hash"):
            audit(self.report_path)

    def test_forged_reward_is_rejected_even_with_updated_artifact_hash(self):
        self.bundles[0]["result"]["evaluation"]["raw_score"] = 1.0
        self.report["cases"][0]["result"] = copy.deepcopy(self.bundles[0]["result"])
        self.write_bundle(0)
        self.write_report()
        with self.assertRaisesRegex(AssertionError, "evaluation"):
            audit(self.report_path)

    def test_forged_tool_reply_is_rejected_even_with_updated_artifact_hash(self):
        self.bundles[0]["transcript"][0]["result"]["max_ticks"] = 999
        self.write_bundle(0)
        self.write_report()
        with self.assertRaisesRegex(AssertionError, "public call"):
            audit(self.report_path)

    def test_duplicate_case_and_missing_case_are_rejected(self):
        for cases in (self.report["cases"][:-1],
                      self.report["cases"][:-1] + [self.report["cases"][0]]):
            with self.subTest(count=len(cases)):
                changed = {**self.report, "cases": cases}
                self.report_path.write_text(json.dumps(changed))
                with self.assertRaisesRegex(AssertionError, "missing, duplicate"):
                    audit(self.report_path)

    def test_summary_and_gate_cannot_override_reconstructed_results(self):
        for field in ("summary", "gate"):
            with self.subTest(field=field):
                changed = copy.deepcopy(self.report)
                if field == "summary":
                    changed[field]["saved_opus"]["changed"]["mean_raw_score"] = 123
                else:
                    changed[field]["retire"] = not changed[field]["retire"]
                self.report_path.write_text(json.dumps(changed))
                with self.assertRaisesRegex(AssertionError, field):
                    audit(self.report_path)


if __name__ == "__main__":
    unittest.main()
