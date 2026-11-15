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

# Clearance map on 2.5m grid
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
SAFE_CLEARANCE = 4.0
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
            nc = c + dt + 0.06 * de
            if nc < bc[v]:
                bc[v] = nc
                bt[v] = ut + dt
                be[v] = ue + de
                heapq.heappush(pq, (nc, v))
    for d_idx in range(N):
        du = poi_nodes[d_idx]
        dist_t[s_idx][d_idx] = bt[du]
        dist_e[s_idx][d_idx] = be[du]

# Precompute solar curve per tick 1..420
SOLAR_SIN = [0.0] + [2.8 * math.sin(math.pi * (t + 56) / 532.0) for t in range(1, 421)]

def eval_route(route, eff=0.85, max_end_tick=408, min_bat_allow=15.0):
    """
    route: list of target indices in 1..N-1. Starts at 0 (at tick 3, before tick 4 executes), ends at 0.
    Wait: ticks 1, 2, 3 are idle before first command executes at tick 4!
    Account for discrete ticks (ceil of leg ticks + overhead for approach/alignment, minus radius savings ~0.4t).
    Let's be conservative: leg_ticks = int(math.ceil(dist_t[u][v] + 0.3))!
    Plus 1 tick to sample!
    """
    bat = 100.0
    for t in range(1, 4):
        bat = min(100.0, bat + eff * SOLAR_SIN[t]) - 0.15
    tick = 3
    min_bat = bat
    cur = 0
    score = 0.0
    details = []
    for nxt in route:
        leg_ticks = max(1, int(math.ceil(dist_t[cur][nxt] + 0.3)))
        leg_e = dist_e[cur][nxt] * 1.03  # 3% margin
        if tick + leg_ticks + 1 > max_end_tick:
            return -1e9, tick, min_bat, []
        e_per_tick = leg_e / leg_ticks
        for _ in range(leg_ticks):
            tick += 1
            bat = min(100.0, bat + eff * SOLAR_SIN[tick]) - 0.15 - e_per_tick
            if bat < min_bat:
                min_bat = bat
        # Sample tick
        tick += 1
        bat = min(100.0, bat + eff * SOLAR_SIN[tick]) - 0.15 - 2.0
        if bat < min_bat:
            min_bat = bat
        _, name_x, name_y, val, dl, lval = pois[nxt][0], pois[nxt][1], pois[nxt][2], pois[nxt][3], pois[nxt][4], pois[nxt][5]
        earned = val if (dl is None or tick <= dl) else lval
        score += earned
        details.append((pois[nxt][0], tick, dl, earned, round(bat, 1)))
        cur = nxt

    # Return to base
    ret_ticks = max(1, int(math.ceil(dist_t[cur][0] - 0.3)))
    ret_e = dist_e[cur][0] * 1.03
    if tick + ret_ticks > max_end_tick:
        return -1e9, tick + ret_ticks, min_bat, []
    e_per_tick = ret_e / ret_ticks
    for _ in range(ret_ticks):
        tick += 1
        bat = min(100.0, bat + eff * SOLAR_SIN[tick]) - 0.15 - e_per_tick
        if bat < min_bat:
            min_bat = bat
    if min_bat < min_bat_allow:
        return -1e9 + min_bat * 10, tick, min_bat, []
    return score, tick, min_bat, details

# Simulated Annealing / Iterated Local Search over subsets and permutations!
def optimize(eff=0.85, max_end_tick=408, min_bat_allow=15.0, seconds=4.0):
    rng = random.Random(42)
    all_t = list(range(1, N))
    best_route = []
    best_score = 0.0
    
    # Greedy randomized starts
    for trial in range(40):
        cur_r = []
        rem = set(all_t)
        while True:
            cands = []
            for cand in rem:
                # try inserting at best position or appending
                sc, tk, mb, _ = eval_route(cur_r + [cand], eff, max_end_tick, min_bat_allow)
                if sc > -1e5:
                    dt = dist_t[cur_r[-1] if cur_r else 0][cand] + 1.0
                    gain = sc - eval_route(cur_r, eff, max_end_tick, min_bat_allow)[0]
                    cands.append((gain / (dt ** (0.7 + 0.5 * (trial % 3))), cand, sc))
            if not cands:
                break
            cands.sort(reverse=True)
            pick = cands[rng.randrange(min(3, len(cands)))][1] if trial > 5 else cands[0][1]
            cur_r.append(pick)
            rem.remove(pick)
        sc, _, _, _ = eval_route(cur_r, eff, max_end_tick, min_bat_allow)
        if sc > best_score:
            best_score = sc
            best_route = cur_r[:]

    # Local search + SA
    t_end = time.time() + seconds
    cur_r = best_route[:]
    cur_sc = best_score
    iters = 0
    while time.time() < t_end:
        iters += 1
        temp = max(0.05, 1.5 * (1.0 - (seconds - (t_end - time.time())) / seconds))
        cand_r = cur_r[:]
        in_set = set(cand_r)
        out_list = [x for x in all_t if x not in in_set]
        op = rng.random()
        if op < 0.28 and out_list:
            # Insert
            x = rng.choice(out_list)
            pos = rng.randint(0, len(cand_r))
            cand_r.insert(pos, x)
        elif op < 0.48 and cand_r:
            # Remove
            pos = rng.randint(0, len(cand_r) - 1)
            cand_r.pop(pos)
        elif op < 0.68 and cand_r and out_list:
            # Replace
            pos = rng.randint(0, len(cand_r) - 1)
            cand_r[pos] = rng.choice(out_list)
        elif op < 0.85 and len(cand_r) >= 2:
            # Relocate within route
            i = rng.randint(0, len(cand_r) - 1)
            x = cand_r.pop(i)
            j = rng.randint(0, len(cand_r))
            cand_r.insert(j, x)
        elif len(cand_r) >= 2:
            # 2-opt segment reverse
            i, j = sorted(rng.sample(range(len(cand_r)), 2))
            cand_r[i:j+1] = reversed(cand_r[i:j+1])

        sc, _, _, _ = eval_route(cand_r, eff, max_end_tick, min_bat_allow)
        if sc > -1e5:
            if sc >= cur_sc or rng.random() < math.exp((sc - cur_sc) / temp):
                cur_r = cand_r
                cur_sc = sc
                if sc > best_score:
                    best_score = sc
                    best_route = cand_r[:]
    return best_score, best_route, iters

for eff in [0.80, 0.85, 0.90, 0.95, 1.00]:
    sc, rt, iters = optimize(eff=eff, max_end_tick=408, min_bat_allow=15.0, seconds=2.5)
    sc, end_tk, mb, det = eval_route(rt, eff=eff, max_end_tick=408, min_bat_allow=15.0)
    print(f"\n=== Eff={eff:.2f} (iters={iters}): Score={sc:.2f} / 98.0, EndTick={end_tk}, MinBat={mb:.1f}, Targets={len(rt)} ===")
    print("Route:", " -> ".join(f"{d[0]}(t={d[1]}/{d[2]},+{d[3]},b={d[4]})" for d in det))
