import math, sys, time, json, random, itertools, heapq
import numpy as np

D2R = math.pi / 180.0


def log(*a):
    print(*a, flush=True)


class Mission:
    def __init__(self, tools):
        self.tools = tools
        self.rules = tools.rules()
        self.world = tools.map()
        self.mission = self.world.get("mission")
        r = self.rules
        self.delay = r["delay_ticks"]
        self.max_ticks = r["max_ticks"]
        self.idle_cost = r["idle_cost"]
        self.drive_cost = r["drive_cost"]
        self.sample_cost = r["sample_cost"]
        self.trad = r["target_radius"]
        self.brad = r["base_radius"]
        self.mult = r.get("terrain_drive_multipliers", {"bedrock": 1.0, "sand": 2.0})
        sens = r.get("sensing") or {}
        self.pos_noise = max(sens.get("position_noise_m", 0.0), 0.05)
        self.vo_noise = max(sens.get("visual_odometry_noise", 0.0), 0.01)
        self.bias_max = sens.get("heading_bias_deg", 0.0)
        self.bias_walk = sens.get("heading_bias_walk_deg", 0.0)
        self.head_noise = sens.get("heading_noise_deg", 0.0)
        self.slip_ranges = r["slip_ranges"]
        self.base = tuple(self.world["base"])
        self.W = self.world["width"]; self.H = self.world["height"]
        self.sand = self.world.get("sand", [])
        self.haz = self.world.get("hazards", [])
        self.margin = 1.0
        self.packets = {}
        self.cmds = {}  # exec_tick -> (cmd, sent_tick)
        self.pending = {}  # target id -> exec tick of sample
        self.sampled = set()
        self.waits_at = {}
        self.last_exec = 0
        self.battery = r["initial_battery"]
        self.start = None
        self.build_graph()
        for p in tools.telemetry_log():
            self.packets[p["tick"]] = p
        if 0 in self.packets:
            self.start = tuple(self.packets[0]["position"])
        else:
            self.start = self.base

    # ---------- geometry ----------
    def terrain(self, x, y):
        for s in self.sand:
            if s["x1"] <= x <= s["x2"] and s["y1"] <= y <= s["y2"]:
                return "sand"
        return "bedrock"

    def inflated(self, m=None):
        m = self.margin if m is None else m
        return [(h["x1"] - m, h["y1"] - m, h["x2"] + m, h["y2"] + m) for h in self.haz]

    def seg_hits(self, a, b, rect):
        x1, y1, x2, y2 = rect
        dx, dy = b[0] - a[0], b[1] - a[1]
        t0, t1 = 0.0, 1.0
        for p, q in ((-dx, a[0] - x1), (dx, x2 - a[0]), (-dy, a[1] - y1), (dy, y2 - a[1])):
            if abs(p) < 1e-12:
                if q < 0:
                    return False
            else:
                t = q / p
                if p < 0:
                    if t > t1: return False
                    if t > t0: t0 = t
                else:
                    if t < t0: return False
                    if t < t1: t1 = t
        return t0 < t1 - 1e-9

    def inside(self, p, rect):
        return rect[0] < p[0] < rect[2] and rect[1] < p[1] < rect[3]

    def build_graph(self):
        rects = self.inflated()
        self.rects = rects
        self.corners = []
        for (x1, y1, x2, y2) in self.inflated(self.margin + 0.1):
            for c in ((x1, y1), (x1, y2), (x2, y1), (x2, y2)):
                if 0.5 < c[0] < self.W - 0.5 and 0.5 < c[1] < self.H - 0.5:
                    if not any(self.inside(c, r) for r in rects):
                        self.corners.append(c)

    def clear(self, a, b):
        for r in self.rects:
            if self.inside(a, r) or self.inside(b, r):
                # allow escaping/entering only if the real hazard isn't crossed
                if self.real_hit(a, b):
                    return False
                continue
            if self.seg_hits(a, b, r):
                return False
        return True

    def real_hit(self, a, b):
        for h in self.haz:
            if self.seg_hits(a, b, (h["x1"] - 0.2, h["y1"] - 0.2, h["x2"] + 0.2, h["y2"] + 0.2)):
                return True
        return False

    def seg_cost(self, a, b):
        """wheel metres, ticks, energy for a straight segment"""
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if L < 1e-9:
            return 0.0, 0, 0.0
        n = max(1, int(L / 0.25))
        wheel = 0.0; energy = 0.0
        for i in range(n):
            t = (i + 0.5) / n
            ter = self.terrain(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
            w = (L / n) / (1 - self.slip_est(ter))
            wheel += w
            energy += w * self.drive_cost * self.mult.get(ter, 1.0)
        return wheel, math.ceil(wheel / 5.0 - 1e-6), energy

    def path(self, a, b):
        """shortest path through corners. returns (points, ticks, energy, length)"""
        if self.clear(a, b):
            w, t, e = self.seg_cost(a, b)
            return [a, b], t, e
        nodes = [a, b] + self.corners
        n = len(nodes)
        dist = [math.inf] * n; prev = [-1] * n
        dist[0] = 0; pq = [(0, 0)]
        while pq:
            d, i = heapq.heappop(pq)
            if d > dist[i]: continue
            if i == 1: break
            for j in range(n):
                if j == i: continue
                if not self.clear(nodes[i], nodes[j]): continue
                nd = d + math.hypot(nodes[i][0] - nodes[j][0], nodes[i][1] - nodes[j][1])
                if nd < dist[j]:
                    dist[j] = nd; prev[j] = i; heapq.heappush(pq, (nd, j))
        if dist[1] == math.inf:
            w, t, e = self.seg_cost(a, b)
            return [a, b], t + 1, e
        pts = []; i = 1
        while i != -1:
            pts.append(nodes[i]); i = prev[i]
        pts.reverse()
        T = 0; E = 0.0
        for k in range(len(pts) - 1):
            w, t, e = self.seg_cost(pts[k], pts[k + 1])
            T += t; E += e
        return pts, T, E

    # ---------- slip estimation ----------
    def slip_est(self, ter):
        lo, hi = self.slip_ranges.get(ter, [0.0, 0.0])
        m0 = (lo + hi) / 2; v0 = ((hi - lo) / 2) ** 2 / 3 + 1e-6
        obs = getattr(self, "_slip_obs", {}).get(ter, [])
        if not obs:
            return m0
        vo = (self.vo_noise * 0.8) ** 2
        num = m0 / v0 + sum(obs) / vo
        den = 1 / v0 + len(obs) / vo
        return min(max(num / den, lo), hi)

    def slip_var(self, ter):
        lo, hi = self.slip_ranges.get(ter, [0.0, 0.0])
        v0 = ((hi - lo) / 2) ** 2 / 3 + 1e-6
        n = len(getattr(self, "_slip_obs", {}).get(ter, []))
        vo = (self.vo_noise * 0.8) ** 2
        return 1 / (1 / v0 + n / vo) + 0.012 ** 2

    # ---------- filter ----------
    def run_filter(self):
        ticks = sorted(self.packets)
        self._slip_obs = {}
        for k in ticks:
            p = self.packets[k]
            w = p.get("wheel_odometry") or 0
            v = p.get("visual_odometry") or 0
            if w > 0.3 and v > 0:
                ter = p.get("terrain", "bedrock")
                ev = " ".join(json.dumps(e) for e in p.get("events", []))
                if "stop" not in ev and "hazard" not in ev:
                    self._slip_obs.setdefault(ter, []).append(1 - v / w)
        N = 9
        comps = []
        bm = self.bias_max
        for j in range(N):
            b = -bm + 2 * bm * (j + 0.5) / N if bm > 0 else 0.0
            P = np.diag([1e-4, 1e-4, ((2 * bm / N) ** 2) / 12 + 0.3 if bm > 0 else 1e-4])
            comps.append([np.array([self.start[0], self.start[1], b]), P, 1.0 / N])
        R = np.eye(2) * self.pos_noise ** 2
        Hm = np.array([[1.0, 0, 0], [0, 1.0, 0]])
        prev_sampled = set()
        K = 0
        for k in ticks:
            if k == 0:
                prev_sampled = set(self.packets[0].get("sampled_targets", []))
                continue
            p = self.packets[k]
            K = k
            w = p.get("wheel_odometry") or 0
            v = p.get("visual_odometry") or 0
            if w > 1e-6:
                h = self.cmds[k][0]["heading_deg"] if k in self.cmds and self.cmds[k][0].get("action") == "drive" else p.get("heading_deg", 0.0)
                ter = p.get("terrain", "bedrock")
                s = self.slip_est(ter)
                d1 = w * (1 - s); v1 = w * w * self.slip_var(ter)
                v2 = (self.vo_noise * max(v, 0.01)) ** 2 + 1e-4
                d = (d1 / v1 + v / v2) / (1 / v1 + 1 / v2)
                vd = 1 / (1 / v1 + 1 / v2)
                for c in comps:
                    self.predict(c, h, d, vd)
            for c in comps:
                m, P, wt = c
                S = Hm @ P @ Hm.T + R
                z = np.array(p["position"], dtype=float)
                y = z - Hm @ m
                Si = np.linalg.inv(S)
                lik = math.exp(-0.5 * y @ Si @ y) / math.sqrt(np.linalg.det(S))
                Kg = P @ Hm.T @ Si
                c[0] = m + Kg @ y
                c[1] = (np.eye(3) - Kg @ Hm) @ P
                c[2] = wt * max(lik, 1e-300)
            # successful sample = fix at target
            cur = set(p.get("sampled_targets", []))
            for tid in cur - prev_sampled:
                tg = self.target_by_id(tid)
                if tg is not None:
                    z = np.array([tg["x"], tg["y"]])
                    Rt = np.eye(2) * (self.trad ** 2 / 4)
                    for c in comps:
                        m, P, wt = c
                        S = Hm @ P @ Hm.T + Rt
                        y = z - Hm @ m
                        Si = np.linalg.inv(S)
                        lik = math.exp(-0.5 * y @ Si @ y) / math.sqrt(np.linalg.det(S))
                        Kg = P @ Hm.T @ Si
                        c[0] = m + Kg @ y
                        c[1] = (np.eye(3) - Kg @ Hm) @ P
                        c[2] = wt * max(lik, 1e-300)
            prev_sampled = cur
            tot = sum(c[2] for c in comps)
            for c in comps:
                c[2] = max(c[2] / tot, 1e-4)
            tot = sum(c[2] for c in comps)
            for c in comps:
                c[2] /= tot
        # merge
        mean = sum(c[2] * c[0] for c in comps)
        cov = sum(c[2] * (c[1] + np.outer(c[0] - mean, c[0] - mean)) for c in comps)
        return K, mean, cov

    def predict(self, c, h, d, vd):
        m, P, wt = c
        P = P.copy()
        P[2, 2] += self.bias_walk ** 2
        th = (h + m[2]) * D2R
        ct, st = math.cos(th), math.sin(th)
        m = m + np.array([d * ct, d * st, 0.0])
        F = np.eye(3)
        F[0, 2] = -d * st * D2R
        F[1, 2] = d * ct * D2R
        lat = (d * self.head_noise * D2R) ** 2
        Rot = np.array([[ct, -st], [st, ct]])
        Q2 = Rot @ np.diag([vd, lat]) @ Rot.T
        Q = np.zeros((3, 3)); Q[:2, :2] = Q2
        P = F @ P @ F.T + Q
        c[0] = m; c[1] = P

    def target_by_id(self, tid):
        for t in self.world.get("targets", []):
            if t["id"] == tid:
                return t
        return None

    # ---------- planning ----------
    def plan_route(self, P, t0, battery_est):
        r1 = self._plan(P, t0, battery_est, None)
        pg = getattr(self, "prev_goal", None)
        if pg and r1[0] and r1[0][0]["id"] != pg:
            r2 = self._plan(P, t0, battery_est, pg)
            if r2[0] and r2[2][0][0] >= r1[2][0][0] - 0.01:
                return r2
        return r1

    def _plan(self, P, t0, battery_est, force):
        tg = [t for t in self.world.get("targets", [])
              if t["id"] not in self.sampled and t["id"] not in self.pending]
        pts = [P] + [(t["x"], t["y"]) for t in tg] + [self.base]
        n = len(pts)
        legs = {}
        for i in range(n):
            for j in range(1, n):
                if i != j:
                    legs[(i, j)] = self.path(pts[i], pts[j])
        end_tick = self.max_ticks - 1
        reserve = 7.0
        best = [(-1, 0, 0), []]
        idle_total = self.idle_cost * max(0, self.max_ticks - t0 + 1)
        budget = battery_est - idle_total - reserve
        bidx = n - 1

        def dfs(i, t, e, val, seq, used):
            # option: go home now
            _, tb, eb = legs[(i, bidx)] if i != bidx else (None, 0, 0)
            if t + tb <= end_tick and e + eb * 1.15 <= budget:
                key = (val, -(t + tb), -e)
                if key > best[0]:
                    best[0] = key; best[1] = list(seq)
            for j in range(1, n - 1):
                if used & (1 << j): continue
                if force and i == 0 and tg[j - 1]["id"] != force: continue
                _, tt, ee = legs[(i, j)]
                ts = t + tt  # sample tick
                tgt = tg[j - 1]
                if ts > end_tick: continue
                dl = tgt.get("deadline_tick")
                v = tgt["value"] if (dl is None or ts <= dl) else tgt.get("late_value", 0)
                ne = e + ee * 1.15 + 0.5 + self.sample_cost
                if ne > budget: continue
                seq.append(j)
                dfs(j, ts + 1, ne, val + v, seq, used | (1 << j))
                seq.pop()

        dfs(0, t0, 0.0, 0.0, [], 0)
        route = [tg[j - 1] for j in best[1]]
        return route, legs, best

    # ---------- main per-tick decision ----------
    def step(self, now):
        next_exec = max(now + self.delay + 1, self.last_exec + 1)
        if next_exec > self.max_ticks:
            return
        K, mean, cov = self.run_filter()
        # resolve pending samples
        for tid, et in list(self.pending.items()):
            if K >= et:
                st = self.packets[K].get("sampled_targets", [])
                if tid in st:
                    self.sampled.add(tid)
                else:
                    log(f"  sample of {tid} at {et} FAILED")
                self.pending.pop(tid)
        if K in self.packets:
            for tid in self.packets[K].get("sampled_targets", []):
                self.sampled.add(tid)
            self.battery = self.packets[K].get("battery", self.battery)
        # propagate through queued commands
        c = [mean.copy(), cov.copy(), 1.0]
        battery_est = self.battery
        for et in range(K + 1, next_exec):
            battery_est -= self.idle_cost
            if et in self.cmds:
                cmd = self.cmds[et][0]
                if cmd["action"] == "drive":
                    ter = self.terrain(c[0][0], c[0][1])
                    s = self.slip_est(ter)
                    d = cmd["metres"] * (1 - s)
                    vd = cmd["metres"] ** 2 * self.slip_var(ter)
                    self.predict(c, cmd["heading_deg"], d, vd)
                    battery_est -= cmd["metres"] * self.drive_cost * self.mult.get(ter, 1)
                elif cmd["action"] == "sample":
                    battery_est -= self.sample_cost
        m, P = c[0], c[1]
        pos = (float(m[0]), float(m[1])); bias = float(m[2])
        Pp = P[:2, :2]
        route, legs, best = self.plan_route(pos, next_exec, battery_est)
        goal = route[0] if route else None
        self.prev_goal = goal["id"] if goal else None
        gpt = (goal["x"], goal["y"]) if goal else self.base
        dist = math.hypot(gpt[0] - pos[0], gpt[1] - pos[1])
        sig = math.sqrt(max(np.trace(Pp) / 2, 0))
        cmd = None
        if goal is not None:
            prob = self.hit_prob(pos, Pp, gpt, self.trad)
            if dist < 0.35 and (prob > 0.6 or self.waits_at.get(goal["id"], 0) >= 2):
                cmd = {"action": "sample"}
            elif dist < 0.35:
                self.waits_at[goal["id"]] = self.waits_at.get(goal["id"], 0) + 1
                cmd = {"action": "wait"}
        else:
            if dist < 0.25:
                cmd = {"action": "wait"}
        if cmd is None:
            pts, _, _ = self.path(pos, gpt)
            wp = pts[1]
            k = 1
            while k < len(pts) - 1 and math.hypot(pts[k][0] - pos[0], pts[k][1] - pos[1]) < 0.3:
                k += 1; wp = pts[k]
            dx, dy = wp[0] - pos[0], wp[1] - pos[1]
            L = math.hypot(dx, dy)
            ter = self.terrain(pos[0] + dx / 2, pos[1] + dy / 2)
            met = min(5.0, max(0.05, L / (1 - self.slip_est(ter))))
            hd = (math.degrees(math.atan2(dy, dx)) - bias) % 360
            cmd = {"action": "drive", "heading_deg": round(hd, 2), "metres": round(met, 3)}
        try:
            acks = self.tools.uplink([cmd])
        except ValueError as e:
            log("uplink rejected", e)
            return
        et = acks[0]["execute_tick"] if isinstance(acks, list) and acks and "execute_tick" in acks[0] else next_exec
        self.cmds[et] = (cmd, now)
        self.last_exec = et
        if cmd["action"] == "sample" and goal is not None:
            self.pending[goal["id"]] = et
        tp = self.packets.get(K, {}).get("true")
        if tp:
            log(f"   ERR K={K} est=({mean[0]:.2f},{mean[1]:.2f}) true=({tp[0]:.2f},{tp[1]:.2f}) err={math.hypot(mean[0]-tp[0],mean[1]-tp[1]):.2f} sigK={math.sqrt(np.trace(cov[:2,:2])/2):.2f} b={mean[2]:.1f} tb={self.packets[K]['tbias']:.1f}")
        log(f"t={now} K={K} ex={et} pos=({pos[0]:.2f},{pos[1]:.2f}) sig={sig:.2f} b={bias:.1f} bat~{battery_est:.1f} "
            f"goal={goal['id'] if goal else 'base'} d={dist:.2f} route={[r['id'] for r in route]} val={best[0][0]} cmd={cmd}")

    def hit_prob(self, pos, P, g, r):
        try:
            L = np.linalg.cholesky(P + np.eye(2) * 1e-9)
        except Exception:
            return 0.5
        rng = np.random.default_rng(0)
        s = rng.standard_normal((400, 2)) @ L.T + np.array(pos)
        return float(np.mean(np.hypot(s[:, 0] - g[0], s[:, 1] - g[1]) < r))

    def ingest(self, pkts):
        for p in pkts or []:
            self.packets[p["tick"]] = p
            for e in p.get("events", []):
                if not (isinstance(e, dict) and e.get("type") == "target_discovered"):
                    log("  event", p["tick"], e)


def run(tools):
    started = False
    while True:
        M = Mission(tools)
        log(f"=== mission {M.mission} targets={len(M.world['targets'])}")
        now = 0
        if not started:
            started = True
        # first command immediately
        try:
            M.step(0)
        except Exception as e:
            log("step error", repr(e))
        while True:
            t0 = time.time()
            out = tools.advance(1)
            now = out["current_tick"]
            pk = None
            for k, v in out.items():
                if isinstance(v, list) and v and isinstance(v[0], dict) and "tick" in v[0]:
                    pk = v
            if pk is None and not out.get("episode_complete"):
                pk = tools.telemetry_log()
            M.ingest(pk or [])
            if out.get("episode_complete"):
                pk = M.packets.get(max(M.packets))
                log(f"=== mission {M.mission} complete; last packet {pk}")
                break
            try:
                M.world = tools.map()
                M.step(now)
            except Exception as e:
                import traceback; traceback.print_exc()
            log(f"   loop {time.time()-t0:.2f}s")
        if out.get("campaign_complete"):
            log("campaign complete")
            return
        # wait for next mission
        for _ in range(50):
            w = tools.map()
            if w.get("mission") != M.mission:
                break
            time.sleep(0.1)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "mock":
        from mock import MockTools
        run(MockTools(int(sys.argv[2]) if len(sys.argv) > 2 else 0))
    else:
        from lightlag_client import connect
        with connect("http://lightlag:8000/mcp") as tools:
            run(tools)
