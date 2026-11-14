"""No satellite positioning: the rover's position is not in telemetry and has to be worked out.

    env = make_nogps_env(seed=7, delay=3, profile="rush_noisy")          # in Main Mars
    env = make_nogps_env(seed=7, delay=3, biome="troy_crust")            # or in any biome
    env = make_nogps_env(seed=7, delay=3, navigation=WEAK_GPS)           # with a very noisy fix kept

Today every telemetry packet carries an absolute position fix, so a player can read where the
rover is. Mars has no satellite positioning: a rover dead-reckons from its wheels, its
cameras and an inertial unit, and takes an absolute heading from the Sun. Here, after the
launch briefing, the position field is null, and three things stand in for it:

    wheel_odometry, visual_odometry   how far the wheels turned and how far the rover moved
                                      (as today)
    sun_heading_deg                   in the packet of every executed drive: the heading the
                                      rover really drove, plus Gaussian noise (a sun compass)
    beacon_range_m                    in every packet: the distance to the lander's radio beacon
                                      at the base, plus Gaussian noise

No single reading gives a position. The commanded heading is off by a hidden, drifting bias,
wider here than on the noisy profiles, so dead reckoning on commanded headings walks away from
the map; one compass reading is too noisy to steer by; the range says how far from base, not
in which direction. Together, over several drives, they pin the rover down. The terrain
field, the battery and sample results are unchanged and carry information too.

A position fix can be kept as one more sensor: navigation=WEAK_GPS puts the position back in
every packet with 2 m of noise per axis, about seven times today's, and makes the compass twice
as coarse. The fix is then far too coarse to drive by, the compass too coarse to steer by, and
each is worth something only when fused with the rest.

Everything is published in rules()["navigation"]; the seed fixes the noise. The evaluator's
truth, scoring and the replay's states use the true position, as always.

A sandbox prototype, not a rules decision. Standard library only. Players that fuse the
sensors are in nogps_players.py (needs numpy).
"""

import math
import random

from lightlag import Config
from lightlag_dynamic.missions import PROFILES, SENSING

from .catalog import MAIN
from .environment import BiomeEnvironment

# Published defaults. heading_bias_deg replaces the +-5 degrees of the noisy profiles.
NAVIGATION = {
    "beacon_range_noise_m": 0.25,   # std dev of every beacon range
    "sun_compass_noise_deg": 6.0,   # std dev of the heading reported for an executed drive
    "heading_bias_deg": 15.0,       # the hidden bias starts uniform in +-this many degrees
    "position_noise_m": None,       # None: no position fix. A number: a fix every tick with this
                                    # std dev per axis (the noisy profiles publish 0.3)
}

# Weak sensors all round: a position fix that is there but far too coarse to drive by (about
# seven times today's noise), and a compass twice as coarse as the default. Chosen on development
# seeds 0-19 as the setting where taking any one sensor away costs the fusing reference
# something and no player leaning on a single sensor comes within ten points of it.
WEAK_GPS = {"position_noise_m": 2.0, "sun_compass_noise_deg": 12.0}


class NoGpsEnvironment(BiomeEnvironment):
    def __init__(self, seed=0, config=None, profile="rush_noisy", biome=MAIN, navigation=None,
                 sensing=None, noise_level=1.0, **kw):
        nav = dict(NAVIGATION)
        extra = dict(navigation or {})
        unknown = set(extra) - set(nav)
        if unknown:
            raise ValueError(f"unknown navigation settings: {sorted(unknown)}")
        nav.update(extra)
        if any(value is not None and value < 0 for value in nav.values()):
            raise ValueError("navigation settings cannot be negative")
        if any(nav[name] is None for name in nav if name != "position_noise_m"):
            raise ValueError("only position_noise_m can be None (no position fix)")
        if sensing is None:  # the published sensing model, on every profile, with the wider bias
            sensing = {name: value * noise_level for name, value in SENSING.items()}
            sensing["heading_bias_deg"] = nav["heading_bias_deg"]
            if nav["position_noise_m"] is not None:
                sensing["position_noise_m"] = nav["position_noise_m"]
        self.navigation = nav
        self._drive_heading = None
        super().__init__(seed=seed, config=config, profile=profile, biome=biome, sensing=sensing,
                         noise_level=noise_level, **kw)
        # The launch briefing: an exact position (the rover stands on the base) and a zero range.
        for packet in (self._received[0], self._truth[0]):
            packet["beacon_range_m"], packet["sun_heading_deg"] = 0.0, None

    # ---- public tools ---------------------------------------------------------------------
    def rules(self):
        rules = super().rules()
        has_fix = self.navigation["position_noise_m"] is not None
        rules["navigation"] = {
            **self.navigation,
            "position": ("in every packet after the exact tick-0 briefing: true position + Gaussian noise with "
                         "std dev position_noise_m per axis, clipped to the map" if has_fix else
                         "null in every telemetry packet after the tick-0 briefing, which is exact"),
            "beacon_range_m": ("in every packet: true distance to the base + Gaussian noise with std dev "
                               "beacon_range_noise_m, never below 0"),
            "sun_heading_deg": ("in the packet of an executed drive: the heading the rover really drove "
                                "(commanded heading + heading error, see heading) + Gaussian noise with "
                                "std dev sun_compass_noise_deg; null on a tick without a drive"),
        }
        if not has_fix:
            rules["position_fix"] = "none: see navigation; the tick-0 briefing position is exact"
            rules["sensing"] = {name: value for name, value in rules["sensing"].items() if name != "position_noise_m"}
        return rules

    # ---- hooks ------------------------------------------------------------------------------
    def _drive(self, command, events):
        result = super()._drive(command, events)
        error = self._heading_errors[-1] if self._heading_errors else None
        if error is not None and error["tick"] == self._tick:
            self._drive_heading = (self._tick, (command["heading_deg"] + error["error_deg"]) % 360.0)
        return result

    def _measured(self, packet):
        packet = super()._measured(packet)
        if self._exact:  # the privileged bounds keep the exact telemetry
            return packet
        rng = random.Random(f"{self._seed}:nav:{packet['tick']}")
        bx, by = self._world.base
        reading = math.hypot(self._x - bx, self._y - by) + rng.gauss(0.0, self.navigation["beacon_range_noise_m"])
        heading = None
        if (self._drive_heading is not None and self._drive_heading[0] == packet["tick"]
                and packet["wheel_odometry"] > 0):
            heading = round((self._drive_heading[1] + rng.gauss(0.0, self.navigation["sun_compass_noise_deg"])) % 360.0, 6)
        position = packet["position"] if self.navigation["position_noise_m"] is not None else None
        return {**packet, "position": position, "beacon_range_m": round(max(0.0, reading), 6),
                "sun_heading_deg": heading}

    def replay(self):
        replay = super().replay()
        replay["navigation"] = dict(self.navigation)
        return replay


def make_nogps_env(seed=0, delay=3, profile="rush_noisy", biome=MAIN, horizon=None, **kw):
    """One episode of `profile` in `biome` without a position fix. `kw`: navigation, settings, factors."""
    if profile not in PROFILES:
        raise ValueError(f"unknown profile {profile!r}; use one of {', '.join(PROFILES)}")
    horizon = PROFILES[profile][4] if horizon is None else horizon
    return NoGpsEnvironment(seed=seed, config=Config(delay_ticks=delay, max_ticks=horizon),
                            profile=profile, biome=biome, **kw)
