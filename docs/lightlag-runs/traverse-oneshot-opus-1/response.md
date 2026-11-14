The module below plays the whole mission. It has not been run against the simulator, so every part of it is untested.

These points rest on my own guesses about details the rules leave open:
- **Odometry:** `wheel_odometry` is taken to report only the drive executed in that packet's tick. If a value above 5 m ever appears, the code switches to treating it as cumulative.
- **Safety-stop clearing:** the code assumes a stop at tick k cleared only commands sent before tick k. Commands sent at or after tick k are assumed to still run.
- **Solar efficiency:** each `charge` value is assumed to be the gain for the sun at that same packet tick.

**How it works:**
- **Ground model.** Every 5 m cell gets its steepest slope from the map. Cells steeper than 0.33 are blocked, and cells that are nearly steep or next to blocked ones cost extra. From each target and from the lander, a search over the cells gives the time and energy to reach it from anywhere on the map.
- **Route choice.** Targets are added one at a time to a route that ends at the lander. Each step adds the one that brings the most value per extra tick, then the order is improved by reversing sections. Several randomised tries are kept within a time budget.
  - Each route is checked for deadlines, time to get home before tick 420, and a battery that must not drop below 10.
  - The battery forecast uses the sun formula and the solar efficiency measured from the `charge` telemetry.
- **Commands.** One command is sent every tick, so about four are always queued. Each is planned from where the rover is predicted to be when it runs, after all earlier commands have been run through the published `drive` model.
- **Position tracking.** A small filter tracks position and the heading bias, using visual odometry for distance and the noisy position fixes. Each terrain's hidden slip is estimated from wheel versus visual odometry.
- **Safety.** Before sending a drive, the code simulates it from three nearby start points and rejects it if any would hit steep ground. Otherwise it tries other headings or shorter drives, and waits if nothing is safe.
- **Recovery.** A target is sampled once the predicted distance is under 1 m, and a failed sample puts it back in the plan. New targets are picked up as they are announced.
- **Going home.** The rover is forced home when the remaining time gets tight.

```python
import math
import heapq
import random
import time

TC = {"b": "bedrock", "r": "regolith", "s": "sand", "k": "rocks"}
INF = float("inf")


class Surface:
    def __init__(self, cell, elevation_cm, terrain):
        self.cell = float(cell)
        self.h = [[v / 100.0 for v in row] for row in elevation_cm]
        self.ny = len(self.h)
        self.nx = len(self.h[0])
        self.codes = [str(r) for r in terrain]
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


def sim_drive(surface, physics, x, y, heading_deg, metres, slip_base, noise=0.0):
    radians = math.radians(heading_deg)
    ux, uy = math.cos(radians), math.sin(radians)
    segment_full = physics["segment_m"]
    gain, side, cost = physics["slip_grade_gain"], physics["side_slip_gain"], physics["drive_cost_per_wheel_m"]
    climb, slip_max, max_tilt = physics["climb_cost_per_m"], physics["slip_max"], physics["max_tilt"]
    width, height = surface.width, surface.height
    remaining = float(metres)
    wheel = ground = energy = 0.0
    stop = None
    here, gx, gy, code = surface.sample(x, y)
    while remaining > 1e-9:
        segment = min(segment_full, remaining)
        name = TC.get(code, "regolith")
        grade = gx * ux + gy * uy
        cross = -gx * uy + gy * ux
        slip = slip_base[name] + gain[name] * (grade if grade > 0 else 0.0) + noise
        slip = 0.0 if slip < 0 else (slip_max if slip > slip_max else slip)
        forward = segment * (1.0 - slip)
        sideways = segment * side[name] * cross
        nx_ = x + ux * forward + uy * sideways
        ny_ = y + uy * forward - ux * sideways
        if not (0.0 <= nx_ <= width and 0.0 <= ny_ <= height):
            stop = "map_boundary"
            break
        there, ngx, ngy, ncode = surface.sample(nx_, ny_)
        if math.hypot(ngx, ngy) > max_tilt:
            stop = "tilt"
            break
        spent = segment * cost[name] + climb * (there - here if there > here else 0.0)
        energy += spent
        wheel += segment
        ground += math.hypot(nx_ - x, ny_ - y)
        remaining -= segment
        x, y, here, gx, gy, code = nx_, ny_, there, ngx, ngy, ncode
    return {"x": x, "y": y, "wheel": wheel, "ground": ground, "energy": energy, "stop": stop}


class AP:
    def __init__(self, tools):
        self.tools = tools
        R = tools.rules()
        M = tools.map()
        self.R = R
        self.delay = int(R.get("delay_ticks", 3))
        self.T = int(R.get("max_ticks", 420))
        self.cap = float(R.get("battery_capacity", 100.0))
        self.idle = float(R.get("idle_cost", 0.15))
        self.scost = float(R.get("sample_cost", 2.0))
        self.peak = float(R.get("solar_peak", 2.8))
        er = R.get("solar_efficiency_range", [0.8, 1.0])
        self.eff_lo, self.eff_hi = float(er[0]), float(er[1])
        self.eff = self.eff_lo + 0.25 * (self.eff_hi - self.eff_lo)
        self.effs = []
        self.smargin = float(R.get("sun_margin_ticks", 56))
        self.phys = R["physics"]
        self.maxm = float(R.get("max_metres_per_drive", 5.0))
        self.sbr = self.phys["slip_base_ranges"]
        self.sb = {k: (v[0] + v[1]) / 2.0 for k, v in self.sbr.items()}
        self.surf = Surface(M["cell_m"], M["elevation_cm"], M["terrain"])
        self.base = (float(M["base"][0]), float(M["base"][1]))
        self.build_cum()
        self.build_grid()
        self.targets = {}
        self.fields = {}
        self.tcell = {}
        self.fields["__base__"] = self.make_field(*self.base)
        self.need_replan = True
        self.refresh_targets(M)
        # filter
        self.x, self.y = self.base
        self.b = 0.0
        self.P = [[1e-4, 0.0, 0.0], [0.0, 1e-4, 0.0], [0.0, 0.0, 0.0026]]
        self.bat = float(R.get("initial_battery", 100.0))
        self.last_pkt = -1
        self.cum = False
        self.pw = 0.0
        self.pv = 0.0
        self.alive = True
        self.acks = {}
        self.last_exec = 0
        self.sampled = set()
        self.attempts = {}
        self.route = []
        self.last_plan = -1000
        self.discover_flag = False
        self.last_map_check = 0

    # ---------------- solar ----------------
    def solar(self, tau):
        return self.peak * self.eff * math.sin(math.pi * (tau + self.smargin) / (self.T + 2 * self.smargin))

    def build_cum(self):
        L = self.T + 300
        c = [0.0] * (L + 1)
        for i in range(1, L + 1):
            c[i] = c[i - 1] + max(0.0, self.solar(i))
        self.cumarr = c

    def cumf(self, t):
        c = self.cumarr
        L = len(c) - 1
        if t <= 0:
            return 0.0
        if t >= L:
            return c[L]
        i = int(t)
        f = t - i
        return c[i] + (c[i + 1] - c[i]) * f

    def sint(self, a, b):
        return self.cumf(b) - self.cumf(a)

    # ---------------- grid ----------------
    def build_grid(self):
        s = self.surf
        nxc, nyc = s.nx - 1, s.ny - 1
        self.nxc, self.nyc = nxc, nyc
        n = nxc * nyc
        self.ncell = n
        cell = s.cell
        ms = [0.0] * n
        blk = [False] * n
        hc = [0.0] * n
        tn = ["regolith"] * n
        for j in range(nyc):
            for i in range(nxc):
                c = j * nxc + i
                m = s.cell_max_slope(i, j)
                ms[c] = m
                blk[c] = m > 0.33
                hc[c] = (s.h[j][i] + s.h[j][i + 1] + s.h[j + 1][i] + s.h[j + 1][i + 1]) / 4.0
                tn[c] = TC.get(s.codes[j][i], "regolith")
        self.blocked = blk
        dirs = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
        pen = [1.0] * n
        for j in range(nyc):
            for i in range(nxc):
                c = j * nxc + i
                if blk[c]:
                    continue
                near = False
                for di, dj in dirs:
                    ii, jj = i + di, j + dj
                    if 0 <= ii < nxc and 0 <= jj < nyc and blk[jj * nxc + ii]:
                        near = True
                        break
                p = 1.0
                if near:
                    p += 0.25
                if ms[c] > 0.27:
                    p += 0.4
                pen[c] = p
        gain = self.phys["slip_grade_gain"]
        cost = self.phys["drive_cost_per_wheel_m"]
        climb = self.phys["climb_cost_per_m"]
        LAM = 0.1
        out = [[] for _ in range(n)]
        inc = [[] for _ in range(n)]
        for j in range(nyc):
            for i in range(nxc):
                u = j * nxc + i
                if blk[u]:
                    continue
                for di, dj in dirs:
                    ii, jj = i + di, j + dj
                    if not (0 <= ii < nxc and 0 <= jj < nyc):
                        continue
                    v = jj * nxc + ii
                    if blk[v]:
                        continue
                    if di != 0 and dj != 0:
                        if blk[j * nxc + ii] or blk[jj * nxc + i]:
                            continue
                    L = cell * (1.4142135 if (di and dj) else 1.0)
                    dh = hc[v] - hc[u]
                    grade = dh / L
                    tu, tv = tn[u], tn[v]
                    su = self.sb[tu] + gain[tu] * max(0.0, grade)
                    sv = self.sb[tv] + gain[tv] * max(0.0, grade)
                    sl = min(0.9, (su + sv) / 2.0)
                    wheel = L / (1.0 - sl)
                    t = wheel / self.maxm * (pen[u] + pen[v]) / 2.0
                    e = wheel * (cost[tu] + cost[tv]) / 2.0 + climb * max(0.0, dh)
                    J = t + LAM * e
                    out[u].append((v, J, t, e))
                    inc[v].append((u, J, t, e))
        self.out = out
        self.inc = inc

    def cell_of(self, x, y):
        c = self.surf.cell
        i = min(self.nxc - 1, max(0, int(x / c)))
        j = min(self.nyc - 1, max(0, int(y / c)))
        return j * self.nxc + i

    def center(self, c):
        cell = self.surf.cell
        return ((c % self.nxc + 0.5) * cell, (c // self.nxc + 0.5) * cell)

    def make_field(self, x, y):
        n = self.ncell
        dist = [INF] * n
        tim = [INF] * n
        en = [INF] * n
        heap = []
        c0 = self.cell_of(x, y)
        if not self.blocked[c0]:
            dist[c0] = 0.0
            tim[c0] = 0.0
            en[c0] = 0.0
            heap.append((0.0, c0))
        else:
            i0, j0 = c0 % self.nxc, c0 // self.nxc
            for dj in range(-2, 3):
                for di in range(-2, 3):
                    i, j = i0 + di, j0 + dj
                    if 0 <= i < self.nxc and 0 <= j < self.nyc:
                        c = j * self.nxc + i
                        if not self.blocked[c]:
                            cx, cy = self.center(c)
                            d = math.hypot(cx - x, cy - y)
                            tt = d / 4.0
                            dist[c] = tt
                            tim[c] = tt
                            en[c] = d * 0.4
                            heap.append((tt, c))
            heapq.heapify(heap)
        inc = self.inc
        hpop, hpush = heapq.heappop, heapq.heappush
        while heap:
            d, v = hpop(heap)
            if d > dist[v]:
                continue
            tv = tim[v]
            ev = en[v]
            for (u, J, t, e) in inc[v]:
                nd = d + J
                if nd < dist[u]:
                    dist[u] = nd
                    tim[u] = tv + t
                    en[u] = ev + e
                    hpush(heap, (nd, u))
        return (dist, tim, en)

    def lookup(self, fld, x, y):
        tim, en = fld[1], fld[2]
        c = self.cell_of(x, y)
        if tim[c] < INF:
            return tim[c], en[c]
        i0, j0 = c % self.nxc, c // self.nxc
        for r in (1, 2, 3):
            best = None
            for dj in range(-r, r + 1):
                for di in range(-r, r + 1):
                    i, j = i0 + di, j0 + dj
                    if 0 <= i < self.nxc and 0 <= j < self.nyc:
                        cc = j * self.nxc + i
                        if tim[cc] < INF:
                            cx, cy = self.center(cc)
                            ex = math.hypot(cx - x, cy - y) / 4.0
                            v = tim[cc] + ex
                            if best is None or v < best[0]:
                                best = (v, en[cc] + ex * 2.0)
            if best:
                return best
        return INF, INF

    # ---------------- targets ----------------
    def refresh_targets(self, M=None):
        if M is None:
            M = self.tools.map()
        for tg in M.get("targets", []):
            tid = str(tg["id"])
            if tid in self.targets:
                continue
            v = float(tg.get("value", 1.0))
            dl = tg.get("deadline_tick")
            lv = tg.get("late_value")
            if lv is None:
                lv = v * 0.25 if dl is not None else v
            info = {"x": float(tg["x"]), "y": float(tg["y"]), "value": v,
                    "deadline": (None if dl is None else int(dl)), "late": float(lv)}
            self.targets[tid] = info
            self.tcell[tid] = self.cell_of(info["x"], info["y"])
            try:
                self.fields[tid] = self.make_field(info["x"], info["y"])
            except Exception:
                pass
            self.need_replan = True

    # ---------------- filter ----------------
    def ekf_predict(self, dx, dy, q, qb):
        self.x += dx
        self.y += dy
        F = [[1.0, 0.0, -dy], [0.0, 1.0, dx], [0.0, 0.0, 1.0]]
        P = self.P
        FP = [[sum(F[i][m] * P[m][j] for m in range(3)) for j in range(3)] for i in range(3)]
        Pn = [[sum(FP[i][m] * F[j][m] for m in range(3)) for j in range(3)] for i in range(3)]
        Pn[0][0] += q
        Pn[1][1] += q
        Pn[2][2] += qb
        self.P = Pn

    def ekf_update(self, zx, zy, r):
        P = self.P
        s00 = P[0][0] + r
        s01 = P[0][1]
        s10 = P[1][0]
        s11 = P[1][1] + r
        det = s00 * s11 - s01 * s10
        if abs(det) < 1e-12:
            return
        i00, i01, i10, i11 = s11 / det, -s01 / det, -s10 / det, s00 / det
        K = [[P[i][0] * i00 + P[i][1] * i10, P[i][0] * i01 + P[i][1] * i11] for i in range(3)]
        vx, vy = zx - self.x, zy - self.y
        self.x += K[0][0] * vx + K[0][1] * vy
        self.y += K[1][0] * vx + K[1][1] * vy
        self.b += K[2][0] * vx + K[2][1] * vy
        self.b = max(-0.17, min(0.17, self.b))
        Pn = [[P[i][j] - (K[i][0] * P[0][j] + K[i][1] * P[1][j]) for j in range(3)] for i in range(3)]
        for i in range(3):
            for j in range(i + 1, 3):
                m = (Pn[i][j] + Pn[j][i]) / 2.0
                Pn[i][j] = Pn[j][i] = m
            if Pn[i][i] < 1e-8:
                Pn[i][i] = 1e-8
        self.P = Pn

    # ---------------- telemetry ----------------
    def process(self):
        log = self.tools.telemetry_log()
        pk = [p for p in log if int(p.get("tick", -1)) > self.last_pkt]
        pk.sort(key=lambda p: int(p["tick"]))
        for p in pk:
            try:
                self.handle(p)
            except Exception:
                self.last_pkt = max(self.last_pkt, int(p.get("tick", self.last_pkt)))

    def handle(self, p):
        k = int(p["tick"])
        if self.last_pkt < 0:
            pos = p["position"]
            self.x, self.y = float(pos[0]), float(pos[1])
            self.bat = float(p.get("battery", self.bat))
            self.pw = float(p.get("wheel_odometry") or 0.0)
            self.pv = float(p.get("visual_odometry") or 0.0)
            self.last_pkt = k
            return
        a = self.acks.get(k)
        w = float(p.get("wheel_odometry") or 0.0)
        v = float(p.get("visual_odometry") or 0.0)
        if not self.cum and w > self.maxm + 1e-6:
            self.cum = True
        if self.cum:
            dw, dv = max(0.0, w - self.pw), max(0.0, v - self.pv)
        else:
            dw, dv = w, v
        self.pw, self.pv = w, v
        if a and not a["cleared"] and a["cmd"].get("action") == "drive":
            cmd = a["cmd"]
            Mc = float(cmd["metres"])
            if dw > 1e-6:
                hdg = float(cmd["heading_deg"]) + math.degrees(self.b)
                r = sim_drive(self.surf, self.phys, self.x, self.y, hdg, dw, self.sb)
                Dx, Dy = r["x"] - self.x, r["y"] - self.y
                g = math.hypot(Dx, Dy)
                if dw >= 2.0 and dv > 0:
                    terr = TC.get(self.surf.sample(self.x, self.y)[3], "regolith")
                    resid = (g / dw) - (dv / dw)
                    lo, hi = self.sbr[terr]
                    self.sb[terr] = min(hi, max(lo, self.sb[terr] + 0.08 * resid))
                if g > 1e-6 and dv > 0:
                    s = dv / g
                    Dx *= s
                    Dy *= s
                q = (0.05 * dv) ** 2 + (dv * 0.03) ** 2 + 0.01
                self.ekf_predict(Dx, Dy, q, 1.5e-5)
            if dw < Mc - 0.05:
                for et, aa in self.acks.items():
                    if et > k and aa["sent"] < k:
                        aa["cleared"] = True
                for tid, e in list(self.attempts.items()):
                    aa = self.acks.get(e)
                    if aa and aa["cleared"]:
                        del self.attempts[tid]
                self.need_replan = True
        pos = p.get("position")
        if pos is not None and k > 0:
            zx, zy = float(pos[0]), float(pos[1])
            W, H = self.surf.width, self.surf.height
            if 0.01 < zx < W - 0.01 and 0.01 < zy < H - 0.01:
                self.ekf_update(zx, zy, 1.0)
        bat = p.get("battery")
        if bat is not None:
            bat = float(bat)
            ch = p.get("charge")
            if ch is not None and bat < self.cap - 3.0 and k > 0:
                sv = self.peak * math.sin(math.pi * (k + self.smargin) / (self.T + 2 * self.smargin))
                if sv > 0.1 and float(ch) > 0:
                    est = float(ch) / sv
                    if self.eff_lo - 0.05 <= est <= self.eff_hi + 0.05:
                        self.effs.append(est)
                        sl = sorted(self.effs)
                        med = sl[len(sl) // 2]
                        ne = min(self.eff_hi, max(self.eff_lo, med - 0.005))
                        if abs(ne - self.eff) > 0.004:
                            self.eff = ne
                            self.build_cum()
            self.bat = bat
        st = p.get("sampled_targets")
        if st:
            for s in st:
                self.sampled.add(str(s))
        if p.get("alive") is False:
            self.alive = False
        ev = p.get("events") or []
        for e in ev:
            if "discover" in str(e).lower():
                self.discover_flag = True
        self.last_pkt = k
        for tid, e in list(self.attempts.items()):
            if self.last_pkt >= e:
                del self.attempts[tid]
                self.need_replan = True

    # ---------------- prediction ----------------
    def predict_to(self, e0):
        x, y, bat = self.x, self.y, self.bat
        bdeg = math.degrees(self.b)
        for tau in range(self.last_pkt + 1, e0):
            bat = min(self.cap, bat + self.solar(tau)) - self.idle
            a = self.acks.get(tau)
            if a and not a["cleared"]:
                c = a["cmd"]
                if c.get("action") == "drive":
                    r = sim_drive(self.surf, self.phys, x, y, float(c["heading_deg"]) + bdeg,
                                  float(c["metres"]), self.sb)
                    x, y = r["x"], r["y"]
                    bat -= r["energy"]
                elif c.get("action") == "sample":
                    bat -= self.scost
        return x, y, bat

    # ---------------- planning ----------------
    def replan(self, t0, px, py, b0, budget):
        tstart = time.perf_counter()
        fb = self.fields["__base__"]
        cands = []
        Tm = {"S": {}}
        Em = {"S": {}}
        for tid, info in self.targets.items():
            if tid in self.sampled or tid in self.attempts or tid not in self.fields:
                continue
            ts, es = self.lookup(self.fields[tid], px, py)
            tb, eb = self.lookup(fb, info["x"], info["y"])
            if ts == INF or tb == INF:
                continue
            cands.append(tid)
            Tm["S"][tid] = ts
            Em["S"][tid] = es
        tb, eb = self.lookup(fb, px, py)
        Tm["S"]["B"] = tb
        Em["S"]["B"] = eb
        for a in cands:
            ia = self.targets[a]
            Tm[a] = {}
            Em[a] = {}
            for bb in cands:
                if bb == a:
                    continue
                t_, e_ = self.lookup(self.fields[bb], ia["x"], ia["y"])
                Tm[a][bb] = t_
                Em[a][bb] = e_
            t_, e_ = self.lookup(fb, ia["x"], ia["y"])
            Tm[a]["B"] = t_
            Em[a]["B"] = e_
        tgi = {k: (self.targets[k]["value"], self.targets[k]["deadline"], self.targets[k]["late"]) for k in cands}
        FAC = 1.1
        Tlim = self.T - 3.0
        reserve = 10.0
        idle, scost, cap = self.idle, self.scost, self.cap
        sint = self.sint

        def ev(route):
            t = float(t0)
            b = b0
            val = 0.0
            mb = b
            prev = "S"
            for k in route:
                tl = Tm[prev][k] * FAC + 1.0
                ts = t + tl + 1.0
                tg = tgi[k]
                dl = tg[1]
                val += tg[0] if (dl is None or ts <= dl) else tg[2]
                b += sint(t, ts) - idle * (ts - t) - Em[prev][k] - scost
                if b < mb:
                    mb = b
                if b > cap:
                    b = cap
                t = ts
                prev = k
            tl = Tm[prev]["B"] * FAC + 1.0
            b += sint(t, t + tl) - idle * tl - Em[prev]["B"]
            if b < mb:
                mb = b
            t += tl
            return (val, t, mb, (t <= Tlim and mb >= reserve))

        def better(v1, v2):
            if not v1[3]:
                return False
            if not v2[3]:
                return True
            if v1[0] > v2[0] + 1e-9:
                return True
            if abs(v1[0] - v2[0]) <= 1e-9 and v1[1] < v2[1] - 1e-6:
                return True
            return False

        rng = random.Random(t0 * 7919 + len(cands))

        def insert_all(route, noise):
            cur = ev(route)
            if not cur[3]:
                return route, cur
            rem = [k for k in cands if k not in route]
            while rem:
                opts = []
                n = len(route)
                for k in rem:
                    vk = tgi[k][0]
                    for p in range(n + 1):
                        a = route[p - 1] if p > 0 else "S"
                        c = route[p] if p < n else "B"
                        dt = Tm[a][k] + Tm[k][c] - Tm[a][c] + 2.0
                        if dt < 0.5:
                            dt = 0.5
                        sc = vk / dt
                        if noise:
                            sc *= 1.0 + noise * (rng.random() - 0.5)
                        opts.append((sc, k, p))
                opts.sort(key=lambda o: -o[0])
                best = None
                bg = 0.0
                for sc, k, p in opts[:30]:
                    r = route[:p] + [k] + route[p:]
                    v = ev(r)
                    if not v[3]:
                        continue
                    dv = v[0] - cur[0]
                    if dv <= 1e-9:
                        continue
                    g = dv / max(0.5, v[1] - cur[1] + 1.0)
                    if best is None or g > bg:
                        best = (r, v, k)
                        bg = g
                if best is None:
                    break
                route, cur, k = best
                rem.remove(k)
            return route, cur

        def two_opt(route, cur):
            loops = 0
            improved = True
            while improved and loops < 3:
                improved = False
                loops += 1
                n = len(route)
                for i in range(n - 1):
                    for j in range(i + 1, n):
                        r = route[:i] + route[i:j + 1][::-1] + route[j + 1:]
                        v = ev(r)
                        if better(v, cur):
                            route, cur = r, v
                            improved = True
                if time.perf_counter() - tstart > budget * 1.5:
                    break
            return route, cur

        best_r = []
        best_v = ev([])
        prev = [k for k in self.route if k in cands]
        # validate prev prefix feasibility
        seeds = [(prev, 0.0), ([], 0.0)]
        it = 0
        while True:
            if it < len(seeds):
                seed, noise = seeds[it]
            else:
                seed, noise = [], 0.7
            it += 1
            pv = ev(seed)
            if not pv[3]:
                seed = []
            r, v = insert_all(list(seed), noise)
            r, v = two_opt(r, v)
            r, v = insert_all(r, 0.0)
            if better(v, best_v):
                best_r, best_v = r, v
            if time.perf_counter() - tstart > budget:
                break
            if it > 60:
                break
        self.route = best_r
        self.need_replan = False
        self.last_plan = t0

    def cleanup_route(self):
        self.route = [k for k in self.route if k not in self.sampled and k not in self.attempts
                      and k in self.targets]

    # ---------------- navigation ----------------
    def los(self, x0, y0, x1, y1):
        L = math.hypot(x1 - x0, y1 - y0)
        n = int(L / 0.5) + 1
        for s in range(1, n + 1):
            f = s / n
            if f * L < 0.5:
                continue
            x = x0 + (x1 - x0) * f
            y = y0 + (y1 - y0) * f
            if not (0 <= x <= self.surf.width and 0 <= y <= self.surf.height):
                return False
            if self.blocked[self.cell_of(x, y)]:
                return False
        return True

    def chain(self, c, fld, n):
        dist = fld[0]
        res = []
        cur = c
        for _ in range(n):
            best = None
            bv = INF
            dc = dist[cur]
            for (v, J, t, e) in self.out[cur]:
                if dist[v] < dc:
                    val = J + dist[v]
                    if val < bv:
                        bv = val
                        best = v
            if best is None:
                break
            res.append(best)
            cur = best
            if dist[cur] <= 0:
                break
        return res

    def sim(self, x, y, hdg, M):
        return sim_drive(self.surf, self.phys, x, y, hdg, M, self.sb)

    def safe(self, px, py, hdg, M, check_end):
        rad = math.radians(hdg)
        ux, uy = math.cos(rad), math.sin(rad)
        for off in (0.0, 0.8, -0.8):
            sx, sy = px - uy * off, py + ux * off
            if not (0 <= sx <= self.surf.width and 0 <= sy <= self.surf.height):
                continue
            r = self.sim(sx, sy, hdg, M)
            if r["stop"] is not None:
                if off == 0.0 or r["stop"] == "tilt":
                    return None
            if off == 0.0:
                res = r
                if check_end and self.blocked[self.cell_of(r["x"], r["y"])] and not self.blocked[self.cell_of(px, py)]:
                    return None
        return res

    def land_metres(self, px, py, hdg, d):
        M = min(self.maxm, max(0.1, d / 0.9))
        for _ in range(3):
            r = self.sim(px, py, hdg, M)
            g = math.hypot(r["x"] - px, r["y"] - py)
            if g < 1e-3:
                break
            M = min(self.maxm, max(0.1, M * d / g))
        return M

    def nav(self, px, py, gx, gy, fld):
        dist = fld[0]
        d = math.hypot(gx - px, gy - py)
        bdeg = math.degrees(self.b)
        exact = False
        aim = None
        c = self.cell_of(px, py)
        if d <= 12.0 and self.los(px, py, gx, gy):
            aim = (gx, gy)
            exact = True
        else:
            ch = self.chain(c, fld, 6)
            if not ch:
                if self.blocked[c] or dist[c] == INF:
                    i0, j0 = c % self.nxc, c // self.nxc
                    best = None
                    for r in (1, 2, 3):
                        for dj in range(-r, r + 1):
                            for di in range(-r, r + 1):
                                i, j = i0 + di, j0 + dj
                                if 0 <= i < self.nxc and 0 <= j < self.nyc:
                                    cc = j * self.nxc + i
                                    if not self.blocked[cc] and dist[cc] < INF:
                                        cx, cy = self.center(cc)
                                        vv = dist[cc] + math.hypot(cx - px, cy - py) / 4.0
                                        if best is None or vv < best[0]:
                                            best = (vv, cc)
                        if best:
                            break
                    aim = self.center(best[1]) if best else (gx, gy)
                else:
                    aim = (gx, gy)
            else:
                for cc in reversed(ch):
                    cx, cy = self.center(cc)
                    if self.los(px, py, cx, cy):
                        aim = (cx, cy)
                        break
                if aim is None:
                    aim = self.center(ch[0])
                if dist[ch[-1]] <= 0 and self.los(px, py, gx, gy) and d < 20:
                    aim = (gx, gy)
        da = math.hypot(aim[0] - px, aim[1] - py)
        if da < 1e-6:
            aim = (gx, gy)
            da = d
        if da < 1e-6:
            return None
        hdg = math.degrees(math.atan2(aim[1] - py, aim[0] - px))
        if exact and d < self.maxm * 1.15:
            M = self.land_metres(px, py, hdg, d)
        else:
            M = min(self.maxm, max(1.5, da / 0.9))
        r = self.safe(px, py, hdg, M, not exact)
        if r is None:
            cands = []
            for delta in (15, -15, 30, -30, 45, -45, 60, -60, 90, -90, 120, -120, 150, -150, 180):
                for MM in (min(M, self.maxm), 2.5):
                    h2 = hdg + delta
                    rr = self.safe(px, py, h2, MM, True)
                    if rr is not None:
                        ec = self.cell_of(rr["x"], rr["y"])
                        val = dist[ec] if dist[ec] < INF else 1e9
                        val += 0.02 * abs(delta)
                        cands.append((val, h2, MM))
                        break
            if not cands:
                for delta in range(0, 360, 30):
                    rr = self.safe(px, py, hdg + delta, 1.0, False)
                    if rr is not None:
                        cands.append((0, hdg + delta, 1.0))
                        break
            if not cands:
                return {"action": "wait"}
            cands.sort()
            _, hdg, M = cands[0]
        H = (hdg - bdeg) % 360.0
        M = round(min(self.maxm, max(0.1, M)), 3)
        return {"action": "drive", "heading_deg": round(H, 3), "metres": M}

    # ---------------- control ----------------
    def send(self, cmd, t):
        try:
            acks = self.tools.uplink([cmd])
        except Exception:
            return None
        et = None
        for a in acks:
            et = int(a["execute_tick"])
            self.acks[et] = {"cmd": a.get("command", cmd) or cmd, "sent": int(a.get("sent_tick", t)),
                             "cleared": False}
            self.last_exec = max(self.last_exec, et)
        return et

    def decide(self, t):
        e0 = max(self.last_exec + 1, t + self.delay + 1)
        if e0 != t + self.delay + 1:
            return
        if e0 > self.T:
            return
        px, py, pb = self.predict_to(e0)
        self.cleanup_route()
        if self.need_replan or e0 - self.last_plan >= 15:
            budget = 3.0 if self.last_plan < 0 else 0.35
            self.replan(e0, px, py, pb, budget)
        fb = self.fields["__base__"]
        tb, _ = self.lookup(fb, px, py)
        goal = None
        if self.route:
            if tb == INF or e0 + tb * 1.12 + 3 < self.T:
                goal = self.route[0]
            else:
                self.route = []
        if goal is not None:
            gx, gy = self.targets[goal]["x"], self.targets[goal]["y"]
            fld = self.fields[goal]
        else:
            gx, gy = self.base
            fld = fb
        d = math.hypot(gx - px, gy - py)
        if goal is not None and d <= 1.0:
            et = self.send({"action": "sample"}, t)
            if et is not None:
                self.attempts[goal] = et
                self.route.pop(0)
                self.need_replan = True
            return
        if goal is None and d <= 1.2:
            return
        if pb < 3.0:
            self.send({"action": "wait"}, t)
            return
        cmd = self.nav(px, py, gx, gy, fld)
        if cmd is None:
            return
        self.send(cmd, t)

    def run(self):
        t = 0
        while True:
            try:
                self.process()
            except Exception:
                pass
            try:
                if self.discover_flag or t - self.last_map_check >= 10:
                    self.discover_flag = False
                    self.last_map_check = t
                    self.refresh_targets()
            except Exception:
                pass
            if self.alive:
                try:
                    self.decide(t)
                except Exception:
                    pass
            try:
                res = self.tools.advance(1)
            except Exception:
                break
            t = int(res.get("current_tick", t + 1))
            if res.get("episode_complete"):
                break
            if t > self.T + 5:
                break


def play(tools):
    ap = AP(tools)
    ap.run()
```