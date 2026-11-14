"""The launcher an agent starts its autopilot with, against a model of an agent's shell tool.

    python3 -m unittest discover -s tests/lightlag_live -v

In three saved agent runs on task 0.1.1 the autopilot stopped exactly 120 seconds into the
campaign (`docs/lightlag-live.md`, "The launch trap"). Each agent had started it in the form
the task suggested, behind a `cd`:

    cd /app && nohup python3 autopilot.py > autopilot.log 2>&1 & sleep 12; cat autopilot.log

OpenCode's shell tool did not return after the `sleep`. It returned at its 120-second limit,
and the program was gone. `ShellTool` below is the smallest model that behaves as the tool was
seen to behave in those runs; the first test reproduces the failure with it, and the others
show that a program started through `lightlag_live/detach.py` is out of its reach.

Standard library only; needs bash and a POSIX system.
"""

import os
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DETACH = REPO / "lightlag_live" / "detach.py"
PYTHON = shlex.quote(sys.executable)

# Stands in for an autopilot: one line per 50 ms, for at most 30 seconds so a failed test leaves nothing behind.
TICKER = """\
import os, time
open("ticker.pid", "w").write(str(os.getpid()))
for number in range(600):
    print("tick", number)
    time.sleep(0.05)
"""


class ShellTool:
    """One command at a time under a time limit, as OpenCode 1.19.5 was seen to run them.

    The command gets its own process group. The call returns when the command has exited and
    nothing it started still holds its output. At the limit the whole group is killed. A
    command that finishes in time is not cleaned up after: what it left running keeps running.
    """

    def run(self, command, cwd, limit):
        started = time.monotonic()
        process = subprocess.Popen(["bash", "-c", command], cwd=cwd, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
        terminated = False
        try:
            output, _ = process.communicate(timeout=limit)
        except subprocess.TimeoutExpired:
            terminated = True
            os.killpg(process.pid, signal.SIGKILL)
            output, _ = process.communicate(timeout=10)
        return output.decode(), terminated, time.monotonic() - started


@unittest.skipUnless(os.name == "posix" and shutil.which("bash"), "needs bash on a POSIX system")
class DetachTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix="lightlag-detach-")
        (Path(self.folder) / "ticker.py").write_text(TICKER, encoding="utf-8")
        self.tool = ShellTool()

    def tearDown(self):
        pid_file = Path(self.folder) / "ticker.pid"
        if pid_file.exists():
            try:
                os.kill(int(pid_file.read_text()), signal.SIGKILL)
            except (OSError, ValueError):
                pass
        shutil.rmtree(self.folder, ignore_errors=True)

    def ticks(self, log):
        path = Path(self.folder) / log
        return path.read_text(encoding="utf-8").count("tick") if path.exists() else 0

    def is_running(self, log, within=3.0):
        """True if the program writes at least two more lines to its log within `within` seconds."""
        before = self.ticks(log)
        deadline = time.monotonic() + within
        while time.monotonic() < deadline:
            if self.ticks(log) >= before + 2:
                return True
            time.sleep(0.05)
        return False

    def test_a_background_job_dies_with_the_command_that_started_it(self):
        # The form three agents used, as suggested by task 0.1.1. This is the failure, reproduced.
        # (`-u` so that the log shows how long the program lived; the launcher needs no such flag.)
        command = "cd {} && nohup {} -u ticker.py > autopilot.log 2>&1 & sleep 0.3; cat autopilot.log".format(
            shlex.quote(self.folder), PYTHON)
        output, terminated, seconds = self.tool.run(command, self.folder, limit=2.0)
        self.assertTrue(terminated, "the call should hang until the limit: the waiting shell holds the tool's output")
        self.assertGreaterEqual(seconds, 2.0)
        self.assertGreater(self.ticks("autopilot.log"), 5, "the program did run until the limit")
        self.assertFalse(self.is_running("autopilot.log", within=1.0), "and was killed with the command")

    def test_the_launcher_returns_at_once_and_its_program_outlives_later_commands(self):
        for shape in ("cd {folder} && {python} {detach} {python} ticker.py; sleep 0.3; cat autopilot.log",
                      # an agent may still add `&` out of habit; that has to be harmless
                      "cd {folder} && {python} {detach} {python} ticker.py & sleep 0.3; cat autopilot.log"):
            with self.subTest(shape=shape):
                for name in ("autopilot.log", "ticker.pid"):
                    (Path(self.folder) / name).unlink(missing_ok=True)
                command = shape.format(folder=shlex.quote(self.folder), python=PYTHON, detach=shlex.quote(str(DETACH)))
                output, terminated, seconds = self.tool.run(command, self.folder, limit=20.0)
                self.assertFalse(terminated, output)
                self.assertLess(seconds, 10.0, "the call returns when its own commands are done")
                self.assertIn("started pid", output)
                self.assertIn("tick 0", output, "output reaches the log without waiting for a full buffer")
                self.assertTrue(self.is_running("autopilot.log"))
                # A later command that runs into its limit is killed; the program is not.
                _, terminated, _ = self.tool.run("sleep 30", self.folder, limit=0.5)
                self.assertTrue(terminated)
                self.assertTrue(self.is_running("autopilot.log"))
                os.kill(int((Path(self.folder) / "ticker.pid").read_text()), signal.SIGKILL)

    def test_the_log_can_be_named_and_is_appended_to(self):
        (Path(self.folder) / "second.log").write_text("earlier run\n", encoding="utf-8")
        done = subprocess.run([sys.executable, str(DETACH), "--log", "second.log", sys.executable, "ticker.py"],
                              cwd=self.folder, capture_output=True, text=True, timeout=20)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn(os.path.join(os.path.realpath(self.folder), "second.log"), done.stdout)
        self.assertTrue(self.is_running("second.log"))
        self.assertTrue((Path(self.folder) / "second.log").read_text(encoding="utf-8").startswith("earlier run\n"))
        self.assertFalse((Path(self.folder) / "autopilot.log").exists())

    def test_misuse_is_reported_and_starts_nothing(self):
        nothing = subprocess.run([sys.executable, str(DETACH)], cwd=self.folder, capture_output=True, text=True, timeout=20)
        self.assertEqual(nothing.returncode, 2)
        self.assertIn("python3 autopilot.py", nothing.stderr)
        missing = subprocess.run([sys.executable, str(DETACH), "no-such-program-here"], cwd=self.folder,
                                 capture_output=True, text=True, timeout=20)
        self.assertEqual(missing.returncode, 1)
        self.assertIn("could not start", missing.stderr)
        self.assertFalse((Path(self.folder) / "ticker.pid").exists())


if __name__ == "__main__":
    unittest.main()
