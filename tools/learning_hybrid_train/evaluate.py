"""Freeze all six completed runs before the single matched fresh evaluation."""

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
import json
import multiprocessing
from pathlib import Path
import platform
import re
import time

import numpy as np
import torch

from lightlag_hybrid_train.learner import Learner, chooser_from_state
from lightlag_hybrid_train.train import (
    BATCH, EXPERIMENT, FINAL_MAPS, MILESTONES, VALIDATION_MAPS, atomic_json,
    assert_source, digest, read_json, source_manifest, state_hash, summarize as episode_summary,
    worker_init,
)
from lightlag_learning.environment import greedy_choice, run_episode
from lightlag_traverse.environment import TraverseEnvironment
from lightlag_traverse.pilot import fly


SEEDS = (17, 29, 43)
VARIANTS = ("prior", "plain")
BOOTSTRAP_DRAWS, BOOTSTRAP_SEED = 20000, 629128
FREEZE_SCHEMA = "hybrid-ppo-final-freeze-v1"
CASE_SCHEMA = "hybrid-ppo-final-case-v1"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def runtime():
    # Declare the portable runtime; retain the actual Python patch in cases.
    return {"python": ".".join(platform.python_version_tuple()[:2]),
            "numpy": np.__version__, "torch": torch.__version__.split("+")[0]}


def write_new(path, value):
    path = Path(path)
    if path.exists():
        raise FileExistsError(path)
    atomic_json(path, value)


def initial_equivalence(policies):
    """Prove deduplication for every public observation, not selected maps.

Zero final actor weights and bias imply equal residual logits for every legal
action. The prior therefore argmaxes exact greedy; plain argmaxes base index0.
    Match initialization within each downloaded prior/plain pair. Provenance is
    bound by report/source hashes; a local cross-platform RNG replay is neither
    required nor claimed as part of the behavioral deduplication proof.
"""
    for variant in VARIANTS:
        for seed in SEEDS:
            key = f"{variant}-{seed}-00000"
            state = policies[key]
            chooser_from_state(state, np.random.default_rng(seed))
            require(state["algorithm"] == variant and state["episodes_seen"] == 0
                    and state["config"]["schedule_episodes"] == 4096, "initial policy identity changed")
            weights = state["model"]["residual"]["weights"]
            require(np.all(np.asarray(weights["score.2.weight"]) == 0)
                    and np.all(np.asarray(weights["score.2.bias"]) == 0), "initial actor head is not zero")
    for seed in SEEDS:
        require(policies[f"prior-{seed}-00000"]["model"]["residual"]
                == policies[f"plain-{seed}-00000"]["model"]["residual"],
                "matched prior/plain initial residual weights differ")
    return {"prior_initial": "greedy", "plain_initial": "plain-17-00000",
            "proof": "All six initial states have validated finite models and zero actor heads; downloaded prior/plain residual weights match within each seed. Prior argmax is greedy, plain argmax is legal base index0. No cross-platform initialization replay is claimed."}


def read_completed_run(directory, pins):
    root = Path(directory)
    report = read_json(root / "report.json")
    require(report.get("schema") == "hybrid-ppo-training-report-v1"
            and report.get("experiment") == EXPERIMENT and report.get("status") == "complete"
            and report.get("smoke") is False and report.get("episodes_completed") == 4096
            and report.get("episodes_target") == 4096 and report.get("phase") == "finished",
            "all six production runs must complete4096 before final freeze")
    variant, seed = report["variant"], report["seed"]
    require(variant in VARIANTS and seed in SEEDS and report["algorithm"] == variant
            and report["source_sha256"] == pins and report["batch_episodes"] == BATCH
            and report["schedule_episodes"] == 4096, "training identity/source changed")
    require(".".join(report["python"].split(".")[:2]) == runtime()["python"]
            and report["numpy"] == runtime()["numpy"]
            and report["torch"].split("+")[0] == runtime()["torch"], "training runtime changed")
    require(set(report["validations"]) == set(map(str, MILESTONES))
            and set(report["checkpoints"]) == set(map(str, MILESTONES)),
            "required training milestones incomplete")
    artifacts, policies = {}, {}
    history = report["history"]
    require(len(history) == 4096 // BATCH, "training history incomplete")
    for index, row in enumerate(history):
        expected_name = f"batches/batch-{index:05d}.json.gz"
        require(row["first_episode"] == index * BATCH
                and row["last_episode"] == (index + 1) * BATCH
                and row["artifact"] == expected_name
                and isinstance(row["sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", row["sha256"]),
                "training batch history/hash record changed")
        artifacts[expected_name] = row["sha256"]
    for count in MILESTONES:
        names = {"policy_sha256": f"policy-{count:05d}.json",
                 "checkpoint_sha256": f"checkpoint-{count:05d}.json.gz",
                 "validation_sha256": f"validation-{count:05d}.json.gz"}
        hashes = report["checkpoints"][str(count)]
        for key, name in names.items():
            require(digest(root / name) == hashes[key], "milestone artifact hash changed")
            artifacts[name] = hashes[key]
        policy = read_json(root / names["policy_sha256"])
        chooser_from_state(policy, np.random.default_rng(seed))  # validates model, no world
        require(policy["algorithm"] == variant and policy["episodes_seen"] == count,
                "milestone policy identity changed")
        checkpoint = read_json(root / names["checkpoint_sha256"])
        identity = checkpoint["identity"]
        require(checkpoint["schema"] == "hybrid-ppo-checkpoint-v1"
                and checkpoint["episodes_completed"] == count
                and identity["source_sha256"] == pins and identity["variant"] == variant
                and identity["seed"] == seed and identity["smoke"] is False,
                "milestone checkpoint identity changed")
        restored = Learner.from_state(checkpoint["learner"])
        require(restored.inference_state() == policy
                and checkpoint["history"] == history[:count // BATCH],
                "milestone weights/history differ from checkpoint")
        validation = read_json(root / names["validation_sha256"])
        episodes = validation["episodes"]
        require(validation["schema"] == "hybrid-ppo-validation-v1"
                and validation["experiment"] == EXPERIMENT and validation["variant"] == variant
                and validation["seed"] == seed and validation["episodes_completed"] == count
                and validation["policy_sha256"] == hashes["policy_sha256"]
                and validation["maps"] == list(VALIDATION_MAPS)
                and [e["seed"] for e in episodes] == list(VALIDATION_MAPS),
                "validation identity/maps changed")
        require(all(e["result"]["tick"] == 420 and np.isfinite(e["reward"]) and 0 <= e["reward"] <= 1
                    and e["reward"] == e["result"]["raw_score"] / e["result"]["max_available_value"]
                    for e in episodes), "validation official reward/horizon changed")
        require(validation["summary"] == episode_summary(episodes) == report["validations"][str(count)],
                "validation summary changed")
        if count in (0, 4096):
            policies[f"{variant}-{seed}-{count:05d}"] = policy
    record = {"variant": variant, "seed": seed, "report_sha256": digest(root / "report.json"),
              "artifacts": artifacts,
              "batch_verification": "128 contiguous report/checkpoint history entries and recorded SHA256 values bound; batch archive bytes remain on Modal and are not reconstructed here.",
              "training_runtime": {key: report[key] for key in ("python", "numpy", "torch")}}
    return record, policies


def freeze_runs(run_dirs, output):
    require(len(run_dirs) == 6, "exactly six completed run directories required")
    require(not Path(output).exists(), "freeze output already exists")
    pins = source_manifest()
    records, policies = [], {}
    for directory in run_dirs:
        record, retained = read_completed_run(directory, pins)
        require(not set(policies).intersection(retained), "duplicate training run")
        records.append(record)
        policies.update(retained)
    require({(r["variant"], r["seed"]) for r in records}
            == {(v, s) for v in VARIANTS for s in SEEDS}, "missing training seed/variant")
    dedup = initial_equivalence(policies)
    arms = [{"id": f"{variant}-{seed}-04096", "kind": "policy", "variant": variant,
             "training_seed": seed, "episodes": 4096, "policy_id": f"{variant}-{seed}-04096"}
            for variant in VARIANTS for seed in SEEDS]
    arms += [{"id": "greedy", "kind": "greedy"}, {"id": "beam", "kind": "beam"},
             {"id": "plain-initial", "kind": "policy", "variant": "plain",
              "training_seed": 17, "episodes": 0, "policy_id": "plain-17-00000"}]
    manifest = {"schema": FREEZE_SCHEMA, "experiment": EXPERIMENT, "smoke": False,
                "maps": list(FINAL_MAPS), "source_sha256": pins, "runtime": runtime(),
                "policies": policies, "policy_sha256": {k: state_hash(v) for k, v in policies.items()},
                "runs": sorted(records, key=lambda r: (r["variant"], r["seed"])), "arms": arms,
                "job_matrix": [{"arm": arm["id"], "seed": seed} for arm in arms for seed in FINAL_MAPS],
                "initial_deduplication": dedup, "explore": False,
                "bootstrap_draws": BOOTSTRAP_DRAWS, "bootstrap_seed": BOOTSTRAP_SEED,
                "selection": "All six fixed4096 policies; no checkpoint or seed selection.",
                "training_audit_limit": "Milestone policy/checkpoint/validation bytes and summaries checked; training batch hashes are report-bound records, not independently downloaded or reconstructed training.",
                "created_unix": time.time()}
    verify_manifest(manifest)
    write_new(output, manifest)
    return manifest


def verify_manifest(manifest):
    require(manifest["schema"] == FREEZE_SCHEMA and manifest["experiment"] == EXPERIMENT
            and manifest["smoke"] is False and manifest["maps"] == list(FINAL_MAPS)
            and manifest["runtime"] == runtime() and manifest["explore"] is False
            and manifest["bootstrap_draws"] == BOOTSTRAP_DRAWS
            and manifest["bootstrap_seed"] == BOOTSTRAP_SEED, "frozen evaluation configuration changed")
    assert_source(manifest["source_sha256"])
    expected = {f"{v}-{s}-{n:05d}" for v in VARIANTS for s in SEEDS for n in (0, 4096)}
    require(set(manifest["policies"]) == expected == set(manifest["policy_sha256"]),
            "frozen policy set changed")
    for key, policy in manifest["policies"].items():
        require(state_hash(policy) == manifest["policy_sha256"][key], "frozen policy hash changed")
        chooser_from_state(policy, np.random.default_rng(17))
        variant, _, count = key.split("-")
        require(policy["algorithm"] == variant and policy["episodes_seen"] == int(count),
                "frozen policy identity changed")
    require(manifest["initial_deduplication"] == initial_equivalence(manifest["policies"]),
            "initial deduplication proof changed")
    require(len(manifest["runs"]) == 6 and {(r["variant"], r["seed"]) for r in manifest["runs"]}
            == {(v, s) for v in VARIANTS for s in SEEDS}, "frozen training identities changed")
    expected_arms = {f"{v}-{s}-04096" for v in VARIANTS for s in SEEDS} | {"greedy", "beam", "plain-initial"}
    require(len(manifest["arms"]) == 9 and {a["id"] for a in manifest["arms"]} == expected_arms,
            "frozen evaluation arms changed")
    require(manifest["job_matrix"] == [{"arm": arm["id"], "seed": seed}
                                        for arm in manifest["arms"] for seed in FINAL_MAPS],
            "frozen job matrix changed")
    for arm in manifest["arms"]:
        if arm["id"] in ("greedy", "beam"):
            require(arm == {"id": arm["id"], "kind": arm["id"]}, "control changed")
        else:
            key = "plain-17-00000" if arm["id"] == "plain-initial" else arm["id"]
            variant, seed, count = key.split("-")
            require(arm == {"id": arm["id"], "kind": "policy", "variant": variant,
                            "training_seed": int(seed), "episodes": int(count), "policy_id": key},
                    "policy arm identity changed")


def jobs(manifest):
    return [{"arm": {**arm, **({"policy": manifest["policies"][arm["policy_id"]],
                                "policy_sha256": manifest["policy_sha256"][arm["policy_id"]]}
                               if arm["kind"] == "policy" else {})},
             "seed": seed, "source_sha256": manifest["source_sha256"],
             "runtime": manifest["runtime"], "smoke": False}
            for arm in manifest["arms"] for seed in manifest["maps"]]


def validate_job(job):
    assert_source(job["source_sha256"])
    require(job["runtime"] == runtime() and type(job["smoke"]) is bool
            and type(job["seed"]) is int
            and job["seed"] in ((1, 2) if job["smoke"] else FINAL_MAPS), "invalid evaluation job")
    arm = job["arm"]
    require(arm["kind"] in ("policy", "greedy", "beam"), "invalid arm kind")
    if arm["kind"] == "policy":
        require(state_hash(arm["policy"]) == arm["policy_sha256"], "job policy hash changed")
        chooser_from_state(arm["policy"], np.random.default_rng(job["seed"]))


def evaluate_job(job):
    """Standalone CPU rollout; validate sources and weights before a world exists."""
    validate_job(job)
    arm, seed = job["arm"], job["seed"]
    if arm["kind"] == "beam":
        env, calls, sent, invalid = TraverseEnvironment(seed), Counter(), Counter(), []

        class CounterTools:
            def __getattr__(self, name):
                if name not in ("rules", "map", "telemetry_log", "uplink", "advance"):
                    raise AttributeError(name)
                def call(*args):
                    calls[name] += 1
                    try:
                        result = getattr(env, name)(*args)
                    except ValueError as error:
                        invalid.append({"tool": name, "error": str(error)})
                        raise
                    if name == "uplink":
                        sent.update(a["command"]["action"] for a in result)
                    return result
                return call

        started = time.monotonic()
        fly(CounterTools())
        result = env.evaluate()
        episode = {"seed": seed, "result": result, "reward": result["raw_score"] / result["max_available_value"],
                   "replay": env.replay(), "invalid_calls": invalid, "public_calls": sum(calls.values()),
                   "calls_by_tool": dict(calls), "commands_by_action": dict(sent),
                   "seconds": time.monotonic() - started}
    else:
        choose = greedy_choice if arm["kind"] == "greedy" else chooser_from_state(
            arm["policy"], np.random.default_rng(seed), explore=False)
        episode = run_episode(seed, choose, keep_replay=True)
    bundle = {"schema": CASE_SCHEMA, "experiment": EXPERIMENT, "status": "complete",
              "arm": arm["id"], "seed": seed, "smoke": job["smoke"],
              "job_sha256": state_hash(job), "source_sha256": job["source_sha256"],
              "policy_sha256": arm.get("policy_sha256"), "runtime": runtime(),
              "python_patch": platform.python_version(), "episode": episode}
    return json.loads(json.dumps(bundle, allow_nan=False))


def audit_case(bundle, job):
    validate_job(job)
    require(bundle["schema"] == CASE_SCHEMA and bundle["status"] == "complete"
            and bundle["experiment"] == EXPERIMENT and bundle["job_sha256"] == state_hash(job)
            and bundle["arm"] == job["arm"]["id"] and bundle["seed"] == job["seed"]
            and bundle["source_sha256"] == job["source_sha256"] and bundle["runtime"] == runtime()
            and bundle["policy_sha256"] == job["arm"].get("policy_sha256")
            and bundle["smoke"] == job["smoke"], "case provenance changed")
    episode, seed = bundle["episode"], bundle["seed"]
    replay = episode["replay"]
    require(episode["seed"] == replay["seed"] == seed, "case seed changed")
    env, sent = TraverseEnvironment(seed), defaultdict(list)
    for command in replay["commands"]:
        sent[command["sent_tick"]].append(command)
    for tick in range(420):
        for command in sent.pop(tick, []):
            require(json.loads(json.dumps(env.uplink([command["command"]]))) == [command],
                    "physics command acknowledgement changed")
        env.advance(1)
    require(not sent and json.loads(json.dumps(env.replay())) == replay
            and json.loads(json.dumps(env.evaluate())) == episode["result"], "physics/grade changed")
    result = episode["result"]
    require(result["tick"] == 420 and episode["reward"] == result["raw_score"] / result["max_available_value"],
            "official horizon/reward changed")
    require(episode["invalid_calls"] == [] and episode["calls_by_tool"]["advance"] == 420
            and episode["public_calls"] == sum(episode["calls_by_tool"].values())
            and episode["commands_by_action"] == dict(Counter(c["command"]["action"] for c in replay["commands"])),
            "public call accounting changed")
    if job["arm"]["kind"] != "beam":
        choose = greedy_choice if job["arm"]["kind"] == "greedy" else chooser_from_state(
            job["arm"]["policy"], np.random.default_rng(seed), explore=False)
        transitions = episode["transitions"]
        require(transitions and len(transitions) == episode["decision_count"]
                and transitions[0]["obs"]["tick"] == 0
                and transitions[-1]["next_obs"]["tick"] == 420, "transition horizon changed")
        for index, transition in enumerate(transitions):
            obs, nxt, action = transition["obs"], transition["next_obs"], transition["action"]
            last = index == len(transitions) - 1
            require(type(action) is int and 0 <= action < len(obs["ids"])
                    and obs["mask"][action] and choose(obs) == action, "effective policy choice changed")
            require(type(transition["elapsed_ticks"]) is int and transition["elapsed_ticks"] > 0
                    and transition["elapsed_ticks"] == nxt["tick"] - obs["tick"]
                    and transition["done"] is last
                    and transition["reward"] == (episode["reward"] if last else 0)
                    and (last or nxt == transitions[index + 1]["obs"]), "transition linkage/reward changed")
    repeated = evaluate_job(job)
    strip = lambda e: {k: v for k, v in e.items() if k != "seconds"}
    require(strip(repeated["episode"]) == strip(episode), "full controller observations/commands changed")
    return {"case_sha256": state_hash(bundle), "physics_verified": True,
            "effective_choices_verified": job["arm"]["kind"] != "beam", "full_controller_replay": True}


def verified_job(job):
    bundle = None
    try:
        bundle = evaluate_job(job)
        return {"status": "complete", "bundle": bundle, "audit": audit_case(bundle, job)}
    except Exception as error:
        return {"status": "failed", "bundle": bundle, "audit": None,
                "arm": job["arm"]["id"], "seed": job["seed"],
                "error": {"type": type(error).__name__, "message": str(error)[:1000]}}


def contrast(values):
    values = np.asarray(values, dtype=float)
    indices = np.random.default_rng(BOOTSTRAP_SEED).integers(0, len(values), (BOOTSTRAP_DRAWS, len(values)))
    return {"mean": float(values.mean()),
            "bootstrap_95_percentile": np.quantile(values[indices].mean(1), [.025, .975]).tolist()}


def summarize(rows, manifest):
    expected = {(a["id"], s) for a in manifest["arms"] for s in manifest["maps"]}
    require(len(rows) == len(expected) and {(r["arm"], r["seed"]) for r in rows} == expected,
            "missing/duplicate evaluation case")
    require(all(r["status"] == "complete" and np.isfinite(r["reward"])
                and 0 <= r["reward"] <= 1 and type(r["home"]) is bool and type(r["alive"]) is bool
                and type(r["invalid_calls"]) is int and r["invalid_calls"] >= 0 for r in rows),
            "incomplete or invalid case summary")
    table = {(r["arm"], r["seed"]): r for r in rows}
    groups = {a["id"]: [a["id"]] for a in manifest["arms"]}
    groups.update({v: [f"{v}-{s}-04096" for s in SEEDS] for v in VARIANTS})
    result = {}
    for group, arms in groups.items():
        selected = [table[a, s] for a in arms for s in manifest["maps"]]
        scores = [float(np.mean([table[a, s]["reward"] for a in arms])) for s in manifest["maps"]]
        result[group] = {"arms": arms, "episodes": len(selected), "mean_reward": float(np.mean(scores)),
                         "map_rewards": scores, "home": sum(r["home"] for r in selected),
                         "alive": sum(r["alive"] for r in selected),
                         "deaths": sum(not r["alive"] for r in selected),
                         "invalid_calls": sum(r["invalid_calls"] for r in selected)}
    differences = {name: contrast(np.array(result[left]["map_rewards"]) - result[right]["map_rewards"])
                   for name, left, right in (("prior_minus_greedy", "prior", "greedy"),
                                              ("prior_minus_plain", "prior", "plain"),
                                              ("prior_minus_beam", "prior", "beam"),
                                              ("plain_minus_beam", "plain", "beam"),
                                              ("plain_minus_initial", "plain", "plain-initial"))}
    primary, prior, greedy = differences["prior_minus_greedy"], result["prior"], result["greedy"]
    success = (primary["mean"] >= .01 and primary["bootstrap_95_percentile"][0] > 0
               and prior["deaths"] == prior["invalid_calls"] == 0
               and prior["home"] / prior["episodes"] >= greedy["home"] / greedy["episodes"] - 1 / 128)
    return {"groups": result, "contrasts": differences, "primary_success": success,
            "limit": "Map bootstrap averages three fixed training seeds within each map; no seed/checkpoint selection."}


def row_for(saved, artifact, hashed):
    bundle = saved["bundle"]
    row = {"arm": bundle["arm"] if bundle else saved["arm"],
           "seed": bundle["seed"] if bundle else saved["seed"], "status": saved["status"],
           "artifact": artifact, "sha256": hashed, "audit": saved["audit"],
           "error": saved.get("error")}
    if bundle is not None:
        episode = bundle["episode"]
        row.update(reward=episode["reward"], home=episode["result"]["at_base"],
                   alive=episode["result"]["alive"], invalid_calls=len(episode["invalid_calls"]))
    return row


def run(manifest_path, output, workers=8):
    require(type(workers) is int and 1 <= workers <= 8, "workers must be1–8")
    manifest = read_json(manifest_path)
    verify_manifest(manifest)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    write_new(output / "manifest.json", manifest)
    report = {"schema": "hybrid-ppo-final-report-v1", "status": "running",
              "manifest_sha256": digest(output / "manifest.json"), "cases": [], "summary": None}
    atomic_json(output / "report.json", report)
    try:
        with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context("spawn"),
                                 initializer=worker_init) as pool:
            for saved in pool.map(verified_job, jobs(manifest), chunksize=1):
                bundle = saved["bundle"]
                arm, seed = (bundle["arm"], bundle["seed"]) if bundle else (saved["arm"], saved["seed"])
                artifact = f"cases/{arm}-{seed}.json.gz"
                write_new(output / artifact, saved)
                report["cases"].append(row_for(saved, artifact, digest(output / artifact)))
                atomic_json(output / "report.json", report)
        report["status"] = "complete" if all(r["status"] == "complete" for r in report["cases"]) else "failed"
        if report["status"] == "complete":
            report["summary"] = summarize(report["cases"], manifest)
    except BaseException as error:
        report.update(status="failed", error={"type": type(error).__name__, "message": str(error)[:1000]})
        raise
    finally:
        atomic_json(output / "report.json", report)
    return report


def _audit_file(item):
    path, row, job = item
    require(digest(path) == row["sha256"], "retained case file hash changed")
    saved = read_json(path)
    require(saved["status"] == "complete" and saved["audit"] == audit_case(saved["bundle"], job),
            "retained case audit changed")
    require(row_for(saved, row["artifact"], row["sha256"]) == row, "retained summary row changed")
    return saved["audit"]


def audit(report_path, workers=8):
    require(type(workers) is int and 1 <= workers <= 8, "workers must be1–8")
    report_path = Path(report_path)
    root, report = report_path.parent, read_json(report_path)
    manifest = read_json(root / "manifest.json")
    verify_manifest(manifest)
    require(report["schema"] == "hybrid-ppo-final-report-v1" and report["status"] == "complete"
            and report["manifest_sha256"] == digest(root / "manifest.json"), "report/manifest incomplete or changed")
    require(report["summary"] == summarize(report["cases"], manifest), "report summary changed")
    by_pair = {(j["arm"]["id"], j["seed"]): j for j in jobs(manifest)}
    items = []
    for row in report["cases"]:
        path = (root / row["artifact"]).resolve()
        require(path.is_relative_to(root.resolve()), "unsafe case path")
        items.append((path, row, by_pair[row["arm"], row["seed"]]))
    with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context("spawn"),
                             initializer=worker_init) as pool:
        verified = list(pool.map(_audit_file, items, chunksize=1))
    result = {"schema": "hybrid-ppo-final-audit-v1", "report_sha256": digest(report_path),
              "manifest_sha256": report["manifest_sha256"], "cases_verified": len(verified),
              "all_physics_choices_and_full_controller_replays_verified": True}
    write_new(root / "audit.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", type=Path)
    action.add_argument("--run", type=Path)
    action.add_argument("--audit", type=Path)
    parser.add_argument("--runs", nargs="+", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    if args.freeze:
        require(args.runs is not None, "--runs required")
        result = freeze_runs(args.runs, args.freeze)
        print(json.dumps({"freeze": str(args.freeze), "arms": len(result["arms"]), "maps": len(result["maps"])}))
    elif args.run:
        require(args.output is not None, "--output required")
        result = run(args.run, args.output, args.workers)
        print(json.dumps({"status": result["status"], "cases": len(result["cases"]), "summary": result["summary"]}))
    else:
        print(json.dumps(audit(args.audit, args.workers), sort_keys=True))


if __name__ == "__main__":
    main()
