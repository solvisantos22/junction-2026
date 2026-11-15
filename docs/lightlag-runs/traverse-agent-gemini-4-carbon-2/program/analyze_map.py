import json
import math
import sys
sys.path.insert(0, "/app")
from lightlag_surface import Surface, TERRAIN_CODES, PHYSICS

with open("/tmp/opencode/rules.json") as f:
    rules = json.load(f)
with open("/tmp/opencode/map.json") as f:
    world = json.load(f)

surf = Surface(world["cell_m"], world["elevation_cm"], world["terrain"])
print(f"Grid: nx={surf.nx}, ny={surf.ny}, width={surf.width}, height={surf.height}, cell={surf.cell}")
print(f"Base: {world['base']}")

# Elevation stats
elevs = [h for row in surf.h for h in row]
print(f"Elevation min={min(elevs):.2f}m, max={max(elevs):.2f}m")

# Terrain counts and slope stats
from collections import Counter
t_counts = Counter(c for row in surf.codes for c in row)
total_cells = (surf.nx - 1) * (surf.ny - 1)
for k, v in t_counts.items():
    print(f"Terrain {TERRAIN_CODES[k]} ({k}): {v} ({100*v/total_cells:.1f}%)")

max_tilt = rules["physics"]["max_tilt"]
steep_cells = 0
near_steep_cells = 0
for j in range(surf.ny - 1):
    for i in range(surf.nx - 1):
        ms = surf.cell_max_slope(i, j)
        if ms > max_tilt:
            steep_cells += 1
        elif ms > 0.30:
            near_steep_cells += 1
print(f"Cells with max_slope > {max_tilt}: {steep_cells}/{total_cells} ({100*steep_cells/total_cells:.1f}%)")
print(f"Cells with max_slope in (0.30, {max_tilt}]: {near_steep_cells}/{total_cells}")

# ASCII visualization of map (downsampled to 120 x 80 = exact 1 cell per char! Wait: 600/5 = 120, 400/5 = 80!)
# Let's print 120x80 ASCII map (maybe 120 wide by 40 tall, combining 2 y-cells per row, or full 80 rows!)
target_cells = {}
for t in world["targets"]:
    ci = int(t["x"] / 5.0)
    cj = int(t["y"] / 5.0)
    target_cells[(ci, cj)] = t["id"]

bi, bj = int(world["base"][0] / 5.0), int(world["base"][1] / 5.0)

print("\n--- MAP (y from top=395 down to 0, x from 0 to 595, step 5m) ---")
print("Legend: # = steep (>0.36), ! = >0.30, s = sand, k = rocks, b = bedrock, . = regolith, B = BASE, * = target")
for j in range(surf.ny - 2, -1, -2):
    row_chars = []
    for i in range(surf.nx - 1):
        # check j and j-1
        ch = None
        if (i, j) == (bi, bj) or (i, j-1) == (bi, bj):
            ch = 'B'
        elif (i, j) in target_cells or (i, j-1) in target_cells:
            ch = '*'
        else:
            ms = max(surf.cell_max_slope(i, j), surf.cell_max_slope(i, max(0, j-1)))
            if ms > max_tilt:
                ch = '#'
            elif ms > 0.30:
                ch = '!'
            else:
                c = surf.codes[j][i]
                ch = '.' if c == 'r' else c
        row_chars.append(ch)
    y_m = j * 5
    print(f"{y_m:3d} " + "".join(row_chars))

# Solar budget
for eff in [0.8, 0.9, 1.0]:
    tot_solar = sum(2.8 * eff * math.sin(math.pi * (t + 56) / (420 + 112)) for t in range(1, 421))
    print(f"Eff={eff}: total solar over 420 ticks = {tot_solar:.1f}, minus idle ({420*0.15:.1f}) = {tot_solar - 420*0.15:.1f}, plus init 100 = {tot_solar - 420*0.15 + 100:.1f}")

# Targets summary
tot_val = sum(t["value"] for t in world["targets"])
print(f"\nInitial 38 targets total value: {tot_val}")
for t in sorted(world["targets"], key=lambda x: (x["deadline_tick"] is None, x["deadline_tick"] or 9999)):
    dist_base = math.hypot(t["x"] - world["base"][0], t["y"] - world["base"][1])
    h_t = surf.elevation(t["x"], t["y"])
    sl_t = surf.slope(t["x"], t["y"])
    ter_t = surf.terrain(t["x"], t["y"])
    print(f"{t['id']:>3s}: ({t['x']:5.1f}, {t['y']:5.1f}) val={t['value']} dl={str(t['deadline_tick']):>4s} dist_base={dist_base:5.1f}m elev={h_t:5.2f}m slope={sl_t:.3f} ter={ter_t}")
