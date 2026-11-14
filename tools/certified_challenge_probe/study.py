"""Run and retain every case, replayable plan, bound status and source hash."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
from statistics import mean
import time

from .model import VERSION, generate, verify
from .search import beam, compile_choices, exact, greedy


def run_case(seed, jobs, max_nodes):
    mission = generate(seed, jobs)
    choices = compile_choices(mission)
    runs = {}
    for name in ("value", "deadline", "density", "scarcity", "beam64", "reference"):
        started = time.perf_counter()
        if name == "reference":
            result = exact(mission, choices, max_nodes)
        elif name == "beam64":
            result = beam(mission, choices, 64)
        else:
            result = greedy(mission, choices, name)
        result["seconds"] = time.perf_counter() - started
        replay = verify(mission, result["plan"])
        if not replay["valid"] or replay["value"] != result["value"]:
            raise AssertionError((seed, name, replay))
        result["replay_valid"] = True
        runs[name] = result
    winner = max(("value", "deadline", "density", "scarcity"), key=lambda n: runs[n]["value"])
    runs["portfolio"] = {**runs[winner], "policy": winner,
                         "seconds": sum(runs[n]["seconds"] for n in ("value", "deadline", "density", "scarcity"))}
    return {"seed": seed, "jobs": jobs, "mission": mission,
            "candidate_count": sum(map(len, choices.values())), "runs": runs}


def summarize(cases):
    summaries = {}
    for size in sorted({case["jobs"] for case in cases}):
        group = [case for case in cases if case["jobs"] == size]
        certified = [c for c in group if c["runs"]["reference"]["proven_optimal"]]
        policies = {}
        for policy in group[0]["runs"]:
            ratios = [c["runs"][policy]["value"] / c["runs"]["reference"]["value"]
                      for c in certified if c["runs"]["reference"]["value"] > 0]
            policies[policy] = {
                "mean_raw_value_all_cases": mean(c["runs"][policy]["value"] for c in group),
                "mean_fraction_of_optimum_certified_nonzero": mean(ratios) if ratios else None,
                "optimal_cases_certified": sum(c["runs"][policy]["value"] == c["runs"]["reference"]["value"] for c in certified),
                "total_seconds": sum(c["runs"][policy]["seconds"] for c in group),
            }
        summaries[str(size)] = {
            "cases": len(group), "certified": len(certified),
            "uncertified_seeds": [c["seed"] for c in group if not c["runs"]["reference"]["proven_optimal"]],
            "zero_optimum_cases": sum(c["runs"]["reference"]["value"] == 0 for c in certified),
            "all_replays_valid": all(r["replay_valid"] for c in group for r in c["runs"].values()),
            "maximum_reference_nodes": max(c["runs"]["reference"]["nodes"] for c in group),
            "policies": policies,
        }
    return summaries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("development", "check"), required=True)
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--count", type=int, required=True)
    parser.add_argument("--jobs", type=int, nargs="+", default=[8, 12])
    parser.add_argument("--max-nodes", type=int, default=250_000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.count < 1 or args.max_nodes < 1:
        parser.error("count and max-nodes must be positive")
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(Path(__file__).parent.glob("*.py"))}
    report = {"version": VERSION, "split": args.split, "python": platform.python_version(),
              "source_sha256": hashes, "configuration": {k: v for k, v in vars(args).items() if k != "output"},
              "model_calls": 0, "cases": []}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for jobs in args.jobs:
        for seed in range(args.start, args.start + args.count):
            result = run_case(seed, jobs, args.max_nodes)
            report["cases"].append(result)
            print(json.dumps({"jobs": jobs, "seed": seed, "reference": result["runs"]["reference"]["value"],
                              "certified": result["runs"]["reference"]["proven_optimal"],
                              "beam64": result["runs"]["beam64"]["value"]}), flush=True)
            # Retain completed work even if a later case interrupts the run.
            args.output.write_text(json.dumps(report, indent=2) + "\n")
    report["summary"] = summarize(report["cases"])
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
