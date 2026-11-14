"""Players for the no-GPS option, and a probe that compares them (needs numpy).

    python3 -m lightlag_dynamic.biomes.nogps_players --seeds 0-19            # every player, no fix
    python3 -m lightlag_dynamic.biomes.nogps_players --seeds 0-19 --weak-gps # a very noisy fix kept
    python3 -m lightlag_dynamic.biomes.nogps_players --players fused blind --delays 0 3 5
    python3 -m lightlag_dynamic.biomes.nogps_players --seeds 0-19 --many-sensors   # many weak sensors
    python3 -m lightlag_dynamic.biomes.nogps_players --weak-gps --set beacons=3 --set gyro_noise_deg=2

The fusing reference (`fused`) is the Manh controllers' particle-filter controller with three
more likelihoods, one per sensor that stands in for a trustworthy position fix:

    beacon range    a ring around the base: weight each particle by how well its distance fits
    sun compass     the heading of the drive just made: weight each particle's own heading
    terrain         the terrain under the rover against the published map (map matching)

A range is a ring and a terrain reading is a region, neither of which a Kalman filter's
Gaussian can hold; a particle filter weighs them as they are. Sample results stay as in the
zoo's filter: a sample taken puts the rover inside that target's radius, a miss outside.
The planner is unchanged: it plans on the filter's mean and covariance.

The other players are what a player without that filter might do:

    fused_no_<sensor>   the reference with one sensor ignored (what each sensor is worth)
    odometry_only       the reference with all of them ignored: wheels, cameras and sample results
    dr_commanded        the frozen reference, kf_mpc, fed a position dead-reckoned from the
                        commanded headings and visual odometry
    dr_compass          kf_mpc fed a position dead-reckoned from each raw compass reading
    dr_mean_compass     kf_mpc fed a position dead-reckoned from the commanded heading plus the
                        average compass error so far: the simplest fusion there is
    blind               plans once from the briefing and never reads telemetry

With a very noisy position fix kept in the packets (--weak-gps), the fix is a fourth sensor
for `fused`, the dead-reckoning players ignore it, and three more players show what it is
worth on its own:

    fix_only            the particle filter fed the fix and odometry, nothing else
    kf_mpc_on_fix       the frozen reference as it is: a Kalman filter on the fix and odometry
    trusts_fix          re-plans from every fix as if it were exact

With more to fuse (--many-sensors, or --set name=value for single settings), `fused` also
weighs every beacon heard, each ring with its own width, and the gyroscope's turn between two
drives, and it carries the hidden wheel scale as one more unknown per particle. Three more
players show what the new readings give without that filter:

    fused_no_gyro, fused_no_scale   the reference without the gyroscope, or taking the wheels
                                    at their nominal size
    dr_gyro_compass     dead reckoning on the gyroscope's turns, anchored by the average of the
                        compass readings carried along those turns: a complementary filter in
                        ten lines
    dr_beacons          the same, and whenever a packet hears three beacons or more the position
                        jumps to where their rings cross (least squares)
    kf_mpc_on_crossings the frozen reference, its position fix replaced by that crossing, each
                        ring weighed by its width, whenever three beacons or more are heard

Scripted players only. A sandbox prototype, not a rules decision.
"""

import argparse
import math
import os
import statistics as st
from multiprocessing import Pool

import numpy as np

from lightlag_dynamic.controllers import POLICIES
from lightlag_dynamic.manh_controllers import controllers as zoo
from lightlag_dynamic.manh_controllers.estimators import VAR_FLOOR, ParticleFilter

# What the reference may use. "fix" and "gyro" only do anything when the packets carry them;
# "scale" is not a sensor but the hidden wheel scale, estimated when the rules publish one.
SENSORS = ("fix", "range", "compass", "terrain", "gyro", "scale")


class NavParticleFilter(ParticleFilter):
    """The zoo's particle filter plus the beacon ranges, the sun compass, the terrain reading, the
    gyroscope and, when the wheels may be off their nominal size, a wheel scale per particle."""

    g = None            # each particle's wheel scale minus 1, when the rules publish a wheel-size error
    scale_error = 0.0
    gyro = False        # set when the packets carry a gyroscope reading to weigh
    last_theta = None   # the heading each particle drove in the drive just predicted
    prev_theta = None   # ... and in the executed drive before it, for the gyroscope
    turn = None

    def learn_scale(self, error):
        """Carry the hidden wheel scale: uniform in 1 +- error, as published."""
        self.scale_error = float(error)
        self.g = self.rng.uniform(-error, error, self.n)

    def predict(self, heading_deg, wheel):
        x0, y0 = self.x.copy(), self.y.copy()
        super().predict(heading_deg, wheel)
        if self.g is not None:
            # The wheels turn for scale x the reported metres: the whole drive stretches with it.
            # (Exact on one terrain; where a drive crosses into sand the crossing shifts a little.)
            k = 1.0 + self.g
            self.x, self.y = x0 + (self.x - x0) * k, y0 + (self.y - y0) * k
            self.last_ground = self.last_ground * k
        moved = self.last_ground > 1e-6
        # The heading each particle really drove: its own bias and noise draw, read off its path.
        theta = np.where(moved, np.arctan2(self.y - y0, self.x - x0), math.radians(heading_deg) + self.b)
        self.last_theta = theta
        if self.gyro:
            self.turn = None if self.prev_theta is None else theta - self.prev_theta
            self.prev_theta = theta

    def update_gyro(self, turn_deg, sigma_deg):
        """The turn since the drive before: each particle's own two headings against the reading."""
        if self.turn is None:
            return
        off = math.radians(turn_deg) - self.turn
        off = (off + math.pi) % (2 * math.pi) - math.pi
        self.logw += -0.5 * (off / math.radians(max(sigma_deg, 0.1))) ** 2
        self._normalise()

    def update_compass(self, measured_deg, sigma_deg):
        if getattr(self, "last_theta", None) is None:
            return
        off = math.radians(measured_deg) - self.last_theta
        off = (off + math.pi) % (2 * math.pi) - math.pi
        self.logw += -0.5 * (off / math.radians(max(sigma_deg, 0.1))) ** 2
        self._normalise()

    def update_range(self, measured, point, sigma, per_m=0.0):
        distance = np.hypot(self.x - point[0], self.y - point[1])
        if per_m > 0:  # a ring that gets wider with distance: its width depends on the particle
            sd = np.maximum(sigma + per_m * distance, 0.02)
            self.logw += -0.5 * ((measured - distance) / sd) ** 2 - np.log(sd)
        else:
            self.logw += -0.5 * ((measured - distance) / max(sigma, 0.02)) ** 2
        self._normalise()

    def update_terrain(self, reported, miss=0.05):
        on_sand = self._terrain(self.x, self.y) == 1
        fits = on_sand if reported == "sand" else ~on_sand
        self.logw += np.where(fits, math.log(1.0 - miss), math.log(miss))
        self._normalise()

    def maybe_resample(self):
        if self.g is None and self.prev_theta is None:
            return super().maybe_resample()
        # The zoo's resampling step for step, with the wheel scale and the last heading carried
        # along with their particle (its own method cannot know of them).
        e = self.ess()
        self.ess_log.append(e)
        if e >= self.n / 2:
            return False
        w = self.weights()
        positions = (self.rng.random() + np.arange(self.n)) / self.n
        idx = np.minimum(np.searchsorted(np.cumsum(w), positions), self.n - 1)
        self.x, self.y, self.b, self.s = self.x[idx], self.y[idx], self.b[idx], self.s[idx]
        if self.prev_theta is not None:
            self.prev_theta = self.prev_theta[idx]
        self.logw = np.zeros(self.n)
        a = self.a
        h = math.sqrt(max(1.0 - a * a, 0.0))
        mean, sd = self.s.mean(axis=0), self.s.std(axis=0)
        self.s = np.clip(a * self.s + (1 - a) * mean + self.rng.normal(0.0, 1.0, self.s.shape) * h * sd,
                         self.lo, self.hi)
        bm, bs = self.b.mean(), self.b.std()
        self.b = a * self.b + (1 - a) * bm + self.rng.normal(0.0, h * bs, self.n)
        if self.g is not None:
            g = self.g[idx]
            self.g = np.clip(a * g + (1 - a) * g.mean() + self.rng.normal(0.0, h * g.std(), self.n),
                             -self.scale_error, self.scale_error)
        self.x = self.x + self.rng.normal(0.0, 0.01, self.n)
        self.y = self.y + self.rng.normal(0.0, 0.01, self.n)
        self.resamples += 1
        return True

    def moments(self):
        if self.g is None:
            return super().moments()
        # The planner knows slip only: hand it the slip that explains the ground really covered,
        # 1 - scale x (1 - slip), which is below zero when big wheels overshoot.
        w = self.weights()
        effective = 1.0 - (1.0 + self.g)[:, None] * (1.0 - self.s)
        state = np.column_stack([self.x, self.y, self.b, effective[:, 0], effective[:, 1]])
        mean = w @ state
        d = state - mean
        cov = (d * w[:, None]).T @ d + np.eye(5) * VAR_FLOOR
        return mean.tolist(), cov.tolist()


def crossing(beacons, ranges, start, size, sigma=None, per_m=0.0):
    """Least squares: the point whose distances to the beacons heard fit their readings best.

    With `sigma`, each ring counts by its published width, sigma + per_m x its reading."""
    x, y = start
    for _ in range(8):
        a11 = a12 = a22 = b1 = b2 = 0.0
        for (bx, by), reading in zip(beacons, ranges):
            if reading is None:
                continue
            dx, dy = x - bx, y - by
            distance = math.hypot(dx, dy) or 1e-6
            weight = 1.0 if sigma is None else 1.0 / (sigma + per_m * reading) ** 2
            jx, jy, miss = dx / distance, dy / distance, reading - distance
            a11, a12, a22 = a11 + weight * jx * jx, a12 + weight * jx * jy, a22 + weight * jy * jy
            b1, b2 = b1 + weight * jx * miss, b2 + weight * jy * miss
        det = a11 * a22 - a12 * a12
        if abs(det) < 1e-9:
            break
        x, y = x + (a22 * b1 - a12 * b2) / det, y + (a11 * b2 - a12 * b1) / det
    return [min(size[0], max(0.0, x)), min(size[1], max(0.0, y))]


def _executed_drive(controller, packet):
    """(commanded heading, wheel metres, clean) for the drive this packet reports, or None."""
    executed = [e["command_id"] for e in packet["events"] if e["type"] == "command_executed"]
    acks = {a["command_id"]: a for a in controller.acks}
    ack = acks.get(executed[0]) if executed else None
    kinds = {e["type"] for e in packet["events"]}
    if ack is not None and ack["command"]["action"] == "drive" and packet["wheel_odometry"] > 0:
        return ack["command"]["heading_deg"], packet["wheel_odometry"], not kinds & {"safety_stop", "battery_depleted"}
    return None


class _Navigator:
    """In front of a particle-filter controller: the position comes from the filter, which is fed
    whatever of the sensors in USE the packets carry. A position fix, when there is one, is one
    more sensor ("fix"), weighed by its published noise; so the same player runs with today's
    fix, with a very noisy one and with none.
    """
    USE = frozenset(SENSORS)
    N = 1000
    HOLD_FOR_FIXES = False   # without a fix, standing still at a target teaches almost nothing

    def absorb(self, packet):
        self._fix = packet["position"] if "fix" in self.USE else None
        # The bookkeeping below reads a position: give it the estimate, never a raw reading.
        packet = dict(packet, position=[self.filter.mean[0], self.filter.mean[1]])
        super().absorb(packet)
        self.packets[-1]["position"] = [self.filter.mean[0], self.filter.mean[1]]

    def _filter(self, packet):
        f = self.filter
        if not hasattr(self, "pf"):
            rules = self.tools.rules()
            self.nav = rules.get("navigation") or {}
            self.pf = NavParticleFilter(rules, self.packets[0]["position"], self.sand, f.rough_cells, f.cell_m,
                                        n=self.N, seed=7, slip_walk=self.SLIP_WALK, map_size=self.size)
            self.beacons = [(b["x"], b["y"]) for b in self.tools.map().get("beacons", [])]
            self.pf.gyro = "gyro" in self.USE and self.nav.get("gyro_noise_deg") is not None
            error = self.nav.get("wheel_scale_error", 0.0) if "scale" in self.USE else 0.0
            self.slip_floor = 0.0
            if error > 0:
                self.pf.learn_scale(error)
                self.wheel_scale = (1.0, error / math.sqrt(3.0))
                # The planner clips slip to the published ranges: widen them by what the scale can do.
                f.ranges = {t: (1.0 - (1.0 + error) * (1.0 - lo), 1.0 - (1.0 - error) * (1.0 - hi))
                            for t, (lo, hi) in f.ranges.items()}
                self.slip_floor = min(lo for lo, _ in f.ranges.values())
        pf, nav = self.pf, self.nav
        drive = _executed_drive(self, packet)
        if drive is not None:
            heading, wheel, clean = drive
            pf.predict(heading, wheel)
            if clean:
                pf.update_visual_odometry(packet["visual_odometry"])
            if "compass" in self.USE and packet.get("sun_heading_deg") is not None:
                pf.update_compass(packet["sun_heading_deg"], nav.get("sun_compass_noise_deg", 6.0))
            if "gyro" in self.USE and packet.get("gyro_turn_deg") is not None:
                pf.update_gyro(packet["gyro_turn_deg"], nav.get("gyro_noise_deg", 1.0))
        if getattr(self, "_fix", None) is not None and packet["tick"] > 0:
            pf.update_position(self._fix)
        if "range" in self.USE and packet["tick"] > 0:
            sigma, per_m = nav.get("beacon_range_noise_m", 0.25), nav.get("beacon_range_noise_per_m", 0.0)
            if packet.get("beacon_ranges_m") is not None:  # every beacon heard, each ring with its own width
                for beacon, reading in zip(self.beacons, packet["beacon_ranges_m"]):
                    if reading is not None:
                        pf.update_range(reading, beacon, sigma, per_m)
            elif packet.get("beacon_range_m") is not None:
                pf.update_range(packet["beacon_range_m"], self.base, sigma, per_m)
        if "terrain" in self.USE and packet["tick"] > 0:
            pf.update_terrain(packet["terrain"])
        self._event_updates(packet)
        pf.maybe_resample()
        f.mean, f.cov = pf.moments()
        for terrain in f.terrains:  # keep the planner's slip physical, as the zoo's filters do
            i = f.index[terrain]
            f.mean[i] = min(0.9, max(self.slip_floor, f.mean[i]))
        if pf.g is not None:
            w = pf.weights()
            mean = float(w @ pf.g)
            self.wheel_scale = (1.0 + mean, math.sqrt(max(float(w @ (pf.g - mean) ** 2), 0.0)))

    def _energy(self, bed, sand, slip_of):
        # The planner's wheel metres are the commanded ones; energy is spent on the metres the wheels
        # really turn, scale x as many. Budget the safe figure with the scale 1.5 sigma high as well.
        scale, sd = getattr(self, "wheel_scale", (1.0, 0.0))
        if slip_of == self.slip_safe:
            scale += 1.5 * sd
        return super()._energy(bed, sand, slip_of) * scale

    def _may_hold(self, key, deadline=None):
        if not self.HOLD_FOR_FIXES and getattr(self, "nav", None):
            return False
        return super()._may_hold(key, deadline)


def navigator(use=SENSORS, base=None, **knobs):
    """A fusing controller class: `base` (a particle-filter controller of the zoo) with the sensors in `use`."""
    base = base or zoo.PF_aimdisc_turncost_window_MPC
    return type("Navigator_" + ("_".join(sorted(use)) or "odometry"), (_Navigator, base), {"USE": frozenset(use), **knobs})


class DeadReckoningTools:
    """The five tools, with the missing position filled in by dead reckoning.

    Each executed drive moves the estimate by its visual-odometry distance along a heading:
    the commanded one (`heading="commanded"`), that drive's raw compass reading
    (`heading="compass"`), the commanded heading corrected by the average of every compass
    error seen so far (`heading="mean_compass"`), or the same average carried from drive to
    drive by the gyroscope's turns (`heading="gyro_compass"`, a complementary filter). With
    `snap_to_beacons`, a packet that hears three beacons or more moves the estimate to where
    their rings cross. What a player gets with a few lines of arithmetic and no filter.
    """

    def __init__(self, tools, heading="commanded", snap_to_beacons=False):
        self._tools, self._mode, self._snap = tools, heading, snap_to_beacons
        self._commands, self._filled, self._errors = {}, {}, []
        self._turned, self._previous, self._anchors = 0.0, None, []
        public = tools.map()
        self._size, self._estimate = (public["width"], public["height"]), list(public["base"])
        self._beacons = [(b["x"], b["y"]) for b in public.get("beacons", [])]


    def rules(self):
        # The position this player hands on is its own reckoning, not a noisy reading: no fix noise.
        rules = dict(self._tools.rules())
        if rules.get("sensing"):
            rules["sensing"] = {name: value for name, value in rules["sensing"].items() if name != "position_noise_m"}
        return rules

    def map(self):
        return self._tools.map()

    def uplink(self, commands):
        acks = self._tools.uplink(commands)
        for ack in acks:
            self._commands[ack["command_id"]] = ack["command"]
        return acks

    def _fill(self, packet):
        tick = packet["tick"]
        if tick == 0:  # the briefing is exact; any later fix is ignored: this player reckons
            self._estimate = list(packet["position"])
            return packet
        if tick not in self._filled:
            executed = [e["command_id"] for e in packet["events"] if e["type"] == "command_executed"]
            command = self._commands.get(executed[0]) if executed else None
            if command and command["action"] == "drive" and packet["wheel_odometry"] > 0:
                heading, compass = command["heading_deg"], packet.get("sun_heading_deg")
                if compass is not None:
                    self._errors.append((compass - heading + 180.0) % 360.0 - 180.0)
                if self._mode == "gyro_compass":
                    turn = packet.get("gyro_turn_deg")
                    if turn is not None and self._previous is not None:  # how far the heading error moved
                        self._turned += (turn - (heading - self._previous) + 180.0) % 360.0 - 180.0
                    self._previous = heading
                    if compass is not None:  # what this reading says the first drive's error was
                        self._anchors.append((compass - heading - self._turned + 180.0) % 360.0 - 180.0)
                    if self._anchors:
                        heading += sum(self._anchors) / len(self._anchors) + self._turned
                elif self._mode == "compass" and compass is not None:
                    heading = compass
                elif self._mode == "mean_compass" and self._errors:
                    heading += sum(self._errors) / len(self._errors)
                distance = packet["visual_odometry"]
                x = self._estimate[0] + distance * math.cos(math.radians(heading))
                y = self._estimate[1] + distance * math.sin(math.radians(heading))
                self._estimate = [min(self._size[0], max(0.0, x)), min(self._size[1], max(0.0, y))]
            ranges = packet.get("beacon_ranges_m") if self._snap else None
            if ranges is not None and sum(reading is not None for reading in ranges) >= 3:
                self._estimate = crossing(self._beacons, ranges, self._estimate, self._size)
            self._filled[tick] = list(self._estimate)
        return dict(packet, position=list(self._filled[tick]))

    def telemetry_log(self):
        return [self._fill(packet) for packet in self._tools.telemetry_log()]

    def advance(self, ticks=1):
        result = self._tools.advance(ticks)
        return dict(result, packets=[self._fill(packet) for packet in result["packets"]])


class CrossingFixTools:
    """The five tools, with the position fix replaced by the beacons' crossing whenever a packet
    hears three or more: least squares, each ring weighed by its published width. Any other packet
    keeps its own fix. What a player gets by turning the ranges into a fix and handing that to a
    standard filter, here the frozen reference's, which is told the fix noise the rules publish.
    """

    def __init__(self, tools):
        self._tools = tools
        public, nav = tools.map(), tools.rules().get("navigation") or {}
        self._size = (public["width"], public["height"])
        self._beacons = [(b["x"], b["y"]) for b in public.get("beacons", [])]
        self._sigma, self._per_m = nav.get("beacon_range_noise_m", 0.25), nav.get("beacon_range_noise_per_m", 0.0)
        self._last = list(public["base"])

    def rules(self):
        return self._tools.rules()

    def map(self):
        return self._tools.map()

    def uplink(self, commands):
        return self._tools.uplink(commands)

    def _fill(self, packet):
        ranges = packet.get("beacon_ranges_m")
        if packet["tick"] > 0 and ranges is not None and sum(reading is not None for reading in ranges) >= 3:
            start = packet["position"] or self._last
            packet = dict(packet, position=crossing(self._beacons, ranges, start, self._size, self._sigma, self._per_m))
        if packet["position"] is not None:
            self._last = list(packet["position"])
        return packet

    def telemetry_log(self):
        return [self._fill(packet) for packet in self._tools.telemetry_log()]

    def advance(self, ticks=1):
        result = self._tools.advance(ticks)
        return dict(result, packets=[self._fill(packet) for packet in result["packets"]])


def _run(cls):
    return lambda tools: cls(tools).run()


def players():
    out = {"fused": _run(navigator())}
    for sensor in SENSORS:
        out[f"fused_no_{sensor}"] = _run(navigator([s for s in SENSORS if s != sensor]))
    out["odometry_only"] = _run(navigator(()))
    out["fix_only"] = _run(navigator(["fix"]))                  # needs a fix in the packets
    out["kf_mpc_on_fix"] = POLICIES["kf_mpc"]                   # needs a fix
    out["trusts_fix"] = POLICIES["reference"]                   # needs a fix
    out["dr_commanded"] = lambda tools: POLICIES["kf_mpc"](DeadReckoningTools(tools, "commanded"))
    out["dr_compass"] = lambda tools: POLICIES["kf_mpc"](DeadReckoningTools(tools, "compass"))
    out["dr_mean_compass"] = lambda tools: POLICIES["kf_mpc"](DeadReckoningTools(tools, "mean_compass"))
    out["dr_gyro_compass"] = lambda tools: POLICIES["kf_mpc"](DeadReckoningTools(tools, "gyro_compass"))
    out["dr_beacons"] = lambda tools: POLICIES["kf_mpc"](DeadReckoningTools(tools, "gyro_compass", True))
    out["kf_mpc_on_crossings"] = lambda tools: POLICIES["kf_mpc"](CrossingFixTools(tools))   # needs a fix
    out["blind"] = POLICIES["open_loop"]
    return out


NEED_A_FIX = ("fused_no_fix", "fix_only", "kf_mpc_on_fix", "trusts_fix", "kf_mpc_on_crossings")
NEED = {"fused_no_gyro": "gyro_noise_deg", "dr_gyro_compass": "gyro_noise_deg",
        "fused_no_scale": "wheel_scale_error", "dr_beacons": "beacons", "kf_mpc_on_crossings": "beacons"}


def default_players(has_fix, navigation=None):
    """Every player that makes sense: the ones that read a sensor only when the packets carry it."""
    navigation = navigation or {}
    has = {"gyro_noise_deg": navigation.get("gyro_noise_deg") is not None,
           "wheel_scale_error": navigation.get("wheel_scale_error", 0.0) > 0,
           "beacons": navigation.get("beacons", 1) > 1}
    return [name for name in players() if (has_fix or name not in NEED_A_FIX) and has.get(NEED.get(name), True)]


def play(job):
    """One episode; (player, profile, delay, seed, share, home, dead, crash)."""
    from lightlag_dynamic.tools import PublicTools

    from .nogps import make_nogps_env
    name, profile, delay, seed, biome, navigation = job
    env = make_nogps_env(seed, delay, profile, biome=biome, navigation=navigation or None)
    crash = None
    try:
        players()[name](PublicTools(env))
    except Exception as error:  # a player's error is a result, not a harness failure
        crash = f"{type(error).__name__}: {error}"[:160]
    while not env.advance(5)["episode_complete"]:
        pass
    result = env.evaluate()
    return {"player": name, "profile": profile, "delay": delay, "seed": seed,
            "share": result["raw_score"] / result["max_available_value"] if result["max_available_value"] else 0.0,
            "home": bool(result["alive"] and result["at_base"]), "dead": not result["alive"], "crash": crash}


def probe(names, profiles, delays, seeds, workers, biome="main_mars", navigation=None):
    jobs = [(n, p, d, s, biome, navigation) for n in names for p in profiles for d in delays for s in seeds]
    if workers > 1:
        with Pool(workers) as pool:
            return pool.map(play, jobs, chunksize=2)
    return [play(job) for job in jobs]


def table(rows):
    lines = []
    cells = sorted({(r["profile"], r["delay"]) for r in rows})
    names = list(dict.fromkeys(r["player"] for r in rows))
    lines.append("| Player | " + " | ".join(f"{p}, delay {d}" for p, d in cells) + " |")
    lines.append("|---|" + "---|" * len(cells))
    for name in names:
        out = []
        for profile, delay in cells:
            g = [r for r in rows if r["player"] == name and r["profile"] == profile and r["delay"] == delay]
            crashes = sum(bool(r["crash"]) for r in g)
            out.append(f"{st.mean(r['share'] for r in g):.0%}, home {sum(r['home'] for r in g) / len(g):.0%}"
                       + (f", dead {sum(r['dead'] for r in g) / len(g):.0%}" if any(r["dead"] for r in g) else "")
                       + (f", {crashes} errors" if crashes else ""))
        lines.append(f"| `{name}` | " + " | ".join(out) + " |")
    return "\n".join(lines)


def main(argv=None):
    from lightlag_dynamic.manh_controllers.swarm import parse_seeds
    ap = argparse.ArgumentParser(prog="python3 -m lightlag_dynamic.biomes.nogps_players", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--players", nargs="*")
    ap.add_argument("--weak-gps", action="store_true",
                    help="the weak-sensor setting: a 2 m position fix and a 12 degree compass (nogps.WEAK_GPS)")
    ap.add_argument("--gps-noise", type=float, default=None,
                    help="keep a position fix with this much noise per axis, in metres (default: no fix)")
    ap.add_argument("--compass-noise", type=float, default=None, help="the sun compass noise in degrees (default 6)")
    ap.add_argument("--many-sensors", action="store_true",
                    help="many weak sensors: the weak fix, four vague beacons, a gyroscope, coarse visual odometry "
                         "and wheels of a hidden size (nogps.MANY_SENSORS)")
    ap.add_argument("--set", action="append", default=[], metavar="NAME=VALUE",
                    help="any single navigation setting of nogps.py, e.g. beacons=6 or gyro_noise_deg=none")
    ap.add_argument("--profiles", nargs="*", default=["rush_noisy"])
    ap.add_argument("--delays", nargs="*", type=int, default=[3])
    ap.add_argument("--seeds", default="0-19")
    ap.add_argument("--biome", default="main_mars")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    a = ap.parse_args(argv)
    from .nogps import MANY_SENSORS, WEAK_GPS
    navigation = dict(MANY_SENSORS) if a.many_sensors else dict(WEAK_GPS) if a.weak_gps else {}
    if a.gps_noise is not None:
        navigation["position_noise_m"] = a.gps_noise
    if a.compass_noise is not None:
        navigation["sun_compass_noise_deg"] = a.compass_noise
    for item in a.set:
        name, _, value = item.partition("=")
        navigation[name] = None if value.lower() == "none" else int(value) if name == "beacons" else float(value)
    names = a.players or default_players(navigation.get("position_noise_m") is not None, navigation)
    unknown = set(names) - set(players())
    if unknown:
        ap.error(f"unknown players: {sorted(unknown)}; choose from {', '.join(players())}")
    rows = probe(names, a.profiles, a.delays, parse_seeds(a.seeds), a.workers, a.biome, navigation)
    print(table(rows))
    for row in rows:
        if row["crash"]:
            print("error:", row["player"], row["profile"], row["delay"], row["seed"], row["crash"])
            break


if __name__ == "__main__":
    main()
