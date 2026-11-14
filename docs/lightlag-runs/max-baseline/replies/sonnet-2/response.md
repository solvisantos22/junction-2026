This module has not been run, not even against a stub of the tools, so treat it as untested. Here is how it works.

- **Planning:** it builds a cost grid over the map's 5 m vertices. Edges steeper than 0.30 tilt, or with a conservative slip estimate above 0.44, are forbidden, and crust regions cost 1.4×. Routes come from Dijkstra distance fields, and each 5 m drive is steered by trying 24 headings through `lightlag_surface.drive`.
- **Position estimate:** the rover's position is dead-reckoned from the commands I sent, because telemetry is old. Each noisy fix pulls the estimate by 0.3, with the pull clipped to 4 m so outlier fixes do little harm. A scale factor learned from visual odometry compensates for the hidden wheel size and slip.
- **Choosing targets:** it picks the target with the best value per estimated tick, using the full value if the estimated arrival beats the deadline and `late_value` otherwise. It only goes for targets it can still reach and return from. Targets with other valuable ones nearby get a small bonus.
- **Sampling:** it parks near the target and waits for at least 5 fixes taken since the last drive. It uses a trimmed mean of those fixes as the position, then sends a short correction drive and a `sample`. If the sample fails it retries at small offsets, up to 3 times, then skips the target.
- **Stops and low battery:** a safety stop drops the commands I had queued by then, resets the estimate to the fix, and penalises the area so routes avoid it. If the battery drops below 20 it waits to recharge, as long as 70 or more ticks remain.
- **Ending the mission:** when the remaining time is only just enough, it abandons the current target and heads for the lander.

```python
import math
import heapq
import lightlag_surface as ls

INF = 1e18
DIRS = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]
NAMES = {"b": "bedrock", "r": "regolith", "s": "sand", "k": "rocks"}
OFFS = [(0.0, 0.0), (1.5, 0.0), (-0.8, 1.3), (-0.8, -1.3)]


class Rover:
    def __init__(self, tools):
        self.t = tools
        self.rules = tools.rules()
        m = tools.map()
        self.phys = self.rules["physics"]
        self.surf = ls.Surface(m["cell_m"], m["elevation_cm"], m["terrain"])
        self.base = (float(m["base"][0]), float(m["base"][1]))
        self.crust = m.get("crust_regions", [])
        self.maxt = self.rules["max_ticks"]
        rg = self.phys["slip_base_ranges"]
        self.slipbase = {n: (a + b) / 2 for n, (a, b) in rg.items()}
        self.slipcons = {n: (a + b) / 2 + 0.25 * (b - a) for n, (a, b) in rg.items()}
        self.gain = self.phys["slip_grade_gain"]
        self.nx, self.ny = self.surf.nx, self.surf.ny
        self.cell = self.surf.cell
        self.pen = [0.0] * (self.nx * self.ny)
        self.ver = 0
        self.fcache = {}
        self.build_edges()
        self.sv = 10.0
        self.sp = 10.0
        self.k = 1.0
        self.cmds = []
        self.by_exec = {}
        self.byid = {}
        self.hist = {}
        self.fixes = []
        self.sampled = set()
        self.skip = set()
        self.goal = None
        self.battery = 100.0
        self.batt_tick = -1
        self.last_pkt = 0
        self.last_heading = 0.0
        self.tick = 0
        self.sim_tick = 0
        self.est = self.base
        self.parked_until = -1
        self.targets = m["targets"]
        self.stops = {}

    # ---------- grid ----------
    def in_crust(self, x, y):
        for r in self.crust:
            if r["x1"] <= x <= r["x2"] and r["y1"] <= y <= r["y2"]:
                return True
        return False

    def cons_slip(self, name, grade):
        g = grade if grade > 0 else 0.0
        gain = 4.5 if name == "sand" else self.gain[name]
        return self.slipcons[name] + gain * g

    def build_edges(self):
        nx, ny, c = self.nx, self.ny, self.cell
        surf = self.surf
        self.ec = [[INF] * (nx * ny) for _ in range(8)]
        for j in range(ny):
            for i in range(nx):
                for d, (di, dj) in enumerate(DIRS):
                    i2, j2 = i + di, j + dj
                    if not (0 <= i2 < nx and 0 <= j2 < ny):
                        continue
                    L = c * math.hypot(di, dj)
                    ux, uy = di * c / L, dj * c / L
                    ok = True
                    mid = None
                    for f in (0.25, 0.5, 0.75, 1.0):
                        x = (i + di * f) * c
                        y = (j + dj * f) * c
                        h, gx, gy, code = surf.sample(x, y)
                        if math.hypot(gx, gy) > 0.30:
                            ok = False
                            break
                        name = NAMES[code]
                        grade = gx * ux + gy * uy
                        if self.cons_slip(name, grade) > 0.44:
                            ok = False
                            break
                        if f == 0.5:
                            mid = (name, grade, x, y)
                    if not ok:
                        continue
                    name, grade, x, y = mid
                    slip = min(0.9, self.slipbase[name] + self.gain[name] * max(0.0, grade))
                    climb = max(0.0, surf.h[j2][i2] - surf.h[j][i])
                    cost = L / (1 - slip) + 2.0 * climb
                    if self.in_crust(x, y):
                        cost *= 1.4
                    self.ec[d][j * nx + i] = cost

    def seeds(self, x, y):
        c = self.cell
        i = min(self.nx - 2, max(0, int(x / c)))
        j = min(self.ny - 2, max(0, int(y / c)))
        out = []
        for a in (0, 1):
            for b in (0, 1):
                out.append(((j + b) * self.nx + i + a,
                            math.hypot(x - (i + a) * c, y - (j + b) * c)))
        return out

    def dijkstra(self, x, y, reverse):
        nx, ny = self.nx, self.ny
        dist = [INF] * (nx * ny)
        heap = []
        for n, c0 in self.seeds(x, y):
            if c0 < dist[n]:
                dist[n] = c0
                heap.append((c0, n))
        heapq.heapify(heap)
        ec, pen = self.ec, self.pen
        while heap:
            dc, n = heapq.heappop(heap)
            if dc > dist[n]:
                continue
            i, j = n % nx, n // nx
            for d in range(8):
                di, dj = DIRS[d]
                if reverse:
                    i2, j2 = i - di, j - dj
                    if not (0 <= i2 < nx and 0 <= j2 < ny):
                        continue
                    n2 = j2 * nx + i2
                    c = ec[d][n2]
                    if c >= INF:
                        continue
                    nd = dc + c + pen[n]
                else:
                    i2, j2 = i + di, j + dj
                    if not (0 <= i2 < nx and 0 <= j2 < ny):
                        continue
                    n2 = j2 * nx + i2
                    c = ec[d][n]
                    if c >= INF:
                        continue
                    nd = dc + c + pen[n2]
                if nd < dist[n2]:
                    dist[n2] = nd
                    heapq.heappush(heap, (nd, n2))
        return dist

    def field_for(self, xy, key=None):
        key = (key or (round(xy[0], 1), round(xy[1], 1)), self.ver)
        f = self.fcache.get(key)
        if f is None:
            if len(self.fcache) > 12:
                self.fcache.clear()
            f = self.dijkstra(xy[0], xy[1], True)
            self.fcache[key] = f
        return f

    def near(self, D, x, y):
        best = INF
        for n, c0 in self.seeds(x, y):
            if D[n] < INF:
                best = min(best, D[n] + c0)
        return best

    def interp(self, F, x, y):
        c = self.cell
        i = min(self.nx - 2, max(0, int(x / c)))
        j = min(self.ny - 2, max(0, int(y / c)))
        tx, ty = x / c - i, y / c - j
        nx = self.nx

        def v(n):
            return min(F[n], 1e4)
        a = v(j * nx + i) * (1 - tx) + v(j * nx + i + 1) * tx
        b = v((j + 1) * nx + i) * (1 - tx) + v((j + 1) * nx + i + 1) * tx
        return a * (1 - ty) + b * ty

    # ---------- model ----------
    def simdrive(self, p, hd, m):
        r = ls.drive(self.surf, self.phys, p[0], p[1], hd, m, self.slipbase, 0.0)
        x = p[0] + (r["x"] - p[0]) * self.k
        y = p[1] + (r["y"] - p[1]) * self.k
        x = min(self.surf.width, max(0.0, x))
        y = min(self.surf.height, max(0.0, y))
        return (x, y), r["ground"], r["stop"]

    def viol(self, p, hd, m):
        u = (math.cos(math.radians(hd)), math.sin(math.radians(hd)))
        s = 0.0
        while s < m:
            x, y = p[0] + u[0] * s, p[1] + u[1] * s
            x = min(self.surf.width, max(0.0, x))
            y = min(self.surf.height, max(0.0, y))
            h, gx, gy, code = self.surf.sample(x, y)
            if self.cons_slip(NAMES[code], gx * u[0] + gy * u[1]) > 0.44:
                return True
            s += 1.25
        return False

    def apply(self, p, cmd):
        if cmd["action"] != "drive":
            return p
        return self.simdrive(p, cmd["heading_deg"], cmd["metres"])[0]

    def project(self):
        p = self.est
        for r in sorted((r for r in self.cmds if r["exec"] > self.tick), key=lambda r: r["exec"]):
            p = self.apply(p, r["cmd"])
        return p

    def direct(self, p, goal):
        d = math.hypot(goal[0] - p[0], goal[1] - p[1])
        hd = math.degrees(math.atan2(goal[1] - p[1], goal[0] - p[0]))
        u = (math.cos(math.radians(hd)), math.sin(math.radians(hd)))
        m = max(0.1, d)
        end = p
        for _ in range(3):
            if m > 5.0:
                return None
            end, pg, stop = self.simdrive(p, hd, m)
            if stop:
                return None
            along = (end[0] - p[0]) * u[0] + (end[1] - p[1]) * u[1]
            if along < 0.05:
                return None
            m = max(0.1, m * d / along)
        if m > 5.0 or self.viol(p, hd, m):
            return None
        end, pg, stop = self.simdrive(p, hd, m)
        if stop:
            return None
        return ({"action": "drive", "heading_deg": round(hd % 360, 1), "metres": round(m, 2)}, end)

    def plan(self, pos, goal, F, n):
        cmds = []
        p = pos
        lh = self.last_heading
        final = False
        for _ in range(n):
            d = math.hypot(goal[0] - p[0], goal[1] - p[1])
            if d < 0.8:
                final = True
                break
            if d <= 4.6:
                c = self.direct(p, goal)
                if c:
                    cmds.append(c[0])
                    p = c[1]
                    final = True
                    break
            gh = math.degrees(math.atan2(goal[1] - p[1], goal[0] - p[0]))
            hs = [15.0 * i for i in range(24)] + [gh % 360]
            best = None
            for hd in hs:
                end, pg, stop = self.simdrive(p, hd, 5.0)
                if stop:
                    continue
                sc = self.interp(F, end[0], end[1])
                sc += 2.0 * max(0.0, self.surf.elevation(*end) - self.surf.elevation(*p))
                dh = abs((hd - lh + 180) % 360 - 180)
                sc += 0.03 * dh
                if self.viol(p, hd, 5.0):
                    sc += 500
                if best is None or sc < best[0]:
                    best = (sc, hd, end)
            if best is None or best[0] >= 5000:
                return (cmds, False) if cmds else (None, False)
            cmds.append({"action": "drive", "heading_deg": round(best[1], 1), "metres": 5.0})
            p = best[2]
            lh = best[1]
        return cmds, final

    # ---------- comms ----------
    def send(self, cmds):
        pos = self.project()
        pgs = []
        for c in cmds:
            if c["action"] == "drive":
                end, pg, stop = self.simdrive(pos, c["heading_deg"], c["metres"])
                pos = end
                pgs.append(pg)
            else:
                pgs.append(0.0)
        acks = self.t.uplink(cmds)
        for a, c, pg in zip(acks, cmds, pgs):
            rec = {"id": a["command_id"], "exec": a["execute_tick"], "sent": a["sent_tick"],
                   "cmd": c, "pg": pg}
            self.cmds.append(rec)
            self.by_exec[rec["exec"]] = rec
            self.byid[rec["id"]] = rec
            if c["action"] == "drive":
                self.last_heading = c["heading_deg"]
        return acks

    def sim_to(self, t):
        for tk in range(self.sim_tick + 1, t + 1):
            r = self.by_exec.get(tk)
            if r:
                self.est = self.apply(self.est, r["cmd"])
            self.hist[tk] = self.est
        self.sim_tick = t
        self.tick = t

    def resim(self, t, pos):
        self.est = pos
        self.hist[t] = pos
        for tk in range(t + 1, self.tick + 1):
            r = self.by_exec.get(tk)
            if r:
                self.est = self.apply(self.est, r["cmd"])
            self.hist[tk] = self.est

    def shift(self, t0, dx, dy):
        for tk in list(self.hist):
            if tk >= t0:
                x, y = self.hist[tk]
                self.hist[tk] = (x + dx, y + dy)
        self.est = (self.est[0] + dx, self.est[1] + dy)

    def process(self, p):
        t = p["tick"]
        self.last_pkt = max(self.last_pkt, t)
        if t >= self.batt_tick:
            self.batt_tick = t
            self.battery = p["battery"]
        for s in p.get("sampled_targets", []):
            self.sampled.add(s)
        pos = (p["position"][0], p["position"][1])
        stopped = False
        if t > 0:
            self.fixes.append((t, pos))
        for ev in p.get("events", []):
            ty = ev.get("type")
            if ty == "command_executed":
                r = self.byid.get(ev.get("command_id"))
                if r and r["cmd"]["action"] == "drive" and r["pg"] > 0.5 \
                        and p["wheel_odometry"] >= 0.99 * r["cmd"]["metres"]:
                    self.sv += p["visual_odometry"]
                    self.sp += r["pg"]
                    self.k = min(1.4, max(0.75, self.sv / self.sp))
            elif ty == "safety_stop":
                stopped = True
                self.on_stop(t, pos, ev.get("reason"))
        if stopped or t == 0 or t not in self.hist:
            return
        hx, hy = self.hist[t]
        dx, dy = pos[0] - hx, pos[1] - hy
        n = math.hypot(dx, dy)
        if n > 4.0:
            dx, dy = dx * 4.0 / n, dy * 4.0 / n
        self.shift(t, 0.3 * dx, 0.3 * dy)

    def on_stop(self, t, pos, reason):
        drop = [r for r in self.cmds if r["sent"] <= t and r["exec"] > t]
        for r in drop:
            self.cmds.remove(r)
            if self.by_exec.get(r["exec"]) is r:
                del self.by_exec[r["exec"]]
        if t <= self.tick:
            self.resim(t, pos)
        else:
            self.est = pos
        c = self.cell
        for j in range(self.ny):
            if abs(j * c - pos[1]) > 8:
                continue
            for i in range(self.nx):
                if math.hypot(i * c - pos[0], j * c - pos[1]) <= 7:
                    self.pen[j * self.nx + i] += 80.0
        self.ver += 1
        g = self.goal
        if g:
            g["phase"] = "travel"
            g["stops"] = g.get("stops", 0) + 1
            if g["stops"] >= 4 and g["kind"] == "target":
                self.skip.add(g["id"])
                self.goal = None

    # ---------- decisions ----------
    def choose(self):
        tick = self.tick
        try:
            self.targets = self.t.map()["targets"]
        except Exception:
            pass
        est = self.est
        D = self.dijkstra(est[0], est[1], False)
        R = self.field_for(self.base, "base")
        cands = []
        act = [t for t in self.targets if t["id"] not in self.sampled and t["id"] not in self.skip
               and t.get("appear_tick", 0) <= tick]
        OV = 16.0
        for t in act:
            dm = self.near(D, t["x"], t["y"])
            rm = self.near(R, t["x"], t["y"])
            if dm >= 1e8 or rm >= 1e8:
                continue
            tt, tb = dm / 4.5, rm / 4.5
            if tick + tt + OV + tb + 14 > self.maxt:
                continue
            arr = tick + tt + OV * 0.6
            dl = t.get("deadline_tick")
            v = t["value"] if dl is None or arr <= dl else t["late_value"]
            bonus = 0.0
            for o in act:
                if o is not t and math.hypot(o["x"] - t["x"], o["y"] - t["y"]) < 45:
                    bonus += 0.04 * o["value"]
            bonus = min(0.4, bonus)
            cands.append((v * (1 + bonus) / (tt + OV), t))
        if cands:
            cands.sort(key=lambda a: -a[0])
            t = cands[0][1]
            self.goal = {"kind": "target", "id": t["id"], "t": (t["x"], t["y"]),
                         "xy": (t["x"], t["y"]), "phase": "travel", "fails": 0, "off": OFFS[0]}
            return
        if math.hypot(est[0] - self.base[0], est[1] - self.base[1]) > 2.2:
            self.goal = {"kind": "base", "xy": self.base, "phase": "travel"}
        else:
            self.parked_until = tick + 8

    def too_late(self):
        R = self.field_for(self.base, "base")
        rm = self.near(R, self.est[0], self.est[1])
        return self.tick + rm / 4.5 + 16 > self.maxt

    def decide(self):
        tick = self.tick
        unexec = [r for r in self.cmds if r["exec"] > tick]
        g = self.goal
        if g is None:
            if unexec or tick < self.parked_until:
                return
            if self.battery < 20 and tick < self.maxt - 70:
                self.send([{"action": "wait"}] * 5)
                return
            self.choose()
            g = self.goal
            if g is None:
                return
        if g["kind"] == "target" and g["phase"] in ("travel", "settle") and self.too_late():
            self.goal = g = {"kind": "base", "xy": self.base, "phase": "travel"}
        ph = g["phase"]
        if ph == "travel":
            self.do_travel(g, unexec)
        elif ph == "settle":
            self.do_settle(g, unexec)
        elif ph == "wait_sample":
            self.do_wait(g)

    def do_travel(self, g, unexec):
        if len(unexec) > 3:
            return
        pos = self.project()
        F = self.field_for(g["xy"])
        cmds, final = self.plan(pos, g["xy"], F, 5)
        if cmds is None:
            if g["kind"] == "target":
                self.skip.add(g["id"])
            else:
                self.parked_until = self.tick + 10
            self.goal = None
            return
        if cmds:
            self.send(cmds)
        if final:
            g["phase"] = "settle"

    def settled_est(self):
        lastd = max([r["exec"] for r in self.cmds
                     if r["cmd"]["action"] == "drive" and r["exec"] <= self.tick], default=0)
        fx = [pos for (t, pos) in self.fixes if t >= lastd]
        return lastd, fx

    def do_settle(self, g, unexec):
        if unexec:
            return
        lastd, fx = self.settled_est()
        n = len(fx)
        if n < 5 and self.tick < lastd + 16:
            return
        if n >= 3:
            xs = sorted(p[0] for p in fx)
            ys = sorted(p[1] for p in fx)
            if n >= 5:
                xs, ys = xs[1:-1], ys[1:-1]
                mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
            else:
                mid = n // 2
                if n % 2:
                    mx, my = xs[mid], ys[mid]
                else:
                    mx, my = (xs[mid - 1] + xs[mid]) / 2, (ys[mid - 1] + ys[mid]) / 2
            self.shift(lastd, mx - self.est[0], my - self.est[1])
        est = self.est
        if g["kind"] == "base":
            d = math.hypot(self.base[0] - est[0], self.base[1] - est[1])
            if d <= 2.0:
                self.goal = None
                self.parked_until = self.tick + 8
            elif d <= 6.0:
                c = self.direct(est, self.base)
                if c:
                    self.send([c[0]])
                else:
                    g["phase"] = "travel"
            else:
                g["phase"] = "travel"
            return
        off = g["off"]
        aim = (g["t"][0] + off[0], g["t"][1] + off[1])
        g["xy"] = aim
        d = math.hypot(aim[0] - est[0], aim[1] - est[1])
        thr = 1.4 if g["fails"] == 0 else 1.0
        if d <= thr:
            acks = self.send([{"action": "sample"}])
        elif d <= 6.0:
            c = self.direct(est, aim)
            if not c:
                g["phase"] = "travel"
                return
            acks = self.send([c[0], {"action": "sample"}])
        else:
            g["phase"] = "travel"
            return
        g["sexec"] = acks[-1]["execute_tick"]
        g["phase"] = "wait_sample"

    def do_wait(self, g):
        if g["id"] in self.sampled:
            self.goal = None
            return
        if self.last_pkt >= g["sexec"] or self.tick > g["sexec"] + 25:
            g["fails"] += 1
            if g["fails"] >= 4:
                self.skip.add(g["id"])
                self.goal = None
                return
            g["off"] = OFFS[g["fails"]]
            g["phase"] = "settle"

    def run(self):
        log = self.t.telemetry_log()
        if log:
            p0 = log[0]
            self.est = (p0["position"][0], p0["position"][1])
            self.hist[0] = self.est
            self.process(p0)
        while True:
            try:
                self.decide()
            except Exception:
                self.goal = None
            r = self.t.advance(1)
            self.sim_to(r["current_tick"])
            for p in r["packets"]:
                self.process(p)
            if r["episode_complete"]:
                break


def play(tools):
    Rover(tools).run()
```