#!/usr/bin/env python3
"""The reference against every saved Claude-written program, on maps none of them was built on.

    python3 -m lightlag_live.fresh_maps play <new-folder> [--first 30000 --count 200]   # needs Docker
    python3 -m lightlag_live.fresh_maps table [docs/lightlag-live-fresh-maps.json]

`play` runs the frozen reference and each program saved under docs/lightlag-runs/ through
`lightlag_live.sandbox` on `rush_noisy` maps at the task's noise level, 40 maps to a campaign,
and writes one score per program and map to `<new-folder>/scores.json`. The programs run in
locked-down containers on a simulated clock; no model is called and nothing is paid for.

`table` reads such a file and answers one question: if a campaign were n of these maps, how
often would the reference's mean score be the higher one? It answers for every map, and for
the maps the task's mission rule would pick (the reference ends at base with at least 0.6).

Why it exists: the task's six missions were chosen by that rule, and the settings were chosen
on 40 exploration maps. Both choices favour the reference. Fresh maps show what is left of
its lead without them. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

REPO = Path(__file__).resolve().parent.parent
RUNS = REPO / "docs" / "lightlag-runs"
SAVED = REPO / "docs" / "lightlag-live-fresh-maps.json"
CHUNK = 40                      # maps per sandbox campaign; a campaign's call cap allows about 130
LENGTHS = (1, 3, 6, 12, 24, 48)
RULE_SCORE = 0.6                # the mission rule of lightlag_live.make_task
NUMPY_IMAGE = "lightlag-sandbox-numpy"   # python:3.12-slim plus numpy, for agents that installed it

# name -> (label, sandbox flags, the program). Agent programs run whole, as they ran in the task;
# one-request programs are a module with play(tools), started fresh for each mission.
PROGRAMS = {
    "reference": ("Reference (kf_mpc)", ["--reference"], None),
    "opus-agent-2": ("Opus 5.5 · agent 2's program", ["--program", "--image", NUMPY_IMAGE], "live-agent-opus-2/program"),
    "opus-agent-3": ("Opus 5.5 · agent 3's program", ["--program", "--image", NUMPY_IMAGE], "live-agent-opus-3/program"),
    "opus-oneshot-1": ("Opus 5.5 · one shot", [], "live-oneshot-opus-1/policy.py"),
    "sonnet-oneshot-2": ("Sonnet 5.5 · one shot 2", [], "live-oneshot-sonnet-2/policy.py"),
    "sonnet-oneshot-1": ("Sonnet 5.5 · one shot 1", [], "live-oneshot-sonnet-1/policy.py"),
    "haiku-oneshot-2": ("Haiku 5.5 · one shot 2", [], "live-oneshot-haiku-2/policy.py"),
    "haiku-oneshot-1": ("Haiku 5.5 · one shot 1", [], "live-oneshot-haiku-1/policy.py"),
    "haiku-oneshot-3": ("Haiku 5.5 · one shot 3", [], "live-oneshot-haiku-3/policy.py"),
}


def play(out: Path, first: int, count: int, parallel: int) -> Dict[str, Any]:
    """Run every program on seeds first..first+count-1. A chunk that is already there is reused."""
    chunks = [list(range(start, min(start + CHUNK, first + count))) for start in range(first, first + count, CHUNK)]

    def one(job):
        name, seeds = job
        target = out / name / "{}-{}".format(seeds[0], seeds[-1])
        if not (target / "sandbox.json").exists():
            if target.exists():
                return name, seeds, None, "half-written chunk, remove it by hand: {}".format(target)
            target.parent.mkdir(parents=True, exist_ok=True)
            _, flags, program = PROGRAMS[name]
            command = [sys.executable, "-m", "lightlag_live.sandbox"] + flags
            command += ([str(RUNS / program)] if program else []) + [
                str(target), "--missions", ",".join("{}:rush_noisy".format(seed) for seed in seeds)]
            done = subprocess.run(command, cwd=REPO, capture_output=True, text=True)
            if done.returncode != 0 or not (target / "sandbox.json").exists():
                return name, seeds, None, (done.stdout + done.stderr)[-600:]
        summary = json.loads((target / "sandbox.json").read_text(encoding="utf-8"))
        result = json.loads((target / "artifacts" / "evaluator" / "result.json").read_text(encoding="utf-8"))
        return name, seeds, {"summary": summary, "missions": result["missions"]}, ""

    scores: Dict[str, Dict[str, Any]] = {name: {} for name in PROGRAMS}
    problems: List[str] = []
    with ThreadPoolExecutor(max_workers=parallel) as pool:
        for name, seeds, data, error in pool.map(one, [(name, seeds) for seeds in chunks for name in PROGRAMS]):
            if data is None:
                problems.append("{} from seed {}: {}".format(name, seeds[0], error))
                continue
            summary = data["summary"]
            # A program that never answered was not played: report it, do not score it as zero.
            if summary.get("status") != "returned" or summary.get("errors"):
                problems.append("{} from seed {}: status {}, errors {}".format(
                    name, seeds[0], summary.get("status"), summary.get("errors")))
                continue
            for seed, mission in zip(seeds, data["missions"]):
                scores[name][str(seed)] = {"reward": round(mission["reward"], 6), "alive": mission["alive"],
                                           "home": mission["at_base"]}
            print("{:<18} {}-{} mean {:.3f}".format(
                name, seeds[0], seeds[-1], statistics.mean(m["reward"] for m in data["missions"])), flush=True)
    saved = {"version": "lightlag-live-fresh-maps-v1", "profile": "rush_noisy", "first_seed": first, "count": count,
             "settings": "lightlag_live.make_task.SETTINGS, simulated clock",
             "programs": {name: {"label": label, "source": program or "lightlag_dynamic kf_mpc"}
                          for name, (label, _, program) in PROGRAMS.items()},
             "scores": scores, "problems": problems}
    (out / "scores.json").write_text(json.dumps(saved, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return saved


def picked_by_the_rule(reference: Dict[str, Any]) -> List[str]:
    return sorted((seed for seed, row in reference.items()
                   if row["alive"] and row["home"] and row["reward"] >= RULE_SCORE - 1e-9), key=int)


def compare(reference: Dict[str, Any], program: Dict[str, Any], pool: Sequence[str],
            lengths: Sequence[int] = LENGTHS, draws: int = 20000, seed: int = 20261114) -> Dict[str, Any]:
    """The reference against one program on the maps in `pool`.

    `campaigns[n]` is the share of n-map campaigns, drawn without replacement, in which the
    reference's mean score is strictly higher; None when the pool has fewer than n maps.
    """
    leads = [reference[s]["reward"] - program[s]["reward"] for s in pool]
    lead = statistics.mean(leads)
    error = statistics.stdev(leads) / len(leads) ** 0.5 if len(leads) > 1 else 0.0
    rng = random.Random(seed)
    campaigns: Dict[int, Optional[float]] = {}
    for n in lengths:
        if n > len(pool):
            campaigns[n] = None
            continue
        if n == len(pool):
            campaigns[n] = 1.0 if sum(leads) > 1e-9 else 0.0
            continue
        indices = range(len(leads))
        wins = sum(sum(leads[i] for i in rng.sample(indices, n)) > 1e-9 for _ in range(draws))
        campaigns[n] = wins / draws
    return {"mean": statistics.mean(program[s]["reward"] for s in pool), "lead": lead,
            "lead_low": lead - 1.96 * error, "lead_high": lead + 1.96 * error,
            "higher": sum(d > 1e-9 for d in leads), "lower": sum(d < -1e-9 for d in leads),
            "equal": sum(abs(d) <= 1e-9 for d in leads),
            "lost": sum(not program[s]["alive"] for s in pool), "campaigns": campaigns}


def table(saved: Dict[str, Any], draws: int = 20000) -> str:
    scores = saved["scores"]
    reference = scores["reference"]
    everything = sorted((s for s in reference if all(s in rows for rows in scores.values())), key=int)
    lines = []
    for title, pool in (("every map", everything),
                        ("maps the mission rule would pick", [s for s in picked_by_the_rule(reference) if s in everything])):
        lines.append("{}: {} maps, reference mean {:.3f}".format(
            title, len(pool), statistics.mean(reference[s]["reward"] for s in pool)))
        lines.append("  {:<30} {:>6} {:>7} {:>16} {:>11}  ".format("program", "mean", "lead", "95% interval", "maps +/=/-")
                     + "".join("{:>6}".format(n) for n in LENGTHS))
        for name, rows in scores.items():
            if name == "reference":
                continue
            c = compare(reference, rows, pool, draws=draws)
            label = (saved.get("programs", {}).get(name) or {}).get("label", name)
            lines.append("  {:<30} {:>6.3f} {:>+7.3f} {:>16} {:>11}  ".format(
                label[:30], c["mean"], c["lead"], "{:+.3f}..{:+.3f}".format(c["lead_low"], c["lead_high"]),
                "{}/{}/{}".format(c["higher"], c["equal"], c["lower"]))
                + "".join("{:>6}".format("-" if c["campaigns"][n] is None else "{:.0%}".format(c["campaigns"][n]))
                          for n in LENGTHS))
        lines.append("")
    lines.append("The last columns: share of campaigns of that many maps in which the reference's mean is higher.")
    if saved.get("problems"):
        lines.append("Not played, so not scored: " + "; ".join(saved["problems"]))
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    playing = commands.add_parser("play", help="run every program on fresh maps (needs Docker)")
    playing.add_argument("out", type=Path)
    playing.add_argument("--first", type=int, default=30000)
    playing.add_argument("--count", type=int, default=200)
    playing.add_argument("--parallel", type=int, default=3)
    showing = commands.add_parser("table", help="print the comparison for a saved scores file")
    showing.add_argument("scores", nargs="?", type=Path, default=SAVED)
    showing.add_argument("--draws", type=int, default=20000)
    args = parser.parse_args(argv)
    if args.command == "play":
        saved = play(args.out.resolve(), args.first, args.count, args.parallel)
        print(table(saved))
        return 1 if saved["problems"] else 0
    print(table(json.loads(args.scores.read_text(encoding="utf-8")), args.draws))
    return 0


if __name__ == "__main__":
    sys.exit(main())
