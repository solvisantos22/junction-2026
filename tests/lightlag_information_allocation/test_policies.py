"""Independent joint-state enumeration and public-callback policy checks."""

import copy
from fractions import Fraction
import itertools
import unittest

from lightlag_information_allocation.environment import Environment
from lightlag_information_allocation.model import CONTEXTS
from lightlag_information_allocation.policies import (
    POLICIES, acquisition_values, choose_acquisition, expected_values, run_policy,
)
from lightlag_information_allocation.study import PublicTools


def independent_acquisition_values(rules):
    """Enumerate all 21 direct/contingent strategies, without Bayesian updates."""
    f = lambda value: Fraction(str(value))
    routes = tuple(rules["routes"])
    states = []
    for ta, tb, sa, sb in itertools.product(("firm", "soft"), repeat=4):
        terrains, signals = {"a": ta, "b": tb}, {"a": sa, "b": sb}
        weight = Fraction(1)
        for target in ("a", "b"):
            prior = f(rules["priors_firm"][target])
            weight *= prior if terrains[target] == "firm" else 1 - prior
            accuracy = f(rules["signal_accuracy"])
            weight *= accuracy if signals[target] == terrains[target] else 1 - accuracy
        states.append((terrains, signals, weight))
    assert sum(state[2] for state in states) == 1

    def reward(route, terrain, inspected):
        trip = rules["routes"][route]
        energy = rules["initial_energy"] - (rules["context"]["probe_energy"] if inspected else 0)
        completion = (3 * rules["delay"] + 2 if inspected else rules["delay"] + 1) + trip["duration"]
        ground = terrain[route] if route in terrain else "firm"
        if trip["energy"][ground] > energy or completion > rules["horizon"]:
            return Fraction(0)
        return max(Fraction(0), f(trip["target_value"]) - f(rules["penalty_per_tick"]) * completion) / f(rules["normalization"])

    values = {"none": max(sum(weight * reward(route, terrain, False)
                               for terrain, _, weight in states) for route in routes)}
    for inspected in ("a", "b"):
        strategies = []
        for firm_route, soft_route in itertools.product(routes, repeat=2):
            strategies.append(sum(weight * reward(firm_route if signal[inspected] == "firm" else soft_route,
                                                   terrain, True)
                                  for terrain, signal, weight in states))
        values[inspected] = max(strategies)
    return values


class ExpectedValueTests(unittest.TestCase):
    def test_public_formula_matches_exhaustive_contingent_strategy_search(self):
        self.assertEqual(len(CONTEXTS), 6)
        for context in CONTEXTS:
            rules = Environment(context=context).rules()
            before = copy.deepcopy(rules)
            expected = independent_acquisition_values(rules)
            observed = acquisition_values(rules)
            with self.subTest(context=context):
                for action in expected:
                    self.assertAlmostEqual(observed[action], float(expected[action]))
                self.assertEqual(rules, before)

    def test_specific_values_and_information_targets(self):
        cases = {
            "case_1": (.45, .53375, .45375, "a"),
            "case_2": (.45, .45375, .53375, "b"),
            "case_3": (.585, .63415, .60555, "a"),
            "case_4": (.585, .60555, .63415, "b"),
            "case_5": (.855, .78375, .78375, None),
            "case_6": (.855, .78375, .78375, None),
        }
        for context, (direct, a, b, target) in cases.items():
            rules = Environment(context=context).rules()
            values = acquisition_values(rules)
            with self.subTest(context=context):
                self.assertAlmostEqual(values["none"], direct)
                self.assertAlmostEqual(values["a"], a)
                self.assertAlmostEqual(values["b"], b)
                self.assertEqual(choose_acquisition(rules), target)

    def test_resource_and_horizon_limits_and_extreme_priors(self):
        original = Environment(context="case_1").rules()
        variants = []
        costly = copy.deepcopy(original)
        costly["context"]["probe_energy"] = 3
        variants.append(costly)
        short = copy.deepcopy(original)
        short["horizon"] = 6
        variants.append(short)
        for prior in (0, 1):
            certain = copy.deepcopy(original)
            certain["priors_firm"] = {"a": prior, "b": 1 - prior}
            certain["signal_accuracy"] = 1
            variants.append(certain)
        for rules in variants:
            independent = independent_acquisition_values(rules)
            for acquisition, value in acquisition_values(rules).items():
                self.assertAlmostEqual(value, float(independent[acquisition]))

    def test_ties_prefer_no_inspection_then_a(self):
        rules = Environment(context="case_1").rules()
        rules["initial_energy"] = 0
        self.assertEqual(choose_acquisition(rules), None)
        rules = Environment(context="case_1").rules()
        rules["priors_firm"] = {"a": .5, "b": .5}
        self.assertEqual(choose_acquisition(rules), "a")

    def test_matched_gate_controls_separate_acquisition_from_target_choice(self):
        for context in ("case_5", "case_6"):
            values = expected_values(Environment(context=context).rules())
            self.assertEqual(values["entropy_matched_gate"], values["selective"])
            self.assertEqual(values["least_useful_matched_gate"], values["selective"])
            self.assertLess(values["most_uncertain"], values["selective"])
        values = expected_values(Environment(context="case_3").rules())
        self.assertAlmostEqual(values["selective"] - values["entropy_matched_gate"], .0286)
        self.assertAlmostEqual(values["selective"] - values["least_useful_matched_gate"], .0286)


class RealizedPolicyTests(unittest.TestCase):
    def test_all_weighted_branches_match_the_analytical_policy_values(self):
        for context in CONTEXTS:
            rules = Environment(context=context).rules()
            analytical = expected_values(rules)
            for policy in POLICIES:
                weighted, mass = 0.0, 0.0
                for ta, tb, sa, sb in itertools.product(("firm", "soft"), repeat=4):
                    terrains, signals = {"a": ta, "b": tb}, {"a": sa, "b": sb}
                    weight = 1.0
                    for target in ("a", "b"):
                        prior = rules["priors_firm"][target]
                        weight *= prior if terrains[target] == "firm" else 1 - prior
                        weight *= .9 if signals[target] == terrains[target] else .1
                    env = Environment(context=context, terrains=terrains, signals=signals)
                    run_policy(PublicTools(env), policy)
                    weighted += weight * env.evaluate()["reward"]
                    mass += weight
                with self.subTest(context=context, policy=policy):
                    self.assertAlmostEqual(mass, 1)
                    self.assertAlmostEqual(weighted, analytical[policy])

    def test_blind_control_matches_selected_probe_and_timing_but_ignores_signal(self):
        results = {}
        for policy in ("selective", "blind_selected_probe"):
            env = Environment(context="case_1", terrains={"a": "firm", "b": "firm"},
                              signals={"a": "soft", "b": "firm"})
            decision = run_policy(PublicTools(env), policy)
            results[policy] = decision
        adaptive, blind = results["selective"], results["blind_selected_probe"]
        self.assertEqual(adaptive["probe_route"], blind["probe_route"])
        self.assertEqual(adaptive["commit_sent_tick"], 3)
        self.assertEqual(blind["commit_sent_tick"], 3)
        self.assertEqual(adaptive["route"], "detour")
        self.assertEqual(blind["route"], "a")
        self.assertAlmostEqual(adaptive["posterior_firm"]["a"], .1)
        self.assertAlmostEqual(blind["posterior_firm"]["a"], .5)
        self.assertEqual(adaptive["posterior_firm"]["b"], .2)

    def test_matched_controls_preserve_probe_skip_and_timing(self):
        for context in CONTEXTS:
            decisions = {}
            for policy in ("selective", "entropy_matched_gate", "least_useful_matched_gate"):
                env = Environment(context=context)
                decisions[policy] = run_policy(PublicTools(env), policy)
            selective = decisions["selective"]
            for decision in decisions.values():
                self.assertEqual(decision["probe_used"], selective["probe_used"])
                self.assertEqual(decision["commit_sent_tick"], selective["commit_sent_tick"])
            if context == "case_3":
                self.assertEqual(selective["probe_route"], "a")
                self.assertEqual(decisions["entropy_matched_gate"]["probe_route"], "b")

    def test_duplicate_entries_do_not_multiply_likelihood(self):
        env = Environment(context="case_5", terrains={"a": "firm", "b": "firm"},
                          signals={"a": "soft", "b": "firm"})
        tools = PublicTools(env)
        original = tools.telemetry_log

        def repeated():
            log = original()
            log["entries"] *= 20
            return log

        tools.telemetry_log = repeated
        decision = run_policy(tools, "probe_a")
        self.assertEqual(decision["route"], "a")
        self.assertAlmostEqual(decision["posterior_firm"]["a"], .095 / .14)
        self.assertEqual(decision["posterior_firm"]["b"], .6)

    def test_unknown_policy_and_nonfresh_episode_are_rejected(self):
        with self.assertRaises(ValueError):
            run_policy(object(), "hidden_oracle")
        env = Environment(context="case_1")
        env.advance()
        with self.assertRaises(ValueError):
            run_policy(PublicTools(env), "selective")


if __name__ == "__main__":
    unittest.main()
