import json, math, heapq, sys
sys.path.insert(0, "/app")
from lightlag_surface import Surface, PHYSICS, TERRAIN_CODES

world = json.load(open("/tmp/opencode/map.json"))
rules = json.load(open("/tmp/opencode/rules.json"))
surf = Surface(world["cell_m"], world["elevation_cm"], world["terrain"])

SLIP_MID = {k: 0.5 * (v[0] + v[1]) for k, v in PHYSICS["slip_base_ranges"].items()}
SLIP_WORST = {k: v[1] for k, v in PHYSICS["slip_base_ranges"].items()}

# Build graph on 5m vertices (121 x 81)
nx, ny = surf.nx, surf.ny
cell = surf.cell
dirs = []
for dx in range(-2, 3):
    for dy in range(-2, 3):
        if dx == 0 and dy == 0:
            continue
        if math.gcd(abs(dx), abs(dy)) == 1:
            dirs.append((dx, dy))

def build_adj(slip_base, margin=0.02):
    max_tilt = PHYSICS["max_tilt"] - margin
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
                # Integrate energy & ticks over 0.25m steps approximately
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
                    slip = min(0.95, max(0.0, slip_base[name] + PHYSICS["slip_grade_gain"][name] * max(0.0, grade)))
                    wheel_ds = ds / (1.0 - slip)
                    dt_sum += wheel_ds / 5.0
                    # height at end of subsegment
                    xe = x0 + (x1 - x0) * ((s + 1) / n_sub)
                    ye = y0 + (y1 - y0) * ((s + 1) / n_sub)
                    he = surf.elevation(xe, ye)
                    e_sum += wheel_ds * PHYSICS["drive_cost_per_wheel_m"][name] + PHYSICS["climb_cost_per_m"] * max(0.0, he - prev_h)
                    prev_h = he
                adj[j][i].append((ni, nj, dt_sum, e_sum))
    return adj

adj = build_adj(SLIP_MID, margin=0.025)
print("Graph built.")

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

# Check NE route feasibility and energy from tick 4
# Let's see how fast a greedy / beam search scores on the 38 known targets!
target_info = [None] + world["targets"]

def solar_gain(tick, eff=0.8):
    return rules["solar_peak"] * eff * math.sin(math.pi * (tick + rules["sun_margin_ticks"]) / (rules["max_ticks"] + 2 * rules["sun_margin_ticks"]))

# Evaluate a sequence of node indices (starting at 0, ending at 0)
def eval_seq(seq, eff=0.8, slip_mult=1.05):
    t = 4.0
    bat = 100.0
    min_bat = 100.0
    score = 0.0
    cur = 0
    for nxt in seq:
        if nxt == 0:
            dt = dist_t[cur][0] * slip_mult
            de = dist_e[cur][0] * slip_mult
            ticks = int(math.ceil(dt))
            for k in range(ticks):
                tk = int(t) + k
                if tk > 420: return -1, 0, 0
                bat = min(100.0, bat + solar_gain(tk, eff)) - 0.15 - (de / max(1, ticks))
                min_bat = min(min_bat, bat)
                if bat <= 0: return -1, 0, 0
            t += ticks
            cur = 0
            break
        dt = dist_t[cur][nxt] * slip_mult
        de = dist_e[cur][nxt] * slip_mult
        ticks = int(math.ceil(dt))
        for k in range(ticks):
            tk = int(t) + k
            if tk > 420: return -1, 0, 0
            bat = min(100.0, bat + solar_gain(tk, eff)) - 0.15 - (de / max(1, ticks))
            min_bat = min(min_bat, bat)
            if bat <= 0: return -1, 0, 0
        t += ticks
        # sample tick
        tk = int(t)
        if tk > 420: return -1, 0, 0
        bat = min(100.0, bat + solar_gain(tk, eff)) - 0.15 - 2.0
        min_bat = min(min_bat, bat)
        if bat <= 0: return -1, 0, 0
        info = target_info[nxt]
        if info["deadline_tick"] is None or tk <= info["deadline_tick"]:
            score += info["value"]
        else:
            score += info["late_value"]
        t += 1
        cur = nxt
    return score, t, min_bat

# Simple beam search to explore attainable scores on initial 38 targets
beam = [(0.0, 4.0, 100.0, 0, frozenset(), [])]
best_done = (0.0, [], 0.0, 100.0)

for step in range(39):
    next_beam = []
    for sc, t, bat, cur, vis, path in beam:
        # try returning to base
        dt0 = dist_t[cur][0] * 1.05
        if t + dt0 <= 416:
            s_fin, t_fin, mb = eval_seq(path + [0])
            if s_fin > best_done[0]:
                best_done = (s_fin, path + [0], t_fin, mb)
        # try next target
        for nxt in range(1, N):
            if nxt in vis:
                continue
            dt = dist_t[cur][nxt] * 1.05
            dt_back = dist_t[nxt][0] * 1.05
            if t + dt + 1 + dt_back > 416:
                continue
            info = target_info[nxt]
            arr_t = t + dt
            val = info["value"] if (info["deadline_tick"] is None or arr_t <= info["deadline_tick"]) else info["late_value"]
            # heuristic priority: score + future potential
            # check battery roughly
            e_need = dist_e[cur][nxt] * 1.05 + 2.0
            if bat + max(1, int(dt)) * 1.0 - e_need < 5.0:
                # only rough filter
                pass
            next_beam.append((sc + val, arr_t + 1, bat, nxt, vis | {nxt}, path + [nxt]))
    if not next_beam:
        break
    # deduplicate by (cur, vis)? No, sort by (sc / max(1, t), sc - 0.15*t) or multi-criteria
    # Keep top 400 by score - 0.12*t and top 200 by score / (t + 10)
    next_beam.sort(key=lambda x: x[0] - 0.12 * x[1], reverse=True)
    beam = next_beam[:300]
    next_beam.sort(key=lambda x: x[0] / (x[1] + 5.0), reverse=True)
    seen = set((x[3], x[4]) for x in beam)
    for x in next_beam[:300]:
        if (x[3], x[4]) not in seen:
            beam.append(x)
            seen.add((x[3], x[4]))
    # actually filter invalid battery paths in beam
    valid_beam = []
    for x in beam:
        s_ok, t_ok, mb = eval_seq(x[5])
        if s_ok >= 0:
            valid_beam.append((s_ok, t_ok, mb, x[3], x[4], x[5]))
    beam = valid_beam[:350]
    if not beam:
        break

print(f"\nBest route on initial 38 targets (eff=0.8, 5% safety margin):")
print(f"  Score = {best_done[0]:.2f} / 98.0, end_tick = {best_done[2]:.1f}, min_bat = {best_done[3]:.1f}")
print("  Path:", " -> ".join(nodes[i][0] for i in best_done[1]))
