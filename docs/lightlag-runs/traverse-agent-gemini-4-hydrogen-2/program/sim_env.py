import json, math, random, sys
sys.path.insert(0, "/app")
from lightlag_surface import Surface, PHYSICS, drive, TERRAIN_CODES

class SimMission:
    def __init__(self, world, rules, seed=1):
        self.rng = random.Random(seed)
        self.rules = rules
        self.base = tuple(world["base"])
        self.surf = Surface(world["cell_m"], world["elevation_cm"], world["terrain"])
        self.init_targets = [dict(t) for t in world["targets"]]
        self.delay = rules["delay_ticks"]
        self.max_ticks = rules["max_ticks"]

        # Hidden mission parameters
        self.slip_base = {
            k: self.rng.uniform(v[0], v[1])
            for k, v in rules["physics"]["slip_base_ranges"].items()
        }
        self.solar_eff = self.rng.uniform(*rules["solar_efficiency_range"])
        self.heading_bias = self.rng.uniform(-rules["sensing"]["heading_bias_deg"],
                                             rules["sensing"]["heading_bias_deg"])

        # Generate synthetic discoveries matching map_generator rules
        self.discoveries = []
        min_app, max_frac = rules["map_generator"]["discovery_appear"]
        max_app = int(self.max_ticks * max_frac)
        w_min, w_max = rules["map_generator"]["discovery_window_ticks"]
        for k in range(rules["map_generator"]["discoveries"]):
            for _ in range(100):
                dx = self.rng.uniform(20.0, self.surf.width - 20.0)
                dy = self.rng.uniform(20.0, self.surf.height - 20.0)
                if self.surf.slope(dx, dy) > 0.25:
                    continue
                if math.hypot(dx - self.base[0], dy - self.base[1]) < 35.0:
                    continue
                break
            app = self.rng.randint(min_app, max_app)
            val = float(self.rng.randint(*rules["map_generator"]["target_values"]))
            has_dl = self.rng.random() < rules["map_generator"]["deadline_share"]
            dl = min(self.max_ticks, app + self.rng.randint(w_min, w_max)) if has_dl else None
            self.discoveries.append({
                "id": f"d{k+1}",
                "x": round(dx, 1),
                "y": round(dy, 1),
                "value": val,
                "late_value": val * rules["sample_windows"]["late_fraction"] if dl is not None else val,
                "deadline_tick": dl,
                "appear_tick": app,
            })

        self.all_targets = self.init_targets + self.discoveries
        self.known_targets = [dict(t) for t in self.init_targets]

        # True state
        self.tick = 0
        self.x, self.y = self.base
        self.battery = rules["initial_battery"]
        self.alive = True
        self.sampled = {}  # id -> sample_tick
        self.queue = {}    # exec_tick -> cmd
        self.last_reserved = 0
        self.packets = [{
            "tick": 0,
            "received_tick": 0,
            "position": [self.x, self.y],
            "heading_deg": 0.0,
            "battery": self.battery,
            "charge": 0.0,
            "terrain": self.surf.terrain(self.x, self.y),
            "tilt": round(self.surf.slope(self.x, self.y), 3),
            "wheel_odometry": 0.0,
            "visual_odometry": 0.0,
            "sampled_targets": [],
            "alive": True,
            "events": [],
        }]

    def get_map(self):
        # Discoveries appear in map() once telemetry for appear_tick has arrived
        avail = [dict(t) for t in self.init_targets]
        for d in self.discoveries:
            if self.tick >= d["appear_tick"] + self.delay:
                avail.append(dict(d))
        return {
            "width": self.surf.width,
            "height": self.surf.height,
            "cell_m": self.surf.cell,
            "elevation_cm": None,
            "terrain": None,
            "terrain_codes": TERRAIN_CODES,
            "base": list(self.base),
            "targets": avail,
        }

    def telemetry_log(self):
        return [p for p in self.packets if p["received_tick"] <= self.tick]

    def uplink(self, commands):
        if not (1 <= len(commands) <= 5):
            raise ValueError("1 to 5 commands")
        first = max(self.tick + self.delay + 1, self.last_reserved + 1)
        acks = []
        for i, cmd in enumerate(commands):
            et = first + i
            if et > self.max_ticks:
                raise ValueError("exceeds max_ticks")
            act = cmd["action"]
            if act == "drive":
                m = float(cmd["metres"])
                if not (0 < m <= 5.0):
                    raise ValueError("invalid metres")
            elif act not in ("sample", "wait"):
                raise ValueError("invalid action")
            self.queue[et] = dict(cmd)
            self.last_reserved = et
            acks.append({"execute_tick": et, "command": dict(cmd)})
        return acks

    def advance(self, n=1):
        arrived = []
        for _ in range(n):
            if self.tick >= self.max_ticks:
                break
            self.tick += 1
            t = self.tick
            events = []
            for d in self.discoveries:
                if d["appear_tick"] == t:
                    events.append({"type": "target_discovered", "target": dict(d)})
            cmd = self.queue.pop(t, {"action": "wait"})
            cmd_hdg = float(cmd.get("heading_deg", 0.0)) if cmd["action"] == "drive" else 0.0
            wheel_odo = 0.0
            vis_odo = 0.0
            if self.alive:
                # solar
                s = self.rules["solar_peak"] * self.solar_eff * math.sin(
                    math.pi * (t + self.rules["sun_margin_ticks"]) /
                    (self.max_ticks + 2 * self.rules["sun_margin_ticks"])
                )
                before_cap = self.battery
                self.battery = min(self.rules["battery_capacity"], self.battery + s)
                charge = self.battery - before_cap
                self.battery -= self.rules["idle_cost"]
                if self.battery <= 0:
                    self.battery = 0.0
                    self.alive = False
                    events.append({"type": "battery_empty"})
                elif cmd["action"] == "drive":
                    self.heading_bias += self.rng.gauss(0.0, self.rules["sensing"]["heading_bias_walk_deg"])
                    h_exec = cmd_hdg + self.heading_bias + self.rng.gauss(0.0, self.rules["sensing"]["heading_noise_deg"])
                    s_noise = self.rng.uniform(-PHYSICS["slip_noise"], PHYSICS["slip_noise"])
                    res = drive(self.surf, PHYSICS, self.x, self.y, h_exec, float(cmd["metres"]),
                                self.slip_base, noise=s_noise, battery=self.battery)
                    self.x, self.y = res["x"], res["y"]
                    self.battery -= res["energy"]
                    wheel_odo = res["wheel"]
                    vis_odo = res["ground"] * (1.0 + self.rng.gauss(0.0, self.rules["sensing"]["visual_odometry_noise"]))
                    if res["stop"] in ("tilt", "map_boundary"):
                        # Clear queued commands, reserved ticks stay reserved
                        self.queue.clear()
                        events.append({"type": "safety_stop", "reason": res["stop"]})
                    elif res["stop"] == "battery" or self.battery <= 0:
                        self.battery = 0.0
                        self.alive = False
                        self.queue.clear()
                        events.append({"type": "battery_empty"})
                elif cmd["action"] == "sample":
                    self.battery -= self.rules["sample_cost"]
                    if self.battery <= 0:
                        self.battery = 0.0
                        self.alive = False
                        self.queue.clear()
                        events.append({"type": "battery_empty"})
                    else:
                        best_t = None
                        best_d = 1e9
                        for tgt in self.all_targets:
                            if tgt["appear_tick"] <= t and tgt["id"] not in self.sampled:
                                d = math.hypot(tgt["x"] - self.x, tgt["y"] - self.y)
                                if d <= self.rules["target_radius"] and d < best_d:
                                    best_d = d
                                    best_t = tgt
                        if best_t is not None:
                            self.sampled[best_t["id"]] = t
                            events.append({"type": "sampled", "target_id": best_t["id"]})
                        else:
                            events.append({"type": "sample_missed"})
            else:
                charge = 0.0

            px = min(self.surf.width, max(0.0, self.x + self.rng.gauss(0.0, self.rules["sensing"]["position_noise_m"])))
            py = min(self.surf.height, max(0.0, self.y + self.rng.gauss(0.0, self.rules["sensing"]["position_noise_m"])))
            pkt = {
                "tick": t,
                "received_tick": t + self.delay,
                "position": [px, py],
                "heading_deg": cmd_hdg,
                "battery": self.battery,
                "charge": charge,
                "terrain": self.surf.terrain(self.x, self.y),
                "tilt": round(self.surf.slope(self.x, self.y), 3),
                "wheel_odometry": wheel_odo,
                "visual_odometry": vis_odo,
                "sampled_targets": sorted(self.sampled.keys()),
                "alive": self.alive,
                "events": events,
            }
            self.packets.append(pkt)
            for p in self.packets:
                if p["received_tick"] == t:
                    arrived.append(p)
        return {
            "current_tick": self.tick,
            "episode_complete": self.tick >= self.max_ticks,
            "packets": arrived,
        }

    def final_score(self):
        if not self.alive:
            return 0.0, 0.0, 0.0
        credited = 0.0
        for tid, stk in self.sampled.items():
            tgt = next(x for x in self.all_targets if x["id"] == tid)
            if tgt["deadline_tick"] is None or stk <= tgt["deadline_tick"]:
                credited += tgt["value"]
            else:
                credited += tgt["late_value"]
        total_val = sum(x["value"] for x in self.all_targets)
        at_base = math.hypot(self.x - self.base[0], self.y - self.base[1]) <= self.rules["base_radius"]
        mult = 1.0 if at_base else 0.5
        return credited * mult / total_val, credited, mult
