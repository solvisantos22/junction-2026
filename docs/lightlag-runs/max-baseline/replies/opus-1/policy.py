import math
import heapq
import time
import random

TC = {"b": "bedrock", "r": "regolith", "s": "sand", "k": "rocks"}
INF = float("inf")
BASEKEY = "__base__"


def angdiff(a, b):
    d = abs((a - b) % 360.0)
    return 360.0 - d if d > 180.0 else d


def mm4(A, B):
    return [[A[i][0] * B[0][j] + A[i][1] * B[1][j] + A[i][2] * B[2][j] + A[i][3] * B[3][j]
             for j in range(4)] for i in range(4)]


def tr4(A):
    return [[A[j][i] for j in range(4)] for i in range(4)]


class Pilot:
    def __init__(self, tools):
        self.tools = tools
        self.wall0 = time.time()
        self.rnd = random.Random(1234)
        R = tools.rules()
        M = tools.map()
        self.R = R
        self.cell = float(M.get("cell_m", 5.0))
        self.h = [[v / 100.0 for v in row] for row in M["elevation_cm"]]
        self.NYV = len(self.h)
        self.NXV = len(self.h[0])
        self.NX = self.NXV - 1
        self.NY = self.NYV - 1
        self.N = self.NX * self.NY
        self.codes = [list(str(r)) for r in M["terrain"]]
        self.Wm = self.NX * self.cell
        self.Hm = self.NY * self.cell
        ph = R["physics"]
        self.seg = float(ph.get("segment_m", 0.25))
        self.max_tilt = float(ph.get("max_tilt", 0.36))
        rng = ph["slip_base_ranges"]
        self.base_mid = {k: (v[0] + v[1]) / 2.0 for k, v in rng.items()}
        self.base_hi = {k: v[1] + 0.02 for k, v in rng.items()}
        self.gain = dict(ph["slip_grade_gain"])
        self.gain_hi = dict(self.gain)
        sg = R.get("sand_grade_gain")
        if isinstance(sg, dict) and sg.get("range"):
            self.gain_hi["sand"] = max(self.gain_hi.get("sand", 3.5), float(max(sg["range"])))
        self.side = ph["side_slip_gain"]
        self.cost = ph["drive_cost_per_wheel_m"]
        self.climb = float(ph.get("climb_cost_per_m", 2.0))
        self.slip_max = float(ph.get("slip_max", 0.95))
        osc = R.get("onboard_slip_check")
        self.slip_limit = float(osc.get("limit", 2.0)) if isinstance(osc, dict) else 2.0
        self.delay = int(R.get("delay_ticks", 3))
        self.T = int(R.get("max_ticks", 420))
        rp = R.get("relay_passes")
        if isinstance(rp, dict):
            self.period = int(rp.get("period_ticks", 1))
            self.open = int(rp.get("open_ticks", 1))
        else:
            self.period, self.open = 1, 1
        self.cap = float(R.get("battery_capacity", 100.0))
        self.idle = float(R.get("idle_cost", 0.15))
        self.sample_cost = float(R.get("sample_cost", 2.0))
        self.peak = float(R.get("solar_peak", 2.8))
        self.margin = float(R.get("sun_margin_ticks", 56))
        er = R.get("solar_efficiency_range", [0.8, 1.0])
        self.eff = float(er[0])
        self.eff_max = float(er[1])
        tcd = R.get("turn_cost_per_degree", 0.0)
        self.turn_c = float(tcd) if isinstance(tcd, (int, float)) else 0.0
        sens = R.get("sensing", {})
        self.pos_sigma = float(sens.get("position_noise_m", 2.0))
        self.vo_by = sens.get("visual_odometry_noise_by_terrain") or {}
        self.vo_def = float(sens.get("visual_odometry_noise", 0.05))
        self.base_xy = (float(M["base"][0]), float(M["base"][1]))
        self.max_m = float(R.get("max_metres_per_drive", 5.0))
        self.crust = M.get("crust_regions") or []
        self.lam = 0.2

        # cell flags
        N, NX, NY, c = self.N, self.NX, self.NY, self.cell
        cms = [0.0] * N
        hc = [0.0] * N
        for j in range(NY):
            lo, hi = self.h[j], self.h[j + 1]
            for i in range(NX):
                h00, h10, h01, h11 = lo[i], lo[i + 1], hi[i], hi[i + 1]
                s_, n_ = (h10 - h00) / c, (h11 - h01) / c
                w_, e_ = (h01 - h00) / c, (h11 - h10) / c
                k = j * NX + i
                cms[k] = max(math.hypot(s_, w_), math.hypot(s_, e_), math.hypot(n_, w_), math.hypot(n_, e_))
                hc[k] = (h00 + h10 + h01 + h11) / 4.0
        self.cms, self.hc = cms, hc
        self.forb = [m > 0.30 for m in cms]
        near = [False] * N
        for j in range(NY):
            for i in range(NX):
                k = j * NX + i
                if cms[k] > 0.22:
                    near[k] = True
                    continue
                for dj in (-1, 0, 1):
                    for di in (-1, 0, 1):
                        ni, nj = i + di, j + dj
                        if 0 <= ni < NX and 0 <= nj < NY and self.forb[nj * NX + ni]:
                            near[k] = True
        self.near = near
        crustc = [False] * N
        for j in range(NY):
            for i in range(NX):
                cx, cy = (i + 0.5) * c, (j + 0.5) * c
                for r in self.crust:
                    try:
                        if r["x1"] <= cx <= r["x2"] and r["y1"] <= cy <= r["y2"]:
                            crustc[j * NX + i] = True
                    except Exception:
                        pass
        self.crustc = crustc
        self.extra = [0.0] * N

        # state
        self.targets = {}
        self.fields = {}
        self.sampled = set()
        self.fails = {}
        self.recs = []
        self.sched = {}
        self.byid = {}
        self.sample_recs = []
        self.route = []
        self.last_reserved = 0
        self.ekf_tick = 0
        self.now = 0
        self.bat = float(R.get("initial_battery", self.cap))
        self.last_hd = 0.0
        self.X = [self.base_xy[0], self.base_xy[1], 0.0, 1.0]
        bvar = (math.radians(float(sens.get("heading_bias_deg", 5.0)))) ** 2 / 3.0
        self.P = [[1e-6, 0, 0, 0], [0, 1e-6, 0, 0], [0, 0, bvar, 0], [0, 0, 0, 0.02]]
        self.outl = 0
        self.need_map = False
        self.need_rebuild = False
        self.need_replan = True
        self.rebuilds = 0
        self.last_map = 0
        self.last_big = 0
        self.cur_goal = None
        self.goal_limit = 0
        self.update_targets(M)
        self.build_edges()

    # ---------------- geometry ----------------
    def samp(self, x, y):
        c = self.cell
        fx, fy = x / c, y / c
        i = min(self.NX - 1, max(0, int(fx)))
        j = min(self.NY - 1, max(0, int(fy)))
        tx, ty = fx - i, fy - j
        lo, hi = self.h[j], self.h[j + 1]
        h00, h10, h01, h11 = lo[i], lo[i + 1], hi[i], hi[i + 1]
        hh = (h00 * (1 - tx) + h10 * tx) * (1 - ty) + (h01 * (1 - tx) + h11 * tx) * ty
        gx = ((h10 - h00) * (1 - ty) + (h11 - h01) * ty) / c
        gy = ((h01 - h00) * (1 - tx) + (h11 - h10) * tx) / c
        return hh, gx, gy, self.codes[j][i]

    def cell_of(self, x, y):
        i = min(self.NX - 1, max(0, int(x / self.cell)))
        j = min(self.NY - 1, max(0, int(y / self.cell)))
        return j * self.NX + i

    def center(self, k):
        j, i = divmod(k, self.NX)
        return ((i + 0.5) * self.cell, (j + 0.5) * self.cell)

    def sim(self, x, y, hd, metres, base, gain, tilt=None):
        tilt = self.max_tilt if tilt is None else tilt
        r = math.radians(hd)
        ux, uy = math.cos(r), math.sin(r)
        seg = self.seg
        rem = metres
        wheel = ground = en = 0.0
        stop = None
        ms = 0.0
        h0, gx, gy, code = self.samp(x, y)
        W, H = self.Wm, self.Hm
        side, cost, climb, smax = self.side, self.cost, self.climb, self.slip_max
        while rem > 1e-9:
            s = seg if seg < rem else rem
            name = TC.get(code, "regolith")
            grade = gx * ux + gy * uy
            cross = -gx * uy + gy * ux
            sl = base[name] + gain[name] * (grade if grade > 0 else 0.0)
            sl = 0.0 if sl < 0 else (smax if sl > smax else sl)
            if sl > ms:
                ms = sl
            fw = s * (1.0 - sl)
            sd = s * side[name] * cross
            nx = x + ux * fw + uy * sd
            ny = y + uy * fw - ux * sd
            if not (0.0 <= nx <= W and 0.0 <= ny <= H):
                stop = "map"
                break
            h1, ngx, ngy, nc = self.samp(nx, ny)
            if math.hypot(ngx, ngy) > tilt:
                stop = "tilt"
                break
            en += s * cost[name] + climb * (h1 - h0 if h1 > h0 else 0.0)
            wheel += s
            ground += math.hypot(nx - x, ny - y)
            rem -= s
            x, y, h0, gx, gy, code = nx, ny, h1, ngx, ngy, nc
        return x, y, wheel, ground, en, stop, ms

    # ---------------- graph ----------------
    def half(self, code, grade, d):
        name = TC.get(code, "regolith")
        g = grade if grade > 0 else 0.0
        sl = self.base_mid[name] + self.gain[name] * g
        if sl > 0.9:
            sl = 0.9
        t = d / (self.max_m * (1.0 - sl))
        e = d * self.cost[name] / (1.0 - sl)
        pess = self.base_hi[name] + self.gain_hi[name] * g * 1.3
        pen = 0.0
        if sl > self.slip_limit - 0.03:
            pen = 30.0
        elif pess > self.slip_limit - 0.01:
            pen = 3.0
        return t, e, pen

    def build_edges(self):
        NX, NY, N = self.NX, self.NY, self.N
        out = [[] for _ in range(N)]
        inc = [[] for _ in range(N)]
        dirs = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
        forb, near, hc, cms, crustc, extra = self.forb, self.near, self.hc, self.cms, self.crustc, self.extra
        codes = self.codes
        lam = self.lam
        for j in range(NY):
            for i in range(NX):
                u = j * NX + i
                cu = codes[j][i]
                for di, dj in dirs:
                    ni, nj = i + di, j + dj
                    if ni < 0 or nj < 0 or ni >= NX or nj >= NY:
                        continue
                    if di and dj:
                        if forb[j * NX + ni] or forb[nj * NX + i]:
                            continue
                        dist = self.cell * 1.41421356
                    else:
                        dist = self.cell
                    v = nj * NX + ni
                    dh = hc[v] - hc[u]
                    grade = dh / dist
                    cv = codes[nj][ni]
                    t1, e1, p1 = self.half(cu, grade, dist / 2)
                    t2, e2, p2 = self.half(cv, grade, dist / 2)
                    t = t1 + t2
                    e = e1 + e2 + self.climb * (dh if dh > 0 else 0.0)
                    pen = p1 if p1 > p2 else p2
                    if near[v]:
                        t *= 1.4
                    if forb[v]:
                        pen += 100.0
                    if crustc[v] and cv == "b" and cms[v] <= 0.1:
                        pen += 0.6 if grade > 0.015 else 0.05
                    pen += extra[v]
                    tt = t + pen
                    w = tt + lam * e
                    out[u].append((v, w))
                    inc[v].append((u, w, tt, e))
        self.out = out
        self.inc = inc

    def compute_field(self, x, y):
        g = self.cell_of(x, y)
        N = self.N
        W = [INF] * N
        T = [INF] * N
        E = [INF] * N
        W[g] = 0.0
        T[g] = 0.0
        E[g] = 0.0
        heap = [(0.0, g)]
        inc = self.inc
        pop, push = heapq.heappop, heapq.heappush
        while heap:
            d, v = pop(heap)
            if d > W[v]:
                continue
            tv, ev_ = T[v], E[v]
            for (u, w, t, e) in inc[v]:
                nd = d + w
                if nd < W[u]:
                    W[u] = nd
                    T[u] = tv + t
                    E[u] = ev_ + e
                    push(heap, (nd, u))
        return (W, T, E, g)

    def compute_missing_fields(self):
        if BASEKEY not in self.fields:
            self.fields[BASEKEY] = self.compute_field(*self.base_xy)
        for tid, tg in self.targets.items():
            if tid not in self.fields:
                self.fields[tid] = self.compute_field(tg["x"], tg["y"])

    def rebuild(self):
        self.build_edges()
        self.fields = {}
        self.compute_missing_fields()
        self.rebuilds += 1
        self.need_rebuild = False
        self.need_replan = True

    def update_targets(self, M):
        new = False
        for t in M.get("targets", []) or []:
            try:
                tid = str(t["id"])
                if tid in self.targets:
                    continue
                v = float(t.get("value", 1.0))
                dl = t.get("deadline_tick")
                lv = t.get("late_value")
                if lv is None:
                    lv = v * 0.25 if dl is not None else v
                self.targets[tid] = {"x": float(t["x"]), "y": float(t["y"]), "value": v,
                                     "deadline": (int(dl) if dl is not None else 10 ** 9),
                                     "late": float(lv)}
                new = True
            except Exception:
                pass
        if new:
            self.need_replan = True

    def refresh_map(self):
        try:
            M = self.tools.map()
            self.update_targets(M)
        except Exception:
            pass
        self.need_map = False
        self.last_map = self.now

    # ---------------- solar ----------------
    def sol(self, t):
        v = math.sin(math.pi * (t + self.margin) / (self.T + 2 * self.margin))
        return self.peak * self.eff * v if v > 0 else 0.0

    def kt(self):
        s = min(1.3, max(0.7, self.X[3]))
        return 1.1 / s

    # ---------------- EKF ----------------
    def ekf_idle(self):
        self.P[0][0] += 0.0004
        self.P[1][1] += 0.0004

    def ekf_drive(self, hd, metres, vo, terr):
        X = self.X
        x0, y0 = X[0], X[1]
        r = self.sim(x0, y0, hd, metres, self.base_mid, self.gain)
        dx, dy = r[0] - x0, r[1] - y0
        L = math.hypot(dx, dy)
        b, s = X[2], X[3]
        c, sn = math.cos(b), math.sin(b)
        rx, ry = dx * c - dy * sn, dx * sn + dy * c
        X[0] += s * rx
        X[1] += s * ry
        X[0] = min(self.Wm, max(0.0, X[0]))
        X[1] = min(self.Hm, max(0.0, X[1]))
        F = [[1, 0, -s * ry, rx], [0, 1, s * rx, ry], [0, 0, 1, 0], [0, 0, 0, 1]]
        P = mm4(mm4(F, self.P), tr4(F))
        q = (0.035 * L) ** 2 + 0.01
        P[0][0] += q
        P[1][1] += q
        P[2][2] += 1.5e-5
        P[3][3] += 6e-5
        self.P = P
        if vo is not None and L > 0.2:
            try:
                vo = float(vo)
                c0 = TC.get(self.samp(x0, y0)[3], "regolith")
                sig = max(self.vo_by.get(c0, self.vo_def), self.vo_by.get(str(terr), self.vo_def))
                Rv = (sig * L) ** 2 + 0.0025
                h = X[3] * L
                y = vo - h
                S = L * L * P[3][3] + Rv
                if abs(y) < 4.0 * math.sqrt(S):
                    K = [P[i][3] * L / S for i in range(4)]
                    for i in range(4):
                        X[i] += K[i] * y
                    P3 = list(P[3])
                    for i in range(4):
                        for j in range(4):
                            P[i][j] -= K[i] * L * P3[j]
            except Exception:
                pass
        self.clampX()

    def clampX(self):
        X = self.X
        X[2] = max(-0.25, min(0.25, X[2]))
        X[3] = max(0.6, min(1.4, X[3]))
        P = self.P
        for i in range(4):
            for j in range(i + 1, 4):
                m = 0.5 * (P[i][j] + P[j][i])
                P[i][j] = P[j][i] = m
            if P[i][i] < 1e-9:
                P[i][i] = 1e-9

    def ekf_fix(self, zx, zy):
        X, P = self.X, self.P
        R = self.pos_sigma ** 2
        yx, yy = zx - X[0], zy - X[1]

        def inv(Rr):
            S00, S01, S10, S11 = P[0][0] + Rr, P[0][1], P[1][0], P[1][1] + Rr
            det = S00 * S11 - S01 * S10
            return S11 / det, -S01 / det, -S10 / det, S00 / det

        i00, i01, i10, i11 = inv(R)
        m2 = yx * (i00 * yx + i01 * yy) + yy * (i10 * yx + i11 * yy)
        if m2 > 11.0:
            self.outl += 1
            if self.outl >= 4:
                P[0][0] += 4.0
                P[1][1] += 4.0
                self.outl = 0
                i00, i01, i10, i11 = inv(R)
            else:
                i00, i01, i10, i11 = inv(R + 40.0)
        else:
            self.outl = 0
        K = [(P[i][0] * i00 + P[i][1] * i10, P[i][0] * i01 + P[i][1] * i11) for i in range(4)]
        for i in range(4):
            X[i] += K[i][0] * yx + K[i][1] * yy
        P0, P1 = list(P[0]), list(P[1])
        for i in range(4):
            for j in range(4):
                P[i][j] -= K[i][0] * P0[j] + K[i][1] * P1[j]
        self.clampX()

    # ---------------- telemetry ----------------
    def cancel_queued(self, t):
        for r in self.recs:
            if not r["executed"] and not r["cancelled"] and r["exec"] > t and r["transmit"] <= t:
                r["cancelled"] = True
        self.need_replan = True

    def add_extra(self, x, y, amount):
        if not (0 <= x <= self.Wm and 0 <= y <= self.Hm):
            return
        k = self.cell_of(x, y)
        self.extra[k] += amount

    def mark_stop(self, reason, hd):
        x, y = self.X[0], self.X[1]
        th = math.radians(hd + math.degrees(self.X[2]))
        ax, ay = x + 3.0 * math.cos(th), y + 3.0 * math.sin(th)
        if "slip" in reason:
            self.add_extra(x, y, 4.0)
            self.add_extra(ax, ay, 4.0)
        else:
            self.add_extra(ax, ay, 10.0)
            self.add_extra(x, y, 2.0)
        self.need_rebuild = True

    def step_missing(self, tt):
        rec = self.sched.get(tt)
        if rec and not rec["cancelled"] and rec["cmd"]["action"] == "drive":
            c = rec["cmd"]
            self.ekf_drive(c["heading_deg"], c["metres"], None, None)
            self.last_hd = c["heading_deg"]
        else:
            self.ekf_idle()

    def step_packet(self, t, p):
        events = p.get("events") or []
        exe = []
        stop = None
        for e in events:
            if not isinstance(e, dict):
                continue
            ty = str(e.get("type", ""))
            if ty == "command_executed":
                exe.append(e.get("command_id"))
            if "stop" in ty:
                stop = str(e.get("reason", ty))
            if "discover" in ty:
                self.need_map = True
        for cid in exe:
            r = self.byid.get(cid)
            if r:
                r["executed"] = True
                r["cancelled"] = False
        rec = self.sched.get(t)
        if rec is not None and not rec["executed"] and rec["id"] not in exe:
            rec["cancelled"] = True
            self.cancel_queued(t)
        drv = None
        for cid in exe:
            r = self.byid.get(cid)
            if r and r["cmd"]["action"] == "drive":
                drv = r
        if drv:
            c = drv["cmd"]
            wo = float(p.get("wheel_odometry") or 0.0)
            if wo > 1e-6:
                self.ekf_drive(c["heading_deg"], min(wo, self.max_m), p.get("visual_odometry"), p.get("terrain"))
            else:
                self.ekf_idle()
            self.last_hd = c["heading_deg"]
            if wo < c["metres"] - 0.05 and stop is None:
                stop = "short"
        else:
            self.ekf_idle()
        pos = p.get("position")
        if pos and len(pos) >= 2:
            self.ekf_fix(float(pos[0]), float(pos[1]))
        if stop is not None:
            self.cancel_queued(t)
            hd = drv["cmd"]["heading_deg"] if drv else self.last_hd
            self.mark_stop(stop, hd)
        if p.get("battery") is not None:
            self.bat = float(p["battery"])
        ch = p.get("charge")
        try:
            if ch is not None and float(ch) > 0:
                sv = math.sin(math.pi * (t + self.margin) / (self.T + 2 * self.margin))
                if sv > 0.05:
                    e = float(ch) / (self.peak * sv)
                    if self.eff < e <= self.eff_max + 0.02:
                        self.eff = min(e, self.eff_max)
        except Exception:
            pass
        for s in p.get("sampled_targets") or []:
            self.sampled.add(str(s))
        if str(p.get("terrain", "")) == "sand":
            k = self.cell_of(self.X[0], self.X[1])
            j, i = divmod(k, self.NX)
            if self.codes[j][i] != "s" and self.crustc[k]:
                self.codes[j][i] = "s"
                self.need_rebuild = True

    def process(self, packets):
        for p in sorted(packets, key=lambda q: q.get("tick", 0)):
            t = int(p.get("tick", 0))
            if t <= self.ekf_tick:
                continue
            for tt in range(self.ekf_tick + 1, t):
                self.step_missing(tt)
            self.step_packet(t, p)
            self.ekf_tick = t
        for r in self.sample_recs:
            if r["counted"] or r["exec"] > self.ekf_tick:
                continue
            r["counted"] = True
            self.need_replan = True
            if r["cancelled"]:
                continue
            if r["target"] not in self.sampled:
                self.fails[r["target"]] = self.fails.get(r["target"], 0) + 1

    def done_set(self):
        d = set(self.sampled)
        for r in self.sample_recs:
            if not r["cancelled"] and r["exec"] > self.ekf_tick:
                d.add(r["target"])
        for tid, c in self.fails.items():
            if c >= 2:
                d.add(tid)
        return d

    # ---------------- prediction ----------------
    def predict_state(self):
        x, y = self.X[0], self.X[1]
        B = self.bat
        hd = self.last_hd
        s = self.X[3]
        for tt in range(self.ekf_tick + 1, self.last_reserved + 1):
            B = min(self.cap, B + self.sol(tt)) - self.idle
            rec = self.sched.get(tt)
            if rec and not rec["cancelled"]:
                c = rec["cmd"]
                if c["action"] == "drive":
                    nx, ny, e = self.model_move(x, y, c["heading_deg"], c["metres"])
                    tcost = self.turn_c * angdiff(hd, c["heading_deg"]) * self.cost[TC.get(self.samp(x, y)[3], "regolith")]
                    B -= e * max(1.0, s) * 1.05 + tcost
                    x, y = nx, ny
                    hd = c["heading_deg"]
                elif c["action"] == "sample":
                    B -= self.sample_cost
        return {"x": x, "y": y, "B": B, "hd": hd, "tick": max(self.last_reserved, self.ekf_tick)}

    def model_move(self, x, y, hd, m):
        r = self.sim(x, y, hd, m, self.base_mid, self.gain)
        dx, dy = r[0] - x, r[1] - y
        b, s = self.X[2], self.X[3]
        c, sn = math.cos(b), math.sin(b)
        nx = x + s * (dx * c - dy * sn)
        ny = y + s * (dx * sn + dy * c)
        return min(self.Wm, max(0.0, nx)), min(self.Hm, max(0.0, ny)), r[4]

    # ---------------- steering ----------------
    def line_ok(self, x, y, px, py):
        D = math.hypot(px - x, py - y)
        k0 = self.cell_of(x, y)
        n = int(D) + 1
        for q in range(1, n + 1):
            f = min(1.0, q / D) if D > 0 else 1.0
            k = self.cell_of(x + (px - x) * f, y + (py - y) * f)
            if k == k0:
                continue
            if self.cms[k] > 0.27 or self.extra[k] >= 4.0:
                return False
        return True

    def plan_drive(self, x, y, px, py, force=False):
        D = math.hypot(px - x, py - y)
        if D < 0.05:
            return None
        theta = math.degrees(math.atan2(py - y, px - x))
        b, s = self.X[2], self.X[3]
        hc = (theta - math.degrees(b)) % 360.0
        r = self.sim(x, y, hc, self.max_m, self.base_mid, self.gain)
        g = r[3] / r[2] if r[2] > 0.2 else 0.85
        g = max(g, 0.3)
        L = min(D, s * g * self.max_m)
        m = min(self.max_m, max(0.05, L / (s * g)))
        r = self.sim(x, y, hc, m, self.base_mid, self.gain)
        if r[3] > 0.05 and r[5] is None:
            m = min(self.max_m, max(0.05, m * L / (s * r[3])))
            r = self.sim(x, y, hc, m, self.base_mid, self.gain)
        if not force:
            if r[5] == "tilt":
                return None
            pr = self.sim(x, y, theta, min(self.max_m, m * 1.25), self.base_hi, self.gain_hi, tilt=0.33)
            if pr[5] == "tilt" or pr[6] > self.slip_limit - 0.01:
                return None
        dx, dy = r[0] - x, r[1] - y
        c, sn = math.cos(b), math.sin(b)
        nx = min(self.Wm, max(0.0, x + s * (dx * c - dy * sn)))
        ny = min(self.Hm, max(0.0, y + s * (dx * sn + dy * c)))
        return hc, m, nx, ny, r[4]

    def steer(self, x, y, gx, gy, F):
        W, gcell = F[0], F[3]
        c = self.cell_of(x, y)
        pts = []
        cur = c
        reached = (c == gcell)
        for _ in range(6):
            if cur == gcell:
                reached = True
                break
            best, bv = None, INF
            for v, w in self.out[cur]:
                val = w + W[v]
                if val < bv:
                    bv, best = val, v
            if best is None:
                break
            cur = best
            pts.append(self.center(cur))
        if cur == gcell:
            reached = True
        if reached:
            pts.append((gx, gy))
        for P in reversed(pts):
            if math.hypot(P[0] - x, P[1] - y) < 0.05:
                continue
            if not self.line_ok(x, y, P[0], P[1]):
                continue
            res = self.plan_drive(x, y, P[0], P[1])
            if res:
                return res
        P = pts[0] if pts else (gx, gy)
        res = self.plan_drive(x, y, P[0], P[1], force=True)
        if res is None and (P[0], P[1]) != (gx, gy):
            res = self.plan_drive(x, y, gx, gy, force=True)
        return res

    # ---------------- command choice ----------------
    def next_command(self, st, ex):
        x, y = st["x"], st["y"]
        Bx = min(self.cap, st["B"] + self.sol(ex)) - self.idle
        kt = self.kt()
        done = self.done_set()
        fb = self.fields[BASEKEY]
        c = self.cell_of(x, y)
        goal = None
        for tid in self.route:
            if tid in done or tid not in self.fields or tid not in self.targets:
                continue
            goal = tid
            break
        if goal is not None:
            tg = self.targets[goal]
            F = self.fields[goal]
            tneed = ex + F[1][c] * kt + 2 + fb[1][self.cell_of(tg["x"], tg["y"])] * kt + 6
            if tneed > self.T:
                goal = None
        if goal is not None:
            if goal != self.cur_goal:
                self.cur_goal = goal
                self.goal_limit = ex + 1.8 * F[1][c] * kt + 15
            elif ex > self.goal_limit:
                self.fails[goal] = 99
                self.need_replan = True
                self.cur_goal = None
                return None
            gx, gy = tg["x"], tg["y"]
            if math.hypot(x - gx, y - gy) <= 0.7:
                if Bx - self.sample_cost < 3.0:
                    return None
                ns = {"x": x, "y": y, "B": Bx - self.sample_cost, "hd": st["hd"]}
                return {"action": "sample"}, ns, goal
        else:
            self.cur_goal = None
            F = fb
            gx, gy = self.base_xy
            if math.hypot(x - gx, y - gy) <= 1.2:
                return None
        res = self.steer(x, y, gx, gy, F)
        if res is None:
            return None
        hc, m, nx, ny, en = res
        tcost = self.turn_c * angdiff(st["hd"], hc) * self.cost[TC.get(self.samp(x, y)[3], "regolith")]
        Bn = Bx - en * max(1.0, self.X[3]) * 1.05 - tcost
        reserve = 6.0 if (goal is not None or self.T - ex > 30) else 2.0
        if Bn < reserve:
            return None
        m = round(max(0.05, min(self.max_m, m)), 3)
        cmd = {"action": "drive", "heading_deg": round(hc % 360.0, 2), "metres": m}
        return cmd, {"x": nx, "y": ny, "B": Bn, "hd": cmd["heading_deg"]}, None

    # ---------------- tour planning ----------------
    def plan(self, budget):
        tstart = time.time()
        deadline = tstart + budget
        st = self.predict_state()
        t0 = max(st["tick"], self.now + self.delay)
        B0 = st["B"]
        fb = self.fields.get(BASEKEY)
        if fb is None:
            self.route = []
            return
        done = self.done_set()
        kt = self.kt()
        ke = 1.15
        c0 = self.cell_of(st["x"], st["y"])
        ids = []
        for tid in self.targets:
            if tid in done or tid not in self.fields:
                continue
            if self.fields[tid][1][c0] >= 1e8:
                continue
            ids.append(tid)
        n = len(ids)
        cells = [self.cell_of(self.targets[i]["x"], self.targets[i]["y"]) for i in ids]
        Ts = [self.fields[i][1][c0] * kt + 1.7 for i in ids]
        Es = [self.fields[i][2][c0] * ke + 2.0 for i in ids]
        TT = [[self.fields[ids[b]][1][cells[a]] * kt + 1.7 for b in range(n)] for a in range(n)]
        EE = [[self.fields[ids[b]][2][cells[a]] * ke + 2.0 for b in range(n)] for a in range(n)]
        TB = [fb[1][cells[a]] * kt + 1.0 for a in range(n)]
        EB = [fb[2][cells[a]] * ke for a in range(n)]
        TB0 = fb[1][c0] * kt + 1.0
        EB0 = fb[2][c0] * ke
        V = [self.targets[i]["value"] for i in ids]
        LV = [self.targets[i]["late"] for i in ids]
        DL = [self.targets[i]["deadline"] for i in ids]
        Tlim = self.T - 6
        S = [0.0]
        for k in range(1, self.T + 400):
            S.append(S[-1] + self.sol(k))
        nS = len(S)
        cap, idle, res_ = self.cap, self.idle, 10.0

        def Sc(t):
            if t <= 0:
                return 0.0
            i = int(t)
            if i >= nS - 1:
                return S[-1]
            return S[i] + (t - i) * (S[i + 1] - S[i])

        def legrun(t, B, tt, ee):
            Bend = B + Sc(t + tt) - Sc(t) - idle * tt - ee
            if Bend >= res_:
                return t + tt, min(cap, Bend)
            w = 0
            while w < 150:
                w += 2
                Bs = min(cap, B + Sc(t + w) - Sc(t) - idle * w)
                Bend = Bs + Sc(t + w + tt) - Sc(t + w) - idle * tt - ee
                if Bend >= res_:
                    return t + w + tt, min(cap, Bend)
            return None, None

        def ev(route):
            t = t0
            B = B0
            val = 0.0
            p = -1
            for a in route:
                if p < 0:
                    tt, ee = Ts[a], Es[a]
                else:
                    tt, ee = TT[p][a], EE[p][a]
                if tt > 1e7:
                    return None
                t, B = legrun(t, B, tt, ee)
                if t is None or t > Tlim:
                    return None
                val += V[a] if t + 1 <= DL[a] else LV[a]
                p = a
            if p < 0:
                tt, ee = TB0, EB0
            else:
                tt, ee = TB[p], EB[p]
            if tt > 1e7:
                return None
            t, B = legrun(t, B, tt, ee)
            if t is None or t > Tlim:
                return None
            return (val, t)

        def obj(r):
            return r[0] - 0.003 * r[1]

        def leg(p, q):
            if p == -1:
                return Ts[q] if q >= 0 else TB0
            if q == -2:
                return TB[p]
            return TT[p][q]

        def bestpos(route, a, mcount):
            L = len(route)
            lst = []
            for k in range(L + 1):
                p = route[k - 1] if k > 0 else -1
                q = route[k] if k < L else -2
                lst.append((leg(p, a) + leg(a, q) - leg(p, q), k))
            lst.sort()
            return [k for _, k in lst[:mcount]]

        def construct(alpha, noise):
            route = []
            cur = ev(route)
            if cur is None:
                return [], None
            while time.time() < deadline + 0.5 * budget:
                best, bs = None, 0.0
                inr = set(route)
                for a in range(n):
                    if a in inr:
                        continue
                    for k in bestpos(route, a, 3):
                        r = route[:k] + [a] + route[k:]
                        res = ev(r)
                        if res is None:
                            continue
                        dv = res[0] - cur[0]
                        if dv <= 1e-9:
                            continue
                        dt = max(res[1] - cur[1], 0.5)
                        sc = dv / (dt ** alpha)
                        if noise:
                            sc *= 1.0 + noise * self.rnd.random()
                        if sc > bs:
                            bs, best = sc, (r, res)
                if best is None:
                    break
                route, cur = best
            return route, cur

        def improve(route, cur):
            if cur is None:
                return route, cur
            improved = True
            while improved and time.time() < deadline:
                improved = False
                inr = set(route)
                outs = [a for a in range(n) if a not in inr]
                for a in outs:
                    for k in bestpos(route, a, 3):
                        r = route[:k] + [a] + route[k:]
                        res = ev(r)
                        if res and obj(res) > obj(cur) + 1e-9:
                            route, cur, improved = r, res, True
                            break
                    if improved:
                        break
                if improved:
                    continue
                for i in range(len(route)):
                    for a in outs:
                        r = route[:i] + [a] + route[i + 1:]
                        res = ev(r)
                        if res and obj(res) > obj(cur) + 1e-9:
                            route, cur, improved = r, res, True
                            break
                    if improved or time.time() > deadline:
                        break
                if improved:
                    continue
                L = len(route)
                for i in range(L - 1):
                    for j in range(i + 1, L):
                        r = route[:i] + route[i:j + 1][::-1] + route[j + 1:]
                        res = ev(r)
                        if res and obj(res) > obj(cur) + 1e-9:
                            route, cur, improved = r, res, True
                            break
                    if improved or time.time() > deadline:
                        break
                if improved:
                    continue
                for i in range(L):
                    a = route[i]
                    rest = route[:i] + route[i + 1:]
                    for k in range(len(rest) + 1):
                        if k == i:
                            continue
                        r = rest[:k] + [a] + rest[k:]
                        res = ev(r)
                        if res and obj(res) > obj(cur) + 1e-9:
                            route, cur, improved = r, res, True
                            break
                    if improved or time.time() > deadline:
                        break
            return route, cur

        sols = []
        idx = {tid: a for a, tid in enumerate(ids)}
        prev = [idx[t] for t in self.route if t in idx]
        cur = ev(prev)
        while prev and cur is None:
            bestr, bestres = None, None
            for i in range(len(prev)):
                r = prev[:i] + prev[i + 1:]
                res = ev(r)
                if res and (bestres is None or obj(res) > obj(bestres)):
                    bestr, bestres = r, res
            if bestr is None:
                prev = prev[:-1]
                cur = ev(prev)
            else:
                prev, cur = bestr, bestres
        if cur is not None:
            sols.append(improve(prev, cur))
        r, c_ = construct(1.0, 0.0)
        if c_ is not None:
            sols.append(improve(r, c_))
        while time.time() < deadline:
            r, c_ = construct(self.rnd.uniform(0.5, 2.5), 0.5)
            if c_ is not None:
                sols.append(improve(r, c_))
        best = None
        for r, c_ in sols:
            if c_ is None:
                continue
            if best is None or obj(c_) > obj(best[1]):
                best = (r, c_)
        self.route = [ids[a] for a in best[0]] if best else []

    # ---------------- per tick ----------------
    def act(self, t):
        self.now = t
        if self.need_map or t - self.last_map >= 24:
            self.refresh_map()
        if self.need_rebuild and self.rebuilds < 10:
            self.rebuild()
        self.compute_missing_fields()
        el = time.time() - self.wall0
        if t % self.period == 0 or self.need_replan:
            if el > 1000:
                budget = 0.05
            elif t - self.last_big >= 48:
                budget = 2.5
                self.last_big = t
            else:
                budget = 0.5
            self.need_replan = False
            self.plan(budget)
        ns = t + 1
        while ns % self.period >= self.open:
            ns += 1
        cover = ns + self.delay
        st = self.predict_state()
        n = 0
        while self.last_reserved < cover and n < 12:
            ex = max(t + self.delay + 1, self.last_reserved + 1)
            for tt in range(st["tick"] + 1, ex):
                st["B"] = min(self.cap, st["B"] + self.sol(tt)) - self.idle
            st["tick"] = ex - 1
            res = self.next_command(st, ex)
            if res is None:
                break
            cmd, newst, tgt = res
            try:
                ack = self.tools.uplink([cmd])[0]
            except Exception:
                break
            rec = {"id": ack.get("command_id"), "exec": int(ack.get("execute_tick", ex)),
                   "transmit": int(ack.get("transmit_tick", t)), "cmd": cmd, "target": tgt,
                   "cancelled": False, "executed": False, "counted": False}
            self.recs.append(rec)
            self.sched[rec["exec"]] = rec
            self.byid[rec["id"]] = rec
            if cmd["action"] == "sample":
                self.sample_recs.append(rec)
            self.last_reserved = max(self.last_reserved, rec["exec"])
            newst["tick"] = rec["exec"]
            st = newst
            n += 1

    def run(self):
        try:
            self.process(self.tools.telemetry_log())
        except Exception:
            pass
        self.compute_missing_fields()
        try:
            self.plan(10.0)
        except Exception:
            self.route = []
        self.need_replan = False
        t = 0
        while True:
            if t % self.period < self.open:
                try:
                    self.act(t)
                except Exception:
                    pass
            try:
                r = self.tools.advance(1)
            except Exception:
                return
            t = int(r.get("current_tick", t + 1))
            self.now = t
            try:
                self.process(r.get("packets") or [])
            except Exception:
                pass
            if r.get("episode_complete"):
                return
            if t > self.T + 20:
                return


def play(tools):
    Pilot(tools).run()
