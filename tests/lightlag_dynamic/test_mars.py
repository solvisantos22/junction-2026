"""Mars-operations tweaks (slip check, downlink passes), the slip-check-aware layer and the executive.

Standard library only; about ten seconds.
"""

import math
import unittest

from lightlag_dynamic.controllers import POLICIES
from lightlag_dynamic.manh_controllers.mars import make_mars_env, policies
from lightlag_dynamic.manh_controllers.scenarios import make_env
from lightlag_dynamic.tools import PublicTools


def play(env, policy=POLICIES["kf_mpc"]):
    policy(PublicTools(env))
    while not env.advance(5)["episode_complete"]:
        pass
    return env


def drive_at_nearest_sand(factors):
    """Seed 0: four full drives from base toward the nearest sand, queued at once."""
    env = make_mars_env(0, 3, "rush_noisy", factors=factors)
    tools = PublicTools(env)
    public, metres = tools.map(), tools.rules()["max_metres_per_drive"]
    bx, by = public["base"]
    centre = min((((r["x1"] + r["x2"]) / 2, (r["y1"] + r["y2"]) / 2) for r in public["sand"]),
                 key=lambda c: math.dist(c, (bx, by)))
    heading = round(math.degrees(math.atan2(centre[1] - by, centre[0] - bx)) % 360, 3)
    tools.uplink([{"action": "drive", "heading_deg": heading, "metres": metres}] * 4)
    while not tools.advance(5)["episode_complete"]:
        pass
    events = [e for p in tools.telemetry_log() for e in p["events"]]
    return env, events


class TweakTest(unittest.TestCase):
    def test_off_is_the_scenario_environment(self):
        for seed in range(4):
            with self.subTest(seed=seed):
                stock = play(make_env(seed, 3, "rush_noisy")).replay()
                self.assertEqual(play(make_mars_env(seed, 3, "rush_noisy")).replay(), stock)
                for inert in ({"slip_check": {"limit": 0.95}}, {"downlink_passes": {"period": 1}}):
                    self.assertEqual(play(make_mars_env(seed, 3, "rush_noisy", factors=inert)).replay()["states"],
                                     stock["states"])

    def test_slip_check_stops_the_drive_and_flushes_the_queue(self):
        env, events = drive_at_nearest_sand({"slip_check": {"limit": 0.25}})
        stops = [e for e in events if e["type"] == "safety_stop"]
        self.assertEqual([e.get("reason") for e in stops], ["slip_limit"])
        self.assertEqual(sum(e["type"] == "command_executed" for e in events), 1, "the other three were discarded")
        self.assertEqual(env.scenario_replay()["scenario"]["slip_trips"], 1)
        _, unchecked = drive_at_nearest_sand({})
        self.assertEqual(sum(e["type"] == "command_executed" for e in unchecked), 4)

    def test_downlink_passes_round_arrivals_up_to_a_pass(self):
        env = play(make_mars_env(1, 3, "rush_noisy", factors={"downlink_passes": {"period": 3}}))
        for packet in env.telemetry_log()[1:]:
            self.assertEqual(packet["received_tick"] % 3, 0)
            self.assertIn(packet["received_tick"] - (packet["tick"] + 3), (0, 1, 2))

    def test_rules_publish_the_tweaks(self):
        env = make_mars_env(0, 3, "rush_noisy", factors={"slip_check": {"limit": 0.4},
                                                         "downlink_passes": {"period": 2}})
        rules = env.rules()
        self.assertEqual(rules["onboard_slip_check"]["limit"], 0.4)
        self.assertEqual(rules["downlink_passes"]["period_ticks"], 2)
        self.assertNotIn("onboard_slip_check", make_mars_env(0, 3, "rush_noisy").rules())
        with self.assertRaises(ValueError):
            make_mars_env(0, 3, "rush_noisy", factors={"dust_storm": {}})


class SlipAwareTest(unittest.TestCase):
    def test_without_a_slip_check_it_is_its_parent(self):
        from lightlag_dynamic.manh_controllers import controllers as zoo
        c1, c24 = zoo.EKF_MPC, zoo.EKF_sandodo_stayalive_aimdisc_turncost_window_MPC
        parents = {"slip_aware_c1": c1, "slip_aware_c24": c24, "executive_c1": c1, "executive_c24": c24}
        self.assertEqual(set(parents), set(policies()))
        for name, cls in policies().items():
            for seed in (0, 5):
                with self.subTest(name=name, seed=seed):
                    ours = play(make_mars_env(seed, 3, "rush_noisy"), lambda t: cls(t).run()).replay()
                    theirs = play(make_mars_env(seed, 3, "rush_noisy"), lambda t: parents[name](t).run()).replay()
                    self.assertEqual(ours["commands"], theirs["commands"])

    def test_trip_chance(self):
        layer = object.__new__(policies()["slip_aware_c1"])
        layer.slip_limit, layer.slip_noise, layer.stops = 0.35, 0.02, {}
        layer.slip_ranges = {"sand": (0.20, 0.45)}
        layer.filter = type("Belief", (), {"slip": lambda self, t: belief[0],
                                           "slip_sigma": lambda self, t: belief[1]})()
        belief = (0.36, 0.0)  # known slip: trips when the drive's noise exceeds -0.01
        self.assertAlmostEqual(layer.trip_chance("sand"), 0.75, delta=0.02)  # to the belief grid's step
        belief = (0.30, 0.0)
        self.assertLess(layer.trip_chance("sand"), 1e-9)
        belief = (0.325, 0.072)  # the prior: a stop raises the chance of the next one
        before = layer.trip_chance("sand")
        layer.stops = {"sand": 1}
        self.assertGreater(layer.trip_chance("sand"), before + 0.2)

    def test_it_stops_driving_into_sand_that_trips_the_check(self):
        # Development seeds, noisy, limit 0.35: controller 1 home 20/40 and 47.8%; with the layer 40/40 and 75.0%.
        layer = policies()["slip_aware_c1"]
        home = {"plain": 0, "aware": 0}
        for seed in range(8):
            for name, policy in (("plain", POLICIES["kf_mpc"]), ("aware", lambda t: layer(t).run())):
                env = play(make_mars_env(seed, 3, "noisy", factors={"slip_check": {"limit": 0.35}}), policy)
                result = env.replay()["result"]
                home[name] += result["alive"] and result["at_base"]
        self.assertGreater(home["aware"], home["plain"])


class ExecutiveTest(unittest.TestCase):
    def test_backs_out_of_sand_that_stops_every_drive(self):
        # Noisy seed 8, limit 0.40: sand slip 0.441, so every drive in it trips the check. The layer
        # alone crawls along the edge (12 stops, nothing sampled); the executive backs out.
        layer, executive = policies()["slip_aware_c24"], policies()["executive_c24"]
        shares = {}
        for name, cls in (("layer", layer), ("executive", executive)):
            env = make_mars_env(8, 3, "noisy", factors={"slip_check": {"limit": 0.40}})
            controller = cls(PublicTools(env))
            controller.run()
            while not env.advance(5)["episode_complete"]:
                pass
            result = env.replay()["result"]
            shares[name] = result["raw_score"] / result["max_available_value"]
        self.assertEqual([m[1] for m in controller.mode_log[:2]], ["recover", "nominal"])
        backouts = [a for a in controller.acks if a["command"]["action"] == "drive"
                    and a["command"]["metres"] == controller.segment]
        self.assertGreaterEqual(len(backouts), 2)
        self.assertTrue(all(a["command_id"] not in controller.cancelled for a in backouts),
                        "each back-out was sent after the one before it executed, so no stop discarded it")
        self.assertTrue(all(b["sent_tick"] >= a["execute_tick"] for a, b in zip(backouts, backouts[1:])))
        self.assertGreater(shares["executive"], shares["layer"])

    def _bare(self):
        controller = object.__new__(policies()["executive_c1"])
        controller.slip_limit, controller.slip_noise, controller.segment, controller.k = 0.40, 0.02, 0.1, 3
        controller.slip_ranges = {"bedrock": (0.0, 0.05), "sand": (0.20, 0.45)}
        controller.sand = [{"x1": 23.0, "y1": 15.0, "x2": 26.0, "y2": 25.0}]
        controller.filter = type("F", (), {"mean": [23.4, 20.0, 0.0, 0.03, 0.44],
                                           "cov": [[0.01, 0], [0, 0.01]],
                                           "slip": lambda self, t: 0.44, "slip_sigma": lambda self, t: 0.0})()
        controller.slip = lambda terrain: 0.44
        controller.stops = {}
        return controller

    def test_way_out(self):
        controller = self._bare()
        controller.packets = [{"terrain": "bedrock"}, {"terrain": "sand"}]
        self.assertEqual(controller._way_out({"terrain": "sand"}, 0.0), (180.0, 2), "started outside: own tracks")
        controller.packets = [{"terrain": "sand"}, {"terrain": "sand"}]
        heading, steps = controller._way_out({"terrain": "sand"}, 90.0)  # drove along the edge
        self.assertEqual(heading, 180.0)  # out through the nearest edge, x = 23, not back along the edge
        self.assertEqual(steps, 9)  # (0.4 m inside + 0.1 m position sigma) / 0.056 m per step

    def test_drops_targets_only_with_evidence(self):
        controller = self._bare()
        controller.filter.slip_sigma = lambda t: 0.07  # the prior: nothing seen on sand yet
        self.assertFalse(controller._drops("sand", 0.9))
        controller.stops = {"sand": 1}
        self.assertTrue(controller._drops("sand", 0.9))
        self.assertFalse(controller._drops("sand", 0.1))


if __name__ == "__main__":
    unittest.main()
