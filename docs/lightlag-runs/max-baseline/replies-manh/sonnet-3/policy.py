import math
import heapq
from lightlag_surface import Surface, drive as sim_drive, TERRAIN_CODES

SLIP_MID = {"bedrock": 0.03, "regolith": 0.085, "sand": 0.25, "rocks": 0.18}
INF = 1e18
OFFS = [(0, 0), (1.6, 0), (-1.6, 0), (0, 1.6)]


class Pilot:
    def __init__(self, tools):
        self.tools = tools
        R = tools.rules()
        self.R = R
        M = tools.map()
        self.cell = M["cell_m"]
        self.surf = Surface(self.cell, M["elevation_cm"], M["terrain"])
        self.phys = R["physics"]
        self.delay = R["delay_ticks"]
        self.T = R["max_ticks"]
        self.base = tuple(M["base"])
        self.nx, self.ny = self.surf.nx, self.surf.ny
        self.N = self.nx * self.ny
        self.crust = M.get("crust_regions", [])
        self.est = [self.base[0], self.base[1]]
        self.est_tick = 0
        self.scale = 1.0
        self.sched = {}
        self.cancelled = set()
        self.sampled = set()
        self.pending = {}
        self.attempts = {}
        self.battery = 100.0
        self.bat_tick = -1
        self.lowpower = False
        self.pen = [0.0] * self.N
        self.pen_ver = 0
        self.dr = None
        self.dr_ver = -1
        self.build_graph()

    # ---------- graph ----------
    def incrust(self, x, y):
        for c in self.crust:
            if c["x1"] <= x <= c["x2"] and c["y1"] <= y <= c["y2"]:
                return True
        return False

    def build_graph(self):
        s = self.surf
        cell = self.cell
        ph = self.phys
        gain = dict(ph["slip_grade_gain"])
        gain["sand"] = 4.2
        costm = ph["drive_cost_per_wheel_m"]
        side = ph["side_slip_gain"]
        climb = ph["climb_cost_per_m"]
        nx, ny = self.nx, self.ny
        adj = [[] for _ in range(self.N)]
        radj = [[] for _ in range(self.N)]
        dirs = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]
        for j in range(ny):
            for i in range(nx):
                n = j * nx + i
                x0, y0 = i * cell, j * cell
                h0 = s.elevation(x0, y0)
                for dx, dy in dirs:
                    i2, j2 = i + dx, j + dy
                    if not (0 <= i2 < nx and 0 <= j2 < ny):
                        continue
                    hyp = math.hypot(dx, dy)
                    L = cell * hyp
                    ux, uy = dx / hyp, dy / hyp
                    ok = True
                    ticks = 0.0
                    en = 0.0
                    for f in (1 / 6, 0.5, 5 / 6):
                        x = x0 + dx * cell * f
                        y = y0 + dy * cell * f
                        h, gx, gy, code = s.sample(x, y)
                        if math.hypot(gx, gy) > 0.30:
                            ok = False
                            break
                        grade = gx * ux + gy * uy
                        cross = -gx * uy + gy * ux
                        name = TERRAIN_CODES[code]
                        slip = SLIP_MID[name] + gain[name] * max(0.0, grade)
                        if slip > 0.40:
                            ok = False
                            break
                        wheel = (L / 3) / (1 - slip)
                        en += wheel * costm[name]
                        t = wheel / 4.4 * (1 + 2 * side[name] * abs(cross))
                        if name == "sand":
                            t *= 1.4
                        ticks += t
                        if self.incrust(x, y):
                            ticks *= 1.0
                            ticks += wheel / 4.4 * 0.15 / 3 * 3
                    if not ok:
                        continue
                    h1 = s.elevation(x0 + dx * cell, y0 + dy * cell)
                    en += climb * max(0.0, h1 - h0)
                    c = ticks + 0.08 * en
                    m = j2 * nx + i2
                    adj[n].append((m, c))
                    radj[m].append((n, c))
        self.adj, self.radj = adj, radj

    def dijkstra(self, src, graph):
        dist = [INF] * self.N
        prev = [-1] * self.N
        dist[src] = 0.0
        h = [(0.0, src)]
        pen = self.pen
        while h:
            d, u = heapq.heappop(h)
            if d > dist[u]:
                continue
            for v, c in graph[u]:
                nd = d + c + pen[v]
                if nd < dist[v]:
                    dist[v] = nd
                    prev[v] = u
                    heapq.heappush(h, (nd, v))
        return dist, prev

    def nodeof(self, x, y):
        i = min(self.nx - 1, max(0, int(round(x / self.cell))))
        j = min(self.ny - 1, max(0, int(round(y / self.cell))))
        return j * self.nx + i

    # ---------- model ----------
    def model_end(self, x, y, heading, metres, scale):
        r = sim_drive(self.surf, self.phys, x, y, heading, metres * scale, SLIP_MID, 0.0)
        return r

    def apply_drive(self, ent, pkt):
        cmd = ent["cmd"]
        M = cmd["metres"]
        h = cmd["heading_deg"]
        x, y = self.est
        if pkt is not None:
            try:
                vo = pkt.get("visual_odometry", 0.0)
                wo = pkt.get("wheel_odometry", 0.0)
                if vo > 0 and abs(wo - M) < 0.05 and pkt.get("terrain") != "sand":
                    g1 = self.model_end(x, y, h, M, 1.0)["ground"]
                    if g1 > 1.5:
                        ratio = min(1.5, max(0.5, vo / g1))
                        self.scale = min(1.2, max(0.8, 0.92 * self.scale + 0.08 * ratio))
            except Exception:
                pass
        r = self.model_end(x, y, h, M, self.scale)
        self.est = [r["x"], r["y"]]

    # ---------- telemetry ----------
    def ingest_all(self, pkts):
        for p in sorted(pkts, key=lambda q: q["tick"]):
            try:
                self.ingest(p)
            except Exception:
                pass

    def ingest(self, pkt):
        t = pkt["tick"]
        self.sampled |= set(pkt.get("sampled_targets", []))
        if t >= self.bat_tick:
            self.bat_tick = t
            self.battery = pkt["battery"]
        if t <= self.est_tick and not (t == 0 and self.est_tick == 0 and False):
            return
        for tt in range(self.est_tick + 1, t + 1):
            ent = self.sched.get(tt)
            if ent and tt not in self.cancelled and ent["cmd"]["action"] == "drive":
                self.apply_drive(ent, pkt if tt == t else None)
        self.est_tick = t
        fx, fy = pkt["position"]
        ix, iy = fx - self.est[0], fy - self.est[1]
        mag = math.hypot(ix, iy)
        if mag > 6.0:
            ix, iy = ix * 6.0 / mag, iy * 6.0 / mag
        self.est[0] += 0.3 * ix
        self.est[1] += 0.3 * iy
        for e in pkt.get("events", []):
            if "safety_stop" in str(e.get("type", "")):
                for et, ent in self.sched.items():
                    if et > t and ent["sent"] < t:
                        self.cancelled.add(et)
                cx, cy = self.est
                for j in range(self.ny):
                    if abs(j * self.cell - cy) > 8:
                        continue
                    for i in range(self.nx):
                        if math.hypot(i * self.cell - cx, j * self.cell - cy) <= 7:
                            self.pen[j * self.nx + i] += 12.0
                self.pen_ver += 1

    def predict(self):
        x, y = self.est
        for tt in sorted(k for k in self.sched if k > self.est_tick):
            ent = self.sched[tt]
            if tt in self.cancelled or ent["cmd"]["action"] != "drive":
                continue
            r = self.model_end(x, y, ent["cmd"]["heading_deg"], ent["cmd"]["metres"], self.scale)
            x, y = r["x"], r["y"]
        return x, y

    # ---------- planning ----------
    def make_commands(self, px, py, start_tick, targets):
        T = self.T
        tick_now = start_tick
        if self.dr is None or self.dr_ver != self.pen_ver:
            bn = self.nodeof(*self.base)
            self.dr = self.dijkstra(bn, self.radj)[0]
            self.dr_ver = self.pen_ver
        Dr = self.dr
        # source node
        cx = int(round(px / self.cell))
        cy = int(round(py / self.cell))
        cands = []
        for dj in (-1, 0, 1):
            for di in (-1, 0, 1):
                i, j = cx + di, cy + dj
                if 0 <= i < self.nx and 0 <= j < self.ny:
                    cands.append((math.hypot(i * self.cell - px, j * self.cell - py), j * self.nx + i))
        cands.sort()
        src = None
        for _, n in cands:
            if self.adj[n]:
                src = n
                break
        D = prev = None
        if src is not None:
            D, prev = self.dijkstra(src, self.adj)
        # choose goal
        best = None
        sc = self.scale
        if D is not None:
            for tg in targets:
                tid = tg["id"]
                if tid in self.sampled or tid in self.pending or self.attempts.get(tid, 0) >= 3:
                    continue
                nt = self.nodeof(tg["x"], tg["y"])
                if D[nt] >= INF or Dr[nt] >= INF:
                    continue
                tt = D[nt] / sc + math.hypot(tg["x"] - nt % self.nx * self.cell,
                                             tg["y"] - nt // self.nx * self.cell) / 4.4
                back = Dr[nt] / sc
                arrive = tick_now + tt
                if arrive + 1 + back + 20 > T:
                    continue
                dl = tg.get("deadline_tick")
                gain = tg["value"] if (dl is None or arrive <= dl - 2) else tg.get("late_value", 0.0)
                if gain <= 0:
                    continue
                score = gain / (tt + 3 + 0.1 * back)
                if best is None or score > best[0]:
                    best = (score, tg, nt)
        if best is not None:
            tg = best[1]
            off = OFFS[min(self.attempts.get(tg["id"], 0), 3)]
            goal = (tg["x"] + off[0], tg["y"] + off[1])
            tid = tg["id"]
            nt = best[2]
            nodes = []
            n = nt
            while n != -1 and n != src:
                nodes.append(n)
                n = prev[n]
            nodes.reverse()
        else:
            goal = self.base
            tid = None
            bn = self.nodeof(*self.base)
            nodes = []
            if D is not None and D[bn] < INF:
                n = bn
                while n != -1 and n != src:
                    nodes.append(n)
                    n = prev[n]
                nodes.reverse()
        pts = [((n % self.nx) * self.cell, (n // self.nx) * self.cell) for n in nodes[1:]]
        pts.append(goal)
        cmds = []
        q = (px, py)
        idx = 0
        last = len(pts) - 1
        for _ in range(5):
            while idx < last and math.hypot(pts[idx][0] - q[0], pts[idx][1] - q[1]) < 3.0:
                idx += 1
            ax, ay = pts[idx]
            d = math.hypot(ax - q[0], ay - q[1])
            if idx == last and d <= 1.2:
                if tid is not None:
                    cmds.append(({"action": "sample"}, tid))
                break
            metres = max(0.5, min(5.0, d))
            h0 = math.degrees(math.atan2(ay - q[1], ax - q[0]))
            bestc = None
            for off in range(-30, 31, 5):
                hh = (h0 + off) % 360.0
                r = self.model_end(q[0], q[1], hh, metres, self.scale)
                err = math.hypot(r["x"] - ax, r["y"] - ay) + 0.03 * abs(off)
                if r["stop"] is not None:
                    err += 50
                if bestc is None or err < bestc[0]:
                    bestc = (err, hh, r)
            _, hh, r = bestc
            q = (r["x"], r["y"])
            cmds.append(({"action": "drive", "heading_deg": round(hh, 2), "metres": round(metres, 2)}, None))
        return cmds

    def plan(self, tick):
        tools = self.tools
        M = tools.map()
        targets = M["targets"]
        for tid in list(self.pending):
            if tid in self.sampled:
                del self.pending[tid]
            elif self.est_tick >= self.pending[tid] + 1:
                self.attempts[tid] = self.attempts.get(tid, 0) + 1
                del self.pending[tid]
        if self.lowpower and self.battery >= 35:
            self.lowpower = False
        if (not self.lowpower) and self.battery < 14 and self.T - tick > 40:
            self.lowpower = True
        for _ in range(4):
            Eres = max(self.sched.keys(), default=0)
            nxt = (tick // 8 + 1) * 8
            if Eres >= nxt + 3 or tick >= self.T - 3:
                break
            start = max(Eres, tick + self.delay) + 1
            if self.lowpower:
                cmds = [({"action": "wait"}, None)] * 5
            else:
                px, py = self.predict()
                cmds = self.make_commands(px, py, start, targets)
            if not cmds:
                break
            acks = tools.uplink([c for c, _ in cmds])
            for ack, (c, tid) in zip(acks, cmds):
                et = ack["execute_tick"]
                self.sched[et] = {"cmd": c, "sent": tick, "tid": tid}
                if tid is not None:
                    self.pending[tid] = et


def play(tools):
    p = Pilot(tools)
    p.ingest_all(tools.telemetry_log())
    tick = 0
    while True:
        if tick % 8 < 4 and tick < p.T:
            try:
                p.plan(tick)
            except Exception:
                pass
        r = tools.advance(1)
        tick = r["current_tick"]
        p.ingest_all(r["packets"])
        if r["episode_complete"] or tick > p.T + 5:
            break
