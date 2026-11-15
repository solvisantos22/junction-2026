import json, math, time, sys
sys.path.insert(0, "/tmp/opencode")
from sim_env import SimMission
from autopilot_core import Autopilot, PHYSICS

world = json.load(open("/tmp/opencode/map.json"))
rules = json.load(open("/tmp/opencode/rules.json"))

t0 = time.time()
base_bot = Autopilot(world, rules, seed=1)
precomp = (base_bot.surf, base_bot.nav, base_bot.dist_t, base_bot.dist_e)
print(f"Precomputed once in {time.time()-t0:.2f}s", flush=True)

def run_one(seed, force_eff=None, force_max_slip=False):
    t1 = time.time()
    sim = SimMission(world, rules, seed=seed)
    if force_eff is not None:
        sim.solar_eff = force_eff
    if force_max_slip:
        sim.slip_base = {k: v[1] for k, v in PHYSICS["slip_base_ranges"].items()}
    bot = Autopilot(world, rules, seed=seed * 100, precomputed=precomp)
    waits_chosen = 0
    out_log = sim.advance(0)
    arrive_base_tick = None
    while not out_log["episode_complete"]:
        cur_t = sim.tick
        force_replan = False
        if out_log["packets"]:
            m_info = sim.get_map()
            if bot.ingest_packets(out_log["packets"], m_info["targets"]):
                force_replan = True
        if cur_t <= 416:
            cmd = bot.choose_command(cur_t, force_replan=(cur_t == 0 or force_replan))
            if cmd is not None:
                if cmd["action"] == "wait":
                    waits_chosen += 1
                acks = sim.uplink([cmd])
                for a in acks:
                    bot.sent_commands[a["execute_tick"]] = a["command"]
                    bot.last_reserved = max(bot.last_reserved, a["execute_tick"])
        out_log = sim.advance(1)
        if arrive_base_tick is None and sim.tick > 350 and math.hypot(sim.x - sim.base[0], sim.y - sim.base[1]) <= 4.0:
            arrive_base_tick = sim.tick
    sc, cred, mult = sim.final_score()
    min_bat = min(p["battery"] for p in sim.packets)
    stops = sum(1 for p in sim.packets for e in p["events"] if e["type"] == "safety_stop")
    misses = sum(1 for p in sim.packets for e in p["events"] if e["type"] == "sample_missed")
    print(f"seed={seed} eff={sim.solar_eff:.2f} max_slip={str(force_max_slip):5s}: score={sc:.3f} cred={cred:5.2f} mult={mult} "
          f"sampled={len(sim.sampled):2d} waits={waits_chosen:2d} min_bat={min_bat:4.1f} stops={stops} miss={misses} base_t={str(arrive_base_tick):>4s} ({time.time()-t1:.1f}s)", flush=True)
    return sc, mult, stops, misses

res = []
res.append(run_one(1, force_eff=0.80, force_max_slip=True))
res.append(run_one(2, force_eff=0.80, force_max_slip=True))
for s in range(1, 4):
    res.append(run_one(s))
print("Mean score:", sum(r[0] for r in res)/len(res), "All mult=1?", all(r[1]==1.0 for r in res), "Total stops:", sum(r[2] for r in res), "Total misses:", sum(r[3] for r in res))
