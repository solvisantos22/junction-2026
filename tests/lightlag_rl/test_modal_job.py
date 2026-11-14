"""Cloud-free boundary tests for the explicitly launched Modal training job."""

import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from tools.lightlag_rl import modal_job as job


class Volume:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1


class ModalJobTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="lightlag-modal-test-")
        self.root = Path(self.temporary.name) / "repo"
        for package in job.PACKAGES:
            directory = self.root / package
            directory.mkdir(parents=True)
            (directory / "__init__.py").write_text("")
        for name in job.LAUNCHER_FILES:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("# pinned launcher fixture\n")
        (self.root / "lightlag_rl/train.py").write_text('''import argparse,json,os
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--output')
for n in ('updates','batch-size','workers','train-seed','max-seconds'):p.add_argument('--'+n,type=int)
a=p.parse_args();d=Path(a.output);d.mkdir()
(d/'fixture-result.json').write_text(json.dumps(vars(a)))
print('credential_present',bool(os.environ.get('MODAL_TOKEN_SECRET')))
''')
        (self.root / "lightlag_rl/.env").write_text("PRIVATE_FIXTURE")
        (self.root / "docs").mkdir()
        (self.root / "docs/private.txt").write_text("PRIVATE_FIXTURE")
        (self.root / job.PUBLIC_PROTOCOL).write_text("Public frozen training protocol fixture.\n")
        self.freeze = self.root / "freeze.json"
        with patch.object(job.subprocess, "check_output", return_value="a" * 40 + "\n"):
            job.write_freeze(self.freeze, self.root)
        self.plan = job.prepare(self.freeze, "test-01", self.root)

    def tearDown(self):
        self.temporary.cleanup()

    def test_freeze_is_exclusive_and_requires_exact_configuration(self):
        with patch.object(job.subprocess, "check_output", return_value="a" * 40 + "\n"):
            with self.assertRaises(FileExistsError):
                job.write_freeze(self.freeze, self.root)
        for run_id in ("../secret", "", "a/b", "x" * 65):
            with self.assertRaises(ValueError):
                job.prepare(self.freeze, run_id, self.root)
        content = json.loads(self.freeze.read_text())
        content["training"]["updates"] = 17
        self.freeze.write_text(json.dumps(content))
        with self.assertRaises(ValueError):
            job.prepare(self.freeze, "test-02", self.root)

    def test_changed_or_extra_source_and_symlink_are_rejected(self):
        source = self.root / "lightlag_rl/train.py"
        source.write_text(source.read_text() + "# drift\n")
        with self.assertRaises(ValueError):
            job.prepare(self.freeze, "test-01", self.root)
        with self.assertRaises(ValueError):
            job.copy_sources(self.plan, Path(self.temporary.name) / "snapshot", self.root)
        source.unlink()
        source.symlink_to(self.root / "tools/lightlag_rl/modal_job.py")
        with self.assertRaises(ValueError):
            job.source_manifest(self.root)

    def test_snapshot_contains_only_allowlisted_python_files(self):
        target = Path(self.temporary.name) / "snapshot"
        copied = job.copy_sources(self.plan, target, self.root)
        self.assertEqual(set(copied), {name for name in self.plan["freeze"]["source_sha256"]
                                       if name.split("/", 1)[0] in job.PACKAGES or name == job.PUBLIC_PROTOCOL})
        self.assertFalse((target / "lightlag_rl/.env").exists())
        self.assertTrue((target / job.PUBLIC_PROTOCOL).is_file())
        self.assertFalse((target / "docs/private.txt").exists())
        self.assertFalse((target / "tools").exists())

    def test_default_cli_does_not_invoke_cloud(self):
        with patch.object(job, "prepare", return_value=self.plan), patch.object(job, "launch") as launch:
            with contextlib.redirect_stdout(io.StringIO()) as output:
                result = job.main(["--freeze", str(self.freeze)])
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(output.getvalue())["cloud_calls"], 0)
        launch.assert_not_called()
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                job.launch(self.plan, self.root)

    def test_mock_launch_pins_resources_volume_and_source_exposure(self):
        captured = {}
        volume = Volume()

        class Image:
            @classmethod
            def debian_slim(cls, **kwargs):
                captured["python"] = kwargs
                return cls()

            def pip_install(self, requirement):
                captured["requirement"] = requirement
                return self

            def add_local_dir(self, directory, **kwargs):
                captured["copy"] = kwargs
                captured["files"] = [str(p.relative_to(directory)) for p in Path(directory).rglob("*") if p.is_file()]
                return self

        class App:
            app_id = "ap-fixture"

            def __init__(self, name):
                captured["app"] = name

            def function(self, **kwargs):
                captured["resources"] = kwargs
                return lambda function: types.SimpleNamespace(remote=lambda payload: {"status": "returned"})

            def run(self):
                return contextlib.nullcontext()

        def from_name(name, **kwargs):
            captured["volume"] = {"name": name, **kwargs}
            return volume

        fake = types.SimpleNamespace(__version__="1.6.4", App=App, Image=Image,
                                     Volume=types.SimpleNamespace(from_name=from_name),
                                     enable_output=contextlib.nullcontext)
        with patch.dict(os.environ, {"MODAL_PROFILE": job.PROFILE}), patch.dict("sys.modules", {"modal": fake}):
            self.assertEqual(job.launch(self.plan, self.root)["status"], "returned")
        self.assertEqual(captured["volume"]["version"], 2)
        self.assertEqual(captured["resources"]["cpu"], (4, 4))
        self.assertEqual(captured["resources"]["memory"], (8192, 8192))
        self.assertEqual(captured["resources"]["max_containers"], 1)
        self.assertEqual(captured["resources"]["retries"], 0)
        self.assertFalse(captured["resources"]["include_source"])
        self.assertTrue(captured["resources"]["serialized"])
        self.assertNotIn("lightlag_rl/.env", captured["files"])

    def test_remote_fixture_records_result_commits_and_strips_credentials(self):
        volume = Volume()
        run = job.make_remote_runner(volume)
        results = Path(self.temporary.name) / "results"
        with patch.dict(os.environ, {"MODAL_TOKEN_SECRET": "fake-private-token"}):
            result = run(self.plan, str(self.root), str(results))
        self.assertEqual(result["status"], "returned")
        self.assertGreaterEqual(volume.commits, 2)
        output = results / "test-01"
        text = (output / "train.stdout.txt").read_text()
        self.assertIn("credential_present False", text)
        metadata = json.loads((output / "modal-job.json").read_text())
        self.assertTrue(metadata["source_snapshot_verified"])
        config = json.loads((output / "training/fixture-result.json").read_text())
        self.assertEqual(config["updates"], 16)
        self.assertEqual(config["max_seconds"], 3000)
        self.assertEqual(config["workers"], 4)
        with self.assertRaises(FileExistsError):
            run(self.plan, str(self.root), str(results))


if __name__ == "__main__":
    unittest.main()
