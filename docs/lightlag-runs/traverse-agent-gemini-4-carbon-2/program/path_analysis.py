import json
import math
import heapq
import time
import sys
sys.path.insert(0, "/app")
from lightlag_surface import Surface, TERRAIN_CODES, PHYSICS, drive

with open("/tmp/opencode/rules.json") as f:
    rules = json.load(f)
with open("/tmp/opencode/map.json") as f:
    world = json.load(f)

surf = Surface(world["cell_m"], world["elevation_cm"], world["terrain"])
max_tilt = PHYSICS["max_tilt"]

# Nominal midpoint slip_base
MID_SLIP = {k: 0.5 * (v[0] + v[1]) for k, v in PHYSICS["slip_base_ranges"].items()}
print("Midpoint slip_base:", MID_SLIP)

# Check min distance from each target (and base) to any steep cell (cell_max_slope > 0.36)
steep_pts = []
for j in range(surf.ny - 1):
    for i in range(surf.nx - 1):
        if surf.cell_max_slope(i, j) > 0.34:
            # sample subgrid
            for sj in range(3):
                for si in range(3):
                    px = (i + si * 0.5) * 5.0
                    py = (j + sj * 0.5) * 5.0
                    if surf.slope(px, py) > 0.35:
                        steep_pts.append((px, py))

print(f"Found {len(steep_pts)} steep sample points (>0.35)")

for t in world["targets"]:
    tx, ty = t["x"], t["y"]
    min_d = min(math.hypot(tx - sx, ty - sy) for sx, sy in steep_pts)
    if min_d < 15.0:
        print(f"Target {t['id']} ({tx},{ty}) val={t['value']} is {min_d:.1f}m from steep slope!")

bx, by = world["base"]
print(f"Base ({bx},{by}) min dist to steep: {min(math.hypot(bx - sx, by - sy) for sx, sy in steep_pts):.1f}m")

# Build a 5m grid graph (121 x 81 = 9801 nodes) with 16-neighbor transitions (dx, dy in {-2,-1,0,1,2} with gcd=1)
# Wait: 16 directions on 5m grid has edge lengths: 5m, 7.07m, 11.18m!
# Using 16 directions makes headings smooth (every ~22.5 deg) and avoids grid Manhattan bias!
t0 = time.time()
NX, NY = surf.nx, surf.ny  # 121, 81

# Precompute clearance from steep (>0.355) for every vertex on 2.5m subgrid
# Let's compute a clearance map on 2.5m grid (241 x 161) using BFS!
SNX, SNY = (NX - 1) * 2 + 1, (NY - 1) * 2 + 1  # 241 x 161
INF = 1e9
clearance = [INF] * (SNX * SNY)
from collections import deque
q = deque()
for sj in range(SNY):
    py = sj * 2.5
    for si in range(SNX):
        px = si * 2.5
        # also treat map border < 2.5m as boundary hazard
        if px <= 0.0 or px >= 600.0 or py <= 0.0 or py >= 400.0 or surf.slope(px, py) > 0.355:
            idx = sj * SNX + si
            clearance[idx] = 0.0
            q.append((si, sj))

# Approximate Euclidean distance transform via 8-neighbor Dijkstra/BFS
hq = []
for si, sj in q:
    heapq.heappush(hq, (0.0, si, sj))
while hq:
    d, si, sj = heapq.heappop(hq)
    if d > clearance[sj * SNX + si] + 1e-6:
        continue
    if d > 15.0:
        continue
    for di, dj, step_d in [(-1,0,2.5),(1,0,2.5),(0,-1,2.5),(0,1,2.5),(-1,-1,3.5355),(-1,1,3.5355),(1,-1,3.5355),(1,1,3.5355)]:
        ni, nj = si + di, sj + dj
        if 0 <= ni < SNX and 0 <= nj < SNY:
            nd = d + step_d
            nidx = nj * SNX + ni
            if nd < clearance[nidx]:
                clearance[nidx] = nd
                heapq.heappush(hq, (nd, ni, nj))

print(f"Clearance map computed in {time.time() - t0:.3f}s")

def get_clearance(x, y):
    si = min(SNX - 1, max(0, int(round(x / 2.5))))
    sj = min(SNY - 1, max(0, int(round(y / 2.5))))
    return clearance[sj * SNX + si]

for t in world["targets"]:
    c = get_clearance(t["x"], t["y"])
    if c < 10.0:
        print(f"  Target {t['id']} clearance = {c:.2f}m")

# Build directed graph on 5m vertices (121 x 81) where clearance >= 4.0m
# For each directed edge (u -> v), compute exact ticks (wheel_m / 5.0) and energy needed!
DIRS = [
    (1, 0), (-1, 0), (0, 1), (0, -1),
    (1, 1), (1, -1), (-1, 1), (-1, -1),
    (2, 1), (2, -1), (-2, 1), (-2, -1),
    (1, 2), (1, -2), (-1, 2), (-1, -2),
]

t1 = time.time()
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
            # Check intermediate points along segment every 1.25m for clearance and integrate ticks & energy
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
                slip = MID_SLIP[tname] + PHYSICS["slip_grade_gain"][tname] * max(0.0, grade)
                slip = max(0.0, min(0.90, slip))
                # To move ground distance ds, wheel metres needed = ds / (1 - slip)
                # (plus slight cosine correction for cross-slope crabbing, very small)
                wheel_m = ds / (1.0 - slip)
                ticks_est += wheel_m / 5.0
                energy_est += wheel_m * PHYSICS["drive_cost_per_wheel_m"][tname] + PHYSICS["climb_cost_per_m"] * max(0.0, h_end - prev_h)
                prev_h = h_end
            if ok:
                v = nj * NX + ni
                # Weight = ticks_est + small penalty for extra energy to prefer bedrock/regolith over sand/rocks
                adj[u].append((v, ticks_est, energy_est))

print(f"Graph built in {time.time() - t1:.3f}s")

# Note: all targets and base have coordinates that are multiples of 5.0! Let's verify!
all_mult_5 = all(t["x"] % 5 == 0 and t["y"] % 5 == 0 for t in world["targets"])
print("All initial targets on 5m grid:", all_mult_5)

# Compute all-pairs shortest paths (in ticks, and also hybrid cost = ticks + 0.12 * energy) among Base + 38 targets!
nodes_of_interest = [("BASE", world["base"][0], world["base"][1])] + [(t["id"], t["x"], t["y"]) for t in world["targets"]]
node_ids = [int(round(y / 5.0)) * NX + int(round(x / 5.0)) for _, x, y in nodes_of_interest]

t2 = time.time()
N_POI = len(nodes_of_interest)
dist_ticks = [[INF] * N_POI for _ in range(N_POI)]
dist_energy = [[INF] * N_POI for _ in range(N_POI)]

for idx_src in range(N_POI):
    src_u = node_ids[idx_src]
    best_cost = [INF] * (NX * NY)
    best_t = [INF] * (NX * NY)
    best_e = [INF] * (NX * NY)
    best_cost[src_u] = 0.0
    best_t[src_u] = 0.0
    best_e[src_u] = 0.0
    pq = [(0.0, src_u)]
    while pq:
        c, u = heapq.heappop(pq)
        if c > best_cost[u] + 1e-9:
            continue
        bt, be = best_t[u], best_e[u]
        for v, dt, de in adj[u]:
            # slight energy weight 0.08 ticks per energy so rover strongly avoids sand/rocks/climbs when ticks are similar!
            nc = c + dt + 0.08 * de
            if nc < best_cost[v]:
                best_cost[v] = nc
                best_t[v] = bt + dt
                best_e[v] = be + de
                heapq.heappush(pq, (nc, v))
    for idx_dst in range(N_POI):
        dst_u = node_ids[idx_dst]
        dist_ticks[idx_src][idx_dst] = best_t[dst_u]
        dist_energy[idx_src][idx_dst] = best_e[dst_u]

print(f"All-pairs Dijkstra ({N_POI} POIs) done in {time.time() - t2:.3f}s")
for idx, (name, x, y) in enumerate(nodes_of_interest[1:], 1):
    t_obj = world["targets"][idx - 1]
    print(f"BASE -> {name:>3s} ({x:5.1f},{y:5.1f}) val={t_obj['value']} dl={str(t_obj['deadline_tick']):>4s}: {dist_ticks[0][idx]:5.1f} ticks, {dist_energy[0][idx]:5.1f} energy | return: {dist_ticks[idx][0]:5.1f}t, {dist_energy[idx][0]:5.1f}e")
