```python
"""Autonomous light-lagged Mars rover traverse autopilot."""

from __future__ import annotations

import collections
import heapq
import math
import random
import time
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

import lightlag_surface

INF = 1e18


def _clamp(val: float, lo: float, hi: float) -> float:
    return lo if val < lo else (hi if val > hi else val)


def _angle_diff_deg(target_deg: float, source_deg: float) -> float:
    return (target_deg - source_deg + 180.0) % 360.0 - 180.0


class SolarModel:
    """Tracks solar charging curve and learns hidden solar panel efficiency."""

    def __init__(self, rules: Dict[str, Any]) -> None:
        self.max_ticks: int = int(rules["max_ticks"])
        self.solar_peak: float = float(rules["solar_peak"])
        self.sun_margin: float = float(rules["sun_margin_ticks"])
        eff_range = rules["solar_efficiency_range"]
        self.eff_lo: float = float(eff_range[0])
        self.eff_hi: float = float(eff_range[1])
        # Slightly conservative prior until first uncapped charge packet arrives (~tick 8)
        self.efficiency: float = self.eff_lo + 0.35 * (self.eff_hi - self.eff_lo)
        self.exact_known: bool = False
        self.bat_cap: float = float(rules["battery_capacity"])

        denom = float(self.max_ticks + 2.0 * self.sun_margin)
        self.unit_solar: List[float] = [0.0] * (self.max_ticks + 16)
        for t in range(len(self.unit_solar)):
            arg = math.pi * (t + self.sun_margin) / denom
            s = math.sin(arg) if 0.0 <= arg <= math.pi else 0.0
            self.unit_solar[t] = self.solar_peak * max(0.0, s)

        self.prefix_solar: List[float] = [0.0] * (len(self.unit_solar) + 1)
        self._rebuild_prefix()

    def _rebuild_prefix(self) -> None:
        acc = 0.0
        eff = self.efficiency
        self.prefix_solar[0] = 0.0
        for i, u in enumerate(self.unit_solar):
            acc += u * eff
            self.prefix_solar[i + 1] = acc

    def raw_charge(self, tick: int, eff: Optional[float] = None) -> float:
        if tick < 0 or tick >= len(self.unit_solar):
            return 0.0
        return self.unit_solar[tick] * (self.efficiency if eff is None else eff)

    def sum_raw_charge(self, t_start_excl: int, t_end_incl: int) -> float:
        a = max(0, min(len(self.unit_solar), t_start_excl + 1))
        b = max(a, min(len(self.unit_solar), t_end_incl + 1))
        return self.prefix_solar[b] - self.prefix_solar[a]

    def observe_packet(self, tick: int, prev_battery: float, charge: float) -> None:
        if tick < 1 or self.exact_known:
            return
        u = self.unit_solar[tick] if tick < len(self.unit_solar) else 0.0
        if u <= 1e-6:
            return
        if prev_battery + charge < self.bat_cap - 1e-5:
            est = _clamp(charge / u, self.eff_lo, self.eff_hi)
            self.efficiency = est
            self.exact_known = True
            self._rebuild_prefix()
        elif charge > 1e-6:
            lb = _clamp(charge / u, self.eff_lo, self.eff_hi)
            if lb > self.efficiency:
                self.efficiency = lb
                self._rebuild_prefix()


class ParticleFilter:
    """Regularized particle filter over (x, y, heading_bias, slip_base)."""

    def __init__(
        self,
        surface: lightlag_surface.Surface,
        rules: Dict[str, Any],
        init_pos: Sequence[float],
        init_battery: float,
        rng: random.Random,
        n_particles: int = 150,
    ) -> None:
        self.surface = surface
        self.physics = rules["physics"]
        self.sensing = rules["sensing"]
        self.idle_cost = float(rules["idle_cost"])
        self.sample_cost = float(rules["sample_cost"])
        self.bat_cap = float(rules["battery_capacity"])
        self.target_radius = float(rules["target_radius"])
        self.rng = rng
        self.n = n_particles

        self.pos_noise = max(0.15, float(self.sensing["position_noise_m"]))
        self.vo_noise = max(0.01, float(self.sensing["visual_odometry_noise"]))
        self.bias_init = float(self.sensing["heading_bias_deg"])
        self.bias_walk = float(self.sensing["heading_bias_walk_deg"])
        self.heading_noise = float(self.sensing["heading_noise_deg"])
        self.slip_noise = float(self.physics["slip_noise"])
        self.slip_ranges: Dict[str, Tuple[float, float]] = {
            k: (float(v[0]), float(v[1]))
            for k, v in self.physics["slip_base_ranges"].items()
        }
        self.terrain_names = list(self.slip_ranges.keys())

        x0, y0 = float(init_pos[0]), float(init_pos[1])
        self.px: List[float] = [x0] * self.n
        self.py: List[float] = [y0] * self.n

        # Stratified initial bias coverage
        biases = [
            -self.bias_init + 2.0 * self.bias_init * (i + 0.5) / self.n
            for i in range(self.n)
        ]
        self.rng.shuffle(biases)
        self.pbias: List[float] = biases

        self.pslip: List[Dict[str, float]] = []
        for i in range(self.n):
            d: Dict[str, float] = {}
            for name, (lo, hi) in self.slip_ranges.items():
                d[name] = lo