"""Safety boundaries of the local free preflight runner, without launching Docker."""

import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/expedition_experiments"))
SPEC = importlib.util.spec_from_file_location("free_harbor_check", ROOT / "tools/expedition_experiments/free_harbor_check.py")
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)
sys.path.pop(0)


class FreeHarborTests(unittest.TestCase):
    def test_container_filter_is_specific_to_our_generated_task(self):
        task = "expedition-free-nop-abcdef1234"
        self.assertTrue(module.matching_main(task + "__abc123__env-main-1", task))
        for name in ("teammate__abc__env-main-1", task + "-other__abc__env-main-1",
                     task + "__abc__env-expedition-1", task + "__abc__env-verifier-1"):
            self.assertFalse(module.matching_main(name, task))

    def test_child_environment_does_not_forward_provider_keys(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-secret", "OPENAI_API_KEY": "test-secret",
                                     "SOME_TOKEN": "test-secret", "PATH": "/usr/bin", "HOME": "/tmp/test"}, clear=True):
            env = module.sanitized_environment()
        self.assertNotIn("test-secret", env.values())
        self.assertEqual(env["PATH"], "/usr/bin")
        self.assertEqual(env["HOME"], "/tmp/test")

    def test_existing_output_is_preserved_before_any_run(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(module.subprocess, "Popen") as popen:
            marker = Path(temporary) / "keep"
            marker.write_text("existing evidence")
            with self.assertRaises(FileExistsError):
                module.run(temporary, "/never/harbor", "/never/docker")
            self.assertEqual(marker.read_text(), "existing evidence")
            popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
