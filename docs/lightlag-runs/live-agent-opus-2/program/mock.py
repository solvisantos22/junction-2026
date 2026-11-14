import json, math, random, time, copy

RULES = json.load(open("/app/rules.json"))
MAP = json.load(open("/app/map.json"))


class MockTools:
    def __init__(self, seed=0, realtime=False):
        self.rng = random.Random(seed)
        self.mission = 0
        self.realtime = realtime
        self.scores = []
        self.new_mission()

    def new_mission(self):
        self.mission += 1
        r = self.rng
        self.tick = 0
        self.pos = [20.0, 20.0]
        self.bat = 100.0
        self.bias = r.uniform(-10, 10)
        self.slip = {"bedrock": r.uniform(0, .05), "sand": r.uniform(.2, .45)}
        self.world = copy.deepcopy(MAP)
        self.world["mission"] = self.mission
        tg = self.world["targets"]
        for t in tg:
            t["x"] += r.uniform(-1, 1); t["y"] += r.uniform(-1, 1)
        self.hidden = [{"id": "d1", "x": 22.0, "y": 14.0, "value": 3, "deadline_tick": 25, "late_value": .75, "appear_tick": 15}]
        self.queue = {}
        self.last = 0
        self.sampled = []
        self.packets = [dict(tick=0, received_tick=0, position=[20.0, 20.0], heading_deg=0, battery=100, terrain="bedrock",
                             wheel_odometry=0, visual_odometry=0, sampled_targets=[], alive=True, events=[])]
        self.delivered = 1
        self.alive = True

    def rules(self):
        return RULES

    def map(self):
        w = copy.deepcopy(self.world)
        w["targets"] = [t for t in w["targets"] if t.get("appear_tick", 0) == 0 or t.get("appear_tick", 0) + 3 <= self.tick]
        return w

    def telemetry_log(self):
        return [p for p in self.packets if p["tick"] + 3 <= self.tick]

    def terrain(self, x, y):
        for s in self.world["sand"]:
            if s["x1"] <= x <= s["x2"] and s["y1"] <= y <= s["y2"]:
                return "sand"
        return "bedrock"

    def uplink(self, cmds):
        out = []
        for c in cmds:
            et = max(self.tick + 4, self.last + 1)
            self.queue[et] = c; self.last = et
            out.append({"execute_tick": et})
        return out

    def step(self):
        self.tick += 1
        t = self.tick
        r = self.rng
        self.bat -= 0.5
        c = self.queue.pop(t, {"action": "wait"})
        w = vo = 0
        ev = []
        h = 0
        if c["action"] == "drive":
            self.bias += r.gauss(0, 1)
            h = c["heading_deg"]
            th = math.radians(h + self.bias + r.gauss(0, 3))
            ter = self.terrain(*self.pos)
            s = min(max(self.slip[ter] + r.uniform(-.02, .02), 0), .9)
            d = c["metres"] * (1 - s)
            self.bat -= c["metres"] * (2 if ter == "sand" else 1)
            self.pos[0] += d * math.cos(th); self.pos[1] += d * math.sin(th)
            w = c["metres"]; vo = d * (1 + r.gauss(0, .1))
        elif c["action"] == "sample":
            self.bat -= 3
            best = None
            for tg in self.world["targets"]:
                if tg["id"] in self.sampled or tg.get("appear_tick", 0) > t: continue
                dd = math.hypot(tg["x"] - self.pos[0], tg["y"] - self.pos[1])
                if dd < .75 and (best is None or dd < best[0]):
                    best = (dd, tg)
            if best:
                self.sampled.append(best[1]["id"])
                v = best[1]["value"] if t <= best[1]["deadline_tick"] else best[1]["late_value"]
                self.score_val = getattr(self, "score_val", 0) + v
        for hd in self.hidden:
            if hd["appear_tick"] == t:
                self.world["targets"].append(hd); ev.append({"type": "target_discovered", "id": hd["id"]})
        self.packets.append(dict(tick=t, received_tick=t + 3, position=[self.pos[0] + r.gauss(0, .6), self.pos[1] + r.gauss(0, .6)],
                                 heading_deg=h, battery=self.bat, terrain=self.terrain(*self.pos), wheel_odometry=w,
                                 visual_odometry=vo, true=list(self.pos), tbias=self.bias, sampled_targets=list(self.sampled), alive=True, events=ev))

    def advance(self, n=1):
        if self.realtime: time.sleep(1)
        newp = []
        for _ in range(n):
            self.step()
            if self.tick >= 50: break
        newp = [p for p in self.packets if p["tick"] + 3 == self.tick]
        done = self.tick >= 50
        res = {"current_tick": self.tick, "episode_complete": done, "campaign_complete": done and self.mission >= 2,
               "mission": self.mission, "packets": newp}
        if done:
            tot = sum(t["value"] for t in self.world["targets"])
            dist = math.hypot(self.pos[0] - 20, self.pos[1] - 20)
            sv = getattr(self, "score_val", 0) * (1 if dist < .75 else .5)
            print("MOCK SCORE", sv / tot, "dist", dist, "sampled", self.sampled, "bat", self.bat, "bias", self.bias, flush=True)
            self.score_val = 0
            if self.mission < 2:
                self.new_mission()
        return res
