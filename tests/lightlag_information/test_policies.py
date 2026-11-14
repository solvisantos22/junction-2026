"""Independent arithmetic and realized-branch checks for information policies."""

import copy
import json
from pathlib import Path
import tempfile
import unittest

from lightlag_information.policies import expected_values, run_policy


def public_rules(prior=0.5, probe_energy=1):
    return {
        "context": {"id": "fixture", "prior_firm": prior, "probe_energy": probe_energy},
        "signal_accuracy": 0.9,
        "initial_energy": 10,
        "horizon": 30,
        "delay": 1,
        "penalty_per_tick": 0.25,
        "normalization": 10,
        "max_batch_size": 5,
        "max_advance_ticks": 5,
        "routes": {
            "shortcut": {"target_value": 10, "duration": 2,
                         "energy": {"firm": 4, "soft": 12}},
            "detour": {"target_value": 6, "duration": 6,
                       "energy": {"firm": 8, "soft": 8}},
        },
    }


class PublicCallbacks:
    """Pass only callbacks, with no environment or hidden-state attribute."""

    __slots__ = ("rules", "map", "telemetry_log", "uplink", "advance")

    def __init__(self, env):
        for name in self.__slots__:
            setattr(self, name, getattr(env, name))


class ExpectedValueTests(unittest.TestCase):
    def test_uncertain_bayes_value_differs_from_prior_only_control(self):
        values = expected_values(public_rules())
        # Each signal has probability .5. A firm signal gives posterior .9.
        adaptive = 0.5 * (0.9 * 0.825) + 0.5 * 0.325
        self.assertAlmostEqual(values["always_probe"], adaptive)
        self.assertAlmostEqual(values["never_probe"], 0.45)
        self.assertAlmostEqual(values["blind_probe"], 0.4125)
        self.assertAlmostEqual(values["selective"], adaptive)

    def test_strong_priors_and_costly_probe_favor_skipping_information(self):
        for prior, cost, direct, probed in (
            (0.95, 1, 0.855, 0.78375),
            (0.05, 1, 0.4, 0.325),
            (0.5, 3, 0.45, 0.4125),
        ):
            with self.subTest(prior=prior, cost=cost):
                values = expected_values(public_rules(prior, cost))
                self.assertAlmostEqual(values["never_probe"], direct)
                self.assertAlmostEqual(values["always_probe"], probed)
                self.assertAlmostEqual(values["selective"], direct)

    def test_extreme_priors_do_not_divide_by_zero_on_impossible_signals(self):
        for prior in (0.0, 1.0):
            rules = public_rules(prior)
            rules["signal_accuracy"] = 1.0
            values = expected_values(rules)
            self.assertAlmostEqual(values["always_probe"], 0.325 if prior == 0 else 0.825)

    def test_expected_values_use_public_reward_resources_and_horizon(self):
        rules = public_rules()
        unchanged = copy.deepcopy(rules)
        expected_values(rules)
        self.assertEqual(rules, unchanged)
        rules["horizon"] = 6
        values = expected_values(rules)
        self.assertAlmostEqual(values["never_probe"], 0.45)
        self.assertEqual(values["always_probe"], 0)
        self.assertEqual(values["blind_probe"], 0)


class RealizedPolicyTests(unittest.TestCase):
    def test_every_weighted_realized_branch_matches_independent_arithmetic(self):
        from lightlag_information.environment import Environment
        from lightlag_information.model import CONTEXTS

        for context_id, context in CONTEXTS.items():
            analytical = expected_values(Environment(context=context_id).rules())
            for policy in analytical:
                weighted = 0.0
                mass = 0.0
                for terrain in ("firm", "soft"):
                    for signal in ("firm", "soft"):
                        prior = context.prior_firm if terrain == "firm" else 1 - context.prior_firm
                        weight = prior * (0.9 if signal == terrain else 0.1)
                        env = Environment(context=context_id, terrain=terrain, signal=signal)
                        run_policy(PublicCallbacks(env), policy)
                        weighted += weight * env.evaluate()["reward"]
                        mass += weight
                with self.subTest(context=context_id, policy=policy):
                    self.assertAlmostEqual(mass, 1)
                    self.assertAlmostEqual(weighted, analytical[policy])

    def test_blind_control_matches_probe_timing_but_ignores_signal(self):
        from lightlag_information.environment import Environment

        outcomes = {}
        for policy in ("always_probe", "blind_probe"):
            env = Environment(terrain="firm", signal="soft")
            result = run_policy(PublicCallbacks(env), policy)
            outcomes[policy] = (result, env.evaluate())
        adaptive, blind = outcomes["always_probe"], outcomes["blind_probe"]
        self.assertEqual(adaptive[0]["commit_sent_tick"], 3)
        self.assertEqual(blind[0]["commit_sent_tick"], 3)
        self.assertEqual(adaptive[1]["route"], "detour")
        self.assertEqual(blind[1]["route"], "shortcut")
        self.assertTrue(adaptive[1]["probe_used"])
        self.assertTrue(blind[1]["probe_used"])

    def test_selective_uses_both_behaviors_and_skips_probe_on_tie(self):
        from lightlag_information.environment import Environment

        for context_id, should_probe in (("uncertain", True), ("likely_firm", False),
                                         ("likely_soft", False), ("costly_probe", False)):
            env = Environment(context=context_id)
            run_policy(PublicCallbacks(env), "selective")
            self.assertEqual(env.evaluate()["probe_used"], should_probe)
        # With no starting energy all strategies score zero; ties skip probing.
        env = Environment()
        tools = PublicCallbacks(env)
        original = tools.rules
        tools.rules = lambda: {**original(), "initial_energy": 0}
        result = run_policy(tools, "selective")
        self.assertFalse(result["probe_used"])

    def test_repeated_log_entries_do_not_multiply_signal_likelihood(self):
        from lightlag_information.environment import Environment

        # Duplicate soft signals would change this strong-prior decision if
        # the same fixed observation were treated as fresh evidence each time.
        env = Environment(context="likely_firm", terrain="firm", signal="soft")
        tools = PublicCallbacks(env)
        original = tools.telemetry_log

        def duplicated_log():
            log = original()
            log["entries"] *= 20
            return log

        tools.telemetry_log = duplicated_log
        run_policy(tools, "always_probe")
        self.assertEqual(env.evaluate()["route"], "shortcut")

    def test_unknown_policy_rejected_before_any_public_calls(self):
        with self.assertRaises(ValueError):
            run_policy(object(), "oracle")


class StudyTests(unittest.TestCase):
    def test_study_retains_all_rows_replays_and_declared_negative_results(self):
        from lightlag_information.study import run_study

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "study"
            summary = run_study(output)
            protocol = json.loads((output / "protocol.json").read_text())
            exact = [json.loads(line) for line in (output / "exact_rows.jsonl").read_text().splitlines()]
            seeded = [json.loads(line) for line in (output / "seeded_rows.jsonl").read_text().splitlines()]
            replays = [json.loads(line) for line in (output / "replays.jsonl").read_text().splitlines()]
            self.assertEqual(len(exact), 64)
            self.assertEqual(len(seeded), 640)
            self.assertEqual(len(replays), 704)
            self.assertEqual(protocol["seeded_smoke"]["seeds"], list(range(40)))
            self.assertEqual(set(row["seed"] for row in seeded), set(range(40)))
            self.assertTrue(protocol["source_hashes"])
            self.assertEqual(summary, json.loads((output / "summary.json").read_text()))
            self.assertTrue(summary["gate"]["passed"])
            self.assertAlmostEqual(summary["exact"]["aggregate"]["selective"], 0.5596875)
            self.assertAlmostEqual(summary["exact"]["aggregate"]["never_probe"], 0.53875)
            self.assertAlmostEqual(summary["exact"]["aggregate"]["always_probe"], 0.51375)
            self.assertLess(summary["exact"]["contexts"]["likely_firm"]["always_probe"],
                            summary["exact"]["contexts"]["likely_firm"]["never_probe"])
            by_id = {row["episode_id"]: row for row in exact + seeded}
            self.assertEqual(len(by_id), 704)
            for replay in replays:
                self.assertEqual(replay["replay"]["evaluation"]["reward"],
                                 by_id[replay["episode_id"]]["reward"])

    def test_existing_output_is_refused_without_modification(self):
        from lightlag_information.study import run_study

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            marker = output / "keep.txt"
            marker.write_text("original")
            with self.assertRaises(FileExistsError):
                run_study(output)
            self.assertEqual(list(output.iterdir()), [marker])
            self.assertEqual(marker.read_text(), "original")


if __name__ == "__main__":
    unittest.main()
