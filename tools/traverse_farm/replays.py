"""Whole missions for the demo: farm rows with replays, saved as the run folders the Traverse demo reads.

Each world gets its own folder, `<out>/world-<seed>/`, holding one `traverse-<name>/` run folder per
policy: `run.json` (who drove: `kind` "reference", "claude" or "scripted", a label, and how the farm
played it) and `artifacts/evaluator/` (the result and the replay), as `lightlag_traverse.play.save_run`
writes them. `viewer/build_traverse.py --runs <out>/world-<seed>` turns one world into a page; that
builder also rewrites `viewer/traverse/data.json`, so build from a copy of `viewer/` unless the
page is meant to replace the main demo.

A Claude program's run keeps the label and model of the run it came from, and says that its saved
program was replayed by the farm without the agent. Standard library only.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


def _origin(spec: Dict[str, Any]) -> Dict[str, Any]:
    """The run.json of the run a saved program came from: docs/lightlag-runs/<run>/(program/)file.py."""
    path = Path(spec.get("label") or "")
    for folder in (path.parent, path.parent.parent):
        if (folder / "run.json").exists():
            return json.loads((folder / "run.json").read_text(encoding="utf-8"))
    return {}


def run_meta(name: str, spec: Dict[str, Any], row: Dict[str, Any]) -> Dict[str, Any]:
    """run.json for one replayed mission."""
    played = {"seed": row["seed"], "mission": row.get("mission") or {}, "source": row.get("source"),
              "host": row.get("host"), "farm_candidate": name}
    if spec["policy"] == "pilot":
        options = spec.get("options") or {}
        return dict(played, kind="reference", label="Reference pilot" + (" (other options)" if options else ""),
                    how="lightlag_traverse pilot, played by the Traverse farm", options=options)
    if spec["policy"] == "program":
        origin = _origin(spec)
        return dict(played, kind="claude", label=origin.get("label") or name, model=origin.get("model", ""),
                    how="its saved program, replayed without the agent", program=spec.get("label"),
                    program_id=row.get("program_id"), died_tick=row.get("died_tick"), program_tick=row.get("program_tick"),
                    error=row.get("error"))
    return dict(played, kind="scripted", label=name, how="lightlag_traverse.play policy {}, played by the Traverse farm".format(name))


def folder_name(name: str) -> str:
    """traverse-<name> from a policy name such as agent:traverse-agent-opus-3 or pilot."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.split(":", 1)[-1].lower()).strip("-")
    return slug if slug.startswith("traverse-") else "traverse-" + slug


def write(rows: List[Dict[str, Any]], policies: Dict[str, Dict[str, Any]], out: Path) -> List[Path]:
    """Save every row that holds a replay; a row without one (a crash) is reported, not saved."""
    from lightlag_traverse import play

    written = []
    for row in rows:
        name = row.get("candidate")
        replay: Optional[Dict[str, Any]] = row.get("replay")
        if replay is None or name not in policies:
            print("  no replay for {} on world {}: {}".format(name, row.get("seed"), row.get("crash") or row.get("error")))
            continue
        folder = out / "world-{}".format(row["seed"]) / folder_name(name)
        if folder.exists():
            raise SystemExit("{} exists: choose another --out or remove it first".format(folder))
        play.save_run(folder, {"result": replay["result"], "replay": replay}, run_meta(name, policies[name], row))
        written.append(folder)
    return written
