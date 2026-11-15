"""The known limit, measured: with this repository's code, the public map gives away the seed.

    python3 -m tools.traverse_integrity.twin --seed 1203 --limit 2000

A world and everything hidden in it are drawn from generators seeded by the mission's seed. So
whoever holds the simulator's code can (1) find the seed by generating worlds until one matches
the public map, and (2) start a copy of the simulator with it and read off every hidden value
and every future noise draw. This script does both on one of the review's own worlds and says
how long it took. The agent's container holds no simulator code (the probes check that), so this
needs the repository; it is the reason the seeds are one line the judges can change.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from lightlag_traverse.environment import MISSION, TraverseEnvironment  # noqa: E402
from lightlag_traverse.terrain import make_world  # noqa: E402

PUBLIC: Tuple = ()


def fingerprint(base, targets) -> Tuple:
    """What map() shows at tick 0: the lander and the first targets."""
    return (tuple(base), tuple((target["x"], target["y"], target["value"]) for target in targets[:6]))


def remember(public: Tuple) -> None:
    global PUBLIC
    PUBLIC = public


def same(candidate: int) -> Optional[int]:
    world = make_world(candidate, MISSION["max_ticks"])
    shown = [{"x": target.x, "y": target.y, "value": target.value} for target in world.targets if target.appear_tick == 0]
    return candidate if fingerprint(world.base, shown) == PUBLIC else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, default=1203, help="the world to recover; one of the review's own")
    parser.add_argument("--limit", type=int, default=2000, help="candidates 0..limit-1 are tried")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    secret = TraverseEnvironment(args.seed)
    shown = secret.map()
    public = fingerprint(shown["base"], shown["targets"])
    started = time.time()
    with multiprocessing.Pool(args.workers, initializer=remember, initargs=(public,)) as pool:
        found: List[int] = [seed for seed in pool.imap_unordered(same, range(args.limit), chunksize=16) if seed is not None]
    search = time.time() - started

    report = {"candidates": args.limit, "workers": args.workers, "search_seconds": round(search, 1), "found": found}
    if found == [args.seed]:
        twin = TraverseEnvironment(found[0])
        commands = [{"action": "drive", "heading_deg": 20.0 * step, "metres": 4.0} for step in range(5)]
        for env in (secret, twin):
            for _ in range(8):
                env.uplink(commands)
                env.advance(5)
        report["hidden_values_equal"] = (secret._slip == twin._slip and secret._efficiency == twin._efficiency
                                         and secret._initial_heading_bias == twin._initial_heading_bias)
        report["true_states_equal_after_40_ticks"] = secret._truth == twin._truth
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
