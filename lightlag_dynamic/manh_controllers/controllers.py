"""Manh controllers: every meaningful controller combination Manh has tried, under one registry.

Naming: <METHODS>_manh_controller_<N>, methods joined by underscores in the order they act
(estimator, additions, planner), N in the order they were built. A number is never reused;
retired numbers are listed in RETIRED with the reason. Parameter variants of an existing
controller (same model, different values) do not get a new number.

Every Manh controller reuses the planner in lightlag_dynamic/kf_mpc.py (receding horizon over
target sequences with chance constraints) and swaps what feeds it or how it budgets a leg, so
differences come from estimation and decision rules, not from a different route search.

Every entry records what it is (note), why it was built and what it showed (why), and when
(built), so the history can be traced; README.md has the same log as a table.

Kinds:
  "manh"   a real controller: public tools only
  "bound"  privileged information (true parameters, exact telemetry, no delay); a yardstick,
           never an entry. Needs a ScenarioEnvironment, which exposes the truth.
  "team"   a teammate's controller, imported unchanged under its own name

Needs numpy (particle filter, cubature filter, smoother, logger).
"""

import copy
import math

import numpy as np

import lightlag_dynamic.controllers as _lc
from lightlag_dynamic.controllers import HAZARD_CLEARANCE, Leg, _clip_interval
from lightlag_dynamic.kf_mpc import GATE, VAR_FLOOR, DriveFilter, KalmanMPCController

from .estimators import ParticleFilter, cubature_drive, rts_smooth


class Current:
    """Per-process hook for the super logger (one episode at a time per worker)."""
    logger = None


class LogMixin:
    def _filter(self, packet):
        super()._filter(packet)
        if Current.logger is not None:
            Current.logger.estimate(self, packet)

    def decide(self):
        log = Current.logger
        before = len(self.acks)
        pre = log.pre_decide(self) if log is not None else None
        super().decide()
        if log is not None:
            log.post_decide(self, pre, self.acks[before:])


def _executed_drive(ctrl, packet):
    """(heading, wheel metres, clean) for the drive this packet reports, or None."""
    executed = [e["command_id"] for e in packet["events"] if e["type"] == "command_executed"]
    acks = {a["command_id"]: a for a in ctrl.acks}
    ack = acks.get(executed[0]) if executed else None
    kinds = {e["type"] for e in packet["events"]}
    if ack is not None and ack["command"]["action"] == "drive" and packet["wheel_odometry"] > 0:
        return ack["command"]["heading_deg"], packet["wheel_odometry"], not kinds & {"safety_stop", "battery_depleted"}
    return None


def _failed_points(ctrl, packet):
    """Unsampled targets, if this packet reports a sample that found none in range."""
    if any(e["type"] == "sample_failed" and e.get("reason") == "no_unsampled_target_in_range"
           for e in packet["events"]):
        sampled = set(packet["sampled_targets"])
        return [t for tid, t in ctrl.targets.items() if tid not in sampled]
    return []


# =============================================================================================
# Estimators
# =============================================================================================

class EKF_MPC(LogMixin, KalmanMPCController):
    """1: the repo's kf_mpc. EKF over position, heading bias and slip; delay compensation;
    failed samples as an outside-the-radius update; MPC with chance constraints."""


class PF_MPC(LogMixin, KalmanMPCController):
    """2: bootstrap particle filter (SIR, systematic resampling, Liu-West) feeding the planner
    its mean and covariance. Exact priors, slip clipping, multimodal wheel spins, failed and
    taken samples as exact outside/inside likelihoods."""
    N = 500
    SLIP_WALK = 0.0

    def _event_updates(self, packet):
        pf = self.pf
        sampled = set(packet["sampled_targets"])
        for e in packet["events"]:
            if e["type"] == "sample_failed" and e.get("reason") == "no_unsampled_target_in_range":
                pts = [(t["x"], t["y"]) for tid, t in self.targets.items() if tid not in sampled]
                pf.update_outside(pts, self.radius)
            elif e["type"] == "sample_taken" and e.get("target_id") in self.targets:
                t = self.targets[e["target_id"]]
                pf.update_inside((t["x"], t["y"]), self.radius)

    def _filter(self, packet):  # replaces the EKF update; logs itself
        f = self.filter
        if not hasattr(self, "pf"):
            self.pf = ParticleFilter(self.tools.rules(), self.packets[0]["position"], self.sand,
                                     f.rough_cells, f.cell_m, n=self.N, seed=7,
                                     slip_walk=self.SLIP_WALK, map_size=self.size)
        pf = self.pf
        drive = _executed_drive(self, packet)
        if drive is not None:
            heading, wheel, clean = drive
            pf.predict(heading, wheel)
            if clean:
                pf.update_visual_odometry(packet["visual_odometry"])
        pf.update_position(packet["position"])
        self._event_updates(packet)
        pf.maybe_resample()
        f.mean, f.cov = pf.moments()
        for t in f.terrains:  # keep the planner's slip physical, like the EKF does
            i = f.index[t]
            f.mean[i] = min(0.9, max(0.0, f.mean[i]))
        if Current.logger is not None:
            Current.logger.estimate(self, packet)


class CKF_MPC(LogMixin, KalmanMPCController):
    """8: cubature Kalman filter: sigma points pushed through the drive kinematics (heading
    bias step, heading noise and slip noise augmented), so no Jacobian is needed."""

    def _filter(self, packet):  # replaces the EKF drive step; logs itself
        f = self.filter
        drive = _executed_drive(self, packet)
        if drive is not None:
            heading, wheel, clean = drive
            m, P, g, Pxg, Pgg = cubature_drive(f, f.mean, f.cov, heading, wheel, self.terrain_at, self.sand)
            f.mean, f.cov = m, P
            if clean:
                v = packet["visual_odometry"]
                r = (f.vo_rel * max(v, 0.05)) ** 2 + VAR_FLOOR
                s = Pgg + r
                if (v - g) ** 2 <= GATE * s:
                    K = np.asarray(Pxg) / s
                    mean = np.asarray(f.mean) + K * (v - g)
                    cov = np.asarray(f.cov) - np.outer(K, K) * s
                    f.mean, f.cov = mean.tolist(), ((cov + cov.T) / 2).tolist()
                    for t in f.terrains:
                        i = f.index[t]
                        f.mean[i] = min(0.9, max(0.0, f.mean[i]))
        f.update_position(packet["position"])
        failed = _failed_points(self, packet)
        if failed:
            nearest = min(failed, key=lambda t: math.hypot(t["x"] - f.mean[0], t["y"] - f.mean[1]))
            f.update_outside((nearest["x"], nearest["y"]), self.radius)
        if Current.logger is not None:
            Current.logger.estimate(self, packet)


class PF_forgetting_MPC(PF_MPC):
    """10: particle filter whose slips random-walk, so it can follow a slip that changes."""
    SLIP_WALK = 0.01


class EKF_forgetting_MPC(EKF_MPC):
    """11: controller 1 with process noise on slip (forgetting), for slip that changes."""
    Q_SLIP = 0.015 ** 2  # per executed drive

    def _filter(self, packet):
        if _executed_drive(self, packet) is not None:
            f = self.filter
            for t in f.terrains:
                i = f.index[t]
                f.cov[i][i] += self.Q_SLIP
        super()._filter(packet)


class EKF_IEKS_MPC(LogMixin, KalmanMPCController):
    """12: iterated extended Kalman smoother. Each new drive: RTS-smooth the history, then re-run
    the EKF with every past drive linearised at its smoothed state (one Gauss-Newton step per
    drive, accumulating). The present estimate is the re-run's last filtered state: smoothing
    improves the linearisation points, not the present directly (SSY345 L6 + L7)."""

    def _base_step(self, f, entry):
        steps = {}
        m0, P0 = list(f.mean), [r[:] for r in f.cov]
        if entry["drive"] is not None:
            heading, wheel, clean = entry["drive"]
            lin = entry.get("lin")
            if lin is None:
                new, P, by = DriveFilter.propagate(f, f.mean, f.cov, heading, wheel, self.terrain_at)
                F = self._jac(f, f.mean, new, by, heading)
            else:
                new_lin, P, by = DriveFilter.propagate(f, lin, f.cov, heading, wheel, self.terrain_at)
                F = self._jac(f, lin, new_lin, by, heading)
                new = (np.asarray(new_lin) + F @ (np.asarray(f.mean) - np.asarray(lin))).tolist()
            steps.update(F=F.tolist(), m_pred=list(new), P_pred=[r[:] for r in P])
            f.mean, f.cov = new, P
            if clean:
                f.update_visual_odometry(entry["vo"], by)
        else:
            steps.update(F=np.eye(len(m0)).tolist(), m_pred=m0, P_pred=P0)
        f.update_position(entry["fix"])
        for point in entry["outside"]:
            f.update_outside(point, self.radius)
        steps.update(m=list(f.mean), P=[r[:] for r in f.cov])
        return steps

    @staticmethod
    def _jac(f, mean, new, by, heading):
        theta = math.radians(heading) + mean[2]
        ux, uy = math.cos(theta), math.sin(theta)
        ground = math.hypot(new[0] - mean[0], new[1] - mean[1])
        F = np.eye(len(mean))
        F[0][2], F[1][2] = -ground * uy, ground * ux
        for t in f.terrains:
            i = f.index[t]
            F[0][i], F[1][i] = -by[t] * ux, -by[t] * uy
        return F

    def _filter(self, packet):  # replaces the EKF update; logs itself
        f = self.filter
        if not hasattr(self, "history"):
            self.history, self.prior, self.steps = [], (list(f.mean), [r[:] for r in f.cov]), []
        drive = _executed_drive(self, packet)
        entry = {"drive": drive, "vo": packet["visual_odometry"], "fix": packet["position"], "outside": []}
        failed = _failed_points(self, packet)
        if failed:  # the failed-sample point is chosen once, from the estimate when the packet arrived
            nearest = min(failed, key=lambda t: math.hypot(t["x"] - f.mean[0], t["y"] - f.mean[1]))
            entry["outside"] = [(nearest["x"], nearest["y"])]
        self.history.append(entry)
        self.steps.append(self._base_step(f, entry))
        if drive is not None and len(self.steps) > 2:
            first = {"m": self.prior[0], "P": self.prior[1], "F": np.eye(len(f.mean)).tolist(),
                     "m_pred": self.prior[0], "P_pred": self.prior[1]}
            smooth = rts_smooth([first] + self.steps)
            for k, e in enumerate(self.history):
                e["lin"] = smooth[k][0] if e["drive"] is not None else None
            g = copy.copy(f)
            g.mean, g.cov = list(self.prior[0]), [r[:] for r in self.prior[1]]
            self.steps = [self._base_step(g, e) for e in self.history]
            f.mean, f.cov = g.mean, g.cov
        if Current.logger is not None:
            Current.logger.estimate(self, packet)


class _TerrainVOFilter(DriveFilter):
    vo_by = None

    def update_visual_odometry(self, measured, by_terrain):
        if not self.vo_by:
            return DriveFilter.update_visual_odometry(self, measured, by_terrain)
        total = sum(by_terrain.values()) or 1.0
        saved = self.vo_rel
        self.vo_rel = sum(self.vo_by[t] * w for t, w in by_terrain.items()) / total
        try:
            return DriveFilter.update_visual_odometry(self, measured, by_terrain)
        finally:
            self.vo_rel = saved


class EKF_terrainVO_MPC(EKF_MPC):
    """15: controller 1 using published per-terrain odometry noise, weighted by metres driven."""

    def __init__(self, tools):
        super().__init__(tools)
        self.filter.__class__ = _TerrainVOFilter
        self.filter.vo_by = (tools.rules().get("sensing") or {}).get("visual_odometry_noise_by_terrain")


# =============================================================================================
# Planner and decision additions (mixins; put them before the estimator class)
# =============================================================================================

class _WindowAware:
    """Decides only inside an uplink window (freshest telemetry) and predicts to the real slot.
    Inactive when the rules publish no windows."""

    def _windows(self):
        if not hasattr(self, "_win"):
            w = self.tools.rules().get("uplink_windows")
            self._win = (w["period_ticks"], w["open_ticks"]) if w else None
        return self._win

    def next_slot(self):
        w = self._windows()
        send = self.tick
        if w and send % w[0] >= w[1]:
            send = (send // w[0] + 1) * w[0]
        return max(send + self.k + 1, self.reserved_until() + 1)

    def decide(self):
        w = self._windows()
        if w and self.tick % w[0] >= w[1]:
            return
        super().decide()


class _TurnCost:
    """Budgets the published energy per degree of heading change into every leg.
    Inactive when the rules publish no turn cost."""

    def leg(self, start, goal):
        hop = super().leg(start, goal)
        if not hasattr(self, "_tc"):
            self._tc = self.tools.rules().get("turn_cost_per_degree")
        cost = self._tc
        if hop is None or not cost:
            return hop
        headings = [c["heading_deg"] for c in hop.commands]
        turns = 90.0 + sum(abs((b - a + 180.0) % 360.0 - 180.0) for a, b in zip(headings, headings[1:]))
        extra = cost * turns * self.drive_cost
        return Leg(hop.commands, hop.energy + extra, hop.energy_safe + 1.5 * extra, hop.uncertainty)


class _SandOdometer:
    """Reads unmapped sand off the battery. Battery telemetry has no noise, and a drive costs
    drive_cost x terrain multiplier per wheel metre, so between two consecutive packets

        sand wheel metres = (battery drop - idle - turn energy) / drive_cost - wheel metres
                            (with multipliers 1 and 2; the general form divides by their difference)

    exactly. Where that is more than the published map predicts along the drive, the controller
    adds the unmapped stretch to its own copy of the sand map, so every later leg and the way home
    are routed and budgeted with it. Where the stretch lies along the drive comes from the packet's
    terrain field (true terrain under the rover at each end); if both ends are bedrock it is placed
    mid-drive, which gives the same cost to a return along the same line. Inactive while the map
    is right."""
    SAND_TOL = 0.2  # wheel metres of disagreement treated as unmapped sand (exact reading: ~1e-6)
    PAD = 0.25      # metres around a marked stretch, for the offset of a later crossing

    def _filter(self, packet):
        f = self.filter
        start = (f.mean[0], f.mean[1])
        super()._filter(packet)
        try:
            self._read_sand(packet, start, (f.mean[0], f.mean[1]))
        except (KeyError, IndexError, ZeroDivisionError):
            pass  # a packet this reading cannot use

    def _read_sand(self, packet, start, end):
        if len(self.packets) < 2 or self.packets[-1] is not packet:
            return
        prev = self.packets[-2]
        drive = _executed_drive(self, packet)
        if drive is None or not drive[2] or packet["tick"] != prev["tick"] + 1 or not packet["alive"]:
            return
        heading, wheel, _ = drive
        mult = self.multiplier
        energy = prev["battery"] - packet["battery"] - self.idle
        if not hasattr(self, "_turn_cost"):
            self._turn_cost = self.tools.rules().get("turn_cost_per_degree") or 0.0
        if self._turn_cost and prev.get("heading_deg") is not None:
            turn = abs((heading - prev["heading_deg"] + 180.0) % 360.0 - 180.0)
            energy -= self._turn_cost * turn * self.drive_cost * mult.get(prev.get("terrain"), 1.0)
        sand_wheel = (energy / self.drive_cost - mult["bedrock"] * wheel) / (mult["sand"] - mult["bedrock"])
        _, bed, sand = self._segment(start, end)
        self.driven = getattr(self, "driven", []) + [(start, end)]  # ground this rover has checked
        self.bedrock_driven = getattr(self, "bedrock_driven", 0.0) + bed
        s_bed, s_sand = self.slip("bedrock"), self.slip("sand")
        mapped_wheel = bed / (1 - s_bed) + sand / (1 - s_sand)
        expected = wheel * (sand / (1 - s_sand)) / mapped_wheel if mapped_wheel > 1e-9 else 0.0
        excess = sand_wheel - expected
        if excess <= self.SAND_TOL:
            return
        length = min(math.dist(start, end), excess * (1 - s_sand))
        d = math.dist(start, end)
        if d < 1e-6:
            return
        ux, uy = (end[0] - start[0]) / d, (end[1] - start[1]) / d
        at_end = packet.get("terrain") == "sand" and self.terrain_at(*end) == "bedrock"
        at_start = prev.get("terrain") == "sand" and self.terrain_at(*start) == "bedrock"
        if at_end and not at_start:
            a = d - length
        elif at_start and not at_end:
            a = 0.0
        else:
            a = (d - length) / 2
        p = (start[0] + ux * a, start[1] + uy * a)
        q = (start[0] + ux * (a + length), start[1] + uy * (a + length))
        self.unmapped_found = getattr(self, "unmapped_found", 0.0) + length
        self._mark_sand(p, q)

    def _mark_sand(self, p, q):
        pad = self.PAD
        rect = {"x1": min(p[0], q[0]) - pad, "y1": min(p[1], q[1]) - pad,
                "x2": max(p[0], q[0]) + pad, "y2": max(p[1], q[1]) + pad}
        if not hasattr(self, "found_sand"):
            self.sand = [dict(r) for r in self.sand]  # own copy: never touch the published map
            self.found_sand = []
        self.sand.append(rect)
        self.found_sand.append(rect)
        w, h = self.size
        for x in (rect["x1"] - 0.05, rect["x2"] + 0.05):
            for y in (rect["y1"] - 0.05, rect["y2"] + 0.05):
                if 0.3 <= x <= w - 0.3 and 0.3 <= y <= h - 0.3 and not any(
                        _clip_interval((x, y), (x, y), r, HAZARD_CLEARANCE) for r in self.hazards):
                    self.corners.append((x, y))
        self._segments.clear()


def _point_segment_distance(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = dx * dx + dy * dy
    t = 0.0 if n < 1e-12 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / n))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


class _MapDoubt:
    """Once the battery has shown the map to be wrong (needs _SandOdometer), the home budget doubts
    the ground the rover has not driven: a share rho of every unverified bedrock metre is budgeted
    as sand, rho being the unmapped share seen so far,

        rho = unmapped sand found / max(bedrock driven, 5 m), at most 0.5.

    Unverified = more than VERIFIED metres from any drive so far, sampled every STEP metres along the
    straight line of the leg. Inactive while the map is right, so clean maps are unchanged. Only the
    safe energy changes, which the planner uses for the way home."""
    VERIFIED = 0.5
    STEP = 0.25
    MIN_DRIVEN = 5.0
    MAX_RHO = 0.5

    def leg(self, start, goal):
        hop = super().leg(start, goal)
        found = getattr(self, "unmapped_found", 0.0)
        if hop is None or found <= 0.0:
            return hop
        rho = min(self.MAX_RHO, found / max(getattr(self, "bedrock_driven", 0.0), self.MIN_DRIVEN))
        d = math.dist(start, goal)
        steps = int(d / self.STEP)
        driven = getattr(self, "driven", [])
        unverified = 0.0
        for i in range(steps):
            t = (i + 0.5) / max(steps, 1)
            pt = (start[0] + (goal[0] - start[0]) * t, start[1] + (goal[1] - start[1]) * t)
            if self.terrain_at(*pt) != "bedrock":
                continue
            if all(_point_segment_distance(pt, a, b) > self.VERIFIED for a, b in driven):
                unverified += d / max(steps, 1)
        if unverified <= 0.0:
            return hop
        m = self.multiplier
        per_metre = self.drive_cost * (m["sand"] / (1 - self.slip_safe("sand")) - m["bedrock"] / (1 - self.slip("bedrock")))
        return Leg(hop.commands, hop.energy, hop.energy_safe + rho * unverified * per_metre, hop.uncertainty)


class _StayAlive:
    """Never sends a batch expected to empty the battery before the horizon. Dead scores 0 while
    alive away from base scores half, so a command is only worth sending when, with expected
    slip, energy remains for every idle tick after it (SSY345 L2: decide on the outcome). If
    staying put cannot survive either, nothing is lost by trying."""

    def send(self, commands):
        if commands and not self._survives(commands):
            return False
        return super().send(commands)

    def _survives(self, commands):
        slot = self.next_slot()
        if slot > self.horizon:
            return True
        state = self.predict(slot)
        if not state["alive"] or state["battery"] - self.idle * (self.horizon - slot + 1) <= 0:
            return True  # lost either way
        sim = {"x": state["x"], "y": state["y"], "battery": state["battery"]}
        batch = commands[:max(0, self.horizon - slot + 1)]
        for c in batch:
            sim["battery"] -= self.idle
            if c["action"] == "drive":
                self._simulate_drive(sim, c)
            elif c["action"] == "sample":
                sim["battery"] -= self.sample_cost
        sim["battery"] -= self.idle * (self.horizon - (slot + len(batch) - 1))
        return sim["battery"] > 0


class _AimDisc:
    """Legs end short of the centre by what the landing uncertainty allows: a sample only needs
    the rover within the radius. Saves about 0.5 m per leg; the end-inside chance accounts for the
    offset (sigma inflated by r / (r - offset)). Found by the exact oracle (see bound 16)."""
    AIM = 0.3        # keep at least this far inside the radius
    SIGMAS = 1.5     # and this many landing standard deviations

    def leg(self, start, goal):
        hop = super().leg(start, goal)
        if hop is None or not hop.commands:
            return hop
        radius = self.base_radius if tuple(goal) == tuple(self.base) else self.radius
        d = math.dist(start, goal)
        offset = min(radius - self.AIM - self.SIGMAS * hop.uncertainty, d - 0.05)
        if offset <= 0.05:
            return hop
        ux, uy = (goal[0] - start[0]) / d, (goal[1] - start[1]) / d
        short = super().leg(start, (goal[0] - ux * offset, goal[1] - uy * offset))
        if short is None or not short.commands:
            return hop
        sigma = short.uncertainty * radius / max(radius - offset, 1e-3)
        return Leg(short.commands, short.energy, short.energy_safe, sigma)


class _Tight:
    """Energy reserve 0.5 instead of 2.0: enough for the +/-0.02 per-drive slip noise when the
    parameters are known. Only the bounds use it."""
    RESERVE = 0.5

    def choose(self, state, slot):
        saved = _lc.RESERVE
        _lc.RESERVE = self.RESERVE
        try:
            return super().choose(state, slot)
        finally:
            _lc.RESERVE = saved


class EKF_window_MPC(_WindowAware, EKF_MPC):
    """13: controller 1, aware of uplink windows."""


class EKF_turncost_MPC(_TurnCost, EKF_MPC):
    """14: controller 1, budgets turn energy."""


class EKF_aimdisc_MPC(_AimDisc, EKF_MPC):
    """18: controller 1 aiming at the target disc instead of its centre."""


class EKF_aimdisc_turncost_window_MPC(_WindowAware, _AimDisc, _TurnCost, EKF_MPC):
    """19: controller 1 with every planner addition that helped on its own (18, 14, 13)."""


class CKF_aimdisc_turncost_window_MPC(_WindowAware, _AimDisc, _TurnCost, CKF_MPC):
    """20: as 19 on the cubature filter."""


class PF_aimdisc_turncost_window_MPC(_WindowAware, _AimDisc, _TurnCost, PF_MPC):
    """21: as 19 on the particle filter."""


class EKF_sandodo_aimdisc_turncost_window_MPC(_WindowAware, _AimDisc, _TurnCost, _SandOdometer, EKF_MPC):
    """22: as 19, plus the battery sand odometer: unmapped sand found from the battery reading is
    added to the controller's own map."""


class EKF_stayalive_aimdisc_turncost_window_MPC(_StayAlive, _WindowAware, _AimDisc, _TurnCost, EKF_MPC):
    """23: as 19, plus the stay-alive rule: no command that is expected to empty the battery."""


class EKF_sandodo_stayalive_aimdisc_turncost_window_MPC(_StayAlive, _WindowAware, _AimDisc, _TurnCost,
                                                        _SandOdometer, EKF_MPC):
    """24: as 19 with both the battery sand odometer (22) and the stay-alive rule (23)."""


class EKF_sandodo_mapdoubt_stayalive_aimdisc_turncost_window_MPC(_StayAlive, _WindowAware, _AimDisc, _TurnCost,
                                                                 _MapDoubt, _SandOdometer, EKF_MPC):
    """25: as 24, plus map doubt: once unmapped sand has been found, the way home budgets the share
    of undriven bedrock that may be sand too."""


# =============================================================================================
# Bounds: same planner, privileged information
# =============================================================================================

class _Oracle(LogMixin, KalmanMPCController):
    EXACT = False

    def __init__(self, tools, env):
        self._env = env
        super().__init__(tools)
        self._pin()

    def terrain_at(self, x, y):
        return self._env.true_terrain(x, y)

    def _pin(self):
        f = self.filter
        if self.EXACT:
            f.r_pos, f.vo_rel = VAR_FLOOR, 1e-3
        truth = self._env.oracle_truth()
        n = len(f.mean)
        for i in [2] + [f.index[t] for t in f.terrains]:
            for j in range(n):
                f.cov[i][j] = f.cov[j][i] = 0.0
            f.cov[i][i] = VAR_FLOOR
        f.mean[2] = truth["bias_rad"]
        for t in f.terrains:
            f.mean[f.index[t]] = truth["slip"][t]

    def _filter(self, packet):
        if hasattr(self, "_env"):
            self._pin()
        super()._filter(packet)
        if hasattr(self, "_env"):
            self._pin()


class Oracle_params_MPC(_Oracle):
    """3: knows the true slip, current heading bias and true terrain; noisy fixes; real delay;
    stock planner (reserve 2.0, aims at centres)."""


class _OracleExact(_Oracle):
    EXACT = True


class Oracle_exact_tight_MPC(_AimDisc, _Tight, _OracleExact):
    """16 (and 17 without delay): true parameters and exact telemetry, with margins matched to
    that information: reserve 0.5 and aims at the disc."""


# =============================================================================================
# Registry
# =============================================================================================

def _ours(cls):
    return lambda tools, env: cls(tools).run()


def _oracle(cls):
    return lambda tools, env: cls(tools, env).run()


def _team(name):
    def run(tools, env):
        from lightlag_dynamic.compare import POLICY_TABLE
        POLICY_TABLE[name](tools)
    return run


REGISTRY = {}

RETIRED = {
    4: "Oracle_exact_MPC: exact information on the stock planner (reserve 2.0, aims at centres); "
       "scored below the EKF, so not a bound; replaced by 16",
    5: "Oracle_exact_nodelay_MPC: as 4 without delay; replaced by 17",
    6: "EKF_MPC_nofailupdate: controller 1 with the failed-sample update switched off (ablation)",
    7: "EKF_MPC_nowait: controller 1 with the 97% wait rule switched off (ablation)",
    9: "PF2000_MPC: controller 2 with 2000 particles instead of 500 (same model, different value)",
}


def register(name, play, kind="manh", env_kwargs=None, force_delay=None, logged=True, note="", why="", built=""):
    REGISTRY[name] = {"play": play, "kind": kind, "env_kwargs": env_kwargs or {},
                      "force_delay": force_delay, "logged": logged, "note": note, "why": why, "built": built}


def number(name):
    """The N in <METHODS>_manh_controller_<N>, or None for a team controller."""
    head, sep, tail = name.rpartition("_manh_controller_")
    return int(tail) if sep and tail.isdigit() else None


_EXACT = {"exact_telemetry": True}
_R1 = "2026-11-14, lab round 1"
_R2 = "2026-11-14, lab round 2"
_R3 = "2026-11-14, combinations"

register("EKF_MPC_manh_controller_1", _ours(EKF_MPC), built="2026-11-14, repo kf_mpc (second increment)",
         note="the repo's kf_mpc: EKF + delay compensation + MPC with chance constraints",
         why="Noisy sensing with a hidden, drifting heading bias needs an estimator that learns bias and slip "
             "while commands are in flight. Home in all 240 repo episodes; 85.0% of the maximum on the base suite.")
register("PF_MPC_manh_controller_2", _ours(PF_MPC), built=_R1,
         note="bootstrap particle filter (500 particles) + the same planner",
         why="Slip clipping, wheel spins and failed samples make the posterior non-Gaussian; a particle filter "
             "handles them exactly (SSY345 L8). Ties the EKF overall (85.3% base, 76.5% noise); better with 1 m "
             "position noise (noisy, delay 5: 84% vs 72%); worse after a slip jump (68% vs 77%).")
register("Oracle_params_MPC_manh_controller_3", _oracle(Oracle_params_MPC), kind="bound", built=_R1,
         note="bound: true slip, bias and terrain; noisy fixes; real delay; stock planner",
         why="Measures what learning the parameters costs: rush_noisy delay 3 goes from 71% to 78%. On static and "
             "noisy it scores below the EKF, because the stock planner's margins cannot fit three targets in the "
             "energy (60.27 needed, 60 available): the planner, not the information, was the limit (see 16).")
register("CKF_MPC_manh_controller_8", _ours(CKF_MPC), built=_R2,
         note="cubature Kalman filter: sigma points through the drive kinematics + the planner",
         why="The EKF linearises the drive at the mean; sigma points carry bias and slip uncertainty through the "
             "terrain-switching drive (SSY345 L6). Best estimator at high noise (noisy, delay 5, noise level 3: "
             "68% vs 50%); otherwise within noise of the EKF.")
register("PF_forgetting_MPC_manh_controller_10", _ours(PF_forgetting_MPC), built=_R2,
         note="particle filter whose slips random-walk (can follow a slip change)",
         why="A slip jump traps a particle filter with static slip particles. Did not help: slip jump, noisy, "
             "delay 3: 65% vs 68% for controller 2.")
register("EKF_forgetting_MPC_manh_controller_11", _ours(EKF_forgetting_MPC), built=_R2,
         note="controller 1 + process noise on slip (forgetting)",
         why="Same idea for the EKF. Best real controller with two hidden sand patches (noisy, delay 3: 56% vs "
             "46%); costs about 1 point elsewhere (83.9% base).")
register("EKF_IEKS_MPC_manh_controller_12", _ours(EKF_IEKS_MPC), built=_R2,
         note="iterated extended Kalman smoother: history relinearised at smoothed states",
         why="Tests whether hindsight helps the present through better linearisation points (SSY345 L6 + L7). "
             "No gain (85.0% base, 75.8% noise): linearisation is not the bottleneck; the controller acts on "
             "predictions, which smoothing cannot improve.")
register("EKF_window_MPC_manh_controller_13", _ours(EKF_window_MPC), built=_R2,
         note="controller 1, aware of uplink windows",
         why="With uplink windows, controllers that ignore them send commands that would execute beyond the "
             "horizon (about 31% of rush_noisy episodes crash). No crashes; windows 10/3, rush_noisy, delay 3: "
             "50% vs 39%.")
register("EKF_turncost_MPC_manh_controller_14", _ours(EKF_turncost_MPC), built=_R2,
         note="controller 1, budgets turn energy",
         why="With a turn cost, planners that ignore it run out of energy. Turn cost 0.03, noisy, delay 3: 75% "
             "and always home, vs 61% for controller 1; every team controller and both bounds collapse there.")
register("EKF_terrainVO_MPC_manh_controller_15", _ours(EKF_terrainVO_MPC), built=_R2,
         note="controller 1, terrain-dependent odometry noise",
         why="Odometry noise may depend on terrain. Small effect: noisy, delay 3: 91% vs 89%.")
register("Oracle_exact_tight_MPC_manh_controller_16", _oracle(Oracle_exact_tight_MPC), kind="bound", built=_R2,
         env_kwargs=_EXACT, note="bound: true parameters, exact telemetry, real delay, reserve 0.5, aims at the disc",
         why="Retired bounds 4 and 5 used the stock planner and scored below the EKF, so they were not bounds. "
             "Margins matched to the information fix that: 90.4% base vs 85.0% for controller 1. Not a bound on "
             "turn-cost or window scenarios, which its planner ignores.")
register("Oracle_exact_nodelay_tight_MPC_manh_controller_17", _oracle(Oracle_exact_tight_MPC), kind="bound",
         built=_R2, env_kwargs=_EXACT, force_delay=0, note="bound: as 16 without delay",
         why="Separates the cost of delay: 95.9% base, so delay costs 5.5 points even with perfect information.")
register("EKF_aimdisc_MPC_manh_controller_18", _ours(EKF_aimdisc_MPC), built=_R2,
         note="controller 1 aiming at the target disc instead of its centre",
         why="Bound 16 showed that aiming at the centre wastes about 0.5 m per leg. Best real controller on the "
             "base suite: 86.5% vs 85.0%, always home.")
register("EKF_aimdisc_turncost_window_MPC_manh_controller_19", _ours(EKF_aimdisc_turncost_window_MPC), built=_R3,
         note="controller 1 + aim at disc + turn-cost budget + window awareness",
         why="18, 14 and 13 each helped on their own factor and are inactive when their rule is absent, so "
             "together they should match the best of them on every scenario. They do: 77.0% averaged over the "
             "three suites vs 75.3% for controller 1. Held-out seeds 400-419: +1.7 points over controller 1 "
             "(95% interval +1.4 to +2.0); no numpy needed.")
register("CKF_aimdisc_turncost_window_MPC_manh_controller_20", _ours(CKF_aimdisc_turncost_window_MPC), built=_R3,
         note="cubature filter + aim at disc + turn-cost budget + window awareness",
         why="As 19 on the estimator that held up best at high noise (8). Best on development seeds (77.5% "
             "averaged over the three suites), but on held-out seeds 400-419 it ties 19 (+0.1 points, interval "
             "-0.2 to +0.4): the cubature filter adds nothing measurable.")
register("PF_aimdisc_turncost_window_MPC_manh_controller_21", _ours(PF_aimdisc_turncost_window_MPC), built=_R3,
         note="particle filter + aim at disc + turn-cost budget + window awareness",
         why="As 19 on the estimator that held up best with large position noise (2). 77.1%; 89% with 1 m "
             "position noise (noisy, delay 3); weak with two hidden sand patches (38%).")
register("EKF_sandodo_aimdisc_turncost_window_MPC_manh_controller_22", _ours(EKF_sandodo_aimdisc_turncost_window_MPC),
         built="2026-11-14, hidden-sand fix",
         note="19 + battery sand odometer: unmapped sand read off the battery is added to its own map",
         why="Hidden sand was the biggest failure: plans trust the published map, so a quarter of rovers die. "
             "Battery telemetry is noise-free, so each drive's battery drop gives its sand wheel metres exactly. "
             "Result, held-out seeds 400-419: +0.2 points over 19 (95% interval +0.1 to +0.3), +0.4 on Part B; "
             "two hidden patches on noisy 49% -> 54%. Unchanged on the published profiles.")
register("EKF_stayalive_aimdisc_turncost_window_MPC_manh_controller_23", _ours(EKF_stayalive_aimdisc_turncost_window_MPC),
         built="2026-11-14, hidden-sand fix",
         note="19 + stay-alive rule: never send a command expected to empty the battery before the horizon",
         why="Traced hidden-sand deaths: the patch on the last route home cannot be seen in time, and the rover "
             "then makes a final short drive home and dies there (score 0) instead of staying alive just "
             "outside (half score). Result, held-out seeds: never worse than 19 (7 episodes better, 0 worse "
             "of 3,840), +0.1 points; two hidden patches on noisy: deaths 27% -> 22%.")
register("EKF_sandodo_stayalive_aimdisc_turncost_window_MPC_manh_controller_24",
         _ours(EKF_sandodo_stayalive_aimdisc_turncost_window_MPC), built="2026-11-14, hidden-sand fix",
         note="19 + battery sand odometer (22) + stay-alive rule (23)",
         why="The odometer fixes legs after a patch is found; the stay-alive rule covers the patch found too "
             "late. Result, held-out seeds: best so far, +0.2 points over 19 (+0.1 to +0.4) and +1.9 over "
             "controller 1 (+1.6 to +2.3); Part B +0.6 over 19 (+0.3 to +0.9); identical on the published "
             "profiles. Two hidden patches on noisy: 54% vs 68% for solvi_reference, deaths 20% vs 7%.")
register("EKF_sandodo_mapdoubt_stayalive_aimdisc_turncost_window_MPC_manh_controller_25",
         _ours(EKF_sandodo_mapdoubt_stayalive_aimdisc_turncost_window_MPC), built="2026-11-14, hidden-sand fix",
         note="24 + map doubt: once the map is shown wrong, undriven bedrock on the way home is budgeted at the "
              "unmapped-sand rate seen so far",
         why="Traces of 24 showed the remaining deaths: the patch on the last route home is crossed only after "
             "the third target. Once one patch has been found, the next may be on undriven ground. "
             "Result, held-out seeds: deaths with two patches on noisy fall from 20% to 12%, but the share "
             "only from 54% to 55%, and it costs 0.4 points on the published profiles and the noise suite "
             "(-0.2 vs 19 overall): the odometer's rare false patches on clean maps switch the doubt on.")
for _name in ("solvi_reference", "kristjan_reference", "blind", "cautious"):
    register(_name, _team(_name), kind="team", logged=False, note="team controller, imported unchanged",
             why="comparison only")
