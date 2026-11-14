#!/usr/bin/env python3
"""Draw every saved Lightlag Live run against the reference: docs/lightlag-live-results.svg.

    python3 -m lightlag_live.results_chart

Reads the same folders as the ghost demo (`docs/lightlag-runs/live-*/run.json` and each run's
`artifacts/evaluator/result.json`), plus the two baselines. Standard library only. The file is
a plain SVG with light and dark colours; open it directly to get a tooltip on every mark.
"""

from __future__ import annotations

import json
import sys
from html import escape
from pathlib import Path
from typing import Any, Dict, List

REPO = Path(__file__).resolve().parent.parent
RUNS = REPO / "docs" / "lightlag-runs"
OUT = REPO / "docs" / "lightlag-live-results.svg"
BASELINES = [("live-do-nothing", "does nothing"), ("live-stop-early", "reference, cut off after 90 s")]
FAMILIES = ["Opus 5.5", "Sonnet 5.5", "Haiku 5.5", "Fable 5.2"]

W, LEFT, RIGHT = 860, 150, 28
STYLE = """
  svg { --surface: #fcfcfb; --ink: #0b0b0b; --ink2: #52514e; --muted: #8a8983; --grid: #e7e6e1; --series: #2a78d6; }
  @media (prefers-color-scheme: dark) {
    svg { --surface: #1a1a19; --ink: #f0efec; --ink2: #c3c2b7; --muted: #8c8b84; --grid: #33332f; --series: #3987e5; }
  }
  text { font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; fill: var(--ink2); font-size: 12px; }
  .title { fill: var(--ink); font-size: 15px; font-weight: 600; }
  .head { fill: var(--ink); font-size: 13px; font-weight: 600; }
  .row { fill: var(--ink); font-size: 13px; }
  .tick { fill: var(--muted); font-size: 11px; font-variant-numeric: tabular-nums; }
  .note { fill: var(--muted); font-size: 11px; }
  .grid { stroke: var(--grid); stroke-width: 1; }
  .ref { stroke: var(--ink); stroke-width: 2; }
  .agent { fill: var(--series); stroke: var(--surface); stroke-width: 2; }
  .shot { fill: var(--surface); stroke: var(--series); stroke-width: 2; }
  .base { fill: var(--muted); stroke: var(--surface); stroke-width: 2; }
"""


def load() -> Dict[str, Any]:
    runs = []
    for path in sorted(RUNS.glob("live-*/run.json")):
        meta = json.loads(path.read_text(encoding="utf-8"))
        result = json.loads((path.parent / "artifacts" / "evaluator" / "result.json").read_text(encoding="utf-8"))
        runs.append({"label": meta["label"], "kind": meta["kind"], "how": meta.get("how", ""),
                     "family": next((f for f in FAMILIES if f in meta.get("model", "") or f in meta["label"]), ""),
                     "agent": "agent" in meta.get("how", "").lower(),
                     "reward": result["reward"], "missions": [m["reward"] for m in result["missions"]],
                     "lost": [not m["alive"] for m in result["missions"]]})
    baselines = []
    for folder, text in BASELINES:
        path = RUNS / folder / "artifacts" / "evaluator" / "result.json"
        if path.exists():
            baselines.append({"label": text, "reward": json.loads(path.read_text(encoding="utf-8"))["reward"]})
    reference = next(run for run in runs if run["kind"] == "reference")
    return {"reference": reference, "claude": [run for run in runs if run["kind"] != "reference"], "baselines": baselines}


def chart(data: Dict[str, Any]) -> str:
    reference, claude = data["reference"], data["claude"]
    families = [f for f in FAMILIES if any(run["family"] == f for run in claude)]
    out: List[str] = []
    add = out.append
    top_scale = 0.8
    x = lambda v: LEFT + (W - LEFT - RIGHT) * v / top_scale
    rows = families + ["Baselines"]
    row_y = {name: 96 + 34 * i for i, name in enumerate(rows)}
    panel_b = row_y[rows[-1]] + 78
    plot_top, plot_bottom = panel_b + 34, panel_b + 34 + 150
    height = plot_bottom + 56

    add('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" '
        'aria-label="Lightlag Live results: every Claude run scores below the reference controller">'.format(w=W, h=height))
    add("<style>{}</style>".format(STYLE))
    add('<rect width="100%" height="100%" fill="var(--surface)"/>')
    wins = sum(run["reward"] < reference["reward"] for run in claude)
    add('<text class="title" x="20" y="28">The reference scored higher than {} of {} Claude runs</text>'.format(wins, len(claude)))
    add('<text x="20" y="47">Lightlag Live: mean score over six missions, from 0 to 1. Each mark is one saved run.</text>')

    # panel A: campaign scores by model
    for value in (0, 0.2, 0.4, 0.6, 0.8):
        add('<line class="grid" x1="{0:.1f}" x2="{0:.1f}" y1="72" y2="{1}"/>'.format(x(value), row_y[rows[-1]] + 16))
        add('<text class="tick" x="{:.1f}" y="{}" text-anchor="middle">{:.1f}</text>'.format(x(value), row_y[rows[-1]] + 32, value))
    rx = x(reference["reward"])
    add('<line class="ref" x1="{0:.1f}" x2="{0:.1f}" y1="66" y2="{1}"><title>Reference controller: {2:.3f}</title></line>'.format(
        rx, row_y[rows[-1]] + 16, reference["reward"]))
    add('<text class="head" x="{:.1f}" y="62" text-anchor="middle">Reference {:.2f}</text>'.format(rx, reference["reward"]))
    for family in families:
        y = row_y[family]
        add('<text class="row" x="20" y="{}">Claude {}</text>'.format(y + 4, family))
        members = sorted((run for run in claude if run["family"] == family), key=lambda run: run["reward"])
        for run in members:
            add('<circle class="{}" cx="{:.1f}" cy="{}" r="{}"><title>{}: {:.3f}</title></circle>'.format(
                "agent" if run["agent"] else "shot", x(run["reward"]), y, 7 if run["agent"] else 6,
                escape(run["label"]), run["reward"]))
        best = members[-1]
        add('<text class="tick" x="{:.1f}" y="{}">{:.2f}</text>'.format(x(best["reward"]) + 11, y + 4, best["reward"]))
    y = row_y["Baselines"]
    add('<text class="row" x="20" y="{}">Baselines</text>'.format(y + 4))
    for base in data["baselines"]:
        add('<circle class="base" cx="{:.1f}" cy="{}" r="6"><title>{}: {:.3f}</title></circle>'.format(
            x(base["reward"]), y, escape(base["label"]), base["reward"]))
        add('<text class="note" x="{:.1f}" y="{}">{} {:.2f}</text>'.format(x(base["reward"]) + 11, y + 4, escape(base["label"]), base["reward"]))

    # legend: one row, names in ink beside the mark that carries the identity
    legend_y = row_y[rows[-1]] + 56
    add('<circle class="agent" cx="26" cy="{}" r="7"/><text x="38" y="{}">agent in Harbor (OpenCode), on the real clock</text>'.format(legend_y, legend_y + 4))
    add('<circle class="shot" cx="330" cy="{}" r="6"/><text x="342" y="{}">one request, one program</text>'.format(legend_y, legend_y + 4))
    add('<line class="ref" x1="512" x2="512" y1="{}" y2="{}"/><text x="522" y="{}">reference controller</text>'.format(legend_y - 8, legend_y + 8, legend_y + 4))

    # panel B: the same runs, mission by mission
    add('<text class="head" x="20" y="{}">Mission by mission: the reference does not win every one, it wins on average</text>'.format(panel_b + 12))
    count = len(reference["missions"])
    band = (W - LEFT - RIGHT) / count
    yv = lambda v: plot_bottom - (plot_bottom - plot_top) * v
    for value in (0, 0.5, 1.0):
        add('<line class="grid" x1="{}" x2="{}" y1="{y:.1f}" y2="{y:.1f}"/>'.format(LEFT, W - RIGHT, y=yv(value)))
        add('<text class="tick" x="{}" y="{:.1f}" text-anchor="end">{:.1f}</text>'.format(LEFT - 8, yv(value) + 4, value))
    add('<text class="row" x="20" y="{:.1f}">Score in</text><text class="row" x="20" y="{:.1f}">each mission</text>'.format(
        yv(0.5) - 4, yv(0.5) + 13))
    ordered = sorted(claude, key=lambda run: (FAMILIES.index(run["family"]) if run["family"] in FAMILIES else 9, -run["reward"]))
    for k in range(count):
        centre = LEFT + band * (k + 0.5)
        add('<text class="tick" x="{:.1f}" y="{}" text-anchor="middle">Mission {}</text>'.format(centre, plot_bottom + 20, k + 1))
        spread = min(band - 34, 14 * max(1, len(ordered) - 1))
        for i, run in enumerate(ordered):
            offset = (i / max(1, len(ordered) - 1) - 0.5) * spread if len(ordered) > 1 else 0
            note = " (rover lost)" if run["lost"][k] else ""
            add('<circle class="{}" cx="{:.1f}" cy="{:.1f}" r="{}"><title>{}, mission {}: {:.3f}{}</title></circle>'.format(
                "agent" if run["agent"] else "shot", centre + offset, yv(run["missions"][k]), 5.5 if run["agent"] else 4.5,
                escape(run["label"]), k + 1, run["missions"][k], note))
        ry = yv(reference["missions"][k])
        add('<line class="ref" x1="{:.1f}" x2="{:.1f}" y1="{y:.1f}" y2="{y:.1f}"><title>Reference, mission {n}: {v:.3f}</title></line>'.format(
            centre - band / 2 + 10, centre + band / 2 - 10, y=ry, n=k + 1, v=reference["missions"][k]))
    add('<text class="note" x="20" y="{}">Six missions chosen by a rule that looks only at the reference; see docs/lightlag-live.md.</text>'.format(height - 14))
    add("</svg>")
    return "\n".join(out) + "\n"


def main() -> int:
    data = load()
    OUT.write_text(chart(data), encoding="utf-8")
    print("wrote {} ({} Claude runs, reference {:.3f})".format(OUT.relative_to(REPO), len(data["claude"]), data["reference"]["reward"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
