import math, time, sys, json, traceback
import numpy as np
from lightlag_client import connect

URL = "http://lightlag:8000/mcp"
N = 1500
rng = np.random.default_rng(1)

def log(*a):
    print(*a, flush=True)


def seg_rect(p, q, r):
    # Liang-Barsky: does segment p->q intersect rect r=(x1,y1,x2,y2)?
    x0, y0 = p; dx = q[0] - x0; dy = q[1] - y0
    t0, t1 = 0.0, 1.0
    for pp, qq in ((-dx, x0 - r[0]), (dx, r[2] - x0), (-dy, y0 - r[1]), (dy, r[3] - y0)):
        if abs(pp) < 1e-12:
            if qq < 0:
                return False
        else:
            t = qq / pp
            if pp < 0:
                if t > t1: return False
                if t > t0: t0 = t
            else:
                if t < t0: return False
                if t < t1: t1 = t
    return True


class Mission:
    def __init__(self, tools):
        self.tools = tools
        self.rules = tools.rules()
        self.world = tools.map()
        R = self.rules
        self.delay = R["delay_ticks"]; self.max_ticks = R["max_ticks"]
        self.idle = R["idle_cost"]; self.drive_cost = R["drive_cost"]; self.sample_cost = R["sample_cost"]
        self.trad = R["target_radius"]; self.brad = R["base_radius"]
        self.mult = R["terrain_drive_multipliers"]
        sens = R.get("sensing") or {}
        self.pos_noise = max(sens.get("position_noise_m", 0.0), 0.05)
        self.vo_noise = max(sens.get("visual_odometry_noise", 0.0), 0.02)
        self.bias_max = sens.get("heading_bias_deg", 0.0)
        self.bias_walk = sens.get("heading_bias_walk_deg", 0.0)
        self.head_noise = sens.get("heading_noise_deg", 0.0)
        sr = R["slip_ranges"]
        self.base = tuple(self.world["base"])
        self.W = self.world["width"]; self.H = self.world["height"]
        self.sand = [(s["x1"], s["y1"], s["x2"], s["y2"]) for s in self.world["sand"]]
        self.haz = [(h["x1"], h["y1"], h["x2"], h["y2"]) for h in self.world["hazards"]]
        m = 1.1
        self.hazi = [(a - m, b - m, c + m, d + m) for a, b, c, d in self.haz]
        self.corners = []
        for a, b, c, d in self.hazi:
            for x, y in ((a - .15, b - .15), (a - .15, d + .15), (c + .15, b - .15), (c + .15, d + .15)):
                if 0.5 < x < self.W - 0.5 and 0.5 < y < self.H - 0.5 and not any(r[0] < x < r[2] and r[1] < y < r[3] for r in self.hazi):
                    self.corners.append((x, y))
        # particles: x y b(deg) sbed ssand
        self.px = np.full(N, self.base[0]); self.py = np.full(N, self.base[1])
        self.pb = rng.uniform(-self.bias_max, self.bias_max, N) if self.bias_max > 0 else np.zeros(N)
        self.psb = rng.uniform(*sr["bedrock"], N); self.pss = rng.uniform(*sr["sand"], N)
        self.sr = sr
        self.last_tick = 0
        self.battery = R["initial_battery"]
        self.queue = {}  # exec_tick -> cmd
        self.pending = {}  # target id -> exec tick of sample
        self.sampled = set()
        self.processed = 0
        self.last_exec = 0
        self.prev_first = None

    # ---------- terrain ----------
    def in_sand(self, x, y):
        s = np.zeros(np.shape(x), dtype=bool)
        for a, b, c, d in self.sand:
            s |= (x >= a) & (x <= c) & (y >= b) & (y <= d)
        return s

    def propagate(self, px, py, pb, psb, pss, heading, metres, noisy=True):
        n = len(px)
        if noisy:
            pb = pb + rng.normal(0, self.bias_walk, n) if self.bias_walk > 0 else pb
            h = np.radians(heading + pb + (rng.normal(0, self.head_noise, n) if self.head_noise > 0 else 0))
            sn = rng.uniform(-0.02, 0.02, n)
        else:
            h = np.radians(heading + pb); sn = 0
        c, s = np.cos(h), np.sin(h)
        steps = max(1, int(math.ceil(metres / 0.1 - 1e-9)))
        st = metres / steps
        px = px.copy(); py = py.copy(); dist = np.zeros(n)
        for _ in range(steps):
            sand = self.in_sand(px, py)
            slip = np.clip(np.where(sand, pss, psb) + sn, 0, 0.9)
            d = st * (1 - slip)
            px += c * d; py += s * d; dist += d
        px = np.clip(px, 0, self.W); py = np.clip(py, 0, self.H)
        return px, py, pb, dist

    # ---------- filter ----------
    def process_packet(self, pk):
        t = pk["tick"]
        if t <= self.last_tick:
            return
        wo = pk.get("wheel_odometry") or 0
        if wo > 0:
            self.px, self.py, self.pb, dist = self.propagate(self.px, self.py, self.pb, self.psb, self.pss, pk["heading_deg"], wo)
            vo = pk.get("visual_odometry")
            w = np.zeros(N)
            if vo is not None:
                sd = np.maximum(self.vo_noise * dist, 0.02)
                w += -0.5 * ((vo - dist) / sd) ** 2 - np.log(sd)
        else:
            w = np.zeros(N)
        pos = pk.get("position")
        if pos is not None:
            w += -0.5 * (((pos[0] - self.px) ** 2 + (pos[1] - self.py) ** 2) / self.pos_noise ** 2)
        w -= w.max(); w = np.exp(w); w /= w.sum()
        ess = 1.0 / np.sum(w ** 2)
        if ess < N * 0.5:
            idx = rng.choice(N, N, p=w)
            self.px = self.px[idx] + rng.normal(0, 0.02, N); self.py = self.py[idx] + rng.normal(0, 0.02, N)
            self.pb = self.pb[idx] + rng.normal(0, 0.15, N)
            self.psb = np.clip(self.psb[idx] + rng.normal(0, 0.002, N), *self.sr["bedrock"])
            self.pss = np.clip(self.pss[idx] + rng.normal(0, 0.005, N), *self.sr["sand"])
            self.w = None
        else:
            # keep weighted by resampling anyway for simplicity
            idx = rng.choice(N, N, p=w)
            self.px = self.px[idx]; self.py = self.py[idx]; self.pb = self.pb[idx]
            self.psb = self.psb[idx]; self.pss = self.pss[idx]
            self.px += rng.normal(0, 0.01, N); self.py += rng.normal(0, 0.01, N); self.pb += rng.normal(0, 0.1, N)
        self.last_tick = t
        self.battery = pk.get("battery", self.battery)
        st = set(pk.get("sampled_targets") or [])
        self.sampled |= st
        for tid, et in list(self.pending.items()):
            if tid in self.sampled:
                del self.pending[tid]
            elif t >= et:
                log(f"  sample of {tid} at {et} FAILED")
                del self.pending[tid]
        ev = pk.get("events") or []
        if ev:
            log("  events", t, ev)
            for e in ev:
                es = json.dumps(e).lower()
                if "stop" in es or "hazard" in es or "edge" in es:
                    for et in list(self.queue):
                        if et > t:
                            del self.queue[et]
                    for tid, et in list(self.pending.items()):
                        if et > t:
                            del self.pending[tid]
        self.queue = {k: v for k, v in self.queue.items() if k > t}

    def predict(self, T):
        px, py, pb = self.px, self.py, self.pb
        energy = 0.0
        for et in sorted(self.queue):
            if et >= T: break
            c = self.queue[et]
            if c["action"] == "drive":
                sand = self.in_sand(px, py).mean() > 0.5
                energy += c["metres"] * self.mult["sand" if sand else "bedrock"] * self.drive_cost
                px, py, pb, _ = self.propagate(px, py, pb, self.psb, self.pss, c["heading_deg"], c["metres"])
            elif c["action"] == "sample":
                energy += self.sample_cost
        bat = self.battery - energy - self.idle * max(0, T - 1 - self.last_tick)
        return px, py, pb, bat

    # ---------- planning ----------
    def clear(self, p, q):
        return not any(seg_rect(p, q, r) for r in self.hazi)

    def path(self, p, q):
        if self.clear(p, q):
            return [p, q]
        nodes = [p] + self.corners + [q]
        n = len(nodes)
        dist = [math.inf] * n; prev = [-1] * n; dist[0] = 0; done = [False] * n
        for _ in range(n):
            u = min((i for i in range(n) if not done[i]), key=lambda i: dist[i], default=None)
            if u is None or dist[u] == math.inf: break
            done[u] = True
            if u == n - 1: break
            for v in range(n):
                if done[v]: continue
                d = math.dist(nodes[u], nodes[v])
                if dist[u] + d < dist[v] and self.clear(nodes[u], nodes[v]):
                    dist[v] = dist[u] + d; prev[v] = u
        if dist[n - 1] == math.inf:
            return [p, q]
        out = []; i = n - 1
        while i != -1:
            out.append(nodes[i]); i = prev[i]
        return out[::-1]

    def leg_cost(self, p, q):
        pts = self.path(p, q)
        sb, ss = float(np.mean(self.psb)), float(np.mean(self.pss))
        wheel = 0.0; energy = 0.0; ticks = 0
        for a, b in zip(pts, pts[1:]):
            L = math.dist(a, b)
            k = max(1, int(L / 0.5))
            xs = np.array([a[0] + (b[0] - a[0]) * (i + .5) / k for i in range(k)])
            ys = np.array([a[1] + (b[1] - a[1]) * (i + .5) / k for i in range(k)])
            fs = self.in_sand(xs, ys).mean() if L > 0 else 0
            w = L * fs / (1 - ss) + L * (1 - fs) / (1 - sb)
            wheel += w
            energy += self.drive_cost * (L * fs / (1 - ss) * self.mult["sand"] + L * (1 - fs) / (1 - sb) * self.mult["bedrock"])
            ticks += max(1, math.ceil(w / 5.0 - 1e-6)) if L > 0.05 else 0
        return ticks, energy, pts

    def plan(self, start, T0, bat):
        world = self.world
        cands = [t for t in world["targets"] if t["id"] not in self.sampled and t["id"] not in self.pending]
        pts = [start, self.base] + [(t["x"], t["y"]) for t in cands]
        n = len(pts)
        C = {}
        for i in range(n):
            for j in range(1, n):
                if i != j:
                    C[(i, j)] = self.leg_cost(pts[i], pts[j])
        end_limit = self.max_ticks - 4
        budget = bat - self.idle * (self.max_ticks - T0 + 1) - 4.0
        best = [(-1, 0), None]

        def dfs(cur, t, energy, value, order):
            # option: return to base
            tk, en, _ = C[(cur, 1)] if cur != 1 else (0, 0, None)
            arrive = t + tk - 1
            if arrive <= end_limit and energy + en <= budget:
                key = (round(value, 3), -arrive)
                if key > best[0]:
                    best[0] = key; best[1] = list(order)
            for j in range(2, n):
                if j in order: continue
                tg = cands[j - 2]
                tk, en, _ = C[(cur, j)]
                st = max(t + tk, tg.get("appear_tick", 0) or 0)
                e2 = energy + en + self.sample_cost
                if e2 > budget or st > end_limit: continue
                dl = tg.get("deadline_tick")
                v = tg["value"] if (dl is None or st <= dl) else tg.get("late_value", 0)
                if v <= 0: continue
                order.append(j)
                dfs(j, st + 1, e2, value + v, order)
                order.pop()
        dfs(0, T0, 0.0, 0.0, [])
        if best[1] is None:
            return None, best[0]
        if best[1]:
            j = best[1][0]
            return (cands[j - 2], C[(0, j)][2]), best[0]
        return (None, C[(0, 1)][2] if (0, 1) in C else [start, self.base]), best[0]

    def wheel_for(self, p, heading_true, D):
        sb, ss = float(np.mean(self.psb)), float(np.mean(self.pss))
        c, s = math.cos(math.radians(heading_true)), math.sin(math.radians(heading_true))
        k = max(1, int(D / 0.1)); w = 0.0
        for i in range(k):
            x = p[0] + c * D * (i + .5) / k; y = p[1] + s * D * (i + .5) / k
            sand = bool(self.in_sand(np.array(x), np.array(y)))
            w += (D / k) / (1 - (ss if sand else sb))
        return w

    def decide(self, T):
        px, py, pb, bat = self.predict(T)
        p = (float(px.mean()), float(py.mean())); b = float(pb.mean())
        spread = float(math.sqrt(px.var() + py.var()))
        res, score = self.plan(p, T, bat)
        if res is None:
            goal = self.base; tgt = None; pts = self.path(p, self.base)
        else:
            tgt, pts = res
            goal = (tgt["x"], tgt["y"]) if tgt else self.base
        D = math.dist(p, goal)
        info = f"T={T} p=({p[0]:.2f},{p[1]:.2f}) sd={spread:.2f} b={b:.1f} bat={bat:.1f} goal={tgt['id'] if tgt else 'base'} D={D:.2f} plan={score}"
        if tgt is not None and D < 0.2:
            if tgt.get("appear_tick", 0) > T:
                return {"action": "wait"}, info, None
            return {"action": "sample"}, info, tgt["id"]
        if tgt is None and D < 0.25:
            return {"action": "wait"}, info, None
        wp = pts[1] if len(pts) > 1 else goal
        dw = math.dist(p, wp)
        if dw < 0.05:
            wp = goal; dw = D
        htrue = math.degrees(math.atan2(wp[1] - p[1], wp[0] - p[0]))
        m = min(5.0, self.wheel_for(p, htrue, dw))
        m = max(0.05, round(m, 3))
        return {"action": "drive", "heading_deg": round((htrue - b) % 360, 3), "metres": m}, info, None


def get_packets(out):
    for k, v in out.items():
        if isinstance(v, list) and v and isinstance(v[0], dict) and "tick" in v[0]:
            return v
    return []


def ack_tick(acks, T):
    try:
        if isinstance(acks, dict):
            for v in acks.values():
                if isinstance(v, list): acks = v; break
        a = acks[0]
        if isinstance(a, dict):
            return int(a.get("execute_tick", T))
        return int(a)
    except Exception:
        return T


def run():
    with connect(URL) as tools:
        mission_no = None
        M = None
        while True:
            out = tools.advance(1)
            cur = out["current_tick"]
            if out.get("campaign_complete"):
                log("campaign complete"); return
            if out.get("episode_complete"):
                log(f"mission {out.get('mission')} complete at {cur}")
                M = None
                continue
            if M is None or out.get("mission") != mission_no:
                M = Mission(tools); mission_no = out.get("mission")
                log(f"=== mission {mission_no} started, tick {cur}")
                for pk in tools.telemetry_log():
                    M.process_packet(pk)
            else:
                for pk in sorted(get_packets(out), key=lambda p: p["tick"]):
                    M.process_packet(pk)
            try:
                if any(True for _ in range(1)):
                    M.world = tools.map()
                if cur + M.delay + 1 > M.last_exec:
                    T = max(cur + M.delay + 1, M.last_exec + 1)
                    if T > M.max_ticks - 1:
                        continue
                    t0 = time.time()
                    cmd, info, tid = M.decide(T)
                    try:
                        acks = tools.uplink([cmd])
                        et = ack_tick(acks, T)
                    except ValueError as e:
                        log("rejected", e); continue
                    M.last_exec = et
                    M.queue[et] = cmd
                    if tid:
                        M.pending[tid] = et
                    log(f"[{cur}] {info} -> {cmd} @ {et} ({time.time()-t0:.2f}s)")
            except Exception:
                traceback.print_exc()


if __name__ == "__main__":
    run()
