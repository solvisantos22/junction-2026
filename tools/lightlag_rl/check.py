"""Frozen before/after comparison and replay audit; no training or model APIs."""

import argparse
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
import gzip
import json
import multiprocessing as mp
from pathlib import Path
import shutil
import time

import numpy as np

from lightlag_rl.adapter import greedy_choice, home_choice, run_episode
from lightlag_rl.model import Policy
from lightlag_rl.train import TRAIN_SEEDS, atomic_json, digest, source_pins, verify_pins

CHECK_SEEDS = tuple(range(72000, 72040))
POLICIES = ("initial", "final", "greedy", "home")
EVALUATION = {"bootstrap_draws": 10000, "bootstrap_seed": 17,
              "minimum_mean_gain": .03, "maximum_home_count_loss": 2,
              "bootstrap_unit": "map: average two action draws before resampling"}


def normal(value):
    return json.loads(json.dumps(value, allow_nan=False))


def training_inputs(directory, smoke=False):
    directory = Path(directory)
    report = json.loads((directory / "training.json").read_text())
    config = report["config"]
    if (report.get("schema") != "lightlag-rl-training-v1" or report["status"] != "complete"
            or config["smoke"] is not smoke or report["model_api_calls"] != 0
            or report["fresh_cases"] != 0 or config["train_seed"] != 17
            or config["rollouts_per_map"] != 2):
        raise ValueError("a matching completed frozen training run is required")
    if smoke:
        if config["training_seeds"] != [1, 2] or not 1 <= config["updates"] <= 2 or config["batch_size"] not in (2, 4):
            raise ValueError("smoke comparison requires used-seed smoke training")
    elif (config["updates"], config["batch_size"], config["training_seeds"]) != (16, 32, list(TRAIN_SEEDS)):
        raise ValueError("fresh comparison requires the declared 16 by 32 training run")
    if (report["updates_completed"] != config["updates"]
            or report["episodes_completed"] != config["updates"] * config["batch_size"]
            or len(report["metrics"]) != config["updates"]):
        raise ValueError("training update/episode totals are incomplete")
    verify_pins(report["source_sha256"])
    if any(config.get(k) != v for k, v in {"learning_rate": .02, "entropy_coefficient": .01,
                                          "gradient_norm_limit": 5}.items()):
        raise ValueError("training hyperparameters differ from the declared protocol")
    for name in ("initial", "final"):
        path = directory / f"{name}-policy.json"
        if digest(path) != report[f"{name}_policy_sha256"]:
            raise ValueError("policy hash does not match completed training")
        if Policy.from_state(json.loads(path.read_text())).W.shape != (14, 16):
            raise ValueError("policy architecture changed")
    checkpoint_name = report["latest_checkpoint"]
    if Path(checkpoint_name).name != checkpoint_name:
        raise ValueError("checkpoint must be a local filename")
    checkpoint = directory / checkpoint_name
    if digest(checkpoint) != report["latest_checkpoint_sha256"]:
        raise ValueError("training checkpoint hash mismatch")
    state = json.loads(checkpoint.read_text())
    if (state["updates_completed"] != config["updates"] or state["config"] != config
            or state["source_sha256"] != report["source_sha256"]
            or state["policy"] != json.loads((directory / "final-policy.json").read_text())):
        raise ValueError("final checkpoint differs from final policy or protocol")
    return report


def jobs(seeds, states):
    return [{"policy": name, "seed": seed, "draw": draw,
             "policy_seed": 1000003 * seed + draw,
             "state": states.get(name)}
            for name in POLICIES for seed in seeds
            for draw in (range(2) if name in ("initial", "final") else range(1))]


def evaluate_job(job):
    if job["policy"] == "home":
        # This is the declared do-nothing control, not noisy-pose recentering.
        from lightlag_traverse.environment import TraverseEnvironment
        started = time.monotonic()
        env, calls = TraverseEnvironment(job["seed"]), 0
        while True:
            calls += 1
            if env.advance(5)["episode_complete"]:
                break
        result = env.evaluate()
        episode = {"seed": job["seed"], "result": result,
                   "reward": result["raw_score"] / result["max_available_value"],
                   "decision_count": 0, "public_calls": calls, "calls_by_tool": {"advance": calls},
                   "commands_by_action": {}, "invalid_calls": [],
                   "seconds": time.monotonic() - started, "replay": env.replay()}
        return {**{k: job[k] for k in ("policy", "seed", "draw", "policy_seed")},
                "episode": episode, "decisions": []}
    policy = Policy.from_state(job["state"]) if job["state"] is not None else None
    rng = np.random.default_rng(job["policy_seed"])
    decisions = []

    def choose(ids, features):
        action = (policy.choose(features, rng) if policy is not None else
                  greedy_choice(ids, features) if job["policy"] == "greedy" else home_choice(ids, features))
        decisions.append({"ids": list(ids), "features": features.tolist(), "action": int(action)})
        return action

    episode = run_episode(job["seed"], choose, keep_replay=True)
    return {**{k: job[k] for k in ("policy", "seed", "draw", "policy_seed")},
            "episode": episode, "decisions": decisions}


def row_for(bundle, artifact, hashed):
    episode, result = bundle["episode"], bundle["episode"]["result"]
    return {**{k: bundle[k] for k in ("policy", "seed", "draw", "policy_seed")},
            "artifact": artifact, "sha256": hashed, "reward": episode["reward"],
            "alive": result["alive"], "at_base": result["at_base"],
            "invalid_calls": len(episode["invalid_calls"])}


def summarize(rows, seeds):
    summary = {}
    for name in POLICIES:
        subset = [r for r in rows if r["policy"] == name]
        summary[name] = {"n": len(subset), "mean_reward": float(np.mean([r["reward"] for r in subset])),
                         "alive_home": sum(r["alive"] and r["at_base"] for r in subset),
                         "deaths": sum(not r["alive"] for r in subset),
                         "invalid_calls": sum(r["invalid_calls"] for r in subset)}
    differences = [float(np.mean([r["reward"] for r in rows if r["policy"] == "final" and r["seed"] == seed])
                         - np.mean([r["reward"] for r in rows if r["policy"] == "initial" and r["seed"] == seed]))
                   for seed in seeds]
    mean = float(np.mean(differences))
    bootstrap = np.random.default_rng(17).choice(differences, size=(10000, len(seeds)), replace=True).mean(axis=1)
    interval = np.quantile(bootstrap, [.025, .975]).tolist()
    gate = {"gain_at_least_03": mean >= .03, "bootstrap_lower_positive": interval[0] > 0,
            "home_no_more_than_two_lower": summary["final"]["alive_home"] >= summary["initial"]["alive_home"] - 2}
    return {"policies": summary, "paired_map_differences": dict(zip(map(str, seeds), differences)),
            "mean_paired_gain": mean, "bootstrap_95_percentile": interval,
            "bootstrap_draws": 10000, "bootstrap_seed": 17, "gate": gate, "screen_passes": all(gate.values())}


def run(training, output, workers=4, smoke=False, *, evaluator=evaluate_job):
    if type(workers) is not int or not 1 <= workers <= 4:
        raise ValueError("workers must be an integer in 1..4")
    training, output = Path(training), Path(output)
    trained = training_inputs(training, smoke)  # before constructing any case
    seeds = (1, 2) if smoke else CHECK_SEEDS
    output.mkdir(parents=True, exist_ok=False)
    (output / "cases").mkdir()
    names = ("training.json", "initial-policy.json", "final-policy.json", trained["latest_checkpoint"])
    for name in names:
        shutil.copyfile(training / name, output / name)
    training_inputs(output, smoke)
    freeze = {"schema": "lightlag-rl-check-freeze-v1", "smoke": smoke, "seeds": list(seeds),
              "source_sha256": trained["source_sha256"],
              "evaluator_sha256": digest(Path(__file__)),
              "evaluation": EVALUATION, "workers": workers,
              "artifacts": {name: digest(output / name) for name in names},
              "action_rng": "1000003 * map_seed + draw; shared by initial and final",
              "home_control": "do nothing: advance to horizon, zero uplinks and decisions",
              "policy_draws": {"initial": 2, "final": 2, "greedy": 1, "home": 1}, "model_api_calls": 0}
    atomic_json(output / "freeze.json", freeze)  # immutable weights before first environment
    report = {"schema": "lightlag-rl-check-v1", "complete": False, "smoke": smoke,
              "freeze_sha256": digest(output / "freeze.json"), "cases": []}
    atomic_json(output / "report.json", report)
    states = {name: json.loads((output / f"{name}-policy.json").read_text()) for name in ("initial", "final")}
    work = jobs(seeds, states)

    def save(bundle):
        artifact = "cases/{}-{}-{}.json.gz".format(bundle["policy"], bundle["seed"], bundle["draw"])
        path = output / artifact
        path.write_bytes(gzip.compress(json.dumps(bundle, allow_nan=False, separators=(",", ":")).encode(), mtime=0))
        report["cases"].append(row_for(bundle, artifact, digest(path)))
        atomic_json(output / "report.json", report)

    if workers == 1 or evaluator is not evaluate_job:
        for job in work:
            save(evaluator(job))
    else:
        with ProcessPoolExecutor(max_workers=workers, mp_context=mp.get_context("spawn")) as pool:
            for bundle in pool.map(evaluator, work):
                save(bundle)
    verify_pins(freeze["source_sha256"])
    if (digest(Path(__file__)) != freeze["evaluator_sha256"] or digest(output / "freeze.json") != report["freeze_sha256"]
            or any(digest(output / n) != h for n, h in freeze["artifacts"].items())):
        raise RuntimeError("frozen inputs changed during comparison")
    report["summary"] = summarize(report["cases"], seeds)
    report["complete"] = True
    atomic_json(output / "report.json", report)
    return report


def audit(path):
    """Reconstruct physics from all accepted commands; verify retained policy choices."""
    from lightlag_traverse.environment import TraverseEnvironment

    if not __debug__:
        raise RuntimeError("run the assertion-based auditor without Python -O")
    path = Path(path).resolve()
    report = json.loads(path.read_text())
    assert report["schema"] == "lightlag-rl-check-v1" and report["complete"] is True
    freeze_path = path.parent / "freeze.json"
    assert digest(freeze_path) == report["freeze_sha256"]
    freeze = json.loads(freeze_path.read_text())
    assert freeze["schema"] == "lightlag-rl-check-freeze-v1" and freeze["smoke"] is report["smoke"]
    assert freeze["evaluator_sha256"] == digest(Path(__file__))
    assert freeze["evaluation"] == EVALUATION and 1 <= freeze["workers"] <= 4
    assert freeze["policy_draws"] == {"initial": 2, "final": 2, "greedy": 1, "home": 1}
    seeds = (1, 2) if report["smoke"] else CHECK_SEEDS
    assert freeze["seeds"] == list(seeds) and freeze["model_api_calls"] == 0
    trained = training_inputs(path.parent, report["smoke"])
    assert trained["source_sha256"] == freeze["source_sha256"]
    for name, hashed in freeze["artifacts"].items():
        assert Path(name).name == name and digest(path.parent / name) == hashed
    states = {n: json.loads((path.parent / f"{n}-policy.json").read_text()) for n in ("initial", "final")}
    expected = {(j["policy"], j["seed"], j["draw"], j["policy_seed"]) for j in jobs(seeds, states)}
    identities = [(r["policy"], r["seed"], r["draw"], r["policy_seed"]) for r in report["cases"]]
    assert len(identities) == len(expected) and set(identities) == expected
    verified, decisions, seen = [], 0, set()
    for row in report["cases"]:
        artifact = (path.parent / row["artifact"]).resolve()
        assert artifact.is_relative_to(path.parent) and artifact not in seen and digest(artifact) == row["sha256"]
        seen.add(artifact)
        bundle = json.loads(gzip.decompress(artifact.read_bytes()))
        assert row_for(bundle, row["artifact"], row["sha256"]) == row
        episode, replay = bundle["episode"], bundle["episode"]["replay"]
        assert episode["seed"] == replay["seed"] == row["seed"]
        env = TraverseEnvironment(row["seed"])
        by_tick = defaultdict(list)
        for command in replay["commands"]:
            by_tick[command["sent_tick"]].append(command)
        for tick in range(420):
            for command in by_tick.pop(tick, []):
                assert normal(env.uplink([command["command"]])) == [command]
            env.advance(1)
        assert not by_tick
        if row["policy"] == "home":
            assert replay["commands"] == [] and bundle["decisions"] == []
        assert normal(env.replay()) == replay and normal(env.evaluate()) == episode["result"]
        assert episode["result"]["tick"] == 420 and episode["reward"] == episode["result"]["raw_score"] / episode["result"]["max_available_value"]
        policy = Policy.from_state(states[row["policy"]]) if row["policy"] in states else None
        rng = np.random.default_rng(row["policy_seed"])
        for decision in bundle["decisions"]:
            features = np.asarray(decision["features"], dtype=float)
            ids = decision["ids"]
            assert features.shape == (len(ids), 14) and len(ids) and ids[0] == "base" and np.isfinite(features).all()
            chosen = (policy.choose(features, rng) if policy is not None else
                      greedy_choice(ids, features) if row["policy"] == "greedy" else home_choice(ids, features))
            assert chosen == decision["action"]
        assert episode["decision_count"] == len(bundle["decisions"])
        decisions += len(bundle["decisions"])
        verified.append(row)
    assert summarize(verified, seeds) == report["summary"]
    return {"report_sha256": digest(path), "smoke": report["smoke"], "cases_verified": len(verified),
            "full_replays_match": True, "decisions_verified": decisions, "summary": report["summary"],
            "limit": "Physics, grades and sampled actions from retained features verified; feature extraction is source-pinned but not independently rerun."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--training", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--audit-output", type=Path)
    args = parser.parse_args()
    if args.audit:
        value = audit(args.audit)
        if args.audit_output:
            atomic_json(args.audit_output, value)
    else:
        if not args.training or not args.output:
            parser.error("--training and --output are required")
        value = run(args.training, args.output, args.workers, args.smoke)["summary"]
    print(json.dumps(value, indent=2))


if __name__ == "__main__":
    main()
