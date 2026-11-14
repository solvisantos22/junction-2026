import json, math, heapq, random, time, sys
from lightlag_client import connect
from lightlag_surface import Surface, drive, PHYSICS, TERRAIN_CODES

DELAY = 3; MAXT = 420
SLIP = {k: (v[0] + v[1]) / 2 for k, v in PHYSICS['slip_base_ranges'].items()}
SLIP_PESS = {k: v[1] for k, v in PHYSICS['slip_base_ranges'].items()}
EFF = 0.8
def log(*a):
    print(*a, flush=True)

def solar(t):
    return 2.8 * EFF * math.sin(math.pi * (t + 56) / (420 + 112))

class Planner:
    def __init__(s, world):
        s.S = Surface(world['cell_m'], world['elevation_cm'], world['terrain'])
        S = s.S; s.nx, s.ny = S.nx, S.ny
        s.cell = S.cell
        bad = [[S.cell_max_slope(i, j) > 0.26 for i in range(S.nx - 1)] for j in range(S.ny - 1)]
        def cellbad(i, j):
            if i < 0 or j < 0 or i >= S.nx - 1 or j >= S.ny - 1: return True
            return bad[j][i]
        def vbad(i, j):  # vertex adjacent to any bad cell
            return any(cellbad(i - a, j - b) for a in (0, 1) for b in (0, 1))
        s.vb = [[vbad(i, j) for i in range(S.nx)] for j in range(S.ny)]
        s.adj = [[] for _ in range(S.nx * S.ny)]
        dirs = [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1),(2,1),(1,2),(-2,1),(-1,2),(2,-1),(1,-2),(-2,-1),(-1,-2)]
        for j in range(S.ny):
            for i in range(S.nx):
                if s.vb[j][i]: continue
                for di, dj in dirs:
                    a, b = i + di, j + dj
                    if not (0 <= a < S.nx and 0 <= b < S.ny) or s.vb[b][a]: continue
                    if abs(di) == 2 or abs(dj) == 2:
                        if s.vb[j + (dj // 2 if abs(dj) == 2 else 0)][i + (di // 2 if abs(di) == 2 else 0)] or s.vb[b - (dj // 2 if abs(dj)==2 else dj) ][a - (di//2 if abs(di)==2 else di)]:
                            continue
                    L = math.hypot(di, dj) * s.cell
                    # sample mid and quarter points
                    t = 0; e = 0; ok = True
                    for f in (0.25, 0.75):
                        x = (i + di * f) * s.cell; y = (j + dj * f) * s.cell
                        h, gx, gy, code = S.sample(x, y)
                        name = TERRAIN_CODES[code]
                        if math.hypot(gx, gy) > 0.26: ok = False
                        grade = (gx * di + gy * dj) * s.cell / L
                        slip = min(0.95, SLIP_PESS[name] + PHYSICS['slip_grade_gain'][name] * max(0, grade))
                        wheel = (L / 2) / (1 - slip)
                        t += wheel / 5.0
                        e += wheel * PHYSICS['drive_cost_per_wheel_m'][name] + 2.0 * max(0, grade) * L / 2
                    if ok:
                        s.adj[j * S.nx + i].append((b * S.nx + a, t, e))
        s.cache = {}

    def nearest_free(s, x, y):
        i0, j0 = int(round(x / s.cell)), int(round(y / s.cell))
        best = None
        for r in range(0, 6):
            for i in range(i0 - r, i0 + r + 1):
                for j in range(j0 - r, j0 + r + 1):
                    if 0 <= i < s.nx and 0 <= j < s.ny and not s.vb[j][i] and s.adj[j * s.nx + i]:
                        d = math.hypot(i * s.cell - x, j * s.cell - y)
                        if best is None or d < best[0]: best = (d, j * s.nx + i)
            if best: return best[1]
        return j0 * s.nx + i0

    def dijkstra(s, src):
        dist = {src: 0.0}; en = {src: 0.0}; prev = {src: None}
        pq = [(0.0, src)]
        while pq:
            d, u = heapq.heappop(pq)
            if d > dist[u]: continue
            for v, t, e in s.adj[u]:
                nd = d + t
                if nd < dist.get(v, 1e18):
                    dist[v] = nd; en[v] = en[u] + e; prev[v] = u; heapq.heappush(pq, (nd, v))
        return dist, en, prev

    def from_point(s, key, x, y):
        if key not in s.cache:
            s.cache[key] = s.dijkstra(s.nearest_free(x, y))
        return s.cache[key]

    def leg(s, key, x0, y0, x1, y1):
        dist, en, prev = s.from_point(key, x0, y0)
        v = s.nearest_free(x1, y1)
        if v not in dist: return 1e9, 1e9
        extra = math.hypot(v % s.nx * s.cell - x1, v // s.nx * s.cell - y1)
        return dist[v] + extra / 4 + 1, en[v] + extra * 0.5

    def path(s, key, x0, y0, x1, y1):
        dist, en, prev = s.from_point(key, x0, y0)
        v = s.nearest_free(x1, y1)
        pts = []
        while v is not None:
            pts.append((v % s.nx * s.cell, v // s.nx * s.cell)); v = prev.get(v)
        pts.reverse()
        pts.append((x1, y1))
        return pts

def plan_route(P, start, t0, bat0, targets, base, sampled, tlimit=2.0):
    """targets: dict id -> target. Returns ordered list of ids."""
    cand = [tg for tg in targets.values() if tg['id'] not in sampled and tg.get('appear_tick', 0) <= t0 + 40]
    nodes = {'S': start, 'B': base}
    for tg in cand: nodes[tg['id']] = (tg['x'], tg['y'])
    T = {}; E = {}
    def leg(a, b):
        if (a, b) not in T:
            ka = ('S', start) if a == 'S' else a
            T[(a, b)], E[(a, b)] = P.leg(ka, *nodes[a], *nodes[b])
        return T[(a, b)], E[(a, b)]
    tmap = {tg['id']: tg for tg in cand}
    FACT = 1.12
    def evaluate(route):
        t = t0; bat = bat0; val = 0; cur = 'S'; minb = bat
        for nid in route + ['B']:
            lt, le = leg(cur, nid)
            nt = int(math.ceil(lt * FACT))
            per = le / max(1, nt)
            for k in range(nt):
                t += 1; bat = min(100, bat + solar(t)) - 0.15 - per
                minb = min(minb, bat)
            if nid != 'B':
                tg = tmap[nid]
                t += 1; bat = min(100, bat + solar(t)) - 2.15
                dl = tg['deadline_tick']
                val += tg['value'] if (dl is None or t <= dl) else tg['late_value']
            cur = nid
        while t < MAXT:
            t += 1; bat = min(100, bat + solar(t)) - 0.15; minb = min(minb, bat)
        feasible = t0 <= MAXT and minb > 6
        tend = t
        return val, feasible, minb
    def ok_time(route):
        t = t0; cur = 'S'
        for nid in route + ['B']:
            lt, _ = leg(cur, nid); t += math.ceil(lt * FACT) + (0 if nid == 'B' else 1); cur = nid
        return t <= MAXT - 6
    def score(route):
        if not ok_time(route): return -1e9
        v, f, mb = evaluate(route)
        return v if f else v - 100 + mb
    # greedy insertion
    route = []
    best = score(route)
    ids = list(tmap)
    improved = True
    while improved:
        improved = False; bestmove = None
        for nid in ids:
            if nid in route: continue
            for pos in range(len(route) + 1):
                r = route[:pos] + [nid] + route[pos:]
                sc = score(r)
                if sc > best + 1e-9 and (bestmove is None or sc > bestmove[0]):
                    bestmove = (sc, r)
        if bestmove:
            best, route = bestmove; improved = True
    # local search
    tend = time.time() + tlimit
    while time.time() < tend:
        r = route[:]
        m = random.random()
        if m < 0.3 and r:
            i = random.randrange(len(r)); x = r.pop(i); r.insert(random.randrange(len(r) + 1), x)
        elif m < 0.5 and len(r) > 2:
            i, j = sorted(random.sample(range(len(r)), 2)); r[i:j + 1] = reversed(r[i:j + 1])
        elif m < 0.8:
            out = [n for n in ids if n not in r]
            if not out: continue
            x = random.choice(out)
            if r and random.random() < 0.5: r.pop(random.randrange(len(r)))
            r.insert(random.randrange(len(r) + 1), x)
        else:
            if r: r.pop(random.randrange(len(r)))
        sc = score(r)
        if sc >= best:
            best, route = sc, r
    return route, best

def main():
    with connect('http://lightlag:8000/mcp') as tools:
        world = tools.map()
        P = Planner(world)
        S = P.S
        base = tuple(world['base'])
        packets = tools.telemetry_log()
        last = packets[-1]
        log('start', last)
        tick = last.get('received_tick', 0)
        targets = {t['id']: t for t in world['targets']}
        sampled = set()
        # estimator
        est = tuple(packets[0]['position']); est_tick = packets[0]['tick']; bias = 0.0
        battery = packets[0]['battery']
        cmds = {}  # exec_tick -> dict(cmd, sent)
        route, sc = plan_route(P, est, tick, battery, targets, base, sampled, 3.0)
        log('route', route, sc)
        cur_path = None; cur_goal = None; path_i = 0
        pending_sample = {}  # exec tick -> target id
        last_replan = tick
        need_replan = False
        sample_attempts = {}
        processed = packets[0]['tick']
        done = False
        while not done:
            # process new packets
            pk = tools.telemetry_log()
            for p in pk:
                if p['tick'] <= processed: continue
                processed = p['tick']
                k = p['tick']
                battery = p['battery']
                c = cmds.get(k)
                stopped = False
                for ev in p.get('events', []) or []:
                    log('EVENT', k, ev)
                    evs = json.dumps(ev)
                    if 'target_discovered' in evs: need_replan = True
                    if 'tilt' in evs or 'stop' in evs or 'boundary' in evs: stopped = True
                if c and c['cmd']['action'] == 'drive' and p.get('wheel_odometry', 0) > 0:
                    h = c['cmd']['heading_deg'] + bias
                    r = drive(S, PHYSICS, est[0], est[1], h, p['wheel_odometry'], SLIP)
                    dx, dy = r['x'] - est[0], r['y'] - est[1]
                    L = math.hypot(dx, dy); vo = p.get('visual_odometry') or L
                    if L > 1e-6: dx, dy = dx * vo / L, dy * vo / L
                    pred = (est[0] + dx, est[1] + dy)
                else:
                    pred = est
                m = p['position']
                rx, ry = m[0] - pred[0], m[1] - pred[1]
                if c and c['cmd']['action'] == 'drive' and p.get('wheel_odometry', 0) > 2:
                    hr = math.radians(c['cmd']['heading_deg'])
                    lat = -rx * math.sin(hr) + ry * math.cos(hr)
                    bias += 0.03 * math.degrees(math.atan2(lat, p['wheel_odometry']))
                    bias = max(-7, min(7, bias))
                g = 0.15
                est = (pred[0] + g * rx, pred[1] + g * ry)
                est_tick = k
                st = set(p.get('sampled_targets') or [])
                if st - sampled:
                    log('sampled', st - sampled, 'at', k)
                sampled |= st
                if k in pending_sample:
                    tid = pending_sample.pop(k)
                    if tid not in sampled:
                        log('SAMPLE FAILED', tid, 'at', k, 'est', est)
                        need_replan = True
                        # correct estimate partially toward target uncertainty: nothing
                if stopped:
                    log('STOP at', k, 'pos', m)
                    est = (0.5 * est[0] + 0.5 * m[0], 0.5 * est[1] + 0.5 * m[1])
                    for t2 in list(cmds):
                        if t2 > k and cmds[t2]['sent'] <= k: del cmds[t2]
                    for t2 in list(pending_sample):
                        if t2 > k: del pending_sample[t2]
                    need_replan = True
                if not p.get('alive', True):
                    log('DEAD'); 
            # refresh targets
            if need_replan or tick - last_replan >= 20:
                world = tools.map()
                for t in world['targets']:
                    if t['id'] not in targets: log('new target', t)
                    targets[t['id']] = t
            # predict forward to the next exec tick
            nexec = max([tick + DELAY + 1] + [t2 + 1 for t2 in cmds])
            ppos = est; pbat = battery
            in_flight_samples = set(pending_sample.values())
            for t2 in range(est_tick + 1, nexec):
                c = cmds.get(t2)
                pbat = min(100, pbat + solar(t2)) - 0.15
                if c and c['cmd']['action'] == 'drive':
                    r = drive(S, PHYSICS, ppos[0], ppos[1], c['cmd']['heading_deg'] + bias, c['cmd']['metres'], SLIP)
                    ppos = (r['x'], r['y']); pbat -= r['energy']
                elif c and c['cmd']['action'] == 'sample':
                    pbat -= 2
            # replan
            if need_replan or tick - last_replan >= 20:
                excl = sampled | in_flight_samples
                P.cache.pop(('S', None), None)
                for kk in [kk for kk in P.cache if isinstance(kk, tuple) and kk[0] == 'S']: del P.cache[kk]
                route, sc = plan_route(P, ppos, nexec, pbat, targets, base, excl, 1.5)
                log('tick', tick, 'replan', route, 'score', sc, 'bat', round(pbat, 1), 'pos', [round(v, 1) for v in ppos])
                cur_goal = None
                need_replan = False; last_replan = tick
            # drop route items already sampled / in-flight
            route = [r_ for r_ in route if r_ not in sampled and r_ not in in_flight_samples]
            goal_id = route[0] if route else 'B'
            gxy = base if goal_id == 'B' else (targets[goal_id]['x'], targets[goal_id]['y'])
            # timeout guard for returning to base
            lt, _ = P.leg(('G', ppos), *ppos, *base) if False else (None, None)
            if goal_id != cur_goal:
                P.cache.pop('tmp', None)
                cur_path = P.path('tmp', ppos[0], ppos[1], gxy[0], gxy[1])
                cur_goal = goal_id; path_i = 0
            # choose command
            d_goal = math.hypot(gxy[0] - ppos[0], gxy[1] - ppos[1])
            cmd = None
            if goal_id != 'B' and d_goal < 1.0:
                cmd = {'action': 'sample'}
                pending_sample[nexec] = goal_id
            elif goal_id == 'B' and d_goal < 1.5:
                cmd = {'action': 'wait'}
            elif pbat < 7:
                cmd = {'action': 'wait'}
            else:
                # lookahead
                while path_i < len(cur_path) - 1 and math.hypot(cur_path[path_i][0] - ppos[0], cur_path[path_i][1] - ppos[1]) < 5.5:
                    path_i += 1
                # if we've drifted to a later point, skip ahead
                best_i = path_i
                for q in range(path_i, min(len(cur_path), path_i + 6)):
                    if math.hypot(cur_path[q][0] - ppos[0], cur_path[q][1] - ppos[1]) < 3: best_i = q + 1
                path_i = min(best_i, len(cur_path) - 1)
                wx, wy = cur_path[path_i]
                dw = math.hypot(wx - ppos[0], wy - ppos[1])
                hd = math.degrees(math.atan2(wy - ppos[1], wx - ppos[0])) - bias
                if path_i == len(cur_path) - 1:
                    # final approach: account slip
                    h, gx_, gy_, code = S.sample(*ppos)
                    sl = SLIP[TERRAIN_CODES[code]]
                    metres = min(5.0, dw / (1 - sl))
                else:
                    metres = 5.0
                # safety check with pessimistic sim
                r = drive(S, PHYSICS, ppos[0], ppos[1], hd + bias, metres, SLIP)
                if r['stop'] == 'tilt':
                    log('tilt risk; shortening')
                    metres = max(0.25, r['wheel'] - 0.75)
                metres = round(max(0.25, min(5.0, metres)), 2)
                cmd = {'action': 'drive', 'heading_deg': round(hd % 360, 2), 'metres': metres}
            try:
                acks = tools.uplink([cmd])
                et = acks[0].get('execute_tick', nexec) if isinstance(acks, list) else nexec
            except Exception as ex:
                log('uplink err', ex); et = None
            if et is not None:
                if et != nexec and nexec in pending_sample:
                    pending_sample[et] = pending_sample.pop(nexec)
                cmds[et] = {'cmd': cmd, 'sent': tick}
            if tick % 10 == 0:
                log('tick', tick, 'est', [round(v, 1) for v in est], 'bat', battery, 'goal', goal_id, round(d_goal, 1), 'bias', round(bias, 2), 'cmd', cmd)
            out = tools.advance(1)
            tick = out['current_tick']
            if out.get('episode_complete'):
                done = True
        log('DONE', tick, 'sampled', sorted(sampled))
        log(tools.telemetry_log()[-1])

if __name__ == '__main__':
    main()
