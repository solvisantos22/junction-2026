"""No satellite positioning: the rover's position is not in telemetry and has to be worked out.

    env = make_nogps_env(seed=7, delay=3, profile="rush_noisy")          # in Main Mars
    env = make_nogps_env(seed=7, delay=3, biome="troy_crust")            # or in any biome
    env = make_nogps_env(seed=7, delay=3, navigation=WEAK_GPS)           # with a very noisy fix kept
    env = make_nogps_env(seed=7, delay=3, navigation=MANY_SENSORS)       # many weak sensors to fuse

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

More to fuse, each off unless its setting is given (an episode without them is unchanged):

    beacons                 more radio beacons, placed by the seed around the working area and
                            listed in map(). One range is a ring around its beacon; several
                            rings cross. beacon_ranges_m carries one entry per beacon. A range
                            can get vaguer with distance (beacon_range_noise_per_m), and a packet
                            can miss a beacon (beacon_hear_chance), so that no single packet
                            pins the rover down
    gyro_noise_deg          a gyroscope: gyro_turn_deg, in the packet of an executed drive, is
                            how far the heading really driven turned since the previous executed
                            drive. Precise from one drive to the next, but summing turns drifts;
                            the compass is the opposite
    heading_walk_deg, heading_wobble_deg
                            how far the hidden heading bias wanders per drive, and how much each
                            drive's heading jitters on top of it (the sensing model's 0.5 and 1.5)
    visual_odometry_noise   a coarser visual odometry than the sensing model's 5%
    wheel_scale_error       the wheels are a hidden few percent bigger or smaller than the
                            odometer assumes: a drive covers wheel_scale times the ground, and
                            the wheel odometer does not notice. The rover can now overshoot a
                            commanded drive; without this it can only fall short

The wheel scale alone, on today's telemetry, is wheels.py. Everything here is published in
rules()["navigation"]; the seed fixes the noise. The evaluator's
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
from .wheels import WHEEL_SCALE_RULE, drive_with_scale, hidden_wheel_scale

# Published defaults. heading_bias_deg replaces the +-5 degrees of the noisy profiles.
NAVIGATION = {
    "beacon_range_noise_m": 0.25,   # std dev of every beacon range
    "sun_compass_noise_deg": 6.0,   # std dev of the heading reported for an executed drive
    "heading_bias_deg": 15.0,       # the hidden bias starts uniform in +-this many degrees
    "position_noise_m": None,       # None: no position fix. A number: a fix every tick with this
                                    # std dev per axis (the noisy profiles publish 0.3)
}

# More to fuse. Off by default, and then neither published nor drawn: an episode without them is
# the episode it was before they existed.
EXTRAS = {
    "beacons": 1,                    # radio beacons, the one at the base included
    "beacon_range_noise_per_m": 0.0,  # extra std dev of a range per metre of true distance
    "beacon_hear_chance": 1.0,       # chance that a packet carries a given beacon's range
    "gyro_noise_deg": None,          # None: no gyroscope. A number: std dev of every turn reading
    "heading_walk_deg": None,        # None: the sensing model's 0.5. A number: the step the hidden
                                     # heading bias takes before every executed drive
    "heading_wobble_deg": None,      # None: the sensing model's 1.5. A number: the independent
                                     # heading noise of every executed drive
    "wheel_scale_error": 0.0,        # wheel_scale is hidden, uniform in 1 +- this
    "visual_odometry_noise": None,   # None: the sensing model's 0.05. A number: the std dev of the
                                     # relative error of reported visual odometry
}
MAY_BE_NONE = ("position_noise_m", "gyro_noise_deg", "heading_walk_deg", "heading_wobble_deg",
               "visual_odometry_noise")
BEACON_RING_M = (9.0, 14.0)          # extra beacons stand this far from the base, around the targets

# Weak sensors all round: a position fix that is there but far too coarse to drive by (about
# seven times today's noise), and a compass twice as coarse as the default. Chosen on development
# seeds 0-19 as the setting where taking any one sensor away costs the fusing reference
# something and no player leaning on a single sensor comes within ten points of it.
WEAK_GPS = {"position_noise_m": 2.0, "sun_compass_noise_deg": 12.0}

# Many weak sensors: no reading can be trusted alone, and each question has more than one answer.
#   how far did it drive?   a wheel odometer off by a hidden scale, and a coarse visual odometry
#   which way?              a coarse compass, and a gyroscope that only knows turns
#   where is it?            a very noisy fix, and four beacons that are vague far away and that a
#                           packet does not always hear
# Chosen on development seeds 0-19 (rush_noisy, delay 3) as the setting where ignoring the fix,
# the beacons, the compass or the wheel scale each costs the fusing reference at least five
# points, while that reference scores about what it scores with WEAK_GPS alone.
MANY_SENSORS = {**WEAK_GPS, "beacons": 4, "beacon_range_noise_per_m": 0.1, "beacon_hear_chance": 0.7,
                "gyro_noise_deg": 1.0, "wheel_scale_error": 0.2, "visual_odometry_noise": 0.15}


def _wrap(degrees):
    """An angle difference in (-180, 180]."""
    return -((-degrees + 180.0) % 360.0 - 180.0)


class NoGpsEnvironment(BiomeEnvironment):
    def __init__(self, seed=0, config=None, profile="rush_noisy", biome=MAIN, navigation=None,
                 sensing=None, noise_level=1.0, **kw):
        nav = {**NAVIGATION, **EXTRAS}
        extra = dict(navigation or {})
        unknown = set(extra) - set(nav)
        if unknown:
            raise ValueError(f"unknown navigation settings: {sorted(unknown)}")
        nav.update(extra)
        if any(value is not None and value < 0 for value in nav.values()):
            raise ValueError("navigation settings cannot be negative")
        if any(nav[name] is None for name in nav if name not in MAY_BE_NONE):
            raise ValueError("only {} can be None".format(", ".join(MAY_BE_NONE)))
        if type(nav["beacons"]) is not int or not 1 <= nav["beacons"] <= 8:
            raise ValueError("beacons must be a whole number from 1 to 8")
        if not 0 < nav["beacon_hear_chance"] <= 1:
            raise ValueError("beacon_hear_chance must be in (0, 1]")
        if nav["wheel_scale_error"] >= 0.5:
            raise ValueError("wheel_scale_error must be below 0.5")
        if nav["position_noise_m"] is None and (kw.get("factors") or {}).get("fix_outliers"):
            raise ValueError("fix_outliers needs a position fix, and this navigation setting has none")
        if sensing is None:  # the published sensing model, on every profile, with the wider bias
            sensing = {name: value * noise_level for name, value in SENSING.items()}
            sensing["heading_bias_deg"] = nav["heading_bias_deg"]
            if nav["position_noise_m"] is not None:
                sensing["position_noise_m"] = nav["position_noise_m"]
            if nav["heading_walk_deg"] is not None:
                sensing["heading_bias_walk_deg"] = nav["heading_walk_deg"]
            if nav["heading_wobble_deg"] is not None:
                sensing["heading_noise_deg"] = nav["heading_wobble_deg"]
            if nav["visual_odometry_noise"] is not None:
                sensing["visual_odometry_noise"] = nav["visual_odometry_noise"]
        self.navigation = nav
        self._drive_heading = None   # (tick, heading really driven) of the latest executed drive
        self._driven_before = None   # the heading really driven by the executed drive before it
        self._turn = None            # (tick, turn since the drive before), what the gyroscope senses
        self._wheel_scale = hidden_wheel_scale(seed, nav["wheel_scale_error"])
        super().__init__(seed=seed, config=config, profile=profile, biome=biome, sensing=sensing,
                         noise_level=noise_level, **kw)
        self._beacons = self._place_beacons(nav["beacons"])
        # The launch briefing: an exact position (the rover stands on the base) and exact ranges.
        for packet in (self._received[0], self._truth[0]):
            packet["beacon_range_m"], packet["sun_heading_deg"] = 0.0, None
            if len(self._beacons) > 1:
                packet["beacon_ranges_m"] = [round(math.dist(self._beacons[0], beacon), 6) for beacon in self._beacons]
            if nav["gyro_noise_deg"] is not None:
                packet["gyro_turn_deg"] = None

    def _place_beacons(self, count):
        """The base beacon, then count - 1 more on a ring around the working area, fixed by the seed."""
        world = self._world
        bx, by = world.base
        beacons = [(float(bx), float(by))]
        rng = random.Random(f"{self._seed}:beacons")
        start = rng.uniform(0.0, 360.0)
        for i in range(count - 1):
            for _ in range(200):
                angle = math.radians(start + 360.0 * i / (count - 1) + rng.uniform(-25.0, 25.0))
                radius = rng.uniform(*BEACON_RING_M)
                x, y = bx + radius * math.cos(angle), by + radius * math.sin(angle)
                if (1.0 <= x <= world.width - 1.0 and 1.0 <= y <= world.height - 1.0
                        and not any(hazard.contains(x, y) for hazard in world.hazards)):
                    break
            else:
                raise ValueError("no room for a beacon on this map")
            beacons.append((round(x, 3), round(y, 3)))
        return beacons

    def _published(self):
        """The navigation numbers a player is told: the four of every episode, then those in use."""
        nav = self.navigation
        out = {name: nav[name] for name in NAVIGATION}
        if nav["beacons"] > 1:
            out["beacons"] = nav["beacons"]
        if nav["beacon_range_noise_per_m"] > 0:
            out["beacon_range_noise_per_m"] = nav["beacon_range_noise_per_m"]
        if nav["beacon_hear_chance"] < 1:
            out["beacon_hear_chance"] = nav["beacon_hear_chance"]
        if nav["gyro_noise_deg"] is not None:
            out["gyro_noise_deg"] = nav["gyro_noise_deg"]
        if nav["wheel_scale_error"] > 0:
            out["wheel_scale_error"] = nav["wheel_scale_error"]
        return out

    # ---- public tools ---------------------------------------------------------------------
    def rules(self):
        rules = super().rules()
        nav = self.navigation
        has_fix = nav["position_noise_m"] is not None
        noise = "std dev beacon_range_noise_m" + (
            " + beacon_range_noise_per_m x the true distance" if nav["beacon_range_noise_per_m"] > 0 else "")
        unheard = ("; null when the beacon is not heard (each packet hears each beacon with chance "
                   "beacon_hear_chance)" if nav["beacon_hear_chance"] < 1 else "")
        rules["navigation"] = {
            **self._published(),
            "position": ("in every packet after the exact tick-0 briefing: true position + Gaussian noise with "
                         "std dev position_noise_m per axis, clipped to the map" if has_fix else
                         "null in every telemetry packet after the tick-0 briefing, which is exact"),
            "beacon_range_m": (f"in every packet: true distance to the base + Gaussian noise with {noise}, "
                               f"never below 0{unheard}"),
            "sun_heading_deg": ("in the packet of an executed drive: the heading the rover really drove "
                                "(commanded heading + heading error, see heading) + Gaussian noise with "
                                "std dev sun_compass_noise_deg; null on a tick without a drive"),
        }
        if nav["beacons"] > 1:
            rules["navigation"]["beacon_ranges_m"] = (
                "in every packet: one entry per beacon of map()['beacons'], in that order, the base first: true "
                f"distance to that beacon + Gaussian noise with {noise}, never below 0{unheard}; "
                "beacon_range_m repeats the first entry")
        if nav["gyro_noise_deg"] is not None:
            rules["navigation"]["gyro_turn_deg"] = (
                "in the packet of an executed drive: how far the heading really driven turned since the previous "
                "executed drive, in degrees in (-180, 180], counter-clockwise positive, + Gaussian noise with "
                "std dev gyro_noise_deg; null on a tick without a drive and for the first executed drive")
        if nav["wheel_scale_error"] > 0:
            rules["navigation"]["wheel_scale"] = WHEEL_SCALE_RULE
        if not has_fix:
            rules["position_fix"] = "none: see navigation; the tick-0 briefing position is exact"
            rules["sensing"] = {name: value for name, value in rules["sensing"].items() if name != "position_noise_m"}
        return rules

    def map(self):
        public = super().map()
        if len(self._beacons) > 1:
            public["beacons"] = [{"id": "base" if i == 0 else f"beacon_{i}", "x": x, "y": y}
                                 for i, (x, y) in enumerate(self._beacons)]
        return public

    # ---- hooks ------------------------------------------------------------------------------
    def _drive(self, command, events):
        wheel, visual = drive_with_scale(self._wheel_scale, command, events, super()._drive)
        error = self._heading_errors[-1] if self._heading_errors else None
        if error is not None and error["tick"] == self._tick:
            heading = (command["heading_deg"] + error["error_deg"]) % 360.0
            self._drive_heading = (self._tick, heading)
            if wheel > 0:
                if self._driven_before is not None:
                    self._turn = (self._tick, _wrap(heading - self._driven_before))
                self._driven_before = heading
        return wheel, visual

    def _range(self, index, tick, first):
        """The reading of beacon `index` in the packet of `tick`, or None when it is not heard."""
        nav = self.navigation
        if nav["beacon_hear_chance"] < 1 and random.Random(f"{self._seed}:hear:{index}:{tick}").random() >= nav["beacon_hear_chance"]:
            return None
        x, y = self._beacons[index]
        distance = math.hypot(self._x - x, self._y - y)
        sigma = nav["beacon_range_noise_m"] + nav["beacon_range_noise_per_m"] * distance
        rng = first if index == 0 else random.Random(f"{self._seed}:beacon:{index}:{tick}")
        return round(max(0.0, distance + rng.gauss(0.0, sigma)), 6)

    def _measured(self, packet):
        packet = super()._measured(packet)
        if self._exact:  # the privileged bounds keep the exact telemetry
            return packet
        nav, tick = self.navigation, packet["tick"]
        rng = random.Random(f"{self._seed}:nav:{tick}")
        base = self._range(0, tick, rng)
        if base is None:
            rng.gauss(0.0, 1.0)  # keep the compass draw where it is whether or not the base is heard
        drove = packet["wheel_odometry"] > 0
        heading = None
        if self._drive_heading is not None and self._drive_heading[0] == tick and drove:
            heading = round((self._drive_heading[1] + rng.gauss(0.0, nav["sun_compass_noise_deg"])) % 360.0, 6)
        position = packet["position"] if nav["position_noise_m"] is not None else None
        packet = {**packet, "position": position, "beacon_range_m": base, "sun_heading_deg": heading}
        if len(self._beacons) > 1:
            packet["beacon_ranges_m"] = [base] + [self._range(i, tick, None) for i in range(1, len(self._beacons))]
        if nav["gyro_noise_deg"] is not None:
            turn = None
            if self._turn is not None and self._turn[0] == tick and drove:
                noise = random.Random(f"{self._seed}:gyro:{tick}").gauss(0.0, nav["gyro_noise_deg"])
                turn = round(_wrap(self._turn[1] + noise), 6)
            packet["gyro_turn_deg"] = turn
        return packet

    def replay(self):
        replay = super().replay()
        replay["navigation"] = self._published()
        if len(self._beacons) > 1:
            replay["navigation"]["beacons_at"] = [list(beacon) for beacon in self._beacons]
        for name in ("heading_walk_deg", "heading_wobble_deg", "visual_odometry_noise"):
            if self.navigation[name] is not None:
                replay["navigation"][name] = self.navigation[name]
        if self._wheel_scale != 1.0:
            replay["navigation"]["wheel_scale"] = round(self._wheel_scale, 6)   # hidden from players
        return replay


def make_nogps_env(seed=0, delay=3, profile="rush_noisy", biome=MAIN, horizon=None, **kw):
    """One episode of `profile` in `biome` without a position fix. `kw`: navigation, settings, factors."""
    if profile not in PROFILES:
        raise ValueError(f"unknown profile {profile!r}; use one of {', '.join(PROFILES)}")
    horizon = PROFILES[profile][4] if horizon is None else horizon
    return NoGpsEnvironment(seed=seed, config=Config(delay_ticks=delay, max_ticks=horizon),
                            profile=profile, biome=biome, **kw)
