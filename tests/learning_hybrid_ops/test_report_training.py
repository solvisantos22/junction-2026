from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

import torch

from lightlag_hybrid_train.learner import Learner
from lightlag_hybrid_train.train import (
    EXPERIMENT, MILESTONES, RATE, VALIDATION_MAPS, atomic_json, digest, read_json,
    source_manifest, summarize,
)
from tools.learning_hybrid_ops import report_training as r


class ReportTrainingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        cls.download = cls.root / "download"
        cls.download.mkdir()
        cls.pins = source_manifest()
        cls.jobs = [{"run_id": f"{v}-{s}", "variant": v, "seed": s, "episodes": 4096}
                    for v in r.VARIANTS for s in r.SEEDS]
        cls.freeze_path = cls.root / "freeze.json"
        atomic_json(cls.freeze_path, {"schema": "greedy-prior-freeze-v1", "experiment": EXPERIMENT,
                                    "source_sha256": cls.pins, "cost_note": "Synthetic cost fixture; not invoice.",
                                    "campaign": {"campaign_id": "synthetic", "jobs": cls.jobs}})
        receipt = {"schema": "greedy-prior-receipt-v1", "status": "submitted", "app_id": "synthetic-app",
                   "campaign_id": "synthetic", "source_sha256": cls.pins,
                   "freeze_sha256": digest(cls.freeze_path),
                   "jobs": [{**j, "call_id": "synthetic-" + j["run_id"]} for j in cls.jobs]}
        atomic_json(cls.download / "receipt.json", receipt)
        status = {"schema": "greedy-prior-status-v1", "receipt_sha256": digest(cls.download / "receipt.json"),
                  "campaign_id": "synthetic", "app_id": "synthetic-app", "jobs": []}
        for job in receipt["jobs"]:
            run_id, variant, seed = job["run_id"], job["variant"], job["seed"]
            failed = run_id == "prior-29"
            count = 1760 if failed else 4096
            learner = Learner(variant, 20, 14, seed)
            identity = {"experiment": EXPERIMENT, "variant": variant, "algorithm": variant, "seed": seed,
                        "smoke": False, "source_sha256": cls.pins, "batch_episodes": 32,
                        "schedule_episodes": 4096, **r.runtime()}
            summary = {"count": 32, "mean_reward": .2, "home": 32, "alive": 32,
                       "invalid_calls": 0, "mean_decisions": 2.}
            history = [{"first_episode": i * 32, "last_episode": (i + 1) * 32,
                        "artifact": f"batches/batch-{i:05d}.json.gz", "sha256": "a" * 64, "summary": summary}
                       for i in range(count // 32)]
            report = {**identity, "schema": "hybrid-ppo-training-report-v1", "episodes_target": 4096,
                      "episodes_completed": count, "status": "running" if failed else "complete",
                      "phase": "training-01760" if failed else "finished", "history": history,
                      "checkpoints": {}, "validations": {}}
            for milestone in MILESTONES:
                if milestone > count:
                    continue
                learner.episodes_seen = milestone
                policy = learner.inference_state()
                base = cls.download / run_id
                policy_path = base / f"policy-{milestone:05d}.json"
                checkpoint_path = base / f"checkpoint-{milestone:05d}.json.gz"
                validation_path = base / f"validation-{milestone:05d}.json.gz"
                atomic_json(policy_path, policy)
                atomic_json(checkpoint_path, {"schema": "hybrid-ppo-checkpoint-v1", "identity": identity,
                                             "episodes_completed": milestone, "learner": learner.state_dict(),
                                             "history": history[:milestone // 32]})
                reward = .36 if variant == "prior" else .30 * milestone / 4096
                episodes = [{"seed": world, "reward": reward, "invalid_calls": [], "decision_count": 2,
                             "result": {"tick": 420, "raw_score": reward, "max_available_value": 1,
                                        "at_base": True, "alive": True}} for world in VALIDATION_MAPS]
                validation = {"schema": "hybrid-ppo-validation-v1", "experiment": EXPERIMENT,
                              "variant": variant, "seed": seed, "episodes_completed": milestone,
                              "policy_sha256": digest(policy_path), "maps": list(VALIDATION_MAPS),
                              "episodes": episodes, "summary": summarize(episodes)}
                atomic_json(validation_path, validation)
                report["validations"][str(milestone)] = validation["summary"]
                report["checkpoints"][str(milestone)] = {
                    "policy_sha256": digest(policy_path), "checkpoint_sha256": digest(checkpoint_path),
                    "validation_sha256": digest(validation_path)}
            atomic_json(cls.download / run_id / "report.json", report)
            metadata = {"schema": "greedy-prior-run-v1", "job": {k: job[k] for k in ("run_id", "variant", "seed", "episodes")},
                        "call_id": job["call_id"], "app_id": "synthetic-app", "campaign_id": "synthetic",
                        "freeze_sha256": digest(cls.freeze_path), "source_sha256": cls.pins,
                        "status": "wrapper_error" if failed else "completed",
                        "started_unix": 100., "finished_unix": 200., "elapsed_seconds": 100.,
                        "running_compute_estimate_usd": 100 * RATE}
            if failed:
                metadata.update(error_type="KeyboardInterrupt", traceback="PRIVATE TRACEBACK")
            else:
                metadata["trainer_report_sha256"] = digest(cls.download / run_id / "report.json")
            atomic_json(cls.download / "_runs" / run_id / "run.json", metadata)
            status["jobs"].append({"job": job, "result": metadata, "poll_error_type": None,
                                   "progress": {"report_sha256": digest(cls.download / run_id / "report.json")}})
        atomic_json(cls.download / "status.json", status)
        cls.inventory = {str(p.relative_to(cls.download)): digest(p) for p in cls.download.rglob("*") if p.is_file()}
        atomic_json(cls.download / "download.json", {"archives": True, "files": cls.inventory})
        cls.report = r.build_report(cls.download, cls.freeze_path)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_stale_running_report_preserves_terminal_failure_and_no_final_gate(self):
        report = self.report
        prior29 = next(row for row in report["runs"] if row["seed"] == 29 and row["variant"] == "prior")
        self.assertEqual(prior29["status"], "wrapper_error")
        self.assertEqual(prior29["trainer_status"], "running")
        self.assertEqual(prior29["episodes_completed"], 1760)
        self.assertFalse(prior29["complete4096"])
        self.assertFalse(report["all_six_complete4096"])
        self.assertFalse(report["fresh_evaluation_performed"])
        self.assertIsNone(report["final_primary_success"])
        self.assertEqual(report["retained_training_missions"], 5 * 4096 + 1760)
        self.assertEqual(report["initial_behavior_proof"]["prior_initial"], "greedy")
        self.assertNotIn("PRIVATE TRACEBACK", str(report))

    def test_missing_seed_suppresses_method_mean_but_preserves_individual_curves(self):
        prior = self.report["curves"]["prior"]
        self.assertEqual([p["episodes"] for p in prior if p["mean_reward"] is not None], [0, 512])
        self.assertEqual(prior[-1]["coverage"], "2/3")
        self.assertEqual(prior[-1]["available_seeds"], [17, 43])
        self.assertIsNone(prior[-1]["mean_reward"])
        self.assertTrue(all(p["complete_three_seed_mean"] for p in self.report["curves"]["plain"]))
        missing = [row for row in self.report["runs"] if not (row["variant"] == "plain" and row["seed"] == 43)]
        self.assertTrue(all(p["mean_reward"] is None for p in r.aggregate(missing)["plain"]))

    def test_tampered_milestone_bytes_fail_inventory_before_model_restore(self):
        path = self.download / "prior-17" / "policy-00512.json"
        original = path.read_bytes()
        try:
            path.write_bytes(original + b" ")
            with self.assertRaisesRegex(ValueError, "download artifact hash"):
                r.build_report(self.download, self.freeze_path)
        finally:
            path.write_bytes(original)

    def test_rehashed_validation_arithmetic_tamper_still_fails(self):
        job = read_json(self.download / "receipt.json")["jobs"][0]
        observed = read_json(self.download / "status.json")["jobs"][0]
        receipt = read_json(self.download / "receipt.json")
        validation_path = self.download / "prior-17" / "validation-00512.json.gz"
        report_path = self.download / "prior-17" / "report.json"
        originals = {p: p.read_bytes() for p in (validation_path, report_path)}
        try:
            validation = read_json(validation_path)
            validation["episodes"][0]["reward"] += .01
            atomic_json(validation_path, validation)
            report = read_json(report_path)
            report["checkpoints"]["512"]["validation_sha256"] = digest(validation_path)
            atomic_json(report_path, report)
            inventory = deepcopy(self.inventory)
            inventory["prior-17/validation-00512.json.gz"] = digest(validation_path)
            inventory["prior-17/report.json"] = digest(report_path)
            # Remove unrelated report-hash check to target the arithmetic validator.
            observed["progress"]["report_sha256"] = digest(report_path)
            metadata_path = self.download / "_runs" / "prior-17" / "run.json"
            originals[metadata_path] = metadata_path.read_bytes()
            metadata = read_json(metadata_path)
            metadata["trainer_report_sha256"] = digest(report_path)
            atomic_json(metadata_path, metadata)
            inventory["_runs/prior-17/run.json"] = digest(metadata_path)
            with self.assertRaisesRegex(ValueError, "reward arithmetic"):
                r.validate_run(self.download, job, observed, receipt, self.pins, inventory)
        finally:
            for path, data in originals.items():
                path.write_bytes(data)

    def test_missing_original_identity_and_changed_source_fail_closed(self):
        receipt_path = self.download / "receipt.json"
        original = receipt_path.read_bytes()
        try:
            receipt = read_json(receipt_path)
            receipt["jobs"].pop()
            atomic_json(receipt_path, receipt)
            with self.assertRaisesRegex(ValueError, "all six original"):
                r.build_report(self.download, self.freeze_path)
            receipt = read_json(receipt_path)
            receipt["source_sha256"] = {}
            atomic_json(receipt_path, receipt)
            with self.assertRaisesRegex(ValueError, "receipt/freeze"):
                r.build_report(self.download, self.freeze_path)
        finally:
            receipt_path.write_bytes(original)


if __name__ == "__main__":
    unittest.main()
