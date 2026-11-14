"""Exhaustive challenger checks, independent branch scoring and retained evidence."""

from fractions import Fraction
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from lightlag_expedition.challenger_check import (
    CASES, EXPECTED, Strategy, arithmetic_reward, case_summary,
    exact_strategy_values, robustness_check, run_check, strategies, worlds,
)
from lightlag_information_allocation.environment import Environment
from lightlag_information_allocation.model import Context, CONTEXTS


class ChallengerTests(unittest.TestCase):
    def test_mirrored_challengers_beat_leader_inspection_and_skipping(self):
        self.assertEqual(len(strategies()), 21)
        original = tuple(CONTEXTS)
        for context, leader, challenger in ((CASES[0], "a", "b"), (CASES[1], "b", "a")):
            rules = Environment(context=context).rules()
            values = exact_strategy_values(rules)
            summary = case_summary(context, values)
            self.assertEqual(summary["prior_best_route"], leader)
            self.assertEqual(summary["best_inspection"], challenger)
            self.assertEqual(summary["exact_expected_rewards"], {k: str(v) for k, v in EXPECTED.items()})
            self.assertAlmostEqual(summary["gain_over_skip"], .084375)
            self.assertAlmostEqual(summary["gain_over_leader_matched_gate"], .102)
            self.assertEqual(summary["optimal_strategies"][0]["firm_route"], challenger)
            self.assertEqual(summary["optimal_strategies"][0]["soft_route"], leader)
        self.assertEqual(tuple(CONTEXTS), original)
        self.assertEqual(len(original), 6)

    def test_all_joint_worlds_have_exact_probability_and_keep_bad_signals(self):
        for context in CASES:
            rules = Environment(context=context).rules()
            outcomes = worlds(rules)
            self.assertEqual(len(outcomes), 16)
            self.assertEqual(sum(weight for _, _, weight in outcomes), 1)
            self.assertTrue(all(weight > 0 for _, _, weight in outcomes))
            for route in ("a", "b"):
                self.assertEqual(sum(weight for terrain, signal, weight in outcomes
                                     if terrain[route] != signal[route]), Fraction(1, 10))
            plan = Strategy("b" if context.id == "challenger_b" else "a", "a", "b")
            rewards = [arithmetic_reward(rules, plan, terrain, signal) for terrain, signal, _ in outcomes]
            self.assertIn(Fraction(0), rewards)
            self.assertGreater(max(rewards), 0)

    def test_declared_nearby_inputs_retain_the_challenger_margin(self):
        result = robustness_check()
        self.assertEqual(result["cases"], 54)
        self.assertTrue(result["all_passed"])
        self.assertEqual(result["minimum_challenger_gain"], .045375)
        self.assertEqual(result["minimum_prior_leader_margin"], .001875)

    def test_all_saved_branches_and_replays_reconstruct_and_archive_hashes_match(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "new"
            summary = run_check(output)
            self.assertTrue(summary["passed"])
            self.assertEqual(summary["model_trials"], 0)
            rows = [json.loads(line) for line in (output / "weighted_rows.jsonl").read_text().splitlines()]
            self.assertEqual(len(rows), 672)
            self.assertEqual(len({row["episode_id"] for row in rows}), 672)
            self.assertEqual(sum(Fraction(row["exact_weight"]) for row in rows), 42)
            raw = gzip.decompress((output / "replays.jsonl.gz").read_bytes())
            episodes = [json.loads(line) for line in raw.decode().splitlines()]
            self.assertEqual(len(episodes), len(rows))
            for row, episode in zip(rows, episodes):
                self.assertEqual(row["episode_id"], episode["episode_id"])
                replay = episode["replay"]
                env = Environment(replay["seed"], Context(**replay["context"]),
                                  terrains=replay["terrains"], signals=replay["signals"])
                for call in replay["transcript"]:
                    self.assertEqual(getattr(env, call["method"])(**call["arguments"]), call["result"])
                self.assertEqual(env.replay(), replay)
                self.assertEqual(Fraction(str(replay["evaluation"]["reward"])), Fraction(row["exact_reward"]))
            manifest = json.loads((output / "artifact-manifest.json").read_text())
            self.assertEqual(hashlib.sha256(raw).hexdigest(), manifest["replay_uncompressed_sha256"])
            self.assertEqual(len(raw), manifest["replay_uncompressed_bytes"])
            for name, record in manifest["files"].items():
                self.assertEqual(hashlib.sha256((output / name).read_bytes()).hexdigest(), record["sha256"])

    def test_existing_output_is_never_changed(self):
        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary) / "keep"
            marker.write_text("original")
            with self.assertRaises(FileExistsError):
                run_check(temporary)
            self.assertEqual(marker.read_text(), "original")
            self.assertEqual(list(Path(temporary).iterdir()), [marker])


if __name__ == "__main__":
    unittest.main()
