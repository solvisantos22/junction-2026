"""Audit saved persistence diagnostics without training or opening new map IDs."""

import argparse
from collections import Counter, defaultdict
import gzip
import json
from pathlib import Path

import numpy as np

from lightlag_rl.adapter import greedy_choice
from lightlag_rl.model import Policy
from lightlag_rl.train import atomic_json, digest
from lightlag_traverse.environment import TraverseEnvironment


def normal(value):
    return json.loads(json.dumps(value, allow_nan=False))


def audit_case(bundle, states):
    """Rebuild physics and independently check proposal/commitment transitions."""
    if not __debug__:
        raise RuntimeError("run this assertion-based auditor without Python -O")
    episode, decisions = bundle["episode"], bundle["decisions"]
    assert bundle["schema"] == "lightlag-rl-persistence-episode-v1"
    replay = episode["replay"]
    assert bundle["seed"] == episode["seed"] == replay["seed"]
    assert bundle["policy"] in ("initial", "final", "greedy")
    assert bundle["mode"] in ("frequent", "persistent")
    assert bundle["policy_seed"] == 1000003 * bundle["seed"] + bundle["draw"]
    env = TraverseEnvironment(bundle["seed"])
    commands = defaultdict(list)
    for command in replay["commands"]:
        commands[command["sent_tick"]].append(command)
    for tick in range(420):
        for command in commands.pop(tick, []):
            assert normal(env.uplink([command["command"]])) == [command]
        env.advance(1)
    assert not commands
    assert normal(env.replay()) == replay
    assert normal(env.evaluate()) == episode["result"]
    assert episode["result"]["tick"] == 420
    assert episode["reward"] == episode["result"]["raw_score"] / episode["result"]["max_available_value"]
    assert episode["decision_count"] == len(decisions)
    assert episode["calls_by_tool"]["advance"] == 420
    assert episode["public_calls"] == sum(episode["calls_by_tool"].values())
    assert dict(Counter(c["command"]["action"] for c in replay["commands"])) == episode["commands_by_action"]

    policy = Policy.from_state(states[bundle["policy"]]) if bundle["policy"] != "greedy" else None
    rng = np.random.default_rng(bundle["policy_seed"])
    held = None
    retained = overridden = 0
    for index, decision in enumerate(decisions):
        ids = decision["ids"]
        features = np.asarray(decision["features"], dtype=float)
        assert ids and ids[0] == "base" and len(ids) == len(set(ids))
        assert all(isinstance(name, str) for name in ids)
        assert features.shape == (len(ids), 14) and np.isfinite(features).all()
        proposal = int(policy.choose(features, rng) if policy is not None else greedy_choice(ids, features))
        assert type(decision["proposed_action"]) is int and decision["proposed_action"] == proposal
        assert decision["prior_goal"] == held
        if bundle["mode"] == "frequent":
            action, reason, next_held = proposal, "pass_through", None
        elif held is not None and held in ids:
            action, reason, next_held = ids.index(held), "retain", held
        else:
            action = proposal
            reason = "release_missing" if held is not None else "initial_select" if index == 0 else "unheld_select"
            next_held = ids[action] if ids[action] != "base" else None
        assert type(decision["action"]) is int and decision["action"] == action
        assert decision["reason"] == reason and decision["held_goal"] == next_held
        retained += reason == "retain"
        overridden += proposal != action
        held = next_held
    return {"decisions": len(decisions), "retained": retained, "overridden": overridden}


def audit(path):
    from .run import CONFIG, INPUT_HASHES, SEEDS, jobs, row_for, source_pins, summarize, verify_inputs

    if not __debug__:
        raise RuntimeError("run this assertion-based auditor without Python -O")
    path = Path(path).resolve()
    report = json.loads(path.read_text())
    assert report["schema"] == "lightlag-rl-persistence-v1"
    assert report["complete"] is True and report["status"] == "complete"
    freeze_path = path.parent / "freeze.json"
    assert digest(freeze_path) == report["freeze_sha256"]
    freeze = json.loads(freeze_path.read_text())
    assert freeze["schema"] == "lightlag-rl-persistence-freeze-v1"
    assert type(freeze["smoke"]) is bool and freeze["smoke"] is report["smoke"]
    assert type(freeze["workers"]) is int and 1 <= freeze["workers"] <= 4
    seeds = (1, 2) if freeze["smoke"] else SEEDS
    assert freeze["seeds"] == list(seeds) and freeze["config"] == CONFIG
    assert freeze["model_api_calls"] == freeze["cloud_jobs"] == freeze["training_updates"] == 0
    assert freeze["source_sha256"] == source_pins()
    states, original_hashes = verify_inputs()
    assert freeze["training_artifacts"] == original_hashes
    assert freeze["artifacts"] == INPUT_HASHES
    for name, hashed in freeze["artifacts"].items():
        assert Path(name).name == name and digest(path.parent / name) == hashed
    for name in ("initial", "final"):
        assert json.loads((path.parent / f"{name}-policy.json").read_text()) == states[name]
    expected = {(j["seed"], j["policy"], j["mode"], j["draw"], j["policy_seed"]) for j in jobs(seeds)}
    identities = [(r["seed"], r["policy"], r["mode"], r["draw"], r["policy_seed"]) for r in report["cases"]]
    assert len(identities) == len(expected) and set(identities) == expected
    verified, seen = [], set()
    totals = {"decisions": 0, "retained": 0, "overridden": 0}
    for row in report["cases"]:
        artifact = (path.parent / row["artifact"]).resolve()
        assert artifact.is_relative_to(path.parent) and artifact not in seen
        assert digest(artifact) == row["sha256"]
        seen.add(artifact)
        bundle = json.loads(gzip.decompress(artifact.read_bytes()))
        assert row_for(bundle, row["artifact"], row["sha256"]) == row
        counts = audit_case(bundle, states)
        for name in totals:
            totals[name] += counts[name]
        verified.append(row)
    assert summarize(verified, seeds) == report["summary"]
    return {"schema": "lightlag-rl-persistence-audit-v1", "report_sha256": digest(path),
            "smoke": freeze["smoke"], "cases_verified": len(verified),
            "full_replays_match": True, "choice_totals": totals,
            "source_files_verified": len(freeze["source_sha256"]),
            "summary": report["summary"],
            "limit": "Physics, grades, proposal sampling and commitment transitions verified. Candidate/feature reconstruction and the choice-to-command connection are source-pinned, not independently regenerated. Reused training maps; no new training or generalization claim."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.report)
    if args.output:
        atomic_json(args.output, result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
