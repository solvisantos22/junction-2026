from contextlib import nullcontext
import copy
import json
from pathlib import Path
import signal
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy  # Keep the real module loaded while fake SDK modules are patched.

from tools.learning_campaign import modal_job as launcher


NOW = launcher.ABSOLUTE_DEADLINE - 9 * 3600


def campaign():
    return {"campaign_id": "test-campaign", "deadline_unix": launcher.ABSOLUTE_DEADLINE,
            "stages": [{"name": name, "max_seconds": seconds,
                        "jobs": [{"run_id": f"{algorithm}-{seed}", "algorithm": algorithm,
                                  "seed": seed, "episodes": episodes}
                                 for algorithm in ("ppo", "replay") for seed in (17, 29, 43)]}
                       for name, seconds, episodes in (("pilot", 5400, 2048), ("expanded", 10800, 8192),
                                                       ("extended", 10800, 32768))]}


class FakeControl:
    def __init__(self):
        self.data = {}

    def put(self, key, value, *, skip_if_exists=False):
        if skip_if_exists and key in self.data:
            return False
        self.data[key] = copy.deepcopy(value)
        return True

    def get(self, key, default=None):
        return copy.deepcopy(self.data.get(key, default))


class FakeVolume:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1


class FakeSDK:
    """Records Modal construction and submissions; never authenticates or launches."""
    def __init__(self, receipt):
        self.receipt = Path(receipt)
        self.control, self.volume = FakeControl(), FakeVolume()
        self.app_count, self.spawned, self.installs = 0, [], []
        self.options = None
        self.Dict = SimpleNamespace(from_name=lambda *a, **kw: self.control)
        self.Volume = SimpleNamespace(from_name=self.volume_from_name)
        self.Image = SimpleNamespace(debian_slim=lambda **kw: self)
        self.FunctionCall = SimpleNamespace(from_id=lambda call_id: SimpleNamespace(get=lambda **kw: {}))

    def volume_from_name(self, name, **kwargs):
        assert name == launcher.VOLUME_NAME and kwargs == {"create_if_missing": True, "version": 2}
        return self.volume

    def pip_install(self, *args, **kwargs):
        self.installs.append((args, kwargs))
        return self

    def add_local_dir(self, path, **kwargs):
        self.uploads = sorted(str(p.relative_to(path)) for p in Path(path).rglob("*") if p.is_file())
        assert kwargs == {"remote_path": "/app", "copy": True}
        return self

    def App(self, name):
        self.app_count += 1
        assert name == launcher.APP_NAME
        return SimpleNamespace(app_id="ap-test", function=self.function, run=self.app_run)

    def function(self, **kwargs):
        self.options = kwargs
        return lambda function: SimpleNamespace(spawn=self.spawn)

    def app_run(self, **kwargs):
        assert kwargs == {"detach": True}
        return nullcontext()

    def enable_output(self):
        return nullcontext()

    def spawn(self, plan, job):
        receipt = json.loads(self.receipt.read_text())
        assert receipt["status"] == "launching" and len(receipt["jobs"]) == len(self.spawned)
        self.spawned.append((plan, job))
        return SimpleNamespace(object_id=f"fc-{len(self.spawned)}")


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="campaign-launcher-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for package in launcher.PACKAGES:
            directory = self.root / package
            directory.mkdir()
            (directory / "__init__.py").write_text('"""Synthetic source fixture."""\n')
        (self.root / "lightlag_learning/train.py").write_text('"""No training runs in these tests."""\n')
        for name in (*launcher.LAUNCHER_FILES, launcher.PROTOCOL):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("test fixture\n")
        (self.root / ".env").write_text("PRIVATE_TEST_VALUE=do-not-upload\n")
        (self.root / "docs/private.md").write_text("private fixture\n")
        self.freeze_path = self.root / "freeze.json"
        with patch.object(launcher.subprocess, "check_output", return_value="fake-commit\n"):
            self.freeze = launcher.write_freeze(self.freeze_path, campaign(), root=self.root, now=NOW)
        self.plan = launcher.prepare(self.freeze_path, "pilot", root=self.root, now=NOW)

    def test_offline_freeze_pins_only_allowlisted_source_and_has_bounded_budget(self):
        destination = self.root / "snapshot"
        launcher.copy_sources(self.plan, destination, self.root)
        uploaded = {str(p.relative_to(destination)) for p in destination.rglob("*") if p.is_file()}
        self.assertEqual(uploaded, set(self.freeze["uploaded_sha256"]))
        self.assertNotIn(".env", uploaded)
        self.assertNotIn("docs/private.md", uploaded)
        self.assertTrue(all(n.endswith(".py") or n == launcher.PROTOCOL for n in uploaded))
        self.assertAlmostEqual(self.freeze["running_compute_envelope_usd"], 22.73184)
        self.assertLess(self.freeze["running_compute_envelope_usd"], 31)
        self.assertEqual(self.freeze["runtime"]["torch"], "2.9.1")

    def test_unapproved_deadline_new_id_or_oversized_target_is_rejected(self):
        for edit in (lambda c: c.update(deadline_unix=launcher.ABSOLUTE_DEADLINE + 1),
                     lambda c: c["stages"][0].update(max_seconds=5401),
                     lambda c: c["stages"][1]["jobs"][0].update(run_id="new-run"),
                     lambda c: c["stages"][2]["jobs"][0].update(episodes=32769)):
            value = campaign()
            edit(value)
            with self.assertRaises(ValueError):
                launcher.validate_campaign(value, NOW)

    def test_drift_and_symlink_rejected_before_modal_construction(self):
        (self.root / "lightlag_learning/train.py").write_text("changed\n")
        with self.assertRaisesRegex(ValueError, "source changed"):
            launcher.prepare(self.freeze_path, "pilot", root=self.root, now=NOW)
        path = self.root / "lightlag_learning/unsafe.py"
        path.symlink_to(self.root / ".env")
        with self.assertRaisesRegex(ValueError, "escaping"):
            launcher.source_manifest(self.root)

    def test_fake_launch_detaches_and_records_receipts_before_each_submission(self):
        receipt_path = self.root / "receipt.json"
        sdk = FakeSDK(receipt_path)
        with patch.object(launcher.time, "time", return_value=NOW):
            receipt = launcher.launch(self.plan, receipt_path, root=self.root, sdk=sdk, now=NOW)
        self.assertEqual(receipt["status"], "submitted")
        self.assertEqual(len(receipt["jobs"]), 6)
        self.assertEqual(sdk.options["cpu"], (16, 16))
        self.assertEqual(sdk.options["memory"], (32768, 32768))
        self.assertEqual(sdk.options["max_containers"], 3)
        self.assertEqual(sdk.options["retries"], 0)
        self.assertTrue(sdk.options["single_use_containers"])
        self.assertFalse(sdk.options["include_source"])
        self.assertNotIn("secrets", sdk.options)
        self.assertEqual(receipt["reservation"]["deadline_unix"], NOW + 5400)
        self.assertIn((("torch==2.9.1",), {"index_url": launcher.RUNTIME["torch_index"]}), sdk.installs)
        sdk.receipt = self.root / "duplicate-receipt.json"
        with self.assertRaisesRegex(ValueError, "stage already reserved"):
            launcher.launch(self.plan, sdk.receipt, root=self.root, sdk=sdk, now=NOW)
        self.assertEqual(sdk.app_count, 1)
        self.assertEqual(json.loads(sdk.receipt.read_text())["status"], "launch_error")

    def test_continuation_requires_terminal_previous_calls_and_irrevocable_subset(self):
        control = FakeControl()
        launcher.reserve_stage(control, self.plan, NOW)
        expanded = launcher.prepare(self.freeze_path, "expanded", root=self.root, now=NOW, algorithms=["ppo"])
        with self.assertRaisesRegex(ValueError, "not terminal"):
            launcher.reserve_stage(control, expanded, NOW)
        for job in self.plan["selected_jobs"]:
            control.put("job:pilot:" + job["run_id"], {"status": "completed", "call_id": "fc-old"})
        reservation = launcher.reserve_stage(control, expanded, NOW + 600)
        self.assertEqual({j["algorithm"] for j in reservation["jobs"]}, {"ppo"})
        self.assertEqual(len(reservation["jobs"]), 3)
        replay = launcher.prepare(self.freeze_path, "expanded", root=self.root, now=NOW, algorithms=["replay"])
        with self.assertRaisesRegex(ValueError, "already reserved"):
            launcher.reserve_stage(control, replay, NOW + 600)
        for job in expanded["selected_jobs"]:
            control.put("job:expanded:" + job["run_id"], {"status": "completed", "call_id": "fc-old"})
        extended = launcher.prepare(self.freeze_path, "extended", root=self.root, now=NOW)
        with self.assertRaisesRegex(ValueError, "reintroduce"):
            launcher.reserve_stage(control, extended, NOW + 700)
        with self.assertRaisesRegex(ValueError, "pilot must run"):
            launcher.prepare(self.freeze_path, "pilot", root=self.root, now=NOW, algorithms=["ppo"])

    def test_stop_marker_blocks_new_stages_and_expired_campaign_cannot_prepare(self):
        control = FakeControl()
        launcher.reserve_stage(control, self.plan, NOW)
        control.put("stop", {"requested_unix": NOW})
        with self.assertRaisesRegex(ValueError, "stop marker"):
            launcher.reserve_stage(control, self.plan, NOW)
        with self.assertRaisesRegex(ValueError, "expired"):
            launcher.prepare(self.freeze_path, "pilot", root=self.root, now=launcher.ABSOLUTE_DEADLINE)

    def test_new_campaign_id_cannot_multiply_apps_using_same_cloud_control(self):
        control = FakeControl()
        launcher.reserve_stage(control, self.plan, NOW)
        changed = copy.deepcopy(self.plan)
        changed["freeze"]["campaign"]["campaign_id"] = "another-campaign"
        with self.assertRaisesRegex(ValueError, "different frozen campaign"):
            launcher.reserve_stage(control, changed, NOW)

    def remote_fixture(self):
        control, volume = FakeControl(), FakeVolume()
        launcher.reserve_stage(control, self.plan, NOW)
        plan = {**self.plan, "app_id": "ap-test"}
        root = self.root / "snapshot"
        launcher.copy_sources(plan, root, self.root)
        results = self.root / "results"
        job = plan["selected_jobs"][0]
        fake_torch = SimpleNamespace(__version__="2.9.1+cpu", version=SimpleNamespace(cuda=None))
        fake_modal = SimpleNamespace(current_function_call_id=lambda: "fc-test")
        return control, volume, plan, root, results, job, {"modal": fake_modal, "torch": fake_torch}

    def test_remote_completion_requires_matching_report_and_strips_child_credentials(self):
        control, volume, plan, root, results, job, modules = self.remote_fixture()
        output = results / job["run_id"]
        output.mkdir(parents=True)
        report = {"schema": "learning-training-report-v1", "status": "complete",
                  "algorithm": job["algorithm"], "seed": job["seed"],
                  "episodes_target": job["episodes"], "episodes_completed": job["episodes"]}
        (output / "report.json").write_text(json.dumps(report))
        process = SimpleNamespace(poll=lambda: 0, returncode=0, pid=99999999)
        with patch.dict("sys.modules", modules), patch("time.time", return_value=NOW), \
                patch.dict("os.environ", {"ANTHROPIC_API_KEY": "synthetic-private", "MODAL_TOKEN_SECRET": "synthetic-private"}), \
                patch("subprocess.Popen", return_value=process) as popen:
            result = launcher.make_remote_runner(volume, control)(plan, job, str(root), str(results))
        self.assertEqual(result["status"], "completed")
        args, kwargs = popen.call_args
        self.assertIn(str(NOW + 5400), args[0])
        self.assertNotIn("ANTHROPIC_API_KEY", kwargs["env"])
        self.assertNotIn("MODAL_TOKEN_SECRET", kwargs["env"])
        self.assertEqual(kwargs["env"]["OMP_NUM_THREADS"], "1")
        self.assertGreaterEqual(volume.commits, 2)
        metadata = next((results / "_campaign").rglob("*.json"))
        self.assertEqual(json.loads(metadata.read_text())["trainer_report"], report)
        # A crash/replay of an already completed call returns its terminal state.
        with patch.dict("sys.modules", modules), patch("subprocess.Popen") as popen:
            second = launcher.make_remote_runner(volume, control)(plan, job, str(root), str(results))
            popen.assert_not_called()
        self.assertEqual(second["status"], "completed")

    def test_remote_expired_stage_retains_stop_record_without_starting_trainer(self):
        control, volume, plan, root, results, job, modules = self.remote_fixture()
        with patch.dict("sys.modules", modules), patch("time.time", return_value=NOW + 5401), \
                patch("subprocess.Popen") as popen:
            result = launcher.make_remote_runner(volume, control)(plan, job, str(root), str(results))
        popen.assert_not_called()
        self.assertEqual(result["status"], "stopped_deadline")
        self.assertFalse((results / job["run_id"]).exists())
        self.assertTrue(list((results / "_campaign").rglob("attempt-*.json")))

    def test_running_child_is_terminated_at_stage_deadline(self):
        control, volume, plan, root, results, job, modules = self.remote_fixture()
        clock = {"now": NOW + 5399}

        class Process:
            pid, returncode = 99999999, None

            def poll(self):
                return self.returncode

            def wait(self, timeout):
                if self.returncode is not None:
                    return self.returncode
                clock["now"] = NOW + 5401
                raise subprocess.TimeoutExpired("fake-child", timeout)

        process, signals = Process(), []

        def killpg(pid, signum):
            self.assertEqual(pid, process.pid)
            signals.append(signum)
            process.returncode = -signum

        with patch.dict("sys.modules", modules), patch("time.time", side_effect=lambda: clock["now"]), \
                patch("subprocess.Popen", return_value=process), patch("os.killpg", side_effect=killpg):
            result = launcher.make_remote_runner(volume, control)(plan, job, str(root), str(results))
        self.assertEqual(result["status"], "stopped_deadline")
        self.assertIn(signal.SIGTERM, signals)


if __name__ == "__main__":
    unittest.main()
