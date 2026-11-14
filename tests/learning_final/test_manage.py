"""Fake SDK supervisor checks; no authentication, simulator, or cloud work."""

import copy
import gzip
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.learning_final import manage as manager

read, digest, MAPS = manager.decision.read, manager.decision.digest, manager.decision.MAPS


def write(path, value):
    raw = json.dumps(value, sort_keys=True).encode()
    path.write_bytes(gzip.compress(raw, mtime=0) if path.suffix == ".gz" else raw)


def add_validation(path, count, reward):
    report = read(path / "report.json")
    policy = {"schema": "lightlag-learning-policy-v1", "algorithm": report["algorithm"],
              "episodes_seen": count, "model": {"candidate_dim": 20, "global_dim": 14, "hidden": 64},
              "config": {"gamma": 1., "schedule_episodes": 2048}}
    policy_path = path / f"policy-{count:05d}.json"
    write(policy_path, policy)
    episodes = [{"seed": world, "action_seed": report["seed"] * 1_000_000_000 + index,
                 "reward": reward, "result": {"tick": 420, "alive": True, "at_base": index < 20,
                                               "max_available_value": 64., "raw_score": reward * 64},
                 "invalid_calls": [], "decision_count": 4} for index, world in enumerate(MAPS)]
    summary = {"count": 32, "mean_reward": reward, "home": 20, "alive": 32,
               "invalid_calls": 0, "mean_decisions": 4.}
    write(path / f"validation-{count:05d}.json.gz",
          {"schema": "learning-validation-v1", "episodes_completed": count, "maps": MAPS,
           "policy_sha256": digest(policy_path), "episodes": episodes, "summary": summary})
    report["validations"][str(count)] = summary
    write(path / "report.json", report)


def make_run(parent, algorithm, seed, final=.15625):
    path = parent / f"{algorithm}-{seed}"
    path.mkdir()
    report = {"schema": "learning-training-report-v1", "algorithm": algorithm, "seed": seed,
              "smoke": False, "status": "complete", "experiment": "learning-final-20261114", "episodes_target": 8192, "episodes_completed": 8192,
              "batch_episodes": 32, "schedule_episodes": 2048,
              "source_sha256": {"docs/learning-final.md": "a" * 64, "lightlag_learning_final/train.py": "b" * 64},
              "python": "3.12.16", "numpy": "2.3.4", "torch": "2.9.1", "validations": {},
              "history": [{"first_episode": i * 32, "last_episode": (i + 1) * 32,
                           "count": 32, "sha256": "c" * 64} for i in range(256)]}
    write(path / "report.json", report)
    for count, reward in ((0, .0625), (512, .09375), (2048, .125), (8192, final)):
        add_validation(path, count, reward)
    return path


def advance(path):
    report = read(path / "report.json")
    report["episodes_target"] = report["episodes_completed"] = 32768
    report["history"] = [{"first_episode": i * 32, "last_episode": (i + 1) * 32,
                          "count": 32, "sha256": "c" * 64} for i in range(1024)]
    write(path / "report.json", report)
    for count, reward in ((16384, .171875), (24576, .1796875), (32768, .1875)):
        add_validation(path, count, reward)



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
        return {"schema": "learning-final-receipt-v1", "status": "submitted", "stage": stage,
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
            advance(path)
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
        self.freeze = {"schema": "learning-final-freeze-v1", "source_sha256": pins, "uploaded_sha256": pins,
                       "campaign": {"campaign_id": "synthetic-test", "deadline_unix": DEADLINE,
                                    "stages": [{"name": name, "jobs": [{"algorithm": a, "seed": s,
                                                                      "run_id": f"{a}-{s}", "episodes": count}
                                                                     for a in ("ppo", "replay") for s in (17, 29, 43)]}
                                               for name, count in zip(manager.STAGES, manager.TARGETS)]}}
        self.freeze_path, self.fit = self.root / "freeze.json", self.root / "fit.json"
        write(self.freeze_path, self.freeze)
        self.launcher = FakeLauncher(self.freeze, self.freeze_path, self.paths)
        write(self.fit, self.launcher.receipt("fit", {"ppo", "replay"}))
        self.output = self.root / "monitor"

    def run_manager(self, follow=False, clock=lambda: NOW):
        return manager.manage(self.freeze_path, self.fit, self.output, self.root,
                              follow, launcher=self.launcher, sdk=self.launcher.sdk, clock=clock,
                              sleeper=lambda seconds: None)

    def test_default_poll_never_launches_or_downloads_running_files(self):
        self.launcher.pending.add("fit")
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

    def test_follow_runs_one_fixed_continuation_then_stops_before_final_check(self):
        state = self.run_manager(follow=True)
        self.assertEqual(state["status"], "ready_for_final_evaluation")
        self.assertEqual(state["stage"], "extend")
        self.assertEqual([x["stage"] for x in self.launcher.launches], ["extend"])
        self.assertTrue(all(x["algorithms"] == ["ppo", "replay"] for x in self.launcher.launches))
        self.assertTrue((self.output / "fit/runs/ppo-17/report.json").exists())
        self.assertEqual(manager.decision.read(self.output / "fit/runs/ppo-17/report.json")["episodes_target"], 8192)
        self.run_manager(follow=True)
        self.assertEqual(len(self.launcher.launches), 1)
        for count in (16384, 24576, 32768):
            self.assertTrue((self.output / f"extend/runs/ppo-17/policy-{count:05d}.json").exists())

    def test_only_eligible_whole_algorithm_continues(self):
        for path in self.paths:
            if path.name.startswith("replay-"):
                add_validation(path, 8192, .125)
        state = self.run_manager(follow=True)
        self.assertEqual(state["status"], "ready_for_final_evaluation")
        self.assertEqual([x["algorithms"] for x in self.launcher.launches], [["ppo"]])
        receipt = read(self.output / "extend/receipt.json")
        self.assertEqual([job["seed"] for job in receipt["jobs"]], [17, 29, 43])

    def test_no_eligible_algorithm_stops_before_continuation(self):
        for path in self.paths:
            add_validation(path, 8192, .125)
        state = self.run_manager(follow=True)
        self.assertEqual((state["status"], state["stage"]), ("ready_for_final_evaluation", "fit"))
        self.assertEqual(state["reason"], "no_qualified_continuation")
        self.assertEqual(self.launcher.launches, [])

    def test_initial_pause_prevents_authentication_poll_and_launch_and_is_durable(self):
        self.output.mkdir()
        marker = self.output / "pause.json"
        write(marker, {"reason": "user paused"})
        with patch.object(self.launcher, "modal_sdk") as authenticate:
            state = manager.manage(self.freeze_path, self.fit, self.output, self.root, True,
                                   launcher=self.launcher, clock=lambda: NOW)
            authenticate.assert_not_called()
        self.assertEqual(state["status"], "user_paused")
        marker.unlink()
        resumed = self.run_manager(follow=True)
        self.assertEqual(resumed["status"], "user_paused")
        self.assertEqual(self.launcher.polls, [])
        self.assertEqual(self.launcher.fake_volume.reads, [])
        self.assertEqual(self.launcher.launches, [])

    def test_retained_user_paused_state_stops_without_marker(self):
        self.launcher.pending.add("fit")
        state = self.run_manager()
        state["status"] = "user_paused"
        write(self.output / "state.json", state)
        polls = len(self.launcher.polls)
        self.assertEqual(self.run_manager(follow=True)["status"], "user_paused")
        self.assertEqual(len(self.launcher.polls), polls)
        self.assertEqual(self.launcher.launches, [])

    def test_pause_arriving_during_prepare_blocks_launch(self):
        original = self.launcher.prepare
        def prepare(*args, **kwargs):
            plan = original(*args, **kwargs)
            write(self.output / "pause.json", {"reason": "paused during preparation"})
            return plan
        with patch.object(self.launcher, "prepare", side_effect=prepare):
            state = self.run_manager(follow=True)
        self.assertEqual(state["status"], "user_paused")
        self.assertEqual(self.launcher.launches, [])
        self.assertEqual(self.run_manager(follow=True)["status"], "user_paused")

    def test_manager_and_decision_hashes_are_bound_on_resume(self):
        self.launcher.pending.add("fit")
        state = self.run_manager()
        for name, path in (("manager_sha256", manager.__file__),
                           ("decision_tool_sha256", manager.decision.__file__)):
            self.assertEqual(state["identity"][name], digest(path))
        state["identity"]["decision_tool_sha256"] = "0" * 64
        write(self.output / "state.json", state)
        with self.assertRaisesRegex(ValueError, "resume identity changed"):
            self.run_manager(follow=True)
        self.assertEqual(self.launcher.launches, [])

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
        self.assertTrue((self.output / "fit/runs/ppo-17/report.json.partial").exists())

    def test_interrupted_submitted_receipt_recovers_without_second_launch(self):
        self.launcher.fail_launch = "after_receipt"
        with self.assertRaises(KeyboardInterrupt):
            self.run_manager(follow=True)
        state = manager.decision.read(self.output / "state.json")
        self.assertEqual(state["launch_intent"]["stage"], "extend")
        resumed = self.run_manager()
        self.assertEqual(resumed["stage"], "extend")
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
        self.launcher.pending.add("fit")
        state = self.run_manager(follow=True, clock=lambda: DEADLINE)
        self.assertEqual(state["status"], "campaign_deadline")
        self.assertEqual(self.launcher.launches, [])


if __name__ == "__main__":
    unittest.main()
