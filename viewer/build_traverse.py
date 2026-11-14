#!/usr/bin/env python3
"""Build the traverse demo: every recorded run of one Lightlag Traverse mission, on its ground.

    python3 viewer/build_traverse.py                   # writes viewer/traverse/data.json and viewer/traverse-demo.html
    python3 viewer/build_traverse.py --runs a/folder --out page.html   # other runs; leaves data.json alone
    python3 viewer/build_traverse.py --data-only       # just refresh viewer/traverse/data.json for development
    python3 viewer/build_traverse.py --campaign        # viewer/traverse-campaign.html from the campaign-* runs

The page replays saved runs. Each run is a folder `traverse-*/` holding `run.json` (who drove and
how: `kind` is "reference", "claude" or "scripted") and `artifacts/evaluator/` (the result and the
replay the simulator wrote). Exactly one run is the reference, and every other run must have played
the reference's world. Nothing is played or invented here.

`viewer/traverse-demo.html` is the single file to open: styles, three.js, the app and the data
are inlined, so it works by double-click with no network. Standard library only.

A campaign (lightlag_traverse/campaign.py) plays several worlds in a row. Its runs are folders
`campaign-*/` whose evaluator kept one result and one replay per mission under
`artifacts/evaluator/missions/NN/`. `--campaign` builds one page per world, all in one file:
`?site=2` (or the key 2) shows the second world.
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

REPO = Path(__file__).resolve().parent.parent
TRAVERSE = REPO / "viewer" / "traverse"
VENDOR = REPO / "viewer" / "mars" / "vendor"
RUNS = REPO / "docs" / "lightlag-runs"
REPLAY_VERSION = "lightlag-traverse-replay-v1"
KINDS = {"reference": "reference", "claude": "Claude run", "scripted": "scripted stand-in"}

sys.path.insert(0, str(REPO))
from lightlag_traverse.terrain import SAFE_SHARE  # noqa: E402  the share of max_tilt the map generator calls drivable


def world_definition(replay: Dict[str, Any]) -> Dict[str, Any]:
    """What must be identical for two replays to be the same mission on the same ground."""
    return {key: replay[key] for key in ("seed", "world", "config", "physics", "sensing")}


def track(replay: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    """One rover's mission, as compact arrays indexed by tick."""
    states = replay["states"]
    events = []
    for state in states:
        for event in state["events"]:
            if event["type"] == "sample_failed":
                events.append({"t": state["tick"], "k": "miss"})
            elif event["type"] == "safety_stop":
                events.append({"t": state["tick"], "k": "stop", "why": event.get("reason", "")})
            elif event["type"] == "battery_depleted":
                events.append({"t": state["tick"], "k": "dead"})
    return {
        "reward": result["raw_score"] / result["max_available_value"],
        "raw": result["raw_score"], "max": result["max_available_value"],
        "alive": result["alive"], "home": result["at_base"],
        "p": [round(v, 2) for state in states for v in state["position"]],
        # what the operator was told, in the order it was reported: the fix for tick i is at 2i, 2i + 1
        "seen": [round(v, 2) for packet in replay["received_telemetry"] for v in packet["position"]],
        "b": [round(state["battery"], 1) for state in states],
        "samples": [{"t": s["tick"], "id": s["target_id"], "v": s["credited_value"], "ok": s["on_time"]}
                    for s in replay["result"].get("samples") or []],
        "events": events,
        "commands": len(replay["commands"]),
    }


def run_folders(root: Path, prefix: str = "traverse-") -> List[Path]:
    """Every saved run under `root`: the folders `<prefix>*` that say who drove them."""
    return sorted(path.parent for path in root.glob(prefix + "*/run.json"))


def load_run(folder: Path, mission: Optional[int] = None) -> Dict[str, Any]:
    """A saved run: who drove (`run.json`) and what the evaluator kept; of one mission, for a campaign."""
    meta = json.loads((folder / "run.json").read_text(encoding="utf-8"))
    evaluator = folder / "artifacts" / "evaluator"
    if mission is not None:
        evaluator = evaluator / "missions" / "{:02d}".format(mission)
    result = json.loads((evaluator / "result.json").read_text(encoding="utf-8"))
    replay = json.loads((evaluator / "replay.json").read_text(encoding="utf-8"))
    return {"meta": meta, "result": result, "replay": replay, "source": folder.name}


def check(run: Dict[str, Any], first: Dict[str, Any]) -> None:
    """Refuse a run that is not one whole mission on the reference's world."""
    source, replay, result = run["source"], run["replay"], run["result"]
    if replay.get("version") != REPLAY_VERSION:
        raise SystemExit("{}: the replay is not a {}".format(source, REPLAY_VERSION))
    if run["meta"].get("kind") not in KINDS:
        raise SystemExit("{}: kind must be one of {}".format(source, ", ".join(sorted(KINDS))))
    if world_definition(replay) != world_definition(first["replay"]):
        raise SystemExit("{} did not play the reference's world".format(source))
    ticks = replay["config"]["max_ticks"]
    if [state["tick"] for state in replay["states"]] != list(range(ticks + 1)):
        raise SystemExit("{}: the replay does not hold one state per tick".format(source))
    if [packet["tick"] for packet in replay["received_telemetry"]] != list(range(len(replay["received_telemetry"]))):
        raise SystemExit("{}: the telemetry log is not one packet per tick from tick 0".format(source))
    for key in ("raw_score", "max_available_value", "alive", "at_base"):
        if replay["result"][key] != result[key]:
            raise SystemExit("{}: result.json and the replay disagree on {}".format(source, key))


def pitch(world: Dict[str, Any], config: Dict[str, Any], runs: Sequence[Dict[str, Any]]) -> str:
    """The opening card's words, written from the data so they stay true whichever runs are shown."""
    features = world.get("features") or {}
    ground = []
    if features.get("craters"):
        ground.append("{} craters with steep walls".format(len(features["craters"])))
    if features.get("scarp"):
        ground.append("a scarp with {} passes".format(len(features["scarp"]["passes"])))
    ground.append("sand, rock fields and bedrock")
    targets = world["targets"]
    timed = sum(t["deadline_tick"] is not None for t in targets)
    hidden = sum(t["appear_tick"] > 0 for t in targets)
    text = ("One mission of {} ticks across {:.0f} m by {:.0f} m of Mars-like ground: {}. "
            "{} science targets, {} with a deadline, {} found on the way. The sun charges the battery; "
            "every command arrives {} ticks late. <b>Gold is the reference controller.</b> ").format(
                config["max_ticks"], world["width"], world["height"], ", ".join(ground),
                len(targets), timed, hidden, config["delay_ticks"])
    others = [run for run in runs if run["kind"] != "reference"]
    scripted = sum(run["kind"] == "scripted" for run in others)
    if not others:
        return text + "No other run has been recorded on this ground yet."
    if scripted == len(others):
        return text + ("No model has driven this ground yet: the other {} scripted stand-in{}."
                       .format(*(("rover is a", "") if scripted == 1 else ("rovers are", "s"))))
    if scripted:
        return text + ("Ice blue is the run you follow; {} of the others {}."
                       .format(scripted, "is a scripted stand-in, not a model run" if scripted == 1
                               else "are scripted stand-ins, not model runs"))
    if len(others) == 1:
        return text + "Ice blue is the one Claude run on the same ground."
    return text + "Ice blue is the Claude run you follow; every other Claude run is a dark shadow."


def gather(folders: Sequence[Path], mission: Optional[int] = None) -> Dict[str, Any]:
    loaded = [load_run(folder, mission) for folder in folders]
    if not loaded:
        raise SystemExit("no runs found: expected traverse-*/run.json in the runs folder")
    references = [run for run in loaded if run["meta"].get("kind") == "reference"]
    if len(references) != 1:
        raise SystemExit("exactly one run must have kind 'reference'; found {}".format(len(references)))
    first = references[0]
    for run in loaded:
        check(run, first)

    replay = first["replay"]
    world, config = replay["world"], replay["config"]
    scarp = (world.get("features") or {}).get("scarp")
    passes = [[round(scarp["x"] + scarp["ux"] * along, 1), round(scarp["y"] + scarp["uy"] * along, 1)]
              for along in scarp["passes"]] if scarp else []
    runs = []
    for run in loaded:
        meta = run["meta"]
        runs.append(dict({"id": run["source"], "kind": meta["kind"], "who": KINDS[meta["kind"]],
                          "label": meta.get("label") or run["source"], "model": meta.get("model", ""),
                          "how": meta.get("how", "")},
                         **track(run["replay"], run["result"])))
    reference = next(run for run in runs if run["kind"] == "reference")
    others = sorted((run for run in runs if run["kind"] != "reference"), key=lambda run: (-run["reward"], run["id"]))
    claude = [run for run in others if run["kind"] == "claude"]
    runs = [reference] + others
    return {
        "title": "Lightlag Traverse",
        "brand": "TRAVERSE",
        "pitch": pitch(world, config, runs),
        "seed": replay["seed"],
        "config": {"ticks": config["max_ticks"], "delay": config["delay_ticks"],
                   "target_radius": config["target_radius"], "base_radius": config["base_radius"],
                   "battery": config["battery_capacity"], "late": config["late_fraction"],
                   "sun_margin": config["sun_margin_ticks"], "max_tilt": replay["physics"]["max_tilt"],
                   "safe_share": SAFE_SHARE},
        "world": {
            "width": world["width"], "height": world["height"], "cell": world["cell_m"],
            "nx": len(world["elevation_cm"][0]), "ny": len(world["elevation_cm"]),
            # the height grid once, row by row from the south: the height at x = i * cell, y = j * cell is at j * nx + i
            "elevation_cm": [value for row in world["elevation_cm"] for value in row],
            "terrain": world["terrain"],
            "base": world["base"],
            "passes": passes,
            "targets": [{"id": t["id"], "x": t["x"], "y": t["y"], "value": t["value"], "late": t["late_value"],
                         "deadline": t["deadline_tick"], "appear": t["appear_tick"]} for t in world["targets"]],
        },
        "runs": runs,
        # the run the page opens on: the best Claude run, or the best stand-in while no model has driven
        "best": (claude or others or [{"id": None}])[0]["id"],
    }


def campaign(root: Path) -> List[Dict[str, Any]]:
    """The pages of a campaign, one per world: every `campaign-*` run of a kind the page knows.

    Each page is gathered like a one-mission page from that mission's replays, then told which
    site it is and how every run did over the whole campaign.
    """
    folders = [folder for folder in run_folders(root, "campaign-")
               if json.loads((folder / "run.json").read_text(encoding="utf-8")).get("kind") in KINDS]
    if not folders:
        raise SystemExit("no campaign runs found: expected campaign-*/run.json in the runs folder")
    missions = sorted(int(path.name) for path in (folders[0] / "artifacts" / "evaluator" / "missions").iterdir()
                      if path.is_dir())
    if missions != list(range(1, len(missions) + 1)):
        raise SystemExit("{}: missions must be numbered 01, 02, ...".format(folders[0].name))
    totals = {}
    for folder in folders:
        results = [json.loads((folder / "artifacts" / "evaluator" / "missions" / "{:02d}".format(m) / "result.json")
                              .read_text(encoding="utf-8")) for m in missions]
        totals[folder.name] = (sum(r["raw_score"] for r in results) / sum(r["max_available_value"] for r in results))
    pages = [gather(folders, mission) for mission in missions]
    reference = next(run for run in pages[0]["runs"] if run["kind"] == "reference")
    others = [run for run in pages[0]["runs"] if run["kind"] == "claude"]
    over = ("Over all {} sites: <b>reference {:.2f}</b>".format(len(missions), totals[reference["id"]]))
    if others:
        scores = sorted(totals[run["id"]] for run in others)
        over += "; {} Claude run{} {}.".format(
            len(others), "" if len(others) == 1 else "s",
            "{:.2f}".format(scores[0]) if len(scores) == 1 else "{:.2f} to {:.2f}".format(scores[0], scores[-1]))
    else:
        over += "."
    for number, page in zip(missions, pages):
        page["brand"] = "SITE {} / {}".format(number, len(missions))
        page["title"] = "Lightlag Traverse campaign · site {}".format(number)
        page["pitch"] = "Site {} of a {}-site campaign. {} {}".format(number, len(missions), page["pitch"], over)
        page["site"] = number
        page["sites"] = [{"n": m, "label": "SITE {}".format(m),
                          "note": "reference {:.2f} here".format(other["runs"][0]["reward"])}
                         for m, other in zip(missions, pages)]
        for run in page["runs"]:
            run["campaign"] = round(totals[run["id"]], 6)
    return pages


def standalone(data: Any) -> str:
    """One HTML file: styles, three.js, the app and the data all inline. Given a list of pages
    (a campaign), every page is inlined and `?site=N` chooses which one opens."""
    def b64(path: Path) -> str:
        return base64.b64encode(path.read_bytes()).decode("ascii")

    page = (TRAVERSE / "index.html").read_text(encoding="utf-8")
    start, end = page.index("<!--DEV-->"), page.index("<!--/DEV-->") + len("<!--/DEV-->")

    def encoded(item: Dict[str, Any]) -> str:
        return base64.b64encode(json.dumps(item, separators=(",", ":")).encode("utf-8")).decode("ascii")

    if isinstance(data, list):
        payload = ""                     # every page has its own element below
        extra = "".join('\n<script id="src-data-{}" type="application/octet-stream">{}</script>'.format(n, encoded(item))
                        for n, item in enumerate(data, 1))
        choose = ("const site = Math.min({}, Math.max(1, parseInt(new URLSearchParams(location.search).get('site'), 10) || 1));\n"
                  "  window.LIGHTLAG_TRAVERSE = JSON.parse(text('src-data-' + site));").format(len(data))
    else:
        payload, extra = encoded(data), ""
        choose = 'window.LIGHTLAG_TRAVERSE = JSON.parse(text("src-data"));'
    inline = """<style>{css}</style>
<script id="src-core" type="application/octet-stream">{core}</script>
<script id="src-three" type="application/octet-stream">{three}</script>
<script id="src-app" type="application/octet-stream">{app}</script>
<script id="src-data" type="application/octet-stream">{data}</script>{extra}
<script>
(async () => {{
  const text = id => new TextDecoder().decode(Uint8Array.from(atob(document.getElementById(id).textContent), c => c.charCodeAt(0)));
  const url = source => URL.createObjectURL(new Blob([source], {{ type: "text/javascript" }}));
  const core = url(text("src-core"));
  const three = url(text("src-three").split("'./three.core.js'").join(JSON.stringify(core)));
  {choose}
  await import(url(text("src-app").split("'three'").join(JSON.stringify(three))));
}})().catch(error => {{ document.body.insertAdjacentHTML("beforeend", "<pre style='color:#f66;padding:20px'>" + error + "</pre>"); throw error; }});
</script>""".format(
        css=(TRAVERSE / "style.css").read_text(encoding="utf-8"),
        core=b64(VENDOR / "three.core.js"),
        three=b64(VENDOR / "three.module.js"),
        app=b64(TRAVERSE / "app.js"),
        data=payload,
        extra=extra,
        choose=choose,
    )
    return page[:start] + inline + page[end:]


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-only", action="store_true", help="only refresh viewer/traverse/data.json")
    parser.add_argument("--runs", type=Path, default=RUNS, help="folder holding the traverse-* run folders")
    parser.add_argument("--out", type=Path, default=None,
                        help="the page to write (default viewer/traverse-demo.html, or viewer/traverse-campaign.html)")
    parser.add_argument("--campaign", action="store_true", help="the campaign-* runs, one page per world, in one file")
    args = parser.parse_args(argv)
    if args.campaign:
        pages = campaign(args.runs)
        out = args.out or REPO / "viewer" / "traverse-campaign.html"
        for page in pages:
            print("site {}: seed {}".format(page["site"], page["seed"]))
            for run in page["runs"]:
                print("  {:<30} {:<9} here {:.3f} campaign {:.3f}  samples {:>2}  {}".format(
                    run["label"][:30], run["kind"], run["reward"], run["campaign"], len(run["samples"]),
                    "lost" if not run["alive"] else "home" if run["home"] else "away from the lander"))
        html = standalone(pages)
        out.write_text(html, encoding="utf-8")
        print("wrote {} ({:.1f} MB)".format(out.name, len(html) / 1e6))
        return 0
    default = args.runs.resolve() == RUNS.resolve() and args.out is None
    args.out = args.out or REPO / "viewer" / "traverse-demo.html"
    data = gather(run_folders(args.runs))
    world = data["world"]
    if default or args.data_only:
        # the development copy of the committed demo's data; a page built from other runs leaves it alone
        (TRAVERSE / "data.json").write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
        print("wrote viewer/traverse/data.json")
    print("seed {}, {:.0f} m by {:.0f} m, {} ticks, {} targets".format(
        data["seed"], world["width"], world["height"], data["config"]["ticks"], len(world["targets"])))
    for run in data["runs"]:
        print("  {:<30} {:<9} reward {:.3f}  samples {:>2}  {}".format(
            run["label"][:30], run["kind"], run["reward"], len(run["samples"]),
            "lost" if not run["alive"] else "home" if run["home"] else "away from the lander"))
    if not args.data_only:
        page = standalone(data)
        args.out.write_text(page, encoding="utf-8")
        print("wrote {} ({:.1f} MB)".format(args.out.name, len(page) / 1e6))
    return 0


if __name__ == "__main__":
    sys.exit(main())
