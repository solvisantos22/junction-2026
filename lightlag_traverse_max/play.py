#!/usr/bin/env python3
"""Play traverse missions on the normal map and the MAX map and compare players on the same seeds.

    python3 -m lightlag_traverse_max.play --seeds 1-24 --maps normal,max
    python3 -m lightlag_traverse_max.play --seeds 101-124 --policies manh_max,pilot,greedy,straight --json out.json
    python3 -m lightlag_traverse_max.play --seeds 7 --maps max --policies 'manh_max:{"stall_drives": 8}'

A seed is the same mission on both maps: the same ground, targets, sun and noise draws. The MAX map
adds the max env's mechanics on top (lightlag_traverse_max/environment.py). The players get the
five public tools and nothing else, as in lightlag_traverse/play.py. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from lightlag_traverse.pilot import fly
from lightlag_traverse.play import PublicTools, parse_seeds

from .environment import OPTIONS, make_env
from .players import POLICIES, fly_max


def policy(name: str) -> Callable[[Any], Any]:
    """A named player, or manh_max or the pilot with other options: `manh_max:{"stall_drives": 8}`."""
    if name in POLICIES:
        return POLICIES[name]
    head, _, options = name.partition(":")
    if head not in ("manh_max", "pilot") or not options:
        raise ValueError("unknown policy {!r}".format(name))
    chosen = json.loads(options)
    if head == "pilot":
        return lambda tools: fly(tools, chosen)
    return lambda tools: fly_max(tools, chosen)


def run_episode(name: str, seed: int, option: str = "normal") -> Dict[str, Any]:
    env = make_env(seed, option)
    tools = PublicTools(env)
    started = time.time()
    policy(name)(tools)          # player errors propagate: they must not turn into a low score
    seconds = time.time() - started
    while not env.advance(5)["episode_complete"]:
        pass
    result = env.evaluate()
    return {"policy": name, "seed": seed, "map": option, "result": result,
            "reward": result["raw_score"] / result["max_available_value"],
            "trips": getattr(env, "_slip_trips", 0), "public_calls": tools.calls,
            "seconds": round(seconds, 2)}


def _job(job: Tuple[str, int, str]) -> Dict[str, Any]:
    return run_episode(*job)


def compare(names: Sequence[str], seeds: Sequence[int], maps: Sequence[str] = OPTIONS,
            workers: int = 6) -> Dict[Tuple[str, str], List[Dict[str, Any]]]:
    """Every player on every seed and map. Keys are (map, player); rows are in seed order."""
    jobs = [(name, seed, option) for option in maps for seed in seeds for name in names]
    runs: Dict[Tuple[str, str], List[Dict[str, Any]]] = {(option, name): [] for option in maps for name in names}
    if workers <= 1:
        done = [_job(job) for job in jobs]
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            done = list(pool.map(_job, jobs))
    for run in done:
        runs[(run["map"], run["policy"])].append(run)
    return runs


def paired(first: List[Dict[str, Any]], second: List[Dict[str, Any]], draws: int = 2000,
           seed: int = 0) -> Tuple[float, float, float, int]:
    """Mean score difference on the same seeds, a 95% bootstrap interval, and the seeds won."""
    other = {r["seed"]: r["reward"] for r in second}
    gaps = [r["reward"] - other[r["seed"]] for r in first if r["seed"] in other]
    rng = random.Random(seed)
    means = sorted(statistics.mean(rng.choice(gaps) for _ in gaps) for _ in range(draws))
    wins = sum(gap > 1e-9 for gap in gaps)
    return statistics.mean(gaps), means[int(0.025 * draws)], means[int(0.975 * draws) - 1], wins


def table(runs: Dict[Tuple[str, str], List[Dict[str, Any]]]) -> str:
    lines = ["{:<7} {:<30} {:>6} {:>6} {:>6} {:>5} {:>5} {:>6} {:>7} {:>6}".format(
        "map", "player", "mean", "min", "max", "dead", "away", "trips", "samples", "sec")]
    for (option, name), rows in runs.items():
        rewards = [r["reward"] for r in rows]
        lines.append("{:<7} {:<30} {:>6.3f} {:>6.3f} {:>6.3f} {:>5} {:>5} {:>6.1f} {:>7.1f} {:>6.1f}".format(
            option, name[:30], statistics.mean(rewards), min(rewards), max(rewards),
            sum(not r["result"]["alive"] for r in rows),
            sum(r["result"]["alive"] and not r["result"]["at_base"] for r in rows),
            statistics.mean(r["trips"] for r in rows),
            statistics.mean(len(r["result"]["sampled_targets"]) for r in rows),
            statistics.mean(r["seconds"] for r in rows)))
    return "\n".join(lines)


def differences(runs: Dict[Tuple[str, str], List[Dict[str, Any]]]) -> str:
    """The first player against each other player, map by map, on the same seeds."""
    lines = []
    maps = list(dict.fromkeys(option for option, _ in runs))
    for option in maps:
        names = [name for m, name in runs if m == option]
        for other in names[1:]:
            mean, low, high, wins = paired(runs[(option, names[0])], runs[(option, other)])
            lines.append("{:<7} {} - {}: {:+.3f} (95% {:+.3f} to {:+.3f}), higher on {} of {} seeds".format(
                option, names[0], other, mean, low, high, wins, len(runs[(option, names[0])])))
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seeds", default="1-12")
    parser.add_argument("--maps", default="normal,max", help="normal, max, or both")
    parser.add_argument("--policies", default="manh_max,pilot,greedy,straight")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--json", type=Path, default=None, help="write every run's result here")
    args = parser.parse_args(argv)
    separator = ";" if (";" in args.policies or "{" in args.policies) else ","
    names, seeds, maps = args.policies.split(separator), parse_seeds(args.seeds), args.maps.split(",")
    for option in maps:
        if option not in OPTIONS:
            parser.error("unknown map {!r}: choose from {}".format(option, ", ".join(OPTIONS)))
    for name in names:
        policy(name)
    runs = compare(names, seeds, maps, args.workers)
    print(table(runs))
    if len(names) >= 2:
        print(differences(runs))
    if args.json:
        args.json.write_text(json.dumps([run for rows in runs.values() for run in rows], indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
