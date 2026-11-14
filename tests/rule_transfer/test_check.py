"""Fresh-check plumbing on consumed seeds and synthetic policy histories only.

No reserved fresh mission is constructed, model is called, or Docker policy is
executed. These tests verify bookkeeping boundaries, not adaptation success.
"""

import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools.rule_transfer import check
from tools.rule_transfer.runner import make_service
from tools.rule_transfer.study import POLICY, POLICY_HASH, normal

IMAGE = "sha256:" + "a" * 64


class CheckIntegrityTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="rule-transfer-check-tests-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.policy = self.root / "candidate.py"
        self.policy.write_bytes(POLICY.read_bytes())
        self.freeze = self.root / "freeze.json"
        self.freeze.write_text(json.dumps({
            "schema": "rule-transfer-adaptation-freeze-v1", "status": "complete",
            "final_policy_sha256": POLICY_HASH, "base_policy_sha256": POLICY_HASH,
            "model": "claude-opus-5-5", "docker_image_id": IMAGE, "fresh_check_opened": False,
            "source_sha256": {str(path.relative_to(check.ROOT)): check.digest(path)
                              for path in check.source_paths()},
        }))
        self.output = self.root / "check"

    @staticmethod
    def no_op_case(policy_path, seed, kind, output, *, image):
        # Construct a valid no-op public history without asserting that the
        # named policy actually generated it. Audit explicitly cannot attest it.
        if seed != 3200:
            raise AssertionError("test must not open a fresh seed")
        service = make_service(seed, kind)
        received = normal(service.call("rules"))
        transcript = [{"n": 1, "tool": "rules", "arguments": {},
                       "tick_before": 0, "tick_after": 0, "ok": True, "result": received}]
        evaluation = normal(service.finish())
        result = {"seed": seed, "kind": kind, "status": "returned", "errors": [],
                  "evaluation": evaluation, "normalized_score": 0.0, "model_calls": 0,
                  "public_calls": 1, "invalid_calls": 0, "final_tick": 50,
                  "policy_sha256": check.digest(policy_path), "image_id": image,
                  "runner_sha256": check.digest(check.ROOT / "tools/rule_transfer/runner.py"),
                  "worker_sha256": check.digest(check.ROOT / "tools/rule_transfer/worker.py")}
        output.mkdir()
        (output / "result.json").write_text(json.dumps(result))
        (output / "replay.json").write_text(json.dumps(normal(service._env.replay())))
        (output / "transcript.jsonl").write_text(json.dumps(transcript[0]) + "\n")
        (output / "stderr.txt").write_text("")
        return result

    def run_smoke(self, runner=None, parallel=2):
        real_check_output = subprocess.check_output

        def inspect_image(command, **kwargs):
            if command[:3] == ["docker", "image", "inspect"]:
                return IMAGE + "\n"
            return real_check_output(command, **kwargs)

        with patch.object(check, "run_case", side_effect=runner or self.no_op_case), \
                patch.object(subprocess, "check_output", side_effect=inspect_image), \
                contextlib.redirect_stdout(io.StringIO()):
            return check.run(self.policy, self.freeze, self.output, IMAGE,
                             start=3200, count=1, parallel=parallel, development=True)

    def test_exact_fresh_range_cannot_be_opened_as_development(self):
        check.validate_range(52000, 40, False)
        check.validate_range(3200, 1, True)
        for start, count, development in ((52000, 1, False), (52000, 40, True),
                                           (3200, 1, False), (3239, 2, True)):
            with self.subTest(start=start, count=count, development=development):
                with self.assertRaises(ValueError):
                    check.validate_range(start, count, development)

    def test_bad_freeze_stops_before_docker_or_any_case(self):
        self.policy.write_text("def play(tools): pass\n")
        with patch.object(check, "reference_case") as reference, \
                patch.object(check, "run_case") as policy, \
                patch.object(subprocess, "check_output") as subprocess_call:
            with self.assertRaisesRegex(ValueError, "mismatched"):
                check.run(self.policy, self.freeze, self.output, IMAGE)
            reference.assert_not_called()
            policy.assert_not_called()
            subprocess_call.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_all_three_policies_are_retained_and_independently_audited(self):
        report = self.run_smoke()
        self.assertEqual(len(report["cases"]), 15)
        self.assertEqual(set(report["summary"]), {"original", "adapted", "prepared"})
        audited = check.audit(self.output / "report.json")
        self.assertEqual(audited["cases_verified"], 15)
        self.assertEqual(audited["split"], "development-smoke")
        self.assertTrue(audited["summary_and_gate_independently_recomputed"])

    def test_changed_adaptation_source_stops_before_any_generation(self):
        changed = json.loads(self.freeze.read_text())
        changed["source_sha256"]["tools/rule_transfer/runner.py"] = "0" * 64
        self.freeze.write_text(json.dumps(changed))
        with patch.object(check, "reference_case") as reference, \
                patch.object(check, "run_case") as policy, \
                patch.object(subprocess, "check_output") as subprocess_call:
            with self.assertRaisesRegex(ValueError, "source changed"):
                check.run(self.policy, self.freeze, self.output, IMAGE)
            reference.assert_not_called()
            policy.assert_not_called()
            subprocess_call.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_duplicate_case_is_rejected(self):
        report = self.run_smoke()
        report["cases"][-1] = report["cases"][0]
        (self.output / "report.json").write_text(json.dumps(report))
        with self.assertRaisesRegex(AssertionError, "duplicate"):
            check.audit(self.output / "report.json")

    def test_rehashed_freeze_cannot_claim_check_was_already_opened(self):
        report = self.run_smoke()
        freeze_path = self.output / "freeze.json"
        changed = json.loads(freeze_path.read_text())
        changed["fresh_check_opened"] = True
        freeze_path.write_text(json.dumps(changed))
        report["protocol"]["freeze"]["sha256"] = check.digest(freeze_path)
        (self.output / "report.json").write_text(json.dumps(report))
        with self.assertRaises(ValueError):
            check.audit(self.output / "report.json")

    def test_mid_run_policy_edit_leaves_an_incomplete_report(self):
        edited = False

        def mutate_copy(policy_path, seed, kind, output, *, image):
            nonlocal edited
            if not edited:
                policy_path.write_bytes(policy_path.read_bytes() + b"\n# synthetic mutation\n")
                edited = True
            return self.no_op_case(policy_path, seed, kind, output, image=image)

        with self.assertRaisesRegex(RuntimeError, "policy changed"):
            self.run_smoke(mutate_copy, parallel=1)
        report = json.loads((self.output / "report.json").read_text())
        self.assertFalse(report["complete"])
        self.assertEqual(len(report["cases"]), 15)
        with self.assertRaises(AssertionError):
            check.audit(self.output / "report.json")


if __name__ == "__main__":
    unittest.main()
