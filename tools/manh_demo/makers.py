"""Who made each AI model on screen, and the logo tile that says so at a glance.

A viewer should not have to read a label to know which lab's model is driving a rover. Every
run whose label names a model gets its maker's mark on a small light tile: over the rover in
the top-down shots, on the card that explains a failure, in the standings and beside the model
names on the charts.

The demos show models from Anthropic, Google and OpenAI side by side (Manh, 15 November 2026):
three labs, three tiers each, the lineup of the tier comparison (`tools/tier_agents/`). To add a
maker: one entry in `MAKERS` and its mark in `logos/`.

The marks are the Simple Icons paths (CC0-1.0, https://simpleicons.org, package 16.37.0),
unchanged. The logos themselves are trademarks of their owners and are used only to name the
maker of the model shown.
"""

from __future__ import annotations

import base64
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

HERE = Path(__file__).resolve().parent
LOGOS = HERE / "logos"

# `words` are matched as whole words in a run's label, in lower case; `ink` is the mark's colour
# and `tile` the square it sits on, chosen to stand out from rust-coloured ground; `text` is the
# company's colour for names and borders on the film's dark charts (OpenAI's own is black and white).
# `mark` is the model family's mark (on the tiles); `logo` and `lab` the company's own, for the floating icons.
MAKERS: Dict[str, Dict[str, Any]] = {
    "anthropic": {
        "name": "Anthropic", "family": "Claude", "mark": "claude.svg", "lab": "Anthropic", "logo": "anthropic.svg", "ink": "#D97757", "tile": "#F4F1E8", "text": "#D97757",
        "words": ("claude", "opus", "sonnet", "haiku", "anthropic"),
    },
    "google": {
        "name": "Google", "family": "Gemini", "mark": "gemini.svg", "lab": "Google DeepMind", "logo": "deepmind.svg", "ink": "#4285F4", "tile": "#FFFFFF", "text": "#4285F4",
        "words": ("gemini", "deepmind", "google", "gemma"),
    },
    "openai": {
        "name": "OpenAI", "family": "GPT", "mark": "openai.svg", "lab": "OpenAI", "logo": "openai.svg", "ink": "#0D0D0D", "tile": "#FFFFFF", "text": "#FFFFFF",
        "words": ("openai", "gpt", "chatgpt", "codex", "o1", "o3", "o4"),
    },
}

# The lineup of the tier comparison (Manh's brand tiers of 15 November, `tools/tier_agents/run_tiers.py`),
# from the fastest model of each lab to its most capable.
TIERS = ("FAST", "BALANCED", "FLAGSHIP")
LINEUP: Dict[str, Tuple[str, str, str]] = {
    "anthropic": ("Claude Haiku 5.5", "Claude Sonnet 5.5", "Claude Opus 5.5"),
    "google": ("Gemini 4 Hydrogen", "Gemini 4 Argon", "Gemini 4 Carbon"),
    "openai": ("GPT-6 Luna", "GPT-6.1 Terra", "GPT-6.1 Sol"),
}

# Modal ran the 300-world replay and the training: its name is drawn in its own green with its mark beside it.
MODAL = {"name": "Modal", "mark": "modal.svg", "ink": "#7FEE64"}

# The reference is a planner, not a model: it gets a tile of its own colour and a route, not a logo.
# The team's own trained agent gets the lime of its learning curve and a small network.
REFERENCE = {"name": "Reference", "family": "Planner", "ink": "#1A120F", "tile": "#FFB224"}
LEARNED = {"name": "RL agent", "family": "PPO", "ink": "#1A120F", "tile": "#B6E35A"}
ROUTE = ('<path d="M5 18.5 9.5 9l5 5.5L19 5.5" fill="none" stroke="{ink}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>'
         '<circle cx="5" cy="18.5" r="2.3" fill="{ink}"/><circle cx="19" cy="5.5" r="2.3" fill="{ink}"/>')
NETWORK = ('<path d="M5 7 12 4.5M5 7l7 5M5 7l7 12.5M5 17l7-12.5M5 17l7-5M5 17l7 2.5M12 4.5 19 12M12 12h7M12 19.5 19 12" fill="none" stroke="{ink}" stroke-width="1.3" stroke-linecap="round"/>'
           '<circle cx="5" cy="7" r="2.1" fill="{ink}"/><circle cx="5" cy="17" r="2.1" fill="{ink}"/><circle cx="12" cy="4.5" r="2.1" fill="{ink}"/>'
           '<circle cx="12" cy="12" r="2.1" fill="{ink}"/><circle cx="12" cy="19.5" r="2.1" fill="{ink}"/><circle cx="19" cy="12" r="2.3" fill="{ink}"/>')
OWN = {"reference": (REFERENCE, ROUTE), "rl": (LEARNED, NETWORK)}


def maker_of(label: str) -> Optional[str]:
    """The maker whose model a run label names ("Opus 5.5 · agent 2" -> "anthropic"), or None."""
    words = set(re.findall(r"[a-z]+\d*", label.lower()))
    for key, maker in MAKERS.items():
        if words & set(maker["words"]):
            return key
    return None


def mark_path(maker: str, company: bool = False) -> str:
    """The `d` of a mark, on Simple Icons' 24 by 24 grid: a maker's model family (or, with `company`, the lab's own
    logo: Anthropic, Google DeepMind, OpenAI), or Modal's for "modal"."""
    name = MODAL["mark"] if maker == "modal" else MAKERS[maker]["logo" if company else "mark"]
    found = re.search(r'<path d="([^"]+)"', (LOGOS / name).read_text(encoding="utf-8"))
    if not found:
        raise ValueError("no path in {}".format(name))
    return found.group(1)


def mark_svg(maker: str, size: int = 96) -> str:
    """A mark alone in its own colour, no tile: Modal's beside its name."""
    if maker == "modal":                 # Modal's mark is wide and low: its picture is cut to the mark, so it can be drawn as tall as the letters
        return ('<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{s}" viewBox="0 5.3 24 13.4"><path d="{d}" fill="{ink}"/></svg>').format(
            w=round(size * 24 / 13.4), s=size, d=mark_path(maker), ink=MODAL["ink"])
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="{s}" height="{s}" viewBox="0 0 24 24"><path d="{d}" fill="{ink}"/></svg>').format(
        s=size, d=mark_path(maker), ink=MAKERS[maker]["ink"])


def tile_svg(maker: Optional[str], size: int = 96) -> str:
    """A rounded square with the maker's mark on it; `None` is the reference's route tile, "rl" the trained agent's."""
    spec, drawing = OWN["reference" if maker is None else maker] if maker in (None, "reference", "rl") else (MAKERS[maker], None)
    inner = drawing.format(ink=spec["ink"]) if drawing else '<path d="{}" fill="{}"/>'.format(mark_path(maker), spec["ink"])
    # the mark keeps a fifth of the tile as margin on every side
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="{s}" height="{s}" viewBox="0 0 40 40">'
            '<rect x="1" y="1" width="38" height="38" rx="8.5" fill="{tile}" stroke="rgba(0,0,0,.55)" stroke-width="1.6"/>'
            '<g transform="translate(8 8)">{inner}</g></svg>').format(s=size, tile=spec["tile"], inner=inner)


def data_url(svg: str) -> str:
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


def for_page() -> Dict[str, Any]:
    """What the page add-ons need: a tile per maker (and the reference's, the trained agent's and Modal's mark),
    how to name each, and the colour to write its name in."""
    tiles = {key: {"name": spec["name"], "family": spec["family"], "tile": data_url(tile_svg(key)), "text": spec["text"],
                   "words": list(spec["words"])} for key, spec in MAKERS.items()}
    tiles["reference"] = {"name": REFERENCE["name"], "family": REFERENCE["family"], "tile": data_url(tile_svg(None)), "text": REFERENCE["tile"], "words": []}
    tiles["rl"] = {"name": LEARNED["name"], "family": LEARNED["family"], "tile": data_url(tile_svg("rl")), "text": LEARNED["tile"], "words": []}
    tiles["modal"] = {"name": MODAL["name"], "family": "", "tile": data_url(mark_svg("modal")), "text": MODAL["ink"], "words": []}
    return tiles


def lineup() -> Dict[str, Any]:
    """The nine models, lab by lab and tier by tier, for the lineup scene."""
    return {"tiers": list(TIERS), "labs": [{"key": key, "name": MAKERS[key]["name"].upper(), "models": [name.upper() for name in LINEUP[key]]} for key in MAKERS]}


def facts() -> Dict[str, Any]:
    """The numbers the new scenes show, read from the files that hold them: the reference and the team's trained
    agent on the submission campaign, from Sölvi's matched comparison (`docs/learning-final-results/campaign/`)."""
    import json

    found = json.loads((HERE.parents[1] / "docs" / "learning-final-results" / "campaign" / "comparison.json").read_text(encoding="utf-8"))
    learned = [policy for policy in found["latest_policies"] if policy["arm"].startswith("ppo")]
    return {"reference": found["beam"], "rl": found["mean_latest_reward"]["ppo"], "rl_runs": len(learned),
            "rl_missions": max(policy["episodes"] for policy in learned), "greedy": found["greedy"],
            "best_claude": max(found["best_recorded_opus"], found["best_recorded_sonnet"])}


def icon_settings(company: bool = False) -> Dict[str, Any]:
    """What the floating-icon drafts need: each lab's mark as a path with its colours, and three.js's SVG loader.
    The marks are the model families' (Claude, Gemini, GPT), the ones Manh saw first and liked; with `company`
    they are the labs' own logos instead (Anthropic, Google DeepMind, OpenAI), the second set of drafts."""
    from . import pages

    return {"loader": pages.svg_loader(),
            "labs": [{"key": key, "name": spec["lab" if company else "family"].upper(), "path": mark_path(key, company=company),
                      "ink": spec["ink"], "tile": spec["tile"], "text": spec["text"]} for key, spec in MAKERS.items()]}


def scene_icon_settings() -> Dict[str, Any]:
    """What the icons over the real environment need: the family mark of every lab, the reference's gold route,
    and three.js's SVG loader. Which rover is whose is added by the recorder, from the page's own runs."""
    from . import pages

    marks = {key: {"path": mark_path(key), "ink": spec["ink"], "tile": spec["tile"], "text": spec["text"]} for key, spec in MAKERS.items()}
    marks["reference"] = {"route": True, "ink": REFERENCE["ink"], "tile": REFERENCE["tile"], "text": REFERENCE["tile"]}
    return {"loader": pages.svg_loader(), "marks": marks}


# ---------------------------------------------------------------- the second draft: nine models in one replay
# Manh, 15 November: the replay should show all the different agents, not seven rovers of one lab. One saved campaign
# run per model, so the map carries nine rovers of three labs (and the team's own trained agent). Which run of each:
# the three the story follows (Opus 2: battery flat 13 m from home; Sonnet 1: thirty safety stops on the scarp;
# Argon 1: the only Argon run that left the lander, flat at site 3), and for every other model the middle one of its
# runs by campaign score. Every run of every model is on the film's chart (`tier_table`), whichever drives here.
CAST: Dict[str, str] = {
    "Claude Opus 5.5": "campaign-agent-opus-2",
    "Claude Sonnet 5.5": "campaign-agent-sonnet-1",
    "Claude Haiku 5.5": "campaign-agent-haiku-1",
    "GPT-6.1 Sol": "campaign-agent-gpt-6.1-sol-1",
    "GPT-6.1 Terra": "campaign-agent-gpt-6.1-terra-3",
    "GPT-6 Luna": "campaign-agent-gpt-6-luna-1",
    "Gemini 4 Carbon": "campaign-agent-gemini-4-carbon-1",
    "Gemini 4 Argon": "campaign-agent-gemini-4-argon-1",
    "Gemini 4 Hydrogen": "campaign-agent-gemini-4-hydrogen-1",
}


def tier_of(model: str) -> str:
    """FAST, BALANCED or FLAGSHIP for a model of the lineup."""
    for models in LINEUP.values():
        if model in models:
            return TIERS[models.index(model)]
    raise KeyError(model)


def cast_tiers() -> Dict[str, str]:
    """For the standings beside the replay: each cast run's tier, by run id."""
    return {run: tier_of(model) for model, run in CAST.items()}


def tier_runs() -> Dict[str, Any]:
    """Every campaign run of the GPT and Gemini models of the tier comparison (`docs/tier-comparison/runs.jsonl`), by
    the model's name as the lineup writes it. A run that timed out counts with the reward it was given, 0."""
    import json

    ledger = HERE.parents[1] / "docs" / "tier-comparison" / "runs.jsonl"
    names = {name.lower().replace(" ", "-"): name.upper() for models in LINEUP.values() for name in models}
    found: Dict[str, Any] = {}
    for line in ledger.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        short = row["model"].split("/")[-1]
        if "campaign" in row["task"] and short in names:
            found.setdefault(names[short], []).append(round(float(row.get("reward") or 0.0), 6))
    return found


def tier_table(claude: Dict[str, Any], reference: float, learned: float) -> Dict[str, Any]:
    """Every campaign run of all nine models beside the planner, for the film's chart, and what the narration says
    about them, checked: no run above the planner (line n8), the best average as a whole percentage (n8), and how
    many models the trained agent out-scores on average (n11). `claude` maps a Claude model's name in capitals to
    its campaign scores (Kristján's runs, from his film's numbers)."""
    runs = {**{name: list(scores) for name, scores in claude.items()}, **tier_runs()}
    rows = []
    for key, models in LINEUP.items():
        for tier, name in enumerate(models):
            scores = sorted(runs.get(name.upper(), []), reverse=True)
            if not scores:
                raise SystemExit("manh_demo: no campaign run found for {}".format(name))
            rows.append({"name": name.upper(), "maker": key, "tier": TIERS[tier], "runs": scores, "mean": sum(scores) / len(scores)})
    rows.sort(key=lambda row: -row["mean"])
    best = max(rows, key=lambda row: row["runs"][0])
    if best["runs"][0] >= reference:
        raise SystemExit("manh_demo: a run of {} scored {:.3f}, at or above the planner's {:.3f}: line n8 (\"none beat our driver\") "
                         "has to change".format(best["name"], best["runs"][0], reference))
    return {"rows": rows, "reference": reference, "count": sum(len(row["runs"]) for row in rows),
            "best_run": {"name": best["name"], "score": best["runs"][0]}, "best_mean": {"name": rows[0]["name"], "score": rows[0]["mean"]},
            "best_mean_percent": round(rows[0]["mean"] * 100), "reference_percent": round(reference * 100),
            "below_learned": sum(row["mean"] < learned for row in rows)}


# The farm: programs the models wrote, replayed on 300 worlds none of them had seen (seeds 600-899), each beside the
# reference on the same world (`docs/traverse-farm/`, on Modal). Kristján's six Claude programs are `programs-1`; the
# tier comparison's are the other three sets. A later set replaces an earlier one for the same program (GPT-6.1 Sol's
# second agent program was replayed again with the packages it had installed).
FARM_SETS = ("programs-1", "programs-tiers", "programs-agents-tiers", "programs-agents-tiers-2")


def worlds_table() -> Dict[str, Any]:
    """For the film's 300-world chart: one row per model, its best program (the highest mean score over the 300
    worlds among the programs that model left: one written in a single request, or one an agent run left), world by
    world against the reference of the same farm run. `cells` holds a letter per world: r the reference scored
    higher, c the program did, = a tie, x the program's rover ran its battery flat. Also the count over every
    program, so the choice of the best is seen not to flatter the reference."""
    import json

    farm = HERE.parents[1] / "docs" / "traverse-farm"
    slugs: Dict[str, str] = {}
    for models in LINEUP.values():
        for name in models:
            slugs[name.lower().replace(" ", "-")] = name
            if name.startswith("Claude"):
                slugs[name.split()[1].lower()] = name            # Kristján's runs are named opus, sonnet, haiku
    programs: Dict[Tuple[str, str], Dict[str, Any]] = {}
    reference: Dict[str, Any] = {}
    for folder in FARM_SETS:
        rows = [json.loads(line) for line in (farm / folder / "rows.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        pilot = {row["seed"]: row for row in rows if row["candidate"] == "pilot"}
        seeds = sorted(pilot)
        reference = {"worlds": len(seeds), "mean": sum(pilot[seed]["reward"] for seed in seeds) / len(seeds),
                     "lost": max(reference.get("lost", 0), sum(not pilot[seed]["alive"] for seed in seeds))}
        for candidate in sorted({row["candidate"] for row in rows} - {"pilot"}):
            found = re.match(r"(?:program|agent):traverse-(oneshot|agent)-(.+)-(\d+)$", candidate)
            if not found or found.group(2) not in slugs:
                raise SystemExit("manh_demo: {} in {} is not a program of a model of the lineup".format(candidate, folder))
            mine = {row["seed"]: row for row in rows if row["candidate"] == candidate}
            cells = "".join("x" if not mine[seed]["alive"] else "c" if mine[seed]["reward"] > pilot[seed]["reward"] + 1e-12
                            else "r" if mine[seed]["reward"] < pilot[seed]["reward"] - 1e-12 else "=" for seed in seeds)
            how = "ONE REQUEST" if found.group(1) == "oneshot" else "AGENT RUN " + found.group(3)
            programs[(slugs[found.group(2)], how)] = {
                "how": how, "cells": cells, "mean": sum(mine[seed]["reward"] for seed in seeds) / len(seeds),
                "reference_higher": sum(pilot[seed]["reward"] > mine[seed]["reward"] + 1e-12 for seed in seeds),
                "wins": sum(mine[seed]["reward"] > pilot[seed]["reward"] + 1e-12 for seed in seeds),
                "ties": sum(abs(mine[seed]["reward"] - pilot[seed]["reward"]) <= 1e-12 for seed in seeds),
                "lost": cells.count("x"), "margin": max(mine[seed]["reward"] - pilot[seed]["reward"] for seed in seeds)}
    rows = []
    for key, models in LINEUP.items():
        for tier, name in enumerate(models):
            left = [program for (model, _), program in programs.items() if model == name]
            if not left:
                raise SystemExit("manh_demo: no program of {} was replayed on the farm".format(name))
            best = max(left, key=lambda program: program["mean"])
            rows.append({"name": name.upper(), "maker": key, "tier": TIERS[tier], "left": len(left), **best})
    rows.sort(key=lambda row: -row["mean"])
    pairs, higher = reference["worlds"] * len(rows), sum(row["reference_higher"] for row in rows)
    return {"rows": rows, "worlds": reference["worlds"], "pairs": pairs, "reference_higher": higher, "percent": round(100 * higher / pairs),
            "wins": sum(row["wins"] for row in rows), "ties": sum(row["ties"] for row in rows), "lost": sum(row["lost"] for row in rows),
            "widest_win": max(row["margin"] for row in rows), "reference_mean": reference["mean"], "reference_lost": reference["lost"],
            "all": {"programs": len(programs), "pairs": reference["worlds"] * len(programs),
                    "reference_higher": sum(program["reference_higher"] for program in programs.values())}}
