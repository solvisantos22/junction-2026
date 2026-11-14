"""Estimators used by the Manh controllers (needs numpy).

ParticleFilter   bootstrap SIR filter over [x, y, heading bias, slip_bedrock, slip_sand]
                 (SSY345 L8): exact uniform priors, slip clipping, multimodal wheel spins,
                 failed/taken samples as exact "outside/inside the radius" likelihoods,
                 systematic resampling at ESS < N/2, Liu-West shrinkage for the static slips.
rts_smooth       Rauch-Tung-Striebel smoother (SSY345 L7) over recorded EKF steps; the iterated
                 smoother controller uses it to relinearise its history.
cubature_drive   cubature (sigma-point) prediction of one drive (SSY345 L6).
"""

import math

import numpy as np

VAR_FLOOR = 1e-6
TINY = math.log(1e-4)


class ParticleFilter:
    def __init__(self, rules, start, sand_rects, rough_cells=(), cell_m=1.0, n=500, seed=0,
                 slip_walk=0.0, liu_west=0.97, map_size=(40.0, 40.0)):
        sensing = rules.get("sensing") or {}
        self.terrains = sorted(rules["slip_ranges"])
        assert self.terrains == ["bedrock", "sand"], self.terrains
        self.lo = np.array([rules["slip_ranges"][t][0] for t in self.terrains])
        self.hi = np.array([rules["slip_ranges"][t][1] for t in self.terrains])
        self.seg = rules["drive_integration_metres"]
        self.noise = max(abs(v) for v in rules["slip_noise"])
        self.sig_pos = max(sensing.get("position_noise_m", 0.0), 0.02)
        self.vo_rel = max(sensing.get("visual_odometry_noise", 0.0), 0.01)
        by = sensing.get("visual_odometry_noise_by_terrain")
        self.vo_by = None if not by else np.array([max(by[t], 0.01) for t in self.terrains])
        self.walk = math.radians(sensing.get("heading_bias_walk_deg", 0.0))
        self.head = math.radians(sensing.get("heading_noise_deg", 0.0))
        bias = math.radians(sensing.get("heading_bias_deg", 0.0))
        rough = rules.get("roughness") or {}
        self.spin_chance = rough.get("spin_chance", 0.0)
        self.spin_lo, self.spin_hi = rough.get("spin_wheel_m", (0.0, 0.0))
        self.jolt = rough.get("jolt_m", 0.0)
        self.cell_m = cell_m
        w, h = map_size
        self.grid = np.zeros((int(math.ceil(w / cell_m)) + 2, int(math.ceil(h / cell_m)) + 2), bool)
        for cx, cy in rough_cells:
            if 0 <= cx < self.grid.shape[0] and 0 <= cy < self.grid.shape[1]:
                self.grid[cx, cy] = True
        self.has_rough = bool(len(rough_cells))
        self.sand = np.array([[r["x1"], r["y1"], r["x2"], r["y2"]] for r in sand_rects], float)
        self.n = n
        self.rng = np.random.default_rng(seed)
        self.x = np.full(n, float(start[0]))
        self.y = np.full(n, float(start[1]))
        self.b = self.rng.uniform(-bias, bias, n) if bias > 0 else np.zeros(n)
        self.s = self.rng.uniform(self.lo, self.hi, (n, 2))
        self.logw = np.zeros(n)
        self.slip_walk = slip_walk
        self.a = liu_west
        self.last_ground = None
        self.last_by = None
        self.resamples = 0
        self.ess_log = []

    # ---- model -----------------------------------------------------------------------------
    def _terrain(self, x, y):
        if len(self.sand) == 0:
            return np.zeros(len(x), int)
        s = self.sand
        inside = ((x[:, None] >= s[None, :, 0]) & (x[:, None] <= s[None, :, 2])
                  & (y[:, None] >= s[None, :, 1]) & (y[:, None] <= s[None, :, 3]))
        return inside.any(axis=1).astype(int)

    def _rough(self, cx, cy):
        cx = np.clip(cx, 0, self.grid.shape[0] - 1)
        cy = np.clip(cy, 0, self.grid.shape[1] - 1)
        return self.grid[cx, cy]

    def predict(self, heading_deg, wheel):
        n, rng = self.n, self.rng
        if self.walk > 0:
            self.b = self.b + rng.normal(0.0, self.walk, n)
        if self.slip_walk > 0:
            self.s = np.clip(self.s + rng.normal(0.0, self.slip_walk, (n, 2)), self.lo, self.hi)
        theta = math.radians(heading_deg) + self.b
        if self.head > 0:
            theta = theta + rng.normal(0.0, self.head, n)
        ux, uy = np.cos(theta), np.sin(theta)
        nz = rng.uniform(-self.noise, self.noise, n)
        remaining = np.full(n, float(wheel))
        ground = np.zeros(n)
        by = np.zeros((n, 2))
        idx = np.arange(n)
        cx = np.floor(self.x / self.cell_m).astype(int)
        cy = np.floor(self.y / self.cell_m).astype(int)
        for _ in range(int(wheel / self.seg) + 40):
            active = remaining > 1e-9
            if not active.any():
                break
            piece = np.where(active, np.minimum(self.seg, remaining), 0.0)
            t = self._terrain(self.x, self.y)
            slip = np.clip(self.s[idx, t] + nz, 0.0, 0.9)
            step = piece * (1.0 - slip)
            self.x = self.x + ux * step
            self.y = self.y + uy * step
            ground += step
            by[idx, t] += piece
            remaining -= piece
            if self.has_rough:
                ncx = np.floor(self.x / self.cell_m).astype(int)
                ncy = np.floor(self.y / self.cell_m).astype(int)
                entered = active & ((ncx != cx) | (ncy != cy)) & self._rough(ncx, ncy)
                cx, cy = ncx, ncy
                if entered.any():
                    k = entered.sum()
                    jolt = rng.normal(0.0, self.jolt, k)
                    self.x[entered] -= uy[entered] * jolt
                    self.y[entered] += ux[entered] * jolt
                    spins = rng.random(k) < self.spin_chance
                    amount = np.where(spins, rng.uniform(self.spin_lo, self.spin_hi, k), 0.0)
                    sub = remaining[entered]
                    remaining[entered] = sub - np.minimum(amount, sub)
        self.last_ground, self.last_by = ground, by

    # ---- measurements ------------------------------------------------------------------------
    def update_position(self, z):
        d2 = (z[0] - self.x) ** 2 + (z[1] - self.y) ** 2
        self.logw += -d2 / (2.0 * self.sig_pos ** 2)
        self._normalise()

    def update_visual_odometry(self, measured):
        g = self.last_ground
        if g is None:
            return
        if self.vo_by is not None:
            total = np.maximum(self.last_by.sum(axis=1), 1e-9)
            rel = (self.last_by @ self.vo_by) / total
        else:
            rel = self.vo_rel
        sd = rel * np.maximum(g, 0.05)
        self.logw += -0.5 * ((measured - g) / sd) ** 2 - np.log(sd)
        self._normalise()

    def update_outside(self, points, radius):
        """A failed sample: the rover is not within `radius` of any of `points`."""
        if not points:
            return
        p = np.array(points, float)
        d2 = (self.x[:, None] - p[None, :, 0]) ** 2 + (self.y[:, None] - p[None, :, 1]) ** 2
        self.logw[(d2 <= radius * radius).any(axis=1)] += TINY
        self._normalise()

    def update_inside(self, point, radius):
        """A sample taken at `point`: the rover is within `radius` of it."""
        d2 = (self.x - point[0]) ** 2 + (self.y - point[1]) ** 2
        self.logw[d2 > radius * radius] += TINY
        self._normalise()

    # ---- resampling and moments ----------------------------------------------------------------
    def _normalise(self):
        self.logw -= self.logw.max()

    def weights(self):
        w = np.exp(self.logw)
        return w / w.sum()

    def ess(self):
        w = self.weights()
        return 1.0 / float((w * w).sum())

    def maybe_resample(self):
        e = self.ess()
        self.ess_log.append(e)
        if e >= self.n / 2:
            return False
        w = self.weights()
        positions = (self.rng.random() + np.arange(self.n)) / self.n
        idx = np.searchsorted(np.cumsum(w), positions)
        idx = np.minimum(idx, self.n - 1)
        self.x, self.y, self.b, self.s = self.x[idx], self.y[idx], self.b[idx], self.s[idx]
        self.logw = np.zeros(self.n)
        # Liu-West shrinkage keeps the static slips diverse without inflating their spread.
        a = self.a
        h = math.sqrt(max(1.0 - a * a, 0.0))
        mean, sd = self.s.mean(axis=0), self.s.std(axis=0)
        self.s = np.clip(a * self.s + (1 - a) * mean + self.rng.normal(0.0, 1.0, self.s.shape) * h * sd,
                         self.lo, self.hi)
        bm, bs = self.b.mean(), self.b.std()
        self.b = a * self.b + (1 - a) * bm + self.rng.normal(0.0, h * bs, self.n)
        self.x = self.x + self.rng.normal(0.0, 0.01, self.n)
        self.y = self.y + self.rng.normal(0.0, 0.01, self.n)
        self.resamples += 1
        return True

    def moments(self):
        w = self.weights()
        state = np.column_stack([self.x, self.y, self.b, self.s[:, 0], self.s[:, 1]])
        mean = w @ state
        d = state - mean
        cov = (d * w[:, None]).T @ d + np.eye(5) * VAR_FLOOR
        return mean.tolist(), cov.tolist()


def rts_smooth(steps):
    """RTS over recorded EKF steps.

    steps: list of dicts per packet, in order, each with
      m_pred, P_pred  (prior at this packet, after the drive prediction; = previous filtered if none)
      F               (transition Jacobian from the previous filtered state; identity if no drive)
      m, P            (filtered, after this packet's updates)
    Returns smoothed (m, P) per packet.
    """
    T = len(steps)
    ms = [None] * T
    Ps = [None] * T
    ms[-1] = np.array(steps[-1]["m"])
    Ps[-1] = np.array(steps[-1]["P"])
    for t in range(T - 2, -1, -1):
        m, P = np.array(steps[t]["m"]), np.array(steps[t]["P"])
        F = np.array(steps[t + 1]["F"])
        mp, Pp = np.array(steps[t + 1]["m_pred"]), np.array(steps[t + 1]["P_pred"])
        G = P @ F.T @ np.linalg.pinv(Pp)
        ms[t] = m + G @ (ms[t + 1] - mp)
        Ps[t] = P + G @ (Ps[t + 1] - Pp) @ G.T
    return [(a.tolist(), b.tolist()) for a, b in zip(ms, Ps)]


def cubature_drive(f, mean, cov, heading_deg, wheel, terrain_at, sand_rects):
    """Cubature (sigma-point) prediction of one drive (SSY345 L6: CKF/UKF).

    Augmented state [x, y, bias, slip_bedrock, slip_sand, bias step, heading noise, slip noise]
    goes through the drive kinematics point by point (no linearisation). Returns the predicted
    mean and covariance, the predicted visual-odometry distance and its cross-covariance with the
    state, and the number of rough-cell entries along the mean path.
    """
    n = len(mean)
    walk = f.q_walk
    head = f.q_head
    slip_noise = f.q_slip
    aug_mean = np.concatenate([np.asarray(mean, float), np.zeros(3)])
    aug_cov = np.zeros((n + 3, n + 3))
    aug_cov[:n, :n] = np.asarray(cov, float)
    aug_cov[n, n], aug_cov[n + 1, n + 1], aug_cov[n + 2, n + 2] = walk, head, slip_noise
    d = n + 3
    try:
        root = np.linalg.cholesky(aug_cov + np.eye(d) * 1e-12)
    except np.linalg.LinAlgError:
        w, v = np.linalg.eigh(aug_cov)
        root = v @ np.diag(np.sqrt(np.maximum(w, 0.0)))
    pts = np.concatenate([aug_mean + math.sqrt(d) * root.T, aug_mean - math.sqrt(d) * root.T])
    k = len(pts)
    x, y = pts[:, 0].copy(), pts[:, 1].copy()
    bias = pts[:, 2] + pts[:, n]
    theta = math.radians(heading_deg) + bias + pts[:, n + 1]
    ux, uy = np.cos(theta), np.sin(theta)
    slips = np.clip(pts[:, 3:5], 0.0, 0.9)
    nz = pts[:, n + 2]
    sand = np.array([[r["x1"], r["y1"], r["x2"], r["y2"]] for r in sand_rects], float)
    seg = f.segment
    remaining = np.full(k, float(wheel))
    ground = np.zeros(k)
    cell_m = f.cell_m
    cx, cy = np.floor(x / cell_m).astype(int), np.floor(y / cell_m).astype(int)
    bumps = np.zeros(k)
    idx = np.arange(k)
    for _ in range(int(wheel / seg) + 40):
        active = remaining > 1e-9
        if not active.any():
            break
        piece = np.where(active, np.minimum(seg, remaining), 0.0)
        if len(sand):
            t = ((x[:, None] >= sand[None, :, 0]) & (x[:, None] <= sand[None, :, 2])
                 & (y[:, None] >= sand[None, :, 1]) & (y[:, None] <= sand[None, :, 3])).any(axis=1).astype(int)
        else:
            t = np.zeros(k, int)
        slip = np.clip(slips[idx, t] + nz, 0.0, 0.9)
        step = piece * (1.0 - slip)
        x, y = x + ux * step, y + uy * step
        ground += step
        remaining -= piece
        if f.rough_cells:
            ncx, ncy = np.floor(x / cell_m).astype(int), np.floor(y / cell_m).astype(int)
            moved = active & ((ncx != cx) | (ncy != cy))
            for i in np.nonzero(moved)[0]:
                if (int(ncx[i]), int(ncy[i])) in f.rough_cells:
                    bumps[i] += 1
                    remaining[i] -= min(remaining[i], f.spin_mean)
            cx, cy = ncx, ncy
    new = np.column_stack([x, y, bias, pts[:, 3], pts[:, 4]])
    m = new.mean(axis=0)
    dev = new - m
    P = dev.T @ dev / k
    g_mean = ground.mean()
    gd = ground - g_mean
    Pxg = dev.T @ gd / k
    Pgg = float(gd @ gd / k)
    b = float(bumps.mean())
    if b > 0:  # wheel spins and jolts as additive noise along and across the drive
        th = math.radians(heading_deg) + m[2]
        u = np.array([math.cos(th), math.sin(th)])
        lat = np.array([-u[1], u[0]])
        P[:2, :2] += b * f.spin_var * np.outer(u, u) + b * f.jolt_var * np.outer(lat, lat)
    P = (P + P.T) / 2 + np.eye(n) * VAR_FLOOR
    return m.tolist(), P.tolist(), g_mean, Pxg.tolist(), Pgg
