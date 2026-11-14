"""The reference pilot: what it is allowed to touch, and what it achieves on a world.

    python3 -m unittest discover -s tests/lightlag_traverse -v

Standard library only. The pilot plays with a small search budget here so the tests stay
quick; its scores with the full budget are in docs/lightlag-traverse.md.
"""

import math
import random
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from lightlag_traverse.environment import MISSION, SENSING, TraverseEnvironment  # noqa: E402
from lightlag_traverse.pilot import DEFAULTS, Filter, fly  # noqa: E402
from lightlag_traverse.play import POLICIES, run_episode  # noqa: E402

QUICK = {"plan_steps": 12000, "replan_steps": 2000, "beam": 60, "rebeam": 20}
SEED = 5


class OnlyFiveTools:
    """The five public calls and nothing else: any other attribute the pilot reaches for is an error."""

    def __init__(self, env):
        self.__env = env
        self.calls = []
        self.rejected = 0

    def rules(self):
        self.calls.append("rules")
        return self.__env.rules()

    def map(self):
        self.calls.append("map")
        return self.__env.map()

    def telemetry_log(self):
        self.calls.append("telemetry_log")
        return self.__env.telemetry_log()

    def uplink(self, commands):
        self.calls.append("uplink")
        try:
            return self.__env.uplink(commands)
        except ValueError:
            self.rejected += 1
            raise

    def advance(self, ticks=1):
        self.calls.append("advance")
        return self.__env.advance(ticks)

    def __getattr__(self, name):
        raise AssertionError("the pilot reached for {!r}, which is not a public tool".format(name))


def play(seed, options):
    env = TraverseEnvironment(seed)
    tools = OnlyFiveTools(env)
    pilot = fly(tools, options)
    return env, tools, pilot


class PilotTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env, cls.tools, cls.pilot = play(SEED, QUICK)
        cls.result = cls.env.evaluate()

    def test_it_plays_through_the_five_tools_and_is_never_refused(self):
        self.assertEqual(set(self.tools.calls), {"rules", "map", "uplink", "advance"})
        self.assertEqual(self.tools.rejected, 0)
        self.assertEqual(self.tools.calls.count("advance"), MISSION["max_ticks"])    # one tick at a time, to the end

    def test_it_ends_alive_at_the_lander_with_a_real_haul(self):
        self.assertTrue(self.result["alive"])
        self.assertTrue(self.result["at_base"])
        reward = self.result["raw_score"] / self.result["max_available_value"]
        self.assertGreater(reward, 0.3)
        self.assertGreater(len(self.result["sampled_targets"]), 14)
        truth = self.env._truth
        self.assertGreater(min(state["battery"] for state in truth), 0.0)
        self.assertFalse(any(e["type"] == "safety_stop" for state in truth for e in state["events"]))

    def test_it_beats_the_same_pilot_without_route_planning_and_a_driver_that_ignores_the_ground(self):
        reward = self.result["raw_score"] / self.result["max_available_value"]
        greedy = run_episode(POLICIES["greedy"], SEED)["reward"]
        straight = run_episode(POLICIES["straight"], SEED)["reward"]
        self.assertGreater(reward, greedy)
        self.assertGreater(greedy, straight)
        self.assertEqual(run_episode(POLICIES["nothing"], SEED)["reward"], 0.0)

    def test_what_it_learned_is_close_to_the_hidden_truth(self):
        self.assertAlmostEqual(self.pilot.efficiency, self.env._efficiency, places=4)
        for name in ("regolith", "bedrock"):                 # the ground it drove most on
            self.assertAlmostEqual(self.pilot.slip[name], self.env._slip[name], delta=0.03, msg=name)
        last = self.env._truth[self.pilot.anchor_tick]["position"]
        self.assertLess(math.hypot(self.pilot.filter.x - last[0], self.pilot.filter.y - last[1]), 2.5)

    def test_the_same_world_gives_the_same_mission_every_time(self):
        env, _, _ = play(SEED, QUICK)
        self.assertEqual(env._sent, self.env._sent)
        self.assertEqual(env.evaluate(), self.result)

    def test_every_default_is_a_number_or_a_known_switch(self):
        for name, value in DEFAULTS.items():
            self.assertIsInstance(value, (int, float, str, bool), name)
        self.assertEqual(DEFAULTS["route"], "optimise")
        self.assertIs(DEFAULTS["terrain"], True)


class FilterTest(unittest.TestCase):
    def test_it_finds_the_heading_bias_from_noisy_fixes(self):
        rng = random.Random(4)
        bias, x, y = 4.0, 0.0, 0.0
        f = Filter(0.0, 0.0, SENSING)
        for _ in range(80):
            commanded = 30.0
            real = math.radians(commanded + bias)
            x, y = x + 4.5 * math.cos(real), y + 4.5 * math.sin(real)
            believed = math.radians(commanded + f.bias)
            f.move(4.5 * math.cos(believed), 4.5 * math.sin(believed), 4.5, believed)
            f.fix(x + rng.gauss(0, 1.0), y + rng.gauss(0, 1.0))
        self.assertAlmostEqual(f.bias, bias, delta=1.2)
        self.assertLess(math.hypot(f.x - x, f.y - y), 1.5)
        self.assertLess(f.sigma, 1.0)

    def test_a_fix_pulls_the_estimate_toward_it_and_shrinks_the_doubt(self):
        f = Filter(10.0, 10.0, SENSING)
        f.move(5.0, 0.0, 5.0, 0.0)
        before = f.sigma
        f.fix(16.0, 10.0)
        self.assertTrue(15.0 < f.x < 16.0)
        self.assertLess(f.sigma, before)


if __name__ == "__main__":
    unittest.main()
