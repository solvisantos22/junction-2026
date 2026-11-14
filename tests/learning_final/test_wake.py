"""Synthetic local wake-up tests; never queue a chat message or access Modal."""

import copy
import fcntl
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools.learning_final import wake


NOW = 1794679400.
DEADLINE = 1794714000.


class WakeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="learning-final-wake-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.monitor = self.root / "monitor"
        self.monitor.mkdir()
        self.private = self.root / "private"
        self.private.mkdir()
        self.state_path = self.private / "wake.json"
        self.codex = self.root / "fake-codex"
        self.codex.write_text("synthetic executable; never run\n")
        self.config = {"monitor_directory": str(self.monitor),
                       "thread_id": "12345678-1234-1234-1234-123456789abc",
                       "codex_path": str(self.codex), "working_directory": str(self.root),
                       "deadline_unix": DEADLINE}
        self.calls = []
        self.monitor_state()

    def monitor_state(self, status="monitoring", updated=NOW):
        (self.monitor / "state.json").write_text(json.dumps(
            {"campaign_id": "learning-final-20261114", "stage": "fit",
             "status": status, "updated_unix": updated}))

    def runner(self, command, **kwargs):
        self.calls.append((command, kwargs))
        # A reservation must reach disk before any potentially ambiguous side effect.
        self.assertTrue(self.state_path.is_file())
        self.assertEqual(json.loads(self.state_path.read_text())["status"], "reserved")
        return subprocess.CompletedProcess(command, 0, stdout="queued\n", stderr="")

    def tick(self, now=NOW, runner=None, config=None):
        return wake.tick(config or self.config, self.state_path, runner=runner or self.runner, now=now)

    def test_monitoring_heartbeat_does_not_queue(self):
        self.tick()
        self.tick(now=NOW + 900)
        self.assertEqual(self.calls, [])

    def test_terminal_monitor_statuses_queue_only_once(self):
        for status in ("ready_for_final_evaluation", "error", "campaign_deadline"):
            with self.subTest(status=status):
                self.state_path = self.private / f"{status}.json"
                self.calls.clear()
                self.monitor_state(status)
                self.tick()
                final = self.tick(now=NOW + 60)
                self.assertEqual(final["status"], "queued")
                self.assertEqual(len(self.calls), 1)
                command, kwargs = self.calls[0]
                self.assertEqual(command[:2], [str(self.codex), "queue"])
                self.assertEqual(command[command.index("--thread") + 1], self.config["thread_id"])
                self.assertIn("--resume", command)
                self.assertTrue(command[command.index("--message") + 1])
                self.assertEqual(Path(kwargs["cwd"]), self.root)

    def test_stale_monitor_queues_after_fifteen_minutes(self):
        self.tick(now=NOW + 901)
        self.tick(now=NOW + 2000)
        self.assertEqual(len(self.calls), 1)

    def test_absolute_deadline_fallback_queues_even_with_fresh_heartbeat(self):
        self.monitor_state(updated=DEADLINE)
        self.tick(now=DEADLINE)
        self.tick(now=DEADLINE + 1)
        self.assertEqual(len(self.calls), 1)

    def test_pause_and_stopped_status_override_terminal_staleness_and_deadline(self):
        for status in ("user_paused", "stopped_marker"):
            with self.subTest(status=status):
                self.state_path = self.private / f"{status}.json"
                self.monitor_state(status)
                self.tick(now=DEADLINE + 1)
                self.assertEqual(self.calls, [])
        self.state_path = self.private / "marker.json"
        self.monitor_state("ready_for_final_evaluation")
        (self.monitor / "pause.json").write_text('{"reason":"user paused"}')
        self.tick(now=DEADLINE + 1)
        self.assertEqual(self.calls, [])

    def test_ambiguous_queue_results_are_never_retried(self):
        self.monitor_state("ready_for_final_evaluation")
        outcomes = [subprocess.TimeoutExpired("fake-codex", 10), FileNotFoundError("not executable"),
                    subprocess.CompletedProcess([], 1, stdout="", stderr="failed"),
                    subprocess.CompletedProcess([], 0, stdout="queued", stderr="warning: unable to resume")]
        for index, outcome in enumerate(outcomes):
            with self.subTest(index=index):
                self.state_path = self.private / f"ambiguous-{index}.json"
                calls = []
                def runner(command, **kwargs):
                    calls.append(command)
                    self.assertTrue(self.state_path.is_file())
                    if isinstance(outcome, Exception):
                        raise outcome
                    return outcome
                self.assertEqual(self.tick(runner=runner)["status"], "uncertain")
                self.assertEqual(self.tick(now=NOW + 60, runner=runner)["status"], "uncertain")
                self.assertEqual(len(calls), 1)

    def test_crash_after_reservation_never_dispatches_again(self):
        self.monitor_state("ready_for_final_evaluation")
        def interrupted(command, **kwargs):
            self.calls.append(command)
            self.assertEqual(json.loads(self.state_path.read_text())["status"], "reserved")
            raise KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            self.tick(runner=interrupted)
        self.assertEqual(self.tick()["status"], "reserved")
        self.assertEqual(len(self.calls), 1)

    def test_lock_contention_prevents_concurrent_queue(self):
        self.monitor_state("ready_for_final_evaluation")
        with Path(str(self.state_path) + ".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):
                self.tick()
        self.assertEqual(self.calls, [])
        self.assertFalse(self.state_path.exists())
        self.assertEqual(self.tick()["status"], "queued")
        self.assertEqual(len(self.calls), 1)

    def test_missing_monitor_gets_grace_and_invalid_monitor_gets_diagnostic(self):
        monitor_path = self.monitor / "state.json"
        monitor_path.unlink()
        self.assertEqual(self.tick()["status"], "waiting")
        self.assertEqual(self.tick(now=NOW + 900)["status"], "waiting")
        self.assertEqual(self.tick(now=NOW + 901)["reason"], "missing_monitor_state")
        self.assertEqual(len(self.calls), 1)
        self.state_path = self.private / "malformed-monitor.json"
        monitor_path.write_text("not valid JSON")
        self.assertEqual(self.tick()["reason"], "unreadable_monitor_state")
        self.assertEqual(len(self.calls), 2)

    def test_pause_arriving_after_reservation_prevents_queue(self):
        self.monitor_state("ready_for_final_evaluation")
        original = wake.save
        def save_and_pause(path, value):
            original(path, value)
            if value["status"] == "reserved":
                (self.monitor / "pause.json").write_text("{}")
        with patch.object(wake, "save", side_effect=save_and_pause):
            self.assertEqual(self.tick()["status"], "disabled")
        (self.monitor / "pause.json").unlink()
        self.assertEqual(self.tick()["status"], "disabled")
        self.assertEqual(self.calls, [])

    def test_wake_stop_file_disables_only_this_watcher(self):
        self.monitor_state("ready_for_final_evaluation")
        (self.monitor / "wake-stop").touch()
        state = self.tick()
        self.assertEqual((state["status"], state["reason"]), ("disabled", "wake_stop_file"))
        self.assertEqual(self.calls, [])

    def test_changed_configuration_is_rejected_before_queue(self):
        self.tick()
        changed = copy.deepcopy(self.config)
        changed["thread_id"] = "22345678-1234-1234-1234-123456789abc"
        self.monitor_state("ready_for_final_evaluation")
        with self.assertRaises(ValueError):
            self.tick(config=changed)
        self.assertEqual(self.calls, [])

    def test_changed_code_identity_is_rejected_before_queue(self):
        self.tick()
        altered_source = self.root / "changed-wake.py"
        altered_source.write_text("different code\n")
        self.monitor_state("ready_for_final_evaluation")
        with patch.object(wake, "__file__", str(altered_source)), self.assertRaises(ValueError):
            self.tick()
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
