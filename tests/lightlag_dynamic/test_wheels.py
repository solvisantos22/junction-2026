"""Wheels of a hidden size on today's telemetry: a drive can fall short or overshoot.

Standard library only, except the reference test, which needs numpy, and the client test, which
needs the mcp package; about five seconds.
"""

import json
import math
import unittest

from lightlag import Config
from lightlag_dynamic.biomes import make_biome_env
from lightlag_dynamic.biomes.nogps import MANY_SENSORS, make_nogps_env
from lightlag_dynamic.biomes.serve import BiomeEpisodeService, build_biome_server
from lightlag_dynamic.biomes.wheels import WHEEL_SCALE_ERROR, OvershootEnvironment, make_overshoot_env
from lightlag_dynamic.biomes.wording import brief, tool_wording
from lightlag_dynamic.controllers import POLICIES
from lightlag_dynamic.tools import PublicTools

try:
    import numpy  # noqa: F401
    HAVE_NUMPY = True
except ImportError:
    HAVE_NUMPY = False


def finish(env):
    while not env.advance(5)["episode_complete"]:
        pass
    return env


def play(env, policy=POLICIES["kf_mpc"]):
    policy(PublicTools(env))
    return finish(env)


def everything(env):
    return json.dumps([env.rules(), env.map(), env.telemetry_log(), env.replay()], sort_keys=True)


class WheelsTest(unittest.TestCase):
    def test_without_an_error_the_episode_is_the_biome_environments(self):
        for biome in ("main_mars", "troy_crust+relay_pass"):
            sized = play(make_overshoot_env(seed=5, delay=3, profile="rush_noisy", biome=biome, error=0.0))
            plain = play(make_biome_env(biome, 5, 3, "rush_noisy"))
            self.assertEqual(everything(sized), everything(plain), biome)

    def test_a_drive_covers_the_wheel_scale_times_the_ground_and_the_odometer_does_not_notice(self):
        ratios = []
        for seed in range(12):
            plain = make_biome_env("main_mars", seed, 0, "noisy")
            sized = make_overshoot_env(seed=seed, delay=0, profile="noisy", error=0.3)
            ground, spent = [], []
            for env in (plain, sized):
                env.uplink([{"action": "drive", "heading_deg": 180.0, "metres": 3.0}])   # west: bedrock all the way
                finish(env)
                states = env.replay()["states"]
                self.assertEqual((states[1]["terrain"], round(env.telemetry_log()[1]["wheel_odometry"], 9)), ("bedrock", 3.0))
                ground.append(math.dist(states[0]["position"], states[1]["position"]))
                spent.append(states[0]["battery"] - states[1]["battery"])
            scale = sized.replay()["wheels"]["wheel_scale"]
            self.assertTrue(0.7 <= scale <= 1.3)
            self.assertAlmostEqual(ground[1] / ground[0], scale, places=5)
            self.assertEqual(spent[1] > spent[0], scale > 1.0, "energy is spent on the metres the wheels really turn")
            self.assertLessEqual(ground[0], 3.0, "today a drive can only fall short")
            self.assertEqual(sized.rules()["wheels"]["wheel_scale_error"], 0.3)
            self.assertIn("hidden for the whole mission", sized.rules()["wheels"]["wheel_scale"])
            self.assertNotIn("wheels", plain.rules())
            self.assertNotIn(str(scale), json.dumps([sized.rules(), sized.map(), sized.telemetry_log()]))
            self.assertEqual(set(sized.telemetry_log()[1]), set(plain.telemetry_log()[1]), "the packets are today's")
            ratios.append(ground[1] / 3.0)
        self.assertGreater(max(ratios), 1.05, "some rover covers more ground than it was told to")
        self.assertLess(min(ratios), 0.9)

    def test_it_is_the_navigation_prototypes_rule_on_todays_telemetry(self):
        today = {"position_noise_m": 0.3, "heading_bias_deg": 5.0, "wheel_scale_error": WHEEL_SCALE_ERROR}
        for seed in range(4):
            here = play(make_overshoot_env(seed=seed, delay=3, profile="rush_noisy"))
            there = play(make_nogps_env(seed=seed, delay=3, profile="rush_noisy", navigation=today))
            states = here.replay()["states"]
            self.assertEqual(states, [{name: state[name] for name in mine} for mine, state in zip(states, there.replay()["states"])],
                             "the same rover, tick for tick")
            self.assertEqual(len(states), len(there.replay()["states"]))
            self.assertEqual(here.evaluate()["raw_score"], there.evaluate()["raw_score"])
            scale = here.replay()["wheels"]["wheel_scale"]
            self.assertEqual(scale, there.replay()["navigation"]["wheel_scale"])
            self.assertEqual(scale, finish(make_nogps_env(seed=seed, navigation=MANY_SENSORS)).replay()["navigation"]["wheel_scale"])
            for mine, theirs in zip(here.telemetry_log(), there.telemetry_log()):
                self.assertEqual(mine, {name: theirs[name] for name in mine}, "the same packets, without the extra readings")
                self.assertEqual(set(theirs) - set(mine), {"beacon_range_m", "sun_heading_deg"})

    def test_bad_errors_are_refused_and_the_entry_points_take_it(self):
        for bad in (-0.1, 0.5, None, "0.2", True):
            with self.assertRaises(ValueError, msg=repr(bad)):
                OvershootEnvironment(seed=1, wheel_scale_error=bad)
        config = Config(delay_ticks=3, max_ticks=50)
        service = BiomeEpisodeService(seed=3, profile="rush_noisy", config=config, wheel_error=0.2)
        self.assertEqual(service.rules()["wheels"]["wheel_scale_error"], 0.2)
        self.assertNotIn("navigation", service.rules())
        both = BiomeEpisodeService(seed=3, profile="rush_noisy", config=config, weak_gps=True, wheel_error=0.1)
        self.assertEqual(both.rules()["navigation"]["wheel_scale_error"], 0.1)
        self.assertNotIn("wheels", both.rules())
        self.assertNotIn("wheels", BiomeEpisodeService(seed=3, profile="rush_noisy", config=config).rules())

    def test_the_texts_say_what_a_drive_covers(self):
        rules = make_overshoot_env(seed=3, biome="troy_crust").rules()
        changes = tool_wording(rules)
        self.assertEqual(sorted(changes), ["INSTRUCTIONS", "MAP_DESCRIPTION", "RULES_DESCRIPTION", "TELEMETRY_DESCRIPTION"])
        told = changes["INSTRUCTIONS"][0][1]
        self.assertIn("Wheels: The wheels are a hidden few percent bigger or smaller than nominal (`rules`, wheels.wheel_scale)", told)
        self.assertIn("this episode is set in Troy Crust", told)
        self.assertEqual(changes["INSTRUCTIONS"][1][1],
                         "Compare wheel_odometry with visual_odometry in telemetry to estimate slip and the wheel scale together.")
        self.assertEqual(changes["TELEMETRY_DESCRIPTION"], [(
            "wheel_odometry (wheel distance in metres during that tick)",
            "wheel_odometry (commanded wheel metres turned during that tick; `rules` describes the hidden wheel scale)")])
        self.assertTrue(changes["RULES_DESCRIPTION"][0][1].endswith(
            "and under `biome` the rules of the biome this episode is set in, and under `wheels` the rule and the range "
            "of the hidden wheel scale."))
        text = brief(rules)
        for fact in ("## Where this mission is set", "## How far a drive goes", "wheels.wheel_scale",
                     "not M x (1 - slip)", "fall short or overshoot", "Their ratio is wheel_scale x (1 - slip)"):
            self.assertIn(fact, text)
        self.assertNotIn("Where the rover is", text)
        plain = make_overshoot_env(seed=3).rules()
        self.assertEqual(sorted(tool_wording(plain)), ["INSTRUCTIONS", "RULES_DESCRIPTION", "TELEMETRY_DESCRIPTION"])
        self.assertEqual(tool_wording(make_overshoot_env(seed=3, error=0.0).rules()), {})
        self.assertEqual(brief(make_overshoot_env(seed=3, error=0.0).rules()), "")

    def test_a_real_client_is_told_about_the_wheels(self):
        try:
            import asyncio

            import lightlag_mcp.server as stock
            from lightlag_mcp.client import connect
        except ImportError:
            self.skipTest("the mcp package is not installed")
        before = (stock.INSTRUCTIONS, stock.TELEMETRY_DESCRIPTION, stock.RULES_DESCRIPTION)
        service = BiomeEpisodeService(seed=3, profile="rush_noisy", config=Config(delay_ticks=3, max_ticks=50), wheel_error=0.2)
        with connect(build_biome_server(service)) as tools:
            listed = asyncio.run_coroutine_threadsafe(tools._client.list_tools(), tools._loop).result(timeout=30)
            described = {tool.name: tool.description for tool in listed.tools}
            self.assertIn("so a drive can also overshoot", tools._client.instructions)
            self.assertNotIn("to estimate slip. ", tools._client.instructions)
            self.assertIn("commanded wheel metres turned during that tick", described["telemetry_log"])
            self.assertIn("under `wheels`", described["rules"])
            self.assertEqual(tools.rules()["wheels"]["wheel_scale_error"], 0.2)
            POLICIES["kf_mpc"](tools)
        self.assertEqual((stock.INSTRUCTIONS, stock.TELEMETRY_DESCRIPTION, stock.RULES_DESCRIPTION), before)
        direct = play(make_overshoot_env(seed=3, delay=3, profile="rush_noisy", error=0.2)).evaluate()
        self.assertEqual(service.finish()["raw_score"], direct["raw_score"])

    @unittest.skipUnless(HAVE_NUMPY, "the reference needs numpy")
    def test_the_reference_learns_the_wheel_scale_from_todays_telemetry(self):
        from lightlag_dynamic.biomes.nogps_players import navigator, play as play_job, probe
        misses = []
        for seed in range(6):
            env = make_overshoot_env(seed, 3, "rush_noisy")
            controller = navigator()(PublicTools(env))
            controller.run()
            finish(env)
            misses.append(abs(controller.wheel_scale[0] - env.replay()["wheels"]["wheel_scale"]))
            self.assertFalse(controller.beacons, "no beacon on today's telemetry")
        self.assertLess(max(misses), 0.06)
        self.assertLess(sum(misses) / len(misses), 0.035)
        unaware = navigator(("fix", "terrain"))(PublicTools(make_overshoot_env(0, 3, "rush_noisy")))
        unaware.run()
        self.assertIsNone(unaware.pf.g, "without `scale` the wheels are taken at their nominal size")
        row = play_job(("fused", "rush_noisy", 3, 1, "main_mars", None, 0.2))
        self.assertIsNone(row["crash"])
        self.assertEqual(row, play_job(("fused", "rush_noisy", 3, 1, "main_mars", {}, 0.2)))
        rows = probe(["kf_mpc_on_fix"], ["rush_noisy"], [3], [1, 2], 1, wheel_error=0.2)
        expected = [play(make_overshoot_env(seed, 3, "rush_noisy")).evaluate() for seed in (1, 2)]
        self.assertEqual([row["share"] for row in rows], [e["raw_score"] / e["max_available_value"] for e in expected])


if __name__ == "__main__":
    unittest.main()
