"""Exact small-instance reference, greedy controls and generic beam search.

All algorithms see the same public geometry and mission. Feasibility is
downward closed: deleting images cannot increase memory or energy, and direct
angular slews obey the triangle inequality. The reference enumerates every
feasible local sequence, then checks the Cartesian product for the two cameras.
"""

from itertools import combinations
import math

from .geometry import EPS, angle, mono_mask, pair_mask, pointing


def bits(mask):
    while mask:
        lowest = mask & -mask
        yield lowest.bit_length() - 1
        mask ^= lowest


class Problem:
    def __init__(self, mission):
        self.mission = mission
        self.images = mission["images"]
        self.n = len(self.images)
        self.weights = [cell["weight"] for cell in mission["cells"]]
        self.value_cache = {0: 0}
        self.mono = [mono_mask(mission, image) for image in self.images]
        self.pairs = [[0] * self.n for _ in self.images]
        for a, b in combinations(range(self.n), 2):
            self.pairs[a][b] = self.pairs[b][a] = pair_mask(mission, self.images[a], self.images[b])
        self.products = [(1 << a) | (1 << b) for a, b in combinations(range(self.n), 2) if self.pairs[a][b]]
        self.platform_masks = [sum(1 << i for i, im in enumerate(self.images) if im["platform"] == p["id"])
                               for p in mission["platforms"]]
        if len(self.platform_masks) != 2:
            raise ValueError("this bounded reference supports exactly two camera platforms")
        self.directions = [pointing(image) for image in self.images]
        self.turns = [[angle(a, b) for b in self.directions] for a in self.directions]
        self.local_cache = [{0: True}, {0: True}]
        self.cover_cache = {("stereo", 0): 0, ("mono", 0): 0}

    def value(self, coverage):
        if coverage not in self.value_cache:
            value = sum(self.weights[i] for i in bits(coverage))
            if len(self.value_cache) < 100_000:
                self.value_cache[coverage] = value
            return value
        return self.value_cache[coverage]

    def coverage(self, mask, objective="stereo"):
        key = (objective, mask)
        if key in self.cover_cache:
            return self.cover_cache[key]
        covered = 0
        indices = list(bits(mask))
        if objective == "mono":
            for i in indices:
                covered |= self.mono[i]
        else:
            for a, b in combinations(indices, 2):
                covered |= self.pairs[a][b]
        if len(self.cover_cache) < 100_000:
            self.cover_cache[key] = covered
        return covered

    def science(self, mask, objective="stereo"):
        return self.value(self.coverage(mask, objective))

    def plan(self, mask):
        return {"images": [self.images[i]["id"] for i in bits(mask)]}

    def local_feasible(self, mask, platform_index):
        cache = self.local_cache[platform_index]
        if mask in cache:
            return cache[mask]
        p = self.mission["platforms"][platform_index]
        sequence = sorted(bits(mask), key=lambda i: (self.images[i]["tick"], i))
        previous, end, tick, queued, energy = None, p["initial_tick"], -1, 0, 0
        valid = True
        for i in sequence:
            image = self.images[i]
            now = image["tick"]
            for event in p["downlinks"]:
                if tick < event["tick"] <= now:
                    queued = max(0, queued - event["capacity"])
            rotation = angle(p["initial_pointing"], self.directions[i]) if previous is None else self.turns[previous][i]
            if now - end < math.ceil(rotation / p["slew_rate"] - EPS):
                valid = False
                break
            energy += p["capture_energy"] + p["transmit_energy"] + math.ceil(rotation / p["slew_energy_angle"] - EPS)
            queued += 1
            if energy > p["battery"] or queued > p["memory"]:
                valid = False
                break
            previous, end, tick = i, now + 1, now
        if queued > sum(e["capacity"] for e in p["downlinks"] if e["tick"] > tick):
            valid = False
        cache[mask] = valid
        return valid

    def feasible(self, mask):
        return all(self.local_feasible(mask & local, i) for i, local in enumerate(self.platform_masks))


def greedy(problem, objective="stereo", density=False, units="products"):
    additions = problem.products if objective == "stereo" and units == "products" else [1 << i for i in range(problem.n)]
    # The single-image control deliberately maximizes monocular coverage.
    planning_objective = "mono" if units == "images" else objective
    selected = 0
    while True:
        current = problem.science(selected, planning_objective)
        best, best_rank = selected, (0, 0, 0)
        for addition in additions:
            candidate = selected | addition
            if candidate == selected or not problem.feasible(candidate):
                continue
            gain = problem.science(candidate, planning_objective) - current
            cost = (candidate ^ selected).bit_count()
            rank = (gain / cost if density else gain, gain, -candidate)
            if gain > 0 and rank > best_rank:
                best, best_rank = candidate, rank
        if best == selected:
            return {"science": problem.science(selected, objective), "plan": problem.plan(selected), "mask": selected}
        selected = best


def beam(problem, objective="stereo", width=64, units="products"):
    additions = problem.products if objective == "stereo" and units == "products" else [1 << i for i in range(problem.n)]
    frontier, expanded, visited = [0], 0, set()
    best = 0
    while frontier:
        children = set()
        for mask in frontier:
            visited.add(mask)
            for addition in additions:
                candidate = mask | addition
                if candidate == mask or candidate in visited or candidate in children:
                    continue
                expanded += 1
                if problem.feasible(candidate):
                    children.add(candidate)
        if not children:
            break
        def rank(mask):
            science = problem.science(mask, objective)
            mono = problem.science(mask, "mono")
            # Give single-image search a visible signal before a pair completes.
            priority = science + 0.25 * (mono - science) if units == "images" and objective == "stereo" else science
            return priority, science, -mask.bit_count(), mono, -mask
        frontier = sorted(children, key=rank, reverse=True)[:width]
        candidate = max(children, key=lambda mask: (problem.science(mask, objective), -mask.bit_count(), -mask))
        if problem.science(candidate, objective) > problem.science(best, objective):
            best = candidate
    return {"science": problem.science(best, objective), "plan": problem.plan(best), "mask": best, "expanded": expanded}


def exact(problem, objective="stereo", max_local=10_000, max_joint=2_000_000, incumbent=0):
    locals_ = []
    local_complete = True
    for platform_index, platform_mask in enumerate(problem.platform_masks):
        groups = {}
        for i in bits(platform_mask):
            groups.setdefault(problem.images[i]["tick"], []).append(i)
        groups = [groups[tick] for tick in sorted(groups)]
        plans = []
        def enumerate_local(index, mask):
            nonlocal local_complete
            if len(plans) >= max_local:
                local_complete = False
                return
            if index == len(groups):
                plans.append(mask)
                return
            enumerate_local(index + 1, mask)
            for i in groups[index]:
                candidate = mask | (1 << i)
                if problem.local_feasible(candidate, platform_index):
                    enumerate_local(index + 1, candidate)
        enumerate_local(0, 0)
        locals_.append(plans)
    best = incumbent if problem.feasible(incumbent) else 0
    best_score = problem.science(best, objective)
    if not local_complete:
        return {"science": best_score, "plan": problem.plan(best), "mask": best,
                "proven_optimal": False, "reason": "local sequence cap", "local_plans": list(map(len, locals_)), "joint_evaluations": 0}
    local_cover = [{mask: problem.coverage(mask, objective) for mask in plans} for plans in locals_]
    right_union, right_internal = 0, 0
    for mask in locals_[1]:
        right_union |= mask
        right_internal |= local_cover[1][mask]
    right_indices = {mask: list(bits(mask)) for mask in locals_[1]}
    left_order = sorted(locals_[0], key=lambda mask: problem.science(mask, "mono"), reverse=True)
    right_order = sorted(locals_[1], key=lambda mask: problem.science(mask, "mono"), reverse=True)
    evaluated = 0
    for left in left_order:
        cross = [0] * problem.n
        if objective == "stereo":
            for i in bits(left):
                for j in bits(right_union):
                    cross[j] |= problem.pairs[i][j]
        optimistic = local_cover[0][left] | right_internal
        for coverage in cross:
            optimistic |= coverage
        if problem.value(optimistic) <= best_score:
            continue
        for right in right_order:
            if evaluated >= max_joint:
                return {"science": best_score, "plan": problem.plan(best), "mask": best,
                        "proven_optimal": False, "reason": "joint search cap", "local_plans": list(map(len, locals_)), "joint_evaluations": evaluated}
            evaluated += 1
            coverage = local_cover[0][left] | local_cover[1][right]
            for j in right_indices[right]:
                coverage |= cross[j]
            science = problem.value(coverage)
            if science > best_score:
                best, best_score = left | right, science
    return {"science": best_score, "plan": problem.plan(best), "mask": best,
            "proven_optimal": True, "reason": "exhausted with valid upper bounds",
            "local_plans": list(map(len, locals_)), "joint_evaluations": evaluated}
