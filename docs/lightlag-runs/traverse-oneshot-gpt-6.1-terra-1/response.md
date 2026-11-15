```python
import heapq
import math

from lightlag_surface import Surface, drive, TERRAIN_CODES


def play(tools):
    rules = tools.rules()
    world = tools.map()
    physics = rules["physics"]
    surface = Surface(world["cell_m"], world["elevation_cm"], world["terrain"])

    delay = int(rules["delay_ticks"])
    end_tick = int(rules["max_ticks"])
    max_drive = float(rules["max_metres_per_drive"])
    target_radius = float(rules["target_radius"])
    base_radius = float(rules["base_radius"])
    base = tuple(world["base"])
    cell = surface.cell
    nx, ny = surface.nx - 1, surface.ny - 1
    count = nx * ny
    infinity = float("inf")

    slip = {
        name: (limits[0] + limits[1]) / 2.0
        for name, limits in physics["slip_base_ranges"].items()
    }

    # Build a directed, terrain-weighted graph of safe cell centres.
    safe = [False] * count
    heights = [0.0] * count
    codes = [""] * count
    centres = [None] * count
    for j in range(ny):
        for i in range(nx):
            k = j * nx + i
            x, y = (i + 0.5) * cell, (j + 0.5) * cell
            centres[k] = (x, y)
            h, _, _, code = surface.sample(x, y)
            heights[k], codes[k] = h, code
            safe[k] = surface.cell_max_slope(i, j) < 0.335

    near_bad = [False] * count
    for j in range(ny):
        for i in range(nx):
            k = j * nx + i
            if not safe[k]:
                continue
            for dj in (-1, 0, 1):
                for di in (-1, 0, 1):
                    ii, jj = i + di, j + dj
                    if ii < 0 or ii >= nx or jj < 0 or jj >= ny:
                        near_bad[k] = True
                    elif not safe[jj * nx + ii]:
                        near_bad[k] = True

    outgoing = [[] for _ in range(count)]
    incoming = [[] for _ in range(count)]
    for j in range(ny):
        for i in range(nx):
            a = j * nx + i
            if not safe[a]:
                continue
            name = TERRAIN_CODES[codes[a]]
            for dj in (-1, 0, 1):
                for di in (-1, 0, 1):
                    if not (di or dj):
                        continue
                    ii, jj = i + di, j + dj
                    if not (0 <= ii < nx and 0 <= jj < ny):
                        continue
                    b = jj * nx + ii
                    if not safe[b]:
                        continue
                    if di and dj:
                        if not safe[j * nx + ii] or not safe[jj * nx + i]:
                            continue
                    distance = cell * math.hypot(di, dj)
                    grade = max(0.0, (heights[b] - heights[a]) / distance)
                    loss = slip[name] + physics["slip_grade_gain"][name] * grade
                    speed = max(0.18, 1.0 - min(0.82, loss))
                    cost = distance / (max_drive * speed)
                    if near_bad[a] or near_bad[b]:
                        cost *= 1.08
                    outgoing[a].append((b, cost))
                    incoming[b].append((a, cost))

    def clear_line(x1, y1, x2, y2, margin=0.65):
        distance = math.hypot(x2 - x1, y2 - y1)
        if distance < 1e-8:
            return True
        ux, uy = (x2 - x1) / distance, (y2 - y1) / distance
        steps = max(1, int(math.ceil(distance / 1.2)))
        for n in range(steps + 1):
            f = n / steps
            x, y = x1 + f * (x2 - x1), y1 + f * (y2 - y1)
            for offset in (-margin, 0.0, margin):
                xx, yy = x - uy * offset, y + ux * offset
                if not (0.05 <= xx <= surface.width - 0.05 and
                        0.05 <= yy <= surface.height - 0.05):
                    return False
                if surface.slope(xx, yy) >= 0.35:
                    return False
        return True

    def nearest_node(x, y, require_connection=False):
        i = max(0, min(nx - 1, int(x / cell)))
        j = max(0, min(ny - 1, int(y / cell)))
        candidates = []
        for radius in (1, 2, 3):
            for jj in range(max(0, j - radius), min(ny, j + radius + 1)):
                for ii in range(max(0, i - radius), min(nx, i + radius + 1)):
                    k = jj * nx + ii
                    if safe[k]:
                        cx, cy = centres[k]
                        candidates.append(((cx - x) ** 2 + (cy - y) ** 2, k))
            if candidates:
                break
        candidates.sort()
        for _, k in candidates:
            cx, cy = centres[k]
            if not require_connection or clear_line(x, y, cx, cy, 0.2):
                return k
        return None

    def distances_to(destination):
        dist = [infinity] * count
        if destination is None:
            return dist
        dist[destination] = 0.0
        heap = [(0.0, destination)]
        while heap:
            d, node = heapq.heappop(heap)
            if d != dist[node]:
                continue
            for prev, cost in incoming[node]:
                nd = d + cost
                if nd < dist[prev]:
                    dist[prev] = nd
                    heapq.heappush(heap, (nd, prev))
        return dist

    base_node = nearest_node(base[0], base[1], True)
    base_field = distances_to(base_node)
    targets = {}
    target_nodes = {}
    fields = {}

    def add_targets(items):
        changed = False
        for item in items:
            ident = item["id"]
            if ident in targets:
                targets[ident] = item
                continue
            targets[ident] = item
            node = nearest_node(float(item["x"]), float(item["y"]), True)
            target_nodes[ident] = node
            if node is not None:
                cx, cy = centres[node]
                # A distant connection to a target is not a reliable route.
                if math.hypot(cx - item["x"], cy - item["y"]) > cell * 1.6:
                    target_nodes[ident] = None
                else:
                    fields[ident] = distances_to(node)
            changed = True
        return changed

    add_targets(world["targets"])

    # Position and heading-bias filter. The bias is in radians.
    briefing = tools.telemetry_log()[0]
    state = [float(briefing["position"][0]), float(briefing["position"][1]), 0.0]
    position_noise = float(rules["sensing"]["position_noise_m"])
    bias_range = math.radians(float(rules["sensing"]["heading_bias_deg"]))
    covariance = [
        [0.001, 0.0, 0.0],
        [0.0, 0.001, 0.0],
        [0.0, 0.0, bias_range * bias_range / 3.0],
    ]
    last_packet_tick = 0
    battery = float(briefing["battery"])
    sampled = set()
    scheduled = {}
    sample_lock = None
    chosen = None
    last_plan_tick = -1000
    now = 0

    def sampled_ids(packet):
        result = set()
        for entry in packet.get("sampled_targets", []):
            if isinstance(entry, dict):
                if "id" in entry:
                    result.add(entry["id"])
            else:
                result.add(entry)
        return result

    sampled.update(sampled_ids(briefing))

    def model_move(x, y, bias, command, wheel=None, visual=None):
        metres = float(command["metres"] if wheel is None else wheel)
        if metres <= 1e-9:
            return x, y, 0.0
        result = drive(
            surface, physics, x, y,
            float(command["heading_deg"]) + math.degrees(bias),
            metres, slip,
        )
        dx, dy = result["x"] - x, result["y"] - y
        expected = math.hypot(dx, dy)
        if visual is not None and expected > 1e-6:
            scale = max(0.0, float(visual)) / expected
            dx *= scale
            dy *= scale
        return x + dx, y + dy, result["energy"]

    def assimilate(packet):
        nonlocal state, covariance, last_packet_tick, battery
        nonlocal sample_lock, chosen

        tick = int(packet["tick"])
        if tick <= last_packet_tick:
            return
        command_record = scheduled.get(tick)
        command = command_record["command"] if command_record else None
        wheel = float(packet.get("wheel_odometry", 0.0))
        dx = dy = 0.0

        if command and command["action"] == "drive" and wheel > 0.0:
            old_x, old_y = state[0], state[1]
            new_x, new_y, _ = model_move(
                old_x, old_y, state[2], command, wheel,
                packet.get("visual_odometry"),
            )
            dx, dy = new_x - old_x, new_y - old_y
            state[0], state[1] = new_x, new_y

        # Linearized propagation through a displacement rotated by the bias.
        f = [[1.0, 0.0, -dy], [0.0, 1.0, dx], [0.0, 0.0, 1.0]]
        fp = [
            [sum(f[i][k] * covariance[k][j] for k in range(3))
             for j in range(3)]
            for i in range(3)
        ]
        covariance = [
            [sum(fp[i][k] * f[j][k] for k in range(3))
             for j in range(3)]
            for i in range(3)
        ]
        travelled = math.hypot(dx, dy)
        if travelled:
            along_var = (0.05 * travelled + 0.08) ** 2
            cross_var = (math.radians(1.5) * travelled + 0.08) ** 2
            ux, uy = dx / travelled, dy / travelled
            covariance[0][0] += along_var * ux * ux + cross_var * uy * uy
            covariance[1][1] += along_var * uy * uy + cross_var * ux * ux
            qxy = (along_var - cross_var) * ux * uy
            covariance[0][1] += qxy
            covariance[1][0] += qxy
            covariance[2][2] += math.radians(
                float(rules["sensing"]["heading_bias_walk_deg"])
            ) ** 2
        else:
            covariance[0][0] += 0.002
            covariance[1][1] += 0.002

        # Two-dimensional position measurement update.
        variance = position_noise * position_noise
        s00 = covariance[0][0] + variance
        s01 = covariance[0][1]
        s10 = covariance[1][0]
        s11 = covariance[1][1] + variance
        det = max(1e-12, s00 * s11 - s01 * s10)
        inv = [[s11 / det, -s01 / det], [-s10 / det, s00 / det]]
        gain = [
            [covariance[i][0] * inv[0][j] +
             covariance[i][1] * inv[1][j] for j in range(2)]
            for i in range(3)
        ]
        residual = [
            float(packet["position"][0]) - state[0],
            float(packet["position"][1]) - state[1],
        ]
        for i in range(3):
            state[i] += gain[i][0] * residual[0] + gain[i][1] * residual[1]
        old_cov = [row[:] for row in covariance]
        for i in range(3):
            for j in range(3):
                covariance[i][j] = (
                    old_cov[i][j] - gain[i][0] * old_cov[0][j]
                    - gain[i][1] * old_cov[1][j]
                )
        for i in range(3):
            covariance[i][i] = max(covariance[i][i], 1e-8)
            for j in range(i):
                v = (covariance[i][j] + covariance[j][i]) / 2.0
                covariance[i][j] = covariance[j][i] = v
        state[0] = min(surface.width, max(0.0, state[0]))
        state[1] = min(surface.height, max(0.0, state[1]))
        state[2] = max(-0.35, min(0.35, state[2]))

        # A truncated drive indicates a safety stop. Commands already in the
        # queue at that tick were cleared, although their ticks remain reserved.
        if command and command["action"] == "drive":
            if wheel + 0.02 < float(command["metres"]):
                for future_tick, record in list(scheduled.items()):
                    if future_tick > tick and record["sent_tick"] < tick:
                        del scheduled[future_tick]

        battery = float(packet["battery"])
        sampled.update(sampled_ids(packet))
        if chosen in sampled:
            chosen = None
        if sample_lock is not None and tick >= sample_lock:
            sample_lock = None
        last_packet_tick = tick

        for old_tick in list(scheduled):
            if old_tick <= tick:
                del scheduled[old_tick]

    def projected_position():
        x, y = state[0], state[1]
        projected_energy = 0.0
        for tick in sorted(scheduled):
            if tick <= last_packet_tick:
                continue
            command = scheduled[tick]["command"]
            if command["action"] == "drive":
                x, y, energy = model_move(x, y, state[2], command)
                projected_energy += energy + float(rules["idle_cost"])
            elif command["action"] == "sample":
                projected_energy += float(rules["sample_cost"]) + float(rules["idle_cost"])
        return x, y, battery - projected_energy

    def route_waypoint(x, y, node, destination, field):
        if node is None or destination is None or not math.isfinite(field[node]):
            return None
        if clear_line(x, y, destination[0], destination[1]):
            return destination

        path = []
        current = node
        seen = set()
        for _ in range(30):
            if current in seen:
                break
            seen.add(current)
            path.append(centres[current])
            if field[current] <= 1e-9:
                path.append(destination)
                break
            choices = outgoing[current]
            if not choices:
                break
            nxt, _ = min(choices, key=lambda item: item[1] + field[item[0]])
            if not math.isfinite(field[nxt]) or field[nxt] >= field[current]:
                break
            current = nxt

        best = None
        for point in path:
            if math.hypot(point[0] - x, point[1] - y) > 35.0:
                break
            if clear_line(x, y, point[0], point[1]):
                best = point
        if best is not None:
            return best
        # This may occur just after a stop, when the rover is outside the
        # conservative graph. Move toward the nearest connected safe centre.
        cx, cy = centres[node]
        if clear_line(x, y, cx, cy, 0.15):
            return (cx, cy)
        return None

    def select_target(x, y, tick):
        start = nearest_node(x, y)
        if start is None or not math.isfinite(base_field[start]):
            return None
        available = [
            ident for ident in targets
            if ident not in sampled and ident in fields
            and math.isfinite(fields[ident][start])
            and math.isfinite(base_field[target_nodes[ident]])
        ]
        if not available:
            return None

        # Beam search over target sequences. Travel times are directional;
        # each candidate must still allow a conservative return to the base.
        remaining = end_tick - tick
        return_margin = 18.0
        beam = [(0.0, 0.0, start, (), None)]
        best_score = -infinity
        best_first = None
        for _ in range(6):
            next_beam = []
            for reward, elapsed, node, used, first in beam:
                for ident in available:
                    if ident in used:
                        continue
                    travel = fields[ident][node]
                    if not math.isfinite(travel):
                        continue
                    arrival = elapsed + travel + 5.0
                    finish = arrival + 4.0
                    dest_node = target_nodes[ident]
                    back = base_field[dest_node] + 3.0
                    if finish + back + return_margin > remaining:
                        continue
                    target = targets[ident]
                    deadline = target.get("deadline_tick")
                    value = float(target["value"])
                    if deadline is not None and tick + arrival > float(deadline):
                        value = float(target.get("late_value", value * 0.25))
                    new_reward = reward + value
                    first_id = ident if first is None else first
                    new_used = used + (ident,)
                    score = new_reward - 0.018 * (finish + back)
                    if score > best_score:
                        best_score, best_first = score, first_id
                    next_beam.append((new_reward, finish, dest_node, new_used, first_id))
            if not next_beam:
                break
            next_beam.sort(
                key=lambda entry: entry[0] - 0.018 * (
                    entry[1] + base_field[entry[2]]
                ),
                reverse=True,
            )
            beam = next_beam[:65]
        return best_first

    def make_drive(x, y, waypoint):
        dx, dy = waypoint[0] - x, waypoint[1] - y
        distance = math.hypot(dx, dy)
        if distance < 0.08:
            return None
        desired = math.atan2(dy, dx)
        heading = desired - state[2]

        # Compensate for predicted side slip using the published model.
        for _ in range(2):
            probe = drive(
                surface, physics, x, y,
                math.degrees(heading + state[2]), max_drive, slip,
            )
            px, py = probe["x"] - x, probe["y"] - y
            if math.hypot(px, py) < 0.05:
                break
            error = (desired - math.atan2(py, px) + math.pi) % (2 * math.pi) - math.pi
            heading += error

        probe = drive(
            surface, physics, x, y,
            math.degrees(heading + state[2]), max_drive, slip,
        )
        ground = math.hypot(probe["x"] - x, probe["y"] - y)
        if ground < 0.05:
            return None
        metres = min(max_drive, max(0.1, distance * max_drive / ground))
        if probe["stop"] is not None:
            metres = min(metres, max(0.0, probe["wheel"] - 0.5))
        if metres < 0.1:
            return None

        return {
            "action": "drive",
            "heading_deg": math.degrees(heading) % 360.0,
            "metres": min(max_drive, metres),
        }

    while now < end_tick:
        x, y, projected_battery = projected_position()
        node = nearest_node(x, y)
        back_time = (
            base_field[node] + 3.0
            if node is not None and math.isfinite(base_field[node])
            else infinity
        )
        remaining = end_tick - now

        # Solar is estimated conservatively for the prospective return.
        solar = 0.0
        if math.isfinite(back_time):
            duration = max(1, int(math.ceil(back_time + 5.0)))
            for step in range(1, duration + 1):
                t = min(end_tick, now + step)
                angle = math.pi * (
                    t + float(rules["sun_margin_ticks"])
                ) / (end_tick + 2.0 * float(rules["sun_margin_ticks"]))
                solar += (
                    float(rules["solar_peak"])
                    * float(rules["solar_efficiency_range"][0])
                    * max(0.0, math.sin(angle))
                )
        energy_return = max(0.0, 2.0 * back_time - solar) if math.isfinite(back_time) else infinity
        must_return = (
            remaining <= back_time + 20.0
            or projected_battery < energy_return + 12.0
        )

        if chosen in sampled:
            chosen = None
        if chosen is not None and chosen not in fields:
            chosen = None

        if sample_lock is None and not must_return:
            if chosen is None or now - last_plan_tick >= 25:
                candidate = select_target(x, y, now)
                if candidate is not None:
                    chosen = candidate
                elif chosen is None:
                    must_return = True
                last_plan_tick = now

        command = None
        if sample_lock is None:
            if must_return:
                chosen = None
                distance_to_base = math.hypot(x - base[0], y - base[1])
                if distance_to_base > min(1.3, base_radius * 0.4):
                    waypoint = route_waypoint(x, y, node, base, base_field)
                    if waypoint is not None:
                        command = make_drive(x, y, waypoint)
            elif chosen is not None:
                target = targets[chosen]
                destination = (float(target["x"]), float(target["y"]))
                distance = math.hypot(x - destination[0], y - destination[1])
                if distance <= min(1.0, target_radius * 0.4):
                    command = {"action": "sample"}
                else:
                    waypoint = route_waypoint(x, y, node, destination, fields[chosen])
                    if waypoint is not None:
                        command = make_drive(x, y, waypoint)

        # Do not spend the last battery reserve on a speculative drive.
        if command and command["action"] == "drive" and projected_battery < 9.0:
            command = None

        if command is not None:
            acknowledgements = tools.uplink([command])
            for record in acknowledgements:
                execute_tick = int(record["execute_tick"])
                scheduled[execute_tick] = record
                if command["action"] == "sample":
                    sample_lock = execute_tick

        result = tools.advance(1)
        now = int(result["current_tick"])
        discovery = False
        for packet in result.get("packets", []):
            assimilate(packet)
            for event in packet.get("events", []):
                if isinstance(event, dict):
                    if (event.get("type") == "target_discovered"
                            or event.get("event") == "target_discovered"
                            or event.get("action") == "target_discovered"):
                        discovery = True

        # map() lists a discovery only after its telemetry packet arrives.
        if discovery:
            if add_targets(tools.map()["targets"]):
                last_plan_tick = -1000

        if result.get("episode_complete"):
            break
```