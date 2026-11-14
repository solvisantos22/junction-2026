import math
import time

EPS = 1e-9


def _angle(a, b):
    denominator = math.sqrt(sum(x * x for x in a) * sum(x * x for x in b))
    if denominator == 0:
        raise ValueError("zero vector")
    cosine = max(-1.0, min(1.0, sum(x * y for x, y in zip(a, b)) / denominator))
    return math.degrees(math.acos(cosine))


def _pointing(image):
    x0, y0, x1, y1 = image["footprint"]
    x, y, z = image["camera"]
    return ((x0 + x1) / 2 - x, (y0 + y1) / 2 - y, -z)


def _covers(image, cell):
    x0, y0, x1, y1 = image["footprint"]
    return x0 - EPS <= cell["x"] <= x1 + EPS and y0 - EPS <= cell["y"] <= y1 + EPS


def _pair_mask(mission, a, b):
    rules = mission["stereo"]
    if a["id"] == b["id"] or abs(a["tick"] - b["tick"]) > rules["max_time_gap"]:
        return 0
    if max(a["gsd"], b["gsd"]) / min(a["gsd"], b["gsd"]) > rules["max_gsd_ratio"] + EPS:
        return 0
    mask = 0
    for i, cell in enumerate(mission["cells"]):
        if not (_covers(a, cell) and _covers(b, cell)):
            continue
        rays = [(im["camera"][0] - cell["x"], im["camera"][1] - cell["y"], im["camera"][2])
                for im in (a, b)]
        conv = _angle(*rays)
        if rules["min_angle"] - EPS <= conv <= rules["max_angle"] + EPS:
            mask |= 1 << i
    return mask


def _enumerate_platform(mission, platform, imgs, idxs, deadline):
    """Return list of tuples of global image indices forming feasible selections."""
    horizon = mission["horizon"]
    downlinks = {e["tick"]: e["capacity"] for e in platform["downlinks"]}
    dl_ticks = sorted(t for t in downlinks if 0 <= t < horizon)
    te = platform["transmit_energy"]
    ce = platform["capture_energy"]
    rate = platform["slew_rate"]
    sea = platform["slew_energy_angle"]
    memory = platform["memory"]
    # group by tick
    by_tick = {}
    for i in idxs:
        by_tick.setdefault(imgs[i]["tick"], []).append(i)
    ticks = sorted(by_tick)
    opps = [(t, sorted(by_tick[t], key=lambda i: imgs[i]["id"])) for t in ticks]
    dirs = {i: _pointing(imgs[i]) for i in idxs}

    def advance(q, bat, frm, to):
        for t in dl_ticks:
            if frm < t <= to:
                cap = downlinks[t]
                n = min(cap, q)
                if n > 0:
                    q -= n
                    bat -= n * te
        return q, bat

    def cap_after(t):
        return sum(max(0, downlinks[u]) for u in dl_ticks if u > t)

    caps_after = {t: cap_after(t) for t, _ in opps}
    results = []
    chosen = []

    def dfs(k, last, q, bat, prev_end, prev_dir):
        if time.time() > deadline:
            return
        if k == len(opps):
            q2, b2 = advance(q, bat, last, horizon - 1)
            if q2 == 0 and b2 >= 0:
                results.append(tuple(chosen))
            return
        t, cands = opps[k]
        q1, b1 = advance(q, bat, last, t)
        # skip
        dfs(k + 1, t, q1, b1, prev_end, prev_dir)
        for i in cands:
            d = dirs[i]
            rot = _angle(prev_dir, d)
            turn_ticks = math.ceil(rot / rate - EPS)
            if t - prev_end < turn_ticks:
                continue
            turn_e = math.ceil(rot / sea - EPS)
            nb = b1 - ce - turn_e
            nq = q1 + 1
            if nq > memory:
                continue
            if nb - nq * te < 0:
                continue
            if caps_after[t] < nq:
                continue
            chosen.append(i)
            dfs(k + 1, t, nq, nb, t + 1, d)
            chosen.pop()

    dfs(0, -1, 0, platform["battery"], platform["initial_tick"], platform["initial_pointing"])
    # maximality filter (single-add dominance)
    pos = {g: j for j, g in enumerate(idxs)}
    masks = {}
    for s in results:
        m = 0
        for g in s:
            m |= 1 << pos[g]
        masks[m] = s
    keep = []
    nloc = len(idxs)
    for m, s in masks.items():
        dominated = False
        for j in range(nloc):
            b = 1 << j
            if not (m & b) and (m | b) in masks:
                dominated = True
                break
        if not dominated:
            keep.append(s)
    if not keep:
        keep = [()]
    return keep


def solve(mission):
    t0 = time.time()
    deadline = t0 + 22.0
    empty = {"images": []}
    try:
        horizon = mission["horizon"]
        cells = mission["cells"]
        ncell = len(cells)
        weights = [c["weight"] for c in cells]
        platforms = mission["platforms"]
        pids = [p["id"] for p in platforms]
        imgs = [im for im in mission["images"]
                if type(im["tick"]) is int and 0 <= im["tick"] < horizon and im["platform"] in pids]
        N = len(imgs)
        pm = [[0] * N for _ in range(N)]
        for i in range(N):
            for j in range(i + 1, N):
                m = _pair_mask(mission, imgs[i], imgs[j])
                pm[i][j] = m
                pm[j][i] = m

        # weight function
        if ncell <= 20:
            tbl = [0] * (1 << ncell)
            for m in range(1, 1 << ncell):
                low = m & (-m)
                tbl[m] = tbl[m ^ low] + weights[low.bit_length() - 1]

            def W(m):
                return tbl[m]
        else:
            cache = {}

            def W(m):
                v = cache.get(m)
                if v is None:
                    v = sum(weights[i] for i in range(ncell) if m >> i & 1)
                    cache[m] = v
                return v

        def intra(s):
            m = 0
            for a in range(len(s)):
                ra = pm[s[a]]
                for b in range(a + 1, len(s)):
                    m |= ra[s[b]]
            return m

        plat_idx = [[i for i in range(N) if imgs[i]["platform"] == pid] for pid in pids]
        sets = []
        for p, plat in enumerate(platforms):
            sets.append(_enumerate_platform(mission, plat, imgs, plat_idx[p], deadline))

        candidates = []  # list of (score, tuple of global idx) improvements
        best = -1

        if len(platforms) == 1:
            for s in sets[0]:
                w = W(intra(s))
                if w > best:
                    best = w
                    candidates.append((w, s))
        elif len(platforms) == 2:
            A, B = sets[0], sets[1]
            Bidx = plat_idx[1]
            bpos = {g: j for j, g in enumerate(Bidx)}
            Tlist = []
            seenT = set()
            UB_B = 0
            for s in B:
                it = intra(s)
                locs = tuple(bpos[g] for g in s)
                Tlist.append((it, locs, s))
                UB_B |= it
            # sort T by own intra weight desc (helps finding good solutions early)
            Tlist.sort(key=lambda x: -W(x[0]))
            Alist = []
            seenA = set()
            for s in A:
                it = intra(s)
                MS = []
                allx = 0
                for g in Bidx:
                    m = 0
                    for a in s:
                        m |= pm[a][g]
                    MS.append(m)
                    allx |= m
                key = (it, tuple(MS))
                if key in seenA:
                    continue
                seenA.add(key)
                ub = W(it | allx | UB_B)
                Alist.append((ub, it, MS, s))
            Alist.sort(key=lambda x: -x[0])
            total = sum(w for w in weights if w > 0)
            for ub, itS, MS, s in Alist:
                if ub <= best:
                    break
                if time.time() > deadline:
                    break
                for itT, locs, tset in Tlist:
                    c = itS | itT
                    for l in locs:
                        c |= MS[l]
                    w = W(c)
                    if w > best:
                        best = w
                        candidates.append((w, tuple(s) + tuple(tset)))
                if best >= total:
                    break
        else:
            cur = [() for _ in platforms]

            def score(sel):
                allimgs = [g for s in sel for g in s]
                return W(intra(allimgs))

            best = score(cur)
            candidates.append((best, ()))
            improved = True
            while improved and time.time() < deadline:
                improved = False
                for p in range(len(platforms)):
                    for s in sets[p]:
                        trial = cur[:]
                        trial[p] = s
                        w = score(trial)
                        if w > best:
                            best = w
                            cur = trial
                            improved = True
                            candidates.append((w, tuple(g for ss in cur for g in ss)))

        try:
            from stereo_survey.verify import verify as _verify
        except Exception:
            _verify = None

        for w, sel in reversed(candidates):
            plan = {"images": [imgs[g]["id"] for g in sel]}
            if _verify is None:
                return plan
            try:
                res = _verify(mission, plan)
                if res.get("valid"):
                    return plan
            except Exception:
                return plan
        return empty
    except Exception:
        return empty
