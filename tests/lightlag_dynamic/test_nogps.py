"""The no-GPS prototype: telemetry without a position fix, and players that work the position out.

The environment tests are standard library only. The player tests need numpy; about ten seconds.
"""

import math
import statistics
import types
import unittest

from lightlag import Config
from lightlag_dynamic.biomes import make_biome_env
from lightlag_dynamic.biomes.nogps import NAVIGATION, WEAK_GPS, NoGpsEnvironment, make_nogps_env
from lightlag_dynamic.biomes.serve import BiomeEpisodeService, build_biome_server
from lightlag_dynamic.biomes.wording import brief, patched, reworded, tool_wording
from lightlag_dynamic.controllers import POLICIES
from lightlag_dynamic.missions import SENSING
from lightlag_dynamic.tools import PublicTools

try:
    import numpy as np
    HAVE_NUMPY = True
except ImportError:
    HAVE_NUMPY = False


def finish(env):
    while not env.advance(5)["episode_complete"]:
        pass
    return env


def play(env, policy):
    policy(PublicTools(env))
    return finish(env)


def drive_out(env, metres=(4.0, 3.0), heading=30.0):
    env.uplink([{"action": "drive", "heading_deg": heading, "metres": m} for m in metres])
    return finish(env)


class EnvironmentTest(unittest.TestCase):
    def test_only_the_briefing_carries_a_position(self):
        env = drive_out(make_nogps_env(seed=3, delay=3, profile="rush_noisy"))
        log = env.telemetry_log()
        self.assertEqual(log[0]["position"], list(env.map()["base"]))
        self.assertEqual((log[0]["beacon_range_m"], log[0]["sun_heading_deg"]), (0.0, None))
        self.assertGreater(len(log), 40)
        for packet in log[1:]:
            self.assertIsNone(packet["position"])
            self.assertGreaterEqual(packet["beacon_range_m"], 0.0)
            self.assertEqual(packet["sun_heading_deg"] is not None, packet["wheel_odometry"] > 0)
        for state in env.replay()["states"]:
            self.assertEqual(len(state["position"]), 2, "the evaluator's truth keeps the true position")

    def test_the_sensors_report_the_truth_plus_the_published_noise(self):
        base = None
        range_errors, compass_errors = [], []
        for seed in range(12):
            env = drive_out(make_nogps_env(seed=seed, delay=0, profile="rush_noisy"), metres=(3.0, 3.0, 2.0), heading=40.0 + 25 * seed)
            replay, log = env.replay(), env.telemetry_log()
            base = replay["world"]["base"]
            errors = {e["tick"]: e["error_deg"] for e in replay["dynamic"]["sensing"]["heading_errors"]}
            commands = {c["execute_tick"]: c["command"] for c in replay["commands"]}
            for packet, state in zip(log[1:], replay["states"][1:]):
                range_errors.append(packet["beacon_range_m"] - math.dist(state["position"], base))
                if packet["sun_heading_deg"] is not None:
                    true = commands[packet["tick"]]["heading_deg"] + errors[packet["tick"]]
                    compass_errors.append((packet["sun_heading_deg"] - true + 180.0) % 360.0 - 180.0)
        self.assertAlmostEqual(statistics.pstdev(range_errors), NAVIGATION["beacon_range_noise_m"], delta=0.05)
        self.assertGreater(len(compass_errors), 20)
        self.assertAlmostEqual(statistics.pstdev(compass_errors), NAVIGATION["sun_compass_noise_deg"], delta=2.0)
        self.assertLess(abs(statistics.mean(compass_errors)), 3.0)

    def test_noiseless_sensors_are_exact(self):
        exact = {"beacon_range_noise_m": 0.0, "sun_compass_noise_deg": 0.0}
        env = drive_out(make_nogps_env(seed=4, delay=0, profile="rush_noisy", navigation=exact))
        replay = env.replay()
        errors = {e["tick"]: e["error_deg"] for e in replay["dynamic"]["sensing"]["heading_errors"]}
        commands = {c["execute_tick"]: c["command"] for c in replay["commands"]}
        for packet, state in zip(env.telemetry_log()[1:], replay["states"][1:]):
            self.assertAlmostEqual(packet["beacon_range_m"], math.dist(state["position"], replay["world"]["base"]), places=5)
            if packet["sun_heading_deg"] is not None:
                true = (commands[packet["tick"]]["heading_deg"] + errors[packet["tick"]]) % 360.0
                self.assertAlmostEqual(packet["sun_heading_deg"], true, places=4)

    def test_the_rules_publish_the_navigation_model(self):
        rules = make_nogps_env(seed=1, delay=3, profile="rush").rules()
        for name, value in NAVIGATION.items():
            self.assertEqual(rules["navigation"][name], value)
        self.assertIn("null", rules["navigation"]["position"])
        self.assertTrue(rules["position_fix"].startswith("none"))
        self.assertNotIn("position_noise_m", rules["sensing"], "no fix, so no fix noise is published")
        self.assertEqual(rules["sensing"]["heading_bias_deg"], NAVIGATION["heading_bias_deg"])
        with self.assertRaises(ValueError):
            make_nogps_env(seed=1, navigation={"gps": True})

    def test_only_telemetry_changes_not_the_rover(self):
        # A player that never reads telemetry drives the same episode with and without the fix.
        sensing = dict(SENSING, heading_bias_deg=NAVIGATION["heading_bias_deg"])
        for seed in (0, 5):
            ours = play(make_nogps_env(seed=seed, delay=3, profile="rush_noisy"), POLICIES["open_loop"]).replay()
            stock = play(make_biome_env("main_mars", seed, 3, "rush_noisy", sensing=sensing), POLICIES["open_loop"]).replay()
            self.assertEqual([s["position"] for s in ours["states"]], [s["position"] for s in stock["states"]])
            self.assertEqual(ours["result"], stock["result"])

    def test_a_weak_gps_puts_a_very_noisy_fix_back(self):
        self.assertEqual(WEAK_GPS["position_noise_m"], 2.0)
        self.assertGreater(WEAK_GPS["position_noise_m"], 5 * SENSING["position_noise_m"], "very noisy next to today's fix")
        errors = []
        for seed in range(6):
            env = finish(make_nogps_env(seed=seed, delay=3, profile="rush_noisy", navigation=WEAK_GPS))
            base = env.map()["base"]
            for packet in env.telemetry_log()[1:]:   # nothing was sent: the rover stands on the base
                errors += [packet["position"][0] - base[0], packet["position"][1] - base[1]]
                self.assertIn("beacon_range_m", packet)
        self.assertAlmostEqual(statistics.pstdev(errors), 2.0, delta=0.25)
        self.assertLess(abs(statistics.mean(errors)), 0.3)
        rules = make_nogps_env(seed=0, navigation=WEAK_GPS).rules()
        self.assertEqual(rules["navigation"]["position_noise_m"], 2.0)
        self.assertEqual(rules["sensing"]["position_noise_m"], 2.0)
        self.assertEqual(rules["navigation"]["sun_compass_noise_deg"], 12.0)
        self.assertNotIn("null", rules["navigation"]["position"])
        self.assertFalse(rules["position_fix"].startswith("none"))
        service = BiomeEpisodeService(seed=3, profile="rush_noisy", config=Config(delay_ticks=0, max_ticks=50), weak_gps=True)
        self.assertEqual(service.rules()["navigation"]["position_noise_m"], 2.0)
        self.assertIsNotNone(service.advance(1)["packets"][0]["position"])

    def test_it_sits_on_any_biome_and_the_entry_points_take_it(self):
        env = make_nogps_env(seed=2, delay=3, profile="rush_noisy", biome="troy_crust")
        self.assertEqual([b["id"] for b in env.rules()["biome"]], ["troy_crust"])
        self.assertIn("navigation", env.rules())
        self.assertIn("crust_regions", env.map())
        service = BiomeEpisodeService(seed=3, profile="rush_noisy", config=Config(delay_ticks=3, max_ticks=50), no_gps=True)
        self.assertIsInstance(service._env, NoGpsEnvironment)
        self.assertIsNone(service.advance(2)["packets"][0]["position"] if service.advance(3)["packets"] else None)
        self.assertEqual(service.finish()["tick"], 50)


@unittest.skipUnless(HAVE_NUMPY, "the players are built on the Manh controllers, which need numpy")
class PlayerTest(unittest.TestCase):
    def test_each_likelihood_pulls_the_particles_the_right_way(self):
        from lightlag_dynamic.biomes.nogps_players import NavParticleFilter
        rules = make_nogps_env(seed=0).rules()
        sand = [{"x1": 30.0, "y1": 0.0, "x2": 40.0, "y2": 40.0}]
        pf = NavParticleFilter(rules, (20.0, 20.0), sand, n=4000, seed=1)
        pf.predict(0.0, 5.0)   # commanded due east; the bias prior is +-15 degrees
        spread = float(np.std(pf.b))
        pf.update_compass(10.0, 3.0)   # the compass says it really drove at 10 degrees
        w = pf.weights()
        self.assertAlmostEqual(math.degrees(float(w @ pf.b)), 10.0, delta=2.5)
        self.assertLess(float(np.sqrt(w @ (pf.b - w @ pf.b) ** 2)), spread / 2)
        pf = NavParticleFilter(rules, (20.0, 20.0), sand, n=4000, seed=1)
        pf.predict(0.0, 5.0)   # on bedrock the rover covers 4.65 to 5 m of it
        radius = np.hypot(pf.x - 20.0, pf.y - 20.0)
        before = float(np.std(radius))
        pf.update_range(4.72, (20.0, 20.0), 0.03)
        w = pf.weights()
        self.assertAlmostEqual(float(w @ radius), 4.72, delta=0.03)
        self.assertLess(float(np.sqrt(w @ (radius - w @ radius) ** 2)), before / 2)
        pf = NavParticleFilter(rules, (29.0, 20.0), sand, n=4000, seed=1)
        pf.predict(0.0, 1.5)   # ends astride the sand edge at x = 30
        pf.update_terrain("sand")
        w = pf.weights()
        self.assertGreater(float(w @ (pf.x >= 30.0)), 0.9)

    def test_dead_reckoning_tools_fill_in_a_position(self):
        from lightlag_dynamic.biomes.nogps_players import DeadReckoningTools
        env = make_nogps_env(seed=6, delay=0, profile="rush_noisy", navigation={"sun_compass_noise_deg": 0.0})
        tools = DeadReckoningTools(PublicTools(env), "compass")
        tools.uplink([{"action": "drive", "heading_deg": 20.0, "metres": 4.0}])
        packets = tools.advance(2)["packets"]
        truth = env._truth[1]["position"]
        self.assertTrue(all(p["position"] is not None for p in packets))
        # an exact compass and a 5% odometer: the reckoned position is within a few decimetres
        self.assertLess(math.dist(packets[0]["position"], truth), 0.5)
        blind = DeadReckoningTools(PublicTools(make_nogps_env(seed=6, delay=0, profile="rush_noisy")), "commanded")
        self.assertEqual(blind.telemetry_log()[0]["position"], list(env.map()["base"]))

    def test_the_fusing_reference_gets_home_and_beats_dead_reckoning(self):
        from lightlag_dynamic.biomes.nogps_players import SENSORS, players, probe
        self.assertEqual(set(players()) >= {"fused", "odometry_only", "dr_commanded", "dr_mean_compass", "blind"}
                         | {f"fused_no_{s}" for s in SENSORS}, True)
        rows = probe(["fused", "dr_commanded", "blind"], ["rush_noisy"], [3], list(range(8)), 1)
        self.assertFalse([r["crash"] for r in rows if r["crash"]])
        mean = {name: statistics.mean(r["share"] for r in rows if r["player"] == name) for name in ("fused", "dr_commanded", "blind")}
        self.assertTrue(all(r["home"] for r in rows if r["player"] == "fused"))
        self.assertGreater(mean["fused"], mean["dr_commanded"] + 0.15)
        self.assertGreater(mean["fused"], mean["blind"] + 0.15)

    def test_with_a_weak_gps_fusing_beats_leaning_on_the_fix(self):
        from lightlag_dynamic.biomes.nogps_players import DeadReckoningTools, default_players, probe
        self.assertIn("kf_mpc_on_fix", default_players(True))
        self.assertNotIn("kf_mpc_on_fix", default_players(False))
        self.assertIn("fused", default_players(False))
        rows = probe(["fused", "fused_no_fix", "kf_mpc_on_fix", "trusts_fix"], ["rush_noisy"], [3], list(range(10)), 1,
                     navigation=dict(WEAK_GPS))
        self.assertFalse([r["crash"] for r in rows if r["crash"]])
        mean = {n: statistics.mean(r["share"] for r in rows if r["player"] == n) for n in {r["player"] for r in rows}}
        self.assertTrue(all(r["home"] for r in rows if r["player"] == "fused"))
        self.assertGreater(mean["fused"], mean["kf_mpc_on_fix"] + 0.1, "the frozen reference leans on the fix alone")
        self.assertGreater(mean["fused"], mean["fused_no_fix"], "the noisy fix is worth something once fused")
        self.assertLess(mean["trusts_fix"], 0.05, "a 2 m fix taken as exact wrecks the mission")
        # the dead-reckoning players ignore the fix: what they hand on is their own estimate
        env = make_nogps_env(seed=1, delay=0, profile="rush_noisy", navigation=WEAK_GPS)
        tools = DeadReckoningTools(PublicTools(env), "commanded")
        raw = PublicTools(env)
        self.assertNotIn("position_noise_m", tools.rules()["sensing"])
        handed = tools.advance(3)["packets"]
        self.assertEqual([p["position"] for p in handed], [list(env.map()["base"])] * 3)
        self.assertNotEqual([p["position"] for p in raw.telemetry_log()[1:4]], [p["position"] for p in handed])

    def test_the_reference_also_plays_with_a_fix(self):
        from lightlag_dynamic.biomes.nogps_players import navigator
        env = make_biome_env("main_mars", 3, 3, "rush_noisy")
        navigator()(PublicTools(env)).run()
        result = finish(env).evaluate()
        self.assertTrue(result["alive"] and result["at_base"])
        self.assertGreater(result["raw_score"], 0)


def service(**kw):
    return BiomeEpisodeService(seed=3, profile="rush_noisy", config=Config(delay_ticks=3, max_ticks=50), **kw)


class WordingTest(unittest.TestCase):
    """What an agent is told about an episode follows that episode's published rules."""

    def test_todays_fix_in_main_mars_changes_no_text(self):
        rules = service()._env.rules()
        self.assertEqual(tool_wording(rules), {})
        self.assertEqual(brief(rules), "")

    def test_the_texts_say_what_telemetry_reports_with_the_published_numbers(self):
        for kw, present, absent in [({"weak_gps": True}, "noise of 2 m per axis", "position is null"),
                                    ({"gps_noise": 1.5}, "noise of 1.5 m per axis", "position is null"),
                                    ({"no_gps": True}, "position is null", "per axis")]:
            rules = service(**kw)._env.rules()
            changes = tool_wording(rules)
            self.assertEqual(sorted(changes), ["INSTRUCTIONS", "RULES_DESCRIPTION", "TELEMETRY_DESCRIPTION"])
            for text in (changes["INSTRUCTIONS"][0][1], brief(rules)):
                self.assertIn(present, text)
                self.assertNotIn(absent, text)
                for field in ("beacon_range_m", "sun_heading_deg", "navigation"):
                    self.assertIn(field, text)
            fields = changes["TELEMETRY_DESCRIPTION"][0][1]
            self.assertIn("beacon_range_m (measured distance to the base), sun_heading_deg", fields)
            self.assertEqual("position (null" in fields, rules["navigation"]["position_noise_m"] is None)
            self.assertIn("## Where the rover is", brief(rules))
            self.assertNotIn("Where this mission is set", brief(rules))

    def test_a_biome_is_pointed_at_and_its_published_rule_is_quoted(self):
        rules = service(biome="troy_crust+relay_pass")._env.rules()
        changes = tool_wording(rules)
        self.assertEqual(sorted(changes), ["INSTRUCTIONS", "MAP_DESCRIPTION", "RULES_DESCRIPTION"])
        self.assertIn("Troy Crust + Relay Pass Schedule", changes["INSTRUCTIONS"][0][1])
        self.assertIn("crust_regions", changes["MAP_DESCRIPTION"][0][1])
        text = brief(rules)
        for entry in rules["biome"]:
            self.assertIn("- {}: {}.".format(entry["name"], entry["rule"]), text)
        self.assertNotIn("Where the rover is", text)
        both = tool_wording(service(biome="troy_crust", weak_gps=True)._env.rules())
        self.assertEqual(sorted(both), ["INSTRUCTIONS", "MAP_DESCRIPTION", "RULES_DESCRIPTION", "TELEMETRY_DESCRIPTION"])
        self.assertIn("under `navigation`", both["RULES_DESCRIPTION"][0][1])
        self.assertIn("under `biome`", both["RULES_DESCRIPTION"][0][1])

    def test_a_change_in_the_stock_wording_fails_loudly_and_swaps_nothing(self):
        rules = service(weak_gps=True)._env.rules()
        moved = types.SimpleNamespace(INSTRUCTIONS="Begin with `rules`.", RULES_DESCRIPTION="and command limits.",
                                      TELEMETRY_DESCRIPTION="position [x, y], heading_deg (commanded heading)")
        with self.assertRaises(RuntimeError):
            reworded(moved, rules)
        with self.assertRaises(RuntimeError):
            with patched(moved, rules):
                self.fail("a server must not be built on half-swapped texts")
        self.assertEqual(moved.TELEMETRY_DESCRIPTION, "position [x, y], heading_deg (commanded heading)")

    def test_a_real_client_is_told_the_truth_and_the_stock_texts_survive(self):
        try:
            import asyncio

            import lightlag_mcp.server as stock
            from lightlag_mcp.client import connect
        except ImportError:
            self.skipTest("the mcp package is not installed")
        names = ("INSTRUCTIONS", "RULES_DESCRIPTION", "MAP_DESCRIPTION", "TELEMETRY_DESCRIPTION")
        before = {name: getattr(stock, name) for name in names}

        def told(episode):
            with connect(build_biome_server(episode)) as tools:
                listed = asyncio.run_coroutine_threadsafe(tools._client.list_tools(), tools._loop).result(timeout=30)
                return tools._client.instructions, {tool.name: tool.description for tool in listed.tools}

        episode = service(biome="troy_crust", weak_gps=True)
        instructions, described = told(episode)
        self.assertEqual(sorted(described), ["advance", "map", "rules", "telemetry_log", "uplink"])
        self.assertIn("this episode is set in Troy Crust", instructions)
        self.assertIn("noise of 2 m per axis", instructions)
        self.assertIn("Start with `rules` and `map`.", instructions)
        self.assertIn("position [x, y] (a noisy fix, see `rules`), beacon_range_m", described["telemetry_log"])
        self.assertNotIn("position [x, y], heading_deg", described["telemetry_log"])
        self.assertIn("crust_regions", described["map"])
        self.assertEqual({name: getattr(stock, name) for name in names}, before, "the swap must not outlive the build")
        self.assertEqual(episode.finish()["tool_calls"], 0, "reading the texts is not a move")
        instructions, described = told(service())
        self.assertEqual(instructions, before["INSTRUCTIONS"])
        self.assertEqual(described["telemetry_log"], before["TELEMETRY_DESCRIPTION"])


if __name__ == "__main__":
    unittest.main()
