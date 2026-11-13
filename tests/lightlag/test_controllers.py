import ast
import importlib
import math
from pathlib import Path
import unittest

from lightlag import Config, Environment, Rect, Target, World
from lightlag.controllers.api import PublicTools
from lightlag.evaluation import run_episode


def controller_type(module, name):
    try:
        return getattr(importlib.import_module("lightlag.controllers." + module), name, None)
    except ModuleNotFoundError:
        return None


def packet(tick, position=(10, 10), battery=100, wheel=0, visual=0,
           events=(), sampled=(), alive=True):
    return {"tick": tick, "received_tick": tick + 3, "position": list(position),
            "heading_deg": 0, "battery": battery, "terrain": "bedrock",
            "wheel_odometry": wheel, "visual_odometry": visual,
            "sampled_targets": list(sampled), "alive": alive, "events": list(events)}


def ack(command_id, sent, execute, metres=1, action="drive", heading=0):
    command = {"action": action}
    if action == "drive":
        command.update(heading_deg=heading, metres=metres)
    return {"command_id": command_id, "sent_tick": sent, "execute_tick": execute,
            "command": command}


class GeometryTests(unittest.TestCase):
    def setUp(self):
        self.geometry_type = controller_type("geometry", "MapGeometry")
        self.assertIsNotNone(self.geometry_type, "public-map geometry is not implemented")

    def test_shortest_visible_route_avoids_inflated_rectangle(self):
        world = World(width=20, height=20, base=(2, 10), sand=(),
                      hazards=(Rect(8, 6, 12, 14),), targets=())
        geometry = self.geometry_type(world.public_map(), margin=0.4)
        route = geometry.route((2, 10), (18, 10))
        self.assertEqual(route[0], (2, 10))
        self.assertEqual(route[-1], (18, 10))
        self.assertGreater(len(route), 2)
        for start, end in zip(route, route[1:]):
            self.assertTrue(geometry.segment_clear(start, end))
        self.assertAlmostEqual(geometry.route_length(route),
                               2 * math.hypot(5.6, 4.4) + 4.8)

    def test_thin_terrain_crossing_is_not_a_homogeneous_leg(self):
        world = World(sand=(Rect(20.2, 0, 20.4, 40),), hazards=(), targets=())
        geometry = self.geometry_type(world.public_map())
        self.assertEqual(geometry.terrain_at((20, 20)), "bedrock")
        self.assertEqual(geometry.terrain_at((21, 20)), "bedrock")
        self.assertIsNone(geometry.homogeneous_terrain((20, 20), (21, 20)))
        self.assertEqual(geometry.homogeneous_terrain((20, 10), (20, 20)), "bedrock")

    def test_unreachable_route_returns_none(self):
        world = World(width=20, height=20, base=(2, 10), sand=(),
                      hazards=(Rect(8, 0, 12, 20),), targets=())
        geometry = self.geometry_type(world.public_map())
        self.assertIsNone(geometry.route((2, 10), (18, 10)))

    def test_route_escapes_an_endpoint_inside_only_the_hazard_margin(self):
        geometry = self.geometry_type(World().public_map())
        near_hazard, base = (20, 29.9567410983), (20, 20)
        self.assertTrue(geometry.segment_clear(near_hazard, base, margin=False))
        self.assertFalse(geometry.segment_clear(near_hazard, base))
        route = geometry.route(near_hazard, base)
        self.assertIsNotNone(route)
        self.assertEqual((route[0], route[-1]), (near_hazard, base))
        self.assertLessEqual(math.dist(route[0], route[1]), geometry.margin + 1e-8)
        self.assertTrue(geometry.segment_clear(route[0], route[1], margin=False))
        for start, end in zip(route[1:], route[2:]):
            self.assertTrue(geometry.segment_clear(start, end))

    def test_route_can_arrive_at_a_safe_destination_inside_the_hazard_margin(self):
        geometry = self.geometry_type(World().public_map())
        start, destination = (20, 29.8), (20, 32.2)
        self.assertFalse(geometry.segment_clear(start, destination, margin=False))
        route = geometry.route(start, destination)
        self.assertIsNotNone(route)
        self.assertEqual((route[0], route[-1]), (start, destination))
        for first, second in zip(route, route[1:]):
            self.assertTrue(geometry.segment_clear(first, second, margin=False))
        for first, second in zip(route[1:-1], route[2:-1]):
            self.assertTrue(geometry.segment_clear(first, second))
        self.assertLessEqual(math.dist(route[0], route[1]), geometry.margin + 1e-8)
        self.assertLessEqual(math.dist(route[-2], route[-1]), geometry.margin + 1e-8)

    def test_endpoint_escape_never_allows_a_point_inside_an_actual_hazard(self):
        geometry = self.geometry_type(World().public_map())
        self.assertIsNone(geometry.route((20, 31), (20, 20)))
        self.assertIsNone(geometry.route((20, 20), (20, 31)))


class PredictorTests(unittest.TestCase):
    def setUp(self):
        self.predictor_type = controller_type("predictor", "Predictor")
        self.assertIsNotNone(self.predictor_type, "public observation predictor is not implemented")
        self.rules = Environment(config=Config(delay_ticks=3)).rules()
        self.world = World(sand=(), hazards=(), targets=()).public_map()

    def predictor(self, initial=None, world=None):
        return self.predictor_type(self.rules, world or self.world,
                                   initial or packet(0))

    def test_slip_starts_at_midpoint_and_uses_wheel_weighted_observations(self):
        predictor = self.predictor()
        self.assertAlmostEqual(predictor.slip["bedrock"], 0.025)
        predictor.acknowledge([ack(1, 0, 1, 1), ack(2, 0, 2, 3)])
        predictor.observe([
            packet(1, (10.98, 10), wheel=1, visual=0.98,
                   events=({"type": "command_executed", "command_id": 1},)),
            packet(2, (13.86, 10), wheel=3, visual=2.88,
                   events=({"type": "command_executed", "command_id": 2},)),
        ])
        self.assertAlmostEqual(predictor.slip["bedrock"], 0.035)
        self.assertEqual(predictor.observed_wheel["bedrock"], 4)
        self.assertAlmostEqual(predictor.slip["sand"], 0.325)

    def test_mixed_terrain_drive_never_updates_slip_even_with_matching_endpoints(self):
        world = World(sand=(Rect(20.2, 0, 20.4, 40),), hazards=(), targets=()).public_map()
        predictor = self.predictor(initial=packet(0, (20, 20)), world=world)
        predictor.acknowledge([ack(1, 0, 1, 1.1)])
        predictor.observe([packet(1, (21, 20), wheel=1.1, visual=1,
                                  events=({"type": "command_executed", "command_id": 1},))])
        self.assertEqual(predictor.observed_wheel, {"bedrock": 0, "sand": 0})

    def test_duplicate_packets_and_partial_drives_do_not_change_learning(self):
        predictor = self.predictor()
        predictor.acknowledge([ack(1, 0, 1, 1), ack(2, 0, 2, 4), ack(3, 0, 3, 1)])
        first = packet(1, (10.98, 10), wheel=1, visual=0.98,
                       events=({"type": "command_executed", "command_id": 1},))
        predictor.observe([first, first])
        predictor.observe([first, packet(2, (11.96, 10), wheel=1, visual=0.98,
                                       events=({"type": "command_executed", "command_id": 2},)),
                           packet(3, (12.94, 10), wheel=1, visual=0.98, alive=False,
                                  events=({"type": "command_executed", "command_id": 3},))])
        self.assertEqual(predictor.observed_wheel["bedrock"], 1)
        self.assertAlmostEqual(predictor.slip["bedrock"], 0.02)
        self.assertEqual(predictor.anchor.tick, 3)

    def test_forecast_replays_unobserved_commands_once_and_idle_once(self):
        predictor = self.predictor()
        predictor.acknowledge([ack(1, 0, 4, 2), ack(2, 1, 5, action="sample")])
        state = predictor.forecast(5)
        self.assertAlmostEqual(state.position[0], 11.95)
        self.assertAlmostEqual(state.battery, 100 - 5 * 0.5 - 2 - 3)
        self.assertEqual(predictor.forecast(5), state)
        predictor.observe([packet(3, battery=98.5),
                           packet(4, (11.95, 10), battery=96, wheel=2, visual=1.95,
                                  events=({"type": "command_executed", "command_id": 1},))])
        corrected = predictor.forecast(5)
        self.assertAlmostEqual(corrected.position[0], 11.95)
        self.assertAlmostEqual(corrected.battery, 92.5)
        self.assertEqual(predictor.anchor.battery, 96)

    def test_safety_stop_cancels_older_sends_but_retains_same_tick_sends_and_slots(self):
        predictor = self.predictor()
        predictor.acknowledge([ack(1, 0, 4), ack(2, 3, 7, 3), ack(3, 4, 8, 2)])
        predictor.observe([packet(3), packet(4, events=(
            {"type": "command_executed", "command_id": 1},
            {"type": "safety_stop", "reason": "hazard"})), packet(5)])
        self.assertIn(2, predictor.cancelled)
        self.assertNotIn(3, predictor.cancelled)
        self.assertEqual(predictor.next_execution_tick(4), 9)
        state = predictor.forecast(8)
        self.assertAlmostEqual(state.position[0], 11.95)
        self.assertAlmostEqual(state.battery, 100 - 3 * 0.5 - 2)
        self.assertEqual(predictor.observed_wheel["bedrock"], 0)

    def test_every_new_packet_is_processed_before_newest_anchor(self):
        predictor = self.predictor()
        predictor.acknowledge([ack(1, 0, 1), ack(2, 0, 2)])
        predictor.observe([packet(2, (11.96, 10), wheel=1, visual=0.98,
                                  events=({"type": "command_executed", "command_id": 2},)),
                           packet(1, (10.98, 10), wheel=1, visual=0.98,
                                  events=({"type": "command_executed", "command_id": 1},))])
        self.assertEqual(predictor.observed_wheel["bedrock"], 2)
        self.assertEqual(predictor.anchor.tick, 2)

    def test_stale_forecast_ignores_pending_motion_but_still_pays_queued_costs(self):
        predictor = self.predictor()
        predictor.acknowledge([ack(1, 0, 4, 2), ack(2, 1, 5, action="sample")])
        state = predictor.forecast(5, ignore_motion=True)
        self.assertEqual(state.position, (10, 10))
        self.assertAlmostEqual(state.battery, 100 - 5 * 0.5 - 2 - 3)

    def test_homogeneous_sand_learning_is_clamped_to_the_published_family(self):
        world = World(sand=(Rect(0, 0, 40, 40),), hazards=(), targets=()).public_map()
        predictor = self.predictor(world=world)
        predictor.acknowledge([ack(1, 0, 1, 2)])
        predictor.observe([packet(1, (11.08, 10), wheel=2, visual=1.08,
                                  events=({"type": "command_executed", "command_id": 1},))])
        self.assertEqual(predictor.slip["sand"], 0.45)
        self.assertEqual(predictor.observed_wheel["sand"], 2)


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.policies = getattr(importlib.import_module("lightlag.controllers"), "POLICIES", None)
        self.assertIsNotNone(self.policies, "the six policy registry is not implemented")

    def test_registry_has_the_six_named_policies(self):
        self.assertEqual(list(self.policies), ["reference", "move_and_wait", "nominal_open_loop",
                                               "stale_telemetry", "do_nothing", "stop_early"])
        self.assertTrue(all(callable(policy) for policy in self.policies.values()))

    def test_reference_collects_science_and_returns_on_representative_seeds(self):
        for delay in (0, 3):
            for seed in (0, 7, 9):
                with self.subTest(delay=delay, seed=seed):
                    run = run_episode(self.policies["reference"], seed=seed,
                                      config=Config(delay_ticks=delay))
                    self.assertGreater(run["result"]["sampled_value"], 0)
                    self.assertTrue(run["result"]["alive"])
                    self.assertTrue(run["result"]["at_base"])
                    self.assertGreater(run["replay"]["states"][-1]["battery"], 0)
                    self.assertFalse(any(event["type"] == "safety_stop"
                                         for state in run["replay"]["states"] for event in state["events"]))

    def test_every_policy_has_valid_calls_and_a_fresh_repeatable_episode(self):
        for name, policy in self.policies.items():
            for delay in (0, 3):
                with self.subTest(policy=name, delay=delay):
                    first = run_episode(policy, seed=7, config=Config(delay_ticks=delay))
                    second = run_episode(policy, seed=7, config=Config(delay_ticks=delay))
                    self.assertEqual(first, second)
                    self.assertEqual(first["result"]["tick"], 80)

    def test_move_and_wait_observes_each_execution_before_the_next_decision(self):
        run = run_episode(self.policies["move_and_wait"], seed=7, config=Config(delay_ticks=3))
        commands = run["replay"]["commands"]
        self.assertGreater(len(commands), 2)
        for previous, following in zip(commands, commands[1:]):
            self.assertGreaterEqual(following["sent_tick"], previous["execute_tick"] + 3)
        self.assertEqual(commands[1]["sent_tick"] - commands[0]["sent_tick"], 7)
        self.assertGreater(run["result"]["sampled_value"], 0)
        self.assertTrue(run["result"]["at_base"])
        self.assertTrue(run["result"]["alive"])

    def test_nominal_open_loop_never_reads_later_packet_contents(self):
        class ForbiddenPackets:
            def __iter__(self):
                raise AssertionError("open loop inspected post-briefing telemetry")

        def guarded_policy(tools):
            reads = []

            def initial_only():
                self.assertEqual(reads, [])
                reads.append(True)
                return tools.telemetry_log()

            def advance(ticks=1):
                response = tools.advance(ticks)
                response["packets"] = ForbiddenPackets()
                return response

            self.policies["nominal_open_loop"](PublicTools(
                tools.rules, tools.map, initial_only, tools.uplink, advance))

        run = run_episode(guarded_policy, seed=7)
        self.assertGreater(len(run["replay"]["commands"]), 0)
        self.assertEqual(run["result"]["tick"], 80)

    def test_stop_early_matches_reference_prefix_then_leaves_horizon_to_evaluator(self):
        config = Config(delay_ticks=3)
        reference = run_episode(self.policies["reference"], seed=7, config=config)
        stopped = run_episode(self.policies["stop_early"], seed=7, config=config)
        prefix = [command for command in reference["replay"]["commands"] if command["sent_tick"] < 20]
        self.assertEqual(stopped["replay"]["commands"], prefix)
        self.assertEqual(stopped["result"]["tick"], 80)
        self.assertTrue(any(call["source"] == "evaluator" and call["tool"] == "advance"
                            for call in stopped["transcript"]))
        policy_ticks = [call["result"]["current_tick"] for call in stopped["transcript"]
                        if call["source"] == "policy" and call["tool"] == "advance"]
        self.assertLessEqual(max(policy_ticks, default=0), 20)

    def test_empty_map_low_energy_and_short_horizon_are_handled_without_invalid_commands(self):
        fixtures = [
            (Config(), World(targets=())),
            (Config(initial_battery=45), World()),
            (Config(delay_ticks=3, max_ticks=3), World()),
        ]
        for config, world in fixtures:
            for name, policy in self.policies.items():
                with self.subTest(policy=name, config=config, targets=world.targets):
                    run = run_episode(policy, config=config, world=world)
                    self.assertTrue(run["result"]["alive"])
                    self.assertTrue(run["result"]["at_base"])
                    self.assertEqual(run["replay"]["commands"], [])

    def test_reference_routes_around_a_visible_obstacle_using_map_target_ids(self):
        world = World(width=20, height=20, base=(3, 10), sand=(),
                      hazards=(Rect(6, 8, 8, 12),), targets=(Target("behind-wall", 11, 10, 5),))
        run = run_episode(self.policies["reference"], seed=7, config=Config(delay_ticks=3), world=world)
        self.assertEqual(run["result"]["sampled_targets"], ["behind-wall"])
        self.assertTrue(run["result"]["at_base"])
        self.assertTrue(run["result"]["alive"])
        self.assertFalse(any(event["type"] == "safety_stop" for state in run["replay"]["states"]
                             for event in state["events"]))

    def test_reference_corrects_a_failed_predicted_sample_from_delivered_telemetry(self):
        world = World(sand=(Rect(0, 0, 40, 40),), hazards=(),
                      targets=(Target("sand-science", 26, 20, 2),))
        run = run_episode(self.policies["reference"], seed=1, config=Config(delay_ticks=3), world=world)
        self.assertTrue(any(event["type"] == "sample_failed" for state in run["replay"]["states"]
                            for event in state["events"]))
        self.assertEqual(run["result"]["sampled_targets"], ["sand-science"])
        self.assertTrue(run["result"]["at_base"])
        self.assertTrue(run["result"]["alive"])

    def test_reference_can_leave_and_return_to_a_base_inside_the_hazard_margin(self):
        world = World(base=(20, 29.8), targets=(Target("near", 20, 28),))
        run = run_episode(self.policies["reference"], seed=7,
                          config=Config(delay_ticks=3), world=world)
        self.assertEqual(run["result"]["sampled_targets"], ["near"])
        self.assertTrue(run["result"]["at_base"])
        self.assertTrue(run["result"]["alive"])
        self.assertFalse(any(event["type"] == "safety_stop" for state in run["replay"]["states"]
                             for event in state["events"]))

    def test_blocked_target_does_not_send_an_unsafe_route(self):
        world = World(width=20, height=20, base=(3, 10), sand=(),
                      hazards=(Rect(6, 0, 8, 20),), targets=(Target("unreachable", 11, 10, 5),))
        run = run_episode(self.policies["reference"], seed=7, world=world)
        self.assertEqual(run["replay"]["commands"], [])
        self.assertTrue(run["result"]["at_base"])

    def test_controller_sources_have_no_simulator_import_or_private_attribute_access(self):
        directory = Path(__file__).resolve().parents[2] / "lightlag" / "controllers"
        forbidden = {"environment", "model", "evaluation", "random"}
        for path in directory.glob("*.py"):
            with self.subTest(path=path.name):
                tree = ast.parse(path.read_text())
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom):
                        self.assertFalse(set((node.module or "").split(".")) & forbidden)
                    elif isinstance(node, ast.Import):
                        for alias in node.names:
                            self.assertFalse(set(alias.name.split(".")) & forbidden)
                    elif isinstance(node, ast.Attribute):
                        self.assertFalse(node.attr.startswith("_"), node.attr)


if __name__ == "__main__":
    unittest.main()
