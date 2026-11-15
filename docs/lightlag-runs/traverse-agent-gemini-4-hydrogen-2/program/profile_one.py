import json, time, sys
sys.path.insert(0, "/tmp/opencode")
from sim_env import SimMission
from autopilot_core import Autopilot

world = json.load(open("/tmp/opencode/map.json"))
rules = json.load(open("/tmp/opencode/rules.json"))

t0 = time.time()
sim = SimMission(world, rules, seed=1)
bot = Autopilot(world, rules, seed=100)
print(f"Init time: {time.time()-t0:.2f}s", flush=True)

t_ingest = t_choose = t_sim = 0.0
safety_stops = missed_samples = 0
out_log = sim.advance(0)
while not out_log["episode_complete"]:
    cur_t = sim.tick
    force_replan = False
    if out_log["packets"]:
        ta = time.time()
        for p in out_log["packets"]:
            for ev in p["events"]:
                if ev["type"] == "safety_stop": safety_stops += 1
                elif ev["type"] == "sample_missed": missed_samples += 1
        m_info = sim.get_map()
        if bot.ingest_packets(out_log["packets"], m_info["targets"]):
            force_replan = True
        t_ingest += time.time() - ta

    if cur_t <= 416:
        ta = time.time()
        cmd = bot.choose_command(cur_t, force_replan=(cur_t == 0 or force_replan))
        t_choose += time.time() - ta
        if cmd is not None:
            acks = sim.uplink([cmd])
            for a in acks:
                bot.sent_commands[a["execute_tick"]] = a["command"]
                bot.last_reserved = max(bot.last_reserved, a["execute_tick"])
    ta = time.time()
    out_log = sim.advance(1)
    t_sim += time.time() - ta

sc, cred, mult = sim.final_score()
print(f"Score={sc:.3f} (cred={cred:.2f}, mult={mult}), eff={sim.solar_eff:.3f}/{bot.est.eff_est:.3f}, "
      f"sampled={len(sim.sampled)}, stops={safety_stops}, miss={missed_samples}", flush=True)
print(f"Times: ingest={t_ingest:.2f}s, choose={t_choose:.2f}s, sim={t_sim:.2f}s", flush=True)
print("Sampled:", sorted(sim.sampled.items(), key=lambda x: x[1]), flush=True)
