"""Run the preregistered teacher, imitation, RL and matched check once."""

import argparse
import gzip
import json
import multiprocessing as mp
from pathlib import Path
import platform
import subprocess
import time

import numpy as np

from lightlag_rl.model import Adam
from lightlag_rl.train import atomic_json, batch_gradient, digest
from lightlag_rl_contextual.adapter import run_episode
from lightlag_rl_contextual.model import Policy
from tools.rl_feasible.run import pins as feasibility_pins, require

ROOT = Path(__file__).resolve().parents[2]
TRAIN = tuple(range(73000, 73128))
TEACHER = tuple(range(73000, 73016))
VALIDATE = tuple(range(73016, 73020))
CHECK = tuple(range(74000, 74016))
TRAIN_SEEDS = (17, 29, 43)
CONFIG = {"epochs": 200, "imitation_batch": 32, "imitation_lr": .01,
          "updates": 8, "rl_batch": 16, "rl_lr": .003, "entropy": .005,
          "max_norm": 5., "minimum_loss_reduction": .2,
          "draws": 2, "bootstrap": 10000, "bootstrap_seed": 17,
          "minimum_rl_gain": .02, "max_seconds": 3600, "workers": 4}
STAGES = ("untrained", "imitation", "rl")


def pins():
    result = feasibility_pins()
    files = [ROOT / "docs/lightlag-rl-contextual.md"]
    for package in ("lightlag_rl_contextual", "tools/rl_contextual"):
        files += list((ROOT / package).rglob("*.py"))
    result.update({str(p.relative_to(ROOT)): digest(p) for p in files})
    return dict(sorted(result.items()))


def normal(value):
    return json.loads(json.dumps(value, allow_nan=False))


def collect(job):
    return {"job": {k: v for k, v in job.items() if k != "policy_state"},
            "episode": run_episode(job["seed"], job["mode"], job.get("policy_state"), job.get("policy_seed", 0))}


def write_bundle(root, relative, value):
    path = root / relative
    require(not path.exists(), "artifact already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(json.dumps(value, allow_nan=False, separators=(",", ":")).encode(), mtime=0))
    return {"artifact": relative, "sha256": digest(path)}


def read_bundle(root, row):
    path = (root / row["artifact"]).resolve()
    require(path.is_relative_to(root.resolve()) and digest(path) == row["sha256"], "artifact hash/path")
    return json.loads(gzip.decompress(path.read_bytes()))


def fit_metrics(policy, examples):
    require(bool(examples), "empty teacher labels")
    probabilities = [policy.probabilities(d["features"]) for d in examples]
    return {"n": len(examples),
            "cross_entropy": float(np.mean([-np.log(max(p[d["action"]], 1e-300)) for p, d in zip(probabilities, examples)])),
            "accuracy": float(np.mean([np.argmax(p) == d["action"] for p, d in zip(probabilities, examples)]))}


def imitate(policy, examples, seed, epochs, check=lambda: None):
    optimizer, rng = Adam(policy), np.random.default_rng(seed)
    for epoch in range(epochs):
        check()
        order = rng.permutation(len(examples))
        for start in range(0, len(order), CONFIG["imitation_batch"]):
            indices = order[start:start + CONFIG["imitation_batch"]]
            gradient = {k: np.zeros_like(getattr(policy, k)) for k in ("W", "b", "v")}
            for i in indices:
                d = examples[int(i)]
                g = policy.gradient(d["features"], d["action"], 1., entropy=0.)
                for k in gradient:
                    gradient[k] += g[k] / len(indices)
            optimizer.step(gradient, lr=CONFIG["imitation_lr"], max_norm=CONFIG["max_norm"])
    return optimizer.state_dict()


def evaluation_jobs(seeds, states):
    result = []
    for train_seed in TRAIN_SEEDS:
        for stage in STAGES:
            for seed in seeds:
                for draw in range(CONFIG["draws"]):
                    result.append({"mode": "policy", "train_seed": train_seed, "stage": stage,
                                   "seed": seed, "draw": draw, "policy_seed": 1000003 * seed + draw,
                                   "policy_state": states[(train_seed, stage)]})
    result.extend({"mode": mode, "seed": seed, "policy_seed": 0}
                  for mode in ("greedy", "reference") for seed in seeds)
    return result


def evaluation_row(bundle, artifact):
    job, e = bundle["job"], bundle["episode"]
    require(e["result"]["tick"] == 420 and 0 <= e["reward"] <= 1, "incomplete/bad episode")
    return {**job, **artifact, "reward": e["reward"], "alive": e["result"]["alive"],
            "home": e["result"]["at_base"], "samples": len(e["result"]["samples"]),
            "invalid": len(e["invalid_calls"])}


def identity(job):
    return tuple(job.get(k) for k in ("mode", "train_seed", "stage", "seed", "draw", "policy_seed"))


def summarize(rows, seeds):
    placeholder = {(t, s): None for t in TRAIN_SEEDS for s in STAGES}
    expected = {identity(j) for j in evaluation_jobs(seeds, placeholder)}
    actual = [identity(r) for r in rows]
    require(len(actual) == len(expected) and set(actual) == expected, "incomplete/duplicate evaluation")
    def stats(subset):
        return {"n": len(subset), "mean_reward": float(np.mean([r["reward"] for r in subset])),
                "alive_home": sum(r["alive"] and r["home"] for r in subset),
                "deaths": sum(not r["alive"] for r in subset), "invalid": sum(r["invalid"] for r in subset)}
    stages = {s: stats([r for r in rows if r.get("stage") == s]) for s in STAGES}
    controls = {m: stats([r for r in rows if r["mode"] == m]) for m in ("greedy", "reference")}
    by_seed = {str(t): {s: stats([r for r in rows if r.get("train_seed") == t and r.get("stage") == s])
                       for s in STAGES} for t in TRAIN_SEEDS}
    diffs = [float(np.mean([r["reward"] for r in rows if r.get("stage") == "rl" and r["seed"] == seed]))
             - float(np.mean([r["reward"] for r in rows if r.get("stage") == "imitation" and r["seed"] == seed]))
             for seed in seeds]
    boot = np.random.default_rng(CONFIG["bootstrap_seed"]).choice(diffs, size=(CONFIG["bootstrap"], len(diffs))).mean(axis=1)
    interval = np.quantile(boot, [.025, .975]).tolist()
    a, b = stages["imitation"], stages["rl"]
    gate = {"gain_at_least_02": float(np.mean(diffs)) >= CONFIG["minimum_rl_gain"],
            "positive_interval": interval[0] > 0, "home_not_lower": b["alive_home"] >= a["alive_home"],
            "deaths_not_higher": b["deaths"] <= a["deaths"], "invalid_not_higher": b["invalid"] <= a["invalid"]}
    ref = controls["reference"]
    return {"stages": stages, "controls": controls, "training_seeds": by_seed,
            "primary": {"mean_gain": float(np.mean(diffs)), "bootstrap_95": interval,
                        "map_differences": dict(zip(map(str, seeds), diffs))},
            "gate": gate, "screen_passes": all(gate.values()),
            "reaches_reference": b["mean_reward"] >= ref["mean_reward"] and
                b["alive_home"] / b["n"] >= ref["alive_home"] / ref["n"] and b["deaths"] == 0 and b["invalid"] == 0}


def run(output, smoke=False):
    output = Path(output)
    require(not output.exists(), "preserve existing run; use a new path")
    feasibility_audit = ROOT / "docs/lightlag-rl-feasible-results/development/audit.json"
    if not smoke:
        audited = json.loads(feasibility_audit.read_text())
        require(audited["cases"] == 240 and audited["summary"]["screen_passes"] and
                audited["scaffold_features_choices_commands_reexecuted"], "feasibility prerequisite")
        require(audited["report_sha256"] == digest(feasibility_audit.parent / "report.json"), "prerequisite report hash")
    sources = pins()
    teacher_seeds, val_seeds = ((1,), (2,)) if smoke else (TEACHER, VALIDATE)
    train_maps, check_maps = ((1, 2), (1, 2)) if smoke else (TRAIN, CHECK)
    epochs, updates, batch = (2, 1, 4) if smoke else (CONFIG["epochs"], CONFIG["updates"], CONFIG["rl_batch"])
    output.mkdir(parents=True)
    freeze = {"schema": "rl-contextual-freeze-v1", "smoke": smoke, "config": CONFIG,
              "teacher_maps": list(teacher_seeds), "validation_maps": list(val_seeds),
              "train_maps": list(train_maps), "check_maps": list(check_maps), "training_seeds": list(TRAIN_SEEDS),
              "epochs": epochs, "updates": updates, "batch": batch, "source_sha256": sources,
              "feasibility_audit_sha256": digest(feasibility_audit) if not smoke else None,
              "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "python": platform.python_version(), "numpy": np.__version__, "cloud_jobs": 0, "model_api_calls": 0}
    atomic_json(output / "freeze.json", freeze)
    report = {"schema": "rl-contextual-run-v1", "status": "incomplete", "smoke": smoke,
              "freeze_sha256": digest(output / "freeze.json"), "teacher": [], "training": {}, "evaluation": []}
    started, failed = time.monotonic(), True
    def save():
        report["elapsed_seconds"] = time.monotonic() - started
        atomic_json(output / "report.json", report)
    def remaining():
        require(pins() == sources, "source drift")
        left = CONFIG["max_seconds"] - (time.monotonic() - started)
        if left <= 0:
            raise TimeoutError("production time limit")
        return left
    def policy_file(seed, stage, state):
        path = output / f"policy-{seed}-{stage}.json"
        require(not path.exists(), "checkpoint exists")
        atomic_json(path, state)
        return {"artifact": path.name, "sha256": digest(path)}
    save()
    pool = mp.get_context("spawn").Pool(CONFIG["workers"])
    try:
        teacher_jobs = [{"mode": "teacher", "seed": seed, "policy_seed": 0,
                         "split": "train" if seed in teacher_seeds else "validation"}
                        for seed in (*teacher_seeds, *val_seeds)]
        iterator = pool.imap_unordered(collect, teacher_jobs)
        examples, validation = [], []
        bundles = {}
        for _ in teacher_jobs:
            bundle = iterator.next(timeout=remaining())
            job = bundle["job"]
            entry = evaluation_row(bundle, write_bundle(output, f"teacher/{job['seed']}.json.gz", bundle))
            report["teacher"].append(entry)
            report["teacher"].sort(key=lambda r: r["seed"])
            bundles[job["seed"]] = bundle
            save()
            print(json.dumps({"teacher_cases": len(report["teacher"]), "total": len(teacher_jobs)}), flush=True)
        # Fixed seed order, independent of worker completion order.
        for seed in teacher_seeds:
            examples.extend(bundles[seed]["episode"]["trajectory"])
        for seed in val_seeds:
            validation.extend(bundles[seed]["episode"]["trajectory"])
        states, learners = {}, {}
        for seed in TRAIN_SEEDS:
            policy = Policy(seed)
            states[(seed, "untrained")] = policy.state_dict()
            entry = {"untrained": policy_file(seed, "untrained", policy.state_dict()),
                     "before_train": fit_metrics(policy, examples), "before_validation": fit_metrics(policy, validation),
                     "updates": []}
            report["training"][str(seed)] = entry
            save()
            optimizer_state = imitate(policy, examples, seed, epochs, remaining)
            entry.update({"after_train": fit_metrics(policy, examples), "after_validation": fit_metrics(policy, validation),
                          "imitation_optimizer": optimizer_state,
                          "imitation": policy_file(seed, "imitation", policy.state_dict())})
            entry["imitation_passes"] = entry["after_train"]["cross_entropy"] <= (1 - CONFIG["minimum_loss_reduction"]) * entry["before_train"]["cross_entropy"]
            states[(seed, "imitation")], learners[seed] = policy.state_dict(), policy
            save()
            print(json.dumps({"train_seed": seed, "imitation_train": entry["after_train"], "imitation_validation": entry["after_validation"]}), flush=True)
        require(smoke or all(e["imitation_passes"] for e in report["training"].values()), "imitation precondition failed; no RL/check")
        for seed in TRAIN_SEEDS:
            policy, rng = learners[seed], np.random.default_rng(seed)
            optimizer = Adam(policy)
            entry = report["training"][str(seed)]
            for update in range(1, updates + 1):
                maps = rng.choice(train_maps, size=batch // 2, replace=False)
                jobs = [{"mode": "policy", "seed": int(m), "policy_seed": int(rng.integers(0, 2**63)),
                         "train_seed": seed, "update": update, "policy_state": policy.state_dict()}
                        for m in maps for _ in range(2)]
                collected = pool.map_async(collect, jobs, chunksize=1).get(timeout=remaining())
                require([identity(b["job"]) for b in collected] == [identity(j) for j in jobs], "training job order")
                rows = [b["episode"] for b in collected]
                artifact = write_bundle(output, f"training/{seed}-{update:02d}.json.gz", collected)
                gradient, advantages = batch_gradient(policy, rows, entropy=CONFIG["entropy"])
                norm = optimizer.step(gradient, lr=CONFIG["rl_lr"], max_norm=CONFIG["max_norm"])
                checkpoint = {"policy": policy.state_dict(), "optimizer": optimizer.state_dict(), "rng_state": rng.bit_generator.state}
                checkpoint_path = output / f"checkpoint-{seed}-{update:02d}.json"
                atomic_json(checkpoint_path, checkpoint)
                entry["updates"].append({"update": update, **artifact, "advantages": advantages, "gradient_norm": norm,
                                         "checkpoint": checkpoint_path.name, "checkpoint_sha256": digest(checkpoint_path),
                                         "mean_reward": float(np.mean([r["reward"] for r in rows]))})
                remaining(); save()
                print(json.dumps({"train_seed": seed, "update": update, "reward": entry["updates"][-1]["mean_reward"]}), flush=True)
            states[(seed, "rl")] = policy.state_dict()
            entry["rl"] = policy_file(seed, "rl", policy.state_dict())
            save()
        # This artifact is saved before any held-out environment can be created.
        atomic_json(output / "evaluation-freeze.json", {"source_sha256": sources, "maps": list(check_maps),
                    "policies": {str(seed): {s: report["training"][str(seed)][s] for s in STAGES} for seed in TRAIN_SEEDS}})
        report["evaluation_freeze_sha256"] = digest(output / "evaluation-freeze.json")
        save()
        eval_jobs = evaluation_jobs(check_maps, states)
        iterator = pool.imap_unordered(collect, eval_jobs)
        for _ in eval_jobs:
            bundle = iterator.next(timeout=remaining())
            j = bundle["job"]
            name = f"{j['mode']}-{j.get('train_seed', 0)}-{j.get('stage', 'control')}-{j['seed']}-{j.get('draw', 0)}"
            entry = evaluation_row(bundle, write_bundle(output, f"evaluation/{name}.json.gz", bundle))
            report["evaluation"].append(entry)
            report["evaluation"].sort(key=lambda r: str(identity(r)))
            save()
            if len(report["evaluation"]) % 20 == 0:
                print(json.dumps({"evaluation_cases": len(report["evaluation"]), "total": len(eval_jobs)}), flush=True)
        remaining()
        report["summary"] = summarize(report["evaluation"], check_maps)
        report["status"] = "complete"
        failed = False
    except BaseException as error:
        report["failure"] = type(error).__name__ + ": " + str(error)[:500]
        raise
    finally:
        pool.terminate() if failed else pool.close()
        pool.join(); save()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.smoke)["summary"], indent=2))


if __name__ == "__main__":
    main()
