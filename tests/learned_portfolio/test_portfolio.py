import ast
from pathlib import Path
import unittest

import numpy as np

from lightlag_traverse.environment import TraverseEnvironment
from lightlag_traverse.pilot import fly
from lightlag_traverse.play import PublicTools
from lightlag_traverse_max.heldout import check_training_seeds
from lightlag_learned_portfolio.policy import PROFILE_NAMES, choose
from lightlag_learned_portfolio.worker import QUICK, digest, run_episode
from tools.learned_portfolio.run import TRAIN, VALIDATION, CHECK, matrix


class PortfolioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = run_episode({"seed":1,"name":"baseline","split":"smoke","quick":True,"keep_replay":True,
                               "spec":{"kind":"fixed","profile":"baseline"}})
        cls.other = run_episode({"seed":1,"name":"refresh","split":"smoke","quick":True,"keep_replay":True,
                                "spec":{"kind":"fixed","profile":"refresh"}})

    def test_baseline_preserves_original_pilot_exactly(self):
        env=TraverseEnvironment(1);fly(PublicTools(env),QUICK)
        self.assertEqual(digest(env.replay()),self.base["replay_sha256"])
        self.assertIsNone(self.base["error"]);self.assertFalse(self.base["invalid"])

    def test_switch_uses_identical_prefix_and_public_features(self):
        self.assertEqual(self.base["prefix_sha256"],self.other["prefix_sha256"])
        self.assertEqual(self.base["decision"]["features"],self.other["decision"]["features"])
        self.assertEqual(self.base["decision"]["tick"],140)
        self.assertEqual(len(self.base["decision"]["features"]),49)
        self.assertIsNone(self.other["error"])

    def test_policy_module_has_no_simulator_or_hidden_state_access(self):
        path=Path(__file__).resolve().parents[2]/"lightlag_learned_portfolio/policy.py"
        tree=ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.ImportFrom):self.assertNotIn('environment',node.module or '')
            if isinstance(node,ast.Attribute):self.assertNotIn(node.attr,('_env','_world','_seed','_truth','replay','evaluate'))

    def test_decision_threshold_falls_back_to_baseline(self):
        class Model:
            feature_names_=['value']
            def predict(self,x):return np.array([[.003]+[-1.]*(len(PROFILE_NAMES)-2)])
        self.assertEqual(choose(Model(),{'value':1},.005)[0],'baseline')
        self.assertEqual(choose(Model(),{'value':1},0)[0],PROFILE_NAMES[1])

    def test_seed_splits_and_reserved_exclusions(self):
        self.assertFalse(set(TRAIN)&set(VALIDATION)|set(TRAIN)&set(CHECK)|set(VALIDATION)&set(CHECK))
        check_training_seeds(TRAIN+VALIDATION+CHECK)
        for seed in (500,523,2026,2029,99991):
            with self.assertRaises(ValueError):check_training_seeds([seed])

    def test_incomplete_counterfactual_matrix_is_rejected(self):
        with self.assertRaises(ValueError):matrix([],TRAIN,'train')


if __name__=='__main__':unittest.main()
