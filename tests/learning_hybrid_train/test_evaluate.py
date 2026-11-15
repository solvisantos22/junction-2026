from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import torch

from lightlag_hybrid_train.learner import Learner
from lightlag_hybrid_train.train import EXPERIMENT, MILESTONES, source_manifest, state_hash
from tools.learning_hybrid_train import evaluate as e


class FinalEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)
        cls.pins = source_manifest()
        cls.initial = {f"{v}-{s}-00000": Learner(v, 20, 14, s).inference_state()
                       for v in e.VARIANTS for s in e.SEEDS}

    def job(self, kind="policy"):
        if kind == "policy":
            policy = deepcopy(self.initial["prior-17-00000"])
            arm = {"id": "prior-smoke", "kind": "policy", "policy": policy,
                   "policy_sha256": state_hash(policy)}
        else:
            arm = {"id": kind, "kind": kind}
        return {"arm": arm, "seed": 1, "source_sha256": self.pins,
                "runtime": e.runtime(), "smoke": True}

    def test_initial_deduplication_is_weight_proof_and_rejects_nonzero_actor(self):
        proof = e.initial_equivalence(self.initial)
        self.assertEqual(proof["prior_initial"], "greedy")
        self.assertEqual(proof["plain_initial"], "plain-17-00000")
        changed = deepcopy(self.initial)
        changed["prior-29-00000"]["model"]["residual"]["weights"]["score.2.weight"][0][0] = .1
        with self.assertRaisesRegex(ValueError, "actor head is not zero"):
            e.initial_equivalence(changed)
        changed = deepcopy(self.initial)
        changed["prior-29-00000"]["model"]["residual"]["weights"]["encoder.0.weight"][0][0] += .1
        with self.assertRaisesRegex(ValueError, "matched prior/plain"):
            e.initial_equivalence(changed)

    def test_freeze_retains_all_twelve_states_and_exact_nine_arm_job_matrix(self):
        # Exercise manifest assembly with synthetic metadata, never evaluation
        # worlds or a claim that these fixtures are actually trained policies.
        records = []
        for variant in e.VARIANTS:
            for seed in e.SEEDS:
                initial = deepcopy(self.initial[f"{variant}-{seed}-00000"])
                final = deepcopy(initial)
                final["episodes_seen"] = 4096
                records.append(({"variant": variant, "seed": seed},
                                {f"{variant}-{seed}-00000": initial,
                                 f"{variant}-{seed}-04096": final}))
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "freeze.json"
            with patch.object(e, "read_completed_run", side_effect=records), \
                    patch.object(e, "TraverseEnvironment", side_effect=AssertionError("world opened")):
                manifest = e.freeze_runs([Path(str(i)) for i in range(6)], output)
            self.assertEqual(len(manifest["policies"]), 12)
            self.assertEqual(len(manifest["arms"]), 9)
            self.assertEqual(len(manifest["job_matrix"]), 1152)
            e.verify_manifest(manifest)
            changed = deepcopy(manifest)
            changed["policies"]["prior-17-04096"]["model"]["residual"]["weights"]["score.2.bias"][0] = .1
            with self.assertRaisesRegex(ValueError, "policy hash"):
                e.verify_manifest(changed)
            changed = deepcopy(manifest)
            changed["job_matrix"].pop()
            with self.assertRaisesRegex(ValueError, "job matrix"):
                e.verify_manifest(changed)

    def test_incomplete_training_and_changed_milestone_weights_fail_before_any_world(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report_path = root / "report.json"
            report_path.write_text(json.dumps({"schema": "hybrid-ppo-training-report-v1",
                                              "experiment": EXPERIMENT, "status": "deadline"}))
            with patch.object(e, "TraverseEnvironment", side_effect=AssertionError("world opened")):
                with self.assertRaisesRegex(ValueError, "complete4096"):
                    e.read_completed_run(root, self.pins)
                with self.assertRaisesRegex(ValueError, "exactly six"):
                    e.freeze_runs([root], root / "freeze.json")
                self.assertFalse((root / "freeze.json").exists())
            # Synthetic metadata only: no training or validation worlds opened.
            report = {"schema": "hybrid-ppo-training-report-v1", "experiment": EXPERIMENT,
                      "status": "complete", "smoke": False, "episodes_completed": 4096,
                      "episodes_target": 4096, "phase": "finished", "variant": "prior",
                      "algorithm": "prior", "seed": 17, "source_sha256": self.pins,
                      "batch_episodes": 32, "schedule_episodes": 4096,
                      "python": "3.12.16", "numpy": e.runtime()["numpy"], "torch": e.runtime()["torch"],
                      "validations": {str(n): {} for n in MILESTONES},
                      "checkpoints": {str(n): {"policy_sha256": "a" * 64,
                                               "checkpoint_sha256": "b" * 64,
                                               "validation_sha256": "c" * 64} for n in MILESTONES},
                      "history": [{"first_episode": i * 32, "last_episode": (i + 1) * 32,
                                   "artifact": f"batches/batch-{i:05d}.json.gz", "sha256": "d" * 64}
                                  for i in range(128)]}
            report_path.write_text(json.dumps(report))
            (root / "policy-00000.json").write_text("{}")
            # Missing multi-GB batch archives are intentional: their hashes are
            # report-bound records, while milestone bytes must actually match.
            with patch.object(e, "TraverseEnvironment", side_effect=AssertionError("world opened")):
                with self.assertRaisesRegex(ValueError, "milestone artifact hash"):
                    e.read_completed_run(root, self.pins)

    def test_job_weight_hash_and_seed_guard_fail_closed(self):
        job = self.job()
        job["arm"]["policy"]["episodes_seen"] = 1
        with patch.object(e, "TraverseEnvironment", side_effect=AssertionError("world opened")):
            with self.assertRaisesRegex(ValueError, "policy hash"):
                e.evaluate_job(job)
        job = self.job()
        job["smoke"] = False  # seed1 cannot enter a production final job
        with self.assertRaisesRegex(ValueError, "invalid evaluation job"):
            e.evaluate_job(job)

    def test_used_world_policy_and_beam_physics_choices_and_full_replay(self):
        for kind in ("policy", "beam"):
            job = self.job(kind)
            saved = e.verified_job(job)
            self.assertEqual(saved["status"], "complete", saved.get("error"))
            self.assertTrue(saved["audit"]["physics_verified"])
            self.assertTrue(saved["audit"]["full_controller_replay"])
            self.assertEqual(saved["bundle"]["episode"]["result"]["tick"], 420)
            if kind == "policy":
                bad = deepcopy(saved["bundle"])
                bad["episode"]["transitions"][0]["obs"]["global"][-1] += .1
                with self.assertRaisesRegex(ValueError, "full controller"):
                    e.audit_case(bad, job)

    def test_group_statistics_average_seeds_and_reject_missing_or_duplicate_cases(self):
        arms = [{"id": f"{v}-{s}-04096"} for v in e.VARIANTS for s in e.SEEDS]
        arms += [{"id": name} for name in ("greedy", "beam", "plain-initial")]
        manifest = {"arms": arms, "maps": list(e.FINAL_MAPS)}
        rewards = {"prior-17-04096": .4, "prior-29-04096": .5, "prior-43-04096": .6,
                   **{f"plain-{s}-04096": .45 for s in e.SEEDS},
                   "greedy": .48, "beam": .6, "plain-initial": 0}
        rows = [{"arm": arm["id"], "seed": seed, "status": "complete",
                 "reward": rewards[arm["id"]], "home": True, "alive": True, "invalid_calls": 0}
                for arm in arms for seed in e.FINAL_MAPS]
        summary = e.summarize(rows, manifest)
        self.assertAlmostEqual(summary["groups"]["prior"]["mean_reward"], .5)
        self.assertAlmostEqual(summary["contrasts"]["prior_minus_greedy"]["mean"], .02)
        self.assertAlmostEqual(summary["contrasts"]["prior_minus_plain"]["mean"], .05)
        self.assertTrue(summary["primary_success"])
        for changed in (rows[:-1], rows[:-1] + [rows[0]]):
            with self.assertRaisesRegex(ValueError, "missing/duplicate"):
                e.summarize(changed, manifest)


if __name__ == "__main__":
    unittest.main()
