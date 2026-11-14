"""Packaging invariants for the protected information-choice pilot."""

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("information_prepare", ROOT / "tools/information_allocation_experiments/prepare.py")
prepare_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prepare_module)


class PrepareTests(unittest.TestCase):
    def test_separate_simulator_verifier_and_manifest_hashes(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "task"
            manifest = prepare_module.prepare(output, context="case_1", seed=1100)
            for name, digest in manifest["source_sha256"].items():
                self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(), digest)
            for name, digest in manifest["task_sha256"].items():
                self.assertEqual(hashlib.sha256((output/name).read_bytes()).hexdigest(), digest)
            task = (output / "task.toml").read_text()
            self.assertIn('environment_mode = "separate"', task)
            self.assertIn('service = "allocation"', task)
            self.assertIn('--token-file /run/information/token', task)
            self.assertIn('source = "/evaluator"', task)
            compose = (output / "environment/docker-compose.yaml").read_text()
            main = compose.split('  allocation:')[0]
            self.assertNotIn('INFORMATION_SEED', main)
            self.assertNotIn('volumes:', compose)
            self.assertNotIn('ports:', compose)
            self.assertNotIn('COPY', (output / "environment/Dockerfile").read_text())
            self.assertIn('mcp==2.3.0', (output / "environment/Dockerfile").read_text())
            self.assertIn('mcp==2.3.0', (output / "environment/simulator/Dockerfile").read_text())
            self.assertFalse((output / "solution/lightlag_information_allocation/environment.py").exists())
            self.assertFalse((output / "solution/lightlag_information_allocation/model.py").exists())
            self.assertNotIn('from .environment', (output / "solution/lightlag_information_allocation/__init__.py").read_text())
            self.assertNotIn('terrain=', (output / "instruction.md").read_text())
            self.assertEqual(json.loads((output/'experiment.json').read_text()), manifest)
            self.assertTrue((output/'solution/solve.sh').stat().st_mode & 0o111)

    def test_inputs_and_existing_output_are_rejected_without_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary)/'new'
            for arguments in ({'context':'unknown'}, {'seed':True}, {'seed':-1}, {'policy':'oracle'}):
                with self.assertRaises(ValueError):
                    prepare_module.prepare(destination, **arguments)
                self.assertFalse(destination.exists())
            marker=Path(temporary)/'keep';marker.write_text('original')
            with self.assertRaises(FileExistsError):
                prepare_module.prepare(temporary)
            self.assertEqual(marker.read_text(),'original')
            with self.assertRaises(ValueError):
                prepare_module.prepare(ROOT/'forbidden-information-task')

    def test_all_contexts_and_nop_keep_identical_public_instructions(self):
        with tempfile.TemporaryDirectory() as temporary:
            instructions=[]
            for context in prepare_module.CONTEXTS:
                destination=Path(temporary)/context
                manifest=prepare_module.prepare(destination,context=context,policy='nop')
                instructions.append((destination/'instruction.md').read_bytes())
                self.assertIn('--policy nop', (destination/'solution/solve.sh').read_text())
                self.assertEqual(manifest['settings']['context'],context)
            self.assertEqual(len(set(instructions)),1)


if __name__ == '__main__':
    unittest.main()
