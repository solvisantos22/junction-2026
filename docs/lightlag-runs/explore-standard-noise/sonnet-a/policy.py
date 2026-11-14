import math


def play(tools):
    rules = tools.rules()
    delay = rules["delay_ticks"]
    maxt = rules["max_ticks"]
    noisy = rules.get("sensing") is not None
    mults = rules["terrain_drive_multipliers"]
    ranges = rules["slip_ranges"]
    sample_cost = rules["sample_cost"]
    idle = rules["idle_cost"]
    m0 = tools.map()
    W, H = m0["width"], m0["height"]
    base = tuple(m0["base"])
    default_t = m0.get("default_terrain", "bedrock")
    sands = [(r["x1"], r["y1"], r["x2"], r["y2"]) for r in m0["sand"]]
    infl = [(r["x1"] - .8, r["y1"] - .8, r["x2"] + .8, r["y2"] + .8) for r in m0["hazards"]]
    corners = []
    for (a, b, c, d) in infl:
        for x, y in ((a - .25, b - .25), (a - .25, d + .25), (c + .25, b - .25), (c + .25, d + .25)):
            corners.append((min(max(x, .3), W - .3), min(max(y, .3), H - .3)))

    pk = {}
    done = set()
    pend = set()
    fails = {}
    sent = []
    obs = {}
    st = {"last_exec": -1, "goal": None}

    def terr(p):
        for (a, b, c, d) in sands:
            if a <= p[0] <= c and b <= p[1] <= d:
                return "sand"
        return default_t

    def slip(t):
        lo, hi = ranges.get(t, [0, 0])
        o = obs.get(t, [])
        v = ((lo + hi) / 2 + sum(o)) / (1 + len(o))
        return min(max(v, lo), hi)

    def sim(P, h, M):
        x, y = P
        r = math.radians(h)
        rem = M
        while rem > 1e-9:
            m = min(0.1, rem)
            rem -= m
            s = slip(terr((x, y)))
            x += m * (1 - s) * math.cos(r)
            y += m * (1 - s) * math.sin(r)
        return (min(max(x, 0), W), min(max(y, 0), H))

    def pcost(P, A):
        d = math.dist(P, A)
        if d < 1e-9:
            return 0.0, 0.0
        n = max(1, math.ceil(d / 0.1))
        step = d / n
        ux, uy = (A[0] - P[0]) / d, (A[1] - P[1]) / d
        wh = co = 0.0
        for i in range(n):
            pt = (P[0] + (i + .5) * step * ux, P[1] + (i + .5) * step * uy)
            t = terr(pt)
            w = step / (1 - slip(t))
            wh += w
            co += w * mults.get(t, 1.0)
        return wh, co

    def clear(a, b):
        d = math.dist(a, b)
        n = max(1, math.ceil(d / 0.2))
        for i in range(1, n + 1):
            x = a[0] + (b[0] - a[0]) * i / n
            y = a[1] + (b[1] - a[1]) * i / n
            for (p, q, r, s) in infl:
                if p <= x <= r and q <= y <= s:
                    return False
        return True

    def route(P, G):
        if clear(P, G):
            return [G]
        best = None
        for c in corners:
            if clear(P, c) and clear(c, G):
                L = math.dist(P, c) + math.dist(c, G)
                if best is None or L < best[0]:
                    best = (L, [c, G])
        if best:
            return best[1]
        for c in corners:
            if not clear(P, c):
                continue
            for c2 in corners:
                if c2 != c and clear(c, c2) and clear(c2, G):
                    L = math.dist(P, c) + math.dist(c, c2) + math.dist(c2, G)
                    if best is None or L < best[0]:
                        best = (L, [c, c2, G])
        if best:
            return best[1]
        return [G]

    def plen(P, pts):
        L = 0
        q = P
        for p in pts:
            L += math.dist(q, p)
            q = p
        return L

    def ingest(packets):
        for p in packets:
            t = p["tick"]
            pk[t] = p
            done.update(p.get("sampled_targets", []))
            evs = p.get("events", [])
            for e in evs:
                ty = str(e.get("type", "")).lower()
                if ty == "sample_failed":
                    for s in sent:
                        if s["exec"] == t and s["cmd"]["action"] == "sample" and s["tid"]:
                            pend.discard(s["tid"])
                            fails[s["tid"]] = fails.get(s["tid"], 0) + 1
                elif ("stop" in ty or "cancel" in ty or "hazard" in ty) and ty != "command_executed":
                    for s in sent:
                        if s["exec"] > t and s["sent"] <= t and not s["cancel"]:
                            s["cancel"] = True
                            if s["tid"]:
                                pend.discard(s["tid"])
            wo = p.get("wheel_odometry", 0)
            if t > 0 and wo and wo > 0.5:
                sl = 1 - p["visual_odometry"] / wo
                obs.setdefault(p.get("terrain", default_t), []).append(sl)

    def decide(now):
        if not pk:
            return
        T = max(pk)
        lp = pk[T]
        P = tuple(lp["position"])
        bat = lp["battery"]
        for s in sent:
            if s["exec"] > T and not s["cancel"]:
                c = s["cmd"]
                if c["action"] == "drive":
                    P = sim(P, c["heading_deg"], c["metres"])
                    bat -= pcost_cmd(s)
                elif c["action"] == "sample":
                    bat -= sample_cost
        if st["last_exec"] >= now + delay + 1:
            return
        tx = now + delay + 1
        if tx > maxt:
            return
        bat -= idle * max(0, tx - T)
        mp = tools.map()
        tg = {t["id"]: t for t in mp["targets"]}
        avail = [t for k, t in tg.items() if k not in done and k not in pend and fails.get(k, 0) < 3]
        margin = delay + 2

        def evaluate(t, P):
            G = (t["x"], t["y"])
            pts = route(P, G)
            L = plen(P, pts)
            n = math.ceil(L / 4.5) if L > 0.3 else 0
            stick = max(tx + n, t.get("appear_tick", 0))
            dl = t.get("deadline_tick")
            gain = t["value"] if (dl is None or stick <= dl) else t.get("late_value", 0)
            back = math.ceil(math.dist(G, base) / 4.5)
            if stick + 1 + back > maxt - 1 - margin:
                return None
            cost = sum(pcost(a, b)[1] for a, b in zip([P] + pts[:-1], pts)) * 1.1
            cost += sample_cost + math.dist(G, base) * 1.3 + idle * (maxt - tx) + 8
            if cost > bat:
                return None
            return gain / (n + 1.0)

        goal = st["goal"]
        if goal is not None:
            t = tg.get(goal)
            if t is None or goal in done or goal in pend or evaluate(t, P) is None:
                goal = None
        if goal is None:
            bs = None
            for t in avail:
                sc = evaluate(t, P)
                if sc is not None and (bs is None or sc > bs[0]):
                    bs = (sc, t["id"])
            goal = bs[1] if bs else None
        st["goal"] = goal
        if goal is not None:
            G = (tg[goal]["x"], tg[goal]["y"])
            tol = 0.3 if noisy else 0.2
        else:
            G = base
            tol = 0.45 if noisy else 0.15
        pts = route(P, G)
        while len(pts) > 1 and math.dist(P, pts[0]) < 0.3:
            pts.pop(0)
        A = pts[0]
        d = math.dist(P, A)
        cmd = None
        tid = None
        if len(pts) == 1 and d <= tol:
            if goal is not None:
                cmd = {"action": "sample"}
                tid = goal
            else:
                return
        else:
            wh, _ = pcost(P, A)
            M = min(5.0, max(wh, 0.05))
            h = math.degrees(math.atan2(A[1] - P[1], A[0] - P[0]))
            cmd = {"action": "drive", "heading_deg": h, "metres": M}
        try:
            acks = tools.uplink([cmd])
        except ValueError:
            return
        a = acks[0]
        st["last_exec"] = a["execute_tick"]
        sent.append({"exec": a["execute_tick"], "cmd": cmd, "tid": tid, "sent": now, "cancel": False,
                     "P": P})
        if tid:
            pend.add(tid)
            st["goal"] = None

    def pcost_cmd(s):
        c = s["cmd"]
        P = s.get("P")
        m = c["metres"]
        if P is None:
            return m
        return m * mults.get(terr(P), 1.0)

    ingest(tools.telemetry_log())
    now = 0
    while True:
        try:
            decide(now)
        except Exception:
            pass
        r = tools.advance(1)
        now = r["current_tick"]
        ingest(r["packets"])
        if r["episode_complete"]:
            return
