"""The Lightlag Harbor task, checked without containers.

    python3 -m unittest discover -s tests/harbor -v
    uv run --with 'mcp==2.3.0' python -m unittest discover -s tests/harbor -v   # adds the end-to-end runs

The end-to-end tests run the same four commands Harbor runs, from the task
directory's own copies of the code: the simulator's container command, the
solution, the collect hook and the verifier. They do not build or start
containers, so they do not replace a real `harbor run`.
"""

import importlib.util
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
TASK = REPO / "harbor" / "lightlag"
SIMULATOR = TASK / "environment" / "simulator"
HAVE_MCP = importlib.util.find_spec("mcp") is not None

sys.path.insert(0, str(REPO / "harbor"))
import sync_task  # noqa: E402

sys.path.insert(0, str(TASK / "tests"))
import grade  # noqa: E402


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class TaskFiles(unittest.TestCase):
    def test_the_task_has_every_file_harbor_requires(self):
        for name in ("instruction.md", "task.toml", "environment/Dockerfile", "environment/docker-compose.yaml",
                     "environment/simulator/Dockerfile", "tests/Dockerfile", "tests/test.sh", "tests/grade.py",
                     "solution/solve.sh", "solution/play_reference.py"):
            self.assertTrue((TASK / name).is_file(), name)
        for script in ("tests/test.sh", "solution/solve.sh"):
            self.assertTrue(os.access(TASK / script, os.X_OK), script)

    def test_copied_code_is_identical_to_the_originals(self):
        self.assertEqual(sync_task.stale(sync_task.plan()), [], "run: python3 harbor/sync_task.py")

    def test_the_agent_image_contains_no_simulator_code_or_episode_settings(self):
        dockerfile = (TASK / "environment" / "Dockerfile").read_text(encoding="utf-8")
        self.assertNotIn("COPY", dockerfile)
        self.assertNotIn("LIGHTLAG_SEED", dockerfile)
        ignored = (TASK / "environment" / ".dockerignore").read_text(encoding="utf-8").split()
        self.assertIn("simulator/", ignored)
        self.assertIn("docker-compose.yaml", ignored)
        solution_files = [p.name for p in (TASK / "solution").rglob("*.py")]
        self.assertNotIn("environment.py", solution_files)
        self.assertNotIn("service.py", solution_files)
        for path in (TASK / "solution").rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("import lightlag\n", text, path.name)
            self.assertNotIn("from lightlag import", text, path.name)

    def test_task_config_wires_the_sidecar_the_collect_hook_and_a_separate_verifier(self):
        try:
            import tomllib
        except ImportError:  # Python < 3.11
            self.skipTest("tomllib needs Python 3.11+")
        config = tomllib.loads((TASK / "task.toml").read_text(encoding="utf-8"))
        self.assertEqual(config["verifier"]["environment_mode"], "separate")
        self.assertEqual(config["artifacts"], [{"source": "/evaluator", "service": "lightlag"}])
        hook = config["verifier"]["collect"][0]
        self.assertEqual(hook["service"], "lightlag")
        self.assertIn("lightlag_mcp.finish", hook["command"])
        server = config["environment"]["mcp_servers"][0]
        self.assertEqual((server["name"], server["transport"], server["url"]),
                         ("lightlag", "streamable-http", "http://lightlag:8000/mcp"))
        compose = (TASK / "environment" / "docker-compose.yaml").read_text(encoding="utf-8")
        for expected in ("lightlag:", "context: ./simulator", "LIGHTLAG_ARTIFACT_DIR: /evaluator",
                         "LIGHTLAG_TOKEN_FILE: /run/lightlag/token", "service_healthy"):
            self.assertIn(expected, compose)


class Grading(unittest.TestCase):
    def test_reward_is_the_share_of_available_value(self):
        self.assertEqual(grade.reward_from({"raw_score": 0.0, "max_available_value": 4.0}), 0.0)
        self.assertEqual(grade.reward_from({"raw_score": 3.0, "max_available_value": 4.0}), 0.75)
        self.assertEqual(grade.reward_from({"raw_score": 4.0, "max_available_value": 4.0}), 1.0)

    def test_malformed_results_are_rejected_not_scored(self):
        bad = [{}, {"raw_score": 1.0}, {"raw_score": "3", "max_available_value": 4.0},
               {"raw_score": True, "max_available_value": 4.0}, {"raw_score": float("nan"), "max_available_value": 4.0},
               {"raw_score": 1.0, "max_available_value": 0.0}, {"raw_score": -1.0, "max_available_value": 4.0},
               {"raw_score": 9.0, "max_available_value": 4.0}, None, []]
        for result in bad:
            with self.assertRaises(grade.BadResult, msg=repr(result)):
                grade.reward_from(result)

    def test_a_missing_result_fails_the_verifier_and_writes_no_reward(self):
        with tempfile.TemporaryDirectory() as directory:
            reward = os.path.join(directory, "reward.txt")
            code = grade.main(["--result", os.path.join(directory, "absent.json"), "--reward", reward])
            self.assertEqual(code, 1)
            self.assertFalse(os.path.exists(reward))


@unittest.skipUnless(HAVE_MCP, "the mcp package is not installed")
class EndToEndWithoutContainers(unittest.TestCase):
    """Simulator command -> play -> collect hook -> verifier, as Harbor sequences them."""

    def run_trial(self, play=None, seed="7", delay="3"):
        with tempfile.TemporaryDirectory() as directory:
            evaluator = os.path.join(directory, "evaluator")
            token_file = os.path.join(directory, "run", "token")
            port = free_port()
            environment = dict(
                os.environ, PYTHONDONTWRITEBYTECODE="1", LIGHTLAG_SEED=seed, LIGHTLAG_DELAY=delay,
                LIGHTLAG_ARTIFACT_DIR=evaluator, LIGHTLAG_TOKEN_FILE=token_file,
                # solve.sh calls `python3`; in the container that is the interpreter with
                # the mcp package, so make it the one running these tests.
                PATH=os.path.dirname(sys.executable) + os.pathsep + os.environ.get("PATH", ""),
            )
            environment.pop("LIGHTLAG_EVALUATOR_TOKEN", None)
            simulator = subprocess.Popen(
                [sys.executable, "-m", "lightlag_mcp", "--transport", "http", "--host", "127.0.0.1", "--port", str(port)],
                cwd=SIMULATOR, env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            try:
                deadline = time.time() + 20
                while time.time() < deadline:
                    try:
                        socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
                        break
                    except OSError:
                        time.sleep(0.1)
                url = "http://127.0.0.1:{}".format(port)
                if play is not None:
                    solve = subprocess.run(
                        ["bash", str(TASK / "solution" / "solve.sh")] if play == "solve.sh" else
                        [sys.executable, "play_reference.py", "--url", url + "/mcp", "--strategy", play],
                        cwd=TASK / "solution", env=dict(environment, LIGHTLAG_MCP_URL=url + "/mcp"),
                        capture_output=True, text=True, timeout=120,
                    )
                    self.assertEqual(solve.returncode, 0, solve.stderr[-800:])
                self.assertEqual(oct(os.stat(token_file).st_mode & 0o777), "0o600")
                collect = subprocess.run(
                    [sys.executable, "-m", "lightlag_mcp.finish", "--url", url, "--token-file", token_file],
                    cwd=SIMULATOR, env=environment, capture_output=True, text=True, timeout=60,
                )
                self.assertEqual(collect.returncode, 0, collect.stderr[-800:])
                reward_file = os.path.join(directory, "logs", "reward.txt")
                verify = subprocess.run(
                    [sys.executable, str(TASK / "tests" / "grade.py"), "--result", os.path.join(evaluator, "result.json"),
                     "--reward", reward_file, "--details", os.path.join(directory, "logs", "details.json")],
                    capture_output=True, text=True, timeout=60,
                )
                self.assertEqual(verify.returncode, 0, verify.stderr[-800:])
                with open(reward_file, encoding="utf-8") as stream:
                    text = stream.read()
                with open(os.path.join(evaluator, "result.json"), encoding="utf-8") as stream:
                    result = json.load(stream)
                self.assertEqual(sorted(os.listdir(evaluator)), ["replay.json", "result.json", "transcript.jsonl"])
                return float(text), text, result
            finally:
                simulator.terminate()
                try:
                    simulator.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    simulator.kill()

    def test_the_solution_script_earns_a_high_reward(self):
        reward, text, result = self.run_trial(play="solve.sh")
        self.assertRegex(text, r"^\d\.\d{6}\n$")
        self.assertGreaterEqual(reward, 0.75)
        self.assertLessEqual(reward, 1.0)
        self.assertTrue(result["alive"] and result["at_base"])

    def test_doing_nothing_earns_zero(self):
        reward, _, result = self.run_trial(play=None)
        self.assertEqual(reward, 0.0)
        self.assertEqual((result["tick"], result["tool_calls"]), (80, 0))

    def test_stopping_early_earns_far_less_than_the_reference(self):
        early, _, _ = self.run_trial(play="stop_early")
        reference, _, _ = self.run_trial(play="reference")
        self.assertLess(early, 0.5 * reference)

    def test_acting_on_stale_telemetry_earns_less_than_the_reference(self):
        stale, _, _ = self.run_trial(play="stale_telemetry")
        reference, _, _ = self.run_trial(play="reference")
        self.assertLess(stale, reference)


if __name__ == "__main__":
    unittest.main()
