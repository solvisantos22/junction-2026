import json, math, sys
sys.path.insert(0, "/tmp/opencode")
from sim_env import SimMission
from autopilot_core import Autopilot

world = json.load(open("/tmp/opencode/map.json"))
rules = json.load(open("/tmp/opencode/rules.json"))

for seed in (1, 2):
    sim = SimMission(world, rules, seed=seed)
    bot = Autopilot(world, rules, seed=seed * 100)
    out_log = sim.advance(0)
    wait_ticks = []
    miss_info = []
    while not out_log["episode_complete"]:
        cur_t = sim.tick
        force_replan = False
        if out_log["packets"]:
            for p in out_log["packets"]:
                for ev in p["events"]:
                    if ev["type"] == "sample_missed":
                        miss_info.append((p["tick"], sim.x, sim.y))
            m_info = sim.get_map()
            if bot.ingest_packets(out_log["packets"], m_info["targets"]):
                force_replan = True
        if cur_t <= 416:
            cmd = bot.choose_command(cur_t, force_replan=(cur_t == 0 or force_replan))
            if cmd is not None:
                if cmd["action"] == "wait":
                    wait_ticks.append(cur_t + 4)
                acks = sim.uplink([cmd])
                for a in acks:
                    bot.sent_commands[a["execute_tick"]] = a["command"]
                    bot.last_reserved = max(bot.last_reserved, a["execute_tick"])
        out_log = sim.advance(1)
    sc, cred, mult = sim.final_score()
    print(f"Seed {seed}: score={sc:.3f} cred={cred:.2f} mult={mult} eff={sim.solar_eff:.3f}")
    print(f"  waits ({len(wait_ticks)}): {wait_ticks[:25]} ... {wait_ticks[-10:] if len(wait_ticks)>25 else []}")
    print(f"  misses: {miss_info}")
    print(f"  sampled: {sorted(sim.sampled.items(), key=lambda x: x[1])}")
