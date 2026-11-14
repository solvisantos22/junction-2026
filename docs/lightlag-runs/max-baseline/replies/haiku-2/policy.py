"""Autopilot for the MAX lightlag traverse.

Approach
- Routes are planned with A* on the published height grid. Edges are rejected when the
  slope is near the tilt limit, or when uphill grade on sand or crust (or rocks and
  regolith near their slip limits) would trigger the slip check.
- Distance per commanded metre is learned from visual odometry (ground distance over
  wheel metres). That absorbs slip and the hidden wheel size. Heading bias is not modelled
  directly; it is corrected by re-aiming from position fixes.
- The position model is dead reckoning through the queued drives, re-anchored to every
  delayed fix with a gentle gain. The queue is kept about ten ticks ahead of the clock so
  the rover never waits for the relay.
- At a target the rover stops and waits for enough fixes. It samples only when the robust
  mean of those fixes is within about a metre of the target. Otherwise it re-approaches.
- The return to the lander is scheduled from the time left, and the mission ends settled
  at the lander.
"""

import heapq
import json
import math
import sys
import traceback

import lightlag_surface as ls

INF = float("inf")
MOVE_HORIZON = 10          # keep this many ticks of commands queued ahead
MIN_BATTERY = 25.0         # stop sending drives below this (telemetry is delayed)
SETTLE_NEED = 8            # stationary fixes needed before deciding at a stop
SETTLE_TOL = 1.0           # accept a sample position this close to the target (m)
HOME_TOL = 2.0             # accept a home position this close to the lander (m)
SAMPLE_FALLBACK_TOL = 2.3  # after too many attempts, sample anyway within this distance
HOME_FALLBACK_TOL = 3.5
MAX_CORR = 6               # re-approach attempts per goal
SPEED = 2.5                # conservative metres per tick, used for time planning
GATE_GAIN = 0.35           # fraction of a fix residual applied to the position model
MAX_DRIVE = 5.0
SLOPE_MAX = 0.28           # never plan over ground steeper than this
PATH_GAP = 6.0             # replan when the model drifts this far from the path


def _nested(v):
    return json.loads(v) if isinstance(v, str) else v


def _d(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _ids(items):
    out = set()
    for s in items or []:
        if isinstance(s, dict):
            s = s.get("id", s.get("target_id"))
        if s is not None:
            out.add(str(s))
    return out


def _robust_mean(vals):
    v = sorted(vals)
    if len(v) >= 6:
        v = v[1:-1]
    return sum(v) / len(v)


class Pilot:
    def __init__(self, tools):
        self.tools = tools
        self.rules = tools.rules()
        m = tools.map()
        self.max_ticks = int(self.rules["max_ticks"])
        self.cell = float(m.get("cell_m", 5.0))
        self.surf = ls.Surface(self.cell, _nested(m["elevation_cm"]), _nested(m["terrain"]))
        self.nx, self.ny = self.surf.nx, self.surf.ny
        self.width, self.height = self.surf.width, self.surf.height
        self.base = (float(m["base"][0]), float(m["base"][1]))
        self.crusts = [(float(c["x1"]), float(c["y1"]), float(c["x2"]), float(c["y2"]))
                       for c in (m.get("crust_regions") or [])]

        self.eff = 0.85                 # ground metres per commanded wheel metre
        self.eff_samples = []
        self.entries = []               # predicted drives: exec, tx, dx, dy
        self.anchor = self.base
        self.anchor_tick = 0
        self.fixes = []                 # (tick, x, y) raw position fixes
        self.processed = set()
        self.sampled = set()
        self.targets = {}
        self.done, self.failed, self.unreach = set(), set(), set()
        self.attempts = {}
        self.now = 0
        self.q_end = 0
        self.latest_tick = -1
        self.battery = float(self.rules.get("initial_battery", 100.0))
        self.phase = "idle"             # idle, move, settle, sampling, done
        self.goal = None
        self.path = None
        self.goal_stops = 0
        self.settle_start = 0
        self.settle_attempts = 0
        self.sample_info = None
        self.edge_cache = {}
        self.refresh_targets()

    # ------------------------------------------------------------------ inputs
    def refresh_targets(self):
        for t in self.tools.map().get("targets", []):
            tid = str(t["id"])
            dl = t.get("deadline_tick")
            self.targets[tid] = {
                "id": tid,
                "x": float(t["x"]),
                "y": float(t["y"]),
                "value": float(t["value"]),
                "deadline": None if dl is None else int(dl),
                "late": float(t.get("late_value") or 0.0),
            }

    def ingest_all(self):
        for p in sorted(self.tools.telemetry_log(), key=lambda q: int(q["tick"])):
            self.ingest(p)

    def ingest(self, p):
        tick = int(p["tick"])
        if tick in self.processed:
            return
        self.processed.add(tick)
        self.latest_tick = max(self.latest_tick, tick)
        if p.get("battery") is not None:
            self.battery = float(p["battery"])
        self.sampled |= _ids(p.get("sampled_targets"))
        for e in p.get("events") or []:
            etype = str(e.get("type", ""))
            if etype == "safety_stop":
                self._on_stop(tick)
            elif "sampl" in etype:
                tgt = e.get("target") or e.get("target_id")
                if tgt:
                    self.sampled.add(str(tgt))
        w = float(p.get("wheel_odometry") or 0.0)
        v = float(p.get("visual_odometry") or 0.0)
        if w >= 0.5 and v > 0.0:
            self.eff_samples = (self.eff_samples + [v / w])[-15:]
            s = sorted(self.eff_samples)
            self.eff = min(1.3, max(0.3, s[len(s) // 2]))
        pos = p.get("position")
        if pos is not None and p.get("alive", True) is not False:
            x, y = float(pos[0]), float(pos[1])
            self.fixes.append((tick, x, y))
            self._rebase(tick, (x, y))

    # ------------------------------------------------------------ position model
    def _model_at(self, t):
        x, y = self.anchor
        for e in self.entries:
            if e["exec"] <= t:
                x += e["dx"]
                y += e["dy"]
        return x, y

    def _tail(self):
        return self._model_at(INF)

    def _rebase(self, tick, pos):
        if tick < self.anchor_tick:
            return
        mx, my = self._model_at(tick)
        rx, ry = pos[0] - mx, pos[1] - my
        r = math.hypot(rx, ry)
        if r > 6.0:
            rx *= 6.0 / r
            ry *= 6.0 / r
        self.anchor = (mx + GATE_GAIN * rx, my + GATE_GAIN * ry)
        self.anchor_tick = tick
        self.entries = [e for e in self.entries if e["exec"] > tick]

    def _reset_anchor(self, tick, pos):
        self.anchor = pos
        self.anchor_tick = max(tick, self.anchor_tick)
        self.entries = [e for e in self.entries if e["exec"] > self.anchor_tick]

    def _on_stop(self, tick):
        # The stop clears commands that were queued at the stop. Commands sent after
        # the stop tick were not in the queue and still run.
        keep = []
        for e in self.entries:
            if e["exec"] > tick and e["tx"] <= tick:
                continue
            keep.append(e)
        self.entries = keep
        self.q_end = max([tick] + [e["exec"] for e in keep])
        self.path = None
        if self.phase == "move" and self.goal is not None:
            self.goal_stops += 1
            if self.goal_stops >= 3 and self.goal["kind"] == "sample":
                self._fail_goal()
        elif self.phase == "settle":
            self.settle_start = tick + 1

    def _send(self, cmds, disp):
        try:
            acks = self.tools.uplink(cmds)
        except ValueError:
            return []
        for k, ack in enumerate(acks):
            ex = int(ack["execute_tick"])
            tx = int(ack.get("transmit_tick", ex - 4))
            self.q_end = max(self.q_end, ex)
            if disp is not None and k < len(disp) and disp[k] is not None:
                self.entries.append({"exec": ex, "tx": tx, "dx": disp[k][0], "dy": disp[k][1]})
        self.entries.sort(key=lambda e: e["exec"])
        return acks

    # ------------------------------------------------------------------ ground
    def _in_crust(self, x, y):
        for x1, y1, x2, y2 in self.crusts:
            if x1 <= x <= x2 and y1 <= y <= y2:
                return True
        return False

    def _cost_xy(self, x1, y1, x2, y2):
        """Cost of a straight segment, or None if it is not safe to drive."""
        length = math.hypot(x2 - x1, y2 - y1)
        if length < 1e-9:
            return 0.0
        ux, uy = (x2 - x1) / length, (y2 - y1) / length
        mx, my = 0.5 * (x1 + x2), 0.5 * (y1 + y2)
        smax, gpos = 0.0, -INF
        for x, y in ((x1, y1), (mx, my), (x2, y2)):
            xc = min(max(x, 0.0), self.width)
            yc = min(max(y, 0.0), self.height)
            _, gx, gy, _ = self.surf.sample(xc, yc)
            smax = max(smax, math.hypot(gx, gy))
            gpos = max(gpos, gx * ux + gy * uy)
        if smax > SLOPE_MAX:
            return None
        mxc = min(max(mx, 0.0), self.width)
        myc = min(max(my, 0.0), self.height)
        code = self.surf.sample(mxc, myc)[3]
        name = ls.TERRAIN_CODES.get(code, "regolith")
        crust = self._in_crust(mx, my)
        if name == "sand" or (crust and smax <= 0.1):
            # Slip grows with uphill grade on sand (gain up to 4.5, base up to 0.35).
            if gpos > 0.02:
                return None
            mult = 1.0 + 80.0 * max(0.0, gpos)
        elif name == "regolith":
            if gpos > 0.18:
                return None
            mult = 1.0 + 2.0 * max(0.0, gpos)
        elif name == "rocks":
            if gpos > 0.14:
                return None
            mult = 1.3 + 2.0 * max(0.0, gpos)
        else:
            mult = 1.0 + 2.0 * max(0.0, gpos)
        mult += 4.0 * max(0.0, smax - 0.15)
        h1 = self.surf.elevation(min(max(x1, 0.0), self.width), min(max(y1, 0.0), self.height))
        h2 = self.surf.elevation(min(max(x2, 0.0), self.width), min(max(y2, 0.0), self.height))
        return length * mult + 0.3 * max(0.0, h2 - h1)

    def _edge(self, i, j, ni, nj):
        key = (i, j, ni, nj)
        if key not in self.edge_cache:
            c = self.cell
            self.edge_cache[key] = self._cost_xy(i * c, j * c, ni * c, nj * c)
        return self.edge_cache[key]

    def _vertex(self, p):
        i = min(self.nx - 1, max(0, int(round(p[0] / self.cell))))
        j = min(self.ny - 1, max(0, int(round(p[1] / self.cell))))
        return (i, j)

    def _astar(self, s, g):
        if s == g:
            return [s]
        c = self.cell
        gxm, gym = g[0] * c, g[1] * c
        gscore = {s: 0.0}
        came = {}
        closed = set()
        heap = [(math.hypot(s[0] * c - gxm, s[1] * c - gym), 0.0, s)]
        expansions = 0
        while heap:
            _, gc, node = heapq.heappop(heap)
            if node in closed:
                continue
            if node == g:
                path = [node]
                while node in came:
                    node = came[node]
                    path.append(node)
                path.reverse()
                return path
            closed.add(node)
            expansions += 1
            if expansions > 60000:
                return None
            i, j = node
            for di in (-1, 0, 1):
                for dj in (-1, 0, 1):
                    if di == 0 and dj == 0:
                        continue
                    ni, nj = i + di, j + dj
                    if not (0 <= ni < self.nx and 0 <= nj < self.ny):
                        continue
                    nb = (ni, nj)
                    if nb in closed:
                        continue
                    ec = self._edge(i, j, ni, nj)
                    if ec is None:
                        continue
                    ng = gc + ec
                    if ng < gscore.get(nb, INF):
                        gscore[nb] = ng
                        came[nb] = node
                        heapq.heappush(heap, (ng + math.hypot(ni * c - gxm, nj * c - gym), ng, nb))
        return None

    def _plan(self, P, G):
        c = self.cell
        verts = self._astar(self._vertex(P), self._vertex(G))
        if verts is None:
            return None
        pts = [P] + [(i * c, j * c) for i, j in verts] + [G]
        if self._cost_xy(pts[-2][0], pts[-2][1], G[0], G[1]) is None:
            return None
        return pts

    def _gap(self, P):
        return min(_d(P, q) for q in self.path)

    def _gen_move(self):
        """Next commands (up to five) toward the goal from the model tail."""
        G = (self.goal["x"], self.goal["y"])
        P = self._tail()
        if self.path is None or self._gap(P) > PATH_GAP:
            self.path = self._plan(P, G)
            if self.path is None:
                return None
        path = list(self.path)
        eff = self.eff
        cmds, disp = [], []
        final = False
        for _ in range(5):
            dg = _d(P, G)
            if dg < 0.4:
                final = True
                break
            if dg / eff <= MAX_DRIVE and self._cost_xy(P[0], P[1], G[0], G[1]) is not None:
                M = dg / eff
                h = math.atan2(G[1] - P[1], G[0] - P[0])
                final = True
            else:
                if not path:
                    path = [G]
                k = min(range(len(path)), key=lambda q: _d(P, path[q]))
                path = path[k:] or [G]
                aim = G
                for q in path:
                    if _d(P, q) >= 3.0:
                        aim = q
                        break
                d = _d(P, aim)
                M = min(MAX_DRIVE, max(0.1, d / eff))
                h = math.atan2(aim[1] - P[1], aim[0] - P[0])
            dx, dy = eff * M * math.cos(h), eff * M * math.sin(h)
            cmds.append({"action": "drive",
                         "heading_deg": round(math.degrees(h) % 360.0, 3),
                         "metres": round(M, 4)})
            disp.append((dx, dy))
            P = (P[0] + dx, P[1] + dy)
            if final:
                break
        self.path = path
        return cmds, disp, final

    # ------------------------------------------------------------ goals & phases
    def _home_goal(self):
        return {"kind": "home", "id": None, "x": self.base[0], "y": self.base[1]}

    def _choose(self):
        P = self._tail()
        best, bs = None, -1.0
        for t in self.targets.values():
            tid = t["id"]
            if tid in self.done or tid in self.failed or tid in self.unreach or tid in self.sampled:
                continue
            tp = (t["x"], t["y"])
            t_fin = self.now + _d(P, tp) / SPEED + 10
            dl = t["deadline"]
            gain = t["value"] if (dl is None or t_fin <= dl) else t["late"]
            back = _d(tp, self.base) / SPEED + 25
            if t_fin + back > self.max_ticks - 2:
                continue
            score = gain / (t_fin - self.now + 6)
            if score > bs:
                bs, best = score, t
        if best is None:
            return None
        return {"kind": "sample", "id": best["id"], "x": best["x"], "y": best["y"]}

    def _pick(self):
        g = self._choose()
        if g is None:
            g = self._home_goal()
        self.goal = g
        self.path = None
        self.goal_stops = 0
        self.settle_attempts = 0
        self.phase = "move"

    def _move(self):
        P = self._tail()
        if self.goal["kind"] == "sample" and \
                self.now + _d(P, self.base) / SPEED + 25 >= self.max_ticks:
            self.goal = self._home_goal()
            self.path = None
        if self.q_end >= self.now + MOVE_HORIZON or self.battery < MIN_BATTERY:
            return
        res = self._gen_move()
        if res is None:
            if self.goal["kind"] == "sample":
                self.unreach.add(self.goal["id"])
                self.goal = None
                self.phase = "idle"
            else:
                self.phase = "done"
            return
        cmds, disp, final = res
        if cmds:
            self._send(cmds, disp)
        if final:
            self.phase = "settle"
            self.settle_start = self.q_end

    def _settle(self):
        g = self.goal
        pts = [(s, x, y) for (s, x, y) in self.fixes if s >= self.settle_start]
        waited = self.now - self.settle_start
        n = len(pts)
        ready = n >= SETTLE_NEED or (n >= 4 and waited >= 14) or (n >= 1 and waited >= 40)
        if not ready:
            if n == 0 and waited >= 60:
                self._fail_or_done()
            return
        tl = max(s for s, _, _ in pts)
        E = (_robust_mean([x for _, x, _ in pts]), _robust_mean([y for _, _, y in pts]))
        self._reset_anchor(tl, E)
        T = (g["x"], g["y"])
        err = _d(E, T)
        is_home = g["kind"] == "home"
        if err <= (HOME_TOL if is_home else SETTLE_TOL):
            self._arrived()
            return
        if self.settle_attempts < MAX_CORR:
            # Re-approach from the corrected position; the move phase will issue the drive.
            self.settle_attempts += 1
            self.phase = "move"
            self.path = None
            return
        if is_home:
            if err <= HOME_FALLBACK_TOL:
                self._arrived()
            else:
                self.phase = "done"
        elif err <= SAMPLE_FALLBACK_TOL:
            self._sample()
        else:
            self._fail_goal()

    def _arrived(self):
        if self.goal["kind"] == "sample":
            self._sample()
        else:
            self.goal = None
            self.phase = "done" if self._choose() is None else "idle"

    def _fail_or_done(self):
        if self.goal and self.goal["kind"] == "sample":
            self._fail_goal()
        else:
            self.phase = "done"

    def _fail_goal(self):
        g = self.goal or {}
        if g.get("kind") == "sample" and g.get("id") is not None:
            self.failed.add(g["id"])
            self.goal = None
            self.phase = "idle"
        else:
            self.phase = "done"

    def _sample(self):
        acks = self._send([{"action": "sample"}], None)
        if acks:
            self.sample_info = {"id": self.goal["id"], "exec": int(acks[0]["execute_tick"])}
            self.phase = "sampling"
        else:
            self._fail_goal()

    def _sampling(self):
        info = self.sample_info
        tid = info["id"]
        if tid in self.sampled:
            self.done.add(tid)
            self.goal = None
            self.phase = "idle"
            return
        if self.latest_tick >= info["exec"] + 6:
            n = self.attempts.get(tid, 0) + 1
            self.attempts[tid] = n
            if n >= 2:
                self.failed.add(tid)
                self.goal = None
                self.phase = "idle"
            else:
                self.phase = "settle"
                self.settle_start = info["exec"] + 1
                self.settle_attempts = 0

    # --------------------------------------------------------------- main loop
    def step(self):
        for _ in range(4):
            ph = self.phase
            if ph == "done":
                return
            if ph == "idle":
                self._pick()
            elif ph == "move":
                self._move()
            elif ph == "settle":
                self._settle()
            elif ph == "sampling":
                self._sampling()
            if self.phase == ph:
                return

    def _safe_step(self):
        try:
            self.step()
        except Exception:
            traceback.print_exc(file=sys.stderr)
            self.path = None
            if self.phase == "move":
                self.phase = "idle"

    def run(self):
        self.ingest_all()
        self._safe_step()
        while True:
            ret = self.tools.advance(1)
            self.now = int(ret["current_tick"])
            self.ingest_all()
            if self.now % 2 == 0:
                self.refresh_targets()
            if ret.get("episode_complete"):
                break
            self._safe_step()


def play(tools):
    Pilot(tools).run()
