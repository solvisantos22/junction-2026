import json
import math
import sys
import time

sys.path.insert(0, "/app")
sys.path.insert(0, "/tmp/opencode")

from lightlag_client import connect, RemoteToolError
from autopilot_core import Autopilot

def main():
    t_start = time.time()
    print("Connecting to http://lightlag:8000/mcp ...", flush=True)
    with connect("http://lightlag:8000/mcp") as tools:
        rules = tools.rules()
        world = tools.map()
        tlog = tools.telemetry_log()
        print(f"Loaded map ({world['width']}x{world['height']}, {len(world['targets'])} targets), "
              f"initial log len={len(tlog)}, tick={tlog[-1]['tick']}", flush=True)

        t0 = time.time()
        bot = Autopilot(world, rules, seed=42)
        print(f"Autopilot initialized in {time.time() - t0:.2f}s", flush=True)

        cur_t = tlog[-1]["tick"]
        bot.ingest_packets(tlog, world["targets"])
        episode_complete = (cur_t >= rules["max_ticks"])

        while not episode_complete:
            force_replan = (cur_t == 0)
            if cur_t <= rules["max_ticks"] - rules["delay_ticks"] - 1:
                cmd = bot.choose_command(cur_t, force_replan=force_replan)
                if cmd is not None:
                    try:
                        acks = tools.uplink([cmd])
                        for a in acks:
                            bot.sent_commands[a["execute_tick"]] = a["command"]
                            bot.last_reserved = max(bot.last_reserved, a["execute_tick"])
                    except RemoteToolError as e:
                        print(f"[WARN] uplink rejected at tick {cur_t}: {e} (cmd={cmd})", flush=True)
                step_n = 1
            else:
                step_n = min(rules["max_advance_ticks"], rules["max_ticks"] - cur_t)
                if step_n <= 0:
                    break

            out = tools.advance(step_n)
            cur_t = out["current_tick"]
            episode_complete = out["episode_complete"]
            pkts = out.get("packets", [])

            if pkts:
                has_discovery = any(
                    "discover" in str(ev).lower()
                    for p in pkts for ev in p.get("events", [])
                )
                world_targets = tools.map()["targets"] if (has_discovery or cur_t % 25 == 0) else None
                need_replan = bot.ingest_packets(pkts, world_targets)

                for p in pkts:
                    for ev in p.get("events", []):
                        print(f"[EVENT @ tick {p['tick']} recv {cur_t}] {ev}", flush=True)

                if need_replan and cur_t <= rules["max_ticks"] - rules["delay_ticks"] - 1:
                    t_exec = max(cur_t + rules["delay_ticks"] + 1, bot.last_reserved + 1)
                    if t_exec <= rules["max_ticks"]:
                        xp, yp, _, bp, _ = bot.est.predict_state(t_exec, bot.sent_commands)
                        bot.replan(t_exec, xp, yp, bp)

            if cur_t % 25 == 0 or episode_complete:
                mx, my, mb = bot.est.mean_state()
                goal = bot.current_route[0] if bot.current_route else "BASE"
                print(
                    f"[tick {cur_t:3d}] est=({mx:5.1f},{my:5.1f},bias={mb:+4.2f}) "
                    f"bat={bot.est.last_bat:5.1f} eff={bot.est.eff_est:.3f}(known={bot.est.eff_known}) "
                    f"sampled={len(bot.est.sampled_ids)} goal={goal} "
                    f"route_len={len(bot.current_route)} elapsed={time.time()-t_start:.1f}s",
                    flush=True
                )

        # Final telemetry summary
        final_log = tools.telemetry_log()
        final_map = tools.map()
        with open("/tmp/opencode/final_telemetry.json", "w") as f:
            json.dump(final_log, f)
        with open("/tmp/opencode/final_map.json", "w") as f:
            json.dump(final_map, f)

        last_pkt = final_log[-1]
        sampled = set(last_pkt["sampled_targets"])
        sample_ticks = {}
        prev_s = set()
        for p in final_log:
            cur_s = set(p.get("sampled_targets", []))
            for tid in cur_s - prev_s:
                sample_ticks[tid] = p["tick"]
            prev_s = cur_s

        all_targets = {t["id"]: t for t in final_map["targets"]}
        credited = 0.0
        for tid in sampled:
            tinfo = all_targets.get(tid)
            if tinfo:
                st = sample_ticks.get(tid, 999)
                if tinfo["deadline_tick"] is None or st <= tinfo["deadline_tick"]:
                    credited += tinfo["value"]
                else:
                    credited += tinfo["late_value"]
        total_known_val = sum(t["value"] for t in final_map["targets"])
        mx, my, _ = bot.est.mean_state()
        dist_base = math.hypot(mx - world["base"][0], my - world["base"][1])
        print("\n=== MISSION COMPLETE ===", flush=True)
        print(f"Tick: {last_pkt['tick']}, Alive: {last_pkt['alive']}, Battery: {last_pkt['battery']:.2f}", flush=True)
        print(f"Final est pos: ({mx:.2f}, {my:.2f}), dist to base: {dist_base:.2f}m (base_radius={rules['base_radius']})", flush=True)
        print(f"Sampled {len(sampled)} targets: {sorted(sample_ticks.items(), key=lambda x: x[1])}", flush=True)
        print(f"Estimated credited value: {credited:.2f} / {total_known_val:.2f} (ratio={credited/total_known_val:.3f})", flush=True)
        print(f"Learned eff: {bot.est.eff_est:.4f}, slip: { {k: round(v, 4) for k, v in bot.est.slip_est().items()} }", flush=True)

if __name__ == "__main__":
    main()
