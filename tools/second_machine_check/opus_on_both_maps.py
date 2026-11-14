#!/usr/bin/env python3
"""The same Claude programs on both maps: who loses what to the MAX rules, and how close they come to the reference.

    python3 tools/second_machine_check/opus_on_both_maps.py table                      # the tables, from the saved rows
    python3 tools/second_machine_check/opus_on_both_maps.py play --seeds 600-629       # play the missing missions (sandbox)
    python3 tools/second_machine_check/opus_on_both_maps.py judged <new-folder>        # worlds 2026-2029, both maps

Manh asked why Claude's Opus programs come so close to `manh_max` on the MAX map when the
reference is far ahead of Claude on the normal map. The two comparisons used different programs:
the normal-map one an older one-request program, the MAX one the four programs written from the
frozen MAX request (docs/lightlag-runs/max-baseline/replies/ and replies-manh/). This plays those
four on the NORMAL map as well, on fresh worlds the farm already used for comparisons, so every
player has a score on both maps on the same worlds:

  normal map   reference pilot, older Opus program: the farm's rows (docs/traverse-farm/programs-1)
               the four MAX-written Opus programs:   played here, in the bubblewrap sandbox
  MAX map      manh_max, Kristján's three programs:  the farm's rows (docs/traverse-farm/max-fresh)
               Manh's-key Opus 1:                    played here

Model-written programs run only in the sandbox (lightlag_traverse_max/sandbox.py: no network,
read-only files, user nobody). Three of the four programs plan against the wall clock, so their
scores shift a little with the machine and its load. Nothing here trains or tunes anything.
Rows: docs/second-machine-check/opus-both-maps.jsonl and opus-judged-worlds.json.
"""

from __future__ import annotations

import argparse
import itertools
import json
import statistics
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))

FARM = REPO / "docs" / "traverse-farm"
BASELINE = REPO / "docs" / "lightlag-runs" / "max-baseline"
ROWS = REPO / "docs" / "second-machine-check" / "opus-both-maps.jsonl"
PROGRAMS = {
    "K-opus-1": BASELINE / "replies" / "opus-1" / "policy.py",          # K: Kristján's key
    "K-opus-2": BASELINE / "replies" / "opus-2" / "policy.py",
    "K-opus-3": BASELINE / "replies" / "opus-3" / "policy.py",
    "M-opus-1": BASELINE / "replies-manh" / "opus-1" / "policy.py",     # M: Manh's key
}
LABELS = {"K-opus-1": "Opus 1, Kristján's key", "K-opus-2": "Opus 2, Kristján's key",
          "K-opus-3": "Opus 3, Kristján's key", "M-opus-1": "Opus 1, Manh's key"}
REFERENCE = "reference pilot (normal) / manh_max (MAX)"
OLDER = "older Opus one-request program"
JUDGED = (2026, 2027, 2028, 2029)


def play_one(job: Tuple[str, int, str, Optional[str]]) -> Dict[str, Any]:
    """One mission in the sandbox. With `keep`, the evaluator's files stay in that folder."""
    name, seed, option, keep = job
    from lightlag_traverse_max.sandbox import run
    with tempfile.TemporaryDirectory(prefix="opus-both-maps-") as scratch:
        folder = Path(keep) if keep else Path(scratch)
        summary = run(PROGRAMS[name], folder, seed, option)
        result = json.loads((folder / "artifacts" / "evaluator" / "result.json").read_text(encoding="utf-8"))
    return {"program": name, "seed": seed, "map": option, "reward": summary["reward"], "samples": summary["samples"],
            "alive": summary["alive"], "at_base": summary["at_base"], "status": summary["status"],
            "errors": (summary["errors"] or [""])[0][:160], "seconds": summary["seconds"],
            "raw_score": result["raw_score"], "sampled_value": result["sampled_value"],
            "max_value": result["max_available_value"]}


def play(rows_file: Path, seeds: Sequence[int], workers: int) -> None:
    """The four programs on the normal map and Manh's-key Opus 1 on the MAX map; skips missions already saved."""
    done = set()
    if rows_file.exists():
        done = {(r["program"], r["seed"], r["map"]) for r in map(json.loads, rows_file.read_text().splitlines())}
    jobs = [(name, seed, "normal", None) for name in PROGRAMS for seed in seeds]
    jobs += [("M-opus-1", seed, "max", None) for seed in seeds]
    jobs = [job for job in jobs if job[:3] not in done]
    rows_file.parent.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(workers) as pool, rows_file.open("a", encoding="utf-8") as handle:
        for future in as_completed([pool.submit(play_one, job) for job in jobs]):
            handle.write(json.dumps(future.result()) + "\n")
            handle.flush()
    print("played {} missions into {}".format(len(jobs), rows_file))


def judged(out: Path, workers: int) -> List[Dict[str, Any]]:
    """The four programs on Kristján's worlds 2026-2029, both maps, the evaluator's files kept."""
    out.mkdir(parents=True)
    jobs = [(name, seed, option, str(out / "{}-{}-{}".format(name, option, seed)))
            for name in PROGRAMS for option in ("normal", "max") for seed in JUDGED]
    with ProcessPoolExecutor(workers) as pool:
        rows = list(pool.map(play_one, jobs))
    (out / "rows.json").write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
    return rows


def farm_rows(folder: str) -> Dict[str, Dict[int, Dict[str, Any]]]:
    by: Dict[str, Dict[int, Dict[str, Any]]] = {}
    for line in (FARM / folder / "rows.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row.get("options"):
            continue
        key = row["policy"] if row["policy"] != "program" else row["candidate"]
        by.setdefault(key, {})[row["seed"]] = row
    return by


def table(rows_file: Path, save: Optional[Path] = None) -> Dict[str, Any]:
    normal, hard = farm_rows("programs-1"), farm_rows("max-fresh")
    here: Dict[Tuple[str, str], Dict[int, Dict[str, Any]]] = {}
    for line in rows_file.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        here.setdefault((row["program"], row["map"]), {})[row["seed"]] = row
    players: Dict[str, Tuple[Optional[Dict[int, Any]], Optional[Dict[int, Any]]]] = {
        REFERENCE: (normal["pilot"], hard["manh_max"]),
        OLDER: (normal["program:traverse-oneshot-opus-1"], None),
    }
    for name in PROGRAMS:
        on_max = here.get((name, "max")) if name.startswith("M-") else hard.get("program:" + name[2:])
        players[LABELS[name]] = (here.get((name, "normal")), on_max)
    worlds = sorted(here[("K-opus-1", "normal")])
    seeds = [s for s in worlds if all(rows is None or s in rows for pair in players.values() for rows in pair)]

    def cell(rows: Dict[int, Dict[str, Any]]) -> Dict[str, Any]:
        mine = [rows[s] for s in seeds]
        return {"score": statistics.mean(r["reward"] for r in mine), "samples": statistics.mean(r["samples"] for r in mine),
                "collected": statistics.mean(r["sampled_value"] / r["max_value"] for r in mine),
                "lost": sum(not r["alive"] for r in mine), "away": sum(r["alive"] and not r["at_base"] for r in mine)}

    ref_normal, ref_max = cell(players[REFERENCE][0]), cell(players[REFERENCE][1])
    out: Dict[str, Any] = {"worlds": seeds, "players": {}}
    print("paired on {} worlds, {} to {}".format(len(seeds), seeds[0], seeds[-1]))
    print("{:<42} | {:<26} | {:<26} | {:>8} | {:>9} | {:>9}".format(
        "player", "NORMAL: score samples l/a", "MAX: score samples l/a", "kept", "of ref N", "of ref M"))
    for name, (on_normal, on_max) in players.items():
        a = cell(on_normal) if on_normal else None
        b = cell(on_max) if on_max else None
        show = lambda c: "{:.3f}  {:4.1f}  {}/{}".format(c["score"], c["samples"], c["lost"], c["away"]) if c else "-"
        print("{:<42} | {:<26} | {:<26} | {:>8} | {:>9} | {:>9}".format(
            name, show(a), show(b), "{:.0%}".format(b["score"] / a["score"]) if a and b else "-",
            "{:.0%}".format(a["score"] / ref_normal["score"]) if a else "-",
            "{:.0%}".format(b["score"] / ref_max["score"]) if b else "-"))
        out["players"][name] = {"normal": a, "max": b}

    def versus(title: str, ref: Dict[int, Any], others: Dict[str, Dict[int, Any]], key: str) -> None:
        groups = list(itertools.combinations(seeds, 3))
        campaign = lambda rows, group: (sum(rows[s].get("raw_score", rows[s]["reward"] * rows[s]["max_value"]) for s in group)
                                        / sum(rows[s]["max_value"] for s in group))
        print("\n{} ({} worlds, all {} groups of three):".format(title, len(seeds), len(groups)))
        for name, rows in others.items():
            diffs = [rows[s]["reward"] - ref[s]["reward"] for s in seeds]
            wins = sum(diff > 1e-12 for diff in diffs)
            won = sum(campaign(rows, group) > campaign(ref, group) + 1e-12 for group in groups)
            share = won / len(groups) if groups else float("nan")
            print("  {:<52} mean {:+.3f}, world-to-world sd {:.3f}; higher on {:>2} of {}; campaigns won {:.1%}".format(
                name, statistics.mean(diffs), statistics.pstdev(diffs), wins, len(diffs), share))
            out["players"].setdefault(name, {})[key] = {
                "mean_difference": statistics.mean(diffs), "sd_difference": statistics.pstdev(diffs),
                "worlds_higher": wins, "campaign_win_share": share if groups else None}

    new_normal = {name: pair[0] for name, pair in players.items() if name.startswith("Opus") and pair[0]}
    best = {s: max((rows[s] for rows in new_normal.values()), key=lambda r: r["reward"]) for s in seeds}
    versus("NORMAL map, against the reference pilot", players[REFERENCE][0],
           dict(new_normal, **{OLDER: players[OLDER][0], "BEST of the four per world (hindsight)": best}), "vs_reference_normal")
    new_max = {name: pair[1] for name, pair in players.items() if name.startswith("Opus") and pair[1]}
    versus("MAX map, against manh_max", players[REFERENCE][1], new_max, "vs_manh_max_max")
    if save:
        save.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    return out


def parse_seeds(text: str) -> List[int]:
    low, _, high = text.partition("-")
    return list(range(int(low), int(high or low) + 1))


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="action", required=True)
    a = sub.add_parser("table", help="the tables from the saved rows")
    a.add_argument("--rows", type=Path, default=ROWS)
    a.add_argument("--json", type=Path, default=None)
    b = sub.add_parser("play", help="play the missing missions in the sandbox")
    b.add_argument("--rows", type=Path, default=ROWS)
    b.add_argument("--seeds", default="600-629")
    b.add_argument("--workers", type=int, default=16)
    c = sub.add_parser("judged", help="worlds 2026-2029 on both maps, files kept")
    c.add_argument("out", type=Path)
    c.add_argument("--workers", type=int, default=8)
    args = parser.parse_args(argv)
    if args.action == "table":
        table(args.rows, args.json)
    elif args.action == "play":
        play(args.rows, parse_seeds(args.seeds), args.workers)
    else:
        if args.out.exists():
            parser.error("the output folder already exists")
        for row in judged(args.out, args.workers):
            print("{:<9} {:<6} {}  {:.3f}  {:>2} samples  {}".format(
                row["program"], row["map"], row["seed"], row["reward"], row["samples"],
                "home" if row["at_base"] else ("away" if row["alive"] else "LOST")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
