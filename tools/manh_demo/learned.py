"""The team's own learned rover for the demo: Sölvi's trained PPO controller, driving the campaign.

Manh asked (15 November) for Sölvi's RL agent, provisionally the one the team shows, to drive in the
demo beside the reference and the AI labs' rovers. Nothing is trained or run here: the agent's own
campaign evaluation already saved every mission it drove, in the same replay format as the other runs
and on the same three worlds (2027-2029), in Sölvi's results:

    docs/learning-final-results/campaign/evaluation/cases/ppo-<seed>-08192.json.gz

These are the final policies of his policy freeze (8192 training missions each; the README's "A smaller
model that learns": PPO, mean of three seeds, 0.366 on the campaign). One rover is shown, so one seed is
chosen: SEED, the best of the three on the campaign (0.395; seeds 17 and 29 score 0.364 and 0.340). Say
so wherever its score is shown: it is the best seed, not the mean.

`write_run(root)` lays the seed's missions out as a saved run, in the layout Kristján's page builder reads
unchanged (`viewer/build_traverse.campaign`): `campaign-rl-ppo-<seed>/run.json` and
`artifacts/evaluator/missions/NN/{result,replay}.json`. Standard library only; nothing is written outside
`root`. `mark_path()` is its floating mark: the small network of the trained agent's tile, as one filled path.
"""

from __future__ import annotations

import gzip
import json
import math
from pathlib import Path
from typing import Any, Dict

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CASES = REPO / "docs" / "learning-final-results" / "campaign" / "evaluation" / "cases"
SEED = 43
CHECKPOINT = 8192          # training missions: the final policy of the freeze
REPLAY_VERSION = "lightlag-traverse-replay-v1"
RUN = {"kind": "claude",   # Kristján's page knows only reference, claude and scripted; the demo maps the id to the "rl" tile
       "label": "RL agent · PPO", "model": "Our RL agent (PPO)", "how": "trained from scratch on Modal"}


def folder_name(seed: int = SEED) -> str:
    return "campaign-rl-ppo-{}".format(seed)


def case(seed: int = SEED) -> Dict[str, Any]:
    """Sölvi's saved campaign evaluation of one final PPO seed."""
    with gzip.open(CASES / "ppo-{}-{:05d}.json.gz".format(seed, CHECKPOINT), "rt", encoding="utf-8") as handle:
        return json.load(handle)


def write_run(root: Path, seed: int = SEED) -> Path:
    """`root/campaign-rl-ppo-<seed>/` as a saved campaign run; returns the folder."""
    bundle = case(seed)
    folder = Path(root) / folder_name(seed)
    missions = folder / "artifacts" / "evaluator" / "missions"
    for number, mission in enumerate(bundle["missions"], 1):
        replay = mission["episode"]["replay"]
        if replay.get("version") != REPLAY_VERSION:
            raise ValueError("ppo-{} mission {}: not a {}".format(seed, number, REPLAY_VERSION))
        if replay["seed"] != mission["seed"]:
            raise ValueError("ppo-{} mission {}: the replay is of world {}, not {}".format(seed, number, replay["seed"], mission["seed"]))
        kept = replay["result"]
        result = {"raw_score": kept["raw_score"], "max_available_value": kept["max_available_value"],
                  "alive": kept["alive"], "at_base": kept["at_base"],
                  "reward": kept["raw_score"] / kept["max_available_value"], "seed": replay["seed"]}
        place = missions / "{:02d}".format(number)
        place.mkdir(parents=True, exist_ok=True)
        (place / "replay.json").write_text(json.dumps(replay, separators=(",", ":")), encoding="utf-8")
        (place / "result.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    whole = dict(bundle["result"], reward=bundle["result"]["raw_score"] / bundle["result"]["max_available_value"])
    (folder / "artifacts" / "evaluator" / "result.json").write_text(json.dumps(whole, indent=1), encoding="utf-8")   # the campaign as a whole
    meta = dict(RUN, seed=seed, checkpoint=CHECKPOINT, campaign_reward=bundle["reward"],
                source="docs/learning-final-results/campaign/evaluation/cases/ppo-{}-{:05d}.json.gz".format(seed, CHECKPOINT))
    (folder / "run.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return folder


# ---------------------------------------------------------------- its floating mark
# Six nodes and the links between them, on the 24 by 24 grid of the labs' marks. The links are thin bars that
# stop short of the nodes, so no two pieces overlap and the path has no holes for the SVG loader to guess at.
NODES = {"a": (5, 7), "b": (5, 17), "c": (12, 4.5), "d": (12, 12), "e": (12, 19.5), "f": (19, 12)}
LINKS = ("ac", "ad", "bd", "be", "cf", "df", "ef")     # no two cross
RADIUS, BAR, GAP = 2.2, 0.62, 0.7
LIME = "#B6E35A"           # the trained agent's colour in the film (makers.LEARNED)


def mark_path() -> str:
    parts = []
    for x, y in NODES.values():               # a circle as two arcs
        parts.append("M{:.2f} {:.2f}a{r} {r} 0 1 0 {d} 0a{r} {r} 0 1 0 -{d} 0z".format(x - RADIUS, y, r=RADIUS, d=2 * RADIUS))
    for a, b in LINKS:
        (x1, y1), (x2, y2) = NODES[a], NODES[b]
        length = math.hypot(x2 - x1, y2 - y1)
        ux, uy = (x2 - x1) / length, (y2 - y1) / length
        nx, ny = -uy * BAR / 2, ux * BAR / 2
        s, e = RADIUS + GAP, length - RADIUS - GAP
        corners = [(x1 + ux * s + nx, y1 + uy * s + ny), (x1 + ux * e + nx, y1 + uy * e + ny),
                   (x1 + ux * e - nx, y1 + uy * e - ny), (x1 + ux * s - nx, y1 + uy * s - ny)]
        parts.append("M" + "L".join("{:.2f} {:.2f}".format(px, py) for px, py in corners) + "z")
    return "".join(parts)


def icon_mark() -> Dict[str, Any]:
    """An entry for the floating marks (like makers.scene_icon_settings()["marks"][key])."""
    return {"path": mark_path(), "ink": "#1A120F", "tile": LIME, "text": LIME}
