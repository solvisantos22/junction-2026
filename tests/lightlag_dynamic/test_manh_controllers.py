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
class LiteratureRoundTest(unittest.TestCase):
    """Controllers 27 and 28 on the development episodes whose traces motivated them (delay 3)."""
    HIDDEN = {"name": "hidden_sand_1", "profile": "noisy", "factors": {"hidden_patches": 1}}

    def _worst_error(self, cls):
        """Largest gap between the filter's position and the truth after any packet."""
        import math

        from lightlag_dynamic.manh_controllers.scenarios import make_env
        from lightlag_dynamic.tools import PublicTools
        seen = []

        class Probe(cls):
            def _filter(self, packet):
                super()._filter(packet)
                seen.append((packet["tick"], self.filter.mean[0], self.filter.mean[1]))

        env = make_env(2, 3, "noisy", factors={"hidden_patches": 1})
        Probe(PublicTools(env)).run()
        while not env.advance(5)["episode_complete"]:
            pass
        states = env.scenario_replay()["states"]
        return max(math.dist((x, y), states[tick]["position"]) for tick, x, y in seen)

    def test_sand_aware_filter_keeps_track_on_hidden_sand(self):
        # Seed 2: the patch lies on the way to the west target. Propagated as bedrock, the drive
        # overshoots and the visual odometry that shows it fails the gate (24: over 1 m off).
        from lightlag_dynamic.manh_controllers import controllers as mc
        self.assertGreater(self._worst_error(mc.EKF_sandodo_stayalive_aimdisc_turncost_window_MPC), 1.0)
        self.assertLess(self._worst_error(mc.EKF_fading_sandfilter_sandodo_guarded_aimdisc_turncost_window_MPC), 0.5)

    def test_guarded_moves_stop_alive(self):
        # Seed 5: the patch is on the last way home. 24 queues the whole leg and dies at base;
        # 27 probes the unverified ground, finds the sand and stops alive with all three samples.
        from lightlag_dynamic.manh_controllers.swarm import resolve, run_one
        n24, n27 = resolve(["24", "27"])
        row24, _ = run_one((n24, self.HIDDEN, 3, 5, False))
        row27, _ = run_one((n27, self.HIDDEN, 3, 5, False))
        self.assertFalse(row24["alive"])
        self.assertTrue(row27["alive"])
        self.assertAlmostEqual(row27["share"], 0.5)

    def test_fading_recovers_after_a_slip_jump(self):
        # Seed 14: after the jump the true slip leaves the published range; without fading the
        # confident filter stops short of base, with it 27 comes home with every target.
        from lightlag_dynamic.manh_controllers.swarm import resolve, run_one
        jump = {"name": "slip_jump", "profile": "noisy", "factors": {"slip_change": "auto"}}
        n24, n27 = resolve(["24", "27"])
        self.assertFalse(run_one((n24, jump, 3, 14, False))[0]["at_base"])
        row27, _ = run_one((n27, jump, 3, 14, False))
        self.assertTrue(row27["alive"] and row27["at_base"])
        self.assertAlmostEqual(row27["share"], 1.0)

    def test_cautious_twin_takes_the_safe_tour(self):
        from lightlag_dynamic.manh_controllers.swarm import resolve, run_one
        row, _ = run_one((resolve(["28"])[0], self.HIDDEN, 3, 5, False))
        self.assertTrue(row["alive"] and row["at_base"])
        self.assertAlmostEqual(row["share"], 0.75)


@unittest.skipUnless(HAVE_NUMPY, "the Manh controllers need numpy")
class ArmedGuardTest(unittest.TestCase):
    """Controller 34: 27's guarded moves, run only when a probe is free (delay 3)."""

    def test_probes_on_the_way_home(self):
        # Hidden-sand seed 5: the patch is on the last way home, where a probe costs no sample.
        # 34 probes there as 27 does and stops alive with all three samples (24 dies at base).
        from lightlag_dynamic.manh_controllers.swarm import resolve, run_one
        row, _ = run_one((resolve(["34"])[0], LiteratureRoundTest.HIDDEN, 3, 5, False))
        self.assertTrue(row["alive"])
        self.assertAlmostEqual(row["share"], 0.5)

    def test_no_probe_when_the_wait_costs_a_target(self):
        # Plain rush, development seed 753: no hidden sand, deadlines, a 50-tick horizon. 27 probes
        # unverified ground, waits a round trip and loses 3 of 11 points; 34 sends the batch under
        # the stay-alive rule and scores what 24 does.
        from lightlag_dynamic.manh_controllers.swarm import resolve, run_one
        scn = {"name": "default", "profile": "rush"}
        n24, n27, n34 = resolve(["24", "27", "34"])
        share = {n: run_one((n, scn, 3, 753, False))[0]["share"] for n in (n24, n27, n34)}
        self.assertAlmostEqual(share[n24], 1.0)
        self.assertLess(share[n27], 0.8)
        self.assertAlmostEqual(share[n34], share[n24])

    def test_mixin_constants_do_not_shadow_each_other(self):
        # A class constant defined by two unrelated mixins of one controller silently takes the
        # value of whichever comes first in the MRO. A draft of 34 replaced _AimDisc.SIGMAS that
        # way and changed where every variant aimed. A subclass overriding its own parent is fine.
        from lightlag_dynamic.manh_controllers import controllers as mc

        def clashes(cls):
            owners = {}
            for klass in cls.__mro__:
                for attr, value in vars(klass).items():
                    if attr.isupper() and not callable(value):
                        owners.setdefault(attr, []).append((klass, value))
            return [(a.__name__, b.__name__, attr) for attr, defs in owners.items()
                    for i, (a, va) in enumerate(defs) for b, vb in defs[i + 1:]
                    if va != vb and not issubclass(a, b)]

        checked = 0
        for name in mc.REGISTRY:
            cls = getattr(mc, name.rpartition("_manh_controller_")[0], None)
            if isinstance(cls, type):
                checked += 1
                self.assertEqual(clashes(cls), [], name)
        self.assertGreaterEqual(checked, 28)

        class Draft(mc._GuardedMove):
            SIGMAS = 3.0

        bad = type("bad", (Draft, mc._AimDisc, mc._Unverified, mc._SandOdometer, mc.EKF_MPC), {})
        self.assertEqual(clashes(bad), [("Draft", "_AimDisc", "SIGMAS")])


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
