import math
import heapq


def play(tools):
    rules = tools.rules()
    mp = tools.map()
    C = float(mp["cell_m"])
    E = mp["elevation_cm"]
    T = mp["terrain"]
    ny = len(E)
    nx = len(E[0])
    N = nx * ny
    W = (nx - 1) * C
    H = (ny - 1) * C
    h = [[v / 100.0 for v in row] for row in E]
    ph = rules["physics"]
    gain = dict(ph["slip_grade_gain"])
    gain["sand"] = 4.0
    dcost = ph["drive_cost_per_wheel_m"]
    side = ph["side_slip_gain"]
    bmid = {k: (v[0] + v[1]) / 2.0 + 0.03 for k, v in ph["slip_base_ranges"].items()}
    names = {"b": "bedrock", "r": "regolith", "s": "sand", "k": "rocks"}
    crust = mp.get("crust_regions", [])
    max_ticks = rules["max_ticks"]
    base = (float(mp["base"][0]), float(mp["base"][1]))
    INF = float("inf")

    def sample(x, y):
        fx, fy = x / C, y / C
        i = min(nx - 2, max(0, int(fx)))
        j = min(ny - 2, max(0, int(fy)))
        tx, ty = fx - i, fy - j
        lo, hi = h[j], h[j + 1]
        h00, h10, h01, h11 = lo[i], lo[i + 1], hi[i], hi[i + 1]
        gx = ((h10 - h00) * (1 - ty) + (h11 - h01) * ty) / C
        gy = ((h01 - h00) * (1 - tx) + (h11 - h10) * tx) / C
        return gx, gy, T[j][i]

    def in_crust(x, y):
        for r in crust:
            if r["x1"] <= x <= r["x2"] and r["y1"] <= y <= r["y2"]:
                return True
        return False

    dirs = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]

    def build_edge(i, j, di, dj):
        x0, y0 = i * C, j * C
        dx, dy = di * C, dj * C
        L = math.hypot(dx, dy)
        ux, uy = dx / L, dy / L
        ws = 0.0
        wsl = 0.0
        f2 = 0.0
        cnt = 0
        for t in (0.15, 0.5, 0.85):
            for off in (-0.03 * C, 0.03 * C):
                px = min(W, max(0.0, x0 + dx * t - uy * off))
                py = min(H, max(0.0, y0 + dy * t + ux * off))
                gx, gy, code = sample(px, py)
                name = names.get(code, "regolith")
                slope = math.hypot(gx, gy)
                grade = gx * ux + gy * uy
                cross = -gx * uy + gy * ux
                slip = bmid[name] + gain[name] * max(0.0, grade)
                wsl = max(wsl, slope)
                ws = max(ws, slip)
                f = 1.0 / (1.0 - min(slip, 0.9))
                f *= (1.0 + 2.0 * abs(cross))
                if in_crust(px, py):
                    f *= 1.2
                f2 += f * (1.0 + 0.8 * dcost[name])
                cnt += 1
        if wsl > 0.34 or ws > 0.42:
            return None
        climb = max(0.0, h[j + dj][i + di] - h[j][i])
        return L * f2 / cnt * (1.0 + 30.0 * max(0.0, wsl - 0.2) ** 2) + 1.6 * climb

    adj = [None] * N
    for j in range(ny):
        for i in range(nx):
            lst = []
            for di, dj in dirs:
                a, b = i + di, j + dj
                if 0 <= a < nx and 0 <= b < ny:
                    c = build_edge(i, j, di, dj)
                    if c is not None:
                        lst.append((b * nx + a, c))
            adj[j * nx + i] = lst

    def sources(x, y):
        i0 = min(nx - 2, max(0, int(x / C)))
        j0 = min(ny - 2, max(0, int(y / C)))
        out = []
        for di, dj in ((0, 0), (1, 0), (0, 1), (1, 1)):
            a, b = i0 + di, j0 + dj
            out.append((b * nx + a, math.hypot(a * C - x, b * C - y) * 1.3))
        return out

    def dijkstra(srcs, pen):
        dist = [INF] * N
        par = [-1] * N
        pq = []
        for n, c in srcs:
            if c < dist[n]:
                dist[n] = c
                heapq.heappush(pq, (c, n))
        while pq:
            d, n = heapq.heappop(pq)
            if d > dist[n]:
                continue
            pn = pen[n]
            for m, c in adj[n]:
                nd = d + c * (pn + pen[m]) * 0.5
                if nd < dist[m]:
                    dist[m] = nd
                    par[m] = n
                    heapq.heappush(pq, (nd, m))
        return dist, par

    pen = [1.0] * N
    bdist, _ = dijkstra(sources(base[0], base[1]), [1.0] * N)

    def cost_at(dist, x, y):
        i0 = min(nx - 2, max(0, int(x / C)))
        j0 = min(ny - 2, max(0, int(y / C)))
        best, bn = INF, -1
        for di, dj in ((0, 0), (1, 0), (0, 1), (1, 1)):
            a, b = i0 + di, j0 + dj
            n = b * nx + a
            c = dist[n] + math.hypot(a * C - x, b * C - y) * 1.3
            if c < best:
                best, bn = c, n
        return best, bn

    # ---------------- state ----------------
    st = {"cur": 0, "done": False, "seen": 0, "battery": 100.0, "btick": -1}
    pkts = {}
    sampled = set()
    stops = []

    def ingest():
        log = tools.telemetry_log()
        for p in log[st["seen"]:]:
            pkts[p["tick"]] = p
            for s in p.get("sampled_targets", []) or []:
                sampled.add(s.get("id") if isinstance(s, dict) else str(s))
            for ev in p.get("events", []) or []:
                if isinstance(ev, dict) and ev.get("type") == "safety_stop":
                    stops.append((p["tick"], ev.get("reason")))
            if p["tick"] >= st["btick"]:
                st["btick"] = p["tick"]
                st["battery"] = p.get("battery", st["battery"])
        st["seen"] = len(log)

    def step(n=1):
        if st["done"]:
            return
        r = tools.advance(n)
        st["cur"] = r["current_tick"]
        if r.get("episode_complete") or st["cur"] >= max_ticks:
            st["done"] = True
        ingest()

    def robust(ps):
        xs = sorted(p[0] for p in ps)
        ys = sorted(p[1] for p in ps)
        mx = xs[len(xs) // 2]
        my = ys[len(ys) // 2]
        keep = [p for p in ps if abs(p[0] - mx) <= 5 and abs(p[1] - my) <= 5] or ps
        return (min(W, max(0.0, sum(p[0] for p in keep) / len(keep))),
                min(H, max(0.0, sum(p[1] for p in keep) / len(keep))))

    ingest()
    est = base
    pred = None
    plan = None
    last_exec = -1
    first = True
    commit = None
    attempts = {}
    black = set()
    cyc = {}
    eff = 0.82
    bias = 0.0
    rate = 0.4

    def send(cmds):
        nonlocal last_exec
        for k in range(0, len(cmds), 5):
            acks = tools.uplink(cmds[k:k + 5])
            for a in acks:
                last_exec = max(last_exec, a["execute_tick"])

    try:
        while not st["done"]:
            if not first:
                while not st["done"]:
                    good = [t for t in pkts if t > last_exec]
                    if len(good) >= 4 or st["cur"] > last_exec + 25:
                        break
                    step()
                if st["done"]:
                    break
                good = sorted(t for t in pkts if t > last_exec)[-10:]
                gps = [pkts[t]["position"] for t in good]
                if gps:
                    est = robust(gps)
                elif pred:
                    est = pred
                if plan and plan["moving"]:
                    stopped = [s for s in stops if s[0] > plan["sent"]]
                    if stopped:
                        for j in range(ny):
                            for i in range(nx):
                                if math.hypot(i * C - est[0], j * C - est[1]) < 7.5:
                                    n = j * nx + i
                                    pen[n] = min(40.0, pen[n] * 2.5)
                    elif len(gps) >= 3:
                        st0 = plan["start"]
                        pn = plan["end"]
                        chx, chy = pn[0] - st0[0], pn[1] - st0[1]
                        dx, dy = est[0] - st0[0], est[1] - st0[1]
                        cl = math.hypot(chx, chy)
                        dl = math.hypot(dx, dy)
                        if cl > 12:
                            ratio = min(1.4, max(0.6, dl / cl))
                            eff = min(1.0, max(0.5, eff * (0.6 + 0.4 * ratio)))
                            ang = math.degrees(math.atan2(chx * dy - chy * dx, chx * dx + chy * dy))
                            ang = max(-15.0, min(15.0, ang))
                            bias = max(-7.0, min(7.0, bias + 0.3 * ang))
                elif plan and plan.get("sample"):
                    tid = plan["tid"]
                    if tid in sampled:
                        commit = None
                    elif attempts.get(tid, 0) >= 3:
                        black.add(tid)
                        commit = None
                plan = None
            first = False
            if st["done"]:
                break
            cur = st["cur"]
            if st["battery"] < 18.0:
                step(3)
                continue
            m2 = tools.map()
            targets = [t for t in m2["targets"] if t["id"] not in sampled and t["id"] not in black]
            tmap = {t["id"]: t for t in targets}
            dist, par = dijkstra(sources(est[0], est[1]), pen)

            def evaluate(t):
                c, bn = cost_at(dist, t["x"], t["y"])
                if c == INF:
                    return None
                tk = rate * c + 18.0
                bc, _ = cost_at(bdist, t["x"], t["y"])
                if bc == INF:
                    return None
                back = rate * bc
                if cur + tk + back + 20.0 > max_ticks:
                    return None
                dl = t.get("deadline_tick")
                v = t["value"] if (dl is None or cur + 4 + tk <= dl) else t.get("late_value", t["value"])
                return (v / (tk + 0.1 * back), bn, c)

            goal = None
            bn = -1
            if commit is not None and commit in tmap:
                cyc[commit] = cyc.get(commit, 0) + 1
                if cyc[commit] > 16 or attempts.get(commit, 0) >= 3:
                    black.add(commit)
                    commit = None
                else:
                    ev = evaluate(tmap[commit])
                    if ev is None:
                        commit = None
                    else:
                        bn = ev[1]
            else:
                commit = None
            if commit is None:
                best = None
                for t in targets:
                    ev = evaluate(t)
                    if ev is None:
                        continue
                    if best is None or ev[0] > best[0]:
                        best = (ev[0], t["id"], ev[1])
                if best is not None:
                    commit = best[1]
                    bn = best[2]
            if commit is not None:
                t = tmap[commit]
                goal = (t["x"], t["y"])
            else:
                goal = base
                c, bn = cost_at(dist, base[0], base[1])
            d_direct = math.hypot(goal[0] - est[0], goal[1] - est[1])
            if commit is not None and d_direct <= 1.7:
                attempts[commit] = attempts.get(commit, 0) + 1
                send([{"action": "sample"}])
                plan = {"moving": False, "sample": True, "tid": commit, "sent": cur}
                pred = est
                continue
            if commit is None and d_direct <= 2.2:
                step(2)
                continue
            if cur + 5 > max_ticks:
                step(2)
                continue
            if bn < 0 or dist[bn] == INF:
                step(2)
                continue
            if d_direct <= 6.0:
                poly = [est, goal]
            else:
                nodes = []
                n = bn
                while n != -1:
                    nodes.append(n)
                    n = par[n]
                nodes.reverse()
                poly = [est] + [((n % nx) * C, (n // nx) * C) for n in nodes] + [goal]

                def dd(a, b):
                    return math.hypot(a[0] - b[0], a[1] - b[1])
                while len(poly) >= 3 and dd(poly[0], poly[2]) < dd(poly[1], poly[2]):
                    del poly[1]
                while len(poly) >= 3 and dd(poly[-1], poly[-3]) < dd(poly[-2], poly[-3]):
                    del poly[-2]
            cum = [0.0]
            for a, b in zip(poly, poly[1:]):
                cum.append(cum[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
            Lg = cum[-1]

            def point_at(s):
                if s >= cum[-1]:
                    return poly[-1]
                for k in range(1, len(cum)):
                    if s <= cum[k]:
                        seg = cum[k] - cum[k - 1]
                        f = (s - cum[k - 1]) / seg if seg > 1e-9 else 0.0
                        a, b = poly[k - 1], poly[k]
                        return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
                return poly[-1]

            legcap = 10 if st["battery"] >= 35.0 else 5
            cap = legcap * 5.0 * eff
            if Lg > cap + 8.0:
                D = cap
            elif Lg > 8.0:
                D = Lg * 0.95
            else:
                D = Lg
            D = max(D, 0.3)
            n = max(1, int(math.ceil(D / (5.0 * eff))))
            stp = D / n
            pts = [poly[0]] + [point_at(stp * k) for k in range(1, n + 1)]
            cmds = []
            for k in range(1, n + 1):
                dx = pts[k][0] - pts[k - 1][0]
                dy = pts[k][1] - pts[k - 1][1]
                hd = (math.degrees(math.atan2(dy, dx)) - bias) % 360.0
                M = min(5.0, max(0.1, stp / eff))
                cmds.append({"action": "drive", "heading_deg": round(hd, 2), "metres": round(M, 3)})
            send(cmds)
            plan = {"moving": True, "sample": False, "sent": cur, "start": est, "end": pts[-1]}
            pred = pts[-1]
    except Exception:
        pass
    guard = 0
    while not st["done"] and guard < 1000:
        guard += 1
        try:
            step(5)
        except Exception:
            break
