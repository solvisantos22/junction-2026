"""manh_demo_1: what this cut does differently from Kristján's storyboard.

The story, the narration, the numbers and the shots are his (`tools/demo_video/storyboard.py`)
and are read from there every time, so a change to his script carries over. This file only
adds to it:

- the top-down moment of the opening shot is held a little longer, so the logo trackers have
  about two seconds over the rovers as they leave the lander, before the camera drops in;
- a few sounds that belong to a moment of a shot (the title, a camera move, a hard cut);
- the length: the film is stretched on its last card to `TARGET_SECONDS`, which a player shows
  as 1:59, one second inside the Junction's two-minute limit.
"""

from __future__ import annotations

from typing import Any, Dict, List

from tools.demo_video import storyboard as base

NAME = "manh_demo_1"
TARGET_SECONDS = 119.1          # a player shows 1:59 whether it rounds down or to the nearest second
LIMIT_SECONDS = 119.4           # never over this; the Junction's limit is 120

LINES, SUBTITLES, VOICE, POSTER, LIVE_URL = base.LINES, base.SUBTITLES, base.VOICE, base.POSTER, base.LIVE_URL

# Draft pieces: short clips of their own, recorded with `make piece --name ...` and looked at one by one. They are
# not in the film; the team picks among them first (Manh, 15 November: "a bunch of small clips ... we select").
PIECES: Dict[str, Dict[str, Any]] = {
    # three labs, three tiers, nine models, rolled out from the fastest tier to the flagships
    "lineup": {"page": "film", "scene": "lineup", "fade_out": 0.4, "beats": [{"min": 8.6}]},
    # what the models are measured against: the reference (a model-based planner) and the team's own RL agent
    "drivers": {"page": "film", "scene": "drivers", "fade_out": 0.4, "beats": [{"min": 9.0}]},
    # Kristján's two Modal scenes and his end card, to show Modal's name in its green with its mark
    "modal_farm": {"page": "film", "scene": "farm", "fade_out": 0.4, "beats": [{"min": 9.0, "cues": [4.6, 6.4]}]},
    "modal_learning": {"page": "film", "scene": "learning", "fade_out": 0.4, "beats": [{"min": 7.0}]},
    "modal_end": {"page": "film", "scene": "end", "fade_out": 0.6, "beats": [{"min": 7.0, "cues": [2.6, 4.2]}]},
}

TITLE_LEAD = 0.25               # the title lands on its own before the narrator names it
MAP_HOLD = 0.5                  # the camera drops in this much later than in Kristján's cut


def only(items: List[Dict[str, Any]], what: str, **match: Any) -> Dict[str, Any]:
    found = [item for item in items if all(item.get(key) == value for key, value in match.items())]
    if len(found) != 1:
        raise SystemExit("manh_demo: expected one {} in Kristján's storyboard, found {}: look at tools/manh_demo/cut.py".format(what, len(found)))
    return found[0]


def shots(durations: Dict[str, float], words: Dict[str, List[Dict[str, Any]]], stretch: float = 0.0) -> List[Dict[str, Any]]:
    """Kristján's shots with this cut's additions. `stretch` lengthens the last card (see `make.fit`)."""
    plan = base.shots(durations, words)
    say = base.Words(words)
    by = {shot["name"]: shot for shot in plan}

    # The cold open: "zero" rings for a moment before the cut; the camera rising to the map is heard.
    cold = by["cold"]["beats"]
    cold[-1]["pad"] = cold[-1].get("pad", 0.0) + 0.3
    cold[-1].setdefault("sfx", []).append({"t": 0.0, "kind": "whoosh", "len": 1.3})

    # The world: the title first, then the map with the trackers up while the rovers leave the lander,
    # then the camera drops in behind one of them as the delay is explained.
    world = only(by["world"]["beats"], "narrated beat of the world shot", vo="b1")
    world["vo_at"] = world.get("vo_at", 0.0) + TITLE_LEAD
    start = world["vo_at"]
    title = only(world["overlay"], "title cue", kind="title")
    title["to"] = round(start + say.at("b1", "one day") - 0.1, 2)
    caption = only(world["overlay"], "caption", kind="caption")
    caption["from"] = round(start + say.at("b1", "Every command"), 2)
    if len(world.get("at", [])) != 1:
        raise SystemExit("manh_demo: the world shot no longer has one timed camera change")
    world["at"][0]["t"] = round(start + say.at("b1", "Every command") - 1.0 + MAP_HOLD, 2)
    world["sfx"] = [{"t": 0.05, "kind": "hit"}, {"t": world["at"][0]["t"], "kind": "whoosh", "len": 1.2}]

    # The ground: the hard cut to the second rover is marked by a short breath of air.
    ground = by["ground"]["beats"]
    ground[1].setdefault("sfx", []).append({"t": 0.0, "kind": "cut"})

    # The end card holds until the film is exactly as long as it should be.
    end = by["end"]["beats"][-1]
    end["pad"] = round(end.get("pad", 0.0) + stretch, 3)
    return plan
