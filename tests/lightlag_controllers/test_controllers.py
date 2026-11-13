"""Behaviour tests for the Lightlag controllers, run against the real simulator.

Run from the repository root:

    python3 -m unittest discover -s tests/lightlag_controllers -v

`env.replay()` is evaluator-only. Tests use it to check what controllers believed
against what really happened; controllers never see it.
"""

import random
import statistics
import unittest

from lightlag import Config, Environment, Rect as SimRect, Target as SimTarget, World as SimWorld

from lightlag_controllers import (
    MOVE_AND_WAIT, NO_OP, OPEN_LOOP_NOMINAL, REFERENCE, STALE_TELEMETRY, STOP_EARLY, make, run_episode,
)
from lightlag_controllers.adapter import parse_map, parse_packets, parse_rules
from lightlag_controllers.estimator import SlipEstimator
from lightlag_controllers.model import Rect, Rules, Target, World, distance
from lightlag_controllers.physics import simulate_drive, wheel_for_distance
from lightlag_controllers.pilot import physics_overrides, seeded_world
from lightlag_controllers.planner import BASE, RoutePlanner


def episode(strategy, seed=1, delay=3, world=None, **config):
    env = Environment(seed=seed, config=Config(delay_ticks=delay, **config), world=world)
    controller = make(strategy)
    return run_episode(env, controller), env, controller


def belief_errors(env, controller):
    """Distance between each believed position and the true position at that tick."""
    states = env.replay()["states"]
    return [
        distance(note["believed"][0], note["believed"][1], *states[note["for_tick"]]["position"])
        for note in controller.trace
    ]


class GeometryAndPhysics(unittest.TestCase):
    def test_segment_through_thin_rectangle_is_blocked(self):
        wall = Rect(5.0, 0.0, 5.1, 10.0)
        self.assertTrue(wall.intersects_segment(0, 5, 10, 5))
        self.assertFalse(wall.intersects_segment(0, 11, 10, 11))
        self.assertTrue(wall.intersects_segment(5.05, 5, 9, 5))

    def test_wheel_for_distance_inverts_the_drive_model_across_terrain(self):
        world = World(40, 40, (20, 20), (), patches=((Rect(22, 0, 40, 40), "sand"),))
        rules = Rules()
        slip = {"bedrock": 0.03, "sand": 0.35}.__getitem__
        wheel = wheel_for_distance(world, rules, slip, 20, 20, 0.0, 6.0)
        result = simulate_drive(world, rules, slip, 20, 20, 0.0, wheel)
        self.assertAlmostEqual(result.x, 26.0, delta=0.02)
        self.assertGreater(wheel, 6.0 / (1 - 0.03))

    def test_drive_model_matches_the_simulator_given_the_true_slip(self):
        """The controller's physics is the published physics, not an approximation."""
        seed = 5
        env = Environment(seed=seed, config=Config(delay_ticks=0, max_ticks=12))
        rules = parse_rules(env.rules())
        world = parse_map(env.map())
        drives = [(0.0, 5.0), (37.0, 4.2), (180.0, 5.0), (251.5, 3.3), (90.0, 5.0)]
        for heading, metres in drives:
            env.uplink([{"action": "drive", "heading_deg": heading, "metres": metres}])
            env.advance(1)
        env.advance(5)
        env.advance(2)
        replay = env.replay()
        true_slip = replay["slip_coefficients"]
        noise_limit = rules.slip_noise
        x, y = world.base
        for index, (heading, metres) in enumerate(drives, start=1):
            noise = random.Random("{}:drive:{}".format(seed, index)).uniform(-noise_limit, noise_limit)
            predicted = simulate_drive(
                world, rules, lambda name: min(0.9, max(0.0, true_slip[name] + noise)), x, y, heading, metres
            )
            actual = replay["states"][index]["position"]
            self.assertAlmostEqual(predicted.x, actual[0], places=6)
            self.assertAlmostEqual(predicted.y, actual[1], places=6)
            x, y = actual


class Estimation(unittest.TestCase):
    def test_estimate_moves_from_the_published_midpoint_to_the_observed_slip(self):
        estimator = SlipEstimator(Rules())
        self.assertAlmostEqual(estimator.mean("sand"), 0.325)
        self.assertAlmostEqual(estimator.halfwidth("sand"), 0.125)
        for _ in range(4):
            estimator.observe("sand", 5.0, 5.0 * (1 - 0.41))
        self.assertAlmostEqual(estimator.mean("sand"), 0.41, places=6)
        self.assertLess(estimator.halfwidth("sand"), 0.02)

    def test_a_non_learning_estimator_keeps_the_midpoint(self):
        estimator = SlipEstimator(Rules(), learn=False)
        estimator.observe("sand", 5.0, 2.0)
        self.assertAlmostEqual(estimator.mean("sand"), 0.325)

    def test_reference_learns_the_hidden_slip_from_telemetry(self):
        _, env, controller = episode(REFERENCE, seed=3, delay=3)
        truth = env.replay()["slip_coefficients"]
        for terrain in ("bedrock", "sand"):
            self.assertTrue(controller.estimator.observed(terrain), terrain)
            self.assertAlmostEqual(controller.estimator.mean(terrain), truth[terrain], delta=0.03)


class Planning(unittest.TestCase):
    def setUp(self):
        self.rules = Rules()
        self.world = World(
            40, 40, (20, 20),
            (Target("near", 26, 20, 1.0), Target("far", 20, 34, 3.0)),
            hazards=(Rect(22.5, 17, 23.5, 23),),
        )
        self.planner = RoutePlanner(self.world, self.rules, margin=0.5)
        self.planner.update(lambda name: self.rules.terrains[name].slip_mid)

    def test_path_goes_around_a_hazard_with_margin(self):
        leg = self.planner.leg(self.world.base, "near")
        self.assertTrue(leg.reachable)
        self.assertGreater(len(leg.waypoints), 1)
        points = [self.world.base] + list(leg.waypoints)
        hazard = self.world.hazards[0].inflate(0.3)
        for a, b in zip(points, points[1:]):
            self.assertFalse(hazard.intersects_segment(a[0], a[1], b[0], b[1]))
        self.assertEqual(leg.waypoints[-1], (26, 20))

    def test_path_keeps_clear_of_the_edge_of_costly_terrain(self):
        world = World(40, 40, (20, 20), (Target("t", 20, 32, 1.0),), patches=((Rect(15, 24, 20.4, 28), "sand"),))
        planner = RoutePlanner(world, self.rules)
        planner.update(lambda name: self.rules.terrains[name].slip_mid)
        points = [world.base] + list(planner.leg(world.base, "t").waypoints)
        sand = world.patches[0][0].inflate(0.3)
        for a, b in zip(points, points[1:]):
            self.assertFalse(sand.intersects_segment(a[0], a[1], b[0], b[1]))

    def test_route_respects_the_energy_budget(self):
        both = self.planner.best_route(self.world.base, self.world.targets, 80.0, 80)
        self.assertEqual(set(both.targets), {"near", "far"})
        self.assertTrue(both.end_at_base)
        one = self.planner.best_route(self.world.base, self.world.targets, 36.0, 80)
        self.assertEqual(one.targets, ("far",))
        nothing = self.planner.best_route(self.world.base, self.world.targets, 2.0, 80)
        self.assertEqual(nothing.targets, ())

    def test_route_never_trades_the_return_for_one_more_sample(self):
        """Value already collected is halved by not returning, so that must be counted."""
        far_only = [t for t in self.world.targets if t.id == "far"]
        start = (26.0, 20.0)
        home_cost = self.planner.leg(start, BASE).energy
        budget = home_cost * 1.5
        route = self.planner.best_route(start, far_only, budget, 80, banked=1.0)
        self.assertEqual(route.targets, ())
        self.assertTrue(route.end_at_base)

    def test_route_respects_the_clock_when_each_command_takes_many_ticks(self):
        fast = self.planner.best_route(self.world.base, self.world.targets, 80.0, 40, ticks_per_command=1)
        slow = self.planner.best_route(self.world.base, self.world.targets, 80.0, 40, ticks_per_command=7)
        self.assertGreater(fast.score, slow.score)


class Adapter(unittest.TestCase):
    def test_public_results_parse_into_controller_types(self):
        env = Environment(seed=7, config=Config(delay_ticks=2, max_ticks=50))
        rules = parse_rules(env.rules())
        self.assertEqual((rules.delay, rules.horizon, rules.battery), (2, 50, 100.0))
        self.assertEqual(rules.terrains["sand"].drive_cost, 2.0)
        self.assertEqual((rules.terrains["sand"].slip_min, rules.terrains["sand"].slip_max), (0.20, 0.45))
        self.assertEqual(rules.slip_noise, 0.02)
        world = parse_map(env.map())
        self.assertEqual(world.base, (20.0, 20.0))
        self.assertEqual({t.id for t in world.targets}, {"east", "west", "north"})
        self.assertEqual(world.terrain_at(30, 5), "sand")
        self.assertEqual(world.terrain_at(10, 5), "bedrock")
        briefing = parse_packets(env.telemetry_log())
        self.assertEqual((briefing[0].tick, briefing[0].x, briefing[0].y), (0, 20.0, 20.0))

    def test_experiment_overrides_are_reported_by_rules_and_then_restored(self):
        with physics_overrides(noise=0.08, sand_slip=(0.15, 0.6)):
            rules = parse_rules(Environment(seed=1).rules())
            self.assertEqual(rules.slip_noise, 0.08)
            self.assertEqual((rules.terrains["sand"].slip_min, rules.terrains["sand"].slip_max), (0.15, 0.6))
        rules = parse_rules(Environment(seed=1).rules())
        self.assertEqual(rules.slip_noise, 0.02)
        self.assertEqual(rules.terrains["sand"].slip_max, 0.45)


class ClosedLoop(unittest.TestCase):
    def test_doing_nothing_scores_zero(self):
        outcome, _, _ = episode(NO_OP)
        self.assertEqual(outcome["raw_score"], 0.0)
        self.assertEqual(outcome["commands_sent"], 0)

    def test_episodes_are_deterministic(self):
        first, _, _ = episode(REFERENCE, seed=4)
        second, _, _ = episode(REFERENCE, seed=4)
        self.assertEqual(first, second)

    def test_without_delay_the_delay_handling_strategies_coincide(self):
        for seed in range(3):
            scores = {s.name: episode(s, seed=seed, delay=0)[0]["raw_score"]
                      for s in (REFERENCE, STALE_TELEMETRY, MOVE_AND_WAIT)}
            self.assertEqual(len(set(scores.values())), 1, scores)

    def test_reference_keeps_its_score_under_delay_and_always_gets_home(self):
        for delay in (0, 3, 6):
            outcomes = [episode(REFERENCE, seed=s, delay=delay, world=seeded_world(s))[0] for s in range(8)]
            self.assertTrue(all(o["alive"] and o["at_base"] for o in outcomes), delay)
            self.assertEqual(sum(o["rejected_uplinks"] for o in outcomes), 0)
            mean = statistics.fmean(o["raw_score"] for o in outcomes)
            if delay == 0:
                without_delay = mean
            self.assertGreaterEqual(mean, 0.9 * without_delay, delay)

    def test_acting_on_stale_telemetry_loses_to_the_reference_under_delay(self):
        for seed in range(3):
            reference = episode(REFERENCE, seed=seed, delay=3)[0]["raw_score"]
            stale = episode(STALE_TELEMETRY, seed=seed, delay=3)[0]["raw_score"]
            self.assertLess(stale, reference)

    def test_move_and_wait_runs_out_of_clock_under_a_long_delay(self):
        reference = statistics.fmean(episode(REFERENCE, seed=s, delay=6)[0]["raw_score"] for s in range(3))
        waiting = statistics.fmean(episode(MOVE_AND_WAIT, seed=s, delay=6)[0]["raw_score"] for s in range(3))
        self.assertLess(waiting, 0.6 * reference)

    def test_stopping_early_scores_well_below_finishing(self):
        full = episode(REFERENCE, delay=3)[0]["raw_score"]
        early = episode(STOP_EARLY, delay=3)[0]["raw_score"]
        self.assertLess(early, 0.5 * full)

    def test_reference_knows_where_the_rover_is_despite_the_delay(self):
        """Measured on seeds 0-4: reference 0.07-0.32 m mean error, stale telemetry 9-11 m."""
        for seed in range(5):
            _, env, controller = episode(REFERENCE, seed=seed, delay=3)
            errors = belief_errors(env, controller)
            self.assertTrue(errors)
            self.assertLess(statistics.fmean(errors), 0.5, seed)
            self.assertLess(max(errors), 0.75, seed)  # never off by more than the sampling radius
            _, stale_env, stale = episode(STALE_TELEMETRY, seed=seed, delay=3)
            self.assertGreater(statistics.fmean(belief_errors(stale_env, stale)), 5.0, seed)

    def test_open_loop_controller_never_reads_telemetry_after_the_briefing(self):
        _, _, controller = episode(OPEN_LOOP_NOMINAL, delay=3)
        self.assertEqual(sorted(controller.by_tick), [0])

    def test_reference_visits_the_uncertain_terrain_first_on_the_default_map(self):
        """All three targets fit the battery only on low-slip seeds; the sand target tells which."""
        outcome, env, _ = episode(REFERENCE, seed=4, delay=3)
        first = next(e for s in env.replay()["states"] for e in s["events"] if e["type"] == "sample_taken")
        self.assertEqual(first["target_id"], "east")
        self.assertEqual(outcome["raw_score"], outcome["max_value"])

    def test_controllers_run_as_policies_in_the_team_evaluation_runner(self):
        """Same score through lightlag.evaluation.run_episode, with no rejected request."""
        from lightlag.evaluation import run_episode as team_run_episode
        from lightlag_controllers import ALL_STRATEGIES, as_policy

        for strategy in ALL_STRATEGIES:
            report = team_run_episode(as_policy(strategy), seed=3, config=Config(delay_ticks=3))
            mine, _, _ = episode(strategy, seed=3, delay=3)
            self.assertEqual(report["policy"], strategy.name)
            self.assertEqual(report["result"]["raw_score"], mine["raw_score"], strategy.name)
            self.assertEqual(mine["rejected_uplinks"], 0, strategy.name)
            self.assertFalse([r for r in report["transcript"] if "error" in r], strategy.name)

    def test_safety_stop_cancels_the_reference_belief_about_queued_commands(self):
        world = SimWorld(
            sand=(), hazards=(SimRect(23, 15, 24, 25),),
            targets=(SimTarget("beyond", 30, 20, 1.0),),
        )
        outcome, env, controller = episode(OPEN_LOOP_NOMINAL, seed=1, delay=3, world=world)
        self.assertTrue(outcome["alive"])
        reference, _, _ = episode(REFERENCE, seed=1, delay=3, world=world)
        self.assertEqual(reference["raw_score"], reference["max_value"])


if __name__ == "__main__":
    unittest.main()
