This is an untested module that plays the mission by dead reckoning with a filter on the noisy position fixes. I have not run it against the simulator.

**Estimator**
- It replays every executed drive from the exact tick-0 position, using mid-range slip for each terrain.
- Each noisy position fix is blended in with a gain of 0.4.
- The hidden heading bias is estimated from the sideways error of the fix after each drive of at least 2 m. Drives are then commanded with that bias compensated.
- The position used for planning is the filtered fix plus every command still queued, so the plan accounts for the signal delay.

**Planner**
- Hazards are inflated by 0.7 m. If the straight line crosses one, it routes around it through one or two inflated corners.
- For each known target it simulates the drive-plus-sample trip and checks that the sample tick, the return trip to base and the battery all fit. It then picks the target with the best gain per tick, where gain is the full value if the sample lands by the deadline and `late_value` otherwise.
- Targets that were sampled and failed lose priority and are retried later. A target is given up after 3 failed attempts.
- If no target is feasible, it drives home. Small corrections near base wait until the rover has settled and fixes have caught up.
- If an uplink raises `ValueError` (for example, commands that would run past the last tick), it stops sending and lets the mission run out.

```python
import math


def play(tools):
    R = tools.rules()
    delay = R["delay_ticks"]
    maxt = R["max_ticks"]
    idle = R["idle_cost"]
    samp_cost = R["sample_cost"]
    sl = R["slip_ranges"]
    slip_b = sum(sl["bedrock"]) / 2.0
    slip_s = sum(sl["sand"]) / 2.0
    mult_s = R["terrain_drive_multipliers"]["sand"]

    m0 = tools.map()
    W, Hh = m0["width"], m0["height"]
    base = tuple(m0["base"])
    sand = m0["sand"]
    hazards = m0["hazards"]
    INF = 0.7

    def in_rect(x, y, r, e=0.0):
        return r["x1"] - e <= x <= r["x2"] + e and r["y1"] - e <= y <= r["y2"] + e

    def is_sand(x, y):
        return any(in_rect(x, y, r) for r in sand)

    def dist(a, b):
        return math.hypot(a[0] - b[0], a[1] - b[1])

    def apply_drive(p, H, M, bias):
        n = max(1, int(round(M / 0.1)))
        st = M / n
        ang = math.radians(H + bias)
        x, y = p
        cost = 0.0
        for _ in range(n):
            if is_sand(x, y):
                s, mu = slip_s, mult_s
            else:
                s, mu = slip_b, 1.0
            x += st * (1 - s) * math.cos(ang)
            y += st * (1 - s) * math.sin(ang)
            x = min(max(x, 0.0), W)
            y = min(max(y, 0.0), Hh)
            cost += st * mu
        return (x, y), cost

    def clear(a, b):
        d = dist(a, b)
        n = int(d / 0.2) + 1
        for i in range(n + 1):
            x = a[0] + (b[0] - a[0]) * i / n
            y = a[1] + (b[1] - a[1]) * i / n
            for h in hazards:
                if in_rect(x, y, h, INF):
                    return False
        return True

    corners = []
    for h in hazards:
        e = INF + 0.25
        for cx in (h["x1"] - e, h["x2"] + e):
            for cy in (h["y1"] - e, h["y2"] + e):
                corners.append((min(max(cx, 0.5), W - 0.5), min(max(cy, 0.5), Hh - 0.5)))

    def route(p, g):
        if clear(p, g):
            return [g]
        best = None
        bl = 1e9
        for c in corners:
            if clear(p, c) and clear(c, g):
                l = dist(p, c) + dist(c, g)
                if l < bl:
                    bl, best = l, [c, g]
        if best:
            return best
        for c1 in corners:
            if not clear(p, c1):
                continue
            for c2 in corners:
                if c1 is c2 or not clear(c1, c2) or not clear(c2, g):
                    continue
                l = dist(p, c1) + dist(c1, c2) + dist(c2, g)
                if l < bl:
                    bl, best = l, [c1, c2, g]
        return best

    st = {"bias": 0.0, "p": base, "t": 0, "bat": R["initial_battery"],
          "last_exec": -1, "idx": 0, "drive": None}
    exec_map = {}
    cost_map = {}
    sampled = set()
    pending = {}
    attempts = {}

    def plan(p, goal):
        wps = route(p, goal)
        if wps is None:
            return None
        cmds = []
        cost = 0.0
        bias = st["bias"]
        for w in wps:
            for _ in range(8):
                d = dist(p, w)
                if d < 0.3:
                    break
                H = math.degrees(math.atan2(w[1] - p[1], w[0] - p[0])) - bias
                trial, _c = apply_drive(p, H, 5.0, bias)
                L = dist(p, trial)
                M = 5.0 if L <= d else max(0.05, 5.0 * d / L)
                M = round(M, 2)
                H = round(H, 2)
                p, c = apply_drive(p, H, M, bias)
                cost += c
                cmds.append({"action": "drive", "heading_deg": H, "metres": M})
                if len(cmds) >= 12:
                    break
        return cmds, p, cost

    def process():
        log = tools.telemetry_log()
        new = sorted(log[st["idx"]:], key=lambda q: q["tick"])
        st["idx"] = len(log)
        for pk in new:
            T = pk["tick"]
            for tid in pk.get("sampled_targets", []):
                sampled.add(tid)
            if T <= st["t"] and T != 0:
                continue
            if T == 0:
                st["p"] = tuple(pk["position"])
                st["t"] = 0
                st["bat"] = pk["battery"]
                continue
            p = st["p"]
            ld = None
            for t in range(st["t"] + 1, T + 1):
                c = exec_map.get(t)
                if c and c["action"] == "drive":
                    before = p
                    p, _c = apply_drive(p, c["heading_deg"], c["metres"], st["bias"])
                    ld = (t, before)
            st["t"] = T
            fx, fy = pk["position"]
            ix, iy = fx - p[0], fy - p[1]
            if ld and ld[0] == T:
                L = dist(ld[1], p)
                if L >= 2.0:
                    th = math.atan2(p[1] - ld[1][1], p[0] - ld[1][0])
                    perp = -math.sin(th) * ix + math.cos(th) * iy
                    ang = math.degrees(perp / L)
                    ang = max(-15, min(15, ang))
                    st["bias"] = max(-15, min(15, st["bias"] + 0.2 * min(1, L / 5) * ang))
            p = (p[0] + 0.4 * ix, p[1] + 0.4 * iy)
            st["p"] = (min(max(p[0], 0), W), min(max(p[1], 0), Hh))
            st["bat"] = pk["battery"]
        for tid, tk in list(pending.items()):
            if st["t"] >= tk:
                if tid not in sampled:
                    attempts[tid] = attempts.get(tid, 0) + 1
                del pending[tid]

    def send(cmds, costs):
        acks = tools.uplink(cmds)
        for a, c in zip(acks, costs):
            t = a["execute_tick"]
            exec_map[t] = a["command"]
            cost_map[t] = c
            st["last_exec"] = max(st["last_exec"], t)
        return acks

    def decide(now):
        s = max(now + delay + 1, st["last_exec"] + 1)
        if s > maxt - 1:
            return False
        p = st["p"]
        qcost = 0.0
        for t in sorted(k for k in exec_map if k > st["t"]):
            c = exec_map[t]
            qcost += cost_map.get(t, 0)
            if c["action"] == "drive":
                p = apply_drive(p, c["heading_deg"], c["metres"], st["bias"])[0]
        remaining_idle = idle * (maxt - st["t"])
        best = None
        bscore = 0.0
        try:
            targets = tools.map()["targets"]
        except Exception:
            targets = m0["targets"]
        for tg in targets:
            tid = tg["id"]
            if tid in sampled or tid in pending or attempts.get(tid, 0) >= 3:
                continue
            goal = (tg["x"], tg["y"])
            pl = plan(p, goal)
            if pl is None:
                continue
            cmds, pe, cost = pl
            ts = s + len(cmds)
            if ts > maxt - 1:
                continue
            rt = plan(pe, base)
            if rt is None:
                continue
            r = len(rt[0])
            if ts + r > maxt - 1 - 2:
                continue
            if st["bat"] < remaining_idle + qcost + cost + samp_cost + rt[2] + 4:
                continue
            dl = tg.get("deadline_tick")
            g = tg["value"] if (dl is None or ts <= dl) else tg["late_value"]
            g *= 0.7 ** attempts.get(tid, 0)
            sc = g / (len(cmds) + 1.5)
            if sc > bscore:
                bscore, best = sc, (tid, cmds, cost)
        if best:
            tid, cmds, cost = best
            seq = cmds + [{"action": "sample"}]
            costs = [cost / max(1, len(cmds))] * len(cmds) + [samp_cost]
            if len(seq) <= 5:
                send(seq, costs)
                pending[tid] = s + len(seq) - 1
            else:
                send(seq[:5], costs[:5])
            return True
        d = dist(p, base)
        if d <= 0.45:
            return True
        if d < 1.5 and st["t"] < st["last_exec"] + 2:
            return True
        pl = plan(p, base)
        if pl is None or not pl[0]:
            return True
        cmds, _pe, cost = pl
        cmds = cmds[:5]
        send(cmds, [cost / len(pl[0])] * len(cmds))
        return True

    now = 0
    stop = False
    while True:
        process()
        if not stop and st["last_exec"] <= now + delay:
            try:
                decide(now)
            except ValueError:
                stop = True
        r = tools.advance(1)
        now = r["current_tick"]
        if r["episode_complete"]:
            break
```