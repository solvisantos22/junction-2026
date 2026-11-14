```python
import math


def play(tools):
    rules = tools.rules()
    DELAY = int(rules.get("delay_ticks", 0))
    MAXT = int(rules.get("max_ticks", 50))
    IDLE = float(rules.get("idle_cost", 0.5))
    DC = float(rules.get("drive_cost", 1.0))
    SC = float(rules.get("sample_cost", 3.0))
    MAXM = min(5.0, float(rules.get("max_metres_per_drive", 5.0)))
    MAXC = max(1, min(5, int(rules.get("max_commands_per_uplink", 5))))
    TMULT = rules.get("terrain_drive_multipliers", {"bedrock": 1.0, "sand": 2.0})
    SR = rules.get("slip_ranges", {"bedrock": [0.0, 0.05], "sand": [0.2, 0.45]})
    PRIOR = {k: (v[0] + v[1]) / 2.0 for k, v in SR.items()}
    LEAD = 8  # keep the uplink queue at most this many ticks ahead

    mp = tools.map()
    W = float(mp["width"])
    H = float(mp["height"])
    base = (float(mp["base"][0]), float(mp["base"][1]))
    sand = mp.get("sand", [])
    haz = mp.get("hazards", [])

    def rect_has(r, x, y, m):
        x1, x2 = min(r["x1"], r["x2"]) - m, max(r["x1"], r["x2"]) + m
        y1, y2 = min(r["y1"], r["y2"]) - m, max(r["y1"], r["y2"]) + m
        return x1 <= x <= x2 and y1 <= y <= y2

    def terrain(x, y):
        for r in sand:
            if rect_has(r, x, y, 0.0):
                return "sand"
        return "bedrock"

    def inside(x, y, m=0.2):
        return m <= x <= W - m and m <= y <= H - m

    def seg_ok(a, b):
        L = math.dist(a, b)
        n = max(2, int(L / 0.2) + 1)
        for i in range(n + 1):
            t = i / n
            x = a[0] + (b[0] - a[0]) * t
            y = a[1] + (b[1] - a[1]) * t
            if not inside(x, y):
                return False
            for r in haz:
                if rect_has(r, x, y, 0.6):
                    return False
        return True

    def route(a, b):
        if seg_ok(a, b):
            return [b]
        best = None
        for r in haz:
            x1 = min(r["x1"], r["x2"]) - 1.0
            x2 = max(r["x1"], r["x2"]) + 1.0
            y1 = min(r["y1"], r["y2"]) - 1.0
            y2 = max(r["y1"], r["y2"]) + 1.0
            for c in ((x1, y1), (x1, y2), (x2, y1), (x2, y2)):
                if not inside(c[0], c[1]):
                    continue
                if seg_ok(a, c) and seg_ok(c, b):
                    L = math.dist(a, c) + math.dist(c, b)
                    if best is None or L < best[0]:
                        best = (L, c)
        return None if best is None else [best[1], b]

    S = {
        "packets": [], "fix": None, "drives": [], "samples": [],
        "claimed": {}, "sampled": set(), "pending": [], "Q": 0,
        "now": 0, "seen": set(), "complete": False,
    }

    def slip_for(t, packets):
        sw = sv = 0.0
        n = 0
        for p in packets:
            if p.get("terrain") == t and float(p.get("wheel_odometry", 0) or 0) > 0:
                sw += float(p["wheel_odometry"])
                sv += float(p.get("visual_odometry", 0) or 0)
                n += 1
        if n >= 2 and sw >= 3.0:
            return min(max(1.0 - sv / sw, 0.0), 0.9)
        return PRIOR.get(t, 0.1)

    def est_pos(T):
        fix = S["fix"]
        k = int(fix["tick"])
        x, y = float(fix["position"][0]), float(fix["position"][1])
        for d in sorted(S["drives"], key=lambda d: d["exec"]):
            if k < d["exec"] <= T:
                s = slip_for(terrain(x, y), S["packets"])
                x += d["M"] * (1 - s) * math.cos(math.radians(d["h"]))
                y += d["M"] * (1 - s) * math.sin(math.radians(d["h"]))
        return (x, y)

    def drive_cmds(a, path):
        out = []
        cur = a
        for p in path:
            L = math.dist(cur, p)
            if L >= 0.02:
                ang = math.degrees(math.atan2(p[1] - cur[1], p[0] - cur[0]))
                mid = ((cur[0] + p[0]) / 2, (cur[1] + p[1]) / 2)
                t = terrain(*mid)
                s = slip_for(t, S["packets"])
                mult = float(TMULT.get(t, 1.0))
                wheel = L / (1 - s)
                n = max(1, math.ceil(wheel / MAXM - 1e-9))
                m = math.floor((wheel / n) * 1e4) / 1e4
                if m >= 0.01:
                    for _ in range(n):
                        out.append({
                            "kind": "drive",
                            "cmd": {"action": "drive", "heading_deg": round(ang, 3), "metres": m},
                            "h": ang, "M": m, "cost": m * DC * mult,
                        })
            cur = p
        return out

    def plan(now, F):
        Q = S["Q"]
        fix = S["fix"]
        kf = int(fix["tick"])
        batt = float(fix.get("battery", 100.0))
        committed = sum(d["cost"] for d in S["drives"] if d["exec"] > kf)
        committed += SC * sum(1 for e in S["samples"] if e > kf)
        budget = batt - IDLE * (MAXT - kf) - committed - 3.0
        start = est_pos(Q)
        best = None
        if budget > 0:
            for t in mp.get("targets", []):
                tid = str(t["id"])
                if tid in S["sampled"] or tid in S["claimed"]:
                    continue
                p = (float(t["x"]), float(t["y"]))
                path = route(start, p)
                if path is None:
                    continue
                dc = drive_cmds(start, path)
                nd = len(dc)
                sexec = F + nd
                if sexec > MAXT or sexec < int(t.get("appear_tick", 0) or 0):
                    continue
                back = route(p, base)
                if back is None:
                    continue
                dr = drive_cmds(p, back)
                if sexec + len(dr) > MAXT:
                    continue
                cost = sum(c["cost"] for c in dc) + SC + sum(c["cost"] for c in dr)
                if cost > budget:
                    continue
                dl = t.get("deadline_tick")
                on_time = dl is None or sexec <= int(dl)
                val = float(t["value"]) if on_time else float(t.get("late_value", 0.0))
                score = val / (nd + 1)
                if best is None or score > best[0]:
                    best = (score, tid, dc)
        pend = []
        if best is not None:
            _, tid, dc = best
            pend = list(dc) + [{"kind": "sample", "cmd": {"action": "sample"}, "tid": tid}]
        else:
            start_d = math.dist(start, base)
            if start_d > 0.35:
                path = route(start, base)
                if path:
                    dc = drive_cmds(start, path)
                    if dc and F + len(dc) - 1 <= MAXT:
                        pend = dc
        return pend

    def refresh():
        packets = sorted(tools.telemetry_log(), key=lambda p: p["tick"])
        S["packets"] = packets
        if packets:
            S["fix"] = packets[-1]
        latest = packets[-1]["tick"] if packets else 0
        for p in packets:
            if p["tick"] in S["seen"]:
                continue
            S["seen"].add(p["tick"])
            for ev in p.get("events", []) or []:
                typ = str(ev.get("type", "")).lower()
                if "safety" in typ or "hazard" in typ or "edge" in typ:
                    S["drives"] = [d for d in S["drives"] if d["exec"] <= p["tick"]]
                    S["pending"] = []
            for item in p.get("sampled_targets", []) or []:
                tid = item if not isinstance(item, dict) else item.get("id")
                if tid is not None:
                    S["sampled"].add(str(tid))
        for tid, ex in list(S["claimed"].items()):
            if tid in S["sampled"]:
                continue
            if latest >= ex:
                del S["claimed"][tid]

    # main loop
    now = 0
    while True:
        try:
            refresh()
            mp = tools.map()
        except Exception:
            pass
        if S["fix"] is None:
            refresh()
        Q = S["Q"]
        F = max(now + DELAY + 1, Q + 1)
        try:
            if not S["pending"] and Q <= now + LEAD - 1 and F <= MAXT:
                S["pending"] = plan(now, F)
            if S["pending"] and Q <= now + LEAD - 1:
                batch = S["pending"][:MAXC]
                try:
                    acks = tools.uplink([c["cmd"] for c in batch])
                except ValueError:
                    S["pending"] = []
                    acks = None
                if acks:
                    for c, a in zip(batch, acks):
                        ex = int(a["execute_tick"])
                        if c["kind"] == "drive":
                            S["drives"].append({"exec": ex, "h": c["h"], "M": c["M"], "cost": c["cost"]})
                        else:
                            S["claimed"][c["tid"]] = ex
                            S["samples"].append(ex)
                        S["Q"] = max(S["Q"], ex)
                    S["pending"] = S["pending"][len(batch):]
        except Exception:
            S["pending"] = []

        res = tools.advance(1)
        now = int(res.get("current_tick", now + 1))
        if res.get("episode_complete"):
            break

    return None
```