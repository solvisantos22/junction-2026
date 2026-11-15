import json, math, time, sys
sys.path.insert(0, "/tmp/opencode")
from sim_env import SimMission
from autopilot_core import Autopilot

world = json.load(open("/tmp/opencode/map.json"))
rules = json.load(open("/tmp/opencode/rules.json"))

scores = []
for seed in range(1, 4):
    t0 = time.time()
    sim = SimMission(world, rules, seed=seed)
    bot = Autopilot(world, rules, seed=seed * 100)

    safety_stops = 0
    missed_samples = 0
    out_log = sim.advance(0)
    while not out_log["episode_complete"]:
        cur_t = sim.tick
        force_replan = False
        if out_log["packets"]:
            for p in out_log["packets"]:
                for ev in p["events"]:
                    if ev["type"] == "safety_stop":
                        safety_stops += 1
                    elif ev["type"] == "sample_missed":
                        missed_samples += 1
            m_info = sim.get_map()
            if bot.ingest_packets(out_log["packets"], m_info["targets"]):
                force_replan = True

        if cur_t <= 416:
            cmd = bot.choose_command(cur_t, force_replan=(cur_t == 0 or force_replan))
            if cmd is not None:
                acks = sim.uplink([cmd])
                for a in acks:
                    bot.sent_commands[a["execute_tick"]] = a["command"]
                    bot.last_reserved = max(bot.last_reserved, a["execute_tick"])
        out_log = sim.advance(1)

    sc, cred, mult = sim.final_score()
    pos_err = math.hypot(bot.est.mean_state()[0] - sim.x, bot.est.mean_state()[1] - sim.y)
    bias_err = abs(bot.est.mean_state()[2] - sim.heading_bias)
    dt = time.time() - t0
    scores.append(sc)
    print(f"Seed {seed:2d}: score={sc:.3f} (cred={cred:5.2f}, mult={mult:.1f}) eff={sim.solar_eff:.3f}/{bot.est.eff_est:.3f} "
          f"sampled={len(sim.sampled):2d} stops={safety_stops} miss={missed_samples} "
          f"pos_err={pos_err:.2f}m bias_err={bias_err:.2f}deg time={dt:.2f}s")

print(f"\nMean score across 10 seeds: {sum(scores)/len(scores):.3f}, min={min(scores):.3f}, max={max(scores):.3f}")
