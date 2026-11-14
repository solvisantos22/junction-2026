"""The max env: lost packets and wild position fixes inside the biomes, the preset itself, and the
controller written for it.

The environment tests are standard library only. The controller tests need numpy; about five
seconds in all.
"""

import copy
import json
import types
import unittest

from lightlag_dynamic.biomes import make_biome_env
from lightlag_dynamic.biomes.maxenv import MAX_BIOME, MAX_FACTORS, make_max_env
from lightlag_dynamic.biomes.nogps import MANY_SENSORS, WEAK_GPS, make_nogps_env
from lightlag_dynamic.controllers import POLICIES
from lightlag_dynamic.manh_controllers.mars import make_mars_env
from lightlag_dynamic.tools import PublicTools

try:
    import numpy  # noqa: F401
    HAVE_NUMPY = True
except ImportError:
    HAVE_NUMPY = False

FAULTS = {"packet_loss": {"p": 0.25}, "fix_outliers": {"p": 0.15, "sigma": 3.0}}


def finish(env):
    while not env.advance(5)["episode_complete"]:
        pass
    return env


def play(env, policy=POLICIES["kf_mpc"]):
    policy(PublicTools(env))
    return finish(env)


def everything(env):
    return json.dumps([env.rules(), env.map(), env.telemetry_log(), env.replay(), env.fault_events], sort_keys=True)


class FaultsInsideBiomesTest(unittest.TestCase):
    def test_in_main_mars_they_are_the_labs_faults(self):
        for profile in ("rush", "rush_noisy"):
            here = play(make_biome_env("main_mars", 4, 3, profile, factors=copy.deepcopy(FAULTS)))
            lab = play(make_mars_env(4, 3, profile, factors=copy.deepcopy(FAULTS)))
            self.assertEqual(everything(here), everything(lab), profile)
            self.assertEqual({e["fault"] for e in lab.fault_events}, {"packet_lost", "fix_outlier"})

    def test_in_the_max_env_they_change_the_packets_and_nothing_else(self):
        calm = {name: value for name, value in MAX_FACTORS.items() if name not in FAULTS}
        seen = set()
        for seed in range(3):
            on = play(make_max_env(seed, 3), POLICIES["open_loop"])
            off = play(make_nogps_env(seed=seed, delay=3, profile="rush_noisy", biome=MAX_BIOME,
                                      navigation=MANY_SENSORS, factors=copy.deepcopy(calm)), POLICIES["open_loop"])
            self.assertEqual(on.replay()["states"], off.replay()["states"], "the same rover, tick for tick")
            lost = {e["tick"] for e in on.fault_events if e["fault"] == "packet_lost"}
            wild = {e["tick"] for e in on.fault_events if e["fault"] == "fix_outlier"} - lost
            mine = {p["tick"]: p for p in on.telemetry_log()}
            theirs = {p["tick"]: p for p in off.telemetry_log()}
            self.assertEqual(set(theirs) - set(mine), lost & set(theirs), "only the lost packets are missing")
            self.assertLessEqual(set(mine), set(theirs))
            for tick, packet in mine.items():
                if tick in wild:
                    self.assertNotEqual(packet["position"], theirs[tick]["position"])
                    self.assertEqual(dict(packet, position=None), dict(theirs[tick], position=None))
                else:
                    self.assertEqual(packet, theirs[tick])
                if tick > 0:
                    self.assertLess(packet["received_tick"] % 8, 4, "a packet still arrives while a pass is open")
            seen |= {"lost"} if lost & set(theirs) else set()
            seen |= {"wild"} if wild & set(mine) else set()
        self.assertEqual(seen, {"lost", "wild"})

    def test_a_wild_fix_needs_a_fix(self):
        with self.assertRaises(ValueError):
            make_nogps_env(seed=1, factors={"fix_outliers": {"p": 0.1, "sigma": 3.0}})   # no position fix at all
        make_nogps_env(seed=1, factors={"packet_loss": {"p": 0.1}})
        make_nogps_env(seed=1, navigation=WEAK_GPS, factors={"fix_outliers": {"p": 0.1, "sigma": 3.0}})


class MaxEnvTest(unittest.TestCase):
    def test_the_preset_switches_on_what_it_says(self):
        rules = make_max_env(seed=2).rules()
        self.assertEqual([b["id"] for b in rules["biome"]], MAX_BIOME.split("+"))
        self.assertEqual(rules["mission_profile"], "rush_noisy")
        self.assertEqual((rules["max_ticks"], rules["delay_ticks"]), (50, 3))
        self.assertEqual(rules["onboard_slip_check"]["limit"], 0.40)
        self.assertEqual(rules["relay_passes"], {"period_ticks": 8, "open_ticks": 4})
        nav = rules["navigation"]
        self.assertEqual((nav["position_noise_m"], nav["beacons"], nav["gyro_noise_deg"], nav["wheel_scale_error"]),
                         (2.0, 4, 1.0, 0.2))
        self.assertEqual((rules["turn_cost_per_degree"], rules["max_metres_per_drive"]), (0.01, 2.0))
        self.assertEqual(rules["telemetry_packet_loss"]["probability"], 0.10)
        self.assertEqual((rules["position_fix_outliers"]["probability"], rules["position_fix_outliers"]["sigma_m"]),
                         (0.05, 3.0))
        rocks = make_max_env(seed=2, rocks=True).rules()
        self.assertEqual([b["id"] for b in rocks["biome"]],
                         ["relay_pass", "gale_rock_field", "bagnold_dunes", "troy_crust", "meridiani_ripples"])
        self.assertNotIn("onboard_slip_check", rocks)
        self.assertEqual(MAX_FACTORS["packet_loss"], {"p": 0.10}, "the preset is not changed by an episode")

    def test_scripted_players_finish_it(self):
        for name in ("kf_mpc", "open_loop"):
            for rocks in (False, True):
                result = play(make_max_env(seed=1, delay=3, rocks=rocks), POLICIES[name]).evaluate()
                self.assertEqual(result["tick"], 50, name)


def navigate(seed, **knobs):
    from lightlag_dynamic.biomes.max_players import max_navigator
    env = make_max_env(seed=seed, delay=3)
    controller = max_navigator(**knobs)(PublicTools(env))
    controller.run()
    return controller, finish(env)


@unittest.skipUnless(HAVE_NUMPY, "the controller is built on the Manh controllers, which need numpy")
class MaxNavigatorTest(unittest.TestCase):
    def test_it_reads_the_wheel_scale_off_the_battery(self):
        for seed in (1, 3):   # wheels 16% big and 4% small
            controller, env = navigate(seed)
            tick, scale = controller.scale_from_battery
            self.assertAlmostEqual(scale, env._wheel_scale, places=6)
            self.assertLess(tick, 10)
            self.assertTrue(all(abs(g - (scale - 1.0)) < 1e-12 for g in controller.pf.g), "every particle takes it")

    def test_it_bridges_lost_packets(self):
        controller, env = navigate(3)
        self.assertTrue(any(e["fault"] == "packet_lost" for e in env.fault_events))
        self.assertGreater(controller.bridged, 0)
        self.assertEqual(navigate(3, BRIDGE=False)[0].bridged, 0)

    def test_trip_chances_come_from_the_true_slip_and_dunes_trip(self):
        controller, env = navigate(5)   # wheels 20% big: the effective bedrock slip is below zero
        self.assertLess(controller.filter.slip("bedrock"), -0.1)
        self.assertEqual(controller.trip_chance("bedrock"), 0.0, "bedrock never trips a 0.40 check")
        self.assertGreaterEqual(controller.trip_chance("sand"), 0.9, "the map has dune faces")
        # Once the filter is sure of the effective slip, the base rule reads it as a true slip
        # far outside the published range: a stop the belief ruled out, so bedrock "always trips".
        i = controller.filter.index["bedrock"]
        controller.filter.cov[i][i] = 0.003 ** 2
        self.assertEqual(controller.trip_chance("bedrock"), 0.0)
        controller.RAW_TRIP = False
        self.assertEqual(controller.trip_chance("bedrock"), 1.0, "the base rule on the effective slip")

    def test_it_finishes_with_and_without_37s_layers(self):
        for layers in (True, False):
            for seed in (0, 2):
                controller, env = navigate(seed, layers=layers)
                result = env.evaluate()
                self.assertEqual(result["tick"], 50)
                self.assertTrue(result["alive"], (layers, seed))
                if layers:
                    self.assertGreater(result["raw_score"], 0.0, seed)

    def test_every_leg_ends_with_a_sample_attempt(self):
        controller, _ = navigate(0)
        unsure = types.SimpleNamespace(uncertainty=5.0)   # lands inside the 0.75 m radius about 1% of the time
        self.assertFalse(controller.needs_confirmation(unsure))
        controller.COMMIT_BELOW = None
        self.assertTrue(controller.needs_confirmation(unsure), "the base rule waits to see it land")

    def test_the_hook_for_another_filter_changes_nothing(self):
        from lightlag_dynamic.biomes.nogps_players import navigator
        calls = []

        class Recorded(navigator()):
            def _made_pf(self, rules):
                calls.append(self.tick)

        runs = []
        for cls in (navigator(), Recorded):
            env = make_nogps_env(seed=2, delay=3, profile="rush_noisy", navigation=MANY_SENSORS)
            cls(PublicTools(env)).run()
            runs.append(finish(env).replay()["commands"])
        self.assertEqual(runs[0], runs[1])
        self.assertEqual(len(calls), 1, "called once, when the filter is made")

    def test_the_runner_compares_players_on_the_same_seeds(self):
        from lightlag_dynamic.biomes.max_check import episode, seed_range, table
        self.assertEqual(seed_range("1-2,7"), [1, 2, 7])
        rows = [episode((name, seed, 3)) for name in ("max_navigator", "blind") for seed in (0, 1)]
        self.assertEqual([(r["player"], r["seed"], r["crash"]) for r in rows],
                         [("max_navigator", 0, None), ("max_navigator", 1, None), ("blind", 0, None), ("blind", 1, None)])
        text = table(rows)
        self.assertIn("max_navigator - blind", text)
        self.assertEqual(len(text.splitlines()), 2)


if __name__ == "__main__":
    unittest.main()
