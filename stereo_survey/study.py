"""Retained stereo/monocular comparison; no model calls or case filtering."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
from statistics import mean
import time

from .mission import PROFILES, VERSION, generate
from .search import Problem, beam, exact, greedy
from .verify import verify


def evaluate(mission, objective, max_local, max_joint):
    started = time.perf_counter()
    problem = Problem(mission)
    compilation = time.perf_counter() - started
    runs = {}
    policies = {
        "mono_greedy": lambda: greedy(problem, objective, units="images"),
        "pair_greedy": lambda: greedy(problem, objective),
        "pair_density": lambda: greedy(problem, objective, density=True),
        "image_beam64": lambda: beam(problem, objective, units="images"),
        "pair_beam64": lambda: beam(problem, objective),
        "reference": lambda: exact(problem, objective, max_local, max_joint),
    }
    for name, run in policies.items():
        started = time.perf_counter()
        result = run()
        result["seconds"] = time.perf_counter() - started
        replay = verify(mission, result["plan"], objective)
        if not replay["valid"] or result["science"] != replay["science"]:
            raise AssertionError((name, objective, result, replay))
        result.pop("mask", None)
        result["replay_valid"] = True
        result["covered_cells"] = replay["covered_cells"]
        result["valid_pairs"] = len(replay["products"])
        runs[name] = result
    for name, members in (("greedy_portfolio", ("mono_greedy", "pair_greedy", "pair_density")),
                          ("beam_portfolio", ("image_beam64", "pair_beam64"))):
        winner = max(members, key=lambda key: runs[key]["science"])
        runs[name] = {**runs[winner], "selected_policy": winner,
                      "seconds": sum(runs[key]["seconds"] for key in members)}
    return {"compilation_seconds": compilation, "runs": runs}


def summarize(cases):
    summary = {}
    for profile in sorted({case["profile"] for case in cases}):
        group = [case for case in cases if case["profile"] == profile]
        summary[profile] = {}
        for objective in ("stereo", "mono"):
            certified = [case for case in group if case[objective]["runs"]["reference"]["proven_optimal"]]
            nonzero = [case for case in certified if case[objective]["runs"]["reference"]["science"] > 0]
            policies = {}
            for policy in group[0][objective]["runs"]:
                ratios = [case[objective]["runs"][policy]["science"] / case[objective]["runs"]["reference"]["science"] for case in nonzero]
                policies[policy] = {
                    "mean_science_all_cases": mean(case[objective]["runs"][policy]["science"] for case in group),
                    "mean_fraction_of_optimum_certified_nonzero": mean(ratios) if ratios else None,
                    "optimal_cases_certified": sum(case[objective]["runs"][policy]["science"] == case[objective]["runs"]["reference"]["science"] for case in certified),
                    "total_seconds": sum(case[objective]["runs"][policy]["seconds"] for case in group),
                }
            summary[profile][objective] = {
                "cases": len(group), "certified": len(certified), "nonzero_optima": len(nonzero),
                "uncertified_seeds": [case["seed"] for case in group if not case[objective]["runs"]["reference"]["proven_optimal"]],
                "all_replays_valid": all(run["replay_valid"] for case in group for run in case[objective]["runs"].values()),
                "max_joint_evaluations": max(case[objective]["runs"]["reference"]["joint_evaluations"] for case in group),
                "policies": policies,
            }
        stereo = summary[profile]["stereo"]
        stereo["free_gate_passed"] = (
            stereo["certified"] == stereo["cases"] == stereo["nonzero_optima"]
            and stereo["all_replays_valid"]
            and stereo["policies"]["greedy_portfolio"]["mean_fraction_of_optimum_certified_nonzero"] <= 0.90
            and stereo["policies"]["beam_portfolio"]["mean_fraction_of_optimum_certified_nonzero"] <= 0.95
        )
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("development", "check"), required=True)
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--count", type=int, required=True)
    parser.add_argument("--profiles", choices=PROFILES, nargs="+", default=list(PROFILES))
    parser.add_argument("--max-local", type=int, default=10_000)
    parser.add_argument("--max-joint", type=int, default=2_000_000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if min(args.count, args.max_local, args.max_joint) < 1:
        parser.error("count and search limits must be positive")
    report = {
        "version": VERSION, "split": args.split, "python": platform.python_version(),
        "configuration": {key: value for key, value in vars(args).items() if key != "output"},
        "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(__file__).parent.glob("*.py"))},
        "model_calls": 0, "cases": [],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for profile in args.profiles:
        for seed in range(args.start, args.start + args.count):
            mission = generate(seed, profile)
            case = {"seed": seed, "profile": profile, "mission": mission}
            for objective in ("stereo", "mono"):
                case[objective] = evaluate(mission, objective, args.max_local, args.max_joint)
            report["cases"].append(case)
            print(json.dumps({"profile": profile, "seed": seed,
                              "reference": case["stereo"]["runs"]["reference"]["science"],
                              "certified": case["stereo"]["runs"]["reference"]["proven_optimal"],
                              "greedy": case["stereo"]["runs"]["greedy_portfolio"]["science"],
                              "beam": case["stereo"]["runs"]["beam_portfolio"]["science"]}), flush=True)
            args.output.write_text(json.dumps(report, indent=2) + "\n")
    report["summary"] = summarize(report["cases"])
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
