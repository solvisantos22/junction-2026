The module plans the whole traverse on its own: it builds a slope-aware route graph, chooses and orders targets under deadlines and energy limits, and steers with a filtered position estimate. It has not been run against the simulator. A few behaviours rest on my reading of the rules rather than on anything I could check:

- **Command acknowledgements.** I assume every executed command produces a `command_executed` event, and that a safety stop shows up as an event whose `type` contains `stop`.
- **What a stop clears.** I assume a safety stop clears every queued command that was sent at or before the stop tick. If the simulator clears a different set, telemetry later corrects the record, but some planning in between will rest on the wrong guess.
- **Calibration.** The safety margins and penalty weights (for example the battery reserve of 15, the 0.30 slope cut-off and the 8-tick margin for getting home) are my estimates, not tuned values.

**What it does**

- **Map and route graph.** It reads the map once and builds a 16-connected graph over the 5 m cells.
  - **Hazards removed.** The graph leaves out ground steep enough to trip the tilt stop. It also leaves out climbs that could trip the 0.45 slip check, using the worst case of the hidden slip ranges.
  - **Hazards penalised.** Crust cells, ground next to crater walls and the scarp, and cells found soft or stopped on during the mission cost extra.
  - **Leg costs.** Shortest paths give time and energy between the lander, every target and every point on the map.
- **Choosing targets.** At every relay pass it re-plans the tour from the predicted position. It inserts targets greedily by value per tick and improves the order by moving targets around in it.
  - Each tour must respect deadlines and get back to the lander with 8 ticks to spare.
  - It also keeps a battery reserve, using a solar model whose efficiency is measured exactly from the `charge` field.
- **Position estimate.** It tracks position, heading bias and a combined distance factor (wheel size and slip) with a filter.
  - **Inputs.** It uses its own drive model, noisy position fixes with wild ones screened out, and visual odometry noise by terrain.
  - **Lost data.** It handles lost packets and safety stops, using wheel odometry to measure how far a stopped drive really went.
- **Commands.** It follows the path with commands corrected for the estimated heading bias and distance factor.
  - **Sampling.** It samples when the prediction is within 0.6 m of a target. If telemetry shows a sample failed, the target goes back into the plan.
  - **Getting home.** It turns home when time runs short, and nudges itself back if the estimate drifts more than about 1 m from the lander.
  - **Battery.** If the battery would fall below a floor, it sends nothing and lets the sun recharge.

```python
import math
import heapq
import time

TERR = {"b": "bedrock", "r": "regolith", "s": "sand", "k": "rocks"}
INF = float("inf")
LAM = 0.2
MOVES = [(1, 0), (0, 1), (-1, 0), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1),
         (2, 1), (1, 2), (-1, 2), (-2, 1), (-2, -1), (-1, -2), (1, -2), (2, -1)]


class EKF:
    def __init__(self, x, y, vb, vf):
        self.s = [x, y, 0.0, 1.0]
        self.P = [[0.0] * 4 for _ in range(4)]
        self.P[2][2] = vb
        self.P[3][3] = vf
        self.rej = 0

    def clamp(self):
        self.s[2] = max(-0.25, min(0.25, self.s[2]))
        self.s[3] = max(0.6, min(1.4, self.s[3]))
        P = self.P
        for i in range(4):
            for j in range(i + 1, 4):
                m = 0.5 * (P[i][j] + P[j][i])
                P[i][j] = m
                P[j][i] = m
            if P[i][i] < 1e-9:
                P[i][i] = 1e-9

    def predict(self, D):
        x, y, b, f = self.s
        cb, sb = math.cos(b), math.sin(b)
        Rx = cb * D[0] - sb * D[1]
        Ry = sb * D[0] + cb * D[1]
        self.s = [x + f * Rx, y + f * Ry, b, f]
        F = [[1.0, 0.0, -f * Ry, Rx], [0.0, 1.0, f * Rx, Ry], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]
        P = self.P
        FP = [[sum(F[i][k] * P[k][j] for k in range(4)) for j in range(4)] for i in range(4)]
        Pn = [[sum(FP[i][k] * F[j][k] for k in range(4)) for j in range(4)] for i in range(4)]
        d = math.hypot(Rx, Ry)
        if d > 1e-6:
            ux, uy = Rx / d, Ry / d
            dd = d * f
            va = (0.03 * dd) ** 2 + (0.012 * dd) ** 2 + 1e-3
            vc = (0.03 * dd) ** 2 + 1e-3
            Pn[0][0] += va * ux * ux + vc * uy * uy
            Pn[1][1] += va * uy * uy + vc * ux * ux
            cxy = (va - vc) * ux * uy
            Pn[0][1] += cxy
            Pn[1][0] += cxy
            Pn[2][2] += 0.0035 ** 2 + 1e-6
            Pn[3][3] += 0.008 ** 2
        self.P = Pn
        self.clamp()

    def inflate(self, v):
        self.P[0][0] += v
        self.P[1][1] += v

    def fix(self, zx, zy, r):
        P = self.P
        y0 = zx - self.s[0]
        y1 = zy - self.s[1]

        def m2_for(rr):
            S00 = P[0][0] + rr
            S01 = P[0][1]
            S10 = P[1][0]
            S11 = P[1][1] + rr
            det = S00 * S11 - S01 * S10
            if abs(det) < 1e-12:
                det = 1e-12
            i00, i01, i10, i11 = S11 / det, -S01 / det, -S10 / det, S00 / det
            return y0 * (i00 * y0 + i01 * y1) + y1 * (i10 * y0 + i11 * y1), (i00, i01, i10, i11)

        m2, Si = m2_for(r)
        if m2 > 16.0:
            m2, Si = m2_for(r + 9.0)
            if m2 > 25.0:
                self.rej += 1
                if self.rej >= 3:
                    self.inflate(16.0)
                    self.rej = 0
                return False
        self.rej = 0
        i00, i01, i10, i11 = Si
        K = [[P[i][0] * i00 + P[i][1] * i10, P[i][0] * i01 + P[i][1] * i11] for i in range(4)]
        self.s = [self.s[i] + K[i][0] * y0 + K[i][1] * y1 for i in range(4)]
        self.P = [[P[i][j] - K[i][0] * P[0][j] - K[i][1] * P[1][j] for j in range(4)] for i in range(4)]
        self.clamp()
        return True

    def vo(self, z, d, r):
        P = self.P
        f = self.s[3]
        inn = z - f * d
        S = d * d * P[3][3] + r
        if S <= 0 or inn * inn > 9.0 * S:
            return
        K = [P[i][3] * d / S for i in range(4)]
        self.s = [self.s[i] + K[i] * inn for i in range(4)]
        self.P = [[P[i][j] - K[i] * d * P[3][j] for j in range(4)] for i in range(4)]
        self.clamp()


class Auto:
    def __init__(self, tools):
        self.tools = tools
        self.wall0 = time.monotonic()
        R = tools.rules()
        self.R = R
        M = tools.map()
        self.delay = int(R.get("delay_ticks", 3))
        self.T = int(R.get("max_ticks", 420))
        rp = R.get("relay_passes")
        if isinstance(rp, dict):
            self.period = int(rp.get("period_ticks", 8))
            self.openn = int(rp.get("open_ticks", 4))
        else:
            self.period = 1
            self.openn = 1
        ph = R["physics"]
        self.segm = float(ph.get("segment_m", 0.25))
        self.max_tilt = float(ph.get("max_tilt", 0.36))
        rng = ph["slip_base_ranges"]
        self.bmid = {k: (v[0] + v[1]) / 2.0 for k, v in rng.items()}
        self.bmax = {k: float(v[1]) for k, v in rng.items()}
        self.gain = {k: float(v) for k, v in ph["slip_grade_gain"].items()}
        self.gmax = dict(self.gain)
        sg = R.get("sand_grade_gain")
        if isinstance(sg, dict) and "range" in sg:
            self.gmax["sand"] = max(self.gmax.get("sand", 3.5), float(sg["range"][1]))
        self.sideg = {k: float(v) for k, v in ph["side_slip_gain"].items()}
        self.dcost = {k: float(v) for k, v in ph["drive_cost_per_wheel_m"].items()}
        self.climb = float(ph.get("climb_cost_per_m", 2.0))
        self.snoise = float(ph.get("slip_noise", 0.02))
        self.slipmax = float(ph.get("slip_max", 0.95))
        osc = R.get("onboard_slip_check")
        self.slim = float(osc["limit"]) if isinstance(osc, dict) and "limit" in osc else 0.9
        self.cap = float(R.get("battery_capacity", 100.0))
        self.idle = float(R.get("idle_cost", 0.15))
        self.scost = float(R.get("sample_cost", 2.0))
        self.maxm = float(R.get("max_metres_per_drive", 5.0))
        self.speak = float(R.get("solar_peak", 2.8))
        self.smargin = float(R.get("sun_margin_ticks", 56))
        er = R.get("solar_efficiency_range", [0.8, 1.0])
        self.eff_lo, self.eff_hi = float(er[0]), float(er[1])
        self.eff = self.eff_lo
        self.eff_samples = []
        self.turn_k = float(R.get("turn_cost_per_degree", 0.0) or 0.0)
        sens = R.get("sensing", {}) or {}
        self.fix_var = float(sens.get("position_noise_m", 2.0)) ** 2
        vob = sens.get("visual_odometry_noise_by_terrain") or {}
        vdef = float(sens.get("visual_odometry_noise", 0.05))
        self.vo_noise = {n: float(vob.get(n, vdef)) for n in TERR.values()}
        hb = float(sens.get("heading_bias_deg", 5.0))
        wse = R.get("wheel_scale_error")
        ws = float(wse.get("range", 0.0)) if isinstance(wse, dict) else 0.0
        self.TEND = self.T - 8
        self.RES = 15.0

        self.cell = float(M["cell_m"])
        self.h = [[v / 100.0 for v in row] for row in M["elevation_cm"]]
        codes = [str(r) for r in M["terrain"]]
        self.ny = len(self.h)
        self.nx = len(self.h[0])
        self.CX = self.nx - 1
        self.CY = self.ny - 1
        self.W = self.CX * self.cell
        self.Hm = self.CY * self.cell
        self.tn = [[TERR.get(ch, "regolith") for ch in codes[j]] for j in range(self.CY)]
        self.base = (float(M["base"][0]), float(M["base"][1]))
        c = self.cell
        self.cms = [[0.0] * self.CX for _ in range(self.CY)]
        for j in range(self.CY):
            lo, hi = self.h[j], self.h[j + 1]
            for i in range(self.CX):
                h00, h10, h01, h11 = lo[i], lo[i + 1], hi[i], hi[i + 1]
                s_, n_ = (h10 - h00) / c, (h11 - h01) / c
                w_, e_ = (h01 - h00) / c, (h11 - h10) / c
                self.cms[j][i] = max(math.hypot(s_, w_), math.hypot(s_, e_), math.hypot(n_, w_), math.hypot(n_, e_))
        self.crust = [[False] * self.CX for _ in range(self.CY)]
        for reg in (M.get("crust_regions") or []):
            try:
                x1, y1, x2, y2 = float(reg["x1"]), float(reg["y1"]), float(reg["x2"]), float(reg["y2"])
            except Exception:
                continue
            for j in range(self.CY):
                if not (j * c < y2 and (j + 1) * c > y1):
                    continue
                for i in range(self.CX):
                    if i * c < x2 and (i + 1) * c > x1:
                        if self.tn[j][i] == "bedrock" and self.cms[j][i] <= 0.1 + 1e-9:
                            self.crust[j][i] = True

        self.build_graph()
        self.pen = {}
        bnf = self.node_for(self.base[0], self.base[1])
        if bnf is None:
            bnf = (0.0, 0)
        self.base_chord, self.base_node = bnf
        _, self.rT, self.rE, self.rpar = self.dijkstra([(self.base_node, 0.0, 0.0, 0.0)], reverse=True)
        self.tg = {}
        for t in M.get("targets", []):
            self.add_target(t)

        self.pk = {}
        self.latest = 0
        self.ekf_tick = 0
        self.cmds = {}
        self.by_tick = {}
        self.last_exec = 0
        self.sampled = set()
        self.fails = {}
        self.bat = float(R.get("initial_battery", 100.0))
        self.bat_tick = 0
        self.plan_h = 0.0
        self.tour = []
        x0, y0 = self.base
        log = tools.telemetry_log()
        for p in log:
            if p.get("tick") == 0 and p.get("position"):
                x0, y0 = float(p["position"][0]), float(p["position"][1])
                self.bat = float(p.get("battery", self.bat))
        self.ekf = EKF(x0, y0, math.radians(hb) ** 2 / 3.0, ws * ws / 3.0 + 0.004)
        self.ingest(log)

    # ---------------- ground ----------------
    def sample(self, x, y):
        c = self.cell
        fx = x / c
        fy = y / c
        i = int(fx)
        j = int(fy)
        if i < 0:
            i = 0
        elif i > self.nx - 2:
            i = self.nx - 2
        if j < 0:
            j = 0
        elif j > self.ny - 2:
            j = self.ny - 2
        tx = fx - i
        ty = fy - j
        lo = self.h[j]
        hi = self.h[j + 1]
        h00 = lo[i]
        h10 = lo[i + 1]
        h01 = hi[i]
        h11 = hi[i + 1]
        hh = (h00 * (1 - tx) + h10 * tx) * (1 - ty) + (h01 * (1 - tx) + h11 * tx) * ty
        gx = ((h10 - h00) * (1 - ty) + (h11 - h01) * ty) / c
        gy = ((h01 - h00) * (1 - tx) + (h11 - h10) * tx) / c
        return hh, gx, gy, i, j

    def cell_of(self, x, y):
        i = min(self.CX - 1, max(0, int(x / self.cell)))
        j = min(self.CY - 1, max(0, int(y / self.cell)))
        return i, j

    def terrain_at(self, p):
        i, j = self.cell_of(p[0], p[1])
        return self.tn[j][i]

    def sim(self, x, y, hdeg, metres):
        rad = math.radians(hdeg)
        ux, uy = math.cos(rad), math.sin(rad)
        rem = float(metres)
        energy = 0.0
        wheel = 0.0
        stop = None
        here, gx, gy, ci, cj = self.sample(x, y)
        name = self.tn[cj][ci]
        mt2 = self.max_tilt * self.max_tilt
        while rem > 1e-9:
            seg = min(self.segm, rem)
            grade = gx * ux + gy * uy
            cross = -gx * uy + gy * ux
            slip = self.bmid[name] + self.gain[name] * (grade if grade > 0 else 0.0)
            slip = 0.0 if slip < 0 else (self.slipmax if slip > self.slipmax else slip)
            fwd = seg * (1.0 - slip)
            side = seg * self.sideg[name] * cross
            nx_ = x + ux * fwd + uy * side
            ny_ = y + uy * fwd - ux * side
            if not (0.0 <= nx_ <= self.W and 0.0 <= ny_ <= self.Hm):
                stop = "edge"
                break
            there, ngx, ngy, ni, nj = self.sample(nx_, ny_)
            if ngx * ngx + ngy * ngy > mt2:
                stop = "tilt"
                break
            energy += seg * self.dcost[name] + self.climb * (there - here if there > here else 0.0)
            wheel += seg
            rem -= seg
            x, y, here, gx, gy = nx_, ny_, there, ngx, ngy
            name = self.tn[nj][ni]
        return x, y, wheel, energy, stop

    # ---------------- graph ----------------
    def build_graph(self):
        CX, CY = self.CX, self.CY
        N = CX * CY
        self.N = N
        self.allowed = [self.cms[j][i] <= 0.32 for j in range(CY) for i in range(CX)]
        near = [[False] * CX for _ in range(CY)]
        for j in range(CY):
            for i in range(CX):
                if self.cms[j][i] > self.max_tilt * 0.97:
                    for dj in (-1, 0, 1):
                        for di in (-1, 0, 1):
                            a, b = i + di, j + dj
                            if 0 <= a < CX and 0 <= b < CY:
                                near[b][a] = True
        self.near = near
        adj = [[] for _ in range(N)]
        radj = [[] for _ in range(N)]
        allowed = self.allowed
        for j in range(CY):
            for i in range(CX):
                u = j * CX + i
                if not allowed[u]:
                    continue
                for di, dj in MOVES:
                    ni, nj = i + di, j + dj
                    if 0 <= ni < CX and 0 <= nj < CY:
                        v = nj * CX + ni
                        if not allowed[v]:
                            continue
                        e = self.edge(i, j, ni, nj)
                        if e is not None:
                            adj[u].append((v, e[0], e[1], e[2]))
                            radj[v].append((u, e[0], e[1], e[2]))
        self.adj = adj
        self.radj = radj

    def edge(self, i0, j0, i1, j1):
        c = self.cell
        x0 = (i0 + 0.5) * c
        y0 = (j0 + 0.5) * c
        dx = (i1 - i0) * c
        dy = (j1 - j0) * c
        L = math.hypot(dx, dy)
        n = max(3, int(math.ceil(L / 1.25)))
        ux = dx / L
        uy = dy / L
        seg = L / n
        tt = en = pen = 0.0
        hprev = None
        lim = self.slim - 0.02
        sandb = self.bmax.get("sand", 0.35)
        sandg = self.gmax.get("sand", 3.5)
        for k in range(n + 1):
            px = x0 + dx * k / n
            py = y0 + dy * k / n
            hh, gx, gy, ci, cj = self.sample(px, py)
            if gx * gx + gy * gy > 0.09:
                return None
            if hprev is not None and hh > hprev:
                en += self.climb * (hh - hprev)
            hprev = hh
            if k == n:
                break
            ci = min(ci, self.CX - 1)
            cj = min(cj, self.CY - 1)
            name = self.tn[cj][ci]
            g = gx * ux + gy * uy
            gp = g if g > 0 else 0.0
            if self.bmax[name] + self.gmax[name] * gp + self.snoise > lim:
                return None
            slip = self.bmid[name] + self.gain[name] * gp
            if slip > 0.85:
                return None
            w = seg / (1.0 - slip)
            tt += w / 5.0
            en += w * self.dcost[name]
            if self.crust[cj][ci] and sandb + sandg * gp + self.snoise > lim:
                pen += 0.25
            if self.near[cj][ci]:
                pen += 0.15 * seg
        return (tt + LAM * en + pen, tt, en)

    def dijkstra(self, srcs, reverse=False, pen=None):
        N = self.N
        cost = [INF] * N
        tt = [INF] * N
        ee = [INF] * N
        par = [-1] * N
        adj = self.radj if reverse else self.adj
        hp = []
        for n, c0, t0, e0 in srcs:
            if c0 < cost[n]:
                cost[n] = c0
                tt[n] = t0
                ee[n] = e0
                hp.append((c0, n))
        heapq.heapify(hp)
        pop = heapq.heappop
        push = heapq.heappush
        if pen:
            pg = pen.get
            while hp:
                c, u = pop(hp)
                if c > cost[u]:
                    continue
                tu = tt[u]
                eu = ee[u]
                for v, ec, et, e2 in adj[u]:
                    nc = c + ec + pg(v, 0.0)
                    if nc < cost[v]:
                        cost[v] = nc
                        tt[v] = tu + et
                        ee[v] = eu + e2
                        par[v] = u
                        push(hp, (nc, v))
        else:
            while hp:
                c, u = pop(hp)
                if c > cost[u]:
                    continue
                tu = tt[u]
                eu = ee[u]
                for v, ec, et, e2 in adj[u]:
                    nc = c + ec
                    if nc < cost[v]:
                        cost[v] = nc
                        tt[v] = tu + et
                        ee[v] = eu + e2
                        par[v] = u
                        push(hp, (nc, v))
        return cost, tt, ee, par

    def node_for(self, x, y):
        c = self.cell
        ci = int(x / c)
        cj = int(y / c)
        best = None
        for dj in range(-3, 4):
            for di in range(-3, 4):
                i = ci + di
                j = cj + dj
                if 0 <= i < self.CX and 0 <= j < self.CY:
                    u = j * self.CX + i
                    if self.allowed[u] and self.adj[u]:
                        d = math.hypot((i + 0.5) * c - x, (j + 0.5) * c - y)
                        if best is None or d < best[0]:
                            best = (d, u)
        return best

    def center(self, n):
        c = self.cell
        return ((n % self.CX + 0.5) * c, (n // self.CX + 0.5) * c)

    def add_target(self, t):
        tid = t.get("id")
        if tid is None or tid in self.tg:
            return
        x, y = float(t["x"]), float(t["y"])
        dl = t.get("deadline_tick")
        rec = {"x": x, "y": y, "v": float(t.get("value", 1.0)),
               "lv": float(t.get("late_value", t.get("value", 1.0))),
               "dl": float(dl) if dl is not None else INF, "ok": False}
        nf = self.node_for(x, y)
        if nf is not None and nf[0] <= 8.0:
            rec["chord"], rec["node"] = nf
            _, tt, ee, par = self.dijkstra([(nf[1], 0.0, 0.0, 0.0)])
            rec["tt"], rec["ee"], rec["par"] = tt, ee, par
            rec["ok"] = tt[self.base_node] < INF
        self.tg[tid] = rec

    # ---------------- link timing ----------------
    def is_decision(self, t):
        return t == 0 or (t % self.period) == self.openn - 1

    def transmit(self, t):
        if t % self.period < self.openn:
            return t
        return (t // self.period + 1) * self.period

    def next_decision(self, t):
        u = t + 1
        while (u % self.period) != self.openn - 1:
            u += 1
        return u

    def solar(self, k):
        v = self.speak * self.eff * math.sin(math.pi * (k + self.smargin) / (self.T + 2 * self.smargin))
        return v if v > 0 else 0.0

    # ---------------- telemetry ----------------
    def ingest(self, packets):
        for p in packets or []:
            try:
                k = int(p["tick"])
            except Exception:
                continue
            self.pk[k] = p
            if k > self.latest:
                self.latest = k

    def mark_bad(self, x, y, val):
        i, j = self.cell_of(x, y)
        u = j * self.CX + i
        self.pen[u] = max(self.pen.get(u, 0.0), val)

    def apply(self, c, pkt):
        c["status"] = "done"
        if c["kind"] != "drive":
            return
        m = c["m"]
        full = True
        if pkt is not None:
            wo = pkt.get("wheel_odometry")
            if wo is not None and float(wo) < m - 1e-3:
                m = max(0.0, float(wo))
                full = False
        if m <= 1e-6:
            return
        x, y = self.ekf.s[0], self.ekf.s[1]
        ex, ey, wheel, en, stop = self.sim(x, y, c["h"], m)
        D = (ex - x, ey - y)
        self.ekf.predict(D)
        if pkt is not None and full and not stop:
            vo = pkt.get("visual_odometry")
            d = math.hypot(D[0], D[1])
            if vo is not None and d > 0.5 and float(vo) > 0:
                sig = self.vo_noise.get(pkt.get("terrain"), 0.05)
                self.ekf.vo(float(vo), d, (sig * float(vo)) ** 2 + (0.03 * d) ** 2 + 1e-4)

    def process(self):
        while self.ekf_tick < self.latest:
            k = self.ekf_tick + 1
            pkt = self.pk.get(k)
            cid_s = self.by_tick.get(k)
            if pkt is not None:
                evs = pkt.get("events") or []
                ex = []
                for e in evs:
                    if isinstance(e, dict) and e.get("type") == "command_executed":
                        ex.append(e.get("command_id"))
                for cid in ex:
                    if cid in self.cmds:
                        self.apply(self.cmds[cid], pkt)
                if cid_s is not None and cid_s not in ex:
                    c = self.cmds[cid_s]
                    if c["status"] == "pending":
                        if c["kind"] == "drive" and float(pkt.get("wheel_odometry") or 0.0) <= 1e-6:
                            c["status"] = "cancelled"
                            for c2 in self.cmds.values():
                                if c2["status"] == "pending" and c2["exec"] > k and c2["sent"] < k:
                                    c2["status"] = "cancelled"
                            self.ekf.inflate(9.0)
                        elif c["kind"] != "drive":
                            c["status"] = "done"
                stop = False
                reason = ""
                for e in evs:
                    if isinstance(e, dict) and "stop" in str(e.get("type", "")):
                        stop = True
                        reason = str(e.get("reason", ""))
                if k > 0 and pkt.get("position"):
                    try:
                        self.ekf.fix(float(pkt["position"][0]), float(pkt["position"][1]), self.fix_var)
                    except Exception:
                        pass
                if stop:
                    for c2 in self.cmds.values():
                        if c2["status"] == "pending" and c2["exec"] > k and c2["sent"] <= k:
                            c2["status"] = "cancelled"
                    hx = 0.0
                    if cid_s is not None and self.cmds[cid_s]["kind"] == "drive":
                        hx = self.cmds[cid_s]["h"]
                    x, y = self.ekf.s[0], self.ekf.s[1]
                    ax = x + 3.0 * math.cos(math.radians(hx))
                    ay = y + 3.0 * math.sin(math.radians(hx))
                    self.mark_bad(ax, ay, 10.0)
                    if "slip" in reason:
                        self.mark_bad(x, y, 8.0)
                if pkt.get("terrain") == "sand":
                    x, y = self.ekf.s[0], self.ekf.s[1]
                    ci, cj = self.cell_of(x, y)
                    if self.tn[cj][ci] != "sand":
                        best = None
                        for dj in (-1, 0, 1):
                            for di in (-1, 0, 1):
                                i, j = ci + di, cj + dj
                                if 0 <= i < self.CX and 0 <= j < self.CY and self.crust[j][i] and self.tn[j][i] != "sand":
                                    d = math.hypot((i + 0.5) * self.cell - x, (j + 0.5) * self.cell - y)
                                    if best is None or d < best[0]:
                                        best = (d, i, j)
                        if best is not None:
                            _, i, j = best
                            self.tn[j][i] = "sand"
                            self.pen[j * self.CX + i] = 12.0
                if pkt.get("battery") is not None:
                    self.bat = float(pkt["battery"])
                    self.bat_tick = k
                    ch = pkt.get("charge")
                    if ch is not None and float(ch) > 0 and self.bat < self.cap - 10:
                        sraw = self.speak * math.sin(math.pi * (k + self.smargin) / (self.T + 2 * self.smargin))
                        if sraw > 0.05:
                            self.eff_samples.append(float(ch) / sraw)
                            srt = sorted(self.eff_samples)
                            self.eff = max(self.eff_lo, min(self.eff_hi, srt[len(srt) // 2]))
                for tid in pkt.get("sampled_targets") or []:
                    self.sampled.add(tid)
            else:
                if cid_s is not None and self.cmds[cid_s]["status"] == "pending":
                    self.apply(self.cmds[cid_s], None)
            self.ekf_tick = k

    def resolve_samples(self):
        for c in self.cmds.values():
            if c["kind"] == "sample" and not c.get("res") and c["exec"] <= self.latest:
                c["res"] = True
                if c["status"] != "cancelled" and c["tid"] not in self.sampled:
                    self.fails[c["tid"]] = self.fails.get(c["tid"], 0) + 1

    def predict_to(self, q):
        s = list(self.ekf.s)
        pend = sorted([c for c in self.cmds.values()
                       if c["status"] == "pending" and self.ekf_tick < c["exec"] < q], key=lambda c: c["exec"])
        for c in pend:
            if c["kind"] == "drive":
                ex, ey, wheel, en, stop = self.sim(s[0], s[1], c["h"], c["m"])
                Dx, Dy = ex - s[0], ey - s[1]
                cb, sb = math.cos(s[2]), math.sin(s[2])
                s[0] += s[3] * (cb * Dx - sb * Dy)
                s[1] += s[3] * (sb * Dx + cb * Dy)
        bat = self.bat
        for k in range(self.bat_tick + 1, q):
            bat = min(self.cap, bat + self.solar(k)) - self.idle
            cid = self.by_tick.get(k)
            if cid is not None and self.cmds[cid]["status"] != "cancelled":
                bat -= self.cmds[cid].get("cost", 0.0)
        return (s[0], s[1]), bat

    def bstep(self, bat, tick, cost):
        return min(self.cap, bat + self.solar(tick)) - self.idle - cost

    # ---------------- tour ----------------
    def plan_tour(self, t0, b0, keep, Tc, Ec, Tm, Em, Tb, Eb, Tcb, Ecb, budget):
        K = len(keep)
        V = [self.tg[a]["v"] for a in keep]
        LV = [self.tg[a]["lv"] for a in keep]
        DL = [self.tg[a]["dl"] for a in keep]
        TEND = self.TEND
        RES = self.RES
        cap = self.cap
        idle = self.idle
        sc = self.scost
        SC = [0.0] * (self.T + 3)
        for k in range(1, self.T + 3):
            SC[k] = SC[k - 1] + self.solar(k)
        nS = len(SC) - 1

        def SCf(x):
            if x <= 0:
                return 0.0
            if x >= nS:
                return SC[nS]
            i = int(x)
            return SC[i] + (x - i) * (SC[i + 1] - SC[i])

        def ev(seq):
            t = t0
            bat = b0
            val = 0.0
            mb = bat
            prev = -1
            for k in seq:
                if prev < 0:
                    dt = Tc[k]
                    de = Ec[k]
                else:
                    dt = Tm[prev][k]
                    de = Em[prev][k]
                if dt == INF:
                    return 0.0, INF, -INF
                t1 = t + dt
                bat = min(cap, bat + SCf(t1) - SCf(t) - idle * dt - de)
                if bat < mb:
                    mb = bat
                val += V[k] if t1 + 1.0 <= DL[k] else LV[k]
                bat -= sc
                t = t1 + 1.0
                prev = k
            if prev < 0:
                dt = Tcb
                de = Ecb
            else:
                dt = Tb[prev]
                de = Eb[prev]
            t1 = t + dt
            bat = min(cap, bat + SCf(t1) - SCf(t) - idle * dt - de)
            if bat < mb:
                mb = bat
            return val, t1, mb

        def feas(r):
            return r[1] <= TEND and r[2] >= RES

        def greedy(seq, alpha):
            seq = list(seq)
            cv, ct, cm = ev(seq)
            rem = [k for k in range(K) if k not in seq]
            while rem:
                best = None
                for k in rem:
                    opts = []
                    for pos in range(len(seq) + 1):
                        a = seq[pos - 1] if pos > 0 else -1
                        nb = seq[pos] if pos < len(seq) else None
                        d_in = Tc[k] if a < 0 else Tm[a][k]
                        if nb is None:
                            d_out = Tb[k]
                            d_old = Tcb if a < 0 else Tb[a]
                        else:
                            d_out = Tm[k][nb]
                            d_old = Tc[nb] if a < 0 else Tm[a][nb]
                        opts.append((d_in + 1.0 + d_out - d_old, pos))
                    opts.sort()
                    for dlt, pos in opts[:3]:
                        if ct + dlt > TEND + 1:
                            break
                        s2 = seq[:pos] + [k] + seq[pos:]
                        r = ev(s2)
                        if not feas(r):
                            continue
                        dv = r[0] - cv
                        if dv <= 1e-9:
                            continue
                        scv = dv / (max(0.5, r[1] - ct) ** alpha)
                        if best is None or scv > best[0]:
                            best = (scv, s2, r, k)
                if best is None:
                    break
                seq = best[1]
                cv, ct, cm = best[2]
                rem.remove(best[3])
            return seq

        def improve(seq):
            cur = ev(seq)
            rounds = 0
            changed = True
            while changed and rounds < 30:
                changed = False
                rounds += 1
                for i in range(len(seq)):
                    k = seq[i]
                    rest = seq[:i] + seq[i + 1:]
                    for pos in range(len(rest) + 1):
                        if pos == i:
                            continue
                        s2 = rest[:pos] + [k] + rest[pos:]
                        r = ev(s2)
                        if feas(r) and (r[0] > cur[0] + 1e-9 or (r[0] > cur[0] - 1e-9 and r[1] < cur[1] - 0.3)):
                            seq = s2
                            cur = r
                            changed = True
                            break
                    if changed:
                        break
            return seq

        prev = [keep.index(a) for a in self.tour if a in keep]

        def score(seq):
            r = ev(seq)
            if seq and not feas(r):
                return -INF
            b = 0.3 if (seq and prev and seq[0] == prev[0]) else 0.0
            return r[0] - 0.002 * r[1] + b

        if t0 + Tcb > TEND:
            return []
        seed = list(prev)
        while seed and not feas(ev(seed)):
            seed.pop()
        start = time.monotonic()
        cands = [seed]
        for s0, al in ((seed, 1.0), ([], 1.0), ([], 0.6), ([], 1.6)):
            if cands and time.monotonic() - start > budget:
                break
            sq = greedy(s0, al)
            sq = improve(sq)
            sq = greedy(sq, al)
            cands.append(sq)
        best = max(cands, key=score)
        bs = score(best)
        for i in range(len(best)):
            if time.monotonic() - start > budget * 1.5:
                break
            s2 = best[:i] + best[i + 1:]
            s2 = greedy(s2, 1.0)
            s2 = improve(s2)
            v = score(s2)
            if v > bs + 1e-6:
                best, bs = s2, v
        if best and not feas(ev(best)):
            return []
        return [keep[k] for k in best]

    # ---------------- paths ----------------
    def goal_pt(self, g):
        if g == "BASE":
            return self.base
        return (self.tg[g]["x"], self.tg[g]["y"])

    def backtrack(self, par, src, dst):
        path = [dst]
        guard = 0
        while path[-1] != src:
            pr = par[path[-1]]
            if pr < 0:
                return None
            path.append(pr)
            guard += 1
            if guard > 20000:
                return None
        path.reverse()
        return path

    def rchain(self, n):
        nodes = [n]
        guard = 0
        while n != self.base_node:
            n = self.rpar[n]
            if n < 0:
                return None
            nodes.append(n)
            guard += 1
            if guard > 20000:
                return None
        return nodes

    def make_poly(self, start_pt, nodes, gp):
        pts = [start_pt]
        if nodes:
            for n in nodes[1:]:
                pts.append(self.center(n))
        pts.append(gp)
        if len(pts) >= 3 and math.hypot(pts[-2][0] - gp[0], pts[-2][1] - gp[1]) < 4.0:
            pts.pop(-2)
        return pts

    def poly_first(self, g, p, ctx):
        gp = self.goal_pt(g)
        dst = self.base_node if g == "BASE" else self.tg[g]["node"]
        nodes = self.backtrack(ctx["par"], ctx["u0"], dst)
        if nodes is None:
            return [p, gp]
        return self.make_poly(p, nodes, gp)

    def poly_between(self, a, g):
        ap = self.goal_pt(a)
        gp = self.goal_pt(g)
        na = self.tg[a]["node"]
        if g == "BASE":
            nodes = self.rchain(na)
        else:
            nodes = self.backtrack(self.tg[a]["par"], na, self.tg[g]["node"])
        if nodes is None:
            return [ap, gp]
        return self.make_poly(ap, nodes, gp)

    def poly_base_from(self, p):
        nf = self.node_for(p[0], p[1])
        if nf is None:
            return [p, self.base]
        nodes = self.rchain(nf[1])
        if nodes is None:
            return [p, self.base]
        return self.make_poly(p, nodes, self.base)

    def lookahead(self, poly, idx, p, s):
        nseg = len(poly) - 1
        if nseg <= 0:
            return poly[-1], 0
        best = None
        for k in range(idx, min(nseg, idx + 6)):
            ax, ay = poly[k]
            bx, by = poly[k + 1]
            vx, vy = bx - ax, by - ay
            L2 = vx * vx + vy * vy
            tp = 0.0 if L2 < 1e-12 else max(0.0, min(1.0, ((p[0] - ax) * vx + (p[1] - ay) * vy) / L2))
            qx, qy = ax + tp * vx, ay + tp * vy
            d = math.hypot(p[0] - qx, p[1] - qy)
            if best is None or d < best[0] - 1e-9:
                best = (d, k, tp)
        if best is None:
            return poly[-1], max(0, nseg - 1)
        _, k, tp = best
        rem = s
        L = math.hypot(poly[k + 1][0] - poly[k][0], poly[k + 1][1] - poly[k][1])
        pos = tp * L
        while True:
            left = L - pos
            if rem <= left:
                if L < 1e-9:
                    return poly[k + 1], k
                fr = (pos + rem) / L
                return (poly[k][0] + fr * (poly[k + 1][0] - poly[k][0]),
                        poly[k][1] + fr * (poly[k + 1][1] - poly[k][1])), k
            rem -= left
            k += 1
            if k >= nseg:
                return poly[-1], nseg - 1
            L = math.hypot(poly[k + 1][0] - poly[k][0], poly[k + 1][1] - poly[k][1])
            pos = 0.0

    def solve(self, p, V, b, f):
        L = math.hypot(V[0], V[1])
        if L < 0.05:
            return None
        c, s = math.cos(-b), math.sin(-b)
        Tx = (c * V[0] - s * V[1]) / f
        Ty = (s * V[0] + c * V[1]) / f
        tl = math.hypot(Tx, Ty)
        ta = math.atan2(Ty, Tx)
        h = math.degrees(ta)
        m = min(self.maxm, max(0.05, tl / 0.9))
        best = None
        for it in range(4):
            ex, ey, wheel, en, stop = self.sim(p[0], p[1], h, m)
            Dx, Dy = ex - p[0], ey - p[1]
            dl = math.hypot(Dx, Dy)
            err = math.hypot(Dx - Tx, Dy - Ty)
            if best is None or err < best[0]:
                best = (err, h, m, Dx, Dy, en)
            if dl < 1e-4:
                break
            da = ta - math.atan2(Dy, Dx)
            da = (da + math.pi) % (2 * math.pi) - math.pi
            h += math.degrees(da)
            if stop:
                m = max(0.05, wheel - 0.3)
            else:
                m = min(self.maxm, max(0.05, m * tl / dl))
        err, h, m, Dx, Dy, en = best
        cb, sb = math.cos(b), math.sin(b)
        pred = (f * (cb * Dx - sb * Dy), f * (sb * Dx + cb * Dy))
        return h, m, pred, en

    # ---------------- command generation ----------------
    def gen(self, p, q, nslots, bat, tour, ctx):
        out = []
        goals = list(tour) + ["BASE"]
        gi = 0
        poly = self.poly_first(goals[0], p, ctx)
        pidx = 0
        b = self.ekf.s[2]
        f = self.ekf.s[3]
        tick = q
        lasth = self.plan_h
        guard = 0
        ff = ctx["ff"]
        consumed = set()
        while len(out) < nslots and guard < 60:
            guard += 1
            g = goals[gi]
            gp = self.goal_pt(g)
            d = math.hypot(gp[0] - p[0], gp[1] - p[1])
            if g != "BASE":
                nb = self.node_for(p[0], p[1])
                if nb is not None and self.rT[nb[1]] < INF:
                    est = (self.rT[nb[1]] + nb[0] / 4.5 + self.base_chord / 4.5) * ff + 1.0
                    if tick + est > self.TEND + 2:
                        goals = ["BASE"]
                        gi = 0
                        poly = self.poly_base_from(p)
                        pidx = 0
                        continue
            if g != "BASE" and d < 0.6:
                nbat = self.bstep(bat, tick, self.scost)
                if nbat < 6:
                    break
                out.append(({"action": "sample"}, {"kind": "sample", "tid": g, "cost": self.scost}))
                consumed.add(g)
                bat = nbat
                tick += 1
                gi += 1
                poly = self.poly_between(g, goals[gi])
                pidx = 0
                continue
            if g == "BASE" and d < ctx.get("home_tol", 0.9):
                break
            tgt, pidx = self.lookahead(poly, pidx, p, 4.6)
            res = self.solve(p, (tgt[0] - p[0], tgt[1] - p[1]), b, f)
            if res is None:
                res = self.solve(p, (gp[0] - p[0], gp[1] - p[1]), b, f)
                if res is None:
                    break
            h, m, pred, en = res
            if math.hypot(pred[0], pred[1]) < 0.05:
                break
            turn = abs(((h - lasth + 180.0) % 360.0) - 180.0)
            tname = self.terrain_at(p)
            cost = en * 1.2 + self.turn_k * turn * self.dcost.get(tname, 0.4)
            nbat = self.bstep(bat, tick, cost)
            if nbat < 8:
                break
            hh = round(h % 360.0, 3)
            if hh >= 360.0:
                hh = 0.0
            mm = round(min(self.maxm, max(0.05, m)), 3)
            out.append(({"action": "drive", "heading_deg": hh, "metres": mm},
                        {"kind": "drive", "h": hh, "m": mm, "cost": cost}))
            p = (p[0] + pred[0], p[1] + pred[1])
            bat = nbat
            tick += 1
            lasth = h
        self.plan_h = lasth
        self.tour = [a for a in goals if a != "BASE" and a not in consumed]
        return out

    def send(self, out, t):
        i = 0
        while i < len(out):
            chunk = out[i:i + 5]
            try:
                acks = self.tools.uplink([c[0] for c in chunk])
            except Exception:
                break
            for (cmd, meta), ack in zip(chunk, acks or []):
                try:
                    cid = ack.get("command_id")
                    ex = int(ack.get("execute_tick"))
                except Exception:
                    continue
                rec = dict(meta)
                rec.update({"exec": ex, "sent": t, "status": "pending", "id": cid})
                self.cmds[cid] = rec
                self.by_tick[ex] = cid
                if ex > self.last_exec:
                    self.last_exec = ex
            i += 5

    # ---------------- decision ----------------
    def refresh_targets(self):
        try:
            M = self.tools.map()
        except Exception:
            return
        for t in M.get("targets", []) or []:
            if t.get("id") not in self.tg:
                try:
                    self.add_target(t)
                except Exception:
                    pass

    def decide(self, t):
        self.refresh_targets()
        self.process()
        self.resolve_samples()
        tn = self.next_decision(t)
        tx = self.transmit(t)
        q = max(tx + self.delay + 1, self.last_exec + 1)
        horizon = min(self.transmit(tn) + self.delay, self.T - 1)
        n = horizon - q + 1
        if n <= 0:
            return
        p, bat = self.predict_to(q)
        f = max(0.7, min(1.3, self.ekf.s[3]))
        ff = 1.06 / f
        st = self.node_for(p[0], p[1])
        if st is None:
            st = (math.hypot(p[0] - self.base[0], p[1] - self.base[1]), self.base_node)
        d0, u0 = st
        _, cT, cE, cpar = self.dijkstra([(u0, 0.0, 0.0, 0.0)], pen=self.pen)
        toff = d0 / 4.5
        eoff = d0 * 0.45
        pend_s = set()
        for c in self.cmds.values():
            if c["kind"] == "sample" and c["status"] != "cancelled" and c["exec"] > self.latest:
                pend_s.add(c["tid"])
        bn = self.base_node
        bch = self.base_chord / 4.5
        keep = []
        for a, g in self.tg.items():
            if not g["ok"] or a in self.sampled or a in pend_s or self.fails.get(a, 0) >= 3:
                continue
            if cT[g["node"]] < INF and g["tt"][bn] < INF:
                keep.append(a)
        tour = []
        if cT[bn] < INF:
            Tcb = (cT[bn] + toff + bch) * ff + 0.7
            Ecb = (cE[bn] + eoff + self.base_chord * 0.45) * 1.15
        else:
            Tcb = (self.rT[u0] + toff + bch) * ff + 0.7
            Ecb = (self.rE[u0] + eoff + self.base_chord * 0.45) * 1.15
        if keep:
            K = len(keep)
            Tc = []
            Ec = []
            for a in keep:
                g = self.tg[a]
                Tc.append((cT[g["node"]] + toff + g["chord"] / 4.5) * ff + 0.7)
                Ec.append((cE[g["node"]] + eoff + g["chord"] * 0.45) * 1.15)
            Tm = [[INF] * K for _ in range(K)]
            Em = [[INF] * K for _ in range(K)]
            Tb = [INF] * K
            Eb = [INF] * K
            for xi, a in enumerate(keep):
                ga = self.tg[a]
                tta, eea, ca = ga["tt"], ga["ee"], ga["chord"]
                for yi, bb in enumerate(keep):
                    if xi == yi:
                        continue
                    gb = self.tg[bb]
                    nb = gb["node"]
                    if tta[nb] < INF:
                        Tm[xi][yi] = (tta[nb] + (ca + gb["chord"]) / 4.5) * ff + 0.7
                        Em[xi][yi] = (eea[nb] + (ca + gb["chord"]) * 0.45) * 1.15
                Tb[xi] = (tta[bn] + ca / 4.5 + bch) * ff + 0.7
                Eb[xi] = (ga["ee"][bn] + (ca + self.base_chord) * 0.45) * 1.15
            elapsed = time.monotonic() - self.wall0
            budget = 1.2 if elapsed < 12 * 60 else (0.4 if elapsed < 17 * 60 else 0.05)
            tour = self.plan_tour(float(q), bat, keep, Tc, Ec, Tm, Em, Tb, Eb, Tcb, Ecb, budget)
        ctx = {"u0": u0, "par": cpar, "ff": ff, "home_tol": 0.9}
        out = self.gen(p, q, n, bat, tour, ctx)
        if out:
            self.send(out, t)

    def run(self):
        t = 0
        loops = 0
        while True:
            loops += 1
            if loops > 5000:
                return
            if t < self.T and self.is_decision(t):
                try:
                    self.decide(t)
                except Exception:
                    pass
            nt = self.next_decision(t) if t < self.T else t + 1
            steps = max(1, nt - t)
            while steps > 0:
                k = min(5, steps)
                r = self.tools.advance(k)
                t = int(r.get("current_tick", t + k))
                self.ingest(r.get("packets") or [])
                steps -= k
                if r.get("episode_complete"):
                    return


def play(tools):
    auto = None
    try:
        auto = Auto(tools)
    except Exception:
        auto = None
    if auto is None:
        for _ in range(1000):
            try:
                r = tools.advance(5)
            except Exception:
                return
            if r.get("episode_complete"):
                return
        return
    auto.run()
```