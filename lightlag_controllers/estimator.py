"""Slip estimation from telemetry, starting from the published ranges."""

from __future__ import annotations

import math
from typing import Dict

from .model import Rules


class SlipEstimator:
    """Per-terrain slip estimate with a rough uncertainty half-width.

    Before any observation the estimate is the midpoint of the published range and
    the half-width is half that range. Each observed drive compares wheel odometry
    with the distance actually covered, as real rovers do.
    """

    MIN_WHEEL_M = 0.3  # ignore very short drives; rounding dominates them

    def __init__(self, rules: Rules, learn: bool = True) -> None:
        self._rules = rules
        self._learn = learn
        self._wheel: Dict[str, float] = {name: 0.0 for name in rules.terrains}
        self._moved: Dict[str, float] = {name: 0.0 for name in rules.terrains}
        self._drives: Dict[str, int] = {name: 0 for name in rules.terrains}

    def observe(self, terrain: str, wheel_m: float, moved_m: float) -> None:
        if not self._learn or terrain not in self._wheel or wheel_m < self.MIN_WHEEL_M:
            return
        self._wheel[terrain] += wheel_m
        self._moved[terrain] += moved_m
        self._drives[terrain] += 1

    def observed(self, terrain: str) -> bool:
        return self._drives.get(terrain, 0) > 0

    def mean(self, terrain: str) -> float:
        spec = self._rules.terrains[terrain]
        if not self.observed(terrain):
            return spec.slip_mid
        slip = 1.0 - self._moved[terrain] / self._wheel[terrain]
        # Per-drive noise can push a single reading slightly outside the range.
        return min(spec.slip_max + self._rules.slip_noise, max(spec.slip_min - self._rules.slip_noise, slip))

    def halfwidth(self, terrain: str) -> float:
        spec = self._rules.terrains[terrain]
        if not self.observed(terrain):
            return spec.slip_halfwidth
        return min(spec.slip_halfwidth, max(0.005, self._rules.slip_noise / math.sqrt(self._drives[terrain])))

    def cautious(self, terrain: str, caution: float) -> float:
        """Estimate shifted toward more slip by `caution` half-widths, for budgeting.

        A negative `caution` gives the hopeful end of the same interval.
        """
        return min(0.9, max(0.0, self.mean(terrain) + caution * self.halfwidth(terrain)))

    def snapshot(self) -> Dict[str, float]:
        return {name: round(self.mean(name), 4) for name in self._rules.terrains}
