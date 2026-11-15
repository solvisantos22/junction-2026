import math
import heapq
import random

from lightlag_surface import Surface, drive, TERRAIN_CODES


class _Navigator:
    def __init__(self, world, rules):
        self.s = Surface(world["cell_m"], world["elevation_cm"],
                         world["terrain"])
        self.p = rules["physics"]
        self.cell = self.s.cell
        self.nx = self.s.nx - 1
        self.ny = self.s.ny - 1
        self.n = self.nx * self.ny
        self.slip = {k: sum(v) / 2
                     for k, v in self.p["slip_base_ranges"].items()}
        self.xy = [((i + .5) * self.cell, (j + .5) * self.cell)
                   for j in range(self.ny) for i in range(self.nx)]
        self.safe = [
            self.s.cell_max_slope(i, j) < self.p["max_tilt"] - .012
            for j in range(self.ny) for i in range(self.nx)
        ]
        self.rev = [[] for _ in range(self.n)]
        self.fields = {}
        self.goals = {}
        for j in range(self.ny):
            for i in range(self.nx):
                u = j * self.nx + i
                if not self.safe[u]:
                    continue
                x, y = self.xy[u]
                h, gx, gy, code = self.s.sample(x, y)
                name = TERRAIN_CODES[code]
                for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1),
                               (1, 1), (1, -1), (-1, 1), (-1, -1)):
                    ii, jj = i + di, j + dj
                    if not (0 <= ii < self.nx and 0 <= jj < self.ny):
                        continue
                    v = jj * self.nx + ii
                    if not self.safe[v]:
                        continue
                    if di and dj:
                        if not (self.safe[j * self.nx + ii] and
                                self.safe[jj * self.nx + i]):
                            continue
                    xx, yy = self.xy[v]
                    length = math.hypot(xx - x, yy - y)
                    grade = (gx * (xx - x) + gy * (yy - y)) / length
                    slip = min(.88, self.slip[name] +
                               self.p["slip_grade_gain"][name] *
                               max(0., grade))
                    wheel = length / (1 - slip)
                    ticks = wheel / 5.
                    energy = (wheel *
                              self.p["drive_cost_per_wheel_m"][name] +
                              self.p["climb_cost_per_m"] *
                              max(0., self.s.elevation(xx, yy) - h))
                    self.rev[v].append((u, ticks + .075 * energy,
                                        ticks, energy))

    def line(self, a, b, margin=.65):
        dx, dy = b[0] - a[0], b[1] - a[1]
        distance = math.hypot(dx, dy)
        count = max(1, int(distance / 1.4) + 1)
        if distance:
            ox, oy = -dy / distance * margin, dx / distance * margin
        else:
            ox, oy = margin, 0.
        limit = self.p["max_tilt"] - .006
        for k in range(count + 1):
            f = k / count
            x, y = a[0] + dx * f, a[1] + dy * f
            for xx, yy in ((x, y), (x + ox, y + oy), (x - ox, y - oy)):
                if not self.s.inside(xx, yy) or self.s.slope(xx, yy) > limit:
                    return False
        return True

    def nearby(self, position, radius=2):
        i = min(self.nx - 1, max(0, int(position[0] / self.cell)))
        j = min(self.ny - 1, max(0, int(position[1] / self.cell)))
        result = []
        for jj in range(max(0, j - radius), min(self.ny, j + radius + 1)):
            for ii in range(max(0, i - radius), min(self.nx, i + radius + 1)):
                u = jj * self.nx + ii
                if self.safe[u]:
                    result.append(u)
        result.sort(key=lambda u: math.dist(position, self.xy[u]))
        return result

    def add_goal(self, key, point):
        if key in self.fields:
            return
        self.goals[key] = tuple(point)
        inf = float("inf")
        cost = [inf] * self.n
        times = [inf] * self.n
        energies = [inf] * self.n
        nxt = [-1] * self.n
        heap = []
        for u in self.nearby(point, 3):
            dist = math.dist(point, self.xy[u])
            if dist > 19 or not self.line(self.xy[u], point, .35):
                continue
            ticks = dist / 3.7
            energy = dist * .60
            c = ticks + .075 * energy
            cost[u], times[u], energies[u] = c, ticks, energy
            heapq.heappush(heap, (c, u))
        while heap:
            c, v = heapq.heappop(heap)
            if c > cost[v] + 1e-9:
                continue
            for u, weight, t, e in self.rev[v]:
                nc = c + weight
                if nc < cost[u]:
                    cost[u] = nc
                    times[u] = times[v] + t
                    energies[u] = energies[v] + e
                    nxt[u] = v
                    heapq.heappush(heap, (nc, u))
        self.fields[key] = (cost, times, energies, nxt)

    def estimate(self, position, key, careful=False):
        point = self.goals[key]
        d = math.dist(position, point)
        if d < 13 and self.line(position, point, .35):
            return d / 3.65, d * .62
        cost, times, energies, _ = self.fields[key]
        candidates = self.nearby(position, 2)
        best = None
        for u in candidates[:(14 if careful else 5)]:
            if not math.isfinite(cost[u]):
                continue
            dd = math.dist(position, self.xy[u])
            if careful and not self.line(position, self.xy[u], .4):
                continue
            c = cost[u] + dd / 3.6 + .075 * dd * .65
            if best is None or c < best[0]:
                best = (c, times[u] + dd / 3.6,
                        energies[u] + dd * .65)
        return (best[1], best[2]) if best else (1e6, 1e6)

    def waypoint(self, position, key):
        point = self.goals[key]
        if math.dist(position, point) < 20 and self.line(position, point):
            return point
        cost, _, _, nxt = self.fields[key]
        choices = []
        for u in self.nearby(position, 3):
            if not math.isfinite(cost[u]):
                continue
            d = math.dist(position, self.xy[u])
            choices.append((cost[u] + d / 3.8, u))
        choices.sort()
        start = None
        for _, u in choices[:30]:
            if self.line(position, self.xy[u], .55):
                start = u
                break
        if start is None:
            for _, u in choices:
                if self.line(position, self.xy[u], .1):
                    start = u
                    break
        if start is None:
            return point
        result = self.xy[start]
        u = start
        for _ in range(7):
            if math.dist(position, self.xy[u]) > 20:
                break
            if self.line(position, self.xy[u], .65):
                result = self.xy[u]
            else:
                break
            if nxt[u] < 0:
                if self.line(position, point, .5):
                    result = point
                break
            u = nxt[u]
        return result


def play(tools):
    rules = tools.rules()
    world = tools.map()
    nav = _Navigator(world, rules)
    physics = rules["physics"]
    delay = rules["delay_ticks"]
    end_tick = rules["max_ticks"]
    capacity = rules["battery_capacity"]
    idle = rules["idle_cost"]
    rng = random.Random(831479)
    base = tuple(world["base"])
    nav.add_goal("__base__", base)
    targets = {}
    pair_cache = {}

    def refresh():
        changed = False
        for target in tools.map()["targets"]:
            key = target["id"]
            if key not in targets:
                targets[key] = target
                nav.add_goal(key, (target["x"], target["y"]))
                changed = True
        return changed

    refresh()
    initial = tools.telemetry_log()[0]
    state = [float(initial["position"][0]),
             float(initial["position"][1]), 0.]
    cov = [[.00001, 0., 0.],
           [0., .00001, 0.],
           [0., 0., math.radians(3.5) ** 2]]
    state_tick = 0
    battery = float(initial["battery"])
    efficiency = .88
    history = {}
    sent_at = {}
    last_reserved = -1
    sampled = set(initial.get("sampled_targets", []))
    pending = {}
    route = []
    dirty = True
    last_plan = -100
    now = 0

    def sunlight(t):
        return rules["solar_peak"] * math.sin(
            math.pi * (t + rules["sun_margin_ticks"]) /
            (end_tick + 2 * rules["sun_margin_ticks"]))

    def propagate_position(x, y, bias, command, wheel=None):
        if not command or command["action"] != "drive":
            return x, y, 0., None
        metres = command["metres"] if wheel is None else wheel
        if metres <= 1e-8:
            return x, y, 0., None
        result = drive(nav.s, physics, x, y,
                       command["heading_deg"] + math.degrees(bias),
                       metres, nav.slip)
        return result["x"], result["y"], result["energy"], result

    def consume(packet):
        nonlocal state, cov, state_tick, battery, efficiency, dirty
        tick = packet["tick"]
        if tick <= state_tick:
            return
        command = history.get(tick)
        wheel = packet.get("wheel_odometry", 0.)
        oldx, oldy, bias = state
        x, y, _, result = propagate_position(
            oldx, oldy, bias, command, wheel)
        dx, dy = x - oldx, y - oldy
        moving = wheel > .01 and command and command["action"] == "drive"

        if moving and result and wheel > 2.0 and result["stop"] is None:
            terrain = nav.s.terrain(oldx, oldy)
            observed = packet.get("visual_odometry", 0.)
            residual = (result["ground"] - observed) / wheel
            lo, hi = physics["slip_base_ranges"][terrain]
            nav.slip[terrain] = max(lo, min(
                hi, nav.slip[terrain] + .065 * residual))

        # Position/bias EKF; the two position observations are assimilated
        # separately, preserving their correlation with heading bias.
        f = [[1., 0., -dy], [0., 1., dx], [0., 0., 1.]]
        temp = [[sum(f[i][k] * cov[k][j] for k in range(3))
                 for j in range(3)] for i in range(3)]
        pc = [[sum(temp[i][k] * f[j][k] for k in range(3))
               for j in range(3)] for i in range(3)]
        q = .00004
        if moving:
            q += .012 + (.026 * math.hypot(dx, dy)) ** 2
            angle_variance = math.radians(
                rules["sensing"]["heading_noise_deg"]) ** 2
            pc[0][0] += dy * dy * angle_variance
            pc[1][1] += dx * dx * angle_variance
            pc[0][1] -= dx * dy * angle_variance
            pc[1][0] -= dx * dy * angle_variance
            pc[2][2] += math.radians(
                rules["sensing"]["heading_bias_walk_deg"]) ** 2
        pc[0][0] += q
        pc[1][1] += q
        state = [x, y, bias]
        variance = rules["sensing"]["position_noise_m"] ** 2
        for axis in (0, 1):
            denom = pc[axis][axis] + variance
            gain = [pc[i][axis] / denom for i in range(3)]
            residual = packet["position"][axis] - state[axis]
            row = pc[axis][:]
            for i in range(3):
                state[i] += gain[i] * residual
                for j in range(3):
                    pc[i][j] -= gain[i] * row[j]
        state[0] = min(nav.s.width, max(0., state[0]))
        state[1] = min(nav.s.height, max(0., state[1]))
        state[2] = max(-.23, min(.23, state[2]))
        cov = pc
        battery = packet["battery"]
        state_tick = tick

        raw_sun = sunlight(tick)
        if battery < capacity - 5 and raw_sun > .1:
            measured = packet.get("charge", 0.) / raw_sun
            lo, hi = rules["solar_efficiency_range"]
            if lo - .01 <= measured <= hi + .01:
                efficiency = max(lo, min(hi, measured))

        got = set(packet.get("sampled_targets", []))
        if not got.issubset(sampled):
            sampled.update(got)
            dirty = True
        for key, execution in list(pending.items()):
            if tick >= execution:
                del pending[key]
                if key not in sampled:
                    dirty = True

        # A safety stop clears commands already on board, but not commands
        # transmitted after the stop occurred.
        if (command and command["action"] == "drive" and
                wheel + .12 < command["metres"]):
            for t in list(history):
                if t > tick and sent_at.get(t, tick + 1) <= tick:
                    history.pop(t, None)
            dirty = True

    def forecast(until):
        x, y, bias = state
        b = battery
        for t in range(state_tick + 1, until + 1):
            b = min(capacity, b + efficiency * sunlight(t)) - idle
            command = history.get(t)
            if command:
                x, y, spent, _ = propagate_position(x, y, bias, command)
                b -= spent
                if command["action"] == "sample":
                    b -= rules["sample_cost"]
        return (x, y), b

    def pair(a, b):
        key = (a, b)
        if key not in pair_cache:
            pair_cache[key] = nav.estimate(nav.goals[a], b, True)
        return pair_cache[key]

    def plan(position, start_tick, start_battery, excluded):
        available = [k for k in targets if k not in excluded]
        start_cost = {k: nav.estimate(position, k, True)
                      for k in available + ["__base__"]}
        solar_floor = .01
        finish_limit = end_tick - 10

        def evaluate(sequence):
            t = float(start_tick)
            b = start_battery
            score = 0.
            previous = None
            for key in list(sequence) + ["__base__"]:
                travel, energy = (start_cost[key] if previous is None
                                  else pair(previous, key))
                if travel > end_tick * 2:
                    return -1., 1e9
                duration = travel * 1.10
                overhead = 2.3 if key != "__base__" else 1.8
                duration += overhead
                expense = energy * 1.04
                if key != "__base__":
                    expense += rules["sample_cost"]
                mid = min(end_tick, max(0., t + duration * .5))
                rate = max(solar_floor, efficiency * sunlight(mid) - idle)
                # Conservative cap: charging cannot bank more than capacity.
                b = min(capacity, b + duration * rate * .5)
                b -= expense
                b = min(capacity, b + duration * rate * .5)
                if b < 18:
                    wait_rate = max(.25, efficiency * sunlight(
                        min(end_tick, t)) - idle)
                    extra = (18 - b) / wait_rate
                    t += extra
                    b = 18.
                t += duration
                if t > finish_limit:
                    return -1., t
                if key != "__base__":
                    target = targets[key]
                    deadline = target.get("deadline_tick")
                    score += (target["value"] if deadline is None or t <= deadline
                              else target.get("late_value",
                                              .25 * target["value"]))
                previous = key
            return score, t

        incumbent = [k for k in route if k in available]
        best_score, best_end = evaluate(incumbent)
        best = incumbent if best_score >= 0 else []
        if best_score < 0:
            best_score, best_end = evaluate([])
        # Randomized insertion accounts for deadline losses to all subsequent
        # targets, rather than assigning each target a static priority.
        for trial in range(9):
            sequence = [] if trial < 6 else best[:]
            if trial >= 6 and sequence:
                remove = max(1, len(sequence) // 3)
                for _ in range(remove):
                    if sequence:
                        sequence.pop(rng.randrange(len(sequence)))
            score, finish = evaluate(sequence)
            if score < 0:
                sequence = []
                score, finish = evaluate([])
            weights = {k: (1. if trial == 0 else
                           math.exp(rng.uniform(-.48, .48)))
                       for k in available}
            while True:
                winner = None
                chosen = set(sequence)
                for key in available:
                    if key in chosen:
                        continue
                    for at in range(len(sequence) + 1):
                        proposal = sequence[:at] + [key] + sequence[at:]
                        value, completion = evaluate(proposal)
                        gain = value - score
                        if value < 0 or gain <= .00001:
                            continue
                        added = max(2., completion - finish)
                        rank = weights[key] * gain / added ** .82
                        if winner is None or rank > winner[0]:
                            winner = (rank, proposal, value, completion)
                if winner is None:
                    break
                _, sequence, score, finish = winner
            if score > best_score + 1e-6 or (
                    abs(score - best_score) < 1e-6 and finish < best_end):
                best, best_score, best_end = sequence, score, finish
        return best

    def make_drive(position, waypoint, bias, goal):
        dx = waypoint[0] - position[0]
        dy = waypoint[1] - position[1]
        distance = math.hypot(dx, dy)
        if distance < .08:
            return {"action": "wait"}, 0.
        angle = math.atan2(dy, dx)
        metres = min(5., distance / .80)
        # Invert the published forward model, including cross-slope drift.
        for _ in range(3):
            result = drive(nav.s, physics, *position,
                           math.degrees(angle), metres, nav.slip)
            vx, vy = result["x"] - position[0], result["y"] - position[1]
            ground = math.hypot(vx, vy)
            if ground < .001:
                break
            correction = math.atan2(dy, dx) - math.atan2(vy, vx)
            correction = (correction + math.pi) % (2 * math.pi) - math.pi
            angle += correction
            metres = min(5., max(.06, metres * distance / ground))

        candidates = []
        for offset in (0, -12, 12, -28, 28, -50, 50, -85, 85, 140, -140):
            actual = math.degrees(angle) + offset
            result = drive(nav.s, physics, *position, actual, metres, nav.slip)
            endpoint = (result["x"], result["y"])
            moved = math.dist(position, endpoint)
            if result["stop"] is not None or moved < .025:
                continue
            safe = nav.line(position, endpoint, .65)
            if not safe and not nav.line(position, endpoint, .18):
                continue
            rank = math.dist(endpoint, waypoint) + (.0 if safe else 2.5)
            rank += .008 * abs(offset)
            candidates.append((rank, actual, metres, result["energy"]))
            if offset == 0 and safe:
                break
        if not candidates:
            # A short corrective move can escape a position very close to a
            # cell boundary without committing another full five metres.
            for heading in range(0, 360, 30):
                result = drive(nav.s, physics, *position, heading, 1.,
                               nav.slip)
                endpoint = (result["x"], result["y"])
                if result["stop"] is None and math.dist(position, endpoint) > .15:
                    t, _ = nav.estimate(endpoint, goal)
                    candidates.append((100 + t, heading, 1.,
                                       result["energy"]))
        if not candidates:
            return {"action": "wait"}, 0.
        _, actual, metres, energy = min(candidates)
        return {
            "action": "drive",
            "heading_deg": (actual - math.degrees(bias)) % 360.,
            "metres": min(5., max(.02, metres))
        }, energy

    complete = False
    while not complete and now < end_tick:
        if now % 9 == 0 and refresh():
            dirty = True
        execution = max(now + delay + 1, last_reserved + 1)
        if execution > end_tick:
            result = tools.advance(min(5, end_tick - now))
            now = result["current_tick"]
            complete = result["episode_complete"]
            for packet in result.get("packets", []):
                consume(packet)
            continue

        position, predicted_battery = forecast(execution - 1)
        excluded = sampled | set(pending)
        route = [k for k in route if k not in excluded]
        if dirty or now - last_plan >= 24:
            route = plan(position, execution - 1, predicted_battery, excluded)
            last_plan = now
            dirty = False

        home_time, _ = nav.estimate(position, "__base__", True)
        forced_home = execution + home_time * 1.13 + 9 >= end_tick
        goal = "__base__" if forced_home or not route else route[0]
        goal_position = nav.goals[goal]
        distance = math.dist(position, goal_position)

        if goal == "__base__" and distance < .85:
            command, cost = {"action": "wait"}, 0.
        elif goal != "__base__" and distance < .65:
            command, cost = {"action": "sample"}, rules["sample_cost"]
        else:
            waypoint = nav.waypoint(position, goal)
            # Close approaches use the target coordinate itself.
            if distance < 5 and nav.line(position, goal_position, .25):
                waypoint = goal_position
            command, cost = make_drive(position, waypoint, state[2], goal)

        next_charge = efficiency * sunlight(execution)
        reserve = 11. if forced_home else 18.
        if (command["action"] != "wait" and
                predicted_battery + next_charge - idle - cost < reserve):
            command = {"action": "wait"}
        if command["action"] == "sample":
            pending[goal] = execution
            route = [k for k in route if k != goal]
            dirty = True

        acknowledgements = tools.uplink([command])
        acknowledgement = acknowledgements[0]
        actual_tick = acknowledgement["execute_tick"]
        history[actual_tick] = command
        sent_at[actual_tick] = now
        last_reserved = max(last_reserved, actual_tick)
        if command["action"] == "sample" and actual_tick != execution:
            pending[goal] = actual_tick

        result = tools.advance(1)
        now = result["current_tick"]
        complete = result["episode_complete"]
        for packet in result.get("packets", []):
            consume(packet)
            if not packet.get("alive", True):
                complete = True
