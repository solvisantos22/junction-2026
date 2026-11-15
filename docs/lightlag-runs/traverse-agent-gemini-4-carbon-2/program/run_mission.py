#!/usr/bin/env python3
from __future__ import annotations

import math
import sys
import time

sys.path.insert(0, "/app")
sys.path.insert(0, "/tmp/opencode")

from lightlag_client import connect
from autopilot_core import RoverAutopilot


def main() -> None:
    t0 = time.time()
    with connect("http://lightlag:8000/mcp") as tools:
        rules = tools.rules()
        world = tools.map()
        pilot = RoverAutopilot(rules, world, verbose=True)
        summary = pilot.run_episode(tools)

        # Final verification check of episode status and telemetry
        final_log = tools.telemetry_log()
        final_map = tools.map()
        last_pkt = final_log[-1] if final_log else {}
        bx, by = world["base"]
        est_x, est_y = pilot.estimator.last_mean_xy
        dist_est = math.hypot(est_x - bx, est_y - by)

        t_by_id = {t["id"]: t for t in final_map["targets"]}
        tot_known_val = sum(float(t["value"]) for t in final_map["targets"])
        print(f"\n--- FINAL TELEMETRY SUMMARY ({time.time() - t0:.1f}s) ---", flush=True)
        print(f"Last packet tick: {last_pkt.get('tick')}, alive: {last_pkt.get('alive')}, battery: {last_pkt.get('battery')}", flush=True)
        print(f"Last noisy GPS: {last_pkt.get('position')}, Filtered XY: ({est_x:.2f}, {est_y:.2f}), est dist to base: {dist_est:.2f}m", flush=True)
        print(f"Learned solar_efficiency: {summary['eff_est']:.6f}", flush=True)
        print(f"Learned slip_base: {summary['mu_slip']}", flush=True)
        print(f"Known targets: {len(t_by_id)} (total value {tot_known_val:.1f})", flush=True)
        print(f"Confirmed sampled targets ({len(last_pkt.get('sampled_targets', []))}): {last_pkt.get('sampled_targets')}", flush=True)


if __name__ == "__main__":
    main()
