"""Reconstruct learning updates, saved physics and evaluation/teacher scaffolds."""

import argparse
from collections import defaultdict
import json
import multiprocessing as mp
from pathlib import Path

import numpy as np

from lightlag_rl.model import Adam
from lightlag_rl.train import atomic_json, batch_gradient, digest
from lightlag_rl_contextual.adapter import executed_decisions
from lightlag_rl_contextual.model import Policy
from lightlag_rl_persistence import GoalChooser
from lightlag_traverse.environment import TraverseEnvironment
from tools.rl_feasible.run import require
from .run import (CHECK, CONFIG, STAGES, TEACHER, TRAIN, TRAIN_SEEDS, VALIDATE, collect,
                  evaluation_jobs, evaluation_row, fit_metrics, identity, imitate, normal,
                  pins, read_bundle, summarize)


def close(a, b, name):
    if isinstance(a, dict):
        require(isinstance(b, dict) and set(a) == set(b), name + " keys")
        for key in a:
            close(a[key], b[key], name + "." + key)
    elif isinstance(a, list):
        require(isinstance(b, list) and len(a) == len(b), name + " length")
        for i, (x, y) in enumerate(zip(a, b)):
            close(x, y, f"{name}[{i}]")
    elif type(a) is float:
        require(np.isclose(a, b, atol=1e-10, rtol=1e-9), name + " numerical drift")
    else:
        require(a == b, name + " differs")


def physics(episode):
    replay = episode["replay"]
    env = TraverseEnvironment(episode["seed"])
    commands = defaultdict(list)
    for command in replay["commands"]:
        commands[command["sent_tick"]].append(command)
    for tick in range(420):
        for command in commands.pop(tick, []):
            require(normal(env.uplink([command["command"]])) == [command], "physics command")
        env.advance(1)
    result = env.evaluate()
    require(not commands and normal(env.replay()) == replay, "physics replay differs")
    require(normal(result) == episode["result"] and episode["reward"] == result["raw_score"] / result["max_available_value"], "grade differs")
    require(episode["trajectory"] == executed_decisions(episode["decisions"]), "overridden proposals entered gradient")


def choices(episode, policy):
    rng = np.random.default_rng(episode["policy_seed"])
    wrapper = GoalChooser(lambda ids, features: policy.choose(features, rng), persistent=True)
    for decision in episode["decisions"]:
        wrapper(decision["ids"], np.asarray(decision["features"]))
        require(normal(wrapper.decisions[-1]) == decision, "candidate draw/persistence differs")


def rerun_job(payload):
    job, expected = payload
    actual = collect(job)
    for field, value in expected["episode"].items():
        if field != "seconds":
            require(normal(actual["episode"][field]) == value, "re-extracted " + field + " differs")
    require(actual["job"] == expected["job"], "re-extracted job differs")
    return {"mode": job["mode"], "decisions": len(actual["episode"]["decisions"])}


def audit(path, workers=4):
    path = Path(path).resolve()
    root = path.parent
    report = json.loads(path.read_text())
    require(report["status"] == "complete", "run incomplete")
    require(digest(root / "freeze.json") == report["freeze_sha256"], "freeze hash")
    freeze = json.loads((root / "freeze.json").read_text())
    require(freeze["source_sha256"] == pins() and freeze["config"] == CONFIG, "source/config drift")
    smoke = report["smoke"]
    require(freeze["smoke"] == smoke and freeze["training_seeds"] == list(TRAIN_SEEDS), "run identity")
    teacher_maps, val_maps = ((1,), (2,)) if smoke else (TEACHER, VALIDATE)
    train_maps, check_maps = ((1, 2), (1, 2)) if smoke else (TRAIN, CHECK)
    epochs, updates, batch = (2, 1, 4) if smoke else (200, 8, 16)
    for key, expected in (("teacher_maps", list(teacher_maps)), ("validation_maps", list(val_maps)),
                          ("train_maps", list(train_maps)), ("check_maps", list(check_maps)),
                          ("epochs", epochs), ("updates", updates), ("batch", batch)):
        require(freeze[key] == expected, "frozen " + key)
    require(set(report["training"]) == set(map(str, TRAIN_SEEDS)), "training initializations")
    teacher = [read_bundle(root, row) for row in report["teacher"]]
    require([b["job"]["seed"] for b in teacher] == sorted((*teacher_maps, *val_maps)), "teacher matrix")
    for row, bundle in zip(report["teacher"], teacher):
        require(evaluation_row(bundle, {k: row[k] for k in ("artifact", "sha256")}) == row, "teacher row")
        physics(bundle["episode"])
    examples = [d for b in teacher if b["job"]["seed"] in teacher_maps for d in b["episode"]["trajectory"]]
    validation = [d for b in teacher if b["job"]["seed"] in val_maps for d in b["episode"]["trajectory"]]
    states, train_cases, draws = {}, 0, 0
    for seed in TRAIN_SEEDS:
        entry = report["training"][str(seed)]
        for stage in STAGES:
            saved = entry[stage]
            require((root / saved["artifact"]).resolve().is_relative_to(root), "policy path")
            require(digest(root / saved["artifact"]) == saved["sha256"], "policy hash")
            states[(seed, stage)] = json.loads((root / saved["artifact"]).read_text())
            Policy.from_state(states[(seed, stage)])
        policy = Policy(seed)
        close(policy.state_dict(), states[(seed, "untrained")], "untrained")
        close(fit_metrics(policy, examples), entry["before_train"], "before train")
        close(fit_metrics(policy, validation), entry["before_validation"], "before validation")
        opt_state = imitate(policy, examples, seed, epochs)
        close(policy.state_dict(), states[(seed, "imitation")], "imitation")
        close(opt_state, entry["imitation_optimizer"], "imitation optimizer")
        close(fit_metrics(policy, examples), entry["after_train"], "after train")
        close(fit_metrics(policy, validation), entry["after_validation"], "after validation")
        passes = entry["after_train"]["cross_entropy"] <= .8 * entry["before_train"]["cross_entropy"]
        require(entry["imitation_passes"] == passes and (passes or smoke), "imitation prerequisite")
        rng, optimizer = np.random.default_rng(seed), Adam(policy)
        require(len(entry["updates"]) == updates, "missing RL update")
        for index, saved in enumerate(entry["updates"], 1):
            require(saved["update"] == index, "update sequence")
            bundles = read_bundle(root, saved)
            maps = rng.choice(train_maps, size=batch // 2, replace=False)
            expected = [(int(m), int(rng.integers(0, 2**63))) for m in maps for _ in range(2)]
            require([(b["episode"]["seed"], b["episode"]["policy_seed"]) for b in bundles] == expected, "training RNG/maps")
            for bundle in bundles:
                require(bundle["job"] == {"mode": "policy", "seed": bundle["episode"]["seed"],
                        "policy_seed": bundle["episode"]["policy_seed"], "train_seed": seed, "update": index}, "training job")
                physics(bundle["episode"])
                choices(bundle["episode"], policy)
                train_cases += 1
                draws += len(bundle["episode"]["decisions"])
            rows = [b["episode"] for b in bundles]
            gradient, advantages = batch_gradient(policy, rows, entropy=CONFIG["entropy"])
            close(advantages, saved["advantages"], "advantages")
            norm = optimizer.step(gradient, lr=CONFIG["rl_lr"], max_norm=CONFIG["max_norm"])
            close(norm, saved["gradient_norm"], "gradient norm")
            close(float(np.mean([r["reward"] for r in rows])), saved["mean_reward"], "training mean")
            checkpoint = root / saved["checkpoint"]
            require(checkpoint.resolve().is_relative_to(root) and digest(checkpoint) == saved["checkpoint_sha256"], "checkpoint hash/path")
            close({"policy": policy.state_dict(), "optimizer": optimizer.state_dict(), "rng_state": rng.bit_generator.state},
                  json.loads(checkpoint.read_text()), "RL checkpoint")
        close(policy.state_dict(), states[(seed, "rl")], "final policy")
        print(json.dumps({"audited_training_seed": seed, "RL_episodes_so_far": train_cases}), flush=True)
    require(digest(root / "evaluation-freeze.json") == report["evaluation_freeze_sha256"], "evaluation freeze hash")
    expected_freeze = {"source_sha256": pins(), "maps": list(check_maps), "policies": {
        str(seed): {s: report["training"][str(seed)][s] for s in STAGES} for seed in TRAIN_SEEDS}}
    require(json.loads((root / "evaluation-freeze.json").read_text()) == expected_freeze, "evaluation freeze")
    require(summarize(report["evaluation"], check_maps) == report["summary"], "summary")
    eval_jobs = {identity(job): job for job in evaluation_jobs(check_maps, states)}
    reruns = [(b["job"], b) for b in teacher]
    for row in report["evaluation"]:
        bundle = read_bundle(root, row)
        require(evaluation_row(bundle, {k: row[k] for k in ("artifact", "sha256")}) == row, "evaluation row")
        physics(bundle["episode"])
        job = eval_jobs[identity(bundle["job"])]
        if job["mode"] == "policy":
            choices(bundle["episode"], Policy.from_state(job["policy_state"]))
        reruns.append((job, bundle))
    with mp.get_context("spawn").Pool(workers) as pool:
        counts = list(pool.imap_unordered(rerun_job, reruns))
    require(pins() == freeze["source_sha256"], "source changed during audit")
    return {"schema": "rl-contextual-audit-v1", "report_sha256": digest(path), "smoke": smoke,
            "teacher_cases": len(teacher), "training_cases": train_cases, "training_draws": draws,
            "optimizer_updates_reconstructed": updates * len(TRAIN_SEEDS),
            "imitation_epochs_reconstructed": epochs * len(TRAIN_SEEDS),
            "evaluation_cases": len(report["evaluation"]), "scaffold_reexecutions": len(counts),
            "all_saved_physics_replayed": True, "all_evaluation_and_teacher_features_reextracted": True,
            "summary": report["summary"],
            "limits": "Training choices replay from recorded features; training feature extraction is source-pinned. Teacher/evaluation scaffolds re-executed, using the same model approximations. Small fixed pilot, not proof of general performance."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "preserve prior audit")
    result = audit(args.report)
    atomic_json(args.output, result)
    print(json.dumps({k: v for k, v in result.items() if k != "summary"}, indent=2))


if __name__ == "__main__":
    main()
