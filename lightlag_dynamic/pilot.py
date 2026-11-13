"""Run the policy x profile x delay x seed matrix and print a summary table.

  python3 -m lightlag_dynamic.pilot                      # defaults: all profiles, delays 0 3, seeds 0-19
  python3 -m lightlag_dynamic.pilot --profiles dynamic --seeds 100-119 --out results.json
"""

import argparse
import json
from pathlib import Path
import statistics
import sys

from .controllers import POLICIES
from .missions import PROFILES
from .tools import run_episode


def parse_seeds(text):
    seeds = []
    for part in text.split(","):
        if "-" in part:
            lo, hi = part.split("-")
            seeds += range(int(lo), int(hi) + 1)
        else:
            seeds.append(int(part))
    if len(set(seeds)) != len(seeds):
        raise ValueError("duplicate seeds")
    return seeds


def run_matrix(profiles, delays, seeds, policies, horizon=None):
    runs = []
    for profile in profiles:
        for delay in delays:
            for seed in seeds:
                for name in policies:
                    run = run_episode(POLICIES[name], seed=seed, delay=delay, profile=profile,
                                      horizon=horizon, policy_name=name)
                    r = run["result"]
                    runs.append({"profile": profile, "delay": delay, "seed": seed, "policy": name,
                                 "score": r["raw_score"], "max": r["max_available_value"],
                                 "at_base": r["at_base"], "alive": r["alive"],
                                 "late": sum(not s["on_time"] for s in r["samples"]),
                                 "calls": run["public_calls"]})
    return runs


def summarize(runs):
    reference = {(r["profile"], r["delay"], r["seed"]): r["score"] for r in runs
                 if r["policy"] == "reference"}
    groups = {}
    for r in runs:
        groups.setdefault((r["profile"], r["delay"], r["policy"]), []).append(r)
    rows = []
    for (profile, delay, policy), group in groups.items():
        ratios = [r["score"] / reference[(profile, delay, r["seed"])] for r in group
                  if reference.get((profile, delay, r["seed"]), 0) > 0]
        rows.append({
            "profile": profile, "delay": delay, "policy": policy, "runs": len(group),
            "mean_score": statistics.mean(r["score"] for r in group),
            "share_of_max": statistics.mean(r["score"] / r["max"] for r in group),
            "vs_reference": statistics.mean(ratios) if ratios else None,
            "worse_than_ref": sum(r["score"] < reference.get((profile, delay, r["seed"]), 0) - 1e-9
                                  for r in group),
            "home_alive": sum(r["at_base"] and r["alive"] for r in group) / len(group),
            "dead": sum(not r["alive"] for r in group) / len(group),
            "late_samples": sum(r["late"] for r in group),
        })
    return rows


def print_table(rows, out=sys.stdout):
    print("| profile | delay | policy | mean score | share of max | vs reference | runs below ref "
          "| home & alive | dead | late samples |", file=out)
    print("|---|---|---|---|---|---|---|---|---|---|", file=out)
    for r in rows:
        vs = "n/a" if r["vs_reference"] is None else f"{r['vs_reference']:.2f}"
        print(f"| {r['profile']} | {r['delay']} | {r['policy']} | {r['mean_score']:.2f} "
              f"| {r['share_of_max']:.2f} | {vs} | {r['worse_than_ref']}/{r['runs']} "
              f"| {r['home_alive']:.0%} | {r['dead']:.0%} | {r['late_samples']} |", file=out)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--profiles", nargs="+", default=list(PROFILES), choices=list(PROFILES))
    parser.add_argument("--delays", nargs="+", type=int, default=[0, 3])
    parser.add_argument("--seeds", default="0-19", help="e.g. 0-19 or 1,5,9")
    parser.add_argument("--policies", nargs="+", default=list(POLICIES), choices=list(POLICIES))
    parser.add_argument("--ticks", type=int, default=None, help="horizon; default: each profile's own")
    parser.add_argument("--out", type=Path, help="write raw runs and summary to a new JSON file")
    args = parser.parse_args(argv)
    if "reference" not in args.policies:
        args.policies = ["reference"] + args.policies
    if args.out is not None and args.out.exists():
        parser.error("--out must be a new file")
    runs = run_matrix(args.profiles, args.delays, parse_seeds(args.seeds), args.policies, args.ticks)
    rows = summarize(runs)
    print_table(rows)
    if args.out is not None:
        with args.out.open("x", encoding="utf-8") as handle:
            json.dump({"config": vars(args) | {"out": str(args.out)}, "summary": rows, "runs": runs},
                      handle, indent=2, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
