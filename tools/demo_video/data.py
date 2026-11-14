"""The numbers the video's slides draw, read from the repository's own evidence.

    python3 -m tools.demo_video.data            # writes tools/demo_video/data/film_data.json

Every figure on a slide comes from here, and each block says where it was read:

- `campaign`: the seven Claude agent runs, the reference and the two baselines on the campaign
  task, from `docs/lightlag-runs/campaign-*/` (the evaluator's results).
- `battery`: the battery over the day at site 3 for the reference and two Claude runs, from the
  same runs' replays, and the sun's share of its peak from the mission's published formula.
- `farm`: the reference against six saved Claude programs on 300 fresh worlds, world by world,
  from `docs/traverse-farm/programs-1/rows.jsonl` (Kristján's other session, on Modal).
- `learning`: a small policy trained from scratch on Modal, from the table in
  `docs/learning-campaign-results/pilot/README.md` (Sölvi's pilot).
- `quotes`: two sentences from a Claude agent's own closing report, checked to be in its saved log.

The farm's rows and the learning table live on `main`; when the working tree does not hold them
they are read with `git show origin/main:<path>`. Standard library only.
"""

from __future__ import annotations

import json
import math
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO = Path(__file__).resolve().parents[2]
RUNS = REPO / "docs" / "lightlag-runs"
OUT = Path(__file__).resolve().parent / "data" / "film_data.json"

FARM_ROWS = "docs/traverse-farm/programs-1/rows.jsonl"
PILOT = "docs/learning-campaign-results/pilot/README.md"
QUOTE_RUN = "campaign-agent-opus-2"
QUOTES = [
    "the route planner only counted time. It never checked whether the battery would last.",
    "ran all three missions in about 45 seconds, without me checking anything between them",
]
FARM_NAMES = {
    "program:traverse-oneshot-opus-1": "OPUS · ONE REQUEST",
    "agent:traverse-agent-opus-1": "OPUS · AGENT 1",
    "agent:traverse-agent-sonnet-1": "SONNET · AGENT 1",
    "agent:traverse-agent-opus-3": "OPUS · AGENT 3",
    "program:traverse-oneshot-sonnet-1": "SONNET · ONE REQUEST",
    "program:traverse-oneshot-haiku-1": "HAIKU · ONE REQUEST",
}


def read(path: str) -> str:
    """A repository file: from the working tree, or from origin/main when this branch lacks it."""
    local = REPO / path
    if local.exists():
        return local.read_text(encoding="utf-8")
    done = subprocess.run(["git", "show", "origin/main:" + path], cwd=REPO, capture_output=True, text=True)
    if done.returncode != 0:
        raise SystemExit("{} is neither in the working tree nor on origin/main".format(path))
    return done.stdout


def campaign() -> Dict[str, Any]:
    rows = []
    for folder in sorted(RUNS.glob("campaign-*")):
        meta = json.loads((folder / "run.json").read_text(encoding="utf-8"))
        result = json.loads((folder / "artifacts" / "evaluator" / "result.json").read_text(encoding="utf-8"))
        sites = []
        for mission in result["missions"]:
            state = "lost" if not mission["alive"] else "home" if mission["at_base"] else "away"
            sites.append({"reward": round(mission["reward"], 6), "end": state, "samples": len(mission["sampled_targets"])})
        # six places, so a slide that shows three rounds the score itself and not an already rounded copy
        rows.append({"id": folder.name, "kind": meta["kind"], "label": meta["label"], "model": meta.get("model", ""),
                     "score": round(result["raw_score"] / result["max_available_value"], 6), "sites": sites})
    reference = next(row for row in rows if row["kind"] == "reference")
    claude = sorted((row for row in rows if row["kind"] == "claude"), key=lambda row: -row["score"])
    baselines = [row for row in rows if row["kind"] == "baseline"]
    return {"source": "docs/lightlag-runs/campaign-*/artifacts/evaluator/result.json",
            "reference": reference, "claude": claude, "baselines": baselines}


def battery(site: int = 3) -> Dict[str, Any]:
    series = {}
    config = None
    for name in ("campaign-reference", "campaign-agent-opus-4", "campaign-agent-opus-2"):
        replay = json.loads((RUNS / name / "artifacts" / "evaluator" / "missions" / "{:02d}".format(site) / "replay.json")
                            .read_text(encoding="utf-8"))
        config = replay["config"]
        states = replay["states"]
        dead = next((s["tick"] for s in states if not s["alive"]), None)
        series[name] = {"battery": [round(s["battery"], 1) for s in states], "dead": dead}
    ticks, margin = config["max_ticks"], config["sun_margin_ticks"]
    sun = [round(math.sin(math.pi * (t + margin) / (ticks + 2 * margin)), 3) for t in range(ticks + 1)]
    return {"source": "docs/lightlag-runs/campaign-*/artifacts/evaluator/missions/{:02d}/replay.json".format(site),
            "site": site, "ticks": ticks, "capacity": config["battery_capacity"], "sun": sun, "series": series}


def farm() -> Dict[str, Any]:
    rows = [json.loads(line) for line in read(FARM_ROWS).splitlines() if line.strip()]
    pilot = {row["seed"]: row for row in rows if row["candidate"] == "pilot"}
    seeds = sorted(pilot)
    programs = []
    for candidate, label in FARM_NAMES.items():
        mine = {row["seed"]: row for row in rows if row["candidate"] == candidate}
        cells, higher, lost, away = [], 0, 0, 0
        for seed in seeds:
            row = mine[seed]
            if not row["alive"]:
                cells.append("x")           # this program's rover ran its battery flat
                lost += 1
            elif row["reward"] > pilot[seed]["reward"] + 1e-12:
                cells.append("c")           # the program scored higher than the reference here
            elif row["reward"] < pilot[seed]["reward"] - 1e-12:
                cells.append("r")           # the reference scored higher
            else:
                cells.append("=")
            if row["alive"] and not row["at_base"]:
                away += 1
            if pilot[seed]["reward"] > row["reward"] + 1e-12:
                higher += 1
        programs.append({"label": label, "cells": "".join(cells), "reference_higher": higher, "lost": lost,
                         "away": away, "mean": round(sum(mine[s]["reward"] for s in seeds) / len(seeds), 3)})
    return {"source": FARM_ROWS + " (Modal; docs/traverse-farm.md)", "worlds": len(seeds),
            "reference_mean": round(sum(row["reward"] for row in pilot.values()) / len(seeds), 3),
            "reference_lost": sum(1 for row in pilot.values() if not row["alive"]),
            "reference_away": sum(1 for row in pilot.values() if row["alive"] and not row["at_base"]),
            "programs": programs,
            # from docs/traverse-farm.md: the point-of-no-return check on these missions, and the farm's scale
            "lost_with_way_home_open": [257, 294], "containers": 100, "missions_by_2115": 6000, "core_hours_by_2115": 105}


def learning() -> Dict[str, Any]:
    text = read(PILOT)
    runs = []
    for match in re.finditer(r"^\| \[(ppo|replay)-(\d+)\]\([^)]*\) \| ([\d.]+) \| ([\d.]+) \| ([\d.]+) \|", text, re.M):
        runs.append({"method": match.group(1), "seed": int(match.group(2)),
                     "scores": [float(match.group(3)), float(match.group(4)), float(match.group(5))]})
    if len(runs) != 6:
        raise SystemExit("expected six runs in {}, found {}".format(PILOT, len(runs)))
    controls = re.search(r"score \*\*greedy ([\d.]+)\*\* and \*\*original beam ([\d.]+)\*\*", text)
    if not controls:
        raise SystemExit("the pilot's control scores were not found in " + PILOT)
    ppo = [run for run in runs if run["method"] == "ppo"]
    mean = [round(sum(run["scores"][i] for run in ppo) / len(ppo), 4) for i in range(3)]
    return {"source": PILOT, "missions": [0, 512, 2048], "ppo": ppo, "ppo_mean": mean,
            "greedy": float(controls.group(1)), "reference": float(controls.group(2)), "validation_worlds": 32}


def quotes() -> Dict[str, Any]:
    log = (RUNS / QUOTE_RUN / "agent" / "opencode.txt").read_text(encoding="utf-8", errors="replace")
    for quote in QUOTES:
        if quote not in log:
            raise SystemExit("the quote {!r} is not in {}'s saved log".format(quote[:40], QUOTE_RUN))
    return {"source": "docs/lightlag-runs/{}/agent/opencode.txt".format(QUOTE_RUN), "run": QUOTE_RUN, "lines": QUOTES}


def build() -> Dict[str, Any]:
    return {"campaign": campaign(), "battery": battery(), "farm": farm(), "learning": learning(), "quotes": quotes()}


def main() -> int:
    data = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, separators=(",", ":")) + "\n", encoding="utf-8")
    c, f, l = data["campaign"], data["farm"], data["learning"]
    print("campaign: reference {:.3f}; Claude {}".format(c["reference"]["score"], [row["score"] for row in c["claude"]]))
    print("farm: {} worlds; reference mean {:.3f}, lost {}, away {}".format(f["worlds"], f["reference_mean"],
                                                                         f["reference_lost"], f["reference_away"]))
    for program in f["programs"]:
        print("   {:22s} reference higher on {:3d}, rover lost on {:3d}, mean {:.3f}".format(
            program["label"], program["reference_higher"], program["lost"], program["mean"]))
    print("learning: PPO mean {} against greedy {:.3f} and the reference {:.3f}".format(l["ppo_mean"], l["greedy"], l["reference"]))
    print("wrote", OUT.relative_to(REPO))
    return 0


if __name__ == "__main__":
    sys.exit(main())
