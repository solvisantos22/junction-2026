import math


def play(tools):
    rules = tools.rules()
    T = int(rules["max_ticks"])
    D = int(rules["delay_ticks"])
    sens = rules.get("sensing", {})
    R_POS = float(sens.get("position_noise_m", 0.6)) ** 2
    slip_ranges = rules.get("slip_ranges", {})

    mp0 = tools.map()
    W = float(mp0["width"])
    HH = float(mp0["height"])
    BASE = (float(mp0["base"][0]), float(mp0["base"][1]))
    DEF_T = mp0.get("default_terrain", "bedrock")
    SAND = list(mp0.get("sand", []))

    EDGE = 1.0      # keep this far from map edges
    HZ_M = 0.9      # clearance from hazard rectangles
    NEAR = 0.5      # ignore obstacle checks this close to segment start

    # Slip model: prior (midpoint of published range) with one pseudo-observation.
    slip_sum = {}
    slip_n = {}
    for name, rng in slip_ranges.items():
        slip_sum[name] = (float(rng[0]) + float(rng[1])) / 2.0
        slip_n[name] = 1
    slip_sum.setdefault("bedrock", 0.025)
    slip_n.setdefault("bedrock", 1)
    slip_sum.setdefault("sand", 0.325)
    slip_n.setdefault("sand", 1)

    S = {
        "est": [BASE[0], BASE[1]],
        "P": 0.0,
        "sampled": set(),
        "seen": set(),
        "fails": {},
        "pending": None,
    }

    # ---------- geometry helpers ----------
    def inrect(x, y, r, m=0.0):
        return (r["x1"] - m <= x <= r["x2"] + m) and (r["y1"] - m <= y <= r["y2"] + m)

    def terrain_at(x, y):
        for r in SAND:
            if inrect(x, y, r):
                return "sand"
        return DEF_T

    def slip(terr):
        key = terr if terr in slip_sum else "bedrock"
        return min(0.9, max(0.0, slip_sum[key] / slip_n[key]))

    def seg_clear(p, q, hz):
        L = math.dist(p, q)
        n = max(2, int(L / 0.2))
        for i in range(n + 1):
            t = i / n
            x = p[0] + (q[0] - p[0]) * t
            y = p[1] + (q[1] - p[1]) * t
            if math.dist((x, y), p) < NEAR:
                continue
            if x < EDGE or x > W - EDGE or y < EDGE or y > HH - EDGE:
                return False
            for r in hz:
                if inrect(x, y, r, HZ_M):
                    return False
        return True

    def cand_points(hz):
        pts = []
        for r in hz:
            for x in (r["x1"] - 1.3, r["x2"] + 1.3):
                for y in (r["y1"] - 1.3, r["y2"] + 1.3):
                    pts.append((x, y))
        pts += [(2.0, 2.0), (W - 2.0, 2.0), (2.0, HH - 2.0), (W - 2.0, HH - 2.0)]
        out = []
        for (x, y) in pts:
            if not (EDGE + 0.5 <= x <= W - EDGE - 0.5 and EDGE + 0.5 <= y <= HH - EDGE - 0.5):
                continue
            if any(inrect(x, y, r, HZ_M) for r in hz):
                continue
            out.append((x, y))
        return out

    def plan_path(p, g, hz):
        if seg_clear(p, g, hz):
            return [g]
        cands = cand_points(hz)
        best = None
        for w in cands:
            if seg_clear(p, w, hz) and seg_clear(w, g, hz):
                L = math.dist(p, w) + math.dist(w, g)
                if best is None or L < best[0]:
                    best = (L, [w, g])
        if best:
            return best[1]
        for i, a in enumerate(cands):
            if not seg_clear(p, a, hz):
                continue
            for j, b in enumerate(cands):
                if i == j:
                    continue
                if seg_clear(a, b, hz) and seg_clear(b, g, hz):
                    L = math.dist(p, a) + math.dist(a, b) + math.dist(b, g)
                    if best is None or L < best[0]:
                        best = (L, [a, b, g])
        return best[1] if best else None

    def drive_plan(p, path):
        cmds = []
        vec = [0.0, 0.0]
        chunks = []
        cp = p
        for q in path:
            dd = math.dist(cp, q)
            if dd < 0.05:
                cp = q
                continue
            ang = math.atan2(q[1] - cp[1], q[0] - cp[0])
            hdg = math.degrees(ang) % 360.0
            mid = ((cp[0] + q[0]) / 2.0, (cp[1] + q[1]) / 2.0)
            s = slip(terrain_at(mid[0], mid[1]))
            Mt = dd / (1.0 - s)
            n = max(1, math.ceil(Mt / 5.0 - 1e-9))
            me = Mt / n
            for _ in range(n):
                cmds.append({"action": "drive", "heading_deg": round(hdg, 2),
                             "metres": round(me, 4)})
                dt = me * (1.0 - s)
                chunks.append(dt)
                vec[0] += dt * math.cos(ang)
                vec[1] += dt * math.sin(ang)
            cp = q
        return cmds, vec, chunks

    # ---------- telemetry ingestion ----------
    def ingest(cur):
        log = tools.telemetry_log()
        for p in log:
            tk = p["tick"]
            if tk in S["seen"]:
                continue
            S["seen"].add(tk)
            w = float(p.get("wheel_odometry", 0) or 0)
            v = float(p.get("visual_odometry", 0) or 0)
            if w > 0 and v > 0:
                obs = min(0.9, max(0.0, 1.0 - v / w))
                key = p.get("terrain", DEF_T)
                key = key if key in slip_sum else "bedrock"
                slip_sum[key] += obs
                slip_n[key] += 1
            for sid in p.get("sampled_targets", []) or []:
                if isinstance(sid, dict):
                    sid = sid.get("id")
                S["sampled"].add(sid)

        pend = S["pending"]
        if pend is not None and cur >= pend["E"] + D:
            pts = [(float(p["position"][0]), float(p["position"][1]))
                   for p in log
                   if p["tick"] >= pend["E"] and p.get("received_tick", p["tick"] + D) <= cur]
            pred = pend["pred"]
            P_pred = pend["P"]
            if pts:
                k = len(pts)
                zx = sum(q[0] for q in pts) / k
                zy = sum(q[1] for q in pts) / k
                Rk = R_POS / k
                K = P_pred / (P_pred + Rk) if (P_pred + Rk) > 0 else 1.0
                nx = pred[0] + K * (zx - pred[0])
                ny = pred[1] + K * (zy - pred[1])
                nx = min(W, max(0.0, nx))
                ny = min(HH, max(0.0, ny))
                S["est"] = [nx, ny]
                S["P"] = (1.0 - K) * P_pred
            else:
                S["est"] = [pred[0], pred[1]]
                S["P"] = P_pred
            tid = pend.get("tid")
            if tid is not None and tid not in S["sampled"]:
                S["fails"][tid] = S["fails"].get(tid, 0) + 1
            S["pending"] = None

    # ---------- planning ----------
    def plan(cur):
        est = tuple(S["est"])
        mp = tools.map()
        hz = mp.get("hazards", [])
        targets = mp.get("targets", [])
        fails = S["fails"]
        best = None
        for t in targets:
            tid = t["id"]
            if tid in S["sampled"] or fails.get(tid, 0) >= 3:
                continue
            tp = (float(t["x"]), float(t["y"]))
            appear = int(t.get("appear_tick", 0) or 0)
            dl = t.get("deadline_tick")
            late = float(t.get("late_value", 0) or 0)
            val = float(t.get("value", 0) or 0)
            d = math.dist(est, tp)
            k = fails.get(tid, 0)
            if d < 0.35 and k > 0:
                # Previous sample missed: small lateral nudge, then sample again.
                hj = math.degrees(math.atan2(tp[1] - est[1], tp[0] - est[0]))
                hj += 90.0 if k % 2 == 1 else -90.0
                hj %= 360.0
                s = slip(terrain_at(est[0], est[1]))
                me = 0.7 / (1.0 - s)
                cmds = [{"action": "drive", "heading_deg": round(hj, 2),
                         "metres": round(me, 4)}]
                ang = math.radians(hj)
                dt = me * (1.0 - s)
                vec = [dt * math.cos(ang), dt * math.sin(ang)]
                chunks = [dt]
            else:
                path = plan_path(est, tp, hz)
                if path is None:
                    continue
                cmds, vec, chunks = drive_plan(est, path)
            n = len(cmds)
            if n > 4:
                continue
            Es = cur + D + n + 1
            if Es > T - 1:
                continue
            if appear > Es:
                continue
            db = math.dist(tp, BASE)
            nr = max(1, math.ceil(db / 4.5))
            if Es + 3 * D + 2 * nr + 2 > T - 1:
                continue
            veff = val if (dl is None or Es <= int(dl)) else late
            if veff <= 0:
                continue
            cyc = (n + 1) + 2 * D
            score = veff / (cyc + 0.05 * d)
            if best is None or score > best[0]:
                best = (score, cmds + [{"action": "sample"}], vec, chunks, tid)
        if best is not None:
            return best[1], best[2], best[3], best[4]

        # No worthwhile target: head home if not already there.
        if math.dist(est, BASE) < 0.5:
            return None
        path = plan_path(est, BASE, hz)
        if path is None:
            return None
        cmds, vec, chunks = drive_plan(est, path)
        n = len(cmds)
        if n == 0 or n > 5 or cur + D + n > T - 1:
            return None
        return cmds, vec, chunks, None

    # ---------- main loop ----------
    cur = 0
    done = False
    while not done and cur < T:
        pend = S["pending"]
        if pend is not None:
            need = pend["E"] + D
            if cur < need:
                res = tools.advance(max(1, min(5, need - cur)))
                cur = int(res["current_tick"])
                done = bool(res.get("episode_complete", False))
                ingest(cur)
                continue
            ingest(cur)

        pl = plan(cur)
        if pl is None:
            res = tools.advance(1)
            cur = int(res["current_tick"])
            done = bool(res.get("episode_complete", False))
            ingest(cur)
            continue

        cmds, vec, chunks, tid = pl
        try:
            acks = tools.uplink(cmds)
        except ValueError:
            res = tools.advance(1)
            cur = int(res["current_tick"])
            done = bool(res.get("episode_complete", False))
            ingest(cur)
            continue

        E = int(acks[-1]["execute_tick"])
        est = S["est"]
        pred = [est[0] + vec[0], est[1] + vec[1]]
        Q = sum((0.15 * c) ** 2 + 0.02 for c in chunks)
        S["pending"] = {"E": E, "pred": pred, "P": S["P"] + Q, "tid": tid}
        # Estimate is refreshed when the fix for tick E arrives.
