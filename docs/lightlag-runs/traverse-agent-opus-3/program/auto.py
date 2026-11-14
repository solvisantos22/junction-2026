import sys, math, json, time, pickle, traceback
sys.path.insert(0, '/tmp/ll'); sys.path.insert(0, '/app')
from plan import *
from opt import optimize, evaluate
from lightlag_surface import drive as sdrive
from lightlag_client import connect

SLIPB = {'bedrock': 0.03, 'regolith': 0.085, 'sand': 0.25, 'rocks': 0.18}
DELAY = 3; MAXT = 420
BX, BY = w['base']

def log(*a):
    print(*a, flush=True)

# dist fields per goal: dijkstra from goal; prev pointer leads from cell toward goal
FIELDS = {}
def field(gid, x, y):
    if gid not in FIELDS:
        FIELDS[gid] = dijkstra(x, y)
    return FIELDS[gid]

def seg_clear(x0, y0, x1, y1):
    n = int(math.hypot(x1 - x0, y1 - y0) / 1.5) + 1
    for k in range(n + 1):
        x = x0 + (x1 - x0) * k / n; y = y0 + (y1 - y0) * k / n
        i, j = cellof(x, y)
        if blocked[j][i] and S.cell_max_slope(i, j) > 0.3:
            return False
    return True

def steer_point(gid, gx, gy, px, py):
    """Point to head toward from (px,py) to reach goal."""
    if math.hypot(gx - px, gy - py) < 12 and seg_clear(px, py, gx, gy):
        return gx, gy, True
    dist, prev = field(gid, gx, gy)
    c = cellof(px, py)
    if c not in dist:
        best = None
        for di in range(-3, 4):
            for dj in range(-3, 4):
                k = (c[0] + di, c[1] + dj)
                if k in dist:
                    dd = math.hypot(di, dj)
                    if best is None or dd < best[0]: best = (dd, k)
        if best is None:
            return gx, gy, True
        c = best[1]
        return c[0] * 5 + 2.5, c[1] * 5 + 2.5, False
    chain = [c]
    k = c
    for _ in range(6):
        if k not in prev: break
        k = prev[k]; chain.append(k)
    pt = (c[0] * 5 + 2.5, c[1] * 5 + 2.5)
    for k in chain[1:]:
        q = (k[0] * 5 + 2.5, k[1] * 5 + 2.5)
        if math.hypot(q[0] - px, q[1] - py) > 14: break
        if seg_clear(px, py, q[0], q[1]): pt = q
        else: break
    if len(chain) == 1:
        return gx, gy, True
    return pt[0], pt[1], False

class EKF:
    def __init__(s, x, y):
        s.x = x; s.y = y; s.b = 0.0
        s.P = [[0.0001, 0, 0], [0, 0.0001, 0], [0, 0, math.radians(5) ** 2 / 3]]
    def predict(s, h, wheel, g):
        if wheel <= 0: return
        r = sdrive(S, PHYSICS, s.x, s.y, h + math.degrees(s.b), wheel, SLIPB)
        dx, dy = r['x'] - s.x, r['y'] - s.y
        gm = math.hypot(dx, dy)
        if gm > 1e-6 and g is not None:
            dx *= g / gm; dy *= g / gm
        if g is None: g = gm
        s.x += dx; s.y += dy
        # jacobian wrt b: rotate
        Jx, Jy = -dy, dx
        P = s.P
        # P = F P F^T, F = [[1,0,Jx],[0,1,Jy],[0,0,1]]
        F = [[1, 0, Jx], [0, 1, Jy], [0, 0, 1]]
        FP = [[sum(F[i][k] * P[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
        P = [[sum(FP[i][k] * F[j][k] for k in range(3)) for j in range(3)] for i in range(3)]
        q = (0.05 * g) ** 2 * 0.5 + (math.radians(1.5) * g) ** 2 + 0.15 ** 2
        P[0][0] += q; P[1][1] += q
        P[2][2] += math.radians(0.2) ** 2
        s.P = P
    def update(s, mx, my, r=1.0):
        P = s.P
        for axis, m in ((0, mx), (1, my)):
            st = [s.x, s.y, s.b]
            S_ = P[axis][axis] + r * r
            K = [P[i][axis] / S_ for i in range(3)]
            innov = m - st[axis]
            if abs(innov) > 5: innov = max(-5, min(5, innov))
            s.x += K[0] * innov; s.y += K[1] * innov; s.b += K[2] * innov
            P = [[P[i][j] - K[i] * P[axis][j] for j in range(3)] for i in range(3)]
        s.P = P
    def std(s):
        return math.sqrt(max(s.P[0][0], s.P[1][1]))

def main():
    with connect("http://lightlag:8000/mcp") as tools:
        world = tools.map()
        pk = tools.telemetry_log()
        p0 = pk[0]
        ekf = EKF(p0['position'][0], p0['position'][1])
        log('start', p0)
        D = pickle.load(open('/tmp/ll/D.pkl', 'rb'))
        targets = {t['id']: t for t in world['targets']}
        info = {t['id']: (t['value'], t['deadline_tick'], t['late_value']) for t in targets.values()}
        sampled = set()  # confirmed
        pending = {}  # tid -> exec tick of sample
        route, best = optimize(D, info, 'base', 4, 405, iters=150000, seed=1)
        for sd in (2, 3):
            r2, b2 = optimize(D, info, 'base', 4, 405, iters=150000, seed=sd)
            if b2 > best: route, best = r2, b2
        log('route', best, route)
        sent = []  # dicts: exec, send, cmd, cancelled
        last_pkt_tick = 0
        cur = 0
        processed = 0
        battery = 100.0
        last_replan = 0
        need_replan = False
        at_base = False
        while True:
            out = tools.advance(1)
            cur = out['current_tick']
            if out.get('episode_complete'):
                log('complete', out); break
            pkts = tools.telemetry_log()
            newp = pkts[processed:]
            processed = len(pkts)
            for p in newp:
                k = p['tick']
                if k == 0: continue
                ev = p.get('events') or []
                if ev: log('events', k, ev)
                cmd = next((c for c in sent if c['exec'] == k and not c['cancelled']), None)
                wo = p.get('wheel_odometry') or 0
                vo = p.get('visual_odometry')
                if wo and wo > 0:
                    ekf.predict(p['heading_deg'], wo, vo)
                ekf.update(p['position'][0], p['position'][1])
                battery = p['battery']
                last_pkt_tick = k
                for c in sent:
                    if c['exec'] <= k: c['done'] = True
                st = set(p.get('sampled_targets') or [])
                for tid in list(pending):
                    if tid in st:
                        sampled.add(tid); pending.pop(tid); log('sampled', tid, 'at', k)
                    elif pending[tid] <= k:
                        log('sample FAILED', tid, k); pending.pop(tid)
                        if tid not in route: route.insert(0, tid)
                sampled |= st
                es = json.dumps(ev)
                if 'tilt' in es or 'stop' in es or 'safety' in es:
                    for c in sent:
                        if c['send'] <= k and c['exec'] > k: c['cancelled'] = True
                    log('safety stop at', k)
                if 'discover' in es:
                    need_replan = True
                if not p.get('alive', True):
                    log('DEAD'); return
            if need_replan:
                world = tools.map()
                for t in world['targets']:
                    if t['id'] not in targets:
                        targets[t['id']] = t
                        info[t['id']] = (t['value'], t['deadline_tick'], t['late_value'])
                        dist, prev = dijkstra(t['x'], t['y'])
                        FIELDS[t['id']] = (dist, prev)
                        for a in ['base'] + list(targets):
                            ax, ay = (BX, BY) if a == 'base' else (targets[a]['x'], targets[a]['y'])
                            D[(t['id'], a)] = dist.get(cellof(ax, ay), 1e9)
                            D[(a, t['id'])] = D[(t['id'], a)]
                        log('discovered', t)
            # predict position at exec time
            exec_tick = max(cur + DELAY + 1, max([c['exec'] for c in sent], default=0) + 1)
            px, py, pb = ekf.x, ekf.y, ekf.b
            for c in sent:
                if c['exec'] > last_pkt_tick and not c['cancelled'] and c['cmd']['action'] == 'drive':
                    r = sdrive(S, PHYSICS, px, py, c['cmd']['heading_deg'] + math.degrees(pb), c['cmd']['metres'], SLIPB)
                    px, py = r['x'], r['y']
            inflight_samples = [c['tid'] for c in sent if c.get('tid') and c['exec'] > last_pkt_tick and not c['cancelled']]
            active = [t for t in route if t not in sampled and t not in pending and t not in inflight_samples]
            route = active
            # replan
            if (need_replan or cur - last_replan > 30) and exec_tick < 380:
                need_replan = False; last_replan = cur
                dist, _ = dijkstra(px, py)
                Dp = dict(D)
                for a in list(targets) + ['base']:
                    ax, ay = (BX, BY) if a == 'base' else (targets[a]['x'], targets[a]['y'])
                    Dp[('here', a)] = dist.get(cellof(ax, ay), 1e9)
                avail = {k: v for k, v in info.items() if k not in sampled and k not in pending and k not in inflight_samples
                         and targets[k].get('appear_tick', 0) <= exec_tick + 5}
                base_v = evaluate(route, Dp, avail, 'here', exec_tick, 408)[0]
                nr, nb = optimize(Dp, avail, 'here', exec_tick, 408, init=route, iters=40000, seed=cur)
                if nb > base_v + 0.01:
                    log('replan', cur, base_v, '->', nb, nr); route = nr
            # time check: go home if needed
            dist_b, _ = field('base', BX, BY)
            tb = dist_b.get(cellof(px, py), 50)
            if route:
                g = route[0]
                tg = targets[g]
                dg, _ = field(g, tg['x'], tg['y'])
                tgo = dg.get(cellof(px, py), 50) * 1.1 + 2 + D[(g, 'base')] * 1.1
                if exec_tick + tgo > 412:
                    log('dropping', g, 'time'); route.pop(0); continue_flag = True
            if route:
                g = route[0]; gx, gy = targets[g]['x'], targets[g]['y']
            else:
                g = 'base'; gx, gy = BX, BY
            d = math.hypot(gx - px, gy - py)
            cmd = None; tid = None
            if g != 'base' and d < 0.9:
                if ekf.std() < 0.9:
                    cmd = {'action': 'sample'}; tid = g
                    pending_candidate = g
                else:
                    cmd = {'action': 'wait'}
            elif g == 'base' and d < 1.5:
                cmd = {'action': 'wait'}
            else:
                sx, sy, direct = steer_point(g, gx, gy, px, py)
                hd = math.degrees(math.atan2(sy - py, sx - px))
                dd = math.hypot(sx - px, sy - py)
                name = S.terrain(px, py)
                m = dd / (1 - SLIPB[name] - 0.02) if direct else 5.0
                m = max(0.3, min(5.0, m))
                # energy guard
                sun = 2.24 * math.sin(math.pi * (exec_tick + 56) / 532)
                if battery < 6 and sun < 2.0:
                    cmd = {'action': 'wait'}
                else:
                    cmd = {'action': 'drive', 'heading_deg': round((hd - math.degrees(pb)) % 360, 2), 'metres': round(m, 2)}
            try:
                ack = tools.uplink([cmd])
                ex = exec_tick
                try:
                    a0 = ack[0] if isinstance(ack, list) else (ack.get('commands') or ack.get('acks') or [ack])[0]
                    ex = int(a0.get('execute_tick', exec_tick))
                except Exception:
                    log('ack?', ack)
            except Exception as e:
                log('uplink err', e); continue
            sent.append({'exec': ex, 'send': cur, 'cmd': cmd, 'cancelled': False, 'tid': tid})
            if tid:
                pending[tid] = ex
            if cur % 5 == 0 or tid:
                log(cur, 'ex', ex, 'est', round(ekf.x, 1), round(ekf.y, 1), 'b', round(math.degrees(ekf.b), 2), 'sd', round(ekf.std(), 2),
                    'pred', round(px, 1), round(py, 1), 'goal', g, round(d, 1), 'bat', battery, cmd, 'route', route[:4], 'n_s', len(sampled))

if __name__ == '__main__':
    try:
        main()
    except Exception:
        traceback.print_exc()
