"""Manh controllers: naming rules, every controller plays an episode, scenario factors, swarm runner."""

import importlib.util
import re
import tempfile
import unittest
from pathlib import Path

HAVE_NUMPY = importlib.util.find_spec("numpy") is not None
NAME = re.compile(r"^[A-Za-z0-9]+(?:_[A-Za-z0-9]+)*_manh_controller_(\d+)$")


@unittest.skipUnless(HAVE_NUMPY, "the Manh controllers need numpy")
class NamingTest(unittest.TestCase):
    def test_names_numbers_and_records(self):
        from lightlag_dynamic.manh_controllers import controllers as mc
        seen = set()
        for name, spec in mc.REGISTRY.items():
            if spec["kind"] == "team":
                self.assertIsNone(mc.number(name))
                continue
            match = NAME.match(name)
            self.assertIsNotNone(match, name)
            n = int(match.group(1))
            self.assertEqual(mc.number(name), n)
            self.assertNotIn(n, seen, f"number {n} used twice")
            self.assertNotIn(n, mc.RETIRED, f"{name} reuses retired number {n}")
            seen.add(n)
            for field in ("note", "why", "built"):
                self.assertTrue(spec[field], f"{name} has no {field}")
        self.assertTrue(seen.isdisjoint(mc.RETIRED))

    def test_resolve(self):
        from lightlag_dynamic.manh_controllers import swarm
        self.assertEqual(swarm.resolve(["1"]), ["EKF_MPC_manh_controller_1"])
        self.assertIn("Oracle_exact_tight_MPC_manh_controller_16", swarm.resolve(["bound"]))
        self.assertNotIn("blind", swarm.resolve(["manh"]))
        with self.assertRaises(SystemExit):
            swarm.resolve(["9"])  # retired
        with self.assertRaises(SystemExit):
            swarm.resolve(["no_such_controller"])


@unittest.skipUnless(HAVE_NUMPY, "the Manh controllers need numpy")
class EveryControllerPlaysTest(unittest.TestCase):
    def test_one_episode_each(self):
        from lightlag_dynamic.manh_controllers import controllers as mc
        from lightlag_dynamic.manh_controllers.swarm import run_one
        scn = {"name": "default", "profile": "rush_noisy"}
        for name, spec in mc.REGISTRY.items():
            if spec["kind"] == "team":
                continue
            with self.subTest(controller=name):
                row, decisions = run_one((name, scn, 3, 3, True))
                self.assertIsNone(row["crash"], row["crash"])
                self.assertTrue(0.0 <= row["share"] <= 1.0)
                self.assertTrue(row["alive"])
                self.assertIsInstance(row["labels"], list)
                if spec["logged"]:
                    self.assertIsNotNone(row.get("pos_rmse"))
                    self.assertTrue(decisions)


@unittest.skipUnless(HAVE_NUMPY, "the Manh controllers need numpy")
class ScenarioTest(unittest.TestCase):
    def test_windows_store_and_forward(self):
        from lightlag_dynamic.manh_controllers.scenarios import make_env
        env = make_env(1, 3, "noisy", factors={"windows": (10, 3)})
        self.assertEqual(env.rules()["uplink_windows"]["period_ticks"], 10)
        env.advance(4)  # tick 4 is outside the 0..2 window
        ack = env.uplink([{"action": "sample"}])[0]
        self.assertEqual(ack["transmit_tick"], 10)
        self.assertEqual(ack["execute_tick"], 14)

    def test_drive_length_limit(self):
        from lightlag_dynamic.manh_controllers.scenarios import make_env
        env = make_env(1, 3, "noisy", factors={"max_metres": 1.0})
        with self.assertRaises(ValueError):
            env.uplink([{"action": "drive", "heading_deg": 0, "metres": 2.0}])

    def test_turn_cost_spends_energy(self):
        from lightlag_dynamic.manh_controllers.scenarios import make_env
        plain = make_env(1, 0, "noisy")
        costly = make_env(1, 0, "noisy", factors={"turn_cost": 0.03})
        for env in (plain, costly):
            env.uplink([{"action": "drive", "heading_deg": 180, "metres": 1.0}])
            while not env.advance(5)["episode_complete"]:
                pass
        self.assertLess(costly.replay()["states"][-1]["battery"], plain.replay()["states"][-1]["battery"])

    def test_hidden_sand_and_truth_tap(self):
        from lightlag_dynamic.manh_controllers.scenarios import make_env
        env = make_env(2, 3, "noisy", factors={"hidden_patches": 1})
        (x1, y1, x2, y2), = env._world.patches
        self.assertEqual(env.true_terrain((x1 + x2) / 2, (y1 + y2) / 2), "sand")
        self.assertEqual(env.rules(), make_env(2, 3, "noisy").rules())  # the patches are not published
        truth = env.oracle_truth()
        self.assertEqual(set(truth["slip"]), {"bedrock", "sand"})


@unittest.skipUnless(HAVE_NUMPY, "the Manh controllers need numpy")
class SwarmTest(unittest.TestCase):
    def test_run_and_report(self):
        from lightlag_dynamic.manh_controllers import swarm
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            names = swarm.resolve(["1", "17", "blind"])
            rows = swarm.run_suite("base", [0], names, 1, out, quiet=True)
            # bound 17 is played once without delay and counted at every delay
            self.assertEqual(len([r for r in rows if r["controller"].endswith("_17")]), 4 * len(swarm.DELAYS))
            text = swarm.report(out)
            self.assertIn("## Leaderboard", text)
            self.assertTrue((out / "report.md").exists())
            swarm.run_suite("base", [1], swarm.resolve(["1"]), 1, out, append=True, quiet=True)
            merged = swarm.load(out)
            self.assertEqual({r["seed"] for r in merged if r["controller"] == "blind"}, {0})
            self.assertEqual({r["seed"] for r in merged if r["controller"].endswith("_1")}, {1})


if __name__ == "__main__":
    unittest.main()
