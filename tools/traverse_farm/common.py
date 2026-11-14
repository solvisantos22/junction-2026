"""Small helpers shared by the local and Modal commands. Standard library only."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


def parse_seeds(text: str) -> List[int]:
    """`100-103,7` -> [100, 101, 102, 103, 7]."""
    seeds: List[int] = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            first, last = part.split("-")
            seeds.extend(range(int(first), int(last) + 1))
        else:
            seeds.append(int(part))
    return seeds


def parse_policies(text: str) -> Dict[str, Dict[str, Any]]:
    """Comma-separated names. `pilot`, `greedy`, `straight`, `nothing`, `pilot:{"floor": 6}`,
    `program:<path to a file defining play(tools)>`, or `agent:<folder>/<entry.py>` for an agent's own
    script started as __main__ with a stand-in lightlag_client (programs run only on Modal)."""
    policies: Dict[str, Dict[str, Any]] = {}
    for part in _split_top_level(text):
        if part.startswith("agent:"):
            entry = Path(part[len("agent:"):])
            files = {path.name: path.read_text(encoding="utf-8") for path in sorted(entry.parent.glob("*.py"))
                     if path.name not in ("lightlag_client.py", "lightlag_surface.py", "detach.py")}
            name = "agent:" + entry.parent.parent.name if entry.parent.name == "program" else "agent:" + entry.parent.name
            policies[name] = {"policy": "program", "files": files, "entry": entry.name, "label": entry.as_posix()}
        elif part.startswith("program:"):
            path = Path(part[len("program:"):])
            name = "program:" + (path.parent.name if path.stem == "policy" else path.stem)
            policies[name] = {"policy": "program", "program": path.read_text(encoding="utf-8"), "label": path.as_posix()}
        elif part.startswith("pilot:"):
            policies[part] = {"policy": "pilot", "options": json.loads(part[len("pilot:"):])}
        else:
            policies[part] = {"policy": part}
    return policies


def _split_top_level(text: str) -> List[str]:
    """Split on commas that are not inside braces, so JSON options survive."""
    parts, depth, current = [], 0, ""
    for char in text:
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        if char == "," and depth == 0:
            parts.append(current.strip())
            current = ""
        else:
            current += char
    if current.strip():
        parts.append(current.strip())
    return parts


def format_table(table: Dict[str, Dict[str, Any]]) -> str:
    lines = ["{:<40} {:>7} {:>7} {:>5} {:>5} {:>7} {:>8} {:>8}".format(
        "policy", "worlds", "mean", "lost", "away", "errors", "crashed", "sec")]
    for name, row in table.items():
        lines.append("{:<40} {:>7} {:>7} {:>5} {:>5} {:>7} {:>8} {:>8}".format(
            name[:40], row["worlds"], "-" if row["mean"] is None else "{:.3f}".format(row["mean"]),
            row["lost"], row["away"], row.get("errors", 0), row["crashed"],
            "-" if row["seconds"] is None else "{:.1f}".format(row["seconds"])))
    return "\n".join(lines)


def format_versus(baseline: str, table: Dict[str, Dict[str, Any]]) -> str:
    """Each policy minus the baseline, world by world: mean, 95% paired bootstrap interval, and counts."""
    lines = ["{:<40} {:>7} {:>8} {:>18} {:>7} {:>6} {:>6}".format(
        "policy minus " + baseline, "worlds", "mean", "95% interval", "higher", "same", "lower")]
    for name, row in table.items():
        if not row.get("worlds"):
            lines.append("{:<40} {:>7}".format(name[:40], 0))
            continue
        lines.append("{:<40} {:>7} {:>+8.3f} {:>18} {:>7} {:>6} {:>6}".format(
            name[:40], row["worlds"], row["difference"], "[{:+.3f}, {:+.3f}]".format(row["low"], row["high"]),
            row["higher"], row["equal"], row["lower"]))
    return "\n".join(lines)
