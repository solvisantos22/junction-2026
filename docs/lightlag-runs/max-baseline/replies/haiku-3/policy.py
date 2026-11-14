"""Autopilot for the MAX lightlag traverse.

Approach
--------
* Routes are planned on a 10 m grid with A* over the published ground model, using
  conservative slip limits (upper ends of the hidden ranges, uphill sand barred) and a
  slope limit well below max_tilt, so the rover avoids crater walls, the scarp and
  ground that would trip the onboard slip check.
* A route is uplinked in one go (one tick per drive). Headings are corrected for the
  cross-slope drift predicted by the published side-slip formula.
* After a route the rover is still. Its position fixes are averaged robustly, and the
  route is repeated from the new estimate until the estimate lies inside the sampling
  radius. The next route is uplinked behind the sample, so the link delay is not wasted.
* Targets are chosen greedily by value per tick, with deadlines, the return to the
  lander and the energy budget kept feasible.
"""

import heapq
import math

from lightlag_surface import TERRAIN_CODES, Surface, drive

GRID = 10.0             # planning grid spacing, metres
PLAN_SLOPE = 0.25       # planned slope limit (max_tilt is 0.36)
SAND_UPHILL = 0.015     # uphill grade allowed on sand (slip would reach the 0.45 check)
SLIP_HI_LIMIT = 0.40    # worst-case slip allowed on other terrain
SAMPLE_OK = 1.6         # estimated distance to target that is good enough to sample
SAMPLE_OK_LAST = 2.2    # looser limit on the last attempt
FIX_RADIUS = 4.5        # fixes further than this from the median are outliers
HOME_OK = 2.2           # estimated distance to lander that counts as home
VISIT_ATTEMPTS = 5
SOLAR_FLOOR = 0.8       # conservative panel efficiency


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


class Pilot:
    def __init__(self, tools):
        self.tools = tools
        rules = tools.rules()
        self.phys = rules["physics"]
        self.max_ticks = int(rules["max_ticks"])
        self.battery = float(rules.get("initial_battery", 100.0))
        self.battery_tick = -1
        self.solar_peak = float(rules.get("solar_peak", 2.8))
        self.sun_margin = float(rules.get("sun_margin_ticks", 56))

        mp = tools.map()
        self.surf = Surface(float(mp["cell_m"]), mp["elevation_cm"], mp["terrain"])
        self.width = float(mp["width"])
        self.height = float(mp["height"])
        self.base = (float(mp["base"][0]), float(mp["base"][1]))
        self.crusts = [(float(c["x1"]), float(c["y1"]), float(c["x2"]), float(c["y2"]))
                       for c in mp.get("crust_regions", [])]

        self.targets = {}
        self.now = 0
        self.complete = False
        self.dead = False
        self.seen = 0
        self.fixes = []            # (tick, x, y) noisy position reports
        self.sampled = set()
        self.pending = {}          # target id -> execute tick of its sample command
        self.tried = {}
        self.exec_drives = {}      # execute tick -> commanded metres
        self.stop_ticks = []
        self.route_send = 0
        self.P = self.base         # current best estimate of the true position
        self.r = {"bedrock": 1.0, "regolith": 1.0, "rocks": 0.95, "sand": 0.85}

        ranges = self.phys["slip_base_ranges"]
        self.base_mid = {k: 0.5 * (v[0] + v[1]) for k, v in ranges.items()}
        self.base_hi = {k: float(v[1]) for k, v in ranges.items()}
        self.gain = {k: float(v) for k, v in self.phys["slip_grade_gain"].items()}
        self.cost = {k: float(v) for k, v in self.phys["drive_cost_per_wheel_m"].items()}
        self.climb = float(self.phys["climb_cost_per_m"])
        self.nx = int(round(self.width / GRID)) + 1
        self.ny = int(round(self.height / GRID)) + 1
        self.edge_cache = {}

    # ------------------------------------------------------------------ telemetry
    def ingest(self):
        log = self.tools.telemetry_log()
        for pkt in log[self.seen:]:
            self._process(pkt)
        self.seen = len(log)

    def _process(self, pkt):
        tick = int(pkt["tick"])
        if pkt.get("battery") is not None and tick >= self.battery_tick:
            self.battery = float(pkt["battery"])
            self.battery_tick = tick
        if not pkt.get("alive", True):
            self.dead = True
        pos = pkt.get("position")
        if pos is not None:
            self.fixes.append((tick, float(pos[0]), float(pos[1])))
        for sid in pkt.get("sampled_targets") or []:
            self.sampled.add(sid.get("id") if isinstance(sid, dict) else sid)
        stopped = False
        for ev in pkt.get("events") or []:
            if isinstance(ev, dict) and ev.get("type") == "safety_stop":
                stopped = True
                self.stop_ticks.append(tick)
        if not stopped:
            m = self.exec_drives.get(tick)
            wheel = float(pkt.get("wheel_odometry") or 0.0)
            vis = float(pkt.get("visual_odometry") or 0.0)
            name = pkt.get("terrain")
            if m and wheel > 0.0 and vis > 0.0 and name in self.r:
                obs = vis / m
                if 0.5 <= obs <= 1.5:
                    self.r[name] = min(1.3, max(0.6, 0.7 * self.r[name] + 0.3 * obs))

    def step(self, n=1):
        if self.complete:
            return
        if self.now >= self.max_ticks:
            self.complete = True
            return
        n = max(1, min(5, int(n), self.max_ticks - self.now))
        res = self.tools.advance(n)
        self.now = int(res["current_tick"])
        if res.get("episode_complete") or self.now >= self.max_ticks:
            self.complete = True
        self.ingest()
        self.check_pending()

    def check_pending(self):
        for tid, ex in list(self.pending.items()):
            if tid in self.sampled:
                del self.pending[tid]
            elif self.now >= ex + 12:
                # no sample confirmation: the target stays available for one retry
                del self.pending[tid]

    def still_tick(self, last_exec):
        s = last_exec
        for stop in self.stop_ticks:
            if stop >= self.route_send and stop < s:
                s = stop
        return s

    def fix_estimate(self, still):
        pts = [(x, y) for (t, x, y) in self.fixes if t >= still]
        if not pts:
            return None
        if len(pts) >= 3:
            xs = sorted(p[0] for p in pts)
            ys = sorted(p[1] for p in pts)
            mx = xs[len(xs) // 2]
            my = ys[len(ys) // 2]
            kept = [p for p in pts if math.hypot(p[0] - mx, p[1] - my) <= FIX_RADIUS]
            if len(kept) >= 2:
                pts = kept
        n = len(pts)
        return (sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n)

    def wait_still(self, last_exec):
        """Advance until the rover has been still long enough to average fixes."""
        while True:
            if self.complete or self.dead:
                return None
            still = self.still_tick(last_exec)
            n = sum(1 for f in self.fixes if f[0] >= still)
            if n >= 4 and self.now >= still + 6:
                break
            if n >= 1 and self.now >= still + 18:
                break
            if self.now >= still + 30:
                return None
            self.step(1)
        return self.fix_estimate(still)

    # ------------------------------------------------------------------ map and planning
    def refresh_map(self):
        mp = self.tools.map()
        for t in mp.get("targets", []):
            tid = t["id"]
            if tid in self.targets:
                continue
            dl = t.get("deadline_tick")
            self.targets[tid] = {
                "x": float(t["x"]),
                "y": float(t["y"]),
                "value": float(t["value"]),
                "deadline": None if dl is None else int(dl),
                "late": float(t.get("late_value", 0.0) or 0.0),
                "appear": int(t.get("appear_tick", 0) or 0),
            }

    def in_crust(self, x, y):
        for x1, y1, x2, y2 in self.crusts:
            if x1 <= x <= x2 and y1 <= y <= y2:
                return True
        return False

    def terrain_name(self, x, y):
        return TERRAIN_CODES[self.surf.sample(x, y)[3]]

    def r_of(self, p):
        return self.r.get(self.terrain_name(p[0], p[1]), 0.9)

    def slope_at(self, p):
        _, gx, gy, _ = self.surf.sample(p[0], p[1])
        return math.hypot(gx, gy)

    def nearest_node(self, p):
        i = int(round(p[0] / GRID))
        j = int(round(p[1] / GRID))
        return (min(self.nx - 2, max(1, i)), min(self.ny - 2, max(1, j)))

    @staticmethod
    def node_xy(n):
        return (n[0] * GRID, n[1] * GRID)

    def edge(self, a, b):
        key = (a[0], a[1], b[0], b[1])
        if key not in self.edge_cache:
            self.edge_cache[key] = self._edge_eval(a, b)
        return self.edge_cache[key]

    def _edge_eval(self, a, b):
        """Predicted energy of a straight segment, or None if it is not safe to drive."""
        L = _dist(a, b)
        if L < 1e-6:
            return 0.0
        ux = (b[0] - a[0]) / L
        uy = (b[1] - a[1]) / L
        n = max(1, int(math.ceil(L)))
        ds = L / n
        xs, ys, hs, gxs, gys, cs = [], [], [], [], [], []
        for k in range(n + 1):
            x = a[0] + ux * ds * k
            y = a[1] + uy * ds * k
            h, gx, gy, code = self.surf.sample(x, y)
            xs.append(x)
            ys.append(y)
            hs.append(h)
            gxs.append(gx)
            gys.append(gy)
            cs.append(code)
        cost = 0.0
        for k in range(n):
            s = math.hypot(gxs[k], gys[k])
            if s > PLAN_SLOPE:
                return None
            g = gxs[k] * ux + gys[k] * uy
            gp = g if g > 0.0 else 0.0
            name = TERRAIN_CODES[cs[k]]
            if name == "bedrock" and s <= 0.1 and self.in_crust(xs[k], ys[k]):
                name = "sand"          # crust may hide soft sand on flat cells
            if name == "sand":
                if g > SAND_UPHILL:
                    return None
                slip = self.base_mid["sand"] + self.gain["sand"] * gp
            else:
                if self.base_hi[name] + self.gain[name] * gp > SLIP_HI_LIMIT:
                    return None
                slip = self.base_mid[name] + self.gain[name] * gp
            cost += ds * self.cost[name] / max(0.2, 1.0 - slip)
            cost += self.climb * max(0.0, hs[k + 1] - hs[k])
        if math.hypot(gxs[n], gys[n]) > PLAN_SLOPE:
            return None
        return cost

    def astar(self, s, g):
        goal_xy = self.node_xy(g)
        heap = [(0.0, 0.0, s)]
        best = {s: 0.0}
        came = {}
        closed = set()
        while heap:
            _, gc, n = heapq.heappop(heap)
            if n in closed:
                continue
            if n == g:
                break
            closed.add(n)
            nxy = self.node_xy(n)
            for di in (-1, 0, 1):
                for dj in (-1, 0, 1):
                    if di == 0 and dj == 0:
                        continue
                    m = (n[0] + di, n[1] + dj)
                    if not (1 <= m[0] <= self.nx - 2 and 1 <= m[1] <= self.ny - 2):
                        continue
                    if m in closed:
                        continue
                    mxy = self.node_xy(m)
                    c = self.edge(nxy, mxy)
                    if c is None:
                        continue
                    ng = gc + c
                    if ng < best.get(m, float("inf")):
                        best[m] = ng
                        came[m] = n
                        heapq.heappush(heap, (ng + 0.3 * _dist(mxy, goal_xy), ng, m))
        if g not in best:
            return None
        path = [g]
        while path[-1] != s:
            path.append(came[path[-1]])
        path.reverse()
        return path, best[g]

    def plan(self, start, goal):
        """Waypoints from start to goal and their predicted energy, or None."""
        if self.slope_at(goal) > PLAN_SLOPE:
            return None
        s = self.nearest_node(start)
        g = self.nearest_node(goal)
        if s == g:
            e = self.edge(start, goal)
            if e is None:
                return None
            return [start, goal], e
        res = self.astar(s, g)
        if res is None:
            return None
        nodes, cost = res
        pts = [start] + [self.node_xy(n) for n in nodes] + [goal]
        last = self.edge(pts[-2], goal)
        if last is None:
            return None
        return pts, cost + last

    def sim_drift(self, start, heading, metres):
        """Sideways displacement (metres, to the right) predicted by the published model."""
        try:
            res = drive(self.surf, self.phys, start[0], start[1], heading, metres, self.base_mid)
        except Exception:
            return None
        ex = res["x"] - start[0]
        ey = res["y"] - start[1]
        rad = math.radians(heading)
        return ex * math.sin(rad) - ey * math.cos(rad)

    def route_commands(self, pts):
        cmds = []
        for a, b in zip(pts, pts[1:]):
            L = _dist(a, b)
            if L < 0.05:
                continue
            h0 = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
            mid = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
            W = L / self.r_of(mid)
            h = h0
            drift = self.sim_drift(a, h0, W)
            if drift is not None:
                h = h0 + math.degrees(math.atan2(drift, L))
            h %= 360.0
            n = max(1, int(math.ceil(W / 5.0 - 1e-9)))
            w = min(5.0, max(0.02, round(W / n, 4)))
            for _ in range(n):
                cmds.append({"action": "drive", "heading_deg": round(h, 3), "metres": w})
        return cmds

    def solar_gain(self, t0, t1):
        span = self.max_ticks + 2 * self.sun_margin
        total = 0.0
        for t in range(int(t0), int(t1)):
            total += self.solar_peak * SOLAR_FLOOR * math.sin(math.pi * (t + self.sun_margin) / span)
        return total

    # ------------------------------------------------------------------ commands
    def send(self, cmds):
        last = None
        for i in range(0, len(cmds), 5):
            acks = self.tools.uplink(cmds[i:i + 5])
            for a in acks:
                ex = int(a["execute_tick"])
                c = a.get("command", {})
                if c.get("action") == "drive":
                    self.exec_drives[ex] = float(c["metres"])
                last = ex if last is None else max(last, ex)
        return last

    def do_sample(self, tid):
        ex = self.send([{"action": "sample"}])
        self.pending[tid] = ex if ex is not None else self.now + 6

    # ------------------------------------------------------------------ mission
    def choose(self):
        self.refresh_map()
        best, best_score = None, 0.0
        for tid, T in self.targets.items():
            if tid in self.sampled or tid in self.pending or self.tried.get(tid, 0) >= 2:
                continue
            g = (T["x"], T["y"])
            d1 = _dist(self.P, g)
            d2 = _dist(g, self.base)
            trav = 5.0 + 0.3 * d1
            t_s = max(self.now + trav + 8.0, float(T["appear"]))
            gain = T["value"]
            if T["deadline"] is not None and t_s > T["deadline"]:
                gain = T["late"]
            if gain <= 0.0:
                continue
            finish = t_s + 3.0 + 0.3 * d2 + 20.0
            if finish > self.max_ticks - 5:
                continue
            score = gain / (trav + 10.0)
            if score > best_score:
                best, best_score = tid, score
        return best

    def visit(self, tid):
        T = self.targets[tid]
        goal = (T["x"], T["y"])
        self.tried[tid] = self.tried.get(tid, 0) + 1
        for attempt in range(VISIT_ATTEMPTS):
            d = _dist(self.P, goal)
            limit = SAMPLE_OK if attempt < VISIT_ATTEMPTS - 2 else SAMPLE_OK_LAST
            if d <= limit:
                self.do_sample(tid)
                return True
            if attempt == VISIT_ATTEMPTS - 1 or self.complete or self.dead:
                break
            plan = self.plan(self.P, goal)
            if plan is None:
                break
            pts, e_go = plan
            back = self.plan(goal, self.base)
            e_back = back[1] if back is not None else 0.8 * _dist(goal, self.base)
            cmds = self.route_commands(pts)
            if not cmds:
                break
            horizon = 30 + len(cmds)
            avail = self.battery + self.solar_gain(self.now, self.now + horizon) - 0.15 * horizon
            if avail - e_go - e_back - 2.0 < 15.0:
                break
            self.route_send = self.now
            last = self.send(cmds)
            if last is None:
                break
            est = self.wait_still(last)
            if est is None:
                break
            self.P = est
        return False

    def go_home(self):
        for _ in range(4):
            if self.complete or self.dead:
                return
            if _dist(self.P, self.base) <= HOME_OK:
                return
            plan = self.plan(self.P, self.base)
            pts = plan[0] if plan is not None else [self.P, self.base]
            cmds = self.route_commands(pts)
            if not cmds:
                return
            self.route_send = self.now
            last = self.send(cmds)
            if last is None:
                return
            est = self.wait_still(last)
            if est is None:
                return
            self.P = est

    def run(self):
        self.ingest()
        for _ in range(300):
            if self.complete or self.dead:
                break
            tid = self.choose()
            if tid is None:
                break
            self.visit(tid)
        if not self.complete and not self.dead:
            self.go_home()

    def finish(self):
        for _ in range(500):
            if self.complete:
                return
            before = self.now
            try:
                self.step(5)
            except Exception:
                return
            if self.now == before and not self.complete:
                return


def play(tools):
    try:
        pilot = Pilot(tools)
    except Exception:
        # Could not read the map: at least let the clock run out.
        for _ in range(200):
            try:
                if tools.advance(5)["episode_complete"]:
                    return
            except Exception:
                return
        return
    try:
        pilot.run()
    except Exception:
        try:
            pilot.go_home()
        except Exception:
            pass
    try:
        pilot.finish()
    except Exception:
        pass
