import unittest

from lightlag import Config, Environment, Rect, Target, World


SAMPLE = {"action": "sample"}


def drive(metres, heading=0):
    return {"action": "drive", "heading_deg": heading, "metres": metres}


def finish(env):
    while not env.advance(5)["episode_complete"]:
        pass
    return env.evaluate()


class MissionTests(unittest.TestCase):
    def test_sampling_at_base_counts_once_and_drains_energy_each_time(self):
        env = Environment(seed=0, config=Config(delay_ticks=0, max_ticks=2),
                          world=World(targets=(Target("home", 20, 20, 2),)))
        env.uplink([SAMPLE, SAMPLE])
        packet = env.advance(2)["packets"][-1]
        self.assertEqual(packet["sampled_targets"], ["home"])
        self.assertEqual(packet["battery"], 93)
        score = env.evaluate()
        self.assertEqual(score["sampled_value"], 2)
        self.assertEqual(score["survival_factor"], 1)
        self.assertEqual(score["raw_score"], 2)

    def test_sample_uses_current_true_position_before_telemetry_arrives(self):
        env = Environment(seed=7, config=Config(delay_ticks=3, max_ticks=6),
                          world=World(sand=(), targets=(Target("near", 22, 20, 2),)))
        env.uplink([drive(2), SAMPLE])
        env.advance(5)
        self.assertEqual(env.telemetry_log()[-1]["position"], [20, 20])
        self.assertEqual(env.telemetry_log()[-1]["sampled_targets"], [])
        score = finish(env)
        self.assertEqual(score["sampled_value"], 2)
        self.assertEqual(score["survival_factor"], 0.5)
        self.assertEqual(score["raw_score"], 1)

    def test_sampling_out_of_range_or_doing_nothing_scores_zero(self):
        for commands in ([SAMPLE], [{"action": "wait"}]):
            with self.subTest(commands=commands):
                env = Environment(seed=0, config=Config(delay_ticks=0, max_ticks=2))
                env.uplink(commands)
                self.assertEqual(finish(env)["raw_score"], 0)

    def test_cannot_award_a_target_by_claim_or_partial_sample_energy(self):
        env = Environment(seed=0, config=Config(delay_ticks=0, max_ticks=1,
                                               initial_battery=3),
                          world=World(targets=(Target("home", 20, 20, 2),)))
        with self.assertRaises(ValueError):
            env.uplink([{"action": "sample", "target": "home"}])
        env.uplink([SAMPLE])
        self.assertEqual(finish(env)["sampled_value"], 0)

    def test_battery_death_erases_survival_credit(self):
        env = Environment(seed=0, config=Config(delay_ticks=0, max_ticks=3,
                                               initial_battery=4),
                          world=World(targets=(Target("home", 20, 20, 2),)))
        env.uplink([SAMPLE])
        score = finish(env)
        self.assertEqual(score["sampled_value"], 2)
        self.assertEqual(score["survival_factor"], 0)
        self.assertEqual(score["raw_score"], 0)

    def test_return_to_base_restores_full_credit(self):
        env = Environment(seed=7, config=Config(delay_ticks=0, max_ticks=3),
                          world=World(sand=(), targets=(Target("near", 22, 20, 2),)))
        env.uplink([drive(2), SAMPLE, drive(2, 180)])
        score = finish(env)
        self.assertTrue(score["at_base"])
        self.assertEqual(score["raw_score"], 2)

    def test_score_cannot_end_the_episode_early(self):
        env = Environment(seed=0, config=Config(max_ticks=4))
        with self.assertRaises(ValueError):
            env.evaluate()
        self.assertEqual(finish(env)["tick"], 4)

    def test_one_sample_collects_only_the_nearest_unsampled_target(self):
        env = Environment(seed=0, config=Config(delay_ticks=0, max_ticks=1),
                          world=World(targets=(Target("farther", 20.5, 20, 3),
                                               Target("nearest", 20.1, 20, 2))))
        env.uplink([SAMPLE])
        self.assertEqual(finish(env)["sampled_targets"], ["nearest"])


class SafetyTests(unittest.TestCase):
    def test_thin_hazard_blocks_whole_segment_and_drops_queue(self):
        env = Environment(seed=7, config=Config(delay_ticks=0, max_ticks=3),
                          world=World(sand=(), hazards=(Rect(20.01, 19, 20.02, 21),),
                                      targets=(Target("home", 20, 20),)))
        env.uplink([drive(2), SAMPLE])
        packet = env.advance()["packets"][0]
        self.assertEqual(packet["position"], [20, 20])
        self.assertIn({"type": "safety_stop", "reason": "hazard"}, packet["events"])
        self.assertEqual(finish(env)["raw_score"], 0)

    def test_unseen_safety_stop_cannot_leak_via_uplink_reservations(self):
        config = Config(delay_ticks=3, max_ticks=12)
        blocked = Environment(seed=7, config=config,
                              world=World(sand=(), hazards=(Rect(20.01, 19, 20.02, 21),)))
        clear = Environment(seed=7, config=config, world=World(sand=(), hazards=()))
        commands = [drive(2)] * 5
        for env in (blocked, clear):
            env.uplink(commands)
            env.advance(4)
        self.assertEqual(blocked.telemetry_log(), clear.telemetry_log())
        self.assertEqual(blocked.uplink([SAMPLE]), clear.uplink([SAMPLE]))

    def test_hazard_intersection_does_not_block_a_clear_parallel_drive(self):
        env = Environment(seed=7, config=Config(delay_ticks=0),
                          world=World(sand=(), hazards=(Rect(20.01, 21, 20.02, 22),)))
        env.uplink([drive(2)])
        packet = env.advance()["packets"][0]
        self.assertGreater(packet["visual_odometry"], 1.8)
        self.assertNotIn("safety_stop", [event["type"] for event in packet["events"]])


if __name__ == "__main__":
    unittest.main()
