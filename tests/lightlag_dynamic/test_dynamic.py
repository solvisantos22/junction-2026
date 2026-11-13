"""Tests for the dynamic-rules pilot. Run from the repository root:

    python3 -m unittest discover -s tests/lightlag_dynamic -v
"""

import ast
import inspect
import json
from pathlib import Path
import subprocess
import sys
import unittest

import lightlag_dynamic  # noqa: E402,F401
from lightlag import Config, Environment  # noqa: E402
from lightlag.model import Target, World  # noqa: E402
from lightlag_dynamic import POLICIES, DynamicEnvironment, Mission, TargetPlan, make_mission, run_episode  # noqa: E402
from lightlag_dynamic import controllers  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]


def mission(plans, targets, profile="dynamic"):
    world = World(sand=(), hazards=(), targets=tuple(targets))
    return Mission(profile, world, tuple(plans))


class HooksStillExist(unittest.TestCase):
    def test_team_simulator_private_hooks(self):
        # The subclass overrides or reads these; fail loudly if the team renames them.
        env = Environment(seed=1)
        for name in ("_sample", "_snapshot", "_spend"):
            self.assertTrue(callable(getattr(env, name)), name)
        for name in ("_tick", "_sampled", "_world", "_config", "_battery", "_x", "_y"):
            self.assertTrue(hasattr(env, name), name)
        self.assertEqual(list(inspect.signature(env._snapshot).parameters), ["wheel", "visual", "events"])


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
