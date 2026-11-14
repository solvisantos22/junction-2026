import copy
from pathlib import Path
import platform
import tempfile
import unittest

import numpy as np
import torch

from lightlag_learning.environment import CANDIDATE_FEATURES, GLOBAL_FEATURES
from lightlag_learning.learners import Learner, chooser_from_state
from lightlag_learning.models import json_state
from lightlag_learning.train import atomic_json, digest, read_json, source_pins, summarize, training_map
from tools.learning_campaign.audit_training import Comparison, audit


def synthetic_run(directory):
    """32 synthetic terminal transitions; no simulator or external service."""
    torch.set_num_threads(1)
    learner = Learner("ppo", len(CANDIDATE_FEATURES), len(GLOBAL_FEATURES), 17, 2048)
    identity = {"algorithm": "ppo", "seed": 17, "smoke": True, "source_sha256": source_pins(),
                "numpy": np.__version__, "torch": torch.__version__, "python": platform.python_version(),
                "batch_episodes": 32, "schedule_episodes": 2048}
    initial = {"schema": "learning-run-checkpoint-v1", "identity": identity,
               "learner": learner.state_dict(), "history": [], "validations": {}}
    atomic_json(directory / "checkpoint-00000.json.gz", initial)
    policy, episodes = learner.inference_state(), []
    for index in range(32):
        obs = {"ids": ["base", "target"], "candidates": [[0.] * len(CANDIDATE_FEATURES)] * 2,
               "global": [0.] * len(GLOBAL_FEATURES), "mask": [True, True], "tick": 0, "planned_tick": 4}
        next_obs = {**copy.deepcopy(obs), "tick": 420, "planned_tick": 420}
        action_seed = 17 * 1_000_000_000 + index
        action = chooser_from_state(policy, np.random.default_rng(action_seed), explore=True)(obs)
        episodes.append({"seed": training_map(index, True), "action_seed": action_seed,
                         "reward": .1, "decision_count": 1, "invalid_calls": [],
                         "result": {"tick": 420, "raw_score": .1, "max_available_value": 1.,
                                    "alive": True, "at_base": True},
                         "transitions": [{"obs": obs, "action": action, "next_obs": next_obs,
                                          "done": True, "reward": .1, "elapsed_ticks": 420}]})
    metrics = learner.update(episodes)
    artifact = "batches/batch-00000.json.gz"
    atomic_json(directory / artifact, {"schema": "learning-batch-v1", "first_episode": 0,
                                      "policy": policy, "episodes": episodes, "metrics": metrics})
    history = [{"first_episode": 0, "last_episode": 32, "artifact": artifact,
                "sha256": digest(directory / artifact), **summarize(episodes), **metrics}]
    checkpoint = {"schema": "learning-run-checkpoint-v1", "identity": identity,
                  "learner": learner.state_dict(), "history": history, "validations": {}}
    atomic_json(directory / "checkpoint-latest.json.gz", checkpoint)
    atomic_json(directory / "checkpoint-00032.json.gz", checkpoint)
    atomic_json(directory / "report.json", {"schema": "learning-training-report-v1", **identity,
                                            "episodes_target": 32, "episodes_completed": 32,
                                            "status": "complete", "history": history, "validations": {}})


class TrainingAuditTests(unittest.TestCase):
    def test_encoded_mapping_order_is_irrelevant_but_array_data_is_not(self):
        left = {"observation": {"ids": ["base"], "features": np.array([.25, .5], dtype=np.float32)}}
        right = {"observation": {"features": np.array([.25, .5], dtype=np.float32), "ids": ["base"]}}
        Comparison().same(json_state(left), json_state(right))
        right["observation"]["features"][0] += .125
        with self.assertRaisesRegex(ValueError, "numeric difference"):
            Comparison().same(json_state(left), json_state(right))

    def test_tolerance_is_explicit_and_does_not_relax_counters(self):
        comparison = Comparison(.001)
        comparison.same(.5, .5005)
        self.assertAlmostEqual(comparison.maximum_difference, .0005)
        with self.assertRaises(ValueError):
            Comparison().same(.5, .5005)
        with self.assertRaises(ValueError):
            Comparison(10).same(1, 2)
        with self.assertRaises(ValueError):
            Comparison(10).same(json_state(np.array([1])), json_state(np.array([2])))

    def test_reconstructs_synthetic_batch_and_rejects_rehashed_forged_action(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            synthetic_run(directory)
            result = audit(directory)
            self.assertEqual(result["episodes_verified"], 32)
            self.assertEqual(result["training_actions_replayed"], 32)
            self.assertEqual(result["maximum_numeric_difference"], 0.)
            self.assertEqual(result["new_environment_cases"], 0)
            report = read_json(directory / "report.json")
            checkpoint = read_json(directory / "checkpoint-latest.json.gz")
            artifact = directory / report["history"][0]["artifact"]
            batch = read_json(artifact)
            batch["episodes"][0]["transitions"][0]["action"] ^= 1
            atomic_json(artifact, batch)
            report["history"][0]["sha256"] = digest(artifact)
            checkpoint["history"] = report["history"]
            atomic_json(directory / "report.json", report)
            atomic_json(directory / "checkpoint-latest.json.gz", checkpoint)
            with self.assertRaisesRegex(ValueError, "recorded action"):
                audit(directory)

    def test_batch_hash_tamper_fails_before_reconstruction(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            synthetic_run(directory)
            path = directory / "batches/batch-00000.json.gz"
            path.write_bytes(path.read_bytes() + b"changed")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                audit(directory)


if __name__ == "__main__":
    unittest.main()
