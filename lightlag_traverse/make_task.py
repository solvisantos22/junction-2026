#!/usr/bin/env python3
"""Write the Lightlag Traverse Harbor tasks: harbor/lightlag-traverse/ (one mission) and
harbor/lightlag-traverse-campaign/ (three missions at three sites, campaign.py).

    python3 -m lightlag_traverse.make_task --all           # refresh both committed tasks from the sources
    python3 -m lightlag_traverse.make_task --all --check   # exit 1 if either committed task is stale
    python3 -m lightlag_traverse.make_task                 # the one-mission task only (--campaign: the other)
    python3 -m lightlag_traverse.make_task /tmp/variant --seed 1003

A Docker build cannot reach files outside the task directory, so the task carries copies of the
simulator, the server and the reference. Edit the originals, then run this. Python 3.9+,
standard library only. `tests/lightlag_traverse/test_task.py` fails when the copies are stale.

The layout is the team's (`harbor/lightlag`): the simulator in a sidecar container the agent
reaches only through the five tools, a collect hook that finishes the mission after the agent's
container has stopped, a separate verifier that reads the simulator's own result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Dict

from lightlag_live.make_task import stale, write

from .environment import MISSION
from .terrain import GENERATOR

REPO = Path(__file__).resolve().parent.parent
TASK = REPO / "harbor" / "lightlag-traverse"

# One world. The seed was fixed as the year before any controller or model had played it; the
# pilot was developed on seeds 1 to 99 and checked on 1000 upward (docs/lightlag-traverse.md).
SEED = 2026
AGENT_TIMEOUT_SEC = 1800

# The campaign: three worlds, fixed (as the three years after the one-mission task's) before any
# controller or model had played them. Three missions take longer to play than one, and an agent
# may want to look at a mission before the next, so the session is longer.
CAMPAIGN_TASK = REPO / "harbor" / "lightlag-traverse-campaign"
CAMPAIGN_SEEDS = (2027, 2028, 2029)
CAMPAIGN_AGENT_TIMEOUT_SEC = 2700

# target path in the task -> source path in the repository
COPIES = {
    # The simulator's container: the episode, the team's service and this ground's server.
    "environment/simulator/lightlag/__init__.py": "lightlag/__init__.py",
    "environment/simulator/lightlag/environment.py": "lightlag/environment.py",
    "environment/simulator/lightlag/model.py": "lightlag/model.py",
    "environment/simulator/lightlag_mcp/__init__.py": "lightlag_mcp/__init__.py",
    "environment/simulator/lightlag_mcp/service.py": "lightlag_mcp/service.py",
    "environment/simulator/lightlag_mcp/finish.py": "lightlag_mcp/finish.py",
    "environment/simulator/lightlag_traverse/surface.py": "lightlag_traverse/surface.py",
    "environment/simulator/lightlag_traverse/terrain.py": "lightlag_traverse/terrain.py",
    "environment/simulator/lightlag_traverse/environment.py": "lightlag_traverse/environment.py",
    "environment/simulator/lightlag_traverse/server.py": "lightlag_traverse/server.py",
    "environment/simulator/requirements.txt": "lightlag_mcp/requirements.txt",
    # The agent's container: a client for the five tools, the published ground model as code, and
    # a launcher that keeps a long-running program alive.
    "environment/lightlag_client.py": "lightlag_mcp/client.py",
    "environment/lightlag_surface.py": "lightlag_traverse/surface.py",
    "environment/detach.py": "lightlag_live/detach.py",
    # The reference run: a controller that sees only the five tools. No simulator code.
    "solution/lightlag_client.py": "lightlag_mcp/client.py",
    "solution/lightlag_traverse/surface.py": "lightlag_traverse/surface.py",
    "solution/lightlag_traverse/planning.py": "lightlag_traverse/planning.py",
    "solution/lightlag_traverse/pilot.py": "lightlag_traverse/pilot.py",
    # The verifier: the team's grader for one episode.
    "tests/grade.py": "harbor/lightlag/tests/grade.py",
}

# The campaign's simulator also needs the campaign itself.
CAMPAIGN_COPIES = dict(COPIES, **{"environment/simulator/lightlag_traverse/campaign.py": "lightlag_traverse/campaign.py"})

STUB_SIMULATOR_INIT = '"""Simulator copy: the ground, the mission and its server; no controller."""\n'
STUB_SOLUTION_INIT = '"""The reference pilot: public geometry and planning only; no simulator."""\n'

TASK_TOML = """\
schema_version = "1.4"

# The simulator's result directory. Harbor copies it out of the simulator's
# container after the agent's container has stopped, and into the verifier's.
# The agent's container never holds it.
artifacts = [{ source = "/evaluator", service = "lightlag" }]

[task]
name = "neural-network-november/%(name)s"
version = "%(version)s"
description = "%(description)s"
authors = []
keywords = [%(keywords)s]

[metadata]

[verifier]
timeout_sec = 120.0
# A fresh container the agent never touched reads the simulator's own result.
environment_mode = "separate"

# Runs inside the simulator's container once the agent's container is stopped:
# closes the mission, lets the remaining ticks pass and writes the grade.
[[verifier.collect]]
service = "lightlag"
command = "python -m lightlag_mcp.finish --url http://127.0.0.1:8000 --token-file /run/lightlag/token"
timeout_sec = 60.0

[verifier.env]

[agent]
timeout_sec = %(agent_timeout)d.0

[environment]
network_mode = "public"
build_timeout_sec = 900.0
os = "linux"

[[environment.mcp_servers]]
name = "lightlag"
transport = "streamable-http"
url = "http://lightlag:8000/mcp"

[environment.env]

[solution.env]
"""

COMPOSE = """\
# Harbor supplies the `main` service (the agent's container) and merges this file
# on top. `lightlag` is the simulator: a separate container, reached by name.
services:
  main:
    depends_on:
      lightlag:
        condition: service_healthy

  lightlag:
    build:
      context: ./simulator
    expose:
      - "8000"
    environment:
%(seed_lines)s
      LIGHTLAG_ARTIFACT_DIR: /evaluator
      LIGHTLAG_TOKEN_FILE: /run/lightlag/token
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"]
      interval: 2s
      timeout: 5s
      retries: 30
      start_period: 3s
"""

AGENT_DOCKERFILE = """\
# The agent's container. It holds no simulator and no mission secrets: the rover is
# reachable only through the `lightlag` MCP service in the other container.
FROM python:3.12-slim

RUN apt-get update \\
    && apt-get install -y --no-install-recommends curl ca-certificates git \\
    && rm -rf /var/lib/apt/lists/*

# An MCP client library and a small helper, so a program can call the five tools.
RUN pip install --no-cache-dir "mcp==2.3.0"

WORKDIR /app
COPY lightlag_client.py /app/lightlag_client.py
# The published ground model as code: how height, slope and a drive are computed.
COPY lightlag_surface.py /app/lightlag_surface.py
# Starts a long-running program outside the reach of the shell tool's time limit.
COPY detach.py /app/detach.py
"""

AGENT_DOCKERIGNORE = """\
# Keep the simulator and its configuration out of the agent image's build context.
simulator/
docker-compose.yaml
"""

SIMULATOR_DOCKERFILE = """\
# The simulator's container: one Lightlag Traverse mission served over MCP.
# The packages here are copies made by lightlag_traverse/make_task.py.
FROM python:3.12-slim

WORKDIR /srv
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY lightlag/ lightlag/
COPY lightlag_mcp/ lightlag_mcp/
COPY lightlag_traverse/ lightlag_traverse/

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
EXPOSE 8000
# 0.0.0.0 so the agent's container can reach it by service name.
CMD ["python", "-m", "lightlag_traverse.server", "--transport", "http", "--host", "0.0.0.0", "--port", "8000"]
"""

SOLVE_SH = """\
#!/bin/bash
# The reference run. It plays through the same MCP service an agent uses, with the
# same five tools and nothing else: no simulator code, no seed, no hidden values.
set -euo pipefail

cd "$(dirname "$0")"
python3 play_reference.py --url "${LIGHTLAG_MCP_URL:-http://lightlag:8000/mcp}"
"""

PLAY_REFERENCE = '''\
"""Play the mission with the traverse pilot, through the public tools."""

import argparse
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    args = parser.parse_args()
    from lightlag_client import connect
    from lightlag_traverse.pilot import fly

    started = time.time()
    with connect(args.url) as tools:
        if set(tools.tool_names()) != {"rules", "map", "telemetry_log", "uplink", "advance"}:
            raise RuntimeError("the task offers exactly the five public tools")
        pilot = fly(tools)
    print("the traverse pilot finished the mission through public MCP tools in {:.0f}s; it believes it "
          "sampled {} targets".format(time.time() - started, len(pilot.sampled)))


if __name__ == "__main__":
    sys.exit(main())
'''

PLAY_REFERENCE_CAMPAIGN = '''\
"""Play the campaign with the traverse pilot, mission after mission, through the public tools."""

import argparse
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    args = parser.parse_args()
    from lightlag_client import connect
    from lightlag_traverse.pilot import fly_campaign

    started = time.time()
    with connect(args.url) as tools:
        if set(tools.tool_names()) != {"rules", "map", "telemetry_log", "uplink", "advance"}:
            raise RuntimeError("the task offers exactly the five public tools")
        pilots = fly_campaign(tools)
    print("the traverse pilot finished {} missions through public MCP tools in {:.0f}s; it believes it "
          "sampled {} targets".format(len(pilots), time.time() - started,
                                      " + ".join(str(len(pilot.sampled)) for pilot in pilots)))


if __name__ == "__main__":
    sys.exit(main())
'''

TESTS_DOCKERFILE = """\
# The verifier's container: fresh for every trial, never touched by the agent.
FROM python:3.12-slim

WORKDIR /app
COPY . /tests/
"""

TEST_SH = """\
#!/bin/bash
# Turn the simulator's own result into the Harbor reward.
#
# /evaluator/result.json was written inside the simulator's container when the
# mission was finished, and copied here by Harbor. If it is missing, something in
# the pipeline broke: fail loudly instead of reporting a score of zero.
set -euo pipefail

python3 /tests/grade.py \\
    --result /evaluator/result.json \\
    --reward /logs/verifier/reward.txt \\
    --details /logs/verifier/lightlag-details.json
"""

INSTRUCTION = """\
# Lightlag Traverse: one sol across Mars

You are the remote operator of a rover on Mars-like ground. You reach it only through the `lightlag` MCP server, which offers five tools: `rules`, `map`, `telemetry_log`, `uplink` and `advance`.

The mission is one long traverse: %(ticks)d ticks over a map of %(width)d m by %(height)d m, with %(targets)d science targets known at launch and more appearing on the way. There is not enough time to visit them all. Which ones you go for, in what order and by which way over the ground is the task.

## Goal

Sample science targets and have the rover back at the lander when the mission ends.

Your score is the value earned from the targets you sampled, multiplied by:

- 1.0 if the rover ends within `base_radius` of the lander,
- 0.5 if it ends alive somewhere else,
- 0 if its battery reached zero,

and divided by the total value of every target of the mission, including those that only appear later. A target sampled at or before its `deadline_tick` earns its full `value`; after that it earns `late_value`. What counts is the tick at which the sample command executes.

The score lies between 0 and 1. Nobody can reach every target, so a good score is well below 1. It is computed from the rover's true state, and nothing you write or report changes it.

## Time

- Only `advance` moves the clock: `advance(n)` lets `n` ticks pass, at most 5 per call. Every other tool is free, and the clock does not run while you think.
- You get this one mission. There is no reset and no practice run.
- Your session is limited to %(session)s in total.

## What makes it hard

- **Commands arrive late.** A command sent at tick `t` executes at tick `t + delay_ticks + 1` at the earliest. Commands execute one per tick, in the order sent.
- **Telemetry is old.** A packet describes the rover at `packet.tick` and reaches you `delay_ticks` later. Commands you have already sent may not show in it yet.
- **The ground is not flat.** `map` gives a height grid and a terrain class for every cell. Slip grows with the slope the rover is climbing and depends on the terrain; on a cross slope the rover slides downhill; energy is spent per wheel metre and per metre climbed. `rules` gives the formulas under `physics`, `drive` and `ground`. Each terrain's base slip is hidden inside a published range.
- **Steep ground stops the rover.** Where the slope exceeds `max_tilt`, the rover stops at the last safe position and every command still queued is cleared. Crater walls and the scarp are that steep. They have breaches and passes.
- **Energy comes from the sun.** The battery is charged every tick by a sun that is low at the start, highest in the middle and low again at the end, through panels whose efficiency is hidden inside a published range. A battery that reaches zero ends the rover for good.
- **Sensing is noisy and the rover drifts.** `rules()["sensing"]` gives the numbers. Every reported position after the tick-0 briefing carries noise, reported visual odometry carries noise, and each drive goes off the commanded heading by a hidden, slowly changing bias. Sampling, the return to the lander and safety stops are decided by the rover's true position.
- **Targets have deadlines and new ones appear.** A `target_discovered` event travels in delayed telemetry; `map` lists the target once that packet has arrived.

## How to act

- `rules` and `map` tell you everything that is fixed. The map is about 65 kB of JSON, so read it with a program.
- `uplink` queues 1 to 5 commands: `{"action": "drive", "heading_deg": H, "metres": M}` (0 degrees is east, 90 is north, `M` in (0, 5]), `{"action": "sample"}` or `{"action": "wait"}`.
- A Python helper is waiting in `/app/lightlag_client.py`. It gives a program the same five tools as plain function calls:

  ```python
  from lightlag_client import connect

  with connect("http://lightlag:8000/mcp") as tools:
      rules = tools.rules()
      world = tools.map()
      packets = tools.telemetry_log()
      acks = tools.uplink([{"action": "drive", "heading_deg": 90, "metres": 2.5}])
      out = tools.advance(1)     # current_tick, episode_complete, packets
  ```

  A rejected request raises `ValueError` with the reason and changes nothing.
- `/app/lightlag_surface.py` is the published ground model as code. `Surface(cell_m, elevation_cm, terrain)` reads height, slope and terrain class from the grid exactly as the simulator does, and `drive(...)` runs one drive command with the slip values you give it. Use it or write your own.
- The mission needs at least %(advances)d `advance` calls and several hundred commands. You may call the tools yourself, but a program that plays the mission is the practical way.
- A program that runs for long is best started with `python3 /app/detach.py python3 your_program.py`. It returns at once and the program's output goes to `autopilot.log`. When a command reaches your shell tool's time limit, the tool may stop everything that command started, background jobs included. The mission waits for you either way.
- Your program stops when your session ends, so do not finish before `episode_complete` is true. If you stop early, the remaining ticks pass with the rover where it is.

You may write and run any code.
"""

INSTRUCTION_CAMPAIGN = """\
# Lightlag Traverse: %(words)s sols at %(words)s sites

You are the remote operator of a rover on Mars-like ground. You reach it only through the `lightlag` MCP server, which offers five tools: `rules`, `map`, `telemetry_log`, `uplink` and `advance`.

The campaign is %(words)s missions, played one after another, each at its own site. Every mission is one long traverse: %(ticks)d ticks over a map of %(width)d m by %(height)d m, with %(targets)d science targets known at launch and more appearing on the way, and the rover starting at that site's lander with a full battery. There is not enough time to visit every target. Which ones you go for, in what order and by which way over the ground is the task, at every site.

## Goal

Sample science targets, and have the rover back at the lander when each mission ends.

A mission earns the value of the targets sampled in it, multiplied by:

- 1.0 if the rover ends within `base_radius` of the lander,
- 0.5 if it ends alive somewhere else,
- 0 if its battery reached zero.

Your score is the value earned in all %(words)s missions divided by the total value of every target of all of them, including those that only appear later. A target sampled at or before its `deadline_tick` earns its full `value`; after that it earns `late_value`. What counts is the tick at which the sample command executes.

The score lies between 0 and 1. Nobody can reach every target, so a good score is well below 1. It is computed from the rover's true state, and nothing you write or report changes it.

## Time and missions

- Only `advance` moves the clock: `advance(n)` lets `n` ticks pass in the mission in play, at most 5 per call and never past its end. Every other tool is free, and the clock does not run while you think.
- When a mission's last tick passes, it is scored and the next mission begins at once, at its tick 0. From then on `rules`, `map`, `telemetry_log` and `uplink` describe the new mission. The `advance` that ends a mission returns `episode_complete: true`; it also returns `campaign_complete: true` when that was the last mission. `map()`, every telemetry packet and every `advance` reply carry `mission`.
- Every site has its own ground and targets, and its own hidden values: each terrain's base slip, the panels' efficiency and the heading bias are drawn afresh for every mission.
- You get these %(words)s missions. There is no reset and no practice run.
- Your session is limited to %(session)s in total.

## What makes it hard

- **Commands arrive late.** A command sent at tick `t` executes at tick `t + delay_ticks + 1` at the earliest. Commands execute one per tick, in the order sent.
- **Telemetry is old.** A packet describes the rover at `packet.tick` and reaches you `delay_ticks` later. Commands you have already sent may not show in it yet.
- **The ground is not flat.** `map` gives a height grid and a terrain class for every cell. Slip grows with the slope the rover is climbing and depends on the terrain; on a cross slope the rover slides downhill; energy is spent per wheel metre and per metre climbed. `rules` gives the formulas under `physics`, `drive` and `ground`. Each terrain's base slip is hidden inside a published range.
- **Steep ground stops the rover.** Where the slope exceeds `max_tilt`, the rover stops at the last safe position and every command still queued is cleared. Crater walls and the scarp are that steep. They have breaches and passes.
- **Energy comes from the sun.** The battery is charged every tick by a sun that is low at the start of each mission, highest in the middle and low again at the end, through panels whose efficiency is hidden inside a published range. A battery that reaches zero ends the rover for good.
- **Sensing is noisy and the rover drifts.** `rules()["sensing"]` gives the numbers. Every reported position after the tick-0 briefing carries noise, reported visual odometry carries noise, and each drive goes off the commanded heading by a hidden, slowly changing bias. Sampling, the return to the lander and safety stops are decided by the rover's true position.
- **Targets have deadlines and new ones appear.** A `target_discovered` event travels in delayed telemetry; `map` lists the target once that packet has arrived.

## How to act

- `rules` and `map` tell you everything that is fixed about the mission in play. The map is about 65 kB of JSON, so read it with a program.
- `uplink` queues 1 to 5 commands: `{"action": "drive", "heading_deg": H, "metres": M}` (0 degrees is east, 90 is north, `M` in (0, 5]), `{"action": "sample"}` or `{"action": "wait"}`.
- A Python helper is waiting in `/app/lightlag_client.py`. It gives a program the same five tools as plain function calls:

  ```python
  from lightlag_client import connect

  with connect("http://lightlag:8000/mcp") as tools:
      rules = tools.rules()
      world = tools.map()          # the mission in play: world["mission"]
      packets = tools.telemetry_log()
      acks = tools.uplink([{"action": "drive", "heading_deg": 90, "metres": 2.5}])
      out = tools.advance(1)       # current_tick, episode_complete, campaign_complete, mission, packets
  ```

  A rejected request raises `ValueError` with the reason and changes nothing.
- `/app/lightlag_surface.py` is the published ground model as code. `Surface(cell_m, elevation_cm, terrain)` reads height, slope and terrain class from the grid exactly as the simulator does, and `drive(...)` runs one drive command with the slip values you give it. Use it or write your own.
- Every mission needs at least %(advances)d `advance` calls and several hundred commands. You may call the tools yourself, but a program that plays the campaign, mission after mission, is the practical way.
- A program that runs for long is best started with `python3 /app/detach.py python3 your_program.py`. It returns at once and the program's output goes to `autopilot.log`. When a command reaches your shell tool's time limit, the tool may stop everything that command started, background jobs included. The campaign waits for you either way.
- Your program stops when your session ends, so do not finish before `campaign_complete` is true. If you stop early, the remaining ticks of every remaining mission pass with the rover where it is; a mission not yet begun passes with its rover standing at the lander, and earns nothing.

You may write and run any code.
"""


KEYWORDS ='"rl-environment", "signal-delay", "planning", "terrain", "state-estimation", "mcp"'


def _assemble(copies: Dict[str, str], toml: Dict[str, object], seed_lines: str, simulator_dockerfile: str,
              play_reference: str, instruction: str, settings: Dict[str, object]) -> Dict[str, bytes]:
    files: Dict[str, bytes] = {target: (REPO / source).read_bytes() for target, source in copies.items()}
    files["environment/simulator/lightlag_traverse/__init__.py"] = STUB_SIMULATOR_INIT.encode()
    files["solution/lightlag_traverse/__init__.py"] = STUB_SOLUTION_INIT.encode()
    files["task.toml"] = (TASK_TOML % toml).encode()
    files["environment/docker-compose.yaml"] = (COMPOSE % {"seed_lines": seed_lines}).encode()
    files["environment/Dockerfile"] = AGENT_DOCKERFILE.encode()
    files["environment/.dockerignore"] = AGENT_DOCKERIGNORE.encode()
    files["environment/simulator/Dockerfile"] = simulator_dockerfile.encode()
    files["solution/solve.sh"] = SOLVE_SH.encode()
    files["solution/play_reference.py"] = play_reference.encode()
    files["tests/Dockerfile"] = TESTS_DOCKERFILE.encode()
    files["tests/test.sh"] = TEST_SH.encode()
    files["instruction.md"] = instruction.encode()
    manifest = {
        "schema_version": 1,
        "settings": settings,
        "sources_sha256": {source: hashlib.sha256((REPO / source).read_bytes()).hexdigest()
                           for source in sorted(set(copies.values()))},
        "task_sha256": {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())},
    }
    files["manifest.json"] = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    return files


def _numbers(session_seconds: int) -> Dict[str, object]:
    ticks = MISSION["max_ticks"]
    return {"ticks": ticks, "width": int(GENERATOR["width_m"]), "height": int(GENERATOR["height_m"]),
            "targets": GENERATOR["initial_targets"], "advances": -(-ticks // 5),
            "session": "{:g} minutes".format(session_seconds / 60)}


def build(seed: int = SEED) -> Dict[str, bytes]:
    """Every file of the one-mission task, as bytes, built in memory from the repository's sources."""
    ticks = MISSION["max_ticks"]
    toml = {"name": "lightlag-traverse", "version": "0.1.2", "keywords": KEYWORDS, "agent_timeout": AGENT_TIMEOUT_SEC,
            "description": "Drive a rover for one sol across Mars-like ground: {} ticks, a height map with craters "
                           "and a scarp, solar power, more targets than can be reached.".format(ticks)}
    seed_lines = ("      # The mission's seed belongs to the evaluator and exists only in this container.\n"
                  '      LIGHTLAG_SEED: "{}"'.format(seed))
    return _assemble(COPIES, toml, seed_lines, SIMULATOR_DOCKERFILE, PLAY_REFERENCE,
                     INSTRUCTION % _numbers(AGENT_TIMEOUT_SEC), {"seed": seed, "mission": MISSION})


def build_campaign(seeds=CAMPAIGN_SEEDS) -> Dict[str, bytes]:
    """Every file of the campaign task, as bytes, built in memory from the repository's sources."""
    seeds = tuple(seeds)
    ticks = MISSION["max_ticks"]
    words = {2: "two", 3: "three", 4: "four"}.get(len(seeds), str(len(seeds)))
    toml = {"name": "lightlag-traverse-campaign", "version": "0.1.0", "agent_timeout": CAMPAIGN_AGENT_TIMEOUT_SEC,
            "keywords": KEYWORDS + ', "robustness"',
            "description": "Drive a rover for one sol at each of {} Mars-like sites: {} missions of {} ticks on height "
                           "maps with craters and a scarp, solar power, more targets than can be reached; scored "
                           "over all of them.".format(words, words, ticks)}
    seed_lines = ("      # The missions' seeds belong to the evaluator and exist only in this container.\n"
                  '      LIGHTLAG_SEEDS: "{}"'.format(",".join(str(seed) for seed in seeds)))
    simulator = SIMULATOR_DOCKERFILE.replace(
        "# The simulator's container: one Lightlag Traverse mission served over MCP.",
        "# The simulator's container: a Lightlag Traverse campaign served over MCP, one mission\n"
        "# after another; the missions' seeds come from LIGHTLAG_SEEDS (docker-compose.yaml).")
    numbers = dict(_numbers(CAMPAIGN_AGENT_TIMEOUT_SEC), missions=len(seeds), words=words)
    return _assemble(CAMPAIGN_COPIES, toml, seed_lines, simulator, PLAY_REFERENCE_CAMPAIGN,
                     INSTRUCTION_CAMPAIGN % numbers, {"seeds": list(seeds), "mission": MISSION})


VARIANTS = {"single": (TASK, build), "campaign": (CAMPAIGN_TASK, build_campaign)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("destination", nargs="?", type=Path, default=None)
    parser.add_argument("--seed", type=int, default=SEED, help="the one-mission task's world")
    parser.add_argument("--campaign", action="store_true", help="the campaign task instead of the one-mission task")
    parser.add_argument("--all", action="store_true", help="both committed tasks")
    parser.add_argument("--check", action="store_true", help="report staleness, write nothing")
    args = parser.parse_args(argv)
    if args.all and args.destination is not None:
        parser.error("--all writes the committed tasks; give no destination")
    names = ["single", "campaign"] if args.all else ["campaign" if args.campaign else "single"]
    status = 0
    for name in names:
        default, maker = VARIANTS[name]
        destination = args.destination or default
        files = maker(args.seed) if name == "single" else maker()
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
