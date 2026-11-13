import copy
import unittest

from lightlag import Config, Environment, Rect, World


def drive(metres=2, heading=0):
    return {"action": "drive", "heading_deg": heading, "metres": metres}


class TimingTests(unittest.TestCase):
    def test_zero_delay_applies_on_next_transition(self):
        env = Environment(seed=7, config=Config(delay_ticks=0))
        initial = env.telemetry_log()[0]
        ack = env.uplink([drive()])
        self.assertEqual(ack[0]["execute_tick"], 1)
        self.assertEqual(env.telemetry_log(), [initial])
        packet = env.advance()["packets"][0]
        self.assertEqual((packet["tick"], packet["received_tick"]), (1, 1))
        self.assertGreater(packet["position"][0], initial["position"][0])
        self.assertEqual(packet["wheel_odometry"], 2)

    def test_three_delay_waits_and_delivers_only_old_state(self):
        env = Environment(seed=7, config=Config(delay_ticks=3))
        self.assertEqual(env.uplink([drive()])[0]["execute_tick"], 4)
        self.assertEqual(env.advance(3)["packets"], [])
        packets = env.advance(3)["packets"]
        self.assertEqual([p["tick"] for p in packets], [1, 2, 3])
        self.assertTrue(all(p["position"] == [20, 20] for p in packets))
        packet = env.advance()["packets"][0]
        self.assertEqual((packet["tick"], packet["received_tick"]), (4, 7))
        self.assertGreater(packet["position"][0], 20)

    def test_uplinks_share_one_fifo_slot_per_tick(self):
        env = Environment(seed=0, config=Config(delay_ticks=3))
        first = env.uplink([drive(), {"action": "wait"}])
        second = env.uplink([drive()])
        self.assertEqual([a["execute_tick"] for a in first + second], [4, 5, 6])
        self.assertEqual([a["command_id"] for a in first + second], [1, 2, 3])

    def test_idle_drain_and_fixed_horizon_survive_battery_death(self):
        env = Environment(seed=0, config=Config(delay_ticks=3, max_ticks=5,
                                               initial_battery=1))
        self.assertFalse(env.advance(2)["episode_complete"])
        self.assertTrue(env.telemetry_log()[-1]["alive"])
        final = env.advance(5)
        self.assertEqual(final["current_tick"], 5)
        self.assertTrue(final["episode_complete"])
        self.assertEqual(final["packets"][-1]["battery"], 0)
        self.assertFalse(final["packets"][-1]["alive"])
        self.assertEqual(env.advance()["packets"], [])
        with self.assertRaises(ValueError):
            env.uplink([{"action": "wait"}])

    def test_waiting_costs_idle_energy(self):
        env = Environment(seed=0, config=Config(delay_ticks=0))
        env.uplink([{"action": "wait"}])
        self.assertEqual(env.advance()["packets"][0]["battery"], 99.5)


class BoundaryTests(unittest.TestCase):
    def test_invalid_batch_is_atomic(self):
        invalid_commands = [
            drive(float("nan")), drive(float("inf")), drive(True), drive(0),
            drive(6), drive(heading=float("nan")), {"action": "teleport"},
            {"action": "wait", "metres": 2}, {"action": "drive", "metres": 2},
            "drive", None,
        ]
        for command in invalid_commands:
            with self.subTest(command=command):
                env = Environment(seed=0)
                before = env.telemetry_log()
                with self.assertRaises(ValueError):
                    env.uplink([drive(), command])
                self.assertEqual(env.telemetry_log(), before)
                self.assertEqual(env.uplink([drive()])[0]["command_id"], 1)

    def test_batch_and_advance_bounds(self):
        env = Environment(seed=0)
        for value in ([], [drive()] * 6, {}, None):
            with self.assertRaises(ValueError):
                env.uplink(value)
        for value in (0, -1, 6, True, 1.5, "1", None):
            with self.assertRaises(ValueError):
                env.advance(value)
        self.assertEqual(env.advance()["current_tick"], 1)

    def test_cannot_reserve_commands_beyond_horizon(self):
        env = Environment(seed=0, config=Config(delay_ticks=3, max_ticks=4))
        with self.assertRaises(ValueError):
            env.uplink([drive(), drive()])
        self.assertEqual(env.uplink([drive()])[0]["execute_tick"], 4)

    def test_reads_return_copies_without_hidden_state_or_time(self):
        env = Environment(seed=123)
        original = [env.rules(), env.map(), env.telemetry_log()]
        mutated = [env.rules(), env.map(), env.telemetry_log()]
        mutated[0]["slip_ranges"]["sand"][0] = 999
        mutated[1]["base"][0] = -999
        mutated[2][0]["position"][0] = -999
        self.assertEqual([env.rules(), env.map(), env.telemetry_log()], original)
        for result in original:
            self.assertNotIn("seed", result)
        self.assertEqual(env.advance()["current_tick"], 1)

    def test_configuration_and_geometry_reject_nonphysical_values(self):
        for values in ({"delay_ticks": -1}, {"delay_ticks": True},
                       {"max_ticks": 0}, {"initial_battery": float("nan")},
                       {"idle_cost": -1}, {"drive_cost": 0}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                Config(**values)
        with self.assertRaises(ValueError):
            Rect(4, 1, 3, 2)
        with self.assertRaises(ValueError):
            World(base=(-1, 20))
        with self.assertRaises(ValueError):
            Environment(seed=True)


class PhysicsTests(unittest.TestCase):
    def test_cardinal_drive_can_follow_the_map_edge(self):
        for base, heading in (((0, 20), 270), ((40, 20), 90),
                              ((20, 0), 180), ((20, 40), 0)):
            with self.subTest(base=base, heading=heading):
                env = Environment(seed=7, config=Config(delay_ticks=0),
                                  world=World(base=base, sand=()))
                env.uplink([drive(1, heading)])
                packet = env.advance()["packets"][0]
                self.assertGreater(packet["visual_odometry"], 0.9)
                self.assertNotIn("safety_stop", [event["type"] for event in packet["events"]])

    def test_map_edge_stops_motion_and_discards_queued_drives(self):
        env = Environment(seed=7, config=Config(delay_ticks=0),
                          world=World(base=(39.95, 20)))
        env.uplink([drive(), drive(heading=180)])
        first = env.advance()["packets"][0]
        second = env.advance()["packets"][0]
        self.assertLessEqual(first["position"][0], 40)
        self.assertIn("safety_stop", [event["type"] for event in first["events"]])
        self.assertEqual(first["position"], second["position"])

    def test_seed_and_actions_replay_identically_despite_reads_and_chunks(self):
        first, second = Environment(seed=7), Environment(seed=7)
        commands = [drive(), drive(heading=90), {"action": "wait"}]
        first.uplink(copy.deepcopy(commands))
        second.uplink(commands)
        commands[0]["metres"] = 5
        for _ in range(10):
            first.advance()
            second.rules()
            second.map()
            second.telemetry_log()
        second.advance(5)
        second.advance(5)
        self.assertEqual(first.telemetry_log(), second.telemetry_log())

    def test_sand_slips_more_and_costs_more_than_bedrock(self):
        bedrock = Environment(seed=7, config=Config(delay_ticks=0),
                              world=World(sand=()))
        sand = Environment(seed=7, config=Config(delay_ticks=0),
                           world=World(sand=(Rect(0, 0, 40, 40),)))
        for env in (bedrock, sand):
            env.uplink([drive()])
            env.advance()
        rock_packet, sand_packet = bedrock.telemetry_log()[-1], sand.telemetry_log()[-1]
        self.assertGreater(rock_packet["visual_odometry"], sand_packet["visual_odometry"])
        self.assertAlmostEqual(rock_packet["battery"], 97.5)
        self.assertAlmostEqual(sand_packet["battery"], 95.5)

    def test_drive_stops_when_energy_runs_out(self):
        env = Environment(seed=7, config=Config(delay_ticks=0, initial_battery=1))
        env.uplink([drive()])
        packet = env.advance()["packets"][0]
        self.assertEqual(packet["battery"], 0)
        self.assertFalse(packet["alive"])
        self.assertAlmostEqual(packet["wheel_odometry"], 0.5)
        self.assertLessEqual(packet["visual_odometry"], 0.5)


if __name__ == "__main__":
    unittest.main()
