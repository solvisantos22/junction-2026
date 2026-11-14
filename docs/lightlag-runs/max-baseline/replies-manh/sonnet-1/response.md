This is a complete module, but I have not run it or tested it against the simulator. Its safety-stop handling, in particular, rests on guesses about the packet format.

**Estimating the rover's position**
- Every decision, it replays all queued commands tick by tick through `lightlag_surface.drive`, using the midpoint slip bases.
- Noisy position fixes pull the estimate with a gain of 0.3. A fix that is more than 9 m off is treated as an outlier and barely moves it.
- It learns the heading bias from fix innovations.
- It learns the wheel scale from the ratio of visual odometry to the modelled ground distance.
- It reads `safety_stop` events from packets to work out which queued commands were cleared. If a stop packet is lost, it infers the stop when a drive that should have executed shows no `command_executed` event and zero wheel odometry.

**Planning**
- It builds a graph over the 5 m vertices with 16 neighbours per node. Edges are dropped if the slope exceeds 0.30 or the predicted slip would be near the 0.45 limit. Cost combines wheel metres and energy, with penalties for cross slopes, steep ground and crust regions.
- It runs Dijkstra from the predicted end-of-queue position and from the lander.
- It picks the target with the best value (full or late, by predicted arrival against the deadline) divided by travel cost. It requires enough time left to get back to the lander, plus a margin.
- Each drive is aimed at a waypoint, with the heading corrected for modelled side slip. The module queues a `sample` when the predicted position is within 1 m of the target.
- Eight commands go up at the start of each relay pass, as two uplinks. That keeps the rover busy until the next pass.
- Failed samples are retried up to three times.
- After a tilt or slip-limit stop it blocks the area ahead. After a slip-limit stop it also marks that cell as sand.
- If the last telemetry battery is below 35, it sends waits to recharge instead of driving.
- When no target is reachable in time, it heads back to the lander.

```python
import math
import heapq
import lightlag_surface as LS

NB = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1),
      (2, 1), (2, -1), (-2, 1), (-2, -1), (1, 2), (1, -2), (-1, 2), (-1, -2)]
INF = float("inf")


def play(tools):
    rules = tools.rules()
    mp = tools.map()
    phys = rules["physics"]
    cell = mp["cell_m"]
    surf = LS.Surface(cell, mp["elevation_cm"], mp["terrain"])
    nx, ny = surf.nx, surf.ny
    N = nx * ny
    TC = LS.TERRAIN_CODES
    bmid = {k: (v[0] + v[1]) / 2.0 for k, v in phys["slip_base_ranges"].items()}
    gtab = phys["slip_grade_gain"]
    ctab = phys["drive_cost_per_wheel_m"]
    stab = phys["side_slip_gain"]
    base = (mp["base"][0], mp["base"][1])
    maxT = rules["max_ticks"]
    vo_noise = rules["sensing"].get("visual_odometry_noise_by_terrain", {})
    SL = 0.30

    crustcells = set()
    for r in mp.get("crust_regions", []):
        for j in range(ny - 1):
            cy = (j + 0.5) * cell
            if not (r["y1"] <= cy <= r["y2"]):
                continue
            for i in range(nx - 1):
                cx = (i + 0.5) * cell
                if r["x1"] <= cx <= r["x2"] and surf.cell_max_slope(i, j) <= 0.1:
                    crustcells.add((i, j))

    def edge_cost(xa, ya, xb, yb):
        dx, dy = xb - xa, yb - ya
        L = math.hypot(dx, dy)
        ux, uy = dx / L, dy / L
        n = 5
        seg = L / n
        total = 0.0
        for k in range(n):
            t = (k + 0.5) / n
            x, y = xa + dx * t, ya + dy * t
            h, gx, gy, code = surf.sample(x, y)
            s = math.hypot(gx, gy)
            if s > SL:
                return None
            name = TC[code]
            grade = gx * ux + gy * uy
            cross = -gx * uy + gy * ux
            g = max(0.0, grade)
            gain_chk = 4.5 if name == "sand" else gtab[name]
            if bmid[name] + gain_chk * g + 0.06 > 0.45:
                return None
            sl = min(0.9, bmid[name] + gtab[name] * g)
            wheel = seg / (1.0 - sl)
            energy = wheel * ctab[name] + 2.0 * g * seg
            w = wheel / 4.5 + 0.08 * energy
            w *= (1 + 3 * abs(cross)) * (1 + 6 * max(0.0, s - 0.18))
            if code == "b":
                i, j, _, _ = surf.locate(x, y)
                if (i, j) in crustcells:
                    w *= 1.4
            total += w
        return total

    def build_adj():
        adj = [None] * N
        for j in range(ny):
            for i in range(nx):
                lst = []
                xa, ya = i * cell, j * cell
                for di, dj in NB:
                    i2, j2 = i + di, j + dj
                    if 0 <= i2 < nx and 0 <= j2 < ny:
                        c = edge_cost(xa, ya, i2 * cell, j2 * cell)
                        if c is not None:
                            lst.append((j2 * nx + i2, c))
                adj[j * nx + i] = lst
        return adj

    blocked = [False] * N

    def dijkstra(src, use_block=True):
        dist = [INF] * N
        par = [-1] * N
        dist[src] = 0.0
        hp = [(0.0, src)]
        while hp:
            d, n = heapq.heappop(hp)
            if d > dist[n]:
                continue
            for m, c in adj[n]:
                if use_block and blocked[m]:
                    continue
                nd = d + c
                if nd < dist[m]:
                    dist[m] = nd
                    par[m] = n
                    heapq.heappush(hp, (nd, m))
        return dist, par

    def node_of(x, y):
        i = min(nx - 1, max(0, int(round(x / cell))))
        j = min(ny - 1, max(0, int(round(y / cell))))
        return j * nx + i

    def block_near(x, y, rad):
        i0 = int((x - rad) / cell) - 1
        i1 = int((x + rad) / cell) + 2
        j0 = int((y - rad) / cell) - 1
        j1 = int((y + rad) / cell) + 2
        for j in range(max(0, j0), min(ny, j1)):
            for i in range(max(0, i0), min(nx, i1)):
                if math.hypot(i * cell - x, j * cell - y) <= rad:
                    blocked[j * nx + i] = True

    adj = build_adj()
    distB, _ = dijkstra(node_of(*base), False)

    sched = []

    def clampb(v, lo, hi):
        return lo if v < lo else hi if v > hi else v

    def estimate():
        log = tools.telemetry_log()
        pk = {}
        for p in log:
            pk[p["tick"]] = p
        ticks = sorted(pk)
        Tlast = ticks[-1]
        byexec = {e["exec"]: e for e in sched}
        cleared = set()
        stops = {}
        sampled = set()
        for t in ticks:
            p = pk[t]
            for s in p.get("sampled_targets", []) or []:
                sampled.add(s)
            evs = p.get("events", []) or []
            for ev in evs:
                if ev.get("type") == "safety_stop":
                    stops[t] = ev.get("reason")
                    for e in sched:
                        if e["tr"] <= t < e["exec"]:
                            cleared.add(e["id"])
            e = byexec.get(t)
            if e and e["id"] not in cleared and e["cmd"]["action"] == "drive" and t not in stops:
                ex = any(ev.get("type") == "command_executed" and ev.get("command_id") == e["id"] for ev in evs)
                if not ex and (p.get("wheel_odometry") or 0) == 0:
                    for e2 in sched:
                        if e2["tr"] <= t - 1 < e2["exec"]:
                            cleared.add(e2["id"])
        p0 = pk.get(0)
        E = [base[0], base[1]]
        if p0:
            E = [p0["position"][0], p0["position"][1]]
        b = 0.0
        wsum = 75.0
        rsum = 75.0
        F = 1.0
        Dx = Dy = 0.0
        live = [e["exec"] for e in sched if e["id"] not in cleared]
        tmax = max([Tlast] + live)
        stoplist = []
        for t in range(1, tmax + 1):
            e = byexec.get(t)
            hh = None
            p = pk.get(t)
            if e and e["id"] not in cleared and e["cmd"]["action"] == "drive":
                hh = e["h"]
                M = e["M"]
                if p and (p.get("wheel_odometry") or 0) >= M - 0.05 and (p.get("visual_odometry") or 0) > 0.3:
                    r1 = LS.drive(surf, phys, E[0], E[1], hh + b, M, bmid)
                    if r1["ground"] > 0.5:
                        ratio = p["visual_odometry"] / r1["ground"]
                        nz = vo_noise.get(p.get("terrain"), 0.05)
                        w = 1.0 / (nz + 0.06) ** 2
                        rsum += w * ratio
                        wsum += w
                        F = clampb(rsum / wsum, 0.8, 1.2)
                r = LS.drive(surf, phys, E[0], E[1], hh + b, M * F, bmid)
                Dx += r["x"] - E[0]
                Dy += r["y"] - E[1]
                E = [r["x"], r["y"]]
            if p:
                ix = p["position"][0] - E[0]
                iy = p["position"][1] - E[1]
                dn = math.hypot(ix, iy)
                if t in stops:
                    k = 0.6
                elif dn > 9:
                    k = 0.03
                else:
                    k = 0.3
                L = math.hypot(Dx, Dy)
                if L >= 4 and dn < 7 and t not in stops:
                    perp = (ix * (-Dy) + iy * Dx) / L
                    db = math.degrees(perp / L) * 0.3 * L * L / (L * L + 225.0)
                    b = clampb(b + db, -8.0, 8.0)
                    Dx = Dy = 0.0
                E[0] += k * ix
                E[1] += k * iy
                if t in stops:
                    h2 = (hh if hh is not None else 0.0) + b
                    stoplist.append((t, (E[0], E[1]), h2, stops[t]))
        bat = None
        for t in reversed(ticks):
            if "battery" in pk[t]:
                bat = pk[t]["battery"]
                break
        return {"P": (E[0], E[1]), "tmax": tmax, "Tlast": Tlast, "cleared": cleared,
                "stops": stoplist, "b": b, "F": F, "sampled": sampled, "bat": bat}

    attempts = {}
    pend = {}
    seen_stops = set()
    state = {"prev_goal": None}

    def decide(tick):
        nonlocal adj, distB
        est = estimate()
        dirty = False
        for (t, pos, hd, reason) in est["stops"]:
            if t in seen_stops:
                continue
            seen_stops.add(t)
            ux, uy = math.cos(math.radians(hd)), math.sin(math.radians(hd))
            block_near(pos[0] + 4 * ux, pos[1] + 4 * uy, 4.0)
            if reason == "slip_limit":
                cx, cy = pos[0] + 2.5 * ux, pos[1] + 2.5 * uy
                i, j, _, _ = surf.locate(cx, cy)
                row = surf.codes[j]
                surf.codes[j] = row[:i] + "s" + row[i + 1:]
                dirty = True
        if dirty:
            adj = build_adj()
            distB, _ = dijkstra(node_of(*base), False)
        sampled = est["sampled"]
        Tl = est["Tlast"]
        for tid, (ex, cid) in list(pend.items()):
            if tid in sampled:
                del pend[tid]
            elif Tl >= ex + 1:
                del pend[tid]
                if cid not in est["cleared"]:
                    attempts[tid] = attempts.get(tid, 0) + 1
        m = tools.map()
        targets = [t for t in m["targets"]]
        P = est["P"]
        b = est["b"]
        F = est["F"]
        last_exec = max([e["exec"] for e in sched] + [tick + 3])
        s0 = max(tick + 4, last_exec + 1)
        cmds = []
        meta = []
        if est["bat"] is not None and est["bat"] < 35:
            for _ in range(8):
                cmds.append({"action": "wait"})
                meta.append(None)
        else:
            pos = P
            taken = set()
            guard = 0
            while len(cmds) < 8 and guard < 14:
                guard += 1
                s = s0 + len(cmds)
                dist, par = dijkstra(node_of(*pos))
                best = None
                bs = -1.0
                for tg in targets:
                    tid = tg["id"]
                    if tid in sampled or tid in pend or tid in taken or attempts.get(tid, 0) >= 3:
                        continue
                    n = node_of(tg["x"], tg["y"])
                    d = dist[n]
                    if d == INF or distB[n] == INF:
                        continue
                    tarr = s + d + 1
                    if tarr + distB[n] * 1.25 + 12 > maxT:
                        continue
                    dl = tg.get("deadline_tick")
                    v = tg["value"] if (dl is None or tarr <= dl - 2) else tg.get("late_value", 0.0)
                    sc = v / (d + 4.0)
                    if state["prev_goal"] == tid:
                        sc *= 1.3
                    if sc > bs:
                        bs = sc
                        best = tg
                if best is not None:
                    gid = best["id"]
                    gxy = (best["x"], best["y"])
                else:
                    gid = None
                    gxy = base
                state["prev_goal"] = gid
                gn = node_of(*gxy)
                if dist[gn] == INF:
                    break
                path = []
                n = gn
                while n != -1:
                    path.append(n)
                    n = par[n]
                path.reverse()
                pts = [((n % nx) * cell, (n // nx) * cell) for n in path] + [gxy]
                ptr = 0
                restart = False
                done_goal = False
                while len(cmds) < 8:
                    dg = math.hypot(pos[0] - gxy[0], pos[1] - gxy[1])
                    if dg < (1.0 if gid else 1.5):
                        if gid:
                            cmds.append({"action": "sample"})
                            meta.append(gid)
                            taken.add(gid)
                            done_goal = True
                        else:
                            guard = 99
                        break
                    while ptr < len(pts) - 1:
                        a = pts[ptr]
                        c = pts[ptr + 1]
                        da = math.hypot(pos[0] - a[0], pos[1] - a[1])
                        if da < 2.5 or math.hypot(pos[0] - c[0], pos[1] - c[1]) < math.hypot(a[0] - c[0], a[1] - c[1]):
                            ptr += 1
                        else:
                            break
                    W = pts[ptr]
                    d = math.hypot(W[0] - pos[0], W[1] - pos[1])
                    if d < 0.3:
                        W = gxy
                        d = dg
                    th = math.degrees(math.atan2(W[1] - pos[1], W[0] - pos[0]))
                    h = th - b
                    r5 = LS.drive(surf, phys, pos[0], pos[1], h, 5.0 * F, bmid)
                    Mm = 5.0
                    if r5["ground"] > 0.5:
                        Mm = min(5.0, d * 5.0 / r5["ground"])
                    Mm = max(0.3, round(Mm, 3))
                    for _ in range(2):
                        r = LS.drive(surf, phys, pos[0], pos[1], h, Mm * F, bmid)
                        ex_, ey_ = r["x"] - pos[0], r["y"] - pos[1]
                        if math.hypot(ex_, ey_) > 0.05:
                            ang = math.degrees(math.atan2(W[1] - pos[1], W[0] - pos[0]) - math.atan2(ey_, ex_))
                            ang = (ang + 180) % 360 - 180
                            h += ang
                    h = round(h % 360.0, 2)
                    r = LS.drive(surf, phys, pos[0], pos[1], h, Mm * F, bmid)
                    if r["stop"]:
                        block_near(r["x"] + 2 * math.cos(math.radians(h + b)),
                                   r["y"] + 2 * math.sin(math.radians(h + b)), 4.0)
                        restart = True
                        break
                    cmds.append({"action": "drive", "heading_deg": h, "metres": Mm})
                    meta.append(None)
                    pos = (r["x"], r["y"])
                if guard >= 99:
                    break
                if restart:
                    continue
                if not done_goal and len(cmds) >= 8:
                    break
        if not cmds:
            return
        i = 0
        while i < len(cmds):
            chunk = cmds[i:i + 5]
            try:
                acks = tools.uplink(chunk)
            except ValueError:
                break
            for k, a in enumerate(acks):
                c = chunk[k]
                ent = {"id": a["command_id"], "exec": a["execute_tick"], "tr": a["transmit_tick"], "cmd": c,
                       "h": c.get("heading_deg", 0.0), "M": c.get("metres", 0.0)}
                sched.append(ent)
                tid = meta[i + k]
                if tid:
                    pend[tid] = (a["execute_tick"], a["command_id"])
            i += 5

    tick = 0
    while tick < maxT + 5:
        if tick % 8 == 0:
            try:
                decide(tick)
            except Exception:
                pass
        r = tools.advance(1)
        tick = r["current_tick"]
        if r["episode_complete"]:
            break
```