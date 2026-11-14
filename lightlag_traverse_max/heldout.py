"""The held-out evaluation worlds of the Traverse MAX map: test on them, never train or tune on them.

    from lightlag_traverse_max.heldout import EVALUATION_WORLDS, check_training_seeds
    check_training_seeds(range(200000, 300000))     # raises ValueError if any seed is reserved

Six worlds, picked by Manh on Saturday 14 November from the 24 worlds 500-523 by how manh_max
scored on them (docs/lightlag-runs/max-baseline/freeze.json says how):

  * superhard 505, 509, 515: manh_max scores about 0.1-0.2;
  * fair 500, 510, 520: manh_max scores about 0.5.

A seed makes the same ground on both maps (the MAX map adds its layers to the normal map's world),
so the whole range 500-523 is reserved on both maps, not only the six. Kristján's submission
worlds 2026-2029 (and the example world 99991 the request shows) are reserved too: his campaign and
task run on them. Every teammate's method is compared on EVALUATION_WORLDS, MAX map, so the
numbers stay comparable; the page viewer/traverse-evaluation-max.html replays them.
"""

from __future__ import annotations

from typing import Iterable, List

SUPERHARD_WORLDS = (505, 509, 515)
FAIR_WORLDS = (500, 510, 520)
EVALUATION_WORLDS = FAIR_WORLDS + SUPERHARD_WORLDS
MANH_RANGE = range(500, 524)              # the pool the six were picked from: seen, so never trained on
KRISTJANS_WORLDS = (2026, 2027, 2028, 2029, 99991)
RESERVED = frozenset(MANH_RANGE) | frozenset(KRISTJANS_WORLDS)


def reserved(seeds: Iterable[int]) -> List[int]:
    """The seeds among `seeds` that no training or tuning may use, sorted."""
    return sorted(RESERVED.intersection(int(seed) for seed in seeds))


def check_training_seeds(seeds: Iterable[int]) -> None:
    """Raise ValueError if any of `seeds` is a held-out or reserved world."""
    found = reserved(seeds)
    if found:
        shown = ", ".join(str(seed) for seed in found[:12]) + (" ..." if len(found) > 12 else "")
        raise ValueError("held-out Traverse worlds may not be trained or tuned on: {} "
                         "(see lightlag_traverse_max/heldout.py)".format(shown))
