"""Players for the no-GPS option, and a probe that compares them (needs numpy).

    python3 -m lightlag_dynamic.biomes.nogps_players --seeds 0-19            # every player
    python3 -m lightlag_dynamic.biomes.nogps_players --players fused blind --delays 0 3 5

The fusing reference (`fused`) is the Manh controllers' particle-filter controller with three
more likelihoods, one per sensor the position fix was replaced by:

    beacon range    a ring around the base: weight each particle by how well its distance fits
    sun compass     the heading of the drive just made: weight each particle's own heading
    terrain         the terrain under the rover against the published map (map matching)

A range is a ring and a terrain reading is a region, neither of which a Kalman filter's
Gaussian can hold; a particle filter weighs them as they are. Sample results stay as in the
zoo's filter: a sample taken puts the rover inside that target's radius, a miss outside.
The planner is unchanged: it plans on the filter's mean and covariance.

The other players are what a player without that filter might do:

    fused_no_<sensor>   the reference with one sensor ignored (what each sensor is worth)
    odometry_only       the reference with all three ignored: wheels, cameras and sample results
    dr_commanded        the frozen reference, kf_mpc, fed a position dead-reckoned from the
                        commanded headings and visual odometry
    dr_compass          kf_mpc fed a position dead-reckoned from each raw compass reading
    dr_mean_compass     kf_mpc fed a position dead-reckoned from the commanded heading plus the
                        average compass error so far: the simplest fusion there is
    blind               plans once from the briefing and never reads telemetry

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
from lightlag_dynamic.manh_controllers.estimators import ParticleFilter

SENSORS = ("range", "compass", "terrain")


class NavParticleFilter(ParticleFilter):
    """The zoo's particle filter plus the beacon range, the sun compass and the terrain reading."""

    def predict(self, heading_deg, wheel):
        x0, y0 = self.x.copy(), self.y.copy()
        super().predict(heading_deg, wheel)
        moved = self.last_ground > 1e-6
        # The heading each particle really drove: its own bias and noise draw, read off its path.
        self.last_theta = np.where(moved, np.arctan2(self.y - y0, self.x - x0), math.radians(heading_deg) + self.b)

    def update_compass(self, measured_deg, sigma_deg):
        if getattr(self, "last_theta", None) is None:
            return
        off = math.radians(measured_deg) - self.last_theta
        off = (off + math.pi) % (2 * math.pi) - math.pi
        self.logw += -0.5 * (off / math.radians(max(sigma_deg, 0.1))) ** 2
        self._normalise()

    def update_range(self, measured, point, sigma):
        distance = np.hypot(self.x - point[0], self.y - point[1])
        self.logw += -0.5 * ((measured - distance) / max(sigma, 0.02)) ** 2
        self._normalise()

    def update_terrain(self, reported, miss=0.05):
        on_sand = self._terrain(self.x, self.y) == 1
        fits = on_sand if reported == "sand" else ~on_sand
        self.logw += np.where(fits, math.log(1.0 - miss), math.log(miss))
        self._normalise()


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
    """In front of a particle-filter controller: no position fix, the three sensors instead.

    With a position in the packet (any environment but the no-GPS one) the fix is used as well,
    so the same player runs everywhere.
    """
    USE = frozenset(SENSORS)
    N = 1000
    HOLD_FOR_FIXES = False   # without a fix, standing still at a target teaches almost nothing

    def absorb(self, packet):
        self._has_fix = packet.get("position") is not None
        if not self._has_fix:  # the bookkeeping below reads a position: give it the estimate
            packet = dict(packet, position=[self.filter.mean[0], self.filter.mean[1]])
        super().absorb(packet)
        if not self._has_fix:
            self.packets[-1]["position"] = [self.filter.mean[0], self.filter.mean[1]]

    def _filter(self, packet):
        f = self.filter
        if not hasattr(self, "pf"):
            rules = self.tools.rules()
            self.nav = rules.get("navigation") or {}
            self.pf = NavParticleFilter(rules, self.packets[0]["position"], self.sand, f.rough_cells, f.cell_m,
                                        n=self.N, seed=7, slip_walk=self.SLIP_WALK, map_size=self.size)
        pf, nav = self.pf, self.nav
        drive = _executed_drive(self, packet)
        if drive is not None:
            heading, wheel, clean = drive
            pf.predict(heading, wheel)
            if clean:
                pf.update_visual_odometry(packet["visual_odometry"])
            if "compass" in self.USE and packet.get("sun_heading_deg") is not None:
                pf.update_compass(packet["sun_heading_deg"], nav.get("sun_compass_noise_deg", 6.0))
        if getattr(self, "_has_fix", packet.get("position") is not None) and packet["tick"] > 0:
            pf.update_position(packet["position"])
        if "range" in self.USE and packet.get("beacon_range_m") is not None and packet["tick"] > 0:
            pf.update_range(packet["beacon_range_m"], self.base, nav.get("beacon_range_noise_m", 0.25))
        if "terrain" in self.USE and packet["tick"] > 0:
            pf.update_terrain(packet["terrain"])
        self._event_updates(packet)
        pf.maybe_resample()
        f.mean, f.cov = pf.moments()
        for terrain in f.terrains:  # keep the planner's slip physical, as the zoo's filters do
            i = f.index[terrain]
            f.mean[i] = min(0.9, max(0.0, f.mean[i]))

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
    (`heading="compass"`), or the commanded heading corrected by the average of every compass
    error seen so far (`heading="mean_compass"`). What a player gets by integrating its own
    drives with a few lines of arithmetic and no filter.
    """

    def __init__(self, tools, heading="commanded"):
        self._tools, self._mode = tools, heading
        self._commands, self._filled, self._errors = {}, {}, []
        public = tools.map()
        self._size, self._estimate = (public["width"], public["height"]), list(public["base"])

    def rules(self):
        return self._tools.rules()

    def map(self):
        return self._tools.map()

    def uplink(self, commands):
        acks = self._tools.uplink(commands)
        for ack in acks:
            self._commands[ack["command_id"]] = ack["command"]
        return acks

    def _fill(self, packet):
        if packet.get("position") is not None:
            self._estimate = list(packet["position"])
            return packet
        tick = packet["tick"]
        if tick not in self._filled:
            executed = [e["command_id"] for e in packet["events"] if e["type"] == "command_executed"]
            command = self._commands.get(executed[0]) if executed else None
            if command and command["action"] == "drive" and packet["wheel_odometry"] > 0:
                heading, compass = command["heading_deg"], packet.get("sun_heading_deg")
                if compass is not None:
                    self._errors.append((compass - heading + 180.0) % 360.0 - 180.0)
                if self._mode == "compass" and compass is not None:
                    heading = compass
                elif self._mode == "mean_compass" and self._errors:
                    heading += sum(self._errors) / len(self._errors)
                distance = packet["visual_odometry"]
                x = self._estimate[0] + distance * math.cos(math.radians(heading))
                y = self._estimate[1] + distance * math.sin(math.radians(heading))
                self._estimate = [min(self._size[0], max(0.0, x)), min(self._size[1], max(0.0, y))]
            self._filled[tick] = list(self._estimate)
        return dict(packet, position=list(self._filled[tick]))

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
    out["dr_commanded"] = lambda tools: POLICIES["kf_mpc"](DeadReckoningTools(tools, "commanded"))
    out["dr_compass"] = lambda tools: POLICIES["kf_mpc"](DeadReckoningTools(tools, "compass"))
    out["dr_mean_compass"] = lambda tools: POLICIES["kf_mpc"](DeadReckoningTools(tools, "mean_compass"))
    out["blind"] = POLICIES["open_loop"]
    return out


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
    ap.add_argument("--players", nargs="*", default=list(players()))
    ap.add_argument("--profiles", nargs="*", default=["rush_noisy"])
    ap.add_argument("--delays", nargs="*", type=int, default=[3])
    ap.add_argument("--seeds", default="0-19")
    ap.add_argument("--biome", default="main_mars")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    a = ap.parse_args(argv)
    unknown = set(a.players) - set(players())
    if unknown:
        ap.error(f"unknown players: {sorted(unknown)}; choose from {', '.join(players())}")
    rows = probe(a.players, a.profiles, a.delays, parse_seeds(a.seeds), a.workers, a.biome)
    print(table(rows))
    for row in rows:
        if row["crash"]:
            print("error:", row["player"], row["profile"], row["delay"], row["seed"], row["crash"])
            break


if __name__ == "__main__":
    main()
