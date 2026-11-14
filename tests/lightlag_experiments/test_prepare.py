"""Exercise the generated task as a standalone artifact, without Docker."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
PREPARE = REPO / "tools/lightlag_experiments/prepare.py"


class Preparation(unittest.TestCase):
    def prepare(self, destination, *args, success=True):
        self.assertTrue(PREPARE.is_file(), "the experiment task generator is missing")
        run = subprocess.run(
            [sys.executable, str(PREPARE), str(destination), *args],
            cwd=REPO, capture_output=True, text=True,
        )
        if success:
            self.assertEqual(run.returncode, 0, run.stderr)
        else:
            self.assertNotEqual(run.returncode, 0, run.stdout)
        return run

    def test_task_runs_from_its_own_copies_and_solution_needs_no_simulator(self):
        with tempfile.TemporaryDirectory() as directory:
            task = Path(directory) / "task"
            self.prepare(task, "--profile", "rush_noisy", "--seed", "501", "--delay", "5")
            simulator = task / "environment/simulator"
            env = dict(os.environ, PYTHONPATH="", PYTHONDONTWRITEBYTECODE="1")
            compose = (task / "environment/docker-compose.yaml").read_text()
            for line in compose.splitlines():
                key, separator, value = line.strip().partition(": ")
                if separator and key in {"LIGHTLAG_SEED", "LIGHTLAG_DELAY", "LIGHTLAG_PROFILE", "LIGHTLAG_TICKS"}:
                    env[key] = json.loads(value)
            probe = subprocess.run(
                [sys.executable, "-c", "import json,os; from lightlag import Config; "
                 "from lightlag_dynamic.serve import DynamicEpisodeService; "
                 "s=DynamicEpisodeService(seed=int(os.environ['LIGHTLAG_SEED']),profile=os.environ['LIGHTLAG_PROFILE'],"
                 "config=Config(delay_ticks=int(os.environ['LIGHTLAG_DELAY']),max_ticks=int(os.environ['LIGHTLAG_TICKS']))); "
                 "print(json.dumps(s.rules()))"],
                cwd=simulator, env=env, capture_output=True, text=True,
            )
            self.assertEqual(probe.returncode, 0, probe.stderr)
            rules = json.loads(probe.stdout)
            self.assertEqual((rules["mission_profile"], rules["max_ticks"], rules["delay_ticks"]),
                             ("rush_noisy", 50, 5))
            self.assertIsNotNone(rules["sensing"])
            probe = subprocess.run(
                [sys.executable, "-c", "from lightlag_dynamic.controllers import POLICIES; "
                 "assert all(callable(POLICIES[p]) for p in ['kf_mpc','open_loop','leg_and_wait'])"],
                cwd=task / "solution", env=env, capture_output=True, text=True,
            )
            self.assertEqual(probe.returncode, 0, probe.stderr)
            self.assertFalse((task / "solution/lightlag").exists())
            self.assertFalse((task / "solution/lightlag_dynamic/environment.py").exists())
            self.assertFalse((task / "solution/lightlag_dynamic/missions.py").exists())
            self.assertEqual((task / "environment/Dockerfile").read_bytes(),
                             (REPO / "harbor/lightlag/environment/Dockerfile").read_bytes())
            for name in ["task.toml", "tests/grade.py", "tests/test.sh"]:
                if name != "task.toml":
                    self.assertEqual((task / name).read_bytes(), (REPO / "harbor/lightlag" / name).read_bytes())
            self.assertIn('LIGHTLAG_SEED: "501"', compose)
            self.assertIn('LIGHTLAG_PROFILE: "rush_noisy"', compose)
            self.assertTrue(os.access(task / "solution/solve.sh", os.X_OK))

    def test_manifest_covers_exact_task_bytes_and_build_is_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            first, second = (Path(directory) / name for name in ["a", "b"])
            for task in [first, second]:
                self.prepare(task, "--policy", "leg_and_wait")
            self.assertEqual((first / "experiment.json").read_bytes(),
                             (second / "experiment.json").read_bytes())
            manifest = json.loads((first / "experiment.json").read_text())
            self.assertEqual(manifest["settings"], {"profile": "rush", "seed": 500, "delay": 3, "horizon": 50,
                                                   "noise_level": 1.0, "bumpiness": 0.0,
                                                   "policy": "leg_and_wait"})
            actual = {str(p.relative_to(first)): hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in first.rglob("*") if p.is_file() and p.name != "experiment.json"}
            self.assertEqual(manifest["task_sha256"], actual)
            for name, digest in manifest["source_sha256"].items():
                self.assertFalse(Path(name).is_absolute())
                self.assertEqual(hashlib.sha256((REPO / name).read_bytes()).hexdigest(), digest)
            self.assertNotIn(str(REPO), (first / "experiment.json").read_text())
            self.assertFalse(any(p.name.startswith(".env") for p in first.rglob("*")))

    def test_existing_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            task = Path(directory) / "task"
            task.mkdir()
            marker = task / "keep.txt"
            marker.write_text("keep this evidence")
            self.prepare(task, success=False)
            self.assertEqual(marker.read_text(), "keep this evidence")
            self.assertEqual(list(task.iterdir()), [marker])

    def test_invalid_parameters_do_not_create_a_task(self):
        with tempfile.TemporaryDirectory() as directory:
            task = Path(directory) / "task"
            for args in [("--profile", "unknown"), ("--delay", "-1"), ("--seed", "-1")]:
                self.prepare(task, *args, success=False)
                self.assertFalse(task.exists())


if __name__ == "__main__":
    unittest.main()
