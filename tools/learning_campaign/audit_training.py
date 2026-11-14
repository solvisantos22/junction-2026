"""Audit retained training actions and updates without constructing environments.

Exact numeric reconstruction is the default. --atol explicitly permits an
absolute tolerance, reported with the largest observed difference. Different
CPU/PyTorch platforms may fail even when artifacts are valid; failures are not
silently waived. Validation physics is a separate audit.
"""

import argparse
import base64
import json
import math
from pathlib import Path
import platform

import numpy as np
import torch

from lightlag_learning.environment import CANDIDATE_FEATURES, GLOBAL_FEATURES
from lightlag_learning.learners import Learner, chooser_from_state
from lightlag_learning.train import BATCH, ROOT, atomic_json, digest, read_json, summarize, training_map

PACKAGES = ("lightlag_learning", "lightlag_traverse", "lightlag", "lightlag_mcp",
            "lightlag_rl", "lightlag_rl_feasible")


def unwrap(value):
    """Decode one checkpoint layer, preserving array efficiency and mapping order independence."""
    if not isinstance(value, dict):
        return value
    if "__mapping__" in value:
        return {unwrap(key): item for key, item in value["__mapping__"]}
    if "__tuple__" in value:
        return value["__tuple__"]
    if "__array__" in value:
        dtype = np.dtype(value["dtype"])
        if dtype.kind not in "bifu":
            raise ValueError("unsupported checkpoint array type")
        return np.frombuffer(base64.b64decode(value["__array__"], validate=True), dtype=dtype).reshape(value["shape"])
    if "__tensor__" in value:
        return np.asarray(value["__tensor__"], dtype=value["dtype"])
    return value


class Comparison:
    def __init__(self, atol=0.):
        if not math.isfinite(atol) or atol < 0:
            raise ValueError("atol must be finite and nonnegative")
        self.atol, self.maximum_difference = atol, 0.

    def same(self, actual, expected, path="state"):
        actual, expected = unwrap(actual), unwrap(expected)
        if isinstance(actual, dict) and isinstance(expected, dict):
            if actual.keys() != expected.keys():
                raise ValueError(path + ": mapping keys differ")
            for key in actual:
                self.same(actual[key], expected[key], path + "/" + str(key))
        elif isinstance(actual, np.ndarray) and isinstance(expected, np.ndarray):
            if actual.shape != expected.shape or actual.dtype != expected.dtype:
                raise ValueError(path + ": array shape/dtype differs")
            if actual.dtype.kind in "biu":
                if not np.array_equal(actual, expected):
                    raise ValueError(path + ": exact integer/boolean array differs")
                return
            if not np.isfinite(actual).all() or not np.isfinite(expected).all():
                raise ValueError(path + ": nonfinite array")
            difference = float(np.max(np.abs(actual.astype(float) - expected.astype(float)))) if actual.size else 0.
            self.maximum_difference = max(self.maximum_difference, difference)
            if difference > self.atol:
                raise ValueError(f"{path}: numeric difference {difference} exceeds atol={self.atol}")
        elif isinstance(actual, (list, tuple)) and isinstance(expected, (list, tuple)):
            if len(actual) != len(expected):
                raise ValueError(path + ": sequence lengths differ")
            for index, (left, right) in enumerate(zip(actual, expected)):
                self.same(left, right, path + "/" + str(index))
        elif type(actual) is float and type(expected) is float:
            difference = abs(actual - expected)
            if not math.isfinite(difference):
                raise ValueError(path + ": nonfinite number")
            self.maximum_difference = max(self.maximum_difference, difference)
            if difference > self.atol:
                raise ValueError(f"{path}: numeric difference {difference} exceeds atol={self.atol}")
        elif type(actual) is not type(expected) or actual != expected:
            raise ValueError(path + ": values differ")


def audit(directory, atol=0., source_root=ROOT):
    directory, source_root = Path(directory).resolve(), Path(source_root).resolve()
    comparison = Comparison(atol)
    report = read_json(directory / "report.json")
    if (report["schema"] != "learning-training-report-v1" or report["status"] not in ("complete", "deadline")
            or report["batch_episodes"] != BATCH or report["schedule_episodes"] != 2048):
        raise ValueError("audit requires a settled complete/deadline training report")
    latest = read_json(directory / "checkpoint-latest.json.gz")
    initial = read_json(directory / "checkpoint-00000.json.gz")
    if latest["schema"] != "learning-run-checkpoint-v1" or initial["schema"] != "learning-run-checkpoint-v1":
        raise ValueError("unrecognized run checkpoint")
    identity = latest["identity"]
    if initial["identity"] != identity or any(report[key] != value for key, value in identity.items()):
        raise ValueError("report/checkpoint identity differs")
    files = [source_root / "docs/learning-campaign.md"]
    for package in PACKAGES:
        files.extend((source_root / package).rglob("*.py"))
    pins = {str(p.relative_to(source_root)): digest(p) for p in files}
    if pins != identity["source_sha256"]:
        raise ValueError("frozen training source closure changed")
    if latest["history"] != report["history"] or latest["validations"] != report["validations"]:
        raise ValueError("report differs from latest committed checkpoint")
    torch.set_num_threads(1)
    learner = Learner(report["algorithm"], len(CANDIDATE_FEATURES), len(GLOBAL_FEATURES), report["seed"], 2048)
    comparison.same(learner.state_dict(), initial["learner"], "initial_seeded_state")
    learner = Learner.from_state(initial["learner"])
    seen, cursor, actions, invalid, checkpoints = set(), 0, 0, 0, 1
    for record in report["history"]:
        artifact = (directory / record["artifact"]).resolve()
        if (not artifact.is_relative_to(directory) or artifact in seen
                or record["first_episode"] != cursor or record["last_episode"] != cursor + BATCH
                or digest(artifact) != record["sha256"]):
            raise ValueError("training history identity/hash mismatch")
        seen.add(artifact)
        batch = read_json(artifact)
        if (batch["schema"] != "learning-batch-v1" or batch["first_episode"] != cursor
                or len(batch["episodes"]) != BATCH):
            raise ValueError("batch schema/count mismatch")
        comparison.same(learner.inference_state(), batch["policy"], "behavior_policy")
        for offset, episode in enumerate(batch["episodes"]):
            expected_seed = training_map(cursor + offset, report["smoke"])
            action_seed = report["seed"] * 1_000_000_000 + cursor + offset
            if (episode["seed"] != expected_seed or episode["action_seed"] != action_seed
                    or episode["decision_count"] != len(episode["transitions"])
                    or episode["result"]["tick"] != 420
                    or episode["reward"] != episode["result"]["raw_score"] / episode["result"]["max_available_value"]):
                raise ValueError("episode map/RNG/count/terminal grade mismatch")
            choose = chooser_from_state(batch["policy"], np.random.default_rng(action_seed), explore=True)
            for transition in episode["transitions"]:
                if choose(transition["obs"]) != transition["action"]:
                    raise ValueError("saved behavior policy does not reproduce recorded action")
                actions += 1
            invalid += len(episode["invalid_calls"])
        metrics = learner.update(batch["episodes"])
        comparison.same(metrics, batch["metrics"], "update_metrics")
        for key, value in {**summarize(batch["episodes"]), **metrics}.items():
            comparison.same(value, record[key], "history/" + key)
        cursor += BATCH
        milestone = directory / f"checkpoint-{cursor:05d}.json.gz"
        if milestone.exists():
            retained = read_json(milestone)
            if retained["identity"] != identity:
                raise ValueError("milestone identity changed")
            comparison.same(learner.state_dict(), retained["learner"], "milestone_learner")
            checkpoints += 1
    if (cursor != learner.episodes_seen or cursor != report["episodes_completed"]
            or (report["status"] == "complete" and cursor != report["episodes_target"])):
        raise ValueError("training completion counters differ")
    comparison.same(learner.state_dict(), latest["learner"], "latest_learner")
    comparison.same(Learner.from_state(latest["learner"]).state_dict(), latest["learner"], "checkpoint_roundtrip")
    return {"schema": "learning-training-audit-v1", "report_sha256": digest(directory / "report.json"),
            "latest_checkpoint_sha256": digest(directory / "checkpoint-latest.json.gz"),
            "algorithm": report["algorithm"], "seed": report["seed"], "smoke": report["smoke"],
            "training_status": report["status"], "episodes_verified": cursor,
            "batches_verified": len(seen), "training_actions_replayed": actions,
            "invalid_calls_retained": invalid, "milestone_checkpoints_verified": checkpoints,
            "source_files_verified": len(pins), "source_sha256": pins,
            "full_update_reconstruction": True, "checkpoint_roundtrip": True,
            "atol": comparison.atol, "maximum_numeric_difference": comparison.maximum_difference,
            "artifact_runtime": {key: identity[key] for key in ("python", "numpy", "torch")},
            "auditor_runtime": {"python": platform.python_version(), "numpy": np.__version__, "torch": torch.__version__},
            "new_environment_cases": 0, "model_api_calls": 0, "cloud_jobs": 0,
            "limits": ["Training feature extraction is source-pinned; environments were not rerun.",
                       "Validation physics and final evaluation are audited separately.",
                       "Cross-platform floating-point changes can fail action/update reproduction; no mismatch is silently waived.",
                       "Batch timing excludes the following latest-checkpoint serialization/write; use total wall time for throughput."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--source-root", type=Path, default=ROOT)
    parser.add_argument("--atol", type=float, default=0.)
    args = parser.parse_args()
    result = audit(args.directory, args.atol, args.source_root)
    if args.output:
        if args.output.exists():
            raise ValueError("audit output already exists")
        atomic_json(args.output, result)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
