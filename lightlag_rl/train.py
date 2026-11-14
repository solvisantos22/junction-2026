"""Bounded Monte Carlo policy-gradient training on Traverse; no fresh evaluation.

Every pair of trajectories uses the same training map and independent action
sampling. The only task reward is the existing full-horizon mission score.
The shared navigator is fixed; only the small candidate scorer is updated.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import multiprocessing as mp
from pathlib import Path
import subprocess
import time
from typing import Callable

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TRAIN_SEEDS = tuple(range(71000, 71128))
SMOKE_SEEDS = (1, 2)
PARAMETERS = ("W", "b", "v")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_json(path: Path, value) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")
    temporary.replace(path)


def source_pins() -> dict[str, str]:
    files = [p for package in ("lightlag_rl", "lightlag_traverse", "lightlag", "lightlag_mcp")
             for p in (ROOT / package).rglob("*.py")]
    protocol = ROOT / "docs/lightlag-rl.md"
    if not protocol.is_file():
        raise ValueError("publish docs/lightlag-rl.md before training")
    files.append(protocol)
    return {str(p.relative_to(ROOT)): digest(p) for p in sorted(files)}


def verify_pins(pins) -> None:
    if source_pins() != pins:
        raise RuntimeError("source or protocol changed during training")


def collect_job(job: dict) -> dict:
    """Worker sees a policy and one allowed training seed, never test cases."""
    from .adapter import run_episode
    from .model import Policy

    policy = Policy.from_state(job["policy"])
    rng = np.random.default_rng(job["policy_seed"])
    trajectory = []

    def choose(ids, features):
        action = int(policy.choose(features, rng))
        trajectory.append({"ids": list(ids), "features": np.asarray(features).tolist(), "action": action})
        return action

    episode = run_episode(job["seed"], choose, keep_replay=False)
    reward = float(episode["reward"])
    if not math.isfinite(reward) or not 0 <= reward <= 1:
        raise ValueError("the official normalized terminal reward must be in [0,1]")
    return {"seed": job["seed"], "policy_seed": job["policy_seed"],
            "reward": reward, "episode": episode, "trajectory": trajectory}


class ProcessCollector:
    """A public multiprocessing API allows timed-out workers to be terminated."""

    def __init__(self, workers: int):
        self.pool = mp.get_context("spawn").Pool(processes=workers)

    def __call__(self, jobs, timeout):
        return self.pool.map_async(collect_job, jobs, chunksize=1).get(timeout=timeout)

    def close(self, failed=False):
        if failed:
            self.pool.terminate()
        else:
            self.pool.close()
        self.pool.join()


def advantages(rows) -> np.ndarray:
    """Within-map mean baseline; scale only by this batch's advantages."""
    if len(rows) < 2 or len(rows) % 2:
        raise ValueError("a batch needs pairs of same-map trajectories")
    rewards = np.asarray([row["reward"] for row in rows], dtype=float)
    if not np.isfinite(rewards).all() or np.any(rewards < 0) or np.any(rewards > 1):
        raise ValueError("invalid terminal reward")
    for i in range(0, len(rows), 2):
        if rows[i]["seed"] != rows[i + 1]["seed"]:
            raise ValueError("adjacent training trajectories must share one map")
    paired = rewards.reshape(-1, 2)
    result = (paired - paired.mean(axis=1, keepdims=True)).ravel()
    return result / max(.01, float(result.std()))


def batch_gradient(policy, rows, entropy=.01):
    """Sum each episode's score gradients, then average across episodes."""
    state = policy.state_dict()
    total = {name: np.zeros_like(np.asarray(state[name], dtype=float)) for name in PARAMETERS}
    adv = advantages(rows)
    for row, value in zip(rows, adv):
        for decision in row["trajectory"]:
            grad = policy.gradient(np.asarray(decision["features"], dtype=float),
                                   decision["action"], float(value), entropy=entropy)
            for name in PARAMETERS:
                total[name] += grad[name] / len(rows)
    if any(not np.isfinite(value).all() for value in total.values()):
        raise ValueError("nonfinite policy gradient")
    return total, adv.tolist()


def _validate_config(updates, batch_size, workers, train_seed, max_seconds, smoke):
    if any(type(v) is not int for v in (updates, batch_size, workers, train_seed)):
        raise ValueError("integer training configuration required")
    if not 1 <= updates <= 16 or not 2 <= batch_size <= 32 or batch_size % 2 or not 1 <= workers <= 4:
        raise ValueError("supported bounds: 1–16 updates, even batch 2–32, 1–4 workers")
    if not math.isfinite(max_seconds) or not 0 < max_seconds <= 3000:
        raise ValueError("max_seconds must be positive and at most 3000")
    if smoke and (updates > 2 or batch_size > 4):
        raise ValueError("smoke mode requires at most 2 updates and batch size 4")


def run(output, updates=16, batch_size=32, workers=4, train_seed=17,
        max_seconds=3000, smoke=False, *, collector: Callable | None = None,
        clock=time.monotonic, pin_source=source_pins, check_pins=verify_pins,
        policy_factory=None, optimizer_factory=None):
    """Train once; incomplete runs never receive a final-policy artifact.

    Test-only dependency injections do not affect the command-line path. The
    caller may use them for finite deterministic unit checks without episodes.
    """
    from .model import Policy, Adam

    _validate_config(updates, batch_size, workers, train_seed, max_seconds, smoke)
    output = Path(output)
    if output.exists():
        raise ValueError("output must be a new directory")
    pins = pin_source()
    policy = (policy_factory or Policy)(seed=train_seed, hidden=16)
    optimizer = (optimizer_factory or Adam)(policy)
    rng = np.random.default_rng(train_seed)
    seeds = SMOKE_SEEDS if smoke else TRAIN_SEEDS
    config = {"updates": updates, "batch_size": batch_size, "workers": workers,
              "train_seed": train_seed, "max_seconds": max_seconds, "smoke": smoke,
              "training_seeds": list(seeds), "rollouts_per_map": 2,
              "learning_rate": .02, "entropy_coefficient": .01, "gradient_norm_limit": 5,
              "reward": "official normalized full-horizon terminal reward",
              "baseline": "within-map pair mean; batch advantage std floor .01"}
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                         stderr=subprocess.DEVNULL, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None  # Modal has the pinned sources, not a Git checkout.
    output.mkdir(parents=True, exist_ok=False)
    (output / "batches").mkdir()
    atomic_json(output / "initial-policy.json", policy.state_dict())
    started = clock()
    report = {"schema": "lightlag-rl-training-v1", "status": "incomplete", "config": config,
              "source_sha256": pins, "source_commit": commit, "updates_completed": 0,
              "episodes_completed": 0, "model_api_calls": 0, "fresh_cases": 0,
              "initial_policy_sha256": digest(output / "initial-policy.json"), "metrics": []}

    def checkpoint(index):
        state = {"schema": "lightlag-rl-checkpoint-v1", "updates_completed": index,
                 "policy": policy.state_dict(), "optimizer": optimizer.state_dict(),
                 "rng_state": rng.bit_generator.state, "config": config, "source_sha256": pins}
        path = output / f"checkpoint-{index:04d}.json"
        atomic_json(path, state)
        report["latest_checkpoint"] = path.name
        report["latest_checkpoint_sha256"] = digest(path)
        report["elapsed_seconds"] = max(0, clock() - started)
        atomic_json(output / "training.json", report)

    checkpoint(0)
    owned_collector = None
    failed = True
    try:
        if collector is None:
            owned_collector = ProcessCollector(workers)
            collector = owned_collector
        for update in range(1, updates + 1):
            check_pins(pins)
            remaining = max_seconds - (clock() - started)
            if remaining <= 0:
                raise TimeoutError("training time limit")
            chosen = rng.choice(seeds, size=batch_size // 2, replace=False)
            state = policy.state_dict()
            jobs = [{"seed": int(seed), "policy_seed": int(rng.integers(0, 2**63)), "policy": state}
                    for seed in chosen for _ in range(2)]
            rows = collector(jobs, remaining)
            if len(rows) != len(jobs) or any((r["seed"], r["policy_seed"]) != (j["seed"], j["policy_seed"])
                                           for r, j in zip(rows, jobs)):
                raise ValueError("collector returned missing, reordered or mismatched trajectories")
            batch = {"schema": "lightlag-rl-training-batch-v1", "update": update,
                     "policy_sha256": hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest(),
                     "rows": rows}
            artifact = output / "batches" / f"update-{update:04d}.json.gz"
            artifact.write_bytes(gzip.compress(json.dumps(batch, allow_nan=False, separators=(",", ":")).encode(), mtime=0))
            report["episodes_completed"] += len(rows)
            check_pins(pins)
            if clock() - started >= max_seconds:
                raise TimeoutError("training time limit after completed batch")
            gradient, adv = batch_gradient(policy, rows)
            optimizer.step(gradient, lr=.02, max_norm=5)
            rewards = [r["reward"] for r in rows]
            report["metrics"].append({"update": update, "episodes": len(rows),
                                      "mean_reward": float(np.mean(rewards)), "min_reward": min(rewards),
                                      "max_reward": max(rewards), "advantage_std": float(np.std(adv)),
                                      "decisions": sum(len(r["trajectory"]) for r in rows),
                                      "artifact": str(artifact.relative_to(output)), "sha256": digest(artifact)})
            report["updates_completed"] = update
            checkpoint(update)
            print(json.dumps({"update": update, "updates": updates,
                              "mean_reward": report["metrics"][-1]["mean_reward"],
                              "elapsed_seconds": report["elapsed_seconds"]}), flush=True)
        check_pins(pins)
        if clock() - started >= max_seconds:
            raise TimeoutError("training time limit before final freeze")
        atomic_json(output / "final-policy.json", policy.state_dict())
        report.update(status="complete", final_policy_sha256=digest(output / "final-policy.json"))
        failed = False
    except (TimeoutError, mp.TimeoutError):
        report["incomplete_reason"] = "training_time_limit"
    except Exception as error:
        report["incomplete_reason"] = type(error).__name__ + ": " + str(error)[:500]
    finally:
        if owned_collector is not None:
            owned_collector.close(failed=failed)
        report["elapsed_seconds"] = max(0, clock() - started)
        atomic_json(output / "training.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--updates", type=int, default=16)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--train-seed", type=int, default=17)
    parser.add_argument("--max-seconds", type=float, default=3000)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    report = run(**vars(args))
    print(json.dumps({key: report.get(key) for key in
                      ("status", "updates_completed", "episodes_completed", "incomplete_reason", "elapsed_seconds")}))
    return 0 if report["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
