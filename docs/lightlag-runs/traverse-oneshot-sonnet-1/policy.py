import math
import heapq
import lightlag_surface as ls


def play(tools):
    rules = tools.rules()
    mp = tools.map()
    phys = rules['physics']
    MAXT = rules['max_ticks']
    D = rules['delay_ticks']
    surf = ls.Surface(mp['cell_m'], mp['elevation_cm'], mp['terrain'])
    cell = surf.cell
    nx, ny = surf.nx, surf.ny
    N = nx * ny
    base = (float(mp['base'][0]), float(mp['base'][1]))
    slipb = {k: (v[0] + v[1]) / 2 for k, v in phys['slip_base_ranges'].items()}
    gain = phys['slip_grade_gain']
    costw = phys['drive_cost_per_wheel_m']
    TC = ls.TERRAIN_CODES
    INF = float('inf')

    # ---------- graph ----------
    offs = [(1, 0), (0, 1), (1, 1), (-1, 1), (2, 1), (1, 2), (-1, 2), (-2, 1)]
    adj = [[] for _ in range(N)]
    radj = [[] for _ in range(N)]
    for j in range(ny):
        for i in range(nx):
            a = j * nx + i
            ax, ay = i * cell, j * cell
            for di, dj in offs:
                i2, j2 = i + di, j + dj
                if not (0 <= i2 < nx and 0 <= j2 < ny):
                    continue
                b = j2 * nx + i2
                bx, by = i2 * cell, j2 * cell
                L = math.hypot(bx - ax, by - ay)
                n = max(2, int(L / 1.25) + 1)
                ds = L / n
                ux, uy = (bx - ax) / L, (by - ay) / L
                ef = eb = wf_t = wb_t = 0.0
                maxs = 0.0
                for k in range(n):
                    t = (k + 0.5) / n
                    h, gx, gy, c = surf.sample(ax + (bx - ax) * t, ay + (by - ay) * t)
                    s = math.hypot(gx, gy)
                    if s > maxs:
                        maxs = s
                    name = TC[c]
                    grade = gx * ux + gy * uy
                    sf = min(0.9, slipb[name] + gain[name] * max(0.0, grade))
                    sb = min(0.9, slipb[name] + gain[name] * max(0.0, -grade))
                    wf = ds / (1 - sf)
                    wb = ds / (1 - sb)
                    ef += wf * costw[name]
                    eb += wb * costw[name]
                    wf_t += wf
                    wb_t += wb
                if maxs > 0.31:
                    continue
                dh = surf.h[j2][i2] - surf.h[j][i]
                ef += 2.0 * max(0.0, dh)
                eb += 2.0 * max(0.0, -dh)
                pen = 40.0 * max(0.0, maxs - 0.2)
                tf, tb = wf_t / 4.6, wb_t / 4.6
                cf = tf + 0.25 * ef + pen
                cb = tb + 0.25 * eb + pen
                adj[a].append((b, cf, tf, ef))
                adj[b].append((a, cb, tb, eb))
                radj[b].append((a, cf, tf, ef))
                radj[a].append((b, cb, tb, eb))

    pen = {}

    def node(x, y):
        i = min(nx - 1, max(0, int(round(x / cell))))
        j = min(ny - 1, max(0, int(round(y / cell))))
        return j * nx + i

    def dijk(src, graph):
        dist = [INF] * N
        tk = [0.0] * N
        en = [0.0] * N
        par = [-1] * N
        dist[src] = 0.0
        heap = [(0.0, src)]
        while heap:
            d, u = heapq.heappop(heap)
            if d > dist[u]:
                continue
            for v, c, t, e in graph[u]:
                nd = d + c + pen.get(v, 0.0)
                if nd < dist[v]:
                    dist[v] = nd
                    tk[v] = tk[u] + t
                    en[v] = en[u] + e
                    par[v] = u
                    heapq.heappush(heap, (nd, v))
        return dist, tk, en, par

    def add_pen(x, y):
        for j in range(max(0, int(y / cell) - 2), min(ny, int(y / cell) + 4)):
            for i in range(max(0, int(x / cell) - 2), min(nx, int(x / cell) + 4)):
                if math.hypot(i * cell - x, j * cell - y) <= 6.5:
                    pen[j * nx + i] = pen.get(j * nx + i, 0.0) + 25.0

    S = {'tick': 0, 'done': False}

    def adv(n):
        r = tools.advance(n)
        S['tick'] = r['current_tick']
        S['done'] = r['episode_complete']

    def sendcmds(cmds):
        E = None
        for k in range(0, len(cmds), 5):
            acks = tools.uplink(cmds[k:k + 5])
            E = acks[-1]['execute_tick']
        return E

    def localize(E, n):
        need = E + n + D
        while S['tick'] < need and not S['done']:
            adv(max(1, min(5, need - S['tick'])))
        log = tools.telemetry_log()
        pk = [p for p in log if p['tick'] >= E + 1]
        if not pk:
            pk = log[-2:]
        x = sum(p['position'][0] for p in pk) / len(pk)
        y = sum(p['position'][1] for p in pk) / len(pk)
        return (x, y)

    def make_leg(path, pos, bias, maxc=13):
        p = pos
        idx = 0
        cmds = []
        reached = False
        stop = False
        hd = 0.0
        while len(cmds) < maxc:
            tgt = path[idx]
            d = math.hypot(tgt[0] - p[0], tgt[1] - p[1])
            last = idx == len(path) - 1
            thr = 0.8 if last else 2.2
            if d < thr:
                if last:
                    reached = True
                    break
                idx += 1
                continue
            desired = math.degrees(math.atan2(tgt[1] - p[1], tgt[0] - p[0]))
            metres = min(5.0, max(0.5, d / 0.9))
            r = ls.drive(surf, phys, p[0], p[1], desired, metres, slipb)
            hd = desired
            moved = math.hypot(r['x'] - p[0], r['y'] - p[1])
            if r['stop'] and moved < 0.05:
                stop = True
                break
            cmds.append({"action": "drive", "heading_deg": (desired - bias) % 360.0,
                         "metres": round(metres, 2)})
            p = (r['x'], r['y'])
            if r['stop']:
                stop = True
                break
        return cmds, p, reached, stop, hd

    pos = base
    bias = 0.0
    attempts = {}
    black = set()
    cur = None

    while not S['done'] and S['tick'] < MAXT:
        try:
            log = tools.telemetry_log()
            last = log[-1]
            sampled = set(last['sampled_targets'])
            battery = last['battery']
            if battery < 18:
                adv(5)
                continue
            m = tools.map()
            targets = [t for t in m['targets'] if t['id'] not in sampled and t['id'] not in black]
            now = S['tick']
            df, tf, ef, pf = dijk(node(*pos), adj)
            db, tb, eb, _ = dijk(node(*base), radj)
            best = None
            bs = 0
            for t in targets:
                nt = node(t['x'], t['y'])
                if df[nt] == INF or db[nt] == INF:
                    continue
                tt = tf[nt]
                arrive = now + 1.2 * tt + 8
                backt = 1.2 * tb[nt] + 10
                if arrive + 3 + backt > MAXT:
                    continue
                if battery - 0.4 * (ef[nt] + eb[nt]) < 15:
                    continue
                dl = t['deadline_tick']
                val = t['value'] if (dl is None or arrive <= dl) else t['late_value']
                sc = val / (1.2 * tt + 12)
                if cur == t['id']:
                    sc *= 1.3
                if sc > bs:
                    bs = sc
                    best = t
            if best is not None:
                cur = best['id']
                goal = (float(best['x']), float(best['y']))
                is_target = True
            else:
                cur = None
                goal = base
                is_target = False
            dg = math.hypot(goal[0] - pos[0], goal[1] - pos[1])
            if is_target and dg <= 1.5:
                E = sendcmds([{"action": "sample"}])
                pos = localize(E, 2)
                attempts[best['id']] = attempts.get(best['id'], 0) + 1
                lg = tools.telemetry_log()[-1]
                if best['id'] not in lg['sampled_targets'] and attempts[best['id']] >= 3:
                    black.add(best['id'])
                continue
            if (not is_target) and dg <= 1.8:
                adv(5)
                continue
            if dg < 12:
                pts = [goal]
            else:
                v = node(*goal)
                chain = []
                while v != -1:
                    chain.append(v)
                    v = pf[v]
                chain.reverse()
                pts = [((c % nx) * cell, (c // nx) * cell) for c in chain]
                if len(pts) > 1 and math.hypot(pos[0] - pts[1][0], pos[1] - pts[1][1]) < \
                        math.hypot(pts[0][0] - pts[1][0], pts[0][1] - pts[1][1]):
                    pts = pts[1:]
                if pts and math.hypot(pts[-1][0] - goal[0], pts[-1][1] - goal[1]) < 2.0:
                    pts = pts[:-1]
                pts.append(goal)
            cmds, pred, reached, stop, hd = make_leg(pts, pos, bias)
            if not cmds:
                add_pen(pos[0] + 5 * math.cos(math.radians(hd)), pos[1] + 5 * math.sin(math.radians(hd)))
                adv(1)
                continue
            start = pos
            E = sendcmds(cmds)
            new = localize(E, 4 if reached else 2)
            if stop:
                add_pen(pred[0] + 5 * math.cos(math.radians(hd)), pred[1] + 5 * math.sin(math.radians(hd)))
            else:
                if math.hypot(new[0] - pred[0], new[1] - pred[1]) > 7:
                    add_pen(new[0] + 5 * math.cos(math.radians(hd)), new[1] + 5 * math.sin(math.radians(hd)))
                elif math.hypot(pred[0] - start[0], pred[1] - start[1]) > 15 and \
                        math.hypot(new[0] - start[0], new[1] - start[1]) > 10:
                    am = math.degrees(math.atan2(new[1] - start[1], new[0] - start[0]))
                    ap = math.degrees(math.atan2(pred[1] - start[1], pred[0] - start[0]))
                    diff = (am - ap + 180.0) % 360.0 - 180.0
                    bias = max(-8.0, min(8.0, bias + 0.6 * diff))
            pos = new
        except Exception:
            if S['done']:
                break
            adv(1)

    while not S['done']:
        adv(5)
