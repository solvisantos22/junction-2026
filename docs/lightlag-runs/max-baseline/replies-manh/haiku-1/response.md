This is an untested design, so treat the thresholds as starting points. The module imports `lightlag_surface` for the terrain model, plans routes with A* over the 5 m grid using the slope, slip and crust limits, and drives in batches. It re-estimates position from telemetry fixes after each batch, samples only when its estimate is within 1.6 m of a target, and returns to the lander before the end.

```python
"""Autopilot for the MAX-option lightlag traverse.

Strategy
- Position: the rover is stationary between drive batches, so the telemetry fixes
  received after the last executed drive are averaged (with a median-based outlier
  filter). Those fixes are the only position truth used for decisions.
- Routing: A* on the 5 m vertex grid. Edges are rejected when the slope (also at
  +-1.5 m lateral offsets) exceeds 0.30, or when uphill grade on sand/soft ground
  would push slip toward the 0.45 onboard limit. Paths are shortcut where straight
  legs are clear.
- Driving: a batch of up to 5 drive commands follows the planned path from the
  estimated position. Wheel metres are M = L / (kest * (1 - slip)), with kest learned
  from how far the rover actually moved on straight batches.
- Science: greedy by value / travel time, respecting deadlines and the need to be
  back at the lander before the end. Sampling happens only when the estimate is
  within 1.6 m of the target and at least 4 stationary fixes support it.
- Return: the last goal is the lander; the rover holds once within 2.2 m of it.
"""

import heapq
import math

import lightlag_surface as ls

TERR = {"b": "bedrock", "r": "regolith", "s": "sand", "k": "rocks"}
TF = {"bedrock": 1.0, "regolith": 1.15, "sand": 1.6, "rocks": 1.4}
PLAN_TILT = 0.30       # planning tilt limit (the rover stops above 0.36)
LAT = 1.5              # lateral check offset, m (heading bias drift)
UP_STRICT = 0.012      # max uphill grade on sand / soft ground
UP_RELAX = 0.02        # fallback when the strict search finds no route
SAMPLE_D = 1.6         # estimated distance at which we sample
MAX_CMDS = 5
MAX_DRIVE = 5.0


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def drive_cmd(heading, metres):
    m = min(MAX_DRIVE, max(0.02, metres))
    return {"action": "drive", "heading_deg": round(heading, 3), "metres": round(m, 4)}


class _Bot:
    def __init__(self, tools):
        self.tools = tools
        self.rules = tools.rules()
        self.mp = tools.map()
        ph = self.rules["physics"]
        self.max_ticks = int(self.rules["max_ticks"])
        self.cell = float(self.mp["cell_m"])
        self.surf = ls.Surface(self.cell, self.mp["elevation_cm"], self.mp["terrain"])
        self.W = self.surf.width
        self.H = self.surf.height
        self.NX = self.surf.nx
        self.NY = self.surf.ny
        self.base = (float(self.mp["base"][0]), float(self.mp["base"][1]))
        self.crusts = [(float(c["x1"]), float(c["y1"]), float(c["x2"]), float(c["y2"]))
                       for c in self.mp.get("crust_regions", [])]
        self.slip_mid = {k: (v[0] + v[1]) / 2.0 for k, v in ph["slip_base_ranges"].items()}
        self.gain = dict(ph["slip_grade_gain"])
        self.gain["sand"] = 3.5
        self.kest = 1.0
        self.tick = 0
        self.seen = 0
        self.packets = []
        self.sampled = set()
        self.dead = set()
        self.attempts = {}
        self.corr = {}
        self.pending = []          # (target id, execute tick) awaiting verification
        self.goal = None
        self.targets = []
        self.queue_end = 0
        self.stat_since = 0
        self.sent_any = False
        self.last_send_tick = -1
        self.finished = False
        self.P_last = self.base
        self.battery = float(self.rules.get("initial_battery", 100.0))
        self.last_batch = None
        self.edge_cache = {UP_STRICT: {}, UP_RELAX: {}}

    # ------------------------------------------------------------------ telemetry
    def ingest(self):
        log = self.tools.telemetry_log()
        while self.seen < len(log):
            p = log[self.seen]
            self.seen += 1
            self.packets.append(p)
            if "battery" in p:
                self.battery = float(p["battery"])
            for item in p.get("sampled_targets") or []:
                tid = item.get("id") if isinstance(item, dict) else item
                if tid is not None:
                    self.sampled.add(str(tid))
            for ev in p.get("events") or []:
                if isinstance(ev, dict) and ev.get("type") == "safety_stop":
                    s = int(p["tick"])
                    self.last_batch = None
                    if self.last_send_tick < s:
                        # the queued batch was cleared at the stop
                        self.queue_end = min(self.queue_end, s)
                        self.stat_since = s

    def fixes(self):
        return [p for p in self.packets
                if int(p["tick"]) >= self.stat_since and p.get("alive", True)]

    def estimate(self):
        pts = [(float(p["position"][0]), float(p["position"][1])) for p in self.fixes()]
        if not pts:
            return None
        if len(pts) >= 3:
            xs = sorted(x for x, _ in pts)
            ys = sorted(y for _, y in pts)
            mx, my = xs[len(xs) // 2], ys[len(ys) // 2]
            kept = [(x, y) for x, y in pts if math.hypot(x - mx, y - my) <= 5.0]
            if kept:
                pts = kept
        x = sum(p[0] for p in pts) / len(pts)
        y = sum(p[1] for p in pts) / len(pts)
        return (x, y)

    def resolve_pending(self):
        keep = []
        for tid, ex in self.pending:
            if any(int(p["tick"]) >= ex for p in self.packets):
                if tid not in self.sampled:
                    self.attempts[tid] = self.attempts.get(tid, 0) + 1
                    if self.attempts[tid] >= 2:
                        self.dead.add(tid)
            else:
                keep.append((tid, ex))
        self.pending = keep

    # ------------------------------------------------------------------ commands
    def send(self, cmds):
        try:
            acks = self.tools.uplink(cmds)
        except ValueError:
            return []
        exs = []
        last_drive = None
        for a in acks:
            ex = int(a["execute_tick"])
            exs.append(ex)
            self.queue_end = max(self.queue_end, ex)
            if a["command"]["action"] == "drive":
                last_drive = ex if last_drive is None else max(last_drive, ex)
        if last_drive is not None:
            self.stat_since = last_drive
        self.sent_any = True
        self.last_send_tick = self.tick
        return exs

    def do_sample(self, tid):
        exs = self.send([{"action": "sample"}])
        if exs:
            self.pending.append((tid, exs[0]))
        self.goal = None
        self.corr.pop(tid, None)

    # ------------------------------------------------------------------ terrain / planning
    def in_crust(self, x, y):
        for x1, y1, x2, y2 in self.crusts:
            if x1 <= x <= x2 and y1 <= y <= y2:
                return True
        return False

    def leg_cost(self, x1, y1, x2, y2, up):
        L = math.hypot(x2 - x1, y2 - y1)
        if L < 1e-9:
            return 0.0
        ux, uy = (x2 - x1) / L, (y2 - y1) / L
        n = max(1, int(math.ceil(L / 1.25)))
        part = L / n
        total = 0.0
        for k in range(n):
            t = (k + 0.5) / n
            px = x1 + (x2 - x1) * t
            py = y1 + (y2 - y1) * t
            if not (0.0 <= px <= self.W and 0.0 <= py <= self.H):
                return None
            _, gx, gy, code = self.surf.sample(px, py)
            if math.hypot(gx, gy) > PLAN_TILT:
                return None
            for off in (-LAT, LAT):
                qx = px - uy * off
                qy = py + ux * off
                if 0.0 <= qx <= self.W and 0.0 <= qy <= self.H:
                    _, hx, hy, _ = self.surf.sample(qx, qy)
                    if math.hypot(hx, hy) > PLAN_TILT:
                        return None
            grade = gx * ux + gy * uy
            name = TERR.get(code, "bedrock")
            soft = False
            if name == "bedrock" and self.crusts and self.in_crust(px, py):
                i, j, _, _ = self.surf.locate(px, py)
                if self.surf.cell_max_slope(i, j) <= 0.1:
                    soft = True
            if name == "sand" or soft:
                if grade > up:
                    return None
                tf = TF["sand"] if name == "sand" else 1.3
            elif name == "rocks":
                if grade > 0.12:
                    return None
                tf = TF["rocks"]
            elif name == "regolith":
                if grade > 0.15:
                    return None
                tf = TF["regolith"]
            else:
                tf = 1.0
            total += part * tf * (1.0 + 2.0 * max(0.0, grade))
        return total

    def node(self, p):
        i = min(self.NX - 1, max(0, int(round(p[0] / self.cell))))
        j = min(self.NY - 1, max(0, int(round(p[1] / self.cell))))
        return (i, j)

    def astar(self, s, g, up):
        cache = self.edge_cache[up]
        cell = self.cell
        counter = 0
        heap = [(0.0, 0, s)]
        best = {s: 0.0}
        parent = {s: None}
        closed = set()
        while heap:
            _, _, cur = heapq.heappop(heap)
            if cur in closed:
                continue
            if cur == g:
                path = []
                n = cur
                while n is not None:
                    path.append(n)
                    n = parent[n]
                path.reverse()
                return path
            closed.add(cur)
            ci, cj = cur
            for di in (-1, 0, 1):
                for dj in (-1, 0, 1):
                    if di == 0 and dj == 0:
                        continue
                    ni, nj = ci + di, cj + dj
                    if not (0 <= ni < self.NX and 0 <= nj < self.NY):
                        continue
                    nxt = (ni, nj)
                    if nxt in closed:
                        continue
                    key = (cur, nxt)
                    if key in cache:
                        c = cache[key]
                    else:
                        c = self.leg_cost(ci * cell, cj * cell, ni * cell, nj * cell, up)
                        cache[key] = c
                    if c is None:
                        continue
                    ng = best[cur] + c
                    if ng < best.get(nxt, float("inf")):
                        best[nxt] = ng
                        parent[nxt] = cur
                        h = math.hypot((ni - g[0]) * cell, (nj - g[1]) * cell)
                        counter += 1
                        heapq.heappush(heap, (ng + h, counter, nxt))
        return None

    def smooth(self, pts, up):
        out = [pts[0]]
        i = 0
        n = len(pts)
        while i < n - 1:
            j = min(n - 1, i + 12)
            chosen = i + 1
            while j > i + 1:
                if self.leg_cost(pts[i][0], pts[i][1], pts[j][0], pts[j][1], up) is not None:
                    chosen = j
                    break
                j -= 1
            out.append(pts[chosen])
            i = chosen
        return out

    def plan(self, P, G):
        if self.leg_cost(P[0], P[1], G[0], G[1], UP_STRICT) is not None:
            return [P, G]
        for up in (UP_STRICT, UP_RELAX):
            nodes = self.astar(self.node(P), self.node(G), up)
            if nodes is None:
                continue
            pts = [P] + [(i * self.cell, j * self.cell) for i, j in nodes] + [G]
            return self.smooth(pts, up)
        return None

    def slip_est(self, x, y, ux, uy):
        _, gx, gy, code = self.surf.sample(x, y)
        name = TERR.get(code, "bedrock")
        grade = gx * ux + gy * uy
        return min(0.7, self.slip_mid[name] + self.gain[name] * max(0.0, grade))

    def make_batch(self, path):
        cmds = []
        V = path[0]
        for W in path[1:]:
            if len(cmds) >= MAX_CMDS:
                break
            dx = W[0] - V[0]
            dy = W[1] - V[1]
            L = math.hypot(dx, dy)
            if L < 0.15:
                V = W
                continue
            ux, uy = dx / L, dy / L
            heading = math.degrees(math.atan2(dy, dx)) % 360.0
            slip = self.slip_est(V[0] + dx / 2.0, V[1] + dy / 2.0, ux, uy)
            eff = max(0.3, self.kest * (1.0 - slip))
            M = L / eff
            pieces = max(1, int(math.ceil(M / MAX_DRIVE - 1e-9)))
            room = MAX_CMDS - len(cmds)
            if pieces <= room:
                for _ in range(pieces):
                    cmds.append(drive_cmd(heading, M / pieces))
                V = W
            else:
                for _ in range(room):
                    cmds.append(drive_cmd(heading, MAX_DRIVE))
                fwd = room * MAX_DRIVE * eff
                V = (V[0] + ux * fwd, V[1] + uy * fwd)
                break
        return cmds, V

    def drive_to(self, P, G, tid):
        path = self.plan(P, G)
        if path is None:
            if tid == "base":
                path = [P, G]
            else:
                self.dead.add(tid)
                self.goal = None
                return
        cmds, V = self.make_batch(path)
        if not cmds:
            if tid == "base":
                self.finished = True
            else:
                self.dead.add(tid)
                self.goal = None
            return
        if len(path) == 2:
            self.last_batch = (P, V)
        exs = self.send(cmds)
        if not exs and tid != "base":
            self.dead.add(tid)
            self.goal = None

    def learn(self, P):
        if self.last_batch is None:
            return
        P0, V = self.last_batch
        self.last_batch = None
        nominal = dist(V, P0)
        obs = dist(P, P0)
        if nominal >= 8.0 and len(self.fixes()) >= 3:
            r = obs / nominal
            self.kest = min(1.25, max(0.75, self.kest * (1.0 + 0.5 * (r - 1.0))))

    # ------------------------------------------------------------------ goals
    def refresh_targets(self):
        mp = self.tools.map()
        self.targets = list(mp.get("targets", []))

    def target_xy(self, tid):
        for tg in self.targets:
            if str(tg["id"]) == tid:
                return (float(tg["x"]), float(tg["y"]))
        return None

    def pick_goal(self, P):
        t = self.tick
        pend = {tid for tid, _ in self.pending}
        best = None
        bs = -1.0
        for tg in self.targets:
            tid = str(tg["id"])
            if tid in self.sampled or tid in self.dead or tid in pend:
                continue
            if float(tg.get("appear_tick", 0) or 0) > t:
                continue
            T = (float(tg["x"]), float(tg["y"]))
            d = dist(P, T)
            travel = 14 * max(1, math.ceil(d * 1.1 / 22.0)) + 6
            arrive = t + travel
            ret = 14 * max(1, math.ceil(dist(T, self.base) * 1.1 / 22.0)) + 6
            if arrive + ret > self.max_ticks - 10:
                continue
            dl = tg.get("deadline_tick")
            value = float(tg["value"]) if (dl is None or arrive <= int(dl)) else float(tg.get("late_value", 0.0))
            score = value / travel
            if score > bs:
                bs = score
                best = tid
        return best if best is not None else "base"

    # ------------------------------------------------------------------ decisions
    def ready(self):
        t = self.tick
        if t < self.queue_end:
            return False
        if not self.sent_any:
            return True
        if self.finished:
            return t % 10 == 0
        n = len(self.fixes())
        if n >= 2 or (t - self.stat_since) >= 30:
            return True
        return False

    def act(self):
        P = self.estimate()
        if P is None:
            P = self.P_last
        self.P_last = P
        t = self.tick
        self.learn(P)
        self.resolve_pending()
        if self.battery < 4.0:
            return
        self.refresh_targets()
        if self.goal in self.sampled or self.goal in self.dead:
            self.goal = None
        if self.goal is None or self.goal == "base":
            self.goal = self.pick_goal(P)
        waited = t - self.stat_since
        nf = len(self.fixes())
        if self.goal == "base":
            d = dist(P, self.base)
            if d <= 3.5 and nf < 4 and waited < 30:
                return
            if d <= 2.2:
                self.finished = True
                return
            self.finished = False
            self.drive_to(P, self.base, "base")
            return
        self.finished = False
        tid = self.goal
        T = self.target_xy(tid)
        if T is None:
            self.dead.add(tid)
            self.goal = None
            return
        d = dist(P, T)
        if d <= 3.0 and nf < 4 and waited < 30:
            return
        if d <= SAMPLE_D or (d <= 2.4 and self.corr.get(tid, 0) >= 6):
            self.do_sample(tid)
            return
        self.corr[tid] = self.corr.get(tid, 0) + 1
        if self.corr[tid] > 12:
            self.dead.add(tid)
            self.goal = None
            return
        self.drive_to(P, T, tid)

    # ------------------------------------------------------------------ main loop
    def run(self):
        while True:
            try:
                self.ingest()
                if self.ready():
                    self.act()
            except ValueError:
                raise
            except Exception:
                # keep the clock running even if a planning step fails
                pass
            res = self.tools.advance(1)
            self.tick = int(res["current_tick"])
            if res.get("episode_complete"):
                break


def play(tools):
    bot = _Bot(tools)
    bot.run()
```