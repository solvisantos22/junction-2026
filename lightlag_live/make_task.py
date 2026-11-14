#!/usr/bin/env python3
"""Write the Lightlag Live Harbor task: harbor/lightlag-live/.

    python3 -m lightlag_live.make_task                 # refresh the committed task from the sources
    python3 -m lightlag_live.make_task --check         # exit 1 if the committed task is stale
    python3 -m lightlag_live.make_task /tmp/variant --missions 8000:rush_noisy,8001:rush_noisy

A Docker build cannot reach files outside the task directory, so the task carries copies of
the simulator, the server and the reference. Edit the originals, then run this. Python 3.9+,
standard library only. `tests/lightlag_live/test_task.py` fails when the copies are stale.

The mission list below is the task's one setting. It was fixed by a rule that looks only at
the reference controller (see docs/lightlag-live.md), before any model played these maps.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Dict, List

REPO = Path(__file__).resolve().parent.parent
TASK = REPO / "harbor" / "lightlag-live"

# The first six seeds from 9001 upward on which the frozen reference, turn-based at this noise
# level, ends at base with a score of at least 0.6 (it averages 0.50 over 9001-9040).
MISSIONS = "9003:rush_noisy,9007:rush_noisy,9008:rush_noisy,9012:rush_noisy,9013:rush_noisy,9020:rush_noisy"
SETTINGS = {"delay": 3, "ticks": 50, "seconds_per_tick": 1.0, "noise_level": 2.0}
AGENT_TIMEOUT_SEC = 1800  # task.toml's [agent] timeout; the instruction tells the agent, so it is no hidden trap

# target path in the task -> source path in the repository
COPIES = {
    # The simulator's container: the episode, the campaign service and its MCP server.
    "environment/simulator/lightlag/__init__.py": "lightlag/__init__.py",
    "environment/simulator/lightlag/environment.py": "lightlag/environment.py",
    "environment/simulator/lightlag/model.py": "lightlag/model.py",
    "environment/simulator/lightlag_dynamic/environment.py": "lightlag_dynamic/environment.py",
    "environment/simulator/lightlag_dynamic/missions.py": "lightlag_dynamic/missions.py",
    "environment/simulator/lightlag_live/__init__.py": "lightlag_live/__init__.py",
    "environment/simulator/lightlag_live/__main__.py": "lightlag_live/__main__.py",
    "environment/simulator/lightlag_live/campaign.py": "lightlag_live/campaign.py",
    "environment/simulator/lightlag_live/finish.py": "lightlag_live/finish.py",
    "environment/simulator/lightlag_live/reference.py": "lightlag_live/reference.py",
    "environment/simulator/lightlag_live/server.py": "lightlag_live/server.py",
    "environment/simulator/requirements.txt": "lightlag_mcp/requirements.txt",
    # The agent's container: a client for the five public tools, and a launcher that keeps the
    # agent's program running after the shell command that started it has returned.
    "environment/lightlag_client.py": "lightlag_mcp/client.py",
    "environment/detach.py": "lightlag_live/detach.py",
    # The reference run: public-tool controllers only, no simulator code.
    "solution/lightlag_client.py": "lightlag_mcp/client.py",
    "solution/campaign_reference.py": "lightlag_live/reference.py",
    "solution/lightlag_dynamic/controllers.py": "lightlag_dynamic/controllers.py",
    "solution/lightlag_dynamic/kf_mpc.py": "lightlag_dynamic/kf_mpc.py",
}

STUB_SIMULATOR_INIT = '"""Simulator copy: the dynamic environment and its missions only; no controllers."""\n'
STUB_SOLUTION_INIT = '"""Public-tool controllers only; simulator modules are deliberately absent."""\n'

TASK_TOML = """\
schema_version = "1.4"

# The simulator's result directory. Harbor copies it out of the simulator's
# container after the agent's container has stopped, and into the verifier's.
# The agent's container never holds it.
artifacts = [{ source = "/evaluator", service = "lightlag" }]

[task]
name = "neural-network-november/lightlag-live"
version = "0.1.3"
description = "Build an autopilot: %(count)d rover missions in a row through a signal delay, on a real-time clock, with noisy sensing."
authors = []
keywords = ["rl-environment", "signal-delay", "real-time", "control", "state-estimation", "mcp"]

[metadata]

[verifier]
timeout_sec = 120.0
# A fresh container the agent never touched reads the simulator's own result.
environment_mode = "separate"

# Runs inside the simulator's container once the agent's container is stopped:
# closes the campaign, lets every remaining tick of every remaining mission pass
# at once and writes the grade.
[[verifier.collect]]
service = "lightlag"
command = "python -m lightlag_live.finish --url http://127.0.0.1:8000 --token-file /run/lightlag/token"
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
      # Campaign settings belong to the evaluator and exist only in this container.
      LIGHTLAG_MISSIONS: "%(missions)s"
      LIGHTLAG_DELAY: "%(delay)d"
      LIGHTLAG_TICKS: "%(ticks)d"
      LIGHTLAG_SECONDS_PER_TICK: "%(seconds_per_tick)s"
      LIGHTLAG_NOISE_LEVEL: "%(noise_level)s"
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
# The agent's container. It holds no simulator code and no campaign secrets: the
# rover is reachable only through the `lightlag` MCP service in the other container.
FROM python:3.12-slim

RUN apt-get update \\
    && apt-get install -y --no-install-recommends curl ca-certificates git \\
    && rm -rf /var/lib/apt/lists/*

# An MCP client library and a small helper, so a program can call the five tools.
RUN pip install --no-cache-dir "mcp==2.3.0"

WORKDIR /app
COPY lightlag_client.py /app/lightlag_client.py
# Starts the agent's program outside the reach of its shell tool's time limit.
COPY detach.py /app/detach.py
"""

AGENT_DOCKERIGNORE = """\
# Keep the simulator and its configuration out of the agent image's build context.
simulator/
docker-compose.yaml
"""

SIMULATOR_DOCKERFILE = """\
# The simulator's container: one Lightlag Live campaign served over MCP.
# The packages here are copies made by lightlag_live/make_task.py.
FROM python:3.12-slim

WORKDIR /srv
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY lightlag/ lightlag/
COPY lightlag_dynamic/ lightlag_dynamic/
COPY lightlag_live/ lightlag_live/

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
EXPOSE 8000
# 0.0.0.0 so the agent's container can reach it by service name.
CMD ["python", "-m", "lightlag_live", "--transport", "http", "--host", "0.0.0.0", "--port", "8000"]
"""

SOLVE_SH = """\
#!/bin/bash
# The reference run. It plays through the same MCP service an agent uses, with the
# same five tools and nothing else: no simulator code, no seeds, no hidden values.
set -euo pipefail

cd "$(dirname "$0")"
python3 play_reference.py --url "${LIGHTLAG_MCP_URL:-http://lightlag:8000/mcp}"
"""

PLAY_REFERENCE = '''\
"""Play the whole campaign with the team's frozen KF + MPC controller, through the public tools."""

import argparse
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    args = parser.parse_args()
    from campaign_reference import play_campaign
    from lightlag_client import connect
    from lightlag_dynamic.controllers import POLICIES

    started = time.time()
    with connect(args.url) as tools:
        if set(tools.tool_names()) != {"rules", "map", "telemetry_log", "uplink", "advance"}:
            raise RuntimeError("the task offers exactly the five public tools")
        play_campaign(tools, POLICIES["kf_mpc"],
                      on_mission=lambda number: print("mission {} at {:.0f}s".format(number, time.time() - started),
                                                      flush=True))
    print("kf_mpc finished the campaign through public MCP tools in {:.0f}s".format(time.time() - started))


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
# campaign was finished, and copied here by Harbor. If it is missing, something in
# the pipeline broke: fail loudly instead of reporting a score of zero.
set -euo pipefail

python3 /tests/grade.py \\
    --result /evaluator/result.json \\
    --reward /logs/verifier/reward.txt \\
    --details /logs/verifier/lightlag-details.json
"""

GRADE = '''\
#!/usr/bin/env python3
"""Write the Harbor reward for one Lightlag Live campaign.

Reward = the mean over the campaign's missions of raw_score / max_available_value, in [0, 1]:

    raw_score = credited value of sampled targets x 1.0 at base, x 0.5 alive elsewhere, x 0 if dead

Only the simulator's result file is read. It comes from the simulator's container, which the
agent can reach through the five tools and nothing else. The mean is recomputed here from
the per-mission numbers and must agree with the simulator's. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from typing import Any, Dict, Optional, Sequence


class BadResult(ValueError):
    """The result file is absent or not what the simulator writes."""


def mission_reward(mission: Dict[str, Any]) -> float:
    try:
        raw = mission["raw_score"]
        available = mission["max_available_value"]
    except (KeyError, TypeError):
        raise BadResult("a mission lacks raw_score or max_available_value") from None
    for name, value in (("raw_score", raw), ("max_available_value", available)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise BadResult("{} is not a finite number".format(name))
    if available <= 0:
        raise BadResult("max_available_value must be positive")
    if raw < 0 or raw > available + 1e-9:
        raise BadResult("raw_score {} is outside 0..{}".format(raw, available))
    return min(1.0, max(0.0, raw / available))


def reward_from(result: Dict[str, Any]) -> float:
    try:
        missions = result["missions"]
        claimed = result["reward"]
    except (KeyError, TypeError):
        raise BadResult("result lacks missions or reward") from None
    if not isinstance(missions, list) or not missions:
        raise BadResult("missions must be a non-empty list")
    reward = sum(mission_reward(mission) for mission in missions) / len(missions)
    if isinstance(claimed, bool) or not isinstance(claimed, (int, float)) or abs(claimed - reward) > 1e-9:
        raise BadResult("the campaign reward does not match its missions")
    return reward


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--result", required=True, help="result.json written by the simulator")
    parser.add_argument("--reward", required=True, help="where to write the single reward number")
    parser.add_argument("--details", default=None, help="optional copy of the result plus the reward")
    args = parser.parse_args(argv)
    try:
        with open(args.result, encoding="utf-8") as stream:
            result = json.load(stream)
        reward = reward_from(result)
    except (OSError, ValueError) as failure:
        print("cannot grade: {}".format(failure), file=sys.stderr)
        return 1
    os.makedirs(os.path.dirname(os.path.abspath(args.reward)), exist_ok=True)
    with open(args.reward, "w", encoding="utf-8") as stream:
        stream.write("{:.6f}\\n".format(reward))
    if args.details:
        with open(args.details, "w", encoding="utf-8") as stream:
            json.dump(dict(result, reward=reward), stream, indent=2, sort_keys=True)
            stream.write("\\n")
    print("reward {:.6f} over {} missions: {}".format(
        reward, len(result["missions"]),
        ", ".join("{:.3f}{}".format(mission_reward(m), "" if m.get("alive") else " (rover lost)")
                  for m in result["missions"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''

INSTRUCTION = """\
# Lightlag Live: build an autopilot for a rover you cannot joystick

You are the remote operator of a rover. You reach it only through the `lightlag` MCP server, which offers five tools: `rules`, `map`, `telemetry_log`, `uplink` and `advance`.

The clock is real. Once you start, one tick passes every %(seconds)s, the rover is given %(count)d missions in a row, and nothing waits for you. A mission of %(ticks)d ticks is over in %(mission_seconds)s, so calling the tools by hand cannot keep up. Your job is to write a program that drives the rover, start it, and let it run.

## Goal

In each mission, sample science targets and have the rover back at base when the mission ends.

A mission's score is the value earned from the targets it sampled, multiplied by:

- 1.0 if the rover ends within `base_radius` of base,
- 0.5 if it ends alive somewhere else,
- 0 if its battery reached zero,

and divided by the total value generated for that mission, including targets that only appear later. A target sampled at or before its `deadline_tick` earns its full `value`; after that it earns `late_value`. What counts is the tick at which the sample command executes.

Your score is the mean over all %(count)d missions, so it lies between 0 and 1. It is computed from the rover's true state. Nothing you write or report changes it. A mission you do not play scores 0.

## The clock

- Nothing moves until your first `uplink` or `advance`. Until then `rules`, `map` and `telemetry_log` are free: read the first mission and prepare for as long as you like.
- From then on one tick passes every %(seconds)s of real time, whether or not you call a tool.
- Each mission lasts `max_ticks` ticks. The next one starts the moment it ends, on a new map, with a recharged rover at base. `rules`, `map` and `telemetry_log` then describe the new mission. You cannot see a map before its mission starts.
- `advance(n)` waits until `n` more ticks have passed, never past the end of the mission. It returns `current_tick`, `episode_complete` (this mission has ended), `campaign_complete`, `mission` and every telemetry packet that arrived since your previous `advance`.
- The whole campaign takes %(campaign_seconds)s once started. Your session is limited to %(session)s in total, preparation included, so start the campaign while at least %(campaign_seconds)s remain.

## What makes it hard

- **Commands arrive late.** A command sent at tick `t` executes at tick `t + delay_ticks + 1` at the earliest. Commands execute one per tick, in the order sent.
- **Telemetry is old.** A packet describes the rover at `packet.tick` and reaches you `delay_ticks` later. Commands you have already sent may not show in it yet.
- **Wheel slip is unknown.** Each terrain has a slip value that `rules` gives only as a range. A drive of `M` wheel metres moves the rover `M x (1 - slip)`. Telemetry reports `wheel_odometry` and `visual_odometry`.
- **Sensing is noisy and the rover drifts.** `rules()["sensing"]` gives the numbers. Every reported position after the tick-0 briefing carries noise, reported visual odometry carries noise, and each drive goes off the commanded heading by a hidden, slowly changing bias. Sampling, returning to base and safety stops are decided by the rover's true position.
- **Targets have deadlines and new ones appear.** A `target_discovered` event travels in delayed telemetry; `map` lists the target once that packet has arrived.
- **The battery is finite.** Every tick costs energy until the mission ends, whether the rover moves or not; driving costs more on sand; a sample costs energy even if it fails.
- **A hazard or the map edge stops the rover** where it is and cancels every command queued at that moment.

## How to act

- `rules` and `map` tell you everything that is fixed for the mission in progress. `uplink` queues 1 to 5 commands: `{"action": "drive", "heading_deg": H, "metres": M}` (0 degrees is east, 90 is north, `M` in (0, 5]), `{"action": "sample"}` or `{"action": "wait"}`.
- A Python helper is waiting in `/app/lightlag_client.py`. It gives a program the same five tools as plain function calls:

  ```python
  from lightlag_client import connect

  with connect("http://lightlag:8000/mcp") as tools:
      rules = tools.rules()            # free
      world = tools.map()              # free
      packets = tools.telemetry_log()  # free
      # The next two start the clock the first time either of them is called:
      # acks = tools.uplink([{"action": "drive", "heading_deg": 90, "metres": 2.5}])
      # out = tools.advance(1)
  ```

  A rejected request raises `ValueError` with the reason and changes nothing.
- Start your program with the launcher: `python3 /app/detach.py python3 autopilot.py`. It returns at once, the program keeps running, and its output goes to `autopilot.log`, which you can read with separate short commands. Do not rely on `&` or `nohup` for this: when a command reaches your shell tool's time limit, the tool may stop everything that command started, background jobs included, and the campaign would go on without your program.
- You may also call the tools yourself at any time, and you may change or restart your program while the campaign runs. The clock does not wait for either.

You may write and run any code. Your program stops when your session ends, so do not finish before `campaign_complete` is true. If you stop early, the mission in progress still runs to its end with the battery draining, and the missions after it score 0.
"""


def build(missions: str = MISSIONS, **overrides) -> Dict[str, bytes]:
    """Every file of the task, as bytes, built in memory from the repository's sources."""
    settings = dict(SETTINGS, **overrides)
    count = len(missions.split(","))
    seconds = settings["seconds_per_tick"]

    def duration(value):
        value = float(value)
        if value < 120:
            return "{:g} seconds".format(value)
        return "{:g} minutes".format(round(value / 60, 1))

    files: Dict[str, bytes] = {target: (REPO / source).read_bytes() for target, source in COPIES.items()}
    files["environment/simulator/lightlag_dynamic/__init__.py"] = STUB_SIMULATOR_INIT.encode()
    files["solution/lightlag_dynamic/__init__.py"] = STUB_SOLUTION_INIT.encode()
    files["task.toml"] = (TASK_TOML % {"count": count, "agent_timeout": AGENT_TIMEOUT_SEC}).encode()
    files["environment/docker-compose.yaml"] = (COMPOSE % dict(settings, missions=missions)).encode()
    files["environment/Dockerfile"] = AGENT_DOCKERFILE.encode()
    files["environment/.dockerignore"] = AGENT_DOCKERIGNORE.encode()
    files["environment/simulator/Dockerfile"] = SIMULATOR_DOCKERFILE.encode()
    files["solution/solve.sh"] = SOLVE_SH.encode()
    files["solution/play_reference.py"] = PLAY_REFERENCE.encode()
    files["tests/Dockerfile"] = TESTS_DOCKERFILE.encode()
    files["tests/test.sh"] = TEST_SH.encode()
    files["tests/grade.py"] = GRADE.encode()
    files["instruction.md"] = (INSTRUCTION % {
        "count": count, "ticks": settings["ticks"],
        "seconds": "second" if float(seconds) == 1 else "{:g} seconds".format(float(seconds)),
        "mission_seconds": duration(settings["ticks"] * float(seconds)),
        "campaign_seconds": duration(count * settings["ticks"] * float(seconds)),
        "session": duration(AGENT_TIMEOUT_SEC),
    }).encode()
    manifest = {
        "schema_version": 1,
        "settings": dict(settings, missions=missions),
        "sources_sha256": {source: hashlib.sha256((REPO / source).read_bytes()).hexdigest()
                           for source in sorted(set(COPIES.values()))},
        "task_sha256": {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())},
    }
    files["manifest.json"] = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    return files


def stale(destination: Path, files: Dict[str, bytes]) -> List[str]:
    """Names that differ between `files` and what is on disk, including leftovers."""
    wrong = [name for name, data in files.items()
             if not (destination / name).is_file() or (destination / name).read_bytes() != data]
    if destination.is_dir():
        present = {str(path.relative_to(destination)) for path in destination.rglob("*")
                   if path.is_file() and "__pycache__" not in path.parts and path.name != ".DS_Store"}
        wrong += sorted(present - set(files))
    return wrong


def write(destination: Path, files: Dict[str, bytes]) -> None:
    for name in stale(destination, files):
        if name not in files:
            (destination / name).unlink()
    for name, data in files.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        if target.suffix == ".sh":
            target.chmod(0o755)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("destination", nargs="?", type=Path, default=TASK)
    parser.add_argument("--missions", default=MISSIONS)
    parser.add_argument("--noise-level", type=float, default=SETTINGS["noise_level"])
    parser.add_argument("--seconds-per-tick", type=float, default=SETTINGS["seconds_per_tick"])
    parser.add_argument("--check", action="store_true", help="report staleness, write nothing")
    args = parser.parse_args(argv)
    files = build(args.missions, noise_level=args.noise_level, seconds_per_tick=args.seconds_per_tick)
    wrong = stale(args.destination, files)
    if args.check:
        if wrong:
            print("stale: " + ", ".join(wrong))
            return 1
        print("{} is up to date ({} files)".format(args.destination, len(files)))
        return 0
    write(args.destination, files)
    print("wrote {} files to {} ({} changed)".format(len(files), args.destination, len(wrong)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
