"""The Harbor task: its copies are fresh, the agent's image holds no simulator, grading is strict.

Standard library only (the chain test needs nothing else either).

    python3 -m unittest discover -s tests/lightlag_live -v
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

from lightlag_dynamic.controllers import POLICIES  # noqa: E402
from lightlag_live import CampaignService, make_task, play_campaign  # noqa: E402

TASK = REPO / "harbor" / "lightlag-live"


def load_grade():
    spec = importlib.util.spec_from_file_location("lightlag_live_grade", TASK / "tests" / "grade.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TaskFilesTest(unittest.TestCase):
    def test_the_committed_task_matches_its_sources(self):
        self.assertEqual(make_task.stale(TASK, make_task.build()), [],
                         "run `python3 -m lightlag_live.make_task` and commit the result")

    def test_harbor_finds_the_required_files(self):
        for name in ("instruction.md", "task.toml", "environment/Dockerfile", "environment/docker-compose.yaml",
                     "tests/test.sh", "solution/solve.sh"):
            self.assertTrue((TASK / name).is_file(), name)
        self.assertTrue(os.access(TASK / "solution" / "solve.sh", os.X_OK))
        self.assertTrue(os.access(TASK / "tests" / "test.sh", os.X_OK))

    def test_the_agent_image_holds_no_simulator_and_no_settings(self):
        ignore = (TASK / "environment" / ".dockerignore").read_text(encoding="utf-8").split()
        self.assertIn("simulator/", ignore)
        self.assertIn("docker-compose.yaml", ignore)
        dockerfile = (TASK / "environment" / "Dockerfile").read_text(encoding="utf-8")
        copied = [line.split()[1] for line in dockerfile.splitlines() if line.startswith("COPY ")]
        self.assertEqual(copied, ["lightlag_client.py", "detach.py"])
        for name in copied:
            text = (TASK / "environment" / name).read_text(encoding="utf-8")
            for word in ("lightlag_live", "lightlag_dynamic", "DynamicEnvironment", "seed"):
                self.assertNotIn(word, text, name)

    def test_the_instruction_names_a_launcher_that_is_in_the_image(self):
        # Task 0.1.1 suggested `nohup ... &`; three agents' programs were killed by their shell tool that way.
        instruction = (TASK / "instruction.md").read_text(encoding="utf-8")
        self.assertIn("python3 /app/detach.py python3 autopilot.py", instruction)
        self.assertNotIn("nohup python3 autopilot.py", instruction)
        # An agent that ends its session takes its program with it; 0.1.3 says so in as many words.
        self.assertIn("Your program stops when your session ends", instruction)
        dockerfile = (TASK / "environment" / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("COPY detach.py /app/detach.py", dockerfile)
        self.assertEqual((TASK / "environment" / "detach.py").read_bytes(),
                         (REPO / "lightlag_live" / "detach.py").read_bytes())

    def test_the_solution_holds_no_simulator_and_no_seed(self):
        for path in (TASK / "solution").rglob("*"):
            if path.is_file():
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("DynamicEnvironment", text, path)
                self.assertNotIn("lightlag_live.campaign", text, path)
                self.assertNotIn("9003", text, path)

    def test_the_instruction_states_the_campaign_it_serves(self):
        instruction = (TASK / "instruction.md").read_text(encoding="utf-8")
        compose = (TASK / "environment" / "docker-compose.yaml").read_text(encoding="utf-8")
        missions = make_task.MISSIONS.split(",")
        self.assertIn('LIGHTLAG_MISSIONS: "{}"'.format(make_task.MISSIONS), compose)
        self.assertIn("{} missions in a row".format(len(missions)), instruction)
        self.assertIn("one tick passes every second", instruction)
        for seed in (part.split(":")[0] for part in missions):
            self.assertNotIn(seed, instruction)


class GradeTest(unittest.TestCase):
    def setUp(self):
        self.grade = load_grade()

    def result(self, *pairs):
        missions = [{"raw_score": raw, "max_available_value": available, "alive": True} for raw, available in pairs]
        reward = sum(raw / available for raw, available in pairs) / len(pairs)
        return {"missions": missions, "reward": reward}

    def test_the_reward_is_the_mean_of_the_missions(self):
        self.assertAlmostEqual(self.grade.reward_from(self.result((5, 10), (0, 8), (12, 12))), 0.5)

    def test_malformed_results_are_refused_not_scored(self):
        good = self.result((5, 10), (4, 8))
        for broken in (
            {}, {"missions": [], "reward": 0}, dict(good, reward=0.9), dict(good, reward=True),
            {"missions": [{"raw_score": 11, "max_available_value": 10}], "reward": 1.1},
            {"missions": [{"raw_score": float("nan"), "max_available_value": 10}], "reward": 0},
            {"missions": [{"raw_score": 1, "max_available_value": 0}], "reward": 0},
            {"missions": [{"raw_score": -1, "max_available_value": 10}], "reward": -0.1},
            {"missions": [{"max_available_value": 10}], "reward": 0},
        ):
            with self.assertRaises(self.grade.BadResult, msg=broken):
                self.grade.reward_from(broken)

    def test_the_chain_from_campaign_to_reward_file(self):
        class Clock:
            now = 0.0

            def __call__(self):
                return self.now

            def sleep(self, seconds):
                self.now += seconds

        missions = [{"seed": 8000, "profile": "rush_noisy"}, {"seed": 8001, "profile": "rush_noisy"}]
        with tempfile.TemporaryDirectory() as folder:
            for name, play in (("reference", lambda c: play_campaign(c, POLICIES["kf_mpc"])),
                               ("do_nothing", lambda c: None),
                               ("stop_early", lambda c: POLICIES["kf_mpc"](c))):
                clock = Clock()
                artifacts = os.path.join(folder, name)
                campaign = CampaignService(missions, noise_level=2.0, artifact_dir=artifacts,
                                           clock=clock, sleep=clock.sleep)
                play(campaign)
                campaign.finish()
                reward_file = os.path.join(folder, name + "-reward.txt")
                code = self.grade.main(["--result", os.path.join(artifacts, "result.json"),
                                        "--reward", reward_file])
                self.assertEqual(code, 0)
                with open(reward_file, encoding="utf-8") as stream:
                    reward = float(stream.read())
                with open(os.path.join(artifacts, "result.json"), encoding="utf-8") as stream:
                    self.assertAlmostEqual(reward, json.load(stream)["reward"], places=6)
                if name == "reference":
                    reference = reward
                    self.assertGreater(reward, 0.3)
                elif name == "do_nothing":
                    self.assertEqual(reward, 0.0)
                else:
                    self.assertLess(reward, reference)
            self.assertEqual(self.grade.main(["--result", os.path.join(folder, "missing.json"),
                                              "--reward", os.path.join(folder, "none.txt")]), 1)
            self.assertFalse(os.path.exists(os.path.join(folder, "none.txt")))


if __name__ == "__main__":
    unittest.main()
