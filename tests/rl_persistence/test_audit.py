import copy
import unittest

import numpy as np

from lightlag_rl.adapter import run_episode
from lightlag_rl.model import Policy
from lightlag_rl_persistence import GoalChooser
from tools.rl_persistence.audit import audit_case


class AuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.states = {"initial": Policy(seed=17).state_dict()}
        cls.bundles = {}
        for mode in ("frequent", "persistent"):
            policy = Policy.from_state(cls.states["initial"])
            rng = np.random.default_rng(1000003)
            chooser = GoalChooser(lambda ids, x: policy.choose(x, rng), mode == "persistent")
            episode = run_episode(1, chooser, keep_replay=True)
            cls.bundles[mode] = {"schema": "lightlag-rl-persistence-episode-v1",
                                 "seed": 1, "policy": "initial", "mode": mode,
                                 "draw": 0, "policy_seed": 1000003,
                                 "episode": episode, "decisions": chooser.decisions}

    def test_both_modes_reconstruct_physics_sampling_and_commitment(self):
        for mode, bundle in self.bundles.items():
            with self.subTest(mode=mode):
                audit = audit_case(bundle, self.states)
                self.assertEqual(audit["decisions"], bundle["episode"]["decision_count"])
                if mode == "frequent":
                    self.assertEqual(audit["overridden"], 0)
                else:
                    self.assertGreater(audit["retained"], 0)

    def test_corrupt_proposal_and_commitment_are_rejected(self):
        for key, value in (("proposed_action", -1), ("held_goal", "invented"), ("reason", "retain")):
            bundle = copy.deepcopy(self.bundles["frequent"])
            bundle["decisions"][0][key] = value
            with self.subTest(key=key), self.assertRaises(AssertionError):
                audit_case(bundle, self.states)

    def test_corrupt_grade_and_physics_are_rejected(self):
        bundle = copy.deepcopy(self.bundles["persistent"])
        bundle["episode"]["reward"] += .1
        with self.assertRaises(AssertionError):
            audit_case(bundle, self.states)

    def test_corrupt_retained_action_is_rejected(self):
        bundle = copy.deepcopy(self.bundles["persistent"])
        retained = next(d for d in bundle["decisions"] if d["reason"] == "retain")
        retained["action"] = (retained["action"] + 1) % len(retained["ids"])
        with self.assertRaises(AssertionError):
            audit_case(bundle, self.states)
        bundle = copy.deepcopy(self.bundles["persistent"])
        drive = next(c["command"] for c in bundle["episode"]["replay"]["commands"]
                     if c["command"]["action"] == "drive")
        drive["heading_deg"] = (drive["heading_deg"] + 180) % 360
        with self.assertRaises(AssertionError):
            audit_case(bundle, self.states)


if __name__ == "__main__":
    unittest.main()
