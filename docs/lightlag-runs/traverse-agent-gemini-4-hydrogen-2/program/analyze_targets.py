import json, math, heapq, sys
sys.path.insert(0, "/app")
from lightlag_surface import Surface, PHYSICS, TERRAIN_CODES, drive

world = json.load(open("/tmp/opencode/map.json"))
rules = json.load(open("/tmp/opencode/rules.json"))
surf = Surface(world["cell_m"], world["elevation_cm"], world["terrain"])

# Nominal mid-range slip_base
SLIP_MID = {k: 0.5 * (v[0] + v[1]) for k, v in PHYSICS["slip_base_ranges"].items()}
SLIP_WORST = {k: v[1] for k, v in PHYSICS["slip_base_ranges"].items()}

print("Nominal mid slip_base:", SLIP_MID)
print("Worst-case slip_base:", SLIP_WORST)

# Check which vertices / cells are safe
# Let's check for each target, what is the terrain and slope nearby
base = tuple(world["base"])
targets = world["targets"]

total_known_val = sum(t["value"] for t in targets)
print(f"Total initial target value: {total_known_val} across {len(targets)} targets")
print(f"Expected discoveries: {rules['map_generator']['discoveries']}")

# Compute a rough visibility/navigation graph on 5m grid centers (or vertices)
# Wait: cells are 5m x 5m. A rover moves up to 5m per tick.
# Let's compute travel time (ticks) from Base to every grid vertex using Dijkstra with 16-connected neighbors (or 8-connected)
# using actual drive() simulation for edges, or fast approximation!
# Wait: 121 x 81 = 9801 nodes. Let's test 8-connected or 16-connected Dijkstra from Base.
# Actually, let's check safe nodes first: a point (x, y) is safe if slope(x, y) <= max_tilt - margin.
# Wait: drive() checks slope at every 0.25m step!
# Let's check how fast Dijkstra on 5m vertices is with 16 directions, calling drive() or segment-checking.

def min_ticks_map(start_xy, slip_base, margin=0.02):
    nx, ny = surf.nx, surf.ny
    cell = surf.cell
    # grid nodes: (i, j) -> x=i*5, y=j*5
    # Wait: cell centers (i+0.5)*5 might be cleaner or vertices i*5. Let's use vertices (i*5, j*5).
    dist = [[1e9]*nx for _ in range(ny)]
    energy_at = [[1e9]*nx for _ in range(ny)]
    si = round(start_xy[0] / cell)
    sj = round(start_xy[1] / cell)
    dist[sj][si] = 0.0
    energy_at[sj][si] = 0.0
    pq = [(0.0, si, sj)]
    # 16 directions with step sizes 1 or 2 cells
    dirs = []
    for dx in range(-2, 3):
        for dy in range(-2, 3):
            if dx == 0 and dy == 0:
                continue
            if math.gcd(abs(dx), abs(dy)) == 1:
                dirs.append((dx, dy))
    max_tilt = PHYSICS["max_tilt"] - margin
    while pq:
        d, i, j = heapq.heappop(pq)
        if d > dist[j][i] + 1e-9:
            continue
        x0, y0 = i * cell, j * cell
        for dx, dy in dirs:
            ni, nj = i + dx, j + dy
            if not (0 <= ni < nx and 0 <= nj < ny):
                continue
            x1, y1 = ni * cell, nj * cell
            # Check straight line steps of 0.5m
            L = math.hypot(x1 - x0, y1 - y0)
            steps = int(math.ceil(L / 0.5))
            ok = True
            cost_ticks = 0.0
            e_cost = 0.0
            ux, uy = (x1 - x0) / L, (y1 - y0) / L
            prev_h = surf.h[j][i]
            for s in range(1, steps + 1):
                t = s / steps
                xm = x0 + (x1 - x0) * t
                ym = y0 + (y1 - y0) * t
                h, gx, gy, code = surf.sample(xm, ym)
                if math.hypot(gx, gy) > max_tilt:
                    ok = False
                    break
            if not ok:
                continue
            # Estimate effective speed per tick along this edge
            xm, ym = 0.5*(x0+x1), 0.5*(y0+y1)
            h0, gx0, gy0, code0 = surf.sample(x0, y0)
            hm, gxm, gym, codem = surf.sample(xm, ym)
            h1, gx1, gy1, code1 = surf.sample(x1, y1)
            for (gx, gy, code) in [(gx0, gy0, code0), (gxm, gym, codem)]:
                pass
            name = TERRAIN_CODES[codem]
            grade = gxm * ux + gym * uy
            slip = min(0.95, max(0.0, slip_base[name] + PHYSICS["slip_grade_gain"][name] * max(0.0, grade)))
            eff_speed = 5.0 * (1.0 - slip)
            dt = L / eff_speed
            nd = d + dt
            if nd < dist[nj][ni]:
                dist[nj][ni] = nd
                e_step = (L / (1.0 - slip)) * PHYSICS["drive_cost_per_wheel_m"][name] + PHYSICS["climb_cost_per_m"] * max(0.0, h1 - h0)
                energy_at[nj][ni] = energy_at[j][i] + e_step
                heapq.heappush(pq, (nd, ni, nj))
    return dist, energy_at

dist, e_at = min_ticks_map(base, SLIP_MID)
print("\nTargets sorted by estimated ticks from Base (300, 265):")
rows = []
for t in targets:
    ti = round(t["x"] / surf.cell)
    tj = round(t["y"] / surf.cell)
    dt = dist[tj][ti]
    ec = e_at[tj][ti]
    rows.append((dt, t["deadline_tick"] or 9999, -t["value"], t, ec))
for dt, dl, nv, t, ec in sorted(rows):
    feasible = "ON_TIME" if (t["deadline_tick"] is None or dt + 5 <= t["deadline_tick"]) else "LATE!!!"
    print(f"  {t['id']:3s} ({t['x']:5.1f},{t['y']:5.1f}) val={t['value']} dl={str(t['deadline_tick']):>4s} "
          f"ticks_from_base={dt:5.1f} e={ec:5.1f} {feasible}")
