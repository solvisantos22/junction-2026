"""Public belief/queue accounting, fair controls, and continuous v2 integration."""

import ast
from copy import deepcopy
import inspect
import math
import unittest
from unittest.mock import patch

from lightlag import Config
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
