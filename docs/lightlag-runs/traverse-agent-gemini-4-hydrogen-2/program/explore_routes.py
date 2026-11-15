import json, math, random, heapq, sys
sys.path.insert(0, "/app")
from lightlag_surface import Surface, PHYSICS, TERRAIN_CODES

world = json.load(open("/tmp/opencode/map.json"))
rules = json.load(open("/tmp/opencode/rules.json"))
surf = Surface(world["cell_m"], world["elevation_cm"], world["terrain"])

SLIP_MID = {k: 0.5 * (v[0] + v[1]) for k, v in PHYSICS["slip_base_ranges"].items()}
nx, ny = surf.nx, surf.ny
cell = surf.cell
dirs = [(dx, dy) for dx in range(-2, 3) for dy in range(-2, 3)
        if (dx != 0 or dy != 0) and math.gcd(abs(dx), abs(dy)) == 1]

# Build adj optimizing time + small energy tie-breaker
max_tilt = PHYSICS["max_tilt"] - 0.025
adj = [[[] for _ in range(nx)] for _ in range(ny)]
for j in range(ny):
    y0 = j * cell
    for i in range(nx):
        x0 = i * cell
        h0, gx0, gy0, _ = surf.sample(x0, y0)
        if math.hypot(gx0, gy0) > max_tilt:
            continue
        for dx, dy in dirs:
            ni, nj = i + dx, j + dy
            if not (0 <= ni < nx and 0 <= nj < ny):
                continue
            x1, y1 = ni * cell, nj * cell
            L = math.hypot(x1 - x0, y1 - y0)
            steps = int(math.ceil(L / 0.5))
            ok = True
            for s in range(1, steps + 1):
                t = s / steps
                h, gx, gy, _ = surf.sample(x0 + (x1 - x0)*t, y0 + (y1 - y0)*t)
                if math.hypot(gx, gy) > max_tilt:
                    ok = False
                    break
            if not ok:
                continue
            ux, uy = (x1 - x0) / L, (y1 - y0) / L
            dt_sum = 0.0
            e_sum = 0.0
            n_sub = int(math.ceil(L / 1.0))
            ds = L / n_sub
            prev_h = h0
            for s in range(n_sub):
                xm = x0 + (x1 - x0) * ((s + 0.5) / n_sub)
                ym = y0 + (y1 - y0) * ((s + 0.5) / n_sub)
                hm, gx, gy, code = surf.sample(xm, ym)
                name = TERRAIN_CODES[code]
                grade = gx * ux + gy * uy
                slip = min(0.95, max(0.0, SLIP_MID[name] + PHYSICS["slip_grade_gain"][name] * max(0.0, grade)))
                wheel_ds = ds / (1.0 - slip)
                dt_sum += wheel_ds / 5.0
                xe = x0 + (x1 - x0) * ((s + 1) / n_sub)
                ye = y0 + (y1 - y0) * ((s + 1) / n_sub)
                he = surf.elevation(xe, ye)
                e_sum += wheel_ds * PHYSICS["drive_cost_per_wheel_m"][name] + PHYSICS["climb_cost_per_m"] * max(0.0, he - prev_h)
                prev_h = he
            adj[j][i].append((ni, nj, dt_sum, e_sum))

nodes = [("BASE", world["base"][0], world["base"][1])] + [(t["id"], t["x"], t["y"]) for t in world["targets"]]
N = len(nodes)
dist_t = [[1e9]*N for _ in range(N)]
dist_e = [[1e9]*N for _ in range(N)]

for a in range(N):
    _, ax, ay = nodes[a]
    si, sj = round(ax / cell), round(ay / cell)
    d = [[1e9]*nx for _ in range(ny)]
    e = [[1e9]*nx for _ in range(ny)]
    d[sj][si] = 0.0
    e[sj][si] = 0.0
    pq = [(0.0, si, sj)]
    while pq:
        cd, i, j = heapq.heappop(pq)
        if cd > d[j][i] + 1e-9:
            continue
        ce = e[j][i]
        for ni, nj, dt, de in adj[j][i]:
            nd = cd + dt
            if nd < d[nj][ni]:
                d[nj][ni] = nd
                e[nj][ni] = ce + de
                heapq.heappush(pq, (nd, ni, nj))
    for b in range(N):
        _, bx, by = nodes[b]
        ti, tj = round(bx / cell), round(by / cell)
        dist_t[a][b] = d[tj][ti]
        dist_e[a][b] = e[tj][ti]

target_info = [None] + world["targets"]

def solar_gain(tick, eff=0.8):
    return rules["solar_peak"] * eff * math.sin(math.pi * (tick + rules["sun_margin_ticks"]) / (rules["max_ticks"] + 2 * rules["sun_margin_ticks"]))

def eval_route(order, eff=0.8, slip_mult=1.05, wait_margin=5.0):
    # order is list of target indices (1..N-1), implicitly starts at 0 and ends at 0
    tk = 4
    bat = 100.0
    # account for ticks 1, 2, 3 idle
    for pre in (1, 2, 3):
        bat = min(100.0, bat + solar_gain(pre, eff)) - 0.15
    min_bat = bat
    score = 0.0
    cur = 0
    total_waits = 0
    for nxt in order:
        dt = dist_t[cur][nxt] * slip_mult
        de = dist_e[cur][nxt] * slip_mult
        ticks = max(1, int(math.ceil(dt)))
        e_per_tick = de / ticks
        for _ in range(ticks):
            # if battery would drop below wait_margin, insert a wait tick first
            g = solar_gain(tk, eff)
            next_b = min(100.0, bat + g) - 0.15 - e_per_tick
            while next_b < wait_margin:
                bat = min(100.0, bat + solar_gain(tk, eff)) - 0.15
                tk += 1
                total_waits += 1
                if tk > 420: return -1, tk, min_bat, total_waits
                g = solar_gain(tk, eff)
                next_b = min(100.0, bat + g) - 0.15 - e_per_tick
            bat = next_b
            min_bat = min(min_bat, bat)
            tk += 1
            if tk > 420: return -1, tk, min_bat, total_waits
        # sample
        g = solar_gain(tk, eff)
        next_b = min(100.0, bat + g) - 0.15 - 2.0
        while next_b < wait_margin:
            bat = min(100.0, bat + solar_gain(tk, eff)) - 0.15
            tk += 1
            total_waits += 1
            if tk > 420: return -1, tk, min_bat, total_waits
            g = solar_gain(tk, eff)
            next_b = min(100.0, bat + g) - 0.15 - 2.0
        bat = next_b
        min_bat = min(min_bat, bat)
        info = target_info[nxt]
        if info["deadline_tick"] is None or tk <= info["deadline_tick"]:
            score += info["value"]
        else:
            score += info["late_value"]
        tk += 1
        cur = nxt
    # return to base
    dt = dist_t[cur][0] * slip_mult
    de = dist_e[cur][0] * slip_mult
    ticks = max(1, int(math.ceil(dt)))
    e_per_tick = de / ticks
    for _ in range(ticks):
        if tk > 420: return -1, tk, min_bat, total_waits
        g = solar_gain(tk, eff)
        next_b = min(100.0, bat + g) - 0.15 - e_per_tick
        while next_b < wait_margin:
            bat = min(100.0, bat + solar_gain(tk, eff)) - 0.15
            tk += 1
            total_waits += 1
            if tk > 420: return -1, tk, min_bat, total_waits
            g = solar_gain(tk, eff)
            next_b = min(100.0, bat + g) - 0.15 - e_per_tick
        bat = next_b
        min_bat = min(min_bat, bat)
        tk += 1
    if tk > 421:
        return -1, tk, min_bat, total_waits
    return score, tk - 1, min_bat, total_waits

# Check NE cluster manually first
id_to_idx = {nodes[i][0]: i for i in range(N)}
ne_test = [id_to_idx[x] for x in ["t32", "t33", "t34", "t21", "t11", "t31", "t38", "t6", "t23", "t37", "t2", "t30", "t8", "t13", "t17", "t4", "t14", "t36", "t27", "t1", "t28", "t25", "t12", "t3"]]
print("NE->SE->Center->Base test:", eval_route(ne_test))

# Simulated annealing / hill climbing over subsets of targets
rng = random.Random(42)
best_sc = -1
best_route = None
best_stats = None

for restart in range(20):
    cur_route = list(range(1, N))
    rng.shuffle(cur_route)
    # Trim until feasible
    while cur_route and eval_route(cur_route)[0] < 0:
        cur_route.pop()
    cur_res = eval_route(cur_route)
    cur_sc = cur_res[0] + (420 - cur_res[1]) * 0.001
    for it in range(3000):
        cand = list(cur_route)
        op = rng.random()
        unused = [i for i in range(1, N) if i not in cand]
        if op < 0.35 and unused:
            # insert random unused at best or random position
            x = rng.choice(unused)
            pos = rng.randint(0, len(cand))
            cand.insert(pos, x)
        elif op < 0.50 and len(cand) > 1:
            # remove one
            cand.pop(rng.randrange(len(cand)))
        elif op < 0.75 and len(cand) >= 2:
            # swap two
            a, b = rng.sample(range(len(cand)), 2)
            cand[a], cand[b] = cand[b], cand[a]
        elif op < 0.90 and len(cand) >= 2:
            # move one
            a = rng.randrange(len(cand))
            x = cand.pop(a)
            b = rng.randrange(len(cand) + 1)
            cand.insert(b, x)
        else:
            # 2-opt reverse segment
            if len(cand) >= 3:
                a, b = sorted(rng.sample(range(len(cand)), 2))
                cand[a:b+1] = reversed(cand[a:b+1])
        res = eval_route(cand)
        if res[0] < 0:
            continue
        sc = res[0] + (420 - res[1]) * 0.001
        temp = 1.0 * (1.0 - it / 3000.0) + 0.02
        if sc >= cur_sc or rng.random() < math.exp((sc - cur_sc) / temp):
            cur_route = cand
            cur_sc = sc
            cur_res = res
            if res[0] > best_sc or (res[0] == best_sc and res[1] < best_stats[1]):
                best_sc = res[0]
                best_route = list(cand)
                best_stats = res

print(f"\nSA Best route (eff=0.8, 5% slip margin, wait_margin=5.0):")
print(f"  Score = {best_stats[0]:.2f} / 98.0, end_tick = {best_stats[1]}, min_bat = {best_stats[2]:.1f}, waits = {best_stats[3]}")
print("  Route:", " -> ".join(nodes[i][0] for i in best_route) + " -> BASE")
for idx in best_route:
    info = target_info[idx]
    print(f"    {info['id']:3s} ({info['x']:5.1f},{info['y']:5.1f}) val={info['value']} dl={info['deadline_tick']}")
