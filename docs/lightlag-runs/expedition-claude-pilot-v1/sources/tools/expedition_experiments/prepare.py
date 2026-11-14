#!/usr/bin/env python3
"""Generate an isolated expedition Harbor task outside the checkout."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

REPO = Path(__file__).resolve().parents[2]
POLICIES = ("reference", "no_probe", "value_blind", "leader_probe", "entropy_probe", "forced_leader_probe", "nop")

INSTRUCTION = """# Explore, collect science and bring the rover home

Maximize expected normalized mission score in this single episode using the five
public `expedition` MCP tools: `rules`, `map`, `telemetry_log`, `uplink`, `advance`.
Read rules and map first. They specify the terrain, energy, wheel slip, sensing,
sample windows, discoveries, regional quality priors and observation reliability.

Drive to targets, sample within target_radius, and return within base_radius of
base. Credited sample value depends on its base value, regional quality and whether
the sample executes before its deadline. Quality is fixed across the mission and
shared by every target in the same region. Regions are independent at launch.
There are two inspections total, at most one per region, each costing energy and
one execution tick. An inspection gives one imperfect rich/poor signal through
delayed telemetry. Sample events also reveal science evidence. Rereading an event
is not a new observation. In public-quality episodes rules publish the actual
regional qualities; all other mechanics are the same.

Commands for `uplink(commands)` are:
- {"action":"drive","heading_deg":H,"metres":M}: 0 degrees east, 90 north;
  M is wheel distance in (0,5], not guaranteed ground distance.
- {"action":"sample"}: collect the nearest eligible target within target_radius;
  spends sampling energy even on a miss.
- {"action":"inspect","region":"r1"}: also accepts r2 or r3.
- {"action":"wait"}.

Send 1–5 commands per batch. Commands execute FIFO, one per tick, no earlier than
sent_tick + delay_ticks + 1 or the tick after the last reservation. Acknowledgements
give execute_tick. Invalid batches are rejected atomically. Telemetry is a list of
packets: each describes packet.tick and arrives at received_tick, delay_ticks
later. The initial briefing is exact; consult rules for subsequent sensing.
Compare wheel and visual odometry to estimate slip. Avoid hazards and map edges.

Only `advance(ticks)` moves simulated time, by 1–5 ticks per call. Reading, thinking,
calculating and writing/running scripts are free. The installed Python MCP client
can call http://expedition:8000/mcp. Do not access simulator internals, hidden state,
evaluator endpoints or evaluator files. There is no reset.

The fixed horizon is 60 simulated ticks. Grade is credited sample value divided
by the published maximum available value, multiplied by 1 at base, 0.5 if alive
elsewhere, or 0 if battery reached zero. If you stop early, the trusted evaluator
runs accepted commands and the remaining simulated time to the horizon. Optimize
expected reward using the evidence available; favorable quality and inspection
signals are not guaranteed. Play through the tools: writing a plan alone does
not act. Scripting is allowed; there is no thinking-time charge in simulated ticks.

Planning aid: keep a ledger of the current tick, newest packet's state tick,
acknowledged execution ticks, confirmed cancellations, sampled targets and regional
evidence. An action absent from an old packet may already be executing. Repeated
reads of the same inspection signal must not be treated as fresh observations.

Forecast terminal battery from the latest packet: subtract all remaining idle
cost through tick 60 and all action costs after that packet's tick, including
already acknowledged commands and the return journey. Count each cost once;
inspections and unsuccessful sample attempts also consume energy. Reserve energy
for idle ticks at base after returning. Compare sample execution times with
published deadlines, and account for FIFO reservations before sending a batch.
"""

SIMULATOR_DOCKERFILE = """FROM python:3.12-slim
WORKDIR /srv
RUN pip install --no-cache-dir "mcp==2.3.0"
COPY lightlag/ lightlag/
COPY lightlag_dynamic/ lightlag_dynamic/
COPY lightlag_expedition/ lightlag_expedition/
COPY finish.py finish.py
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
EXPOSE 8000
CMD ["python", "-m", "lightlag_expedition.serve", "--transport", "http", "--host", "0.0.0.0", "--port", "8000"]
"""

TASK = """schema_version = "1.4"
artifacts = [{ source = "/evaluator", service = "expedition" }]

[task]
name = "neural-network-november/lightlag-expedition-pilot"
version = "0.1.0"
description = "Allocate scarce science observations and control a delayed rover through a multi-target mission."
authors = []
keywords = ["partial-observability", "information-acquisition", "control", "mcp"]

[metadata]

[verifier]
timeout_sec = 120.0
environment_mode = "separate"

[[verifier.collect]]
service = "expedition"
command = "python /srv/finish.py --url http://127.0.0.1:8000 --token-file /run/expedition/token"
timeout_sec = 60.0

[verifier.env]

[agent]
timeout_sec = 1800.0

[environment]
network_mode = "public"
build_timeout_sec = 900.0
os = "linux"

[[environment.mcp_servers]]
name = "expedition"
transport = "streamable-http"
url = "http://expedition:8000/mcp"

[environment.env]

[solution.env]
"""


def prepare(destination, mission_seed=0, seed=100, visibility="hidden", policy="reference"):
    destination = Path(destination).resolve()
    if destination == REPO or REPO in destination.parents:
        raise ValueError("generate experimental tasks outside the checkout")
    if destination.exists():
        raise FileExistsError("output already exists; choose a new directory")
    if visibility not in ("hidden", "public") or policy not in POLICIES:
        raise ValueError("unknown visibility or policy")
    for name, value in (("seed", seed), ("mission_seed", mission_seed)):
        if type(value) is not int or value < 0:
            raise ValueError(name + " must be a nonnegative integer")

    sources = {
        "environment/Dockerfile": "harbor/lightlag/environment/Dockerfile",
        "tests/Dockerfile": "harbor/lightlag/tests/Dockerfile",
        "tests/grade.py": "harbor/lightlag/tests/grade.py",
        "environment/simulator/finish.py": "lightlag_mcp/finish.py",
        "solution/mcp_client.py": "lightlag_mcp/client.py",
        "solution/play_policy.py": "tools/expedition_experiments/play_policy.py",
        "solution/lightlag_expedition/reference.py": "lightlag_expedition/reference.py",
        "solution/lightlag_dynamic/controllers.py": "lightlag_dynamic/controllers.py",
        "solution/lightlag_dynamic/kf_mpc.py": "lightlag_dynamic/kf_mpc.py",
    }
    simulator_modules = {
        "lightlag": ("__init__", "environment", "model"),
        "lightlag_dynamic": ("__init__", "environment", "missions", "tools", "controllers", "kf_mpc"),
        "lightlag_expedition": ("__init__", "environment", "model", "missions", "service", "server", "serve"),
    }
    for package, modules in simulator_modules.items():
        for module in modules:
            path = package + "/" + module + ".py"
            sources["environment/simulator/" + path] = path
    source_bytes = {source: (REPO / source).read_bytes() for source in set(sources.values())}
    source_bytes["tools/expedition_experiments/prepare.py"] = Path(__file__).read_bytes()
    files = {target: source_bytes[source] for target, source in sources.items()}
    files.update({
        "task.toml": TASK.encode(),
        "instruction.md": INSTRUCTION.encode(),
        "environment/simulator/Dockerfile": SIMULATOR_DOCKERFILE.encode(),
        "solution/lightlag_expedition/__init__.py": b'"""Public reference only; no environment or hidden episode state."""\n',
        "solution/lightlag_dynamic/__init__.py": b'"""Public controllers only; no environment or hidden episode state."""\n',
        "solution/solve.sh": ('''#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
python3 play_policy.py --policy ''' + policy + ''' --url "${EXPEDITION_MCP_URL:-http://expedition:8000/mcp}"
''').encode(),
        "tests/test.sh": b'''#!/bin/bash
set -euo pipefail
python3 /tests/grade.py --result /evaluator/result.json --reward /logs/verifier/reward.txt --details /logs/verifier/expedition-details.json
''',
        "environment/docker-compose.yaml": ('''services:
  main:
    depends_on:
      expedition:
        condition: service_healthy
  expedition:
    build:
      context: ./simulator
    expose:
      - "8000"
    environment:
      EXPEDITION_SEED: "''' + str(seed) + '''"
      EXPEDITION_MISSION_SEED: "''' + str(mission_seed) + '''"
      EXPEDITION_VISIBILITY: "''' + visibility + '''"
      EXPEDITION_ARTIFACT_DIR: /evaluator
      EXPEDITION_TOKEN_FILE: /run/expedition/token
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"]
      interval: 2s
      timeout: 5s
      retries: 30
      start_period: 3s
''').encode(),
    })
    manifest = {
        "schema_version": 1,
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
        "source_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO)),
        "settings": {"seed": seed, "mission_seed": mission_seed, "visibility": visibility,
                     "policy": policy, "horizon": 60, "delay": 3},
        "seed_semantics": {"mission_seed": "public mission geometry", "seed": "physics and fixed regional quality/signal draws; keep identical for paired visibility comparisons"},
        "source_sha256": {name: hashlib.sha256(data).hexdigest() for name, data in sorted(source_bytes.items())},
        "task_sha256": {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())},
    }
    # Validate and assemble all inputs before creating anything.
    destination.mkdir(parents=True, exist_ok=False)
    for name, data in files.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        if target.suffix == ".sh":
            target.chmod(0o755)
    (destination / "experiment.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--mission-seed", type=int, default=0)
    parser.add_argument("--seed", type=int, default=100)
    parser.add_argument("--visibility", choices=("hidden", "public"), default="hidden")
    parser.add_argument("--policy", choices=POLICIES, default="reference")
    try:
        result = prepare(**vars(parser.parse_args()))
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, "cannot prepare expedition task: " + str(error) + "\n")
    print("Prepared", len(result["task_sha256"]), "files; settings", json.dumps(result["settings"], sort_keys=True))


if __name__ == "__main__":
    main()
