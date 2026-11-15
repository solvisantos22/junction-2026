import json, math, heapq, sys
sys.path.insert(0, "/app")
from lightlag_surface import Surface, PHYSICS

world = json.load(open("/tmp/opencode/map.json"))
surf = Surface(world["cell_m"], world["elevation_cm"], world["terrain"])

# Check clearance of every target from slope > 0.36
print("Target clearances to slope > 0.36:")
for t in world["targets"]:
    min_d = 999.0
    tx, ty = t["x"], t["y"]
    for dx in range(-20, 21):
        for dy in range(-20, 21):
            x, y = tx + dx * 0.5, ty + dy * 0.5
            if surf.inside(x, y) and surf.slope(x, y) > PHYSICS["max_tilt"]:
                min_d = min(min_d, math.hypot(dx*0.5, dy*0.5))
    if min_d < 8.0:
        print(f"  {t['id']:3s} ({tx:.1f},{ty:.1f}) slope_here={surf.slope(tx,ty):.3f} dist_to_steep={min_d:.1f}m")

# Check minimum distance from each grid vertex to slope > 0.36
# Only check within 15m
steep_pts = []
for j in range(0, int(surf.height * 2) + 1):
    y = j * 0.5
    for i in range(0, int(surf.width * 2) + 1):
        x = i * 0.5
        if surf.slope(x, y) > PHYSICS["max_tilt"]:
            steep_pts.append((x, y))
print(f"Total 0.5m sample points with slope > 0.36: {len(steep_pts)}")

# Check reachability from BASE with different clearance radii (0m, 1.5m, 2.5m, 3.5m)
for buf in [0.0, 1.5, 2.5, 3.5]:
    # Build quick grid of safe vertices
    # Fast check: check 8 points around vertex at distance buf + center
    safe = [[True]*surf.nx for _ in range(surf.ny)]
    for j in range(surf.ny):
        y = j * surf.cell
        for i in range(surf.nx):
            x = i * surf.cell
            if surf.slope(x, y) > 0.34:
                safe[j][i] = False
                continue
            if buf > 0:
                ok = True
                for ang_k in range(12):
                    ang = 2 * math.pi * ang_k / 12
                    for r in (buf * 0.5, buf):
                        px, py = x + r * math.cos(ang), y + r * math.sin(ang)
                        if not surf.inside(px, py) or surf.slope(px, py) > PHYSICS["max_tilt"]:
                            ok = False
                            break
                    if not ok: break
                safe[j][i] = ok
    # BFS from base
    bi, bj = round(world["base"][0]/5), round(world["base"][1]/5)
    vis = [[False]*surf.nx for _ in range(surf.ny)]
    q = [(bi, bj)]
    vis[bj][bi] = True
    while q:
        ci, cj = q.pop()
        for dx, dy in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(1,-1),(-1,1),(1,1)]:
            ni, nj = ci+dx, cj+dy
            if 0 <= ni < surf.nx and 0 <= nj < surf.ny and not vis[nj][ni] and safe[nj][ni]:
                vis[nj][ni] = True
                q.append((ni, nj))
    unreach = []
    for t in world["targets"]:
        ti, tj = round(t["x"]/5), round(t["y"]/5)
        if not vis[tj][ti]:
            unreach.append(t["id"])
    print(f"Clearance {buf:.1f}m: reachable vertices={sum(sum(r) for r in vis)}, unreachable targets={unreach}")
