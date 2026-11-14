"""The MAX map's Harbor tasks: fresh copies, seeds only in the simulator, MAX behind the five tools, honest grading.

    python3 -m unittest discover -s tests/lightlag_traverse_max -p "test_task.py" -v

Standard library only, except the end-to-end test, which serves the task's own simulator folder
over HTTP and needs the `mcp` package (skipped without it). Docker is not needed.
"""

import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from lightlag_live.make_task import stale  # noqa: E402
from lightlag_traverse import make_task as kristjans  # noqa: E402
from lightlag_traverse_max import heldout, make_task  # noqa: E402
from lightlag_traverse_max.server import MaxCampaignService  # noqa: E402

FAIR, HARD = (make_task.TASKS[group][0] for group in ("fair", "superhard"))


def load_grade(task):
    spec = importlib.util.spec_from_file_location("lightlag_max_grade", task / "tests" / "grade.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def has_mcp():
    return importlib.util.find_spec("mcp") is not None


class TaskFilesTest(unittest.TestCase):
    def test_the_committed_tasks_match_their_sources_and_kristjans_are_untouched(self):
        for group, (task, _) in make_task.TASKS.items():
            self.assertEqual(stale(task, make_task.build(group)), [], group)
        self.assertEqual(stale(kristjans.TASK, kristjans.build()), [])
        self.assertEqual(stale(kristjans.CAMPAIGN_TASK, kristjans.build_campaign()), [])

    def test_the_seeds_are_the_held_out_worlds_and_live_in_the_simulator_only(self):
        for task, seeds in ((FAIR, heldout.FAIR_WORLDS), (HARD, heldout.SUPERHARD_WORLDS)):
            compose = (task / "environment" / "docker-compose.yaml").read_text(encoding="utf-8")
            self.assertIn('LIGHTLAG_SEEDS: "{}"'.format(",".join(map(str, seeds))), compose)
            self.assertEqual(json.loads((task / "manifest.json").read_text())["settings"]["seeds"], list(seeds))
            outside = [path for path in task.rglob("*") if path.is_file() and "simulator" not in path.parts
                       and path.name not in ("docker-compose.yaml", "manifest.json")]
            for path in outside:
                text = path.read_text(encoding="utf-8", errors="replace")
                for seed in seeds:
                    self.assertNotIn('"{}"'.format(seed), text, path)
                    self.assertNotIn("seed {}".format(seed), text, path)

    def test_the_agent_gets_the_same_image_and_verifier_as_kristjans_campaign(self):
        for task in (FAIR, HARD):
            for name in ("environment/Dockerfile", "environment/.dockerignore", "environment/lightlag_client.py",
                         "environment/lightlag_surface.py", "environment/detach.py", "tests/grade.py",
                         "tests/test.sh", "tests/Dockerfile", "solution/play_reference.py", "solution/solve.sh"):
                self.assertEqual((task / name).read_bytes(), (kristjans.CAMPAIGN_TASK / name).read_bytes(), name)
            self.assertFalse(any("lightlag_traverse_max" in path.parts for path in (task / "solution").rglob("*")))

    def test_the_simulator_serves_the_max_map_and_the_instruction_says_so(self):
        for task in (FAIR, HARD):
            docker = (task / "environment" / "simulator" / "Dockerfile").read_text(encoding="utf-8")
            self.assertIn('"lightlag_traverse_max.server"', docker)
            self.assertIn("COPY lightlag_traverse_max/ lightlag_traverse_max/", docker)
            text = (task / "instruction.md").read_text(encoding="utf-8")
            self.assertIn("## This is the MAX map", text)
            self.assertIn("three missions", text)
            self.assertIn('version = "0.1.0"', (task / "task.toml").read_text(encoding="utf-8"))


class GradeChainTest(unittest.TestCase):
    def test_the_campaign_is_on_the_max_map_and_doing_nothing_scores_zero(self):
        with tempfile.TemporaryDirectory() as folder:
            service = MaxCampaignService(list(heldout.FAIR_WORLDS), artifact_dir=folder)
            rules = service.call("rules")
            self.assertEqual(rules["map_option"], "max")
            self.assertEqual(rules["physics"]["slip_grade_gain"]["sand"], 3.5)        # the published value
            self.assertIn("crust_regions", service.call("map"))
            for tool in ("evaluate", "replay", "reset", "finish", "seed", "run_out", "mission_records"):
                with self.assertRaises(ValueError):
                    service.call(tool, {})
            result = service.finish()
            self.assertEqual(result["raw_score"], 0.0)
            reward = Path(folder) / "reward.txt"
            self.assertEqual(load_grade(FAIR).main(["--result", str(Path(folder) / "result.json"),
                                                    "--reward", str(reward)]), 0)
            self.assertEqual(float(reward.read_text()), 0.0)


@unittest.skipUnless(has_mcp(), "needs the mcp package")
class EndToEndTest(unittest.TestCase):
    """The task's own simulator folder, served over HTTP as its container would, reached with the
    agent's own client; then the evaluator's finish route and the task's grader."""

    def test_an_agent_reaches_the_max_map_through_the_five_tools_and_is_graded(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            shutil.copytree(HARD / "environment" / "simulator", root / "srv")
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 0))
                port = probe.getsockname()[1]
            env = dict(os.environ, LIGHTLAG_SEEDS="505,509,515", LIGHTLAG_ARTIFACT_DIR=str(root / "evaluator"),
                       LIGHTLAG_TOKEN_FILE=str(root / "run" / "token"), PYTHONPATH=str(root / "srv"))
            server = subprocess.Popen([sys.executable, "-m", "lightlag_traverse_max.server", "--transport", "http",
                                       "--host", "127.0.0.1", "--port", str(port)], cwd=root / "srv", env=env,
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            def stop():
                server.kill()
                server.wait()
            self.addCleanup(stop)
            url = "http://127.0.0.1:{}".format(port)
            for _ in range(100):
                try:
                    import urllib.request
                    urllib.request.urlopen(url + "/healthz", timeout=1)
                    break
                except OSError:
                    time.sleep(0.2)
            sys.path.insert(0, str(HARD / "environment"))
            self.addCleanup(sys.path.remove, str(HARD / "environment"))
            from lightlag_client import connect
            with connect(url + "/mcp") as tools:
                self.assertEqual(set(tools.tool_names()), {"rules", "map", "telemetry_log", "uplink", "advance"})
                self.assertEqual(tools.rules()["map_option"], "max")
                self.assertEqual(tools.map()["mission"], 1)
                tools.uplink([{"action": "drive", "heading_deg": 0, "metres": 2.0}])
                out = tools.advance(5)
                self.assertEqual(out["current_tick"], 5)
            sys.path.insert(0, str(root / "srv"))
            self.addCleanup(sys.path.remove, str(root / "srv"))
            from lightlag_mcp.finish import finish
            result = finish(url, (root / "run" / "token").read_text().strip())
            self.assertEqual(result["raw_score"], 0.0)
            reward = root / "reward.txt"
            self.assertEqual(load_grade(HARD).main(["--result", str(root / "evaluator" / "result.json"),
                                                    "--reward", str(reward)]), 0)
            self.assertEqual(float(reward.read_text()), 0.0)
            missions = json.loads((root / "evaluator" / "result.json").read_text())
            self.assertIn("missions", json.dumps(missions))


if __name__ == "__main__":
    unittest.main()
