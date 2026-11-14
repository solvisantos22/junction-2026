This module has not been run, not even against a mock server, so treat it as untested. It plays the mission as a repeating 8-tick cycle that matches the relay pass period.

- **Cycle:** at the start of each pass it processes the new telemetry, plans the next 8 commands and sends them as 5 + 3, so execution is continuous with one command per tick.
- **Position estimate:** it replays the commands that actually executed, using the published `lightlag_surface.drive` model, and blends in each noisy position fix. Fixes that disagree with the replay by more than about 9 m are mostly ignored, unless three in a row disagree.
- **Wheel scale:** it estimates the hidden wheel scale from visual odometry versus the modelled ground distance of each completed drive.
- **Executed or cleared:** whether a command ran is read from `command_executed` events, with inference when a packet was lost.
- **Routing:** it builds a symmetric Dijkstra graph over the 5 m grid. Slopes above 0.30 are forbidden. Uphill slip is penalised using pessimistic slip bases, because a step slipping above 0.45 triggers the onboard stop. After each safety stop the area around the estimated position gets extra cost, and a `slip_limit` stop raises the slip padding for the terrain reported in telemetry.
- **Target choice:**
  - Greedy on value divided by travel time, using the late value when the estimated arrival is past the deadline.
  - A target is chosen only if the rover can still sample it and return to base with margin before tick 420.
  - A target stays pending until telemetry confirms the sample. Each retry aims at a slightly offset point, and a target is dropped after 4 failures.
- **Battery guard:** it holds with waits when the battery drops below 12, and it parks at base when no target is feasible.

```python
import math
import heapq
import lightlag_surface as LS


def play(tools):
    R = tools.rules()
    mp = tools.map()
    ph = R["physics"]
    surf = LS.Surface(mp["cell_m"], mp["elevation_cm"], mp["terrain"])
    NX, NY = surf.nx, surf.ny
    cell = surf.cell
    N = NX * NY
    base = (float(mp["base"][0]), float(mp["base"][1]))
    TEND = R["max_ticks"]
    DELAY = R["delay_ticks"]
    PER = R["relay_passes"]["period_ticks"]
    INF = float("inf")
    mid = {k: (v[0] + v[1]) / 2.0 for k, v in ph["slip_base_ranges"].items()}
    hi = {k: v[1] for k, v in ph["slip_base_ranges"].items()}
    gain = dict(ph["slip_grade_gain"])
    gain_hi = dict(gain)
    gain_hi["sand"] = 4.5
    dcost = ph["drive_cost_per_wheel_m"]
    pad = {k: 0.0 for k in mid}
    crust = mp.get("crust_regions", []) or []
    names = {"b": "bedrock", "r": "regolith", "s": "sand", "k": "rocks"}

    def in_crust(x, y):
        for r in crust:
            if r["x1"] <= x <= r["x2"] and r["y1"] <= y <= r["y2"]:
                return True
        return False

    S = {"adj": None, "bdist": None, "rebuild": False, "scale": 1.0, "sv": 0.0,
         "sm": 0.0, "rej": 0, "maxrcv": -1, "evmax": -1, "goal": None}
    npen = [0.0] * N

    def edge(ax, ay, bx, by):
        L = math.hypot(bx - ax, by - ay)
        ux, uy = (bx - ax) / L, (by - ay) / L
        for t in (0.05, 0.25, 0.5, 0.75, 0.95):
            _, gx, gy, _c = surf.sample(ax + (bx - ax) * t, ay + (by - ay) * t)
            if math.hypot(gx, gy) > 0.30:
                return None
        smp = []
        for t in (1 / 6.0, 0.5, 5 / 6.0):
            x = ax + (bx - ax) * t
            y = ay + (by - ay) * t
            _, gx, gy, code = surf.sample(x, y)
            nm = names[code]
            cr = 1.08 if (code == "b" and in_crust(x, y)) else 1.0
            smp.append((gx, gy, nm, math.hypot(gx, gy), cr))
        res = []
        for sgn in (1.0, -1.0):
            tot = 0.0
            for gx, gy, nm, sl, cr in smp:
                grade = (gx * ux + gy * uy) * sgn
                g = grade if grade > 0 else 0.0
                sm = min(0.9, mid[nm] + pad[nm] + gain[nm] * g)
                sp = hi[nm] + pad[nm] + gain_hi[nm] * g
                pen = 1.0 + 12.0 * max(0.0, sp - 0.40)
                if sl > 0.15:
                    pen *= 1.0 + 8.0 * (sl - 0.15)
                seg = L / 3.0
                wheel = seg / (1.0 - sm)
                en = wheel * dcost[nm] + 2.0 * g * seg
                tot += wheel / 4.6 * pen * cr + 0.02 * en
            res.append(tot)
        return res

    def dijkstra(src):
        adj = S["adj"]
        dist = [INF] * N
        prev = [-1] * N
        dist[src] = 0.0
        h = [(0.0, src)]
        while h:
            d, u = heapq.heappop(h)
            if d > dist[u]:
                continue
            for v, c in adj[u]:
                nd = d + c + npen[v]
                if nd < dist[v]:
                    dist[v] = nd
                    prev[v] = u
                    heapq.heappush(h, (nd, v))
        return dist, prev

    def nn(x, y):
        i = min(NX - 1, max(0, int(round(x / cell))))
        j = min(NY - 1, max(0, int(round(y / cell))))
        return j * NX + i

    def build():
        adj = [[] for _ in range(N)]
        for j in range(NY):
            for i in range(NX):
                a = j * NX + i
                ax, ay = i * cell, j * cell
                for di, dj in ((1, 0), (0, 1), (1, 1), (1, -1)):
                    ii, jj = i + di, j + dj
                    if not (0 <= ii < NX and 0 <= jj < NY):
                        continue
                    r = edge(ax, ay, ii * cell, jj * cell)
                    if r is None:
                        continue
                    c = (r[0] + r[1]) / 2.0
                    b = jj * NX + ii
                    adj[a].append((b, c))
                    adj[b].append((a, c))
        S["adj"] = adj
        S["bdist"] = dijkstra(nn(*base))[0]
        S["rebuild"] = False

    build()

    packets = {}
    sampled = set()
    ev_exec = set()
    stops = []
    cmds = []
    pending = {}
    fails = {}
    est = {"pos": None, "pt": 0}

    def store(p):
        t = p["tick"]
        packets[t] = p
        if t > S["maxrcv"]:
            S["maxrcv"] = t
        for s in p.get("sampled_targets", []) or []:
            sampled.add(s["id"] if isinstance(s, dict) else s)
        for e in p.get("events", []) or []:
            if e.get("type") == "command_executed":
                ev_exec.add(e.get("command_id"))
                if e.get("command_id", -1) > S["evmax"]:
                    S["evmax"] = e.get("command_id")
            elif e.get("type") == "safety_stop":
                stops.append(t)

    for p in tools.telemetry_log():
        store(p)
    est["pos"] = tuple(packets[0]["position"]) if 0 in packets else base

    def executed(c):
        if c["id"] in ev_exec:
            return True
        if c["exe"] in packets:
            return False
        if S["evmax"] > c["id"]:
            return True
        if c["exe"] > S["maxrcv"]:
            return True
        for s in stops:
            if s < c["exe"] <= s + PER + DELAY + 2:
                return False
        return True

    def sbase():
        return {k: mid[k] + pad[k] for k in mid}

    def sim(P, h, M):
        return LS.drive(surf, ph, P[0], P[1], h, M * S["scale"], sbase(), 0.0)

    def apply(c, P, calib):
        if c["action"] != "drive":
            return P
        r = sim(P, c["heading"], c["metres"])
        if calib:
            p = packets.get(c["exe"])
            if p and p.get("visual_odometry", 0) > 0 and p.get("wheel_odometry", 0) >= 0.95 * c["metres"]:
                r1 = LS.drive(surf, ph, P[0], P[1], c["heading"], c["metres"], sbase(), 0.0)
                S["sv"] += p["visual_odometry"]
                S["sm"] += r1["ground"]
                S["scale"] = min(1.3, max(0.7, (S["sv"] + 10.0) / (S["sm"] + 10.0)))
        return (r["x"], r["y"])

    def handle_stop(t, e):
        pos = est["pos"]
        for j in range(max(0, int((pos[1] - 7) / cell)), min(NY - 1, int((pos[1] + 7) / cell) + 1) + 1):
            for i in range(max(0, int((pos[0] - 7) / cell)), min(NX - 1, int((pos[0] + 7) / cell) + 1) + 1):
                if math.hypot(i * cell - pos[0], j * cell - pos[1]) <= 7:
                    npen[j * NX + i] += 8.0
        if e.get("reason") == "slip_limit":
            nm = packets[t].get("terrain")
            if nm in pad:
                pad[nm] = min(0.15, pad[nm] + 0.03)
        S["rebuild"] = True

    def process():
        for t in sorted(k for k in packets if k > est["pt"]):
            pos = est["pos"]
            for c in cmds:
                if est["pt"] < c["exe"] <= t and executed(c):
                    pos = apply(c, pos, True)
            z = packets[t]["position"]
            dx, dy = z[0] - pos[0], z[1] - pos[1]
            d = math.hypot(dx, dy)
            if d > 9 and S["rej"] < 3:
                S["rej"] += 1
                k = 0.0
            else:
                k = 0.6 if d > 9 else (0.3 if d < 5 else 0.12)
                S["rej"] = 0
            est["pos"] = (pos[0] + k * dx, pos[1] + k * dy)
            est["pt"] = t
            for e in packets[t].get("events", []) or []:
                if e.get("type") == "safety_stop":
                    handle_stop(t, e)
        if S["rebuild"]:
            build()

    def wrap(a):
        return (a + 180.0) % 360.0 - 180.0

    def mk(P, wp, final):
        dx, dy = wp[0] - P[0], wp[1] - P[1]
        d = math.hypot(dx, dy)
        h0 = math.degrees(math.atan2(dy, dx))
        if final:
            Mg = min(5.0, max(0.2, d))
            r = sim(P, h0, Mg)
            g = math.hypot(r["x"] - P[0], r["y"] - P[1])
            M = min(5.0, max(0.2, d * Mg / g)) if g > 0.05 else 5.0
        else:
            M = 5.0
        r = sim(P, h0, M)
        g = math.hypot(r["x"] - P[0], r["y"] - P[1])
        h1 = h0
        if g > 0.05:
            a = math.degrees(math.atan2(r["y"] - P[1], r["x"] - P[0]))
            h1 = h0 + max(-40.0, min(40.0, wrap(h0 - a)))
        r = sim(P, h1, M)
        return h1 % 360.0, M, (r["x"], r["y"])

    targets = []

    def choose(Pp, ex, taken):
        dist, prev = dijkstra(nn(*Pp))
        best, bs = None, -1.0
        sc = S["scale"]
        for t in targets:
            tid = t["id"]
            if tid in sampled or tid in pending or tid in taken or fails.get(tid, 0) >= 4:
                continue
            n = nn(t["x"], t["y"])
            d = dist[n]
            if d == INF:
                continue
            tk = d * 1.1 / sc + 1.0
            arrive = ex + tk
            back = S["bdist"][n] * 1.1 / sc
            if arrive + 3 + back + 6 > TEND:
                continue
            dl = t.get("deadline_tick")
            v = t["value"] if (dl is None or arrive <= dl) else t.get("late_value", t["value"])
            score = v / (tk + 4.0)
            if tid == S["goal"]:
                score *= 1.25
            if score > bs:
                bs, best = score, t
        return best, dist, prev

    def setgoal(Pp, ex, taken):
        t, dist, prev = choose(Pp, ex, taken)
        if t is None:
            S["goal"] = None
            tp = base
            tid = None
        else:
            tid = t["id"]
            S["goal"] = tid
            f = fails.get(tid, 0)
            if f > 0:
                a = f * 2.1
                tp = (min(mp["width"], max(0.0, t["x"] + 1.5 * math.cos(a))),
                      min(mp["height"], max(0.0, t["y"] + 1.5 * math.sin(a))))
            else:
                tp = (t["x"], t["y"])
        n = nn(*tp)
        path = []
        if dist[n] < INF:
            u = n
            while u != -1:
                path.append((float((u % NX) * cell), float((u // NX) * cell)))
                u = prev[u]
            path.reverse()
        path.append(tp)
        if len(path) > 1:
            path[-2:-1] = [] if False else []
        return tid, tp, path

    def cycle(now):
        nonlocal targets
        process()
        for tid, ex in list(pending.items()):
            ts = [t for t in packets if t >= ex]
            if ts:
                t0 = min(ts)
                ids = packets[t0].get("sampled_targets", []) or []
                ids = [s["id"] if isinstance(s, dict) else s for s in ids]
                if tid in ids or tid in sampled:
                    sampled.add(tid)
                else:
                    fails[tid] = fails.get(tid, 0) + 1
                del pending[tid]
        try:
            targets = tools.map()["targets"]
        except Exception:
            pass
        last = max([c["exe"] for c in cmds]) if cmds else -1
        first = max(now + DELAY + 1, last + 1)
        P = est["pos"]
        for c in cmds:
            if c["exe"] > est["pt"] and executed(c):
                P = apply(c, P, False)
        batt = packets[max(packets)]["battery"] if packets else 100.0
        out = []
        taken = set()
        if batt < 12.0:
            out = [({"action": "wait"}, None)] * PER
        else:
            tid, tp, path = setgoal(P, first, taken)
            idx = 0
            for s in range(PER):
                ex = first + s
                d = math.hypot(tp[0] - P[0], tp[1] - P[1])
                if tid is not None and d <= 1.0:
                    out.append(({"action": "sample"}, tid))
                    taken.add(tid)
                    tid, tp, path = setgoal(P, ex + 1, taken)
                    idx = 0
                    continue
                if tid is None and d <= 1.5:
                    out.append(({"action": "wait"}, None))
                    continue
                while idx < len(path) - 1 and (
                        math.hypot(P[0] - path[idx][0], P[1] - path[idx][1]) < 3.0 or
                        math.hypot(P[0] - path[idx + 1][0], P[1] - path[idx + 1][1]) <=
                        math.hypot(path[idx][0] - path[idx + 1][0], path[idx][1] - path[idx + 1][1])):
                    idx += 1
                wp = path[idx]
                final = idx == len(path) - 1
                h, M, newP = mk(P, wp, final)
                out.append(({"action": "drive", "heading_deg": h, "metres": M}, None))
                P = newP
        for k in range(0, len(out), 5):
            chunk = out[k:k + 5]
            try:
                acks = tools.uplink([c for c, _ in chunk])
            except ValueError:
                chunk = [({"action": "wait"}, None)] * len(chunk)
                acks = tools.uplink([c for c, _ in chunk])
            for (cmd, tid2), a in zip(chunk, acks):
                cmds.append({"id": a["command_id"], "exe": a["execute_tick"],
                             "action": cmd["action"], "heading": cmd.get("heading_deg", 0.0),
                             "metres": cmd.get("metres", 0.0)})
                if tid2:
                    pending[tid2] = a["execute_tick"]

    tick = 0
    while True:
        cycle(tick)
        while True:
            n = min(5, PER - tick % PER)
            res = tools.advance(n)
            tick = res["current_tick"]
            for p in res.get("packets", []):
                store(p)
            if res.get("episode_complete"):
                return
            if tick % PER == 0:
                break
```