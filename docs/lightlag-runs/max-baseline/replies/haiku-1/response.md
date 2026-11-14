```python
"""Autopilot for the MAX lightlag traverse.

Approach:
- Dead reckoning from the telemetry: each drive tick adds its visual odometry along the commanded
  heading, and each noisy position fix is blended in with a fixed gain. A lost packet on a drive
  tick is bridged with the planned drive length.
- Routes are A* paths on a 5 m grid. They respect the tilt limit with margin, avoid soft sand and
  penalise crust regions.
- The rover keeps about eight drives queued ahead of its estimate, so link latency does not stall it.
- At a target the rover stops, waits for fixes to settle, corrects with a short drive if needed,
  and then queues the sample together with the next leg.
- Targets are picked greedily by value per tick, respecting deadlines and the time needed to return.
- Near the end the rover heads home and localises inside the base radius.
"""

import heapq
import math

import lightlag_surface as ls

DRIVE_MAX = 5.0
GRID_M = 5.0
ARRIVE_M = 3.0
SAMPLE_OK_M = 2.0
SAMPLE_MAX_M = 2.5
HOME_OK_M = 2.5
QUEUE_TARGET = 8
PLAN_SPEED = 3.0
MIN_FIXES = 3
TERRAIN = ls.TERRAIN_CODES


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


class Autopilot:
    def __init__(self, tools):
        self.tools = tools
        rules = tools.rules()
        self.max_ticks = int(rules["max_ticks"])
        self.battery = float(rules.get("initial_battery", 100.0))
        grid = tools.map()
        self.width = float(grid["width"])
        self.height = float(grid["height"])
        self.surface = ls.Surface(float(grid["cell_m"]), grid["elevation_cm"], grid["terrain"])
        bx, by = grid["base"]
        self.base = (float(bx), float(by))
        self.crusts = []
        for c in grid.get("crust_regions", []) or []:
            self.crusts.append((float(c["x1"]), float(c["y1"]), float(c["x2"]), float(c["y2"])))
        self.targets = {}
        self._absorb_targets(grid)
        self.map_tick = 0
        self.map_dirty = False
        self.r = 0.85                      # ground metres per commanded metre (learned)
        self.est = [self.base[0], self.base[1]]
        self.last_tick = -1
        self.log_seen = 0
        self.fix_ticks = []
        self.last_move = -1
        self.orders = {}                   # execute_tick -> order dict
        self.sampled = set()
        self.sample_pending = {}           # target id -> execute tick (None until acknowledged)
        self.attempts = {}
        self.goal = None
        self.goal_start = 0
        self.corrections = 0
        self.path = None
        self.path_key = None
        self.path_idx = 0
        self.home_done = False
        self.last_goal_check = -100
        self.edge_cache = {}
        self.now = 0
        self.dead = False
        self.nxn = int(round(self.width / GRID_M)) + 1
        self.nyn = int(round(self.height / GRID_M)) + 1

    # ------------------------------------------------------------------ map and targets
    def _absorb_targets(self, grid):
        for t in grid.get("targets", []) or []:
            tid = str(t["id"])
            dl = t.get("deadline_tick")
            self.targets[tid] = {
                "id": tid,
                "x": float(t["x"]),
                "y": float(t["y"]),
                "value": float(t["value"]),
                "deadline": None if dl is None else float(dl),
                "late": float(t.get("late_value", 0.0) or 0.0),
            }

    def _refresh_map(self, now):
        grid = self.tools.map()
        self._absorb_targets(grid)
        self.map_tick = now
        self.map_dirty = False

    # ------------------------------------------------------------------ telemetry
    def ingest(self):
        log = self.tools.telemetry_log()
        fresh = log[self.log_seen:]
        self.log_seen = len(log)
        if fresh:
            by_tick = {}
            for p in fresh:
                by_tick[int(p["tick"])] = p
            top = max(by_tick)
            for k in range(self.last_tick + 1, top + 1):
                p = by_tick.get(k)
                if p is None:
                    # Lost packet: bridge a drive tick with the planned distance.
                    order = self.orders.get(k)
                    if order is not None and order["action"] == "drive":
                        self._dead_reckon(order["heading"], order["metres"] * self.r)
                        self.last_move = k
                else:
                    self._apply(k, p)
                self.last_tick = k
        if len(self.fix_ticks) > 200:
            self.fix_ticks = self.fix_ticks[-100:]
        for e in [e for e in self.orders if e < self.last_tick - 5]:
            del self.orders[e]

    def _apply(self, k, p):
        if p.get("battery") is not None:
            self.battery = float(p["battery"])
        if p.get("alive") is False:
            self.dead = True
        for sid in p.get("sampled_targets") or []:
            name = sid if isinstance(sid, str) else sid.get("id")
            if name is not None:
                self.sampled.add(str(name))
        for ev in p.get("events") or []:
            kind = ev.get("type")
            if kind == "safety_stop":
                self.clear_after(k)
            elif kind == "target_discovered":
                self.map_dirty = True
        pos = p.get("position")
        if k == 0:
            if pos is not None:
                self.est = [float(pos[0]), float(pos[1])]
            return
        v = float(p.get("visual_odometry") or 0.0)
        w = float(p.get("wheel_odometry") or 0.0)
        order = self.orders.get(k)
        if order is not None and order["action"] == "drive":
            self.last_move = k
            if v < 0.02:
                # The rover did not move on a drive tick: a safety stop cleared the queue.
                self.clear_after(k)
            elif w >= 0.5:
                ratio = min(1.1, max(0.5, v / w))
                self.r = min(1.05, max(0.6, 0.95 * self.r + 0.05 * ratio))
        if v > 0.0:
            self._dead_reckon(float(p.get("heading_deg") or 0.0), v)
        if pos is not None:
            zx, zy = float(pos[0]), float(pos[1])
            dx = zx - self.est[0]
            dy = zy - self.est[1]
            gain = 0.3 if math.hypot(dx, dy) < 7.0 else 0.08
            self.est[0] += gain * dx
            self.est[1] += gain * dy
            self.fix_ticks.append(k)

    def _dead_reckon(self, heading_deg, dist):
        a = math.radians(heading_deg)
        self.est[0] += dist * math.cos(a)
        self.est[1] += dist * math.sin(a)

    def clear_after(self, k):
        for e in list(self.orders):
            if e > k:
                del self.orders[e]
        for tid, e in list(self.sample_pending.items()):
            if e is not None and e > k:
                del self.sample_pending[tid]
        self.path = None

    def _settle_samples(self):
        for tid, ex in list(self.sample_pending.items()):
            if ex is None:
                continue
            if tid in self.sampled:
                del self.sample_pending[tid]
            elif self.last_tick >= ex + 3:
                self.attempts[tid] = self.attempts.get(tid, 0) + 1
                del self.sample_pending[tid]

    # ------------------------------------------------------------------ estimates
    def pending_drives(self):
        return [o for e, o in self.orders.items() if e > self.last_tick and o["action"] == "drive"]

    def plan_pos(self):
        x, y = self.est[0], self.est[1]
        for e, o in self.orders.items():
            if e > self.last_tick and o["action"] == "drive":
                d = o["metres"] * self.r
                a = math.radians(o["heading"])
                x += d * math.cos(a)
                y += d * math.sin(a)
        return (x, y)

    def fixes_since_move(self):
        return sum(1 for t in self.fix_ticks if t > self.last_move)

    def _queued(self):
        return sum(1 for e in self.orders if e >= self.now)

    # ------------------------------------------------------------------ terrain and paths
    def _in_crust(self, x, y):
        for x1, y1, x2, y2 in self.crusts:
            if x1 <= x <= x2 and y1 <= y <= y2:
                return True
        return False

    def _point_cost(self, x, y):
        _, gx, gy, code = self.surface.sample(x, y)
        s = math.hypot(gx, gy)
        if s > 0.30:
            return None
        name = TERRAIN.get(code, "bedrock")
        if name == "sand":
            if s > 0.04:
                return None
            mult = 5.0
        elif name == "rocks":
            if s > 0.18:
                return None
            mult = 1.8
        elif name == "regolith":
            if s > 0.18:
                return None
            mult = 1.2
        else:
            mult = 1.0
        if self._in_crust(x, y):
            mult *= 2.5
        return mult * (1.0 + 2.0 * s)

    def _edge_cost(self, a, b):
        key = (a, b)
        if key in self.edge_cache:
            return self.edge_cache[key]
        length = _dist(a, b)
        n = max(1, int(math.ceil(length)))
        total = 0.0
        result = None
        for k in range(n + 1):
            t = k / n
            c = self._point_cost(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
            if c is None:
                break
            total += c
        else:
            result = length * total / (n + 1)
        self.edge_cache[key] = result
        return result

    def plan_path(self, start, goal):
        def snap(p):
            i = min(self.nxn - 2, max(1, int(round(p[0] / GRID_M))))
            j = min(self.nyn - 2, max(1, int(round(p[1] / GRID_M))))
            return (i, j)

        def xy(n):
            return (n[0] * GRID_M, n[1] * GRID_M)

        s = snap(start)
        g = snap(goal)
        if s == g:
            return [start, goal]
        best = {s: 0.0}
        came = {}
        closed = set()
        heap = [(_dist(xy(s), xy(g)), 0.0, s)]
        found = False
        expansions = 0
        while heap and expansions < 6000:
            _, cost, cur = heapq.heappop(heap)
            if cur in closed:
                continue
            closed.add(cur)
            expansions += 1
            if cur == g:
                found = True
                break
            for di in (-1, 0, 1):
                for dj in (-1, 0, 1):
                    if di == 0 and dj == 0:
                        continue
                    nb = (cur[0] + di, cur[1] + dj)
                    if not (1 <= nb[0] <= self.nxn - 2 and 1 <= nb[1] <= self.nyn - 2):
                        continue
                    if nb in closed:
                        continue
                    ec = self._edge_cost(xy(cur), xy(nb))
                    if ec is None:
                        continue
                    ng = cost + ec
                    if ng < best.get(nb, float("inf")):
                        best[nb] = ng
                        came[nb] = cur
                        heapq.heappush(heap, (ng + _dist(xy(nb), xy(g)), ng, nb))
        if not found:
            return [start, goal]
        nodes = [g]
        while nodes[-1] != s:
            nodes.append(came[nodes[-1]])
        nodes.reverse()
        return [start] + [xy(n) for n in nodes] + [goal]

    def _off_path(self, p):
        if not self.path:
            return True
        return min(_dist(p, v) for v in self.path) > 4.0

    def _next_drive(self, sim, g):
        key = g["id"]
        if self.path is None or self.path_key != key or self._off_path(sim):
            self.path = self.plan_path(sim, (g["x"], g["y"]))
            self.path_key = key
            self.path_idx = 0
        path = self.path
        n = len(path)
        bi = min(self.path_idx, n - 1)
        bd = _dist(sim, path[bi])
        for i in range(bi, min(n, bi + 10)):
            d = _dist(sim, path[i])
            if d < bd:
                bd, bi = d, i
        self.path_idx = bi
        j = min(bi + 1, n - 1)
        while j < n - 1 and _dist(sim, path[j]) < 2.0:
            j += 1
        tx, ty = path[j]
        dx = tx - sim[0]
        dy = ty - sim[1]
        d = math.hypot(dx, dy)
        if d < 0.3:
            return None
        metres = min(DRIVE_MAX, max(0.2, d / self.r))
        return {"action": "drive", "heading": math.degrees(math.atan2(dy, dx)), "metres": metres}

    def _drive_toward(self, src, dst):
        dx = dst[0] - src[0]
        dy = dst[1] - src[1]
        d = math.hypot(dx, dy)
        return {"action": "drive", "heading": math.degrees(math.atan2(dy, dx)),
                "metres": min(DRIVE_MAX, max(0.2, d / self.r))}

    # ------------------------------------------------------------------ goals
    def _base_goal(self):
        return {"kind": "base", "id": "base", "x": self.base[0], "y": self.base[1]}

    def _set_goal(self, g, now):
        self.goal = g
        self.goal_start = now
        self.corrections = 0
        self.path = None

    def choose_goal(self, plan, now):
        best_id, best_score = None, -1.0
        for tid, t in self.targets.items():
            if tid in self.sampled or tid in self.sample_pending:
                continue
            if self.attempts.get(tid, 0) >= 2:
                continue
            xy = (t["x"], t["y"])
            travel = 1.25 * _dist(plan, xy) / PLAN_SPEED + 10.0
            eta = now + travel
            home = 1.25 * _dist(xy, self.base) / PLAN_SPEED + 14.0
            if eta + home > self.max_ticks - 3:
                continue
            dl = t["deadline"]
            value = t["value"] if (dl is None or eta <= dl) else t["late"]
            score = value / travel
            if score > best_score:
                best_id, best_score = tid, score
        if best_id is None:
            return self._base_goal()
        t = self.targets[best_id]
        return {"kind": "target", "id": best_id, "x": t["x"], "y": t["y"]}

    def must_go_home(self, plan, now):
        return now + 1.25 * _dist(plan, self.base) / PLAN_SPEED + 25 >= self.max_ticks

    # ------------------------------------------------------------------ control
    def decide(self):
        self.ingest()
        if self.dead:
            return
        now = self.now
        self._settle_samples()
        if self.map_dirty or now - self.map_tick >= 10:
            self._refresh_map(now)
        plan = self.plan_pos()

        if self.goal is None or (self.goal["kind"] == "target" and self.goal["id"] in self.sampled):
            self._set_goal(self.choose_goal(plan, now), now)
        g = self.goal
        if g["kind"] == "target" and now - self.goal_start > 160:
            self.attempts[g["id"]] = self.attempts.get(g["id"], 0) + 2
            self._set_goal(self.choose_goal(plan, now), now)
        g = self.goal
        if g["kind"] != "base" and self.must_go_home(plan, now):
            self._set_goal(self._base_goal(), now)
        g = self.goal
        if g["kind"] == "base" and self.home_done and now - self.last_goal_check >= 10:
            self.last_goal_check = now
            cand = self.choose_goal(plan, now)
            if cand["kind"] == "target":
                self._set_goal(cand, now)
        g = self.goal

        cmds = []
        corrected = False
        goal_xy = (g["x"], g["y"])
        if (_dist(plan, goal_xy) <= ARRIVE_M and not self.pending_drives()
                and self.fixes_since_move() >= MIN_FIXES):
            ed = _dist(self.est, goal_xy)
            if g["kind"] == "target":
                if ed <= SAMPLE_OK_M or self.corrections >= 2:
                    if ed <= SAMPLE_MAX_M:
                        self.sample_pending[g["id"]] = None
                        cmds.append({"action": "sample", "target": g["id"]})
                    else:
                        self.attempts[g["id"]] = self.attempts.get(g["id"], 0) + 1
                    self._set_goal(self.choose_goal(plan, now), now)
                    g = self.goal
                else:
                    cmds.append(self._drive_toward(self.est, goal_xy))
                    self.corrections += 1
                    corrected = True
            else:
                if ed <= HOME_OK_M or self.corrections >= 4:
                    self.home_done = True
                else:
                    cmds.append(self._drive_toward(self.est, goal_xy))
                    self.corrections += 1
                    corrected = True

        if not corrected and self.battery >= 6.0:
            goal_xy = (g["x"], g["y"])
            sim = plan
            added = 0
            while (_dist(sim, goal_xy) > ARRIVE_M
                   and self._queued() + len(cmds) < QUEUE_TARGET
                   and added < 8):
                c = self._next_drive(sim, g)
                if c is None:
                    break
                cmds.append(c)
                added += 1
                a = math.radians(c["heading"])
                sim = (sim[0] + c["metres"] * self.r * math.cos(a),
                       sim[1] + c["metres"] * self.r * math.sin(a))

        if cmds:
            self._send(cmds)

    def _send(self, cmds):
        for i in range(0, len(cmds), 5):
            chunk = cmds[i:i + 5]
            payload = []
            for c in chunk:
                if c["action"] == "drive":
                    payload.append({"action": "drive",
                                    "heading_deg": round(c["heading"], 3),
                                    "metres": round(c["metres"], 4)})
                else:
                    payload.append({"action": "sample"})
            try:
                acks = self.tools.uplink(payload)
            except ValueError:
                for c in chunk:
                    if c["action"] == "sample":
                        self.sample_pending.pop(c["target"], None)
                continue
            for c, ack in zip(chunk, acks):
                ex = int(ack["execute_tick"])
                if c["action"] == "drive":
                    self.orders[ex] = {"action": "drive",
                                       "heading": round(c["heading"], 3),
                                       "metres": round(c["metres"], 4)}
                else:
                    self.orders[ex] = {"action": "sample"}
                    self.sample_pending[c["target"]] = ex

    def run(self):
        while True:
            try:
                self.decide()
            except Exception:
                # Keep the clock running; the next cycle plans again from the latest state.
                pass
            res = self.tools.advance(1)
            self.now = int(res["current_tick"])
            if res.get("episode_complete"):
                break


def play(tools):
    Autopilot(tools).run()
```