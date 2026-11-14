"""Wheels of a hidden size: a drive can fall short of its commanded metres or overshoot them.

    env = make_overshoot_env(seed=7, delay=3, profile="rush_noisy")            # today's environment + the wheel scale
    env = make_overshoot_env(seed=7, delay=3, biome="troy_crust", error=0.1)   # in a biome, +-10%

In the team's environment a drive can only fall short: it covers M x (1 - slip) of ground and slip
is never below zero. Here the wheels are a hidden few percent bigger or smaller than the odometer
assumes. A drive of M commanded metres turns the wheels for M x wheel_scale metres, so it covers
M x wheel_scale x (1 - slip) and spends the energy of M x wheel_scale wheel metres. The wheel
odometer counts wheel turns, so it still reports M; visual odometry reports the ground covered.

The scale is drawn once per mission, uniform in 1 +- wheel_scale_error, and fixed by the seed. Its
range is published in rules()["wheels"]; its value is in the evaluator's replay only. Nothing else
changes: the telemetry fields, the position fix, the sensing model and the scoring are today's.
With an error of 0 the episode is the biome environment's, unchanged.

The navigation prototype (nogps.py) has the same rule as one of its settings and publishes it under
rules()["navigation"]; both draw the scale from the seed in the same way.

A sandbox option, not a rules decision. Standard library only.
"""

import random

from lightlag import Config
from lightlag_dynamic.missions import PROFILES

from .catalog import MAIN
from .environment import BiomeEnvironment

WHEEL_SCALE_ERROR = 0.2   # the published default: the wheel scale is uniform in 0.8 .. 1.2
WHEEL_SCALE_RULE = (
    "hidden for the whole mission, uniform in 1 - wheel_scale_error .. 1 + wheel_scale_error: a "
    "drive of M commanded metres turns the wheels for M x wheel_scale metres, so it covers "
    "M x wheel_scale x (1 - slip) of ground and spends the energy of M x wheel_scale wheel metres; "
    "wheel_odometry still reports the commanded wheel metres, visual_odometry the ground covered")


def hidden_wheel_scale(seed, error):
    """The mission's wheel scale: 1 when there is no error, else uniform in 1 +- error, fixed by the seed."""
    return 1.0 + random.Random(f"{seed}:wheel").uniform(-error, error) if error > 0 else 1.0


def drive_with_scale(scale, command, events, drive):
    """Run `drive` with the wheels turning scale x the commanded metres; report the commanded ones."""
    if scale == 1.0:
        return drive(command, events)
    wheel, visual = drive(dict(command, metres=command["metres"] * scale), events)
    return wheel / scale, visual  # the odometer counts wheel turns


class OvershootEnvironment(BiomeEnvironment):
    def __init__(self, seed=0, config=None, profile="rush_noisy", biome=MAIN, wheel_scale_error=WHEEL_SCALE_ERROR, **kw):
        if not isinstance(wheel_scale_error, (int, float)) or isinstance(wheel_scale_error, bool) or not 0 <= wheel_scale_error < 0.5:
            raise ValueError("wheel_scale_error must be a number from 0 to below 0.5")
        self.wheel_scale_error = float(wheel_scale_error)
        self._wheel_scale = hidden_wheel_scale(seed, self.wheel_scale_error)
        super().__init__(seed=seed, config=config, profile=profile, biome=biome, **kw)

    def rules(self):
        rules = super().rules()
        if self.wheel_scale_error > 0:
            rules["wheels"] = {"wheel_scale_error": self.wheel_scale_error, "wheel_scale": WHEEL_SCALE_RULE}
        return rules

    def _drive(self, command, events):
        return drive_with_scale(self._wheel_scale, command, events, super()._drive)

    def replay(self):
        replay = super().replay()
        if self.wheel_scale_error > 0:
            replay["wheels"] = {"wheel_scale_error": self.wheel_scale_error,
                                "wheel_scale": round(self._wheel_scale, 6)}   # hidden from players
        return replay


def make_overshoot_env(seed=0, delay=3, profile="rush_noisy", biome=MAIN, horizon=None, error=WHEEL_SCALE_ERROR, **kw):
    """One episode of `profile` in `biome` with wheels of a hidden size. `kw`: settings, factors, noise_level."""
    if profile not in PROFILES:
        raise ValueError(f"unknown profile {profile!r}; use one of {', '.join(PROFILES)}")
    horizon = PROFILES[profile][4] if horizon is None else horizon
    return OvershootEnvironment(seed=seed, config=Config(delay_ticks=delay, max_ticks=horizon),
                                profile=profile, biome=biome, wheel_scale_error=error, **kw)
