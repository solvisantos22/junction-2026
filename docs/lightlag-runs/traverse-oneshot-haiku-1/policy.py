"""Autopilot for the lightlag traverse.

Strategy
- Plan routes on a 5 m grid (Dijkstra) that keep slope well under max_tilt and
  prefer firmer ground.
- Dead-reckon the rover between telemetry packets with the published drive
  model (mid-range slip), and blend in each packet's noisy position.
- Keep about PIPE commands queued so the rover never idles while telemetry is
  in flight.
- Choose targets greedily by value per estimated travel time, requiring that
  the return to the lander still fits in the mission.
- Sample only when the predicted position is within 1.5 m of the target.
"""

import heapq
import math

import lightlag_surface as ls

PIPE = 4                # commands kept queued ahead of the rover
SLOPE_LIM = 0.27        # planning limit, below max_tilt 0.36 to allow for drift
MAX_WHEEL = 5.0         # max metres per drive command
PLAN_SPEED = 2.5        # conservative ground metres per tick for time estimates
MULT = {"bedrock": 1.0, "regolith": 1.2, "sand": 2.2, "rocks": 1.6}
ARRIVE_R = 1.5          # sample / park when predicted this close


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _est(a, b):
    return _dist(a, b) * 1.3 / PLAN_SPEED + 2.0


def play(tools):
    rules = tools.rules()
    phys = rules["physics"]
    max_ticks = int(rules["max_ticks"])

    mp = tools.map()
    surf = ls.Surface(float(mp["cell_m"]), mp["elevation_cm"], mp["terrain"])
    cell = surf.cell
    NX, NY = surf.nx, surf.ny
    W, H = surf.width, surf.height
    base = (float(mp["base"][0]), float(mp["base"][1]))
    slip_mid = {k: 0.5 * (v[0] + v[1]) for k, v in phys["slip_base_ranges"].items()}
    gain = phys["slip_grade_gain"]

    edge_cache = {}
    sampled = set()
    attempts = {}
    unreachable = set()
    pending_sample = {}     # target id -> execute tick of its queued sample
    drive_log = []          # drives not yet reflected in a packet: exec, heading, wheel
    queue = []              # commands not yet executed: exec
    st = {"base_pos": base, "base_tick": 0, "alive": True}

    try:
        tele = tools.telemetry_log()
        if tele:
            st["base_pos"] = (float(tele[0]["position"][0]), float(tele[0]["position"][1]))
    except Exception:
        pass

    # ---------- planning geometry ----------

    def seg_cost(p, q):
        """Cost of a straight segment, or None if it is too steep or leaves the map."""
        x0, y0 = p
        x1, y1 = q
        L = math.hypot(x1 - x0, y1 - y0)
        if L < 1e-9:
            return 0.0
        n = max(2, int(L) + 1)
        acc = 0.0
        for k in range(n + 1):
            t = k / n
            x = min(max(x0 + (x1 - x0) * t, 0.0), W)
            y = min(max(y0 + (y1 - y0) * t, 0.0), H)
            _, gx, gy, code = surf.sample(x, y)
            s = math.hypot(gx, gy)
            if s > SLOPE_LIM:
                return None
            acc += MULT[ls.TERRAIN_CODES[code]] + 3.0 * s
        return L * acc / (n + 1)

    def grid_xy(v):
        return ((v % NX) * cell, (v // NX) * cell)

    def grid_edge(u, v):
        key = (u, v) if u < v else (v, u)
        if key not in edge_cache:
            edge_cache[key] = seg_cost(grid_xy(key[0]), grid_xy(key[1]))
        return edge_cache[key]

    def links(p, radius=12.0):
        out = []
        i0 = int(round(p[0] / cell))
        j0 = int(round(p[1] / cell))
        r = int(radius / cell) + 1
        for j in range(max(0, j0 - r), min(NY, j0 + r + 1)):
            for i in range(max(0, i0 - r), min(NX, i0 + r + 1)):
                q = (i * cell, j * cell)
                if _dist(q, p) <= radius:
                    c = seg_cost(p, q)
                    if c is not None:
                        out.append((j * NX + i, c))
        return out

    def route(start, goal):
        """List of points from start to goal, or None."""
        if seg_cost(start, goal) is not None:
            return [start, goal]
        glinks = dict(links(goal))
        slinks = links(start)
        if not glinks or not slinks:
            return None
        dist = {"S": 0.0}
        prev = {}
        pq = [(0.0, 0, "S")]
        counter = 1
        found = False
        while pq:
            d, _, u = heapq.heappop(pq)
            if u == "G":
                found = True
                break
            if d > dist.get(u, 1e18):
                continue
            if u == "S":
                cand = slinks
            else:
                cand = []
                if u in glinks:
                    cand.append(("G", glinks[u]))
                ui, uj = u % NX, u // NX
                for di in (-1, 0, 1):
                    for dj in (-1, 0, 1):
                        if di == 0 and dj == 0:
                            continue
                        i, j = ui + di, uj + dj
                        if 0 <= i < NX and 0 <= j < NY:
                            v = j * NX + i
                            c = grid_edge(u, v)
                            if c is not None:
                                cand.append((v, c))
            for v, c in cand:
                nd = d + c
                if nd < dist.get(v, 1e18):
                    dist[v] = nd
                    prev[v] = u
                    heapq.heappush(pq, (nd, counter, v))
                    counter += 1
        if not found:
            return None
        seq = []
        v = "G"
        while v != "S":
            seq.append(v)
            v = prev[v]
        seq.append("S")
        seq.reverse()
        pts = []
        for v in seq:
            if v == "S":
                pts.append(start)
            elif v == "G":
                pts.append(goal)
            else:
                pts.append(grid_xy(v))
        return pts

    # ---------- dead reckoning ----------

    def predict(pos, from_tick):
        x, y = pos
        for d in drive_log:
            if d["exec"] > from_tick:
                r = ls.drive(surf, phys, x, y, d["heading"], d["wheel"], slip_mid)
                x, y = r["x"], r["y"]
        return (x, y)

    def handle(p):
        if p["tick"] < st["base_tick"]:
            return
        if not p.get("alive", True):
            st["alive"] = False
        for s in p.get("sampled_targets", []) or []:
            sid = s if isinstance(s, str) else s.get("id")
            if sid is not None:
                sampled.add(sid)
        fix = (float(p["position"][0]), float(p["position"][1]))
        pred = predict(st["base_pos"], st["base_tick"])
        # predict up to the packet tick only
        x, y = st["base_pos"]
        for d in drive_log:
            if st["base_tick"] < d["exec"] <= p["tick"]:
                r = ls.drive(surf, phys, x, y, d["heading"], d["wheel"], slip_mid)
                x, y = r["x"], r["y"]
        pred_at = (x, y)
        if _dist(pred_at, fix) > 4.0:
            # a safety stop probably cleared the queue: trust the fix
            new = fix
            drive_log[:] = []
        else:
            new = ((fix[0] + pred_at[0]) / 2.0, (fix[1] + pred_at[1]) / 2.0)
            drive_log[:] = [d for d in drive_log if d["exec"] > p["tick"]]
        st["base_pos"] = new
        st["base_tick"] = p["tick"]

    # ---------- main loop ----------

    goal = None
    now = 0
    while True:
        tm = tools.map()
        targets = {t["id"]: t for t in tm["targets"]}
        P0 = predict(st["base_pos"], st["base_tick"])
        tq = now + len(queue)

        def infeasible(tid):
            t = targets[tid]
            c = (float(t["x"]), float(t["y"]))
            return tq + _est(P0, c) + _est(c, base) + 3 > max_ticks

        if goal not in (None, "base"):
            if (goal not in targets or goal in sampled or goal in unreachable
                    or attempts.get(goal, 0) >= 3 or infeasible(goal)):
                goal = None

        if goal in (None, "base"):
            best, bs = None, -1.0
            for tid, t in targets.items():
                if tid in sampled or tid in unreachable or attempts.get(tid, 0) >= 3:
                    continue
                if infeasible(tid):
                    continue
                c = (float(t["x"]), float(t["y"]))
                go = _est(P0, c)
                arrive = tq + go
                dl = t.get("deadline_tick")
                v = float(t["value"]) if (dl is None or arrive <= dl) else float(t["late_value"])
                sc = v / (go + 3.0)
                if sc > bs:
                    bs, best = sc, tid
            goal = best if best is not None else "base"

        gp = base if goal == "base" else (float(targets[goal]["x"]), float(targets[goal]["y"]))

        # build commands
        cmds, metas = [], []
        P = P0
        room = min(5, PIPE - len(queue))
        path = None
        while len(cmds) < room:
            dg = _dist(P, gp)
            if dg <= ARRIVE_R:
                if goal != "base":
                    if pending_sample.get(goal, -99) + 4 > now:
                        break   # sample already queued and not yet resolved
                    cmds.append({"action": "sample"})
                    metas.append(("sample", goal))
                break
            if path is None:
                path = route(P, gp)
                if path is None:
                    if goal == "base":
                        path = [P, gp]
                    else:
                        unreachable.add(goal)
                        break
            wp = gp
            for pt in path:
                if _dist(pt, P) >= 4.0:
                    wp = pt
                    break
            dx, dy = wp[0] - P[0], wp[1] - P[1]
            dd = math.hypot(dx, dy)
            heading = round(math.degrees(math.atan2(dy, dx)), 3)
            ux, uy = math.cos(math.radians(heading)), math.sin(math.radians(heading))
            _, gx, gy, code = surf.sample(P[0], P[1])
            name = ls.TERRAIN_CODES[code]
            grade = gx * ux + gy * uy
            slip = min(0.95, max(0.0, slip_mid[name] + gain[name] * max(0.0, grade)))
            wheel = min(MAX_WHEEL, dd / max(0.05, 1.0 - slip))
            wheel = round(max(0.05, wheel), 3)
            cmds.append({"action": "drive", "heading_deg": heading, "metres": wheel})
            metas.append(("drive", heading, wheel))
            r = ls.drive(surf, phys, P[0], P[1], heading, wheel, slip_mid)
            P = (r["x"], r["y"])
            if r["stop"] is not None:
                break

        if cmds:
            acks = tools.uplink(cmds)
            for ack, meta in zip(acks, metas):
                ex = int(ack["execute_tick"])
                queue.append({"exec": ex})
                if meta[0] == "drive":
                    drive_log.append({"exec": ex, "heading": meta[1], "wheel": meta[2]})
                else:
                    tid = meta[1]
                    pending_sample[tid] = ex
                    attempts[tid] = attempts.get(tid, 0) + 1

        n = min(2, max_ticks - now)
        if n <= 0:
            break
        r = tools.advance(n)
        now = int(r["current_tick"])
        for p in sorted(r.get("packets", []), key=lambda q: q["tick"]):
            handle(p)
        queue[:] = [q for q in queue if q["exec"] > now]
        for tid in list(pending_sample):
            if pending_sample[tid] + 4 <= now and tid in sampled:
                del pending_sample[tid]
        if r.get("episode_complete") or not st["alive"]:
            break
