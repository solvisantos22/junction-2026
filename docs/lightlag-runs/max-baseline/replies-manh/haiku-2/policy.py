"""Autopilot for the MAX lightlag traverse.

play(tools) plays the whole mission:
  * position is estimated by fitting a constant heading bias and the position at the start of
    a sliding window to the noisy position fixes; between fixes, dead reckoning uses the
    commanded heading plus the bias estimate and the visual odometry of each drive;
  * routes are found with Dijkstra on the published height grid (5 m vertices), with slope,
    predicted slip and terrain costs, and followed in short drives re-aimed from the estimate;
  * targets are chosen greedily by deadline-aware value per tick, with a check that the rover
    can still reach the lander before the end; the rover samples once its estimate is close;
  * the rover returns to the lander in time and idles there.
"""

import bisect
import heapq
import math

from lightlag_surface import Surface, TERRAIN_CODES

WINDOW = 120            # ticks of telemetry used by the position fit
BIAS_LIMIT_DEG = 8.0
BIAS_STEP_DEG = 0.1
SAMPLE_STEP_M = 2.5     # spacing of slope checks along a planned edge
SLOPE_LIMIT = 0.30      # planning limit, below the 0.36 stop
SLIP_LIMIT = 0.36       # planning limit on predicted slip, below the 0.45 fault
APPROACH_M = 1.0        # sample once the estimate is this close to the target
HOME_DONE_M = 1.2
CHUNK_MIN_M = 2.0
DIRECT_M = 4.0
CHUNK_MAX_M = 5.0
SPEED = 4.0             # planning estimate: effort units per tick
CLAIM_WAIT = 12
MAX_CHUNKS_PER_TARGET = 90
REPLAN_EVERY = 6
MAX_TRIES = 3
QUEUE_AHEAD = 10
BASE = "__base__"
INF = float("inf")
DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))


def _median(values):
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    m = n // 2
    return s[m] if n % 2 else 0.5 * (s[m - 1] + s[m])


def _wrap(deg):
    return (deg + 180.0) % 360.0 - 180.0


class Pilot:
    def __init__(self, tools):
        self.tools = tools
        rules = tools.rules()
        ph = rules["physics"]
        mp = tools.map()
        self.cell = float(mp["cell_m"])
        self.surf = Surface(self.cell, mp["elevation_cm"], mp["terrain"])
        self.nx, self.ny = self.surf.nx, self.surf.ny
        self.N = self.nx * self.ny
        self.width, self.height = self.surf.width, self.surf.height
        self.max_ticks = int(rules["max_ticks"])
        rp = rules["relay_passes"]
        self.period = int(rp["period_ticks"])
        self.open_ticks = int(rp["open_ticks"])
        self.base = (float(mp["base"][0]), float(mp["base"][1]))
        self.crust = [(float(r["x1"]), float(r["y1"]), float(r["x2"]), float(r["y2"]))
                      for r in mp.get("crust_regions", [])]
        self.slip_mid = {k: 0.5 * (lo + hi) for k, (lo, hi) in ph["slip_base_ranges"].items()}
        self.gain = dict(ph["slip_grade_gain"])
        self.drive_cost = dict(ph["drive_cost_per_wheel_m"])

        self.targets = {}
        self._absorb_targets(mp)
        self.sampled = set()
        self.claims = {}
        self.tries = {}
        self.banned = set()
        self.memo = {}

        self.fixes = []          # (tick, x, y) from telemetry
        self.vo = {}             # tick -> visual odometry reported at that tick
        self.seen = 0
        self.battery = float(rules["initial_battery"])
        self.dead = False
        self.drives = []         # dicts: exec, sent, h, M, cancel
        self.anchor_tick = 0
        self.anchor = self.base
        self.b_hat = 0.0
        self.ratio = 0.85
        self.busy = 0            # last reserved execution tick
        self.cur = None
        self.path = None
        self.ptr = 0
        self.path_since = 0
        self.chunks = 0
        self.tick = 0
        self.complete = False

    # ------------------------------------------------------------------ map and targets
    def _absorb_targets(self, mp):
        for tg in mp.get("targets", []):
            self.targets[tg["id"]] = {
                "x": float(tg["x"]), "y": float(tg["y"]),
                "value": float(tg["value"]), "late": float(tg["late_value"]),
                "deadline": tg.get("deadline_tick"),
            }

    @staticmethod
    def _value_at(tg, tick):
        dl = tg["deadline"]
        if dl is None or tick <= dl:
            return tg["value"]
        return tg["late"]

    # ------------------------------------------------------------------ telemetry
    def _read_telemetry(self):
        log = self.tools.telemetry_log()
        new = log[self.seen:]
        self.seen = len(log)
        stops = []
        for pk in new:
            tick = int(pk["tick"])
            pos = pk.get("position")
            if pos is not None:
                self.fixes.append((tick, float(pos[0]), float(pos[1])))
            self.vo[tick] = float(pk.get("visual_odometry", 0.0) or 0.0)
            if pk.get("battery") is not None:
                self.battery = float(pk["battery"])
            if pk.get("alive") is False:
                self.dead = True
            for sid in pk.get("sampled_targets") or []:
                if isinstance(sid, dict):
                    sid = sid.get("id")
                if sid is not None:
                    self.sampled.add(str(sid))
            for ev in pk.get("events") or []:
                typ = str(ev.get("type", "")) if isinstance(ev, dict) else ""
                if "safety" in typ:
                    stops.append(tick)
            if pk.get("safety_stop"):
                stops.append(tick)
        for s in stops:
            self._on_stop(s)
        self._update_ratio()

    def _on_stop(self, s):
        # commands sent before the stop and not yet executed were cleared by the rover
        for d in self.drives:
            if not d["cancel"] and d["sent"] <= s < d["exec"]:
                d["cancel"] = True
        for tid in list(self.claims):
            c = self.claims[tid]
            if c["sent"] <= s < c["exec"]:
                del self.claims[tid]
        self.path = None

    def _update_ratio(self):
        rs = []
        for d in self.drives:
            if d["cancel"] or d["M"] <= 0:
                continue
            v = self.vo.get(d["exec"])
            if v is None or v <= 0:
                continue
            rs.append(v / d["M"])
        if len(rs) >= 5:
            self.ratio = min(1.15, max(0.5, _median(rs)))

    def _dist(self, d):
        v = self.vo.get(d["exec"])
        if v is not None:
            return v
        return d["M"] * self.ratio

    # ------------------------------------------------------------------ estimation
    def _fit(self, t):
        w0 = max(0, t - WINDOW)
        F = [f for f in self.fixes if w0 <= f[0] <= t]
        if len(F) < 4:
            return
        D = [d for d in self.drives if not d["cancel"] and w0 < d["exec"] <= t]
        execs = [d["exec"] for d in D]
        dists = [self._dist(d) for d in D]
        hs = [d["h"] for d in D]
        prev = self.b_hat
        steps = int(round(BIAS_LIMIT_DEG / BIAS_STEP_DEG))
        best = None
        for k in range(-steps, steps + 1):
            b = k * BIAS_STEP_DEG
            cx = [0.0]
            cy = [0.0]
            for dd, h in zip(dists, hs):
                a = math.radians(h + b)
                cx.append(cx[-1] + dd * math.cos(a))
                cy.append(cy[-1] + dd * math.sin(a))
            rx = []
            ry = []
            for tau, x, y in F:
                i = bisect.bisect_right(execs, tau)
                rx.append(x - cx[i])
                ry.append(y - cy[i])
            mx = _median(rx)
            my = _median(ry)
            cost = sum(math.hypot(a - mx, c - my) for a, c in zip(rx, ry))
            cost += 0.02 * len(F) * abs(b - prev)
            if best is None or cost < best[0]:
                best = (cost, b, mx, my)
        _, b, mx, my = best
        self.b_hat = b
        self.anchor = (mx, my)
        self.anchor_tick = w0

    def _predict(self):
        x, y = self.anchor
        b = self.b_hat
        for d in self.drives:
            if d["cancel"] or d["exec"] <= self.anchor_tick:
                continue
            dd = self._dist(d)
            a = math.radians(d["h"] + b)
            x += dd * math.cos(a)
            y += dd * math.sin(a)
        return (x, y)

    # ------------------------------------------------------------------ ground model
    def _sample(self, x, y):
        x = min(max(x, 0.0), self.width)
        y = min(max(y, 0.0), self.height)
        return self.surf.sample(x, y)

    def _in_crust(self, x, y):
        for x1, y1, x2, y2 in self.crust:
            if x1 <= x <= x2 and y1 <= y <= y2:
                return True
        return False

    def _slip_est(self, P, ux, uy):
        _, gx, gy, code = self._sample(P[0], P[1])
        name = TERRAIN_CODES[code]
        grade = gx * ux + gy * uy
        return min(0.6, self.slip_mid[name] + self.gain[name] * max(0.0, grade))

    def _seg_weight(self, x1, y1, x2, y2):
        """Planning effort of a straight drive, or None if it is too steep or too slippery."""
        L = math.hypot(x2 - x1, y2 - y1)
        if L < 1e-9:
            return 0.0
        n = max(1, int(math.ceil(L / SAMPLE_STEP_M)))
        seg = L / n
        ux = (x2 - x1) / L
        uy = (y2 - y1) / L
        prev_h = self._sample(x1, y1)[0]
        w = 0.0
        for k in range(1, n + 1):
            f = k / n
            x = x1 + (x2 - x1) * f
            y = y1 + (y2 - y1) * f
            h, gx, gy, code = self._sample(x, y)
            if math.hypot(gx, gy) > SLOPE_LIMIT:
                return None
            name = TERRAIN_CODES[code]
            grade = gx * ux + gy * uy
            slip = self.slip_mid[name] + self.gain[name] * max(0.0, grade)
            if slip > SLIP_LIMIT:
                return None
            dh = h - prev_h
            prev_h = h
            cost = 0.5 + self.drive_cost[name]
            if self._in_crust(x, y):
                cost *= 1.3
            w += seg * cost / (1.0 - slip) + 0.5 * max(0.0, dh)
        return w

    # ------------------------------------------------------------------ graph
    def _nearest(self, x, y):
        i = min(self.nx - 1, max(0, int(round(x / self.cell))))
        j = min(self.ny - 1, max(0, int(round(y / self.cell))))
        return j * self.nx + i

    def _xy(self, v):
        return ((v % self.nx) * self.cell, (v // self.nx) * self.cell)

    def _edge(self, u, v):
        key = u * self.N + v
        w = self.memo.get(key)
        if w is None:
            x1, y1 = self._xy(u)
            x2, y2 = self._xy(v)
            r = self._seg_weight(x1, y1, x2, y2)
            w = -1.0 if r is None else r
            self.memo[key] = w
        return w

    def _dijkstra(self, start):
        nx, ny = self.nx, self.ny
        dist = [INF] * self.N
        par = [-1] * self.N
        dist[start] = 0.0
        heap = [(0.0, start)]
        while heap:
            d, u = heapq.heappop(heap)
            if d > dist[u]:
                continue
            ui = u % nx
            uj = u // nx
            for di, dj in DIRS:
                vi = ui + di
                vj = uj + dj
                if vi < 0 or vj < 0 or vi >= nx or vj >= ny:
                    continue
                v = vj * nx + vi
                w = self._edge(u, v)
                if w < 0:
                    continue
                nd = d + w
                if nd < dist[v]:
                    dist[v] = nd
                    par[v] = u
                    heapq.heappush(heap, (nd, v))
        return dist, par

    def _make_path(self, P, goal):
        start = self._nearest(P[0], P[1])
        dist, par = self._dijkstra(start)
        vi = self._nearest(goal[0], goal[1])
        if dist[vi] == INF:
            return False
        seq = []
        v = vi
        while v != -1:
            seq.append(v)
            v = par[v]
        seq.reverse()
        pts = [self._xy(v) for v in seq]
        pts.append(goal)
        self.path = pts
        self.ptr = 0
        self.path_since = 0
        return True

    def _aim(self, P, goal):
        if (math.hypot(goal[0] - P[0], goal[1] - P[1]) <= DIRECT_M
                and self._seg_weight(P[0], P[1], goal[0], goal[1]) is not None):
            return goal
        pts = self.path
        if not pts:
            return goal
        best_k = self.ptr
        best_d = INF
        for k in range(self.ptr, len(pts)):
            d = math.hypot(pts[k][0] - P[0], pts[k][1] - P[1])
            if d < best_d:
                best_d = d
                best_k = k
        self.ptr = best_k
        while self.ptr < len(pts) - 1 and math.hypot(pts[self.ptr][0] - P[0], pts[self.ptr][1] - P[1]) < CHUNK_MIN_M:
            self.ptr += 1
        return pts[self.ptr]

    # ------------------------------------------------------------------ decisions
    def _choose(self, t, P, busy_off):
        if self.battery < 25.0:
            return None
        start = self._nearest(P[0], P[1])
        dist, _ = self._dijkstra(start)
        hx, hy = self.base
        best = None
        for tid, tg in self.targets.items():
            if tid in self.sampled or tid in self.banned or tid in self.claims:
                continue
            if self.tries.get(tid, 0) >= MAX_TRIES:
                continue
            w = dist[self._nearest(tg["x"], tg["y"])]
            if w == INF:
                continue
            eta = busy_off + w / SPEED + 2.0
            arrive = t + eta
            val = self._value_at(tg, arrive)
            back = math.hypot(tg["x"] - hx, tg["y"] - hy) * 1.3 / SPEED + 3.0
            if arrive + back + 20 > self.max_ticks:
                continue
            score = val / (eta + 3.0)
            if best is None or score > best[0]:
                best = (score, tid)
        return best[1] if best else None

    def _home_time(self, P, t, off):
        if self.battery < 15.0:
            return True
        rem = self.max_ticks - t - off
        eta = math.hypot(P[0] - self.base[0], P[1] - self.base[1]) * 1.3 / SPEED + 6.0
        return rem <= eta + 25.0

    def _build(self, t, n):
        items = []
        P = self._predict()
        busy_off = max(0, self.busy - t)
        guard = 0
        while len(items) < n and guard < 40:
            guard += 1
            off = busy_off + len(items)
            if self._home_time(P, t, off):
                if self.cur != BASE:
                    self.cur = BASE
                    self.path = None
            elif self.cur is None or self.cur == BASE:
                tid = self._choose(t, P, off)
                if tid is None:
                    if self.cur != BASE:
                        self.cur = BASE
                        self.path = None
                else:
                    self.cur = tid
                    self.path = None
                    self.chunks = 0

            if self.cur == BASE:
                goal = self.base
                if math.hypot(P[0] - goal[0], P[1] - goal[1]) <= HOME_DONE_M:
                    break
            else:
                tg = self.targets[self.cur]
                goal = (tg["x"], tg["y"])
                if math.hypot(P[0] - goal[0], P[1] - goal[1]) <= APPROACH_M:
                    items.append(({"action": "sample"}, ("sample", self.cur)))
                    self.cur = None
                    self.path = None
                    continue
                self.chunks += 1
                if self.chunks > MAX_CHUNKS_PER_TARGET:
                    self.banned.add(self.cur)
                    self.cur = None
                    self.path = None
                    continue

            if self.path is None or self.path_since >= REPLAN_EVERY:
                ok = self._make_path(P, goal)
                if not ok:
                    if self.cur == BASE:
                        self.path = None      # head straight for the lander
                    else:
                        self.banned.add(self.cur)
                        self.cur = None
                        self.path = None
                        continue

            aim = self._aim(P, goal)
            dx = aim[0] - P[0]
            dy = aim[1] - P[1]
            L = math.hypot(dx, dy)
            if L < 0.2:
                break
            desired = math.degrees(math.atan2(dy, dx))
            ux, uy = dx / L, dy / L
            s = self._slip_est(P, ux, uy)
            M = min(CHUNK_MAX_M, max(0.2, L / (1.0 - s)))
            M = round(M, 4)
            h = round(_wrap(desired - self.b_hat), 4)
            adv = M * (1.0 - s)
            P = (P[0] + adv * math.cos(math.radians(desired)),
                 P[1] + adv * math.sin(math.radians(desired)))
            items.append(({"action": "drive", "heading_deg": h, "metres": M}, ("drive", h, M)))
            self.path_since += 1
        return items

    def _expire_claims(self, t):
        for tid in list(self.claims):
            c = self.claims[tid]
            if tid in self.sampled or c["exec"] + CLAIM_WAIT < t:
                del self.claims[tid]

    def _uplink_round(self, t):
        for _ in range(4):
            if self.busy >= t + QUEUE_AHEAD:
                break
            items = self._build(t, 5)
            if not items:
                break
            try:
                acks = self.tools.uplink([c for c, _ in items])
            except ValueError:
                break
            for (cmd, meta), ack in zip(items, acks):
                ex = int(ack["execute_tick"])
                sent = int(ack["transmit_tick"])
                self.busy = max(self.busy, ex)
                if meta[0] == "drive":
                    self.drives.append({"exec": ex, "sent": sent, "h": meta[1],
                                        "M": meta[2], "cancel": False})
                else:
                    tid = meta[1]
                    self.claims[tid] = {"exec": ex, "sent": sent}
                    self.tries[tid] = self.tries.get(tid, 0) + 1
                    self.cur = None

    # ------------------------------------------------------------------ main loop
    def run(self):
        while True:
            self._read_telemetry()
            t = self.tick
            if t % self.period < self.open_ticks:
                self._absorb_targets(self.tools.map())
                self._expire_claims(t)
                self._fit(t)
                if not self.dead:
                    self._uplink_round(t)
                step = 1
            else:
                step = self.period - t % self.period
            res = self.tools.advance(step)
            self.tick = int(res["current_tick"])
            if res["episode_complete"]:
                self.complete = True
                return


def play(tools):
    try:
        Pilot(tools).run()
        return
    except Exception:
        pass
    # Fallback: keep the clock running so the mission still completes.
    while True:
        res = tools.advance(1)
        if res["episode_complete"]:
            return
