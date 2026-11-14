#!/usr/bin/env python3
"""How often does a player beat a designated controller? From the Traverse farm's saved rows.

    python3 tools/second_machine_check/outperform.py                 # both tables
    python3 tools/second_machine_check/outperform.py --json out.json

Two comparisons, each on worlds every player played (paired):

  normal map, fresh worlds 600-899   every saved Claude program against the reference pilot
  MAX map, fresh worlds 600-699      every one-request Claude program against manh_max

Per world: wins, ties, losses and the largest win. Per campaign: 200,000 random groups of three
worlds, each scored as the campaign task scores three missions (value earned in all three over
the value there was in all three). "BEST of all Claude programs" takes, on every world, the
highest score any saved Claude program reached there: hindsight no single program has.

The rows are the farm's (docs/traverse-farm/, played on Modal by Kristján's farm session); this
only reads them. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

REPO = Path(__file__).resolve().parent.parent.parent
FARM = REPO / "docs" / "traverse-farm"
GROUPS = 200000
BEST = "BEST of all Claude programs, per world (hindsight)"


def load(folder: str) -> Dict[str, Dict[int, Dict[str, Any]]]:
    """player -> world -> row. A pilot with other options is its own player."""
    by: Dict[str, Dict[int, Dict[str, Any]]] = {}
    for line in (FARM / folder / "rows.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        key = row["policy"] if row["policy"] != "program" else row["candidate"]
        if row.get("options"):
            key += " " + json.dumps(row["options"], sort_keys=True)
        by.setdefault(key, {})[row["seed"]] = row
    return by


def campaign(rows: Dict[int, Dict[str, Any]], group: Sequence[int]) -> float:
    return sum(rows[seed]["raw_score"] for seed in group) / sum(rows[seed]["max_value"] for seed in group)


def compare(title: str, by: Dict[str, Dict[int, Dict[str, Any]]], base: str, others: Sequence[str],
            envelope: Sequence[str], rng: random.Random) -> List[Dict[str, Any]]:
    ref = by[base]
    seeds = sorted(ref)
    groups = [rng.sample(seeds, 3) for _ in range(GROUPS)]
    table = {name: by[name] for name in others if name in by}
    if envelope:
        table[BEST] = {seed: max((by[name][seed] for name in envelope if seed in by[name]), key=lambda row: row["reward"])
                       for seed in seeds}
    print("\n== {}: {} worlds; {} scores {:.3f}, loses {} rovers, ends away from the lander on {}".format(
        title, len(seeds), base, sum(ref[seed]["reward"] for seed in seeds) / len(seeds),
        sum(not ref[seed]["alive"] for seed in seeds),
        sum(ref[seed]["alive"] and not ref[seed]["at_base"] for seed in seeds)))
    print("{:<60} {:>6} {:>13} {:>8} {:>9} {:>12} {:>9}".format(
        "player", "mean", "win/tie/loss", "worlds", "best win", "campaigns", "best"))
    out = []
    for name, rows in table.items():
        common = [seed for seed in seeds if seed in rows]
        diffs = [rows[seed]["reward"] - ref[seed]["reward"] for seed in common]
        wins = sum(diff > 1e-12 for diff in diffs)
        ties = sum(abs(diff) <= 1e-12 for diff in diffs)
        played = [group for group in groups if all(seed in rows for seed in group)]
        gaps = [campaign(rows, group) - campaign(ref, group) for group in played]
        row = {"comparison": title, "baseline": base, "player": name, "worlds": len(common),
               "mean": sum(rows[seed]["reward"] for seed in common) / len(common),
               "wins": wins, "ties": ties, "losses": len(diffs) - wins - ties, "best_world_win": max(diffs),
               "campaign_win_share": sum(gap > 1e-12 for gap in gaps) / len(gaps), "best_campaign_win": max(gaps)}
        out.append(row)
        print("{:<60} {:>6.3f} {:>13} {:>7.1f}% {:>+9.3f} {:>11.2f}% {:>+9.3f}".format(
            name[:60], row["mean"], "{}/{}/{}".format(wins, ties, row["losses"]), 100.0 * wins / len(diffs),
            row["best_world_win"], 100.0 * row["campaign_win_share"], row["best_campaign_win"]))
    return out


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args(argv)
    rng = random.Random(20261114)
    normal = load("programs-1")
    for key, rows in load("classic-fresh").items():        # the controller ladder, on the same worlds
        normal.setdefault(key, rows)
    claude = [key for key in normal if key.startswith(("program:", "agent:"))]
    variants = [key for key in normal if key.startswith("pilot {")]
    rows = compare("Normal map, fresh worlds 600-899, against the reference pilot", normal, "pilot",
                   claude + variants + ["greedy", "straight"], claude, rng)
    hard = load("max-fresh")
    claude_max = [key for key in hard if key.startswith("program:")]
    rows += compare("MAX map, fresh worlds 600-699, against manh_max", hard, "manh_max", claude_max + ["pilot"],
                    claude_max, rng)
    if args.json:
        args.json.write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
