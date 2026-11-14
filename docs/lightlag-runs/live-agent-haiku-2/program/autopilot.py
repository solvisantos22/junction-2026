import math
import sys
import time

from lightlag_client import connect

URL = "http://lightlag:8000/mcp"
LOG = open("/app/autopilot_state.log", "a", buffering=1)


def log(*a):
    line = time.strftime("%H:%M:%S ") + " ".join(str(x) for x in a)
    print(line, flush=True)
    LOG.write(line + "\n")


def d2(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def seg_hits_rect(p, q, r, margin):
    x1, y1 = r["x1"] - margin, r["y1"] - margin
    x2, y2 = r["x2"] + margin, r["y2"] + margin
    n = max(2, int(d2(p, q) / 0.1))
    for i in range(n + 1):
        t = i / n
        x = p[0] + (q[0] - p[0]) * t
        y = p[1] + (q[1] - p[1]) * t
        if x1 <= x <= x2 and y1 <= y <= y2:
            return True
    return False


def route(p, q, hazards, W, H):
    """Waypoints from p to q (excluding p, ending at q), avoiding hazards."""
    def blocked(a, b):
        return any(seg_hits_rect(a, b, h, 1.0) for h in hazards)

    if not blocked(p, q):
        return [q]
    cands = []
    for h in hazards:
        m = 1.5
        for x, y in [(h["x1"] - m, h["y1"] - m), (h["x2"] + m, h["y1"] - m),
                     (h["x1"] - m, h["y2"] + m), (h["x2"] + m, h["y2"] + m)]:
            if 1 <= x <= W - 1 and 1 <= y <= H - 1:
                cands.append((x, y))
    best = None
    for c in cands:
        if not blocked(p, c) and not blocked(c, q):
            dd = d2(p, c) + d2(c, q)
            if best is None or dd < best[0]:
                best = (dd, [c, q])
    if best:
        return best[1]
    for c1 in cands:
        if blocked(p, c1):
            continue
        for c2 in cands:
            if blocked(c1, c2) or blocked(c2, q):
                continue
            dd = d2(p, c1) + d2(c1, c2) + d2(c2, q)
            if best is None or dd < best[0]:
                best = (dd, [c1, c2, q])
    return best[1] if best else [q]


def extract_packets(out):
    pk = []
    if isinstance(out, dict):
        for v in out.values():
            if isinstance(v, list) and v and isinstance(v[0], dict) and "tick" in v[0]:
                pk.extend(v)
    return pk


def exec_tick_of(acks, default):
    ts = []
    items = acks if isinstance(acks, list) else (
        [x for v in acks.values() if isinstance(v, list) for x in v] if isinstance(acks, dict) else [])
    for a in items:
        if isinstance(a, dict) and "execute_tick" in a:
            ts.append(int(a["execute_tick"]))
    return max(ts) if ts else default


class Mission:
    def __init__(self, number, rules, world):
        self.number = number
        self.rules = rules
        self.world = world
        self.base = tuple(world["base"])
        self.W = world["width"]
        self.H = world["height"]
        self.hazards = world["hazards"]
        self.delay = rules["delay_ticks"]
        self.maxt = rules["max_ticks"]
        self.fixes = []          # (tick, (x, y))
        self.seen_ticks = set()
        self.busy_until = 0
        self.battery = rules["initial_battery"]
        self.sampled = set()
        self.attempts = {}
        self.goal = None
        self.plan = []

    def ingest(self, packets):
        for p in packets:
            t = p.get("tick")
            if t is None:
                continue
            if p.get("battery") is not None:
                self.battery = p["battery"]
            pos = p.get("position")
            if pos is not None and t not in self.seen_ticks and t > 0:
                self.seen_ticks.add(t)
                self.fixes.append((t, (float(pos[0]), float(pos[1]))))
            for s in p.get("sampled_targets") or []:
                sid = s if isinstance(s, str) else (s.get("id") if isinstance(s, dict) else None)
                if sid:
                    self.sampled.add(sid)

    def estimate(self):
        settled = [p for t, p in self.fixes if t >= self.busy_until + 1]
        if not settled:
            if self.busy_until == 0:
                return self.base, 0
            return None, 0
        last = settled[-4:]
        x = sum(p[0] for p in last) / len(last)
        y = sum(p[1] for p in last) / len(last)
        return (x, y), len(settled)

    def send(self, tools, c, commands):
        acks = tools.uplink(commands)
        e = exec_tick_of(acks, c + self.delay + len(commands))
        self.busy_until = max(self.busy_until, e)
        log("uplink at", c, commands, "exec", e)

    def decide(self, tools, c):
        est, n = self.estimate()
        if est is None:
            return
        world = tools.map()
        self.world = world
        targets = [t for t in world["targets"]
                   if t["id"] not in self.sampled
                   and not t.get("sampled")
                   and self.attempts.get(t["id"], 0) < 3
                   and t.get("appear_tick", 0) <= c]
        dhome = d2(est, self.base)
        left = self.maxt - c
        need_home = (not targets) or (left < 2 * dhome + 8) or \
                    (self.battery < 1.5 * dhome + 0.5 * left + 8)
        if need_home:
            kind, goal, tid = "home", self.base, None
        else:
            t = min(targets, key=lambda t: (t.get("deadline_tick") or 999, d2(est, (t["x"], t["y"]))))
            kind, goal, tid = "sample", (t["x"], t["y"]), t["id"]
        if self.goal != (kind, goal):
            self.goal = (kind, goal)
            self.plan = route(est, goal, self.hazards, self.W, self.H)
            log("goal", kind, tid, goal, "plan", self.plan, "est", est, "c", c)
        while len(self.plan) > 1 and d2(est, self.plan[0]) <= 0.5:
            self.plan.pop(0)
        wp = self.plan[0]
        d = d2(est, wp)
        if len(self.plan) == 1 and d <= 0.5:
            if kind == "sample":
                if n < 3:
                    return
                self.attempts[tid] = self.attempts.get(tid, 0) + 1
                self.send(tools, c, [{"action": "sample"}])
            return
        heading = math.degrees(math.atan2(wp[1] - est[1], wp[0] - est[0]))
        m = min(d, 4.0)
        self.send(tools, c, [{"action": "drive", "heading_deg": round(heading, 2), "metres": round(m, 3)}])


def main():
    with connect(URL) as tools:
        rules = tools.rules()
        world = tools.map()
        M = Mission(world["mission"], rules, world)
        log("start mission", M.number, "targets", [(t["id"], t["x"], t["y"], t["deadline_tick"], t["value"]) for t in world["targets"]])
        while True:
            out = tools.advance(1)
            log("advance", {k: v for k, v in out.items() if not isinstance(v, list)})
            if out.get("mission") != M.number:
                rules = tools.rules()
                world = tools.map()
                M = Mission(out.get("mission", world["mission"]), rules, world)
                log("new mission", M.number, "targets", [(t["id"], t["x"], t["y"], t["deadline_tick"], t["value"]) for t in world["targets"]])
            M.ingest(extract_packets(out))
            if out.get("campaign_complete"):
                log("campaign complete")
                break
            if out.get("episode_complete"):
                log("episode complete, mission", M.number)
                continue
            c = out["current_tick"]
            if c >= M.busy_until + 4:
                try:
                    M.decide(tools, c)
                except Exception as ex:
                    log("decide error", repr(ex))


if __name__ == "__main__":
    main()
