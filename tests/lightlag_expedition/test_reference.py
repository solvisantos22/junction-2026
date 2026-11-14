"""Belief, information allocation and resource invariants for the public reference."""

import ast
import copy
import inspect
import math
import unittest

from lightlag import Config
from lightlag_dynamic.controllers import Leg
from lightlag_dynamic.environment import DynamicEnvironment
from lightlag_expedition import reference
from lightlag_expedition.reference import ExpeditionController, posterior


class PublicFixture:
    """Only public payloads/methods; the controller cannot access any simulator state."""

    def __init__(self, qualities=None, inspection_energy=2, deadline=None):
        source = DynamicEnvironment(seed=0, config=Config(delay_ticks=3, max_ticks=60))
        self.briefing = source.rules()
        self.briefing["idle_cost"] = 0.0
        self.briefing["science"] = {
            "regions": {"r1": {"prior_rich": .95}, "r2": {"prior_rich": .4},
                        "r3": {"prior_rich": .5}},
            "quality_multipliers": {"poor": .2, "rich": 1.0},
            "inspection_budget": 2, "inspection_energy": inspection_energy,
            "inspection_accuracy": .9, "visibility": "public" if qualities else "hidden"}
        if qualities:
            self.briefing["science"]["public_qualities"] = qualities
        self.public_map = {"width": 40, "height": 40, "base": [20, 20],
                           "sand": [], "hazards": [], "targets": [
                               {"id": "a", "x": 14, "y": 20, "value": 6,
                                "base_value": 6, "region": "r1"},
                               {"id": "b", "x": 26, "y": 20, "value": 10,
                                "base_value": 10, "region": "r2"}]}
        if deadline is not None:
            for target in self.public_map["targets"]:
                target.update(deadline_tick=deadline, late_value=0)
        self.packet = source.telemetry_log()[0]
        self.packet["battery"] = 25.0
        self.sent = []

    def rules(self):
        return copy.deepcopy(self.briefing)

    def map(self):
        return copy.deepcopy(self.public_map)

    def telemetry_log(self):
        return [copy.deepcopy(self.packet)]

    def uplink(self, commands):
        first = max(4, max((ack["execute_tick"] for ack in self.sent), default=0) + 1)
        acks = [{"command_id": len(self.sent) + index + 1, "sent_tick": 0,
                 "execute_tick": first + index, "command": copy.deepcopy(command)}
                for index, command in enumerate(commands)]
        self.sent.extend(acks)
        return copy.deepcopy(acks)


class StraightController(ExpeditionController):
    """Deterministic public geometry isolates information decisions from KF noise."""

    def leg(self, start, goal):
        distance = math.dist(start, goal)
        commands = [{"action": "wait"}] * math.ceil(distance / 5)
        return Leg(commands, distance, distance, 0.0)

    def home_slack(self):
        return 0


class Beliefs(unittest.TestCase):
    def test_bayes_probabilities_and_martingale(self):
        p_rich, mass_rich = posterior(.4, "rich", .9)
        p_poor, mass_poor = posterior(.4, "poor", .9)
        self.assertAlmostEqual(p_rich, .36 / .42)
        self.assertAlmostEqual(p_poor, .04 / .58)
        self.assertAlmostEqual(mass_rich + mass_poor, 1)
        self.assertAlmostEqual(p_rich * mass_rich + p_poor * mass_poor, .4)

    def test_sample_truth_overrides_signal_and_is_not_overwritten(self):
        controller = StraightController(PublicFixture())
        packet = copy.deepcopy(controller.packets[-1])
        packet["tick"] = 4
        packet["events"] = [{"type": "inspection_result", "region": "r2", "signal": "rich"}]
        controller.absorb(packet)
        self.assertAlmostEqual(controller.beliefs["r2"], .36 / .42)
        controller._read_quality(packet)
        self.assertAlmostEqual(controller.beliefs["r2"], .36 / .42)
        packet = copy.deepcopy(packet)
        packet["tick"] = 8
        packet["events"] = [{"type": "region_quality", "region": "r2", "quality": "poor",
                             "target_id": "b"}]
        controller.absorb(packet)
        self.assertEqual(controller.beliefs["r2"], 0)
        packet = copy.deepcopy(packet)
        packet["tick"] = 9
        packet["events"] = [{"type": "inspection_result", "region": "r2", "signal": "rich"}]
        controller.absorb(packet)
        self.assertEqual(controller.beliefs["r2"], 0)

    def test_public_qualities_start_exact_and_disable_inspection(self):
        controller = StraightController(PublicFixture({"r1": "poor", "r2": "rich", "r3": "poor"}))
        direct, options = controller.inspection_options()
        self.assertEqual(controller.beliefs, {"r1": 0., "r2": 1., "r3": 0.})
        self.assertEqual(direct.sequence[0]["id"], "b")
        self.assertEqual(options, {})

    def test_late_and_on_time_values_share_quality_multiplier(self):
        controller = StraightController(PublicFixture())
        target = dict(controller.targets["a"], deadline_tick=10, late_value=2)
        self.assertAlmostEqual(controller.value_at(target, 10), 6 * .96)
        self.assertAlmostEqual(controller.value_at(target, 11), 2 * .96)


class InspectionPlanning(unittest.TestCase):
    def test_inspects_challenger_not_current_leader(self):
        tools = PublicFixture()
        tools.briefing["science"]["inspection_budget"] = 1
        controller = StraightController(tools)
        direct, options = controller.inspection_options()
        self.assertEqual(direct.sequence[0]["id"], "a")
        self.assertGreater(options["r2"], direct.value)
        self.assertGreater(options["r2"], options["r1"])
        controller.decide()
        self.assertEqual(tools.sent[0]["command"], {"action": "inspect", "region": "r2"})
        self.assertEqual(controller.confirm_tick, 4)
        self.assertFalse(controller.ready(), "must await the delayed observation")

    def test_leader_counterpart_has_same_gate_but_different_candidate(self):
        controller = StraightController(PublicFixture(), mode="leader_probe")
        direct, options = controller.inspection_options()
        self.assertEqual(set(options), {"r1"})
        self.assertGreater(options["r1"], direct.value)

    def test_probe_cost_and_deadline_can_outweigh_information(self):
        costly = StraightController(PublicFixture(inspection_energy=20))
        direct, options = costly.inspection_options()
        self.assertTrue(all(value < direct.value for value in options.values()))
        late = StraightController(PublicFixture(deadline=8))
        direct, options = late.inspection_options()
        self.assertGreater(direct.value, max(options.values()))
        late.decide()
        self.assertFalse(any(ack["command"]["action"] == "inspect" for ack in late.acks))

    def test_second_inspection_is_planned_conditionally(self):
        tools = PublicFixture()
        two = StraightController(tools).inspection_options()[1]
        tools.briefing["science"]["inspection_budget"] = 1
        one = StraightController(tools).inspection_options()[1]
        self.assertGreater(two["r1"], one["r1"])
        self.assertAlmostEqual(two["r1"], two["r2"])

    def test_lookahead_charges_roundtrip_idle_and_inspection_energy(self):
        controller = StraightController(PublicFixture())
        controller.idle = .5
        state = controller.predict(4)
        state["battery"] = 100
        after, slot = controller._after_inspection(state, 4)
        self.assertEqual(slot, 11)
        self.assertEqual(after["tick"], 10)
        self.assertEqual(after["battery"], 100 - 2 - 7 * .5)

    def test_pending_inspection_cost_not_double_counted_after_packet(self):
        controller = StraightController(PublicFixture())
        controller.send([{"action": "inspect", "region": "r2"}])
        self.assertEqual(controller.predict(4)["battery"], 25)
        self.assertEqual(controller.predict(5)["battery"], 23)
        packet = copy.deepcopy(controller.packets[-1])
        packet.update(tick=4, battery=23)
        packet["events"] = [{"type": "inspection_result", "region": "r2", "signal": "rich"}]
        controller.absorb(packet)
        self.assertEqual(controller.predict(5)["battery"], 23)
        self.assertNotIn("r2", controller.inspection_options()[1])

    def test_cancelled_inspection_preserves_reservation_but_does_not_cost_energy(self):
        controller = StraightController(PublicFixture())
        controller.send([{"action": "inspect", "region": "r2"}])
        controller.cancelled.add(controller.acks[0]["command_id"])
        self.assertEqual(controller.predict(5)["battery"], 25)
        self.assertEqual(controller._requested_regions(), {"r2"})

    def test_no_probe_still_learns_and_value_blind_ignores_quality(self):
        tools = PublicFixture({"r1": "rich", "r2": "poor", "r3": "poor"})
        aware = StraightController(tools, mode="no_probe")
        blind = StraightController(tools, mode="value_blind")
        self.assertEqual(aware.inspection_options()[0].sequence[0]["id"], "a")
        self.assertEqual(blind.inspection_options()[0].sequence[0]["id"], "b")
        self.assertEqual(aware.inspection_options()[1], {})
        self.assertEqual(blind.inspection_options()[1], {})

    def test_plan_is_bounded_at_four_targets_and_keeps_home_energy(self):
        tools = PublicFixture()
        tools.packet["battery"] = 100
        tools.public_map["targets"] = [
            {"id": str(index), "x": 20, "y": 20, "value": 1, "base_value": 1,
             "region": "r1"} for index in range(6)]
        controller = StraightController(tools, mode="no_probe")
        self.assertEqual(len(controller.inspection_options()[0].sequence), 4)
        tools.packet["battery"] = 14  # either round trip + sampling needs 15, before reserve
        tools.public_map["targets"] = PublicFixture().public_map["targets"]
        self.assertFalse(StraightController(tools).inspection_options()[0].sequence)

    def test_reference_imports_no_environment_or_service(self):
        tree = ast.parse(inspect.getsource(reference))
        imports = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        self.assertEqual(set(imports), {"dataclasses", "lightlag_dynamic.controllers",
                                       "lightlag_dynamic.kf_mpc"})


class ContinuousIntegration(unittest.TestCase):
    def test_all_controls_run_real_delayed_missions_through_public_tools(self):
        from lightlag_dynamic.tools import PublicTools
        from lightlag_expedition.environment import ExpeditionEnvironment

        for mission_seed in (0, 1, 2):
            for mode in reference.MODES:
                with self.subTest(mission_seed=mission_seed, mode=mode):
                    env = ExpeditionEnvironment(seed=mission_seed, mission_seed=mission_seed)
                    controller = reference.run_policy(PublicTools(env), mode)
                    result = env.evaluate()
                    self.assertEqual(controller.tick, 60)
                    self.assertGreaterEqual(result["raw_score"], 0)
                    self.assertLessEqual(result["raw_score"], 20)
                    self.assertLessEqual(len(controller._requested_regions()), 2)
                    if mode in ("no_probe", "value_blind"):
                        self.assertEqual(controller._requested_regions(), set())
                    for packet in env.telemetry_log():
                        for event in packet["events"]:
                            if event["type"] == "region_quality":
                                self.assertEqual(controller.beliefs[event["region"]],
                                                 float(event["quality"] == "rich"))

    def test_public_quality_control_uses_same_motion_planner_without_probes(self):
        from lightlag_dynamic.tools import PublicTools
        from lightlag_expedition.environment import ExpeditionEnvironment

        env = ExpeditionEnvironment(seed=3, mission_seed=3, visibility="public")
        controller = reference.run_policy(PublicTools(env))
        self.assertEqual(controller._requested_regions(), set())
        self.assertTrue(all(value in (0, 1) for value in controller.beliefs.values()))
        self.assertEqual(controller.tick, 60)


if __name__ == "__main__":
    unittest.main()
