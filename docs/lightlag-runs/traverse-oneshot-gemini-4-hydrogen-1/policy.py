import heapq
import math
import lightlag_surface


def play(tools):
    rules = tools.rules()
    world_map = tools.map()
    log = tools.telemetry_log()
    init_pkt = log[0]

    max_ticks = rules["max_ticks"]
    delay_ticks = rules["delay_ticks"]
    base_x, base_y = world_map["base"]
    target_radius = rules["target_radius"]
    base_radius = rules["base_radius"]
    max_tilt = rules["physics"]["max_tilt"]
    physics = rules["physics"]

    surface = lightlag_surface.Surface(
        world_map["cell_m"], world_map["elevation_cm"], world_map["terrain"]
    )
    cell_m = surface.cell
    nx_cells = surface.nx - 1
    ny_cells = surface.ny - 1

    # Midpoint estimates for hidden slip_base
    slip_base_est = {
        k: 0.5 * (v[0] + v[1]) for k, v in physics["slip_base_ranges"].items()
    }
    solar_eff_est = 0.5 * (
        rules["solar_efficiency_range"][0] + rules["solar_efficiency_range"][1]
    )

    # Precompute passable cells with a safety margin on max_tilt
    safe_tilt = max_tilt * 0.90
    passable = [[True] * nx_cells for _ in range(ny_cells)]
    for j in range(ny_cells):
        for i in range(nx_cells):
            if surface.cell_max_slope(i, j) > safe_tilt:
                passable[j][i] = False

    # Add small penalty for cells adjacent to impassable cells
    near_cliff = [[False] * nx_cells for _ in range(ny_cells)]
    for j in range(ny_cells):
        for i in range(nx_cells):
            if not passable[j][i]:
                continue
            for dj in (-1, 0, 1):
                for di in (-1, 0, 1):
                    ni, nj = i + di, j + dj
                    if 0 <= ni < nx_cells and 0 <= nj < ny_cells:
                        if not passable[nj][ni]:
                            near_cliff[j][i] = True
                            break
                if near_cliff[j][i]:
                    break

    def pos_to_cell(x, y):
        i = min(nx_cells - 1, max(0, int(x / cell_m)))
        j = min(ny_cells - 1, max(0, int(y / cell_m)))
        return i, j

    def cell_to_pos(i, j):
        return (i + 0.5) * cell_m, (j + 0.5) * cell_m

    def find_nearest_passable(i, j):
        if passable[j][i]:
            return i, j
        best = None
        best_d = 1e9
        for r in range(1, 6):
            for dj in range(-r, r + 1):
                for di in range(-r, r + 1):
                    ni, nj = i + di, j + dj
                    if 0 <= ni < nx_cells and 0 <= nj < ny_cells and passable[nj][ni]:
                        d = di * di + dj * dj
                        if d < best_d:
                            best_d = d
                            best = (ni, nj)
            if best is not None:
                return best
        return i, j

    def astar(start_pos, goal_pos):
        si, sj = find_nearest_passable(*pos_to_cell(*start_pos))
        gi, gj = find_nearest_passable(*pos_to_cell(*goal_pos))
        if (si, sj) == (gi, gj):
            return [goal_pos], 1.0, 1.0

        pq = [(0.0, si, sj)]
        g_cost = {(si, sj): 0.0}
        g_ticks = {(si, sj): 0.0}
        g_energy = {(si, sj): 0.0}
        parent = {}

        dirs = [
            (1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
            (1, 1, 1.4142), (1, -1, 1.4142), (-1, 1, 1.4142), (-1, -1, 1.4142),
        ]
        gain = physics["slip_grade_gain"]
        cost_m = physics["drive_cost_per_wheel_m"]
        climb_m = physics["climb_cost_per_m"]

        while pq:
            _, ci, cj = heapq.heappop(pq)
            if (ci, cj) == (gi, gj):
                path = []
                cur = (gi, gj)
                while cur in parent:
                    path.append(cell_to_pos(*cur))
                    cur = parent[cur]
                path.reverse()
                if path:
                    path[-1] = goal_pos
                else:
                    path = [goal_pos]
                return path, g_ticks[(gi, gj)], g_energy[(gi, gj)]

            cx, cy = cell_to_pos(ci, cj)
            ch = surface.elevation(cx, cy)
            cur_g = g_cost[(ci, cj)]
            cur_t = g_ticks[(ci, cj)]
            cur_e = g_energy[(ci, cj)]

            for di, dj, d_mult in dirs:
                ni, nj = ci + di, cj + dj
                if not (0 <= ni < nx_cells and 0 <= nj < ny_cells):
                    continue
                if not passable[nj][ni]:
                    continue
                nx_pos, ny_pos = cell_to_pos(ni, nj)
                nh = surface.elevation(nx_pos, ny_pos)
                dist = cell_m * d_mult
                dh = nh - ch
                grade = dh / dist
                t_name = lightlag_surface.TERRAIN_CODES[surface.codes[nj][ni]]
                slip = min(0.85, slip_base_est[t_name] + gain[t_name] * max(0.0, grade))
                speed = 5.0 * max(0.15, 1.0 - slip)
                step_ticks = dist / speed
                step_energy = dist * cost_m[t_name] + climb_m * max(0.0, dh)
                cliff_pen = 0.6 if near_cliff[nj][ni] else 0.0
                new_g = cur_g + step_ticks + 0.04 * step_energy + cliff_pen

                if new_g < g_cost.get((ni, nj), 1e18):
                    g_cost[(ni, nj)] = new_g
                    g_ticks[(ni, nj)] = cur_t + step_ticks
                    g_energy[(ni, nj)] = cur_e + step_energy
                    parent[(ni, nj)] = (ci, cj)
                    h_est = math.hypot(gi - ni, gj - nj) * cell_m / 5.0
                    heapq.heappush(pq, (new_g + h_est, ni, nj))

        # Fallback direct
        d = math.hypot(goal_pos[0] - start_pos[0], goal_pos[1] - start_pos[1])
        return [goal_pos], d / 3.5, d * 0.5

    # State tracking
    est_x, est_y = init_pkt["position"]
    est_bias_deg = 0.0
    est_battery = init_pkt["battery"]
    last_telem_tick = 0
    last_telem_pos = (est_x, est_y)
    alive = True

    # Command queue: list of (execute_tick, cmd_dict)
    cmd_queue = []
    sampled_ids = set(init_pkt["sampled_targets"])
    known_targets = {t["id"]: t for t in world_map["targets"]}

    def solar_gain_at(tick, eff):
        return (
            rules["solar_peak"]
            * eff
            * math.sin(
                math.pi
                * (tick + rules["sun_margin_ticks"])
                / (max_ticks + 2 * rules["sun_margin_ticks"])
            )
        )

    def process_packets(packets):
        nonlocal est_x, est_y, est_bias_deg, est_battery, last_telem_tick, last_telem_pos, alive, solar_eff_est
        for pkt in packets:
            t = pkt["tick"]
            if not pkt["alive"]:
                alive = False
            for sid in pkt["sampled_targets"]:
                sampled_ids.add(sid)
            for ev in pkt.get("events", []):
                if ev.get("type") == "target_discovered" or "target" in ev:
                    # Refresh map to get newly discovered targets
                    m = tools.map()
                    for tgt in m["targets"]:
                        known_targets[tgt["id"]] = tgt

            # Update solar efficiency estimate if battery < 100
            if pkt["charge"] > 0 and pkt["battery"] < rules["battery_capacity"] - 1e-6:
                denom = solar_gain_at(t, 1.0)
                if denom > 0.05:
                    eff = pkt["charge"] / denom
                    if 0.7 <= eff <= 1.05:
                        solar_eff_est = 0.5 * solar_eff_est + 0.5 * min(1.0, max(0.8, eff))

            # Find if a drive executed at tick t
            exec_cmd = None
            for et, c in cmd_queue:
                if et == t:
                    exec_cmd = c
                    break

            if exec_cmd is not None and exec_cmd["action"] == "drive":
                res = lightlag_surface.drive(
                    surface,
                    physics,
                    est_x,
                    est_y,
                    exec_cmd["heading_deg"] + est_bias_deg,
                    exec_cmd["metres"],
                    slip_base_est,
                )
                pred_x, pred_y = res["x"], res["y"]
                obs_x, obs_y = pkt["position"]
                # Kalman-like blend
                est_x = 0.65 * pred_x + 0.35 * obs_x
                est_y = 0.65 * pred_y + 0.35 * obs_y

                # Update heading bias if we moved significantly
                dx_m = est_x - last_telem_pos[0]
                dy_m = est_y - last_telem_pos[1]
                if math.hypot(dx_m, dy_m) > 1.5:
                    obs_hdg = math.degrees(math.atan2(dy_m, dx_m))
                    pred_hdg = exec_cmd["heading_deg"] + est_bias_deg
                    diff = (obs_hdg - pred_hdg + 180.0) % 360.0 - 180.0
                    est_bias_deg = max(-12.0, min(12.0, est_bias_deg + 0.12 * diff))
            else:
                obs_x, obs_y = pkt["position"]
                est_x = 0.7 * est_x + 0.3 * obs_x
                est_y = 0.7 * est_y + 0.3 * obs_y

            est_battery = pkt["battery"]
            last_telem_tick = t
            last_telem_pos = (est_x, est_y)

    def predict_state_at_queue_end(current_tick):
        px, py = est_x, est_y
        pb = est_battery
        last_t = last_telem_tick
        for et, c in cmd_queue:
            if et <= last_telem_tick:
                continue
            # Account for idle ticks between last_t and et
            for tt in range(last_t + 1, et):
                pb = min(100.0, pb + solar_gain_at(tt, solar_eff_est)) - rules["idle_cost"]
            pb = min(100.0, pb + solar_gain_at(et, solar_eff_est)) - rules["idle_cost"]
            if c["action"] == "drive":
                res = lightlag_surface.drive(
                    surface,
                    physics,
                    px,
                    py,
                    c["heading_deg"] + est_bias_deg,
                    c["metres"],
                    slip_base_est,
                )
                px, py = res["x"], res["y"]
                pb -= res["energy"]
            elif c["action"] == "sample":
                pb -= rules["sample_cost"]
            last_t = et
        end_tick = max(current_tick + delay_ticks, last_t)
        return px, py, pb, end_tick

    def choose_next_target(px, py, pb, from_tick):
        best_tgt = None
        best_score = -1.0
        best_path = None
        margin_tick = max_ticks - 8

        for tid, tgt in known_targets.items():
            if tid in sampled_ids:
                continue
            tx, ty = tgt["x"], tgt["y"]
            path, t_ticks, t_energy = astar((px, py), (tx, ty))
            arr_tick = from_tick + t_ticks + 1.0
            _, r_ticks, r_energy = astar((tx, ty), (base_x, base_y))
            if arr_tick + r_ticks > margin_tick:
                continue

            # Energy check
            avg_solar = solar_gain_at(int(min(max_ticks - 1, from_tick + t_ticks * 0.5)), solar_eff_est)
            net_solar = (t_ticks + r_ticks) * (avg_solar - rules["idle_cost"])
            if pb + net_solar - t_energy - rules["sample_cost"] - r_energy < 8.0:
                continue

            dl = tgt["deadline_tick"]
            val = tgt["value"] if (dl is None or arr_tick <= dl - 1.5) else tgt["late_value"]
            score = val / (t_ticks + 2.0)
            if dl is not None and arr_tick <= dl - 1.5 and dl - arr_tick < 40:
                score *= 1.25
            if score > best_score:
                best_score = score
                best_tgt = tgt
                best_path = path

        return best_tgt, best_path

    current_tick = 0
    current_target = None
    current_path = []
    returning_home = False

    while True:
        if not alive:
            res = tools.advance(min(5, max_ticks - current_tick) if current_tick < max_ticks else 1)
            current_tick = res["current_tick"]
            if res["episode_complete"]:
                break
            continue

        px, py, pb, queue_end_tick = predict_state_at_queue_end(current_tick)

        # Keep queue fed just ahead of delay_ticks
        if queue_end_tick <= current_tick + delay_ticks + 1 and current_tick + delay_ticks + 1 < max_ticks:
            cmds_to_send = []

            if pb < 12.0:
                cmds_to_send.append({"action": "wait"})
            else:
                if current_target is not None and current_target["id"] in sampled_ids:
                    current_target = None
                    current_path = []

                if current_target is None and not returning_home:
                    current_target, current_path = choose_next_target(px, py, pb, queue_end_tick)
                    if current_target is None:
                        returning_home = True
                        current_path, _, _ = astar((px, py), (base_x, base_y))

                if returning_home:
                    dist_base = math.hypot(base_x - px, base_y - py)
                    if dist_base <= base_radius * 0.65:
                        cmds_to_send.append({"action": "wait"})
                    else:
                        if not current_path:
                            current_path, _, _ = astar((px, py), (base_x, base_y))
                        while len(current_path) > 1 and math.hypot(current_path[0][0] - px, current_path[0][1] - py) < 3.0:
                            current_path.pop(0)
                        wx, wy = current_path[0]
                        dx, dy = wx - px, wy - py
                        d = math.hypot(dx, dy)
                        hdg = (math.degrees(math.atan2(dy, dx)) - est_bias_deg) % 360.0
                        m = max(0.2, min(5.0, d / (1.0 - 0.1)))
                        cmds_to_send.append({"action": "drive", "heading_deg": hdg, "metres": m})
                else:
                    tx, ty = current_target["x"], current_target["y"]
                    dist_tgt = math.hypot(tx - px, ty - py)
                    if dist_tgt <= target_radius * 0.72:
                        cmds_to_send.append({"action": "sample"})
                        sampled_ids.add(current_target["id"])
                        current_target = None
                        current_path = []
                    else:
                        if not current_path:
                            current_path, _, _ = astar((px, py), (tx, ty))
                        while len(current_path) > 1 and math.hypot(current_path[0][0] - px, current_path[0][1] - py) < 3.0:
                            current_path.pop(0)
                        wx, wy = current_path[0]
                        dx, dy = wx - px, wy - py
                        d = math.hypot(dx, dy)
                        hdg = (math.degrees(math.atan2(dy, dx)) - est_bias_deg) % 360.0
                        m = max(0.2, min(5.0, d / (1.0 - 0.1)))
                        cmds_to_send.append({"action": "drive", "heading_deg": hdg, "metres": m})

            if cmds_to_send:
                acks = tools.uplink(cmds_to_send)
                for ack in acks:
                    cmd_queue.append((ack["execute_tick"], ack["command"]))

        res = tools.advance(1)
        current_tick = res["current_tick"]
        process_packets(res["packets"])
        if res["episode_complete"]:
            break
