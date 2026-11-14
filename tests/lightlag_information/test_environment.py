"""Contract checks for the isolated, delayed information-choice environment."""

import copy
import unittest
from dataclasses import FrozenInstanceError

from lightlag_information import CONTEXTS, Context, Environment


def finish(env):
    while env.telemetry_log()["current_tick"] < env.rules()["horizon"]:
        env.advance(5)
    return env.evaluate()


class EnvironmentTests(unittest.TestCase):
    def test_contexts_publish_all_route_and_sensor_parameters(self):
        self.assertEqual(set(CONTEXTS), {
            "uncertain", "likely_firm", "likely_soft", "costly_probe"
        })
        self.assertEqual(CONTEXTS["uncertain"], Context("uncertain", .5, 1))
        with self.assertRaises(FrozenInstanceError):
            CONTEXTS["uncertain"].prior_firm = .2
        rules = Environment(context=Context("fixture", .25, 2)).rules()
        self.assertEqual(rules["context"], {
            "id": "fixture", "prior_firm": .25, "probe_energy": 2
        })
        self.assertEqual(rules["routes"], {
            "shortcut": {"target_value": 10, "duration": 2,
                         "energy": {"firm": 4, "soft": 12}},
            "detour": {"target_value": 6, "duration": 6,
                       "energy": {"firm": 8, "soft": 8}},
        })
        self.assertEqual((rules["initial_energy"], rules["horizon"],
                          rules["delay"], rules["signal_accuracy"],
                          rules["penalty_per_tick"], rules["normalization"]),
                         (10, 30, 1, .9, .25, 10))

    def test_hidden_fixture_controls_never_change_initial_public_surfaces(self):
        a = Environment(seed=0, terrain="firm", signal="soft")
        b = Environment(seed=993, terrain="soft", signal="firm")
        for method in ("rules", "map", "telemetry_log"):
            self.assertEqual(getattr(a, method)(), getattr(b, method)())
        self.assertEqual(a.uplink([{"action": "probe"}]),
                         b.uplink([{"action": "probe"}]))
        self.assertEqual(a.advance(2), b.advance(2))

    def test_probe_signal_arrives_once_at_tick_three(self):
        env = Environment(terrain="soft", signal="firm")
        ack = env.uplink([{"action": "probe"}])
        self.assertEqual(ack, {"sent_tick": 0, "accepted": [
            {"action": "probe", "execution_tick": 2}
        ]})
        self.assertEqual(len(env.advance(2)["entries"]), 1)
        visible = env.advance()
        self.assertEqual(visible["current_tick"], 3)
        probe = visible["entries"][-1]
        self.assertEqual((probe["action"], probe["state_tick"],
                          probe["delivery_tick"], probe["signal"],
                          probe["energy"]), ("probe", 2, 3, "firm", 9))
        self.assertEqual(env.telemetry_log(), visible)
        self.assertEqual(env.telemetry_log(), visible)
        with self.assertRaises(ValueError):
            env.uplink([{"action": "probe"}])
        self.assertEqual(env.telemetry_log(), visible)

    def test_accepted_route_is_immutable_before_execution(self):
        env = Environment(terrain="firm")
        env.uplink([{"action": "commit", "route": "shortcut"}])
        for command in ({"action": "commit", "route": "detour"},
                        {"action": "commit", "route": "shortcut"},
                        {"action": "probe"}):
            with self.assertRaises(ValueError):
                env.uplink([command])
        result = finish(env)
        self.assertEqual(result["route"], "shortcut")
        self.assertEqual(result["reward"], .9)

    def test_invalid_batch_is_atomic_including_semantic_errors(self):
        invalid_batches = [
            [], [{"action": "wait"}] * 6, "probe", None,
            [{"action": "probe"}, {"action": "unknown"}],
            [{"action": "probe"}, {"action": "probe"}],
            [{"action": "commit", "route": "shortcut"}, {"action": "probe"}],
            [{"action": "commit", "route": "shortcut"},
             {"action": "commit", "route": "detour"}],
            [{"action": "probe", "extra": 3}],
            [{"action": "commit", "route": "unknown"}],
            [{"action": "commit"}], [None], [{"action": []}],
        ]
        for batch in invalid_batches:
            with self.subTest(batch=batch):
                env = Environment(terrain="firm")
                before = env.telemetry_log()
                with self.assertRaises(ValueError):
                    env.uplink(batch)
                self.assertEqual(env.telemetry_log(), before)
                accepted = env.uplink([
                    {"action": "probe"},
                    {"action": "commit", "route": "detour"}
                ])
                self.assertEqual([c["execution_tick"] for c in accepted["accepted"]],
                                 [2, 3])
                self.assertEqual(finish(env)["energy"], 1)

    def test_fifo_reservations_include_earlier_uplinks(self):
        env = Environment(terrain="firm")
        env.uplink([{"action": "wait"}] * 3)
        ack = env.uplink([{"action": "probe"},
                          {"action": "commit", "route": "shortcut"}])
        self.assertEqual([c["execution_tick"] for c in ack["accepted"]], [5, 6])
        result = finish(env)
        self.assertEqual(result["completion_tick"], 8)
        self.assertEqual(result["reward"], .8)

    def test_blind_probe_then_commit_in_one_batch_is_legal(self):
        env = Environment(terrain="firm", signal="soft")
        env.uplink([{"action": "probe"},
                    {"action": "commit", "route": "shortcut"}])
        result = finish(env)
        self.assertEqual(result["completion_tick"], 5)
        self.assertEqual(result["reward"], .875)
        self.assertEqual(result["energy"], 5)

    def test_execution_energy_stays_hidden_until_telemetry_arrival(self):
        firm = Environment(terrain="firm")
        soft = Environment(terrain="soft")
        command = [{"action": "commit", "route": "shortcut"}]
        self.assertEqual(firm.uplink(command), soft.uplink(command))
        self.assertEqual(firm.advance(2), soft.advance(2))
        firm_entry = firm.advance()["entries"][-1]
        soft_entry = soft.advance()["entries"][-1]
        self.assertEqual((firm_entry["energy"], firm_entry["status"]),
                         (6, "traveling"))
        self.assertEqual((soft_entry["energy"], soft_entry["status"]),
                         (0, "failed"))
        self.assertEqual(firm_entry["state_tick"], 2)
        self.assertEqual(soft_entry["delivery_tick"], 3)

    def test_direct_route_realized_rewards_and_completion(self):
        for terrain, route, reward, completion, energy in [
            ("firm", "shortcut", .9, 4, 6),
            ("soft", "shortcut", 0, None, 0),
            ("firm", "detour", .4, 8, 2),
            ("soft", "detour", .4, 8, 2),
        ]:
            with self.subTest(terrain=terrain, route=route):
                env = Environment(terrain=terrain)
                env.uplink([{"action": "commit", "route": route}])
                result = finish(env)
                self.assertEqual(result["reward"], reward)
                self.assertEqual(result["completion_tick"], completion)
                self.assertEqual(result["energy"], energy)
                self.assertEqual(result["success"], completion is not None)
                self.assertEqual(result["completed"], completion is not None)

    def test_adaptive_probe_timing_and_costly_probe_exhaustion(self):
        for context, route, terrain, reward, energy, completion in [
            ("uncertain", "shortcut", "firm", .825, 5, 7),
            ("uncertain", "detour", "soft", .325, 1, 11),
            ("costly_probe", "detour", "firm", 0, 0, None),
        ]:
            with self.subTest(context=context, route=route):
                env = Environment(context=context, terrain=terrain, signal=terrain)
                env.uplink([{"action": "probe"}])
                env.advance(3)
                ack = env.uplink([{"action": "commit", "route": route}])
                self.assertEqual(ack["accepted"][0]["execution_tick"], 5)
                result = finish(env)
                self.assertEqual((result["reward"], result["energy"],
                                  result["completion_tick"]),
                                 (reward, energy, completion))
                self.assertTrue(result["probe_used"])

    def test_public_results_and_input_commands_are_defensive_copies(self):
        env = Environment(terrain="firm")
        rules = env.rules()
        rules["routes"]["shortcut"]["energy"]["firm"] = 999
        public_map = env.map()
        original_map = copy.deepcopy(public_map)
        public_map.clear()
        self.assertEqual(env.map(), original_map)
        log = env.telemetry_log()
        log["entries"][0]["energy"] = 0
        commands = [{"action": "probe"},
                    {"action": "commit", "route": "shortcut"}]
        ack = env.uplink(commands)
        commands[1]["route"] = "detour"
        ack["accepted"][1]["route"] = "detour"
        visible = env.advance(3)
        visible["entries"][-1]["signal"] = "changed"
        result = finish(env)
        self.assertEqual((result["route"], result["energy"]), ("shortcut", 5))
        self.assertNotEqual(env.telemetry_log()["entries"][1]["signal"], "changed")
        result["reward"] = -1
        self.assertEqual(env.evaluate()["reward"], .875)
        replay = env.replay()
        replay["events"].clear()
        self.assertTrue(env.replay()["events"])

    def test_invalid_advance_preserves_clock_and_queue(self):
        env = Environment(terrain="firm")
        env.uplink([{"action": "probe"}])
        for ticks in (True, False, 0, -1, 6, 1.0, "1", None):
            with self.subTest(ticks=ticks):
                with self.assertRaises(ValueError):
                    env.advance(ticks)
                self.assertEqual(env.telemetry_log()["current_tick"], 0)
        self.assertEqual(env.advance(3)["entries"][-1]["energy"], 9)

    def test_evaluator_is_only_available_at_horizon(self):
        env = Environment(terrain="firm")
        for method in (env.evaluate, env.replay):
            with self.assertRaises(ValueError):
                method()
        self.assertEqual(finish(env)["reward"], 0)
        self.assertEqual(env.advance(5)["current_tick"], 30)
        with self.assertRaises(ValueError):
            env.uplink([{"action": "wait"}])

    def test_horizon_batch_validation_is_atomic(self):
        env = Environment(terrain="firm")
        for _ in range(5):
            env.advance(5)
        env.advance(2)
        with self.assertRaises(ValueError):
            env.uplink([{"action": "probe"}, {"action": "wait"},
                        {"action": "commit", "route": "shortcut"}])
        ack = env.uplink([{"action": "probe"},
                          {"action": "commit", "route": "shortcut"}])
        self.assertEqual([c["execution_tick"] for c in ack["accepted"]], [29, 30])
        self.assertEqual(env.advance(5)["current_tick"], 30)
        result = env.evaluate()
        self.assertEqual((result["reward"], result["status"], result["energy"]),
                         (0, "traveling", 5))
        self.assertEqual(env.telemetry_log()["entries"][-1]["action"], "probe")

    def test_completion_at_horizon_counts_before_telemetry_arrives(self):
        env = Environment(terrain="firm")
        for _ in range(5):
            env.advance(5)
        env.advance()
        env.uplink([{"action": "commit", "route": "shortcut"}])
        env.advance(5)
        result = env.evaluate()
        self.assertEqual((result["reward"], result["completion_tick"]), (.25, 30))
        self.assertEqual(env.telemetry_log()["entries"][-1]["action"], "commit")

    def test_completion_arrives_one_tick_after_physical_completion(self):
        env = Environment(terrain="firm")
        env.uplink([{"action": "commit", "route": "shortcut"}])
        self.assertEqual(env.advance(4)["entries"][-1]["action"], "commit")
        completed = env.advance()["entries"][-1]
        self.assertEqual((completed["action"], completed["state_tick"],
                          completed["delivery_tick"], completed["status"]),
                         ("complete", 4, 5, "complete"))

    def test_seeded_replay_is_deterministic_and_contains_public_transcript(self):
        def run():
            env = Environment(seed=17, context="likely_firm")
            env.rules()
            env.map()
            env.uplink([{"action": "probe"}])
            env.advance(3)
            env.uplink([{"action": "commit", "route": "detour"}])
            finish(env)
            return env.replay()
        replay = run()
        self.assertEqual(replay, run())
        self.assertEqual(replay["seed"], 17)
        self.assertIn(replay["terrain"], ("firm", "soft"))
        self.assertIn(replay["signal"], ("firm", "soft"))
        self.assertEqual(replay["transcript"][0]["method"], "rules")
        self.assertIn("result", replay["transcript"][0])
        self.assertEqual(replay["evaluation"]["reward"], .325)

    def test_terrain_and_signal_random_streams_are_independent(self):
        for seed in range(10):
            default = Environment(seed=seed)
            firm = Environment(seed=seed, terrain="firm")
            soft = Environment(seed=seed, terrain="soft")
            for env in (default, firm, soft):
                finish(env)
            actual, firm_replay, soft_replay = [
                env.replay() for env in (default, firm, soft)
            ]
            self.assertEqual(firm_replay["signal"] == "firm",
                             soft_replay["signal"] == "soft")
            comparison = firm_replay if actual["terrain"] == "firm" else soft_replay
            self.assertEqual(actual["signal"], comparison["signal"])


if __name__ == "__main__":
    unittest.main()
