#!/usr/bin/env python3
"""Play traverse missions in this process and compare controllers on the same worlds.

    python3 -m lightlag_traverse.play --seeds 1-20 --policies pilot,greedy,straight
    python3 -m lightlag_traverse.play --seeds 7 --policies pilot --replay /tmp/seed7.json

A policy is a callable that gets the five public tools and nothing else. The evaluator, not the
policy, lets the remaining ticks pass and grades. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from .environment import TraverseEnvironment
from .pilot import fly


class PublicTools:
    """Exactly the five public methods. An auditable boundary, not a security sandbox."""

    def __init__(self, env: TraverseEnvironment) -> None:
        self._env = env
        self.calls = 0

    def rules(self) -> Dict[str, Any]:
        self.calls += 1
        return self._env.rules()

    def map(self) -> Dict[str, Any]:
        self.calls += 1
        return self._env.map()

    def telemetry_log(self) -> List[Dict[str, Any]]:
        self.calls += 1
        return self._env.telemetry_log()

    def uplink(self, commands: Any) -> List[Dict[str, Any]]:
        self.calls += 1
        return self._env.uplink(commands)

    def advance(self, ticks: int = 1) -> Dict[str, Any]:
        self.calls += 1
        return self._env.advance(ticks)


def nothing(tools: Any) -> None:
    """The do-nothing baseline."""


def quick(options: Dict[str, Any]) -> Callable[[Any], Any]:
    return lambda tools: fly(tools, options)


POLICIES: Dict[str, Callable[[Any], Any]] = {
    "pilot": quick({}),                                          # the reference
    "pilot_fast": quick({"plan_steps": 40000, "replan_steps": 5000}),     # the same with less search, for sweeps
    "greedy": quick({"route": "greedy"}),                        # reads the ground, no route optimisation
    "straight": quick({"route": "greedy", "terrain": False}),    # neither
    "nothing": nothing,
}


def run_episode(policy: Callable[[Any], Any], seed: int, keep_replay: bool = False) -> Dict[str, Any]:
    env = TraverseEnvironment(seed)
    tools = PublicTools(env)
    started = time.time()
    policy(tools)                 # policy errors propagate: they must not turn into a low score
    seconds = time.time() - started
    while not env.advance(5)["episode_complete"]:
        pass
    result = env.evaluate()
    run = {"seed": seed, "result": result, "reward": result["raw_score"] / result["max_available_value"],
           "public_calls": tools.calls, "seconds": round(seconds, 2)}
    if keep_replay:
        run["replay"] = env.replay()
    return run


def save_run(folder: Path, run: Dict[str, Any], meta: Dict[str, Any]) -> None:
    """Write a run the way the Harbor runs are kept: run.json and artifacts/evaluator/."""
    evaluator = folder / "artifacts" / "evaluator"
    evaluator.mkdir(parents=True, exist_ok=False)
    (folder / "run.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (evaluator / "result.json").write_text(json.dumps(run["result"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (evaluator / "replay.json").write_text(json.dumps(run["replay"], separators=(",", ":")) + "\n", encoding="utf-8")


def policy(name: str) -> Callable[[Any], Any]:
    """A named policy, or the pilot with other options: `pilot:{"plan_steps": 50000}`."""
    if name in POLICIES:
        return POLICIES[name]
    head, _, options = name.partition(":")
    if head != "pilot" or not options:
        raise ValueError("unknown policy {!r}".format(name))
    return quick(json.loads(options))


def _job(job) -> Dict[str, Any]:
    name, seed = job
    run = run_episode(policy(name), seed)
    return dict(run, policy=name)


def parse_seeds(text: str) -> List[int]:
    seeds: List[int] = []
    for part in text.split(","):
        if "-" in part:
            first, last = part.split("-")
            seeds.extend(range(int(first), int(last) + 1))
        else:
            seeds.append(int(part))
    return seeds


def compare(names: Sequence[str], seeds: Sequence[int], workers: int = 6) -> Dict[str, List[Dict[str, Any]]]:
    jobs = [(name, seed) for seed in seeds for name in names]
    runs: Dict[str, List[Dict[str, Any]]] = {name: [] for name in names}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for run in pool.map(_job, jobs):
            runs[run["policy"]].append(run)
    return runs


def table(runs: Dict[str, List[Dict[str, Any]]]) -> str:
    lines = ["{:<44} {:>6} {:>6} {:>6} {:>6} {:>6} {:>7} {:>6}".format(
        "policy", "mean", "min", "max", "lost", "away", "samples", "sec")]
    for name, rows in runs.items():
        rewards = [r["reward"] for r in rows]
        lines.append("{:<44} {:>6.3f} {:>6.3f} {:>6.3f} {:>6} {:>6} {:>7.1f} {:>6.1f}".format(
            name[:44], statistics.mean(rewards), min(rewards), max(rewards),
            sum(not r["result"]["alive"] for r in rows),
            sum(r["result"]["alive"] and not r["result"]["at_base"] for r in rows),
            statistics.mean(len(r["result"]["sampled_targets"]) for r in rows),
            statistics.mean(r["seconds"] for r in rows)))
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seeds", default="1-10")
    parser.add_argument("--policies", default="pilot,greedy,straight,nothing")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--replay", type=Path, default=None, help="one seed, one policy: write its replay here")
    parser.add_argument("--json", type=Path, default=None, help="write every run's result here")
    parser.add_argument("--save", type=Path, default=None,
                        help="one seed: save each policy's run as <folder>/traverse-<policy>/ (must not exist)")
    args = parser.parse_args(argv)
    separator = ";" if (";" in args.policies or "{" in args.policies) else ","
    names, seeds = args.policies.split(separator), parse_seeds(args.seeds)
    if args.save:
        for name in names:
            run = run_episode(policy(name), seeds[0], keep_replay=True)
            kind = "reference" if name == "pilot" else "scripted"
            save_run(args.save / "traverse-{}".format(name), run, {
                "kind": kind, "label": "Reference" if name == "pilot" else name, "model": "",
                "how": "traverse pilot" if name == "pilot" else "scripted stand-in, not a model run",
                "source": "python3 -m lightlag_traverse.play --seeds {} --policies {}".format(seeds[0], name)})
            print("{} seed {}: reward {:.3f}, {} samples, alive {}, at base {}".format(
                name, seeds[0], run["reward"], len(run["result"]["sampled_targets"]), run["result"]["alive"],
                run["result"]["at_base"]))
        return 0
    if args.replay:
        run = run_episode(policy(names[0]), seeds[0], keep_replay=True)
        args.replay.write_text(json.dumps(run["replay"]), encoding="utf-8")
        print("{} seed {}: reward {:.3f}, {} samples, alive {}, at base {}, {} s".format(
            names[0], seeds[0], run["reward"], len(run["result"]["sampled_targets"]), run["result"]["alive"],
            run["result"]["at_base"], run["seconds"]))
        return 0
    runs = compare(names, seeds, args.workers)
    print(table(runs))
    if len(names) >= 2:
        first = {r["seed"]: r["reward"] for r in runs[names[0]]}
        for other in names[1:]:
            second = {r["seed"]: r["reward"] for r in runs[other]}
            higher = sum(first[s] > second[s] + 1e-9 for s in first)
            print("{} scores higher than {} on {} of {} worlds".format(names[0], other, higher, len(first)))
    if args.json:
        args.json.write_text(json.dumps({name: [{k: v for k, v in r.items() if k != "replay"} for r in rows]
                                         for name, rows in runs.items()}, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
