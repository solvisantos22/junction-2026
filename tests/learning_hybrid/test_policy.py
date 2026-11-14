import copy
import json
from pathlib import Path
import unittest

import numpy as np
import torch

from lightlag_hybrid.policy import build_specs, legal_ranks, make_chooser, validate_spec
from lightlag_learning.environment import greedy_choice, run_episode
from lightlag_learning.learners import chooser_from_state


ROOT = Path(__file__).resolve().parents[2]


def observation():
    rows = [[0.0] * 20 for _ in range(5)]
    rows[0][0] = 1.0
    for i, credit in enumerate((0.0, 1.0, 0.5, 1.0, 100.0)):
        rows[i][14], rows[i][19] = 0.1, credit
    return {"ids": ["base", "a", "b", "c", "masked"], "candidates": rows,
            "global": [0.0] * 14, "mask": [True, True, True, True, False],
            "tick": 12, "planned_tick": 15}


class FixedModel:
    def __init__(self, scores):
        self.scores = scores

    def __call__(self, batch):
        return torch.tensor([self.scores], dtype=torch.float32), torch.tensor([0.0])


class HybridPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)
        cls.parent = json.loads((ROOT / "docs/learning-final-results/policy-freeze.json").read_text())
        cls.specs = build_specs(cls.parent)
        cls.policies = {arm["id"]: arm["policy"] for arm in cls.parent["arms"]
                        if arm["kind"] == "policy"}

    def spec(self, identifier):
        return next(copy.deepcopy(s) for s in self.specs if s["id"] == identifier)

    def test_grid_covers_all_seeds_and_partial_latest_without_best_seed_selection(self):
        self.assertEqual(len(self.specs), 65)
        self.assertEqual(len({s["id"] for s in self.specs}), 65)
        groups = {}
        for spec in self.specs:
            validate_spec(spec, self.policies)
            groups.setdefault(spec["group"], []).append(spec)
        self.assertEqual(len(groups), 41)
        for group in groups.values():
            if group[0]["kind"] == "single":
                self.assertEqual({s["training_seed"] for s in group}, {17, 29, 43})
        replay43 = self.spec("single-replay-43-rho000")
        self.assertEqual(replay43["members"], ["replay-43-02048"])
        broken = copy.deepcopy(self.parent)
        broken["arms"] = [a for a in broken["arms"] if a["id"] != "replay-43-02048"]
        with self.assertRaises(ValueError):
            build_specs(broken)
        broken = copy.deepcopy(self.parent)
        broken["arms"].append(broken["arms"][0])
        with self.assertRaises(ValueError):
            build_specs(broken)

    def test_rank_ties_mask_and_affine_invariance(self):
        mask = [True, True, True, False]
        np.testing.assert_allclose(legal_ranks([2, 2, 5, 999], mask), [.25, .25, 1, np.nan])
        np.testing.assert_allclose(legal_ranks([2, 2, 5, 999], mask),
                                   legal_ranks([24, 24, 45, -999], mask))
        np.testing.assert_allclose(legal_ranks([7, 7, 7], [True] * 3), [.5] * 3)
        np.testing.assert_allclose(legal_ranks([1, 2], [True, False]), [1, np.nan])
        with self.assertRaises(ValueError):
            legal_ranks([1], [False])

    def test_shortlist_keeps_home_and_context_with_exact_density_boundary(self):
        obs = observation()
        before = copy.deepcopy(obs)
        chooser = make_chooser(self.spec("single-ppo-17-rho075"), self.policies)
        member = chooser.spec["members"][0]
        chooser.models[member] = FixedModel([0, 2, 9, 3, 100])
        self.assertEqual(chooser(obs), 3)
        trace = chooser.diagnostics[-1]
        self.assertEqual(trace["eligible"], [True, True, False, True, False])
        self.assertEqual(trace["member_ranks"][member], [0, 1 / 3, 1, 2 / 3, None])
        self.assertEqual(trace["chosen_density_ratio"], 1)
        self.assertEqual(obs, before)
        chooser.models[member] = FixedModel([99, 2, 9, 3, 100])
        self.assertEqual(chooser(obs), 0)  # shortlist never removes public home
        json.dumps(chooser.diagnostics, allow_nan=False)

    def test_ensemble_ranks_not_raw_units_and_blend_uses_fixed_weight(self):
        obs = observation()
        chooser = make_chooser(self.spec("ensemble-ppo-rho000"), self.policies)
        values = ([0, 4, 3, 2, 999], [0, 4, 3, 2, 999], [0, 1, 10000, 0.5, 99999])
        for member, scores in zip(chooser.models, values):
            chooser.models[member] = FixedModel(scores)
        self.assertEqual(chooser(obs), 1)  # huge Q/logit scale cannot overwhelm votes
        blend = make_chooser(self.spec("blend-ppo-greedy075"), self.policies)
        for member in blend.models:
            blend.models[member] = FixedModel([0, 2, 9, 1, 100])
        self.assertEqual(blend(obs), 1)
        trace = blend.diagnostics[-1]
        for i in range(4):
            self.assertAlmostEqual(trace["combined_score"][i],
                                   .25 * trace["learned_rank"][i] + .75 * trace["greedy_rank"][i])

    def test_greedy_zero_ties_and_forced_home(self):
        chooser = make_chooser(self.spec("greedy"), {})
        obs = observation()
        for row in obs["candidates"]:
            row[19] = 0
        self.assertEqual(chooser(obs), greedy_choice(obs))
        self.assertEqual(chooser(obs), 1)
        obs["mask"] = [True, False, False, False, False]
        self.assertEqual(chooser(obs), 0)
        self.assertEqual(chooser.diagnostics[-1]["eligible"], obs["mask"])
        json.dumps(chooser.diagnostics, allow_nan=False)

    def test_all_six_unrestricted_policies_match_frozen_argmax(self):
        for spec in self.specs:
            if spec["kind"] != "single" or spec["rho"] != 0:
                continue
            before = copy.deepcopy(self.policies[spec["members"][0]])
            chooser = make_chooser(spec, self.policies)
            original = chooser_from_state(before, np.random.default_rng(17), explore=False)
            obs = observation()
            self.assertEqual(chooser(obs), original(obs))
            self.assertEqual(self.policies[spec["members"][0]], before)

    def test_used_map_null_rule_exact_full_horizon_equivalence(self):
        spec = self.spec("single-ppo-17-rho000")
        chooser = make_chooser(spec, self.policies)
        original = chooser_from_state(self.policies[spec["members"][0]],
                                      np.random.default_rng(17), explore=False)
        hybrid = run_episode(1, chooser, keep_replay=True)
        control = run_episode(1, original, keep_replay=True)
        self.assertEqual(hybrid["replay"], control["replay"])
        self.assertEqual(hybrid["transitions"], control["transitions"])
        self.assertEqual(hybrid["reward"], control["reward"])
        self.assertEqual(hybrid["result"]["tick"], 420)
        self.assertEqual(len(chooser.diagnostics), hybrid["decision_count"])

    def test_reject_bad_spec_missing_policy_bad_observation_and_beam(self):
        spec = self.spec("single-ppo-17-rho000")
        with self.assertRaises(ValueError):
            make_chooser(spec, {})
        spec["greedy_weight"] = .25
        with self.assertRaises(ValueError):
            make_chooser(spec, self.policies)
        with self.assertRaises(ValueError):
            make_chooser(self.spec("beam"), {})
        chooser = make_chooser(self.spec("greedy"), {})
        obs = observation()
        obs["mask"] = [1] * 5
        with self.assertRaises(ValueError):
            chooser(obs)
        obs = observation()
        obs["candidates"][1][19] = float("nan")
        with self.assertRaises(ValueError):
            chooser(obs)


if __name__ == "__main__":
    unittest.main()
