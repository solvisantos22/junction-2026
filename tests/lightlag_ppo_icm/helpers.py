"""Shared by the tests in this folder (run them with `unittest discover -s tests/lightlag_ppo_icm`)."""

import numpy as np


def numeric_gradient(loss, array, picks, eps=1e-6):
    """Central differences of `loss()` at a few entries of `array` (changed in place, restored)."""
    out = []
    for index in picks:
        saved = array[index]
        array[index] = saved + eps
        up = loss()
        array[index] = saved - eps
        down = loss()
        array[index] = saved
        out.append((up - down) / (2 * eps))
    return np.array(out)


def some_entries(rng, array, count=6):
    flat = rng.choice(array.size, size=min(count, array.size), replace=False)
    return [np.unravel_index(i, array.shape) for i in flat]


def plain_chooser(config):
    """A hand-written player that reads the observation only: sample when the nearest open target is
    in range, else drive at it; turn for home when the time or energy margin runs low. It checks
    that the observation holds enough to act on, and gives the tests episodes that score."""
    import math

    from lightlag_ppo_icm.task import BASE, FIRST_DRIVE, GLOBAL, SAMPLE, WAIT

    sizes = len(config.metres)

    def drive(cos, sin, near):
        heading = int(round(math.degrees(math.atan2(sin, cos)) / (360.0 / config.headings))) % config.headings
        size = sizes - 1 if near > 0.45 else (1 if near > 0.2 else 0)
        return FIRST_DRIVE + heading * sizes + size

    def choose(obs):
        base = obs[GLOBAL:GLOBAL + BASE]
        target = obs[GLOBAL + BASE:]
        if target[0] > 0 and base[5] > 0.15 and base[6] > 0.12:
            return SAMPLE if target[5] > 0 else drive(target[1], target[2], target[4])
        return WAIT if base[4] > 0 else drive(base[0], base[1], base[3])

    return choose
