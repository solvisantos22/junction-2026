"""Preparation/broker guards; fixtures never construct the declared fresh maps."""

import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
SPEC = importlib.util.find_spec("tools.lightlag_experiments.overnight_synthesis")
if SPEC:
    from tools.lightlag_experiments import overnight_synthesis as subject
else:
    subject = None


class PreparationGuards(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(subject, "synthesis preparation is not implemented")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_existing_output_is_never_reused(self):
        old = self.root / "old"
        old.mkdir()
        (old / "evidence").write_text("preserve")
        with self.assertRaises(FileExistsError):
            subject.claim_output(old)
        self.assertEqual((old / "evidence").read_text(), "preserve")

    def test_source_guard_checks_snapshot_and_rejects_extra_python(self):
        frozen = self.root / "frozen"
        frozen.mkdir()
        (frozen / "one.py").write_bytes(b"x = 1\n")
        expected = {"one.py": subject.sha256(b"x = 1\n")}
        subject.verify_source(frozen, expected)
        (self.root / "mutable.py").write_text("unrelated change")
        subject.verify_source(frozen, expected)
        (frozen / "injected.py").write_text("pass")
        with self.assertRaises(subject.GuardError):
            subject.verify_source(frozen, expected)
        (frozen / "injected.py").unlink()
        (frozen / "one.py").write_text("x = 2\n")
        with self.assertRaises(subject.GuardError):
            subject.verify_source(frozen, expected)

    def test_extraction_permits_only_outer_fence_and_terminal_whitespace(self):
        self.assertEqual(subject.extract_module("```python\n  x = 1\n```\n\n"), "  x = 1")
        self.assertEqual(subject.extract_module("\n  x = 1\n\t"), "\n  x = 1")
        prose = "Here is code:\n```python\nx=1\n```"
        self.assertEqual(subject.extract_module(prose), prose)
        multiple = "```python\nx=1\n```\n```python\ny=2\n```"
        self.assertEqual(subject.extract_module(multiple), multiple)

    def test_request_contains_exact_public_inputs_and_fixed_settings(self):
        request = subject.build_request("PUBLIC INSTRUCTION", "PUBLIC AID",
                                        {"rush": {"max_ticks": 50}, "rush_noisy": {"max_ticks": 50}})
        self.assertEqual(request["model"], "claude-opus-5-5")
        self.assertEqual(request["max_tokens"], 24000)
        self.assertEqual(request["thinking"], {"type": "adaptive"})
        self.assertEqual(request["output_config"], {"effort": "high"})
        self.assertEqual(request.get("speed"), "standard")
        self.assertEqual(request.get("service_tier"), "standard_only")
        self.assertNotIn("tools", request)
        self.assertNotIn("temperature", request)
        content = request["messages"][0]["content"]
        self.assertIn("PUBLIC INSTRUCTION", content)
        self.assertIn("PUBLIC AID", content)
        self.assertIn("default_terrain", content)
        for forbidden in ("60000", "60019", "501", "kf_mpc", "raw_score", "/Users/", "reference route"):
            self.assertNotIn(forbidden, content)

    def test_container_command_has_only_two_read_only_file_mounts(self):
        policy, worker = self.root / "policy.py", self.root / "worker.py"
        for p in (policy, worker):
            p.write_text("pass\n")
        cmd = subject.docker_command("docker", "python@sha256:" + "a" * 64,
                                     policy, worker, "synthesis-test")
        for flag in ("--read-only", "--network=none", "--cap-drop=ALL", "--user=65534:65534",
                     "--cpus=1", "--memory=256m", "--pids-limit=64", "--security-opt=no-new-privileges"):
            self.assertIn(flag, cmd)
        mounts = [cmd[i + 1] for i, value in enumerate(cmd) if value == "--mount"]
        self.assertEqual(len(mounts), 2)
        self.assertTrue(all("readonly" in mount for mount in mounts))
        self.assertFalse(any("/var/run/docker" in value or value == "--env-file" for value in cmd))

    def test_public_instruction_reconstruction_matches_every_frozen_task(self):
        self.assertTrue(hasattr(subject, "original_instruction"), "instruction freezing is not implemented")
        instruction, provenance = subject.original_instruction(REPO)
        for profile in ("rush", "rush-noisy"):
            for seed in range(501, 505):
                manifest = json.loads((REPO / f"docs/lightlag-runs/{profile}-seed{seed}-delay3-kf-mpc/experiment.json").read_text())
                self.assertEqual(subject.sha256(instruction.encode()), manifest["task_sha256"]["instruction.md"])
        self.assertEqual(len(provenance), 2)

    def test_prepared_input_guard_rejects_changes_before_phase_execution(self):
        self.assertTrue(hasattr(subject, "verify_preparation"), "preparation guard is not implemented")
        (self.root / "request.json").write_bytes(b"{}\n")
        manifest = {"artifact_sha256": {"request.json": subject.sha256(b"{}\n")}}
        subject.verify_preparation(self.root, manifest)
        (self.root / "request.json").write_text('{"changed":true}')
        with self.assertRaises(subject.GuardError):
            subject.verify_preparation(self.root, manifest)

    def test_diagnostic_sanitization_never_publishes_local_paths(self):
        self.assertTrue(hasattr(subject, "sanitize_text"), "diagnostic sanitizer is not implemented")
        message = "mount /Users/example/private/a.py failed; temp /var/folders/xx/random/file and /tmp/task/a.py"
        cleaned = subject.sanitize_text(message)
        self.assertNotIn("/Users/", cleaned)
        self.assertNotIn("/var/folders/", cleaned)
        self.assertNotIn("/tmp/", cleaned)


class BrokerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if subject is None:
            return
        cls.temp = tempfile.TemporaryDirectory()
        cls.frozen = Path(cls.temp.name) / "source"
        cls.hashes = subject.freeze_source(REPO, cls.frozen)
        cls.runtime = subject.load_runtime(cls.frozen, cls.hashes)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "temp"):
            cls.temp.cleanup()

    def setUp(self):
        self.assertIsNotNone(subject, "broker is not implemented")
        self.broker = subject.Broker(self.runtime, 501, "rush")

    def test_json_shapes_are_copy_safe_and_only_five_tools_dispatch(self):
        first = self.broker.call("rules", {})
        first["max_ticks"] = -1
        self.assertEqual(self.broker.call("rules", {})["max_ticks"], 50)
        for forbidden in ("finish", "result", "_env", "evaluate", "reset"):
            with self.assertRaises(subject.PublicCallError):
                self.broker.call(forbidden, {})
        self.assertEqual(self.broker.policy_calls, 7)
        self.assertEqual(len(self.broker.transcript), 7)
        self.assertTrue(all(not row["ok"] for row in self.broker.transcript[2:]))

    def test_policy_error_still_grades_accepted_commands_at_horizon(self):
        self.broker.call("uplink", {"commands": [{"action": "drive", "heading_deg": 0, "metres": 1}]})
        with self.assertRaises(subject.PublicCallError):
            self.broker.call("advance", {"ticks": 0})
        episode = self.broker.finish({"status": "policy_error", "error": {"type": "ValueError"}})
        self.assertEqual(episode["result"]["tick"], 50)
        self.assertEqual(len(episode["replay"]["commands"]), 1)
        self.assertTrue(any(event["type"] == "command_executed"
                            for state in episode["replay"]["states"] for event in state["events"]))
        self.assertEqual(episode["execution"]["status"], "policy_error")
        self.assertEqual(episode["grading_status"], "scored")
        self.assertEqual(subject.replay_episode(self.runtime, episode)["exact"], True)

    def test_501st_attempt_is_rejected_before_dispatch_and_recorded(self):
        for _ in range(500):
            self.broker.call("rules", {})
        with self.assertRaises(subject.CallLimit):
            self.broker.call("advance", {"ticks": 1})
        self.assertEqual(self.broker.transcript[-1]["tick_after"], 0)
        self.assertEqual(self.broker.transcript[-1]["error"]["type"], "CallLimit")

    def test_protocol_requires_sequence_exact_envelope_and_json_object(self):
        good = {"id": 1, "tool": "rules", "arguments": {}}
        self.assertEqual(subject.parse_call(json.dumps(good).encode(), 1), good)
        for bad in (dict(good, id=2), dict(good, state=True), [], {"id": True, "tool": "rules", "arguments": {}},
                    {"id": 1, "tool": "rules", "arguments": {"x": float("nan")}}):
            with self.assertRaises(subject.ProtocolError):
                subject.parse_call(json.dumps(bad).encode(), 1)

    def test_all_eight_historical_reference_scores_and_full_replays_match(self):
        self.assertTrue(hasattr(subject, "historical_gate"), "historical gate is not implemented")
        output = Path(self.temp.name) / "historical-gate"
        output.mkdir()
        gate = subject.historical_gate(REPO, self.runtime, output)
        self.assertEqual(len(gate["rows"]), 8)
        self.assertTrue(all(row["passed"] for row in gate["rows"]))
        self.assertEqual(gate["passed"], True)

    @unittest.skipUnless(os.environ.get("SYNTHESIS_TEST_IMAGE"), "set pinned image for actual Docker probes")
    def test_actual_docker_policy_errors_timeout_and_accepted_queue(self):
        self.assertTrue(hasattr(subject, "run_container"), "container broker is not implemented")
        image = os.environ["SYNTHESIS_TEST_IMAGE"]
        worker = REPO / "tools/lightlag_experiments/overnight_synthesis_worker.py"
        for suffix, code, seconds, expected in [
            ("error", "def play(t):\n t.uplink([{'action':'drive','heading_deg':0,'metres':1}])\n raise RuntimeError('fixture failure')\n", 10, "policy_error"),
            ("timeout", "def play(t):\n t.rules()\n while True: pass\n", 1, "policy_timeout"),
            ("syntax", "def play(:\n", 10, "policy_error"),
        ]:
            policy = Path(self.temp.name) / (suffix + ".py")
            policy.write_text(code)
            broker = subject.Broker(self.runtime, 501, "rush")
            execution = subject.run_container(broker, policy, worker, image, "/usr/local/bin/docker", seconds=seconds)
            self.assertEqual(execution["status"], expected, execution)
            self.assertTrue(execution["cleanup"]["confirmed_absent"])
            episode = broker.finish(execution)
            self.assertEqual(episode["result"]["tick"], 50)
            self.assertTrue(subject.replay_episode(self.runtime, episode)["exact"])
            if suffix == "error":
                self.assertEqual(len(episode["replay"]["commands"]), 1)

    @unittest.skipUnless(os.environ.get("SYNTHESIS_TEST_IMAGE"), "set pinned image for actual Docker probes")
    def test_actual_container_isolation_probe(self):
        self.assertTrue(hasattr(subject, "isolation_probe"), "container isolation probe is not implemented")
        report = subject.isolation_probe(os.environ["SYNTHESIS_TEST_IMAGE"], "/usr/local/bin/docker",
                                          REPO / "tools/lightlag_experiments/overnight_synthesis_worker.py",
                                          Path(self.temp.name) / "probe")
        self.assertTrue(report["passed"], report)


if __name__ == "__main__":
    unittest.main()
