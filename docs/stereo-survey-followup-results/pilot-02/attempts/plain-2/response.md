The program enumerates each camera's feasible schedules exactly, keeps only the ones that cannot be improved by adding another image, and then searches every pairing of the two cameras' schedules. I have not run it. As a safeguard, every returned plan is first checked with the supplied `verify`, and the program falls back to an empty plan if none pass.

**How it works:**

1. **Stereo masks.** It computes the stereo mask for every pair of images, using the same rules as the public `geometry.py`. Images that pair with nothing can never add science, so the search ignores them.
2. **Per-camera schedules.** For each camera, a depth-first search tries every option at each opportunity: skip, or take one frame. It replays the validator's rules as it goes: downlink before capture, slew time and slew energy, memory, battery, and every frame returned by the horizon. Dead branches are cut early because battery never increases. The search stops at 400,000 nodes or 9 seconds per camera.
3. **Keep only maximal schedules.** Adding a returned image can only add stereo pairs, so science never drops when a schedule grows. A feasible schedule that is a strict subset of another feasible schedule can therefore be dropped. Only the maximal schedules are kept, compared on their useful images.
4. **Two-camera search.** It pairs every kept schedule of one camera with every kept schedule of the other:
   - For each schedule of the smaller side, it builds lookup tables for the cross-camera stereo cells, so each pairing costs a few lookups.
   - It visits schedules in order of an upper bound on their best possible score and stops once that bound cannot beat the best found.
   - It also stops at the maximum possible weight or at about 26 seconds.
5. **Final check.** Each candidate plan is checked with the supplied `verify`, newest first, and the first valid one is returned. If no candidate passes, it returns an empty plan, which is always valid.
6. **Other platform counts.** With one platform, or more than two, it uses coordinate ascent instead of the exact pairing search.

```python
import math
import time

EPS = 1e-9


def _angle(a, b):
    den = math.sqrt(sum(x * x for x in a) * sum(x * x for x in b))
    if den == 0:
        raise ValueError("zero vector")
    c = max(-1.0, min(1.0, sum(x * y for x, y in zip(a, b)) / den))
    return math.degrees(math.acos(c))


def _pointing(im):
    x0, y0, x1, y1 = im["footprint"]
    x, y, z = im["camera"]
    return ((x0 + x1) / 2 - x, (y0 + y1) / 2 - y, -z)


def _covers(im, cell):
    x0, y0, x1, y1 = im["footprint"]
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


def _popcount(m):
    return bin(m).count("1")


def _maximal(masks):
    feas = set(masks)
    levels = {}
    for m in feas:
        levels.setdefault(_popcount(m), set()).add(m)
    dominated = set()
    if not levels:
        return []
    maxp = max(levels)
    for pc in range(maxp, 0, -1):
        cur = levels.get(pc)
        if not cur:
            continue
        nxt = levels.setdefault(pc - 1, set())
        for m in list(cur):
            mm = m
            while mm:
                b = mm & -mm
                mm ^= b
                s = m ^ b
                if s not in dominated:
                    dominated.add(s)
                    nxt.add(s)
    return [m for m in feas if m not in dominated]


def solve(mission):
    t_start = time.time()
    deadline = t_start + 26.0
    try:
        return _solve(mission, t_start, deadline)
    except Exception:
        return {"images": []}


def _solve(mission, t_start, deadline):
    cells = mission["cells"]
    nc = len(cells)
    H = mission["horizon"]
    plats = mission["platforms"]
    pnames = [p["id"] for p in plats]
    pset = set(pnames)
    imgs = [im for im in mission["images"]
            if type(im["tick"]) is int and 0 <= im["tick"] < H and im["platform"] in pset]
    n = len(imgs)
    pm = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            try:
                m = _pair_mask(mission, imgs[i], imgs[j])
            except Exception:
                m = 0
            pm[i][j] = m
            pm[j][i] = m
    useful = [any(pm[i]) for i in range(n)]
    dirs = [_pointing(im) for im in imgs]

    wts = [c["weight"] for c in cells]
    nwt = max(1, (nc + 9) // 10)
    tables = []
    for k in range(nwt):
        T = [0] * 1024
        for m in range(1, 1024):
            lb = m & -m
            bi = lb.bit_length() - 1 + 10 * k
            T[m] = T[m ^ lb] + (wts[bi] if bi < nc else 0)
        tables.append(T)

    def W(m):
        s = 0
        k = 0
        while m:
            s += tables[k][m & 1023]
            m >>= 10
            k += 1
        return s

    total_w = W((1 << nc) - 1)

    def intra(globs):
        m = 0
        L = len(globs)
        for a in range(L):
            ra = pm[globs[a]]
            for b in range(a + 1, L):
                m |= ra[globs[b]]
        return m

    # ---- per-platform enumeration ----
    plat_data = []
    for p in plats:
        name = p["id"]
        idxs = [i for i in range(n) if imgs[i]["platform"] == name]
        dl = {}
        for e in p["downlinks"]:
            dl[e["tick"]] = e["capacity"]
        dl_list = sorted((u, c) for u, c in dl.items() if type(u) is int and 0 <= u < H)
        groups = {}
        for i in idxs:
            groups.setdefault(imgs[i]["tick"], []).append(i)
        ticks = sorted(groups)
        G = [groups[t] for t in ticks]
        loc = [i for i in idxs if useful[i]]
        bit = {i: 1 << k for k, i in enumerate(loc)}
        te = p["transmit_energy"]
        ce = p["capture_energy"]
        sr = p["slew_rate"]
        sea = p["slew_energy_angle"]
        mem = p["memory"]
        res = {}
        nodes = [0]
        plat_deadline = min(deadline, time.time() + 9.0)

        def adv(q, bat, upto, t):
            for u, c in dl_list:
                if upto < u <= t and q > 0:
                    k = c if c < q else q
                    if k > 0:
                        q -= k
                        bat -= k * te
            return q, bat

        NG = len(G)

        def dfs(k, q, bat, prev_end, prev_dir, upto, chosen, pmask):
            nodes[0] += 1
            if nodes[0] > 400000 or (nodes[0] & 1023) == 0 and time.time() > plat_deadline:
                if nodes[0] > 400000:
                    return
                if time.time() > plat_deadline:
                    nodes[0] = 10 ** 9
                    return
            if k == NG:
                q2, b2 = adv(q, bat, upto, H - 1)
                if q2 == 0 and b2 >= 0 and pmask not in res:
                    res[pmask] = list(chosen)
                return
            dfs(k + 1, q, bat, prev_end, prev_dir, upto, chosen, pmask)
            t = ticks[k]
            q1, b1 = adv(q, bat, upto, t)
            if b1 < 0:
                return
            for i in G[k]:
                d = dirs[i]
                try:
                    rot = _angle(prev_dir, d)
                except Exception:
                    continue
                tt = math.ceil(rot / sr - EPS)
                if t - prev_end < tt:
                    continue
                ten = math.ceil(rot / sea - EPS)
                b2 = b1 - ce - ten
                if b2 < 0:
                    continue
                q2 = q1 + 1
                if q2 > mem:
                    continue
                chosen.append(i)
                dfs(k + 1, q2, b2, t + 1, d, t, chosen, pmask | bit.get(i, 0))
                chosen.pop()

        if p["battery"] >= 0:
            dfs(0, 0, p["battery"], p["initial_tick"], p["initial_pointing"], -1, [], 0)
        maxm = _maximal(res.keys())
        entries = []
        for m in maxm:
            globs = [loc[k] for k in range(len(loc)) if (m >> k) & 1]
            entries.append((m, globs, intra(globs), res[m]))
        plat_data.append({"loc": loc, "entries": entries})

    if any(not d["entries"] for d in plat_data) or not plat_data:
        return {"images": []}

    cands = []  # list of full selections (global idx lists), increasing quality

    if len(plat_data) == 2:
        dA, dB = plat_data
        if len(dA["entries"]) > len(dB["entries"]):
            dA, dB = dB, dA
        Bglob = dB["loc"]
        nB = len(Bglob)
        ubB = 0
        for e in dB["entries"]:
            ubB |= e[2]
        fast = nB <= 16 and nc <= 20
        Bentries = [(e[2], e[0] & 255, (e[0] >> 8) & 255, bi, e[0])
                    for bi, e in enumerate(dB["entries"])]
        Alist = []
        for ai, e in enumerate(dA["entries"]):
            globs = e[1]
            c = []
            allC = 0
            for j in Bglob:
                v = 0
                for i in globs:
                    v |= pm[i][j]
                c.append(v)
                allC |= v
            ub = W(e[2] | allC | ubB)
            Alist.append((ub, ai, c))
        Alist.sort(key=lambda x: -x[0])
        best = -1
        bestpair = None
        if fast:
            WL = tables[0]
            WH = tables[1] if len(tables) > 1 else [0] * 1024
        for ub, ai, c in Alist:
            if ub <= best or best >= total_w:
                break
            if time.time() > deadline:
                break
            base = dA["entries"][ai][2]
            if fast:
                cc = c + [0] * (16 - len(c))
                t0 = [0] * 256
                t1 = [0] * 256
                for m in range(1, 256):
                    lb = m & -m
                    b = lb.bit_length() - 1
                    t0[m] = t0[m ^ lb] | cc[b]
                    t1[m] = t1[m ^ lb] | cc[8 + b]
                for ib, l, h, bi, _ in Bentries:
                    m = base | ib | t0[l] | t1[h]
                    w = WL[m & 1023] + WH[m >> 10]
                    if w > best:
                        best = w
                        bestpair = (ai, bi)
                        cands.append(dA["entries"][ai][3] + dB["entries"][bi][3])
                        if best >= total_w:
                            break
            else:
                for ib, l, h, bi, bm in Bentries:
                    m = base | ib
                    k = 0
                    mm = bm
                    while mm:
                        if mm & 1:
                            m |= c[k]
                        mm >>= 1
                        k += 1
                    w = W(m)
                    if w > best:
                        best = w
                        bestpair = (ai, bi)
                        cands.append(dA["entries"][ai][3] + dB["entries"][bi][3])
                        if best >= total_w:
                            break
    else:
        P = len(plat_data)

        def score(sel_entries):
            globs = []
            for e in sel_entries:
                globs.extend(e[1])
            return W(intra(globs))

        cur = [max(d["entries"], key=lambda e: W(e[2])) for d in plat_data]
        cur_s = score(cur)
        cands.append([i for e in cur for i in e[3]])
        improved = True
        while improved and time.time() < deadline:
            improved = False
            for p in range(P):
                for e in plat_data[p]["entries"]:
                    if time.time() > deadline:
                        break
                    trial = cur[:p] + [e] + cur[p + 1:]
                    s = score(trial)
                    if s > cur_s:
                        cur_s = s
                        cur = trial
                        improved = True
                        cands.append([i for e2 in cur for i in e2[3]])

    try:
        from stereo_survey.verify import verify as _verify
    except Exception:
        _verify = None

    for sel in reversed(cands):
        plan = {"images": [imgs[i]["id"] for i in sel]}
        if _verify is None:
            return plan
        try:
            r = _verify(mission, plan)
            if r.get("valid"):
                return plan
        except Exception:
            continue
    return {"images": []}
```