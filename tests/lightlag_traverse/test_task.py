"""The Harbor task: its copies are fresh, the agent's image holds no simulator, grading is honest.

    python3 -m unittest discover -s tests/lightlag_traverse -v

Standard library only.
"""

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from lightlag_traverse import make_task  # noqa: E402
from lightlag_traverse.environment import MISSION  # noqa: E402
from lightlag_traverse.pilot import fly  # noqa: E402
from lightlag_traverse.server import TraverseEpisodeService  # noqa: E402

TASK = REPO / "harbor" / "lightlag-traverse"
QUICK = {"plan_steps": 8000, "replan_steps": 1500, "beam": 40, "rebeam": 15}


def load_grade():
    spec = importlib.util.spec_from_file_location("lightlag_traverse_grade", TASK / "tests" / "grade.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TaskFilesTest(unittest.TestCase):
    def test_the_committed_task_matches_its_sources(self):
        self.assertEqual(make_task.stale(TASK, make_task.build()), [],
                         "run `python3 -m lightlag_traverse.make_task` and commit the result")

    def test_harbor_finds_the_required_files(self):
        for name in ("instruction.md", "task.toml", "environment/Dockerfile", "environment/docker-compose.yaml",
                     "tests/test.sh", "solution/solve.sh"):
            self.assertTrue((TASK / name).is_file(), name)
        self.assertTrue(os.access(TASK / "solution" / "solve.sh", os.X_OK))
        self.assertTrue(os.access(TASK / "tests" / "test.sh", os.X_OK))

    def test_the_agent_image_holds_the_client_the_ground_model_and_a_launcher_and_nothing_else(self):
        ignore = (TASK / "environment" / ".dockerignore").read_text(encoding="utf-8").split()
        self.assertIn("simulator/", ignore)
        self.assertIn("docker-compose.yaml", ignore)
        dockerfile = (TASK / "environment" / "Dockerfile").read_text(encoding="utf-8")
        copied = [line.split()[1] for line in dockerfile.splitlines() if line.startswith("COPY ")]
        self.assertEqual(copied, ["lightlag_client.py", "lightlag_surface.py", "detach.py"])
        for name in copied:
            text = (TASK / "environment" / name).read_text(encoding="utf-8")
            for word in ("TraverseEnvironment", "make_world", "lightlag-traverse-hidden", "_efficiency", str(make_task.SEED)):
                self.assertNotIn(word, text, name)
        # the ground model is the simulator's own file, byte for byte: nothing to reverse-engineer
        self.assertEqual((TASK / "environment" / "lightlag_surface.py").read_bytes(),
                         (TASK / "environment" / "simulator" / "lightlag_traverse" / "surface.py").read_bytes())

    def test_the_solution_holds_no_simulator_and_no_seed(self):
        for path in (TASK / "solution").rglob("*"):
            if path.is_file():
                text = path.read_text(encoding="utf-8")
                for word in ("TraverseEnvironment", "make_world", "from .terrain", "from .environment",
                             "lightlag-traverse-hidden", str(make_task.SEED)):
                    self.assertFalse(word in text, "{} holds {!r}".format(path.name, word))
        names = {str(p.relative_to(TASK / "solution")) for p in (TASK / "solution").rglob("*.py")}
        self.assertEqual(names, {"play_reference.py", "lightlag_client.py", "lightlag_traverse/__init__.py",
                                 "lightlag_traverse/surface.py", "lightlag_traverse/planning.py",
                                 "lightlag_traverse/pilot.py"})

    def test_the_instruction_states_the_mission_it_serves(self):
        instruction = (TASK / "instruction.md").read_text(encoding="utf-8")
        compose = (TASK / "environment" / "docker-compose.yaml").read_text(encoding="utf-8")
        self.assertIn('LIGHTLAG_SEED: "{}"'.format(make_task.SEED), compose)
        self.assertNotIn(str(make_task.SEED), instruction)
        self.assertIn("{} ticks".format(MISSION["max_ticks"]), instruction)
        self.assertIn("600 m by 400 m", instruction)
        for phrase in ("no reset and no practice run", "limited to 30 minutes", "`max_tilt`",
                       "python3 /app/detach.py", "/app/lightlag_surface.py",
                       "do not finish before `episode_complete` is true"):
            self.assertIn(phrase, instruction)
        toml = (TASK / "task.toml").read_text(encoding="utf-8")
        self.assertIn("timeout_sec = 1800.0", toml)
        self.assertIn("lightlag_mcp.finish", toml)


class GradeChainTest(unittest.TestCase):
    """From a mission to the number Harbor reads, with the service and the grader the task ships."""

    def grade(self, folder, name, play):
        artifacts = os.path.join(folder, name)
        service = TraverseEpisodeService(5, artifact_dir=artifacts)
        play(service)
        result = service.finish()
        reward_file = os.path.join(folder, name + "-reward.txt")
        code = load_grade().main(["--result", os.path.join(artifacts, "result.json"), "--reward", reward_file])
        self.assertEqual(code, 0)
        with open(reward_file, encoding="utf-8") as stream:
            reward = float(stream.read())
        self.assertAlmostEqual(reward, result["raw_score"] / result["max_available_value"], places=6)
        self.assertTrue(os.path.exists(os.path.join(artifacts, "replay.json")))
        return reward, service

    def test_reference_do_nothing_and_stop_early(self):
        def stop_early(service):
            from lightlag_traverse.pilot import Pilot
            pilot = Pilot(service, QUICK)
            for _ in range(100):                             # the agent leaves after a quarter of the day
                pilot.act()
                out = service.advance(1)
                pilot.observe(out["packets"], out["current_tick"])

        with tempfile.TemporaryDirectory() as folder:
            reference, service = self.grade(folder, "reference", lambda s: fly(s, QUICK))
            nothing, _ = self.grade(folder, "nothing", lambda s: None)
            early, _ = self.grade(folder, "early", stop_early)
            self.assertGreater(reference, 0.3)
            self.assertEqual(nothing, 0.0)
            self.assertLess(early, 0.5 * reference)          # stranded far from the lander with a few samples
            with self.assertRaises(ValueError):              # a finished mission takes no more calls
                service.call("advance", {"ticks": 1})
            transcript = service.transcript()
            self.assertEqual({row["tool"] for row in transcript}, {"rules", "map", "uplink", "advance"})

    def test_the_service_offers_exactly_the_five_tools(self):
        service = TraverseEpisodeService(5)
        for tool in ("evaluate", "replay", "reset", "finish", "seed"):
            with self.assertRaises(ValueError):
                service.call(tool, {})
        self.assertIn("physics", service.call("rules"))
        self.assertEqual(len(service.call("map")["elevation_cm"]), 81)
        self.assertEqual(json.loads(json.dumps(service.call("telemetry_log")))[0]["tick"], 0)


if __name__ == "__main__":
    unittest.main()
