"""Generated simulator/reference/verifier isolation and complete provenance."""

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("expedition_prepare", ROOT / "tools/expedition_experiments/prepare.py")
prepare_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prepare_module)


class PrepareTests(unittest.TestCase):
    def test_separate_simulator_verifier_and_complete_manifest_hashes(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "task"
            manifest = prepare_module.prepare(output, mission_seed=19, seed=1100)
            for name, digest in manifest["source_sha256"].items():
                self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), digest)
            for name, digest in manifest["task_sha256"].items():
                self.assertEqual(hashlib.sha256((output / name).read_bytes()).hexdigest(), digest)
            actual = {p.relative_to(output).as_posix() for p in output.rglob("*") if p.is_file()}
            self.assertEqual(actual, set(manifest["task_sha256"]) | {"experiment.json"})
            self.assertEqual(manifest["settings"], dict(seed=1100, mission_seed=19, visibility="hidden", policy="reference", horizon=60, delay=3))
            task = (output / "task.toml").read_text()
            for declaration in ('environment_mode = "separate"', 'service = "expedition"', '--token-file /run/expedition/token', 'source = "/evaluator"', 'timeout_sec = 1800.0'):
                self.assertIn(declaration, task)
            compose = (output / "environment/docker-compose.yaml").read_text()
            main = compose.split("\n  expedition:")[0]
            for private in ("EXPEDITION_SEED", "EXPEDITION_MISSION_SEED", "/evaluator", "TOKEN_FILE"):
                self.assertNotIn(private, main)
            self.assertNotIn("volumes:", compose)
            self.assertNotIn("ports:", compose)
            self.assertEqual((output / "environment/Dockerfile").read_bytes(), (ROOT / "harbor/lightlag/environment/Dockerfile").read_bytes())
            self.assertNotIn("COPY", (output / "environment/Dockerfile").read_text())
            self.assertIn("mcp==2.3.0", (output / "environment/simulator/Dockerfile").read_text())
            self.assertEqual((output / "tests/grade.py").read_bytes(), (ROOT / "harbor/lightlag/tests/grade.py").read_bytes())
            self.assertIn("expedition-details.json", (output / "tests/test.sh").read_text())
            self.assertFalse((output / "environment/simulator/lightlag_expedition/reference.py").exists())
            self.assertEqual(json.loads((output / "experiment.json").read_text()), manifest)
            self.assertTrue((output / "solution/solve.sh").stat().st_mode & 0o111)

    def test_copied_packages_import_without_checkout_or_hidden_oracle_dependencies(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "task"
            prepare_module.prepare(output)
            oracle = output / "solution"
            for package in ("lightlag_expedition", "lightlag_dynamic"):
                for private in ("environment.py", "missions.py", "model.py", "service.py"):
                    self.assertFalse((oracle / package / private).exists())
            for relative, code in [
                ("environment/simulator", "from lightlag_expedition.service import ExpeditionService; s = ExpeditionService(1); assert s.rules()['max_ticks'] == 60; assert s.finish()['reward'] == 0"),
                ("solution", "from lightlag_expedition.reference import run_policy; assert callable(run_policy); assert not any(k == 'lightlag' or k.endswith('.environment') or k.endswith('.missions') for k in sys.modules)"),
            ]:
                script = "import sys; sys.path.insert(0, sys.argv[1]); " + code
                result = subprocess.run([sys.executable, "-I", "-B", "-c", script, str(output / relative)], cwd=temporary, text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_bad_inputs_and_existing_output_leave_files_untouched(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "new"
            for arguments in ({"visibility": "oracle"}, {"seed": True}, {"seed": -1}, {"mission_seed": False}, {"mission_seed": -1}, {"policy": "unknown"}):
                with self.assertRaises(ValueError):
                    prepare_module.prepare(destination, **arguments)
                self.assertFalse(destination.exists())
            marker = Path(temporary) / "keep"
            marker.write_text("original")
            with self.assertRaises(FileExistsError):
                prepare_module.prepare(temporary)
            self.assertEqual(marker.read_text(), "original")
            with self.assertRaises(ValueError):
                prepare_module.prepare(ROOT / "forbidden-expedition-task")

    def test_paired_visibility_and_all_policies_keep_identical_instructions(self):
        with tempfile.TemporaryDirectory() as temporary:
            instructions = []
            for index, policy in enumerate(prepare_module.POLICIES):
                destination = Path(temporary) / policy
                visibility = "public" if index % 2 else "hidden"
                manifest = prepare_module.prepare(destination, seed=89, mission_seed=4, visibility=visibility, policy=policy)
                instructions.append((destination / "instruction.md").read_bytes())
                self.assertIn("--policy " + policy, (destination / "solution/solve.sh").read_text())
                self.assertEqual(manifest["settings"]["visibility"], visibility)
                self.assertEqual((manifest["settings"]["seed"], manifest["settings"]["mission_seed"]), (89, 4))
            self.assertEqual(len(set(instructions)), 1)


if __name__ == "__main__":
    unittest.main()
