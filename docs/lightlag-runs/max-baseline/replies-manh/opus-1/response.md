The module plans a route over the map, schedules commands around the relay passes, tracks the rover's position from noisy telemetry, and replans as events arrive. It has not been run against the simulator. The command and estimation logic rests on a few guesses about the simulator, listed after the code.

**How it works**

1. **Ground model.** At start it builds a 16-direction graph over the 5 m cells.
   - Cells steeper than 0.32 are forbidden; target and lander cells are allowed up to 0.355.
   - Each edge is weighted by expected wheel metres (with slip) and energy (drive cost plus climbing).
   - Each edge also gets a penalty for the chance of an onboard slip stop. This uses the worst-case slip base and the hidden sand gain range, plus the 10% soft-sand chance on flat crust cells. Cells next to steep ground get a small extra penalty.
   - A reverse Dijkstra is run from the lander and from every target, including targets discovered later. From any cell this gives the time, energy and next step towards each goal.

2. **Route choice.** A target-selection search picks which targets to visit and in what order.
   - It models time from wheel metres and the learned wheel scale.
   - It counts value only if the sample tick meets the deadline, otherwise the late value.
   - It tracks the battery with the solar curve, inserting waits when needed and keeping a reserve.
   - It must return to the lander with a margin before tick 420.
   - It builds a greedy route, then improves it with insertion, replacement, relocation and 2-opt moves.
   - It replans every relay pass and after discoveries, failed samples or safety stops.

3. **Command timing.** On each open tick it fills the command queue exactly up to the point the next uplink can take over. That is one command per tick early in a pass and five on the last open tick. This keeps the rover busy without committing further ahead than needed.

4. **Position tracking.** A Kalman filter estimates x, y and the heading bias.
   - It uses visual odometry and the terrain's noise level, discounts wild position fixes, and models lost packets.
   - It works out cancelled commands from safety-stop events and from commands that never reported executing.
   - The wheel scale is learned from visual odometry against simulated drives; solar efficiency comes from the exact `charge` field.

5. **Commands.** Drives follow the path towards a look-ahead point that has been checked for safe slope. Each drive is aimed through the published ground model so heading bias and cross-slope sliding are cancelled. Before every command it checks that the rover can still reach the lander in time and that the battery stays above a reserve.

**Assumptions about the simulator**

- **Safety stops:** a stop at tick s is assumed to clear the commands transmitted at or before s that were due to run after s.
- **Stopped drives:** a drive that stops part-way is assumed to still report a `command_executed` event.
- **Event names:** event types are assumed to be `"command_executed"`, `"safety_stop"` and `"target_discovered"`.
- **Sampled list:** `sampled_targets` is assumed to be cumulative and to contain the target ids.

```python
import math
import heapq
import time

TC = {"b": "bedrock", "r": "regolith", "s": "sand", "k": "rocks"}
INF = float("inf")
DIRS = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1),
        (2, 1), (1, 2), (-1, 2), (-2, 1), (-2, -1), (-1, -2), (1, -2), (2, -1)]


def wrap180(a):
    return (a + 180.0) % 360.0 - 180.0


class Surf:
    def __init__(self, cell, elevation_cm, terrain):
        self.cell = float(cell)
        self.h = [[v / 100.0 for v in row] for row in elevation_cm]
        self.ny, self.nx = len(self.h), len(self.h[0])
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
        name = TC[code]
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
        energy += segment * cost[name] + climb * (there - here if there > here else 0.0)
        wheel += segment
        ground += math.hypot(nx_ - x, ny_ - y)
        remaining -= segment
        x, y, here, gx, gy, code = nx_, ny_, there, ngx, ngy, ncode
    return {"x": x, "y": y, "wheel": wheel, "ground": ground, "energy": energy, "stop": stop}


class Pilot:
    def __init__(self, tools):
        self.t_start = time.time()
        self.tools = tools
        R = tools.rules()
        self.R = R
        M = tools.map()
        self.C = float(M["cell_m"])
        self.surf = Surf(self.C, M["elevation_cm"], M["terrain"])
        ph = R["physics"]
        self.ph = ph
        self.delay = int(R.get("delay_ticks", 3))
        self.T = int(R["max_ticks"])
        self.cap = float(R["battery_capacity"])
        self.idle = float(R["idle_cost"])
        self.scost = float(R["sample_cost"])
        self.peak = float(R["solar_peak"])
        self.smargin = float(R["sun_margin_ticks"])
        er = R.get("solar_efficiency_range", [0.8, 1.0])
        self.eff_lo, self.eff_hi = float(er[0]), float(er[1])
        self.eff = self.eff_lo
        rp = R.get("relay_passes") or {}
        self.period = int(rp.get("period_ticks", 1)) or 1
        self.opent = int(rp.get("open_ticks", self.period))
        sb = ph["slip_base_ranges"]
        self.slo = {k: float(v[0]) for k, v in sb.items()}
        self.shi = {k: float(v[1]) for k, v in sb.items()}
        self.smid = {k: 0.5 * (float(v[0]) + float(v[1])) for k, v in sb.items()}
        self.gain = {k: float(v) for k, v in ph["slip_grade_gain"].items()}
        self.ghi = dict(self.gain)
        self.glo = dict(self.gain)
        sg = R.get("sand_grade_gain")
        if isinstance(sg, dict) and "range" in sg:
            self.glo["sand"] = float(sg["range"][0])
            self.ghi["sand"] = float(sg["range"][1])
        osc = R.get("onboard_slip_check")
        self.slip_limit = float(osc.get("limit", 0.95)) if isinstance(osc, dict) else 0.95
        self.snoise = float(ph.get("slip_noise", 0.02))
        self.side = ph["side_slip_gain"]
        self.dcost = ph["drive_cost_per_wheel_m"]
        self.climb = float(ph["climb_cost_per_m"])
        self.turn_k = float(R.get("turn_cost_per_degree", 0.0) or 0.0)
        sens = R.get("sensing", {}) or {}
        self.pos_sig = float(sens.get("position_noise_m", 1.0))
        vo0 = float(sens.get("visual_odometry_noise", 0.05))
        self.vo_sig = {k: vo0 for k in TC.values()}
        vbt = sens.get("visual_odometry_noise_by_terrain") or {}
        for k, v in vbt.items():
            self.vo_sig[k] = float(v)
        pfo = R.get("position_fix_outliers")
        self.out_sig = float(pfo.get("sigma_m", 0.0)) if isinstance(pfo, dict) else 0.0
        hb = float(sens.get("heading_bias_deg", 5.0))
        self.beta_var0 = math.radians(hb) ** 2 / 3.0
        self.walk_var = math.radians(float(sens.get("heading_bias_walk_deg", 0.2))) ** 2
        self.hn = math.radians(float(sens.get("heading_noise_deg", 1.5)))
        self.base = (float(M["base"][0]), float(M["base"][1]))
        self.crust = M.get("crust_regions", []) or []
        self.scale = 1.0
        self.scale_obs = {}
        self.NX = self.surf.nx - 1
        self.NY = self.surf.ny - 1
        self.N = self.NX * self.NY
        self.targets = {}
        for t in M.get("targets", []) or []:
            self.targets[t["id"]] = t
        self.build_grid()
        self.rev = {}
        self.rev["BASE"] = self.rev_dij(self.cell_of(*self.base))
        for k in list(self.targets):
            self.rev[k] = self.rev_dij(self.cell_of(self.targets[k]["x"], self.targets[k]["y"]))
        # bookkeeping
        self.pk = {}
        self.pk_exec = {}
        self.exec_known = set()
        self.not_exec = set()
        self.stop_ticks = set()
        self.cmds = {}
        self.sched = {}
        self.last_res = 0
        self.cancelled = set()
        self.dirty = False
        self.disc_flag = False
        self.new_stop = False
        self.need_replan = True
        self.route = []
        self.pending = {}
        self.sampled = set()
        P0 = [[1e-4, 0.0, 0.0], [0.0, 1e-4, 0.0], [0.0, 0.0, self.beta_var0]]
        self.est = {0: (self.base[0], self.base[1], 0.0, P0)}
        self.freeze = 0
        self.L = 0

    # ---------------------------------------------------------------- grid
    def cell_of(self, x, y):
        i = min(self.NX - 1, max(0, int(x / self.C)))
        j = min(self.NY - 1, max(0, int(y / self.C)))
        return j * self.NX + i

    def center(self, u):
        return ((u % self.NX + 0.5) * self.C, (u // self.NX + 0.5) * self.C)

    def txy(self, k):
        t = self.targets[k]
        return float(t["x"]), float(t["y"])

    def build_grid(self):
        s = self.surf
        NX, NY, C, N = self.NX, self.NY, self.C, self.N
        cms = [0.0] * N
        for j in range(NY):
            for i in range(NX):
                cms[j * NX + i] = s.cell_max_slope(i, j)
        forb = [c > 0.32 for c in cms]
        for (px, py) in [self.base] + [(t["x"], t["y"]) for t in self.targets.values()]:
            u = self.cell_of(px, py)
            if cms[u] < 0.355:
                forb[u] = False
        danger = [False] * N
        for j in range(NY):
            for i in range(NX):
                m = 0.0
                for dj in (-1, 0, 1):
                    for di in (-1, 0, 1):
                        a, b = i + di, j + dj
                        if 0 <= a < NX and 0 <= b < NY:
                            m = max(m, cms[b * NX + a])
                danger[j * NX + i] = m > 0.34
        soft = [False] * N
        for reg in self.crust:
            try:
                x1, y1, x2, y2 = float(reg["x1"]), float(reg["y1"]), float(reg["x2"]), float(reg["y2"])
            except Exception:
                continue
            for j in range(NY):
                cy = (j + 0.5) * C
                if not (y1 <= cy <= y2):
                    continue
                for i in range(NX):
                    cx = (i + 0.5) * C
                    if x1 <= cx <= x2 and cms[j * NX + i] <= 0.1 + 1e-9:
                        soft[j * NX + i] = True
        self.cms, self.forb, self.danger, self.soft = cms, forb, danger, soft
        inc = [[] for _ in range(N)]
        sample = s.sample
        smid, gain, shi, slo, ghi, glo = self.smid, self.gain, self.shi, self.slo, self.ghi, self.glo
        dcost, climb, lim, nz = self.dcost, self.climb, self.slip_limit, self.snoise
        for j in range(NY):
            for i in range(NX):
                u = j * NX + i
                x0 = (i + 0.5) * C
                y0 = (j + 0.5) * C
                h0 = sample(x0, y0)[0]
                for (di, dj) in DIRS:
                    i2, j2 = i + di, j + dj
                    if not (0 <= i2 < NX and 0 <= j2 < NY):
                        continue
                    v = j2 * NX + i2
                    if forb[v]:
                        continue
                    L = C * math.hypot(di, dj)
                    ux = di * C / L
                    uy = dj * C / L
                    n = int(math.ceil(L / 1.7))
                    seg = L / n
                    ok = True
                    W = E = pen = pmax = 0.0
                    hp = h0
                    for k in range(n):
                        f = (k + 0.5) / n
                        px = x0 + ux * L * f
                        py = y0 + uy * L * f
                        h, gx, gy, code = sample(px, py)
                        ci = min(NY - 1, int(py / C)) * NX + min(NX - 1, int(px / C))
                        if ci != u:
                            if forb[ci] or gx * gx + gy * gy > 0.1024:
                                ok = False
                                break
                        name = TC[code]
                        g = gx * ux + gy * uy
                        gp = g if g > 0 else 0.0
                        sm = smid[name] + gain[name] * gp
                        if sm > 0.42 and ci != u:
                            ok = False
                            break
                        if sm > 0.9:
                            sm = 0.9
                        sw = shi[name] + nz + ghi[name] * gp
                        if sw > lim:
                            sbv = slo[name] - nz + glo[name] * gp
                            p = min(1.0, (sw - lim) / max(1e-6, sw - sbv))
                            if p > pmax:
                                pmax = p
                        if soft[ci] and gp > 0:
                            swS = shi["sand"] + nz + ghi["sand"] * gp
                            if swS > lim:
                                sbS = slo["sand"] - nz + glo["sand"] * gp
                                p2 = 0.1 * min(1.0, (swS - lim) / max(1e-6, swS - sbS))
                                pen += 8.0 * p2 * seg / 5.0
                        w = seg / (1.0 - sm)
                        W += w
                        E += w * dcost[name]
                        if h > hp:
                            E += climb * (h - hp)
                        hp = h
                        if danger[ci]:
                            pen += 0.05 * seg
                    if not ok:
                        continue
                    h1 = sample(x0 + ux * L, y0 + uy * L)[0]
                    if h1 > hp:
                        E += climb * (h1 - hp)
                    cost = W / 5.0 + 0.4 * E + 8.0 * pmax + pen
                    inc[v].append((u, cost, W, E))
        self.inc = inc

    def rev_dij(self, g):
        N = self.N
        dist = [INF] * N
        Wd = [0.0] * N
        Ed = [0.0] * N
        nxt = [-1] * N
        dist[g] = 0.0
        hq = [(0.0, g)]
        inc = self.inc
        pop, push = heapq.heappop, heapq.heappush
        while hq:
            dv, v = pop(hq)
            if dv > dist[v]:
                continue
            Wv, Ev = Wd[v], Ed[v]
            for (u, c, w, e) in inc[v]:
                nd = dv + c
                if nd < dist[u]:
                    dist[u] = nd
                    nxt[u] = v
                    Wd[u] = Wv + w
                    Ed[u] = Ev + e
                    push(hq, (nd, u))
        return (dist, Wd, Ed, nxt)

    # ---------------------------------------------------------------- helpers
    def solar(self, t):
        if t < 1:
            return 0.0
        v = math.sin(math.pi * (t + self.smargin) / (self.T + 2 * self.smargin))
        return self.peak * self.eff * max(0.0, v)

    def tks(self, W):
        return int(math.ceil(W * 1.06 / (5.0 * self.scale))) + 1

    def is_open(self, t):
        return (t % self.period) < self.opent

    def nearest_finite(self, key, u):
        d = self.rev[key][0]
        i0, j0 = u % self.NX, u // self.NX
        best = None
        for dj in range(-2, 3):
            for di in range(-2, 3):
                i, j = i0 + di, j0 + dj
                if 0 <= i < self.NX and 0 <= j < self.NY:
                    v = j * self.NX + i
                    if d[v] < INF:
                        sc = d[v] + 0.5 * math.hypot(di, dj)
                        if best is None or sc < best[0]:
                            best = (sc, v, math.hypot(di, dj))
        return best

    def w_from(self, key, x, y):
        if key not in self.rev:
            return None
        d, Wd, Ed, _ = self.rev[key]
        u = self.cell_of(x, y)
        if d[u] < INF:
            return Wd[u], Ed[u]
        b = self.nearest_finite(key, u)
        if b is None:
            return None
        v = b[1]
        return Wd[v] + 5.0 * b[2], Ed[v] + 2.0 * b[2]

    def sim(self, x, y, h, Mw, beta, scale=None):
        sc = self.scale if scale is None else scale
        return sim_drive(self.surf, self.ph, x, y, h + math.degrees(beta), Mw * sc, self.smid, 0.0)

    # ---------------------------------------------------------------- telemetry
    def store(self, p):
        try:
            s = int(p["tick"])
        except Exception:
            return
        if s in self.pk:
            return
        self.pk[s] = p
        self.dirty = True
        ids = []
        for e in p.get("events", []) or []:
            if not isinstance(e, dict):
                continue
            ty = e.get("type")
            if ty == "command_executed":
                ids.append(e.get("command_id"))
            elif ty == "safety_stop":
                self.stop_ticks.add(s)
                self.new_stop = True
            elif ty == "target_discovered":
                self.disc_flag = True
        self.pk_exec[s] = ids
        self.exec_known.update(ids)
        cid = self.sched.get(s)
        if cid is not None and cid not in ids:
            self.not_exec.add(cid)
        if s > 0:
            try:
                raw = self.peak * math.sin(math.pi * (s + self.smargin) / (self.T + 2 * self.smargin))
                ch = float(p.get("charge", 0.0) or 0.0)
                if raw > 0.1:
                    ratio = ch / raw
                    if ratio <= self.eff_hi + 0.02:
                        self.eff = max(self.eff, min(self.eff_hi, ratio))
            except Exception:
                pass

    def kf_pred(self, x, y, beta, P, h, wheel, vo, unc, terr):
        phi = math.radians(h) + beta
        c, s = math.cos(phi), math.sin(phi)
        _, gx, gy, code = self.surf.sample(x, y)
        name = TC[code]
        wm = wheel * self.scale
        if vo is not None and vo >= 0:
            d = vo
            vs = self.vo_sig.get(terr, self.vo_sig.get(name, 0.05)) if terr else self.vo_sig.get(name, 0.05)
            sa = d * vs + 0.05
        else:
            grade = gx * c + gy * s
            slip = min(0.95, self.smid[name] + self.gain[name] * max(0.0, grade))
            d = wm * (1.0 - slip)
            sa = 0.12 * d + 0.1
            if unc:
                d *= 0.5
                sa = max(sa, 0.5 * wm + 0.2)
        cross = -gx * s + gy * c
        side = wm * self.side[name] * cross
        dx = d * c + side * s
        dy = d * s - side * c
        x += dx
        y += dy
        sc_ = (self.hn + 0.005) * d + 0.05
        FP = [[P[0][k] - dy * P[2][k] for k in range(3)],
              [P[1][k] + dx * P[2][k] for k in range(3)],
              [P[2][k] for k in range(3)]]
        NP = [[FP[a][0] - dy * FP[a][2], FP[a][1] + dx * FP[a][2], FP[a][2]] for a in range(3)]
        sa2, sc2 = sa * sa, sc_ * sc_
        NP[0][0] += sa2 * c * c + sc2 * s * s
        NP[1][1] += sa2 * s * s + sc2 * c * c
        q = (sa2 - sc2) * c * s
        NP[0][1] += q
        NP[1][0] += q
        NP[2][2] += self.walk_var
        return x, y, NP

    def kf_upd(self, x, y, beta, P, z):
        r = self.pos_sig ** 2
        ix = float(z[0]) - x
        iy = float(z[1]) - y
        ia = ib = ic = idd = 0.0
        for attempt in (0, 1):
            a = P[0][0] + r
            b = P[0][1]
            c = P[1][0]
            d = P[1][1] + r
            det = a * d - b * c
            if abs(det) < 1e-12:
                return x, y, beta, P
            ia, ib, ic, idd = d / det, -b / det, -c / det, a / det
            m = ix * (ia * ix + ib * iy) + iy * (ic * ix + idd * iy)
            if attempt == 0 and m > 11.8 and self.out_sig > 0:
                r = self.pos_sig ** 2 + self.out_sig ** 2
                continue
            break
        K = [[P[k][0] * ia + P[k][1] * ic, P[k][0] * ib + P[k][1] * idd] for k in range(3)]
        x += K[0][0] * ix + K[0][1] * iy
        y += K[1][0] * ix + K[1][1] * iy
        beta += K[2][0] * ix + K[2][1] * iy
        beta = max(-0.15, min(0.15, beta))
        NP = [[P[k][l] - (K[k][0] * P[0][l] + K[k][1] * P[1][l]) for l in range(3)] for k in range(3)]
        for a in range(3):
            for b in range(a + 1, 3):
                v = 0.5 * (NP[a][b] + NP[b][a])
                NP[a][b] = NP[b][a] = v
            NP[a][a] = max(NP[a][a], 1e-6)
        return x, y, beta, NP

    def run_est(self):
        if not self.pk:
            return
        L = max(self.pk)
        canc = set()
        for s in self.stop_ticks:
            for cid, c in self.cmds.items():
                if c["exec"] > s and c["transmit"] <= s:
                    canc.add(cid)
        canc |= self.not_exec
        canc -= self.exec_known
        self.cancelled = canc
        ne = [self.cmds[c] for c in self.not_exec if c in self.cmds]
        s0 = self.freeze if self.freeze in self.est else 0
        x, y, beta, P = self.est[s0]
        P = [row[:] for row in P]
        for s in range(s0 + 1, L + 1):
            pkt = self.pk.get(s)
            mot = None
            if pkt is not None:
                c = None
                for cid in self.pk_exec.get(s, []):
                    cc = self.cmds.get(cid)
                    if cc and cc["cmd"]["action"] == "drive":
                        c = cc
                wo = float(pkt.get("wheel_odometry") or 0.0)
                if c is None and wo > 0:
                    cid = self.sched.get(s)
                    cc = self.cmds.get(cid) if cid is not None else None
                    if cc and cc["cmd"]["action"] == "drive":
                        c = cc
                if c is not None and wo > 0:
                    vo = pkt.get("visual_odometry")
                    vo = float(vo) if vo is not None else None
                    terr = pkt.get("terrain")
                    mot = (c["cmd"]["heading_deg"], wo, vo, False, terr)
                    full = abs(wo - c["cmd"]["metres"]) < 1e-3 and s not in self.stop_ticks
                    if full and vo is not None and s not in self.scale_obs and wo >= 1.0:
                        try:
                            r = self.sim(x, y, c["cmd"]["heading_deg"], wo, beta, scale=1.0)
                            if r["stop"] is None and r["ground"] > 0.8:
                                ratio = max(0.5, min(1.5, vo / r["ground"]))
                                vs = self.vo_sig.get(terr, 0.05) + 0.01
                                self.scale_obs[s] = (ratio, 1.0 / (vs * vs))
                                num = 75.0
                                den = 75.0
                                for (rr, ww) in self.scale_obs.values():
                                    num += rr * ww
                                    den += ww
                                self.scale = max(0.75, min(1.25, num / den))
                        except Exception:
                            pass
            else:
                cid = self.sched.get(s)
                if cid is not None and cid not in canc:
                    cc = self.cmds[cid]
                    if cc["cmd"]["action"] == "drive":
                        unc = any(cn["transmit"] < s < cn["exec"] for cn in ne)
                        mot = (cc["cmd"]["heading_deg"], cc["cmd"]["metres"], None, unc, None)
            if mot:
                x, y, P = self.kf_pred(x, y, beta, P, *mot)
            if pkt is not None and s > 0 and pkt.get("position") is not None:
                x, y, beta, P = self.kf_upd(x, y, beta, P, pkt["position"])
            self.est[s] = (x, y, beta, [r[:] for r in P])
        self.L = L
        if L - 30 > self.freeze:
            self.freeze = L - 30

    def check_map(self):
        try:
            M = self.tools.map()
        except Exception:
            return
        for t in M.get("targets", []) or []:
            if t["id"] not in self.targets:
                self.targets[t["id"]] = t
                try:
                    self.rev[t["id"]] = self.rev_dij(self.cell_of(t["x"], t["y"]))
                except Exception:
                    pass
                self.need_replan = True

    def update(self):
        self.dirty = False
        if self.disc_flag:
            self.disc_flag = False
            self.check_map()
        self.run_est()
        pkt = self.pk.get(self.L)
        if pkt is not None:
            self.sampled = set(pkt.get("sampled_targets", []) or [])
        for k, et in list(self.pending.items()):
            if k in self.sampled:
                del self.pending[k]
            elif et <= self.L:
                del self.pending[k]
                self.need_replan = True
        if self.new_stop:
            self.new_stop = False
            self.need_replan = True

    def predict(self, upto):
        L = self.L
        x, y, beta, P = self.est[L]
        pk = self.pk.get(L, {})
        b = float(pk.get("battery", self.cap))
        hd = float(pk.get("heading_deg", 0.0) or 0.0)
        for s in range(L + 1, upto + 1):
            b = min(self.cap, b + self.solar(s)) - self.idle
            cid = self.sched.get(s)
            if cid is None or cid in self.cancelled:
                continue
            c = self.cmds[cid]["cmd"]
            if c["action"] == "drive":
                r = self.sim(x, y, c["heading_deg"], c["metres"], beta)
                name = TC[self.surf.sample(x, y)[3]]
                b -= r["energy"] + self.turn_k * abs(wrap180(c["heading_deg"] - hd)) * self.dcost[name]
                x, y = r["x"], r["y"]
                hd = c["heading_deg"]
            elif c["action"] == "sample":
                b -= self.scost
        return {"x": x, "y": y, "b": b, "hd": hd, "beta": beta, "t": upto}

    # ---------------------------------------------------------------- planning
    def replan(self, st):
        t0 = st["t"]
        b0 = st["b"]
        x, y = st["x"], st["y"]
        elapsed = time.time() - self.t_start
        tl = 1.0 if elapsed < 900 else 0.15
        deadline = time.time() + tl
        cands = []
        for k, tg in self.targets.items():
            if k in self.sampled or k in self.pending or k not in self.rev:
                continue
            u = self.cell_of(tg["x"], tg["y"])
            if self.rev["BASE"][0][u] == INF:
                continue
            if self.w_from(k, x, y) is None:
                continue
            cands.append(k)
        n = len(cands)
        keys = ["START"] + cands + ["BASE"]
        TK = [[0] * (n + 2) for _ in range(n + 2)]
        EN = [[0.0] * (n + 2) for _ in range(n + 2)]
        for a in range(n + 1):
            for b in range(1, n + 2):
                kb = keys[b]
                if a == 0:
                    wf = self.w_from(kb, x, y)
                else:
                    if a == b:
                        continue
                    ax, ay = self.txy(keys[a])
                    wf = self.w_from(kb, ax, ay)
                if wf is None:
                    TK[a][b] = 10 ** 6
                    EN[a][b] = 1e6
                else:
                    TK[a][b] = self.tks(wf[0])
                    EN[a][b] = wf[1] + 0.4
        V = [0.0] * (n + 2)
        LV = [0.0] * (n + 2)
        DL = [10 ** 9] * (n + 2)
        for idx, k in enumerate(cands, 1):
            tg = self.targets[k]
            V[idx] = float(tg.get("value", 1.0))
            lv = tg.get("late_value")
            LV[idx] = float(lv) if lv is not None else V[idx]
            dl = tg.get("deadline_tick")
            DL[idx] = int(dl) if dl is not None else 10 ** 9
        S = [0.0] * (self.T + 800)
        for i in range(1, len(S)):
            S[i] = S[i - 1] + self.solar(i)
        cap, idle, scost = self.cap, self.idle, self.scost
        res = 8.0
        Tlim = self.T - 8
        SL = len(S) - 1

        def leg(t, b, nn, E):
            if nn <= 0:
                return t, b
            if t + nn > SL:
                return None
            bn = b + S[t + nn] - S[t] - idle * nn - E
            if bn >= res:
                return t + nn, min(cap, bn)
            w = 0
            while w < 200:
                w += 1
                if t + w + nn > SL:
                    return None
                bn = b + S[t + w + nn] - S[t] - idle * (w + nn) - E
                if bn >= res:
                    return t + w + nn, min(cap, bn)
            return None

        def ev(seq):
            t = t0
            b = b0
            val = 0.0
            prev = 0
            for k in seq:
                r = leg(t, b, TK[prev][k], EN[prev][k])
                if r is None:
                    return None
                t, b = r
                t += 1
                b = min(cap, b + S[min(t, SL)] - S[min(t - 1, SL)]) - idle - scost
                if b < res or t > Tlim:
                    return None
                val += V[k] if t <= DL[k] else LV[k]
                prev = k
            r = leg(t, b, TK[prev][n + 1], EN[prev][n + 1])
            if r is None or r[0] > Tlim:
                return None
            return (val, r[0])

        def better(a, b):
            if a is None:
                return False
            if b is None:
                return True
            return a[0] > b[0] + 1e-9 or (a[0] > b[0] - 1e-9 and a[1] < b[1])

        def added(seq, p, u):
            a = seq[p - 1] if p > 0 else 0
            c = seq[p] if p < len(seq) else n + 1
            return TK[a][u] + TK[u][c] - TK[a][c]

        def bestpos(seq, u, m=2):
            ps = sorted(range(len(seq) + 1), key=lambda p: added(seq, p, u))
            return ps[:m]

        def construct():
            seq = []
            cur = ev(seq)
            if cur is None:
                return [], None
            while time.time() < deadline:
                bestS = None
                bestr = None
                bestsc = 0.0
                inr = set(seq)
                for u in range(1, n + 1):
                    if u in inr:
                        continue
                    for p in bestpos(seq, u, 2):
                        s2 = seq[:p] + [u] + seq[p:]
                        r = ev(s2)
                        if r is None:
                            continue
                        g = r[0] - cur[0]
                        if g <= 1e-9:
                            continue
                        sc = g / (max(0, r[1] - cur[1]) + 2.0)
                        if sc > bestsc:
                            bestsc, bestS, bestr = sc, s2, r
                if bestS is None:
                    break
                seq, cur = bestS, bestr
            return seq, cur

        def improve(seq, cur):
            while time.time() < deadline:
                changed = False
                inr = set(seq)
                un = [u for u in range(1, n + 1) if u not in inr]
                bs, br = None, cur
                for u in un:
                    for p in bestpos(seq, u, 2):
                        s2 = seq[:p] + [u] + seq[p:]
                        r = ev(s2)
                        if r is not None and better(r, br):
                            bs, br = s2, r
                if bs is not None:
                    seq, cur = bs, br
                    continue
                for i in range(len(seq)):
                    rest = seq[:i] + seq[i + 1:]
                    for u in un:
                        for p in bestpos(rest, u, 2):
                            s2 = rest[:p] + [u] + rest[p:]
                            r = ev(s2)
                            if r is not None and better(r, cur):
                                seq, cur, changed = s2, r, True
                                break
                        if changed:
                            break
                    if changed or time.time() > deadline:
                        break
                if changed:
                    continue
                for i in range(len(seq)):
                    rest = seq[:i] + seq[i + 1:]
                    for p in range(len(rest) + 1):
                        if p == i:
                            continue
                        s2 = rest[:p] + [seq[i]] + rest[p:]
                        r = ev(s2)
                        if r is not None and better(r, cur):
                            seq, cur, changed = s2, r, True
                            break
                    if changed:
                        break
                if changed:
                    continue
                for i in range(len(seq) - 1):
                    for j in range(i + 2, len(seq) + 1):
                        s2 = seq[:i] + seq[i:j][::-1] + seq[j:]
                        r = ev(s2)
                        if r is not None and better(r, cur):
                            seq, cur, changed = s2, r, True
                            break
                    if changed:
                        break
                if not changed:
                    break
            return seq, cur

        idx_of = {k: i for i, k in enumerate(cands, 1)}
        old = [idx_of[k] for k in self.route if k in idx_of]
        oc = ev(old)
        while old and oc is None:
            old = old[:-1]
            oc = ev(old)
        best_seq, best_cur = [], None
        if oc is not None:
            old, oc = improve(old, oc)
            best_seq, best_cur = old, oc
        gs, gc = construct()
        if gc is not None:
            gs, gc = improve(gs, gc)
            if better(gc, best_cur):
                best_seq, best_cur = gs, gc
        self.route = [cands[i - 1] for i in best_seq]

    # ---------------------------------------------------------------- commands
    def chain(self, key, x, y, gx, gy):
        d, Wd, Ed, nxt = self.rev[key]
        u = self.cell_of(x, y)
        pts = []
        if d[u] == INF:
            b = self.nearest_finite(key, u)
            if b is None:
                return [(gx, gy)]
            u = b[1]
            pts.append(self.center(u))
        v = u
        for _ in range(12):
            if d[v] <= 0 or nxt[v] < 0:
                break
            v = nxt[v]
            pts.append(self.center(v))
        if d[v] <= 0:
            if pts:
                pts[-1] = (gx, gy)
            else:
                pts = [(gx, gy)]
        if not pts:
            pts = [(gx, gy)]
        return pts

    def seg_safe(self, x, y, p):
        dx = p[0] - x
        dy = p[1] - y
        L = math.hypot(dx, dy)
        if L < 0.5:
            return True
        ux, uy = dx / L, dy / L
        nx_, ny_ = -uy, ux
        u0 = self.cell_of(x, y)
        n = max(1, int(L / 1.0))
        W, H = self.surf.width, self.surf.height
        for k in range(1, n + 1):
            f = k / n
            px = x + dx * f
            py = y + dy * f
            if not (0.5 <= px <= W - 0.5 and 0.5 <= py <= H - 0.5):
                return False
            ci = self.cell_of(px, py)
            h, gx, gy, code = self.surf.sample(px, py)
            if ci != u0:
                if self.forb[ci]:
                    return False
                if gx * gx + gy * gy > 0.31 ** 2:
                    return False
                name = TC[code]
                g = gx * ux + gy * uy
                if g > 0 and self.smid[name] + self.gain[name] * g > 0.40:
                    return False
            for off in (-1.5, 1.5):
                qx = px + off * nx_
                qy = py + off * ny_
                if 0 <= qx <= W and 0 <= qy <= H:
                    _, ax, ay, _ = self.surf.sample(qx, qy)
                    if ax * ax + ay * ay > 0.355 ** 2:
                        return False
        return True

    def carrot(self, x, y, pts):
        best = pts[0]
        acc = 0.0
        px, py = x, y
        for idx, p in enumerate(pts):
            acc += math.hypot(p[0] - px, p[1] - py)
            px, py = p
            if idx > 0 and acc > 15.0:
                break
            if idx > 0 and self.seg_safe(x, y, p):
                best = p
        return best

    def make_drive(self, st, p):
        x, y, beta, hd = st["x"], st["y"], st["beta"], st["hd"]
        Dx, Dy = p[0] - x, p[1] - y
        Ld = math.hypot(Dx, Dy)
        if Ld < 0.05:
            return None
        ux, uy = Dx / Ld, Dy / Ld
        phi = math.atan2(uy, ux)
        _, gxs, gys, code = self.surf.sample(x, y)
        name = TC[code]
        grade = gxs * ux + gys * uy
        slip = min(0.9, self.smid[name] + self.gain[name] * max(0.0, grade))
        g = Ld
        Mw = max(0.05, min(5.0, g / (self.scale * (1.0 - slip))))
        h = math.degrees(phi) - math.degrees(beta)
        for _ in range(3):
            r = self.sim(x, y, h, Mw, beta)
            ex, ey = r["x"] - x, r["y"] - y
            ga = math.hypot(ex, ey)
            if ga < 1e-3:
                break
            err = wrap180(math.degrees(phi - math.atan2(ey, ex)))
            err = max(-20.0, min(20.0, err))
            h += err
            prog = ex * ux + ey * uy
            if prog > 0.05:
                Mw = min(5.0, max(0.05, Mw * g / prog))
        r = self.sim(x, y, h, Mw, beta)
        if r["stop"] is not None:
            M2 = Mw
            okr = None
            for _ in range(3):
                M2 *= 0.5
                r2 = self.sim(x, y, h, M2, beta)
                if r2["stop"] is None:
                    okr = (M2, r2)
                    break
            if okr is not None:
                Mw, r = okr
        h = h % 360.0
        Mw = round(max(0.05, min(5.0, Mw)), 3)
        turn = self.turn_k * abs(wrap180(h - hd)) * self.dcost[name]
        cmd = {"action": "drive", "heading_deg": round(h, 3), "metres": Mw}
        return cmd, r, r["energy"] + turn

    def gen(self, st):
        self._samp_key = None
        t = st["t"]
        x, y = st["x"], st["y"]
        bb = min(self.cap, st["b"] + self.solar(t)) - self.idle
        while self.route:
            k = self.route[0]
            if k in self.sampled or k in self.pending or k not in self.targets or k not in self.rev:
                self.route.pop(0)
                continue
            wa = self.w_from(k, x, y)
            kx, ky = self.txy(k)
            wb = self.w_from("BASE", kx, ky)
            if wa is None or wb is None:
                self.route.pop(0)
                continue
            if t + self.tks(wa[0]) + 1 + self.tks(wb[0]) > self.T - 3:
                self.route.pop(0)
                continue
            break
        if self.route:
            key = self.route[0]
            gx, gy = self.txy(key)
        else:
            key = "BASE"
            gx, gy = self.base
        d = math.hypot(gx - x, gy - y)
        if key != "BASE" and d <= 1.0:
            if bb - self.scost < 3.0:
                st["b"] = bb
                return {"action": "wait"}
            st["b"] = bb - self.scost
            self.route.pop(0)
            self.pending[key] = t
            self._samp_key = key
            return {"action": "sample"}
        if key == "BASE" and d <= 1.0:
            st["b"] = bb
            return None
        pts = self.chain(key, x, y, gx, gy)
        p = self.carrot(x, y, pts)
        res = self.make_drive(st, p)
        if res is None:
            st["b"] = bb
            return {"action": "wait"}
        cmd, r, E = res
        if bb - E < 4.0:
            st["b"] = bb
            return {"action": "wait"}
        st["x"], st["y"] = r["x"], r["y"]
        st["b"] = bb - E
        st["hd"] = cmd["heading_deg"]
        return cmd

    def send(self, t):
        n = t + 1
        while not self.is_open(n):
            n += 1
        H = n + self.delay
        first = max(self.last_res, t + self.delay) + 1
        if first > self.T:
            return
        cnt = min(5, H - first + 1, self.T - first + 1)
        if cnt <= 0:
            return
        st = self.predict(first - 1)
        if self.need_replan:
            try:
                self.replan(st)
            except Exception:
                pass
            self.need_replan = False
        route_bak = list(self.route)
        pend_bak = dict(self.pending)
        cmds = []
        skeys = {}
        try:
            for k in range(cnt):
                st["t"] = first + k
                c = self.gen(st)
                if self._samp_key is not None:
                    skeys[k] = self._samp_key
                cmds.append(c if c else {"action": "wait"})
        except Exception:
            self.route = route_bak
            self.pending = pend_bak
            return
        while cmds and cmds[-1]["action"] == "wait":
            cmds.pop()
        if not cmds:
            return
        try:
            acks = self.tools.uplink(cmds)
        except Exception:
            self.route = route_bak
            self.pending = pend_bak
            return
        for k, a in enumerate(acks or []):
            try:
                cid = a.get("command_id")
                ex = int(a.get("execute_tick"))
                tr = int(a.get("transmit_tick", t))
                cmd = a.get("command", cmds[k]) or cmds[k]
                self.cmds[cid] = {"cmd": cmds[k] if k < len(cmds) else cmd, "exec": ex, "transmit": tr}
                self.sched[ex] = cid
                self.last_res = max(self.last_res, ex)
                if k in skeys:
                    self.pending[skeys[k]] = ex
            except Exception:
                pass

    def step(self, t):
        if t % self.period == 0:
            self.need_replan = True
            if t % (self.period * 4) == 0:
                self.check_map()
        if self.dirty:
            self.update()
        self.send(t)

    def run(self):
        try:
            for p in self.tools.telemetry_log() or []:
                self.store(p)
        except Exception:
            pass
        if 0 in self.pk and self.pk[0].get("position"):
            pos = self.pk[0]["position"]
            P0 = self.est[0][3]
            self.est[0] = (float(pos[0]), float(pos[1]), 0.0, P0)
        t = 0
        complete = False
        while not complete:
            if self.is_open(t) and t <= self.T:
                try:
                    self.step(t)
                except Exception:
                    pass
            try:
                res = self.tools.advance(1)
            except Exception:
                break
            t = int(res.get("current_tick", t + 1))
            complete = bool(res.get("episode_complete"))
            for p in res.get("packets", []) or []:
                self.store(p)
            if t > self.T + 40:
                break


def play(tools):
    try:
        pilot = Pilot(tools)
    except Exception:
        pilot = None
    if pilot is None:
        while True:
            try:
                r = tools.advance(5)
            except Exception:
                return
            if r.get("episode_complete"):
                return
    pilot.run()
```