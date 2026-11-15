import json
from lightlag_client import connect
from lightlag_surface import Surface

with connect("http://lightlag:8000/mcp") as tools:
    rules = tools.rules()
    world = tools.map()
    tlog = tools.telemetry_log()

with open("/tmp/opencode/map.json", "w") as f:
    json.dump(world, f)
with open("/tmp/opencode/rules.json", "w") as f:
    json.dump(rules, f)
with open("/tmp/opencode/tlog0.json", "w") as f:
    json.dump(tlog, f)

print("Map keys:", list(world.keys()))
print("Width:", world["width"], "Height:", world["height"], "cell_m:", world["cell_m"])
print("Lander:", world["lander"])
print("Num targets:", len(world["targets"]))
print("Terrain codes:", world["terrain_codes"])
for t in sorted(world["targets"], key=lambda x: (x["deadline_tick"] or 9999, -x["value"])):
    print(f"  T{t['id']:02d}: ({t['x']:.1f}, {t['y']:.1f}) val={t['value']} late={t['late_value']} dl={t['deadline_tick']} app={t['appear_tick']}")
