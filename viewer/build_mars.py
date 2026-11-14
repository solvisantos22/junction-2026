#!/usr/bin/env python3
"""Build the 3D Mars demo: gather the saved runs, then write a standalone page.

    python3 viewer/build_mars.py                 # writes viewer/mars/data.json and viewer/mars-demo.html
    python3 viewer/build_mars.py --data-only     # just refresh viewer/mars/data.json for development

`viewer/mars-demo.html` contains everything (three.js, the app, the runs) and
opens by double-click with no network. For development, serve `viewer/mars/`
with any static server and open `index.html`; it loads the same files separately.

Every run comes from a saved Harbor trial under `docs/lightlag-runs/`: the
simulator's replay and call transcript, plus the agent's own trajectory when a
model played. Nothing is played or invented here: every call shown in the demo
was made in that trial. Standard library only.
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

REPO = Path(__file__).resolve().parent.parent
MARS = REPO / "viewer" / "mars"
RUNS = REPO / "docs" / "lightlag-runs"

# Two missions from the overnight evaluation (docs/lightlag-overnight-evaluation.md).
# Each lists the three unchanged-prompt attempts by Claude Opus 5.5 from block A,
# in the order they ran, and the frozen reference on the same seed. `featured`
# is the run the demo opens on. These seeds were chosen overnight because the
# model had failed on them before, so they are not a random sample of maps.
MISSIONS: List[Dict[str, Any]] = [
    {
        "id": "deadlines", "name": "Deadlines", "featured": "claude-3",
        "brief": "Seven samples, each with a deadline. Two appear mid-mission. Every tick drains the battery, "
                 "and the score only counts if the rover is home and alive at tick 50.",
        "runs": [
            ("claude-1", "overnight-a01-rush-seed501-r1-opus-5-5"),
            ("claude-2", "overnight-a04-rush-seed501-r2-opus-5-5"),
            ("claude-3", "overnight-a07-rush-seed501-r3-opus-5-5"),
            ("reference", "rush-seed501-delay3-kf-mpc"),
        ],
    },
    {
        "id": "sand", "name": "Sand", "featured": "claude-1",
        "brief": "The same rules, plus noisy position fixes and targets across a sand field, "
                 "where the wheels slip by an amount nobody is told.",
        "runs": [
            ("claude-1", "overnight-a02-rush-noisy-seed502-r1-opus-5-5"),
            ("claude-2", "overnight-a05-rush-noisy-seed502-r2-opus-5-5"),
            ("claude-3", "overnight-a08-rush-noisy-seed502-r3-opus-5-5"),
            ("reference", "rush-noisy-seed502-delay3-kf-mpc"),
        ],
    },
]


def _transcript(run_dir: Path) -> List[Dict[str, Any]]:
    text = (run_dir / "artifacts" / "evaluator" / "transcript.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _mcp_call(record: Dict[str, Any], say: str = "") -> Dict[str, Any]:
    return {
        "kind": "mcp", "tool": record["tool"], "arguments": record["arguments"],
        "tick": record["tick_before"], "tick_after": record["tick_after"], "ok": record["ok"],
        "error": record.get("error"), "summary": record.get("summary") or {}, "say": say,
    }


def load_run(run_id: str, folder: str) -> Dict[str, Any]:
    """One saved trial: its replay and every tool call, in order, with the agent's own words."""
    run_dir = RUNS / folder
    replay = json.loads((run_dir / "artifacts" / "evaluator" / "replay.json").read_text(encoding="utf-8"))
    transcript = _transcript(run_dir)
    result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    agent = result.get("agent_info") or {}
    trajectory_path = run_dir / "agent" / "trajectory.json"
    calls: List[Dict[str, Any]] = []
    report = ""
    if trajectory_path.exists():
        trajectory = json.loads(trajectory_path.read_text(encoding="utf-8"))
        cursor = 0
        tick = 0
        for step in trajectory["steps"]:
            if step.get("source") != "agent":
                continue
            say = (step.get("message") or "").strip()
            tool_calls = step.get("tool_calls") or []
            if say and not tool_calls:
                report = say
            for index, tool_call in enumerate(tool_calls):
                name = tool_call["function_name"]
                first = say if index == 0 else ""
                if name.startswith("lightlag_"):
                    record = transcript[cursor]
                    cursor += 1
                    if name != "lightlag_" + record["tool"]:
                        raise SystemExit("{}: trajectory and simulator transcript disagree at call {}".format(folder, cursor))
                    calls.append(_mcp_call(record, first))
                    tick = record["tick_after"]
                else:
                    # the agent's own tools: its shell, or a call to a tool that does not exist
                    calls.append({
                        "kind": "shell" if name == "bash" else "other", "tool": name,
                        "arguments": tool_call.get("arguments") or {}, "tick": tick, "tick_after": tick,
                        "ok": name == "bash", "error": None, "summary": {}, "say": first,
                    })
        if cursor != len(transcript):
            raise SystemExit("{}: {} simulator calls were not matched to the agent's trajectory".format(folder, len(transcript) - cursor))
        model = (agent.get("model_info") or {}).get("name", "model")
        attempt = int(run_id.rsplit("-", 1)[1])
        kind = "model"
        label = "Claude Opus 5.5" if model == "claude-opus-5-5" else model
        short = "Claude #{}".format(attempt)
        sub = "attempt {} of 3 · {} {} through Harbor".format(attempt, agent.get("name", "agent"), agent.get("version", "")).strip()
    else:
        calls = [_mcp_call(record) for record in transcript]
        kind, label, short = "reference", "Reference controller", "Reference"
        sub = "scripted Kalman filter + MPC · same mission, same tools"
    saved_reward = float((run_dir / "verifier" / "reward.txt").read_text(encoding="utf-8").strip())
    return {
        "id": run_id, "kind": kind, "label": label, "short": short, "sub": sub, "source": folder,
        "replay": replay, "calls": calls, "report": report, "reward": saved_reward,
        "cost_usd": (result.get("agent_result") or {}).get("cost_usd"),
    }


def mission_definition(replay: Dict[str, Any]) -> Dict[str, Any]:
    """What makes two replays the same mission. The per-run log of realised heading errors is left out."""
    dynamic = dict(replay.get("dynamic") or {})
    sensing = dict(dynamic.get("sensing") or {})
    sensing.pop("heading_errors", None)
    dynamic["sensing"] = sensing
    return {"seed": replay["seed"], "world": replay["world"], "config": replay["config"], "dynamic": dynamic}


def gather() -> Dict[str, Any]:
    missions = []
    for spec in MISSIONS:
        runs = [load_run(run_id, folder) for run_id, folder in spec["runs"]]
        first = runs[0]["replay"]
        for run in runs:
            if mission_definition(run["replay"]) != mission_definition(first):
                raise SystemExit("{}: {} is not the same mission as {}".format(spec["id"], run["source"], runs[0]["source"]))
        dynamic = first.get("dynamic") or {}
        missions.append({
            "id": spec["id"], "name": spec["name"], "brief": spec["brief"], "featured": spec["featured"],
            "seed": first["seed"], "profile": dynamic.get("profile", "core"),
            "delay": first["config"]["delay_ticks"], "ticks": first["config"]["max_ticks"], "runs": runs,
        })
    return {"title": "Lightlag", "missions": missions}


def standalone(data: Dict[str, Any]) -> str:
    """One HTML file: styles, three.js, the app and the data all inline."""
    def b64(path: Path) -> str:
        return base64.b64encode(path.read_bytes()).decode("ascii")

    page = (MARS / "index.html").read_text(encoding="utf-8")
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
  window.LIGHTLAG_DATA = JSON.parse(text("src-data"));
  await import(url(text("src-app").split("'three'").join(JSON.stringify(three))));
}})().catch(error => {{ document.body.insertAdjacentHTML("beforeend", "<pre style='color:#f66;padding:20px'>" + error + "</pre>"); throw error; }});
</script>""".format(
        css=(MARS / "style.css").read_text(encoding="utf-8"),
        core=b64(MARS / "vendor" / "three.core.js"),
        three=b64(MARS / "vendor" / "three.module.js"),
        app=b64(MARS / "app.js"),
        data=payload,
    )
    return page[:start] + inline + page[end:]


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-only", action="store_true", help="only refresh viewer/mars/data.json")
    parser.add_argument("--out", type=Path, default=REPO / "viewer" / "mars-demo.html")
    args = parser.parse_args(argv)
    data = gather()
    (MARS / "data.json").write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    print("wrote viewer/mars/data.json")
    for mission in data["missions"]:
        print("  {} ({} seed {}, delay {}, {} ticks)".format(mission["name"], mission["profile"], mission["seed"], mission["delay"], mission["ticks"]))
        for run in mission["runs"]:
            result = run["replay"]["result"]
            print("    {:<22} reward {:.2f}  calls {:>3}  alive {!s:<5} at base {}".format(
                run["short"], run["reward"], len(run["calls"]), result["alive"], result["at_base"]))
    if not args.data_only:
        page = standalone(data)
        args.out.write_text(page, encoding="utf-8")
        print("wrote {} ({:.1f} MB)".format(args.out.relative_to(REPO), len(page) / 1e6))
    return 0


if __name__ == "__main__":
    sys.exit(main())
