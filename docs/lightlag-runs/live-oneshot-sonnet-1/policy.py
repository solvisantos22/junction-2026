import math


def play(tools):
    rules = tools.rules()
    mp = tools.map()
    D = rules["delay_ticks"]
    maxt = rules["max_ticks"]
    last = maxt - 1
    W, H = mp["width"], mp["height"]
    base = tuple(mp["base"])
    hazards = mp["hazards"]
    sands = mp["sand"]
    idle = rules["idle_cost"]
    dcost = rules["drive_cost"]
    scost = rules["sample_cost"]
    sl = rules["slip_ranges"]
    slip_b = sum(sl["bedrock"]) / 2
    slip_s = sum(sl["sand"]) / 2
    smult = rules["terrain_drive_multipliers"]["sand"]
    MARGIN = 0.9

    cmds = []  # (exec_tick, cmd)
    st = {"pos": base, "tick": 0, "bat": rules["initial_battery"], "bat_tick": 0}
    sampled = set()
    pending = {}
    attempts = {}
    seen = [0]
    cur = [0]

    def in_rect(p, r, m=0.0):
        return r["x1"] - m <= p[0] <= r["x2"] + m and r["y1"] - m <= p[1] <= r["y2"] + m

    def on_sand(p):
        return any(in_rect(p, r) for r in sands)

    def slip_at(p):
        return slip_s if on_sand(p) else slip_b

    def clamp(p):
        return (min(max(p[0], 0.0), W), min(max(p[1], 0.0), H))

    def propagate(pos, t0, t1):
        for et, c in sorted(cmds, key=lambda x: x[0]):
            if t0 < et <= t1 and c["action"] == "drive":
                h = math.radians(c["heading_deg"])
                m = c["metres"] * (1 - slip_at(pos))
                pos = clamp((pos[0] + m * math.cos(h), pos[1] + m * math.sin(h)))
        return pos

    def process():
        log = tools.telemetry_log()
        while seen[0] < len(log):
            p = log[seen[0]]
            seen[0] += 1
            s = p["tick"]
            for t in p.get("sampled_targets", []):
                sampled.add(t)
            if s >= st["bat_tick"]:
                st["bat"] = p["battery"]
                st["bat_tick"] = s
            if s == 0:
                st["pos"] = tuple(p["position"])
                st["tick"] = 0
            elif s > st["tick"]:
                pred = propagate(st["pos"], st["tick"], s)
                m = p["position"]
                st["pos"] = clamp((pred[0] + 0.5 * (m[0] - pred[0]),
                                   pred[1] + 0.5 * (m[1] - pred[1])))
                st["tick"] = s
        latest = st["bat_tick"]
        for tid, et in list(pending.items()):
            if tid in sampled:
                del pending[tid]
            elif latest >= et:
                attempts[tid] = attempts.get(tid, 0) + 1
                del pending[tid]

    def blocked(a, b):
        n = max(2, int(math.dist(a, b) / 0.25))
        for i in range(n + 1):
            f = i / n
            p = (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
            for r in hazards:
                if in_rect(p, r, MARGIN):
                    return True
        return False

    def route(a, b):
        """return (first waypoint, total length)"""
        if not blocked(a, b):
            return b, math.dist(a, b)
        best = None
        for r in hazards:
            for cx in (r["x1"] - MARGIN - 0.1, r["x2"] + MARGIN + 0.1):
                for cy in (r["y1"] - MARGIN - 0.1, r["y2"] + MARGIN + 0.1):
                    c = clamp((cx, cy))
                    if blocked(a, c) or blocked(c, b):
                        continue
                    L = math.dist(a, c) + math.dist(c, b)
                    if best is None or L < best[1]:
                        best = (c, L)
        if best:
            return best
        return b, math.dist(a, b)

    def send(cl):
        try:
            acks = tools.uplink(cl)
        except ValueError:
            return False
        for a in acks:
            cmds.append((a["execute_tick"], a["command"]))
        return True

    def decide():
        Q = max([e for e, _ in cmds], default=-1)
        if Q >= cur[0] + D + 1:
            return
        nt = max(cur[0] + D + 1, Q + 1)
        if nt > last:
            return
        P = propagate(st["pos"], st["tick"], Q)
        sl_ = slip_at(P)
        bat = st["bat"]
        for et, c in cmds:
            if et > st["bat_tick"]:
                if c["action"] == "drive":
                    bat -= c["metres"] * dcost * (smult if on_sand(P) else 1)
                elif c["action"] == "sample":
                    bat -= scost
        bat -= idle * max(0, Q - st["bat_tick"])
        best = None
        for t in mp["targets"]:
            tid = t["id"]
            if tid in sampled or tid in pending or attempts.get(tid, 0) >= 3:
                continue
            T = (t["x"], t["y"])
            wp, L = route(P, T)
            dd = math.dist(P, T)
            steps = 0 if dd <= 0.4 else max(1, math.ceil(L / (5 * (1 - sl_))))
            stick = max(nt + steps, t.get("appear_tick", 0))
            homeL = math.dist(T, base)
            if stick + math.ceil(homeL / 4.5) + 1 > last:
                continue
            mult = smult if (on_sand(P) or on_sand(T)) else 1
            need = (L + homeL) / (1 - slip_s) * dcost * mult + scost + idle * (last - nt) + 5
            if need > bat:
                continue
            dl = t.get("deadline_tick")
            gain = t["value"] if (dl is None or stick <= dl) else t["late_value"]
            score = gain / (stick - nt + 1.5)
            if best is None or score > best[0]:
                best = (score, t, T, wp, dd, stick)
        if best:
            _, t, T, wp, dd, stick = best
            if dd <= 0.4:
                if stick > nt + 0 and t.get("appear_tick", 0) > nt:
                    send([{"action": "wait"}])
                elif send([{"action": "sample"}]):
                    pending[t["id"]] = nt
                return
            tgt = wp
        else:
            if math.dist(P, base) <= 0.35:
                return
            tgt, _ = route(P, base)
        dw = math.dist(P, tgt)
        M = min(5.0, dw / (1 - sl_))
        if M < 0.05:
            return
        hd = math.degrees(math.atan2(tgt[1] - P[1], tgt[0] - P[0]))
        send([{"action": "drive", "heading_deg": hd, "metres": M}])

    while True:
        process()
        try:
            decide()
        except Exception:
            pass
        r = tools.advance(1)
        cur[0] = r["current_tick"]
        if r["episode_complete"]:
            return
