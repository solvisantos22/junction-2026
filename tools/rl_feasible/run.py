"""Run or fully audit the fixed charging-aware development comparison."""

import argparse
from collections import defaultdict
import gzip
import json
import math
import multiprocessing as mp
from pathlib import Path
import platform
import shutil
import subprocess
import time

import numpy as np

from lightlag_rl.adapter import greedy_choice
from lightlag_rl.model import Policy
from lightlag_rl.train import atomic_json, digest, source_pins as original_pins
from lightlag_rl_feasible.adapter import run_episode
from lightlag_rl_persistence import GoalChooser
from tools.rl_persistence.run import SEEDS, INPUT_HASHES, verify_inputs


ROOT = Path(__file__).resolve().parents[2]
TRAINING = ROOT / "docs/lightlag-rl-results/modal/pilot-01/training"
BASELINE = ROOT / "docs/lightlag-rl-persistence-results/development/report.json"
MODES = ("time_only", "charge_aware")
POLICIES = ("initial", "final", "greedy")
CONFIG = {"draws": {"initial": 2, "final": 2, "greedy": 1}, "horizon": 420,
          "action_rng_multiplier": 1000003, "bootstrap_draws": 10000, "bootstrap_seed": 17,
          "primary_policy": "final", "maximum_mean_score_loss": .01,
          "maximum_home_loss": 0, "maximum_death_increase": 0, "maximum_invalid_increase": 0}
IDENTITY = ("mode", "policy", "seed", "draw", "policy_seed")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def normal(value):
    return json.loads(json.dumps(value, allow_nan=False))


def pins():
    result = original_pins()
    files = [ROOT / "docs/lightlag-rl-feasible.md", ROOT / "docs/lightlag-rl-persistence.md"]
    for package in ("lightlag_rl_persistence", "lightlag_rl_feasible", "tools/rl_persistence",
                    "tools/rl_feasible", "tools/lightlag_rl"):
        files += list((ROOT / package).rglob("*.py"))
    result.update({str(p.relative_to(ROOT)): digest(p) for p in files})
    return dict(sorted(result.items()))


def jobs(seeds):
    return [{"mode": mode, "policy": policy, "seed": seed, "draw": draw,
             "policy_seed": CONFIG["action_rng_multiplier"] * seed + draw}
            for policy in POLICIES for mode in MODES for seed in seeds
            for draw in range(CONFIG["draws"][policy])]


def evaluate_job(payload):
    job, states = payload
    policy = Policy.from_state(states[job["policy"]]) if job["policy"] != "greedy" else None
    rng = np.random.default_rng(job["policy_seed"])
    def choose(ids, features):
        return policy.choose(features, rng) if policy else greedy_choice(ids, features)
    chooser = GoalChooser(choose, persistent=True)
    episode, checks = run_episode(job["seed"], chooser, job["mode"] == "charge_aware", keep_replay=True)
    return {"schema": "rl-feasible-case-v1", **job, "episode": episode,
            "decisions": chooser.decisions, "feasibility": checks}


def row_for(bundle, artifact, hashed):
    episode, decisions = bundle["episode"], bundle["decisions"]
    result = episode["result"]
    require(result["tick"] == CONFIG["horizon"] and len(decisions) == episode["decision_count"],
            "incomplete case")
    require(math.isfinite(episode["reward"]) and 0 <= episode["reward"] <= 1, "invalid reward")
    if bundle["mode"] == "charge_aware":
        require(len(bundle["feasibility"]) == len(decisions), "missing feasibility trace")
    else:
        require(not bundle["feasibility"], "control must not filter")
    return {**{k: bundle[k] for k in IDENTITY}, "artifact": artifact, "sha256": hashed,
            "reward": episode["reward"], "alive": result["alive"], "at_base": result["at_base"],
            "samples": len(result["samples"]), "invalid_calls": len(episode["invalid_calls"]),
            "decisions": len(decisions), "rejected_candidates": sum(
                len(r["original_ids"]) - len(r["offered_ids"]) for r in bundle["feasibility"])}


def summarize(rows, seeds):
    expected = {tuple(j[k] for k in IDENTITY) for j in jobs(seeds)}
    actual = [tuple(row[k] for k in IDENTITY) for row in rows]
    require(len(actual) == len(expected) and set(actual) == expected, "incomplete/duplicate matrix")
    arms, contrasts = {}, {}
    for policy in POLICIES:
        arms[policy] = {}
        for mode in MODES:
            subset = [r for r in rows if r["policy"] == policy and r["mode"] == mode]
            arms[policy][mode] = {"n": len(subset), "mean_reward": float(np.mean([r["reward"] for r in subset])),
                                  "alive_home": sum(r["alive"] and r["at_base"] for r in subset),
                                  "deaths": sum(not r["alive"] for r in subset),
                                  "invalid_calls": sum(r["invalid_calls"] for r in subset),
                                  "mean_samples": float(np.mean([r["samples"] for r in subset])),
                                  "rejected_candidates": sum(r["rejected_candidates"] for r in subset)}
        differences = [float(np.mean([r["reward"] for r in rows if r["policy"] == policy and r["mode"] == "charge_aware" and r["seed"] == seed]))
                       - float(np.mean([r["reward"] for r in rows if r["policy"] == policy and r["mode"] == "time_only" and r["seed"] == seed]))
                       for seed in seeds]
        samples = np.random.default_rng(CONFIG["bootstrap_seed"]).choice(
            differences, size=(CONFIG["bootstrap_draws"], len(seeds)), replace=True).mean(axis=1)
        contrasts[policy] = {"mean_paired_gain": float(np.mean(differences)),
                             "paired_map_differences": dict(zip(map(str, seeds), differences)),
                             "bootstrap_95": np.quantile(samples, [.025, .975]).tolist()}
    control, treatment = arms["final"]["time_only"], arms["final"]["charge_aware"]
    gate = {"score_within_01": contrasts["final"]["mean_paired_gain"] >= -.01,
            "home_not_lower": treatment["alive_home"] >= control["alive_home"],
            "deaths_not_higher": treatment["deaths"] <= control["deaths"],
            "invalid_not_higher": treatment["invalid_calls"] <= control["invalid_calls"]}
    return {"arms": arms, "contrasts": contrasts, "gate": gate, "screen_passes": all(gate.values())}


def unchanged_control(bundle):
    """The new runner's time-only arm must exactly reproduce Sölvi's saved arm."""
    report = json.loads(BASELINE.read_text())
    key = (bundle["policy"], bundle["seed"], bundle["draw"])
    found = [r for r in report["cases"] if r["mode"] == "persistent" and
             (r["policy"], r["seed"], r["draw"]) == key]
    require(len(found) == 1, "missing preceding control")
    row = found[0]
    artifact = BASELINE.parent / row["artifact"]
    require(digest(artifact) == row["sha256"], "preceding control changed")
    previous = json.loads(gzip.decompress(artifact.read_bytes()))
    for name in ("replay", "result", "reward", "decision_count", "public_calls", "calls_by_tool", "commands_by_action", "invalid_calls"):
        require(normal(bundle["episode"][name]) == previous["episode"][name], f"control differs: {name}")
    require(normal(bundle["decisions"]) == previous["decisions"], "control decisions differ")


def run(output, smoke=False, workers=4, max_seconds=1200):
    output = Path(output)
    require(not output.exists(), "output exists; preserve earlier attempt")
    require(type(workers) is int and 1 <= workers <= 4, "one to four workers required")
    require(0 < max_seconds <= 1200, "maximum 1200 local seconds")
    states, training_hashes = verify_inputs()
    sources = pins()
    seeds = (1, 2) if smoke else SEEDS
    output.mkdir(parents=True)
    (output / "cases").mkdir()
    for name in INPUT_HASHES:
        shutil.copyfile(TRAINING / name, output / name)
    freeze = {"schema": "rl-feasible-freeze-v1", "smoke": smoke, "seeds": list(seeds), "config": CONFIG,
              "source_sha256": sources, "training_sha256": training_hashes,
              "policy_sha256": INPUT_HASHES, "baseline_report_sha256": digest(BASELINE),
              "workers": workers, "max_seconds": max_seconds,
              "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=ROOT).strip(),
              "python": platform.python_version(), "numpy": np.__version__,
              "cloud_jobs": 0, "model_api_calls": 0, "training_updates": 0}
    atomic_json(output / "freeze.json", freeze)
    report = {"schema": "rl-feasible-comparison-v1", "status": "incomplete", "smoke": smoke,
              "freeze_sha256": digest(output / "freeze.json"), "cases": []}
    atomic_json(output / "report.json", report)
    started = time.monotonic()
    pool = mp.get_context("spawn").Pool(workers)
    failed = True
    try:
        iterator = pool.imap_unordered(evaluate_job, [(job, states) for job in jobs(seeds)])
        for _ in jobs(seeds):
            require(pins() == sources, "source changed during comparison")
            remaining = max_seconds - (time.monotonic() - started)
            if remaining <= 0:
                raise TimeoutError("comparison time limit")
            bundle = iterator.next(timeout=remaining)
            if bundle["mode"] == "time_only" and not smoke:
                unchanged_control(bundle)
            name = f"{bundle['policy']}-{bundle['mode']}-{bundle['seed']}-{bundle['draw']}.json.gz"
            path = output / "cases" / name
            require(not path.exists(), "duplicate case file")
            path.write_bytes(gzip.compress(json.dumps(bundle, allow_nan=False, separators=(",", ":")).encode(), mtime=0))
            report["cases"].append(row_for(bundle, str(path.relative_to(output)), digest(path)))
            report["cases"].sort(key=lambda row: tuple(row[k] for k in IDENTITY))
            atomic_json(output / "report.json", report)
            if len(report["cases"]) % 20 == 0:
                print(json.dumps({"cases": len(report["cases"]), "total": len(jobs(seeds))}), flush=True)
        require(pins() == sources, "source changed at completion")
        report["summary"] = summarize(report["cases"], seeds)
        report["status"] = "complete"
        failed = False
    except BaseException as error:
        report["failure"] = type(error).__name__ + ": " + str(error)[:500]
        raise
    finally:
        pool.terminate() if failed else pool.close()
        pool.join()
        report["elapsed_seconds"] = time.monotonic() - started
        atomic_json(output / "report.json", report)
    return report


def audit(path):
    from lightlag_traverse.environment import TraverseEnvironment
    path = Path(path).resolve()
    report = json.loads(path.read_text())
    require(report["status"] == "complete", "incomplete comparison")
    freeze_path = path.parent / "freeze.json"
    require(digest(freeze_path) == report["freeze_sha256"], "freeze hash")
    freeze = json.loads(freeze_path.read_text())
    require(freeze["source_sha256"] == pins() and freeze["config"] == CONFIG, "source/config drift")
    states, original = verify_inputs()
    require(freeze["training_sha256"] == original and freeze["policy_sha256"] == INPUT_HASHES, "training inputs")
    require(freeze["baseline_report_sha256"] == digest(BASELINE), "baseline report changed")
    seeds = (1, 2) if report["smoke"] else SEEDS
    require(freeze["seeds"] == list(seeds) and freeze["smoke"] is report["smoke"], "map identity")
    for name, hashed in INPUT_HASHES.items():
        require(digest(path.parent / name) == hashed, "policy input changed")
    totals = {"cases": 0, "decisions": 0, "rejected_candidates": 0}
    for row in report["cases"]:
        artifact = (path.parent / row["artifact"]).resolve()
        require(artifact.is_relative_to(path.parent) and digest(artifact) == row["sha256"], "case artifact hash")
        bundle = json.loads(gzip.decompress(artifact.read_bytes()))
        require(row_for(bundle, row["artifact"], row["sha256"]) == row, "case row mismatch")
        replay = bundle["episode"]["replay"]
        env = TraverseEnvironment(row["seed"])
        commands = defaultdict(list)
        for command in replay["commands"]:
            commands[command["sent_tick"]].append(command)
        for tick in range(CONFIG["horizon"]):
            for command in commands.pop(tick, []):
                require(normal(env.uplink([command["command"]])) == [command], "command replay")
            env.advance(1)
        require(not commands and normal(env.replay()) == replay, "physics replay")
        job = {k: bundle[k] for k in IDENTITY}
        rerun = evaluate_job((job, states))
        for field in ("decisions", "feasibility"):
            require(normal(rerun[field]) == bundle[field], f"scaffold re-extraction mismatch: {field}")
        for field in ("replay", "result", "reward", "decision_count", "public_calls", "calls_by_tool", "commands_by_action", "invalid_calls"):
            require(normal(rerun["episode"][field]) == bundle["episode"][field], f"scaffold command mismatch: {field}")
        if row["mode"] == "time_only" and not report["smoke"]:
            unchanged_control(bundle)
        totals["cases"] += 1
        totals["decisions"] += len(bundle["decisions"])
        totals["rejected_candidates"] += row["rejected_candidates"]
    require(summarize(report["cases"], seeds) == report["summary"], "summary mismatch")
    return {"schema": "rl-feasible-audit-v1", "report_sha256": digest(path), "smoke": report["smoke"],
            **totals, "full_physics_replays": True, "scaffold_features_choices_commands_reexecuted": True,
            "control_matches_frozen_persistence": not report["smoke"], "summary": report["summary"],
            "limit": "Uses the same source-pinned feasibility model and navigator to re-extract features; model accuracy is not proved. Reused maps."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--audit", type=Path)
    args = parser.parse_args()
    if args.audit:
        result = audit(args.audit)
        if args.output:
            require(not args.output.exists(), "audit output exists")
            atomic_json(args.output, result)
        print(json.dumps({k: v for k, v in result.items() if k != "summary"}, indent=2))
    else:
        if args.output is None:
            parser.error("--output required")
        result = run(args.output, args.smoke, args.workers)
        print(json.dumps(result["summary"], indent=2))


if __name__ == "__main__":
    main()
