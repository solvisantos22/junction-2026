"""Read-only, all-seed staging decisions from retained final-version learning evidence."""

import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path


SEEDS = (17, 29, 43)
ALGORITHMS = ("ppo", "replay")
MAPS = list(range(81000, 81032))
STAGES = {"fit": (8192, (0, 512, 2048, 8192), .01)}
EXPERIMENT = "learning-final-20261114"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path = Path(path)
    data = path.read_bytes()
    return json.loads(gzip.decompress(data) if path.suffix == ".gz" else data)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def valid_hash(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def same_summary(stored, calculated):
    require(set(stored) == set(calculated), "validation summary fields differ")
    for key, value in calculated.items():
        require(isinstance(stored[key], (int, float)) and math.isfinite(stored[key])
                and math.isclose(stored[key], value, rel_tol=1e-12, abs_tol=1e-12),
                f"validation summary mismatch: {key}")


def validation(directory, milestone, algorithm, seed, report_summary):
    filename = f"validation-{milestone:05d}.json.gz"
    policy_name = f"policy-{milestone:05d}.json"
    data, policy = read(directory / filename), read(directory / policy_name)
    require(data["schema"] == "learning-validation-v1" and data["episodes_completed"] == milestone,
            "validation milestone differs")
    require(data["maps"] == MAPS and len(data["episodes"]) == 32
            and [e["seed"] for e in data["episodes"]] == MAPS, "validation must contain all 32 fixed maps exactly once")
    require(data["policy_sha256"] == digest(directory / policy_name), "validation policy hash differs")
    require(policy["schema"] == "lightlag-learning-policy-v1" and policy["algorithm"] == algorithm
            and policy["episodes_seen"] == milestone, "validation policy identity differs")
    require((policy["model"]["candidate_dim"], policy["model"]["global_dim"], policy["model"]["hidden"]) == (20, 14, 64),
            "policy architecture differs")
    require(policy["config"]["gamma"] == 1 and policy["config"]["schedule_episodes"] == 2048,
            "policy objective or exploration schedule differs")
    rewards, homes, alive, invalid, decisions = [], 0, 0, 0, []
    for index, episode in enumerate(data["episodes"]):
        result = episode["result"]
        require(result["tick"] == 420 and type(result["alive"]) is bool and type(result["at_base"]) is bool,
                "validation episode is incomplete")
        require(episode["action_seed"] == seed * 1_000_000_000 + index, "validation action seed differs")
        maximum, raw, reward = result["max_available_value"], result["raw_score"], episode["reward"]
        require(all(math.isfinite(value) for value in (maximum, raw, reward)) and maximum > 0
                and 0 <= reward <= 1 and reward == raw / maximum, "validation reward arithmetic differs")
        require(isinstance(episode["invalid_calls"], list) and type(episode["decision_count"]) is int
                and episode["decision_count"] >= 0, "validation counts are invalid")
        rewards.append(reward)
        homes += result["at_base"]
        alive += result["alive"]
        invalid += len(episode["invalid_calls"])
        decisions.append(episode["decision_count"])
    summary = {"count": 32, "mean_reward": sum(rewards) / 32, "home": homes, "alive": alive,
               "invalid_calls": invalid, "mean_decisions": sum(decisions) / 32}
    same_summary(data["summary"], summary)
    if report_summary is not None:
        same_summary(report_summary, summary)
    return {**summary, "deaths": 32 - alive, "filename": filename, "sha256": digest(directory / filename),
            "policy_filename": policy_name, "policy_sha256": digest(directory / policy_name)}, policy["config"]


def inspect_run(directory, stage):
    directory = Path(directory).resolve()
    report = read(directory / "report.json")
    target, milestones, _ = STAGES[stage]
    require(report["schema"] == "learning-training-report-v1" and report["smoke"] is False
            and report.get("experiment") == EXPERIMENT,
            "a production training report is required")
    require(report["algorithm"] in ALGORITHMS and type(report["seed"]) is int and report["seed"] in SEEDS,
            "undeclared algorithm or initialization seed")
    require(report["episodes_target"] == target and report["batch_episodes"] == 32
            and report["schedule_episodes"] == 2048, "report target or schedule differs")
    completed = report["episodes_completed"]
    require(type(completed) is int and 0 <= completed <= target and completed % 32 == 0,
            "invalid completed episode count")
    require(report["status"] in ("complete", "deadline", "failed", "running"), "unknown run status")
    require(report["status"] != "complete" or completed == target, "complete report lacks target episodes")
    require(len(report["history"]) == completed // 32, "training history count is incomplete")
    for index, entry in enumerate(report["history"]):
        require(entry["first_episode"] == index * 32 and entry["last_episode"] == (index + 1) * 32
                and entry["count"] == 32 and valid_hash(entry["sha256"]), "training history is not contiguous")
    pins = report["source_sha256"]
    require(isinstance(pins, dict) and "docs/learning-final.md" in pins and "lightlag_learning_final/train.py" in pins
            and all(valid_hash(value) for value in pins.values()), "invalid source manifest")
    require(set(report["validations"]) <= {str(m) for m in milestones}, "undeclared validation milestone")
    retained, configs = {}, []
    for milestone in milestones:
        path = directory / f"validation-{milestone:05d}.json.gz"
        exists, listed = path.exists(), str(milestone) in report["validations"]
        require(not listed or exists, "reported validation artifact is missing")
        if exists:
            require(milestone <= completed, "validation precedes the recorded training state")
            details, config = validation(directory, milestone, report["algorithm"], report["seed"],
                                          report["validations"].get(str(milestone)))
            retained[str(milestone)] = details
            configs.append(config)
        if report["status"] == "complete":
            require(exists and listed, "complete run is missing a declared validation")
    require(not configs or all(config == configs[0] for config in configs), "learner configuration changes across milestones")
    for path in directory.glob("validation-*.json.gz"):
        require(path.name in {f"validation-{m:05d}.json.gz" for m in milestones}, "undeclared validation file")
    baseline = 2048
    available = str(target) in retained and str(baseline) in retained
    gain = retained[str(target)]["mean_reward"] - retained[str(baseline)]["mean_reward"] if available else None
    return {"algorithm": report["algorithm"], "seed": report["seed"], "directory": str(directory),
            "report_sha256": digest(directory / "report.json"), "status": report["status"],
            "episodes_completed": completed, "complete": report["status"] == "complete" and completed == target,
            "validations": retained, "gain": gain,
            "initial_gain": retained[str(target)]["mean_reward"] - retained["0"]["mean_reward"] if str(target) in retained and "0" in retained else None, "source_sha256": pins,
            "runtime": {key: report[key] for key in ("python", "numpy", "torch")},
            "learner_config": configs[0] if configs else None}


def decide(run_directories, stage, previous_decision=None):
    """Validate saved evidence and return a decision; never run or modify a policy."""
    require(stage == "fit", "only the fit stage has a continuation decision")
    require(previous_decision is None, "fit does not consume an old campaign decision")
    expected_algorithms = set(ALGORITHMS)
    runs = [inspect_run(directory, stage) for directory in run_directories]
    identities = [(run["algorithm"], run["seed"]) for run in runs]
    expected = {(algorithm, seed) for algorithm in expected_algorithms for seed in SEEDS}
    require(len(identities) == len(expected) and set(identities) == expected,
            "all three seeds of every required algorithm must be supplied exactly once")
    first = runs[0]
    require(all(run["source_sha256"] == first["source_sha256"] and run["runtime"] == first["runtime"] for run in runs),
            "source or runtime differs across runs")
    configs = [run["learner_config"] for run in runs if run["learner_config"] is not None]
    require(not configs or all(config == configs[0] for config in configs), "learner configuration differs across runs")
    algorithms = {}
    for algorithm in sorted(expected_algorithms):
        group = sorted((run for run in runs if run["algorithm"] == algorithm), key=lambda run: run["seed"])
        complete = all(run["complete"] for run in group)
        gains = [run["gain"] for run in group]
        mean_gain = sum(gains) / 3 if all(gain is not None for gain in gains) else None
        initial_gains = [run["initial_gain"] for run in group]
        initial_mean = sum(initial_gains) / 3 if all(gain is not None for gain in initial_gains) else None
        positive = sum(gain is not None and gain > 0 for gain in gains)
        deaths = sum(v["deaths"] for run in group for v in run["validations"].values())
        invalid = sum(v["invalid_calls"] for run in group for v in run["validations"].values())
        reasons = []
        if not complete: reasons.append("one_or_more_runs_incomplete")
        if mean_gain is None or mean_gain < STAGES[stage][2]: reasons.append("mean_gain_below_threshold")
        if initial_mean is None or initial_mean < .03: reasons.append("mean_initial_gain_below_threshold")
        if positive < 2: reasons.append("fewer_than_two_positive_initializations")
        if deaths: reasons.append("validation_deaths")
        if invalid: reasons.append("validation_invalid_calls")
        algorithms[algorithm] = {"eligible": not reasons, "reasons": reasons, "mean_gain": mean_gain,
                                 "mean_initial_gain": initial_mean, "positive_initializations": positive, "validation_deaths": deaths,
                                 "validation_invalid_calls": invalid,
                                 "seeds": [{k: v for k, v in run.items() if k not in ("source_sha256", "runtime", "learner_config")}
                                           for run in group]}
    return {"schema": "learning-final-stage-decision-v1", "experiment": EXPERIMENT, "stage": stage,
            "episodes_target": STAGES[stage][0], "minimum_mean_gain": STAGES[stage][2], "minimum_mean_initial_gain": .03,
            "validation_maps": MAPS, "initialization_seeds": list(SEEDS),
            "source_sha256": first["source_sha256"], "runtime": first["runtime"],
            "learner_config": configs[0] if configs else None,
            "decision_tool_sha256": digest(__file__),
            "previous_decision_sha256": digest(previous_decision) if previous_decision else None,
            "algorithms": algorithms, "eligible_algorithms": [name for name, result in algorithms.items() if result["eligible"]],
            "limit": "Staging on reused validation maps, not a generalization result. Checks recorded grades, summaries, policy hashes and source/runtime consistency; does not replay physics, batch artifacts or optimizer updates. No cloud launch or spend authorization."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", nargs="+", type=Path)
    parser.add_argument("--stage", choices=tuple(STAGES), required=True)
    parser.add_argument("--previous-decision", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = decide(args.runs, args.stage, args.previous_decision)
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"stage": args.stage, "eligible_algorithms": result["eligible_algorithms"]}))


if __name__ == "__main__":
    main()
