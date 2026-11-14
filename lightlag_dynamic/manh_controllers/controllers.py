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
import itertools
import math

import numpy as np

import lightlag_dynamic.controllers as _lc
from lightlag_dynamic.controllers import HAZARD_CLEARANCE, Leg, _clip_interval
from lightlag_dynamic.kf_mpc import GATE, VAR_FLOOR, DriveFilter, KalmanMPCController
from lightlag_dynamic.kf_mpc_rt import RealTimeKalmanMPC

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


class _Unverified:
    """Mapped bedrock this rover has not driven over: the ground a hidden patch could still be on.
    Needs _SandOdometer, which records every drive. A point counts as verified within VERIFIED
    metres of a drive; paths are sampled every STEP metres."""
    VERIFIED = 0.5
    STEP = 0.25

    def sand_extra_per_metre(self):
        m = self.multiplier
        return max(0.0, self.drive_cost * (m["sand"] / (1 - self.slip_safe("sand"))
                                           - m["bedrock"] / (1 - self.slip("bedrock"))))

    def _unverified(self, start, goal):
        key = (round(start[0], 3), round(start[1], 3), round(goal[0], 3), round(goal[1], 3),
               len(getattr(self, "driven", [])), len(self.sand))
        cache = self.__dict__.setdefault("_unverified_cache", {})
        if key not in cache:
            cache[key] = self._unverified_metres(self.route(start, goal) or [start, goal])
        return cache[key]

    def _unverified_metres(self, path, strict=False):
        """Mapped-bedrock metres along a polyline farther than VERIFIED from every drive so far.
        strict: only ground beside a drive counts, not ground just past its end, which is where a
        rover probing along a line goes next."""
        points, weights = [], []
        for a, b in zip(path, path[1:]):
            d = math.dist(a, b)
            n = max(1, int(d / self.STEP))
            for i in range(n):
                t = (i + 0.5) / n
                p = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
                if self.terrain_at(*p) == "bedrock":
                    points.append(p)
                    weights.append(d / n)
        if not points:
            return 0.0
        w = np.array(weights)
        driven = getattr(self, "driven", [])
        if not driven:
            return float(w.sum())
        P = np.array(points)
        A = np.array([a for a, _ in driven])
        AB = np.array([b for _, b in driven]) - A
        n2 = np.maximum((AB ** 2).sum(1), 1e-12)
        raw = ((P[:, None, :] - A[None]) * AB[None]).sum(2) / n2[None]
        t = np.clip(raw, 0.0, 1.0)
        gap = np.sqrt(((P[:, None, :] - (A[None] + t[..., None] * AB[None])) ** 2).sum(2))
        if strict:
            gap = np.where((raw >= 0.0) & (raw <= 1.0), gap, np.inf)
        nearest = gap.min(1)
        return float(w[nearest > self.VERIFIED].sum())


class _BayesSand(_Unverified):
    """Bayesian belief about unmapped sand, priced on the way home from the first decision
    (needs _SandOdometer, which counts the evidence).

    The share rho of mapped bedrock that is really sand has a Beta prior counted in metres,
    PRIOR_SAND pseudo-metres of sand against PRIOR_BED of bedrock. After every drive the battery
    odometer adds the unmapped sand it found and the mapped bedrock it crossed. Every leg that ends
    at base adds rho_up x (unverified mapped-bedrock metres on its route) x (extra energy per sand
    metre) to its pessimistic energy, with rho_up = posterior mean + Z standard deviations and
    unverified = more than VERIFIED metres from every drive so far. Before any driving this is
    cautious, like a worst-case budget; every clean metre driven tightens it, so on a map that is
    right the plan relaxes towards 24's. Only the pessimistic way home changes, which is what
    the planner checks after each stop; the nominal plan is untouched.

    Literature: adaptive (recourse) instead of static robust budgets under uncertain energy use
    (arXiv 2204.10913); chance-constrained, risk-aware rover planning (Ono, Pavone et al. 2015;
    Endo et al., ICRA 2023, arXiv 2303.01169); online energy maps from the robot's own
    measurements (Wei & Isler, CoRL 2019, arXiv 1907.06337)."""
    PRIOR_SAND = 1.0
    PRIOR_BED = 4.0
    Z = 1.0

    def sand_rate(self, z=None):
        """Posterior mean of rho plus z standard deviations (default Z), at most 1."""
        z = self.Z if z is None else z
        found = getattr(self, "unmapped_found", 0.0)
        a = self.PRIOR_SAND + found
        b = self.PRIOR_BED + max(0.0, getattr(self, "bedrock_driven", 0.0) - found)
        n = a + b
        return min(1.0, a / n + z * math.sqrt(a * b / (n * n * (n + 1))))

    def leg(self, start, goal):
        hop = super().leg(start, goal)
        if hop is None or math.dist(goal, self.base) > 1e-9:
            return hop  # only the way home is budgeted pessimistically by the planner
        unverified = self._unverified(start, goal)
        if unverified <= 0.0:
            return hop
        extra = self.sand_rate() * unverified * self.sand_extra_per_metre()
        return Leg(hop.commands, hop.energy, hop.energy_safe + extra, hop.uncertainty)


class EKF_sandodo_bayessand_stayalive_aimdisc_turncost_window_MPC(_StayAlive, _WindowAware, _AimDisc, _TurnCost,
                                                                  _BayesSand, _SandOdometer, EKF_MPC):
    """26: as 24, plus a Bayesian belief about unmapped sand that prices the undriven part of
    every way home from the first decision, tightening as clean ground is driven."""


class _SafetyFilter(_StayAlive):
    """Energy safety filter (needs _BayesSand): the stay-alive check also charges the batch's
    undriven bedrock at the posterior-mean sand rate (SURVIVE_Z standard deviations above it).
    A batch is held back only when it would empty the battery before the horizon under that
    charge while holding still survives: dead scores 0 and alive away from base scores half, so
    sending pays only when it more likely than not survives. The nominal planner proposes and the
    filter vetoes, as in energy-sufficiency safety filters (Eclares/eware, arXiv 2310.06933;
    control-barrier energy sufficiency, arXiv 2306.15115).

    Tried on 26, not kept: no measurable effect on development seeds (within 0.1 points and 0.4
    points of deaths). At the posterior-mean rate the filter almost never binds; the worst-case
    version that does bind, with probing, is _GuardedMove."""
    SURVIVE_Z = 0.0

    def _survives(self, commands):
        slot = self.next_slot()
        if slot > self.horizon:
            return True
        state = self.predict(slot)
        if not state["alive"] or state["battery"] - self.idle * (self.horizon - slot + 1) <= 0:
            return True  # lost either way
        sim = {"x": state["x"], "y": state["y"], "battery": state["battery"]}
        batch = commands[:max(0, self.horizon - slot + 1)]
        path = [(sim["x"], sim["y"])]
        for c in batch:
            sim["battery"] -= self.idle
            if c["action"] == "drive":
                self._simulate_drive(sim, c)
                path.append((sim["x"], sim["y"]))
            elif c["action"] == "sample":
                sim["battery"] -= self.sample_cost
        sim["battery"] -= self.idle * (self.horizon - (slot + len(batch) - 1))
        if len(path) > 1:
            sim["battery"] -= (self.sand_rate(self.SURVIVE_Z) * self._unverified_metres(path)
                               * self.sand_extra_per_metre())
        return sim["battery"] > 0


class _MaxMargin:
    """Robust tie-break: among target sequences of equal value, prefer the one that leaves more
    pessimistic energy to spare at the end (capped at SPARE_CAP), then the earlier finish. Slack
    beyond the cap buys nothing, so with ample energy the planner behaves exactly as before; when
    margins are thin it takes the cheaper of equally valuable tours, as a robust optimiser
    maximising slack would. Same enumeration as lightlag_dynamic.controllers.Controller.choose.

    Tried on 24 and 26, not kept: no effect on development seeds (within 0.1 points). Ties in
    value are rare, and where they occur the spares rarely differ."""
    SPARE_CAP = 6.0

    def choose(self, state, slot):
        start = (state["x"], state["y"])
        open_targets = [t for tid, t in sorted(self.targets.items()) if tid not in state["sampled"]]
        budget = state["battery"] - self.idle * (self.horizon - state["tick"]) - _lc.RESERVE
        points = {t["id"]: (t["x"], t["y"]) for t in open_targets}
        points.update({"start": start, "base": self.base})
        legs = {}

        def leg(a, b):
            if (a, b) not in legs:
                legs[(a, b)] = self.leg(points[a], points[b])
            return legs[(a, b)]

        best_key, best = None, (0.0, math.inf, ())
        for size in range(1, min(len(open_targets), _lc.MAX_SEQUENCE) + 1):
            for sequence in itertools.permutations(open_targets, size):
                tick, value, expected, here = slot, 0.0, 0.0, "start"
                for target in sequence:
                    hop = leg(here, target["id"])
                    home = leg(target["id"], "base")
                    if hop is None or home is None:
                        break
                    if here != "start":
                        tick += self.wait_per_leg()
                    tick += len(hop.commands)
                    if self.needs_confirmation(hop):
                        tick += self.confirmation_ticks(hop)
                    value += self.value_at(target, tick)
                    tick += 1
                    expected += hop.energy + self.sample_cost
                    if expected + home.energy_safe > budget:
                        break
                    here = target["id"]
                else:
                    home = leg(here, "base")
                    end = tick + self.wait_per_leg() + len(home.commands) - 1
                    if end > self.horizon - self.home_slack() or expected + home.energy > budget:
                        continue
                    spare = min(self.SPARE_CAP, budget - expected - home.energy_safe)
                    key = (round(value, 9),) + self._tiebreak(spare, points[here]) + (-end,)
                    if best_key is None or key > best_key:
                        best_key, best = key, (value, end, sequence)
        self.plan_end, self.plan = best[1], best[2]
        return best[2]

    def _tiebreak(self, spare, last):
        return (round(spare, 6),)


class _SafeOrder(_MaxMargin):
    """Among target sequences of equal value, prefer the one whose last way home crosses the
    least unverified mapped bedrock (needs _Unverified), then the larger spare, then the earlier
    finish. Ground driven on the way out is checked by the battery odometer while there is still
    energy to re-plan; the last way home is the one leg after which nothing can be re-planned, so
    the order that leaves it on checked ground carries the least unrecoverable risk (the
    recourse argument of adaptive robust routing, arXiv 2204.10913). With no hidden ground on any
    route home it changes nothing.

    Tried on 24 + sand-aware filter + guarded moves, not kept: hidden sand on noisy +1.2 points,
    but clean maps -4.3 and base -2.8 (development seeds). The safer order is often the one with
    less energy to spare, which then cannot finish the third target; a spare floor of 1 or 2
    energy before the risk key changed nothing."""

    SPARE_FLOOR = None  # if set: first keep at least this much pessimistic energy spare

    def _tiebreak(self, spare, last):
        risk = -round(self._unverified(last, self.base), 1)
        if self.SPARE_FLOOR is None:
            return (risk, round(spare, 6))
        return (round(min(spare, self.SPARE_FLOOR), 6), risk, round(spare, 6))



class _SandAwareFilter:
    """Proprioceptive terrain labels for the drive filter. Before the EKF propagates a drive,
    the battery reading gives the exact wheel metres it spent on sand (see _SandOdometer); where
    the map disagrees, the drive is propagated with that many metres relabelled, so the filter
    predicts the right slip and the visual odometry that follows passes its gate.

    Without it, a drive across unmapped sand is propagated as bedrock: the filter overshoots
    along the drive, the visual odometry that measures the shortfall fails the 3-sigma gate (it
    is meant to reject wheel spins) and is thrown away, the position fixes drag the bedrock slip
    above its published range, and the estimate stays several standard deviations off for tens
    of ticks. On development seed 2 (noisy, one hidden patch, delay 3) controller 26 missed a
    sample by 1.1 m and parked 0.76 m from base, just outside the 0.75 m radius, believing it
    was 0.13 m from the centre with 0.09 m standard deviation.

    The endpoint of a straight drive depends only on its wheel metres per terrain, not their
    order, so the relabelled metres are placed at the end (rover ends on sand), the start (began
    on sand) or the middle. Literature: proprioceptive (energy / motor-current) terrain
    classification (Ojeda et al., J. Field Robotics 2006; Brooks & Iagnemma 2005); terrain-
    dependent slip models selected by the observed terrain, the multiple-model approach to
    estimation under a switching model (Bar-Shalom, Li & Kirubarajan 2001); slip from visual
    odometry on Mars rovers (Helmick et al. 2006; Maimone, Cheng & Matthies 2007)."""
    RELABEL_TOL = 0.05  # wheel metres

    def _filter(self, packet):
        f = self.filter
        sand_wheel = self._battery_sand_wheel(packet)
        if sand_wheel is None:
            return super()._filter(packet)
        base = type(f).propagate

        def propagate(mean, cov, heading_deg, wheel, terrain_at):
            labels = []
            base(f, mean, cov, heading_deg, wheel, lambda x, y: labels.append(terrain_at(x, y)) or labels[-1])
            it = iter(self._relabel(labels, wheel, sand_wheel, packet))
            return base(f, mean, cov, heading_deg, wheel, lambda x, y: next(it, None) or terrain_at(x, y))

        f.propagate = propagate
        try:
            return super()._filter(packet)
        finally:
            del f.propagate

    def _battery_sand_wheel(self, packet):
        """Exact sand wheel metres of the drive this packet reports, or None."""
        index = next((i for i in range(len(self.packets) - 1, 0, -1) if self.packets[i] is packet), None)
        if index is None:
            return None
        prev = self.packets[index - 1]
        drive = _executed_drive(self, packet)
        if drive is None or not drive[2] or packet["tick"] != prev["tick"] + 1 or not packet["alive"]:
            return None
        heading, wheel, _ = drive
        mult = self.multiplier
        energy = prev["battery"] - packet["battery"] - self.idle
        if not hasattr(self, "_turn_cost"):
            self._turn_cost = self.tools.rules().get("turn_cost_per_degree") or 0.0
        if self._turn_cost and prev.get("heading_deg") is not None:
            turn = abs((heading - prev["heading_deg"] + 180.0) % 360.0 - 180.0)
            energy -= self._turn_cost * turn * self.drive_cost * mult.get(prev.get("terrain"), 1.0)
        sand = (energy / self.drive_cost - mult["bedrock"] * wheel) / (mult["sand"] - mult["bedrock"])
        return min(wheel, max(0.0, sand))

    def _relabel(self, labels, wheel, sand_wheel, packet):
        seg = self.filter.segment
        pieces = [min(seg, wheel - k * seg) for k in range(len(labels))]
        delta = sand_wheel - sum(p for p, t in zip(pieces, labels) if t == "sand")
        if abs(delta) <= self.RELABEL_TOL:
            return labels
        prev = self.packets[self.packets.index(packet) - 1]
        n = len(labels)
        if packet.get("terrain") == "sand" and prev.get("terrain") != "sand":
            order = list(range(n - 1, -1, -1))
        elif prev.get("terrain") == "sand" and packet.get("terrain") != "sand":
            order = list(range(n))
        else:
            order = sorted(range(n), key=lambda k: abs(k - (n - 1) / 2))
        new, flip_from, flip_to = list(labels), *(("bedrock", "sand") if delta > 0 else ("sand", "bedrock"))
        left = abs(delta)
        for k in (order if delta > 0 else order[::-1]):
            if left < pieces[k] / 2:
                break
            if new[k] == flip_from:
                new[k] = flip_to
                left -= pieces[k]
        return new



class _FadingFilter:
    """Innovation-based adaptive fading for the drive filter's position. Each position fix's
    normalised innovation squared (NIS, chi-square with 2 degrees of freedom: mean 2 when the
    filter's covariance is honest) is kept over the last WINDOW fixes. When their mean exceeds
    NIS_LIMIT, the position rows and columns of the covariance are scaled by sqrt(mean NIS / 2)
    (a congruence, so the matrix stays positive semi-definite), the history is cleared, and the
    fix is applied to the inflated covariance.

    It catches a filter that is confident and wrong for any reason the model does not cover: on
    development seeds a slip jump pushes the true slip outside the published range the filter
    clamps to, and controller 24 + guarded moves then stopped 0.9 m from base believing it was
    0.3 m away with 0.11 m standard deviation, taking 30 fixes to drift back. Under an honest model
    five fixes average above 4 about 3% of the time, and the inflation is then mild.

    Literature: adaptive Kalman filtering by covariance matching (Mehra, IEEE TAC 1972); adaptive
    fading Kalman filter (Xia, Rao, Ying & Shen, Automatica 1994); strong tracking filter (Zhou &
    Frank 1996); innovation-based adaptive estimation (Mohamed & Schwarz, J. Geodesy 1999;
    Akhlaghi, Zhou & Huang, arXiv 1702.00884)."""
    WINDOW = 5
    NIS_LIMIT = 4.0

    def _filter(self, packet):
        f = self.filter
        base = type(f).update_position

        def update_position(z):
            P, r = f.cov, f.r_pos
            nu0, nu1 = z[0] - f.mean[0], z[1] - f.mean[1]
            s00, s01, s11 = P[0][0] + r, P[0][1], P[1][1] + r
            det = s00 * s11 - s01 * s01
            if det > 1e-12:
                history = self.__dict__.setdefault("_nis", [])
                history.append((s11 * nu0 * nu0 - 2 * s01 * nu0 * nu1 + s00 * nu1 * nu1) / det)
                del history[:-self.WINDOW]
                mean = sum(history) / len(history)
                if len(history) == self.WINDOW and mean > self.NIS_LIMIT:
                    g = math.sqrt(mean / 2.0)
                    d = [g, g] + [1.0] * (len(f.mean) - 2)
                    f.cov = [[P[i][j] * d[i] * d[j] for j in range(len(d))] for i in range(len(d))]
                    history.clear()
                    self.fadings = getattr(self, "fadings", 0) + 1
            return base(f, z)

        f.update_position = update_position
        try:
            return super()._filter(packet)
        finally:
            del f.update_position

class _GuardedMove(_StayAlive):
    """Worst-case energy sufficiency with guarded moves (needs _Unverified and _SandOdometer).

    The planner stays nominal and takes the third target when the published map says it fits.
    Before a batch goes up, the filter asks whether the rover would still be alive at the horizon
    if every unverified metre of mapped bedrock in the batch were sand. If yes, the batch goes as
    planned. If not, only its longest prefix that passes is sent (a drive may be shortened, never
    below MIN_STEP metres), and the controller waits for that prefix's telemetry before deciding
    again: the battery reading shows exactly whether the ground was sand, so a hidden patch on
    the last way home is found after a short step, while the rover can still stop alive, instead
    of after the whole leg has been queued. Probing costs time, not energy (idle drain is paid
    anyway), so it runs only while the horizon leaves room for another round trip of telemetry;
    otherwise, or when no prefix passes, the nominal stay-alive rule decides as before.

    Literature: control-barrier / safety-filter energy sufficiency, a minimal change to the nominal
    command that keeps the safe set invariant (arXiv 2306.15115; Eclares/eware, arXiv 2310.06933;
    aerial safety survey, arXiv 2504.08601); guarded moves under uncertain terrain, as on the Mars
    rovers, which drive in short checked steps where slip may be high (Maimone et al. 2007;
    Helmick et al. 2006); robust (worst-case) constraints applied only where the evidence is
    missing, as adaptive robust routing recommends (arXiv 2204.10913)."""
    MIN_STEP = 0.25
    MARGIN = 0.5  # energy kept for modelling error (turns, slip spread)

    def send(self, commands):
        slot = self.next_slot()
        if not commands or slot > self.horizon:
            return super().send(commands)
        state = self.predict(slot)
        if not state["alive"] or self._worst_battery([], slot, state) <= 0:
            return super().send(commands)  # staying put cannot survive either
        if self._worst_battery(commands, slot, state) > 0:
            return super().send(commands)
        prefix = self._guarded_prefix(commands, slot, state)
        windows = self._windows() if hasattr(self, "_windows") else None
        round_trip = 2 * self.k + 2 + (windows[0] - windows[1] if windows else 0)  # + wait for a window
        if prefix and slot + len(commands) + round_trip <= self.horizon:
            if super().send(prefix):
                self.confirm_tick = self.reserved_until()
                return True
            return False
        return super().send(commands)

    def _worst_battery(self, commands, slot, state):
        """Battery left at the horizon if every unverified bedrock metre of the batch is sand."""
        sim = {"x": state["x"], "y": state["y"], "battery": state["battery"]}
        batch = commands[:max(0, self.horizon - slot + 1)]
        path = [(sim["x"], sim["y"])]
        for c in batch:
            sim["battery"] -= self.idle
            if c["action"] == "drive":
                self._simulate_drive(sim, c)
                path.append((sim["x"], sim["y"]))
            elif c["action"] == "sample":
                sim["battery"] -= self.sample_cost
        sim["battery"] -= self.idle * (self.horizon - (slot + len(batch) - 1))
        if len(path) > 1:
            sim["battery"] -= self._unverified_metres(path, strict=True) * self.sand_extra_per_metre()
        return sim["battery"] - (self.MARGIN if batch else 0.0)

    def _guarded_prefix(self, commands, slot, state):
        prefix = []
        for c in commands:
            if self._worst_battery(prefix + [c], slot, state) > 0:
                prefix.append(c)
                continue
            if c["action"] == "drive":
                lo, hi = 0.0, c["metres"]
                for _ in range(8):
                    mid = (lo + hi) / 2
                    if self._worst_battery(prefix + [dict(c, metres=mid)], slot, state) > 0:
                        lo = mid
                    else:
                        hi = mid
                if lo >= self.MIN_STEP:
                    prefix.append(dict(c, metres=round(lo, 3)))
            break
        return prefix


class _ArmedGuard(_GuardedMove):
    """Guarded moves, armed only when a probe is free (needs what _GuardedMove needs).

    _GuardedMove asks before every batch whether the rover survives if all unverified bedrock in
    it is sand, and if not it probes: it sends a prefix and waits a round trip of telemetry. A
    published map has no hidden sand, yet in the 50-tick rush missions energy is tight, the check
    fails in 50-80% of episodes, and each probe costs 2k + 2 ticks. That wait was the whole
    plain-profile cost of 27 (-3.3 points at delay 3; ablation in the README), while on hidden
    sand the same guard is worth +6.4 points.

    Here the guard runs only when the wait costs nothing the plan counts on: started one round
    trip later, the current plan still collects the same value (no deadline is passed) and still
    ends in time to be home. On the way home, with no target left in the plan, that always holds
    (the guard itself checks that the round trip fits the horizon). Otherwise the batch goes as
    planned under 24's stay-alive rule. The rule has no parameter of its own.

    Literature: probing pays only while the information can still change a decision at an
    acceptable price. Dual control weighs the probing effect of a command against its control
    cost (Feldbaum 1960; Bar-Shalom & Tse 1974; Mesbah 2018, survey of dual MPC); the value of
    information is the expected gain from deciding after the observation instead of before
    (Howard 1966); safe exploration keeps a way back to a safe state (Moldovan & Abbeel 2012).

    Mixin attribute names must be unique along the MRO: a first draft's class constant SIGMAS
    silently replaced _AimDisc.SIGMAS and changed where every variant aimed."""

    def send(self, commands):
        if commands and self._probe_is_free():
            return super().send(commands)                # guarded moves, as in 27
        return super(_GuardedMove, self).send(commands)  # the stay-alive rule, as in 24

    def _guard_round_trip(self):
        windows = self._windows() if hasattr(self, "_windows") else None
        return 2 * self.k + 2 + (windows[0] - windows[1] if windows else 0)

    def _probe_is_free(self):
        plan = getattr(self, "plan", ())
        if not plan:
            return True  # the way home
        slot = self.next_slot()
        if slot > self.horizon:
            return False
        state = self.predict(slot)
        now = self._plan_outcome(plan, state, slot)
        late = self._plan_outcome(plan, state, slot + self._guard_round_trip())
        return late[0] >= now[0] - 1e-9 and late[1] <= self.horizon - self.home_slack()

    def _plan_outcome(self, plan, state, slot):
        """Value and end tick of the plan if it starts at slot (the planner's tick accounting)."""
        tick, value, here = slot, 0.0, (state["x"], state["y"])
        for i, target in enumerate(plan):
            point = (target["x"], target["y"])
            hop = self.leg(here, point)
            if hop is None:
                return -math.inf, math.inf
            if i:
                tick += self.wait_per_leg()
            tick += len(hop.commands)
            if self.needs_confirmation(hop):
                tick += self.confirmation_ticks(hop)
            value += self.value_at(target, tick)
            tick += 1
            here = point
        home = self.leg(here, self.base)
        if home is None:
            return -math.inf, math.inf
        return value, tick + self.wait_per_leg() + len(home.commands) - 1


class EKF_fading_sandfilter_sandodo_guarded_aimdisc_turncost_window_MPC(
        _GuardedMove, _WindowAware, _AimDisc, _TurnCost, _Unverified, _FadingFilter, _SandAwareFilter,
        _SandOdometer, EKF_MPC):
    """27: 24 with the estimator fixed for unmodelled ground (sand-aware propagation, adaptive
    fading) and the stay-alive rule replaced by guarded moves (worst-case energy sufficiency over
    unverified ground, probing in short checked steps)."""


class EKF_fading_sandfilter_sandodo_bayessand_guarded_aimdisc_turncost_window_MPC(
        _GuardedMove, _WindowAware, _AimDisc, _TurnCost, _BayesSand, _FadingFilter, _SandAwareFilter,
        _SandOdometer, EKF_MPC):
    """28: 27 plus 26's Bayesian unmapped-sand belief priced on the way home: the cautious twin,
    which gives up the thin third target unless clean ground driven so far makes it safe."""


class EKF_fading_sandfilter_sandodo_armedguard_aimdisc_turncost_window_MPC(
        _ArmedGuard, _WindowAware, _AimDisc, _TurnCost, _Unverified, _FadingFilter, _SandAwareFilter,
        _SandOdometer, EKF_MPC):
    """34: 27 whose guarded moves run only when a probe is free (a round trip of delay costs the
    plan no value and still fits the horizon, as on every way home); otherwise 24's stay-alive
    rule. Keeps 24's score on the published profiles and 27's survival on hidden sand."""

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
# Real-time clock (lightlag_dynamic/realtime.py; an optional extra, not adopted)
# =============================================================================================

class EKF_latencyaware_MPC(LogMixin, RealTimeKalmanMPC):
    """29: controller 1 for the real-time clock (lightlag_dynamic/kf_mpc_rt.py). It measures its
    own lag and decides that much earlier; with no lag (turn-based play, as in the swarm) it
    sends exactly controller 1's commands."""


# =============================================================================================
# Mars-operations tweaks (mars.py; a sandbox experiment, not a rules decision)
# =============================================================================================
# The layer and the executive live in mars.py with the tweaks they answer; with no slip check
# in the rules (the swarm's ScenarioEnvironment) each class plays exactly like its parent.

from .mars import executive as _mars_executive, slip_aware as _mars_slip_aware  # noqa: E402


class EKF_slipaware_MPC(_mars_slip_aware(EKF_MPC)):
    """30: controller 1 with the slip-check-aware layer."""


class EKF_slipaware_sandodo_stayalive_aimdisc_turncost_window_MPC(
        _mars_slip_aware(EKF_sandodo_stayalive_aimdisc_turncost_window_MPC)):
    """31: controller 24 with the slip-check-aware layer."""


class EKF_executive_slipaware_MPC(_mars_executive(EKF_MPC)):
    """32: controller 1 with the layer and the executive (nominal / recover modes)."""


class EKF_executive_slipaware_sandodo_stayalive_aimdisc_turncost_window_MPC(
        _mars_executive(EKF_sandodo_stayalive_aimdisc_turncost_window_MPC)):
    """33: controller 24 with the layer and the executive (nominal / recover modes)."""


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
_R4 = "2026-11-14, literature round (beat the static-robust reference on every front)"
_WHY26 = ("Sölvi's static robust plan still won on noisy maps with hidden sand. Adaptive robust routing "
          "(arXiv 2204.10913) and chance-constrained rover planning suggest pricing a belief, not the worst "
          "case. Result, held-out seeds 400-419: noisy with one / two hidden patches 71% / 70% (24: 69% / "
          "54%), no deaths there, but clean noisy maps 75% (24: 90%): the prior gives up the thin third "
          "target, -2.5 vs controller 1 overall (-3.4 to -1.7). Traces then showed the estimator, not the "
          "budget, failing (see 27).")
_WHY27 = ("Traces of 24 and 26 on hidden sand: a drive across unmapped sand was propagated as bedrock, its "
          "visual odometry failed the 3-sigma gate and was dropped, and the filter stayed over 1 m off at "
          "8 sigma (seed 2: a missed sample, parked 0.76 m from base believing 0.13 m). Fixes: sand-aware "
          "propagation from the exact battery reading (proprioceptive terrain classification); adaptive "
          "fading on the position fixes' innovations (Mehra 1972; Xia et al. 1994); guarded moves, worst-"
          "case energy sufficiency over unverified ground with short checked steps (safety filters, arXiv "
          "2306.15115, 2310.06933). Result, held-out seeds 400-419: +2.7 over controller 1 (+2.2 to +3.4), "
          "+0.8 over 24 (+0.5 to +1.2), +27.9 over solvi_reference; noisy with one / two hidden patches "
          "80% / 71% vs 73% / 68% for Sölvi, never dead there (Sölvi 2% / 7%); higher share than Sölvi in "
          "190 of 192 cells.")
_WHY28 = ("The cautious twin of 27. Result, held-out seeds 400-419: 75% and home in every noisy episode, "
          "with or without hidden sand (Sölvi 74% / 73% / 68%, deaths up to 7%), but clean noisy maps "
          "75% against 92% for 27, so about 5 points below 27 overall (-2.5 vs controller 1, +22.7 over "
          "solvi_reference). For when the score must never fall below the static robust plan.")

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
register("EKF_sandodo_bayessand_stayalive_aimdisc_turncost_window_MPC_manh_controller_26",
         _ours(EKF_sandodo_bayessand_stayalive_aimdisc_turncost_window_MPC), built=_R4,
         note="24 + Bayesian unmapped-sand belief (Beta prior in metres) priced on every way home",
         why=_WHY26)
register("EKF_fading_sandfilter_sandodo_guarded_aimdisc_turncost_window_MPC_manh_controller_27",
         _ours(EKF_fading_sandfilter_sandodo_guarded_aimdisc_turncost_window_MPC), built=_R4,
         note="24 + sand-aware filter propagation + adaptive fading + guarded moves",
         why=_WHY27)
register("EKF_fading_sandfilter_sandodo_bayessand_guarded_aimdisc_turncost_window_MPC_manh_controller_28",
         _ours(EKF_fading_sandfilter_sandodo_bayessand_guarded_aimdisc_turncost_window_MPC), built=_R4,
         note="27 + 26's Bayesian unmapped-sand pricing on the way home",
         why=_WHY28)
register("EKF_latencyaware_MPC_manh_controller_29", _ours(EKF_latencyaware_MPC),
         built="2026-11-14, real-time clock (optional extra)",
         note="controller 1 for the real-time clock: measures its own lag (median of the last five uplinks' "
              "sent_tick minus its decision tick) and decides that much earlier; turn-based it equals 1 exactly",
         why="On the real-time clock ticks pass while a controller thinks, and controller 1 then lets the queue "
             "run empty; deciding early keeps commands arriving as the queue empties. The swarm plays "
             "turn-based, where 29 equals 1: the gain shows only on the real-time clock. Fresh seeds 600-639 "
             "at 1 tick of thinking per call: +4.0 points on rush_noisy and +8.9 on rush, never worse. A "
             "proposal, not adopted (docs/lightlag-dynamic-pilot.md, 'Real-time-aware reference').")
_R5 = "2026-11-14, Mars-operations tweaks (sandbox)"
_SWARM_NOTE = (" The swarm plays without a slip check, where it equals its parent exactly; results come from "
               "manh_controllers/mars.py's MarsEnvironment (docs/lightlag-dynamic-pilot.md, 'Mars-operations "
               "tweaks'). A proposal, not a rules decision.")
register("EKF_slipaware_MPC_manh_controller_30", _ours(EKF_slipaware_MPC), built=_R5,
         note="1 plus the slip-check-aware layer: a Bayesian trip chance per terrain from the filter's slip belief "
              "and every slip stop seen; routes around terrain above 10%, drops targets reachable only through "
              "terrain above 30%",
         why="With the onboard slip check (stop + discard the queue above a slip limit), 1 replans straight back "
             "into the sand that stopped it: 6-9 stops per episode and stranded. Fresh seeds 800-879, noisy, "
             "limit 0.35: 54.1% -> 75.0%, home 51 -> 80 of 80." + _SWARM_NOTE)
register("EKF_slipaware_sandodo_stayalive_aimdisc_turncost_window_MPC_manh_controller_31",
         _ours(EKF_slipaware_sandodo_stayalive_aimdisc_turncost_window_MPC), built=_R5,
         note="24 plus the slip-check-aware layer (as 30)",
         why="The same layer on the best controller at the time. Fresh seeds 800-879, noisy: limit 0.40 "
             "74.8% -> 78.8% (home 67 -> 74 of 80), limit 0.35 55.3% -> 75.0% (51 -> 80)." + _SWARM_NOTE)
register("EKF_executive_slipaware_MPC_manh_controller_32", _ours(EKF_executive_slipaware_MPC), built=_R5,
         note="30 plus an executive: explicit modes switched by telemetry events (nominal / recover); recover "
              "backs out by one-segment drives, each sent after the previous executed, when that beats driving "
              "on; nominal drops a target only with evidence about its terrain",
         why="The layer alone still crawled along sand edges (12 stops, nothing sampled) and wrote off sand "
             "targets on the prior. Fresh seeds 900-979, noisy: limit 0.40 78.1% -> 86.6%, 0.35 75.0% -> 85.0%, "
             "home 80 of 80; never below 30." + _SWARM_NOTE)
register("EKF_executive_slipaware_sandodo_stayalive_aimdisc_turncost_window_MPC_manh_controller_33",
         _ours(EKF_executive_slipaware_sandodo_stayalive_aimdisc_turncost_window_MPC), built=_R5,
         note="31 plus the executive (as 32)",
         why="Best on the slip check. Fresh seeds 900-979, noisy: limit 0.40 80.3% -> 88.8% (home 77 -> 80 of 80), "
             "0.35 75.0% -> 85.9%; rush_noisy +0.6 to +0.7 at 0.35-0.42; never below 31." + _SWARM_NOTE)
_R6 = "2026-11-14, armed guard (27's guarded moves only when a probe is free)"
register("EKF_fading_sandfilter_sandodo_armedguard_aimdisc_turncost_window_MPC_manh_controller_34",
         _ours(EKF_fading_sandfilter_sandodo_armedguard_aimdisc_turncost_window_MPC), built=_R6,
         note="27 with the guarded moves armed only when a probe is free: one telemetry round trip of delay "
              "costs the current plan no value and still fits the horizon (always so on the way home); "
              "otherwise 24's stay-alive rule",
         why="The ablation of 27 showed its guarded moves are the whole plain-profile cost (-3.3 points at "
             "delay 3 on plain rush: every probe waits a round trip) while being worth +6.4 with hidden sand. "
             "Running the guard only when the wait costs the plan no value keeps both. Chosen on development "
             "data (suites on seeds 0-19, plain rush on 700-899) over 'way home only' and over an extra "
             "proven-unmapped-sand trigger, which added nothing. One final check on fresh seeds (suites "
             "5000-5059, plain rush 5060-5259): suites +3.2 over controller 1 (+2.7 to +3.8), +1.2 over 24 "
             "(+0.9 to +1.4), +0.5 over 27 (+0.4 to +0.7), +27.7 over solvi_reference; plain rush +0.2 over 24 "
             "(-0.0 to +0.5, a tie), +1.8 over 27 (+1.5 to +2.1), +1.4 over controller 1; hidden sand 63.3% "
             "against 63.2% for 27 and 51.8% for 24 (dead 4% / 3% / 17%). Not ahead in every cell: below 24 in "
             "51 of 192 suite cells (worst -3.3) and below solvi_reference in the two noisy cells with two "
             "hidden patches, the limit described in the README.")
for _name in ("solvi_reference", "kristjan_reference", "blind", "cautious"):
    register(_name, _team(_name), kind="team", logged=False, note="team controller, imported unchanged",
             why="comparison only")
