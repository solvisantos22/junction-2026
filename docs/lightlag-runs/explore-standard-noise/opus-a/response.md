```python
import math


def _rect(r):
    x1 = float(r["x1"]); x2 = float(r["x2"]); y1 = float(r["y1"]); y2 = float(r["y2"])
    return (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))


def _clip(ax, ay, bx, by, rc):
    """Liang-Barsky: parameter interval of segment AB inside rect rc, or None."""
    dx = bx - ax
    dy = by - ay
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, ax - rc[0]), (dx, rc[2] - ax), (-dy, ay - rc[1]), (dy, rc[3] - ay)):
        if abs(p) < 1e-12:
            if q < 0:
                return None
        else:
            r = q / p
            if p < 0:
                if r > t1:
                    return None
                if r > t0:
                    t0 = r
            else:
                if r < t0:
                    return None
                if r < t1:
                    t1 = r
    if t1 < t0:
        return None
    return (t0, t1)


def _pdist(px, py, rc):
    dx = max(rc[0] - px, 0.0, px - rc[2])
    dy = max(rc[1] - py, 0.0, py - rc[3])
    return math.hypot(dx, dy)


def _psucc(dist, var, r):
    if dist >= r:
        return 0.0
    if var < 1e-9:
        return 1.0
    return 1.0 - math.exp(-((r - dist) ** 2) / (2.0 * var))


class _Pilot:
    def __init__(self, tools):
        self.tools = tools
        R = tools.rules() or {}
        M = tools.map() or {}
        self.R = R
        self.d = int(R.get("delay_ticks", 3))
        self.maxt = int(R.get("max_ticks", 50))
        self.idle = float(R.get("idle_cost", 0.5))
        self.dcost = float(R.get("drive_cost", 1.0))
        self.scost = float(R.get("sample_cost", 3.0))
        self.trad = float(R.get("target_radius", 0.75))
        self.brad = float(R.get("base_radius", 0.75))
        self.maxm = float(R.get("max_metres_per_drive", 5.0))
        self.batt = float(R.get("initial_battery", 100.0))
        sw = R.get("sample_windows") or {}
        try:
            self.late_frac = float(sw.get("late_fraction", 0.25)) if isinstance(sw, dict) else 0.25
        except Exception:
            self.late_frac = 0.25

        self.W = float(M.get("width", 40.0))
        self.H = float(M.get("height", 40.0))
        b = M.get("base") or [self.W / 2, self.H / 2]
        self.base = (float(b[0]), float(b[1]))
        self.dter = M.get("default_terrain", "bedrock")
        self.sand = [_rect(r) for r in (M.get("sand") or [])]
        self.haz = [_rect(r) for r in (M.get("hazards") or [])]
        self.mults = R.get("terrain_drive_multipliers") or {}

        sn = R.get("slip_noise") or [-0.02, 0.02]
        self.snv = (float(sn[1]) - float(sn[0])) ** 2 / 12.0
        self.slip = {}
        for ter, rg in (R.get("slip_ranges") or {}).items():
            lo, hi = float(rg[0]), float(rg[1])
            self.slip[ter] = [(lo + hi) / 2.0, max((hi - lo) ** 2 / 12.0, 1e-6), lo, hi]

        sens = R.get("sensing")
        self.noisy = bool(sens)
        if self.noisy:
            self.sp = float(sens.get("position_noise_m", 0.3) or 0.0)
            self.von = float(sens.get("visual_odometry_noise", 0.05) or 0.0)
            self.bias0 = math.radians(float(sens.get("heading_bias_deg", 5.0) or 0.0))
            self.walk = math.radians(float(sens.get("heading_bias_walk_deg", 0.5) or 0.0))
            self.hn = math.radians(float(sens.get("heading_noise_deg", 1.5) or 0.0))
            if self.sp < 1e-3:
                self.sp = 1e-3
        else:
            self.sp = 0.0
            self.von = 0.0
            self.bias0 = 0.0
            self.walk = 0.0
            self.hn = 0.0
        self.margin = 0.9 if self.noisy else 0.4
        self.reserve = 5.0 if self.noisy else 3.0

        self.x, self.y = self.base
        self.b = 0.0
        self.P = [[0.0] * 3 for _ in range(3)]
        self.P[2][2] = self.bias0 ** 2 / 3.0
        self.last_k = -1
        self.cmds = {}
        self.last_exec = 0
        self.sampled = set()
        self.pending = {}
        self.goal_id = None
        self.waited = 0
        self.alive = True

        # static graph nodes
        self.snodes = []
        cand = []
        m = self.margin + 0.15
        for rc in self.haz:
            cand += [(rc[0] - m, rc[1] - m), (rc[2] + m, rc[1] - m),
                     (rc[0] - m, rc[3] + m), (rc[2] + m, rc[3] + m)]
        for rc in self.sand:
            o = 0.3
            cand += [(rc[0] - o, rc[1] - o), (rc[2] + o, rc[1] - o),
                     (rc[0] - o, rc[3] + o), (rc[2] + o, rc[3] + o)]
        for (px, py) in cand:
            if px < 0.3 or py < 0.3 or px > self.W - 0.3 or py > self.H - 0.3:
                continue
            if any(_pdist(px, py, rc) < self.margin + 0.1 for rc in self.haz):
                continue
            self.snodes.append((px, py))

    # ---------- terrain / slip ----------
    def ter(self, x, y):
        for rc in self.sand:
            if rc[0] <= x <= rc[2] and rc[1] <= y <= rc[3]:
                return "sand"
        return self.dter

    def smean(self, t):
        v = self.slip.get(t)
        return v[0] if v else 0.0

    def svar(self, t):
        v = self.slip.get(t)
        return (v[1] if v else 0.0) + self.snv

    def mult(self, t):
        try:
            return float(self.mults.get(t, 1.0))
        except Exception:
            return 1.0

    def sim(self, x, y, phi, wheel):
        n = max(1, int(math.ceil(wheel / 0.1 - 1e-9)))
        dw = wheel / n
        c = math.cos(phi); s = math.sin(phi)
        g = en = sd = 0.0
        for _ in range(n):
            t = self.ter(x, y)
            k = 1.0 - self.smean(t)
            st = dw * k
            x += st * c; y += st * s; g += st
            en += dw * self.dcost * self.mult(t)
            sd += dw * math.sqrt(self.svar(t))
        return x, y, g, en, sd

    def wheel_for(self, x, y, phi, D):
        c = math.cos(phi); s = math.sin(phi)
        w = g = 0.0
        it = 0
        while g < D - 1e-9 and it < 3000:
            t = self.ter(x, y)
            k = max(0.05, 1.0 - self.smean(t))
            st = min(0.1 * k, D - g)
            w += st / k; g += st
            x += st * c; y += st * s
            it += 1
        return w

    def slip_obs(self, ter, o):
        v = self.slip.get(ter)
        if not v:
            return
        lo, hi = v[2], v[3]
        if o < lo - 0.1 or o > hi + 0.1:
            return
        ov = self.snv + (self.von * (1.0 - v[0])) ** 2 + 1e-6
        nv = 1.0 / (1.0 / v[1] + 1.0 / ov)
        v[0] = nv * (v[0] / v[1] + o / ov)
        v[1] = nv
        v[0] = min(hi, max(lo, v[0]))

    # ---------- filter ----------
    def prop(self, P, b, d, h, sd2):
        P = [r[:] for r in P]
        if self.noisy:
            P[2][2] += self.walk ** 2
        phi = h + b
        c = math.cos(phi); s = math.sin(phi)
        a = -d * s; e = d * c
        FP = [[P[0][j] + a * P[2][j] for j in range(3)],
              [P[1][j] + e * P[2][j] for j in range(3)],
              [P[2][j] for j in range(3)]]
        N = [[FP[i][0] + a * FP[i][2], FP[i][1] + e * FP[i][2], FP[i][2]] for i in range(3)]
        sh2 = (d * self.hn) ** 2
        N[0][0] += sd2 * c * c + sh2 * s * s
        N[1][1] += sd2 * s * s + sh2 * c * c
        cr = (sd2 - sh2) * c * s
        N[0][1] += cr
        N[1][0] += cr
        return N

    def ekf_drive(self, d, h):
        phi = h + self.b
        if self.noisy:
            sd2 = (self.von * d) ** 2 + 1e-6
            self.P = self.prop(self.P, self.b, d, h, sd2)
        self.x += d * math.cos(phi)
        self.y += d * math.sin(phi)

    def ekf_update(self, zx, zy):
        P = self.P
        r = self.sp ** 2
        S00 = P[0][0] + r; S01 = P[0][1]; S10 = P[1][0]; S11 = P[1][1] + r
        det = S00 * S11 - S01 * S10
        if abs(det) < 1e-12:
            return
        i00 = S11 / det; i01 = -S01 / det; i10 = -S10 / det; i11 = S00 / det
        K = [[P[i][0] * i00 + P[i][1] * i10, P[i][0] * i01 + P[i][1] * i11] for i in range(3)]
        ix = zx - self.x; iy = zy - self.y
        self.x += K[0][0] * ix + K[0][1] * iy
        self.y += K[1][0] * ix + K[1][1] * iy
        self.b += K[2][0] * ix + K[2][1] * iy
        lim = self.bias0 + 0.15
        self.b = max(-lim, min(lim, self.b))
        N = [[P[i][j] - K[i][0] * P[0][j] - K[i][1] * P[1][j] for j in range(3)] for i in range(3)]
        for i in range(3):
            for j in range(i + 1, 3):
                v = 0.5 * (N[i][j] + N[j][i])
                N[i][j] = v; N[j][i] = v
            if N[i][i] < 1e-9:
                N[i][i] = 1e-9
        self.P = N

    # ---------- telemetry ----------
    def ingest(self):
        log = self.tools.telemetry_log() or []
        for pk in sorted(log, key=lambda p: p.get("tick", -1)):
            if pk.get("tick", -1) > self.last_k:
                try:
                    self.process(pk)
                except Exception:
                    self.last_k = max(self.last_k, pk.get("tick", self.last_k))

    def process(self, pk):
        k = int(pk.get("tick"))
        events = pk.get("events") or []
        execd = []
        stop = False
        for e in events:
            if not isinstance(e, dict):
                continue
            ty = str(e.get("type", "")).lower()
            if ty == "command_executed":
                execd.append(e.get("command_id"))
            elif any(w in ty for w in ("stop", "safety", "hazard", "cancel", "edge", "abort", "collision")):
                stop = True
        pos = pk.get("position")
        drove = False
        for cid in execd:
            c = self.cmds.get(cid)
            if c is None:
                continue
            c["status"] = "done"
            cmd = c["cmd"]
            if cmd.get("action") == "drive":
                drove = True
                vo = float(pk.get("visual_odometry") or 0.0)
                wo = float(pk.get("wheel_odometry") or cmd.get("metres", 0.0) or 0.0)
                ter0 = self.ter(self.x, self.y)
                self.ekf_drive(vo, math.radians(float(cmd["heading_deg"])))
                ter1 = pk.get("terrain")
                if wo > 0.3 and vo < 0.35 * wo:
                    stop = True
                if wo > 1e-6 and ter1 == ter0 and not stop:
                    self.slip_obs(ter0, 1.0 - vo / wo)
        if pos is not None:
            if k == 0 or not self.noisy:
                self.x, self.y = float(pos[0]), float(pos[1])
                for i in range(2):
                    for j in range(3):
                        self.P[i][j] = 0.0
                        self.P[j][i] = 0.0
            else:
                self.ekf_update(float(pos[0]), float(pos[1]))
        stop = stop and drove
        for cid, c in self.cmds.items():
            if c["status"] == "q":
                if c["exec"] <= k:
                    c["status"] = "cancel"
                elif stop and c["sent"] < k:
                    c["status"] = "cancel"
        st = pk.get("sampled_targets") or []
        for s in st:
            if isinstance(s, dict):
                s = s.get("id")
            if s is not None:
                self.sampled.add(s)
        for tid, et in list(self.pending.items()):
            if tid in self.sampled or et <= k:
                del self.pending[tid]
        if pk.get("battery") is not None:
            self.batt = float(pk["battery"])
        if pk.get("alive") is False:
            self.alive = False
        self.last_k = k

    # ---------- prediction ----------
    def predict(self, T):
        x, y, b = self.x, self.y, self.b
        P = [r[:] for r in self.P]
        batt = self.batt - self.idle * max(0, T - 1 - self.last_k)
        q = [c for c in self.cmds.values()
             if c["status"] == "q" and self.last_k < c["exec"] < T]
        q.sort(key=lambda c: c["exec"])
        for c in q:
            cmd = c["cmd"]
            if cmd.get("action") == "drive":
                h = math.radians(float(cmd["heading_deg"]))
                nx, ny, g, en, sd = self.sim(x, y, h + b, float(cmd["metres"]))
                P = self.prop(P, b, g, h, sd * sd + 1e-6)
                x, y = nx, ny
                batt -= en
            elif cmd.get("action") == "sample":
                batt -= self.scost
        return x, y, b, P, batt

    # ---------- planning ----------
    def plan(self, sx, sy, T, batt, targets):
        keys = [(sx, sy)] + [(float(g["x"]), float(g["y"])) for g in targets] + [self.base]
        nk = len(keys)
        nodes = keys + self.snodes
        N = len(nodes)
        smb = min(0.9, self.smean(self.dter)); sms = min(0.9, self.smean("sand"))
        mb = self.mult(self.dter); ms = self.mult("sand")
        cache = {}

        def edge(i, j):
            if i > j:
                i, j = j, i
            key = (i, j)
            if key in cache:
                return cache[key]
            ax, ay = nodes[i]; bx, by = nodes[j]
            L = math.hypot(bx - ax, by - ay)
            res = None
            ok = True
            for rc in self.haz:
                em = min(self.margin, max(0.0, _pdist(ax, ay, rc) - 0.05),
                         max(0.0, _pdist(bx, by, rc) - 0.05))
                iv = _clip(ax, ay, bx, by, (rc[0] - em, rc[1] - em, rc[2] + em, rc[3] + em))
                if iv is not None and (iv[1] - iv[0]) * L > 1e-6:
                    ok = False
                    break
            if ok:
                sl = 0.0
                for rc in self.sand:
                    iv = _clip(ax, ay, bx, by, rc)
                    if iv is not None:
                        sl += (iv[1] - iv[0]) * L
                sl = min(sl, L); bl = L - sl
                wb = bl / (1 - smb); ws = sl / (1 - sms)
                wheel = wb + ws
                en = self.dcost * (wb * mb + ws * ms)
                tk = int(math.ceil(wheel / self.maxm - 1e-6)) if L > 1e-6 else 0
                res = (en + 0.3 * tk, tk, en)
            cache[key] = res
            return res

        def dijk(src):
            dist = [float("inf")] * N
            prev = [-1] * N
            done = [False] * N
            dist[src] = 0.0
            for _ in range(N):
                u = -1; bd = float("inf")
                for v in range(N):
                    if not done[v] and dist[v] < bd:
                        bd = dist[v]; u = v
                if u < 0:
                    break
                done[u] = True
                for v in range(N):
                    if done[v]:
                        continue
                    ed = edge(u, v)
                    if ed is not None and dist[u] + ed[0] < dist[v]:
                        dist[v] = dist[u] + ed[0]
                        prev[v] = u
            return dist, prev

        legs = {}
        path0 = {}
        for src in range(nk - 1):
            dist, prev = dijk(src)
            for dst in range(1, nk):
                if dst == src or dist[dst] == float("inf"):
                    continue
                p = [dst]
                okp = True
                while p[-1] != src:
                    q = prev[p[-1]]
                    if q < 0:
                        okp = False
                        break
                    p.append(q)
                if not okp:
                    continue
                p.reverse()
                tk = 0; en = 0.0
                for a, c2 in zip(p, p[1:]):
                    ed = edge(a, c2)
                    tk += ed[1]; en += ed[2]
                legs[(src, dst)] = (tk, en)
                if src == 0:
                    path0[dst] = [nodes[i] for i in p]

        base_i = nk - 1
        info = {}
        for i, g in enumerate(targets):
            v = float(g.get("value", 1.0))
            lv = g.get("late_value")
            lv = float(lv) if lv is not None else v * self.late_frac
            dl = g.get("deadline_tick")
            ap = int(g.get("appear_tick", 0) or 0)
            info[i + 1] = (v, lv, dl, ap, g.get("id"))
        lastslot = self.maxt - (3 if self.noisy else 0)
        Eav = batt - self.idle * (self.maxt - T + 1) - self.reserve
        best = [-1e18, None]
        cnt = [0]

        def dfs(cur, t, e, val, seq, rem):
            cnt[0] += 1
            if cnt[0] > 40000:
                return
            lb = (0, 0.0) if cur == base_i else legs.get((cur, base_i))
            if lb is not None and t + lb[0] - 1 <= lastslot and e + lb[1] <= Eav:
                sc = val - 0.003 * (t + lb[0]) - 0.002 * (e + lb[1])
                if seq and info[seq[0]][4] == self.goal_id:
                    sc += 0.05
                if sc > best[0]:
                    best[0] = sc; best[1] = list(seq)
            ub = val + sum(info[j][0] for j in rem) + 0.06
            if ub <= best[0]:
                return
            for j in rem:
                lg = legs.get((cur, j))
                if lg is None:
                    continue
                v, lv, dl, ap, _ = info[j]
                arr = max(t + lg[0], ap)
                if arr > lastslot:
                    continue
                e2 = e + lg[1] + self.scost
                if e2 > Eav:
                    continue
                gain = v if (dl is None or arr <= dl) else lv
                seq.append(j)
                dfs(j, arr + 1, e2, val + gain, seq, [r for r in rem if r != j])
                seq.pop()

        dfs(0, T, 0.0, 0.0, [], list(range(1, nk - 1)))
        seq = best[1] or []
        if seq:
            gi = seq[0]
            return targets[gi - 1], path0.get(gi) or [keys[0], keys[gi]]
        return None, path0.get(base_i) or [keys[0], self.base]

    # ---------- decision ----------
    def decide(self, t):
        if not self.alive:
            return
        T = max(t + self.d + 1, self.last_exec + 1)
        if T != t + self.d + 1 or T > self.maxt:
            return
        x, y, b, P, batt = self.predict(T)
        M = self.tools.map() or {}
        targets = []
        for tg in M.get("targets") or []:
            tid = tg.get("id")
            if tid in self.sampled or tid in self.pending:
                continue
            if int(tg.get("appear_tick", 0) or 0) > self.maxt:
                continue
            targets.append(tg)
        if len(targets) > 8:
            targets.sort(key=lambda g: -float(g.get("value", 1)) / (1.0 + math.hypot(float(g["x"]) - x, float(g["y"]) - y)))
            targets = targets[:8]
        goal, path = self.plan(x, y, T, batt, targets)
        var = max(0.0, (P[0][0] + P[1][1]) / 2.0)
        idle_rest = self.idle * (self.maxt - T + 1)
        cmd = None
        gid = goal.get("id") if goal else None
        if gid != self.goal_id:
            self.waited = 0
        self.goal_id = gid
        if goal is not None:
            gx, gy = float(goal["x"]), float(goal["y"])
            dist = math.hypot(gx - x, gy - y)
            reff = self.trad - (0.05 if self.noisy else 0.02)
            ps = _psucc(dist, var, reff)
            dl = goal.get("deadline_tick")
            urgent = dl is not None and T >= int(dl) and ps >= 0.5
            if ps >= 0.85 or (self.waited >= 3 and ps >= 0.55) or urgent:
                if batt - self.scost - idle_rest >= 0.5:
                    cmd = {"action": "sample"}
            elif dist > 0.12:
                cmd = self.drive_cmd(x, y, b, path, batt, idle_rest)
            if cmd is None:
                self.waited += 1
            else:
                self.waited = 0
        else:
            dist = math.hypot(self.base[0] - x, self.base[1] - y)
            thr = 0.2 if self.noisy else 0.08
            if dist > thr:
                cmd = self.drive_cmd(x, y, b, path, batt, idle_rest)
        if cmd is None:
            return
        try:
            acks = self.tools.uplink([cmd])
        except Exception:
            return
        for a in acks or []:
            cid = a.get("command_id")
            et = int(a.get("execute_tick", T))
            self.cmds[cid] = {"cmd": dict(cmd), "exec": et, "sent": t, "status": "q"}
            self.last_exec = max(self.last_exec, et)
            if cmd["action"] == "sample" and gid is not None:
                self.pending[gid] = et

    def drive_cmd(self, x, y, b, path, batt, idle_rest):
        nxt = None
        if path:
            for i in range(1, len(path)):
                px, py = path[i]
                if i == len(path) - 1 or math.hypot(px - x, py - y) > 0.3:
                    nxt = (px, py)
                    break
        if nxt is None:
            return None
        D = math.hypot(nxt[0] - x, nxt[1] - y)
        if D < 0.02:
            return None
        phi = math.atan2(nxt[1] - y, nxt[0] - x)
        wheel = min(self.maxm, self.wheel_for(x, y, phi, D))
        wheel = round(wheel, 3)
        if wheel < 0.01:
            return None
        en = self.sim(x, y, phi, wheel)[3]
        if batt - en - idle_rest < 0.5:
            return None
        hd = math.degrees(phi - b) % 360.0
        return {"action": "drive", "heading_deg": round(hd, 3), "metres": wheel}

    # ---------- main loop ----------
    def run(self):
        try:
            self.ingest()
        except Exception:
            pass
        t = 0
        try:
            log = self.tools.telemetry_log() or []
            if log:
                t = max(int(p.get("received_tick", 0) or 0) for p in log)
        except Exception:
            t = 0
        guard = 0
        while guard < self.maxt + 30:
            guard += 1
            try:
                self.decide(t)
            except Exception:
                pass
            try:
                res = self.tools.advance(1)
            except Exception:
                return
            t = int(res.get("current_tick", t + 1))
            try:
                self.ingest()
            except Exception:
                pass
            if res.get("episode_complete"):
                return


def play(tools):
    try:
        pilot = _Pilot(tools)
    except Exception:
        return
    pilot.run()
```