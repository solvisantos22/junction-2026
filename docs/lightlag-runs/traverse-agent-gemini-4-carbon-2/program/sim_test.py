import copy
import json
import math
import random
import sys
import time

sys.path.insert(0, "/app")
sys.path.insert(0, "/tmp/opencode")
from lightlag_surface import PHYSICS, TERRAIN_CODES, Surface, drive
from autopilot_core import RoverAutopilot


class MockLightlagServer:
    def __init__(self, rules_data, map_data, seed=101, fixed_eff=None):
        self.rules_data = copy.deepcopy(rules_data)
        self.base_map = copy.deepcopy(map_data)
        self.surf = Surface(map_data["cell_m"], map_data["elevation_cm"], map_data["terrain"])
        self.rng = random.Random(seed)

        self.eff = fixed_eff if fixed_eff is not None else self.rng.uniform(0.80, 1.00)
        self.slip_base = {
            k: self.rng.uniform(lo, hi) for k, (lo, hi) in PHYSICS["slip_base_ranges"].items()
        }
        self.heading_bias = self.rng.uniform(-5.0, 5.0)

        # Generate 8 discoveries matching map_generator rules
        self.all_targets = copy.deepcopy(map_data["targets"])
        bx, by = map_data["base"]
        for d_i in range(1, 9):
            while True:
                tx = self.rng.randint(4, 116) * 5.0
                ty = self.rng.randint(4, 76) * 5.0
                if self.surf.slope(tx, ty) > 0.22:
                    continue
                if math.hypot(tx - bx, ty - by) < 35.0:
                    continue
                if any(math.hypot(tx - ot["x"], ty - ot["y"]) < 15.0 for ot in self.all_targets):
                    continue
                app_t = self.rng.randint(30, int(0.68 * 420))
                val = float(self.rng.randint(1, 5))
                has_dl = self.rng.random() < 0.7
                dl = app_t + self.rng.randint(60, 130) if has_dl else None
                if dl is not None and dl > 420:
                    dl = 420
                self.all_targets.append({
                    "id": f"d{d_i}",
                    "x": tx,
                    "y": ty,
                    "value": val,
                    "deadline_tick": dl,
                    "late_value": round(0.25 * val, 4) if dl is not None else val,
                    "appear_tick": app_t,
                })
                break

        self.current_tick = 0
        self.x, self.y = float(bx), float(by)
        self.battery = 100.0
        self.alive = True
        self.sampled_at: dict[str, int] = {}
        self.cmd_queue: dict[int, dict] = {}
        self.last_reserved = 0
        self.safety_stops = 0
        self.min_battery = 100.0

        self.pending_packets = []
        self.delivered_packets = [{
            "tick": 0,
            "received_tick": 0,
            "position": [self.x, self.y],
            "heading_deg": 0.0,
            "battery": 100.0,
            "charge": 0.0,
            "terrain": self.surf.terrain(self.x, self.y),
            "tilt": round(self.surf.slope(self.x, self.y), 4),
            "wheel_odometry": 0.0,
            "visual_odometry": 0.0,
            "sampled_targets": [],
            "alive": True,
            "events": [],
        }]

    def rules(self):
        return copy.deepcopy(self.rules_data)

    def map(self):
        # Discoveries are visible in map() once their appear_tick + delay_ticks <= current_tick
        vis = [
            copy.deepcopy(t)
            for t in self.all_targets
            if t["appear_tick"] == 0 or (t["appear_tick"] + 3 <= self.current_tick)
        ]
        out = copy.deepcopy(self.base_map)
        out["targets"] = vis
        return out

    def telemetry_log(self):
        return copy.deepcopy(self.delivered_packets)

    def uplink(self, commands):
        if not (1 <= len(commands) <= 5):
            raise ValueError("1 to 5 commands required")
        for c in commands:
            if c["action"] == "drive":
                if not (0.0 < float(c["metres"]) <= 5.0):
                    raise ValueError(f"invalid metres {c['metres']}")
        start_t = max(self.current_tick + 3 + 1, self.last_reserved + 1)
        acks = []
        for idx, c in enumerate(commands):
            et = start_t + idx
            self.cmd_queue[et] = copy.deepcopy(c)
            self.last_reserved = et
            acks.append({"execute_tick": et, "action": c["action"]})
        return acks

    def advance(self, ticks=1):
        arrived = []
        for _ in range(ticks):
            if self.current_tick >= 420:
                break
            self.current_tick += 1
            t = self.current_tick
            events = []
            for tobj in self.all_targets:
                if tobj["appear_tick"] == t:
                    events.append({"type": "target_discovered", "id": tobj["id"]})

            cmd = self.cmd_queue.pop(t, {"action": "wait"})
            h_rep = 0.0
            w_odom = 0.0
            v_odom = 0.0
            charge = 0.0

            if self.alive:
                raw_solar = 2.8 * self.eff * math.sin(math.pi * (t + 56) / 532.0)
                nb = min(100.0, self.battery + raw_solar)
                charge = nb - self.battery
                self.battery = nb - 0.15
                if self.battery <= 0.0:
                    self.battery = 0.0
                    self.alive = False

            if self.alive:
                act = cmd["action"]
                if act == "drive":
                    h_rep = float(cmd["heading_deg"])
                    m_req = float(cmd["metres"])
                    self.heading_bias += self.rng.gauss(0.0, 0.2)
                    h_act = h_rep + self.heading_bias + self.rng.gauss(0.0, 1.5)
                    u_slip = self.rng.uniform(-0.02, 0.02)
                    res = drive(self.surf, PHYSICS, self.x, self.y, h_act, m_req, self.slip_base, noise=u_slip, battery=self.battery)
                    self.x, self.y = res["x"], res["y"]
                    w_odom = res["wheel"]
                    v_odom = max(0.0, res["ground"] * (1.0 + self.rng.gauss(0.0, 0.05)))
                    self.battery -= res["energy"]
                    if res["stop"] == "battery" or self.battery <= 0.0:
                        self.battery = 0.0
                        self.alive = False
                    elif res["stop"] in ("tilt", "map_boundary"):
                        self.safety_stops += 1
                        events.append({"type": "safety_stop", "reason": res["stop"]})
                        self.cmd_queue.clear()  # reserved ticks stay reserved!
                elif act == "sample":
                    if self.battery <= 2.0:
                        self.battery = 0.0
                        self.alive = False
                    else:
                        self.battery -= 2.0
                        cands = []
                        for tobj in self.all_targets:
                            if tobj["appear_tick"] <= t and tobj["id"] not in self.sampled_at:
                                d = math.hypot(tobj["x"] - self.x, tobj["y"] - self.y)
                                if d <= 2.5:
                                    cands.append((d, tobj["id"]))
                        if cands:
                            cands.sort()
                            sid = cands[0][1]
                            self.sampled_at[sid] = t
                            events.append({"type": "sampled", "id": sid})

                if self.battery < self.min_battery:
                    self.min_battery = self.battery

            pkt = {
                "tick": t,
                "received_tick": t + 3,
                "position": [
                    max(0.0, min(600.0, self.x + self.rng.gauss(0.0, 1.0))),
                    max(0.0, min(400.0, self.y + self.rng.gauss(0.0, 1.0))),
                ],
                "heading_deg": h_rep,
                "battery": round(self.battery, 6),
                "charge": round(charge, 6),
                "terrain": self.surf.terrain(self.x, self.y),
                "tilt": round(self.surf.slope(self.x, self.y), 4),
                "wheel_odometry": round(w_odom, 6),
                "visual_odometry": round(v_odom, 6),
                "sampled_targets": list(self.sampled_at.keys()),
                "alive": self.alive,
                "events": events,
            }
            self.pending_packets.append(pkt)

            still_pending = []
            for p in self.pending_packets:
                if p["received_tick"] <= t:
                    self.delivered_packets.append(p)
                    arrived.append(copy.deepcopy(p))
                else:
                    still_pending.append(p)
            self.pending_packets = still_pending

        return {
            "current_tick": self.current_tick,
            "episode_complete": self.current_tick >= 420,
            "packets": arrived,
        }

    def true_score(self):
        total_val = sum(t["value"] for t in self.all_targets)
        earned = 0.0
        for t in self.all_targets:
            tid = t["id"]
            if tid in self.sampled_at:
                st = self.sampled_at[tid]
                dl = t["deadline_tick"]
                earned += t["value"] if (dl is None or st <= dl) else t["late_value"]
        bx, by = self.base_map["base"]
        dist_base = math.hypot(self.x - bx, self.y - by)
        if not self.alive or self.battery <= 0.0:
            mult = 0.0
        elif dist_base <= 4.0:
            mult = 1.0
        else:
            mult = 0.5
        return {
            "score": (earned * mult) / total_val,
            "earned": earned,
            "total_val": total_val,
            "mult": mult,
            "dist_base": dist_base,
            "alive": self.alive,
            "min_bat": self.min_battery,
            "end_bat": self.battery,
            "safety_stops": self.safety_stops,
            "n_sampled": len(self.sampled_at),
        }


if __name__ == "__main__":
    with open("/tmp/opencode/rules.json") as f:
        rules_data = json.load(f)
    with open("/tmp/opencode/map.json") as f:
        map_data = json.load(f)

    test_cases = [
        (103, 0.90),
        (105, 0.99),
    ]
    scores = []
    for seed, eff in test_cases:
        t0 = time.time()
        sim = MockLightlagServer(rules_data, map_data, seed=seed, fixed_eff=eff)
        pilot = RoverAutopilot(sim.rules(), sim.map(), verbose=(seed == 103))
        pilot.run_episode(sim)
        res = sim.true_score()
        dt = time.time() - t0
        scores.append(res["score"])
        print(
            f"Seed {seed} (eff={eff:.2f}): SCORE={res['score']:.4f} "
            f"(earned={res['earned']:.2f}/{res['total_val']:.1f}, mult={res['mult']}, "
            f"samples={res['n_sampled']}, dist_base={res['dist_base']:.2f}m, "
            f"min_bat={res['min_bat']:.1f}, stops={res['safety_stops']}, time={dt:.1f}s)"
        )
    print(f"\nMean score across 5 seeds: {sum(scores)/len(scores):.4f}")
