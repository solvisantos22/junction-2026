"""Public belief/queue accounting, fair controls, and continuous v2 integration."""

import ast
from copy import deepcopy
import inspect
import math
import unittest
from unittest.mock import patch

from lightlag import Config, Environment
from lightlag.model import Rect, World
from lightlag_dynamic.controllers import Leg
from lightlag_dynamic.kf_mpc import KalmanMPCController
from lightlag_dynamic.environment import DynamicEnvironment
from lightlag_dynamic.tools import PublicTools
from lightlag_expedition.environment import ExpeditionEnvironment
from lightlag_expedition import reference_v2
from lightlag_expedition.reference_v2 import ExpeditionControllerV2, run_policy


class Fixture:
    def __init__(self):
        source = DynamicEnvironment(seed=0, config=Config(max_ticks=60, delay_ticks=3))
        self.briefing = source.rules()
        self.briefing["science"] = {
            "regions": {region: {"prior_rich": .5} for region in ("r1", "r2", "r3")},
            "quality_multipliers": {"poor": .2, "rich": 1.0}, "inspection_budget": 2,
            "inspection_energy": 2., "inspection_accuracy": .9,
            "inspection_reserved_regions": [], "visibility": "hidden"}
        self.packet = source.telemetry_log()[0]
        self.public_map = {"width": 40, "height": 40, "base": [20, 20], "sand": [],
                           "hazards": [], "targets": [
                               {"id": "t1", "x": 20, "y": 20, "region": "r1",
                                "value": 2, "base_value": 2, "deadline_tick": 40},
                               {"id": "t2", "x": 21, "y": 20, "region": "r1",
                                "value": 2, "base_value": 2, "deadline_tick": 40}]}
        self.sent = []

    def rules(self):
        return deepcopy(self.briefing)

    def map(self):
        return deepcopy(self.public_map)

    def telemetry_log(self):
        return [deepcopy(self.packet)]

    def uplink(self, commands):
        first = max(4, max((ack["execute_tick"] for ack in self.sent), default=0) + 1)
        result = [{"command_id": len(self.sent) + index + 1, "sent_tick": 0,
                   "execute_tick": first + index, "command": deepcopy(command)}
                  for index, command in enumerate(commands)]
        self.sent.extend(result)
        return deepcopy(result)


class BeliefAndQueue(unittest.TestCase):
    def test_pending_sample_is_intention_not_success_or_quality(self):
        c = ExpeditionControllerV2(Fixture())
        c.send([{"action": "sample"}, {"action": "inspect", "region": "r2"}])
        c._sample_intents[c.acks[0]["command_id"]] = "t1"
        state = c.predict(6)
        self.assertEqual(state["sampled"], set())
        self.assertEqual(state["pending_samples"], {"t1"})
        self.assertEqual(c.beliefs["r1"], .5)
        self.assertNotIn("r1", c._available(state))
        self.assertNotIn("r2", c._available(state))
        # Tick1..5 idle, sample3, inspect2; no cost is silently omitted.
        self.assertEqual(state["battery"], 100 - 5 * .5 - 3 - 2)

    def test_cancelled_prefix_does_not_reveal_or_cost_but_probe_stays_reserved(self):
        c = ExpeditionControllerV2(Fixture())
        c.send([{"action": "sample"}, {"action": "inspect", "region": "r2"}])
        c._sample_intents[c.acks[0]["command_id"]] = "t1"
        c.cancelled.update(ack["command_id"] for ack in c.acks)
        state = c.predict(6)
        self.assertEqual(state["pending_samples"], set())
        self.assertEqual(state["sampled"], set())
        self.assertEqual(state["battery"], 100 - 5 * .5)
        self.assertEqual(c._requested_regions(), {"r2"})
        self.assertEqual(c.beliefs["r1"], .5)

    def test_failure_preserves_prior_delivered_quality_updates_it(self):
        c = ExpeditionControllerV2(Fixture())
        packet = deepcopy(c.packets[-1])
        packet.update(tick=4, events=[{"type": "sample_failed", "reason": "no_unsampled_target_in_range"}])
        c.absorb(packet)
        self.assertEqual(c.beliefs["r1"], .5)
        packet = deepcopy(packet)
        packet.update(tick=5, sampled_targets=["t1"], events=[
            {"type": "sample_taken", "target_id": "t1", "on_time": True},
            {"type": "region_quality", "region": "r1", "quality": "poor", "target_id": "t1"}])
        c.absorb(packet)
        self.assertEqual(c.beliefs["r1"], 0)
        self.assertEqual(c.predict(6)["sampled"], {"t1"})

    def test_sample_failure_and_exact_revelation_have_correct_branch_mass(self):
        c = ExpeditionControllerV2(Fixture())
        state = c.predict(4)
        prefix = {"target": c.targets["t1"], "commands": [{"action": "sample"}],
                  "energy": 3, "chance": .5, "position": (20, 20), "cov": state["cov"],
                  "sample_tick": 4}
        branches = []

        def fake_pool(branch_state, slot, depth):
            return set(branch_state["sampled"]), depth

        def fake_best(pool, beliefs):
            branches.append((pool, dict(beliefs)))
            return None, max(6, 10 * (.2 + .8 * beliefs["r1"]))

        with patch.object(c, "_pool", side_effect=fake_pool), patch.object(c, "_best", side_effect=fake_best):
            option = c._evaluate(state, 4, (), prefix)
        # Fail .5*6; poor success .25*(.4+6); rich success .25*(2+10).
        self.assertAlmostEqual(option["value"], 7.6)
        self.assertEqual([(pool[0], b["r1"]) for pool, b in branches],
                         [(set(), .5), ({"t1"}, 0.), ({"t1"}, 1.)])
        self.assertTrue(all(pool[1] == 3 for pool, _ in branches))
        self.assertEqual(c.beliefs["r1"], .5)
        self.assertEqual(state["sampled"], set())

    def test_two_signal_branches_integrate_to_one_without_changing_real_beliefs(self):
        c = ExpeditionControllerV2(Fixture())
        c.beliefs.update(r2=.35, r3=.6)
        original = dict(c.beliefs)
        branches = c._signal_branches(c.beliefs, ("r2", "r3"))
        self.assertEqual(len(branches), 4)
        self.assertAlmostEqual(sum(mass for mass, _ in branches), 1)
        for region in ("r2", "r3"):
            self.assertAlmostEqual(sum(mass * beliefs[region] for mass, beliefs in branches), original[region])
        self.assertEqual(c.beliefs, original)

    def test_prefix_timing_idle_and_probe_cost_include_both_delays(self):
        c = ExpeditionControllerV2(Fixture())
        state = c.predict(4)
        prefix = {"target": c.targets["t1"], "commands": [
            {"action": "drive", "heading_deg": 0, "metres": .1},
            {"action": "drive", "heading_deg": 180, "metres": .1}, {"action": "sample"}],
                  "energy": 3.2, "chance": 1., "position": (20, 20), "cov": state["cov"],
                  "sample_tick": 6}
        captured = []
        original = c._pool

        def record(branch_state, slot, depth):
            captured.append((branch_state["tick"], branch_state["battery"], slot, depth))
            return original(branch_state, slot, depth)

        with patch.object(c, "_pool", side_effect=record):
            option = c._evaluate(state, 4, ("r2", "r3"), prefix)
        self.assertEqual(option["next_slot"], 15)
        self.assertTrue(all(item == (14, 85.8, 15, 3) for item in captured))
        self.assertEqual(len(option["commands"]), 5)

    def test_send_chunks_long_prefix_and_keeps_confirmable_fifo_slots(self):
        tools = Fixture()
        c = ExpeditionControllerV2(tools)
        commands = [{"action": "wait"}] * 4 + [{"action": "sample"},
                    {"action": "inspect", "region": "r2"}, {"action": "inspect", "region": "r3"}]
        c.send(commands)
        self.assertEqual([ack["execute_tick"] for ack in c.acks], list(range(4, 11)))
        self.assertEqual(c.reserved_until(), 10)


class RoutePoolsAndControls(unittest.TestCase):
    def controller(self, mode="reference", fixed_pair=None):
        return ExpeditionControllerV2(PublicTools(ExpeditionEnvironment(seed=101, mission_seed=1)),
                                      mode=mode, fixed_pair=fixed_pair)

    def test_pool_reuses_routes_across_beliefs_and_horizon_stays_four(self):
        c = self.controller()
        state = c.predict(4)
        c._reset_planning(state)
        pool = c._pool(state, 4)
        self.assertTrue(pool.routes)
        self.assertTrue(all(len(route.target_ids) <= 4 for route in pool.routes))
        count = len(c._v2_geometry)
        for region in c.regions:
            beliefs = dict(c.beliefs, **{region: 0.0})
            c._best(pool, beliefs)
        self.assertEqual(len(c._v2_geometry), count)
        self.assertIs(c._pool(state, 4), pool)
        self.assertLess(len(pool.routes), pool.enumerated_feasible)

    def test_controls_share_free_sample_learning_and_strict_admission(self):
        sample_wait = []
        for mode in ("reference", "no_probe", "entropy", "fixed_pair"):
            c = self.controller(mode, ("r1", "r2") if mode == "fixed_pair" else None)
            direct, choice, _ = c.planning_options()
            direct_value = c._dot(direct.coefficients, c._factors(c.beliefs))
            self.assertGreaterEqual(choice["value"], direct_value)
            sample_wait.append({option["prefix"]["target"]["id"]: option["value"]
                                for option in c._evaluated_candidates if option["kind"] == "sample_wait"})
            for option in c._evaluated_candidates:
                if option["prefix"]:
                    self.assertNotIn(option["prefix"]["target"]["region"], option["probes"])
                if mode == "no_probe":
                    self.assertEqual(option["probes"], ())
                if mode == "fixed_pair":
                    self.assertLessEqual(set(option["probes"]), {"r1", "r2"})
        self.assertTrue(all(item == sample_wait[0] for item in sample_wait))

    def test_impossible_cost_never_bypasses_probe_admission(self):
        c = self.controller()
        c.inspection_energy = 1000
        _, choice, _ = c.planning_options()
        self.assertEqual(choice["probes"], ())
        self.assertFalse(any(option["probes"] for option in c._evaluated_candidates))

    def test_development_fixture_selects_productive_overlap_and_waits_for_results(self):
        c = self.controller()
        c.decide()
        first = c.decision_log[0]
        self.assertEqual(first["action"], "overlap")
        actions = [ack["command"]["action"] for ack in c.acks]
        self.assertIn("drive", actions)
        self.assertLess(actions.index("sample"), actions.index("inspect"))
        self.assertEqual(c.confirm_tick, c.reserved_until())
        self.assertFalse(c.ready())
        self.assertTrue(all(value not in (0, 1) for value in c.beliefs.values()))

    def test_public_quality_mode_has_no_inspection_and_delivers_structure(self):
        c = ExpeditionControllerV2(PublicTools(ExpeditionEnvironment(seed=100, mission_seed=0,
                                                                     visibility="public")))
        c.decide()
        self.assertEqual(c.decision_log[0]["probes"], [])
        self.assertEqual(set(c.initial_single_region_values), {"r1", "r2", "r3"})
        for region, plan in c.initial_single_region_plans.items():
            self.assertTrue(plan["feasible"])
            self.assertEqual(len(plan["targets"]), 2)
            self.assertTrue(all(c.targets[tid]["region"] == region for tid in plan["targets"]))
            self.assertLessEqual(plan["movement_and_sample_energy"] + plan["home_energy_safe"]
                                 + plan["idle_energy_to_horizon"] + plan["energy_reserve"], plan["battery"])
            self.assertLessEqual(plan["return_tick"], c.horizon - c.home_slack())

    def test_fixed_pair_validates_public_names_and_distinctness(self):
        for pair in (None, ("r1",), ("r1", "r1"), ("r1", "hidden")):
            with self.subTest(pair=pair), self.assertRaises(ValueError):
                self.controller("fixed_pair", pair)

    def test_no_hidden_environment_imports(self):
        tree = ast.parse(inspect.getsource(reference_v2))
        imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        self.assertEqual(imports, {"dataclasses", "lightlag_dynamic.controllers",
                                   "lightlag_dynamic.kf_mpc", "reference"})


class PublicTerrainSafety(unittest.TestCase):
    def pending_controller(self):
        tools = Fixture()
        tools.public_map["sand"] = [{"x1": 20, "y1": 20.5, "x2": 30, "y2": 30}]
        c = ExpeditionControllerV2(tools)
        c.filter.cov[0][0] = c.filter.cov[1][1] = 1.
        c.send([{"action": "drive", "heading_deg": 0, "metres": 2},
                {"action": "drive", "heading_deg": 0, "metres": 2},
                {"action": "sample"}, {"action": "inspect", "region": "r2"}])
        return c

    def test_pending_drives_keep_reserve_without_changing_pose_or_other_costs(self):
        c = self.pending_controller()
        raw = KalmanMPCController.predict(c, 8)
        guarded = c.predict(8)
        self.assertAlmostEqual(guarded["battery"], 100 - 7 * .5 - 8 - 3 - 2)
        self.assertAlmostEqual(c._pending_drive_reserve(8), 4.)
        for key in ("x", "y", "cov", "bias", "tick"):
            self.assertEqual(guarded[key], raw[key])
        # The slot itself has not executed: neither drive at4 is charged before4.
        self.assertEqual(c._pending_drive_reserve(4), 0.)
        self.assertAlmostEqual(c._pending_drive_reserve(5), 2.)

    def test_pending_drive_reserve_reconciles_delivery_and_cancellation(self):
        c = self.pending_controller()
        c.cancelled.add(c.acks[0]["command_id"])
        self.assertAlmostEqual(c._pending_drive_reserve(8), 2.)
        self.assertAlmostEqual(c.predict(8)["battery"], 100 - 7 * .5 - 4 - 3 - 2)
        # Public battery at tick5 supersedes both drive forecasts; only later
        # sample/inspection and tick6/7 idle remain. No reserve is charged twice.
        packet = deepcopy(c.packets[-1])
        packet.update(tick=5, battery=93.5, position=[23.8, 20.], events=[])
        c.absorb(packet)
        self.assertEqual(c._pending_drive_reserve(8), 0.)
        self.assertAlmostEqual(c.predict(8)["battery"], 93.5 - 2 * .5 - 3 - 2)

    def test_multiple_pending_drives_propagate_in_chronological_order(self):
        c = self.pending_controller()
        seen = []

        def record(start, end, wheel, radius):
            seen.append((start, end))
            return 2 * wheel

        with patch.object(c, "_guarded_segment_cost", side_effect=record):
            c._pending_drive_reserve(8)
        self.assertEqual(len(seen), 2)
        self.assertEqual(seen[0][1], seen[1][0])
        self.assertNotEqual(seen[0][0], seen[1][0])

    def test_sand_exposure_inside_pose_corridor_covers_cost_missed_by_mean_route(self):
        tools = Fixture()
        tools.public_map["sand"] = [{"x1": 20, "y1": 20.5, "x2": 30, "y2": 30}]
        c = ExpeditionControllerV2(tools)
        low = c._geometry((20, 20), (24, 20), 1e-6)
        guarded = c._geometry((20, 20), (24, 20), 1.0)
        self.assertGreater(guarded.energy_safe, low.energy_safe)
        self.assertIs(c._geometry((20, 20), (24, 20), 1e-6), low)
        self.assertIs(c._geometry((20, 20), (24, 20), 1.0), guarded)
        # A possible true starting pose .6m north is inside the 90% corridor.
        # Execute the unchanged public commands in that explicit synthetic world.
        env = Environment(seed=0, config=Config(delay_ticks=0, max_ticks=60, idle_cost=0),
                          world=World(base=(20, 20.6), sand=(Rect(20, 20.5, 30, 30),),
                                      hazards=(), targets=()))
        env.uplink(guarded.commands)
        env.advance(5)
        actual_cost = 100 - env.telemetry_log()[-1]["battery"]
        self.assertGreater(actual_cost, low.energy_safe)
        self.assertGreaterEqual(guarded.energy_safe + 1e-8, actual_cost)

    def test_no_sand_preserves_frozen_leg_energy_and_commands(self):
        c = ExpeditionControllerV2(Fixture())
        legacy = c.leg((20, 20), (24, 20))
        guarded = c._geometry((20, 20), (24, 20), .8)
        self.assertEqual(guarded.commands, legacy.commands)
        self.assertAlmostEqual(guarded.energy, legacy.energy, places=5)
        self.assertAlmostEqual(guarded.energy_safe, legacy.energy_safe, places=5)

    def test_corridor_does_not_assume_position_and_slip_are_independent(self):
        tools = Fixture()
        tools.public_map["sand"] = [{"x1": 20, "y1": 23.5, "x2": 30, "y2": 30}]
        c = ExpeditionControllerV2(tools)
        start, goal = (20, 20), (24, 20)
        legacy = c.leg(start, goal)
        wheel = sum(command["metres"] for command in legacy.commands)
        # Equal unit position/motion variances may be positively correlated:
        # the 90% radius then exceeds the3.5m sand gap. Independence would miss it.
        profile = (wheel, ((start, goal, wheel, 1.000001),))
        with patch.object(c, "_command_energy_profile", return_value=profile):
            guarded = c._geometry(start, goal, 1.)
        self.assertAlmostEqual(guarded.energy_safe, 2 * wheel)

    def test_correlated_starting_position_uses_eigenvalue_at_all_safety_call_sites(self):
        tools = Fixture()
        tools.public_map["sand"] = [{"x1": 20, "y1": 22.5, "x2": 30, "y2": 30}]
        tools.public_map["targets"][1]["x"] = 24
        c = ExpeditionControllerV2(tools)
        state = c.predict(4)
        state["cov"] = [[1., .9], [.9, 1.]]
        c._reset_planning(state)
        self.assertAlmostEqual(c._var0, 1.9)
        original_geometry = c._geometry
        variances = []

        def record_geometry(start, goal, variance):
            variances.append(variance)
            return original_geometry(start, goal, variance)

        with patch.object(c, "_geometry", side_effect=record_geometry):
            c._pool(state, 4)
            c._prefix(state, 4, c.targets["t2"])
            c._safe_future(state, 11, 2)
        self.assertTrue(variances)
        self.assertTrue(all(abs(variance - 1.9) < 1e-9 for variance in variances))
        # Isolate starting covariance: no nuisance variance in this public profile.
        # A2.5m sand gap lies outside maxdiag's90% radius, but inside lambda_max's.
        c._v2_geometry.clear()
        c._v2_execution.clear()
        c._v2_safe_geometry.clear()
        start, goal = (20, 20), (24, 20)
        wheel = sum(command["metres"] for command in c.leg(start, goal).commands)
        profile = (wheel, ((start, goal, wheel, 1e-6),))
        with patch.object(c, "_command_energy_profile", return_value=profile):
            underpriced = c._geometry(start, goal, 1.)
            guarded = c._geometry(start, goal, c._position_variance(state["cov"]))
        self.assertGreater(guarded.energy_safe, underpriced.energy_safe)
        self.assertAlmostEqual(guarded.energy_safe, 2 * wheel)

    def test_route_pool_requires_safe_outbound_as_well_as_home_and_idle(self):
        c = ExpeditionControllerV2(Fixture())
        state = c.predict(4)
        state["battery"] = c.idle * (c.horizon - state["tick"]) + 2 + 10
        risky = Leg([{"action": "wait"}], 1., 5., 0.)
        with patch.object(c, "_geometry", return_value=risky):
            pool = c._pool(state, 4)
        # Mean outbound1+sample3+home5 fits10; safe outbound5+sample3+home5 does not.
        self.assertEqual(pool.routes, ())

    def test_productive_prefix_charges_guarded_outbound_cost(self):
        c = ExpeditionControllerV2(Fixture())
        state = c.predict(4)
        guarded = Leg([{"action": "drive", "heading_deg": 0, "metres": .1}], .1, 10., 0.)
        with patch.object(c, "_geometry", return_value=guarded):
            prefix = c._prefix(state, 4, c.targets["t1"])
        self.assertIsNotNone(prefix)
        self.assertEqual(prefix["energy"], 13.)


class ContinuousDevelopmentSmoke(unittest.TestCase):
    def test_three_region_mission_all_controls(self):
        for mode in ("reference", "no_probe", "entropy", "fixed_pair"):
            with self.subTest(mode=mode):
                env = ExpeditionEnvironment(seed=101, mission_seed=1)
                c = run_policy(PublicTools(env), mode, ("r1", "r2") if mode == "fixed_pair" else None)
                self.assertEqual(c.tick, 60)
                self.assertTrue(env.evaluate()["alive"])
                self.assertLessEqual(len(c._requested_regions()), 2)
                self.assertTrue(all(0 <= belief <= 1 for belief in c.beliefs.values()))

    def test_six_region_development_map_zero_and_public_control(self):
        from lightlag_survey.environment import SurveyEnvironment
        for visibility in ("hidden", "public"):
            env = SurveyEnvironment(seed=100, mission_seed=0, visibility=visibility)
            c = run_policy(PublicTools(env))
            self.assertEqual(c.tick, 60)
            self.assertEqual(len(c.initial_single_region_values), 6)
            self.assertTrue(all(plan["feasible"] for plan in c.initial_single_region_plans.values()))
            self.assertLessEqual(len(c._requested_regions()), 2)
            if visibility == "public":
                self.assertEqual(c._requested_regions(), set())


if __name__ == "__main__":
    unittest.main()
