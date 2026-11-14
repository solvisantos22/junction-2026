The program enumerates each camera's feasible sequences, then searches exactly over pairs of sequences, using a bit-parallel scoring trick for the cross-camera step.

**How it works**

1. **Pair masks.** It precomputes `pair_mask` for every pair of images. Images that form no valid stereo pair with any other image are dropped, since they can only cost resources.

2. **Per-camera enumeration.** For each camera, a depth-first search walks the opportunities in tick order and picks skip or one frame at each.
   - It simulates the validator's rules exactly: downlink before capture, slew ticks and energy, memory, battery and final return of all data.
   - Battery only decreases, so a branch is cut as soon as it goes negative.

3. **Dominance filter.** Removing an image never makes a plan infeasible, and adding one never lowers science. So only maximal sequences are kept: those where no frame can be added at a skipped opportunity.

4. **Exact two-camera search.**
   - Sequences of camera B are indexed as bits of large Python integers.
   - For a fixed camera-A sequence, the program builds, for each cell, the set of B-sequences that would reconstruct it. This combines A's own pairs, B's own pairs and A×B cross pairs.
   - These sets are added together with weights using bit-sliced binary addition, which scores all B sequences at once.
   - A top-down bit scan then finds the best B sequence.
   - A-sequences are processed in decreasing order of an optimistic bound, and the loop stops when the bound cannot beat the best score.

5. **Fallbacks.**
   - Non-integer weights use a pruned double loop.
   - A platform count other than two uses coordinate descent.
   - The search stops at a deadline about 24 seconds after start.
   - The final plan is checked with the supplied `verify`; if it fails or anything crashes, the program returns the empty plan, which is always valid.

```python
import math
import time

try:
    from stereo_survey.geometry import angle, pointing, pair_mask, EPS
except Exception:  # pragma: no cover
    EPS = 1e-9

    def angle(a, b):
        denominator = math.sqrt(sum(x * x for x in a) * sum(x * x for x in b))
        if denominator == 0:
            raise ValueError("zero vector")
        cosine = max(-1.0, min(1.0, sum(x * y for x, y in zip(a, b)) / denominator))
        return math.degrees(math.acos(cosine))

    def pointing(image):
        x0, y0, x1, y1 = image["footprint"]
        x, y, z = image["camera"]
        return ((x0 + x1) / 2 - x, (y0 + y1) / 2 - y, -z)

    def _covers(image, cell):
        x0, y0, x1, y1 = image["footprint"]
        return x0 - EPS <= cell["x"] <= x1 + EPS and y0 - EPS <= cell["y"] <= y1 + EPS

    def pair_mask(mission, a, b):
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
            conv = angle(*rays)
            if rules["min_angle"] - EPS <= conv <= rules["max_angle"] + EPS:
                mask |= 1 << i
        return mask

try:
    from stereo_survey.verify import verify as _verify
except Exception:  # pragma: no cover
    _verify = None


def solve(mission):
    t0 = time.time()
    try:
        plan = _solve(mission, t0)
    except Exception:
        plan = {"images": []}
    try:
        if _verify is not None and plan["images"]:
            r = _verify(mission, plan)
            if not r.get("valid"):
                plan = {"images": []}
    except Exception:
        plan = {"images": []}
    return plan


def _solve(mission, t0):
    deadline = t0 + 24.0
    cells = mission["cells"]
    nc = len(cells)
    w = [c["weight"] for c in cells]
    horizon = mission["horizon"]
    platforms = mission["platforms"]
    pids = [p["id"] for p in platforms]
    seen = set()
    images = []
    for im in mission["images"]:
        if type(im.get("tick")) is not int or not (0 <= im["tick"] < horizon):
            continue
        if im.get("platform") not in pids or im["id"] in seen:
            continue
        seen.add(im["id"])
        images.append(im)
    N = len(images)
    if N == 0:
        return {"images": []}

    # weight function via chunk tables
    tables = []
    for st in range(0, nc, 10):
        size = min(10, nc - st)
        tab = [0] * (1 << size)
        for m in range(1, 1 << size):
            low = m & -m
            b = low.bit_length() - 1
            tab[m] = tab[m ^ low] + w[st + b]
        tables.append((st, (1 << size) - 1, tab))

    if len(tables) == 2:
        (s0, m0, t0_), (s1, m1, t1_) = tables

        def wt(m):
            return t0_[m & m0] + t1_[(m >> s1) & m1]
    else:
        def wt(m):
            s = 0
            for st, mk, tab in tables:
                s += tab[(m >> st) & mk]
            return s

    pm = [[0] * N for _ in range(N)]
    for i in range(N):
        for j in range(i + 1, N):
            try:
                m = pair_mask(mission, images[i], images[j])
            except Exception:
                m = 0
            pm[i][j] = m
            pm[j][i] = m

    dirs = [None] * N
    for i in range(N):
        try:
            d = pointing(images[i])
            if sum(x * x for x in d) == 0:
                d = None
        except Exception:
            d = None
        dirs[i] = d

    useful = [i for i in range(N) if dirs[i] is not None and any(pm[i])]

    def enum_platform(p, idxs):
        memory = p["memory"]
        ce = p["capture_energy"]
        te = p["transmit_energy"]
        sr = p["slew_rate"]
        sea = p["slew_energy_angle"]
        init_tick = p["initial_tick"]
        init_dir = p["initial_pointing"]
        dl = {e["tick"]: e["capacity"] for e in p["downlinks"]}
        dlt = []
        for t in range(horizon):
            c = dl.get(t, 0)
            if c > 0:
                dlt.append((t, c))
        groups = {}
        for i in idxs:
            groups.setdefault(images[i]["tick"], []).append(i)
        ticks = sorted(groups)
        cost = {}

        def get_cost(prev, i):
            key = (prev, i)
            if key in cost:
                return cost[key]
            pd = init_dir if prev < 0 else dirs[prev]
            try:
                r = angle(pd, dirs[i])
                v = (math.ceil(r / sr - EPS), math.ceil(r / sea - EPS))
            except Exception:
                v = None
            cost[key] = v
            return v

        def apply_dl(tf, tt, q, b):
            for t, c in dlt:
                if t < tf:
                    continue
                if t > tt or q <= 0:
                    break
                n = min(c, q)
                q -= n
                b -= n * te
            return q, b

        out = []
        m = len(ticks)
        chosen = []

        def rec(gi, t, b, pe, pd, q):
            if gi == m:
                q2, b2 = apply_dl(t, horizon - 1, q, b)
                if q2 == 0 and b2 >= 0:
                    out.append(tuple(chosen))
                return
            tick = ticks[gi]
            q2, b2 = apply_dl(t, tick, q, b)
            if b2 < 0:
                return
            rec(gi + 1, tick + 1, b2, pe, pd, q2)
            if q2 + 1 > memory:
                return
            for i in groups[tick]:
                c = get_cost(pd, i)
                if c is None:
                    continue
                turn, en = c
                if tick - pe < turn:
                    continue
                nb = b2 - ce - en
                if nb < 0:
                    continue
                chosen.append(i)
                rec(gi + 1, tick + 1, nb, tick + 1, i, q2 + 1)
                chosen.pop()

        if p["battery"] >= 0:
            rec(0, 0, p["battery"], init_tick, -1, 0)
        # maximal filter
        sset = set(frozenset(s) for s in out)
        res = []
        for s in out:
            fs = frozenset(s)
            used = set(images[i]["tick"] for i in s)
            dom = False
            for g in ticks:
                if g in used:
                    continue
                for x in groups[g]:
                    if (fs | {x}) in sset:
                        dom = True
                        break
                if dom:
                    break
            if not dom:
                res.append(s)
        return res

    seqs = []
    for p in platforms:
        idxs = [i for i in useful if images[i]["platform"] == p["id"]]
        seqs.append(enum_platform(p, idxs))
    if any(len(s) == 0 for s in seqs):
        # some platform has no feasible set (even empty); best we can do is empty plan
        return {"images": []}

    def intra(s):
        m = 0
        L = len(s)
        for x in range(L):
            row = pm[s[x]]
            for y in range(x + 1, L):
                m |= row[s[y]]
        return m

    intm = [[intra(s) for s in sl] for sl in seqs]
    intw = all(type(x) is int and x >= 0 for x in w)

    chosen = []
    if len(seqs) == 2:
        a_i, b_i = (0, 1) if len(seqs[0]) <= len(seqs[1]) else (1, 0)
        As, Bs = seqs[a_i], seqs[b_i]
        intA, intB = intm[a_i], intm[b_i]
        Bimgs = sorted(set(i for s in Bs for i in s))
        Aimgs = sorted(set(i for s in As for i in s))
        loc = {i: k for k, i in enumerate(Bimgs)}
        nBi = len(Bimgs)
        UB = 0
        for m in intB:
            UB |= m
        Ainfo = []
        for k, s in enumerate(As):
            XA = [0] * nBi
            for a in s:
                row = pm[a]
                for bl in range(nBi):
                    XA[bl] |= row[Bimgs[bl]]
            cA = 0
            for x in XA:
                cA |= x
            Ainfo.append((wt(intA[k] | cA | UB), k, XA, cA))
        Ainfo.sort(key=lambda t: -t[0])
        best = -1
        bestA, bestB = 0, 0
        if intw:
            nB = len(Bs)
            contains = [0] * nBi
            intcell = [0] * nc
            cbits = [[] for _ in range(nBi)]
            ibits = [[] for _ in range(nc)]
            for k, s in enumerate(Bs):
                for i in s:
                    cbits[loc[i]].append(k)
                m = intB[k]
                while m:
                    low = m & -m
                    ibits[low.bit_length() - 1].append(k)
                    m ^= low
            for bl in range(nBi):
                v = 0
                for k in cbits[bl]:
                    v |= 1 << k
                contains[bl] = v
            for ci in range(nc):
                v = 0
                for k in ibits[ci]:
                    v |= 1 << k
                intcell[ci] = v
            total = sum(w)
            L = max(1, total.bit_length())
            ALL = (1 << nB) - 1
            for cnt, (bound, k, XA, cA) in enumerate(Ainfo):
                if bound <= best:
                    break
                if (cnt & 31) == 0 and time.time() > deadline:
                    break
                base = intA[k]
                nbase = ~base
                cov = intcell[:]
                for bl in range(nBi):
                    x = XA[bl] & nbase
                    if x:
                        c = contains[bl]
                        while x:
                            low = x & -x
                            ci = low.bit_length() - 1
                            cov[ci] |= c
                            x ^= low
                S = [0] * L
                for ci in range(nc):
                    if (base >> ci) & 1:
                        continue
                    X = cov[ci]
                    ww = w[ci]
                    if not X or not ww:
                        continue
                    j = 0
                    while ww:
                        if ww & 1:
                            carry = X
                            kk = j
                            while carry and kk < L:
                                s_ = S[kk]
                                S[kk] = s_ ^ carry
                                carry = s_ & carry
                                kk += 1
                        ww >>= 1
                        j += 1
                cand = ALL
                val = 0
                for kk in range(L - 1, -1, -1):
                    t = cand & S[kk]
                    if t:
                        cand = t
                        val |= 1 << kk
                score = wt(base) + val
                if score > best:
                    best = score
                    bestA = k
                    bestB = (cand & -cand).bit_length() - 1
        else:
            crossAll = {}
            for b in Bimgs:
                v = 0
                for a in Aimgs:
                    v |= pm[b][a]
                crossAll[b] = v
            Binfo = []
            for k, s in enumerate(Bs):
                cB = 0
                for b in s:
                    cB |= crossAll[b]
                Binfo.append((wt(intB[k] | cB), k, cB))
            Binfo.sort(key=lambda t: -t[0])
            stop = False
            for bound, k, XA, cA in Ainfo:
                if bound <= best or stop:
                    break
                if time.time() > deadline:
                    break
                ia = intA[k]
                for cnt, (bb, kb, cB) in enumerate(Binfo):
                    if (cnt & 255) == 0 and time.time() > deadline:
                        stop = True
                        break
                    ib = intB[kb]
                    if wt(ia | ib | (cA & cB)) <= best:
                        continue
                    m = ia | ib
                    for b in Bs[kb]:
                        m |= XA[loc[b]]
                    sc = wt(m)
                    if sc > best:
                        best = sc
                        bestA, bestB = k, kb
        chosen = list(As[bestA]) + list(Bs[bestB])
    else:
        def evalsel(lst):
            m = 0
            for x in range(len(lst)):
                row = pm[lst[x]]
                for y in range(x + 1, len(lst)):
                    m |= row[lst[y]]
            return wt(m)

        cur = [max(range(len(sl)), key=lambda k, p=p: wt(intm[p][k])) for p, sl in enumerate(seqs)]

        def union(cur, skip=None, alt=None):
            lst = []
            for p, k in enumerate(cur):
                if p == skip:
                    lst.extend(seqs[p][alt])
                else:
                    lst.extend(seqs[p][k])
            return lst

        best = evalsel(union(cur))
        improved = True
        while improved and time.time() < deadline:
            improved = False
            for p in range(len(seqs)):
                for k in range(len(seqs[p])):
                    if time.time() > deadline:
                        break
                    sc = evalsel(union(cur, p, k))
                    if sc > best:
                        best = sc
                        cur[p] = k
                        improved = True
        chosen = union(cur)

    return {"images": [images[i]["id"] for i in chosen]}
```