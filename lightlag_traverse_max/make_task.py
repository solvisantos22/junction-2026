#!/usr/bin/env python3
"""Write the Harbor tasks of the Traverse MAX map: two campaigns on the held-out evaluation worlds.

    python3 -m lightlag_traverse_max.make_task           # refresh both committed tasks
    python3 -m lightlag_traverse_max.make_task --check   # exit 1 if either is stale

  harbor/lightlag-traverse-max-fair/       fair worlds 500, 510, 520 (manh_max about 0.5)
  harbor/lightlag-traverse-max-superhard/  superhard worlds 505, 509, 515 (manh_max about 0.1-0.2)

Each is Kristján's campaign task (lightlag_traverse/make_task.py, imported, unchanged) with the MAX
map behind it: three missions in a row, scored together, the same agent image, verifier, grader,
time limit and reference solution (his pilot, which knows nothing of the MAX map). What differs:
the simulator's container also holds lightlag_traverse_max (the MAX environment and its server)
and starts that server, the seeds are the held-out worlds, and the instruction has one section on
what the MAX map changes. The worlds are held out (lightlag_traverse_max/heldout.py): never train
or tune on them. Standard library only; tests/lightlag_traverse_max/test_task.py fails when stale.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, Sequence

from lightlag_live.make_task import stale, write
from lightlag_traverse import make_task as kristjans

from .heldout import FAIR_WORLDS, SUPERHARD_WORLDS
from .oneshot import max_section

REPO = Path(__file__).resolve().parent.parent
TASKS = {
    "fair": (REPO / "harbor" / "lightlag-traverse-max-fair", FAIR_WORLDS),
    "superhard": (REPO / "harbor" / "lightlag-traverse-max-superhard", SUPERHARD_WORLDS),
}
VERSION = "0.1.0"

COPIES = dict(kristjans.CAMPAIGN_COPIES, **{
    "environment/simulator/lightlag_traverse_max/__init__.py": "lightlag_traverse_max/__init__.py",
    "environment/simulator/lightlag_traverse_max/environment.py": "lightlag_traverse_max/environment.py",
    "environment/simulator/lightlag_traverse_max/server.py": "lightlag_traverse_max/server.py",
})

SIMULATOR_DOCKERFILE = kristjans.SIMULATOR_DOCKERFILE.replace(
    "# The simulator's container: one Lightlag Traverse mission served over MCP.",
    "# The simulator's container: a Lightlag Traverse campaign on the MAX map served over MCP,\n"
    "# one mission after another; the missions' seeds come from LIGHTLAG_SEEDS (docker-compose.yaml).",
).replace(
    "COPY lightlag_traverse/ lightlag_traverse/\n",
    "COPY lightlag_traverse/ lightlag_traverse/\nCOPY lightlag_traverse_max/ lightlag_traverse_max/\n",
).replace("lightlag_traverse/make_task.py", "lightlag_traverse_max/make_task.py").replace(
    '"lightlag_traverse.server"', '"lightlag_traverse_max.server"')


def build(group: str) -> Dict[str, bytes]:
    """Every file of one MAX campaign task, as bytes, built in memory from the repository's sources."""
    seeds = tuple(TASKS[group][1])
    ticks = kristjans.MISSION["max_ticks"]
    words = {2: "two", 3: "three", 4: "four"}.get(len(seeds), str(len(seeds)))
    toml = {"name": "lightlag-traverse-max-{}".format(group), "version": VERSION,
            "agent_timeout": kristjans.CAMPAIGN_AGENT_TIMEOUT_SEC,
            "keywords": kristjans.KEYWORDS + ', "robustness", "intermittent-link"',
            "description": "Drive a rover for one sol at each of {} Mars-like sites on the MAX map ({} held-out "
                           "worlds): {} missions of {} ticks, a link open only in relay passes, lost packets, wild "
                           "fixes, hidden soft ground; scored over all of them.".format(words, group, words, ticks)}
    seed_lines = ("      # The missions' seeds belong to the evaluator and exist only in this container.\n"
                  '      LIGHTLAG_SEEDS: "{}"'.format(",".join(str(seed) for seed in seeds)))
    numbers = dict(kristjans._numbers(kristjans.CAMPAIGN_AGENT_TIMEOUT_SEC), missions=len(seeds), words=words)
    instruction = kristjans.INSTRUCTION_CAMPAIGN % numbers
    instruction = instruction.replace("\n## What makes it hard\n", "\n" + max_section() + "## What makes it hard\n", 1)
    instruction = instruction.replace("# Lightlag Traverse: ", "# Lightlag Traverse MAX: ", 1)
    return kristjans._assemble(COPIES, toml, seed_lines, SIMULATOR_DOCKERFILE, kristjans.PLAY_REFERENCE_CAMPAIGN,
                               instruction, {"seeds": list(seeds), "map": "max", "mission": kristjans.MISSION})


def main(argv: Sequence[str] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="report staleness, write nothing")
    args = parser.parse_args(argv)
    status = 0
    for group, (destination, _) in TASKS.items():
        files = build(group)
        wrong = stale(destination, files)
        if args.check:
            if wrong:
                print("stale: {}: {}".format(destination, ", ".join(wrong)))
                status = 1
            else:
                print("{} is up to date ({} files)".format(destination, len(files)))
            continue
        write(destination, files)
        print("wrote {} files to {} ({} changed)".format(len(files), destination, len(wrong)))
    return status


if __name__ == "__main__":
    sys.exit(main())
