"""Shared by the tests in this folder (run them with `unittest discover -s tests/lightlag_ppo_icm`)."""

import numpy as np

from lightlag_ppo_icm.player import plain_chooser  # noqa: F401  (the tests import it from here)


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

