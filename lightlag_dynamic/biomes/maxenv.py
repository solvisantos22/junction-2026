"""The max env: every option that combines, switched on at once.

    env = make_max_env(seed=7, delay=3)               # the preset below
    env = make_max_env(seed=7, delay=3, rocks=True)   # Gale Rock Field in place of Hidden Valley

What is on:
  profile   rush_noisy: 50 ticks, sample deadlines, targets discovered mid-mission, noisy sensing
            and heading drift
  biomes    Relay Pass + Hidden Valley + Bagnold Dunes + Troy Crust + Meridiani Ripples. Gale Rock
            Field and Hidden Valley cannot be mixed (the rough-ground drive loop has no slip check),
            so rocks=True swaps the one for the other
  sensors   MANY_SENSORS: a position fix 2 m off, four radio beacons that are vague far away and
            not always heard, a coarse sun compass, a gyroscope, coarse visual odometry, and wheels
            of a hidden size (+-20%)
  factors   the controller lab's mildest settings: a turn costs 0.01 energy per degree, a drive
            covers at most 2 m, 10% of telemetry packets are lost, and 5% of position fixes are off
            by an extra 3 m (sigma per axis)

Left out because it does not combine or adds nothing: the slip jump and unmapped sand (not with
Bagnold Dunes), orbiter downlink passes (Relay Pass already holds telemetry back to a pass) and
the real-time clock (plain profiles only).

A stress test for controllers, not a rules decision. Standard library only.
"""

import copy

from lightlag import Config
from lightlag_dynamic.missions import PROFILES

from .nogps import MANY_SENSORS, NoGpsEnvironment

MAX_BIOME = "relay_pass+hidden_valley+bagnold_dunes+troy_crust+meridiani_ripples"
MAX_BIOME_ROCKS = "relay_pass+gale_rock_field+bagnold_dunes+troy_crust+meridiani_ripples"
MAX_FACTORS = {"turn_cost": 0.01, "max_metres": 2.0, "packet_loss": {"p": 0.10},
               "fix_outliers": {"p": 0.05, "sigma": 3.0}}


def make_max_env(seed=0, delay=3, profile="rush_noisy", rocks=False, horizon=None):
    """One episode of the max env. `rocks`: Gale Rock Field in place of Hidden Valley."""
    if profile not in PROFILES:
        raise ValueError(f"unknown profile {profile!r}; use one of {', '.join(PROFILES)}")
    horizon = PROFILES[profile][4] if horizon is None else horizon
    return NoGpsEnvironment(seed=seed, config=Config(delay_ticks=delay, max_ticks=horizon), profile=profile,
                            biome=MAX_BIOME_ROCKS if rocks else MAX_BIOME, navigation=dict(MANY_SENSORS),
                            factors=copy.deepcopy(MAX_FACTORS))
