#!/usr/bin/env python3
"""Manh's best controller (manh_max) and the reference pilot on Kristján's worlds, on both maps.

    python3 tools/second_machine_check/kristjans_worlds.py <new-out-dir>     # about 6 minutes on 8 cores

Kristján's worlds are the one-site task's world 2026 and the campaign's sites 2027, 2028, 2029.
Every run goes through the service its Harbor task uses (the campaign service scores three
missions together), in this process, with the five public tools and nothing else. Eight runs:
{normal map, MAX map} x {campaign, world 2026} x {pilot, manh_max}. The artifacts
(`result.json`, each mission's `replay.json`) are kept in <out>/<map>-<kind>-<player>/ so they
can be compared byte for byte with the saved Harbor runs:

    cmp <out>/normal-campaign-pilot/missions/01/replay.json \
        docs/lightlag-runs/campaign-reference/artifacts/evaluator/missions/01/replay.json

Also plays the pilot with its battery reserves switched off on the normal map (the farm's
"reference without its reserves"), to show whether the reference can be beaten on these worlds.
Standard library only. Nothing here trains or tunes anything on these worlds.
"""

from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))

CAMPAIGN = [2027, 2028, 2029]
SINGLE = 2026
NO_RESERVES = {"floor": 0.0, "home_floor": 0.0, "home_margin": 0.0, "home_slack": 1.0}


def fly_campaign_with(tools: Any, make: Any) -> List[Any]:
    """Kristján's `fly_campaign` loop (lightlag_traverse/pilot.py), with another pilot class."""
    pilots = []
    while True:
        pilot = make(tools)
        while True:
            pilot.act()
            out = tools.advance(1)
            pilot.observe(out["packets"], out["current_tick"])
            if out["episode_complete"]:
                break
        pilots.append(pilot)
        if out.get("campaign_complete", True):
            return pilots


def one(job: Tuple[str, str, str, str, str]) -> Dict[str, Any]:
    out, option, kind, player, name = job
    from lightlag_traverse.campaign import TraverseCampaignService
    from lightlag_traverse.pilot import Pilot, fly
    from lightlag_traverse.server import TraverseEpisodeService
    from lightlag_traverse_max.players import MaxPilot, fly_max
    from lightlag_traverse_max.server import MaxCampaignService, MaxEpisodeService
    folder = str(Path(out) / name)
    started = time.time()
    options = NO_RESERVES if player == "pilot-no-reserves" else None
    if kind == "campaign":
        service = (TraverseCampaignService if option == "normal" else MaxCampaignService)(CAMPAIGN, artifact_dir=folder)
        make = (lambda tools: MaxPilot(tools)) if player == "manh_max" else (lambda tools: Pilot(tools, options))
        fly_campaign_with(service, make)
    else:
        service = (TraverseEpisodeService(SINGLE, artifact_dir=folder) if option == "normal"
                   else MaxEpisodeService(SINGLE, artifact_dir=folder))
        fly_max(service) if player == "manh_max" else fly(service, options)
    result = service.finish()
    row = {"name": name, "map": option, "kind": kind, "player": player,
           "reward": result["raw_score"] / result["max_available_value"],
           "raw_score": result["raw_score"], "max_available_value": result["max_available_value"],
           "seconds": round(time.time() - started, 1)}
    missions = result.get("missions") or [dict(result, seed=SINGLE)]
    row["missions"] = [{"seed": m["seed"], "reward": m["raw_score"] / m["max_available_value"],
                        "samples": len(m["sampled_targets"]), "alive": m["alive"], "at_base": m["at_base"]}
                       for m in missions]
    return row


def main(argv: List[str]) -> int:
    if len(argv) != 1 or Path(argv[0]).exists():
        print(__doc__)
        print("give one output folder that does not exist yet")
        return 2
    out = Path(argv[0])
    out.mkdir(parents=True)
    jobs = [(str(out), option, kind, player, "{}-{}-{}".format(option, kind, player))
            for option in ("normal", "max") for kind in ("campaign", "single") for player in ("pilot", "manh_max")]
    jobs += [(str(out), "normal", kind, "pilot-no-reserves", "normal-{}-pilot-no-reserves".format(kind))
             for kind in ("campaign", "single")]
    with ProcessPoolExecutor(8) as pool:
        rows = list(pool.map(one, jobs))
    (out / "rows.json").write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
    for row in rows:
        print("{:<34} {:.6f}  {}".format(row["name"], row["reward"], "  ".join(
            "{}: {:.3f} ({} samples, {})".format(m["seed"], m["reward"], m["samples"],
                                               "lost" if not m["alive"] else "home" if m["at_base"] else "away")
            for m in row["missions"])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
