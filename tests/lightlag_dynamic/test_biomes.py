"""Selectable biomes: Main Mars is the unchanged environment, and every other biome is published.

Standard library only, except the trial test, which needs numpy; about ten seconds.
"""

import contextlib
import io
import json
import math
from pathlib import Path
import tempfile
import unittest

from lightlag import Config
from lightlag_dynamic.biomes import BIOME_IDS, CATALOG, MAIN, BiomeEnvironment, make_biome_env, parse_biome
from lightlag_dynamic.biomes.__main__ import main as biome_cli
from lightlag_dynamic.biomes.serve import BiomeEpisodeService
from lightlag_dynamic.controllers import POLICIES
from lightlag_dynamic.environment import DynamicEnvironment
from lightlag_dynamic.manh_controllers.mars import MarsEnvironment
from lightlag_dynamic.missions import PROFILES
from lightlag_dynamic.tools import PublicTools

try:
    import numpy  # noqa: F401
    HAVE_NUMPY = True
except ImportError:
    HAVE_NUMPY = False


def play(env, policy=POLICIES["kf_mpc"]):
    policy(PublicTools(env))
    while not env.advance(5)["episode_complete"]:
        pass
    return env


def finish(env):
    while not env.advance(5)["episode_complete"]:
        pass
    return env


def heading(a, b):
    return round(math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 360, 6)


def drive_line(env, start, goal, step=5.0):
    """Uplink straight drives from start toward goal, as many as fit in one batch chain."""
    distance, commands = math.dist(start, goal), []
    while distance > 1e-6:
        metres = min(step, distance)
        commands.append({"action": "drive", "heading_deg": heading(start, goal), "metres": round(metres, 6)})
        distance -= metres
    for i in range(0, len(commands), 5):
        env.uplink(commands[i:i + 5])


class MainMarsTest(unittest.TestCase):
    def test_main_mars_is_the_dynamic_environment(self):
        for profile in ("rush", "rush_noisy", "noisy", "static", "dynamic"):
            for seed in (0, 3):
                with self.subTest(profile=profile, seed=seed):
                    config = Config(delay_ticks=3, max_ticks=PROFILES[profile][4])
                    stock = DynamicEnvironment(seed=seed, config=config, profile=profile)
                    ours = make_biome_env(MAIN, seed, 3, profile)
                    self.assertEqual(ours.rules(), stock.rules())
                    self.assertEqual(ours.map(), stock.map())
                    self.assertEqual(play(ours).replay(), play(stock).replay())

    def test_main_mars_is_the_default_and_cannot_be_mixed(self):
        self.assertEqual(BiomeEnvironment(seed=1).biome_ids, ())
        self.assertNotIn("biome", make_biome_env(seed=1).rules())
        with self.assertRaises(ValueError):
            parse_biome("main_mars+troy_crust")

    def test_private_hooks_this_package_relies_on(self):
        for name in ("_rough_cells", "_snapshot", "_drive", "_announced", "rules", "map", "replay",
                     "scenario_replay"):
            self.assertTrue(callable(getattr(MarsEnvironment, name)), name)
        env = make_biome_env("gale_rock_field", 0, 3, "rush")
        for name in ("_roughness", "_rough", "_spins", "_slip", "_world", "_x", "_y", "_config", "_mission",
                     "factors"):
            self.assertTrue(hasattr(env, name), name)


class CatalogTest(unittest.TestCase):
    def test_every_biome_is_published_in_rules(self):
        self.assertEqual(BIOME_IDS[0], MAIN)
        for biome in BIOME_IDS[1:]:
            with self.subTest(biome=biome):
                rules = make_biome_env(biome, 2, 3, "rush_noisy").rules()
                self.assertEqual([b["id"] for b in rules["biome"]], [biome])
                self.assertEqual(rules["biome"][0]["rule"], CATALOG[biome]["rule"])
                self.assertEqual(rules["biome"][0]["name"], CATALOG[biome]["name"])
                json.dumps(rules)

    def test_choice_errors(self):
        for bad in ("jungle", "", "troy_crust+troy_crust", "gale_rock_field+hidden_valley"):
            with self.subTest(biome=bad), self.assertRaises(ValueError):
                parse_biome(bad)
        with self.assertRaises(ValueError):
            make_biome_env("troy_crust", 0, 3, "rush", settings={"troy_crust": {"softness": 1}})
        with self.assertRaises(ValueError):
            make_biome_env("troy_crust", 0, 3, "rush", settings={"relay_pass": {"period_ticks": 4}})
        with self.assertRaises(ValueError):
            make_biome_env("relay_pass", 0, 3, "rush", factors={"windows": (10, 3)})

    def test_biomes_mix(self):
        env = make_biome_env("troy_crust+relay_pass", 4, 3, "rush_noisy")
        rules, public = env.rules(), env.map()
        self.assertEqual([b["id"] for b in rules["biome"]], ["troy_crust", "relay_pass"])
        self.assertIn("crust", rules)
        self.assertIn("relay_passes", rules)
        self.assertIn("crust_regions", public)
        self.assertEqual(play(env).replay()["biome"]["ids"], ["troy_crust", "relay_pass"])


class RelayPassTest(unittest.TestCase):
    def test_link_is_open_only_during_passes(self):
        env = make_biome_env("relay_pass", 1, 3, "rush_noisy")
        period, open_ = 8, 4
        self.assertEqual(env.rules()["relay_passes"], {"period_ticks": period, "open_ticks": open_})
        self.assertEqual(env.rules()["uplink_windows"]["period_ticks"], period)
        env.advance(5)  # tick 5 is between passes
        ack = env.uplink([{"action": "wait"}])[0]
        self.assertEqual((ack["sent_tick"], ack["transmit_tick"], ack["execute_tick"]), (5, 8, 12))
        finish(env)
        packets = env.telemetry_log()
        self.assertGreater(len(packets), 20)
        for packet in packets[1:]:
            arrival, earliest = packet["received_tick"], packet["tick"] + 3
            self.assertLess(arrival % period, open_)
            self.assertGreaterEqual(arrival, earliest)
            self.assertTrue(all(t % period >= open_ for t in range(earliest, arrival)), "the first open tick")

    def test_a_discovery_is_listed_when_its_packet_arrives(self):
        for seed in range(12):
            env = make_biome_env("relay_pass", seed, 3, "rush")
            found = [p for p in env._mission.plans if p.appear_tick and (p.appear_tick + 3) % 8 >= 4]
            if found:
                break
        plan = found[0]
        arrival = ((plan.appear_tick + 3) // 8 + 1) * 8
        while env.advance(1)["current_tick"] < arrival - 1:
            pass
        self.assertNotIn(plan.id, [t["id"] for t in env.map()["targets"]])
        env.advance(1)
        self.assertIn(plan.id, [t["id"] for t in env.map()["targets"]])

    def test_an_always_open_link_is_main_mars(self):
        always = {"relay_pass": {"period_ticks": 5, "open_ticks": 5}}
        ours = play(make_biome_env("relay_pass", 2, 3, "rush_noisy", settings=always)).replay()
        self.assertEqual(ours["states"], play(make_biome_env(MAIN, 2, 3, "rush_noisy")).replay()["states"])


class HiddenValleyTest(unittest.TestCase):
    def test_limit_follows_the_mission_length(self):
        self.assertEqual(make_biome_env("hidden_valley", 0, 3, "rush_noisy").rules()["onboard_slip_check"]["limit"], 0.40)
        self.assertEqual(make_biome_env("hidden_valley", 0, 3, "noisy").rules()["onboard_slip_check"]["limit"], 0.45)


class TroyCrustTest(unittest.TestCase):
    def test_regions_are_published_and_soft_cells_are_not(self):
        rate, cells, soft = 0.10, 0, 0
        for seed in range(30):
            env = make_biome_env("troy_crust", seed, 3, "rush")
            public, rules = env.map(), env.rules()
            self.assertEqual(rules["crust"]["soft_rate"], rate)
            self.assertEqual(public["crust_regions"], env.crust_regions)
            self.assertNotIn("soft", json.dumps(public))
            bx, by = public["base"]
            inside = set()
            for r in public["crust_regions"]:
                self.assertTrue(all(float(v).is_integer() for v in r.values()), "whole cells")
                gap = math.hypot(max(r["x1"] - bx, 0, bx - r["x2"]), max(r["y1"] - by, 0, by - r["y2"]))
                self.assertGreaterEqual(gap, 1.5)
                inside |= {(x, y) for x in range(int(r["x1"]), int(r["x2"])) for y in range(int(r["y1"]), int(r["y2"]))}
            self.assertTrue(env.soft_cells <= inside)
            cells, soft = cells + len(inside), soft + len(env.soft_cells)
        self.assertAlmostEqual(soft / cells, rate, delta=0.03)

    def test_a_soft_cell_behaves_like_sand_and_shows_in_telemetry(self):
        env = make_biome_env("troy_crust", 3, 0, "rush", settings={"troy_crust": {"soft_rate": 1.0}})
        region = env.crust_regions[0]
        centre = ((region["x1"] + region["x2"]) / 2, (region["y1"] + region["y2"]) / 2)
        self.assertEqual(env.map()["sand"], make_biome_env(MAIN, 3, 0, "rush").map()["sand"], "mapped as before")
        drive_line(env, tuple(env.map()["base"]), centre)
        finish(env)
        packets = env.telemetry_log()
        on_crust = [p for p in packets if region["x1"] < p["position"][0] < region["x2"]
                    and region["y1"] < p["position"][1] < region["y2"]]
        self.assertTrue(on_crust)
        self.assertTrue(all(p["terrain"] == "sand" for p in on_crust))
        # A drive wholly on soft ground slips and costs like sand (the rover is placed there:
        # this part is about the ground only).
        env = make_biome_env("troy_crust", 3, 0, "rush", settings={"troy_crust": {"soft_rate": 1.0}})
        env._x, env._y = centre
        env.uplink([{"action": "drive", "heading_deg": 0.0, "metres": 1.2}])
        finish(env)
        before, after = env.telemetry_log()[:2]
        self.assertEqual(after["terrain"], "sand")
        self.assertAlmostEqual(1 - after["visual_odometry"] / after["wheel_odometry"],
                               env.replay()["slip_coefficients"]["sand"], delta=0.021)
        self.assertAlmostEqual(before["battery"] - after["battery"], 0.5 + 2.0 * 1.2, places=6)

    def test_no_soft_cells_is_main_mars(self):
        firm = {"troy_crust": {"soft_rate": 0.0}}
        ours = play(make_biome_env("troy_crust", 2, 3, "rush_noisy", settings=firm)).replay()
        self.assertEqual(ours["states"], play(make_biome_env(MAIN, 2, 3, "rush_noisy")).replay()["states"])


class GaleRockFieldTest(unittest.TestCase):
    def test_rough_cells_sit_in_the_fields(self):
        for seed in range(8):
            env = make_biome_env("gale_rock_field", seed, 3, "rush")
            public = env.map()
            self.assertEqual(public["rock_fields"], env.rock_fields)
            launch = [(t["x"], t["y"]) for t in public["targets"]] + [tuple(public["base"])]
            for ix, iy in public["rough_cells"]:
                self.assertTrue(any(r["x1"] <= ix < r["x2"] and r["y1"] <= iy < r["y2"] for r in public["rock_fields"]))
                self.assertTrue(all(math.dist((ix + 0.5, iy + 0.5), p) > 1.5 for p in launch))
        self.assertEqual(env.rules()["roughness"]["rough_share_in_fields"], 0.3)
        self.assertEqual(env.rules()["wheel_wear"]["budget_cells"], 4)

    def test_worn_wheels_shorten_drives(self):
        dense = {"gale_rock_field": {"rough_share": 1.0, "budget_cells": 2}}
        env = make_biome_env("gale_rock_field", 1, 0, "rush", settings=dense)
        field = env.rock_fields[0]
        base = tuple(env.map()["base"])
        far = ((field["x1"] + field["x2"]) / 2, (field["y1"] + field["y2"]) / 2)
        drive_line(env, base, far)
        drive_line(env, far, base)
        drive_line(env, base, far)
        finish(env)
        packets = env.telemetry_log()
        wear = [p["wheel_wear"] for p in packets]
        self.assertEqual(wear, sorted(wear))
        self.assertGreater(wear[-1], 2)
        events = [(p["tick"], e) for p in packets for e in p["events"]]
        worn = [t for t, e in events if e["type"] == "wheels_worn"]
        limited = [t for t, e in events if e["type"] == "drive_limited"]
        self.assertEqual(len(worn), 1)
        self.assertTrue(limited and min(limited) > worn[0])
        for p in packets:
            if p["tick"] in limited:
                self.assertLessEqual(p["wheel_odometry"], 2.5 + 1e-9)
        info = env.replay()["biome"]
        self.assertEqual((info["wheel_wear"], info["drives_limited"]), (wear[-1], len(limited)))

    def test_no_rocks_is_main_mars(self):
        smooth = {"gale_rock_field": {"rough_share": 0.0}}
        ours = play(make_biome_env("gale_rock_field", 2, 3, "rush_noisy", settings=smooth)).replay()
        stock = play(make_biome_env(MAIN, 2, 3, "rush_noisy")).replay()
        self.assertEqual([s["position"] for s in ours["states"]], [s["position"] for s in stock["states"]])
        self.assertEqual(ours["result"], stock["result"])


class BagnoldDunesTest(unittest.TestCase):
    def test_faces_cover_the_sand_and_are_published(self):
        env = make_biome_env("bagnold_dunes", 4, 3, "rush")
        public, rules = env.map(), env.rules()
        self.assertEqual(public["sand"], make_biome_env(MAIN, 4, 3, "rush").map()["sand"], "no extra fields by default")
        lo, hi = rules["dune_slip"]["slope_deg"]
        for face in public["dune_faces"]:
            self.assertTrue(lo <= face["slope_deg"] <= hi)
        for patch in public["sand"]:
            area = sum((f["x2"] - f["x1"]) * (f["y2"] - f["y1"]) for f in public["dune_faces"]
                       if patch["x1"] - 1e-6 <= f["x1"] and f["x2"] <= patch["x2"] + 1e-6
                       and patch["y1"] - 1e-6 <= f["y1"] and f["y2"] <= patch["y2"] + 1e-6)
            self.assertGreaterEqual(area + 1e-6, (patch["x2"] - patch["x1"]) * (patch["y2"] - patch["y1"]))
        self.assertNotIn("slip_per_degree", public)
        b_lo, b_hi = rules["dune_slip"]["slip_per_degree"]
        self.assertTrue(b_lo <= env.slip_per_degree <= b_hi)

    def test_slip_grows_with_the_slope(self):
        with_field = {"bagnold_dunes": {"fields": 1, "field_size_m": [6.0, 6.0]}}
        env = make_biome_env("bagnold_dunes", 6, 0, "rush", settings=with_field)
        public = env.map()
        self.assertEqual(len(public["dune_fields"]), 1)
        self.assertIn(public["dune_fields"][0], public["sand"])
        steep = max(public["dune_faces"], key=lambda f: f["slope_deg"])
        # along the face, parallel to its long side, so the whole drive stays on one slope
        wide = (steep["x2"] - steep["x1"]) >= (steep["y2"] - steep["y1"])
        mid = ((steep["x1"] + steep["x2"]) / 2, (steep["y1"] + steep["y2"]) / 2)
        env._x, env._y = mid  # place the rover on the face: this test is about the slip rule only
        env.uplink([{"action": "drive", "heading_deg": 0.0 if wide else 90.0, "metres": 0.5}])
        finish(env)
        packet = next(p for p in env.telemetry_log() if p["wheel_odometry"] > 0)
        replay = env.replay()
        expected = replay["slip_coefficients"]["sand"] + replay["biome"]["slip_per_degree"] * steep["slope_deg"]
        measured = 1 - packet["visual_odometry"] / packet["wheel_odometry"]
        self.assertAlmostEqual(measured, min(0.9, expected), delta=0.021)
        self.assertGreater(steep["slope_deg"], 0)
        self.assertIs(type(replay["slip_coefficients"]), dict)

    def test_flat_dunes_are_main_mars(self):
        flat = {"bagnold_dunes": {"slope_deg": [0.0, 0.0]}}
        ours = play(make_biome_env("bagnold_dunes", 2, 3, "rush_noisy", settings=flat)).replay()
        self.assertEqual(ours["states"], play(make_biome_env(MAIN, 2, 3, "rush_noisy")).replay()["states"])


class MeridianiTest(unittest.TestCase):
    def test_sensing_is_on_and_published_per_terrain(self):
        for profile in ("rush", "rush_noisy"):
            rules = make_biome_env("meridiani_ripples", 0, 3, profile).rules()
            self.assertEqual(rules["sensing"]["visual_odometry_noise_by_terrain"], {"bedrock": 0.03, "sand": 0.2})
            self.assertEqual(rules["sensing"]["position_noise_m"], 0.3)


class EntryPointTest(unittest.TestCase):
    def test_list_and_json_lines_runner(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(biome_cli(["--list"]), 0)
        for biome in BIOME_IDS:
            self.assertIn(f"`{biome}`", out.getvalue())

    def test_service_plays_the_chosen_biome(self):
        with tempfile.TemporaryDirectory() as folder:
            service = BiomeEpisodeService(seed=3, biome="gale_rock_field", profile="rush",
                                          config=Config(delay_ticks=3, max_ticks=50), artifact_dir=folder)
            self.assertEqual(service.rules()["biome"][0]["id"], "gale_rock_field")
            POLICIES["kf_mpc"](service)
            result = service.finish()
            self.assertEqual(result["tick"], 50)
            replay = json.loads(Path(folder, "replay.json").read_text())
            self.assertEqual(replay["biome"]["ids"], ["gale_rock_field"])
        stock = BiomeEpisodeService(seed=3, profile="rush")
        POLICIES["kf_mpc"](stock)
        self.assertEqual(stock.finish()["raw_score"],
                         play(make_biome_env(MAIN, 3, 3, "rush")).evaluate()["raw_score"])


    def test_a_biome_through_a_real_mcp_client(self):
        try:
            from lightlag_mcp.client import connect
            from lightlag_mcp.server import build_server
        except ImportError:
            self.skipTest("the mcp package is not installed")
        service = BiomeEpisodeService(seed=7, biome="troy_crust+relay_pass", profile="rush_noisy",
                                      config=Config(delay_ticks=3, max_ticks=50))
        with connect(build_server(service)) as tools:
            self.assertEqual(sorted(tools.tool_names()), ["advance", "map", "rules", "telemetry_log", "uplink"])
            self.assertEqual([b["id"] for b in tools.rules()["biome"]], ["troy_crust", "relay_pass"])
            self.assertIn("crust_regions", tools.map())
            POLICIES["kf_mpc"](tools)
        direct = play(make_biome_env("troy_crust+relay_pass", 7, 3, "rush_noisy")).evaluate()
        self.assertEqual(service.finish()["raw_score"], direct["raw_score"])


@unittest.skipUnless(HAVE_NUMPY, "the trial plays the Manh controllers, which need numpy")
class TrialTest(unittest.TestCase):
    def test_trial_ranks_controllers_per_biome(self):
        from lightlag_dynamic.biomes import trial
        from lightlag_dynamic.manh_controllers.swarm import resolve
        names = resolve(["1", "24", "blind", "16"])
        with tempfile.TemporaryDirectory() as folder:
            rows = trial.run_trial([MAIN, "troy_crust"], ["rush"], [3], [0, 1], names, 1, folder, quiet=True)
            self.assertEqual(len(rows), 2 * 4 * 2)
            text = trial.report(folder)
            summary = json.loads(Path(folder, "summary.json").read_text())
        self.assertIn("Best controller in each biome", text)
        self.assertEqual(set(summary["best"]), {MAIN, "troy_crust"})
        for biome, best in summary["best"].items():
            self.assertNotIn("Oracle", best["controller"], "bounds are never ranked")
        stock = play(make_biome_env(MAIN, 0, 3, "rush")).evaluate()
        row = next(r for r in rows if r["biome"] == MAIN and r["seed"] == 0 and r["controller"].endswith("_1"))
        self.assertAlmostEqual(row["share"], stock["raw_score"] / stock["max_available_value"])


if __name__ == "__main__":
    unittest.main()
