"""The traverse simulator behind the five tools: timing, energy, sampling, grading, what stays hidden.

    python3 -m unittest discover -s tests/lightlag_traverse -v

Standard library only.
"""

import json
import math
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from lightlag_traverse.environment import MISSION, SENSING, TraverseEnvironment, sun  # noqa: E402
from lightlag_traverse.surface import PHYSICS  # noqa: E402
from lightlag_traverse.terrain import TraverseTarget, TraverseWorld  # noqa: E402

FLAT = [[0] * 41 for _ in range(41)]
REGOLITH = ["r" * 40 for _ in range(40)]


def flat_world(targets, base=(100.0, 100.0)):
    return TraverseWorld(1, 5.0, tuple(tuple(row) for row in FLAT), tuple(REGOLITH), base, tuple(targets))


def finish(env):
    while not env.advance(5)["episode_complete"]:
        pass
    return env.evaluate()


class TimingTest(unittest.TestCase):
    def setUp(self):
        self.env = TraverseEnvironment(3, flat_world([TraverseTarget("t1", 120.0, 100.0, 2.0)]))

    def test_a_command_executes_delay_plus_one_ticks_after_it_is_sent(self):
        delay = MISSION["delay_ticks"]
        acks = self.env.uplink([{"action": "drive", "heading_deg": 0, "metres": 5}, {"action": "wait"}])
        self.assertEqual([a["execute_tick"] for a in acks], [delay + 1, delay + 2])
        for _ in range(delay):
            self.env.advance(1)
        self.assertEqual(self.env._truth[-1]["position"], [100.0, 100.0])       # nothing has run yet
        self.env.advance(1)
        self.assertGreater(self.env._truth[-1]["position"][0], 103.0)
        later = self.env.uplink([{"action": "wait"}])                            # queued behind the reserved ticks
        self.assertEqual(later[0]["execute_tick"], max(self.env._tick + delay + 1, delay + 3))

    def test_telemetry_arrives_delay_ticks_late_and_the_briefing_is_exact(self):
        log = self.env.telemetry_log()
        self.assertEqual(len(log), 1)
        self.assertEqual((log[0]["tick"], log[0]["position"], log[0]["battery"]), (0, [100.0, 100.0], 100.0))
        out = self.env.advance(2)
        self.assertEqual(out["packets"], [])
        out = self.env.advance(2)
        self.assertEqual([p["tick"] for p in out["packets"]], [1])              # tick 1 arrives at tick 4
        self.assertEqual(out["packets"][0]["received_tick"], 1 + MISSION["delay_ticks"])

    def test_requests_are_validated_whole(self):
        for bad in ([], [{"action": "fly"}], [{"action": "drive", "heading_deg": 0, "metres": 5.1}],
                    [{"action": "wait"}] * 6, "drive"):
            with self.assertRaises(ValueError):
                self.env.uplink(bad)
        self.assertEqual(self.env._sent, [])
        for bad in (0, 6, 1.0, "1"):
            with self.assertRaises(ValueError):
                self.env.advance(bad)

    def test_the_mission_ends_at_max_ticks_and_nothing_can_be_queued_past_it(self):
        ticks = MISSION["max_ticks"]
        for _ in range(ticks // 5 - 1):
            self.assertFalse(self.env.advance(5)["episode_complete"])
        with self.assertRaises(ValueError):
            self.env.uplink([{"action": "wait"}] * 5)       # the fifth would run after the end
        self.assertTrue(self.env.advance(5)["episode_complete"])
        self.assertEqual(self.env.advance(5)["current_tick"], ticks)
        with self.assertRaises(ValueError):
            self.env.uplink([{"action": "wait"}])


class EnergyTest(unittest.TestCase):
    def test_the_sun_is_low_at_both_ends_and_highest_in_the_middle(self):
        ticks = MISSION["max_ticks"]
        self.assertAlmostEqual(sun(ticks / 2), 1.0)
        self.assertAlmostEqual(sun(0), sun(ticks))
        self.assertLess(sun(0), 0.5)
        self.assertGreater(sun(0), 0.2)

    def test_each_tick_charges_then_drains_and_the_battery_is_capped(self):
        env = TraverseEnvironment(3, flat_world([]))
        env.advance(1)
        first = env._truth[1]
        self.assertAlmostEqual(first["battery"], 100.0 - MISSION["idle_cost"])   # full: the charge is lost
        self.assertAlmostEqual(first["charge"], 0.0)
        env.uplink([{"action": "drive", "heading_deg": 0, "metres": 5}] * 5)
        env.advance(5)
        env.advance(4)
        tick = env._truth[7]
        gained = MISSION["solar_peak"] * env._efficiency * sun(7)
        self.assertAlmostEqual(tick["charge"], gained, places=5)
        spent = MISSION["idle_cost"] + 5 * PHYSICS["drive_cost_per_wheel_m"]["regolith"]
        self.assertAlmostEqual(env._truth[6]["battery"] + gained - spent, tick["battery"], places=5)
        low, high = MISSION["solar_efficiency_range"]
        self.assertTrue(low <= env._efficiency <= high)

    def test_an_empty_battery_ends_the_rover_for_good(self):
        env = TraverseEnvironment(3, flat_world([]), {"initial_battery": 3.0, "solar_peak": 0.0})
        env.uplink([{"action": "drive", "heading_deg": 0, "metres": 5}] * 5)
        result = finish(env)
        self.assertFalse(result["alive"])
        self.assertEqual(result["raw_score"], 0.0)
        dead = [s for s in env._truth if any(e["type"] == "battery_depleted" for e in s["events"])]
        self.assertEqual(len(dead), 1)
        self.assertTrue(all(s["battery"] == 0.0 and not s["alive"] for s in env._truth[dead[0]["tick"]:]))
        self.assertEqual(env._truth[-1]["position"], env._truth[dead[0]["tick"]]["position"])


class SamplingAndScoreTest(unittest.TestCase):
    def play(self, targets, commands, seed=3):
        env = TraverseEnvironment(seed, flat_world(targets))
        for start in range(0, len(commands), 5):
            env.uplink(commands[start:start + 5])
        return env, finish(env)

    def test_doing_nothing_scores_nothing_and_ends_alive_at_the_lander(self):
        _, result = self.play([TraverseTarget("t1", 120.0, 100.0, 2.0)], [{"action": "wait"}])
        self.assertEqual((result["raw_score"], result["alive"], result["at_base"]), (0.0, True, True))
        self.assertEqual(result["max_available_value"], 2.0)

    def test_a_sample_counts_only_within_the_radius_and_is_halved_away_from_the_lander(self):
        east = {"action": "drive", "heading_deg": 0, "metres": 5}
        # Regolith slips 5 to 12%, so five drives land 22 to 24 m east: beside a target at 23 m.
        env, result = self.play([TraverseTarget("t1", 123.0, 100.0, 4.0), TraverseTarget("t2", 190.0, 100.0, 3.0)],
                                [east] * 5 + [{"action": "sample"}])
        self.assertEqual(result["sampled_targets"], ["t1"])
        self.assertEqual(result["samples"][0]["tick"], MISSION["delay_ticks"] + 6)
        self.assertFalse(result["at_base"])
        self.assertAlmostEqual(result["raw_score"], 4.0 * 0.5)
        self.assertEqual(result["max_available_value"], 7.0)
        miss, missed = self.play([TraverseTarget("t1", 123.0, 100.0, 4.0)], [east] * 3 + [{"action": "sample"}])
        self.assertEqual(missed["sampled_targets"], [])
        self.assertTrue(any(e["type"] == "sample_failed" for s in miss._truth for e in s["events"]))

    def test_a_late_sample_earns_the_late_fraction(self):
        east = {"action": "drive", "heading_deg": 0, "metres": 5}
        targets = [TraverseTarget("t1", 123.0, 100.0, 4.0, deadline_tick=5)]
        _, result = self.play(targets, [east] * 5 + [{"action": "sample"}])
        self.assertFalse(result["samples"][0]["on_time"])
        self.assertAlmostEqual(result["sampled_value"], 4.0 * MISSION["late_fraction"])

    def test_a_discovery_is_hidden_until_its_packet_arrives_and_cannot_be_sampled_early(self):
        targets = [TraverseTarget("t1", 150.0, 100.0, 1.0), TraverseTarget("d1", 100.5, 100.0, 3.0, None, 6)]
        env = TraverseEnvironment(3, flat_world(targets))
        self.assertEqual([t["id"] for t in env.map()["targets"]], ["t1"])
        env.uplink([{"action": "sample"}])                   # executes at tick 4, before d1 exists
        env.advance(5)
        self.assertEqual(env._sampled, set())
        env.advance(3)                                       # tick 8: the tick-6 packet has not arrived
        self.assertEqual([t["id"] for t in env.map()["targets"]], ["t1"])
        out = env.advance(1)                                 # tick 9 = 6 + delay
        self.assertTrue(any(e["type"] == "target_discovered" for p in out["packets"] for e in p["events"]))
        self.assertEqual([t["id"] for t in env.map()["targets"]], ["t1", "d1"])
        env.uplink([{"action": "sample"}])
        result = finish(env)
        self.assertEqual(result["sampled_targets"], ["d1"])
        self.assertAlmostEqual(result["raw_score"], 3.0)     # sampled on the spot, so still at the lander


class SafetyStopTest(unittest.TestCase):
    def test_steep_ground_stops_the_rover_and_clears_the_queue(self):
        rows = [[0 if i <= 24 else int(100 * 0.5 * (i - 24) * 5.0) for i in range(41)] for _ in range(41)]
        world = TraverseWorld(1, 5.0, tuple(tuple(r) for r in rows), tuple(REGOLITH), (100.0, 100.0), ())
        env = TraverseEnvironment(3, world)
        env.uplink([{"action": "drive", "heading_deg": 0, "metres": 5}] * 5)
        env.uplink([{"action": "drive", "heading_deg": 0, "metres": 5}] * 5)
        env.advance(5)
        env.advance(5)
        env.advance(5)
        stops = [s for s in env._truth if any(e["type"] == "safety_stop" for e in s["events"])]
        self.assertEqual(len(stops), 1)
        self.assertLess(stops[0]["position"][0], 120.5)
        self.assertEqual(len(env._commands), 0)
        self.assertEqual(env._truth[-1]["position"], stops[0]["position"])       # the cleared drives never ran
        again = env.uplink([{"action": "wait"}])
        self.assertGreater(again[0]["execute_tick"], 14)                        # the reserved ticks stay reserved


class SecrecyAndReplayTest(unittest.TestCase):
    def setUp(self):
        self.env = TraverseEnvironment(11)

    def test_the_tools_tell_the_ranges_not_the_draws(self):
        public = json.dumps([self.env.rules(), self.env.map(), self.env.telemetry_log()])
        for hidden in (self.env._slip["sand"], self.env._slip["regolith"], self.env._efficiency,
                       self.env._heading_bias):
            self.assertNotIn(repr(round(hidden, 6))[:8], public)
        rules = self.env.rules()
        self.assertEqual(rules["physics"]["slip_base_ranges"], PHYSICS["slip_base_ranges"])
        self.assertEqual(rules["sensing"], SENSING)
        self.assertNotIn("seed", rules)
        self.assertNotIn("features", self.env.map())
        for name in ("evaluate", "replay"):
            self.assertNotIn(name, rules["supported_actions"])

    def test_reported_positions_are_noisy_and_the_truth_is_kept_apart(self):
        self.env.uplink([{"action": "drive", "heading_deg": 0, "metres": 5}] * 5)
        self.env.advance(5)
        out = self.env.advance(5)
        errors = [math.hypot(p["position"][0] - self.env._truth[p["tick"]]["position"][0],
                             p["position"][1] - self.env._truth[p["tick"]]["position"][1]) for p in out["packets"]]
        self.assertTrue(all(e > 0 for e in errors))
        self.assertLess(max(errors), 6 * SENSING["position_noise_m"])
        self.assertEqual([p["battery"] for p in out["packets"]],
                         [self.env._truth[p["tick"]]["battery"] for p in out["packets"]])

    def test_the_same_seed_and_commands_give_the_same_mission(self):
        def play():
            env = TraverseEnvironment(11)
            for _ in range(6):
                env.uplink([{"action": "drive", "heading_deg": 200, "metres": 5}] * 5)
                env.advance(5)
            finish(env)
            return env.replay()

        first, second = play(), play()
        self.assertEqual(first, second)
        self.assertEqual(first["version"], "lightlag-traverse-replay-v1")
        self.assertEqual(len(first["states"]), MISSION["max_ticks"] + 1)
        self.assertEqual(len(first["world"]["targets"]), len(self.env._world.targets))      # the truth: every target
        self.assertIn("slip_base", first["hidden"])
        other = TraverseEnvironment(12)
        self.assertNotEqual(other.map()["elevation_cm"], self.env.map()["elevation_cm"])

    def test_the_replay_is_not_available_before_the_end(self):
        with self.assertRaises(ValueError):
            self.env.evaluate()
        with self.assertRaises(ValueError):
            self.env.replay()


if __name__ == "__main__":
    unittest.main()
