#!/usr/bin/env python3
"""Build the ghost demo: every Claude attempt as a shadow beside the reference.

    python3 viewer/build_ghosts.py                 # writes viewer/ghosts/data.json and viewer/ghosts-demo.html
    python3 viewer/build_ghosts.py --data-only     # just refresh viewer/ghosts/data.json for development

The page replays saved Lightlag Live campaigns. Each run is a folder `docs/lightlag-runs/live-*/`
holding `run.json` (who played and how) and `artifacts/evaluator/` (the campaign's result and one
replay per mission, written by the simulator). Nothing is played or invented here.

`viewer/ghosts-demo.html` is the single file to open: styles, three.js, the app and the data
are inlined, so it works by double-click with no network. Standard library only.
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

REPO = Path(__file__).resolve().parent.parent
GHOSTS = REPO / "viewer" / "ghosts"
VENDOR = REPO / "viewer" / "mars" / "vendor"
RUNS = REPO / "docs" / "lightlag-runs"


def mission_definition(replay: Dict[str, Any]) -> Dict[str, Any]:
    """What must be identical for two replays to be the same mission."""
    dynamic = dict(replay.get("dynamic") or {})
    sensing = dict(dynamic.get("sensing") or {})
    sensing.pop("heading_errors", None)  # drawn per executed drive, so it differs between runs
    dynamic["sensing"] = sensing
    return {"seed": replay["seed"], "world": replay["world"], "config": replay["config"], "dynamic": dynamic}


def track(replay: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    """One rover's mission, as compact arrays indexed by tick."""
    states = replay["states"]
    seen = {packet["tick"]: packet["position"] for packet in replay.get("received_telemetry") or []}
    events = []
    for state in states:
        for event in state["events"]:
            if event["type"] == "sample_failed":
                events.append({"t": state["tick"], "k": "miss"})
            elif event["type"] == "safety_stop":
                events.append({"t": state["tick"], "k": "stop"})
            elif event["type"] == "battery_depleted":
                events.append({"t": state["tick"], "k": "dead"})
    return {
        "reward": result["reward"], "raw": result["raw_score"], "max": result["max_available_value"],
        "alive": result["alive"], "home": result["at_base"],
        "p": [round(v, 2) for state in states for v in state["position"]],
        "seen": [round(v, 2) for state in states for v in seen.get(state["tick"], state["position"])],
        "h": [round(state["heading_deg"], 1) for state in states],
        "b": [round(state["battery"], 1) for state in states],
        "samples": [{"t": s["tick"], "id": s["target_id"], "v": s["credited_value"], "ok": s["on_time"]}
                    for s in replay["result"].get("samples") or []],
        "events": events,
        "commands": len(replay["commands"]),
    }


def load_run(folder: Path, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """A saved run: a Lightlag Live campaign, or one turn-based episode shown as a one-mission campaign."""
    if meta is None:
        meta = json.loads((folder / "run.json").read_text(encoding="utf-8"))
    evaluator = folder / "artifacts" / "evaluator"
    result = json.loads((evaluator / "result.json").read_text(encoding="utf-8"))
    replays = []
    if "missions" in result:
        for mission in result["missions"]:
            path = evaluator / "missions" / "{:02d}".format(mission["mission"]) / "replay.json"
            replays.append(json.loads(path.read_text(encoding="utf-8")))
    else:
        reward = result["raw_score"] / result["max_available_value"]
        result = {"reward": reward, "seconds_per_tick": None, "missions": [dict(result, mission=1, reward=reward)]}
        replays.append(json.loads((evaluator / "replay.json").read_text(encoding="utf-8")))
    return {"meta": meta, "result": result, "replays": replays, "source": folder.name}


def gather(folders: Sequence[Path], described: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """`described` is a set file: which folders to show and how to name them, for runs that carry no run.json."""
    if described:
        loaded = [load_run(RUNS / run["folder"], {key: value for key, value in run.items() if key != "folder"})
                  for run in described["runs"]]
    else:
        loaded = [load_run(folder) for folder in folders]
    if not loaded:
        raise SystemExit("no runs found: expected docs/lightlag-runs/live-*/run.json")
    references = [run for run in loaded if run["meta"]["kind"] == "reference"]
    if len(references) != 1:
        raise SystemExit("exactly one run must have kind 'reference'; found {}".format(len(references)))
    first = references[0]
    for run in loaded:
        if len(run["replays"]) != len(first["replays"]):
            raise SystemExit("{} did not play the same number of missions".format(run["source"]))
        for index, replay in enumerate(run["replays"]):
            if mission_definition(replay) != mission_definition(first["replays"][index]):
                raise SystemExit("{}: mission {} is not the reference's mission".format(run["source"], index + 1))

    missions = []
    for index, replay in enumerate(first["replays"]):
        dynamic = replay.get("dynamic") or {}
        plan = {t["id"]: t for t in dynamic.get("targets") or []}
        world = replay["world"]
        targets = [{"id": t["id"], "x": t["x"], "y": t["y"], "value": t["value"],
                    "appear": (plan.get(t["id"]) or {}).get("appear_tick") or 0,
                    "deadline": (plan.get(t["id"]) or {}).get("deadline_tick")} for t in world["targets"]]
        missions.append({"n": index + 1, "profile": dynamic.get("profile"), "width": world["width"],
                         "height": world["height"], "base": world["base"], "sand": world["sand"],
                         "hazards": world["hazards"], "targets": targets,
                         "late": dynamic.get("late_fraction", 1), "ticks": replay["config"]["max_ticks"],
                         "delay": replay["config"]["delay_ticks"],
                         "base_radius": replay["config"]["base_radius"],
                         "target_radius": replay["config"]["target_radius"]})

    runs = []
    for run in loaded:
        meta, result = run["meta"], run["result"]
        runs.append({
            "id": run["source"], "kind": meta["kind"], "model": meta.get("model", ""), "label": meta["label"],
            "how": meta.get("how", ""), "reward": result["reward"],
            "lost": sum(not m["alive"] for m in result["missions"]),
            "missions": [track(replay, mission) for replay, mission in zip(run["replays"], result["missions"])],
        })
    claude = sorted((r for r in runs if r["kind"] != "reference"), key=lambda r: -r["reward"])
    reference = next(r for r in runs if r["kind"] == "reference")
    sensing = dict((first["replays"][0].get("dynamic") or {}).get("sensing") or {})
    sensing.pop("heading_errors", None)
    count, delay = len(missions), missions[0]["delay"]
    text = dict(DEFAULT_TEXT, **{key: value for key, value in (described or {}).items() if key in DEFAULT_TEXT})
    return {
        "title": "Lightlag " + text["brand"].title(),
        "brand": text["brand"],
        "pitch": text["pitch"].format(count=count, delay=delay),
        "tag": text["tag"].format(count=count, delay=delay),
        "note": text["note"],
        "settings": {"seconds_per_tick": first["result"]["seconds_per_tick"],
                     "noise_level": (first["replays"][0].get("dynamic") or {}).get("noise_level"),
                     "sensing": sensing},
        "missions": missions,
        "runs": [reference] + claude,
        "best": claude[0]["id"] if claude else None,
    }


# What the page says about the runs it shows. A set file may replace any of these.
DEFAULT_TEXT = {
    "brand": "LIVE",
    "pitch": "{count} missions back to back, one second per tick. Nobody can joystick that, so each Claude model "
             "wrote an autopilot. <b>Gold is the reference controller on the same missions.</b>",
    "tag": "every position fix is {delay} ticks old and off by up to a metre",
    "note": "",
}


def standalone(data: Dict[str, Any]) -> str:
    """One HTML file: styles, three.js, the app and the data all inline."""
    def b64(path: Path) -> str:
        return base64.b64encode(path.read_bytes()).decode("ascii")

    page = (GHOSTS / "index.html").read_text(encoding="utf-8")
    start, end = page.index("<!--DEV-->"), page.index("<!--/DEV-->") + len("<!--/DEV-->")
    payload = base64.b64encode(json.dumps(data, separators=(",", ":")).encode("utf-8")).decode("ascii")
    inline = """<style>{css}</style>
<script id="src-core" type="application/octet-stream">{core}</script>
<script id="src-three" type="application/octet-stream">{three}</script>
<script id="src-app" type="application/octet-stream">{app}</script>
<script id="src-data" type="application/octet-stream">{data}</script>
<script>
(async () => {{
  const text = id => new TextDecoder().decode(Uint8Array.from(atob(document.getElementById(id).textContent), c => c.charCodeAt(0)));
  const url = source => URL.createObjectURL(new Blob([source], {{ type: "text/javascript" }}));
  const core = url(text("src-core"));
  const three = url(text("src-three").split("'./three.core.js'").join(JSON.stringify(core)));
  window.LIGHTLAG_GHOSTS = JSON.parse(text("src-data"));
  await import(url(text("src-app").split("'three'").join(JSON.stringify(three))));
}})().catch(error => {{ document.body.insertAdjacentHTML("beforeend", "<pre style='color:#f66;padding:20px'>" + error + "</pre>"); throw error; }});
</script>""".format(
        css=(GHOSTS / "style.css").read_text(encoding="utf-8"),
        core=b64(VENDOR / "three.core.js"),
        three=b64(VENDOR / "three.module.js"),
        app=b64(GHOSTS / "app.js"),
        data=payload,
    )
    return page[:start] + inline + page[end:]


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-only", action="store_true", help="only refresh viewer/ghosts/data.json")
    parser.add_argument("--runs", type=Path, default=RUNS, help="folder holding the live-* run folders")
    parser.add_argument("--set", type=Path, default=None,
                        help="a set file under viewer/ghosts/sets/: show the runs it lists instead of live-*")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.set:
        data = gather([], json.loads(args.set.read_text(encoding="utf-8")))
        out = args.out or REPO / "viewer" / "ghosts-{}.html".format(args.set.stem)
        print("gathered {}: {} mission(s)".format(args.set.name, len(data["missions"])))
    else:
        folders = sorted(path.parent for path in args.runs.glob("live-*/run.json"))
        data = gather(folders)
        out = args.out or REPO / "viewer" / "ghosts-demo.html"
        (GHOSTS / "data.json").write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
        print("wrote viewer/ghosts/data.json: {} missions".format(len(data["missions"])))
    args.out = out
    for run in data["runs"]:
        print("  {:<34} {:<9} reward {:.3f}  missions {}  rovers lost {}".format(
            run["label"][:34], run["kind"], run["reward"],
            " ".join("{:.2f}".format(m["reward"]) for m in run["missions"]), run["lost"]))
    if not args.data_only:
        page = standalone(data)
        args.out.write_text(page, encoding="utf-8")
        print("wrote {} ({:.1f} MB)".format(args.out.name, len(page) / 1e6))
    return 0


if __name__ == "__main__":
    sys.exit(main())
