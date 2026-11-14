"""Compare fixed policies with frequent or persistent goals; no training or APIs."""

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import gzip
import json
import multiprocessing as mp
from pathlib import Path
import platform
import shutil
import subprocess
import sys

import numpy as np

from lightlag_rl.adapter import greedy_choice, run_episode
from lightlag_rl.model import Policy
from lightlag_rl.train import atomic_json, digest, source_pins as original_source_pins
from lightlag_rl_persistence.chooser import GoalChooser
from tools.lightlag_rl.check import training_inputs

ROOT = Path(__file__).resolve().parents[2]
TRAINING = ROOT / "docs/lightlag-rl-results/modal/pilot-01/training"
SEEDS = tuple(range(71000, 71006)) + tuple(range(71007, 71025))
SMOKE_SEEDS = (1, 2)
POLICIES = ("initial", "final", "greedy")
MODES = ("frequent", "persistent")
INPUT_HASHES = {
    "training.json": "67256197108905c3b47075ce247f1321e4dde59cc3671f48379894ea681ea06d",
    "initial-policy.json": "2ccca99c72e2302330f594ae03958ed1b8699dfa7fd92295675b5d59b94f431b",
    "final-policy.json": "3f636cac0bb774db76060004c04666eb41693f15acc766aca43a7e8942b5c33a",
}
CONFIG = {
    "draws": {"initial": 2, "final": 2, "greedy": 1},
    "action_rng_multiplier": 1000003,
    "primary_policy": "initial",
    "contrast": "persistent minus frequent",
    "bootstrap_draws": 10000,
    "bootstrap_seed": 17,
    "bootstrap_unit": "map: average two action draws before resampling",
    "minimum_mean_gain": .03,
    "maximum_home_count_loss": 2,
    "maximum_death_count_increase": 0,
    "maximum_invalid_call_increase": 0,
    "horizon": 420,
}
IDENTITY = ("mode", "policy", "seed", "draw", "policy_seed")


def source_pins():
    """Pin the original closure plus this diagnostic and its protocol."""
    pins = original_source_pins()
    files = [ROOT / "tools/lightlag_rl/__init__.py", ROOT / "tools/lightlag_rl/check.py",
             ROOT / "docs/lightlag-rl-persistence.md"]
    for package in ("lightlag_rl_persistence", "tools/rl_persistence"):
        files.extend(sorted((ROOT / package).rglob("*.py")))
    pins.update({str(path.relative_to(ROOT)): digest(path) for path in files})
    return dict(sorted(pins.items()))


def verify_inputs(training_dir=TRAINING):
    """Verify original weights, source closure and observed training maps; no cases."""
    directory = Path(training_dir).resolve()
    for name, hashed in INPUT_HASHES.items():
        if digest(directory / name) != hashed:
            raise ValueError(f"immutable original training input changed: {name}")
    trained = training_inputs(directory, smoke=False)
    artifacts = dict(INPUT_HASHES)
    artifacts[trained["latest_checkpoint"]] = trained["latest_checkpoint_sha256"]
    visited, episodes = set(), 0
    for update, metric in enumerate(trained["metrics"], 1):
        name = metric["artifact"]
        path = (directory / name).resolve()
        if (not path.is_relative_to(directory) or metric["update"] != update
                or digest(path) != metric["sha256"]):
            raise ValueError("original training batch identity/hash mismatch")
        batch = json.loads(gzip.decompress(path.read_bytes()))
        if (batch["schema"] != "lightlag-rl-training-batch-v1"
                or batch["update"] != update or len(batch["rows"]) != 32):
            raise ValueError("original training batch is incomplete")
        visited.update(row["seed"] for row in batch["rows"])
        episodes += len(batch["rows"])
        artifacts[name] = metric["sha256"]
    if episodes != 512 or tuple(sorted(visited)[:24]) != SEEDS:
        raise ValueError("diagnostic maps differ from the first 24 visited training maps")
    states = {name: json.loads((directory / f"{name}-policy.json").read_text())
              for name in ("initial", "final")}
    # Paths describe retained original evidence, not copies of every training batch.
    return states, {str((directory / name).relative_to(ROOT)): hashed
                    for name, hashed in artifacts.items()}


def jobs(seeds):
    return [{"mode": mode, "policy": policy, "seed": seed, "draw": draw,
             "policy_seed": CONFIG["action_rng_multiplier"] * seed + draw}
            for policy in POLICIES for mode in MODES for seed in seeds
            for draw in range(CONFIG["draws"][policy])]


def evaluate_job(job, states):
    policy = Policy.from_state(states[job["policy"]]) if job["policy"] in states else None
    rng = np.random.default_rng(job["policy_seed"])

    def choose(ids, features):
        return policy.choose(features, rng) if policy is not None else greedy_choice(ids, features)

    chooser = GoalChooser(choose, persistent=job["mode"] == "persistent")
    episode = run_episode(job["seed"], chooser, keep_replay=True)
    return {"schema": "lightlag-rl-persistence-episode-v1", **job,
            "episode": episode, "decisions": chooser.decisions}


def row_for(bundle, artifact, hashed):
    episode, decisions = bundle["episode"], bundle["decisions"]
    result = episode["result"]
    if (episode["seed"] != bundle["seed"] or result["tick"] != CONFIG["horizon"]
            or episode["decision_count"] != len(decisions)
            or not np.isfinite(episode["reward"])):
        raise ValueError("episode is incomplete or inconsistent")
    return {**{key: bundle[key] for key in IDENTITY}, "artifact": artifact, "sha256": hashed,
            "reward": episode["reward"], "alive": result["alive"], "at_base": result["at_base"],
            "invalid_calls": len(episode["invalid_calls"]), "decision_count": len(decisions),
            "retained_decisions": sum(d["reason"] == "retain" for d in decisions),
            "overridden_proposals": sum(d["proposed_action"] != d["action"] for d in decisions)}


def summarize(rows, seeds):
    """A paired-map screen on initial weights; final/greedy remain descriptive."""
    expected = {tuple(job[k] for k in IDENTITY) for job in jobs(seeds)}
    actual = [tuple(row[k] for k in IDENTITY) for row in rows]
    if len(actual) != len(expected) or set(actual) != expected:
        raise ValueError("summary requires every declared case exactly once")
    descriptions, contrasts = {}, {}
    for policy in POLICIES:
        descriptions[policy] = {}
        for mode in MODES:
            subset = [r for r in rows if r["policy"] == policy and r["mode"] == mode]
            descriptions[policy][mode] = {
                "n": len(subset), "mean_reward": float(np.mean([r["reward"] for r in subset])),
                "alive_home": sum(bool(r["alive"] and r["at_base"]) for r in subset),
                "deaths": sum(not r["alive"] for r in subset),
                "invalid_calls": sum(r["invalid_calls"] for r in subset),
                "decision_count": sum(r["decision_count"] for r in subset),
                "retained_decisions": sum(r["retained_decisions"] for r in subset),
                "overridden_proposals": sum(r["overridden_proposals"] for r in subset),
            }
        differences = [float(
            np.mean([r["reward"] for r in rows if r["policy"] == policy and r["mode"] == "persistent" and r["seed"] == seed])
            - np.mean([r["reward"] for r in rows if r["policy"] == policy and r["mode"] == "frequent" and r["seed"] == seed]))
            for seed in seeds]
        contrasts[policy] = {"paired_map_differences": dict(zip(map(str, seeds), differences)),
                             "mean_paired_gain": float(np.mean(differences))}
    primary = dict(contrasts["initial"])
    differences = list(primary["paired_map_differences"].values())
    samples = np.random.default_rng(CONFIG["bootstrap_seed"]).choice(
        differences, size=(CONFIG["bootstrap_draws"], len(seeds)), replace=True).mean(axis=1)
    primary["bootstrap_95_percentile"] = np.quantile(samples, [.025, .975]).tolist()
    primary["bootstrap_draws"], primary["bootstrap_seed"] = CONFIG["bootstrap_draws"], CONFIG["bootstrap_seed"]
    frequent, persistent = (descriptions["initial"][mode] for mode in MODES)
    gate = {
        "gain_at_least_03": primary["mean_paired_gain"] >= CONFIG["minimum_mean_gain"],
        "bootstrap_lower_positive": primary["bootstrap_95_percentile"][0] > 0,
        "home_no_more_than_two_lower": persistent["alive_home"] >= frequent["alive_home"] - CONFIG["maximum_home_count_loss"],
        "no_increased_deaths": persistent["deaths"] <= frequent["deaths"],
        "no_increased_invalid_calls": persistent["invalid_calls"] <= frequent["invalid_calls"],
    }
    return {"policies": descriptions, "contrasts": contrasts, "primary": primary,
            "gate": gate, "screen_passes": all(gate.values())}


def run(output, workers=4, smoke=False, *, training=TRAINING, evaluator=evaluate_job):
    if type(workers) is not int or not 1 <= workers <= 4:
        raise ValueError("workers must be an integer in 1..4")
    if type(smoke) is not bool:
        raise ValueError("smoke must be a bool")
    training, output = Path(training), Path(output)
    states, original_artifacts = verify_inputs(training)  # before any environment case
    pins, seeds = source_pins(), SMOKE_SEEDS if smoke else SEEDS
    output.mkdir(parents=True, exist_ok=False)
    (output / "cases").mkdir()
    for name in INPUT_HASHES:
        shutil.copyfile(training / name, output / name)
        if digest(output / name) != INPUT_HASHES[name]:
            raise RuntimeError("training inputs changed while freezing")
    try:
        source_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        source_commit = None
    freeze = {"schema": "lightlag-rl-persistence-freeze-v1", "smoke": smoke,
              "seeds": list(seeds), "config": CONFIG, "workers": workers,
              "source_commit": source_commit,
              "runtime": {"python": sys.version, "python_version": platform.python_version(),
                          "numpy": np.__version__},
              "source_sha256": pins, "artifacts": dict(INPUT_HASHES),
              "training_artifacts": original_artifacts,
              "model_api_calls": 0, "cloud_jobs": 0, "training_updates": 0}
    atomic_json(output / "freeze.json", freeze)
    report = {"schema": "lightlag-rl-persistence-v1", "status": "incomplete", "complete": False,
              "smoke": smoke, "freeze_sha256": digest(output / "freeze.json"), "cases": [], "summary": None}
    atomic_json(output / "report.json", report)

    def verify_freeze():
        if (source_pins() != pins or digest(output / "freeze.json") != report["freeze_sha256"]
                or any(digest(output / n) != h for n, h in freeze["artifacts"].items())
                or any(digest(ROOT / n) != h for n, h in original_artifacts.items())):
            raise RuntimeError("frozen inputs changed during diagnostic")

    def save(bundle, job):
        if any(bundle[key] != job[key] for key in IDENTITY):
            raise ValueError("worker returned a different case identity")
        artifact = "cases/{policy}-{mode}-{seed}-{draw}.json.gz".format(**bundle)
        path = output / artifact
        row_for(bundle, artifact, "")  # reject incomplete episodes before recording them
        path.write_bytes(gzip.compress(json.dumps(bundle, allow_nan=False, separators=(",", ":")).encode(), mtime=0))
        report["cases"].append(row_for(bundle, artifact, digest(path)))
        report["cases"].sort(key=lambda row: tuple(row[key] for key in IDENTITY))
        atomic_json(output / "report.json", report)

    try:
        verify_freeze()
        work = jobs(seeds)
        if workers == 1:
            for job in work:
                save(evaluator(job, states), job)
        else:
            with ProcessPoolExecutor(max_workers=workers, mp_context=mp.get_context("spawn")) as pool:
                pending = {pool.submit(evaluator, job, states): job for job in work}
                try:
                    for future in as_completed(pending):
                        save(future.result(), pending[future])
                except BaseException:
                    for future in pending:
                        future.cancel()
                    raise
        verify_freeze()
        report["summary"] = summarize(report["cases"], seeds)
        report["complete"], report["status"] = True, "complete"
        atomic_json(output / "report.json", report)
    except BaseException as error:
        report["complete"], report["status"] = False, "incomplete"
        report["error"] = {"type": type(error).__name__, "message": str(error)}
        atomic_json(output / "report.json", report)
        raise
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, choices=range(1, 5), default=4)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    report = run(args.output, args.workers, args.smoke)
    print(json.dumps({"complete": report["complete"], "cases": len(report["cases"]),
                      "smoke": report["smoke"], "summary": report["summary"]}, indent=2))


if __name__ == "__main__":
    main()
