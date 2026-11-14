"""The no-GPS prototype: telemetry without a position fix, and players that work the position out.

The environment tests are standard library only. The player tests need numpy; about thirty seconds.
"""

import hashlib
import json
import math
import statistics
import types
import unittest

from lightlag import Config
from lightlag_dynamic.biomes import make_biome_env
from lightlag_dynamic.biomes.nogps import MANY_SENSORS, NAVIGATION, WEAK_GPS, NoGpsEnvironment, make_nogps_env
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
def find(node, key):
    """The first value stored under `key` anywhere in a nested replay."""
    if isinstance(node, dict):
        if key in node:
            return node[key]
        for value in node.values():
            found = find(value, key)
            if found is not None:
                return found
    return None


def wrap(degrees):
    return (degrees + 180.0) % 360.0 - 180.0


DRIVES = [{"action": "drive", "heading_deg": 30.0, "metres": 4.0}, {"action": "drive", "heading_deg": 75.0, "metres": 3.0},
          {"action": "sample"}, {"action": "drive", "heading_deg": 200.0, "metres": 5.0}]


def fingerprint(**kw):
    """What a player is told and sent in one episode driven by fixed commands."""
    env = make_nogps_env(seed=7, delay=3, **kw)
    env.uplink(DRIVES)
    finish(env)
    blob = json.dumps([env.rules()["navigation"], env.rules()["sensing"], env.map(), env.telemetry_log(),
                       env.replay()["navigation"]], sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


class MoreSensorsTest(unittest.TestCase):
    """More to fuse: several vague beacons, a gyroscope and wheels of a hidden size. All off by default."""

    def test_episodes_without_the_new_settings_are_what_they_were(self):
        # Fingerprints taken from the code as it was before these settings existed (commit 6a5e36a).
        self.assertEqual(fingerprint(profile="rush_noisy"), "84e5f951211fe4b7")
        self.assertEqual(fingerprint(profile="rush_noisy", navigation=dict(WEAK_GPS)), "d63a402e7a4b89f6")
        self.assertEqual(fingerprint(profile="rush_noisy", navigation=dict(WEAK_GPS), biome="troy_crust+relay_pass"),
                         "378ba7a71acc67d7")
        self.assertEqual(fingerprint(profile="noisy", navigation={"position_noise_m": 1.0}), "191ab0014fb63f18")
        packet = drive_out(make_nogps_env(seed=3, delay=0, navigation=WEAK_GPS)).telemetry_log()[2]
        self.assertFalse({"beacon_ranges_m", "gyro_turn_deg"} & set(packet))
        self.assertNotIn("beacons", make_nogps_env(seed=3, navigation=WEAK_GPS).map())

    def test_beacons_are_on_the_map_and_their_ranges_are_the_truth_plus_the_published_noise(self):
        nav = {"beacons": 4, "beacon_range_noise_per_m": 0.1, "beacon_hear_chance": 0.6}
        scaled, heard, total = [], 0, 0
        for seed in range(10):
            env = drive_out(make_nogps_env(seed=seed, delay=0, navigation=nav), metres=(4.0, 4.0, 3.0), heading=20.0 + 33 * seed)
            public, rules, replay, log = env.map(), env.rules(), env.replay(), env.telemetry_log()
            beacons = [(b["x"], b["y"]) for b in public["beacons"]]
            self.assertEqual([b["id"] for b in public["beacons"]], ["base", "beacon_1", "beacon_2", "beacon_3"])
            self.assertEqual(list(beacons[0]), list(public["base"]))
            for beacon in beacons[1:]:
                self.assertTrue(9.0 - 1e-6 <= math.dist(beacon, public["base"]) <= 14.0 + 1e-6)
                self.assertTrue(1.0 <= beacon[0] <= public["width"] - 1.0 and 1.0 <= beacon[1] <= public["height"] - 1.0)
            self.assertEqual({name: rules["navigation"][name] for name in nav}, nav)
            self.assertIn("beacon_ranges_m", rules["navigation"])
            self.assertEqual(log[0]["beacon_ranges_m"], [round(math.dist(beacons[0], b), 6) for b in beacons])
            truth = {state["tick"]: state["position"] for state in replay["states"]}
            for packet in log[1:]:
                self.assertEqual(packet["beacon_range_m"], packet["beacon_ranges_m"][0])
                for beacon, reading in zip(beacons, packet["beacon_ranges_m"]):
                    total += 1
                    if reading is not None:
                        heard += 1
                        distance = math.dist(truth[packet["tick"]], beacon)
                        if distance > 1.0:  # close to a beacon the reading is cut off at zero
                            scaled.append((reading - distance) / (0.25 + 0.1 * distance))
        self.assertAlmostEqual(heard / total, 0.6, delta=0.05)
        self.assertAlmostEqual(statistics.pstdev(scaled), 1.0, delta=0.1)
        self.assertAlmostEqual(statistics.mean(scaled), 0.0, delta=0.1)

    def test_the_gyroscope_reports_the_turn_between_two_executed_drives(self):
        commands = [{"action": "drive", "heading_deg": h, "metres": 2.0} for h in (30.0, 75.0, 350.0)]
        commands.insert(2, {"action": "wait"})
        errors_seen = []
        for noise in (0.0, 2.0):
            for seed in range(12):
                env = make_nogps_env(seed=seed, delay=0, navigation={"gyro_noise_deg": noise})
                env.uplink(commands)
                finish(env)
                log = env.telemetry_log()
                drove = [packet for packet in log if packet["wheel_odometry"] > 0]
                error = {entry["tick"]: entry["error_deg"] for entry in find(env.replay(), "heading_errors")}
                self.assertEqual(len(drove), 3)
                self.assertIsNone(drove[0]["gyro_turn_deg"], "nothing to turn from before the first drive")
                self.assertTrue(all(packet["gyro_turn_deg"] is None for packet in log if packet["wheel_odometry"] == 0))
                for before, after in zip(drove, drove[1:]):
                    turned = wrap((after["heading_deg"] + error[after["tick"]]) - (before["heading_deg"] + error[before["tick"]]))
                    miss = wrap(after["gyro_turn_deg"] - turned)
                    if noise == 0:
                        self.assertAlmostEqual(miss, 0.0, places=4)
                    else:
                        errors_seen.append(miss)
        self.assertAlmostEqual(statistics.pstdev(errors_seen), 2.0, delta=0.6)
        self.assertIn("gyro_turn_deg", make_nogps_env(seed=1, navigation={"gyro_noise_deg": 1.0}).rules()["navigation"])

    def test_wheels_of_a_hidden_size_make_a_drive_fall_short_or_overshoot(self):
        ratios = []
        for seed in range(12):
            plain = make_nogps_env(seed=seed, delay=0, profile="noisy")
            sized = make_nogps_env(seed=seed, delay=0, profile="noisy", navigation={"wheel_scale_error": 0.3})
            ground, spent = [], []
            for env in (plain, sized):
                env.uplink([{"action": "drive", "heading_deg": 180.0, "metres": 3.0}])   # west: bedrock all the way
                finish(env)
                states = env.replay()["states"]
                self.assertEqual((states[1]["terrain"], round(env.telemetry_log()[1]["wheel_odometry"], 9)), ("bedrock", 3.0),
                                 "the odometer counts wheel turns: it reports the commanded metres")
                ground.append(math.dist(states[0]["position"], states[1]["position"]))
                spent.append(states[0]["battery"] - states[1]["battery"])
            scale = sized.replay()["navigation"]["wheel_scale"]
            self.assertTrue(0.7 <= scale <= 1.3)
            self.assertAlmostEqual(ground[1] / ground[0], scale, places=5)
            self.assertEqual(spent[1] > spent[0], scale > 1.0, "the wheels spend energy on the metres they really turn")
            self.assertLessEqual(ground[0], 3.0, "without the setting a drive can only fall short")
            self.assertEqual(sized.rules()["navigation"]["wheel_scale_error"], 0.3)
            self.assertNotIn("wheel_scale", plain.replay()["navigation"])
            self.assertNotIn(str(scale), json.dumps([sized.rules(), sized.map(), sized.telemetry_log()]))
            ratios.append(ground[1] / 3.0)
        self.assertGreater(max(ratios), 1.05, "some rover covers more ground than it was told to")
        self.assertLess(min(ratios), 0.9)

    def test_the_settings_reach_the_published_model_and_bad_ones_are_refused(self):
        rules = make_nogps_env(seed=1, navigation={"heading_walk_deg": 3.0, "heading_wobble_deg": 4.0,
                                                   "visual_odometry_noise": 0.2}).rules()
        self.assertEqual((rules["sensing"]["heading_bias_walk_deg"], rules["sensing"]["heading_noise_deg"],
                          rules["sensing"]["visual_odometry_noise"]), (3.0, 4.0, 0.2))
        many = make_nogps_env(seed=1, navigation=MANY_SENSORS).rules()
        self.assertEqual({name: many["navigation"][name] for name in ("beacons", "gyro_noise_deg", "wheel_scale_error")},
                         {"beacons": 4, "gyro_noise_deg": 1.0, "wheel_scale_error": 0.2})
        self.assertEqual((many["sensing"]["visual_odometry_noise"], many["sensing"]["position_noise_m"]), (0.15, 2.0))
        for bad in ({"beacons": 0}, {"beacons": 9}, {"beacons": 2.5}, {"beacon_hear_chance": 0.0},
                    {"wheel_scale_error": 0.5}, {"gyro_noise_deg": -1.0}, {"beacons": None}, {"lidar": 1}):
            with self.assertRaises(ValueError, msg=bad):
                make_nogps_env(seed=1, navigation=bad)
        service = BiomeEpisodeService(seed=3, profile="rush_noisy", many_sensors=True)
        self.assertEqual(len(service.map()["beacons"]), 4)


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

    def test_crossing_finds_where_the_rings_meet(self):
        from lightlag_dynamic.biomes.nogps_players import crossing
        beacons, rover = [(20.0, 20.0), (12.0, 27.0), (31.0, 24.0), (14.0, 9.0)], (23.5, 17.25)
        ranges = [math.dist(rover, beacon) for beacon in beacons]
        found = crossing(beacons, ranges, [20.0, 20.0], (40.0, 40.0))
        self.assertAlmostEqual(found[0], rover[0], places=5)
        self.assertAlmostEqual(found[1], rover[1], places=5)
        ranges[1] = None  # three rings still cross at one point; a far, vague ring counts for less
        found = crossing(beacons, ranges, [20.0, 20.0], (40.0, 40.0), sigma=0.25, per_m=0.1)
        self.assertAlmostEqual(math.dist(found, rover), 0.0, places=4)

    def test_the_filter_weighs_a_turn_and_learns_the_wheel_scale(self):
        from lightlag_dynamic.biomes.nogps_players import NavParticleFilter
        rules = make_nogps_env(seed=1, navigation={"wheel_scale_error": 0.2, "gyro_noise_deg": 1.0}).rules()
        pf = NavParticleFilter(rules, (20.0, 20.0), [], n=4000, seed=1)
        pf.gyro = True
        pf.learn_scale(0.2)
        pf.predict(0.0, 4.0)
        pf.update_gyro(40.0, 1.0)            # no drive before it: nothing to weigh
        self.assertEqual(float(np.ptp(pf.logw)), 0.0)
        pf.update_visual_odometry(4.0 * 1.15 * 0.975)   # big wheels: more ground than the wheel metres
        scale = 1.0 + float(pf.weights() @ pf.g)
        self.assertAlmostEqual(scale, 1.15, delta=0.04)
        mean, _ = pf.moments()
        self.assertLess(mean[3], 0.0, "the planner is handed a slip below zero: the drive overshoots")
        pf.maybe_resample()
        pf.predict(40.0, 2.0)
        spread = float(np.sqrt(pf.weights() @ (pf.turn - pf.weights() @ pf.turn) ** 2))
        pf.update_gyro(47.0, 1.0)
        turned = math.degrees(float(pf.weights() @ pf.turn))
        self.assertAlmostEqual(turned, 47.0, delta=1.0)
        self.assertLess(float(np.sqrt(pf.weights() @ (pf.turn - pf.weights() @ pf.turn) ** 2)), spread)
        before = (pf.g.copy(), pf.prev_theta.copy())
        self.assertTrue(pf.maybe_resample())
        self.assertEqual((len(pf.g), len(pf.prev_theta)), (4000, 4000))
        self.assertLess(float(pf.g.std()), float(before[0].std()) + 1e-9)

    def test_the_reference_fuses_the_new_readings(self):
        from lightlag_dynamic.biomes.nogps_players import default_players, probe
        names = default_players(True, MANY_SENSORS)
        for name in ("fused_no_gyro", "fused_no_scale", "dr_gyro_compass", "dr_beacons", "kf_mpc_on_crossings"):
            self.assertIn(name, names)
            self.assertNotIn(name, default_players(True, WEAK_GPS))
        rows = probe(["fused", "fused_no_range", "fused_no_scale", "kf_mpc_on_fix", "dr_beacons"], ["rush_noisy"], [3],
                     list(range(10)), 1, navigation=dict(MANY_SENSORS))
        self.assertFalse([r["crash"] for r in rows if r["crash"]])
        mean = {n: statistics.mean(r["share"] for r in rows if r["player"] == n) for n in {r["player"] for r in rows}}
        self.assertGreater(mean["fused"], mean["fused_no_range"] + 0.05, "the beacons are worth something once fused")
        self.assertGreater(mean["fused"], mean["fused_no_scale"] + 0.05, "so is knowing the wheels may be off size")
        self.assertGreater(mean["fused"], mean["kf_mpc_on_fix"] + 0.15, "the frozen reference leans on the fix alone")
        self.assertGreater(mean["fused"], mean["dr_beacons"] + 0.15, "jumping to the rings' crossing is not enough")

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

    def test_more_sensors_are_described_and_the_pushed_texts_are_what_they_were(self):
        rules = service(many_sensors=True, biome="troy_crust")._env.rules()
        changes = tool_wording(rules)
        fields, told, layers = (changes[name][0][1] for name in ("TELEMETRY_DESCRIPTION", "INSTRUCTIONS", "MAP_DESCRIPTION"))
        for field in ("beacon_ranges_m", "gyro_turn_deg", "null when not heard"):
            self.assertIn(field, fields)
        for fact in ("beacon_ranges_m", "gyroscope (gyro_turn_deg)", "navigation.wheel_scale", "can also overshoot"):
            self.assertIn(fact, told)
            self.assertIn(fact, brief(rules))
        self.assertIn("crust_regions", layers)
        self.assertIn("`beacons` lists the radio beacons", layers)
        for words in (told, fields, brief(rules)):   # the hidden values stay hidden
            self.assertNotIn(str(service(many_sensors=True)._env._wheel_scale)[:6], words)

        def texts(**kw):
            told = service(**kw)._env.rules()
            return hashlib.sha256(json.dumps([tool_wording(told), brief(told)], sort_keys=True).encode()).hexdigest()[:16]
        # What a model would be told in the weak-GPS pilot, as pushed in commit 6a5e36a.
        self.assertEqual(texts(weak_gps=True), "bc2f73eb6bfe8bdc")
        self.assertEqual(texts(no_gps=True), "d71921946e408440")
        self.assertEqual(texts(weak_gps=True, biome="troy_crust"), "79eead717a14cde6")

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
