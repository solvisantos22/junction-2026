"""Behavioral tests: all subprocesses are replaced at the process boundary."""

import contextlib
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import fcntl
import io
import json
import os
from pathlib import Path
import plistlib
import subprocess
import tempfile
import threading
import unittest

import watch


NOW = 1794596400.0


class WatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config_path = self.root / "config.json"
        self.timer = self.root / "junction-watch.plist"
        self.config = {
            "enabled": True,
            "thread_id": "dedicated-thread",
            "parent_thread_id": "parent-thread",
            "codex_path": "/private/bin/codex",
            "working_directory": str(self.root),
            "interval_seconds": 900,
            "ends_at": "2026-11-15T17:00:00+02:00",
            "instructions_path": str(self.root / "instructions.md"),
            "launch_agent_path": str(self.timer),
            "launch_agent_label": "com.example.junction-watch",
        }
        self.write("config.json", self.config)
        self.calls = []
        self.outcome = subprocess.CompletedProcess([], 0, "Queued", "")

    def write(self, name, value):
        (self.root / name).write_text(json.dumps(value), encoding="utf-8")

    def read(self, name):
        return json.loads((self.root / name).read_text(encoding="utf-8"))

    def runner(self, args, **kwargs):
        self.calls.append((args, kwargs))
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome

    def invoke(self, command="tick", when=NOW, runner=None):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = watch.main(
                ["--config", str(self.config_path), command],
                runner=runner or self.runner,
                now=when,
            )
        return code, json.loads(output.getvalue())

    def make_timer(self, label=None):
        self.timer.write_bytes(plistlib.dumps({
            "Label": label or self.config["launch_agent_label"]
        }))

    def test_enabled_tick_queues_check_and_records_success(self):
        code, result = self.invoke()
        self.assertEqual(code, 0)
        self.assertEqual(result["state"], "queued")
        args, kwargs = self.calls[0]
        self.assertEqual(args[:4], [
            self.config["codex_path"], "queue", "--thread", "dedicated-thread"
        ])
        self.assertEqual(args[4], "--message")
        self.assertIn(self.config["instructions_path"], args[5])
        self.assertIn(str(self.root / "run.json"), args[5])
        self.assertIn("last_finished_at", args[5])
        self.assertEqual(args[6:], ["--resume"])
        self.assertEqual(kwargs, {
            "cwd": str(self.root), "capture_output": True,
            "text": True, "timeout": 45,
        })
        state = self.read("scheduler.json")
        self.assertEqual(state["last_queued_at"], NOW)
        self.assertEqual(state["last_successful_queue_at"], NOW)
        self.assertEqual(state["queue_status"], "queued")
        self.assertFalse((self.root / "run.json").exists())

    def test_paused_tick_does_nothing(self):
        self.config["enabled"] = False
        self.write("config.json", self.config)
        self.assertEqual(self.invoke()[1]["state"], "paused")
        self.assertEqual(self.calls, [])
        self.assertFalse((self.root / "scheduler.json").exists())

    def test_relative_config_path_still_sends_absolute_acknowledgement_path(self):
        self.config_path = Path(os.path.relpath(self.config_path))
        self.invoke()
        self.assertIn("in {}.".format(self.root / "run.json"), self.calls[0][0][5])

    def test_expiry_disables_and_removes_only_configured_timer(self):
        self.make_timer()
        other = self.root / "other.plist"
        other.write_text("unrelated", encoding="utf-8")
        code, result = self.invoke(when=1794754800.0)
        self.assertEqual(code, 0)
        self.assertEqual(result["state"], "expired")
        self.assertFalse(self.read("config.json")["enabled"])
        self.assertFalse(self.timer.exists())
        self.assertTrue(other.exists())
        self.assertEqual(self.calls[0][0], [
            "launchctl", "bootout",
            "gui/{}/com.example.junction-watch".format(os.getuid()),
        ])
        self.assertEqual(len(self.calls), 1)

    def test_pending_check_is_not_queued_again(self):
        self.invoke()
        self.invoke(when=NOW + 899)
        self.assertEqual(len(self.calls), 1)

    def test_stalled_check_alerts_parent_once(self):
        self.invoke()
        self.invoke(when=NOW + 900)
        self.invoke(when=NOW + 1800)
        self.assertEqual(len(self.calls), 2)
        alert = self.calls[1][0]
        self.assertEqual(alert[2:4], ["--thread", "parent-thread"])
        self.assertIn("health alert", alert[5].lower())
        self.assertEqual(self.read("scheduler.json")["stalled_alert_for"], NOW)

    def test_uncertain_health_alert_is_not_retried(self):
        self.invoke()
        self.outcome = subprocess.CompletedProcess([], 1, "", "daemon unavailable")
        self.assertEqual(self.invoke(when=NOW + 900)[0], 1)
        self.invoke(when=NOW + 1800)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.read("scheduler.json")["alert_status"], "uncertain")

    def test_acknowledgement_allows_next_scheduled_check(self):
        self.invoke()
        self.invoke(when=NOW + 900)
        run = {
            "last_started_at": NOW + 1, "last_finished_at": NOW + 1000,
            "status": "partial", "sources": {"discord": "unavailable"},
        }
        self.write("run.json", run)
        self.invoke(when=NOW + 1800)
        self.assertEqual(len(self.calls), 3)
        self.assertEqual(self.calls[2][0][3], "dedicated-thread")
        self.assertEqual(self.read("scheduler.json")["last_queued_at"], NOW + 1800)
        self.assertEqual(self.read("run.json"), run)
        self.invoke(when=NOW + 2700)
        self.assertEqual(len(self.calls), 4)

    def test_finished_check_waits_for_interval_before_next_dispatch(self):
        self.invoke()
        self.write("run.json", {"last_finished_at": NOW + 1})
        self.assertEqual(self.invoke(when=NOW + 2)[1]["state"], "waiting")
        self.assertEqual(len(self.calls), 1)

    def test_previous_completion_cannot_acknowledge_new_reservation(self):
        for finished in (NOW, NOW + 0.001):
            with self.subTest(previous_completion=finished):
                self.calls.clear()
                self.write("scheduler.json", {"last_queued_at": NOW - 900})
                self.write("run.json", {"last_finished_at": finished})
                self.invoke()
                self.invoke(when=NOW + 901)
                self.assertEqual(
                    [call[0][3] for call in self.calls],
                    ["dedicated-thread", "parent-thread"],
                )
                self.assertGreater(self.read("scheduler.json")["last_queued_at"], finished)

    def test_nonzero_exit_stays_uncertain_without_duplicate_dispatch(self):
        self.outcome = subprocess.CompletedProcess([], 1, "", "daemon error")
        self.assertEqual(self.invoke()[0], 1)
        self.invoke(when=NOW + 1)
        self.assertEqual(len(self.calls), 1)
        state = self.read("scheduler.json")
        self.assertEqual(state["queue_status"], "uncertain")
        self.assertIn("status 1", state["last_queue_error"])
        self.assertNotIn("last_successful_queue_at", state)

    def test_resume_warning_is_failure_even_with_zero_exit(self):
        self.outcome = subprocess.CompletedProcess(
            [], 0, "Queued", "Warning: failed to resume thread"
        )
        self.assertEqual(self.invoke()[0], 1)
        self.invoke(when=NOW + 1)
        self.assertEqual(len(self.calls), 1)
        state = self.read("scheduler.json")
        self.assertEqual(state["queue_status"], "uncertain")
        self.assertIn("resume", state["last_queue_error"])
        self.assertNotIn("last_successful_queue_at", state)

    def test_timeout_preserves_pending_reservation(self):
        self.outcome = subprocess.TimeoutExpired("codex", 45)
        self.assertEqual(self.invoke()[0], 1)
        self.invoke(when=NOW + 1)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.read("scheduler.json")["queue_status"], "uncertain")

    def test_dispatch_reservation_survives_process_interruption(self):
        self.outcome = KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            self.invoke()
        self.outcome = subprocess.CompletedProcess([], 0, "", "")
        self.invoke(when=NOW + 1)
        self.assertEqual(len(self.calls), 1)

    def test_pause_resume_and_stop_control_dispatch_and_timer(self):
        self.make_timer()
        self.invoke("pause")
        self.assertFalse(self.read("config.json")["enabled"])
        self.assertTrue(self.timer.exists())
        self.invoke("resume")
        self.assertTrue(self.read("config.json")["enabled"])
        self.invoke("stop")
        self.assertFalse(self.read("config.json")["enabled"])
        self.assertFalse(self.timer.exists())
        self.assertEqual(len(self.calls), 1)

    def test_cannot_resume_after_expiry(self):
        self.config["enabled"] = False
        self.write("config.json", self.config)
        self.assertEqual(self.invoke("resume", when=1794754800.0)[0], 1)
        self.assertFalse(self.read("config.json")["enabled"])
        self.assertFalse(any(call[0][1] == "queue" for call in self.calls))

    def test_status_does_not_expose_private_config_or_source_results(self):
        self.config["secret"] = "private-token"
        self.write("config.json", self.config)
        self.write("run.json", {"last_finished_at": NOW - 1, "sources": {
            "private": "sensitive source text"
        }})
        code, status = self.invoke("status")
        self.assertEqual(code, 0)
        rendered = json.dumps(status)
        for private in ("private-token", "sensitive source text", "dedicated-thread", str(self.root)):
            self.assertNotIn(private, rendered)
        self.assertEqual(status["interval_seconds"], 900)
        self.assertEqual(self.calls, [])

    def test_string_false_does_not_enable_dispatch(self):
        self.config["enabled"] = "false"
        self.write("config.json", self.config)
        self.assertEqual(self.invoke()[0], 1)
        self.assertEqual(self.calls, [])

    def test_invalid_interval_does_not_enable_dispatch(self):
        self.config["interval_seconds"] = 0
        self.write("config.json", self.config)
        self.assertEqual(self.invoke()[0], 1)
        self.assertEqual(self.calls, [])

    def test_stop_still_disables_and_removes_timer_with_corrupt_scheduler(self):
        self.make_timer()
        (self.root / "scheduler.json").write_text("incomplete", encoding="utf-8")
        self.assertEqual(self.invoke("stop")[0], 0)
        self.assertFalse(self.read("config.json")["enabled"])
        self.assertFalse(self.timer.exists())

    def test_stopping_refuses_to_remove_a_different_launch_agent(self):
        self.make_timer(label="com.example.other")
        self.assertEqual(self.invoke("stop")[0], 1)
        self.assertFalse(self.read("config.json")["enabled"])
        self.assertTrue(self.timer.exists())
        self.assertEqual(self.calls, [])

    def test_invalid_acknowledgement_preserves_pending_check_and_alerts_once(self):
        for invalid in (str(NOW + 1), None, True, -1, float("nan"), float("inf"), []):
            with self.subTest(invalid_completion=invalid):
                self.calls.clear()
                self.write("scheduler.json", {})
                self.write("run.json", {})
                self.invoke()
                self.write("run.json", {"last_finished_at": invalid})
                self.assertEqual(self.invoke(when=NOW + 899)[0], 1)
                self.assertEqual(len(self.calls), 1)
                self.invoke(when=NOW + 900)
                self.invoke(when=NOW + 1800)
                self.assertEqual(
                    [call[0][3] for call in self.calls],
                    ["dedicated-thread", "parent-thread"],
                )
                code, status = self.invoke("status", when=NOW + 1800)
                self.assertEqual(code, 1)
                self.assertTrue(status["pending"])
                self.assertIn("acknowledgement_error", status)

    def test_malformed_run_json_alerts_once_then_recovers_after_valid_ack(self):
        self.invoke()
        (self.root / "run.json").write_text("{", encoding="utf-8")
        self.invoke(when=NOW + 900)
        self.invoke(when=NOW + 1800)
        self.assertEqual(
            [call[0][3] for call in self.calls],
            ["dedicated-thread", "parent-thread"],
        )
        self.write("run.json", {"last_finished_at": NOW + 1801})
        self.assertEqual(self.invoke(when=NOW + 2700)[0], 0)
        self.assertEqual(self.calls[-1][0][3], "dedicated-thread")
        self.assertEqual(len(self.calls), 3)

    def test_invalid_acknowledgement_without_reservation_fails_closed(self):
        self.write("run.json", {"last_finished_at": "invalid"})
        self.assertEqual(self.invoke()[0], 1)
        self.assertEqual(self.calls, [])

    def test_corrupt_config_or_scheduler_still_fails_closed(self):
        for name in ("config.json", "scheduler.json"):
            with self.subTest(corrupt_file=name):
                self.calls.clear()
                self.write("config.json", self.config)
                self.write("scheduler.json", {})
                self.invoke()
                (self.root / name).write_text("{", encoding="utf-8")
                self.assertEqual(self.invoke(when=NOW + 900)[0], 1)
                self.assertEqual(len(self.calls), 1)

    def test_tick_waits_for_existing_file_lock(self):
        started = threading.Event()

        def waiting_tick():
            started.set()
            return self.invoke()

        with (self.root / "watch.lock").open("a") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(waiting_tick)
                try:
                    self.assertTrue(started.wait(timeout=1))
                    with self.assertRaises(TimeoutError):
                        future.result(timeout=0.05)
                    self.assertEqual(self.calls, [])
                finally:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
                self.assertEqual(future.result(timeout=2)[0], 0)
        self.assertEqual(len(self.calls), 1)


if __name__ == "__main__":
    unittest.main()
