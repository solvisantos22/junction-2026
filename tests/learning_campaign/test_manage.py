"""Fake SDK supervisor checks; no authentication, simulator, or cloud work."""

import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from tools.learning_campaign import manage as manager
from test_decide import add_validation, advance, make_run, write


NOW = 1794679400.
DEADLINE = 1794713400.


class FakeVolume:
    def __init__(self, paths):
        self.paths, self.reads = paths, []
        self.corrupt = None

    def iterdir(self, path, recursive=False):
        assert recursive is False
        directory = next(p for p in self.paths if p.name == path)
        for file in directory.iterdir():
            yield SimpleNamespace(path=f"{path}/{file.name}")
        for suffix in ("checkpoint-latest.json.gz", "train.stdout.txt", ".env", "batches/batch-00000.json.gz", "../escape"):
            yield SimpleNamespace(path=f"{path}/{suffix}")

    def read_file(self, path):
        self.reads.append(path)
        if self.corrupt == path:
            yield b"\xffinterrupted report"
            return
        run, name = path.split("/")
        directory = next(p for p in self.paths if p.name == run)
        yield (directory / name).read_bytes()


class FakeLauncher:
    ABSOLUTE_DEADLINE = DEADLINE
    VOLUME_NAME = "fake-volume"
    TERMINAL = {"completed", "training_incomplete", "training_error", "stopped_deadline", "wrapper_error"}

    def __init__(self, freeze, freeze_path, paths):
        self.freeze, self.freeze_path, self.paths = freeze, freeze_path, paths
        self.pending, self.launches, self.polls = set(), [], []
        self.fail_launch = None
        self.error_status = False
        self.sdk = SimpleNamespace(Volume=SimpleNamespace(from_name=self.volume))
        self.fake_volume = FakeVolume(paths)

    def volume(self, name):
        assert name == self.VOLUME_NAME
        return self.fake_volume

    def modal_sdk(self):
        return self.sdk

    def receipt(self, stage, algorithms):
        declared = next(s for s in self.freeze["campaign"]["stages"] if s["name"] == stage)
        jobs = [j for j in declared["jobs"] if j["algorithm"] in algorithms]
        return {"schema": "learning-campaign-receipt-v1", "status": "submitted", "stage": stage,
                "campaign_id": self.freeze["campaign"]["campaign_id"],
                "freeze_sha256": manager.decision.digest(self.freeze_path), "app_id": f"ap-{stage}",
                "jobs": [{**j, "call_id": f"fc-{stage}-{j['run_id']}"} for j in jobs],
                "reservation": {"jobs": jobs, "deadline_unix": DEADLINE}}

    def status(self, receipt_path, sdk):
        receipt = manager.decision.read(receipt_path)
        self.polls.append(receipt["stage"])
        jobs = []
        for job in receipt["jobs"]:
            result = {"run_id": job["run_id"], "state": {}}
            if self.error_status:
                result["error_type"] = "FakeRemoteError"
            elif receipt["stage"] in self.pending:
                result["pending"] = True
            else:
                result["result"] = {"status": "completed"}
            jobs.append(result)
        return {"campaign_id": receipt["campaign_id"], "stage": receipt["stage"], "jobs": jobs,
                "app_id": receipt["app_id"], "stop_marker": False}

    def prepare(self, freeze_path, stage, root, algorithms, now):
        assert freeze_path == self.freeze_path.resolve()
        assert now < DEADLINE
        return {"stage": stage, "algorithms": algorithms, "root": root}

    def launch(self, plan, receipt_path, root, sdk, now):
        assert root == plan["root"]
        self.launches.append(plan)
        if self.fail_launch == "before_receipt":
            raise KeyboardInterrupt
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        write(receipt_path, self.receipt(plan["stage"], plan["algorithms"]))
        if self.fail_launch == "after_receipt":
            self.pending.add(plan["stage"])
            raise KeyboardInterrupt
        for path in self.paths:
            if path.name.split("-")[0] not in plan["algorithms"]:
                continue
            if plan["stage"] == "expanded":
                advance(path)
            else:
                report = manager.decision.read(path / "report.json")
                report["episodes_target"] = report["episodes_completed"] = 32768
                report["history"] = [{"first_episode": i * 32, "last_episode": (i + 1) * 32,
                                      "count": 32, "sha256": "c" * 64} for i in range(1024)]
                write(path / "report.json", report)
                add_validation(path, 32768, .1875)
        return manager.decision.read(receipt_path)


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        sources = self.root / "remote"
        sources.mkdir()
        self.paths = [make_run(sources, algorithm, seed) for algorithm in ("ppo", "replay") for seed in (17, 29, 43)]
        pins = manager.decision.read(self.paths[0] / "report.json")["source_sha256"]
        self.freeze = {"schema": "learning-campaign-freeze-v1", "source_sha256": pins, "uploaded_sha256": pins,
                       "campaign": {"campaign_id": "synthetic-test", "deadline_unix": DEADLINE,
                                    "stages": [{"name": name, "jobs": [{"algorithm": a, "seed": s,
                                                                      "run_id": f"{a}-{s}", "episodes": count}
                                                                     for a in ("ppo", "replay") for s in (17, 29, 43)]}
                                               for name, count in zip(manager.STAGES, manager.TARGETS)]}}
        self.freeze_path, self.pilot = self.root / "freeze.json", self.root / "pilot.json"
        write(self.freeze_path, self.freeze)
        self.launcher = FakeLauncher(self.freeze, self.freeze_path, self.paths)
        write(self.pilot, self.launcher.receipt("pilot", {"ppo", "replay"}))
        self.output = self.root / "monitor"

    def run_manager(self, follow=False, clock=lambda: NOW):
        return manager.manage(self.freeze_path, self.pilot, self.output, self.root,
                              follow, launcher=self.launcher, sdk=self.launcher.sdk, clock=clock,
                              sleeper=lambda seconds: None)

    def test_default_poll_never_launches_or_downloads_running_files(self):
        self.launcher.pending.add("pilot")
        state = self.run_manager()
        self.assertEqual(state["status"], "monitoring")
        self.assertEqual(self.launcher.fake_volume.reads, [])
        self.assertEqual(self.launcher.launches, [])

    def test_default_completed_poll_downloads_allowlist_and_decides_without_launch(self):
        state = self.run_manager()
        self.assertEqual(state["status"], "ready_for_continuation")
        self.assertEqual(self.launcher.launches, [])
        self.assertTrue(self.launcher.fake_volume.reads)
        self.assertTrue(all(manager.ALLOWED.fullmatch(name.split("/")[1]) for name in self.launcher.fake_volume.reads))
        self.assertFalse(any("checkpoint" in name or ".env" in name or "stdout" in name for name in self.launcher.fake_volume.reads))
        count = len(self.launcher.fake_volume.reads)
        self.run_manager()
        self.assertEqual(len(self.launcher.fake_volume.reads), count)

    def test_follow_runs_only_two_fixed_continuations_then_stops_before_final_check(self):
        state = self.run_manager(follow=True)
        self.assertEqual(state["status"], "ready_for_final_evaluation")
        self.assertEqual(state["stage"], "extended")
        self.assertEqual([x["stage"] for x in self.launcher.launches], ["expanded", "extended"])
        self.assertTrue(all(x["algorithms"] == ["ppo", "replay"] for x in self.launcher.launches))
        self.assertTrue((self.output / "pilot/runs/ppo-17/report.json").exists())
        self.assertEqual(manager.decision.read(self.output / "pilot/runs/ppo-17/report.json")["episodes_target"], 2048)
        self.run_manager(follow=True)
        self.assertEqual(len(self.launcher.launches), 2)

    def test_terminal_download_error_is_retained_and_never_retried(self):
        self.launcher.fake_volume.corrupt = "ppo-17/report.json"
        with self.assertRaises(UnicodeDecodeError):
            self.run_manager(follow=True)
        state = manager.decision.read(self.output / "state.json")
        self.assertEqual(state["status"], "error")
        self.assertEqual(state["error"]["operation"], "download_terminal_artifacts")
        count = len(self.launcher.fake_volume.reads)
        self.run_manager(follow=True)
        self.assertEqual(len(self.launcher.fake_volume.reads), count)
        self.assertEqual(self.launcher.launches, [])
        self.assertTrue((self.output / "pilot/runs/ppo-17/report.json.partial").exists())

    def test_interrupted_submitted_receipt_recovers_without_second_launch(self):
        self.launcher.fail_launch = "after_receipt"
        with self.assertRaises(KeyboardInterrupt):
            self.run_manager(follow=True)
        state = manager.decision.read(self.output / "state.json")
        self.assertEqual(state["launch_intent"]["stage"], "expanded")
        resumed = self.run_manager()
        self.assertEqual(resumed["stage"], "expanded")
        self.assertIsNone(resumed["launch_intent"])
        self.assertEqual(len(self.launcher.launches), 1)

    def test_ambiguous_interruption_stops_instead_of_relaunching(self):
        self.launcher.fail_launch = "before_receipt"
        with self.assertRaises(KeyboardInterrupt):
            self.run_manager(follow=True)
        with self.assertRaisesRegex(ValueError, "manual reconciliation"):
            self.run_manager(follow=True)
        self.assertEqual(len(self.launcher.launches), 1)
        self.assertEqual(manager.decision.read(self.output / "state.json")["status"], "error")

    def test_remote_errors_and_absolute_deadline_prevent_launch(self):
        self.launcher.error_status = True
        with self.assertRaisesRegex(ValueError, "remote function"):
            self.run_manager(follow=True)
        self.assertEqual(self.launcher.launches, [])
        self.output = self.root / "deadline-monitor"
        self.launcher.error_status = False
        self.launcher.pending.add("pilot")
        state = self.run_manager(follow=True, clock=lambda: DEADLINE)
        self.assertEqual(state["status"], "campaign_deadline")
        self.assertEqual(self.launcher.launches, [])


if __name__ == "__main__":
    unittest.main()
