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

def compute_apsp(alpha):
    dist_t = [[1e9]*N for _ in range(N)]
    dist_e = [[1e9]*N for _ in range(N)]
    for a in range(N):
        _, ax, ay = nodes[a]
        si, sj = round(ax / cell), round(ay / cell)
        cost = [[1e9]*nx for _ in range(ny)]
        d = [[1e9]*nx for _ in range(ny)]
        e = [[1e9]*nx for _ in range(ny)]
        cost[sj][si] = 0.0
        d[sj][si] = 0.0
        e[sj][si] = 0.0
        pq = [(0.0, si, sj)]
        while pq:
            cc, i, j = heapq.heappop(pq)
            if cc > cost[j][i] + 1e-9: continue
            cd, ce = d[j][i], e[j][i]
            for ni, nj, dt, de in adj[j][i]:
                nc = cc + dt + alpha * de
                if nc < cost[nj][ni]:
                    cost[nj][ni] = nc
                    d[nj][ni] = cd + dt
                    e[nj][ni] = ce + de
                    heapq.heappush(pq, (nc, ni, nj))
        for b in range(N):
            _, bx, by = nodes[b]
            ti, tj = round(bx / cell), round(by / cell)
            dist_t[a][b] = d[tj][ti]
            dist_e[a][b] = e[tj][ti]
    return dist_t, dist_e

modes = [compute_apsp(a) for a in (0.02, 0.35, 1.2)]
target_info = [None] + world["targets"]

def solar_gain(tick, eff=0.8):
    return rules["solar_peak"] * eff * math.sin(math.pi * (tick + rules["sun_margin_ticks"]) / (rules["max_ticks"] + 2 * rules["sun_margin_ticks"]))

def eval_route(order, eff=0.8, slip_mult=1.03, wait_margin=5.0):
    tk = 4
    bat = 100.0
    for pre in (1, 2, 3):
        bat = min(100.0, bat + solar_gain(pre, eff)) - 0.15
    min_bat = bat
    score = 0.0
    cur = 0
    total_waits = 0
    for nxt in order + [0]:
        # Try fast mode first; if it hits wait_margin or uses too much energy, try balanced then eco
        best_leg = None
        for dt_m, de_m in modes:
            dt = dt_m[cur][nxt] * slip_mult
            de = de_m[cur][nxt] * slip_mult
            ticks = max(1, int(math.ceil(dt)))
            e_per_tick = de / ticks
            tk_sim, bat_sim, mb_sim, w_sim = tk, bat, min_bat, 0
            ok = True
            for _ in range(ticks):
                g = solar_gain(tk_sim, eff)
                next_b = min(100.0, bat_sim + g) - 0.15 - e_per_tick
                while next_b < wait_margin:
                    bat_sim = min(100.0, bat_sim + solar_gain(tk_sim, eff)) - 0.15
                    tk_sim += 1
                    w_sim += 1
                    if tk_sim > 420: ok = False; break
                    g = solar_gain(tk_sim, eff)
                    next_b = min(100.0, bat_sim + g) - 0.15 - e_per_tick
                if not ok: break
                bat_sim = next_b
                mb_sim = min(mb_sim, bat_sim)
                tk_sim += 1
                if tk_sim > 421: ok = False; break
            if not ok: continue
            if best_leg is None or tk_sim < best_leg[0] or (tk_sim == best_leg[0] and bat_sim > best_leg[1]):
                best_leg = (tk_sim, bat_sim, mb_sim, w_sim)
        if best_leg is None:
            return -1, 421, min_bat, total_waits
        tk, bat, min_bat, w_leg = best_leg
        total_waits += w_leg
        if nxt == 0:
            break
        # sample
        if tk > 420: return -1, tk, min_bat, total_waits
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
    return score, tk - 1, min_bat, total_waits

# Check NE path alone first!
id_to_idx = {nodes[i][0]: i for i in range(N)}
for name, seq in [
    ("NE only", ["t32", "t33", "t38", "t6", "t31", "t23", "t11", "t21"]),
    ("NE+SE", ["t33", "t38", "t6", "t31", "t23", "t11", "t37", "t2", "t30", "t8", "t13", "t17", "t4", "t14", "t36", "t1", "t28", "t25", "t12", "t32"]),
]:
    res = eval_route([id_to_idx[x] for x in seq])
    print(name, res)

rng = random.Random(7)
best_sc = -1
best_route = None
best_stats = None
seeds = [
    [id_to_idx[x] for x in ["t33", "t38", "t6", "t31", "t23", "t11", "t37", "t2", "t30", "t8", "t13", "t17", "t4", "t14", "t36", "t1", "t28", "t25", "t12"]],
    [id_to_idx[x] for x in ["t12", "t25", "t28", "t1", "t4", "t13", "t8", "t17", "t14", "t36", "t27", "t18", "t10", "t22", "t20", "t26", "t15", "t16"]],
    [id_to_idx[x] for x in ["t3", "t7", "t19", "t29", "t24", "t5", "t32", "t33", "t38", "t6", "t31", "t23", "t11"]],
]
for restart in range(25):
    if restart < len(seeds):
        cur_route = list(seeds[restart])
    else:
        cur_route = list(range(1, N))
        rng.shuffle(cur_route)
    while cur_route and eval_route(cur_route)[0] < 0:
        cur_route.pop()
    cur_res = eval_route(cur_route)
    cur_sc = cur_res[0] + (420 - cur_res[1]) * 0.001
    for it in range(3000):
        cand = list(cur_route)
        op = rng.random()
        unused = [i for i in range(1, N) if i not in cand]
        if op < 0.35 and unused:
            x = rng.choice(unused)
            cand.insert(rng.randint(0, len(cand)), x)
        elif op < 0.50 and len(cand) > 1:
            cand.pop(rng.randrange(len(cand)))
        elif op < 0.70 and len(cand) >= 2:
            a, b = rng.sample(range(len(cand)), 2)
            cand[a], cand[b] = cand[b], cand[a]
        elif op < 0.85 and len(cand) >= 2:
            x = cand.pop(rng.randrange(len(cand)))
            cand.insert(rng.randrange(len(cand) + 1), x)
        elif len(cand) >= 3:
            a, b = sorted(rng.sample(range(len(cand)), 2))
            cand[a:b+1] = reversed(cand[a:b+1])
        res = eval_route(cand)
        if res[0] < 0: continue
        sc = res[0] + (420 - res[1]) * 0.001
        temp = 1.2 * (1.0 - it / 3000.0) + 0.02
        if sc >= cur_sc or rng.random() < math.exp((sc - cur_sc) / temp):
            cur_route, cur_sc, cur_res = cand, sc, res
            if res[0] > best_sc or (res[0] == best_sc and res[1] < best_stats[1]):
                best_sc, best_route, best_stats = res[0], list(cand), res

print(f"\nMulti-mode SA Best (eff=0.8): Score={best_stats[0]:.2f}/98, end={best_stats[1]}, min_bat={best_stats[2]:.1f}, waits={best_stats[3]}")
print("  " + " -> ".join(nodes[i][0] for i in best_route) + " -> BASE")
for eff in (0.9, 1.0):
    print(f"  Same route if eff={eff}:", eval_route(best_route, eff=eff))
