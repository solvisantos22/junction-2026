import math
import heapq
import random
import time
from typing import Any, Dict, List, Optional, Tuple
import sys
sys.path.insert(0, "/app")
from lightlag_surface import Surface, PHYSICS, TERRAIN_CODES, drive

SOLAR_PEAK = 2.8
SUN_MARGIN = 56
MAX_TICKS = 420
IDLE_COST = 0.15
SAMPLE_COST = 2.0
TARGET_RADIUS = 2.5
BASE_RADIUS = 4.0

SOLAR_SIN = [
    SOLAR_PEAK * math.sin(math.pi * (tk + SUN_MARGIN) / (MAX_TICKS + 2 * SUN_MARGIN))
    for tk in range(MAX_TICKS + 20)
]
SOLAR_PRE = [0.0] * (MAX_TICKS + 21)
for _k in range(1, MAX_TICKS + 20):
    SOLAR_PRE[_k] = SOLAR_PRE[_k - 1] + SOLAR_SIN[_k]

SLIP_MID = {k: 0.5 * (v[0] + v[1]) for k, v in PHYSICS["slip_base_ranges"].items()}


class NavGraph:
    def __init__(self, surf: Surface, margin: float = 0.03, clearance_m: float = 2.0):
        self.surf = surf
        self.nx = surf.nx
        self.ny = surf.ny
        self.cell = surf.cell
        self.max_tilt = PHYSICS["max_tilt"] - margin

        nx, ny = self.nx, self.ny
        self.safe_pt = [[False] * self.nx for _ in range(self.ny)]
        for j in range(self.ny):
            y0 = j * self.cell
            for i in range(self.nx):
                x0 = i * self.cell
                _, gx, gy, _ = surf.sample(x0, y0)
                if math.hypot(gx, gy) > self.max_tilt:
                    continue
                ok = True
                if clearance_m > 0:
                    for ak in range(8):
                        ang = 0.7853981633974483 * ak
                        ca, sa = math.cos(ang), math.sin(ang)
                        for r in (clearance_m * 0.5, clearance_m):
                            px, py = x0 + r * ca, y0 + r * sa
                            if not surf.inside(px, py) or surf.slope(px, py) > PHYSICS["max_tilt"]:
                                ok = False
                                break
                        if not ok:
                            break
                self.safe_pt[j][i] = ok

        dirs = [(dx, dy) for dx in range(-2, 3) for dy in range(-2, 3)
                if (dx != 0 or dy != 0) and math.gcd(abs(dx), abs(dy)) == 1]

        self.adj: List[List[List[Tuple[int, int, float, float]]]] = [
            [[] for _ in range(self.nx)] for _ in range(self.ny)
        ]
        for j in range(self.ny):
            y0 = j * self.cell
            for i in range(self.nx):
                if not self.safe_pt[j][i]:
                    continue
                x0 = i * self.cell
                h0 = surf.h[j][i]
                for dx, dy in dirs:
                    ni, nj = i + dx, j + dy
                    if not (0 <= ni < nx and 0 <= nj < ny) or not self.safe_pt[nj][ni]:
                        continue
                    x1, y1 = ni * self.cell, nj * self.cell
                    L = math.hypot(x1 - x0, y1 - y0)
                    ux, uy = (x1 - x0) / L, (y1 - y0) / L
                    steps = int(math.ceil(L / 1.0))
                    ok = True
                    max_s = 0.0
                    for s in range(1, steps):
                        t = s / steps
                        xm, ym = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
                        _, gx, gy, _ = surf.sample(xm, ym)
                        slp = math.hypot(gx, gy)
                        if slp > self.max_tilt:
                            ok = False
                            break
                        # Check 1.5m lateral clearance on both sides
                        for side_s in (-1.5, 1.5):
                            lx, ly = xm - uy * side_s, ym + ux * side_s
                            if not surf.inside(lx, ly) or surf.slope(lx, ly) > PHYSICS["max_tilt"]:
                                ok = False
                                break
                        if not ok:
                            break
                        if slp > max_s:
                            max_s = slp
                    if not ok:
                        continue
                    dt_sum = 0.0
                    e_sum = 0.0
                    n_sub = 2 if L <= 7.5 else 3
                    ds = L / n_sub
                    prev_h = h0
                    for s in range(n_sub):
                        xm = x0 + (x1 - x0) * ((s + 0.5) / n_sub)
                        ym = y0 + (y1 - y0) * ((s + 0.5) / n_sub)
                        _, gx, gy, code = surf.sample(xm, ym)
                        name = TERRAIN_CODES[code]
                        grade = gx * ux + gy * uy
                        slip = min(0.95, max(0.0, SLIP_MID[name] + PHYSICS["slip_grade_gain"][name] * max(0.0, grade)))
                        wheel_ds = ds / (1.0 - slip)
                        dt_sum += wheel_ds / 5.0
                        he = surf.elevation(x0 + (x1 - x0) * ((s + 1) / n_sub), y0 + (y1 - y0) * ((s + 1) / n_sub))
                        e_sum += wheel_ds * PHYSICS["drive_cost_per_wheel_m"][name] + PHYSICS["climb_cost_per_m"] * max(0.0, he - prev_h)
                        prev_h = he
                    if max_s > 0.27:
                        dt_sum += (max_s - 0.27) * 4.0
                    self.adj[j][i].append((ni, nj, dt_sum, e_sum))

    def nearest_safe_vertices(self, x: float, y: float) -> List[Tuple[int, int, float, float]]:
        fx, fy = x / self.cell, y / self.cell
        i0 = min(self.nx - 2, max(0, int(fx)))
        j0 = min(self.ny - 2, max(0, int(fy)))
        cands = []
        for di in (0, 1):
            for dj in (0, 1):
                ni, nj = i0 + di, j0 + dj
                if self.safe_pt[nj][ni]:
                    vx, vy = ni * self.cell, nj * self.cell
                    L = math.hypot(vx - x, vy - y)
                    dt, de = self.segment_cost(x, y, vx, vy)
                    if dt < 1e8:
                        cands.append((ni, nj, dt, de))
        if not cands:
            best = []
            for r in range(1, 5):
                for di in range(-r, r + 1):
                    for dj in range(-r, r + 1):
                        ni, nj = i0 + di, j0 + dj
                        if 0 <= ni < self.nx and 0 <= nj < self.ny and self.safe_pt[nj][ni]:
                            vx, vy = ni * self.cell, nj * self.cell
                            L = math.hypot(vx - x, vy - y)
                            best.append((L, ni, nj))
                if best:
                    best.sort()
                    _, ni, nj = best[0]
                    vx, vy = ni * self.cell, nj * self.cell
                    cands.append((ni, nj, math.hypot(vx - x, vy - y) / 4.2, math.hypot(vx - x, vy - y) * 0.5))
                    break
        return cands

    def segment_cost(self, x0: float, y0: float, x1: float, y1: float) -> Tuple[float, float]:
        L = math.hypot(x1 - x0, y1 - y0)
        if L < 1e-6:
            return 0.0, 0.0
        steps = max(2, int(math.ceil(L / 1.0)))
        ux, uy = (x1 - x0) / L, (y1 - y0) / L
        dt_sum = 0.0
        e_sum = 0.0
        ds = L / steps
        prev_h = self.surf.elevation(x0, y0)
        for s in range(steps):
            xm = x0 + (x1 - x0) * ((s + 0.5) / steps)
            ym = y0 + (y1 - y0) * ((s + 0.5) / steps)
            if not self.surf.inside(xm, ym):
                return 1e9, 1e9
            _, gx, gy, code = self.surf.sample(xm, ym)
            if math.hypot(gx, gy) > self.max_tilt:
                return 1e9, 1e9
            name = TERRAIN_CODES[code]
            grade = gx * ux + gy * uy
            slip = min(0.95, max(0.0, SLIP_MID[name] + PHYSICS["slip_grade_gain"][name] * max(0.0, grade)))
            wheel_ds = ds / (1.0 - slip)
            dt_sum += wheel_ds / 5.0
            he = self.surf.elevation(x0 + (x1 - x0) * ((s + 1) / steps), y0 + (y1 - y0) * ((s + 1) / steps))
            e_sum += wheel_ds * PHYSICS["drive_cost_per_wheel_m"][name] + PHYSICS["climb_cost_per_m"] * max(0.0, he - prev_h)
            prev_h = he
        return dt_sum, e_sum

    def dijkstra_from_point(self, x: float, y: float, alpha: float):
        nx, ny = self.nx, self.ny
        cost = [[1e9] * nx for _ in range(ny)]
        d = [[1e9] * nx for _ in range(ny)]
        e = [[1e9] * nx for _ in range(ny)]
        pq = []
        for ni, nj, dt, de in self.nearest_safe_vertices(x, y):
            c = dt + alpha * de
            if c < cost[nj][ni]:
                cost[nj][ni] = c
                d[nj][ni] = dt
                e[nj][ni] = de
                heapq.heappush(pq, (c, ni, nj))
        adj = self.adj
        while pq:
            cc, i, j = heapq.heappop(pq)
            if cc > cost[j][i] + 1e-9:
                continue
            cd, ce = d[j][i], e[j][i]
            for ni, nj, dt, de in adj[j][i]:
                nc = cc + dt + alpha * de
                if nc < cost[nj][ni]:
                    cost[nj][ni] = nc
                    d[nj][ni] = cd + dt
                    e[nj][ni] = ce + de
                    heapq.heappush(pq, (nc, ni, nj))
        return d, e

    def find_path(self, x0: float, y0: float, x1: float, y1: float, alpha: float) -> Tuple[List[Tuple[float, float]], float, float]:
        if math.hypot(x1 - x0, y1 - y0) <= 12.0:
            dt, de = self.segment_cost(x0, y0, x1, y1)
            if dt < 1e8:
                return [(x1, y1)], dt, de

        nx, ny = self.nx, self.ny
        cell = self.cell
        cost = [[1e9] * nx for _ in range(ny)]
        d = [[1e9] * nx for _ in range(ny)]
        e = [[1e9] * nx for _ in range(ny)]
        parent: Dict[Tuple[int, int], Optional[Tuple[int, int]]] = {}
        pq = []
        for ni, nj, dt, de in self.nearest_safe_vertices(x0, y0):
            c = dt + alpha * de
            if c < cost[nj][ni]:
                cost[nj][ni] = c
                d[nj][ni] = dt
                e[nj][ni] = de
                parent[(ni, nj)] = None
                h = math.hypot(x1 - ni * cell, y1 - nj * cell) / 4.8
                heapq.heappush(pq, (c + h, c, ni, nj))

        goal_cands = {
            (ni, nj): (dt, de) for ni, nj, dt, de in self.nearest_safe_vertices(x1, y1)
        }
        best_goal = None
        best_total_c = 1e9
        best_dt, best_de = 1e9, 1e9
        adj = self.adj

        while pq:
            _, cc, i, j = heapq.heappop(pq)
            if cc > cost[j][i] + 1e-9:
                continue
            if cc >= best_total_c:
                break
            if (i, j) in goal_cands:
                gdt, gde = goal_cands[(i, j)]
                tc = cc + gdt + alpha * gde
                if tc < best_total_c:
                    best_total_c = tc
                    best_goal = (i, j)
                    best_dt = d[j][i] + gdt
                    best_de = e[j][i] + gde
            cd, ce = d[j][i], e[j][i]
            for ni, nj, dt, de in adj[j][i]:
                nc = cc + dt + alpha * de
                if nc < cost[nj][ni]:
                    cost[nj][ni] = nc
                    d[nj][ni] = cd + dt
                    e[nj][ni] = ce + de
                    parent[(ni, nj)] = (i, j)
                    h = math.hypot(x1 - ni * cell, y1 - nj * cell) / 4.8
                    heapq.heappush(pq, (nc + h, nc, ni, nj))

        if best_goal is None:
            return [(x1, y1)], 1e9, 1e9

        pts = []
        cur: Optional[Tuple[int, int]] = best_goal
        while cur is not None:
            pts.append((cur[0] * cell, cur[1] * cell))
            cur = parent[cur]
        pts.reverse()
        if math.hypot(pts[-1][0] - x1, pts[-1][1] - y1) > 0.2:
            pts.append((x1, y1))
        return pts, best_dt, best_de


class StateEstimator:
    def __init__(self, surf: Surface, rules: Dict[str, Any], base: Tuple[float, float], n_particles: int = 250, seed: int = 1):
        self.surf = surf
        self.rules = rules
        self.rng = random.Random(seed)
        self.n_p = n_particles
        self.particles = [
            [base[0], base[1], self.rng.uniform(-5.0, 5.0)]
            for _ in range(self.n_p)
        ]
        self.weights = [1.0 / self.n_p] * self.n_p
        self.last_pkt_tick = 0
        self.last_bat = float(rules["initial_battery"])
        self.eff_est = float(rules["solar_efficiency_range"][0])
        self.eff_known = False
        self.sampled_ids = set()

        # 21-point discrete Bayesian posterior per terrain
        self.slip_grid: Dict[str, List[float]] = {}
        self.slip_prob: Dict[str, List[float]] = {}
        for tname, (lo, hi) in PHYSICS["slip_base_ranges"].items():
            pts = [lo + (hi - lo) * i / 20.0 for i in range(21)]
            self.slip_grid[tname] = pts
            self.slip_prob[tname] = [1.0 / 21.0] * 21

    def slip_est(self) -> Dict[str, float]:
        return {
            t: sum(g * p for g, p in zip(self.slip_grid[t], self.slip_prob[t]))
            for t in self.slip_grid
        }

    def mean_state(self) -> Tuple[float, float, float]:
        mx = sum(p[0] * w for p, w in zip(self.particles, self.weights))
        my = sum(p[1] * w for p, w in zip(self.particles, self.weights))
        mb = sum(p[2] * w for p, w in zip(self.particles, self.weights))
        return mx, my, mb

    def _update_slip(self, mx: float, my: float, mb: float, cmd_hdg: float, metres: float, vo: float, obs_terrain: str):
        # Only update if terrain at start and end match obs_terrain and metres >= 1.0
        if metres < 1.0:
            return
        if self.surf.terrain(mx, my) != obs_terrain:
            return
        pts = self.slip_grid[obs_terrain]
        probs = self.slip_prob[obs_terrain]
        s_est = self.slip_est()
        h_exec = cmd_hdg + mb
        sigma_vo = max(0.08, 0.055 * metres)
        new_p = []
        for s_val, pr in zip(pts, probs):
            s_try = dict(s_est)
            s_try[obs_terrain] = s_val
            res = drive(self.surf, PHYSICS, mx, my, h_exec, metres, s_try, noise=0.0)
            if res["stop"] is not None:
                new_p.append(pr)
            else:
                err = (vo - res["ground"]) / sigma_vo
                new_p.append(pr * math.exp(-0.5 * err * err))
        tot = sum(new_p)
        if tot > 1e-30:
            self.slip_prob[obs_terrain] = [v / tot for v in new_p]

    def process_packet(self, pkt: Dict[str, Any], sent_commands: Dict[int, Dict[str, Any]]):
        tk = pkt["tick"]
        if tk <= self.last_pkt_tick:
            return
        self.sampled_ids = set(pkt.get("sampled_targets", []))
        if not self.eff_known and self.last_bat < 98.0 and pkt["charge"] > 0.0:
            s_sin = SOLAR_SIN[tk]
            if s_sin > 0.1:
                eff = pkt["charge"] / s_sin
                lo, hi = self.rules["solar_efficiency_range"]
                self.eff_est = min(hi, max(lo, eff))
                self.eff_known = True

        self.last_bat = pkt["battery"]
        self.last_pkt_tick = tk

        cmd = sent_commands.get(tk, {"action": "wait"})
        pos = pkt["position"]
        obs_ter = pkt["terrain"]
        obs_tilt = pkt["tilt"]
        vo = pkt["visual_odometry"]
        wo = pkt["wheel_odometry"]

        if cmd["action"] == "drive" and wo > 0.0:
            mx, my, mb = self.mean_state()
            self._update_slip(mx, my, mb, float(cmd["heading_deg"]), float(cmd["metres"]), vo, obs_ter)

        s_est = self.slip_est()
        log_w = []
        max_lw = -1e18
        if cmd["action"] == "drive" and wo > 0.0:
            cmd_h = float(cmd["heading_deg"])
            m = float(cmd["metres"])
            for i in range(self.n_p):
                x, y, b = self.particles[i]
                b_new = b + self.rng.gauss(0.0, 0.2)
                h_exec = cmd_h + b_new + self.rng.gauss(0.0, 1.5)
                s_noise = self.rng.uniform(-0.02, 0.02)
                res = drive(self.surf, PHYSICS, x, y, h_exec, m, s_est, noise=s_noise)
                nx, ny = res["x"], res["y"]
                self.particles[i] = [nx, ny, b_new]

                ll = -0.5 * ((nx - pos[0]) ** 2 + (ny - pos[1]) ** 2)
                sig_vo = max(0.05, 0.05 * max(0.5, res["ground"]))
                ll -= 0.5 * ((vo - res["ground"]) / sig_vo) ** 2
                if self.surf.terrain(nx, ny) != obs_ter:
                    ll -= 3.5
                tilt_p = self.surf.slope(nx, ny)
                ll -= 0.5 * ((tilt_p - obs_tilt) / 0.018) ** 2
                lw = math.log(max(1e-30, self.weights[i])) + ll
                log_w.append(lw)
                if lw > max_lw:
                    max_lw = lw
        else:
            for i in range(self.n_p):
                x, y, b = self.particles[i]
                ll = -0.5 * ((x - pos[0]) ** 2 + (y - pos[1]) ** 2)
                if self.surf.terrain(x, y) != obs_ter:
                    ll -= 3.5
                tilt_p = self.surf.slope(x, y)
                ll -= 0.5 * ((tilt_p - obs_tilt) / 0.018) ** 2
                lw = math.log(max(1e-30, self.weights[i])) + ll
                log_w.append(lw)
                if lw > max_lw:
                    max_lw = lw

        ws = [math.exp(lw - max_lw) for lw in log_w]
        tot = sum(ws)
        if tot <= 0:
            self.weights = [1.0 / self.n_p] * self.n_p
        else:
            self.weights = [w / tot for w in ws]

        ess = 1.0 / sum(w * w for w in self.weights)
        if ess < 0.5 * self.n_p:
            self._resample()

    def _resample(self):
        cdf = []
        acc = 0.0
        for w in self.weights:
            acc += w
            cdf.append(acc)
        cdf[-1] = 1.0
        step = 1.0 / self.n_p
        u0 = self.rng.uniform(0.0, step)
        new_p = []
        idx = 0
        for k in range(self.n_p):
            u = u0 + k * step
            while u > cdf[idx] and idx < self.n_p - 1:
                idx += 1
            px, py, pb = self.particles[idx]
            px = min(self.surf.width, max(0.0, px + self.rng.gauss(0.0, 0.05)))
            py = min(self.surf.height, max(0.0, py + self.rng.gauss(0.0, 0.05)))
            pb = min(7.0, max(-7.0, pb + self.rng.gauss(0.0, 0.05)))
            new_p.append([px, py, pb])
        self.particles = new_p
        self.weights = [1.0 / self.n_p] * self.n_p

    def _sample_slip(self) -> Dict[str, float]:
        out = {}
        for t, pts in self.slip_grid.items():
            probs = self.slip_prob[t]
            r = self.rng.random()
            acc = 0.0
            chosen = pts[-1]
            for g, p in zip(pts, probs):
                acc += p
                if r <= acc:
                    chosen = g
                    break
            out[t] = chosen
        return out

    def predict_state(self, target_tick: int, sent_commands: Dict[int, Dict[str, Any]], n_sample: int = 35):
        cdf = []
        acc = 0.0
        for w in self.weights:
            acc += w
            cdf.append(acc)
        cdf[-1] = 1.0
        step = 1.0 / n_sample
        u0 = 0.5 * step
        cloud = []
        cloud_slips = []
        idx = 0
        for k in range(n_sample):
            u = u0 + k * step
            while u > cdf[idx] and idx < self.n_p - 1:
                idx += 1
            cloud.append(list(self.particles[idx]))
            cloud_slips.append(self._sample_slip())

        bat = self.last_bat
        eff_cons = self.eff_est
        for tk in range(self.last_pkt_tick + 1, target_tick):
            g = eff_cons * SOLAR_SIN[tk]
            bat = min(100.0, bat + g) - IDLE_COST
            cmd = sent_commands.get(tk, {"action": "wait"})
            if cmd["action"] == "sample":
                bat -= SAMPLE_COST
            elif cmd["action"] == "drive":
                cmd_h = float(cmd["heading_deg"])
                m = float(cmd["metres"])
                e_list = []
                for p, s_draw in zip(cloud, cloud_slips):
                    p[2] += self.rng.gauss(0.0, 0.2)
                    h_exec = cmd_h + p[2] + self.rng.gauss(0.0, 1.5)
                    s_noise = self.rng.uniform(-0.02, 0.02)
                    res = drive(self.surf, PHYSICS, p[0], p[1], h_exec, m, s_draw, noise=s_noise)
                    p[0], p[1] = res["x"], res["y"]
                    e_list.append(res["energy"])
                e_list.sort()
                bat -= e_list[int(0.75 * len(e_list))]

        mx = sum(p[0] for p in cloud) / len(cloud)
        my = sum(p[1] for p in cloud) / len(cloud)
        mb = sum(p[2] for p in cloud) / len(cloud)
        return mx, my, mb, bat, cloud


class Autopilot:
    def __init__(self, world: Dict[str, Any], rules: Dict[str, Any], seed: int = 1,
                 precomputed: Optional[Tuple[Any, Any, Any, Any]] = None):
        self.world = world
        self.rules = rules
        self.base = tuple(world["base"])
        self.alphas = (0.02, 0.45)
        self.targets: Dict[str, Dict[str, Any]] = {t["id"]: dict(t) for t in world["targets"]}
        self.node_ids: List[str] = ["BASE"] + [t["id"] for t in world["targets"]]
        self.node_xy: Dict[str, Tuple[float, float]] = {"BASE": self.base}
        for t in world["targets"]:
            self.node_xy[t["id"]] = (t["x"], t["y"])

        if precomputed is not None:
            self.surf, self.nav, dt_copy, de_copy = precomputed
            self.dist_t = {0: dict(dt_copy[0]), 1: dict(dt_copy[1])}
            self.dist_e = {0: dict(de_copy[0]), 1: dict(de_copy[1])}
        else:
            self.surf = Surface(world["cell_m"], world["elevation_cm"], world["terrain"])
            self.nav = NavGraph(self.surf, margin=0.03)
            self.dist_t = {0: {}, 1: {}}
            self.dist_e = {0: {}, 1: {}}
            self._precompute_all()

        self.est = StateEstimator(self.surf, rules, self.base, n_particles=220, seed=seed)
        self.rng = random.Random(seed + 100)
        self._was_eff_known = False

        self.sent_commands: Dict[int, Dict[str, Any]] = {}
        self.last_reserved = 0
        self.pending_sample_ticks: Dict[str, int] = {}
        self.current_route: List[str] = []
        self.last_replan_tick = -999
        self.cached_path: Optional[Tuple[str, float, List[Tuple[float, float]]]] = None

    def _add_node_apsp(self, nid: str, x: float, y: float):
        self.node_xy[nid] = (x, y)
        if nid not in self.node_ids:
            self.node_ids.append(nid)
        cell = self.nav.cell
        for m_idx, alpha in enumerate(self.alphas):
            d_grid, e_grid = self.nav.dijkstra_from_point(x, y, alpha)
            for other in self.node_ids:
                ox, oy = self.node_xy[other]
                oi, oj = round(ox / cell), round(oy / cell)
                dt = d_grid[oj][oi]
                de = e_grid[oj][oi]
                self.dist_t[m_idx][(nid, other)] = dt
                self.dist_e[m_idx][(nid, other)] = de
                self.dist_t[m_idx][(other, nid)] = dt
                self.dist_e[m_idx][(other, nid)] = de

    def _precompute_all(self):
        cell = self.nav.cell
        for m_idx, alpha in enumerate(self.alphas):
            for a in self.node_ids:
                ax, ay = self.node_xy[a]
                d_grid, e_grid = self.nav.dijkstra_from_point(ax, ay, alpha)
                for b in self.node_ids:
                    bx, by = self.node_xy[b]
                    bi, bj = round(bx / cell), round(by / cell)
                    self.dist_t[m_idx][(a, b)] = d_grid[bj][bi]
                    self.dist_e[m_idx][(a, b)] = e_grid[bj][bi]

    def ingest_packets(self, packets: List[Dict[str, Any]], world_targets: Optional[List[Dict[str, Any]]] = None):
        need_replan = False
        packets_sorted = sorted(packets, key=lambda p: p["tick"])
        for pkt in packets_sorted:
            for ev in pkt.get("events", []):
                if isinstance(ev, dict):
                    etype = str(ev.get("type", "")).lower()
                    if etype == "target_discovered" and isinstance(ev.get("target"), dict):
                        tgt = ev["target"]
                        tid = tgt["id"]
                        if tid not in self.targets:
                            self.targets[tid] = dict(tgt)
                            self._add_node_apsp(tid, tgt["x"], tgt["y"])
                            need_replan = True
                    elif "stop" in etype or "tilt" in etype or "boundary" in etype:
                        for k in [kk for kk in self.sent_commands if kk > pkt["tick"]]:
                            del self.sent_commands[k]
                        need_replan = True
                    elif "miss" in etype:
                        need_replan = True
            cmd_at_tk = self.sent_commands.get(pkt["tick"])
            if cmd_at_tk and cmd_at_tk.get("action") == "drive" and pkt.get("wheel_odometry", 0.0) < float(cmd_at_tk["metres"]) - 0.1:
                for k in [kk for kk in self.sent_commands if kk > pkt["tick"]]:
                    del self.sent_commands[k]
                need_replan = True
            self.est.process_packet(pkt, self.sent_commands)
            if self.est.eff_known and not self._was_eff_known:
                self._was_eff_known = True
                need_replan = True
            # Clear pending samples whose packets have arrived
            for tid in list(self.pending_sample_ticks.keys()):
                if self.pending_sample_ticks[tid] <= pkt["tick"]:
                    del self.pending_sample_ticks[tid]

        if world_targets:
            for tgt in world_targets:
                tid = tgt["id"]
                if tid not in self.targets:
                    self.targets[tid] = dict(tgt)
                    self._add_node_apsp(tid, tgt["x"], tgt["y"])
                    need_replan = True
        return need_replan

    def replan(self, t_exec: int, x_pred: float, y_pred: float, bat_pred: float):
        # Compute shortest distances from (x_pred, y_pred) to all nodes
        cell = self.nav.cell
        eff = self.est.eff_est
        start_dt = [{}, {}]
        start_de = [{}, {}]
        for m_idx, alpha in enumerate(self.alphas):
            d_grid, e_grid = self.nav.dijkstra_from_point(x_pred, y_pred, alpha)
            for nid, (nx_p, ny_p) in self.node_xy.items():
                ni, nj = round(nx_p / cell), round(ny_p / cell)
                start_dt[m_idx][nid] = d_grid[nj][ni]
                start_de[m_idx][nid] = e_grid[nj][ni]

        rem = [
            tid for tid in self.targets
            if tid not in self.est.sampled_ids and tid not in self.pending_sample_ticks
        ]
        # Filter out targets already infeasible to reach and return to base by 414
        feasible_rem = []
        for tid in rem:
            if t_exec + start_dt[0][tid] + 1 + self.dist_t[0][(tid, "BASE")] <= 415:
                feasible_rem.append(tid)

        if not feasible_rem:
            self.current_route = []
            self.last_replan_tick = t_exec
            return

        # Fast route evaluator from (x_pred, y_pred) at t_exec, bat_pred
        slip_mult = 1.03
        wait_margin = 5.0
        end_limit = 415  # 5-tick safety buffer for base return!

        def eval_suffix(order: List[str]):
            tk = t_exec
            bat = bat_pred
            score = 0.0
            cur = None
            for nxt in order + ["BASE"]:
                best_leg = None
                for m_idx in (0, 1):
                    dt = (start_dt[m_idx][nxt] if cur is None else self.dist_t[m_idx][(cur, nxt)]) * slip_mult
                    de = (start_de[m_idx][nxt] if cur is None else self.dist_e[m_idx][(cur, nxt)]) * slip_mult
                    ticks = 0 if dt < 0.25 else max(1, int(math.ceil(dt)))
                    if tk + ticks > end_limit:
                        continue
                    if ticks == 0:
                        tk_s, bat_end = tk, bat
                    else:
                        tk_end = tk + ticks - 1
                        net_solar = eff * (SOLAR_PRE[tk_end] - SOLAR_PRE[tk - 1])
                        bat_end = bat + net_solar - IDLE_COST * ticks - de
                        if bat_end < wait_margin or bat > 92.0:
                            b = bat
                            tk_s = tk
                            e_tick = de / ticks
                            ok = True
                            for _ in range(ticks):
                                if tk_s > end_limit:
                                    ok = False
                                    break
                                nb = min(100.0, b + eff * SOLAR_SIN[tk_s]) - IDLE_COST - e_tick
                                while nb < wait_margin:
                                    b = min(100.0, b + eff * SOLAR_SIN[tk_s]) - IDLE_COST
                                    tk_s += 1
                                    if tk_s > end_limit:
                                        ok = False
                                        break
                                    nb = min(100.0, b + eff * SOLAR_SIN[tk_s]) - IDLE_COST - e_tick
                                if not ok:
                                    break
                                b = nb
                                tk_s += 1
                            if not ok:
                                continue
                            bat_end = b
                        else:
                            if bat_end > 100.0:
                                bat_end = 100.0
                            tk_s = tk + ticks
                    if best_leg is None or tk_s < best_leg[0] or (tk_s == best_leg[0] and bat_end > best_leg[1]):
                        best_leg = (tk_s, bat_end)
                if best_leg is None:
                    return -1.0, end_limit + 1
                tk, bat = best_leg
                if nxt == "BASE":
                    break
                if tk >= end_limit:
                    return -1.0, end_limit + 1
                nb = min(100.0, bat + eff * SOLAR_SIN[tk]) - IDLE_COST - SAMPLE_COST
                while nb < wait_margin:
                    bat = min(100.0, bat + eff * SOLAR_SIN[tk]) - IDLE_COST
                    tk += 1
                    if tk >= end_limit:
                        return -1.0, end_limit + 1
                    nb = min(100.0, bat + eff * SOLAR_SIN[tk]) - IDLE_COST - SAMPLE_COST
                bat = nb
                info = self.targets[nxt]
                if info["deadline_tick"] is None or tk <= info["deadline_tick"]:
                    score += info["value"]
                else:
                    score += info["late_value"]
                tk += 1
                cur = nxt
            return score, tk

        # Warm-start from current_route (filtered to feasible_rem) + greedy insertion
        seed_routes = []
        warm = [tid for tid in self.current_route if tid in feasible_rem]
        while warm and eval_suffix(warm)[0] < 0:
            warm.pop()
        if warm:
            # Greedily try inserting any new/unused targets into warm
            for tid in feasible_rem:
                if tid in warm:
                    continue
                best_pos = None
                best_s = eval_suffix(warm)[0]
                for pos in range(len(warm) + 1):
                    cand = warm[:pos] + [tid] + warm[pos:]
                    s, _ = eval_suffix(cand)
                    if s > best_s:
                        best_s = s
                        best_pos = pos
                if best_pos is not None:
                    warm.insert(best_pos, tid)
            seed_routes.append(warm)

        # Also construct diverse greedy value/time seeds
        for g_idx in range(3):
            g_route = []
            used = set()
            for _step in range(len(feasible_rem)):
                last = g_route[-1] if g_route else None
                cands = [tid for tid in feasible_rem if tid not in used]
                cands.sort(key=lambda x: (start_dt[0][x] if last is None else self.dist_t[0][(last, x)]) / (self.targets[x]["value"] + 0.5))
                pool = cands[:4]
                if g_idx > 0 and len(pool) > 1:
                    self.rng.shuffle(pool)
                added = False
                for pick in pool:
                    if eval_suffix(g_route + [pick])[0] >= 0:
                        g_route.append(pick)
                        used.add(pick)
                        added = True
                        break
                if not added:
                    break
            seed_routes.append(g_route)

        best_sc = -1.0
        best_route: List[str] = []
        best_end = end_limit
        for s_idx, init_r in enumerate(seed_routes):
            cur_r = list(init_r)
            cur_s, cur_e = eval_suffix(cur_r)
            if cur_s < 0:
                continue
            cur_obj = cur_s + (end_limit - cur_e) * 0.002
            if cur_s > best_sc or (cur_s == best_sc and cur_e < best_end):
                best_sc, best_route, best_end = cur_s, list(cur_r), cur_e
            n_iters = 1400 if s_idx == 0 else 1000
            for it in range(n_iters):
                cand = list(cur_r)
                op = self.rng.random()
                unused = [x for x in feasible_rem if x not in cand]
                if op < 0.35 and unused:
                    cand.insert(self.rng.randint(0, len(cand)), self.rng.choice(unused))
                elif op < 0.48 and len(cand) > 1:
                    cand.pop(self.rng.randrange(len(cand)))
                elif op < 0.70 and len(cand) >= 2:
                    a, b = self.rng.sample(range(len(cand)), 2)
                    cand[a], cand[b] = cand[b], cand[a]
                elif op < 0.85 and len(cand) >= 2:
                    x = cand.pop(self.rng.randrange(len(cand)))
                    cand.insert(self.rng.randrange(len(cand) + 1), x)
                elif len(cand) >= 3:
                    a, b = sorted(self.rng.sample(range(len(cand)), 2))
                    cand[a:b + 1] = reversed(cand[a:b + 1])
                res_s, res_e = eval_suffix(cand)
                if res_s < 0:
                    continue
                obj = res_s + (end_limit - res_e) * 0.002
                temp = 1.2 * (1.0 - it / n_iters) + 0.02
                if obj >= cur_obj or self.rng.random() < math.exp((obj - cur_obj) / temp):
                    cur_r, cur_obj = cand, obj
                    if res_s > best_sc or (res_s == best_sc and res_e < best_end):
                        best_sc, best_route, best_end = res_s, list(cand), res_e

        self.current_route = best_route
        self.last_replan_tick = t_exec
        self.cached_path = None

    def _safe_for_cloud(self, x_mean: float, y_mean: float, bias_mean: float,
                        cloud: List[List[float]], cmd_hdg: float, metres: float,
                        s_est: Dict[str, float]) -> bool:
        std_pos = math.sqrt(sum((p[0] - x_mean) ** 2 + (p[1] - y_mean) ** 2 for p in cloud) / len(cloud))
        r_unc = max(0.35, min(1.4, 2.0 * std_pos))
        if (12.0 < x_mean < self.surf.width - 12.0 and
                12.0 < y_mean < self.surf.height - 12.0 and
                self.surf.slope(x_mean, y_mean) < 0.21):
            checks = [
                (x_mean, y_mean, bias_mean),
                (x_mean + r_unc, y_mean, bias_mean + 3.0),
                (x_mean - r_unc, y_mean, bias_mean - 3.0),
                (x_mean, y_mean + r_unc, bias_mean),
                (x_mean, y_mean - r_unc, bias_mean),
            ]
        else:
            checks = []
            for dx, dy in [(0, 0), (r_unc, 0), (-r_unc, 0), (0, r_unc), (0, -r_unc),
                           (0.7 * r_unc, 0.7 * r_unc), (-0.7 * r_unc, -0.7 * r_unc)]:
                for db in (-3.5, 0.0, 3.5):
                    checks.append((x_mean + dx, y_mean + dy, bias_mean + db))
            step_p = max(1, len(cloud) // 8)
            for p in cloud[::step_p]:
                for db in (-3.5, 3.5):
                    checks.append((p[0], p[1], p[2] + db))

        for px, py, pb in checks:
            if not self.surf.inside(px, py):
                return False
            res = drive(self.surf, PHYSICS, px, py, cmd_hdg + pb, metres, s_est, noise=-0.02)
            if res["stop"] in ("tilt", "map_boundary"):
                return False
        return True

    def choose_command(self, current_tick: int, force_replan: bool = False) -> Optional[Dict[str, Any]]:
        t_exec = max(current_tick + self.rules["delay_ticks"] + 1, self.last_reserved + 1)
        if t_exec > MAX_TICKS:
            return None

        x_pred, y_pred, bias_pred, bat_pred, cloud = self.est.predict_state(t_exec, self.sent_commands)

        # Clean route of already sampled or pending targets
        self.current_route = [
            tid for tid in self.current_route
            if tid not in self.est.sampled_ids and tid not in self.pending_sample_ticks
        ]

        if force_replan or (t_exec - self.last_replan_tick >= 25) or (not self.current_route and t_exec < 350):
            self.replan(t_exec, x_pred, y_pred, bat_pred)

        # Choose goal: first in current_route, unless emergency RTB
        goal_id = self.current_route[0] if self.current_route else "BASE"
        if goal_id != "BASE":
            gx, gy = self.node_xy[goal_id]
            _, dt_to_goal, de_to_goal = self.nav.find_path(x_pred, y_pred, gx, gy, 0.02)
            dt_goal_to_base = self.dist_t[0][(goal_id, "BASE")]
            de_goal_to_base = self.dist_e[0][(goal_id, "BASE")]
            tot_dt = dt_to_goal * 1.06 + 1 + dt_goal_to_base * 1.06
            tot_de = de_to_goal * 1.06 + SAMPLE_COST + de_goal_to_base * 1.06 + IDLE_COST * tot_dt
            t_arr = min(MAX_TICKS, int(t_exec + tot_dt))
            solar_avail = self.est.eff_est * (SOLAR_PRE[t_arr] - SOLAR_PRE[t_exec - 1])
            bat_deficit = max(0.0, tot_de - (bat_pred - 3.0 + solar_avail))
            waits_est = bat_deficit / max(0.5, self.est.eff_est * SOLAR_SIN[min(MAX_TICKS, t_arr)] - IDLE_COST)
            if t_exec + tot_dt + waits_est > 416.0:
                goal_id = "BASE"
                self.current_route = []

        tx, ty = self.node_xy[goal_id]

        # Check if we are at target or BASE
        if goal_id != "BASE":
            dists = [math.hypot(p[0] - tx, p[1] - ty) for p in cloud]
            p_in = sum(1 for d in dists if d <= TARGET_RADIUS - 0.25) / len(dists)
            mean_d = sum(dists) / len(dists)
            dl = self.targets[goal_id]["deadline_tick"]
            urgent_dl = (dl is not None and t_exec == dl and sum(1 for d in dists if d <= TARGET_RADIUS - 0.05) / len(dists) >= 0.85)
            if (p_in >= 0.97 and mean_d <= 1.35) or (mean_d <= 1.05 and max(dists) <= TARGET_RADIUS - 0.2) or urgent_dl:
                g = self.est.eff_est * SOLAR_SIN[t_exec]
                if min(100.0, bat_pred + g) - IDLE_COST - SAMPLE_COST >= 3.0:
                    self.pending_sample_ticks[goal_id] = t_exec
                    return {"action": "sample"}
                else:
                    return {"action": "wait"}
        else:
            dists = [math.hypot(p[0] - tx, p[1] - ty) for p in cloud]
            p_in = sum(1 for d in dists if d <= BASE_RADIUS - 0.6) / len(dists)
            mean_d = sum(dists) / len(dists)
            if p_in >= 0.98 and mean_d <= 2.2:
                return {"action": "wait"}

        # Compute/reuse A* path to goal
        alpha = 0.45 if (bat_pred < 25.0 or (t_exec < 120 and not self.est.eff_known and bat_pred < 65.0) or (t_exec < 120 and self.est.eff_est < 0.87 and bat_pred < 50.0)) else 0.02
        need_path = (
            self.cached_path is None
            or self.cached_path[0] != goal_id
            or abs(self.cached_path[1] - alpha) > 0.05
        )
        if need_path:
            pts, _, _ = self.nav.find_path(x_pred, y_pred, tx, ty, alpha)
            self.cached_path = (goal_id, alpha, pts)
        else:
            pts = self.cached_path[2]

        # Pick lookahead waypoint ~10m ahead on path, or direct to goal if close & clear
        direct_dist = math.hypot(tx - x_pred, ty - y_pred)
        if direct_dist <= 13.0 and self.nav.segment_cost(x_pred, y_pred, tx, ty)[0] < 1e8:
            lx, ly = tx, ty
        else:
            # Find closest segment / next waypoint >= 8m ahead
            lx, ly = pts[-1]
            best_idx = 0
            best_d = 1e9
            for idx, (wx, wy) in enumerate(pts):
                d = math.hypot(wx - x_pred, wy - y_pred)
                if d < best_d:
                    best_d = d
                    best_idx = idx
            for idx in range(best_idx, len(pts)):
                wx, wy = pts[idx]
                if math.hypot(wx - x_pred, wy - y_pred) >= 7.5:
                    lx, ly = wx, wy
                    break

        s_est = self.est.slip_est()
        # Choose heading H compensating for bias_pred AND side_slip using drive()
        base_hdg = math.degrees(math.atan2(ly - y_pred, lx - x_pred)) - bias_pred
        best_h = base_hdg
        best_err = 1e9
        ux_g = (lx - x_pred) / max(1e-6, math.hypot(lx - x_pred, ly - y_pred))
        uy_g = (ly - y_pred) / max(1e-6, math.hypot(lx - x_pred, ly - y_pred))
        test_m = min(5.0, max(1.0, math.hypot(lx - x_pred, ly - y_pred)))
        for dh in range(-14, 15, 2):
            h_cand = base_hdg + dh
            res = drive(self.surf, PHYSICS, x_pred, y_pred, h_cand + bias_pred, test_m, s_est, noise=0.0)
            if res["stop"] is not None:
                continue
            dx = res["x"] - x_pred
            dy = res["y"] - y_pred
            # Maximize progress toward (lx, ly) minus lateral error
            proj = dx * ux_g + dy * uy_g
            lat = abs(-dx * uy_g + dy * ux_g)
            score_h = lat * 2.0 - proj * 0.3
            if score_h < best_err:
                best_err = score_h
                best_h = h_cand

        # Determine exact metres M
        metres = 5.0
        if direct_dist <= 6.0 and (lx, ly) == (tx, ty):
            # Binary search M in (0.1, 5.0] so drive ends as close to (tx, ty) as possible
            res_full = drive(self.surf, PHYSICS, x_pred, y_pred, best_h + bias_pred, 5.0, s_est, noise=0.0)
            proj_full = (res_full["x"] - x_pred) * ux_g + (res_full["y"] - y_pred) * uy_g
            if proj_full >= direct_dist:
                lo, hi = 0.1, 5.0
                for _ in range(8):
                    mid = 0.5 * (lo + hi)
                    r = drive(self.surf, PHYSICS, x_pred, y_pred, best_h + bias_pred, mid, s_est, noise=0.0)
                    p = (r["x"] - x_pred) * ux_g + (r["y"] - y_pred) * uy_g
                    if p < direct_dist:
                        lo = mid
                    else:
                        hi = mid
                metres = round(0.5 * (lo + hi), 3)
                metres = min(5.0, max(0.1, metres))

        # Battery check
        res_nom = drive(self.surf, PHYSICS, x_pred, y_pred, best_h + bias_pred, metres, s_est, noise=0.0)
        g = self.est.eff_est * SOLAR_SIN[t_exec]
        bat_after = min(100.0, bat_pred + g) - IDLE_COST - res_nom["energy"] * 1.15
        bat_floor = 7.0 if not self.est.eff_known else (1.5 if (goal_id == "BASE" and t_exec > 395) else 4.0)
        if bat_after < bat_floor:
            return {"action": "wait"}

        # Safety Shield check
        if not self._safe_for_cloud(x_pred, y_pred, bias_pred, cloud, best_h, metres, s_est):
            found = False
            for m_try in (metres, min(metres, 3.0), min(metres, 1.5), 0.8):
                for dh in (0, 5, -5, 10, -10, 15, -15, 25, -25, 40, -40, 60, -60, 90, -90, 120, -120, 150, -150, 180):
                    h_try = best_h + dh
                    if self._safe_for_cloud(x_pred, y_pred, bias_pred, cloud, h_try, m_try, s_est):
                        best_h = h_try
                        metres = m_try
                        if abs(dh) >= 35:
                            self.cached_path = None
                        found = True
                        break
                if found:
                    break
            if not found:
                return {"action": "wait"}

        best_h = best_h % 360.0
        return {"action": "drive", "heading_deg": round(best_h, 2), "metres": round(metres, 3)}
