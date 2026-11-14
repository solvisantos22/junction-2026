#!/usr/bin/env python3
"""Build an isolated experimental Harbor task; never edits the canonical task.

    python3 tools/lightlag_experiments/prepare.py /tmp/lightlag-rush-500 \
        --profile rush --seed 500 --delay 3 --policy kf_mpc

Python 3.9+, standard library only. Output must be a new directory outside the
checkout. The manifest records every source and generated file's content hash.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

REPO = Path(__file__).resolve().parents[2]
BASE = Path("harbor/lightlag")


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("upstream task template changed: expected one occurrence of " + repr(old))
    return text.replace(old, new, 1)


def prepare(destination, profile="rush", seed=500, delay=3, policy="kf_mpc"):
    destination = Path(destination).resolve()
    if destination == REPO or REPO in destination.parents:
        raise ValueError("generate experimental tasks outside the checkout")
    if destination.exists():
        raise FileExistsError("output already exists; choose a new directory")
    if profile not in ("rush", "rush_noisy") or policy not in ("kf_mpc", "open_loop", "leg_and_wait"):
        raise ValueError("unknown profile or solution policy")
    if type(seed) is not int or seed < 0 or type(delay) is not int or delay < 0:
        raise ValueError("seed and delay must be nonnegative integers")

    tracked = subprocess.check_output(["git", "ls-files", "-z", "--", str(BASE)], cwd=REPO).decode()
    sources = {}
    for name in filter(None, tracked.split("\0")):
        relative = Path(name).relative_to(BASE)
        if relative.parts[:2] == ("solution", "lightlag_controllers") or relative.name == "play_reference.py":
            continue
        sources[str(relative)] = name

    # Use original source packages even when the canonical task's generated copies lag.
    for package, names in {
        "lightlag": ("__init__.py", "environment.py", "model.py"),
        "lightlag_mcp": ("__init__.py", "__main__.py", "finish.py", "server.py", "service.py", "requirements.txt"),
        "lightlag_dynamic": ("__init__.py", "environment.py", "missions.py", "tools.py", "controllers.py", "kf_mpc.py", "serve.py"),
    }.items():
        for name in names:
            sources["environment/simulator/{}/{}".format(package, name)] = package + "/" + name
    for name in ("controllers.py", "kf_mpc.py"):
        sources["solution/lightlag_dynamic/" + name] = "lightlag_dynamic/" + name
    sources["solution/mcp_client.py"] = "lightlag_mcp/client.py"
    sources["solution/play_policy.py"] = "tools/lightlag_experiments/play_policy.py"

    source_bytes = {source: (REPO / source).read_bytes() for source in set(sources.values())}
    source_bytes["tools/lightlag_experiments/prepare.py"] = Path(__file__).read_bytes()
    files = {target: source_bytes[source] for target, source in sources.items()}

    def edit(name, change):
        files[name] = change(files[name].decode()).encode()

    def compose(text):
        for key, value in (("SEED", seed), ("DELAY", delay)):
            text, count = re.subn(r'(?m)^(\s+LIGHTLAG_' + key + r':) [^\n]+$',
                                 lambda m: '{} "{}"'.format(m[1], value), text)
            if count != 1:
                raise ValueError("missing or repeated simulator setting: " + key)
        return replace_once(text, "      LIGHTLAG_ARTIFACT_DIR: /evaluator",
                            '      LIGHTLAG_PROFILE: "{}"\n'.format(profile)
                            + '      LIGHTLAG_TICKS: "50"\n'
                            + '      LIGHTLAG_NOISE_LEVEL: "1.0"\n'
                            + '      LIGHTLAG_BUMPINESS: "0.0"\n'
                            + "      LIGHTLAG_ARTIFACT_DIR: /evaluator")

    edit("environment/docker-compose.yaml", compose)
    edit("environment/simulator/Dockerfile", lambda text:
         replace_once(replace_once(text, "COPY lightlag_mcp/ lightlag_mcp/",
                                   "COPY lightlag_mcp/ lightlag_mcp/\nCOPY lightlag_dynamic/ lightlag_dynamic/"),
                      '"-m", "lightlag_mcp"', '"-m", "lightlag_dynamic.serve"'))
    edit("task.toml", lambda text: replace_once(text, 'name = "neural-network-november/lightlag"',
                                               'name = "neural-network-november/lightlag-experiment-{}"'.format(profile)))
    edit("solution/solve.sh", lambda text:
         replace_once(text, 'python3 play_reference.py --url "${LIGHTLAG_MCP_URL:-http://lightlag:8000/mcp}"',
                      'python3 play_policy.py --policy {} --url "${{LIGHTLAG_MCP_URL:-http://lightlag:8000/mcp}}"'.format(policy)))
    files["solution/lightlag_dynamic/__init__.py"] = b'"""Public-tool controllers only; simulator modules are deliberately absent."""\n'
    extra = """
## This mission's public rules

This is a time-pressured mission with a seeded map. Read `rules()` and `map()`
before acting; their values are authoritative.

- Targets have deadlines. A sample executed at or before its deadline earns full
  value; afterwards it earns the published `late_fraction` (0.25).
- Additional targets appear during the mission. Their discovery travels in
  delayed telemetry; `map()` lists them once that information has arrived. Read
  new packets and refresh the map to learn about them.
- The denominator includes the full value of every generated mission target,
  including later discoveries. Late sampling reduces earned value.
- `rules()["sensing"]` describes observation noise and heading drift when enabled.
  If it is non-null, position and visual odometry are noisy, and actual drives can
  differ from the commanded heading. The initial briefing is exact. Sampling,
  safety and returning to base are evaluated at the true position.

You may script a controller using the five public tools. No hidden simulator
state, evaluator access or reference code is part of the agent interface.
"""
    edit("instruction.md", lambda text: replace_once(text, "total value on the map",
                                                    "total maximum value generated for the mission") + extra)

    manifest = {
        "schema_version": 1,
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
        "source_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO)),
        "settings": {"profile": profile, "seed": seed, "delay": delay, "horizon": 50,
                     "noise_level": 1.0, "bumpiness": 0.0, "policy": policy},
        "source_sha256": {name: hashlib.sha256(data).hexdigest() for name, data in source_bytes.items()},
        "task_sha256": {name: hashlib.sha256(data).hexdigest() for name, data in files.items()},
    }
    # Assemble and validate in memory first. Never erase or reuse previous results.
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
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("destination", type=Path)
    parser.add_argument("--profile", choices=("rush", "rush_noisy"), default="rush")
    parser.add_argument("--seed", type=int, default=500)
    parser.add_argument("--delay", type=int, default=3)
    parser.add_argument("--policy", choices=("kf_mpc", "open_loop", "leg_and_wait"), default="kf_mpc")
    args = parser.parse_args()
    try:
        manifest = prepare(**vars(args))
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, "cannot prepare experiment: {}\n".format(error))
    print("Prepared {} task files; settings: {}".format(len(manifest["task_sha256"]),
                                                       json.dumps(manifest["settings"], sort_keys=True)))


if __name__ == "__main__":
    main()
