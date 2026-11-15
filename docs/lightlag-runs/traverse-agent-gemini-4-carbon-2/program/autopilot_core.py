from __future__ import annotations

import heapq
import math
import random
import time
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, "/app")
from lightlag_surface import PHYSICS, TERRAIN_CODES, Surface, drive


def angle_diff_deg(a: float, b: float) -> float:
    """Signed shortest angle a - b in [-180, 180)."""
    d = (a - b + 180.0) % 360.0 - 180.0
    return d


class TerrainNavGraph:
    """16-direction 5m grid navigation graph with steep-slope clearance and slip-aware edge costs."""

    DIRS = [
        (1, 0), (-1, 0), (0, 1), (0, -1),
        (1, 1), (1, -1), (-1, 1), (-1, -1),
        (2, 1), (2, -1), (-2, 1), (-2, -1),
        (1, 2), (1, -2), (-1, 2), (-1, -2),
    ]

    def __init__(self, surf: Surface, safe_clearance: float = 3.6) -> None:
        self.surf = surf
        self.nx = surf.nx  # 121
        self.ny = surf.ny  # 81
        self.safe_clearance = safe_clearance
        self.snx = (self.nx - 1) * 2 + 1  # 241 (2.5m subgrid)
        self.sny = (self.ny - 1) * 2 + 1  # 161
        self.clearance = self._build_clearance()
        self.adj: List[List[Tuple[int, float, float]]] = [[] for _ in range(self.nx * self.ny)]
        self.rev_adj: List[List[Tuple[int, float, float]]] = [[] for _ in range(self.nx * self.ny)]
        self.base_bt: List[float] = [1e9] * (self.nx * self.ny)
        self.base_be: List[float] = [1e9] * (self.nx * self.ny)
        self.last_slip: Dict[str, float] = {}
        mid_slip = {k: 0.5 * (v[0] + v[1]) for k, v in PHYSICS["slip_base_ranges"].items()}
        self.rebuild_edges(mid_slip)

    def _build_clearance(self) -> List[float]:
        INF = 1e9
        snx, sny = self.snx, self.sny
        clr = [INF] * (snx * sny)
        hq: List[Tuple[float, int, int]] = []
        for sj in range(sny):
            py = sj * 2.5
            for si in range(snx):
                px = si * 2.5
                if px <= 0.0 or px >= 600.0 or py <= 0.0 or py >= 400.0 or self.surf.slope(px, py) > 0.352:
                    clr[sj * snx + si] = 0.0
                    heapq.heappush(hq, (0.0, si, sj))
        neighbors = [
            (-1, 0, 2.5), (1, 0, 2.5), (0, -1, 2.5), (0, 1, 2.5),
            (-1, -1, 3.5355), (-1, 1, 3.5355), (1, -1, 3.5355), (1, 1, 3.5355),
        ]
        while hq:
            d, si, sj = heapq.heappop(hq)
            if d > clr[sj * snx + si] + 1e-6 or d > 18.0:
                continue
            for di, dj, sd in neighbors:
                ni, nj = si + di, sj + dj
                if 0 <= ni < snx and 0 <= nj < sny:
                    nd = d + sd
                    nidx = nj * snx + ni
                    if nd < clr[nidx]:
                        clr[nidx] = nd
                        heapq.heappush(hq, (nd, ni, nj))
        return clr

    def get_clearance(self, x: float, y: float) -> float:
        if not (0.0 <= x <= 600.0 and 0.0 <= y <= 400.0):
            return 0.0
        si = min(self.snx - 1, max(0, int(round(x / 2.5))))
        sj = min(self.sny - 1, max(0, int(round(y / 2.5))))
        return self.clearance[sj * self.snx + si]

    def segment_cost(
        self, x0: float, y0: float, x1: float, y1: float, slip_base: Dict[str, float], min_clr: float
    ) -> Optional[Tuple[float, float]]:
        dist = math.hypot(x1 - x0, y1 - y0)
        if dist < 1e-6:
            return (0.0, 0.0)
        n_steps = max(1, int(math.ceil(dist / 1.25)))
        ux, uy = (x1 - x0) / dist, (y1 - y0) / dist
        ds = dist / n_steps
        ticks_est = 0.0
        energy_est = 0.0
        prev_h = self.surf.elevation(x0, y0)
        gain = PHYSICS["slip_grade_gain"]
        cost_w = PHYSICS["drive_cost_per_wheel_m"]
        climb = PHYSICS["climb_cost_per_m"]
        side = PHYSICS["side_slip_gain"]
        for s in range(n_steps):
            mx = x0 + ux * (s + 0.5) * ds
            my = y0 + uy * (s + 0.5) * ds
            if self.get_clearance(mx, my) < min_clr:
                return None
            ex = x0 + ux * (s + 1) * ds
            ey = y0 + uy * (s + 1) * ds
            if self.get_clearance(ex, ey) < min_clr:
                return None
            h_end = self.surf.elevation(ex, ey)
            _, gx, gy, code = self.surf.sample(mx, my)
            tname = TERRAIN_CODES[code]
            grade = gx * ux + gy * uy
            cross = -gx * uy + gy * ux
            slip = max(0.0, min(0.92, slip_base[tname] + gain[tname] * max(0.0, grade)))
            # Account slightly for cross-slope crabbing extra wheel travel
            crab = side[tname] * abs(cross)
            eff_fwd = max(0.08, (1.0 - slip) - 0.15 * crab * crab)
            wheel_m = ds / eff_fwd
            ticks_est += wheel_m / 5.0
            energy_est += wheel_m * cost_w[tname] + climb * max(0.0, h_end - prev_h)
            prev_h = h_end
        return (ticks_est, energy_est)

    def rebuild_edges(self, slip_base: Dict[str, float], base_xy: Tuple[float, float] = (300.0, 265.0)) -> None:
        self.last_slip = dict(slip_base)
        nx, ny = self.nx, self.ny
        new_adj: List[List[Tuple[int, float, float]]] = [[] for _ in range(nx * ny)]
        new_rev: List[List[Tuple[int, float, float]]] = [[] for _ in range(nx * ny)]
        for j in range(1, ny - 1):
            y = j * 5.0
            for i in range(1, nx - 1):
                x = i * 5.0
                if self.get_clearance(x, y) < self.safe_clearance:
                    continue
                u = j * nx + i
                for di, dj in self.DIRS:
                    ni, nj = i + di, j + dj
                    if 1 <= ni < nx - 1 and 1 <= nj < ny - 1:
                        res = self.segment_cost(x, y, ni * 5.0, nj * 5.0, slip_base, self.safe_clearance)
                        if res is not None:
                            v = nj * nx + ni
                            new_adj[u].append((v, res[0], res[1]))
                            new_rev[v].append((u, res[0], res[1]))
        self.adj = new_adj
        self.rev_adj = new_rev
        # Precompute O(1) cost-to-go to base from all grid nodes!
        bu = self.nearest_safe_node(base_xy[0], base_xy[1])
        n_tot = nx * ny
        INF = 1e9
        bc = [INF] * n_tot
        bt = [INF] * n_tot
        be = [INF] * n_tot
        bc[bu] = bt[bu] = be[bu] = 0.0
        pq = [(0.0, bu)]
        while pq:
            c, u = heapq.heappop(pq)
            if c > bc[u] + 1e-9:
                continue
            ut, ue = bt[u], be[u]
            for prev_u, dt, de in new_rev[u]:
                nc = c + dt + 0.10 * de
                if nc < bc[prev_u]:
                    bc[prev_u] = nc
                    bt[prev_u] = ut + dt
                    be[prev_u] = ue + de
                    heapq.heappush(pq, (nc, prev_u))
        self.base_bt = bt
        self.base_be = be

    def fast_return_estimate(self, x: float, y: float) -> Tuple[float, float]:
        u = self.nearest_safe_node(x, y)
        ux_m, uy_m = (u % self.nx) * 5.0, (u // self.nx) * 5.0
        d = math.hypot(x - ux_m, y - uy_m)
        return self.base_bt[u] + d / 4.2, self.base_be[u] + d * 0.45

    def nearest_safe_node(self, x: float, y: float) -> int:
        ci = min(self.nx - 2, max(1, int(round(x / 5.0))))
        cj = min(self.ny - 2, max(1, int(round(y / 5.0))))
        u0 = cj * self.nx + ci
        if self.adj[u0]:
            return u0
        best_u = u0
        best_d = 1e9
        for r in range(1, 8):
            for dj in range(-r, r + 1):
                for di in range(-r, r + 1):
                    ni, nj = ci + di, cj + dj
                    if 1 <= ni < self.nx - 1 and 1 <= nj < self.ny - 1:
                        u = nj * self.nx + ni
                        if self.adj[u]:
                            d = math.hypot(ni * 5.0 - x, nj * 5.0 - y)
                            if d < best_d:
                                best_d = d
                                best_u = u
            if best_d < 1e8:
                return best_u
        return best_u

    def dijkstra(self, src_u: int, alpha_energy: float = 0.10) -> Tuple[List[float], List[float], List[int]]:
        n_tot = self.nx * self.ny
        INF = 1e9
        bc = [INF] * n_tot
        bt = [INF] * n_tot
        be = [INF] * n_tot
        parent = [-1] * n_tot
        bc[src_u] = bt[src_u] = be[src_u] = 0.0
        pq = [(0.0, src_u)]
        adj = self.adj
        while pq:
            c, u = heapq.heappop(pq)
            if c > bc[u] + 1e-9:
                continue
            ut, ue = bt[u], be[u]
            for v, dt, de in adj[u]:
                nc = c + dt + alpha_energy * de
                if nc < bc[v]:
                    bc[v] = nc
                    bt[v] = ut + dt
                    be[v] = ue + de
                    parent[v] = u
                    heapq.heappush(pq, (nc, v))
        return bt, be, parent

    def extract_smooth_waypoints(
        self, x0: float, y0: float, dst_x: float, dst_y: float, alpha_energy: float = 0.10
    ) -> Tuple[List[Tuple[float, float]], float, float]:
        """Shortest safe path from continuous (x0, y0) to (dst_x, dst_y), smoothed without sacrificing terrain cost."""
        # Check direct shortcut if short and optimal
        direct = self.segment_cost(x0, y0, dst_x, dst_y, self.last_slip, self.safe_clearance)
        if direct is not None and math.hypot(dst_x - x0, dst_y - y0) <= 18.0:
            return [(x0, y0), (dst_x, dst_y)], direct[0], direct[1]

        src_u = self.nearest_safe_node(x0, y0)
        dst_u = self.nearest_safe_node(dst_x, dst_y)
        bt, be, parent = self.dijkstra(src_u, alpha_energy=alpha_energy)
        if bt[dst_u] >= 1e8:
            return [(x0, y0), (dst_x, dst_y)], math.hypot(dst_x - x0, dst_y - y0) / 4.0, 20.0

        nodes = []
        cur = dst_u
        while cur != -1:
            nodes.append(cur)
            if cur == src_u:
                break
            cur = parent[cur]
        nodes.reverse()

        pts: List[Tuple[float, float]] = [(x0, y0)]
        for u in nodes[1:]:
            ui, uj = u % self.nx, u // self.nx
            pts.append((ui * 5.0, uj * 5.0))
        if math.hypot(pts[-1][0] - dst_x, pts[-1][1] - dst_y) > 0.5:
            pts.append((dst_x, dst_y))
        else:
            pts[-1] = (dst_x, dst_y)

        # Precompute cumulative cost along polyline
        m = len(pts)
        cum_cost = [0.0] * m
        cum_t = [0.0] * m
        cum_e = [0.0] * m
        for k in range(m - 1):
            sc = self.segment_cost(pts[k][0], pts[k][1], pts[k + 1][0], pts[k + 1][1], self.last_slip, 2.8)
            if sc is None:
                dt = math.hypot(pts[k + 1][0] - pts[k][0], pts[k + 1][1] - pts[k][1]) / 4.2
                de = dt * 2.0
            else:
                dt, de = sc
            cum_t[k + 1] = cum_t[k] + dt
            cum_e[k + 1] = cum_e[k] + de
            cum_cost[k + 1] = cum_cost[k] + dt + alpha_energy * de

        # Physics-preserving string pulling (eliminates grid discretization angles while keeping sand/rock detours)
        smooth: List[Tuple[float, float]] = [pts[0]]
        idx = 0
        while idx < m - 1:
            best_j = idx + 1
            for j in range(min(m - 1, idx + 6), idx + 1, -1):
                if math.hypot(pts[j][0] - pts[idx][0], pts[j][1] - pts[idx][1]) > 28.0:
                    continue
                sc = self.segment_cost(pts[idx][0], pts[idx][1], pts[j][0], pts[j][1], self.last_slip, self.safe_clearance + 0.2)
                if sc is not None:
                    direct_c = sc[0] + alpha_energy * sc[1]
                    sub_c = cum_cost[j] - cum_cost[idx]
                    if direct_c <= sub_c * 1.008 + 0.02:
                        best_j = j
                        break
            smooth.append(pts[best_j])
            idx = best_j

        return smooth, cum_t[-1], cum_e[-1]


class StateEstimator:
    """Joint solar-efficiency, terrain slip_base, and 300-particle state + heading-bias estimator."""

    def __init__(self, surf: Surface, rules: Dict[str, Any], n_particles: int = 300) -> None:
        self.surf = surf
        self.rules = rules
        self.n_p = n_particles
        self.rng = random.Random(20261115)

        bx, by = 300.0, 265.0
        self.px = [bx] * n_particles
        self.py = [by] * n_particles
        b_lim = rules["sensing"]["heading_bias_deg"]
        self.pb = [-b_lim + (2.0 * b_lim) * (i + 0.5) / n_particles for i in range(n_particles)]
        self.pw = [1.0 / n_particles] * n_particles

        self.last_obs_tick = 0
        self.last_obs_bat = float(rules["initial_battery"])
        self.last_obs_terrain = surf.terrain(bx, by)
        self.last_mean_xy = (bx, by)

        # Solar efficiency estimator
        self.eff_est = 0.87  # conservative until tick 5 packet arrives at tick 8
        self.eff_known = False
        self.eff_samples: List[float] = []

        # Slip base Kalman estimators per terrain
        self.mu_slip: Dict[str, float] = {}
        self.var_slip: Dict[str, float] = {}
        for tname, (lo, hi) in PHYSICS["slip_base_ranges"].items():
            self.mu_slip[tname] = 0.5 * (lo + hi)
            self.var_slip[tname] = ((hi - lo) ** 2) / 12.0
        self.slip_updates = 0

    def process_packet(
        self, pkt: Dict[str, Any], cmd_executed: Dict[str, Any]
    ) -> bool:
        """Process one newly arrived telemetry packet in chronological order. Returns True if safety stop detected."""
        t = int(pkt["tick"])
        if t <= self.last_obs_tick:
            if t == 0:
                bx, by = float(pkt["position"][0]), float(pkt["position"][1])
                self.px = [bx] * self.n_p
                self.py = [by] * self.n_p
                self.last_mean_xy = (bx, by)
                self.last_obs_bat = float(pkt["battery"])
                self.last_obs_terrain = str(pkt["terrain"])
            return False

        # 1. Solar efficiency exact check (uncapped whenever prev_bat + charge < 99.999)
        charge = float(pkt["charge"])
        cur_bat = float(pkt["battery"])
        if pkt["alive"] and (self.last_obs_bat + charge < 99.995):
            sin_v = 2.8 * math.sin(math.pi * (t + 56) / 532.0)
            if sin_v > 0.1:
                e_obs = max(0.8, min(1.0, charge / sin_v))
                self.eff_samples.append(e_obs)
                self.eff_est = sum(self.eff_samples) / len(self.eff_samples)
                self.eff_known = True

        obs_cmd_energy = max(0.0, (self.last_obs_bat + charge) - 0.15 - cur_bat)
        action = cmd_executed.get("action", "wait")
        wheel_odom = float(pkt["wheel_odometry"])
        vis_odom = float(pkt["visual_odometry"])
        obs_x, obs_y = float(pkt["position"][0]), float(pkt["position"][1])
        obs_ter = str(pkt["terrain"])
        obs_tilt = float(pkt["tilt"])

        safety_stop = False
        if action == "drive" and pkt["alive"]:
            cmd_m = float(cmd_executed.get("metres", 0.0))
            if wheel_odom < cmd_m - 1e-5:
                safety_stop = True

        # 2. Propagate & weight particles
        n_p = self.n_p
        log_w = [0.0] * n_p
        max_lw = -1e18
        cmd_h = float(cmd_executed.get("heading_deg", 0.0))

        for i in range(n_p):
            x_i, y_i, b_i = self.px[i], self.py[i], self.pb[i]
            res_ground = 0.0
            res_energy = 0.0
            res_stop = None
            if action == "drive" and wheel_odom > 1e-7:
                b_i = max(-12.0, min(12.0, b_i + self.rng.gauss(0.0, 0.2)))
                h_act = cmd_h + b_i + self.rng.gauss(0.0, 1.5)
                u_slip = self.rng.uniform(-0.02, 0.02)
                res = drive(self.surf, PHYSICS, x_i, y_i, h_act, wheel_odom, self.mu_slip, noise=u_slip)
                x_i, y_i = res["x"], res["y"]
                res_ground = res["ground"]
                res_energy = res["energy"]
                res_stop = res["stop"]
                self.px[i], self.py[i], self.pb[i] = x_i, y_i, b_i

            # Log-likelihood
            lw = math.log(max(1e-12, self.pw[i]))
            lw -= 0.5 * ((x_i - obs_x) ** 2 + (y_i - obs_y) ** 2) / 1.0  # position_noise_m = 1.0
            if action == "drive" and wheel_odom > 0.1:
                sig_vo = max(0.08, 0.055 * max(0.5, res_ground))
                lw -= 0.5 * ((vis_odom - res_ground) / sig_vo) ** 2
                lw -= 0.5 * ((res_energy - obs_cmd_energy) / 0.14) ** 2
                if not safety_stop and res_stop is not None:
                    lw -= 4.5

            _, gx, gy, code = self.surf.sample(x_i, y_i)
            if TERRAIN_CODES[code] != obs_ter:
                lw -= 1.6
            sl = math.hypot(gx, gy)
            lw -= 0.5 * ((sl - obs_tilt) / 0.028) ** 2

            log_w[i] = lw
            if lw > max_lw:
                max_lw = lw

        # Guard against extreme outlier collapse
        if max_lw < -22.0:
            mean_b = sum(self.pb) / n_p
            for i in range(n_p):
                if i % 5 == 0:
                    self.px[i] = max(0.5, min(599.5, obs_x + self.rng.gauss(0.0, 1.0)))
                    self.py[i] = max(0.5, min(399.5, obs_y + self.rng.gauss(0.0, 1.0)))
                    self.pb[i] = max(-8.0, min(8.0, mean_b + self.rng.gauss(0.0, 1.5)))
                    log_w[i] = max_lw

        w_sum = 0.0
        for i in range(n_p):
            wi = math.exp(max(-40.0, log_w[i] - max_lw))
            self.pw[i] = wi
            w_sum += wi
        for i in range(n_p):
            self.pw[i] /= w_sum

        # Effective sample size & systematic resampling
        ess = 1.0 / sum(w * w for w in self.pw)
        if ess < 0.55 * n_p:
            new_px = [0.0] * n_p
            new_py = [0.0] * n_p
            new_pb = [0.0] * n_p
            step = 1.0 / n_p
            r0 = self.rng.uniform(0.0, step)
            c = self.pw[0]
            j = 0
            sig_xy = 0.045 if (action == "drive" and wheel_odom > 0.1) else 0.015
            sig_b = 0.08 if (action == "drive" and wheel_odom > 0.1) else 0.02
            for i in range(n_p):
                u = r0 + i * step
                while u > c and j < n_p - 1:
                    j += 1
                    c += self.pw[j]
                nx_i = max(0.2, min(599.8, self.px[j] + self.rng.gauss(0.0, sig_xy)))
                ny_i = max(0.2, min(399.8, self.py[j] + self.rng.gauss(0.0, sig_xy)))
                nb_i = max(-12.0, min(12.0, self.pb[j] + self.rng.gauss(0.0, sig_b)))
                new_px[i], new_py[i], new_pb[i] = nx_i, ny_i, nb_i
            self.px, self.py, self.pb = new_px, new_py, new_pb
            self.pw = [1.0 / n_p] * n_p

        cur_mx = sum(w * x for w, x in zip(self.pw, self.px))
        cur_my = sum(w * y for w, y in zip(self.pw, self.py))

        # 3. Slip base recursive update on clean single-terrain drives
        if (
            action == "drive"
            and not safety_stop
            and wheel_odom >= 2.0
            and obs_ter == self.last_obs_terrain
        ):
            dx = cur_mx - self.last_mean_xy[0]
            dy = cur_my - self.last_mean_xy[1]
            disp = math.hypot(dx, dy)
            if disp > 0.4:
                ux, uy = dx / disp, dy / disp
                mid_x = 0.5 * (cur_mx + self.last_mean_xy[0])
                mid_y = 0.5 * (cur_my + self.last_mean_xy[1])
                _, gx, gy, _ = self.surf.sample(mid_x, mid_y)
                grade = gx * ux + gy * uy
                cross = -gx * uy + gy * ux
                side_c = PHYSICS["side_slip_gain"][obs_ter] * cross
                fwd_est = max(0.2, 1.0 - self.mu_slip[obs_ter])
                side_fac = math.hypot(1.0, side_c / fwd_est)
                ratio = (vis_odom / wheel_odom) / side_fac
                obs_sb = 1.0 - ratio - PHYSICS["slip_grade_gain"][obs_ter] * max(0.0, grade)
                lo, hi = PHYSICS["slip_base_ranges"][obs_ter]
                r_var = (0.055 * fwd_est) ** 2 + (0.02 ** 2) / 3.0 + (PHYSICS["slip_grade_gain"][obs_ter] * 0.015) ** 2
                v_prior = self.var_slip[obs_ter]
                k_gain = v_prior / (v_prior + r_var)
                self.mu_slip[obs_ter] = max(lo, min(hi, self.mu_slip[obs_ter] + k_gain * (obs_sb - self.mu_slip[obs_ter])))
                self.var_slip[obs_ter] = max(2e-5, (1.0 - k_gain) * v_prior)
                self.slip_updates += 1

        self.last_obs_tick = t
        self.last_obs_bat = cur_bat
        self.last_obs_terrain = obs_ter
        self.last_mean_xy = (cur_mx, cur_my)
        return safety_stop

    def predict_rollout(
        self, inflight_cmds: List[Tuple[int, Dict[str, Any]]], n_rep: int = 25
    ) -> Tuple[float, float, float, float, List[Tuple[float, float]]]:
        """
        Roll forward `n_rep` stratified particles from `last_obs_tick` through `inflight_cmds`.
        Returns (pred_x, pred_y, pred_bias, pred_battery_conservative, rep_xy_points).
        """
        # Pick n_rep particles using systematic sampling from current posterior
        idxs = []
        step = 1.0 / n_rep
        c = self.pw[0]
        j = 0
        for k in range(n_rep):
            u = (k + 0.5) * step
            while u > c and j < self.n_p - 1:
                j += 1
                c += self.pw[j]
            idxs.append(j)

        rx = [self.px[j] for j in idxs]
        ry = [self.py[j] for j in idxs]
        rb = [self.pb[j] for j in idxs]

        # Deterministic seed per call for smooth control + realistic spread
        mc_rng = random.Random(1337 + self.last_obs_tick * 31)
        bat_cons = self.last_obs_bat
        eff_cons = self.eff_est if self.eff_known else 0.80

        for tick_k, cmd in inflight_cmds:
            sin_v = 2.8 * math.sin(math.pi * (tick_k + 56) / 532.0)
            bat_cons = min(100.0, bat_cons + eff_cons * sin_v) - 0.15
            act = cmd.get("action", "wait")
            if act == "sample":
                bat_cons -= 2.0
            elif act == "drive":
                h_cmd = float(cmd["heading_deg"])
                m_cmd = float(cmd["metres"])
                e_sum = 0.0
                for k in range(n_rep):
                    if k == 0:
                        # Zero-noise nominal particle
                        h_act = h_cmd + rb[k]
                        u_s = 0.0
                    else:
                        rb[k] += mc_rng.gauss(0.0, 0.2)
                        h_act = h_cmd + rb[k] + mc_rng.gauss(0.0, 1.5)
                        u_s = mc_rng.uniform(-0.02, 0.02)
                    res = drive(self.surf, PHYSICS, rx[k], ry[k], h_act, m_cmd, self.mu_slip, noise=u_s)
                    rx[k], ry[k] = res["x"], res["y"]
                    e_sum += res["energy"]
                bat_cons -= (e_sum / n_rep) * 1.05

        pred_x = sum(rx) / n_rep
        pred_y = sum(ry) / n_rep
        pred_b = sum(w * b for w, b in zip(self.pw, self.pb))
        pts = list(zip(rx, ry))
        return pred_x, pred_y, pred_b, bat_cons, pts


class TourPlanner:
    """Orienteering with Time Windows & Battery Trajectory optimizer for initial & dynamic replanning."""

    def __init__(self, nav: TerrainNavGraph, base_xy: Tuple[float, float]) -> None:
        self.nav = nav
        self.base_xy = base_xy
        self.solar_sin = [0.0] + [2.8 * math.sin(math.pi * (t + 56) / 532.0) for t in range(1, 425)]
        # Cache POI pairwise (ticks, energy) for current graph & alpha
        self.poi_cache_alpha: float = -1.0
        self.poi_coords: Dict[str, Tuple[float, float]] = {"BASE": base_xy}
        self.pair_t: Dict[Tuple[str, str], float] = {}
        self.pair_e: Dict[Tuple[str, str], float] = {}

    def ensure_pairwise(self, targets: List[Dict[str, Any]], alpha: float, force: bool = False) -> None:
        if force or abs(alpha - self.poi_cache_alpha) > 0.03:
            self.pair_t.clear()
            self.pair_e.clear()
            self.poi_cache_alpha = alpha

        all_ids = ["BASE"] + [t["id"] for t in targets]
        for t in targets:
            self.poi_coords[t["id"]] = (float(t["x"]), float(t["y"]))

        node_of = {pid: self.nav.nearest_safe_node(*self.poi_coords[pid]) for pid in all_ids}
        for sid in all_ids:
            if all((sid, did) in self.pair_t for did in all_ids if sid != did):
                continue
            bt, be, _ = self.nav.dijkstra(node_of[sid], alpha_energy=alpha)
            sx, sy = self.poi_coords[sid]
            dx_start = math.hypot(sx - (node_of[sid] % self.nav.nx) * 5.0, sy - (node_of[sid] // self.nav.nx) * 5.0)
            for did in all_ids:
                if sid == did:
                    self.pair_t[(sid, did)] = 0.0
                    self.pair_e[(sid, did)] = 0.0
                else:
                    du = node_of[did]
                    nx_m, ny_m = (du % self.nav.nx) * 5.0, (du // self.nav.nx) * 5.0
                    dx_end = math.hypot(self.poi_coords[did][0] - nx_m, self.poi_coords[did][1] - ny_m)
                    extra_m = dx_start + dx_end
                    self.pair_t[(sid, did)] = bt[du] + extra_m / 4.3
                    self.pair_e[(sid, did)] = be[du] + extra_m * 0.45

    def plan(
        self,
        start_xy: Tuple[float, float],
        start_tick: int,
        start_bat: float,
        eff: float,
        unsampled_targets: List[Dict[str, Any]],
        current_route_ids: List[str],
        time_budget_s: float = 0.6,
        max_end_tick: int = 407,
        min_bat_floor: float = 9.5,
    ) -> List[str]:
        if not unsampled_targets:
            return []

        alpha = 0.22 if eff < 0.87 else (0.12 if eff < 0.93 else 0.06)
        self.ensure_pairwise(unsampled_targets, alpha=alpha)

        # Compute exact Dijkstra from rover's current predicted start_xy to all unsampled targets + BASE
        u_start = self.nav.nearest_safe_node(start_xy[0], start_xy[1])
        ux_grid, uy_grid = (u_start % self.nav.nx) * 5.0, (u_start // self.nav.nx) * 5.0
        d_snap = math.hypot(start_xy[0] - ux_grid, start_xy[1] - uy_grid)
        bt_s, be_s, _ = self.nav.dijkstra(u_start, alpha_energy=alpha)

        t_by_id = {t["id"]: t for t in unsampled_targets}
        cand_ids = [t["id"] for t in unsampled_targets]
        n_c = len(cand_ids)
        idx_map = {tid: i for i, tid in enumerate(cand_ids)}

        start_dt = [0.0] * n_c
        start_de = [0.0] * n_c
        ret_dt = [0.0] * n_c
        ret_de = [0.0] * n_c
        val_arr = [float(t_by_id[tid]["value"]) for tid in cand_ids]
        lval_arr = [float(t_by_id[tid]["late_value"]) for tid in cand_ids]
        dl_arr = [t_by_id[tid]["deadline_tick"] for tid in cand_ids]

        for i, tid in enumerate(cand_ids):
            tx, ty = float(t_by_id[tid]["x"]), float(t_by_id[tid]["y"])
            du = self.nav.nearest_safe_node(tx, ty)
            d_end = math.hypot(tx - (du % self.nav.nx) * 5.0, ty - (du // self.nav.nx) * 5.0)
            # Direct check if very close!
            if math.hypot(tx - start_xy[0], ty - start_xy[1]) <= 18.0:
                sc = self.nav.segment_cost(start_xy[0], start_xy[1], tx, ty, self.nav.last_slip, 3.0)
                if sc is not None:
                    start_dt[i], start_de[i] = sc[0], sc[1]
                else:
                    start_dt[i] = bt_s[du] + (d_snap + d_end) / 4.2
                    start_de[i] = be_s[du] + (d_snap + d_end) * 0.45
            else:
                start_dt[i] = bt_s[du] + (d_snap + d_end) / 4.2
                start_de[i] = be_s[du] + (d_snap + d_end) * 0.45
            ret_dt[i] = self.pair_t[(tid, "BASE")]
            ret_de[i] = self.pair_e[(tid, "BASE")]

        mat_t = [[0.0] * n_c for _ in range(n_c)]
        mat_e = [[0.0] * n_c for _ in range(n_c)]
        for i, ti in enumerate(cand_ids):
            for j, tj in enumerate(cand_ids):
                if i != j:
                    mat_t[i][j] = self.pair_t[(ti, tj)]
                    mat_e[i][j] = self.pair_e[(ti, tj)]

        solar_sin = self.solar_sin
        cum_solar = [0.0] * len(solar_sin)
        for t_i in range(1, len(solar_sin)):
            cum_solar[t_i] = cum_solar[t_i - 1] + eff * solar_sin[t_i] - 0.15

        def step_leg(tick: int, bat: float, min_b: float, n_ticks: int, ept: float, floor_b: float) -> Tuple[int, float, float]:
            if tick + n_ticks <= max_end_tick:
                # Fast path when battery clearly cannot hit 100 cap or floor_b during leg
                net_end = bat + (cum_solar[tick + n_ticks] - cum_solar[tick]) - n_ticks * ept
                worst_dip = bat - n_ticks * max(0.0, ept - (eff * 0.85 - 0.15))
                if worst_dip >= floor_b + 1.0 and bat + n_ticks * max(0.0, eff * 2.8 - 0.15 - ept) <= 99.5:
                    if net_end < min_b:
                        min_b = net_end
                    return tick + n_ticks, net_end, min_b
            for _ in range(n_ticks):
                while tick + 1 <= max_end_tick:
                    pb = min(100.0, bat + eff * solar_sin[tick + 1]) - 0.15 - ept
                    if pb >= floor_b:
                        break
                    tick += 1
                    bat = min(100.0, bat + eff * solar_sin[tick]) - 0.15
                    if tick >= max_end_tick:
                        return (-1, bat, min_b)
                tick += 1
                if tick > max_end_tick:
                    return (-1, bat, min_b)
                bat = min(100.0, bat + eff * solar_sin[tick]) - 0.15 - ept
                if bat < min_b:
                    min_b = bat
            return tick, bat, min_b

        def eval_seq(seq: List[int]) -> Tuple[float, int, float]:
            tick = start_tick
            bat = start_bat
            min_b = bat
            score = 0.0
            prev = -1
            for nxt in seq:
                raw_t = start_dt[nxt] if prev == -1 else mat_t[prev][nxt]
                raw_e = start_de[nxt] if prev == -1 else mat_e[prev][nxt]
                leg_ticks = max(1, int(math.ceil(max(0.2, raw_t - 0.05))))
                leg_e = max(0.3, raw_e - 0.2) * 1.03
                tick, bat, min_b = step_leg(tick, bat, min_b, leg_ticks, leg_e / leg_ticks, min_bat_floor)
                if tick < 0:
                    return (-1e9, max_end_tick + 1, min_b)
                tick, bat, min_b = step_leg(tick, bat, min_b, 1, 2.0, min_bat_floor)
                if tick < 0:
                    return (-1e9, max_end_tick + 1, min_b)
                dl = dl_arr[nxt]
                score += val_arr[nxt] if (dl is None or tick <= dl) else lval_arr[nxt]
                prev = nxt

            if prev == -1:
                u_b = self.nav.nearest_safe_node(*self.base_xy)
                rt_raw, re_raw = bt_s[u_b], be_s[u_b]
            else:
                rt_raw, re_raw = ret_dt[prev], ret_de[prev]
            ret_ticks = max(1, int(math.ceil(max(0.2, rt_raw - 0.35))))
            ret_e = max(0.3, re_raw - 0.6) * 1.04
            tick, bat, min_b = step_leg(tick, bat, min_b, ret_ticks, ret_e / ret_ticks, min_bat_floor - 1.5)
            if tick < 0:
                return (-1e9, max_end_tick + 1, min_b)
            return (score, tick, min_b)

        # Build diverse initial seeds:
        # Seed 0: current_route_ids (preserved for warm-start stability + inserting new discoveries!)
        seeds: List[List[int]] = []
        if current_route_ids:
            warm = [idx_map[tid] for tid in current_route_ids if tid in idx_map]
            seeds.append(warm)

        # Clockwise geographic skeleton (if targets present)
        cw_names = [
            "t32", "t33", "t34", "t12", "t25", "t28", "t1",
            "t4", "t13", "t8", "t17", "t14", "t36", "t27",
            "t22", "t35", "t20", "t10", "t15", "t26", "t16", "t18", "t9", "t19", "t7", "t3",
        ]
        seeds.append([idx_map[nm] for nm in cw_names if nm in idx_map])
        # Reverse / NW-first skeleton
        ccw_names = ["t7", "t19", "t29", "t9", "t16", "t26", "t15", "t20", "t35", "t22", "t10", "t18", "t27", "t36", "t14", "t1", "t28", "t25", "t12", "t34", "t32", "t3"]
        seeds.append([idx_map[nm] for nm in ccw_names if nm in idx_map])
        # NE + SE + SW skeleton
        ne_names = ["t32", "t11", "t23", "t31", "t38", "t6", "t13", "t8", "t17", "t4", "t14", "t36", "t27", "t1", "t28", "t25", "t12", "t34", "t3"]
        seeds.append([idx_map[nm] for nm in ne_names if nm in idx_map])

        rng = random.Random(42 + start_tick * 17)
        all_indices = list(range(n_c))

        best_seq: List[int] = []
        best_sc = 0.0
        best_tk = start_tick

        n_restarts = max(4, min(10, int(time_budget_s / 0.12) + 2))
        t_deadline = time.time() + time_budget_s

        for r_i in range(n_restarts):
            if time.time() >= t_deadline and best_seq:
                break
            cur_seq: List[int] = []
            if r_i < len(seeds) and seeds[r_i]:
                for x in seeds[r_i]:
                    if eval_seq(cur_seq + [x])[0] > -1e5:
                        cur_seq.append(x)
                # Also greedily try inserting any remaining targets (especially newly discovered targets!) into best position!
                in_s = set(cur_seq)
                rem = [x for x in all_indices if x not in in_s]
                rng.shuffle(rem)
                for x in rem:
                    b_pos = -1
                    b_val = eval_seq(cur_seq)[0]
                    for p in range(len(cur_seq) + 1):
                        sc_p, _, _ = eval_seq(cur_seq[:p] + [x] + cur_seq[p:])
                        if sc_p > b_val + 1e-6:
                            b_val = sc_p
                            b_pos = p
                    if b_pos != -1:
                        cur_seq.insert(b_pos, x)
            else:
                rem = all_indices[:]
                rng.shuffle(rem)
                for x in rem:
                    b_pos = -1
                    b_obj = -1e9
                    for p in range(len(cur_seq) + 1):
                        sc_p, tk_p, _ = eval_seq(cur_seq[:p] + [x] + cur_seq[p:])
                        if sc_p > -1e5 and (sc_p - 0.002 * tk_p) > b_obj:
                            b_obj = sc_p - 0.002 * tk_p
                            b_pos = p
                    if b_pos != -1:
                        cur_seq.insert(b_pos, x)

            cur_sc, cur_tk, _ = eval_seq(cur_seq)
            if cur_sc > best_sc or (cur_sc == best_sc and cur_tk < best_tk):
                best_sc, best_tk, best_seq = cur_sc, cur_tk, cur_seq[:]

            sub_end = min(t_deadline, time.time() + (t_deadline - time.time()) / max(1, n_restarts - r_i))
            sub_dur = max(0.01, sub_end - time.time())
            while time.time() < sub_end:
                frac = max(0.0, (sub_end - time.time()) / sub_dur)
                temp = 0.04 + 1.6 * frac
                cand = cur_seq[:]
                in_set = set(cand)
                out_list = [x for x in all_indices if x not in in_set]
                op = rng.random()
                if op < 0.32 and out_list:
                    x = rng.choice(out_list)
                    if rng.random() < 0.65:
                        best_p = 0
                        best_o = -1e18
                        for p in range(len(cand) + 1):
                            s, tk, _ = eval_seq(cand[:p] + [x] + cand[p:])
                            if s - 0.002 * tk > best_o:
                                best_o = s - 0.002 * tk
                                best_p = p
                        cand.insert(best_p, x)
                    else:
                        cand.insert(rng.randint(0, len(cand)), x)
                elif op < 0.50 and cand:
                    cand.pop(rng.randint(0, len(cand) - 1))
                elif op < 0.70 and cand and out_list:
                    pos = rng.randint(0, len(cand) - 1)
                    cand[pos] = rng.choice(out_list)
                elif op < 0.86 and len(cand) >= 2:
                    i = rng.randint(0, len(cand) - 1)
                    x = cand.pop(i)
                    cand.insert(rng.randint(0, len(cand)), x)
                elif len(cand) >= 2:
                    i, j = sorted(rng.sample(range(len(cand)), 2))
                    cand[i : j + 1] = reversed(cand[i : j + 1])

                sc, tk, _ = eval_seq(cand)
                if sc > -1e5:
                    # tiny bonus for preserving immediate next target if score equal (avoids unnecessary jitter)
                    bonus = 0.02 if (cand and current_route_ids and cand_ids[cand[0]] == current_route_ids[0]) else 0.0
                    obj_new = sc - 0.002 * tk + bonus
                    obj_old = cur_sc - 0.002 * cur_tk + (
                        0.02 if (cur_seq and current_route_ids and cand_ids[cur_seq[0]] == current_route_ids[0]) else 0.0
                    )
                    if obj_new >= obj_old or rng.random() < math.exp(min(10.0, (obj_new - obj_old) / temp)):
                        cur_seq, cur_sc, cur_tk = cand, sc, tk
                        if sc > best_sc or (sc == best_sc and tk < best_tk):
                            best_sc, best_tk, best_seq = sc, tk, cand[:]

        return [cand_ids[i] for i in best_seq]


class RoverAutopilot:
    """Full end-to-end Lightlag rover operator."""

    def __init__(self, rules: Dict[str, Any], initial_world: Dict[str, Any], verbose: bool = True) -> None:
        self.rules = rules
        self.verbose = verbose
        self.surf = Surface(initial_world["cell_m"], initial_world["elevation_cm"], initial_world["terrain"])
        self.base_xy = (float(initial_world["base"][0]), float(initial_world["base"][1]))
        self.max_ticks = int(rules["max_ticks"])
        self.delay_ticks = int(rules["delay_ticks"])

        self.nav = TerrainNavGraph(self.surf, safe_clearance=3.6)
        self.estimator = StateEstimator(self.surf, rules, n_particles=220)
        self.planner = TourPlanner(self.nav, self.base_xy)

        self.known_targets: Dict[str, Dict[str, Any]] = {t["id"]: t for t in initial_world["targets"]}
        self.confirmed_sampled: set[str] = set()
        self.pending_samples: Dict[str, int] = {}  # target_id -> execute_tick
        self.sample_attempts: Dict[str, int] = {}

        self.cmd_ledger: Dict[int, Dict[str, Any]] = {}
        self.last_reserved_tick = 0
        self.processed_up_to = -1

        self.route_ids: List[str] = []
        self.return_base_locked = False
        self.last_replan_tick = -999
        self.last_graph_rebuild_updates = 0
        self.cached_goal_xy: Tuple[float, float] = (-999.0, -999.0)
        self.cached_wp_tick: int = -999
        self.cached_wps: List[Tuple[float, float]] = []

    def get_waypoints_cached(self, pred_x: float, pred_y: float, goal_x: float, goal_y: float, current_tick: int, alpha_energy: float) -> List[Tuple[float, float]]:
        dist_goal = math.hypot(goal_x - pred_x, goal_y - pred_y)
        if dist_goal <= 16.0:
            sc = self.nav.segment_cost(pred_x, pred_y, goal_x, goal_y, self.estimator.mu_slip, 3.2)
            if sc is not None:
                return [(pred_x, pred_y), (goal_x, goal_y)]
        if (
            math.hypot(goal_x - self.cached_goal_xy[0], goal_y - self.cached_goal_xy[1]) > 0.8
            or current_tick - self.cached_wp_tick >= 6
            or len(self.cached_wps) < 2
        ):
            wps, _, _ = self.nav.extract_smooth_waypoints(pred_x, pred_y, goal_x, goal_y, alpha_energy=alpha_energy)
            self.cached_goal_xy = (goal_x, goal_y)
            self.cached_wp_tick = current_tick
            self.cached_wps = wps
            return wps
        # Trim already-passed waypoints on cached polyline
        wps = self.cached_wps
        while len(wps) > 2 and math.hypot(wps[1][0] - pred_x, wps[1][1] - pred_y) < 3.2:
            wps.pop(0)
        wps[0] = (pred_x, pred_y)
        return wps

    def log(self, msg: str) -> None:
        if self.verbose:
            print(msg, flush=True)

    def solve_drive_command(
        self,
        x0: float,
        y0: float,
        aim_x: float,
        aim_y: float,
        bias_deg: float,
        max_metres: float = 5.0,
    ) -> Dict[str, Any]:
        """Inverse shooting over exact `drive()` physics to cancel slip, cross-slope slide, and heading bias."""
        dx, dy = aim_x - x0, aim_y - y0
        dist = math.hypot(dx, dy)
        if dist < 0.12:
            return {"action": "wait"}

        target_deg = math.degrees(math.atan2(dy, dx))
        tname = self.surf.terrain(x0, y0)
        slip0 = max(0.02, min(0.80, self.estimator.mu_slip[tname]))
        m_cmd = min(max_metres, max(0.12, dist / (1.0 - slip0)))
        act_deg = target_deg

        for _ in range(4):
            res = drive(self.surf, PHYSICS, x0, y0, act_deg, m_cmd, self.estimator.mu_slip, noise=0.0)
            ach_dx, ach_dy = res["x"] - x0, res["y"] - y0
            ach_d = math.hypot(ach_dx, ach_dy)
            if ach_d > 1e-4:
                ach_deg = math.degrees(math.atan2(ach_dy, ach_dx))
                err_deg = angle_diff_deg(target_deg, ach_deg)
                act_deg += 0.9 * err_deg
                if dist < ach_d or m_cmd < max_metres - 1e-6:
                    m_cmd = min(max_metres, max(0.12, m_cmd * (dist / ach_d)))

        # Verify safety along nominal drive; if close to steep ground, scan safe heading fan
        res_nom = drive(self.surf, PHYSICS, x0, y0, act_deg, m_cmd, self.estimator.mu_slip, noise=0.0)
        if res_nom["stop"] is not None or self.nav.get_clearance(res_nom["x"], res_nom["y"]) < 2.2:
            best_act = act_deg
            best_m = m_cmd
            best_score = -1e9
            for d_ang in [0, -15, 15, -30, 30, -50, 50, -75, 75, -110, 110, 180]:
                cand_a = target_deg + d_ang
                for cand_m in [m_cmd, min(2.5, m_cmd)]:
                    r_c = drive(self.surf, PHYSICS, x0, y0, cand_a, cand_m, self.estimator.mu_slip, noise=0.0)
                    if r_c["stop"] is None:
                        clr = self.nav.get_clearance(r_c["x"], r_c["y"])
                        if clr >= 1.8:
                            sc = -math.hypot(aim_x - r_c["x"], aim_y - r_c["y"]) + 0.5 * min(4.0, clr)
                            if sc > best_score:
                                best_score = sc
                                best_act = cand_a
                                best_m = cand_m
            act_deg, m_cmd = best_act, best_m

        cmd_h = (act_deg - bias_deg) % 360.0
        return {"action": "drive", "heading_deg": round(cmd_h, 3), "metres": round(max(0.12, min(5.0, m_cmd)), 4)}

    def ingest_telemetry(self, packets: List[Dict[str, Any]], tools: Any) -> Tuple[bool, bool]:
        """Process new packets; returns (discovered_new_target, safety_or_miss_replan)."""
        discovered = False
        need_replan = False
        packets_sorted = sorted(packets, key=lambda p: int(p["tick"]))

        for pkt in packets_sorted:
            t = int(pkt["tick"])
            if t <= self.processed_up_to:
                continue
            cmd_exec = self.cmd_ledger.get(t, {"action": "wait"})
            was_eff_known = self.estimator.eff_known
            safety_stop = self.estimator.process_packet(pkt, cmd_exec)
            self.processed_up_to = t

            if not was_eff_known and self.estimator.eff_known:
                self.log(f"[t_obs={t}] Exact solar_efficiency learned: {self.estimator.eff_est:.6f}")
                need_replan = True

            if safety_stop:
                self.log(f"[t_obs={t}] SAFETY STOP detected (wheel={pkt['wheel_odometry']}); clearing inflight ledger <= {self.last_reserved_tick}")
                for tau in range(t + 1, self.last_reserved_tick + 1):
                    self.cmd_ledger[tau] = {"action": "wait"}
                self.pending_samples.clear()
                need_replan = True

            for sid in pkt.get("sampled_targets", []):
                self.confirmed_sampled.add(str(sid))

            # Check any pending samples that executed at or before t
            done_pending = [tid for tid, st in self.pending_samples.items() if st <= t]
            for tid in done_pending:
                del self.pending_samples[tid]
                if tid in self.confirmed_sampled:
                    t_obj = self.known_targets[tid]
                    dl = t_obj["deadline_tick"]
                    earned = t_obj["value"] if (dl is None or t <= dl) else t_obj["late_value"]
                    self.log(f"[t_obs={t}] CONFIRMED SAMPLE {tid} (+{earned}, dl={dl}) | bat={pkt['battery']:.1f}")
                else:
                    self.log(f"[t_obs={t}] MISSED SAMPLE {tid} at pos~({self.estimator.last_mean_xy[0]:.1f},{self.estimator.last_mean_xy[1]:.1f})! Triggering replan.")
                    need_replan = True

            if pkt.get("events"):
                self.log(f"[t_obs={t}] Events: {pkt['events']}")
                # Fetch updated map to pick up any discovered target cleanly
                w_now = tools.map()
                for t_obj in w_now.get("targets", []):
                    tid = t_obj["id"]
                    if tid not in self.known_targets:
                        self.known_targets[tid] = t_obj
                        discovered = True
                        self.log(
                            f"[t_obs={t}] NEW TARGET DISCOVERED: {tid} at ({t_obj['x']},{t_obj['y']}) "
                            f"val={t_obj['value']} dl={t_obj['deadline_tick']}"
                        )

        return discovered, need_replan

    def decide_next_command(self, current_tick: int) -> Optional[Dict[str, Any]]:
        next_exec_tick = max(current_tick + self.delay_ticks + 1, self.last_reserved_tick + 1)
        if next_exec_tick > self.max_ticks:
            return None

        # Rebuild graph edge weights ONCE after ~25 clean drives have refined terrain slip
        if self.last_graph_rebuild_updates == 0 and self.estimator.slip_updates >= 25:
            self.nav.rebuild_edges(self.estimator.mu_slip, self.base_xy)
            self.planner.ensure_pairwise(list(self.known_targets.values()), alpha=self.planner.poi_cache_alpha, force=True)
            self.last_graph_rebuild_updates = self.estimator.slip_updates

        # Roll forward from last_obs_tick through all already-queued commands up to next_exec_tick - 1
        inflight = [
            (tau, self.cmd_ledger.get(tau, {"action": "wait"}))
            for tau in range(self.estimator.last_obs_tick + 1, next_exec_tick)
        ]
        pred_x, pred_y, pred_b, pred_bat, rep_pts = self.estimator.predict_rollout(inflight, n_rep=25)

        # Active unsampled targets (excluding confirmed and optimistically in-flight samples)
        active_unsampled = [
            t_obj
            for tid, t_obj in self.known_targets.items()
            if tid not in self.confirmed_sampled
            and tid not in self.pending_samples
            and self.sample_attempts.get(tid, 0) < 2
        ]

        # Replan at t=0, on discovery/miss/eff learned, or periodically every 28 ticks
        if not self.return_base_locked and (
            current_tick == 0
            or (current_tick - self.last_replan_tick >= 28 and next_exec_tick < 395)
        ):
            budget = 1.4 if current_tick == 0 else 0.35
            # Prune route_ids to active unsampled
            active_set = {t["id"] for t in active_unsampled}
            cur_valid = [tid for tid in self.route_ids if tid in active_set]
            self.route_ids = self.planner.plan(
                start_xy=(pred_x, pred_y),
                start_tick=next_exec_tick - 1,
                start_bat=max(10.0, pred_bat),
                eff=self.estimator.eff_est,
                unsampled_targets=active_unsampled,
                current_route_ids=cur_valid,
                time_budget_s=budget,
                max_end_tick=408,
                min_bat_floor=9.0,
            )
            self.last_replan_tick = current_tick
            if current_tick == 0 or current_tick % 56 == 0:
                self.log(f"[tick={current_tick}->exec={next_exec_tick}] Planned route ({len(self.route_ids)}): {self.route_ids}")

        # Prune any already sampled / pending targets from head of route_ids
        while self.route_ids and (
            self.route_ids[0] in self.confirmed_sampled
            or self.route_ids[0] in self.pending_samples
            or self.sample_attempts.get(self.route_ids[0], 0) >= 2
        ):
            self.route_ids.pop(0)

        # Real-time Return-To-Base bailout guard (O(1) lookup, aligned with planner's max_end_tick=408 + 7-tick safety buffer!)
        alpha_now = 0.22 if self.estimator.eff_est < 0.87 else 0.08
        ret_ticks_est, ret_e_est = self.nav.fast_return_estimate(pred_x, pred_y)
        if not self.return_base_locked:
            if not self.route_ids:
                self.return_base_locked = True
                self.log(f"[tick={current_tick}] Route complete! Returning to BASE (est {ret_ticks_est:.1f} ticks).")
            elif next_exec_tick + int(math.ceil(ret_ticks_est * 1.04)) + 2 >= 416:
                self.return_base_locked = True
                self.route_ids.clear()
                self.log(f"[tick={current_tick}] Bailout guard triggered (exec={next_exec_tick}, ret={ret_ticks_est:.1f}t)! Locking RETURN_BASE.")

        sin_next = 2.8 * math.sin(math.pi * (next_exec_tick + 56) / 532.0)
        eff_cons = self.estimator.eff_est if self.estimator.eff_known else 0.80
        bat_after_idle = min(100.0, pred_bat + eff_cons * sin_next) - 0.15

        # Mode A: Returning to or holding at BASE
        if self.return_base_locked or not self.route_ids:
            bx, by = self.base_xy
            dist_base = math.hypot(bx - pred_x, by - pred_y)
            in_base_cnt = sum(1 for px, py in rep_pts if math.hypot(bx - px, by - py) <= 3.3)
            if dist_base <= 1.5 and in_base_cnt >= 23:
                return {"action": "wait"}
            # Navigate along safe smoothed path to exact base center
            wps = self.get_waypoints_cached(pred_x, pred_y, bx, by, current_tick, alpha_energy=alpha_now)
            aim_x, aim_y = wps[1] if len(wps) >= 2 else (bx, by)
            # Look ahead ~8m on smooth path if multi-segment so rover doesn't slow down prematurely at intermediate waypoints
            if len(wps) >= 3 and math.hypot(aim_x - pred_x, aim_y - pred_y) < 5.2:
                seg_dx, seg_dy = wps[2][0] - aim_x, wps[2][1] - aim_y
                seg_l = math.hypot(seg_dx, seg_dy)
                if seg_l > 1e-3:
                    rem_l = min(seg_l, 6.0 - math.hypot(aim_x - pred_x, aim_y - pred_y))
                    if self.nav.segment_cost(pred_x, pred_y, aim_x + seg_dx / seg_l * rem_l, aim_y + seg_dy / seg_l * rem_l, self.estimator.mu_slip, 3.0) is not None:
                        aim_x += seg_dx / seg_l * rem_l
                        aim_y += seg_dy / seg_l * rem_l

            cmd = self.solve_drive_command(pred_x, pred_y, aim_x, aim_y, pred_b, max_metres=5.0)
            if cmd["action"] == "drive":
                est_e = drive(self.surf, PHYSICS, pred_x, pred_y, (cmd["heading_deg"] + pred_b) % 360.0, cmd["metres"], self.estimator.mu_slip)["energy"]
                if bat_after_idle - est_e < 5.0:
                    return {"action": "wait"}
            return cmd

        # Mode B: Pursuing next target tid
        tid = self.route_ids[0]
        t_obj = self.known_targets[tid]
        tx, ty = float(t_obj["x"]), float(t_obj["y"])
        dist_t = math.hypot(tx - pred_x, ty - pred_y)
        in_rad_cnt = sum(1 for px, py in rep_pts if math.hypot(tx - px, ty - py) <= 2.35)

        # Check if ready to SAMPLE at next_exec_tick!
        if (in_rad_cnt >= 23 and dist_t <= 1.75) or (in_rad_cnt >= 24 and dist_t <= 1.95):
            if bat_after_idle - 2.0 < 5.5:
                return {"action": "wait"}
            self.pending_samples[tid] = next_exec_tick
            self.sample_attempts[tid] = self.sample_attempts.get(tid, 0) + 1
            return {"action": "sample"}

        # Otherwise drive toward optimal sample offset point (0.35m-0.45m from target center toward subsequent waypoint)
        nxt_xy = self.base_xy
        if len(self.route_ids) >= 2 and self.route_ids[1] in self.known_targets:
            t2 = self.known_targets[self.route_ids[1]]
            nxt_xy = (float(t2["x"]), float(t2["y"]))
        ndx, ndy = nxt_xy[0] - tx, nxt_xy[1] - ty
        nd = math.hypot(ndx, ndy)
        offset_r = 0.35 if float(t_obj["value"]) >= 3.0 else 0.45
        if nd > 1.0 and self.sample_attempts.get(tid, 0) == 0:
            goal_x = tx + offset_r * (ndx / nd)
            goal_y = ty + offset_r * (ndy / nd)
            if self.nav.get_clearance(goal_x, goal_y) < 3.5:
                goal_x, goal_y = tx, ty
        else:
            goal_x, goal_y = tx, ty

        wps = self.get_waypoints_cached(pred_x, pred_y, goal_x, goal_y, current_tick, alpha_energy=alpha_now)
        aim_x, aim_y = wps[1] if len(wps) >= 2 else (goal_x, goal_y)
        # Lookahead smoothing across intermediate waypoint so intermediate vertices always run full 5.0m wheel speed!
        if len(wps) >= 3 and math.hypot(aim_x - pred_x, aim_y - pred_y) < 5.2:
            seg_dx, seg_dy = wps[2][0] - aim_x, wps[2][1] - aim_y
            seg_l = math.hypot(seg_dx, seg_dy)
            if seg_l > 1e-3:
                rem_l = min(seg_l, 6.0 - math.hypot(aim_x - pred_x, aim_y - pred_y))
                cand_ax = aim_x + seg_dx / seg_l * rem_l
                cand_ay = aim_y + seg_dy / seg_l * rem_l
                if self.nav.segment_cost(pred_x, pred_y, cand_ax, cand_ay, self.estimator.mu_slip, 3.0) is not None:
                    aim_x, aim_y = cand_ax, cand_ay

        cmd = self.solve_drive_command(pred_x, pred_y, aim_x, aim_y, pred_b, max_metres=5.0)
        if cmd["action"] == "drive":
            est_e = drive(self.surf, PHYSICS, pred_x, pred_y, (cmd["heading_deg"] + pred_b) % 360.0, cmd["metres"], self.estimator.mu_slip)["energy"]
            # Respect planned battery floor (allow waiting when solar is recharging)
            bat_floor_now = 8.5 if next_exec_tick < 360 else 6.0
            if bat_after_idle - est_e < bat_floor_now:
                return {"action": "wait"}
        return cmd

    def run_episode(self, tools: Any) -> Dict[str, Any]:
        init_pkts = tools.telemetry_log()
        self.ingest_telemetry(init_pkts, tools)
        current_tick = max((int(p["tick"]) for p in init_pkts), default=0)

        episode_complete = False
        while not episode_complete and current_tick < self.max_ticks:
            cmd = self.decide_next_command(current_tick)
            if cmd is not None:
                try:
                    acks = tools.uplink([cmd])
                    exec_t = current_tick + self.delay_ticks + 1
                    if isinstance(acks, list) and acks:
                        first = acks[0]
                        if isinstance(first, dict) and "execute_tick" in first:
                            exec_t = int(first["execute_tick"])
                        elif isinstance(first, int):
                            exec_t = first
                    self.cmd_ledger[exec_t] = cmd
                    if exec_t > self.last_reserved_tick:
                        self.last_reserved_tick = exec_t
                except Exception as exc:
                    self.log(f"[tick={current_tick}] Uplink warning: {exc}")

            out = tools.advance(1)
            current_tick = int(out["current_tick"])
            episode_complete = bool(out.get("episode_complete", current_tick >= self.max_ticks))
            new_pkts = out.get("packets", [])
            if new_pkts:
                disc, need_replan = self.ingest_telemetry(new_pkts, tools)
                if (disc or need_replan) and not self.return_base_locked:
                    self.last_replan_tick = -999  # force immediate replan on next step!

        self.log(
            f"=== MISSION COMPLETE at tick={current_tick}: confirmed_samples={len(self.confirmed_sampled)} "
            f"({sorted(self.confirmed_sampled)}) ==="
        )
        return {
            "current_tick": current_tick,
            "confirmed_sampled": sorted(self.confirmed_sampled),
            "eff_est": self.estimator.eff_est,
            "mu_slip": dict(self.estimator.mu_slip),
        }
