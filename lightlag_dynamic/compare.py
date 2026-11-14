"""Compare the three team references, plus baselines, on the same seeds and profiles.

  python3 -m lightlag_dynamic.compare        # static noisy rush rush_noisy, delays 0 3, seeds 300-319
  python3 -m lightlag_dynamic.compare --profiles noisy --delays 0 3 5 --seeds 300-339 --out c.json
  python3 -m lightlag_dynamic.compare --profiles rush_noisy --noise-level 1.5 --bumpiness 0.1

References (each team member's, imported unchanged):
  solvi_reference     lightlag/controllers/reference.py: conservative, greedy, worst-case budgets
  kristjan_reference  lightlag_controllers REFERENCE: adaptive, exact route search, probes slip
  kf_mpc              lightlag_dynamic/kf_mpc.py: Kalman filter + receding horizon, chance constraints
Context:
  naive_reference     this pilot's first reference: kf_mpc's planner, but trusts every fix as exact
  blind               plans once from the briefing, never reads telemetry
  cautious            sends a whole leg, then waits to see it land
  do_nothing          sends nothing

"vs best reference" divides each score by the best of the three references on the same
seed, profile and delay, so no single reference is the yardstick.
"""

import argparse
import json
from pathlib import Path
import statistics
import sys

from lightlag.controllers import POLICIES as SOLVI_POLICIES
from lightlag_controllers import REFERENCE, as_policy

from .controllers import POLICIES
from .pilot import parse_seeds
from .tools import run_episode

REFERENCES = ("solvi_reference", "kristjan_reference", "kf_mpc")
POLICY_TABLE = {
    "solvi_reference": SOLVI_POLICIES["reference"],
    "kristjan_reference": as_policy(REFERENCE),
    "kf_mpc": POLICIES["kf_mpc"],
    "naive_reference": POLICIES["reference"],
    "blind": POLICIES["open_loop"],
    "cautious": POLICIES["leg_and_wait"],
    "do_nothing": POLICIES["do_nothing"],
}
DEFAULT_PROFILES = ("static", "noisy", "rush", "rush_noisy")


def run_compare(profiles, delays, seeds, policies, noise_level=1.0, bumpiness=0.0):
    rows = []
    for profile in profiles:
        for delay in delays:
            for seed in seeds:
                for name in policies:
                    run = run_episode(POLICY_TABLE[name], seed=seed, delay=delay, profile=profile,
                                      policy_name=name, noise_level=noise_level, bumpiness=bumpiness)
                    r = run["result"]
                    rows.append({"profile": profile, "delay": delay, "seed": seed, "policy": name,
                                 "score": r["raw_score"], "max": r["max_available_value"],
                                 "home_alive": bool(r["at_base"] and r["alive"]),
                                 "dead": not r["alive"]})
    return rows


def summarize(rows):
    best = {}
    for r in rows:
        if r["policy"] in REFERENCES:
            key = (r["profile"], r["delay"], r["seed"])
            best[key] = max(best.get(key, 0.0), r["score"])
    groups = {}
    for r in rows:
        groups.setdefault((r["profile"], r["delay"], r["policy"]), []).append(r)
    table = []
    for (profile, delay, policy), group in groups.items():
        ratios = [r["score"] / best[(profile, delay, r["seed"])] for r in group
                  if best.get((profile, delay, r["seed"]), 0) > 0]
        table.append({
            "profile": profile, "delay": delay, "policy": policy, "runs": len(group),
            "mean_score": statistics.mean(r["score"] for r in group),
            "share_of_max": statistics.mean(r["score"] / r["max"] for r in group),
            "vs_best_reference": statistics.mean(ratios) if ratios else None,
            "home_alive": sum(r["home_alive"] for r in group) / len(group),
            "dead": sum(r["dead"] for r in group) / len(group),
        })
    return table


def print_table(table, out=sys.stdout):
    print("| profile | delay | policy | mean score | share of max | vs best reference "
          "| home & alive | dead |", file=out)
    print("|---|---|---|---|---|---|---|---|", file=out)
    for t in table:
        vs = "-" if t["vs_best_reference"] is None else f"{t['vs_best_reference']:.0%}"
        print(f"| {t['profile']} | {t['delay']} | {t['policy']} | {t['mean_score']:.2f} "
              f"| {t['share_of_max']:.0%} | {vs} | {t['home_alive']:.0%} | {t['dead']:.0%} |", file=out)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--profiles", nargs="+", default=list(DEFAULT_PROFILES))
    parser.add_argument("--delays", nargs="+", type=int, default=[0, 3])
    parser.add_argument("--seeds", default="300-319")
    parser.add_argument("--policies", nargs="+", default=list(POLICY_TABLE), choices=list(POLICY_TABLE))
    parser.add_argument("--noise-level", type=float, default=1.0,
                        help="multiplies the sensing noise and drift of the noisy profiles")
    parser.add_argument("--bumpiness", type=float, default=0.0,
                        help="experimental: share of rough cells that can spin the wheels")
    parser.add_argument("--out", help="write every episode row and the summary as JSON")
    args = parser.parse_args(argv)
    rows = run_compare(args.profiles, args.delays, parse_seeds(args.seeds), args.policies,
                       args.noise_level, args.bumpiness)
    table = summarize(rows)
    print_table(table)
    if args.out:
        Path(args.out).write_text(json.dumps({"rows": rows, "summary": table}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
