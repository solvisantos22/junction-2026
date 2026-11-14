"""Offline CLI exit and malformed-worker regressions; no episode maps needed."""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from tools.lightlag_experiments import overnight_synthesis as base


class Guardrails(unittest.TestCase):
    def test_cli_propagates_phase_exit_status(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shutil.copyfile(REPO / "tools/lightlag_experiments/overnight_synthesis.py", root / "overnight_synthesis.py")
            (root / "overnight_synthesis_evaluate.py").write_text("def main(argv, *, base):\n    return 7\n")
            result = subprocess.run([sys.executable, "-B", str(root / "overnight_synthesis.py"), "evaluate"],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 7, result.stderr)

    def test_deep_untrusted_json_is_a_protocol_error(self):
        with self.assertRaises(base.ProtocolError):
            base.parse_call(b'[' * 2000 + b'0' + b']' * 2000, 1)

    @unittest.skipUnless(os.environ.get("SYNTHESIS_TEST_IMAGE"), "set pinned image for malformed worker canary")
    def test_raw_nonfinite_terminal_message_cannot_poison_grade_serialization(self):
        with tempfile.TemporaryDirectory() as temporary:
            policy = Path(temporary) / "canary.py"
            policy.write_text("import os, sys\ndef play(tools):\n sys.__stdout__.write('{\"done\":true,\"status\":\"policy_error\",\"error\":NaN}\\n')\n sys.__stdout__.flush()\n os._exit(0)\n")
            execution = base.run_container(None, policy, REPO / "tools/lightlag_experiments/overnight_synthesis_worker.py",
                                           os.environ["SYNTHESIS_TEST_IMAGE"], "/usr/local/bin/docker", seconds=10)
            self.assertEqual(execution["status"], "policy_protocol_error", execution)
            self.assertTrue(execution["cleanup"]["confirmed_absent"])
            base.canonical(execution)


if __name__ == "__main__":
    unittest.main()
