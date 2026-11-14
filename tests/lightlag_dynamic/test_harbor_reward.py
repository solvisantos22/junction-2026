"""Our swarm optimises the number Harbor grades.

The Manh controllers are ranked by superlog's `share`. Harbor's verifier (Kristján's
harbor/lightlag/tests/grade.py) writes reward = raw_score / max_available_value to
verifier/reward.txt. These tests fail if the two ever drift apart: on every recorded Harbor
run, and on a fresh noisy rush episode (no noisy run is recorded yet).
"""

import importlib.util
import json
import unittest
from pathlib import Path

HAVE_NUMPY = importlib.util.find_spec("numpy") is not None
REPO = Path(__file__).resolve().parents[2]
GRADER = REPO / "harbor" / "lightlag" / "tests" / "grade.py"
RUNS = REPO / "docs" / "lightlag-runs"


def load_grader():
    spec = importlib.util.spec_from_file_location("lightlag_harbor_grade", GRADER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def recorded_runs():
    return sorted(path.parents[2] for path in RUNS.glob("*/artifacts/evaluator/replay.json")
                  if (path.parents[2] / "verifier" / "reward.txt").exists())


@unittest.skipUnless(HAVE_NUMPY, "superlog needs numpy")
@unittest.skipUnless(GRADER.exists(), "the Harbor task's grader is not in this checkout")
class HarborRewardTest(unittest.TestCase):
    def test_recorded_runs(self):
        from lightlag_dynamic.manh_controllers.superlog import summarize
        grade = load_grader()
        runs = recorded_runs()
        if not runs:
            self.skipTest("no recorded Harbor runs under docs/lightlag-runs")
        for run in runs:
            with self.subTest(run=run.name):
                reward = float((run / "verifier" / "reward.txt").read_text())
                result = json.loads((run / "artifacts" / "evaluator" / "result.json").read_text())
                replay = json.loads((run / "artifacts" / "evaluator" / "replay.json").read_text())
                self.assertAlmostEqual(grade.reward_from(result), reward, places=6)
                self.assertAlmostEqual(summarize(replay, None, None)["share"], reward, places=6)

    def test_fresh_noisy_rush_episode(self):
        from lightlag_dynamic.manh_controllers.scenarios import make_env
        from lightlag_dynamic.manh_controllers.superlog import summarize
        from lightlag_dynamic.controllers import kf_mpc
        from lightlag_dynamic.tools import PublicTools
        grade = load_grader()
        env = make_env(500, 3, "rush_noisy")  # the predeclared noisy pilot: seed 500, delay 3
        kf_mpc(PublicTools(env))
        while not env.advance(5)["episode_complete"]:
            pass
        reward = grade.reward_from(env.evaluate())
        self.assertAlmostEqual(summarize(env.scenario_replay(), None, None)["share"], reward, places=9)


if __name__ == "__main__":
    unittest.main()
