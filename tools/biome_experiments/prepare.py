#!/usr/bin/env python3
"""Build an isolated experimental Harbor task for a biome or a navigation setting.

    python3 tools/biome_experiments/prepare.py /tmp/lightlag-weak-gps-2400 \\
        --navigation weak_gps --profile rush_noisy --seed 2400 --delay 3

Follows tools/lightlag_experiments/prepare.py: the output is a new directory outside the
checkout, the canonical task under harbor/lightlag is never edited, and a manifest records
the content hash of every source and generated file. What differs is the episode behind the
five tools and what the agent is told about it:

    --biome        any biome of lightlag_dynamic.biomes (default main_mars); mix with +
    --navigation   gps (today's position fix), weak_gps (a 2 m fix, a sun compass and a beacon
                   range), no_gps (no fix; the compass and the beacon only) or many_sensors (the
                   weak fix, four vague beacons, a gyroscope, coarse visual odometry and wheels
                   of a hidden size)
    --wheel-error  wheels of a hidden size, 1 +- this, so that a drive can overshoot. With
                   --navigation gps it is the only change to today's episode

The simulator container runs `python -m lightlag_dynamic.biomes.serve`, whose tool
descriptions are made true for the episode, and instruction.md gets the same facts. The
solution is a pipeline check through the public tools, not the reference for the setting:
the fusing reference needs numpy and plays outside the container.

Standard library only (it imports this repository's own packages to read the episode's
rules); checked with Python 3.12 and 3.14, which write identical tasks.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

REPO = Path(__file__).resolve().parents[2]
BASE = Path("harbor/lightlag")
NAVIGATION = {"gps": {}, "weak_gps": {"LIGHTLAG_WEAK_GPS": "1"}, "no_gps": {"LIGHTLAG_NO_GPS": "1"},
              "many_sensors": {"LIGHTLAG_MANY_SENSORS": "1"}}
POLICIES = ("kf_mpc", "open_loop", "leg_and_wait")
PROFILES = ("rush", "rush_noisy", "noisy")

SIMULATOR = {
    "lightlag": ("__init__.py", "environment.py", "model.py"),
    "lightlag_mcp": ("__init__.py", "__main__.py", "finish.py", "server.py", "service.py", "requirements.txt"),
    "lightlag_dynamic": ("__init__.py", "environment.py", "missions.py", "tools.py", "controllers.py", "kf_mpc.py"),
    "lightlag_dynamic/manh_controllers": ("__init__.py", "scenarios.py", "mars.py"),
    "lightlag_dynamic/biomes": ("__init__.py", "catalog.py", "environment.py", "nogps.py", "serve.py", "wheels.py",
                                "wording.py"),
}


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("upstream task template changed: expected one occurrence of " + repr(old))
    return text.replace(old, new, 1)


def episode_rules(biome, profile, seed, delay, navigation, wheel_error=0.0):
    """The rules() of the episode the generated task will serve, read from this checkout."""
    sys.path.insert(0, str(REPO))
    try:
        from lightlag import Config
        from lightlag_dynamic.biomes.serve import BiomeEpisodeService
        from lightlag_dynamic.missions import PROFILES as HORIZONS
        service = BiomeEpisodeService(seed=seed, biome=biome, profile=profile,
                                      config=Config(delay_ticks=delay, max_ticks=HORIZONS[profile][4]),
                                      no_gps=navigation == "no_gps", weak_gps=navigation == "weak_gps",
                                      many_sensors=navigation == "many_sensors", wheel_error=wheel_error or None)
        return service._env.rules()
    finally:
        sys.path.remove(str(REPO))


# The dynamic experiments' own sentences (tools/lightlag_experiments/prepare.py), word for word, so
# that with today's position fix in Main Mars this generator writes the instruction that one writes
# and a navigation setting adds to it instead of rephrasing it. A test compares the two outputs.
LEAD = "Read `rules()` and `map()`\nbefore acting; their values are authoritative.\n"
RUSH = "This is a time-pressured mission with a seeded map. "
DEADLINES = ("- Targets have deadlines. A sample executed at or before its deadline earns full\n"
             "  value; afterwards it earns the published `late_fraction` ({:g}).\n")
DISCOVERIES = ("- Additional targets appear during the mission. Their discovery travels in\n"
               "  delayed telemetry; `map()` lists them once that information has arrived. Read\n"
               "  new packets and refresh the map to learn about them.\n"
               "- The denominator includes the full value of every generated mission target,\n"
               "  including later discoveries. Late sampling reduces earned value.\n")
SENSING = ("- `rules()[\"sensing\"]` describes observation noise and heading drift when enabled.\n"
           "  If it is non-null, position and visual odometry are noisy, and actual drives can\n"
           "  differ from the commanded heading. The initial briefing is exact. Sampling,\n"
           "  safety and returning to base are evaluated at the true position.\n")
CLOSING = ("You may script a controller using the five public tools. No hidden simulator\n"
           "state, evaluator access or reference code is part of the agent interface.\n")


def mission_text(rules):
    """What instruction.md adds to the canonical text: this mission's public rules, then its biome and sensors."""
    sys.path.insert(0, str(REPO))
    try:
        from lightlag_dynamic.biomes.wording import brief
    finally:
        sys.path.remove(str(REPO))
    windows, discoveries = rules["sample_windows_enabled"], rules["discoveries_enabled"]
    text = "\n## This mission's public rules\n\n"
    text += (RUSH if rules["random_map"] and windows and discoveries else "") + LEAD + "\n"
    if windows:
        text += DEADLINES.format(rules["sample_windows"]["late_fraction"])
    if discoveries:
        text += DISCOVERIES
    sensing = SENSING
    if (rules.get("navigation") or {}).get("position_noise_m", 0.0) is None:  # no fix: there is no position to be noisy
        sensing = replace_once(sensing, "position and visual odometry are noisy", "visual odometry is noisy")
    text += sensing
    extra = brief(rules)
    if extra:
        text += "\n" + extra + "\n"
    return text + "\n" + CLOSING


def prepare(destination, biome="main_mars", profile="rush_noisy", seed=2400, delay=3, navigation="weak_gps",
            policy="kf_mpc", wheel_error=0.0):
    destination = Path(destination).resolve()
    if destination == REPO or REPO in destination.parents:
        raise ValueError("generate experimental tasks outside the checkout")
    if destination.exists():
        raise FileExistsError("output already exists; choose a new directory")
    if profile not in PROFILES or policy not in POLICIES or navigation not in NAVIGATION:
        raise ValueError("unknown profile, navigation setting or solution policy")
    if navigation == "no_gps" and policy != "open_loop":
        raise ValueError("without a position fix only the open_loop solution can play; the others read the position")
    if type(seed) is not int or seed < 0 or type(delay) is not int or delay < 0:
        raise ValueError("seed and delay must be nonnegative integers")
    if type(wheel_error) not in (int, float) or not 0 <= wheel_error < 0.5:
        raise ValueError("the wheel error must be a number from 0 to below 0.5")
    rules = episode_rules(biome, profile, seed, delay, navigation, wheel_error)  # ValueError on an unknown biome
    horizon = rules["max_ticks"]

    tracked = subprocess.check_output(["git", "ls-files", "-z", "--", str(BASE)], cwd=REPO).decode()
    sources = {}
    for name in filter(None, tracked.split("\0")):
        relative = Path(name).relative_to(BASE)
        if relative.parts[:2] == ("solution", "lightlag_controllers") or relative.name == "play_reference.py":
            continue
        sources[str(relative)] = name
    # Use original source packages even when the canonical task's generated copies lag.
    for package, names in SIMULATOR.items():
        for name in names:
            sources["environment/simulator/{}/{}".format(package, name)] = package + "/" + name
    for name in ("controllers.py", "kf_mpc.py"):
        sources["solution/lightlag_dynamic/" + name] = "lightlag_dynamic/" + name
    sources["solution/mcp_client.py"] = "lightlag_mcp/client.py"
    sources["solution/play_policy.py"] = "tools/lightlag_experiments/play_policy.py"

    source_bytes = {source: (REPO / source).read_bytes() for source in set(sources.values())}
    source_bytes["tools/biome_experiments/prepare.py"] = Path(__file__).read_bytes()
    files = {target: source_bytes[source] for target, source in sources.items()}

    def edit(name, change):
        files[name] = change(files[name].decode()).encode()

    def compose(text):
        for key, value in (("SEED", seed), ("DELAY", delay)):
            text, count = re.subn(r'(?m)^(\s+LIGHTLAG_' + key + r':) [^\n]+$',
                                  lambda m: '{} "{}"'.format(m[1], value), text)
            if count != 1:
                raise ValueError("missing or repeated simulator setting: " + key)
        settings = {"LIGHTLAG_PROFILE": profile, "LIGHTLAG_TICKS": horizon, "LIGHTLAG_BIOME": biome,
                    "LIGHTLAG_NOISE_LEVEL": "1.0", **NAVIGATION[navigation]}
        if wheel_error:
            settings["LIGHTLAG_WHEEL_ERROR"] = wheel_error
        block = "".join('      {}: "{}"\n'.format(key, value) for key, value in settings.items())
        return replace_once(text, "      LIGHTLAG_ARTIFACT_DIR: /evaluator", block + "      LIGHTLAG_ARTIFACT_DIR: /evaluator")

    slug = re.sub(r"[^a-z0-9]+", "-", "{}-{}-{}{}".format(biome, navigation, profile,
                                                         "-wheels" if wheel_error else "").lower()).strip("-")
    edit("environment/docker-compose.yaml", compose)
    edit("environment/simulator/Dockerfile", lambda text:
         replace_once(replace_once(text, "COPY lightlag_mcp/ lightlag_mcp/",
                                   "COPY lightlag_mcp/ lightlag_mcp/\nCOPY lightlag_dynamic/ lightlag_dynamic/"),
                      '"-m", "lightlag_mcp"', '"-m", "lightlag_dynamic.biomes.serve"'))
    edit("task.toml", lambda text: replace_once(text, 'name = "neural-network-november/lightlag"',
                                               'name = "neural-network-november/lightlag-biome-{}"'.format(slug)))
    edit("solution/solve.sh", lambda text:
         replace_once(text, 'python3 play_reference.py --url "${LIGHTLAG_MCP_URL:-http://lightlag:8000/mcp}"',
                      'python3 play_policy.py --policy {} --url "${{LIGHTLAG_MCP_URL:-http://lightlag:8000/mcp}}"'.format(policy)))
    files["solution/lightlag_dynamic/__init__.py"] = b'"""Public-tool controllers only; simulator modules are deliberately absent."""\n'
    edit("instruction.md", lambda text: replace_once(text, "total value on the map",
                                                    "total maximum value generated for the mission")
         + mission_text(rules))

    manifest = {
        "schema_version": 1,
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
        "source_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO)),
        "settings": {"biome": biome, "profile": profile, "seed": seed, "delay": delay, "horizon": horizon,
                     "navigation": navigation, "noise_level": 1.0, "policy": policy, "wheel_error": float(wheel_error)},
        "navigation_rules": rules.get("navigation") and {k: v for k, v in rules["navigation"].items()
                                                        if isinstance(v, (int, float)) or v is None},
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
    parser.add_argument("--biome", default="main_mars")
    parser.add_argument("--profile", choices=PROFILES, default="rush_noisy")
    parser.add_argument("--seed", type=int, default=2400)
    parser.add_argument("--delay", type=int, default=3)
    parser.add_argument("--navigation", choices=tuple(NAVIGATION), default="weak_gps")
    parser.add_argument("--policy", choices=POLICIES, default="kf_mpc")
    parser.add_argument("--wheel-error", type=float, default=0.0, dest="wheel_error")
    args = parser.parse_args()
    try:
        manifest = prepare(**vars(args))
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, "cannot prepare experiment: {}\n".format(error))
    print("Prepared {} task files; settings: {}".format(len(manifest["task_sha256"]),
                                                       json.dumps(manifest["settings"], sort_keys=True)))


if __name__ == "__main__":
    main()
