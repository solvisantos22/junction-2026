"""Trusted evaluator, isolated prefix copies and independently replayable outcomes."""

from collections import Counter, defaultdict
import copy
import hashlib
import json
from pathlib import Path
import pickle
import platform
import time
import traceback

from lightlag_traverse.environment import TraverseEnvironment
from lightlag_traverse_max.heldout import check_training_seeds
from lightlag_learned_portfolio.policy import features as old_features, choose as old_choose, apply_profile as old_apply
from .policy import Pilot, SWITCH_TICK, features, step

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT/"docs/learned-portfolio-results/models/extra_trees.pkl"
LEGACY_SHA = "74fe342c638606dc2e0cbe970ea2bfa6cb4be8c6431a8b7a11988e844a7a2c4e"
QUICK = dict(plan_steps=12000, replan_steps=2000, beam=60, rebeam=20)


def canonical(value): return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
def digest(value): return hashlib.sha256(canonical(value)).hexdigest()
def file_hash(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_manifest():
    paths = [ROOT/"docs/planner-lab.md", ROOT/"lightlag_traverse_max/heldout.py",
             ROOT/"lightlag_learned_portfolio/policy.py", ROOT/"lightlag_learned_portfolio/__init__.py", LEGACY]
    for package in ("lightlag", "lightlag_traverse", "lightlag_planner_lab"):
        paths += sorted((ROOT/package).glob("*.py"))
    return {str(p.relative_to(ROOT)): file_hash(p) for p in sorted(paths)}


def load_model(path, sha):
    data = Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest() != sha: raise ValueError("checkpoint hash mismatch")
    return pickle.loads(data)  # Only this study's own, pinned checkpoints.


class Tools:
    """Evaluator-owned proxy. Policy code uses only these five public methods."""
    def __init__(self, env):
        self._env = env; self.calls = Counter(); self.commands = []; self.invalid = []
    def invoke(self, name, *args):
        self.calls[name] += 1
        try: result = getattr(self._env, name)(*args)
        except ValueError as error:
            self.invalid.append({"method": name, "message": str(error)}); raise
        if name == "uplink": self.commands.extend(copy.deepcopy(result))
        return result
    def rules(self): return self.invoke("rules")
    def map(self): return self.invoke("map")
    def telemetry_log(self): return self.invoke("telemetry_log")
    def uplink(self, commands): return self.invoke("uplink", commands)
    def advance(self, ticks=1): return self.invoke("advance", ticks)


def make_prefix(seed, quick=False):
    start, cpu = time.perf_counter(), time.process_time()
    env = TraverseEnvironment(seed); tools = Tools(env); pilot = Pilot(tools, QUICK if quick else None)
    while pilot.now < SWITCH_TICK: step(pilot)
    state = features(pilot)
    return (pilot, env, tools), state, {"seconds": time.perf_counter()-start, "cpu_seconds": time.process_time()-cpu}


def replay_parts(replay):
    return {**{k: digest(v) for k, v in replay.items() if k != "world"},
            "world_without_features": digest({k: v for k, v in replay["world"].items() if k != "features"}),
            "world_features": digest(replay["world"]["features"])}


def continue_arm(context, state, timing, arm, model=None, keep_replay=False):
    pilot, env, tools = context
    assert pilot.tools is tools and tools._env is env
    start, cpu = time.perf_counter(), time.process_time()
    decision, legacy_decision, error = None, None, None
    try:
        spec = arm["spec"]
        if spec["kind"] == "fixed": name, prediction = spec["profile"], None
        elif spec["kind"] == "learned": name, prediction = model.choose(state, spec["setting"])
        elif spec["kind"] == "legacy": name, prediction = "baseline", None
        else: raise ValueError("unknown arm kind")
        pilot.configure(name)
        decision = {"tick": SWITCH_TICK, "features": state, "profile": name, "prediction": prediction}
        while True:
            if spec["kind"] == "legacy" and pilot.now >= 140 and legacy_decision is None:
                old_state = old_features(pilot); old_name, scores = old_choose(model, old_state, 0.)
                old_apply(pilot, old_name)
                legacy_decision = {"tick": pilot.now, "features": old_state, "profile": old_name, "prediction": scores}
            if step(pilot): break
    except Exception: error = traceback.format_exc()
    elapsed, used_cpu = time.perf_counter()-start, time.process_time()-cpu
    while not env.advance(1)["episode_complete"]: pass
    replay = env.replay(); grade = replay["result"]
    result = {"arm": arm, "decision": decision, "legacy_decision": legacy_decision,
              "reward": grade["raw_score"]/grade["max_available_value"], "result": grade,
              "commands": replay["commands"], "replay_sha256": digest(replay), "parts_sha256": replay_parts(replay),
              "prefix_sha256": digest([c for c in replay["commands"] if c["sent_tick"] < SWITCH_TICK]),
              "events": pilot.events, "calls": dict(tools.calls), "invalid": tools.invalid, "error": error,
              "continuation_seconds": elapsed, "continuation_cpu_seconds": used_cpu,
              "seconds": timing["seconds"]+elapsed, "cpu_seconds": timing["cpu_seconds"]+used_cpu}
    if keep_replay: result["replay"] = replay
    return result


def run_batch(job, models=None):
    check_training_seeds([job["seed"]]); models = models or {}
    if job.get("source") != source_manifest(): raise ValueError("runtime differs from frozen source")
    started, cpu = time.perf_counter(), time.process_time()
    context, state, timing = make_prefix(job["seed"], job.get("quick", False))
    results, copy_seconds = [], 0.
    for arm in job["arms"]:
        cloned_at = time.perf_counter(); isolated = copy.deepcopy(context)
        copy_seconds += time.perf_counter()-cloned_at
        result = continue_arm(isolated, state, timing, arm, models.get(arm["name"]), job.get("keep_replay", False))
        results.append(result)
    return {"job": {k:v for k,v in job.items() if k != "source"}, "episodes": results,
            "source_sha256": digest(source_manifest()), "prefix_timing": timing, "copy_seconds": copy_seconds,
            "wall_seconds": time.perf_counter()-started, "cpu_seconds": time.process_time()-cpu,
            "python": platform.python_version()}


def run_without_copy(job, arm, model=None):
    """Parity check: one ordinary prefix/continuation with no checkpoint copying."""
    context, state, timing = make_prefix(job["seed"], job.get("quick", False))
    return continue_arm(context, state, timing, arm, model, True)


def replay_episode(seed, result, strict=True):
    env = TraverseEnvironment(seed); by_tick = defaultdict(list)
    for command in result["commands"]: by_tick[command["sent_tick"]].append(command)
    for tick in range(env.rules()["max_ticks"]):
        for command in by_tick.pop(tick, []):
            if digest(env.uplink([command["command"]])) != digest([command]): raise ValueError("acknowledgement mismatch")
        env.advance(1)
    if by_tick: raise ValueError("commands after horizon")
    replay = env.replay(); exact = digest(replay) == result["replay_sha256"]
    if strict and not exact: raise ValueError("replay mismatch")
    if replay["result"] != result["result"]: raise ValueError("grade mismatch")
    if replay["result"]["raw_score"]/replay["result"]["max_available_value"] != result["reward"]:
        raise ValueError("reward mismatch")
    differences = [k for k,h in replay_parts(replay).items() if h != result["parts_sha256"][k]]
    if not strict and set(differences)-{"world_features"}: raise ValueError("local physical trajectory mismatch")
    return {"exact": exact, "commands": len(replay["commands"]), "states": len(replay["states"]),
            "different_parts": differences, "replay_sha256": result["replay_sha256"]}
