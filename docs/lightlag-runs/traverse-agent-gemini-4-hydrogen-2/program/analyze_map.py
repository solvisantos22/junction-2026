import json, math, sys
sys.path.insert(0, "/app")
from lightlag_surface import Surface, PHYSICS, TERRAIN_CODES

world = json.load(open("/tmp/opencode/map.json"))
rules = json.load(open("/tmp/opencode/rules.json"))
surf = Surface(world["cell_m"], world["elevation_cm"], world["terrain"])

print(f"Grid: nx={surf.nx}, ny={surf.ny}, width={surf.width}, height={surf.height}, cell={surf.cell}")

# Terrain counts and blocked cells
terrain_counts = {}
blocked_cells = 0
for j in range(surf.ny - 1):
    for i in range(surf.nx - 1):
        c = surf.codes[j][i]
        terrain_counts[c] = terrain_counts.get(c, 0) + 1
        if surf.cell_max_slope(i, j) > PHYSICS["max_tilt"]:
            blocked_cells += 1

print("Terrain cell counts:", {TERRAIN_CODES[k]: v for k, v in terrain_counts.items()})
print(f"Cells with cell_max_slope > max_tilt: {blocked_cells} / {(surf.nx-1)*(surf.ny-1)}")

# Check targets: are any inside or near steep ground?
for t in world["targets"]:
    h, gx, gy, code = surf.sample(t["x"], t["y"])
    s = math.hypot(gx, gy)
    if s > 0.25:
        print(f"  High slope target {t['id']}: slope={s:.3f} at ({t['x']}, {t['y']})")

# Print ASCII map (120x40, grouping 2 y-cells per char)
chars_map = []
target_cells = {}
for t in world["targets"]:
    ci = int(t["x"] / surf.cell)
    cj = int(t["y"] / surf.cell)
    target_cells[(ci, cj)] = t["id"]

bi = int(world["base"][0] / surf.cell)
bj = int(world["base"][1] / surf.cell)

print("\nASCII Map (y from top=400 down to 0, x from 0 to 600, each row = 10m, col = 5m):")
for row_pair in range((surf.ny - 1) // 2 - 1, -1, -1):
    j1 = row_pair * 2 + 1
    j0 = row_pair * 2
    line = []
    for i in range(surf.nx - 1):
        if (i == bi and (j0 == bj or j1 == bj)):
            line.append("B")
        elif (i, j1) in target_cells or (i, j0) in target_cells:
            line.append("*")
        elif surf.cell_max_slope(i, j1) > PHYSICS["max_tilt"] or surf.cell_max_slope(i, j0) > PHYSICS["max_tilt"]:
            line.append("#")
        else:
            c = surf.codes[j0][i]
            line.append("." if c == "r" else ("," if c == "b" else ("~" if c == "s" else "^")))
    print(f"{j1*5:3d}|" + "".join(line))

# Solar budget calculation
total_solar_min = 0.0
total_solar_max = 0.0
max_ticks = rules["max_ticks"]
margin = rules["sun_margin_ticks"]
peak = rules["solar_peak"]
for tick in range(1, max_ticks + 1):
    s = peak * math.sin(math.pi * (tick + margin) / (max_ticks + 2 * margin))
    total_solar_min += s * rules["solar_efficiency_range"][0]
    total_solar_max += s * rules["solar_efficiency_range"][1]
idle_total = rules["idle_cost"] * max_ticks
print(f"\nEnergy budget over {max_ticks} ticks:")
print(f"  Initial battery: {rules['initial_battery']}")
print(f"  Solar gain (eff 0.8..1.0): {total_solar_min:.1f} .. {total_solar_max:.1f}")
print(f"  Idle cost: {idle_total:.1f}")
print(f"  Net energy before drive/sample (eff 0.8..1.0): {rules['initial_battery'] + total_solar_min - idle_total:.1f} .. {rules['initial_battery'] + total_solar_max - idle_total:.1f}")
print(f"  Solar at tick 1 (eff=0.8): {peak*0.8*math.sin(math.pi*(1+margin)/(max_ticks+2*margin)):.2f}, at tick 210: {peak*0.8:.2f}, at tick 420: {peak*0.8*math.sin(math.pi*(420+margin)/(max_ticks+2*margin)):.2f}")
