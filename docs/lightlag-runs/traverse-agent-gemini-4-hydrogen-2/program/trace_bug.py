import json, math, sys
sys.path.insert(0, "/tmp/opencode")
from sim_env import SimMission
from autopilot_core import Autopilot

world = json.load(open("/tmp/opencode/map.json"))
rules = json.load(open("/tmp/opencode/rules.json"))

# Trace Seed 1 around ticks 235..295 and Seed 2 around ticks 120..145
for seed, t_lo, t_hi in [(1, 230, 295), (2, 120, 145)]:
    print(f"=== SEED {seed} ===")
    sim = SimMission(world, rules, seed=seed)
    bot = Autopilot(world, rules, seed=seed * 100)
    out_log = sim.advance(0)
    while not out_log["episode_complete"]:
        cur_t = sim.tick
        force_replan = False
        if out_log["packets"]:
            m_info = sim.get_map()
            if bot.ingest_packets(out_log["packets"], m_info["targets"]):
                force_replan = True
        if cur_t <= 416:
            cmd = bot.choose_command(cur_t, force_replan=(cur_t == 0 or force_replan))
            if t_lo <= cur_t + 4 <= t_hi:
                mx, my, mb = bot.est.mean_state()
                px, py, pb, pbat, cloud = bot.est.predict_state(cur_t + 4, bot.sent_commands)
                pstd = math.sqrt(sum((p[0]-px)**2 + (p[1]-py)**2 for p in cloud)/len(cloud))
                goal = bot.current_route[0] if bot.current_route else "BASE"
                print(f"  t={cur_t}->exec={cur_t+4} goal={goal} cmd={cmd} | true@t=({sim.x:.1f},{sim.y:.1f},b={sim.heading_bias:.1f},bat={sim.battery:.1f}) "
                      f"| est@obs({bot.est.last_pkt_tick})=({mx:.1f},{my:.1f},b={mb:.1f}) | pred@exec=({px:.1f},{py:.1f},std={pstd:.2f},bat={pbat:.1f})")
            if cmd is not None:
                acks = sim.uplink([cmd])
                for a in acks:
                    bot.sent_commands[a["execute_tick"]] = a["command"]
                    bot.last_reserved = max(bot.last_reserved, a["execute_tick"])
        out_log = sim.advance(1)
