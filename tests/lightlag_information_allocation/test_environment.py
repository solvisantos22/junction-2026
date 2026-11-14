"""Two hidden states, one shared observation budget and delayed commitments."""

from dataclasses import replace
import json
import unittest

from lightlag_information_allocation import Environment, Context, CONTEXTS


BASE = Context("fixture", .5, .5, 10, 9)


def finish(env):
    for _ in range(6):
        env.advance(5)
    return env.evaluate()


class EnvironmentTests(unittest.TestCase):
    def test_context_validation_and_frozen_parameters(self):
        for name, values in {"prior_a": [-.1, 1.1, True, float("nan")],
                             "prior_b": [float("inf"), "0.5"],
                             "value_a": [-1, 11, False], "value_b": [None],
                             "probe_energy": [-1, 11, True]}.items():
            for value in values:
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    replace(BASE, **{name: value})
        self.assertEqual(tuple(CONTEXTS), tuple("case_" + str(i) for i in range(1, 7)))
        with self.assertRaises(TypeError):
            CONTEXTS["new"] = BASE

    def test_fixture_validation_and_evaluator_requires_horizon(self):
        for fixture in ({"a": "firm"}, {"a": "firm", "b": "sand"},
                        {"a": "firm", "b": "soft", "c": "firm"}, []):
            for name in ("terrains", "signals"):
                with self.subTest(name=name, fixture=fixture), self.assertRaises(ValueError):
                    Environment(context=BASE, **{name: fixture})
        env = Environment(context=BASE)
        for method in (env.evaluate, env.replay):
            with self.assertRaises(ValueError):
                method()
        with self.assertRaises(ValueError):
            Environment(seed=True, context=BASE)

    def test_initial_public_surfaces_hide_all_seeded_state(self):
        envs = [Environment(seed, BASE) for seed in range(16)]
        for name, args in (("rules", {}), ("map", {}), ("telemetry_log", {}),
                           ("uplink", {"commands": [{"action": "probe", "route": "a"}]})):
            results = [getattr(env, name)(**args) for env in envs]
            self.assertTrue(all(result == results[0] for result in results))
            encoded = json.dumps(results[0])
            self.assertNotIn('"seed"', encoded)
            self.assertNotIn('"signals"', encoded)
            self.assertNotIn('"terrains"', encoded)

    def test_probe_reveals_only_target_at_delivery_tick(self):
        env = Environment(context=BASE, terrains={"a": "firm", "b": "soft"},
                          signals={"a": "soft", "b": "firm"})
        env.uplink([{"action": "probe", "route": "b"}])
        early = env.advance(2)
        self.assertEqual(len(early["entries"]), 1)
        delivered = env.advance(1)["entries"][-1]
        self.assertEqual((delivered["action"], delivered["probe_route"], delivered["signal"]),
                         ("probe", "b", "firm"))
        self.assertEqual((delivered["state_tick"], delivered["delivery_tick"], delivered["energy"]), (2, 3, 9))
        self.assertIsNone(delivered["route"])
        before = env.telemetry_log()
        self.assertEqual(env.telemetry_log(), before)
        self.assertNotIn('"terrains"', json.dumps(before))

    def test_other_route_state_and_signal_cannot_change_probe_result(self):
        logs = []
        for terrain_b in ("firm", "soft"):
            for signal_b in ("firm", "soft"):
                env = Environment(context=BASE, terrains={"a": "firm", "b": terrain_b},
                                  signals={"a": "soft", "b": signal_b})
                env.uplink([{"action": "probe", "route": "a"}])
                logs.append(env.advance(3))
        self.assertTrue(all(log == logs[0] for log in logs))

    def test_seed_streams_are_route_specific_and_replay_deterministic(self):
        combinations = set()
        for seed in range(32):
            first, second = Environment(seed, BASE), Environment(seed, BASE)
            finish(first); finish(second)
            self.assertEqual(first.replay(), second.replay())
            combinations.add(tuple(first.replay()["terrains"].values()))
            changed = Environment(seed, replace(BASE, prior_a=1))
            finish(changed)
            self.assertEqual(first.replay()["terrains"]["b"], changed.replay()["terrains"]["b"])
            self.assertEqual(first.replay()["signals"]["b"], changed.replay()["signals"]["b"])
        self.assertEqual(combinations, {("firm", "firm"), ("firm", "soft"), ("soft", "firm"), ("soft", "soft")})

    def test_one_shared_probe_rejects_repeated_and_other_route(self):
        for second in ("a", "b"):
            env = Environment(context=BASE)
            env.uplink([{"action": "probe", "route": "a"}])
            with self.assertRaisesRegex(ValueError, "shared probe"):
                env.uplink([{"action": "probe", "route": second}])
            env.advance(3)
            self.assertEqual(env.telemetry_log()["entries"][-1]["energy"], 9)

    def test_rejected_two_probe_batch_is_atomic(self):
        env = Environment(context=BASE)
        with self.assertRaises(ValueError):
            env.uplink([{"action": "probe", "route": "a"}, {"action": "probe", "route": "b"}])
        ack = env.uplink([{"action": "probe", "route": "b"}])
        self.assertEqual(ack["accepted"][0]["execution_tick"], 2)
        self.assertEqual(finish(env)["probe_route"], "b")

    def test_commit_is_irrevocable_at_acceptance(self):
        env = Environment(context=BASE)
        env.uplink([{"action": "commit", "route": "a"}])
        for command in ({"action": "commit", "route": "b"}, {"action": "probe", "route": "b"}):
            with self.assertRaises(ValueError):
                env.uplink([command])
        self.assertEqual(env.telemetry_log()["current_tick"], 0)

    def test_probe_and_commit_same_batch_cannot_adapt(self):
        env = Environment(context=BASE, terrains={"a": "firm", "b": "firm"})
        ack = env.uplink([{"action": "probe", "route": "a"}, {"action": "commit", "route": "b"}])
        self.assertEqual([cmd["execution_tick"] for cmd in ack["accepted"]], [2, 3])
        with self.assertRaises(ValueError):
            env.uplink([{"action": "commit", "route": "a"}])
        result = finish(env)
        self.assertEqual((result["route"], result["completion_tick"], result["reward"]), ("b", 5, .775))

    def test_adaptive_route_timing_and_actual_route_ground(self):
        env = Environment(context=BASE, terrains={"a": "soft", "b": "firm"},
                          signals={"a": "soft", "b": "firm"})
        env.uplink([{"action": "probe", "route": "a"}])
        env.advance(3)
        env.uplink([{"action": "commit", "route": "b"}])
        result = finish(env)
        self.assertEqual((result["route"], result["probe_route"], result["completion_tick"], result["energy"]), ("b", "a", 7, 5))
        self.assertEqual(result["reward"], .725)

    def test_soft_selected_route_fails_despite_other_route_firm(self):
        for selected in ("a", "b"):
            terrain = {"a": "firm", "b": "firm"}; terrain[selected] = "soft"
            env = Environment(context=BASE, terrains=terrain)
            env.uplink([{"action": "commit", "route": selected}])
            result = finish(env)
            self.assertEqual((result["reward"], result["status"], result["energy"]), (0, "failed", 0))

    def test_detour_exact_energy_and_insufficient_energy(self):
        for probe_cost, expected in ((2, .325), (3, 0)):
            env = Environment(context=replace(BASE, probe_energy=probe_cost))
            env.uplink([{"action": "probe", "route": "a"}]); env.advance(3)
            env.uplink([{"action": "commit", "route": "detour"}])
            self.assertEqual(finish(env)["reward"], expected)

    def test_strict_schemas_clock_and_horizon_atomicity(self):
        invalid = [[{"action": "probe"}], [{"action": "probe", "route": "detour"}],
                   [{"action": "probe", "route": "a", "seed": 4}], [{"action": "wait", "route": "a"}],
                   [{"action": "commit", "route": []}], [{"action": "probe", "route": "a"}, {"action": "oops"}]]
        for commands in invalid:
            env = Environment(context=BASE)
            with self.assertRaises(ValueError): env.uplink(commands)
            self.assertEqual(env.uplink([{"action": "commit", "route": "detour"}])["accepted"][0]["execution_tick"], 2)
        env = Environment(context=BASE)
        for ticks in (True, 0, 6, 1.5, "1"):
            with self.assertRaises(ValueError): env.advance(ticks)
        for _ in range(5): env.advance(5)
        env.advance(3)
        with self.assertRaises(ValueError): env.uplink([{"action": "wait"}, {"action": "commit", "route": "detour"}])
        self.assertEqual(env.uplink([{"action": "wait"}])["accepted"][0]["execution_tick"], 30)
        self.assertEqual(env.advance(5)["current_tick"], 30)

    def test_returned_data_and_arguments_cannot_mutate_episode(self):
        env = Environment(context=BASE, terrains={"a": "firm", "b": "firm"})
        rules = env.rules(); rules["routes"]["a"]["target_value"] = 999
        rules["priors_firm"]["b"] = 0
        command = {"action": "commit", "route": "a"}
        ack = env.uplink([command]); command["route"] = "b"; ack["accepted"][0]["route"] = "b"
        self.assertEqual(finish(env)["reward"], .9)
        replay = env.replay(); replay["terrains"]["a"] = "soft"
        self.assertEqual(env.replay()["terrains"]["a"], "firm")
        self.assertEqual(env.rules()["priors_firm"]["b"], .5)


if __name__ == "__main__":
    unittest.main()
