import json
import math
import heapq
import random
import time
import sys
sys.path.insert(0, "/app")
from lightlag_surface import Surface, TERRAIN_CODES, PHYSICS

with open("/tmp/opencode/rules.json") as f:
    rules = json.load(f)
with open("/tmp/opencode/map.json") as f:
    world = json.load(f)

surf = Surface(world["cell_m"], world["elevation_cm"], world["terrain"])
NX, NY = surf.nx, surf.ny
MID_SLIP = {k: 0.5 * (v[0] + v[1]) for k, v in PHYSICS["slip_base_ranges"].items()}

SNX, SNY = (NX - 1) * 2 + 1, (NY - 1) * 2 + 1
INF = 1e9
clearance = [INF] * (SNX * SNY)
hq = []
for sj in range(SNY):
    py = sj * 2.5
    for si in range(SNX):
        px = si * 2.5
        if px <= 0.0 or px >= 600.0 or py <= 0.0 or py >= 400.0 or surf.slope(px, py) > 0.355:
            clearance[sj * SNX + si] = 0.0
            heapq.heappush(hq, (0.0, si, sj))
while hq:
    d, si, sj = heapq.heappop(hq)
    if d > clearance[sj * SNX + si] + 1e-6 or d > 15.0:
        continue
    for di, dj, sd in [(-1,0,2.5),(1,0,2.5),(0,-1,2.5),(0,1,2.5),(-1,-1,3.5355),(-1,1,3.5355),(1,-1,3.5355),(1,1,3.5355)]:
        ni, nj = si + di, sj + dj
        if 0 <= ni < SNX and 0 <= nj < SNY:
            nd = d + sd
            if nd < clearance[nj * SNX + ni]:
                clearance[nj * SNX + ni] = nd
                heapq.heappush(hq, (nd, ni, nj))

def get_clearance(x, y):
    si = min(SNX - 1, max(0, int(round(x / 2.5))))
    sj = min(SNY - 1, max(0, int(round(y / 2.5))))
    return clearance[sj * SNX + si]

DIRS = [
    (1, 0), (-1, 0), (0, 1), (0, -1),
    (1, 1), (1, -1), (-1, 1), (-1, -1),
    (2, 1), (2, -1), (-2, 1), (-2, -1),
    (1, 2), (1, -2), (-1, 2), (-1, -2),
]
SAFE_CLEARANCE = 3.5
adj = [[] for _ in range(NX * NY)]
for j in range(1, NY - 1):
    y = j * 5.0
    for i in range(1, NX - 1):
        x = i * 5.0
        if get_clearance(x, y) < SAFE_CLEARANCE:
            continue
        u = j * NX + i
        for di, dj in DIRS:
            ni, nj = i + di, j + dj
            if not (1 <= ni < NX - 1 and 1 <= nj < NY - 1):
                continue
            nx_m, ny_m = ni * 5.0, nj * 5.0
            dist = math.hypot(nx_m - x, ny_m - y)
            n_steps = int(math.ceil(dist / 1.25))
            ok = True
            ticks_est = 0.0
            energy_est = 0.0
            ux, uy = (nx_m - x) / dist, (ny_m - y) / dist
            ds = dist / n_steps
            prev_h = surf.elevation(x, y)
            for s in range(n_steps):
                mx = x + ux * (s + 0.5) * ds
                my = y + uy * (s + 0.5) * ds
                if get_clearance(mx, my) < SAFE_CLEARANCE:
                    ok = False
                    break
                h_end = surf.elevation(x + ux * (s + 1) * ds, y + uy * (s + 1) * ds)
                _, gx, gy, code = surf.sample(mx, my)
                tname = TERRAIN_CODES[code]
                grade = gx * ux + gy * uy
                slip = max(0.0, min(0.90, MID_SLIP[tname] + PHYSICS["slip_grade_gain"][tname] * max(0.0, grade)))
                wheel_m = ds / (1.0 - slip)
                ticks_est += wheel_m / 5.0
                energy_est += wheel_m * PHYSICS["drive_cost_per_wheel_m"][tname] + PHYSICS["climb_cost_per_m"] * max(0.0, h_end - prev_h)
                prev_h = h_end
            if ok:
                adj[u].append((nj * NX + ni, ticks_est, energy_est))

targets = world["targets"]
pois = [("BASE", world["base"][0], world["base"][1], 0.0, None, 0.0)]
for t in targets:
    pois.append((t["id"], t["x"], t["y"], t["value"], t["deadline_tick"], t["late_value"]))

N = len(pois)
poi_nodes = [int(round(p[2] / 5.0)) * NX + int(round(p[1] / 5.0)) for p in pois]
dist_t = [[INF] * N for _ in range(N)]
dist_e = [[INF] * N for _ in range(N)]

for s_idx in range(N):
    su = poi_nodes[s_idx]
    bc = [INF] * (NX * NY)
    bt = [INF] * (NX * NY)
    be = [INF] * (NX * NY)
    bc[su] = bt[su] = be[su] = 0.0
    pq = [(0.0, su)]
    while pq:
        c, u = heapq.heappop(pq)
        if c > bc[u] + 1e-9:
            continue
        ut, ue = bt[u], be[u]
        for v, dt, de in adj[u]:
            nc = c + dt + 0.08 * de
            if nc < bc[v]:
                bc[v] = nc
                bt[v] = ut + dt
                be[v] = ue + de
                heapq.heappush(pq, (nc, v))
    for d_idx in range(N):
        du = poi_nodes[d_idx]
        dist_t[s_idx][d_idx] = bt[du]
        dist_e[s_idx][d_idx] = be[du]

SOLAR_SIN = [0.0] + [2.8 * math.sin(math.pi * (t + 56) / 532.0) for t in range(1, 421)]

def eval_route(route, eff=0.85, max_end_tick=408, min_bat_allow=12.0):
    """
    Note: sampling within 1.6m of target center saves ~2.0m (~0.45 ticks, ~0.8 energy) per visit compared to center-to-center!
    Let's use ceil(max(0.5, dist_t[cur][nxt] - 0.35)) ticks, which accurately matches closed-loop simulation!
    And if battery would dip below min_bat_allow during a leg or before sample, insert wait ticks to recharge!
    """
    bat = 100.0
    for t in range(1, 4):
        bat = min(100.0, bat + eff * SOLAR_SIN[t]) - 0.15
    tick = 3
    min_bat = bat
    cur = 0
    score = 0.0
    details = []
    waits_used = 0

    for nxt in route:
        leg_ticks = max(1, int(math.ceil(dist_t[cur][nxt] - 0.30)))
        leg_e = max(0.5, dist_e[cur][nxt] - 0.6) * 1.03
        e_per_tick = leg_e / leg_ticks
        for _ in range(leg_ticks):
            # If next drive tick would drop battery below min_bat_allow, wait until solar recharges enough!
            while tick + 1 <= max_end_tick:
                proj_bat = min(100.0, bat + eff * SOLAR_SIN[tick + 1]) - 0.15 - e_per_tick
                if proj_bat >= min_bat_allow:
                    break
                # Wait 1 tick
                tick += 1
                waits_used += 1
                bat = min(100.0, bat + eff * SOLAR_SIN[tick]) - 0.15
                if tick >= max_end_tick:
                    return -1e9, tick, min_bat, [], waits_used
            tick += 1
            if tick > max_end_tick:
                return -1e9, tick, min_bat, [], waits_used
            bat = min(100.0, bat + eff * SOLAR_SIN[tick]) - 0.15 - e_per_tick
            if bat < min_bat:
                min_bat = bat

        # Sample tick (cost 2.0)
        while tick + 1 <= max_end_tick:
            proj_bat = min(100.0, bat + eff * SOLAR_SIN[tick + 1]) - 0.15 - 2.0
            if proj_bat >= min_bat_allow:
                break
            tick += 1
            waits_used += 1
            bat = min(100.0, bat + eff * SOLAR_SIN[tick]) - 0.15
            if tick >= max_end_tick:
                return -1e9, tick, min_bat, [], waits_used
        tick += 1
        if tick > max_end_tick:
            return -1e9, tick, min_bat, [], waits_used
        bat = min(100.0, bat + eff * SOLAR_SIN[tick]) - 0.15 - 2.0
        if bat < min_bat:
            min_bat = bat

        val, dl, lval = pois[nxt][3], pois[nxt][4], pois[nxt][5]
        earned = val if (dl is None or tick <= dl) else lval
        score += earned
        details.append((pois[nxt][0], tick, dl, earned, round(bat, 1)))
        cur = nxt

    # Return to base (within 2.5m of base saves ~0.5 ticks)
    ret_ticks = max(1, int(math.ceil(dist_t[cur][0] - 0.50)))
    ret_e = max(0.5, dist_e[cur][0] - 1.0) * 1.03
    e_per_tick = ret_e / ret_ticks
    for _ in range(ret_ticks):
        while tick + 1 <= max_end_tick:
            proj_bat = min(100.0, bat + eff * SOLAR_SIN[tick + 1]) - 0.15 - e_per_tick
            if proj_bat >= min_bat_allow:
                break
            tick += 1
            waits_used += 1
            bat = min(100.0, bat + eff * SOLAR_SIN[tick]) - 0.15
            if tick >= max_end_tick:
                return -1e9, tick, min_bat, [], waits_used
        tick += 1
        if tick > max_end_tick:
            return -1e9, tick, min_bat, [], waits_used
        bat = min(100.0, bat + eff * SOLAR_SIN[tick]) - 0.15 - e_per_tick
        if bat < min_bat:
            min_bat = bat

    return score, tick, min_bat, details, waits_used

id_to_idx = {pois[i][0]: i for i in range(N)}

# Hand-craft seed skeletons covering all major cluster combinations!
SEEDS = [
    # 1. NE -> East -> SE -> South -> CenterEast
    ["t32", "t21", "t11", "t31", "t38", "t6", "t23", "t2", "t30", "t8", "t17", "t13", "t4", "t14", "t36", "t1", "t28", "t25", "t12", "t34", "t3"],
    # 2. NE (urgent t38, t6 first!) -> SE -> CenterEast
    ["t38", "t6", "t23", "t31", "t11", "t2", "t30", "t8", "t13", "t4", "t17", "t14", "t36", "t27", "t1", "t28", "t25", "t12", "t34", "t32", "t3"],
    # 3. CenterEast -> SE -> South -> SW -> NW
    ["t33", "t34", "t12", "t25", "t28", "t1", "t4", "t13", "t8", "t17", "t14", "t36", "t27", "t22", "t35", "t20", "t10", "t15", "t26", "t16", "t18", "t3"],
    # 4. NW (urgent t7, t19, t29) -> SW -> South -> SE -> CenterEast
    ["t7", "t19", "t29", "t9", "t16", "t26", "t15", "t20", "t35", "t22", "t10", "t18", "t27", "t36", "t14", "t1", "t28", "t25", "t12", "t34", "t32"],
    # 5. NE -> CenterEast -> SE -> SW
    ["t32", "t38", "t6", "t23", "t31", "t11", "t33", "t34", "t28", "t25", "t12", "t1", "t13", "t8", "t17", "t4", "t14", "t36", "t27"],
    # 6. East urgent (t37, t38, t6) -> NE -> SE -> CenterEast
    ["t37", "t6", "t38", "t23", "t31", "t11", "t2", "t30", "t8", "t17", "t13", "t4", "t14", "t36", "t1", "t28", "t25", "t12", "t34", "t32"],
]

def multi_start_sa(eff, max_end_tick=408, min_bat_allow=12.0, restarts=12, sec_per_restart=0.4):
    all_t = list(range(1, N))
    global_best_sc = -1e9
    global_best_rt = []
    rng = random.Random(100 + int(eff * 1000))

    for r_idx in range(restarts):
        if r_idx < len(SEEDS):
            # Trim seed until feasible or start from subset
            seed = [id_to_idx[s] for s in SEEDS[r_idx]]
            cur_r = []
            for x in seed:
                if eval_route(cur_r + [x], eff, max_end_tick, min_bat_allow)[0] > -1e5:
                    cur_r.append(x)
        else:
            cur_r = []
            rem = all_t[:]
            rng.shuffle(rem)
            for x in rem:
                best_ins_sc = -1e9
                best_pos = 0
                for p in range(len(cur_r) + 1):
                    sc = eval_route(cur_r[:p] + [x] + cur_r[p:], eff, max_end_tick, min_bat_allow)[0]
                    if sc > best_ins_sc:
                        best_ins_sc = sc
                        best_pos = p
                if best_ins_sc > -1e5:
                    cur_r.insert(best_pos, x)

        cur_sc, cur_tk, _, _, _ = eval_route(cur_r, eff, max_end_tick, min_bat_allow)
        if cur_sc > global_best_sc:
            global_best_sc = cur_sc
            global_best_rt = cur_r[:]

        t_end = time.time() + sec_per_restart
        while time.time() < t_end:
            rem_frac = (t_end - time.time()) / sec_per_restart
            temp = 0.05 + 2.0 * rem_frac
            cand_r = cur_r[:]
            in_set = set(cand_r)
            out_list = [x for x in all_t if x not in in_set]
            op = rng.random()
            if op < 0.30 and out_list:
                # Best-position insert of a random out target!
                x = rng.choice(out_list)
                best_p = rng.randint(0, len(cand_r))
                if rng.random() < 0.6:
                    best_s = -1e9
                    for p in range(len(cand_r) + 1):
                        s, tk, _, _, _ = eval_route(cand_r[:p] + [x] + cand_r[p:], eff, max_end_tick, min_bat_allow)
                        s_tie = s - 0.001 * tk
                        if s_tie > best_s:
                            best_s = s_tie
                            best_p = p
                cand_r.insert(best_p, x)
            elif op < 0.50 and cand_r:
                cand_r.pop(rng.randint(0, len(cand_r) - 1))
            elif op < 0.70 and cand_r and out_list:
                pos = rng.randint(0, len(cand_r) - 1)
                cand_r[pos] = rng.choice(out_list)
            elif op < 0.86 and len(cand_r) >= 2:
                i = rng.randint(0, len(cand_r) - 1)
                x = cand_r.pop(i)
                j = rng.randint(0, len(cand_r))
                cand_r.insert(j, x)
            elif len(cand_r) >= 2:
                i, j = sorted(rng.sample(range(len(cand_r)), 2))
                cand_r[i:j+1] = reversed(cand_r[i:j+1])

            sc, tk, _, _, _ = eval_route(cand_r, eff, max_end_tick, min_bat_allow)
            if sc > -1e5:
                # slight preference for shorter ticks when score is equal!
                obj_cand = sc - 0.002 * tk
                obj_cur = cur_sc - 0.002 * cur_tk
                if obj_cand >= obj_cur or rng.random() < math.exp((obj_cand - obj_cur) / temp):
                    cur_r = cand_r
                    cur_sc = sc
                    cur_tk = tk
                    if sc > global_best_sc or (sc == global_best_sc and tk < eval_route(global_best_rt, eff, max_end_tick, min_bat_allow)[1]):
                        global_best_sc = sc
                        global_best_rt = cand_r[:]

    return global_best_sc, global_best_rt

for eff in [0.80, 0.85, 0.90, 0.95, 1.00]:
    sc, rt = multi_start_sa(eff, max_end_tick=408, min_bat_allow=12.0, restarts=14, sec_per_restart=0.4)
    sc, end_tk, mb, det, waits = eval_route(rt, eff=eff, max_end_tick=408, min_bat_allow=12.0)
    print(f"\n=== Eff={eff:.2f}: Score={sc:.2f} / 98.0, EndTick={end_tk}, Waits={waits}, MinBat={mb:.1f}, N={len(rt)} ===")
    print(" -> ".join(f"{d[0]}(t={d[1]}/{d[2]},+{d[3]},b={d[4]})" for d in det))
