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
class FaultFactorTest(unittest.TestCase):
    def _played(self, profile, factors, **kw):
        from lightlag_dynamic.manh_controllers.scenarios import make_env
        env = make_env(7001, 3, profile, factors=factors, **kw)
        while not env.advance(5)["episode_complete"]:
            pass
        return env

    def test_packet_loss_drops_packets_and_is_published(self):
        env = self._played("rush_noisy", {"packet_loss": {"p": 0.25}})
        lost = {e["tick"] for e in env.fault_events if e["fault"] == "packet_lost"}
        received = {p["tick"] for p in env.telemetry_log()}
        self.assertTrue(lost)
        self.assertIn(0, received)  # the briefing is never lost
        self.assertFalse(lost & received)
        deliverable = set(range(0, 48))  # a packet from tick t arrives at t + 3; the horizon is 50
        self.assertEqual((lost | received) & deliverable, deliverable)
        self.assertEqual(env.rules()["telemetry_packet_loss"]["probability"], 0.25)

    def test_outliers_move_fixes_but_never_exact_telemetry(self):
        clean = {p["tick"]: p["position"] for p in self._played("rush", {}).telemetry_log()}
        env = self._played("rush", {"fix_outliers": {"p": 0.15, "sigma": 3.0}})
        hit = {e["tick"] for e in env.fault_events}
        self.assertTrue(hit)
        moved = {p["tick"] for p in env.telemetry_log() if p["position"] != clean[p["tick"]]}
        self.assertEqual(moved, hit)
        exact = self._played("rush", {"fix_outliers": {"p": 0.15, "sigma": 3.0}}, exact_telemetry=True)
        self.assertEqual(exact.fault_events, [])

    def test_no_factor_no_change(self):
        a = self._played("rush_noisy", {}).replay()
        b = self._played("rush_noisy", {"packet_loss": {"p": 0.0}}).replay()
        self.assertEqual(a["received_telemetry"], b["received_telemetry"])


@unittest.skipUnless(HAVE_NUMPY, "the Manh controllers need numpy")
class GapGateTest(unittest.TestCase):
    """35 = 24 + gap bridging + fix gate. Seed 7001 is a development seed (vault note 23)."""

    def _row(self, number, profile, factors):
        from lightlag_dynamic.manh_controllers.swarm import resolve, run_one
        row, _ = run_one((resolve([number])[0], {"name": "t", "profile": profile, "factors": factors},
                          3, 7001, False))
        return row

    def test_identical_to_24_without_faults(self):
        for profile in ("rush", "rush_noisy"):
            a, b = self._row("24", profile, {}), self._row("35", profile, {})
            for key in ("score", "share", "alive", "at_base", "samples_taken", "battery_end"):
                self.assertEqual(a[key], b[key], (profile, key))

    def test_lost_packets_no_longer_kill(self):
        loss = {"packet_loss": {"p": 0.25}}
        self.assertFalse(self._row("24", "rush_noisy", loss)["alive"])
        row = self._row("35", "rush_noisy", loss)
        self.assertTrue(row["alive"] and row["at_base"])
        self.assertEqual(row["share"], 1.0)

    def test_outlier_fixes_are_held_back(self):
        outliers = {"fix_outliers": {"p": 0.15, "sigma": 3.0}}
        nominal = self._row("35", "rush", {})["share"]
        self.assertLess(self._row("24", "rush", outliers)["share"], nominal - 0.3)
        self.assertEqual(self._row("35", "rush", outliers)["share"], nominal)


@unittest.skipUnless(HAVE_NUMPY, "the Manh controllers need numpy")
class AllInOneTest(unittest.TestCase):
    """Controller 36: 34 on the real-time base of 29, under the Mars layers of 33, with the rules
    read once and the reserve matched to the evidence. Each layer is inactive without its rule."""

    @staticmethod
    def _classes():
        from lightlag_dynamic.manh_controllers import controllers as mc
        name36 = ("EKF_executive_slipaware_latencyaware_fading_sandfilter_sandodo_armedguard_evidencereserve_"
                  "aimdisc_turncost_window_MPC")
        return mc.EKF_fading_sandfilter_sandodo_armedguard_aimdisc_turncost_window_MPC, getattr(mc, name36)

    @staticmethod
    def _commands(cls, env):
        from lightlag_dynamic.tools import PublicTools
        cls(PublicTools(env)).run()
        while not env.advance(5)["episode_complete"]:
            pass
        return env.replay()["commands"]

    def test_with_the_stock_reserve_it_is_34(self):
        # Turn-based and without a slip check, the real-time base, the Mars layers and the rules
        # cache change nothing: with the stock reserve, 34's commands, command for command.
        from lightlag_dynamic.manh_controllers.scenarios import make_env
        c34, c36 = self._classes()
        stock = type("stock_reserve", (c36,), {"RESERVE_CLEAN": 2.0})
        cases = (("rush_noisy", 3, {}), ("noisy", 5, {"hidden_patches": 1}),
                 ("noisy", 1, {"turn_cost": 0.03, "windows": (10, 3)}))
        for profile, seed, factors in cases:
            with self.subTest(profile=profile, seed=seed):
                self.assertEqual(self._commands(stock, make_env(seed, 3, profile, factors=factors)),
                                 self._commands(c34, make_env(seed, 3, profile, factors=factors)))

    def test_reserve_drops_only_while_the_map_is_right(self):
        # Plain noisy, development seed 701: with the stock 2.0 reserve the third target does not
        # fit (34 takes two); with 1.0 it does, and the rover is home with energy left.
        from lightlag_dynamic.manh_controllers.scenarios import make_env
        from lightlag_dynamic.manh_controllers.swarm import resolve, run_one
        from lightlag_dynamic.tools import PublicTools
        scn = {"name": "default", "profile": "noisy"}
        n34, n36 = resolve(["34", "36"])
        row34, _ = run_one((n34, scn, 3, 701, False))
        row36, _ = run_one((n36, scn, 3, 701, False))
        self.assertAlmostEqual(row34["share"], 0.75)
        self.assertAlmostEqual(row36["share"], 1.0)
        self.assertTrue(row36["alive"] and row36["at_base"])
        controller = self._classes()[1](PublicTools(make_env(701, 3, "noisy")))
        self.assertEqual(controller.RESERVE, 1.0)
        controller.unmapped_found = 0.4  # what the battery sand odometer records
        self.assertEqual(controller.RESERVE, 2.0)

    def test_backs_out_under_the_slip_check_like_33(self):
        # Noisy seed 8, slip check 0.40: the sand slips 0.441, so every drive in it trips the check.
        # 34 has no Mars layer and samples nothing; 36 backs out as 33 does.
        from lightlag_dynamic.manh_controllers import controllers as mc
        from lightlag_dynamic.manh_controllers.mars import make_mars_env
        from lightlag_dynamic.tools import PublicTools
        c34, c36 = self._classes()
        c33 = mc.EKF_executive_slipaware_sandodo_stayalive_aimdisc_turncost_window_MPC
        shares = {}
        for name, cls in (("33", c33), ("34", c34), ("36", c36)):
            env = make_mars_env(8, 3, "noisy", factors={"slip_check": {"limit": 0.40}})
            controller = cls(PublicTools(env))
            controller.run()
            while not env.advance(5)["episode_complete"]:
                pass
            result = env.replay()["result"]
            shares[name] = result["raw_score"] / result["max_available_value"]
        self.assertEqual([m[1] for m in controller.mode_log[:2]], ["recover", "nominal"])
        self.assertLess(shares["34"], 0.25)
        self.assertGreaterEqual(shares["36"], shares["33"])
        self.assertGreaterEqual(shares["36"], 0.75)

    def test_on_the_real_time_clock(self):
        # A fake clock on which every tool call costs one tick of thinking (as in test_kf_mpc_rt.py).
        # 36 asks for the rules once and never sends a command too late. Over development seeds 0-5
        # on rush it scores more than 34, which has no real-time base, and more than kf_mpc.
        from lightlag import Config
        from lightlag_dynamic.controllers import POLICIES
        from lightlag_dynamic.realtime import RealTimeEpisodeService
        c34, c36 = self._classes()
        seconds_per_tick = 5.0

        class Clock:
            def __init__(self):
                self.t = 0.0

            def __call__(self):
                return self.t

            def sleep(self, seconds):
                self.t += seconds

        class Thinking:
            def __init__(self, service, clock):
                self.service, self.clock, self.calls = service, clock, {}

            def _call(self, tool, arguments=None):
                self.clock.t += seconds_per_tick
                self.calls[tool] = self.calls.get(tool, 0) + 1
                return self.service.call(tool, arguments)

            def rules(self):
                return self._call("rules")

            def map(self):
                return self._call("map")

            def telemetry_log(self):
                return self._call("telemetry_log")

            def uplink(self, commands):
                return self._call("uplink", {"commands": commands})

            def advance(self, ticks=1):
                return self._call("advance", {"ticks": ticks})

        def play(policy, seed):
            clock = Clock()
            service = RealTimeEpisodeService(seed=seed, seconds_per_tick=seconds_per_tick, clock=clock,
                                             sleep=clock.sleep, profile="rush",
                                             config=Config(delay_ticks=3, max_ticks=50))
            tools = Thinking(service, clock)
            late = False
            try:
                policy(tools)
            except Exception as error:  # without the real-time base a late uplink ends the run
                if "beyond the episode horizon" not in str(error):
                    raise
                late = True
            result = service.finish()
            return result["raw_score"] / result["max_available_value"], tools.calls, late

        totals = {}
        for name, policy in (("kf_mpc", POLICIES["kf_mpc"]), ("34", lambda t: c34(t).run()),
                             ("36", lambda t: c36(t).run())):
            runs = [play(policy, seed) for seed in range(6)]
            totals[name] = sum(share for share, _, _ in runs)
            if name == "36":
                self.assertTrue(all(calls["rules"] == 1 for _, calls, _ in runs))
                self.assertFalse(any(late for _, _, late in runs))
        self.assertGreater(totals["36"], totals["34"])
        self.assertGreater(totals["36"], totals["kf_mpc"])


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
