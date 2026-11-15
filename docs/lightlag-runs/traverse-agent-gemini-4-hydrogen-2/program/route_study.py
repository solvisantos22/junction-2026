import json, math, random, heapq, time, sys
sys.path.insert(0, "/app")
from lightlag_surface import Surface, PHYSICS, TERRAIN_CODES

t0 = time.time()
world = json.load(open("/tmp/opencode/map.json"))
rules = json.load(open("/tmp/opencode/rules.json"))
surf = Surface(world["cell_m"], world["elevation_cm"], world["terrain"])

SLIP_MID = {k: 0.5 * (v[0] + v[1]) for k, v in PHYSICS["slip_base_ranges"].items()}
nx, ny = surf.nx, surf.ny
cell = surf.cell
dirs = [(dx, dy) for dx in range(-2, 3) for dy in range(-2, 3)
        if (dx != 0 or dy != 0) and math.gcd(abs(dx), abs(dy)) == 1]

# Precompute safe vertices first (much faster than checking segments repeatedly!)
max_tilt = PHYSICS["max_tilt"] - 0.03
safe_pt = [[False]*nx for _ in range(ny)]
for j in range(ny):
    y0 = j * cell
    for i in range(nx):
        x0 = i * cell
        _, gx, gy, _ = surf.sample(x0, y0)
        safe_pt[j][i] = (math.hypot(gx, gy) <= max_tilt)

adj = [[[] for _ in range(nx)] for _ in range(ny)]
for j in range(ny):
    y0 = j * cell
    for i in range(nx):
        if not safe_pt[j][i]: continue
        x0 = i * cell
        h0 = surf.h[j][i]
        for dx, dy in dirs:
            ni, nj = i + dx, j + dy
            if not (0 <= ni < nx and 0 <= nj < ny) or not safe_pt[nj][ni]:
                continue
            x1, y1 = ni * cell, nj * cell
            L = math.hypot(x1 - x0, y1 - y0)
            steps = int(math.ceil(L / 1.0))
            ok = True
            for s in range(1, steps):
                t = s / steps
                _, gx, gy, _ = surf.sample(x0 + (x1 - x0)*t, y0 + (y1 - y0)*t)
                if math.hypot(gx, gy) > max_tilt:
                    ok = False
                    break
            if not ok:
                continue
            ux, uy = (x1 - x0) / L, (y1 - y0) / L
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
            adj[j][i].append((ni, nj, dt_sum, e_sum))

print(f"Adj built in {time.time()-t0:.2f}s")

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

t1 = time.time()
modes = [compute_apsp(a) for a in (0.02, 0.5)]
print(f"2 APSPs built in {time.time()-t1:.2f}s")

target_info = [None] + world["targets"]

# Precompute solar table
SOLAR_SIN = [rules["solar_peak"] * math.sin(math.pi * (tk + rules["sun_margin_ticks"]) / (rules["max_ticks"] + 2 * rules["sun_margin_ticks"])) for tk in range(430)]
# Prefix sums of solar_sin for O(1) leg solar calculation!
SOLAR_PRE = [0.0] * 431
for k in range(1, 430):
    SOLAR_PRE[k] = SOLAR_PRE[k-1] + SOLAR_SIN[k]

def optimize_for_eff(eff):
    def eval_route_fast(order, slip_mult=1.03, wait_margin=5.0):
        tk = 4
        bat = 100.0 - 3 * 0.15 + eff * (SOLAR_PRE[3] - SOLAR_PRE[0])
        if bat > 100.0: bat = 100.0
        min_bat = bat
        score = 0.0
        cur = 0
        total_waits = 0
        for nxt in order + [0]:
            best_leg = None
            for dt_m, de_m in modes:
                ticks = max(1, int(math.ceil(dt_m[cur][nxt] * slip_mult)))
                de = de_m[cur][nxt] * slip_mult
                tk_end = tk + ticks - 1
                if tk_end > 420: continue
                # Fast check without capping if bat + net < 100
                net_solar = eff * (SOLAR_PRE[tk_end] - SOLAR_PRE[tk - 1])
                bat_end = bat + net_solar - 0.15 * ticks - de
                w = 0
                tk_s = tk
                if bat_end < wait_margin or bat > 90.0:
                    # Exact per-tick simulation for this leg only when needed
                    b = bat
                    mb = min_bat
                    ok = True
                    e_tick = de / ticks
                    for _ in range(ticks):
                        if tk_s > 420: ok = False; break
                        g = eff * SOLAR_SIN[tk_s]
                        nb = min(100.0, b + g) - 0.15 - e_tick
                        while nb < wait_margin:
                            b = min(100.0, b + eff * SOLAR_SIN[tk_s]) - 0.15
                            tk_s += 1
                            w += 1
                            if tk_s > 420: ok = False; break
                            nb = min(100.0, b + eff * SOLAR_SIN[tk_s]) - 0.15 - e_tick
                        if not ok: break
                        b = nb
                        if b < mb: mb = b
                        tk_s += 1
                    if not ok: continue
                    bat_end, mb_end = b, mb
                else:
                    if bat_end > 100.0: bat_end = 100.0
                    tk_s = tk + ticks
                    mb_end = min(min_bat, bat_end)
                if best_leg is None or tk_s < best_leg[0] or (tk_s == best_leg[0] and bat_end > best_leg[1]):
                    best_leg = (tk_s, bat_end, mb_end, w)
            if best_leg is None:
                return -1, 421, min_bat, total_waits
            tk, bat, min_bat, w_leg = best_leg
            total_waits += w_leg
            if nxt == 0:
                break
            if tk > 420: return -1, tk, min_bat, total_waits
            nb = min(100.0, bat + eff * SOLAR_SIN[tk]) - 0.15 - 2.0
            while nb < wait_margin:
                bat = min(100.0, bat + eff * SOLAR_SIN[tk]) - 0.15
                tk += 1
                total_waits += 1
                if tk > 420: return -1, tk, min_bat, total_waits
                nb = min(100.0, bat + eff * SOLAR_SIN[tk]) - 0.15 - 2.0
            bat = nb
            if bat < min_bat: min_bat = bat
            info = target_info[nxt]
            score += info["value"] if (info["deadline_tick"] is None or tk <= info["deadline_tick"]) else info["late_value"]
            tk += 1
            cur = nxt
        return score, tk - 1, min_bat, total_waits

    rng = random.Random(123)
    best_sc = -1
    best_route = None
    best_stats = None
    for restart in range(25):
        cur_route = []
        used = set()
        for _ in range(25):
            cands = [i for i in range(1, N) if i not in used]
            if not cands: break
            last = cur_route[-1] if cur_route else 0
            cands.sort(key=lambda x: modes[0][0][last][x] / (target_info[x]["value"] + 0.5))
            pick = cands[rng.randrange(min(4, len(cands)))]
            if eval_route_fast(cur_route + [pick])[0] >= 0:
                cur_route.append(pick)
                used.add(pick)
            else:
                break
        cur_res = eval_route_fast(cur_route)
        cur_sc = cur_res[0] + (420 - cur_res[1]) * 0.001
        for it in range(3000):
            cand = list(cur_route)
            op = rng.random()
            unused = [i for i in range(1, N) if i not in cand]
            if op < 0.35 and unused:
                x = rng.choice(unused)
                cand.insert(rng.randint(0, len(cand)), x)
            elif op < 0.48 and len(cand) > 1:
                cand.pop(rng.randrange(len(cand)))
            elif op < 0.68 and len(cand) >= 2:
                a, b = rng.sample(range(len(cand)), 2)
                cand[a], cand[b] = cand[b], cand[a]
            elif op < 0.85 and len(cand) >= 2:
                x = cand.pop(rng.randrange(len(cand)))
                cand.insert(rng.randrange(len(cand) + 1), x)
            elif len(cand) >= 3:
                a, b = sorted(rng.sample(range(len(cand)), 2))
                cand[a:b+1] = reversed(cand[a:b+1])
            res = eval_route_fast(cand)
            if res[0] < 0: continue
            sc = res[0] + (420 - res[1]) * 0.001
            temp = 1.5 * (1.0 - it / 3000.0) + 0.015
            if sc >= cur_sc or rng.random() < math.exp((sc - cur_sc) / temp):
                cur_route, cur_sc, cur_res = cand, sc, res
                if res[0] > best_sc or (res[0] == best_sc and res[1] < best_stats[1]):
                    best_sc, best_route, best_stats = res[0], list(cand), res
    print(f"eff={eff}: Score={best_stats[0]:.2f}/98, end={best_stats[1]}, min_bat={best_stats[2]:.1f}, waits={best_stats[3]}")
    print("  " + " -> ".join(nodes[i][0] for i in best_route) + " -> BASE")

for eff in [0.8, 0.9, 1.0]:
    optimize_for_eff(eff)
print(f"Total time: {time.time()-t0:.2f}s")
