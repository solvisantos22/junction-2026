#!/usr/bin/env python3
"""Copy the simulator, MCP server and reference controller into the Harbor task.

    python3 harbor/sync_task.py           # refresh the copies
    python3 harbor/sync_task.py --check   # exit 1 if a copy is stale

A Harbor task has to be self-contained: its Docker build contexts cannot reach
files outside the task directory. So the task carries copies of the code it runs.
The originals stay the single place to edit; this script and its test keep the
copies identical to them. Standard library only, Python 3.9+.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence

REPO = Path(__file__).resolve().parent.parent
TASK = REPO / "harbor" / "lightlag"
SIMULATOR = TASK / "environment" / "simulator"
SOLUTION = TASK / "solution"


def plan() -> Dict[Path, Path]:
    """Destination -> source, for every copied file."""
    copies: Dict[Path, Path] = {}
    # The simulator's container: the physics and the MCP server, nothing else.
    for name in ("__init__.py", "environment.py", "model.py"):
        copies[SIMULATOR / "lightlag" / name] = REPO / "lightlag" / name
    for name in ("__init__.py", "__main__.py", "finish.py", "server.py", "service.py", "requirements.txt"):
        copies[SIMULATOR / "lightlag_mcp" / name] = REPO / "lightlag_mcp" / name
    # The reference run: the controllers and a client, without the simulator.
    for source in sorted((REPO / "lightlag_controllers").glob("*.py")):
        if source.name != "pilot.py":  # the pilot imports the simulator; the solution must not need it
            copies[SOLUTION / "lightlag_controllers" / source.name] = source
    copies[SOLUTION / "mcp_client.py"] = REPO / "lightlag_mcp" / "client.py"
    return copies


def stale(copies: Dict[Path, Path]) -> List[str]:
    problems: List[str] = []
    for destination, source in copies.items():
        if not destination.exists():
            problems.append("missing: {}".format(destination.relative_to(REPO)))
        elif destination.read_bytes() != source.read_bytes():
            problems.append("differs from {}: {}".format(source.relative_to(REPO), destination.relative_to(REPO)))
    expected = set(copies)
    for folder in (SIMULATOR / "lightlag", SIMULATOR / "lightlag_mcp", SOLUTION / "lightlag_controllers"):
        if folder.exists():
            for found in sorted(folder.rglob("*")):
                if found.is_file() and "__pycache__" not in found.parts and found not in expected:
                    problems.append("not produced by sync: {}".format(found.relative_to(REPO)))
    return problems


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="report stale copies without changing anything")
    args = parser.parse_args(argv)
    copies = plan()
    if args.check:
        problems = stale(copies)
        for problem in problems:
            print(problem)
        return 1 if problems else 0
    for destination, source in copies.items():
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
    print("copied {} files into {}".format(len(copies), TASK.relative_to(REPO)))
    leftovers = stale(copies)
    for problem in leftovers:
        print(problem)
    return 1 if leftovers else 0


if __name__ == "__main__":
    sys.exit(main())
