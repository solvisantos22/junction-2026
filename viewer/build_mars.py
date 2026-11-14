#!/usr/bin/env python3
"""Build the 3D Mars demo: gather the runs, then write a standalone page.

    python3 viewer/build_mars.py                 # writes viewer/mars/data.json and viewer/mars-demo.html
    python3 viewer/build_mars.py --data-only     # just refresh viewer/mars/data.json for development

`viewer/mars-demo.html` contains everything (three.js, the app, the runs) and
opens by double-click with no network. For development, serve `viewer/mars/`
with any static server and open `index.html`; it loads the same files separately.

The model run comes from a saved Harbor trial: the simulator's replay and call
transcript, plus the agent's own trajectory. Scripted policies are played here,
through the same episode service the MCP server uses, so they have a call
transcript too. Nothing is invented: every call shown in the demo was made.
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

REPO = Path(__file__).resolve().parent.parent
MARS = REPO / "viewer" / "mars"
RUNS = REPO / "docs" / "lightlag-runs"
sys.path.insert(0, str(REPO))

MODEL_RUN = RUNS / "opencode-opus-5-5-seed7-delay3"
SCRIPTED = [
    ("reference", "Reference controller", "scripted · predicts the present from commands in transit"),
    ("stale_telemetry", "Forgets commands in transit", "scripted · treats old telemetry as the present"),
    ("move_and_wait", "Waits for every command", "scripted · one command, then waits to see it land"),
]


def model_run(run_dir: Path) -> Dict[str, Any]:
    """The model's run: replay + every tool call it made, in order, with its own words."""
    replay = json.loads((run_dir / "artifacts" / "evaluator" / "replay.json").read_text(encoding="utf-8"))
    transcript = [
        json.loads(line)
        for line in (run_dir / "artifacts" / "evaluator" / "transcript.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    trajectory = json.loads((run_dir / "agent" / "trajectory.json").read_text(encoding="utf-8"))
    result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    calls: List[Dict[str, Any]] = []
    report = ""
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
            if name.startswith("lightlag_"):
                record = transcript[cursor]
                cursor += 1
                if name != "lightlag_" + record["tool"]:
                    raise SystemExit("trajectory and simulator transcript disagree at call {}".format(cursor))
                calls.append({
                    "kind": "mcp", "tool": record["tool"], "arguments": record["arguments"],
                    "tick": record["tick_before"], "tick_after": record["tick_after"], "ok": record["ok"],
                    "error": record.get("error"), "summary": record.get("summary") or {},
                    "say": say if index == 0 else "",
                })
                tick = record["tick_after"]
            else:
                calls.append({
                    "kind": "shell", "tool": name, "arguments": tool_call.get("arguments") or {},
                    "tick": tick, "tick_after": tick, "ok": True, "error": None, "summary": {},
                    "say": say if index == 0 else "",
                })
    if cursor != len(transcript):
        raise SystemExit("{} simulator calls were not matched to the agent's trajectory".format(len(transcript) - cursor))
    agent = result.get("agent_info") or {}
    usage = result.get("agent_result") or {}
    model = (agent.get("model_info") or {}).get("name", "model")
    return {
        "id": "claude", "kind": "model",
        "label": "Claude Opus 5.5" if model == "claude-opus-5-5" else model,
        "sub": "{} {} · real run through Harbor".format(agent.get("name", "agent"), agent.get("version", "")).strip(),
        "replay": replay, "belief": [], "calls": calls, "report": report,
        "cost_usd": usage.get("cost_usd"),
    }


def scripted_run(policy: str, label: str, sub: str, seed: int, delay: int) -> Dict[str, Any]:
    """Play a scripted policy through the episode service and keep its call transcript."""
    from lightlag import Config
    from lightlag_controllers import ALL_STRATEGIES, drive, make
    from lightlag_mcp import EpisodeService

    strategy = {s.name: s for s in ALL_STRATEGIES}[policy]
    with tempfile.TemporaryDirectory() as directory:
        service = EpisodeService(seed=seed, config=Config(delay_ticks=delay), artifact_dir=directory)
        controller = make(strategy)
        drive(service, controller)
        service.finish()
        replay = json.loads((Path(directory) / "replay.json").read_text(encoding="utf-8"))
        transcript = service.transcript()
    calls = [{
        "kind": "mcp", "tool": c["tool"], "arguments": c["arguments"], "tick": c["tick_before"],
        "tick_after": c["tick_after"], "ok": c["ok"], "error": c.get("error"), "summary": c.get("summary") or {}, "say": "",
    } for c in transcript]
    belief = {note["for_tick"]: list(note["believed"]) for note in controller.trace}
    return {
        "id": policy, "kind": "scripted", "label": label, "sub": sub, "replay": replay,
        "belief": [{"tick": t, "position": p} for t, p in sorted(belief.items())],
        "calls": calls, "report": "", "cost_usd": None,
    }


def gather() -> Dict[str, Any]:
    model = model_run(MODEL_RUN)
    seed, delay = model["replay"]["seed"], model["replay"]["config"]["delay_ticks"]
    runs = [model] + [scripted_run(policy, label, sub, seed, delay) for policy, label, sub in SCRIPTED]
    return {"title": "Lightlag", "seed": seed, "delay": delay, "runs": runs}


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
    print("wrote viewer/mars/data.json: {} runs, seed {}, delay {}".format(len(data["runs"]), data["seed"], data["delay"]))
    for run in data["runs"]:
        result = run["replay"]["result"]
        print("  {:<28} reward {:.2f}  calls {:>3}".format(
            run["label"], result["raw_score"] / result["max_available_value"], len(run["calls"])))
    if not args.data_only:
        page = standalone(data)
        args.out.write_text(page, encoding="utf-8")
        print("wrote {} ({:.1f} MB)".format(args.out.relative_to(REPO), len(page) / 1e6))
    return 0


if __name__ == "__main__":
    sys.exit(main())
