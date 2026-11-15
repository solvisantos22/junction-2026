from __future__ import annotations

import heapq
import math
from typing import Any, Dict, List, Optional, Tuple

import lightlag_surface


def _wrap_deg(a: float) -> float:
    return (a + 180.0) % 360.0 - 180.0


class PlannerGrid:
    """Grid-based A* pathfinder over the surface cells."""

    def __init__(self, surface: lightlag_surface.Surface, rules: Dict[str, Any]) -> None:
        self.surface = surface
        self.rules = rules
        self.physics = rules["physics"]
        self.nx = surface.nx - 1
        self.ny = surface.ny - 1
        self.cell = surface.cell
        self.max_tilt = self.physics["max_tilt"]
        
        # Precompute cell properties for fast A*
        self.safe = [[False] * self.nx for _ in range(self.ny)]
        self.cost_mult = [[1.0] * self.nx for _ in range(self.ny)]
        self.elev = [[0.0] * self.nx for _ in range(self.ny)]
        
        # Safety margin against max_tilt to prevent accidental safety stops due to drift/noise
        safe_tilt = self.max_tilt - 0.035
        
        for j in range(self.ny):
            for i in range(self.nx):
                cx = (i + 0.5) * self.cell
                cy = (j + 0.5) * self.cell
                h, gx, gy, code = surface.sample(cx, cy)
                self.elev[j][i] = h
                ms = surface.cell_max_slope(i, j)
                if ms <= safe_tilt:
                    self.safe[j][i] = True
                
                # Weight by expected ticks per metre (1 / (1 - slip)) + energy factor
                t_name = lightlag_surface.TERRAIN_CODES[code]
                s_range = self.physics["slip_base_ranges"][t_name]
                s_base = 0.5 * (s_range[0] + s_range[1])
                # Penalize high slip and high energy terrains
                mult = 1.0 / max(0.2, 1.0 - s_base)
                if t_name == "sand":
                    mult *= 1.25
                elif t_name == "rocks":
                    mult *= 1.15
                if ms > safe_tilt - 0.04:
                    mult *= 1.4  # avoid hugging steep walls
                self.cost_mult[j][i] = mult

        self._dijkstra_cache: Dict[Tuple[int, int], Tuple[List[List[float]], List[List[Optional[Tuple[int, int]]]]]] = {}

    def cell_coords(self, x: float, y: float) -> Tuple[int, int]:
        i = min(self.nx - 1, max(0, int(x / self.cell)))
        j = min(self.ny - 1, max(0, int(y / self.cell)))
        return i, j

    def compute_dijkstra(self, start_x: float, start_y: float) -> Tuple[List[List[float]], List[List[Optional[Tuple[int, int]]]]]:
        si, sj = self.cell_coords(start_x, start_y)
        key = (si, sj)
        if key in self._dijkstra_cache:
            return self._dijkstra_cache[key]

        INF = 1e18
        dist = [[INF] * self.nx for _ in range(self.ny)]
        parent: List[List[Optional[Tuple[int, int]]]] = [[None] * self.nx for _ in range(self.ny)]
        
        dist[sj][si] = 0.0
        pq = [(0.0, si, sj)]
        
        # 8-connected neighbors
        neighbors = [
            (-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0),
            (-1, -1, 1.41421356), (1, -1, 1.41421356), (-1, 1, 1.41421356), (1, 1, 1.41421356)
        ]

        while pq:
            d, ui, uj = heapq.heappop(pq)
            if d > dist[uj][ui]:
                continue
            uh = self.elev[uj][ui]
            um = self.cost_mult[uj][ui]
            
            for di, dj, d_len in neighbors:
                vi, vj = ui + di, uj + dj
                if 0 <= vi < self.nx and 0 <= vj < self.ny:
                    if not self.safe[vj][vi] and (vi, vj) != (si, sj):
                        continue
                    # For diagonal moves, also check that at least one cardinal neighbor is safe
                    if di != 0 and dj != 0:
                        if not (self.safe[uj][vi] or self.safe[vj][ui]):
                            continue
                    
                    vh = self.elev[vj][vi]
                    dh = max(0.0, vh - uh)
                    step_m = d_len * self.cell
                    # Effective distance cost in metres (adjusted for slip & climb)
                    edge_cost = step_m * 0.5 * (um + self.cost_mult[vj][vi]) + dh * 3.5
                    nd = d + edge_cost
                    if nd < dist[vj][vi]:
                        dist[vj][vi] = nd
                        parent[vj][vi] = (ui, uj)
                        heapq.heappush(pq, (nd, vi, vj))

        self._dijkstra_cache[key] = (dist, parent)
        return dist, parent

    def get_distance_and_path(self, x1: float, y1: float, x2: float, y2: float) -> Tuple[float, List[Tuple[float, float]]]:
        dist, parent = self.compute_dijkstra(x1, y1)
        ti, tj = self.cell_coords(x2, y2)
        
        # If target cell is marked unsafe, find closest safe neighbor
        if dist[tj][ti] >= 1e17:
            best_d = 1e18
            best_cell = (ti, tj)
            for dj in range(-2, 3):
                for di in range(-2, 3):
                    ni, nj = ti + di, tj + dj
                    if 0 <= ni < self.nx and 0 <= nj < self.ny and dist[nj][ni] < best_d:
                        best_d = dist[nj][ni]
                        best_cell = (ni, nj)
            ti, tj = best_cell
            if best_d >= 1e17:
                return 1e9, [(x2, y2)]

        path_cells = []
        curr: Optional[Tuple[int, int]] = (ti, tj)
        while curr is not None:
            path_cells.append(curr)
            curr = parent[curr[1]][curr[0]]
        path_cells.reverse()

        waypoints = [( (i + 0.5) * self.cell, (j + 0.5) * self.cell ) for i, j in path_cells]
        if waypoints:
            waypoints[0] = (x1, y1)
            waypoints[-1] = (x2, y2)
        else:
            waypoints = [(x1, y1), (x2, y2)]

        # Smooth path by string-pulling where line of sight is completely safe
        smoothed = [waypoints[0]]
        idx = 0
        while idx < len(waypoints) - 1:
            next_idx = idx + 1
            for probe in range(min(len(waypoints) - 1, idx + 8), idx + 1, -1):
                if self._line_safe(waypoints[idx][0], waypoints[idx][1], waypoints[probe][0], waypoints[probe][1]):
                    next_idx = probe
                    break
            smoothed.append(waypoints[next_idx])
            idx = next_idx

        return dist[tj][ti], smoothed

    def _line_safe(self, x1: float, y1: float, x2: float, y2: float) -> bool:
        d = math.hypot(x2 - x1, y2 - y1)
        if d < 1e-6:
            return True
        steps = max(2, int(d / 1.0) + 1)
        safe_tilt = self.max_tilt - 0.045
        for s in range(1, steps + 1):
            t = s / steps
            x = x1 + (x2 - x1) * t
            y = y1 + (y2 - y1) * t
            if not self.surface.inside(x, y):
                return False
            if self.surface.slope(x, y) > safe_tilt:
                return False
            _, _, _, code = self.surface.sample(x, y)
            if code == "s":  # Do not shortcut across sand traps
                return False
        return True


class Estimator:
    """Tracks hidden environment parameters and rover state across light-lag."""

    def __init__(self, surface: lightlag_surface.Surface, rules: Dict[str, Any], init_pos: Tuple[float, float], init_bat: float) -> None:
        self.surface = surface
        self.rules = rules
        self.physics = rules["physics"]
        
        self.slip_base: Dict[str, float] = {}
        for k, r in self.physics["slip_base_ranges"].items():
            self.slip_base[k] = 0.5 * (r[0] + r[1])
            
        eff_r = rules["solar_efficiency_range"]
        self.solar_eff = 0.5 * (eff_r[0] + eff_r[1])
        
        self.heading_bias = 0.0
        self.pos_est = list(init_pos)
        self.last_processed_tick = 0
        
        # History of sent commands by execute_tick: tick -> command dict
        self.cmd_by_exec_tick: Dict[int, Dict[str, Any]] = {}
        # Predicted state before command at tick t
        self.pos_before_tick: Dict[int, Tuple[float, float]] = {0: init_pos}

    def solar_gain(self, tick: int) -> float:
        peak = self.rules["solar_peak"]
        margin = self.rules["sun_margin_ticks"]
        max_t = self.rules["max_ticks"]
        s = math.sin(math.pi * (tick + margin) / (max_t + 2 * margin))
        return max(0.0, peak * self.solar_eff * s)

    def update_from_telemetry(self, packets: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
        safety_stopped = False
        sampled = []
        
        for pkt in packets:
            t = pkt["tick"]
            if len(pkt.get("sampled_targets", [])) > 0:
                sampled = pkt["sampled_targets"]
            if t <= self.last_processed_tick:
                continue
            
            # 1. Update solar efficiency from exact charge reading
            charge = pkt.get("charge", 0.0)
            if charge > 0.01 and pkt.get("battery", 0.0) < self.rules["battery_capacity"] - 0.01:
                peak = self.rules["solar_peak"]
                margin = self.rules["sun_margin_ticks"]
                max_t = self.rules["max_ticks"]
                s = math.sin(math.pi * (t + margin) / (max_t + 2 * margin))
                if s > 0.05:
                    est_eff = charge / (peak * s)
                    eff_r = self.rules["solar_efficiency_range"]
                    est_eff = max(eff_r[0], min(eff_r[1], est_eff))
                    self.solar_eff = 0.7 * self.solar_eff + 0.3 * est_eff

            # Check for safety stop events or unexpected zero odometry on a drive tick
            cmd = self.cmd_by_exec_tick.get(t)
            wheel_odo = pkt.get("wheel_odometry", 0.0)
            vis_odo = pkt.get("visual_odometry", 0.0)
            events = pkt.get("events", [])
            
            for ev in events:
                if isinstance(ev, str) and ("stop" in ev.lower() or "tilt" in ev.lower() or "bound" in ev.lower()):
                    safety_stopped = True
                elif isinstance(ev, dict) and ev.get("type") in ("safety_stop", "stop", "tilt"):
                    safety_stopped = True

            if cmd and cmd["action"] == "drive":
                if wheel_odo < cmd["metres"] - 0.05:
                    safety_stopped = True

                # 2. Update slip_base estimate if full step on uniform terrain
                if wheel_odo > 1.0:
                    px, py = self.pos_est
                    _, gx, gy, code = self.surface.sample(px, py)
                    t_name = lightlag_surface.TERRAIN_CODES[code]
                    h_rad = math.radians(cmd["heading_deg"] + self.heading_bias)
                    grade = gx * math.cos(h_rad) + gy * math.sin(h_rad)
                    gain = self.physics["slip_grade_gain"][t_name]
                    obs_slip = 1.0 - (vis_odo / wheel_odo)
                    est_base = obs_slip - gain * max(0.0, grade)
                    s_range = self.physics["slip_base_ranges"][t_name]
                    est_base = max(s_range[0], min(s_range[1], est_base))
                    self.slip_base[t_name] = 0.85 * self.slip_base[t_name] + 0.15 * est_base

            # 3. Update position and heading bias filter
            prev_pos = tuple(self.pos_est)
            self.pos_before_tick[t] = prev_pos
            
            if cmd and cmd["action"] == "drive" and wheel_odo > 0.01:
                sim = lightlag_surface.drive(
                    self.surface, self.physics,
                    prev_pos[0], prev_pos[1],
                    cmd["heading_deg"] + self.heading_bias,
                    wheel_odo,
                    self.slip_base,
                    noise=0.0
                )
                pred_x, pred_y = sim["x"], sim["y"]
            else:
                pred_x, pred_y = prev_pos

            meas_x, meas_y = pkt["position"]
            
            # Estimate heading bias innovation if moved enough
            if cmd and cmd["action"] == "drive" and wheel_odo >= 2.0:
                dx_pred = pred_x - prev_pos[0]
                dy_pred = pred_y - prev_pos[1]
                dx_meas = meas_x - prev_pos[0]
                dy_meas = meas_y - prev_pos[1]
                dist_pred = math.hypot(dx_pred, dy_pred)
                dist_meas = math.hypot(dx_meas, dy_meas)
                if dist_pred > 1.5 and dist_meas > 1.5:
                    ang_pred = math.degrees(math.atan2(dy_pred, dx_pred))
                    ang_meas = math.degrees(math.atan2(dy_meas, dx_meas))
                    err = _wrap_deg(ang_meas - ang_pred)
                    if abs(err) < 25.0:
                        self.heading_bias += 0.08 * err
                        max_b = self.rules["sensing"]["heading_bias_deg"] * 2.5
                        self.heading_bias = max(-max_b, min(max_b, self.heading_bias))

            # Kalman-like blend of predicted position and noisy GPS measurement
            alpha = 0.35 if (cmd and cmd["action"] == "drive") else 0.25
            if safety_stopped:
                alpha = 0.65
            self.pos_est[0] = (1.0 - alpha) * pred_x + alpha * meas_x
            self.pos_est[1] = (1.0 - alpha) * pred_y + alpha * meas_y
            self.last_processed_tick = t

        if safety_stopped:
            # Clear pending commands that were wiped by the safety stop
            to_del = [k for k in self.cmd_by_exec_tick if k > self.last_processed_tick]
            for k in to_del:
                del self.cmd_by_exec_tick[k]

        return safety_stopped, sampled

    def predict_state_at(self, current_tick: int, latest_pkt: Dict[str, Any]) -> Tuple[float, float, float, int]:
        """Forward-simulate from last telemetry tick through all queued commands."""
        x, y = self.pos_est[0], self.pos_est[1]
        bat = latest_pkt["battery"]
        last_t = self.last_processed_tick
        
        max_queued_tick = max(self.cmd_by_exec_tick.keys(), default=last_t)
        horizon = max(last_t, max_queued_tick, current_tick + self.rules["delay_ticks"])
        
        for t in range(last_t + 1, horizon + 1):
            bat = min(self.rules["battery_capacity"], bat + self.solar_gain(t))
            bat -= self.rules["idle_cost"]
            cmd = self.cmd_by_exec_tick.get(t)
            if cmd:
                if cmd["action"] == "drive":
                    sim = lightlag_surface.drive(
                        self.surface, self.physics,
                        x, y,
                        cmd["heading_deg"] + self.heading_bias,
                        cmd["metres"],
                        self.slip_base,
                        noise=0.0
                    )
                    x, y = sim["x"], sim["y"]
                    bat -= sim["energy"]
                    if sim["stop"] is not None:
                        # A queued command will trigger a safety stop; clear subsequent commands in prediction
                        break
                elif cmd["action"] == "sample":
                    bat -= self.rules["sample_cost"]
                    
        next_free_tick = max(current_tick + self.rules["delay_ticks"] + 1, max_queued_tick + 1)
        return x, y, bat, next_free_tick


def select_best_target(
    planner: PlannerGrid,
    est: Estimator,
    pred_x: float,
    pred_y: float,
    pred_bat: float,
    next_tick: int,
    targets: List[Dict[str, Any]],
    sampled_ids: set,
    failed_counts: Dict[str, int],
    base_pos: Tuple[float, float],
    rules: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    max_ticks = rules["max_ticks"]
    bx, by = base_pos
    
    # Average ground speed is roughly 3.8 m/tick; use conservative 3.3 m/tick for return margin
    SAFE_SPEED = 3.35
    RETURN_BUFFER_TICKS = 16
    
    candidates = []
    for tgt in targets:
        tid = tgt["id"]
        if tid in sampled_ids:
            continue
        if failed_counts.get(tid, 0) >= 2:
            continue
        candidates.append(tgt)
        
    if not candidates:
        return None

    # Evaluate 1-step and 2-step lookahead for candidate targets
    best_target = None
    best_score = -1e9

    # Pre-calculate distances from current position and to base
    cand_info = []
    for tgt in candidates:
        tx, ty = tgt["x"], tgt["y"]
        d_to_t, _ = planner.get_distance_and_path(pred_x, pred_y, tx, ty)
        d_t_to_base, _ = planner.get_distance_and_path(tx, ty, bx, by)
        if d_to_t > 1e8 or d_t_to_base > 1e8:
            continue
        cand_info.append((tgt, d_to_t, d_t_to_base))

    # Sort by rough distance/value to keep 2-step lookahead fast
    cand_info.sort(key=lambda item: item[1] / max(1.0, item[0]["value"]))
    top_cands = cand_info[:18]

    for tgt1, d1, d1_base in top_cands:
        t1_ticks = math.ceil(d1 / 3.7) + 2  # +1 approach +1 sample
        arr1_tick = next_tick + t1_ticks
        ret1_ticks = math.ceil(d1_base / SAFE_SPEED) + RETURN_BUFFER_TICKS
        
        if arr1_tick + ret1_ticks > max_ticks:
            continue

        dl1 = tgt1["deadline_tick"]
        val1 = tgt1["value"] if (dl1 is None or arr1_tick <= dl1) else tgt1["late_value"]
        
        # Urgency bonus if deadline is soon and reachable on time
        urgency1 = 0.0
        if dl1 is not None and arr1_tick <= dl1:
            slack = dl1 - arr1_tick
            if slack < 45:
                urgency1 = (tgt1["value"] - tgt1["late_value"]) * 0.35 * (1.0 - slack / 45.0)

        rate1 = (val1 + urgency1) / max(4.0, float(t1_ticks))
        best_2step_rate = rate1

        # 2-step lookahead
        for tgt2, _, d2_base in top_cands[:12]:
            if tgt2["id"] == tgt1["id"]:
                continue
            d12, _ = planner.get_distance_and_path(tgt1["x"], tgt1["y"], tgt2["x"], tgt2["y"])
            if d12 > 1e8:
                continue
            t2_ticks = math.ceil(d12 / 3.7) + 2
            arr2_tick = arr1_tick + t2_ticks
            ret2_ticks = math.ceil(d2_base / SAFE_SPEED) + RETURN_BUFFER_TICKS
            if arr2_tick + ret2_ticks > max_ticks:
                continue
            dl2 = tgt2["deadline_tick"]
            val2 = tgt2["value"] if (dl2 is None or arr2_tick <= dl2) else tgt2["late_value"]
            rate12 = (val1 + urgency1 + val2) / max(6.0, float(t1_ticks + t2_ticks))
            if rate12 > best_2step_rate:
                best_2step_rate = rate12

        score = 0.45 * rate1 + 0.55 * best_2step_rate
        if score > best_score:
            best_score = score
            best_target = tgt1

    return best_target


def choose_safe_drive(
    surface: lightlag_surface.Surface,
    physics: Dict[str, Any],
    est: Estimator,
    x: float,
    y: float,
    goal_x: float,
    goal_y: float,
    desired_dist: float
) -> Optional[Dict[str, Any]]:
    """Finds a drive command towards (goal_x, goal_y) that compensates for slip/side-slip and avoids steep tilts."""
    dx = goal_x - x
    dy = goal_y - y
    direct_dist = math.hypot(dx, dy)
    if direct_dist < 1e-4:
        return None
        
    base_heading = math.degrees(math.atan2(dy, dx))
    max_m = 5.0
    
    # Estimate wheel metres needed to cover desired_dist
    _, gx, gy, code = surface.sample(x, y)
    t_name = lightlag_surface.TERRAIN_CODES[code]
    h_rad = math.radians(base_heading)
    grade = gx * math.cos(h_rad) + gy * math.sin(h_rad)
    slip_est = est.slip_base[t_name] + physics["slip_grade_gain"][t_name] * max(0.0, grade)
    slip_est = max(0.0, min(0.85, slip_est))
    
    wheel_m = min(max_m, max(0.25, desired_dist / max(0.2, 1.0 - slip_est)))
    
    # Candidate heading offsets to test (fine grid near 0, wider grid for obstacle avoidance)
    offsets = [0.0, -3.0, 3.0, -6.0, 6.0, -10.0, 10.0, -15.0, 15.0, -25.0, 25.0, -40.0, 40.0, -60.0, 60.0, -85.0, 85.0, -115.0, 115.0]
    
    best_cmd = None
    best_cost = 1e18
    safe_tilt = physics["max_tilt"] - 0.032

    for m_try in ([wheel_m, min(max_m, wheel_m * 0.6), 1.5] if wheel_m > 1.5 else [wheel_m, 0.5]):
        if m_try < 0.15:
            continue
        for off in offsets:
            cmd_h = (base_heading + off - est.heading_bias) % 360.0
            
            # Check worst-case heading perturbations (+-4 deg) to guarantee no tilt safety stop
            safe_all = True
            max_s_seen = 0.0
            sim_nom = None
            
            for h_err in (0.0, -4.5, 4.5):
                actual_h = (cmd_h + est.heading_bias + h_err) % 360.0
                sim = lightlag_surface.drive(
                    surface, physics, x, y, actual_h, m_try, est.slip_base, noise=0.0
                )
                if sim["stop"] is not None:
                    safe_all = False
                    break
                end_slope = surface.slope(sim["x"], sim["y"])
                if end_slope > safe_tilt:
                    safe_all = False
                    break
                if h_err == 0.0:
                    sim_nom = sim
                    max_s_seen = end_slope
                    
            if not safe_all or sim_nom is None:
                continue
                
            rem_d = math.hypot(goal_x - sim_nom["x"], goal_y - sim_nom["y"])
            # Cost: remaining distance to waypoint + slight penalty for high slope or energy
            cost = rem_d + 0.08 * sim_nom["energy"] + (8.0 * max(0.0, max_s_seen - (safe_tilt - 0.04)))
            if cost < best_cost:
                best_cost = cost
                best_cmd = {
                    "action": "drive",
                    "heading_deg": round(cmd_h, 3),
                    "metres": round(m_try, 3)
                }
        if best_cmd is not None and best_cost < direct_dist:
            break

    # Fallback if tight margin rejected everything: relax tilt margin slightly
    if best_cmd is None:
        for off in range(0, 360, 15):
            cmd_h = (base_heading + off - est.heading_bias) % 360.0
            sim = lightlag_surface.drive(
                surface, physics, x, y, (cmd_h + est.heading_bias) % 360.0, min(2.0, wheel_m), est.slip_base, noise=0.0
            )
            if sim["stop"] is None and surface.slope(sim["x"], sim["y"]) < physics["max_tilt"] - 0.012:
                rem_d = math.hypot(goal_x - sim["x"], goal_y - sim["y"])
                if rem_d < best_cost:
                    best_cost = rem_d
                    best_cmd = {
                        "action": "drive",
                        "heading_deg": round(cmd_h, 3),
                        "metres": round(min(2.0, wheel_m), 3)
                    }
                    
    return best_cmd


def play(tools: Any) -> None:
    rules = tools.rules()
    map_data = tools.map()
    
    surface = lightlag_surface.Surface(
        map_data["cell_m"],
        map_data["elevation_cm"],
        map_data["terrain"]
    )
    planner = PlannerGrid(surface, rules)
    
    base_pos: Tuple[float, float] = (float(map_data["base"][0]), float(map_data["base"][1]))
    init_log = tools.telemetry_log()
    init_pkt = init_log[-1]
    
    est = Estimator(surface, rules, (init_pkt["position"][0], init_pkt["position"][1]), init_pkt["battery"])
    
    sampled_ids: set = set(init_pkt.get("sampled_targets", []))
    failed_counts: Dict[str, int] = {}
    sample_attempted_ticks: Dict[str, int] = {}
    
    current_tick = 0
    max_ticks = rules["max_ticks"]
    delay_ticks = rules["delay_ticks"]
    target_radius = rules["target_radius"]
    base_radius = rules["base_radius"]
    
    active_target_id: Optional[str] = None
    returning_to_base = False
    known_target_count = len(map_data["targets"])

    while current_tick < max_ticks:
        log = tools.telemetry_log()
        latest_pkt = log[-1]
        
        # Process any newly arrived telemetry packets
        new_pkts = [p for p in log if p["tick"] > est.last_processed_tick]
        safety_stopped, newly_sampled = est.update_from_telemetry(new_pkts)
        for tid in newly_sampled:
            sampled_ids.add(tid)
            if active_target_id == tid:
                active_target_id = None

        # Check if any packet announced a target discovery
        discovered = False
        for p in new_pkts:
            for ev in p.get("events", []):
                if (isinstance(ev, str) and "discover" in ev) or (isinstance(ev, dict) and "discover" in str(ev.get("type", ""))):
                    discovered = True
        if discovered or current_tick % 10 == 0:
            map_data = tools.map()
            if len(map_data["targets"]) > known_target_count:
                known_target_count = len(map_data["targets"])
                # Re-evaluate active target if a new discovery appeared
                active_target_id = None

        # Check if a previously attempted sample failed to collect its target
        for tid, exec_t in list(sample_attempted_ticks.items()):
            if est.last_processed_tick >= exec_t:
                del sample_attempted_ticks[tid]
                if tid not in sampled_ids:
                    failed_counts[tid] = failed_counts.get(tid, 0) + 1
                    if active_target_id == tid:
                        active_target_id = None

        pred_x, pred_y, pred_bat, next_free_tick = est.predict_state_at(current_tick, latest_pkt)
        
        if next_free_tick > max_ticks:
            res = tools.advance(min(5, max_ticks - current_tick))
            current_tick = res["current_tick"]
            if res["episode_complete"]:
                break
            continue

        # Keep queue short (only 1 or 2 commands ahead of execution horizon) to stay responsive to noisy telemetry
        queued_ahead = next_free_tick - (current_tick + delay_ticks + 1)
        if queued_ahead >= 2:
            res = tools.advance(1)
            current_tick = res["current_tick"]
            if res["episode_complete"]:
                break
            continue

        # Check return-to-base requirement
        dist_to_base, base_path = planner.get_distance_and_path(pred_x, pred_y, base_pos[0], base_pos[1])
        euclid_to_base = math.hypot(pred_x - base_pos[0], pred_y - base_pos[1])
        
        # Conservative return ticks calculation
        ticks_needed_for_base = math.ceil(dist_to_base / 3.3) + 15
        if next_free_tick + ticks_needed_for_base >= max_ticks:
            returning_to_base = True

        # Select or validate target
        targets = map_data["targets"]
        target_by_id = {t["id"]: t for t in targets}
        
        if not returning_to_base:
            # Always re-verify active target can still beat return deadline
            if active_target_id is not None:
                if active_target_id in sampled_ids or failed_counts.get(active_target_id, 0) >= 2:
                    active_target_id = None
                else:
                    t_obj = target_by_id[active_target_id]
                    d_t, _ = planner.get_distance_and_path(pred_x, pred_y, t_obj["x"], t_obj["y"])
                    d_b, _ = planner.get_distance_and_path(t_obj["x"], t_obj["y"], base_pos[0], base_pos[1])
                    if next_free_tick + math.ceil(d_t / 3.5) + 2 + math.ceil(d_b / 3.35) + 14 > max_ticks:
                        active_target_id = None

            if active_target_id is None:
                chosen = select_best_target(
                    planner, est, pred_x, pred_y, pred_bat, next_free_tick,
                    targets, sampled_ids, failed_counts, base_pos, rules
                )
                if chosen is not None:
                    active_target_id = chosen["id"]
                else:
                    returning_to_base = True

        # Determine next command to uplink
        cmd_to_send: Optional[Dict[str, Any]] = None

        if returning_to_base:
            if euclid_to_base <= base_radius * 0.45:
                cmd_to_send = {"action": "wait"}
            else:
                # Navigate towards base
                wp_x, wp_y = base_path[1] if len(base_path) > 1 else base_pos
                if euclid_to_base <= 12.0 and planner._line_safe(pred_x, pred_y, base_pos[0], base_pos[1]):
                    wp_x, wp_y = base_pos
                
                # Reserve battery for final steps
                if pred_bat < 8.0 and next_free_tick + math.ceil(dist_to_base / 3.2) + 8 < max_ticks:
                    cmd_to_send = {"action": "wait"}
                else:
                    cmd_to_send = choose_safe_drive(
                        surface, rules["physics"], est,
                        pred_x, pred_y, wp_x, wp_y,
                        min(5.0, euclid_to_base if (wp_x, wp_y) == base_pos else math.hypot(wp_x - pred_x, wp_y - pred_y))
                    )
                    if cmd_to_send is None:
                        cmd_to_send = {"action": "wait"}
        else:
            t_obj = target_by_id[active_target_id]
            tx, ty = t_obj["x"], t_obj["y"]
            dist_euclid = math.hypot(tx - pred_x, ty - pred_y)
            
            # Opportunistic check: are we already inside another unsampled target's radius?
            opp_id = None
            for other in targets:
                oid = other["id"]
                if oid not in sampled_ids and oid not in sample_attempted_ticks and failed_counts.get(oid, 0) < 2:
                    if math.hypot(other["x"] - pred_x, other["y"] - pred_y) <= target_radius * 0.58:
                        opp_id = oid
                        break

            # Only sample when confident we are well inside target_radius (<= 1.45 m, vs 2.5 m radius)
            sample_thresh = 1.40 if failed_counts.get(active_target_id, 0) == 0 else 1.05
            
            if opp_id is not None and pred_bat > 6.0:
                cmd_to_send = {"action": "sample"}
                sample_attempted_ticks[opp_id] = next_free_tick
            elif dist_euclid <= sample_thresh and active_target_id not in sample_attempted_ticks:
                if pred_bat < 5.0:
                    cmd_to_send = {"action": "wait"}
                else:
                    cmd_to_send = {"action": "sample"}
                    sample_attempted_ticks[active_target_id] = next_free_tick
            else:
                # Battery conservation check before driving
                min_bat = 14.0 if next_free_tick < 320 else 9.0
                if pred_bat < min_bat:
                    cmd_to_send = {"action": "wait"}
                else:
                    _, t_path = planner.get_distance_and_path(pred_x, pred_y, tx, ty)
                    wp_x, wp_y = t_path[1] if len(t_path) > 1 else (tx, ty)
                    if dist_euclid <= 12.0 and planner._line_safe(pred_x, pred_y, tx, ty):
                        wp_x, wp_y = tx, ty
                    
                    step_goal_dist = math.hypot(wp_x - pred_x, wp_y - pred_y)
                    cmd_to_send = choose_safe_drive(
                        surface, rules["physics"], est,
                        pred_x, pred_y, wp_x, wp_y,
                        step_goal_dist
                    )
                    if cmd_to_send is None:
                        # Target unreachable safely; mark failed and pick another
                        failed_counts[active_target_id] = failed_counts.get(active_target_id, 0) + 2
                        active_target_id = None
                        cmd_to_send = {"action": "wait"}

        if cmd_to_send is not None:
            try:
                acks = tools.uplink([cmd_to_send])
                for ack in acks:
                    est.cmd_by_exec_tick[ack["execute_tick"]] = ack["command"]
                    if cmd_to_send["action"] == "sample":
                        for tid in list(sample_attempted_ticks.keys()):
                            if sample_attempted_ticks[tid] == next_free_tick:
                                sample_attempted_ticks[tid] = ack["execute_tick"]
            except ValueError:
                pass

        res = tools.advance(1)
        current_tick = res["current_tick"]
        if res["episode_complete"]:
            break
