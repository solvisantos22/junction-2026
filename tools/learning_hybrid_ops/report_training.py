"""Audit terminal six-run archives and plot descriptive development curves only.

No simulator, training, inference, network, or fresh-world calls are made here.
The source-bound checkpoint restore verifies saved state, not training gradients.
"""

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re

import numpy as np
import torch

from lightlag_hybrid_train.learner import Learner
from lightlag_hybrid_train.train import (
    BATCH, EXPERIMENT, MILESTONES, RATE, VALIDATION_MAPS, assert_source,
    atomic_json, digest, read_json, summarize,
)
from tools.learning_hybrid_train.evaluate import initial_equivalence, require, runtime

SEEDS = (17, 29, 43)
VARIANTS = ("prior", "plain")
IDENTITIES = {f"{v}-{s}" for v in VARIANTS for s in SEEDS}


def finite_tree(value):
    if isinstance(value, dict):
        return all(finite_tree(v) for v in value.values())
    if isinstance(value, list):
        return all(finite_tree(v) for v in value)
    return not isinstance(value, float) or math.isfinite(value)


def aggregate(runs):
    """Only complete, matched three-seed checkpoints have a method mean."""
    result = {}
    for variant in VARIANTS:
        selected = [r for r in runs if r["variant"] == variant]
        require(len({r["seed"] for r in selected}) == len(selected), "duplicate seed")
        curve = []
        for count in MILESTONES:
            available = {r["seed"]: r["validations"][str(count)] for r in selected
                         if str(count) in r["validations"]}
            complete = set(available) == set(SEEDS)
            curve.append({"episodes": count, "available_seeds": sorted(available),
                          "coverage": f"{len(available)}/3", "complete_three_seed_mean": complete,
                          "mean_reward": float(np.mean([s["mean_reward"] for s in available.values()])) if complete else None,
                          "home": sum(s["home"] for s in available.values()) if complete else None,
                          "alive": sum(s["alive"] for s in available.values()) if complete else None,
                          "invalid_calls": sum(s["invalid_calls"] for s in available.values()) if complete else None,
                          "validation_missions": sum(s["count"] for s in available.values()) if complete else None})
        result[variant] = curve
    return result


def validate_run(root, job, observed, receipt, pins, inventory):
    run_id, variant, seed = job["run_id"], job["variant"], job["seed"]
    expected_job = {"run_id": run_id, "variant": variant, "seed": seed, "episodes": 4096}
    require(observed["job"] == job and observed["result"] is not None
            and observed.get("poll_error_type") is None, "original call is not confirmed terminal")
    metadata_path = f"_runs/{run_id}/run.json"
    require(metadata_path in inventory, "wrapper metadata missing from inventory")
    metadata, terminal = read_json(root / metadata_path), observed["result"]
    for record in (metadata, terminal):
        require(record["schema"] == "greedy-prior-run-v1" and record["job"] == expected_job
                and record["call_id"] == job["call_id"] and record["app_id"] == receipt["app_id"]
                and record["campaign_id"] == receipt["campaign_id"]
                and record["freeze_sha256"] == receipt["freeze_sha256"], "terminal identity differs")
    require(metadata["source_sha256"] == pins, "wrapper source changed")
    for key in ("status", "error_type", "started_unix", "finished_unix", "elapsed_seconds", "running_compute_estimate_usd"):
        require(metadata.get(key) == terminal.get(key), "terminal metadata/result disagreement")
    require(metadata["status"] not in ("running", "pending")
            and math.isclose(metadata["elapsed_seconds"], metadata["finished_unix"] - metadata["started_unix"], abs_tol=1e-6)
            and math.isclose(metadata["running_compute_estimate_usd"], metadata["elapsed_seconds"] * RATE, abs_tol=1e-9),
            "terminal timing/cost arithmetic changed")
    record = {**expected_job, "call_id": job["call_id"], "status": metadata["status"],
              "error_type": metadata.get("error_type"), "elapsed_seconds": metadata["elapsed_seconds"],
              "running_compute_estimate_usd": metadata["running_compute_estimate_usd"],
              "metadata_sha256": inventory[metadata_path], "validations": {}, "artifacts": {},
              "episodes_completed": None, "trainer_status": None, "complete4096": False}
    report_name = f"{run_id}/report.json"
    if report_name not in inventory:
        require(metadata["status"] != "completed", "completed run has no report")
        record["evidence_error"] = "No retained trainer report; actual episode count is unknown."
        return record, {}
    report = read_json(root / report_name)
    require(report["schema"] == "hybrid-ppo-training-report-v1" and report["experiment"] == EXPERIMENT
            and report["variant"] == report["algorithm"] == variant and report["seed"] == seed
            and report["smoke"] is False and report["source_sha256"] == pins
            and report["episodes_target"] == report["schedule_episodes"] == 4096
            and report["batch_episodes"] == BATCH, "trainer identity/source changed")
    require(".".join(report["python"].split(".")[:2]) == runtime()["python"]
            and report["numpy"] == runtime()["numpy"]
            and report["torch"].split("+")[0] == runtime()["torch"], "trainer runtime changed")
    for saved_hash in (metadata.get("trainer_report_sha256"), (observed.get("progress") or {}).get("report_sha256")):
        if saved_hash is not None:
            require(saved_hash == inventory[report_name], "terminal report hash changed")
    completed, history = report["episodes_completed"], report["history"]
    require(type(completed) is int and 0 <= completed <= 4096 and completed % BATCH == 0
            and len(history) == completed // BATCH, "training history/count incomplete")
    for i, batch in enumerate(history):
        require(batch["first_episode"] == i * BATCH and batch["last_episode"] == (i + 1) * BATCH
                and batch["artifact"] == f"batches/batch-{i:05d}.json.gz"
                and re.fullmatch(r"[a-f0-9]{64}", batch["sha256"]), "batch history changed")
    require(set(report["validations"]) <= set(map(str, MILESTONES))
            and set(report["validations"]) <= set(report["checkpoints"]), "undeclared validation milestone")
    policies = {}
    for count_string, expected_summary in report["validations"].items():
        count = int(count_string)
        require(count <= completed, "validation beyond completed training")
        hashes = report["checkpoints"][count_string]
        names = {"policy_sha256": f"policy-{count:05d}.json", "checkpoint_sha256": f"checkpoint-{count:05d}.json.gz",
                 "validation_sha256": f"validation-{count:05d}.json.gz"}
        for key, name in names.items():
            relative = f"{run_id}/{name}"
            require(relative in inventory and inventory[relative] == hashes[key], "milestone artifact hash changed")
            record["artifacts"][name] = hashes[key]
        policy = read_json(root / run_id / names["policy_sha256"])
        checkpoint = read_json(root / run_id / names["checkpoint_sha256"])
        identity = checkpoint["identity"]
        require(checkpoint["schema"] == "hybrid-ppo-checkpoint-v1" and checkpoint["episodes_completed"] == count
                and all(identity[key] == report[key] for key in ("experiment", "variant", "algorithm", "seed", "smoke",
                                                                "source_sha256", "numpy", "torch", "python", "batch_episodes", "schedule_episodes"))
                and checkpoint["history"] == history[:count // BATCH], "checkpoint identity/history changed")
        restored = Learner.from_state(checkpoint["learner"])
        require(finite_tree(checkpoint["learner"]) and restored.state_dict() == checkpoint["learner"]
                and restored.inference_state() == policy and restored.seed == seed
                and policy["algorithm"] == variant and policy["episodes_seen"] == count,
                "checkpoint optimizer/RNG/policy restoration changed")
        validation = read_json(root / run_id / names["validation_sha256"])
        episodes = validation["episodes"]
        require(validation["schema"] == "hybrid-ppo-validation-v1" and validation["experiment"] == EXPERIMENT
                and validation["variant"] == variant and validation["seed"] == seed
                and validation["episodes_completed"] == count and validation["policy_sha256"] == hashes["policy_sha256"]
                and validation["maps"] == list(VALIDATION_MAPS)
                and [e["seed"] for e in episodes] == list(VALIDATION_MAPS), "validation identity/maps changed")
        require(all(e["result"]["tick"] == 420 and math.isfinite(e["reward"]) and 0 <= e["reward"] <= 1
                    and e["reward"] == e["result"]["raw_score"] / e["result"]["max_available_value"]
                    for e in episodes), "validation reward arithmetic changed")
        require(validation["summary"] == summarize(episodes) == expected_summary, "validation summary changed")
        record["validations"][count_string] = expected_summary
        if count == 0:
            policies[f"{run_id}-00000"] = policy
    complete = metadata["status"] == "completed" and report["status"] == "complete" and completed == 4096
    if metadata["status"] == "completed":
        require(complete and report["phase"] == "finished"
                and set(report["validations"]) == set(map(str, MILESTONES)), "claimed completion is incomplete")
    record.update(episodes_completed=completed, trainer_status=report["status"], complete4096=complete,
                  report_sha256=inventory[report_name], training_batches=len(history),
                  training_summary={"count": sum(b["summary"]["count"] for b in history),
                                    "home": sum(b["summary"]["home"] for b in history),
                                    "alive": sum(b["summary"]["alive"] for b in history),
                                    "invalid_calls": sum(b["summary"]["invalid_calls"] for b in history)})
    return record, policies


def build_report(download, freeze_path):
    root, freeze_path = Path(download), Path(freeze_path)
    freeze, receipt = read_json(freeze_path), read_json(root / "receipt.json")
    pins = freeze["source_sha256"]
    assert_source(pins)
    require(freeze["schema"] == "greedy-prior-freeze-v1" and freeze["experiment"] == EXPERIMENT
            and receipt["schema"] == "greedy-prior-receipt-v1" and receipt["status"] == "submitted"
            and receipt["freeze_sha256"] == digest(freeze_path) and receipt["source_sha256"] == pins
            and receipt["campaign_id"] == freeze["campaign"]["campaign_id"], "receipt/freeze identity changed")
    jobs = receipt["jobs"]
    require(len(jobs) == 6 and {j["run_id"] for j in jobs} == IDENTITIES
            and len({j["call_id"] for j in jobs}) == 6
            and [{k: j[k] for k in ("run_id", "variant", "seed", "episodes")} for j in jobs] == freeze["campaign"]["jobs"],
            "all six original jobs required")
    downloaded, status = read_json(root / "download.json"), read_json(root / "status.json")
    inventory = downloaded["files"]
    require(downloaded["archives"] is True, "download with --archives required")
    for relative, expected_hash in inventory.items():
        path = root / relative
        require(not Path(relative).is_absolute() and path.resolve().is_relative_to(root.resolve())
                and digest(path) == expected_hash, "download artifact hash changed")
    require(all(name in inventory for name in ("receipt.json", "status.json"))
            and status["schema"] == "greedy-prior-status-v1" and status["receipt_sha256"] == digest(root / "receipt.json")
            and status["campaign_id"] == receipt["campaign_id"] and status["app_id"] == receipt["app_id"]
            and len(status["jobs"]) == 6 and {r["job"]["run_id"] for r in status["jobs"]} == IDENTITIES,
            "terminal status identity changed")
    rows = {row["job"]["run_id"]: row for row in status["jobs"]}
    runs, initials = [], {}
    for job in jobs:
        record, retained = validate_run(root, job, rows[job["run_id"]], receipt, pins, inventory)
        runs.append(record)
        initials.update(retained)
    proof = initial_equivalence(initials) if len(initials) == 6 else {"verified": False, "reason": "initial checkpoint missing"}
    return {"schema": "hybrid-ppo-descriptive-report-v1", "experiment": EXPERIMENT,
            "created_utc": datetime.now(timezone.utc).isoformat(), "campaign_id": receipt["campaign_id"],
            "app_id": receipt["app_id"], "freeze_sha256": digest(freeze_path), "source_sha256": pins,
            "receipt_sha256": digest(root / "receipt.json"), "download_manifest_sha256": digest(root / "download.json"),
            "status_sha256": digest(root / "status.json"), "reporter_sha256": digest(__file__),
            "runs": runs, "curves": aggregate(runs), "initial_behavior_proof": proof,
            "initial_behavior_note": "The prior starts with greedy behavior programmed into its action probabilities. Its initial advantage over plain PPO is not learning.",
            "all_six_complete4096": all(r["complete4096"] for r in runs),
            "fresh_evaluation_performed": False, "final_primary_success": None,
            "primary_gate_reason": "Descriptive development evidence only; any incomplete original run fails the required all-six completion gate. No replacement, imputation, fresh-world comparison, or final primary success is reported.",
            "retained_training_missions": sum(r["episodes_completed"] or 0 for r in runs),
            "training_count_complete": all(r["episodes_completed"] is not None for r in runs),
            "running_compute_estimate_usd": sum(r["running_compute_estimate_usd"] for r in runs),
            "cost_note": freeze["cost_note"], "validation_maps": list(VALIDATION_MAPS),
            "validation_note": "Repeated development worlds; individual later prior curves are not a three-seed method estimate. No missing seed is imputed.",
            "audit_limit": "Downloaded bytes, source/receipt identities, checkpoint optimizer/RNG roundtrip, inference-state equality, initial zero heads, and validation reward/summary arithmetic verified. Batch hashes/history are report-bound; no training gradient replay or mission physics replay is performed."}


def plot_report(report, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(11.8, 4.8), sharey=True)
    colors = {17: "#2563eb", 29: "#d97706", 43: "#16856b"}
    for ax, variant in zip(axes, VARIANTS):
        for row in report["runs"]:
            if row["variant"] != variant:
                continue
            counts = sorted(map(int, row["validations"]))
            label = f"Seed {row['seed']} ({row['episodes_completed']} missions; {row['status']})"
            ax.plot(counts, [100 * row["validations"][str(n)]["mean_reward"] for n in counts],
                    marker="o", linestyle="--", color=colors[row["seed"]], linewidth=1.3, label=label)
        common = [r for r in report["curves"][variant] if r["complete_three_seed_mean"]]
        ax.plot([r["episodes"] for r in common], [100 * r["mean_reward"] for r in common],
                color="#111827", linewidth=2.7, marker="s", label="Mean: all 3 seeds only")
        for point in report["curves"][variant]:
            ax.text(point["episodes"], 1.02, point["coverage"], transform=ax.get_xaxis_transform(),
                    ha="center", fontsize=9, color="#475569")
        ax.set_title("Greedy-prior PPO" if variant == "prior" else "Plain PPO", pad=27)
        ax.set_xticks(MILESTONES)
        ax.set_xlim(-120, 4216)
        ax.set_ylim(bottom=0)
        ax.set_xlabel("Completed training missions (coverage shown above)")
        ax.grid(alpha=.2)
        ax.legend(loc="lower right", fontsize=7.5)
    axes[0].set_ylabel("Mean official reward on 64 development worlds (%)")
    fig.suptitle("Descriptive learning curves — all six original runs retained", fontsize=14, y=.99)
    fig.text(.5, .015, "Greedy-prior starting advantage is programmed, not learned. Reused development worlds; no fresh evaluation.\n"
             "Later prior points show individual available seeds only; no missing-seed estimate or final primary claim.",
             ha="center", fontsize=9)
    fig.tight_layout(rect=(0, .09, 1, .96))
    for extension in ("png", "svg"):
        fig.savefig(Path(output) / f"learning-curves.{extension}", dpi=160)
    plt.close(fig)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", type=Path, required=True)
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    torch.set_num_threads(1)
    report = build_report(args.download, args.freeze)
    args.output.mkdir(parents=True, exist_ok=False)
    atomic_json(args.output / "report.json", report)
    plot_report(report, args.output)
    atomic_json(args.output / "artifacts.json", {p.name: digest(p) for p in sorted(args.output.iterdir()) if p.is_file()})
    print(json.dumps({"output": str(args.output), "runs": len(report["runs"]),
                      "all_six_complete4096": report["all_six_complete4096"]}))


if __name__ == "__main__":
    main()
