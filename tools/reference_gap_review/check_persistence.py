"""Independently recalculate the published persistence table and primary gate."""

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import statistics

import numpy as np


ROOT = Path(__file__).resolve().parents[2]


def check():
    path = ROOT / "docs/lightlag-rl-persistence-results/development/report.json"
    report = json.loads(path.read_text())
    if report["complete"] is not True or report["smoke"] is not False:
        raise ValueError("expected completed production diagnostic")
    rows = report["cases"]
    maps = sorted({row["seed"] for row in rows})
    if len(maps) != 24 or len(rows) != 240:
        raise ValueError("wrong diagnostic case count")
    table, paired_returns = {}, {}
    for policy in ("initial", "final", "greedy"):
        draws = 1 if policy == "greedy" else 2
        table[policy] = {}
        pairs = {}
        for mode in ("frequent", "persistent"):
            selected = [r for r in rows if r["policy"] == policy and r["mode"] == mode]
            identity = {(r["seed"], r["draw"]): r for r in selected}
            expected = {(seed, draw) for seed in maps for draw in range(draws)}
            if len(selected) != len(expected) or set(identity) != expected:
                raise ValueError("missing or duplicate policy case")
            summary = {
                "n": len(selected), "mean_reward": statistics.mean(r["reward"] for r in selected),
                "alive_home": sum(r["alive"] and r["at_base"] for r in selected),
                "deaths": sum(not r["alive"] for r in selected),
                "invalid_calls": sum(r["invalid_calls"] for r in selected),
            }
            for name, value in summary.items():
                if not math.isclose(value, report["summary"]["policies"][policy][mode][name], abs_tol=1e-12):
                    raise ValueError("published summary mismatch")
            table[policy][mode] = summary
            pairs[mode] = identity
        transitions = Counter()
        for key in expected:
            old, new = pairs["frequent"][key], pairs["persistent"][key]
            a, b = old["alive"] and old["at_base"], new["alive"] and new["at_base"]
            transitions[f"{'home' if a else 'away'}_to_{'home' if b else 'away'}"] += 1
        paired_returns[policy] = dict(sorted(transitions.items()))
    differences = []
    for seed in maps:
        means = {mode: statistics.mean(r["reward"] for r in rows
                                       if r["policy"] == "initial" and r["mode"] == mode and r["seed"] == seed)
                 for mode in ("frequent", "persistent")}
        differences.append(means["persistent"] - means["frequent"])
    indices = np.random.default_rng(17).integers(0, len(maps), size=(10000, len(maps)))
    interval = np.quantile(np.asarray(differences)[indices].mean(axis=1), [0.025, 0.975]).tolist()
    gain = statistics.mean(differences)
    if not math.isclose(gain, report["summary"]["primary"]["mean_paired_gain"], abs_tol=1e-12):
        raise ValueError("primary gain mismatch")
    if not np.allclose(interval, report["summary"]["primary"]["bootstrap_95_percentile"], atol=1e-12, rtol=0):
        raise ValueError("primary interval mismatch")
    a, b = table["initial"]["frequent"], table["initial"]["persistent"]
    gates = {"gain_at_least_03": gain >= .03, "bootstrap_lower_positive": interval[0] > 0,
             "home_no_more_than_two_lower": b["alive_home"] >= a["alive_home"] - 2,
             "no_increased_deaths": b["deaths"] <= a["deaths"],
             "no_increased_invalid_calls": b["invalid_calls"] <= a["invalid_calls"]}
    if gates != report["summary"]["gate"] or all(gates.values()) != report["summary"]["screen_passes"]:
        raise ValueError("published gates mismatch")
    hashed = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    return {
        "schema": "reference-gap-persistence-summary-v1", "report_sha256": hashed(path),
        "reviewer_source_sha256": hashed(Path(__file__)), "table": table,
        "matched_home_transitions": paired_returns, "maps": maps,
        "primary_gain": gain, "primary_95_interval": interval,
        "primary_positive_maps": sum(value > 0 for value in differences),
        "gates": gates, "screen_passes": all(gates.values()),
        "limits": ["Reused development maps, fixed weights; not new learning or held-out generalization.",
                   "Home transitions are paired descriptive outcomes, not causal attribution or a population decline claim.",
                   "This script verifies retained row summaries; the separate persistence auditor checks full physics and choices."],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("preserve existing output")
    report = check()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"gain": report["primary_gain"], "gate_passes": report["screen_passes"],
                      "home_transitions": report["matched_home_transitions"]}, indent=2))


if __name__ == "__main__":
    main()
