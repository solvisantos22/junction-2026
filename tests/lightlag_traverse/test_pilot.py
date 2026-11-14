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
from lightlag_traverse.pilot import DEFAULTS, Filter, Pilot, fly  # noqa: E402
from lightlag_traverse.play import POLICIES, PublicTools, run_episode  # noqa: E402
from lightlag_traverse.terrain import TraverseTarget, TraverseWorld  # noqa: E402

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


class WayHomeTest(unittest.TestCase):
    """The battery reserve protects the rover out in the field; on the way home it is there to be spent."""

    def setUp(self):
        flat = tuple(tuple([0] * 41) for _ in range(41))
        world = TraverseWorld(1, 5.0, flat, tuple("r" * 40 for _ in range(40)), (100.0, 100.0),
                              (TraverseTarget("t1", 130.0, 100.0, 2.0),))
        self.pilot = Pilot(PublicTools(TraverseEnvironment(3, world)), QUICK)
        self.floor, self.home_floor = self.pilot.opt["floor"], self.pilot.opt["home_floor"]
        self.assertLess(self.home_floor, self.floor)

    def drive(self, goal, battery):
        gx, gy = self.pilot._spot(goal)
        return self.pilot._drive(goal, 115.0, 100.0, gx, gy, math.hypot(gx - 115.0, gy - 100.0), battery)

    def test_out_in_the_field_it_waits_for_the_sun_rather_than_dip_into_the_reserve(self):
        self.assertEqual(self.drive("t1", self.floor + 1.0), {"action": "wait"})
        self.assertEqual(self.drive("t1", self.floor + 4.0)["action"], "drive")

    def test_on_the_way_home_it_spends_the_reserve_and_creeps_on_what_is_left(self):
        full = self.drive("base", self.floor + 4.0)
        self.assertEqual((full["action"], full["metres"]), ("drive", 5.0))
        low = self.drive("base", self.floor)                       # under the field reserve, over the home one
        self.assertEqual((low["action"], low["metres"]), ("drive", 5.0))
        creep = self.drive("base", self.home_floor + 1.2)          # pays for part of a drive only
        self.assertEqual(creep["action"], "drive")
        self.assertTrue(0.5 <= creep["metres"] < 5.0, creep)
        self.assertEqual(self.drive("base", self.home_floor + 0.2), {"action": "wait"})

    def test_a_creeping_drive_never_costs_more_than_the_battery_has_above_the_home_reserve(self):
        from lightlag_traverse.surface import drive as model_drive
        for battery in (2.6, 3.0, 3.4, 4.0, 5.0):
            command = self.drive("base", battery)
            if command["action"] != "drive":
                continue
            heading = command["heading_deg"] + self.pilot.filter.bias
            cost = model_drive(self.pilot.surface, self.pilot.physics, 115.0, 100.0, heading, command["metres"],
                               self.pilot.slip)["energy"]
            self.assertGreaterEqual(battery - cost - self.pilot.sun.idle, self.home_floor - 1e-9, battery)


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
