import math
import heapq
import random

INF = float("inf")
TC = {"b": "bedrock", "r": "regolith", "s": "sand", "k": "rocks"}


def wrap180(a):
    return (a + 180.0) % 360.0 - 180.0


def wrap_pi(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


class Surf:
    def __init__(self, cell, elev, terr):
        self.cell = float(cell)
        self.h = [[float(v) / 100.0 for v in row] for row in elev]
        self.ny = len(self.h)
        self.nx = len(self.h[0])
        self.codes = [str(r) for r in terr]
        self.width = (self.nx - 1) * self.cell
        self.height = (self.ny - 1) * self.cell

    def sample(self, x, y):
        cell = self.cell
        fx, fy = x / cell, y / cell
        i = min(self.nx - 2, max(0, int(fx)))
        j = min(self.ny - 2, max(0, int(fy)))
        tx, ty = fx - i, fy - j
        low, high = self.h[j], self.h[j + 1]
        h00, h10, h01, h11 = low[i], low[i + 1], high[i], high[i + 1]
        height = (h00 * (1 - tx) + h10 * tx) * (1 - ty) + (h01 * (1 - tx) + h11 * tx) * ty
        gx = ((h10 - h00) * (1 - ty) + (h11 - h01) * ty) / cell
        gy = ((h01 - h00) * (1 - tx) + (h11 - h10) * tx) / cell
        return height, gx, gy, self.codes[j][i]

    def cell_max_slope(self, i, j):
        low, high, cell = self.h[j], self.h[j + 1], self.cell
        h00, h10, h01, h11 = low[i], low[i + 1], high[i], high[i + 1]
        south, north = (h10 - h00) / cell, (h11 - h01) / cell
        west, east = (h01 - h00) / cell, (h11 - h10) / cell
        return max(math.hypot(south, west), math.hypot(south, east),
                   math.hypot(north, west), math.hypot(north, east))


def sim_drive(S, P, x, y, hd, metres, sb, gain):
    rad = math.radians(hd)
    ux, uy = math.cos(rad), math.sin(rad)
    seg_full = P["segment_m"]
    side = P["side_slip_gain"]
    cost = P["drive_cost_per_wheel_m"]
    climb = P["climb_cost_per_m"]
    smax = P["slip_max"]
    mt = P["max_tilt"]
    W, H = S.width, S.height
    rem = float(metres)
    wheel = ground = energy = 0.0
    stop = None
    here, gx, gy, code = S.sample(x, y)
    while rem > 1e-9:
        seg = min(seg_full, rem)
        name = TC.get(code, "regolith")
        grade = gx * ux + gy * uy
        cross = -gx * uy + gy * ux
        slip = sb[name] + gain[name] * (grade if grade > 0 else 0.0)
        slip = 0.0 if slip < 0 else (smax if slip > smax else slip)
        fwd = seg * (1.0 - slip)
        sw = seg * side[name] * cross
        nx = x + ux * fwd + uy * sw
        ny = y + uy * fwd - ux * sw
        if not (0.0 <= nx <= W and 0.0 <= ny <= H):
            stop = "map_boundary"
            break
        there, ngx, ngy, ncode = S.sample(nx, ny)
        if math.hypot(ngx, ngy) > mt:
            stop = "tilt"
            break
        energy += seg * cost[name] + climb * (there - here if there > here else 0.0)
        wheel += seg
        ground += math.hypot(nx - x, ny - y)
        rem -= seg
        x, y, here, gx, gy, code = nx, ny, there, ngx, ngy, ncode
    return x, y, wheel, ground, energy, stop


def mm4(A, B):
    return [[A[i][0] * B[0][j] + A[i][1] * B[1][j] + A[i][2] * B[2][j] + A[i][3] * B[3][j]
             for j in range(4)] for i in range(4)]


def tr4(A):
    return [[A[j][i] for j in range(4)] for i in range(4)]


class Pilot:
    def __init__(self, tools):
        self.tools = tools
        R = tools.rules()
        Mp = tools.map()
        self.R = R
        self.delay = int(R.get("delay_ticks", 3))
        self.max_ticks = int(R.get("max_ticks", 420))
        rp = R.get("relay_passes")
        if isinstance(rp, dict):
            self.period = max(1, int(rp.get("period_ticks", 1)))
            self.open_n = max(1, int(rp.get("open_ticks", self.period)))
        else:
            self.period = 1
            self.open_n = 1
        ph = R["physics"]
        self.ph = ph
        rg = ph["slip_base_ranges"]
        self.slip_lo = {k: float(v[0]) for k, v in rg.items()}
        self.slip_hi = {k: float(v[1]) for k, v in rg.items()}
        self.slip_mid = {k: (float(v[0]) + float(v[1])) / 2 for k, v in rg.items()}
        self.gain = {k: float(v) for k, v in ph["slip_grade_gain"].items()}
        self.gain_lo = dict(self.gain)
        self.gain_hi = dict(self.gain)
        sgg = R.get("sand_grade_gain")
        if isinstance(sgg, dict) and "range" in sgg:
            self.gain_lo["sand"] = float(sgg["range"][0])
            self.gain_hi["sand"] = float(sgg["range"][1])
        self.dcost = ph["drive_cost_per_wheel_m"]
        self.climb = float(ph.get("climb_cost_per_m", 2.0))
        osc = R.get("onboard_slip_check")
        self.slip_limit = float(osc.get("limit", 1.0)) if isinstance(osc, dict) else 1.0
        self.cap = float(R.get("battery_capacity", 100.0))
        self.idle = float(R.get("idle_cost", 0.15))
        self.sample_cost = float(R.get("sample_cost", 2.0))
        self.peak = float(R.get("solar_peak", 2.8))
        self.sun_margin = float(R.get("sun_margin_ticks", 56))
        er = R.get("solar_efficiency_range", [0.8, 1.0])
        self.eff = float(er[0]) + 0.25 * (float(er[1]) - float(er[0]))
        self.eff_seen = False
        self.tpd = float(R.get("turn_cost_per_degree", 0.0) or 0.0)
        self.max_m = float(R.get("max_metres_per_drive", 5.0))
        sens = R.get("sensing", {}) or {}
        self.pos_sig = float(sens.get("position_noise_m", 2.0))
        pfo = R.get("position_fix_outliers")
        self.out_sig = float(pfo.get("sigma_m", 3.0)) if isinstance(pfo, dict) else 3.0
        vb = sens.get("visual_odometry_noise_by_terrain")
        vdef = float(sens.get("visual_odometry_noise", 0.05))
        self.vo_sig = {k: (float(vb.get(k, vdef)) if isinstance(vb, dict) else vdef)
                       for k in ("bedrock", "regolith", "rocks", "sand")}
        self.relerr = {"bedrock": 0.015, "regolith": 0.025, "rocks": 0.04, "sand": 0.1}

        self.surf = Surf(Mp["cell_m"], Mp["elevation_cm"], Mp["terrain"])
        self.cell = self.surf.cell
        self.NX = self.surf.nx - 1
        self.NY = self.surf.ny - 1
        self.N = self.NX * self.NY
        self.base = (float(Mp["base"][0]), float(Mp["base"][1]))
        self.crust = []
        for cr in Mp.get("crust_regions", []) or []:
            try:
                self.crust.append((float(cr["x1"]), float(cr["y1"]), float(cr["x2"]), float(cr["y2"])))
            except Exception:
                pass

        # solar cumulative (eff = 1)
        T = self.max_ticks + 10
        self.Scum = [0.0] * (T + 1)
        for t in range(1, T + 1):
            self.Scum[t] = self.Scum[t - 1] + self.solar_raw(t)

        self.build_grid()

        self.targets = {}
        self.goals = {}
        self.gcell = {}
        self.gpts = {}
        self.add_goal("BASE", self.base[0], self.base[1])
        for tg in Mp.get("targets", []):
            self.add_target(tg)

        # state
        self.s = [self.base[0], self.base[1], 0.0, 1.0]
        bvar = (math.radians(float(sens.get("heading_bias_deg", 5.0)))) ** 2 / 3.0
        wse = R.get("wheel_scale_error")
        wr = float(wse.get("range", 0.2)) if isinstance(wse, dict) else 0.05
        fvar = wr * wr / 3.0 + 0.0005
        self.walk_var = math.radians(float(sens.get("heading_bias_walk_deg", 0.2))) ** 2
        self.P = [[0.0] * 4 for _ in range(4)]
        self.P[0][0] = 1e-4
        self.P[1][1] = 1e-4
        self.P[2][2] = bvar
        self.P[3][3] = fvar
        self.K = 0
        self.pkts = {}
        self.cmds = {}
        self.sched = {}
        self.last_reserved = 0
        self.seen_exec_types = set()
        self.sampled = set()
        self.pending = {}
        self.approach = {}
        self.skip = set()
        self.batt_K = float(R.get("initial_battery", 100.0))
        self.lh_K = 0.0
        self.alive = True
        self.route = []
        self.need_replan = True
        self.last_plan = -100
        self.tf = 1.3
        self.end_margin = 8.0
        self.reserve = 10.0

    # ------------------------------------------------------------ energy
    def solar_raw(self, t):
        v = math.sin(math.pi * (t + self.sun_margin) / (self.max_ticks + 2 * self.sun_margin))
        return self.peak * max(0.0, v)

    def solar(self, t):
        return self.eff * self.solar_raw(t)

    def solar_sum(self, t1, t2):
        n = len(self.Scum) - 1
        a = int(max(0, min(n, t1)))
        b = int(max(0, min(n, t2)))
        if b <= a:
            return 0.0
        return self.eff * (self.Scum[b] - self.Scum[a])

    # ------------------------------------------------------------ grid
    def cellof(self, x, y):
        i = min(self.NX - 1, max(0, int(x / self.cell)))
        j = min(self.NY - 1, max(0, int(y / self.cell)))
        return j * self.NX + i

    def center(self, c):
        return ((c % self.NX) + 0.5) * self.cell, ((c // self.NX) + 0.5) * self.cell

    def build_grid(self):
        S = self.surf
        NX, NY, N, cell = self.NX, self.NY, self.N, self.cell
        cms = [0.0] * N
        code = ["r"] * N
        for j in range(NY):
            row = S.codes[j]
            for i in range(NX):
                c = j * NX + i
                cms[c] = S.cell_max_slope(i, j)
                code[c] = row[i]
        self.cms = cms
        self.code = code
        blocked = [cms[c] > 0.33 for c in range(N)]
        self.blocked = blocked
        fac = [1.0] * N
        dirs = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]
        self.dirs = dirs
        for j in range(NY):
            for i in range(NX):
                c = j * NX + i
                if blocked[c]:
                    continue
                f = 1.0
                if cms[c] > 0.25:
                    f = 3.0
                elif cms[c] > 0.2:
                    f = 1.3
                for di, dj in dirs:
                    ni, nj = i + di, j + dj
                    if 0 <= ni < NX and 0 <= nj < NY and blocked[nj * NX + ni]:
                        f = max(f, 1.6)
                        break
                fac[c] = f
        self.fac = fac
        soft = [False] * N
        for j in range(NY):
            for i in range(NX):
                c = j * NX + i
                if code[c] != "b" or cms[c] > 0.1:
                    continue
                cx, cy = (i + 0.5) * cell, (j + 0.5) * cell
                for (x1, y1, x2, y2) in self.crust:
                    if min(x1, x2) <= cx <= max(x1, x2) and min(y1, y2) <= cy <= max(y1, y2):
                        soft[c] = True
                        break
        self.soft = soft
        nb = [-1] * (N * 8)
        pred = [-1] * (N * 8)
        for j in range(NY):
            for i in range(NX):
                c = j * NX + i
                for d, (di, dj) in enumerate(dirs):
                    ni, nj = i + di, j + dj
                    if 0 <= ni < NX and 0 <= nj < NY:
                        v = nj * NX + ni
                        nb[c * 8 + d] = v
                        pred[v * 8 + d] = c
        self.nb = nb
        self.pred = pred
        hcen = [0.0] * N
        for c in range(N):
            cx, cy = self.center(c)
            hcen[c] = S.sample(cx, cy)[0]
        W = [INF] * (N * 8)
        TM = [INF] * (N * 8)
        EN = [INF] * (N * 8)
        sq2 = math.sqrt(2.0)
        for c in range(N):
            if blocked[c]:
                continue
            i = c % NX
            j = c // NX
            ax, ay = (i + 0.5) * cell, (j + 0.5) * cell
            ha = hcen[c]
            for d in range(8):
                v = nb[c * 8 + d]
                if v < 0 or blocked[v]:
                    continue
                di, dj = dirs[d]
                if di and dj and (blocked[j * NX + i + di] or blocked[(j + dj) * NX + i]):
                    continue
                bx, by = ax + di * cell, ay + dj * cell
                L = cell * (sq2 if (di and dj) else 1.0)
                ux, uy = di * cell / L, dj * cell / L
                hm = S.sample((ax + bx) / 2, (ay + by) / 2)[0]
                hb = hcen[v]
                t1, e1 = self.half(c, ax + 0.25 * (bx - ax), ay + 0.25 * (by - ay), ux, uy, L / 2, hm - ha)
                t2, e2 = self.half(v, ax + 0.75 * (bx - ax), ay + 0.75 * (by - ay), ux, uy, L / 2, hb - hm)
                k = c * 8 + d
                TM[k] = t1 + t2
                EN[k] = e1 + e2
                W[k] = TM[k] + 0.04 * EN[k]
        self.W, self.TM, self.EN = W, TM, EN

    def risk(self, name, gp):
        lim = self.slip_limit
        hi = self.slip_hi[name] + self.gain_hi[name] * gp + 0.02
        if hi <= lim:
            return 0.0
        lo = self.slip_lo[name] + self.gain_lo[name] * gp - 0.02
        if lo >= lim:
            return 1.0
        return (hi - lim) / max(1e-6, hi - lo)

    def half(self, c, px, py, ux, uy, L, dh):
        _, gx, gy, _ = self.surf.sample(px, py)
        g = gx * ux + gy * uy
        gp = g if g > 0 else 0.0
        name = TC.get(self.code[c], "regolith")
        sm = self.slip_mid[name] + self.gain[name] * gp
        rk = self.risk(name, gp)
        cm = self.dcost[name]
        if self.soft[c]:
            sm = 0.9 * sm + 0.1 * (self.slip_mid["sand"] + self.gain["sand"] * gp)
            rk = rk + 0.1 * self.risk("sand", gp)
            cm = 0.9 * cm + 0.1 * self.dcost["sand"]
        if sm > 0.9:
            sm = 0.9
        wheel = L / (1.0 - sm)
        t = wheel / self.max_m * self.fac[c] + rk * 6.0
        e = wheel * cm + self.climb * (dh if dh > 0 else 0.0)
        return t, e

    def rev_dijkstra(self, g):
        N = self.N
        dist = [INF] * N
        T = [INF] * N
        E = [INF] * N
        nxt = [-1] * N
        dist[g] = 0.0
        T[g] = 0.0
        E[g] = 0.0
        W, TM, EN, pred = self.W, self.TM, self.EN, self.pred
        h = [(0.0, g)]
        pop, push = heapq.heappop, heapq.heappush
        while h:
            dv, v = pop(h)
            if dv > dist[v]:
                continue
            base = v * 8
            Tv, Ev = T[v], E[v]
            for d in range(8):
                u = pred[base + d]
                if u < 0:
                    continue
                k = u * 8 + d
                w = W[k]
                if w == INF:
                    continue
                nd = dv + w
                if nd < dist[u]:
                    dist[u] = nd
                    T[u] = Tv + TM[k]
                    E[u] = Ev + EN[k]
                    nxt[u] = v
                    push(h, (nd, u))
        return {"dist": dist, "T": T, "E": E, "nxt": nxt}

    def add_goal(self, key, x, y):
        c = self.cellof(x, y)
        self.gcell[key] = c
        self.gpts[key] = (x, y)
        self.goals[key] = self.rev_dijkstra(c)

    def add_target(self, tg):
        tid = str(tg["id"])
        if tid in self.targets:
            return False
        rec = {"x": float(tg["x"]), "y": float(tg["y"]), "value": float(tg.get("value", 1.0)),
               "deadline_tick": tg.get("deadline_tick"),
               "late_value": float(tg.get("late_value", tg.get("value", 1.0)))}
        self.targets[tid] = rec
        try:
            self.add_goal(tid, rec["x"], rec["y"])
        except Exception:
            pass
        return True

    def gpoint(self, key):
        return self.gpts[key]

    def cell_safe(self, x, y, key):
        c = self.cellof(x, y)
        g = self.goals.get(key)
        if g is None or g["dist"][c] < INF:
            return c
        i0, j0 = c % self.NX, c // self.NX
        best, bd = c, INF
        for r in (1, 2, 3):
            for dj in range(-r, r + 1):
                for di in range(-r, r + 1):
                    i, j = i0 + di, j0 + dj
                    if 0 <= i < self.NX and 0 <= j < self.NY:
                        cc = j * self.NX + i
                        dd = g["dist"][cc]
                        if dd < INF:
                            cx, cy = self.center(cc)
                            sc = dd + 0.5 * math.hypot(cx - x, cy - y)
                            if sc < bd:
                                bd, best = sc, cc
            if bd < INF:
                return best
        return c

    # ------------------------------------------------------------ filter
    def ekf_predict(self, qx, qy, terr):
        x, y, b, f = self.s
        self.s = [x + f * qx, y + f * qy, b, f]
        F = [[1.0, 0.0, -f * qy, qx], [0.0, 1.0, f * qx, qy], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]
        P2 = mm4(mm4(F, self.P), tr4(F))
        q = math.hypot(qx, qy)
        dist = f * q
        sa = (self.relerr.get(terr, 0.03) + 0.012) * dist + 0.05
        sl = 0.027 * dist + 0.05
        if q > 1e-6:
            ux, uy = qx / q, qy / q
        else:
            ux, uy = 1.0, 0.0
        a2, l2 = sa * sa, sl * sl
        P2[0][0] += a2 * ux * ux + l2 * uy * uy
        P2[1][1] += a2 * uy * uy + l2 * ux * ux
        cxy = (a2 - l2) * ux * uy
        P2[0][1] += cxy
        P2[1][0] += cxy
        P2[2][2] += self.walk_var
        P2[3][3] += 2e-6
        self.P = P2

    def ekf_pos(self, zx, zy):
        P = self.P
        ix, iy = zx - self.s[0], zy - self.s[1]
        r1 = self.pos_sig ** 2
        r2 = r1 + self.out_sig ** 2
        use = None
        for Rv in (r1, r2):
            a = P[0][0] + Rv
            bb = P[0][1]
            cc = P[1][0]
            d = P[1][1] + Rv
            det = a * d - bb * cc
            if det <= 1e-12:
                return
            i00, i01, i10, i11 = d / det, -bb / det, -cc / det, a / det
            d2 = ix * (i00 * ix + i01 * iy) + iy * (i10 * ix + i11 * iy)
            if Rv == r1:
                if d2 <= 9.0:
                    use = (i00, i01, i10, i11)
                    break
            else:
                if d2 <= 16.0:
                    use = (i00, i01, i10, i11)
        if use is None:
            return
        i00, i01, i10, i11 = use
        K = [[P[r][0] * i00 + P[r][1] * i10, P[r][0] * i01 + P[r][1] * i11] for r in range(4)]
        for r in range(4):
            self.s[r] += K[r][0] * ix + K[r][1] * iy
        P0, P1 = P[0][:], P[1][:]
        newP = [[P[r][c] - K[r][0] * P0[c] - K[r][1] * P1[c] for c in range(4)] for r in range(4)]
        for r in range(4):
            for c in range(r + 1, 4):
                m = 0.5 * (newP[r][c] + newP[c][r])
                newP[r][c] = m
                newP[c][r] = m
        self.P = newP
        if self.s[3] < 0.6:
            self.s[3] = 0.6
        if self.s[3] > 1.4:
            self.s[3] = 1.4

    def ekf_vo(self, vo, q, terr_a, terr_b):
        sig = max(self.vo_sig.get(terr_a, 0.05), self.vo_sig.get(terr_b, 0.05) if terr_b else 0.0)
        rel = max(self.relerr.get(terr_a, 0.03), self.relerr.get(terr_b, 0.03) if terr_b else 0.0)
        Rv = (vo * sig) ** 2 + (rel * q) ** 2 + 1e-4
        P = self.P
        Sv = q * q * P[3][3] + Rv
        innov = vo - self.s[3] * q
        if innov * innov / Sv > 16.0:
            return
        K = [P[r][3] * q / Sv for r in range(4)]
        for r in range(4):
            self.s[r] += K[r] * innov
        HP = [q * P[3][c] for c in range(4)]
        self.P = [[P[r][c] - K[r] * HP[c] for c in range(4)] for r in range(4)]
        if self.s[3] < 0.6:
            self.s[3] = 0.6
        if self.s[3] > 1.4:
            self.s[3] = 1.4

    # ------------------------------------------------------------ telemetry
    def ingest(self):
        try:
            log = self.tools.telemetry_log()
        except Exception:
            return
        for p in log:
            if not isinstance(p, dict):
                continue
            tk = p.get("tick")
            if tk is None:
                continue
            tk = int(tk)
            if tk not in self.pkts:
                self.pkts[tk] = p
        self.process()

    def mark_stop(self, s):
        for cid, rec in self.cmds.items():
            if rec["status"] == "scheduled" and rec["exec"] > s and rec["tx"] + self.delay <= s:
                rec["status"] = "cleared"
        self.need_replan = True

    def process(self):
        if not self.pkts:
            return
        Kmax = max(self.pkts)
        if Kmax <= self.K:
            return
        for k in range(self.K + 1, Kmax + 1):
            pkt = self.pkts.get(k)
            evs = (pkt.get("events") or []) if pkt else []
            exec_ids = set()
            stop_here = False
            for ev in evs:
                if not isinstance(ev, dict):
                    continue
                ty = str(ev.get("type", ""))
                if ty == "command_executed":
                    cidx = ev.get("command_id")
                    exec_ids.add(cidx)
                    rr = self.cmds.get(cidx)
                    if rr is not None:
                        self.seen_exec_types.add(rr["cmd"]["action"])
                elif "stop" in ty:
                    stop_here = True
            cid = self.sched.get(k)
            executed = False
            rec = None
            if cid is not None:
                rec = self.cmds[cid]
                act = rec["cmd"]["action"]
                if pkt is not None and act in self.seen_exec_types:
                    executed = cid in exec_ids
                    if not executed and act == "drive":
                        wo = pkt.get("wheel_odometry")
                        if wo is not None and float(wo) > 1e-6:
                            executed = True
                    if not executed and rec["status"] == "scheduled":
                        self.mark_stop(k - 1)
                    rec["status"] = "executed" if executed else "cleared"
                elif pkt is not None and act == "drive":
                    executed = rec["status"] != "cleared"
                    wo = pkt.get("wheel_odometry")
                    if executed and wo is not None and float(wo) <= 1e-6 and stop_here is False:
                        executed = False
                    rec["status"] = "executed" if executed else rec["status"]
                else:
                    executed = rec["status"] != "cleared"
                    if executed:
                        rec["status"] = "executed"
            if executed and rec is not None and rec["cmd"]["action"] == "drive":
                c = rec["cmd"]
                M = float(c["metres"])
                if pkt is not None:
                    wo = pkt.get("wheel_odometry")
                    if wo is not None:
                        try:
                            M = float(wo)
                        except Exception:
                            pass
                hd = float(c["heading_deg"])
                self.lh_K = hd
                if M > 1e-6:
                    x, y, b, f = self.s
                    terr = TC.get(self.surf.sample(x, y)[3], "regolith")
                    r = sim_drive(self.surf, self.ph, x, y, hd + math.degrees(b), M, self.slip_mid, self.gain)
                    qx, qy = r[0] - x, r[1] - y
                    self.ekf_predict(qx, qy, terr)
                    if pkt is not None:
                        vo = pkt.get("visual_odometry")
                        q = math.hypot(qx, qy)
                        if vo is not None and q > 0.3:
                            try:
                                self.ekf_vo(float(vo), q, terr, pkt.get("terrain"))
                            except Exception:
                                pass
            if stop_here:
                self.mark_stop(k)
            if pkt is not None:
                pos = pkt.get("position")
                if pos and k > 0:
                    try:
                        self.ekf_pos(float(pos[0]), float(pos[1]))
                    except Exception:
                        pass
                ch = pkt.get("charge")
                bt = pkt.get("battery")
                if ch is not None and bt is not None:
                    sr = self.solar_raw(k)
                    if sr > 0.3 and float(bt) < self.cap - 1.0 and float(ch) > 0:
                        e = float(ch) / sr
                        if 0.5 < e < 1.2:
                            if not self.eff_seen:
                                self.eff = e
                                self.eff_seen = True
                            else:
                                self.eff = max(self.eff, e)
        self.K = Kmax
        latest = self.pkts[Kmax]
        try:
            self.batt_K = float(latest.get("battery", self.batt_K))
        except Exception:
            pass
        st = latest.get("sampled_targets")
        if isinstance(st, list):
            self.sampled = set(str(v) for v in st)
        if latest.get("alive") is False:
            self.alive = False
        for tid, et in list(self.pending.items()):
            if Kmax >= et:
                del self.pending[tid]
                if tid not in self.sampled:
                    self.need_replan = True
                    self.approach[tid] = 0

    def update_targets(self):
        try:
            Mp = self.tools.map()
        except Exception:
            return
        for tg in Mp.get("targets", []) or []:
            try:
                if self.add_target(tg):
                    self.need_replan = True
            except Exception:
                pass

    # ------------------------------------------------------------ prediction
    def predict_to(self, T):
        x, y, b, f = self.s
        batt = self.batt_K
        lh = self.lh_K
        bdeg = math.degrees(b)
        for k in range(self.K + 1, T + 1):
            batt = min(self.cap, batt + self.solar(k)) - self.idle
            cid = self.sched.get(k)
            if cid is None:
                continue
            rec = self.cmds[cid]
            if rec["status"] == "cleared":
                continue
            c = rec["cmd"]
            if c["action"] == "drive":
                terr = TC.get(self.surf.sample(x, y)[3], "regolith")
                batt -= abs(wrap180(c["heading_deg"] - lh)) * self.tpd * self.dcost[terr]
                r = sim_drive(self.surf, self.ph, x, y, c["heading_deg"] + bdeg, c["metres"] * f,
                              self.slip_mid, self.gain)
                x, y = r[0], r[1]
                batt -= r[4]
                lh = c["heading_deg"]
            elif c["action"] == "sample":
                batt -= self.sample_cost
        return x, y, batt, lh

    # ------------------------------------------------------------ planning
    def tf_update(self):
        f = max(0.6, self.s[3])
        sf = math.sqrt(max(0.0, self.P[3][3]))
        self.tf = 1.05 / f * (1.0 + 1.5 * sf)

    def evaluate(self, route, t0, b0, c0):
        G = self.goals
        TT = self.targets
        tf = self.tf
        t = t0
        b = b0
        val = 0.0
        pc = c0
        cap = self.cap
        idle = self.idle
        for tid in route:
            g = G[tid]
            tt = g["T"][pc]
            if tt == INF:
                return -1.0, INF
            dt = tt * tf + 0.6
            t2 = t + dt
            b = min(cap, b + self.solar_sum(t, t2) - idle * dt - g["E"][pc])
            if b < self.reserve:
                return -1.0, INF
            t2 += 1.0
            b -= self.sample_cost + idle
            tg = TT[tid]
            dl = tg["deadline_tick"]
            if dl is None or t2 <= dl - 1:
                val += tg["value"]
            else:
                val += tg["late_value"]
            t = t2
            pc = self.gcell[tid]
        g = G["BASE"]
        tt = g["T"][pc]
        if tt == INF:
            return -1.0, INF
        dt = tt * tf + 0.6
        t2 = t + dt
        if t2 > self.max_ticks - self.end_margin:
            return -1.0, INF
        b = min(cap, b + self.solar_sum(t, t2) - idle * dt - g["E"][pc])
        if b < self.reserve:
            return -1.0, INF
        return val, t2

    def greedy(self, route, cands, ev, alpha, noise, rng):
        route = list(route)
        v0, te0 = ev(route)
        if v0 < 0:
            return route
        pool = [c for c in cands if c not in route]
        while pool:
            best = None
            bs = 0.0
            for c in pool:
                for pos in range(len(route) + 1):
                    r = route[:pos] + [c] + route[pos:]
                    v, te = ev(r)
                    if v < 0:
                        continue
                    dv = v - v0
                    if dv <= 1e-9:
                        continue
                    dt = max(0.5, te - te0)
                    s = dv / (dt ** alpha)
                    if noise:
                        s *= 1.0 + noise * rng.random()
                    if s > bs:
                        bs = s
                        best = (r, v, te, c)
            if best is None:
                break
            route, v0, te0, c = best
            pool.remove(c)
        return route

    def improve(self, route, ev):
        v, te = ev(route)
        if v < 0:
            return route
        for _ in range(4):
            improved = False
            n = len(route)
            for i in range(n):
                for j in range(n):
                    if i == j:
                        continue
                    r = route[:i] + route[i + 1:]
                    r.insert(j, route[i])
                    v2, t2 = ev(r)
                    if v2 > v + 1e-9 or (v2 >= v - 1e-9 and t2 < te - 0.05):
                        route, v, te = r, v2, t2
                        improved = True
                        break
                if improved:
                    break
            if not improved:
                break
        return route

    def replan(self, x, y, t0, b0):
        self.tf_update()
        c0 = self.cell_safe(x, y, "BASE")
        cands = []
        for tid in self.targets:
            if tid in self.sampled or tid in self.pending or tid in self.skip:
                continue
            g = self.goals.get(tid)
            if g is None or g["T"][c0] == INF:
                continue
            cands.append(tid)

        def ev(r):
            return self.evaluate(r, t0, b0, c0)

        if ev([])[0] < 0:
            self.route = []
            return
        cur = [tid for tid in self.route if tid in cands]
        while cur and ev(cur)[0] < 0:
            bestr = None
            bv = -1.0
            for i in range(len(cur)):
                r = cur[:i] + cur[i + 1:]
                v = ev(r)[0]
                if v > bv:
                    bv, bestr = v, r
            if bestr is None or bv < 0:
                cur = cur[:-1]
            else:
                cur = bestr
        best = cur
        bv = ev(cur)[0]
        rng = random.Random(int(t0) * 7919 + 13)
        variants = [(cur, 1.0, 0.0), ([], 1.0, 0.0), ([], 1.6, 0.0), ([], 0.6, 0.0), ([], 1.0, 0.4)]
        for start, al, nz in variants:
            r = self.greedy(start, cands, ev, al, nz, rng)
            r = self.improve(r, ev)
            r = self.greedy(r, cands, ev, 1.0, 0.0, rng)
            v = ev(r)[0]
            if v > bv + 1e-6:
                best, bv = r, v
        self.route = list(best)

    def route_ok(self, x, y, t0, b0):
        if not self.route:
            return True
        self.tf_update()
        c0 = self.cell_safe(x, y, "BASE")
        for tid in self.route:
            if tid in self.sampled:
                return False
        return self.evaluate(self.route, t0, b0, c0)[0] >= 0

    # ------------------------------------------------------------ steering
    def los(self, x, y, px, py, ctx):
        D = math.hypot(px - x, py - y)
        n = int(D / 1.0) + 1
        for k in range(1, n + 1):
            fr = k / n
            qx, qy = x + (px - x) * fr, y + (py - y) * fr
            c = self.cellof(qx, qy)
            if ctx is not None:
                cs, allowed, soft_ok = ctx
                if c in cs:
                    continue
                if self.blocked[c] or self.fac[c] > 1.0:
                    return False
                if self.code[c] not in allowed:
                    return False
                if self.soft[c] and not soft_ok:
                    return False
            else:
                if self.blocked[c] or self.fac[c] > 1.6:
                    return False
        return True

    def choose_aim(self, x, y, goal):
        gx, gy = self.gpoint(goal)
        D = math.hypot(gx - x, gy - y)
        if D < 7.0 and self.los(x, y, gx, gy, None):
            return gx, gy, True
        g = self.goals[goal]
        gc = self.gcell[goal]
        c = self.cell_safe(x, y, goal)
        chain = [c]
        while len(chain) < 7:
            n = g["nxt"][chain[-1]]
            if n < 0:
                break
            chain.append(n)
        if len(chain) == 1:
            return gx, gy, True
        cs = set(chain)
        allowed = {"b", "r"} | set(self.code[n] for n in chain)
        soft_ok = any(self.soft[n] for n in chain)
        best = None
        for n in chain[1:]:
            if n == gc:
                px, py = gx, gy
            else:
                px, py = self.center(n)
            if math.hypot(px - x, py - y) > 22.0:
                break
            if self.los(x, y, px, py, (cs, allowed, soft_ok)):
                best = (px, py, n == gc)
        if best is None:
            n = chain[1]
            if n == gc:
                best = (gx, gy, True)
            else:
                cx, cy = self.center(n)
                best = (cx, cy, False)
        return best

    def make_drive(self, x, y, ax, ay, final):
        b, f = self.s[2], self.s[3]
        bdeg = math.degrees(b)
        th = math.atan2(ay - y, ax - x)
        D = math.hypot(ax - x, ay - y)
        h = th - b
        M = self.max_m
        for _ in range(3):
            r = sim_drive(self.surf, self.ph, x, y, math.degrees(h) + bdeg, M * f, self.slip_mid, self.gain)
            qx, qy = r[0] - x, r[1] - y
            q = math.hypot(qx, qy)
            if q < 0.05:
                break
            h += wrap_pi(th - math.atan2(qy, qx))
            rate = q / M
            want = D if final else D + 1.5
            M = min(self.max_m, max(0.05, want / max(0.05, rate)))
        hd = math.degrees(h) % 360.0
        r = sim_drive(self.surf, self.ph, x, y, hd + bdeg, M * f, self.slip_mid, self.gain)
        if r[5] == "tilt":
            ok = False
            for off in (25, -25, 50, -50, 80, -80):
                r2 = sim_drive(self.surf, self.ph, x, y, hd + off + bdeg, M * f, self.slip_mid, self.gain)
                if r2[5] != "tilt":
                    hd = (hd + off) % 360.0
                    ok = True
                    break
            if not ok:
                M = max(0.05, min(self.max_m, r[2] / max(0.6, f) * 0.8))
        return hd, M

    def gen(self, x, y, b, lh, e):
        terr_code = self.surf.sample(x, y)[3]
        bb = min(self.cap, b + self.solar(e)) - self.idle
        goal = "BASE"
        while True:
            goal = self.route[0] if self.route else "BASE"
            gx, gy = self.gpoint(goal)
            D = math.hypot(gx - x, gy - y)
            if goal != "BASE":
                n = self.approach.get(goal, 0)
                if D <= 0.6 or (n >= 4 and D <= 2.0):
                    self.route.pop(0)
                    self.approach[goal] = 0
                    return {"action": "sample"}, (x, y, bb - self.sample_cost, lh), goal
                if n >= 7:
                    self.route.pop(0)
                    self.skip.add(goal)
                    continue
            else:
                if D <= 1.0:
                    return None
            break
        if bb < 8.0:
            return {"action": "wait"}, (x, y, bb, lh), None
        ax, ay, final = self.choose_aim(x, y, goal)
        hd, M = self.make_drive(x, y, ax, ay, final)
        if final and goal != "BASE":
            self.approach[goal] = self.approach.get(goal, 0) + 1
        f = self.s[3]
        bdeg = math.degrees(self.s[2])
        r = sim_drive(self.surf, self.ph, x, y, hd + bdeg, M * f, self.slip_mid, self.gain)
        terr = TC.get(terr_code, "regolith")
        bb -= abs(wrap180(hd - lh)) * self.tpd * self.dcost[terr] + r[4]
        M = round(min(self.max_m, max(0.05, M)), 3)
        if M <= 0:
            M = 0.05
        cmd = {"action": "drive", "heading_deg": round(hd % 360.0, 3), "metres": M}
        return cmd, (r[0], r[1], bb, hd), None

    # ------------------------------------------------------------ loop
    def is_open(self, t):
        return (t % self.period) < self.open_n

    def act(self, t):
        if not self.alive:
            return
        if self.is_open(t + 1):
            nxt_send = t + 1
        else:
            m = t + 1
            while not self.is_open(m):
                m += 1
            nxt_send = m
        target_L = min(self.max_ticks, nxt_send + self.delay)
        next_exec = max(t + self.delay + 1, self.last_reserved + 1)
        count = min(5, target_L - next_exec + 1)
        if count <= 0:
            return
        x, y, b, lh = self.predict_to(next_exec - 1)
        t0 = next_exec - 1
        self.tf_update()
        if self.need_replan or t - self.last_plan >= 16 or not self.route_ok(x, y, t0, b):
            try:
                self.replan(x, y, t0, b)
            except Exception:
                pass
            self.need_replan = False
            self.last_plan = t
        cmds = []
        metas = []
        for k in range(count):
            e = next_exec + k
            try:
                out = self.gen(x, y, b, lh, e)
            except Exception:
                out = None
            if out is None:
                break
            cmd, (x, y, b, lh), meta = out
            cmds.append(cmd)
            metas.append(meta)
        if not cmds:
            return
        try:
            acks = self.tools.uplink(cmds)
        except Exception:
            for meta in reversed(metas):
                if meta:
                    self.route.insert(0, meta)
            return
        for ack, cmd, meta in zip(acks, cmds, metas):
            try:
                cid = ack["command_id"]
                et = int(ack["execute_tick"])
                tt = int(ack.get("transmit_tick", t))
            except Exception:
                continue
            self.cmds[cid] = {"cmd": cmd, "exec": et, "tx": tt, "status": "scheduled"}
            self.sched[et] = cid
            self.last_reserved = max(self.last_reserved, et)
            if meta:
                self.pending[meta] = et

    def run(self):
        tools = self.tools
        t = 0
        self.ingest()
        guard = 0
        while guard < 5000:
            guard += 1
            if t < self.max_ticks and self.is_open(t) and self.alive:
                try:
                    self.update_targets()
                except Exception:
                    pass
                try:
                    self.act(t)
                except Exception:
                    pass
            if self.is_open(t) and self.is_open(t + 1):
                n = 1
            else:
                m = t + 1
                while not self.is_open(m):
                    m += 1
                n = m - t
            n = max(1, min(5, n, max(1, self.max_ticks - t)))
            try:
                res = tools.advance(n)
            except Exception:
                try:
                    res = tools.advance(1)
                except Exception:
                    return
            t = int(res.get("current_tick", t + n))
            try:
                self.ingest()
            except Exception:
                pass
            if res.get("episode_complete"):
                return


def play(tools):
    pilot = Pilot(tools)
    pilot.run()
