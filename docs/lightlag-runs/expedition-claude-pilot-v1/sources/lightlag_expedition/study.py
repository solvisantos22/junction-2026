"""Free paired development study: exact science worlds, fixed continuous noise draws.

Run ``python3 -m lightlag_expedition.study --output NEW_DIRECTORY``. All 8 qualities
and all 8 conditional signal combinations are enumerated per map. Their public-prior
weights integrate only discrete science uncertainty; four fixed physics seeds are not
an exact integral over continuous rover noise or evidence about unseen map performance.
"""

import argparse
from collections import defaultdict
from copy import deepcopy
import gzip
import hashlib
import itertools
import json
from pathlib import Path
import time

from .environment import ExpeditionEnvironment
from .model import INSPECTION_ACCURACY, PRIORS, REGIONS, TARGET_REGIONS
from .reference import run_policy


POLICIES = ("reference", "no_probe", "leader_probe", "entropy_probe", "value_blind",
            "public_reference")
SOURCE_FILES = (
    "lightlag_expedition/environment.py", "lightlag_expedition/missions.py",
    "lightlag_expedition/model.py", "lightlag_expedition/reference.py",
    "lightlag_expedition/study.py", "lightlag_dynamic/environment.py",
    "lightlag_dynamic/missions.py", "lightlag_dynamic/controllers.py",
    "lightlag_dynamic/kf_mpc.py", "lightlag/environment.py", "lightlag/model.py")


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def science_worlds():
    """The complete joint distribution, using public priors and signal likelihoods."""
    worlds = []
    for qualities in itertools.product(("poor", "rich"), repeat=len(REGIONS)):
        quality = dict(zip(REGIONS, qualities))
        prior = 1.0
        for region in REGIONS:
            prior *= PRIORS[region] if quality[region] == "rich" else 1 - PRIORS[region]
        for signals in itertools.product(("poor", "rich"), repeat=len(REGIONS)):
            signal = dict(zip(REGIONS, signals))
            likelihood = 1.0
            for region in REGIONS:
                likelihood *= INSPECTION_ACCURACY if signal[region] == quality[region] \
                    else 1 - INSPECTION_ACCURACY
            worlds.append({"id": "q" + "".join(str(int(q == "rich")) for q in qualities)
                                  + "s" + "".join(str(int(s == "rich")) for s in signals),
                           "qualities": quality, "signals": signal,
                           "weight": prior * likelihood})
    return worlds


class RecordingPublicTools:
    """Auditable five-method facade, not a security sandbox for adversarial Python.

    The policy receives no environment attribute or evaluator methods. A dispatcher
    closes over the evaluator-owned environment; only public tool names are accepted.
    """

    __slots__ = ("__dispatch", "transcript")

    def __init__(self, dispatch):
        self.__dispatch = dispatch
        self.transcript = []

    def _call(self, name, arguments=None):
        arguments = arguments or {}
        try:
            result = self.__dispatch(name, arguments)
        except Exception as error:
            self.transcript.append({"tool": name, "arguments": deepcopy(arguments),
                                    "error": {"type": type(error).__name__, "message": str(error)}})
            raise
        self.transcript.append({"tool": name, "arguments": deepcopy(arguments),
                                "result": deepcopy(result)})
        return result

    def rules(self):
        return self._call("rules")

    def map(self):
        return self._call("map")

    def telemetry_log(self):
        return self._call("telemetry_log")

    def uplink(self, commands):
        return self._call("uplink", {"commands": commands})

    def advance(self, ticks=1):
        return self._call("advance", {"ticks": ticks})


def _public_tools(env):
    methods = {name: getattr(env, name) for name in
               ("rules", "map", "telemetry_log", "uplink", "advance")}

    def dispatch(name, arguments):
        return methods[name](**arguments)

    return RecordingPublicTools(dispatch)


def run_episode(mission_seed, physics_seed, world, policy):
    if policy not in POLICIES:
        raise ValueError(f"unknown study policy {policy!r}")
    public = policy == "public_reference"
    env = ExpeditionEnvironment(seed=physics_seed, mission_seed=mission_seed,
                                visibility="public" if public else "hidden",
                                quality_fixture=world["qualities"], signal_fixture=world["signals"])
    tools = _public_tools(env)
    controller = run_policy(tools, "reference" if public else policy)
    result, replay = env.evaluate(), env.replay()
    inspections = [ack for ack in replay["commands"] if ack["command"]["action"] == "inspect"]
    probe_decisions = [decision for decision in controller.decision_log
                       if decision["action"] == "inspect"]
    first = probe_decisions[0] if probe_decisions else None
    leader = TARGET_REGIONS[first["plan"][0]] if first and first["plan"] else None
    row = {"id": f"m{mission_seed}-{world['id']}-{policy}", "mission_seed": mission_seed,
           "physics_seed": physics_seed, "world_id": world["id"], "policy": policy,
           "qualities": world["qualities"], "signals": world["signals"], "weight": world["weight"],
           "raw_score": result["raw_score"], "normalized_score": result["raw_score"] / 20,
           "alive": result["alive"], "at_base": result["at_base"],
           "inspections_reserved": len(inspections),
           "inspections_executed": len(replay["expedition"]["inspection_executed"]),
           "first_probe_region": first["region"] if first else None,
           "first_probe_leader_region": leader,
           "first_probe_is_leader": first["region"] == leader if first else None,
           "public_calls": len(tools.transcript),
           "sampled_targets": result["sampled_targets"]}
    full = {"episode": row, "result": result, "decisions": controller.decision_log,
            "replay": replay, "transcript": tools.transcript}
    return row, full


def summarize(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[(row["mission_seed"], row["policy"])].append(row)

    def aggregate(group):
        mass = sum(row["weight"] for row in group)
        if mass <= 0:
            raise ValueError("summary needs positive probability mass")
        numeric = ("raw_score", "normalized_score", "alive", "at_base",
                   "inspections_reserved", "inspections_executed", "public_calls")
        item = {field: sum(row["weight"] * row[field] for row in group) / mass
                for field in numeric}
        item.update(episodes=len(group), probability_mass=mass)
        probed = sum(row["weight"] for row in group if row["first_probe_region"] is not None)
        leader = sum(row["weight"] for row in group if row["first_probe_is_leader"] is True)
        item["probability_any_inspection"] = probed / mass
        item["probability_first_probe_is_leader"] = leader / mass
        item["probability_first_probe_is_challenger"] = (probed - leader) / mass
        item["first_probe_leader_fraction_given_probe"] = leader / probed if probed else None
        item["first_probe_regions"] = {
            region: sum(row["weight"] for row in group if row["first_probe_region"] == region) / mass
            for region in REGIONS}
        return item

    per_map = {str(seed): {policy: aggregate(groups[(seed, policy)])
                          for policy in sorted({row["policy"] for row in rows})
                          if (seed, policy) in groups}
               for seed in sorted({row["mission_seed"] for row in rows})}
    overall = {policy: aggregate([row for row in rows if row["policy"] == policy])
               for policy in sorted({row["policy"] for row in rows})}
    differences = {}
    if "reference" in overall:
        for policy, data in overall.items():
            if policy != "reference":
                differences[policy] = overall["reference"]["normalized_score"] - data["normalized_score"]
    return {"per_map": per_map, "aggregate": overall,
            "reference_minus_control_normalized": differences,
            "interpretation": [
                "Exact discrete science expectation conditional on each fixed map and physics seed.",
                "Maps receive equal weight; no claim of an exact continuous-noise or unseen-map expectation.",
                "Public reference is the same bounded heuristic with quality disclosed, not an optimal bound.",
                "All worlds and negative outcomes are retained; no model agents or paid calls are involved."]}


def run_study(output, map_seeds=(0, 1, 2, 3), physics_offset=100, worlds=None,
              policies=POLICIES, progress=None):
    output = Path(output)
    maps, policies = tuple(map_seeds), tuple(policies)
    worlds = science_worlds() if worlds is None else deepcopy(list(worlds))
    if not maps or len(set(maps)) != len(maps) or not worlds or not policies:
        raise ValueError("need distinct maps, science worlds, and policies")
    if len(set(policies)) != len(policies) or any(policy not in POLICIES for policy in policies):
        raise ValueError("policies must be distinct study policies")
    if len({world["id"] for world in worlds}) != len(worlds):
        raise ValueError("science world ids must be distinct")
    output.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[1]
    sources = {name: _sha(root / name) for name in SOURCE_FILES}
    config = {"study": "expedition-development-v1", "map_seeds": maps,
              "physics_seeds": {str(seed): physics_offset + seed for seed in maps},
              "policies": policies, "science_worlds": worlds,
              "episodes": len(maps) * len(worlds) * len(policies),
              "science_probability_mass_per_map": sum(world["weight"] for world in worlds),
              "full_discrete_enumeration": worlds == science_worlds(),
              "source_sha256": sources}
    (output / "config.json").write_text(json.dumps(config, indent=2, sort_keys=True) + "\n")
    started = time.monotonic()
    rows = []
    artifact = output / "episodes.jsonl.gz"
    with artifact.open("wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
        for seed in maps:
            for world in worlds:
                for policy in policies:
                    row, full = run_episode(seed, physics_offset + seed, world, policy)
                    rows.append(row)
                    compressed.write((_json(full) + "\n").encode())
                if progress:
                    progress({"completed": len(rows), "total": config["episodes"],
                              "map_seed": seed, "world_id": world["id"],
                              "elapsed_seconds": time.monotonic() - started})
    (output / "rows.jsonl").write_text("".join(_json(row) + "\n" for row in rows))
    summary = summarize(rows)
    summary.update(episodes=len(rows), elapsed_seconds=time.monotonic() - started,
                   source_unchanged=all(_sha(root / name) == digest for name, digest in sources.items()))
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    hashes = {path.name: _sha(path) for path in sorted(output.iterdir()) if path.is_file()}
    (output / "sha256.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n")
    if not summary["source_unchanged"]:
        raise RuntimeError("source changed during study; preserved artifacts are not a frozen comparison")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--maps", type=int, nargs="+", default=[0, 1, 2, 3])
    parser.add_argument("--physics-offset", type=int, default=100)
    args = parser.parse_args()

    def progress(item):
        if item["completed"] % 96 == 0 or item["completed"] == item["total"]:
            print(_json(item), flush=True)

    summary = run_study(args.output, args.maps, args.physics_offset, progress=progress)
    print(json.dumps(summary["aggregate"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
