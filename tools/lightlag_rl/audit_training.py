"""Reconstruct saved sampling and training updates; never generate a mission."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np

from lightlag_rl.model import Adam, Policy
from lightlag_rl.train import PARAMETERS, TRAIN_SEEDS, batch_gradient, digest, source_pins


def close(actual, expected, label):
    if isinstance(expected, dict):
        assert isinstance(actual, dict) and actual.keys() == expected.keys(), label
        for key in expected:
            close(actual[key], expected[key], label + "." + key)
    elif isinstance(expected, (list, float)):
        np.testing.assert_allclose(actual, expected, rtol=1e-9, atol=1e-9, err_msg=label)
    else:
        assert actual == expected, label


def audit(training, smoke=False):
    if not __debug__:
        raise RuntimeError("Run this assertion-based auditor without Python -O")
    directory = Path(training).resolve()
    read = lambda name: json.loads((directory / name).read_text())
    report = read("training.json")
    assert report["schema"] == "lightlag-rl-training-v1" and report["status"] == "complete"
    config, pins = report["config"], report["source_sha256"]
    assert config["smoke"] is smoke and pins == source_pins(), "source/protocol pins"
    expected_updates, expected_batch = (2, 4) if smoke else (16, 32)
    expected_seeds = [1, 2] if smoke else list(TRAIN_SEEDS)
    assert (config["updates"], config["batch_size"], config["train_seed"]) == (expected_updates, expected_batch, 17)
    assert config["training_seeds"] == expected_seeds and config["rollouts_per_map"] == 2
    assert (config["learning_rate"], config["entropy_coefficient"], config["gradient_norm_limit"]) == (.02, .01, 5)
    assert config["baseline"] == "within-map pair mean; batch advantage std floor .01"
    assert config["reward"] == "official normalized full-horizon terminal reward"
    assert 1 <= config["workers"] <= 4 and 0 < config["max_seconds"] <= 3000
    if not smoke:
        assert config["workers"] == 4 and config["max_seconds"] == 3000
    assert report["updates_completed"] == expected_updates and report["episodes_completed"] == expected_updates * expected_batch
    assert report["model_api_calls"] == report["fresh_cases"] == 0
    assert len(report["metrics"]) == expected_updates
    assert digest(directory / "initial-policy.json") == report["initial_policy_sha256"]
    assert digest(directory / "final-policy.json") == report["final_policy_sha256"]
    previous = read("checkpoint-0000.json")
    initial = Policy(seed=17, hidden=16)
    close(read("initial-policy.json"), initial.state_dict(), "initial weights")
    close(previous["policy"], initial.state_dict(), "initial checkpoint")
    close(previous["optimizer"], Adam(initial).state_dict(), "initial optimizer")
    assert previous["rng_state"] == np.random.default_rng(17).bit_generator.state
    assert previous["updates_completed"] == 0
    seen, decisions, invalid_calls = set(), 0, 0
    for index, metric in enumerate(report["metrics"], 1):
        assert previous["schema"] == "lightlag-rl-checkpoint-v1"
        assert previous["config"] == config and previous["source_sha256"] == pins
        artifact = f"batches/update-{index:04d}.json.gz"
        assert metric["artifact"] == artifact and metric["sha256"] == digest(directory / artifact)
        batch = json.loads(gzip.decompress((directory / artifact).read_bytes()))
        assert batch["schema"] == "lightlag-rl-training-batch-v1" and batch["update"] == index
        assert batch["policy_sha256"] == hashlib.sha256(json.dumps(previous["policy"], sort_keys=True).encode()).hexdigest()
        rows = batch["rows"]
        assert len(rows) == expected_batch
        rng = np.random.default_rng()
        rng.bit_generator.state = previous["rng_state"]
        maps = rng.choice(expected_seeds, size=expected_batch // 2, replace=False)
        expected_ids = [(int(seed), int(rng.integers(0, 2**63))) for seed in maps for _ in range(2)]
        policy = Policy.from_state(previous["policy"])
        for row, identity in zip(rows, expected_ids):
            assert (row["seed"], row["policy_seed"]) == identity and identity not in seen
            seen.add(identity)
            episode, sampling = row["episode"], np.random.default_rng(row["policy_seed"])
            result = episode["result"]
            assert episode["seed"] == row["seed"] and result["tick"] == 420 and result["mission_profile"] == "traverse"
            assert result["max_available_value"] > 0
            reward = result["raw_score"] / result["max_available_value"]
            assert np.isfinite(reward) and 0 <= reward <= 1
            close(row["reward"], reward, "retained terminal reward")
            close(episode["reward"], reward, "episode reward")
            assert episode["decision_count"] == len(row["trajectory"])
            invalid_calls += len(episode["invalid_calls"])
            for decision in row["trajectory"]:
                ids, features = decision["ids"], np.asarray(decision["features"], dtype=float)
                assert ids and ids[0] == "base" and len(ids) == len(set(ids)) and ids[1:] == sorted(ids[1:])
                assert features.shape == (len(ids), 14) and np.isfinite(features).all() and np.max(np.abs(features)) <= 2
                assert decision["action"] == policy.choose(features, sampling), "stored action differs from sampling replay"
                decisions += 1
        optimizer = Adam(policy)
        optimizer.t = previous["optimizer"]["t"]
        for field in ("m", "v"):
            setattr(optimizer, field, {key: np.asarray(previous["optimizer"][field][key], dtype=float) for key in PARAMETERS})
        gradient, advantages = batch_gradient(policy, rows, entropy=.01)
        optimizer.step(gradient, lr=.02, max_norm=5)
        current = read(f"checkpoint-{index:04d}.json")
        assert current["schema"] == "lightlag-rl-checkpoint-v1"
        assert current["updates_completed"] == index and current["config"] == config and current["source_sha256"] == pins
        assert current["rng_state"] == rng.bit_generator.state
        close(current["policy"], policy.state_dict(), "reconstructed checkpoint policy")
        close(current["optimizer"], optimizer.state_dict(), "reconstructed checkpoint optimizer")
        rewards = [row["reward"] for row in rows]
        expected = {"update": index, "episodes": expected_batch, "mean_reward": float(np.mean(rewards)),
                    "min_reward": min(rewards), "max_reward": max(rewards), "advantage_std": float(np.std(advantages)),
                    "decisions": sum(len(row["trajectory"]) for row in rows), "artifact": artifact, "sha256": digest(directory / artifact)}
        close(metric, expected, "batch metrics")
        previous = current
    assert report["latest_checkpoint"] == f"checkpoint-{expected_updates:04d}.json"
    assert digest(directory / report["latest_checkpoint"]) == report["latest_checkpoint_sha256"]
    close(read("final-policy.json"), previous["policy"], "final frozen policy")
    return {"schema": "lightlag-rl-training-audit-v1", "training_sha256": digest(directory / "training.json"),
            "smoke": smoke, "updates_reconstructed": expected_updates, "episodes_verified": len(seen),
            "sampled_actions_reconstructed": decisions, "invalid_calls_retained": invalid_calls,
            "source_files_verified": len(pins), "tolerance": 1e-9, "new_environment_cases": 0,
            "limit": "Reconstructs sampling, recorded reward arithmetic, gradients and optimizer updates. Does not independently verify simulator physics or recorded features/rewards against mission replays."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--training", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    result = json.dumps(audit(args.training, args.smoke), indent=2) + "\n"
    if args.output:
        args.output.write_text(result)
    print(result, end="")


if __name__ == "__main__":
    main()
