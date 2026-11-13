import copy
import csv
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from lightlag import Config, Environment, Target, World
from lightlag.controllers import POLICIES
from lightlag.controllers.api import PublicTools
from lightlag.controllers.baselines import do_nothing
from lightlag import evaluation
from lightlag.evaluation import run_episode


TOOL_NAMES = {"rules", "map", "telemetry_log", "uplink", "advance"}
ROOT = Path(__file__).resolve().parents[2]


def run_comparison_cli(*arguments):
    return subprocess.run([sys.executable, "-m", "lightlag.evaluation", *arguments],
                          capture_output=True, text=True, cwd=ROOT, timeout=30)


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


class ComparisonTests(unittest.TestCase):
    @staticmethod
    def collect_west(tools):
        tools.uplink([
            {"action": "drive", "heading_deg": 180, "metres": 5},
            {"action": "drive", "heading_deg": 180, "metres": 1},
            {"action": "sample"},
            {"action": "drive", "heading_deg": 0, "metres": 5},
            {"action": "drive", "heading_deg": 0, "metres": 1},
        ])

    def test_matrix_preserves_requested_order_and_uses_fresh_episodes(self):
        retained_tools = []
        observations = []

        def observe(name):
            def policy(tools):
                retained_tools.append(tools)
                rules = tools.rules()
                public_map = tools.map()
                briefing = tools.telemetry_log()
                ack = tools.uplink([{"action": "wait"}])
                observations.append((name, rules["delay_ticks"], briefing[0]["tick"],
                                     ack[0]["command_id"]))
                public_map["targets"].clear()
                rules["initial_battery"] = -1
            return policy

        policies = {name: observe(name) for name in ("second", "first")}
        batch = evaluation.run_comparison(policies, seeds=(3, 1), delays=(3, 0), ticks=8)
        summary, episodes = batch["summary"], batch["episodes"]
        expected = [(name, seed, delay) for name in policies
                    for delay in (3, 0) for seed in (3, 1)]
        self.assertEqual([(row["policy"], row["seed"], row["delay"])
                          for row in summary["runs"]], expected)
        self.assertEqual([(episode["policy"], episode["seed"], episode["delay"])
                          for episode in episodes], expected)
        self.assertEqual(observations, [(name, delay, 0, 1) for name, _, delay in expected])
        self.assertEqual(len({id(tools) for tools in retained_tools}), len(expected))
        for row, episode in zip(summary["runs"], episodes):
            self.assertEqual(episode["result"]["tick"], 8)
            self.assertEqual(len(episode["replay"]["states"]), 9)
            self.assertEqual(episode["rules"]["initial_battery"], 100)
            self.assertEqual(len(episode["replay"]["world"]["targets"]), 3)
            self.assertEqual(row["raw_score"], 0)
            self.assertEqual(row["sampled_value"], 0)
            self.assertTrue(row["alive"])
            self.assertTrue(row["at_base"])
            self.assertTrue(row["alive_and_at_base"])
            self.assertEqual(row["policy_calls"], 4)
            self.assertEqual(row["evaluator_calls"], 3)

    def test_summary_records_actual_reproducible_rules_and_default_world(self):
        batch = evaluation.run_comparison({"idle": do_nothing}, seeds=(0,),
                                          delays=(3, 0), ticks=7)
        summary = batch["summary"]
        self.assertEqual(summary["version"], "lightlag-comparison-v1")
        self.assertEqual(summary["rules_version"], "lightlag-core-v1")
        self.assertEqual(summary["seeds"], [0])
        self.assertEqual(summary["delays"], [3, 0])
        self.assertEqual(summary["ticks"], 7)
        self.assertEqual(summary["policies"], ["idle"])
        self.assertEqual(summary["reference_policy"], "reference")
        self.assertEqual(summary["run_order"], "policy/delay/seed")
        self.assertEqual(summary["world"], World().public_map())
        self.assertEqual(summary["rules"], [Environment(config=Config(delay_ticks=delay,
                                                                 max_ticks=7)).rules()
                                          for delay in (3, 0)])
        self.assertNotIn("episodes", summary)
        self.assertNotIn("replay", summary["runs"][0])

    def test_default_matrix_and_default_policy_selection_remain_local(self):
        summary = evaluation.run_comparison({"idle": do_nothing})["summary"]
        self.assertEqual(summary["seeds"], list(range(10)))
        self.assertEqual(summary["delays"], [0, 3])
        self.assertEqual(summary["ticks"], 80)
        self.assertEqual(len(summary["runs"]), 20)
        local = evaluation.run_comparison(seeds=(0,), delays=(0,), ticks=1)["summary"]
        self.assertEqual(local["policies"], list(POLICIES))
        self.assertEqual(len(local["runs"]), 6)

    def test_repeated_comparisons_are_deterministic_with_independent_seed_truth(self):
        def drive(tools):
            tools.uplink([{"action": "drive", "heading_deg": 0, "metres": 1}])

        arguments = {"policies": {"drive": drive}, "seeds": (0, 1), "delays": (0, 3),
                     "ticks": 8}
        first = evaluation.run_comparison(**arguments)
        second = evaluation.run_comparison(**arguments)
        self.assertEqual(json.dumps(first, sort_keys=True, allow_nan=False),
                         json.dumps(second, sort_keys=True, allow_nan=False))
        episodes = first["episodes"]
        self.assertEqual(episodes[0]["replay"]["slip_coefficients"],
                         episodes[2]["replay"]["slip_coefficients"])
        self.assertNotEqual(episodes[0]["replay"]["slip_coefficients"],
                            episodes[1]["replay"]["slip_coefficients"])
        before = copy.deepcopy(first)
        second["episodes"][0]["replay"]["states"][0]["position"][0] = -1
        self.assertEqual(first, before)

    def test_ratios_match_each_seed_and_delay_without_clipping(self):
        def reference(tools):
            if tools.rules()["delay_ticks"] == 0:
                tools.uplink([
                    {"action": "drive", "heading_deg": 180, "metres": 5},
                    {"action": "drive", "heading_deg": 180, "metres": 1},
                    {"action": "sample"},
                ])

        summary = evaluation.run_comparison(
            {"candidate": self.collect_west, "denominator": reference},
            seeds=(1, 0), delays=(0, 3), ticks=12, reference_policy="denominator")["summary"]
        self.assertEqual(summary["reference_policy"], "denominator")
        for row in summary["runs"]:
            self.assertEqual(row["sampled_value"], 0 if row["policy"] == "denominator"
                             and row["delay"] == 3 else 1)
            if row["delay"] == 0:
                self.assertEqual(row["reference_ratio"],
                                 2 if row["policy"] == "candidate" else 1)
                self.assertIsNone(row["reference_ratio_reason"])
            else:
                self.assertIsNone(row["reference_ratio"])
                self.assertEqual(row["reference_ratio_reason"], "zero_reference_score")
        aggregates = summary["aggregates"]
        self.assertEqual([(row["policy"], row["delay"]) for row in aggregates],
                         [("candidate", 0), ("candidate", 3),
                          ("denominator", 0), ("denominator", 3)])
        self.assertEqual(aggregates[0]["mean_reference_ratio"], 2)
        self.assertEqual(aggregates[0]["reference_ratio_defined_count"], 2)
        self.assertEqual(aggregates[0]["reference_ratio_undefined_count"], 0)
        self.assertIsNone(aggregates[1]["mean_reference_ratio"])
        self.assertEqual(aggregates[1]["reference_ratio_defined_count"], 0)
        self.assertEqual(aggregates[1]["reference_ratio_undefined_count"], 2)

    def test_mean_ratio_excludes_undefined_seed_but_counts_it(self):
        def conditional_reference(tools):
            tools.uplink([{"action": "drive", "heading_deg": 180, "metres": 5}])
            position = tools.advance()["packets"][-1]["position"]
            # Seeds 0 and 1 visibly move different distances under default physics.
            if position[0] < 15.15:
                tools.uplink([
                    {"action": "drive", "heading_deg": 180, "metres": 1},
                    {"action": "sample"},
                ])

        summary = evaluation.run_comparison(
            {"candidate": self.collect_west, "reference": conditional_reference},
            seeds=(0, 1), delays=(0,), ticks=12)["summary"]
        self.assertEqual([row["raw_score"] for row in summary["runs"]], [1, 1, 0, 0.5])
        self.assertEqual([row["reference_ratio"] for row in summary["runs"]],
                         [None, 2, None, 1])
        candidate, reference = summary["aggregates"]
        self.assertEqual(candidate["run_count"], 2)
        self.assertEqual(candidate["mean_reference_ratio"], 2)
        self.assertEqual(candidate["reference_ratio_defined_count"], 1)
        self.assertEqual(candidate["reference_ratio_undefined_count"], 1)
        self.assertEqual(reference["mean_raw_score"], 0.25)
        self.assertEqual(reference["min_raw_score"], 0)
        self.assertEqual(reference["max_raw_score"], 0.5)
        self.assertEqual(reference["survival_rate"], 1)
        self.assertEqual(reference["return_rate"], 0)

    def test_unselected_reference_keeps_raw_scores_and_explicit_missing_ratios(self):
        summary = evaluation.run_comparison(
            {"candidate": self.collect_west}, seeds=(0, 1), delays=(0,), ticks=12,
            reference_policy="unselected")["summary"]
        self.assertEqual(summary["reference_policy"], "unselected")
        for row in summary["runs"]:
            self.assertEqual(row["raw_score"], 1)
            self.assertIsNone(row["reference_ratio"])
            self.assertEqual(row["reference_ratio_reason"], "missing_reference")
        aggregate = summary["aggregates"][0]
        self.assertEqual(aggregate["mean_raw_score"], 1)
        self.assertEqual(aggregate["survival_rate"], 1)
        self.assertEqual(aggregate["return_rate"], 1)
        self.assertIsNone(aggregate["mean_reference_ratio"])
        self.assertEqual(aggregate["reference_ratio_defined_count"], 0)
        self.assertEqual(aggregate["reference_ratio_undefined_count"], 2)

    def test_dead_at_base_is_not_a_successful_return_and_keeps_sampled_value(self):
        summary = evaluation.run_comparison(
            {"candidate": self.collect_west}, seeds=(0,), delays=(0,), ticks=200)["summary"]
        row, aggregate = summary["runs"][0], summary["aggregates"][0]
        self.assertEqual(row["sampled_value"], 1)
        self.assertEqual(row["raw_score"], 0)
        self.assertTrue(row["at_base"])
        self.assertFalse(row["alive"])
        self.assertFalse(row["alive_and_at_base"])
        self.assertEqual(aggregate["return_rate"], 0)
        self.assertEqual(aggregate["survival_rate"], 0)
        self.assertEqual(aggregate["mean_policy_calls"], 1)
        self.assertEqual(aggregate["mean_evaluator_calls"], 41)

    def test_invalid_inputs_are_rejected_before_any_policy_runs(self):
        calls = []

        def observe(tools):
            calls.append(tools)

        invalid = [
            {"policies": {}}, {"policies": [("valid", observe)]},
            {"policies": {"valid": observe, "invalid": object()}},
            {"seeds": ()}, {"seeds": (0, 0)}, {"seeds": (0, True)},
            {"seeds": (0, 1.0)}, {"seeds": (0, "1")}, {"seeds": None},
            {"delays": ()}, {"delays": (0, 0)}, {"delays": (0, True)},
            {"delays": (0, -1)}, {"delays": (0, 1.0)}, {"delays": (0, "1")},
            {"delays": None},
        ]
        invalid.extend({"ticks": value} for value in (True, 0, -1, 1.5, "2", None))
        for name in ("", ".", "..", "../escape", "path/name", "path\\name", "has space",
                     "line\nbreak", 3, True, None):
            invalid.append({"policies": {"valid": observe, name: observe}})
            invalid.append({"reference_policy": name})
        for overrides in invalid:
            calls.clear()
            arguments = {"policies": {"valid": observe}, "seeds": (0,),
                         "delays": (0,), "ticks": 8}
            arguments.update(overrides)
            with self.subTest(overrides=overrides):
                with self.assertRaises(ValueError):
                    evaluation.run_comparison(**arguments)
                self.assertEqual(calls, [], "validation must precede every policy")

    def test_safe_unselected_reference_is_accepted(self):
        summary = evaluation.run_comparison({"policy.v2": do_nothing}, seeds=(0,),
                                          delays=(0,), ticks=1,
                                          reference_policy="external-ref_v2")["summary"]
        self.assertEqual(summary["seeds"], [0])
        self.assertEqual(summary["reference_policy"], "external-ref_v2")
        self.assertEqual(summary["runs"][0]["reference_ratio_reason"], "missing_reference")

    def test_output_path_preflight_rejects_existing_files_directories_and_symlinks(self):
        calls = []
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            existing_dir = parent / "existing-directory"
            existing_dir.mkdir()
            existing_file = parent / "existing-file"
            existing_file.write_text("keep me", encoding="utf-8")
            link = parent / "linked-directory"
            link.symlink_to(existing_dir, target_is_directory=True)
            broken = parent / "broken-link"
            broken.symlink_to(parent / "missing-target")
            for path in (existing_dir, existing_file, link, broken):
                with self.subTest(path=path), self.assertRaisesRegex(ValueError, "new"):
                    evaluation.run_comparison({"observe": calls.append}, seeds=(0,), delays=(0,),
                                              ticks=1, output_dir=path)
                self.assertEqual(calls, [])
            self.assertEqual(existing_file.read_text(encoding="utf-8"), "keep me")
            self.assertEqual(list(existing_dir.iterdir()), [])
            self.assertTrue(link.is_symlink())
            self.assertTrue(broken.is_symlink())

    def test_missing_output_parent_is_rejected_before_any_policy_runs(self):
        calls = []
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing-parent" / "batch"
            with self.assertRaisesRegex(ValueError, "parent.*exist"):
                evaluation.run_comparison({"observe": calls.append}, seeds=(0,), delays=(0,),
                                          ticks=1, output_dir=path)
            self.assertEqual(calls, [])
            self.assertFalse(path.parent.exists())

    def test_exports_are_byte_identical_and_preserve_every_replay_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            outputs = [Path(directory) / name for name in ("first", "second")]
            batches = [evaluation.run_comparison(
                {"candidate": self.collect_west, "reference": do_nothing},
                seeds=(1, 0), delays=(3, 0), ticks=12, output_dir=output)
                for output in outputs]
            self.assertEqual(batches[0], batches[1])
            files = [{str(path.relative_to(output)): path.read_bytes()
                      for path in output.rglob("*") if path.is_file()}
                     for output in outputs]
            self.assertEqual(files[0], files[1])
            summary = batches[0]["summary"]
            self.assertEqual(set(files[0]), {"summary.json", "scores.csv"}
                             | {row["replay_file"] for row in summary["runs"]})
            self.assertEqual(json.loads(files[0]["summary.json"]), summary)
            for row, episode in zip(summary["runs"], batches[0]["episodes"]):
                replay = json.loads(files[0][row["replay_file"]])
                self.assertEqual(replay, episode["replay"])
                self.assertEqual(replay["version"], "lightlag-replay-v1")
                self.assertEqual(set(replay), {"version", "seed", "config", "world",
                                              "slip_coefficients", "commands", "states",
                                              "received_telemetry", "result"})
                self.assertEqual(replay["seed"], row["seed"])
                self.assertEqual(replay["config"]["delay_ticks"], row["delay"])
            csv_rows = list(csv.DictReader(files[0]["scores.csv"].decode("utf-8").splitlines()))
            self.assertEqual(len(csv_rows), 8)
            for csv_row, row in zip(csv_rows, summary["runs"]):
                self.assertEqual(csv_row, {key: "" if value is None else str(value)
                                           for key, value in row.items()})
            encoded = files[0]["summary.json"].decode("utf-8")
            self.assertNotIn(directory, encoded)
            self.assertNotIn("timestamp", encoded)
            self.assertNotIn("elapsed", encoded)

    def test_relative_output_paths_and_case_distinct_policy_names_are_supported(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "batch"
            batch = evaluation.run_comparison({"probe": do_nothing, "Probe": do_nothing},
                                              seeds=(0,), delays=(0,), ticks=1,
                                              output_dir=os.path.relpath(output))
            self.assertTrue((output / "summary.json").is_file())
            replay_names = [row["replay_file"] for row in batch["summary"]["runs"]]
            self.assertEqual(len({name.casefold() for name in replay_names}), 2)
            self.assertEqual(len(list((output / "replays").iterdir())), 2)

    def test_invalid_output_type_and_oversized_filenames_fail_before_policy(self):
        calls = []
        invalid = [{"output_dir": 1}, {"policies": {"x" * 300: calls.append}},
                   {"seeds": (10 ** 300,)}]
        for overrides in invalid:
            calls.clear()
            arguments = {"policies": {"probe": calls.append}, "seeds": (0,),
                         "delays": (0,), "ticks": 1}
            arguments.update(overrides)
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                evaluation.run_comparison(**arguments)
            self.assertEqual(calls, [])

    def test_policy_failure_propagates_and_creates_no_batch_artifacts(self):
        failure = RuntimeError("deliberate policy failure")
        calls = []

        def broken(tools):
            calls.append("broken")
            raise failure

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "batch"
            with self.assertRaises(RuntimeError) as caught:
                evaluation.run_comparison({"first": calls.append, "broken": broken},
                                          seeds=(0,), delays=(0,), ticks=1, output_dir=output)
            self.assertIs(caught.exception, failure)
            self.assertEqual(len(calls), 2)
            self.assertFalse(output.exists())

    def test_output_directory_created_after_preflight_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "batch"

            def create_output(tools):
                output.mkdir()
                (output / "other-owner.txt").write_text("preserve", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                evaluation.run_comparison({"race": create_output}, seeds=(0,), delays=(0,),
                                          ticks=1, output_dir=output)
            self.assertEqual((output / "other-owner.txt").read_text(encoding="utf-8"), "preserve")
            self.assertEqual([path.name for path in output.iterdir()], ["other-owner.txt"])

    def test_partial_export_error_is_visible_and_leaves_no_completed_summary(self):
        original_open = Path.open

        def failing_csv_open(path, *args, **kwargs):
            if path.name == "scores.csv":
                raise OSError("simulated disk failure")
            return original_open(path, *args, **kwargs)

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "batch"
            with patch.object(Path, "open", failing_csv_open):
                with self.assertRaisesRegex(OSError, "simulated disk failure"):
                    evaluation.run_comparison({"idle": do_nothing}, seeds=(0,), delays=(0,),
                                              ticks=1, output_dir=output)
            self.assertTrue(output.is_dir())
            self.assertEqual(len(list((output / "replays").iterdir())), 1)
            self.assertFalse((output / "summary.json").exists())

    def test_file_created_during_export_is_not_overwritten(self):
        original_open = Path.open
        raced_paths = []

        def create_before_open(path, *args, **kwargs):
            if path.parent.name == "replays" and not raced_paths:
                raced_paths.append(path)
                with original_open(path, "x", encoding="utf-8") as output:
                    output.write("another writer")
            return original_open(path, *args, **kwargs)

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "batch"
            with patch.object(Path, "open", create_before_open):
                with self.assertRaises(FileExistsError):
                    evaluation.run_comparison({"idle": do_nothing}, seeds=(0,), delays=(0,),
                                              ticks=1, output_dir=output)
            self.assertEqual(raced_paths[0].read_text(encoding="utf-8"), "another writer")
            self.assertFalse((output / "summary.json").exists())

    def test_output_path_with_null_byte_is_rejected_before_policies(self):
        calls = []
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "null byte"):
                evaluation.run_comparison({"observe": calls.append}, seeds=(0,), delays=(0,),
                                          ticks=1, output_dir=Path(directory) / "bad\x00path")
            self.assertEqual(calls, [])


class ComparisonCliTests(unittest.TestCase):
    def test_cli_matrix_exports_repeatable_summary_csv_and_replays(self):
        with tempfile.TemporaryDirectory() as directory:
            outputs = [Path(directory) / name for name in ("first", "second")]
            processes = [run_comparison_cli(
                "--seeds", "1", "0", "--delays", "3", "0", "--ticks", "12",
                "--policies", "reference", "team_reference", "--reference-policy",
                "team_reference", "--output-dir", str(output)) for output in outputs]
            for process in processes:
                self.assertEqual(process.returncode, 0, process.stderr)
                self.assertEqual(process.stderr, "")
            self.assertEqual(processes[0].stdout, processes[1].stdout)
            summary = json.loads(processes[0].stdout)
            self.assertEqual(summary["policies"], ["reference", "team_reference"])
            self.assertEqual(summary["reference_policy"], "team_reference")
            self.assertEqual(len(summary["runs"]), 8)
            self.assertEqual(len(summary["aggregates"]), 4)
            self.assertEqual(summary["ticks"], 12)
            self.assertEqual((outputs[0] / "summary.json").read_text(encoding="utf-8"),
                             processes[0].stdout)
            files = [{str(path.relative_to(output)): path.read_bytes()
                      for path in output.rglob("*") if path.is_file()} for output in outputs]
            self.assertEqual(files[0], files[1])
            self.assertEqual(len(files[0]), 10)
            for row in summary["runs"]:
                replay = json.loads(files[0][row["replay_file"]])
                self.assertEqual(replay["version"], "lightlag-replay-v1")
                self.assertEqual(replay["result"]["tick"], 12)
                self.assertEqual(replay["result"]["raw_score"], row["raw_score"])

    def test_cli_offers_all_twelve_policies_but_defaults_to_six_local_names(self):
        names = list(POLICIES) + ["team_reference", "team_move_and_wait", "team_stale_telemetry",
                                 "team_open_loop_nominal", "team_stop_early", "team_no_op"]
        selected = run_comparison_cli("--seeds", "0", "--delays", "0", "--ticks", "1",
                                      "--policies", *names)
        self.assertEqual(selected.returncode, 0, selected.stderr)
        summary = json.loads(selected.stdout)
        self.assertEqual(summary["policies"], names)
        self.assertEqual(len(summary["runs"]), 12)
        default = run_comparison_cli("--seeds", "0", "--delays", "0", "--ticks", "1")
        self.assertEqual(default.returncode, 0, default.stderr)
        self.assertEqual(json.loads(default.stdout)["policies"], list(POLICIES))

    def test_cli_accepts_unselected_reference_with_explicit_missing_ratios(self):
        process = run_comparison_cli("--seeds", "0", "--delays", "0", "--ticks", "1",
                                     "--policies", "do_nothing", "--reference-policy", "external")
        self.assertEqual(process.returncode, 0, process.stderr)
        summary = json.loads(process.stdout)
        self.assertEqual(summary["reference_policy"], "external")
        self.assertIsNone(summary["runs"][0]["reference_ratio"])
        self.assertEqual(summary["runs"][0]["reference_ratio_reason"], "missing_reference")

    def test_invalid_cli_selections_fail_without_summary_or_artifacts(self):
        invalid = [
            ("--seeds", "0", "0"), ("--seeds", "True"), ("--seeds",),
            ("--delays", "0", "0"), ("--delays", "-1"), ("--delays", "1.5"),
            ("--delays",), ("--ticks", "0"), ("--ticks", "True"),
            ("--policies", "do_nothing", "do_nothing"), ("--policies",),
            ("--policies", "unknown"), ("--reference-policy", "../unsafe"),
            ("--reference-policy", ""),
        ]
        with tempfile.TemporaryDirectory() as directory:
            for index, arguments in enumerate(invalid):
                output = Path(directory) / f"invalid-{index}"
                with self.subTest(arguments=arguments):
                    process = run_comparison_cli(*arguments, "--output-dir", str(output))
                    self.assertEqual(process.returncode, 2, process.stderr)
                    self.assertEqual(process.stdout, "")
                    self.assertIn("error", process.stderr.lower())
                    self.assertFalse(output.exists())

    def test_existing_cli_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "existing"
            output.write_text("preserve", encoding="utf-8")
            process = run_comparison_cli("--seeds", "0", "--delays", "0", "--ticks", "1",
                                         "--policies", "do_nothing", "--output-dir", str(output))
            self.assertEqual(process.returncode, 2)
            self.assertEqual(process.stdout, "")
            self.assertIn("must be new", process.stderr)
            self.assertEqual(output.read_text(encoding="utf-8"), "preserve")

    def test_policy_failure_exits_nonzero_with_clear_stderr_and_no_grade(self):
        def broken(tools):
            raise RuntimeError("deliberate controller crash")

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "failed"
            stdout, stderr = io.StringIO(), io.StringIO()
            with patch.dict(POLICIES, {"broken": broken}), redirect_stdout(stdout), redirect_stderr(stderr):
                status = evaluation.main(["--seeds", "0", "--delays", "0", "--ticks", "1",
                                          "--policies", "broken", "--output-dir", str(output)])
            self.assertEqual(status, 2)
            self.assertEqual(stdout.getvalue(), "")
            self.assertIn("RuntimeError: deliberate controller crash", stderr.getvalue())
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
