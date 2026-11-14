import math


def _rects(lst):
    out = []
    for r in lst or []:
        x1, x2 = sorted((float(r["x1"]), float(r["x2"])))
        y1, y2 = sorted((float(r["y1"]), float(r["y2"])))
        out.append((x1, y1, x2, y2))
    return out


def _inside(p, r, m):
    return r[0] - m <= p[0] <= r[2] + m and r[1] - m <= p[1] <= r[3] + m


def play(tools):
    rules = tools.rules()
    LAST = int(rules.get("max_ticks", 50)) - 1          # last executable tick (safe side)
    DELAY = int(rules.get("delay_ticks", 3))
    IDLE = float(rules.get("idle_cost", 0.5))
    SCOST = float(rules.get("sample_cost", 3.0))
    MAXM = float(rules.get("max_metres_per_drive", 5.0))
    mult = {"bedrock": 1.0, "sand": 2.0}
    mult.update(rules.get("terrain_drive_multipliers", {}))
    prior = {"bedrock": 0.025, "sand": 0.325}
    for k, v in rules.get("slip_ranges", {}).items():
        prior[k] = (float(v[0]) + float(v[1])) / 2.0

    mp = tools.map()
    base = (float(mp["base"][0]), float(mp["base"][1]))
    W = float(mp["width"])
    HH = float(mp["height"])
    sand = _rects(mp.get("sand", []))
    haz = _rects(mp.get("hazards", []))
    MARGIN = 1.0
    EDGE = 0.6
    GRID = [i * 0.5 for i in range(-24, 25)]

    recs = []     # drive records: e (exec tick), h (commanded heading), m (wheel metres), t (terrain)
    queue = []    # all queued actions: e (exec tick), cost (battery)
    attempts = {}
    st = {"done": False, "busy": 0}

    def terr_at(p):
        for r in sand:
            if _inside(p, r, 0.0):
                return "sand"
        return "bedrock"

    def free_pt(p, m):
        if not (EDGE <= p[0] <= W - EDGE and EDGE <= p[1] <= HH - EDGE):
            return False
        for r in haz:
            if _inside(p, r, m):
                return False
        return True

    def seg_ok(a, b):
        d = math.hypot(b[0] - a[0], b[1] - a[1])
        n = max(1, int(d / 0.1))
        for i in range(1, n + 1):
            f = i / n
            p = (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
            m = 0.3 if i == n else MARGIN
            if not free_pt(p, m):
                return False
        return True

    def cands():
        out = []
        for r in haz:
            g = MARGIN + 0.3
            out += [(r[0] - g, r[1] - g), (r[2] + g, r[1] - g),
                    (r[0] - g, r[3] + g), (r[2] + g, r[3] + g)]
        out += [(EDGE + 1, EDGE + 1), (W - EDGE - 1, EDGE + 1),
                (EDGE + 1, HH - EDGE - 1), (W - EDGE - 1, HH - EDGE - 1)]
        return [p for p in out if free_pt(p, MARGIN)]

    CANDS = cands()

    def dist(a, b):
        return math.hypot(b[0] - a[0], b[1] - a[1])

    def route(a, b):
        if seg_ok(a, b):
            return [a, b]
        best, bc = None, float("inf")
        for w in CANDS:
            if seg_ok(a, w) and seg_ok(w, b):
                c = dist(a, w) + dist(w, b)
                if c < bc:
                    best, bc = w, c
        if best is not None:
            return [a, best, b]
        best2, bc2 = None, float("inf")
        for w1 in CANDS:
            if not seg_ok(a, w1):
                continue
            for w2 in CANDS:
                if w2 == w1 or not seg_ok(w1, w2) or not seg_ok(w2, b):
                    continue
                c = dist(a, w1) + dist(w1, w2) + dist(w2, b)
                if c < bc2:
                    best2, bc2 = (w1, w2), c
        if best2 is not None:
            return [a, best2[0], best2[1], b]
        return None

    def pieces(path, th, slip):
        out = []
        for a, b in zip(path, path[1:]):
            d = dist(a, b)
            if d < 1e-6:
                continue
            brg = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
            n = max(1, int(math.ceil(d / 0.1)))
            step = d / n
            runs = []
            for i in range(n):
                f = (i + 0.5) * step / d
                mid = (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
                t = terr_at(mid)
                if runs and runs[-1][0] == t:
                    runs[-1][1] += step
                else:
                    runs.append([t, step])
            for t, length in runs:
                if length < 1e-3:
                    continue
                wheel = length / max(0.05, 1.0 - slip[t])
                k = max(1, int(math.ceil(wheel / MAXM - 1e-9)))
                for _ in range(k):
                    m = wheel / k
                    if m < 1e-3:
                        continue
                    out.append({"h": (brg - th) % 360.0, "m": m, "t": t})
        return out

    def simulate(rs, th, slip):
        x, y = base
        out = []
        for r in rs:
            s = slip[r["t"]]
            d = r["m"] * (1.0 - s)
            a = math.radians(r["h"] + th)
            x += d * math.cos(a)
            y += d * math.sin(a)
            out.append((r["e"], x, y))
        return out

    def estimate_slip(log):
        slip = {}
        for terr in ("bedrock", "sand"):
            Wsum = Vsum = 0.0
            for p in log:
                if p.get("tick", 0) >= 1 and p.get("terrain") == terr and p.get("wheel_odometry", 0) > 0:
                    Wsum += float(p["wheel_odometry"])
                    Vsum += float(p.get("visual_odometry", 0.0))
            ratio = (1.0 - Vsum / Wsum) if Wsum > 0 else prior[terr]
            est = (Wsum * ratio + prior[terr]) / (Wsum + 1.0)
            slip[terr] = min(0.9, max(0.0, est))
        return slip

    def fit_theta(log, slip):
        pk = [p for p in log if p.get("tick", 0) >= 1]
        if len(pk) < 2 or not recs:
            return 0.0
        best, bc = 0.0, float("inf")
        for th in GRID:
            traj = simulate(recs, th, slip)
            sse = 0.0
            for p in pk:
                px, py = base
                for e, x, y in traj:
                    if e <= p["tick"]:
                        px, py = x, y
                    else:
                        break
                zx, zy = p["position"]
                sse += (zx - px) ** 2 + (zy - py) ** 2
            cost = sse + 0.72 * (th / 6.0) ** 2
            if cost < bc:
                best, bc = th, cost
        return best

    def send(items):
        for i in range(0, len(items), 5):
            chunk = items[i:i + 5]
            tools.uplink([it[1] for it in chunk])
            for e, cmd, rec, cost in chunk:
                queue.append({"e": e, "cost": cost})
                st["busy"] = max(st["busy"], e)
                if rec is not None:
                    recs.append({"e": e, "h": rec["h"], "m": rec["m"], "t": rec["t"]})

    def plan(T):
        log = tools.telemetry_log()
        mpn = tools.map()
        slip = estimate_slip(log)
        th = fit_theta(log, slip)

        sampled = set()
        for p in log:
            for s in p.get("sampled_targets", []) or []:
                sampled.add(s.get("id") if isinstance(s, dict) else s)
        for c in mpn.get("targets", []):
            if c.get("sampled"):
                sampled.add(c["id"])

        if len([q for q in queue if q["e"] > T]) > 1:
            return

        last = max(log, key=lambda p: p["tick"])
        pt = last["tick"]
        bl = float(last.get("battery", 100.0))
        queued = sum(q["cost"] for q in queue if q["e"] > pt)
        remaining = bl - IDLE * (LAST - pt) - queued

        t0 = max(T + DELAY + 1, st["busy"] + 1)
        if recs:
            tr = simulate(recs, th, slip)
            pos_q = (tr[-1][1], tr[-1][2])
        else:
            pos_q = base

        best = None
        for c in mpn.get("targets", []):
            cid = c["id"]
            if cid in sampled or attempts.get(cid, 0) >= 2:
                continue
            appear = int(c.get("appear_tick", 0) or 0)
            if appear > LAST:
                continue
            cp = (float(c["x"]), float(c["y"]))
            r1 = route(pos_q, cp)
            if r1 is None:
                continue
            d1 = pieces(r1, th, slip)
            nd = len(d1)
            smp = max(t0 + nd, appear)
            r2 = route(cp, base)
            if r2 is None:
                continue
            d2 = pieces(r2, th, slip)
            nh = len(d2)
            if smp + nh > LAST:
                continue
            dl = c.get("deadline_tick")
            late = dl is not None and smp > dl
            lv = c.get("late_value", 0.0)
            val = (lv if late else c["value"]) or 0.0
            cost = sum(d["m"] * mult[d["t"]] for d in d1 + d2) + SCOST
            if remaining - cost < 2.0:
                continue
            span = smp - t0 + 1 + 0.5 * nh
            score = val / max(1.0, span)
            if best is None or score > best[0]:
                best = (score, cid, d1, smp, nd)

        if best is not None:
            _, cid, d1, smp, nd = best
            items = []
            for i, d in enumerate(d1):
                items.append((t0 + i,
                              {"action": "drive", "heading_deg": round(d["h"], 4),
                               "metres": round(d["m"], 5)},
                              d, d["m"] * mult[d["t"]]))
            for e in range(t0 + nd, smp):
                items.append((e, {"action": "wait"}, None, 0.0))
            items.append((smp, {"action": "sample"}, None, SCOST))
            attempts[cid] = attempts.get(cid, 0) + 1
            send(items)
            return

        # Nothing worth sampling: wait at the current spot while we can still get home,
        # then head home so the rover ends at base.
        r = route(pos_q, base)
        if r is None:
            st["done"] = True
            return
        dh = pieces(r, th, slip)
        nh = len(dh)
        if t0 + nh <= LAST:
            send([(t0, {"action": "wait"}, None, 0.0)])
        else:
            items = []
            for i, d in enumerate(dh):
                items.append((t0 + i,
                              {"action": "drive", "heading_deg": round(d["h"], 4),
                               "metres": round(d["m"], 5)},
                              d, d["m"] * mult[d["t"]]))
            if items and items[-1][0] <= LAST:
                send(items)
            st["done"] = True

    T = 0
    while True:
        try:
            if not st["done"]:
                plan(T)
        except Exception:
            st["done"] = True
        res = tools.advance(1)
        T = res["current_tick"]
        if res.get("episode_complete"):
            break
