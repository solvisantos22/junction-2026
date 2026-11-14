import math


def play(tools):
    rules = tools.rules()
    H = int(rules["max_ticks"])
    DELAY = int(rules["delay_ticks"])
    IDLE = float(rules["idle_cost"])
    DRIVE_C = float(rules["drive_cost"])
    SAMPLE_C = float(rules["sample_cost"])
    MULT = {k: float(v) for k, v in rules.get("terrain_drive_multipliers", {}).items()}
    SLIPR = rules.get("slip_ranges", {})
    PRIOR = {k: 0.5 * (float(v[0]) + float(v[1])) for k, v in SLIPR.items()}
    MAXCMD = int(rules.get("max_commands_per_uplink", 5))

    mp = tools.map()
    W = float(mp["width"])
    HT = float(mp["height"])
    bx, by = float(mp["base"][0]), float(mp["base"][1])
    dflt = mp.get("default_terrain", "bedrock")
    sand = mp.get("sand", []) or []
    hazards = mp.get("hazards", []) or []

    # ---------- geometry helpers ----------
    def dist(a, b):
        return math.hypot(a[0] - b[0], a[1] - b[1])

    def inrect(x, y, r, m=0.0):
        return (r["x1"] - m <= x <= r["x2"] + m) and (r["y1"] - m <= y <= r["y2"] + m)

    def terrain_at(x, y):
        for r in sand:
            if inrect(x, y, r):
                return "sand"
        return dflt

    def seg_ok(a, b):
        L = dist(a, b)
        n = max(2, int(L / 0.1))
        for i in range(n + 1):
            t = i / n
            x = a[0] + (b[0] - a[0]) * t
            y = a[1] + (b[1] - a[1]) * t
            if x < 0.2 or x > W - 0.2 or y < 0.2 or y > HT - 0.2:
                return False
            if 0 < i < n:
                for hz in hazards:
                    if inrect(x, y, hz, 0.9):
                        return False
        return True

    def route(a, b):
        if seg_ok(a, b):
            return [b]
        best = None
        bestlen = 1e18
        for hz in hazards:
            corners = ((hz["x1"], hz["y1"]), (hz["x1"], hz["y2"]),
                       (hz["x2"], hz["y1"]), (hz["x2"], hz["y2"]))
            for cx, cy in corners:
                for dx, dy in ((-2, -2), (-2, 2), (2, -2), (2, 2)):
                    w = (min(max(cx + dx, 0.5), W - 0.5), min(max(cy + dy, 0.5), HT - 0.5))
                    if not seg_ok(a, w) or not seg_ok(w, b):
                        continue
                    L = dist(a, w) + dist(w, b)
                    if L < bestlen:
                        bestlen = L
                        best = w
        if best is None:
            return None
        return [best, b]

    # ---------- state ----------
    cmds = {}          # command_id -> record
    sample_at = {}     # exec tick -> command_id
    fails = {}         # target id -> failed attempts
    sampled = set()
    fixes = {}         # tick -> (x, y)
    ratios = {}        # terrain -> list of (1 - visual/wheel)
    pk = [0, 100.0]    # latest packet tick, battery
    st = {"b": 0.0, "ret": False, "corr": 0}
    log_idx = [0]

    def slip_of(t):
        L = ratios.get(t, [])
        s = (sum(L) + 2.0 * PRIOR.get(t, 0.1)) / (len(L) + 2.0)
        return min(0.9, max(0.0, s))

    def ingest():
        log = tools.telemetry_log()
        for p in log[log_idx[0]:]:
            k = int(p["tick"])
            x, y = p["position"]
            if k not in fixes:
                fixes[k] = (float(x), float(y))
            if k >= pk[0]:
                pk[0] = k
                pk[1] = float(p["battery"])
            w = float(p.get("wheel_odometry") or 0.0)
            v = float(p.get("visual_odometry") or 0.0)
            if w > 0 and v > 0:
                ratios.setdefault(p.get("terrain", dflt), []).append(1.0 - v / w)
            for e in p.get("events", []) or []:
                et = str(e.get("type", ""))
                if et == "command_executed":
                    c = cmds.get(e.get("command_id"))
                    if c is not None:
                        c["confirmed"] = True
                elif "sample_failed" in et:
                    cid = sample_at.get(k)
                    if cid is not None:
                        tid = cmds[cid]["target"]
                        fails[tid] = fails.get(tid, 0) + 1
            for s in p.get("sampled_targets", []) or []:
                sid = s if isinstance(s, str) else s.get("id")
                if sid is not None:
                    sampled.add(sid)
        log_idx[0] = len(log)

    # ---------- dead reckoning ----------
    def vec(rec, b):
        s = slip_of(rec["terr"])
        d = rec["m"] * (1.0 - s)
        a = math.radians(rec["h"] + b)
        return d * math.cos(a), d * math.sin(a)

    def dr(recs, b, upto=None):
        x, y = bx, by
        for r in recs:
            if upto is not None and r["exec"] > upto:
                break
            vx, vy = vec(r, b)
            x += vx
            y += vy
        return x, y

    def fit_bias(conf):
        t0 = conf[0]["exec"]
        pts = [(k, fx, fy) for k, (fx, fy) in fixes.items() if k >= t0]
        if not pts:
            return st["b"]
        best = None
        for i in range(-30, 31):
            b = i * 0.5
            err = 0.0
            for k, fx, fy in pts:
                dx, dy = dr(conf, b, k)
                err += (fx - dx) ** 2 + (fy - dy) ** 2
            if best is None or err < best[0]:
                best = (err, b)
        return best[1]

    def norm_deg(h):
        while h > 180:
            h -= 360
        while h <= -180:
            h += 360
        return h

    def chunk(start, path, b):
        legs = []
        cur = start
        for p in path:
            L = dist(cur, p)
            if L < 0.12:
                cur = p
                continue
            ang = math.atan2(p[1] - cur[1], p[0] - cur[0])
            h = norm_deg(math.degrees(ang) - b)
            ux, uy = math.cos(ang), math.sin(ang)
            rem = L
            px, py = cur
            guard = 0
            while rem > 1e-6 and guard < 60:
                guard += 1
                terr = terrain_at(px, py)
                s = slip_of(terr)
                step = min(rem, min(4.0, 4.6 * (1.0 - s)))
                m = step / (1.0 - s)
                if m >= 0.02:
                    legs.append({"h": h, "m": m, "terr": terr})
                px += step * ux
                py += step * uy
                rem -= step
            cur = (px, py)
        return legs

    def send(cmdlist, recs):
        try:
            acks = tools.uplink(cmdlist)
        except Exception:
            return False
        for ack, rec in zip(acks, recs):
            cid = ack["command_id"]
            ex = int(ack["execute_tick"])
            r = dict(rec)
            r["exec"] = ex
            r["confirmed"] = False
            cmds[cid] = r
            if r["kind"] == "sample":
                sample_at[ex] = cid
        return True

    def send_legs(legs, tail_sample=None):
        cl = [{"action": "drive", "heading_deg": float(l["h"]), "metres": float(l["m"])} for l in legs]
        rc = [{"kind": "drive", "h": float(l["h"]), "m": float(l["m"]), "terr": l["terr"]} for l in legs]
        if tail_sample is not None:
            cl.append({"action": "sample"})
            rc.append({"kind": "sample", "target": tail_sample})
        if not cl or len(cl) > MAXCMD:
            return False
        return send(cl, rc)

    # ---------- planning ----------
    def plan(now):
        ingest()
        conf = sorted([r for r in cmds.values() if r["kind"] == "drive" and r["confirmed"]],
                      key=lambda r: r["exec"])
        alive = sorted([r for r in cmds.values() if r["kind"] == "drive" and
                        (r["confirmed"] or r["exec"] > now - DELAY)], key=lambda r: r["exec"])
        if conf and sum(r["m"] for r in conf) >= 1.0:
            st["b"] = fit_bias(conf)
        b = st["b"]

        last_exec = conf[-1]["exec"] if conf else 0
        dexec = dr(conf, b)
        post = [(fx, fy) for k, (fx, fy) in fixes.items() if k >= last_exec]
        ox, oy = 0.0, 0.0
        if post:
            n = len(post)
            w = n / (n + 1.0)
            ox = w * sum(fx - dexec[0] for fx, fy in post) / n
            oy = w * sum(fy - dexec[1] for fx, fy in post) / n
        est = (dexec[0] + ox, dexec[1] + oy)
        pa = dr(alive, b)
        S = (pa[0] + ox, pa[1] + oy)

        nf = max([c["exec"] for c in cmds.values()], default=0) + 1
        # wait for feedback of previous commands before planning anew
        if nf - 1 > now - DELAY:
            return

        # battery projection
        pk_t, pb = pk[0], pk[1]
        future = 0.0
        for c in cmds.values():
            if c["exec"] <= pk_t:
                continue
            if c["kind"] == "drive":
                if c["confirmed"] or c["exec"] > now - DELAY:
                    future += c["m"] * MULT.get(c["terr"], 1.0) * DRIVE_C
            else:
                future += SAMPLE_C
        bat = pb - IDLE * (H - pk_t) - future

        c0 = max(now + DELAY + 1, nf)
        tm = tools.map().get("targets", []) or []

        best = None
        for t in tm:
            tid = t["id"]
            if tid in sampled or fails.get(tid, 0) >= 2:
                continue
            if int(t.get("appear_tick", 0)) > c0:
                continue
            T = (float(t["x"]), float(t["y"]))
            path = route(S, T)
            if path is None:
                continue
            legs = chunk(S, path, b)
            ndr = len(legs)
            if ndr + 1 > MAXCMD:
                continue
            e = c0 + ndr
            if e > H - 1:
                continue
            dl = t.get("deadline_tick")
            if dl is None or e <= int(dl):
                val = float(t["value"])
            else:
                val = float(t.get("late_value", 0.0))
            rp = route(T, (bx, by))
            if rp is None:
                continue
            rl = chunk(T, rp, b)
            nret = len(rl)
            if e + nret > H - 1:
                continue
            cost = sum(l["m"] * MULT.get(l["terr"], 1.0) * DRIVE_C for l in legs)
            cost += SAMPLE_C
            cost += sum(l["m"] * 2.0 * DRIVE_C for l in rl)
            if bat - cost < 1.5:
                continue
            score = val / (ndr + 2.0)
            if best is None or score > best[0]:
                best = (score, tid, legs)

        if best is not None:
            if send_legs(best[2], tail_sample=best[1]):
                st["ret"] = False
            return

        if not st["ret"]:
            path = route(S, (bx, by))
            if path is None:
                path = [(bx, by)]
            legs = chunk(S, path, b)
            if not legs:
                st["ret"] = True
                return
            if len(legs) <= MAXCMD and c0 + len(legs) - 1 <= H - 1:
                if send_legs(legs):
                    st["ret"] = True
            else:
                st["ret"] = True
            return

        # final correction toward base using fresh feedback
        if st["corr"] < 4 and dist(est, (bx, by)) > 0.45 and c0 + 6 <= H - 1:
            path = route(est, (bx, by))
            if path is None:
                return
            legs = chunk(est, path, b)
            if legs and len(legs) <= MAXCMD and c0 + len(legs) - 1 <= H - 1:
                if send_legs(legs):
                    st["corr"] += 1

    # ---------- main loop ----------
    now = 0
    while True:
        try:
            plan(now)
        except Exception:
            pass
        r = tools.advance(1)
        now = int(r["current_tick"])
        if r.get("episode_complete") or now >= H:
            break
