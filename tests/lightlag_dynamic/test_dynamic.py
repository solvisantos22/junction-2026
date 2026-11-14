"""Tests for the dynamic-rules pilot. Run from the repository root:

    python3 -m unittest discover -s tests/lightlag_dynamic -v
"""

import ast
import inspect
import json
import math
from pathlib import Path
import subprocess
import sys
import unittest

import lightlag_dynamic  # noqa: E402,F401
from lightlag import Config, Environment  # noqa: E402
from lightlag.model import Target, World  # noqa: E402
from lightlag_dynamic import POLICIES, DynamicEnvironment, Mission, TargetPlan, make_mission, run_episode  # noqa: E402
from lightlag_dynamic import controllers, kf_mpc  # noqa: E402
from lightlag_dynamic.missions import SENSING  # noqa: E402
from lightlag_dynamic.tools import PublicTools  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]


def mission(plans, targets, profile="dynamic"):
    world = World(sand=(), hazards=(), targets=tuple(targets))
    return Mission(profile, world, tuple(plans))


class HooksStillExist(unittest.TestCase):
    def test_team_simulator_private_hooks(self):
        # The subclass overrides or reads these; fail loudly if the team renames them.
        env = Environment(seed=1)
        for name in ("_sample", "_snapshot", "_spend", "_step", "_drive"):
            self.assertTrue(callable(getattr(env, name)), name)
        for name in ("_tick", "_sampled", "_world", "_config", "_battery", "_x", "_y", "_heading",
                     "_seed", "_pending_packets"):
            self.assertTrue(hasattr(env, name), name)
        self.assertEqual(list(inspect.signature(env._snapshot).parameters), ["wheel", "visual", "events"])
        self.assertEqual(list(inspect.signature(env._drive).parameters), ["command", "events"])

    def test_mcp_service_private_hooks(self):
        # serve.DynamicEpisodeService swaps the episode held in these attributes.
        from lightlag_mcp.service import EpisodeService
        service = EpisodeService(seed=1)
        for name in ("_env", "_max_ticks", "_max_advance"):
            self.assertTrue(hasattr(service, name), name)


class StaticMatchesTeamSimulator(unittest.TestCase):
    def test_same_script_same_result(self):
        script = [[{"action": "drive", "heading_deg": 180, "metres": 5},
                   {"action": "drive", "heading_deg": 180, "metres": 1.2}, {"action": "sample"},
                   {"action": "drive", "heading_deg": 0, "metres": 5},
                   {"action": "drive", "heading_deg": 0, "metres": 1.2}]]
        results = []
        for env in (Environment(seed=7, config=Config(delay_ticks=3)),
                    DynamicEnvironment(seed=7, config=Config(delay_ticks=3), profile="static")):
            for batch in script:
                env.uplink(batch)
            while not env.advance(5)["episode_complete"]:
                pass
            results.append({k: env.evaluate()[k] for k in ("raw_score", "sampled_targets", "alive", "at_base")})
        self.assertEqual(results[0], results[1])


class Windows(unittest.TestCase):
    def test_late_sample_earns_late_fraction(self):
        m = mission([TargetPlan("a", 2.0, deadline_tick=3)], [Target("a", 20, 20, 2.0)])
        on_time = DynamicEnvironment(seed=0, config=Config(delay_ticks=0, max_ticks=10), mission=m)
        on_time.uplink([{"action": "sample"}])  # executes at tick 1
        late = DynamicEnvironment(seed=0, config=Config(delay_ticks=0, max_ticks=10), mission=m)
        late.uplink([{"action": "wait"}] * 4 + [{"action": "sample"}])  # executes at tick 5
        for env in (on_time, late):
            while not env.advance(5)["episode_complete"]:
                pass
        self.assertEqual(on_time.evaluate()["raw_score"], 2.0)
        self.assertEqual(late.evaluate()["raw_score"], 2.0 * m.late_fraction)
        self.assertFalse(late.evaluate()["samples"][0]["on_time"])


class Discoveries(unittest.TestCase):
    def setUp(self):
        self.m = mission([TargetPlan("known", 1.0), TargetPlan("new", 3.0, deadline_tick=30, appear_tick=5)],
                         [Target("known", 10, 10, 1.0), Target("new", 20, 20, 3.0)])

    def test_announced_only_after_delay(self):
        env = DynamicEnvironment(seed=0, config=Config(delay_ticks=3, max_ticks=20), mission=self.m)
        seen_at = None
        for tick in range(1, 12):
            packets = env.advance(1)["packets"]
            ids = [t["id"] for t in env.map()["targets"]]
            found = [e for p in packets for e in p["events"] if e["type"] == "target_discovered"]
            if "new" in ids and seen_at is None:
                seen_at = tick
                self.assertEqual(found[0]["target"]["id"], "new")
            if seen_at is None:
                self.assertEqual(found, [])
        self.assertEqual(seen_at, 5 + 3)

    def test_cannot_sample_before_it_appears(self):
        # The rover starts on top of the future target (base is 20, 20).
        env = DynamicEnvironment(seed=0, config=Config(delay_ticks=0, max_ticks=20), mission=self.m)
        env.uplink([{"action": "sample"}, {"action": "wait"}, {"action": "wait"}, {"action": "wait"},
                    {"action": "wait"}])
        env.uplink([{"action": "sample"}])  # tick 6, after appear tick 5
        while not env.advance(5)["episode_complete"]:
            pass
        events = [e for p in env.telemetry_log() for e in p["events"] if e["type"].startswith("sample")]
        self.assertEqual([e["type"] for e in events], ["sample_failed", "sample_taken"])

    def test_replay_has_full_truth(self):
        env = DynamicEnvironment(seed=0, config=Config(delay_ticks=3, max_ticks=4), mission=self.m)
        while not env.advance(5)["episode_complete"]:
            pass
        replay = env.replay()
        self.assertEqual({t["id"] for t in replay["world"]["targets"]}, {"known", "new"})
        self.assertNotIn("new", [t["id"] for t in env.map()["targets"]])


class Generator(unittest.TestCase):
    def test_deterministic_and_valid(self):
        for profile in ("random", "dynamic", "rush"):
            for seed in range(60):
                a, b = make_mission(profile, seed), make_mission(profile, seed)
                self.assertEqual(a, b)
        self.assertNotEqual(make_mission("rush", 1).world, make_mission("rush", 2).world)

    def test_random_and_dynamic_share_geometry(self):
        for seed in range(20):
            a, b = make_mission("random", seed).world, make_mission("dynamic", seed).world
            self.assertEqual((a.sand, a.hazards), (b.sand, b.hazards))
            self.assertEqual(a.targets, b.targets[:len(a.targets)])


class Controllers(unittest.TestCase):
    def test_controllers_import_no_simulator(self):
        tree = ast.parse(Path(controllers.__file__).read_text())
        imported = {alias.name.split(".")[0] for node in ast.walk(tree)
                    if isinstance(node, (ast.Import, ast.ImportFrom))
                    for alias in getattr(node, "names", [])}
        modules = {node.module.split(".")[0] for node in ast.walk(tree)
                   if isinstance(node, ast.ImportFrom) and node.module}
        self.assertFalse({"lightlag", "lightlag_controllers"} & (imported | modules))

    def test_reference_returns_home_with_science(self):
        for profile in ("static", "windows", "dynamic", "rush"):
            for delay in (0, 3):
                for seed in (0, 1, 2):
                    r = run_episode(POLICIES["reference"], seed, delay, profile)["result"]
                    self.assertTrue(r["alive"] and r["at_base"], (profile, delay, seed))
                    self.assertGreater(r["raw_score"], 0, (profile, delay, seed))

    def test_do_nothing_scores_zero(self):
        for profile in ("static", "rush"):
            self.assertEqual(run_episode(POLICIES["do_nothing"], 3, 3, profile)["result"]["raw_score"], 0)


EAST = [{"action": "drive", "heading_deg": 0, "metres": 5}]


def play(profile, seed, script, delay=0, ticks=12):
    env = DynamicEnvironment(seed=seed, config=Config(delay_ticks=delay, max_ticks=ticks), profile=profile)
    env.uplink(script)
    while not env.advance(5)["episode_complete"]:
        pass
    return env


class NoisySensing(unittest.TestCase):
    def test_noise_model_is_published_only_on_noisy_profiles(self):
        for profile in ("noisy", "rush_noisy"):
            rules = DynamicEnvironment(seed=1, profile=profile).rules()
            self.assertEqual(rules["sensing"], dict(SENSING))
            self.assertIn("position_fix", rules)
        self.assertIsNone(DynamicEnvironment(seed=1, profile="static").rules()["sensing"])

    def test_noisy_profiles_use_the_same_maps(self):
        for seed in (0, 5):
            self.assertEqual(make_mission("noisy", seed).world, make_mission("static", seed).world)
            self.assertEqual(make_mission("rush_noisy", seed).world, make_mission("rush", seed).world)

    def test_truth_is_exact_and_telemetry_is_measured(self):
        env = play("noisy", 3, EAST)
        replay = env.replay()
        truth, received = replay["states"], replay["received_telemetry"]
        self.assertEqual(truth[0]["position"], received[0]["position"])  # exact briefing
        moved = [t for t in range(1, len(truth)) if truth[t]["position"] != received[t]["position"]]
        self.assertEqual(len(moved), len(truth) - 1)  # every later fix is noisy
        self.assertEqual(received[1]["heading_deg"], 0)  # the commanded heading is reported
        self.assertNotEqual(truth[1]["visual_odometry"], received[1]["visual_odometry"])

    def test_heading_drift_moves_the_rover_sideways(self):
        quiet, drifting = play("static", 3, EAST), play("noisy", 3, EAST)
        self.assertEqual(quiet.replay()["states"][-1]["position"][1], 20.0)
        error = drifting.replay()["dynamic"]["sensing"]["heading_errors"][0]["error_deg"]
        dy = drifting.replay()["states"][-1]["position"][1] - 20.0
        self.assertAlmostEqual(math.copysign(1, dy), math.copysign(1, error))
        self.assertGreater(abs(dy), 0.0)

    def test_seeded_and_reproducible(self):
        a, b = play("noisy", 4, EAST), play("noisy", 4, EAST)
        self.assertEqual(a.telemetry_log(), b.telemetry_log())
        self.assertNotEqual(a.telemetry_log(), play("noisy", 5, EAST).telemetry_log())


class Dials(unittest.TestCase):
    def test_noise_level_scales_the_published_model(self):
        rules = DynamicEnvironment(seed=1, profile="noisy", noise_level=1.5).rules()
        self.assertAlmostEqual(rules["sensing"]["position_noise_m"], SENSING["position_noise_m"] * 1.5)
        self.assertEqual(rules["noise_level"], 1.5)
        quiet = play("noisy", 3, EAST, ticks=8)
        silent = DynamicEnvironment(seed=3, config=Config(delay_ticks=0, max_ticks=8), profile="noisy",
                                    noise_level=0.0)
        silent.uplink(EAST)
        while not silent.advance(5)["episode_complete"]:
            pass
        replay = silent.replay()
        self.assertEqual([s["position"] for s in replay["states"]],
                         [s["position"] for s in replay["received_telemetry"]])
        self.assertNotEqual(quiet.telemetry_log(), silent.telemetry_log())

    def test_rough_drive_matches_the_team_drive_without_rough_cells(self):
        for heading, metres in ((0.0, 5.0), (30.0, 5.0), (90.0, 5.0), (200.0, 5.0)):
            a = DynamicEnvironment(seed=3, profile="static", bumpiness=0.5)
            b = DynamicEnvironment(seed=3, profile="static")
            a._rough, a._tick, b._tick = frozenset(), 1, 1
            command = {"action": "drive", "heading_deg": heading, "metres": metres}
            events_a, events_b = [], []
            self.assertEqual(a._drive_rough(dict(command), events_a), Environment._drive(b, dict(command), events_b))
            self.assertEqual((a._x, a._y, a._battery, events_a), (b._x, b._y, b._battery, events_b))

    def test_bumpy_ground_is_published_and_spins_the_wheels(self):
        env = DynamicEnvironment(seed=2, config=Config(delay_ticks=0, max_ticks=12), profile="static",
                                 bumpiness=1.0)
        self.assertTrue(env.map()["rough_cells"])
        self.assertIn("terrain_roughness", env.rules())
        env.uplink([{"action": "drive", "heading_deg": 90, "metres": 5}])
        while not env.advance(5)["episode_complete"]:
            pass
        spins = env.replay()["dynamic"]["roughness"]["spins"]
        self.assertTrue(spins)
        moved = env.replay()["states"][1]
        lost = sum(spin["spin_wheel_m"] for spin in spins)
        self.assertAlmostEqual(moved["wheel_odometry"], 5.0)
        self.assertGreater(lost, 0)
        self.assertLess(moved["visual_odometry"], 5.0 - lost + 1e-6)
        self.assertIsNone(DynamicEnvironment(seed=2, profile="static").rules()["roughness"])


class KalmanMPC(unittest.TestCase):
    def test_imports_no_simulator(self):
        tree = ast.parse(Path(kf_mpc.__file__).read_text())
        modules = {node.module.split(".")[0] for node in ast.walk(tree)
                   if isinstance(node, ast.ImportFrom) and node.module}
        imported = {alias.name.split(".")[0] for node in ast.walk(tree)
                    if isinstance(node, ast.Import) for alias in node.names}
        self.assertFalse({"lightlag", "lightlag_controllers"} & (imported | modules))

    def test_returns_home_with_science_on_every_profile(self):
        for profile in ("static", "noisy", "rush", "rush_noisy"):
            for seed in (0, 1):
                r = run_episode(POLICIES["kf_mpc"], seed, 3, profile)["result"]
                self.assertTrue(r["alive"] and r["at_base"], (profile, seed))
                self.assertGreater(r["raw_score"], 0, (profile, seed))

    def test_filter_tracks_drift_and_slip(self):
        env = DynamicEnvironment(seed=2, config=Config(delay_ticks=3, max_ticks=80), profile="noisy")
        controller = kf_mpc.KalmanMPCController(PublicTools(env))
        controller.run()
        bias = env.replay()["dynamic"]["sensing"]["heading_errors"][-1]["bias_deg"]
        self.assertLess(abs(math.degrees(controller.filter.mean[2]) - bias), 2.0)
        self.assertLess(abs(controller.filter.slip("sand") - env._slip["sand"]), 0.03)

    def test_chance_of_being_inside(self):
        self.assertAlmostEqual(kf_mpc.inside_probability((0, 0), [[1e-8, 0], [0, 1e-8]], (0.5, 0), 0.75), 1.0)
        self.assertEqual(kf_mpc.inside_probability((0, 0), [[1e-8, 0], [0, 1e-8]], (1.0, 0), 0.75), 0.0)
        p = kf_mpc.inside_probability((0, 0), [[0.09, 0], [0, 0.09]], (0, 0), 0.75)
        self.assertAlmostEqual(p, 1 - math.exp(-0.75 ** 2 / (2 * 0.09)), delta=0.04)

    def test_failed_sample_moves_the_estimate_outside(self):
        env = DynamicEnvironment(seed=0, config=Config(delay_ticks=3, max_ticks=80), profile="noisy")
        f = kf_mpc.DriveFilter(env.rules(), (20.0, 20.0))
        f.cov[0][0] = f.cov[1][1] = 0.04  # sure, at 0.2 m, that it is inside a 0.75 m radius
        before = kf_mpc.inside_probability(f.mean[:2], [r[:2] for r in f.cov[:2]], (20.3, 20.0), 0.75)
        f.update_outside((20.3, 20.0), 0.75)
        after = kf_mpc.inside_probability(f.mean[:2], [r[:2] for r in f.cov[:2]], (20.3, 20.0), 0.75)
        self.assertGreater(before, 0.9)
        self.assertLess(after, 0.5)
        self.assertLess(f.mean[0], 20.0)  # pushed away from the target, along the line to it
        self.assertLess(f.cov[0][0], 0.04 + 1e-9)  # an update never adds uncertainty here


class ServedOverMcp(unittest.TestCase):
    def test_service_plays_the_chosen_profile(self):
        from lightlag_dynamic.serve import DynamicEpisodeService
        service = DynamicEpisodeService(seed=7, profile="rush_noisy", config=Config(delay_ticks=3, max_ticks=50))
        self.assertEqual(service.rules()["mission_profile"], "rush_noisy")
        POLICIES["kf_mpc"](service)
        direct = run_episode(POLICIES["kf_mpc"], 7, 3, "rush_noisy")["result"]
        result = service.finish()
        self.assertEqual(result["raw_score"], direct["raw_score"])
        self.assertEqual(result["mission_profile"], "rush_noisy")

    def test_through_a_real_mcp_client(self):
        try:
            from lightlag_mcp.client import connect
            from lightlag_mcp.server import build_server
        except ImportError:
            self.skipTest("the mcp package is not installed")
        from lightlag_dynamic.serve import DynamicEpisodeService
        service = DynamicEpisodeService(seed=7, profile="rush", config=Config(delay_ticks=3, max_ticks=50))
        with connect(build_server(service)) as tools:
            self.assertEqual(sorted(tools.tool_names()), ["advance", "map", "rules", "telemetry_log", "uplink"])
            POLICIES["kf_mpc"](tools)
        direct = run_episode(POLICIES["kf_mpc"], 7, 3, "rush")["result"]
        self.assertEqual(service.finish()["raw_score"], direct["raw_score"])


class ThreeReferences(unittest.TestCase):
    def test_all_three_references_run_on_the_same_episode(self):
        from lightlag_dynamic.compare import REFERENCES, run_compare, summarize
        rows = run_compare(["noisy"], [3], [0], list(REFERENCES))
        self.assertEqual({r["policy"] for r in rows}, set(REFERENCES))
        self.assertEqual(len(summarize(rows)), 3)


class JsonLinesRunner(unittest.TestCase):
    def test_runner_uses_team_dispatch(self):
        lines = "\n".join(json.dumps(r) for r in [
            {"id": 1, "method": "rules"},
            {"id": 2, "method": "evaluate"},
            {"id": 3, "method": "uplink", "params": {"commands": [{"action": "sample"}]}},
            {"id": 4, "method": "advance", "params": {"ticks": 5}},
        ])
        out = subprocess.run([sys.executable, "-B", "-m", "lightlag_dynamic", "--profile", "rush",
                              "--seed", "4"], input=lines, capture_output=True, text=True, cwd=REPO_ROOT,
                             check=True).stdout.splitlines()
        replies = [json.loads(line) for line in out]
        self.assertEqual(replies[0]["result"]["version"], "lightlag-dynamic-v1")
        self.assertFalse(replies[1]["ok"])  # evaluator methods are not dispatchable
        self.assertTrue(replies[2]["ok"] and replies[3]["ok"])


if __name__ == "__main__":
    unittest.main()
