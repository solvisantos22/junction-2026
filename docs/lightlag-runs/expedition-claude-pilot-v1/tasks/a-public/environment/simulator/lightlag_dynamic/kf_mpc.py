"""Kalman filter + receding-horizon (MPC-style) reference for the dynamic pilot.

Estimation: an extended Kalman filter over

    [x, y, heading bias (rad), slip on bedrock, slip on sand]

runs on every delivered packet, in order. A drive is the prediction step (the published
kinematics with the estimated slip and bias); the position fix and the visual-odometry
distance are the measurement updates. The heading bias is a random walk, so the filter
tracks it as the drift wanders. A failed sample is a measurement too: the rover is outside
the target radius, applied as a moment-matched (truncated-Gaussian) pseudo-measurement, so
the controller does not keep sampling from a spot it wrongly believes is inside.

Delay: the filter sits at the newest packet. Commands already sent but not yet seen are
pushed through the same model, mean and covariance, to the tick the next command will
execute (dead-time compensation in the Smith-predictor sense, now with uncertainty).

Control: every decision re-plans the best target sequence from that predicted state (the
same exhaustive search as the dynamic reference: which targets, in which order, home),
sends only the next leg, and plans again later: a receding horizon over a mixed-integer
choice. Fixed margins become chance constraints on the predicted covariance:
  * a leg ends with a sample when the chance of arriving inside the target radius is high
    enough: 90% when there is time to spare (stopping only costs ticks), 60% under time
    pressure, meaning targets with deadlines or little slack before the planned return (a
    miss costs less than the stop); otherwise the rover stops for fixes first;
  * near a target it samples at once when the chance is 90%, or 70% with energy to spare
    (a miss costs one tick); otherwise it drives closer or holds still briefly for fixes;
  * with time to spare, it waits to see a sample land unless it is 97% sure, so a miss is
    retried from close by rather than found out on the way home;
  * energy is budgeted with slip at its mean plus 1.5 standard deviations;
  * every heading is corrected by the estimated bias.
On bumpy ground (experimental) the filter uses the published rough cells: it expects the
average wheel spin, feeds it forward into the commanded distance, widens the covariance for
spins and jolts, and gates visual-odometry outliers so a spin is not learned as slip.

Only the five public tools and the published rules are used. Without sensing noise the
filter trusts each fix, so the controller also runs on the noiseless profiles.
"""

import math
import random

from .controllers import SAMPLE, Controller, Leg

# Decision settings. P_COMMIT, P_TRY, SAFE_SIGMAS and MAX_HOLD were tuned on development seeds
# 0-9 (noisy and rush_noisy, delays 0/3/5, bumpiness 0 and 0.1) over a 108-point grid, keeping
# only settings that returned home in every run; the score surface is flat (about 2 points).
# CONFIRM_BELOW and USE_FAILED_SAMPLES were then checked on development seeds 0-19 and held-out
# seeds 400-419 over every noise and bumpiness setting; both helped on both seed sets.
P_SAMPLE = 0.9         # chance of being inside the target radius that counts as sure
P_TRY = 0.7            # below P_SAMPLE but above this, a sample attempt beats holding still:
                       # a miss costs one tick and the sampling energy, holding costs ticks too
P_COMMIT = 0.6         # under time pressure a leg ends with a sample unless the chance is below this
TIME_TO_SPARE = 3      # confirmation stops of slack that count as "time to spare" (then P_SAMPLE applies)
CONFIRM_BELOW = 0.97   # with time to spare, wait to see a sample land unless at least this sure
P_HOME = 0.9           # required chance of being inside the base radius at the end
CLOSE_ENOUGH = 0.2     # metres: closer than this, holding for fixes beats another drive
MAX_HOLD = 2           # ticks the controller holds still for fixes before taking its chance
SAFE_SIGMAS = 1.5      # slip budgeted at mean + this many standard deviations
GATE = 9.0             # reject a visual-odometry reading whose squared innovation exceeds 3 sigma
USE_FAILED_SAMPLES = True  # a failed sample is a measurement: the rover is outside the radius
VAR_FLOOR = 1e-6

# Fixed standard-normal pairs: a deterministic particle cloud for chance constraints.
_CLOUD = [(g.gauss(0.0, 1.0), g.gauss(0.0, 1.0)) for g in [random.Random("lightlag-kf-mpc")]
          for _ in range(400)]


# ---- small dense linear algebra (5 x 5 at most, standard library only) -----------------
def _mm(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(len(b))) for j in range(len(b[0]))]
            for i in range(len(a))]


def _t(a):
    return [list(row) for row in zip(*a)]


def _eye(n):
    return [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]


def _copy(a):
    return [row[:] for row in a]


def _inverse(s):
    if len(s) == 1:
        return [[1.0 / s[0][0]]]
    (a, b), (c, d) = s
    det = a * d - b * c
    return [[d / det, -b / det], [-c / det, a / det]]


def _cloud(mean_xy, cov_xy):
    """The fixed particle cloud, shaped to a 2-D Gaussian (Cholesky transform)."""
    a, b, c = cov_xy[0][0], cov_xy[0][1], cov_xy[1][1]
    l11 = math.sqrt(max(a, 0.0))
    l21 = b / l11 if l11 > 1e-12 else 0.0
    l22 = math.sqrt(max(c - l21 * l21, 0.0))
    return [(mean_xy[0] + l11 * z1, mean_xy[1] + l21 * z1 + l22 * z2) for z1, z2 in _CLOUD]


def inside_probability(mean_xy, cov_xy, point, radius):
    """Chance that the true position lies within `radius` of `point` (particle estimate)."""
    r2 = radius * radius
    hits = sum(1 for x, y in _cloud(mean_xy, cov_xy)
               if (x - point[0]) ** 2 + (y - point[1]) ** 2 <= r2)
    return hits / len(_CLOUD)


class DriveFilter:
    """Extended Kalman filter for position, heading bias and per-terrain slip."""

    def __init__(self, rules, start):
        sensing = rules.get("sensing") or {}
        self.terrains = sorted(rules["slip_ranges"])
        self.index = {name: 3 + i for i, name in enumerate(self.terrains)}
        self.ranges = {name: tuple(bounds) for name, bounds in rules["slip_ranges"].items()}
        self.segment = rules["drive_integration_metres"]
        self.r_pos = max(VAR_FLOOR, sensing.get("position_noise_m", 0.0) ** 2)
        self.vo_rel = sensing.get("visual_odometry_noise", 0.0)
        self.q_walk = math.radians(sensing.get("heading_bias_walk_deg", 0.0)) ** 2
        self.q_head = math.radians(sensing.get("heading_noise_deg", 0.0)) ** 2
        noise = max(abs(v) for v in rules["slip_noise"])
        self.q_slip = noise * noise / 3.0  # uniform per-drive slip noise
        bias = math.radians(sensing.get("heading_bias_deg", 0.0))
        rough = rules.get("roughness") or {}
        self.rough_cells, self.cell_m = frozenset(), rough.get("cell_m", 1.0)
        lo, hi = rough.get("spin_wheel_m", (0.0, 0.0))
        chance = rough.get("spin_chance", 0.0)
        self.spin_mean = chance * (lo + hi) / 2           # expected wheel metres lost per rough cell
        second = (lo * lo + lo * hi + hi * hi) / 3        # E[L^2] for L uniform in [lo, hi]
        self.spin_var = chance * second - self.spin_mean ** 2
        self.jolt_var = rough.get("jolt_m", 0.0) ** 2
        n = 3 + len(self.terrains)
        self.mean = [float(start[0]), float(start[1]), 0.0] + [
            sum(self.ranges[t]) / 2 for t in self.terrains]
        self.cov = [[0.0] * n for _ in range(n)]
        self.cov[0][0] = self.cov[1][1] = VAR_FLOOR  # the tick-0 briefing is exact
        self.cov[2][2] = bias * bias / 3.0 + VAR_FLOOR
        for t in self.terrains:
            lo, hi = self.ranges[t]
            self.cov[self.index[t]][self.index[t]] = (hi - lo) ** 2 / 12.0 + VAR_FLOOR

    def set_rough_cells(self, cells, cell_m):
        self.rough_cells, self.cell_m = frozenset(tuple(c) for c in cells), cell_m

    def cell(self, x, y):
        return (int(x // self.cell_m), int(y // self.cell_m))

    def slip(self, terrain, mean=None):
        lo, hi = self.ranges[terrain]
        value = (self.mean if mean is None else mean)[self.index[terrain]]
        return min(hi, max(lo, value))

    def slip_sigma(self, terrain):
        i = self.index[terrain]
        return math.sqrt(max(self.cov[i][i], 0.0))

    def propagate(self, mean, cov, heading_deg, wheel, terrain_at):
        """Prediction step for one drive. Returns mean, covariance, wheel metres by terrain."""
        n = len(mean)
        cov = _copy(cov)
        cov[2][2] += self.q_walk  # the bias takes its random-walk step before the drive
        theta = math.radians(heading_deg) + mean[2]
        ux, uy = math.cos(theta), math.sin(theta)
        x, y = mean[0], mean[1]
        by_terrain = {t: 0.0 for t in self.terrains}
        ground, remaining = 0.0, wheel
        cell, bumps = self.cell(x, y), 0
        while remaining > 1e-9:
            piece = min(self.segment, remaining)
            terrain = terrain_at(x, y)
            step = piece * (1.0 - self.slip(terrain, mean))
            x, y = x + ux * step, y + uy * step
            by_terrain[terrain] += piece
            ground += step
            remaining -= piece
            entered = self.cell(x, y)
            if entered != cell:
                cell = entered
                if cell in self.rough_cells:
                    bumps += 1
                    remaining -= min(remaining, self.spin_mean)  # expected spin: wheel, no progress
        jac = _eye(n)
        jac[0][2], jac[1][2] = -ground * uy, ground * ux
        for t in self.terrains:
            i = self.index[t]
            jac[0][i], jac[1][i] = -by_terrain[t] * ux, -by_terrain[t] * uy
        cov = _mm(_mm(jac, cov), _t(jac))
        lateral = ground * ground * self.q_head + bumps * self.jolt_var
        along = wheel * wheel * self.q_slip + bumps * self.spin_var
        cov[0][0] += lateral * uy * uy + along * ux * ux
        cov[1][1] += lateral * ux * ux + along * uy * uy
        cov[0][1] += (along - lateral) * ux * uy
        cov[1][0] = cov[0][1]
        new = list(mean)
        new[0], new[1] = x, y
        return new, cov, by_terrain

    def _update(self, rows, residual, variances):
        n = len(self.mean)
        noise_r = (variances if isinstance(variances[0], list) else
                   [[v if i == j else 0.0 for j in range(len(variances))]
                    for i, v in enumerate(variances)])
        pht = _mm(self.cov, _t(rows))
        s = _mm(rows, pht)
        for i in range(len(rows)):
            for j in range(len(rows)):
                s[i][j] += noise_r[i][j]
        gain = _mm(pht, _inverse(s))
        self.mean = [self.mean[i] + sum(gain[i][j] * residual[j] for j in range(len(residual)))
                     for i in range(n)]
        ikh = _eye(n)
        kh = _mm(gain, rows)
        for i in range(n):
            for j in range(n):
                ikh[i][j] -= kh[i][j]
        joseph = _mm(_mm(ikh, self.cov), _t(ikh))
        noise = _mm(_mm(gain, noise_r), _t(gain))
        self.cov = [[(joseph[i][j] + joseph[j][i]) / 2 + noise[i][j] for j in range(n)]
                    for i in range(n)]
        for t in self.terrains:  # keep slip estimates physical
            i = self.index[t]
            self.mean[i] = min(0.9, max(0.0, self.mean[i]))

    def update_position(self, z):
        n = len(self.mean)
        rows = [[1.0 if j == 0 else 0.0 for j in range(n)], [1.0 if j == 1 else 0.0 for j in range(n)]]
        self._update(rows, [z[0] - self.mean[0], z[1] - self.mean[1]], [self.r_pos, self.r_pos])

    def update_outside(self, point, radius):
        """A failed sample: the rover is outside `radius` of `point`.

        The position estimate truncated to outside that disc is moment-matched on the particle
        cloud and applied as a pseudo-measurement z with noise R = 3 P, z chosen so the update
        lands the mean exactly on the truncated mean (the position covariance shrinks to 3/4).
        The heading bias and slip move with it through their cross-covariance.
        """
        m = self.mean[:2]
        p = [[self.cov[0][0], self.cov[0][1]], [self.cov[1][0], self.cov[1][1]]]
        r2 = radius * radius
        outside = [(x, y) for x, y in _cloud(m, p)
                   if (x - point[0]) ** 2 + (y - point[1]) ** 2 > r2]
        if len(outside) >= 20:
            target = (sum(x for x, _ in outside) / len(outside),
                      sum(y for _, y in outside) / len(outside))
        else:  # the estimate is almost surely inside: push it just outside along the ray
            dx, dy = m[0] - point[0], m[1] - point[1]
            norm = math.hypot(dx, dy) or 1.0
            if norm == 1.0 and dx == dy == 0.0:
                dx = 1.0
            target = (point[0] + dx / norm * radius * 1.05, point[1] + dy / norm * radius * 1.05)
        n = len(self.mean)
        rows = [[1.0 if j == 0 else 0.0 for j in range(n)], [1.0 if j == 1 else 0.0 for j in range(n)]]
        residual = [4.0 * (target[0] - m[0]), 4.0 * (target[1] - m[1])]
        self._update(rows, residual, [[3.0 * p[0][0], 3.0 * p[0][1]], [3.0 * p[1][0], 3.0 * p[1][1]]])

    def update_visual_odometry(self, measured, by_terrain):
        """Slip from visual odometry, with a 3-sigma gate so a wheel spin is not read as slip."""
        predicted = sum(w * (1.0 - self.mean[self.index[t]]) for t, w in by_terrain.items())
        row = [0.0] * len(self.mean)
        for t, w in by_terrain.items():
            row[self.index[t]] = -w
        variance = (self.vo_rel * max(measured, 0.05)) ** 2 + VAR_FLOOR
        spread = sum(row[i] * row[j] * self.cov[i][j] for i in range(len(row))
                     for j in range(len(row))) + variance
        if (measured - predicted) ** 2 > GATE * spread:
            return False
        self._update([row], [measured - predicted], [variance])
        return True


class KalmanMPCController(Controller):
    """The dynamic reference's planner, driven by an EKF state and chance constraints."""

    def __init__(self, tools):
        super().__init__(tools, mode="reference")
        rules = tools.rules()
        self.filter = DriveFilter(rules, self.packets[0]["position"])
        self._rough_map()
        self._holds = {}
        self._var0 = VAR_FLOOR
        for packet in self.packets[1:]:
            self._filter(packet)

    # ---- estimation -----------------------------------------------------------------
    def _learn_slip(self, a, b, wheel):
        return None  # the filter learns slip from visual odometry and fixes instead

    def _rough_map(self):
        public = self.tools.map()
        if public.get("rough_cells"):
            self.filter.set_rough_cells(public["rough_cells"], public["rough_cell_m"])

    def absorb(self, packet):
        super().absorb(packet)
        self._filter(packet)

    def _filter(self, packet):
        f = self.filter
        executed = [e["command_id"] for e in packet["events"] if e["type"] == "command_executed"]
        acks = {a["command_id"]: a for a in self.acks}
        ack = acks.get(executed[0]) if executed else None
        kinds = {e["type"] for e in packet["events"]}
        if ack is not None and ack["command"]["action"] == "drive" and packet["wheel_odometry"] > 0:
            f.mean, f.cov, by_terrain = f.propagate(
                f.mean, f.cov, ack["command"]["heading_deg"], packet["wheel_odometry"], self.terrain_at)
            if not kinds & {"safety_stop", "battery_depleted"}:
                f.update_visual_odometry(packet["visual_odometry"], by_terrain)
        f.update_position(packet["position"])
        if USE_FAILED_SAMPLES and "sample_failed" in kinds:
            sampled = set(packet["sampled_targets"])
            open_targets = [t for tid, t in self.targets.items() if tid not in sampled]
            if open_targets:
                nearest = min(open_targets, key=lambda t: math.hypot(t["x"] - f.mean[0], t["y"] - f.mean[1]))
                f.update_outside((nearest["x"], nearest["y"]), self.radius)

    def slip(self, terrain):
        return self.filter.slip(terrain)

    def slip_safe(self, terrain):
        return min(0.9, self.filter.slip(terrain) + SAFE_SIGMAS * self.filter.slip_sigma(terrain))

    def slip_spread(self, terrain):
        return self.filter.slip_sigma(terrain)

    # ---- prediction through the delay --------------------------------------------------
    def predict(self, slot, use_pending=True):
        last = self.packets[-1]
        f = self.filter
        mean, cov = list(f.mean), _copy(f.cov)
        state = {"battery": last["battery"], "sampled": set(last["sampled_targets"]),
                 "alive": last["alive"]}
        queue = {a["execute_tick"]: a["command"] for a in self.acks
                 if a["execute_tick"] > last["tick"] and a["command_id"] not in self.cancelled}
        for t in range(last["tick"] + 1, slot):
            state["battery"] -= self.idle
            if state["battery"] <= 0:
                state["battery"], state["alive"] = 0.0, False
                break
            command = queue.get(t)
            if command and command["action"] == "drive":
                mean, cov, by_terrain = f.propagate(mean, cov, command["heading_deg"],
                                                    command["metres"], self.terrain_at)
                state["battery"] -= sum(w * self.drive_cost * self.multiplier[name]
                                        for name, w in by_terrain.items())
            elif command and command["action"] == "sample":
                state["battery"] -= self.sample_cost
                near = [tid for tid, tg in self.targets.items() if tid not in state["sampled"]
                        and math.hypot(tg["x"] - mean[0], tg["y"] - mean[1]) <= self.radius]
                if near:
                    state["sampled"].add(min(near, key=lambda tid: math.hypot(
                        self.targets[tid]["x"] - mean[0], self.targets[tid]["y"] - mean[1])))
        state.update({"x": mean[0], "y": mean[1], "tick": slot - 1, "bias": mean[2],
                      "cov": [[cov[0][0], cov[0][1]], [cov[1][0], cov[1][1]]]})
        return state

    # ---- legs with bias correction and propagated uncertainty --------------------------
    def leg(self, start, goal):
        path = self.route(start, goal)
        if path is None:
            return None
        f = self.filter
        bias_deg = math.degrees(f.mean[2])
        commands, energy, energy_safe = [], 0.0, 0.0
        variance, ground_total = self._var0, 0.0
        wheel_by = {t: 0.0 for t in f.terrains}
        for a, b in zip(path, path[1:]):
            _, bed, sand = self._segment(a, b)
            if bed + sand < 0.02:
                continue
            wheel_bed = bed / (1 - self.slip("bedrock"))
            wheel_sand = sand / (1 - self.slip("sand"))
            wheel = wheel_bed + wheel_sand
            wheel_by["bedrock"] += wheel_bed
            wheel_by["sand"] += wheel_sand
            energy += self._energy(bed, sand, self.slip)
            energy_safe += self._energy(bed, sand, self.slip_safe)
            bumps = self._rough_entries(a, b)
            if bumps:
                wheel += bumps * f.spin_mean  # feed forward the expected wheel spin
                variance += bumps * (f.spin_var + f.jolt_var)
                per_metre = self.drive_cost * (self.multiplier["bedrock"] * bed
                                               + self.multiplier["sand"] * sand) / (bed + sand)
                energy += bumps * f.spin_mean * per_metre
                energy_safe += (bumps * f.spin_mean + 2 * math.sqrt(bumps * f.spin_var)) * per_metre
            heading = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) - bias_deg
            pieces = max(1, math.ceil(wheel / self.max_metres - 1e-9))
            for _ in range(pieces):
                commands.append({"action": "drive", "heading_deg": round(heading % 360.0, 6),
                                 "metres": round(wheel / pieces, 6)})
                ground = (bed + sand) / pieces
                variance += ground * ground * f.q_head + (wheel / pieces) ** 2 * f.q_slip
            ground_total += bed + sand
        # Correlated parts: bias uncertainty (sideways) and slip uncertainty (along track).
        bias_var = f.cov[2][2] + f.q_walk * len(commands) / 2
        variance += ground_total * ground_total * bias_var
        variance += sum(w * w * f.cov[f.index[t]][f.index[t]] for t, w in wheel_by.items())
        return Leg(commands, energy, energy_safe, math.sqrt(variance))

    def _rough_entries(self, a, b):
        cells = self.filter.rough_cells
        if not cells:
            return 0
        steps = max(1, int(math.dist(a, b) / 0.2))
        seen, count, previous = set(), 0, self.filter.cell(*a)
        for i in range(1, steps + 1):
            c = self.filter.cell(a[0] + (b[0] - a[0]) * i / steps, a[1] + (b[1] - a[1]) * i / steps)
            if c != previous and c in cells and c not in seen:
                seen.add(c)
                count += 1
            previous = c
        return count

    def _end_inside(self, leg, radius):
        sigma = leg.uncertainty
        return 1.0 - math.exp(-radius * radius / (2 * sigma * sigma)) if sigma > 1e-9 else 1.0

    def time_pressure(self):
        """Targets with deadlines, or little slack before the planned arrival home."""
        if any(t.get("deadline_tick") is not None for t in self.targets.values()):
            return True
        end = getattr(self, "plan_end", None)
        return end is not None and end != math.inf and \
            self.horizon - end < TIME_TO_SPARE * (2 * self.k + 2)

    def needs_confirmation(self, leg):
        # Stopping to confirm costs ticks, not energy; a missed sample costs energy and a
        # return. With time to spare, confirm unless sure; under time pressure, commit early.
        threshold = P_COMMIT if self.time_pressure() else P_SAMPLE
        return self._end_inside(leg, self.radius) < threshold

    def confirmation_ticks(self, leg):
        return 2 * self.k + 2  # stop, see the last drive land, plus one more fix

    def home_slack(self):
        # With noise or spins the drive home can fall short: keep time to see it and correct.
        f = self.filter
        uncertain = f.r_pos > VAR_FLOOR or f.q_head > 0 or f.rough_cells
        return 2 * self.k + 2 if uncertain else 0

    # ---- decisions ------------------------------------------------------------------------
    def _energy_to_spare(self, state):
        """A missed sample costs sample_cost; only gamble when the way home stays affordable."""
        home = self.leg((state["x"], state["y"]), self.base)
        need = (home.energy_safe if home else 0.0) + self.idle * (self.horizon - state["tick"])
        return state["battery"] - need - 2 * self.sample_cost > 0

    def _may_hold(self, key, deadline=None):
        first = self._holds.setdefault(key, self.tick)
        if self.tick - first >= MAX_HOLD:
            return False
        slot = self.next_slot()
        if deadline is not None and slot + 1 > deadline:
            return False
        return slot + 1 < self.horizon

    def _sample(self, chance):
        """Send a sample. Below P_SAMPLE it is a try: with time to spare, wait to see it land
        before leaving, so a miss is retried from close by instead of found out on the way home."""
        if self.send([SAMPLE]) and chance < CONFIRM_BELOW and not self.time_pressure():
            self.confirm_tick = self.reserved_until()

    def decide(self):
        slot = self.next_slot()
        if slot > self.horizon:
            return
        state = self.predict(slot)
        if not state["alive"]:
            return
        here, cov = (state["x"], state["y"]), state["cov"]
        self._var0 = max(cov[0][0], cov[1][1], VAR_FLOOR)
        sequence = self.choose(state, slot)
        if sequence:
            target = sequence[0]
            point = (target["x"], target["y"])
            gap = math.dist(here, point)
            chance = inside_probability(here, cov, point, self.radius)
            if chance >= P_SAMPLE or (chance >= P_TRY and self._energy_to_spare(state)):
                self._holds.pop(target["id"], None)
                self._sample(chance)
                return
            if gap <= CLOSE_ENOUGH:
                if self._may_hold(target["id"], target.get("deadline_tick")):
                    return  # hold still: the next fixes shrink the covariance
                self._holds.pop(target["id"], None)
                self._sample(chance)  # out of patience or time: take the chance
                return
            hop = self.leg(here, point)
            if hop is not None and hop.commands:
                if self.needs_confirmation(hop):
                    if self.send(hop.commands):
                        self.confirm_tick = self.reserved_until()
                else:
                    self.send(hop.commands + [SAMPLE])
                return
        # Home: be confidently inside the base radius at the horizon.
        if inside_probability(here, cov, self.base, self.base_radius) >= P_HOME:
            return
        if math.dist(here, self.base) <= CLOSE_ENOUGH:
            return  # nothing better to do than collect more fixes
        hop = self.leg(here, self.base)
        if hop is not None and hop.commands:
            if self.send(hop.commands) and self._end_inside(hop, self.base_radius) < P_HOME:
                self.confirm_tick = self.reserved_until()
