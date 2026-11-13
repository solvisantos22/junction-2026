import copy
import json
import unittest

from lightlag import Config, Environment, Target, World
from lightlag.controllers.api import PublicTools
from lightlag.controllers.baselines import do_nothing
from lightlag.evaluation import run_episode


TOOL_NAMES = {"rules", "map", "telemetry_log", "uplink", "advance"}


class EvaluationTests(unittest.TestCase):
    def test_policy_receives_only_the_five_public_callbacks(self):
        def inspect_tools(tools):
            self.assertIsInstance(tools, PublicTools)
            self.assertNotIsInstance(tools, Environment)
            self.assertEqual({name for name in dir(tools) if not name.startswith("_")},
                             TOOL_NAMES)
            for name in TOOL_NAMES:
                self.assertTrue(callable(getattr(tools, name)))
            for name in ("environment", "seed", "config", "world", "evaluate", "replay",
                         "_seed", "_config", "_world", "_slip", "_truth"):
                self.assertFalse(hasattr(tools, name), name)
            rules = tools.rules()
            public_map = tools.map()
            self.assertEqual(rules["delay_ticks"], 0)
            self.assertEqual(public_map["targets"][0]["id"], "home")
            self.assertNotIn("seed", rules)
            self.assertNotIn("slip_coefficients", rules)
            self.assertEqual(tools.telemetry_log()[0]["tick"], 0)
            tools.uplink([{"action": "sample"}])
            self.assertEqual(tools.advance()["current_tick"], 1)

        run = run_episode(inspect_tools, seed=99, config=Config(delay_ticks=0, max_ticks=3),
                          world=World(targets=(Target("home", 20, 20),)))
        self.assertEqual(run["result"]["raw_score"], 1)
        self.assertEqual(run["tool_calls"]["policy"], 5)
        self.assertEqual(run["tool_calls"]["by_tool"]["policy"],
                         {name: 1 for name in TOOL_NAMES})

    def test_do_nothing_still_runs_the_default_full_horizon(self):
        run = run_episode(do_nothing, seed=7, config=Config(delay_ticks=3),
                          policy_name="do_nothing")
        self.assertEqual((run["policy"], run["seed"], run["delay"]), ("do_nothing", 7, 3))
        self.assertEqual(run["result"]["tick"], 80)
        self.assertEqual(run["result"]["raw_score"], 0)
        self.assertEqual(len(run["replay"]["states"]), 81)
        self.assertEqual(run["replay"]["states"][-1]["battery"], 60)
        self.assertEqual(run["replay"]["commands"], [])
        self.assertEqual(run["tool_calls"]["policy"], 0)
        self.assertEqual(run["tool_calls"]["evaluator"], 17)
        self.assertEqual(run["tool_calls"]["total"], len(run["transcript"]))
        self.assertTrue(all(call["source"] == "evaluator" for call in run["transcript"]))

    def test_early_return_cannot_keep_science_credit_before_later_battery_death(self):
        def sample_and_return(tools):
            tools.uplink([{"action": "sample"}])
            packet = tools.advance()["packets"][0]
            self.assertTrue(packet["alive"])
            self.assertEqual(packet["sampled_targets"], ["home"])

        run = run_episode(sample_and_return, config=Config(delay_ticks=0, max_ticks=4,
                                                          initial_battery=4),
                          world=World(targets=(Target("home", 20, 20, 2),)))
        self.assertEqual(run["result"]["tick"], 4)
        self.assertEqual(run["result"]["sampled_value"], 2)
        self.assertFalse(run["result"]["alive"])
        self.assertEqual(run["result"]["raw_score"], 0)
        self.assertEqual(run["transcript"][-1]["source"], "evaluator")
        self.assertEqual(run["transcript"][-1]["request"], {"ticks": 3})
        self.assertEqual(run["transcript"][-1]["result"]["current_tick"], 4)

    def test_policy_can_complete_the_horizon_without_extra_evaluator_advances(self):
        def finish(tools):
            self.assertTrue(tools.advance(5)["episode_complete"])

        run = run_episode(finish, config=Config(max_ticks=2))
        evaluator_calls = [call["tool"] for call in run["transcript"]
                           if call["source"] == "evaluator"]
        self.assertEqual(evaluator_calls, ["rules"])
        self.assertEqual(run["tool_calls"]["policy"], 1)
        self.assertEqual(run["tool_calls"]["evaluator"], 1)

    def test_repeated_seed_gets_fresh_environment_and_preserves_inputs(self):
        config = Config(delay_ticks=0, max_ticks=3)
        world = World(sand=(), targets=(Target("home", 20, 20, 2),))
        before_config, before_world = copy.deepcopy(config), copy.deepcopy(world)
        seen_tools = []

        def sample(tools):
            seen_tools.append(tools)
            self.assertEqual(tools.telemetry_log()[0]["sampled_targets"], [])
            ack = tools.uplink([{"action": "sample"}])
            self.assertEqual(ack[0]["command_id"], 1)
            tools.map()["targets"][0]["value"] = -1
            tools.rules()["sample_cost"] = -1

        first = run_episode(sample, seed=7, config=config, world=world)
        first_copy = copy.deepcopy(first)
        second = run_episode(sample, seed=7, config=config, world=world)
        self.assertIsNot(seen_tools[0], seen_tools[1])
        self.assertEqual(first, second)
        second["replay"]["states"][0]["position"][0] = -1
        self.assertEqual(first, first_copy)
        self.assertEqual(config, before_config)
        self.assertEqual(world, before_world)

    def test_policy_exception_is_raised_instead_of_scored(self):
        failure = RuntimeError("policy failed deliberately")

        def broken(tools):
            tools.advance()
            raise failure

        with self.assertRaises(RuntimeError) as caught:
            run_episode(broken)
        self.assertIs(caught.exception, failure)

    def test_invalid_public_requests_fail_the_run_visibly(self):
        for policy in (lambda tools: tools.advance(6),
                       lambda tools: tools.uplink([{"action": "teleport"}]),
                       lambda tools: tools.uplink([])):
            with self.subTest(policy=policy), self.assertRaises(ValueError):
                run_episode(policy)

    def test_policy_cannot_hide_an_invalid_request_by_catching_the_error(self):
        caught_failures = []

        def catch_and_return(tools):
            try:
                tools.advance(6)
            except ValueError as failure:
                caught_failures.append(failure)
            self.assertEqual(tools.rules()["max_ticks"], 80)

        with self.assertRaises(ValueError) as caught:
            run_episode(catch_and_return)
        self.assertIs(caught.exception, caught_failures[0])

    def test_first_caught_tool_failure_is_preserved_after_later_tool_failures(self):
        caught_failures = []

        def catch_twice(tools):
            for request in (lambda: tools.advance(6), lambda: tools.uplink([])):
                try:
                    request()
                except ValueError as failure:
                    caught_failures.append(failure)

        with self.assertRaises(ValueError) as caught:
            run_episode(catch_twice)
        self.assertIs(caught.exception, caught_failures[0])

    def test_policy_cannot_hide_argument_binding_errors(self):
        requests = {
            "missing argument": lambda tools: tools.uplink(),
            "extra keyword": lambda tools: tools.advance(unknown=1),
            "extra positional": lambda tools: tools.rules(1),
            "duplicate argument": lambda tools: tools.advance(1, ticks=1),
            "helper keyword": lambda tools: tools.advance(source="policy"),
        }
        for name, request in requests.items():
            caught_failures = []

            def catch_and_return(tools):
                try:
                    request(tools)
                except TypeError as failure:
                    caught_failures.append(failure)
                tools.rules()

            with self.subTest(request=name):
                with self.assertRaises(TypeError) as caught:
                    run_episode(catch_and_return)
                self.assertIs(caught.exception, caught_failures[0])

    def test_transcript_requests_and_replies_are_isolated_from_policy_mutation(self):
        received = []

        def mutate(tools):
            rules = tools.rules()
            public_map = tools.map()
            telemetry = tools.telemetry_log()
            commands = [{"action": "drive", "heading_deg": 0, "metres": 1}]
            ack = tools.uplink(commands)
            reply = tools.advance()
            received.extend([rules, public_map, telemetry, commands, ack, reply])
            rules["slip_ranges"]["sand"][0] = -1
            public_map["base"][0] = -1
            telemetry[0]["position"][0] = -1
            commands[0]["metres"] = 5
            ack[0]["command"]["metres"] = 5
            reply["current_tick"] = 999
            reply["packets"][0]["position"][0] = -1

        run = run_episode(mutate, config=Config(delay_ticks=0, max_ticks=2))
        calls = {call["tool"]: call for call in run["transcript"]
                 if call["source"] == "policy"}
        self.assertEqual(calls["rules"]["result"]["slip_ranges"]["sand"][0], 0.2)
        self.assertEqual(calls["map"]["result"]["base"], [20, 20])
        self.assertEqual(calls["telemetry_log"]["result"][0]["position"], [20, 20])
        self.assertEqual(calls["uplink"]["request"]["commands"][0]["metres"], 1)
        self.assertEqual(calls["uplink"]["result"][0]["command"]["metres"], 1)
        self.assertEqual(calls["advance"]["request"], {"ticks": 1})
        self.assertEqual(calls["advance"]["result"]["current_tick"], 1)
        self.assertGreater(calls["advance"]["result"]["packets"][0]["position"][0], 20)
        self.assertEqual(run["result"]["tick"], 2)
        self.assertEqual(run["replay"]["commands"][0]["command"]["metres"], 1)
        calls["map"]["result"]["targets"].clear()
        self.assertEqual(len(received[1]["targets"]), 3)
        calls["advance"]["result"]["packets"][0]["position"][0] = -2
        self.assertGreater(run["replay"]["states"][1]["position"][0], 20)

    def test_runs_serialize_to_identical_json_without_timestamps(self):
        def drive(tools):
            tools.uplink([{"action": "drive", "heading_deg": 0, "metres": 1}])
            tools.advance(2)

        config = Config(max_ticks=6)
        first = run_episode(drive, seed=7, config=config)
        second = run_episode(drive, seed=7, config=config)
        serialized = json.dumps(first, sort_keys=True, allow_nan=False)
        self.assertEqual(serialized, json.dumps(second, sort_keys=True, allow_nan=False))
        self.assertEqual(first["policy"], "drive")
        self.assertNotIn("timestamp", serialized)
        self.assertNotIn("elapsed", serialized)
        self.assertNotEqual(first["replay"]["slip_coefficients"],
                            run_episode(drive, seed=8, config=config)["replay"]["slip_coefficients"])

    def test_completed_artifact_is_independent_of_retained_public_callbacks(self):
        retained = []

        def retain_tools(tools):
            retained.append(tools)

        run = run_episode(retain_tools, config=Config(max_ticks=1))
        before = copy.deepcopy(run)
        retained[0].rules()
        retained[0].advance()
        self.assertEqual(run, before)


if __name__ == "__main__":
    unittest.main()
