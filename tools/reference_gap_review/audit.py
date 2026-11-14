"""Read-only review of retained RL training and Traverse agent missions.

Replays accepted commands with the trusted simulator. It never executes model
programs, trains weights, opens new seed ranges or calls an external service.
"""

import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess

from lightlag_traverse.environment import TraverseEnvironment


ROOT = Path(__file__).resolve().parents[2]


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def normalized(value):
    return json.loads(json.dumps(value, allow_nan=False))


def review_run(folder):
    replay_path = folder / "artifacts/evaluator/replay.json"
    replay = read(replay_path)
    result_path = folder / "artifacts/evaluator/result.json"
    result = read(result_path)
    transcript_path = folder / "artifacts/evaluator/transcript.jsonl"
    transcript = [json.loads(line) for line in transcript_path.read_text().splitlines()]
    env = TraverseEnvironment(replay["seed"], mission=replay["config"])
    by_tick = defaultdict(list)
    for command in replay["commands"]:
        by_tick[command["sent_tick"]].append(command)
    for tick in range(replay["config"]["max_ticks"]):
        for command in by_tick.pop(tick, []):
            require(normalized(env.uplink([command["command"]])) == [command],
                    f"{folder.name}: acknowledgement mismatch")
        env.advance(1)
    require(not by_tick, f"{folder.name}: unplayed commands")
    require(normalized(env.replay()) == replay, f"{folder.name}: physics replay mismatch")
    require(all(result[key] == value for key, value in replay["result"].items()),
            f"{folder.name}: retained result mismatch")
    reward = result["raw_score"] / result["max_available_value"]
    grade_path = folder / "verifier/reward.txt"
    require(math.isclose(float(grade_path.read_text()), reward, abs_tol=1e-6),
            f"{folder.name}: verifier grade mismatch")
    require(math.isclose(sum(sample["credited_value"] for sample in result["samples"]),
                         result["sampled_value"], abs_tol=1e-12), "sample accounting")
    require(result["raw_score"] == result["sampled_value"] * result["survival_factor"],
            "terminal factor accounting")
    base = replay["world"]["base"]
    states = replay["states"]
    end = states[-1]
    distance = lambda state: math.dist(state["position"], base)
    deaths = [state for state in states if not state["alive"]]
    finishes = []
    log_path = folder / "agent/opencode.txt"
    if log_path.exists():
        for line in log_path.read_text().splitlines():
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if entry.get("type") == "step_finish":
                finishes.append(entry["part"].get("reason"))
    run_path, harbor_path = folder / "run.json", folder / "result.json"
    require(run_path.exists() or folder.name in {"traverse-do-nothing", "traverse-stop-early"},
            "missing model-run metadata")
    run, harbor = read(run_path) if run_path.exists() else {}, read(harbor_path)
    paths = [replay_path, result_path, transcript_path, grade_path, harbor_path]
    if run_path.exists():
        paths.append(run_path)
    if log_path.exists():
        paths.append(log_path)
    last_drives = [command for command in replay["commands"]
                   if command["command"]["action"] == "drive"]
    errors = [entry for entry in transcript if not entry.get("ok", True)]
    return {
        "run": folder.name, "seed": replay["seed"], "task_version": run.get("task_version"),
        "task_checksum": harbor.get("task_checksum"), "model": run.get("model"),
        "reward": reward, "sampled_value": result["sampled_value"],
        "samples": len(result["samples"]), "max_available_value": result["max_available_value"],
        "late_samples": sum(not sample["on_time"] for sample in result["samples"]),
        "survival_factor": result["survival_factor"], "alive": result["alive"],
        "at_base": result["at_base"], "terminal_tick": end["tick"],
        "last_agent_tool_tick": max((row["tick_after"] for row in transcript), default=0),
        "end_battery": end["battery"], "minimum_battery": min(s["battery"] for s in states),
        "end_distance_to_base": distance(end), "base_radius": replay["config"]["base_radius"],
        "death_tick": deaths[0]["tick"] if deaths else None,
        "death_distance_to_base": distance(deaths[0]) if deaths else None,
        "penultimate_distance_to_base": distance(states[-2]),
        "last_drive": last_drives[-1] if last_drives else None,
        "rejected_public_calls": len(errors),
        "rejected_call_tools": dict(Counter(row["tool"] for row in errors)),
        "last_generation_finish": finishes[-1] if finishes else None,
        "harbor_exception": (harbor.get("exception_info") or {}).get("exception_type"),
        "full_physics_and_grade_reproduced": True,
        "input_sha256": {str(path.relative_to(ROOT)): digest(path) for path in paths},
    }


def training_observations():
    folder = ROOT / "docs/lightlag-rl-results/modal/pilot-01/training"
    metadata = read(folder / "training.json")
    rows, hashes = [], {}
    for entry in metadata["metrics"]:
        path = folder / entry["artifact"]
        require(digest(path) == entry["sha256"], "changed training batch")
        hashes[str(path.relative_to(ROOT))] = digest(path)
        rows.extend(json.loads(gzip.decompress(path.read_bytes()))["rows"])
    equal_pairs = 0
    zero_pairs = 0
    opportunities = switches = before_eta = 0
    replanning_gaps, chosen_travel = [], []
    for left, right in zip(rows[::2], rows[1::2]):
        require(left["seed"] == right["seed"], "unpaired training rows")
        equal_pairs += left["reward"] == right["reward"]
        zero_pairs += left["reward"] == right["reward"] == 0
    for row in rows:
        previous = None
        for decision in row["trajectory"]:
            ids, features, action = decision["ids"], decision["features"], decision["action"]
            tick = (1 - features[0][1]) * 420
            goal, travel = ids[action], features[action][4] * 420
            if goal != "base":
                chosen_travel.append(travel)
            if previous is not None:
                prior, prior_tick, prior_eta = previous
                replanning_gaps.append(tick - prior_tick)
                if prior != "base" and prior in ids:
                    opportunities += 1
                    if goal != prior:
                        switches += 1
                        before_eta += tick < prior_eta
            previous = (goal, tick, tick + travel)
    return {
        "episodes": len(rows), "same_map_pairs": len(rows) // 2,
        "equal_reward_pairs": equal_pairs, "both_zero_reward_pairs": zero_pairs,
        "zero_reward_episodes": sum(row["reward"] == 0 for row in rows),
        "decisions": sum(len(row["trajectory"]) for row in rows),
        "previous_science_goal_still_available": opportunities,
        "switches_while_previous_available": switches,
        "switch_fraction": switches / opportunities,
        "switches_before_previous_estimated_arrival": before_eta,
        "before_estimated_arrival_fraction": before_eta / switches,
        "median_replanning_interval_ticks": statistics.median(replanning_gaps),
        "mean_selected_science_travel_ticks": statistics.mean(chosen_travel),
        "input_sha256": hashes,
        "limits": ["Recorded chooser intentions and public estimates, not proof of actual pursuit or cause.",
                   "Equal reward pairs have zero reward advantage; entropy gradients may remain.",
                   "All batches come from the completed single-seed run; no new training or cases."],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "output already exists; preserve the earlier review")
    folders = ROOT / "docs/lightlag-runs"
    names = sorted(path.name for path in folders.glob("traverse-agent-*"))
    names += ["traverse-reference", "traverse-do-nothing", "traverse-stop-early"]
    require(len(names) == len(set(names)), "duplicate run")
    results = [review_run(folders / name) for name in names]
    reference = next(row for row in results if row["run"] == "traverse-reference")
    require(reference["survival_factor"] == 1, "decomposition requires home reference")
    primary = [row for row in results if row["run"].startswith(("traverse-agent-opus-", "traverse-agent-sonnet-"))]
    for row in results:
        require(row["seed"] == reference["seed"] and row["max_available_value"] == reference["max_available_value"], "unmatched mission")
        row["sample_value_gap"] = reference["sampled_value"] - row["sampled_value"]
        row["terminal_factor_value_loss"] = row["sampled_value"] * (1 - row["survival_factor"])
        row["reference_reward_gap"] = reference["reward"] - row["reward"]
        require(math.isclose((row["sample_value_gap"] + row["terminal_factor_value_loss"]) / reference["max_available_value"],
                             row["reference_reward_gap"], abs_tol=1e-12), "gap accounting")
    source_files = sorted((ROOT / "lightlag_traverse").glob("*.py"))
    source_files += [ROOT / "lightlag_rl/adapter.py", ROOT / "lightlag_rl/model.py",
                     ROOT / "lightlag_rl/train.py", ROOT / "lightlag_rl_persistence/chooser.py",
                     Path(__file__).resolve()]
    report = {
        "schema": "reference-gap-review-v1",
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "scope": "retained artifacts only; no new check missions, training or model API requests",
        "sources_sha256": {str(p.relative_to(ROOT)): digest(p) for p in source_files},
        "runs": results,
        "opus_sonnet_summary": {
            "attempts": len(primary), "unique_missions": len({row["seed"] for row in primary}),
            "mean_reward": statistics.mean(row["reward"] for row in primary),
            "reference_reward": reference["reward"],
            "mean_gap": statistics.mean(row["reference_reward_gap"] for row in primary),
            "mean_sample_value_gap_scaled": statistics.mean(row["sample_value_gap"] / reference["max_available_value"] for row in primary),
            "mean_terminal_factor_loss_scaled": statistics.mean(row["terminal_factor_value_loss"] / reference["max_available_value"] for row in primary),
            "alive_home": sum(row["alive"] and row["at_base"] for row in primary),
            "terminal_penalty_runs": sum(row["survival_factor"] < 1 for row in primary),
            "all_agent_tool_calls_reach_horizon": all(row["last_agent_tool_tick"] == 420 for row in primary),
            "all_final_generation_reasons_stop": all(row["last_generation_finish"] == "stop" for row in primary),
            "all_have_harbor_exit_exception": all(row["harbor_exception"] for row in primary),
        },
        "training_observations": training_observations(),
        "limits": ["The score decomposition is arithmetic, not a counterfactual rescue or causal attribution.",
                   "One mission and a reference improved after early agent results; not a fresh gap confirmation.",
                   "All Harbor process-exit errors are retained; completing a mission does not explain their root cause.",
                   "Haiku output-length truncation is separate from completed Opus/Sonnet planning outcomes."],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(json.dumps({"runs_verified": len(results), **report["opus_sonnet_summary"]}, indent=2))


if __name__ == "__main__":
    main()
