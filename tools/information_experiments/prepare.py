#!/usr/bin/env python3
"""Generate an isolated information-choice Harbor task outside the checkout."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


REPO = Path(__file__).resolve().parents[2]
CONTEXTS = ("uncertain", "likely_firm", "likely_soft", "costly_probe")

INSTRUCTION = """# Choose a rover mission under uncertainty

Maximize the expected score of this single episode using the five public
`information` MCP tools: `rules`, `map`, `telemetry_log`, `uplink`, and `advance`.
Read the public rules and map before acting. They disclose the terrain prior,
inspection reliability, resource costs, timing and reward. Only the actual
terrain and any inspection result not yet delivered are hidden.

The shortcut and detour visit different targets and both include returning
home. At most one trip may be committed. You may obtain one physical inspection
before committing; it costs energy and its imperfect signal arrives later.
A route is irrevocable when its command is accepted, even before execution.
A batch that queues an inspection and a route commits before seeing the signal.
Choose your actions using the public information and update from observations.

Commands for `uplink(commands)` are:
- {"action":"probe"}
- {"action":"commit","route":"shortcut"} or route "detour"
- {"action":"wait"}

Only `advance(ticks)` moves simulated time, by 1–5 ticks per call. Reading
rules/maps or delivered logs is free; rereading a signal does not obtain another
independent observation. You can think, calculate, write scripts and run code.
The installed Python MCP client can call http://information:8000/mcp from scripts.
Do not access simulator internals, hidden state, evaluator endpoints or files.

Commands execute FIFO at the published delay and consume the published energy.
The realized score is the value of a successfully completed trip minus its
published completion-time decay, normalized to [0,1]; a failed/incomplete trip
scores zero. The horizon is fixed. If you stop early, the evaluator still lets
accepted commands and the remaining simulated time run to that horizon.
Play the episode through the tools; writing a proposed plan alone does not act.
"""

SIMULATOR_DOCKERFILE = """FROM python:3.12-slim
WORKDIR /srv
RUN pip install --no-cache-dir "mcp==2.3.0"
COPY lightlag_information/ lightlag_information/
COPY finish.py finish.py
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
EXPOSE 8000
CMD ["python", "-m", "lightlag_information.serve", "--transport", "http", "--host", "0.0.0.0", "--port", "8000"]
"""

TASK = """schema_version = "1.4"
artifacts = [{ source = "/evaluator", service = "information" }]

[task]
name = "neural-network-november/information-choice-pilot"
version = "0.1.0"
description = "Decide whether to acquire a costly delayed observation before an irreversible route choice."
authors = []
keywords = ["partial-observability", "information-acquisition", "mcp"]

[metadata]

[verifier]
timeout_sec = 120.0
environment_mode = "separate"

[[verifier.collect]]
service = "information"
command = "python /srv/finish.py --url http://127.0.0.1:8000 --token-file /run/information/token"
timeout_sec = 60.0

[verifier.env]

[agent]
timeout_sec = 1800.0

[environment]
network_mode = "public"
build_timeout_sec = 900.0
os = "linux"

[[environment.mcp_servers]]
name = "information"
transport = "streamable-http"
url = "http://information:8000/mcp"

[environment.env]

[solution.env]
"""


def prepare(destination, context="uncertain", seed=100, policy="selective"):
    destination = Path(destination).resolve()
    if destination == REPO or REPO in destination.parents:
        raise ValueError("generate experimental tasks outside the checkout")
    if destination.exists():
        raise FileExistsError("output already exists; choose a new directory")
    if context not in CONTEXTS or policy not in ("selective", "nop"):
        raise ValueError("unknown context or policy")
    if type(seed) is not int or seed < 0:
        raise ValueError("seed must be a nonnegative integer")

    sources = {
        "environment/Dockerfile": "harbor/lightlag/environment/Dockerfile",
        "tests/Dockerfile": "harbor/lightlag/tests/Dockerfile",
        "tests/grade.py": "harbor/lightlag/tests/grade.py",
        "environment/simulator/finish.py": "lightlag_mcp/finish.py",
        "solution/mcp_client.py": "lightlag_mcp/client.py",
        "solution/play_policy.py": "tools/information_experiments/play_policy.py",
        "solution/lightlag_information/policies.py": "lightlag_information/policies.py",
    }
    for name in ("__init__.py", "environment.py", "model.py", "service.py", "server.py", "serve.py"):
        sources["environment/simulator/lightlag_information/" + name] = "lightlag_information/" + name
    source_bytes = {source: (REPO / source).read_bytes() for source in set(sources.values())}
    source_bytes["tools/information_experiments/prepare.py"] = Path(__file__).read_bytes()
    files = {target: source_bytes[source] for target, source in sources.items()}
    files.update({
        "task.toml": TASK.encode(),
        "instruction.md": INSTRUCTION.encode(),
        "environment/simulator/Dockerfile": SIMULATOR_DOCKERFILE.encode(),
        "solution/lightlag_information/__init__.py": b'"""Public policy only; no environment or hidden episode state."""\n',
        "solution/solve.sh": ('''#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
python3 play_policy.py --policy ''' + policy + ''' --url "${INFORMATION_MCP_URL:-http://information:8000/mcp}"
''').encode(),
        "tests/test.sh": b'''#!/bin/bash
set -euo pipefail
python3 /tests/grade.py --result /evaluator/result.json --reward /logs/verifier/reward.txt --details /logs/verifier/information-details.json
''',
        "environment/docker-compose.yaml": ('''services:
  main:
    depends_on:
      information:
        condition: service_healthy
  information:
    build:
      context: ./simulator
    expose:
      - "8000"
    environment:
      INFORMATION_SEED: "''' + str(seed) + '''"
      INFORMATION_CONTEXT: "''' + context + '''"
      INFORMATION_ARTIFACT_DIR: /evaluator
      INFORMATION_TOKEN_FILE: /run/information/token
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
        "settings": {"context": context, "seed": seed, "policy": policy, "horizon": 30},
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
    parser.add_argument("--context", choices=CONTEXTS, default="uncertain")
    parser.add_argument("--seed", type=int, default=100)
    parser.add_argument("--policy", choices=("selective", "nop"), default="selective")
    try:
        result = prepare(**vars(parser.parse_args()))
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, "cannot prepare information task: " + str(error) + "\n")
    print("Prepared", len(result["task_sha256"]), "files; settings", json.dumps(result["settings"], sort_keys=True))


if __name__ == "__main__":
    main()
