```python
import heapq
import math


def play(tools):
    rules = tools.rules()
    world = tools.map()
    delay = int(rules["delay_ticks"])
    max_ticks = int(rules["max_ticks"])
    base_x, base_y = map(float, world["base"])
    cell = float(world["cell_m"])
    width, height = float(world["width"]), float(world["height"])
    physics = rules["physics"]

    try:
        from lightlag_surface import Surface
        surface = Surface(cell, world["elevation_cm"], world["terrain"])
    except Exception:
        surface = None

    def distance(a, b):
        return math.hypot(a[0] - b[0], a[1] - b[1])

    def route(start, goal):
        """Find a conservative, terrain-aware route on the map's grid."""
        if surface is None:
            return [goal]
        nx = surface.nx - 1
        ny = surface.ny - 1

        def node(p):
            i = min(nx - 1, max(0, int(p[0] / cell)))
            j = min(ny - 1, max(0, int(p[1] / cell)))
            return i, j

        def center(n):
            return ((n[0] + 0.5) * cell, (n[1] + 0.5) * cell)

        source, dest = node(start), node(goal)
        if source == dest:
            return [goal]

        # Permit traversal only through cells whose full bilinear patch is safe.
        safe = {}
        for j in range(ny):
            for i in range(nx):
                safe[(i, j)] = surface.cell_max_slope(i, j) <= physics["max_tilt"]

        safe[source] = True
        safe[dest] = True
        frontier = [(0.0, source)]
        cost = {source: 0.0}
        parent = {}
        while frontier:
            _, cur = heapq.heappop(frontier)
            if cur == dest:
                break
            for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1),
                           (1, 1), (1, -1), (-1, 1), (-1, -1)):
                nxt = (cur[0] + di, cur[1] + dj)
                if not (0 <= nxt[0] < nx and 0 <= nxt[1] < ny and safe[nxt]):
                    continue
                if di and dj:
                    if not safe.get((cur[0] + di, cur[1])) or not safe.get((cur[0], cur[1] + dj)):
                        continue
                step = distance(center(cur), center(nxt))
                _, _, _, code = surface.sample(*center(nxt))
                terrain = {"b": "bedrock", "r": "regolith",
                           "s": "sand", "k": "rocks"}.get(code, "regolith")
                terrain_weight = {"bedrock": 1.0, "regolith": 1.08,
                                  "rocks": 1.25, "sand": 1.55}[terrain]
                new_cost = cost[cur] + step * terrain_weight
                if new_cost < cost.get(nxt, float("inf")):
                    cost[nxt] = new_cost
                    parent[nxt] = cur
                    heuristic = distance(center(nxt), center(dest))
                    heapq.heappush(frontier, (new_cost + heuristic, nxt))

        if dest not in parent:
            return [goal]
        nodes = [dest]
        while nodes[-1] != source:
            nodes.append(parent[nodes[-1]])
        nodes.reverse()
        points = [center(n) for n in nodes[1:]]
        points.append(goal)
        # Remove adjacent grid points that do not materially change direction.
        return points

    def target_score(target, pos, tick):
        d = distance(pos, (target["x"], target["y"]))
        value = float(target.get("value", 1.0))
        deadline = target.get("deadline_tick")
        if deadline is not None and tick + d / 0.7 > float(deadline):
            value = float(target.get("late_value", value * 0.25))
        # Prefer worthwhile nearby targets, while reserving ample time to return.
        return value / (d + 18.0)

    log = tools.telemetry_log()
    initial = log[0]
    pos = tuple(map(float, initial["position"]))
    tick = int(initial["tick"])
    battery = float(initial.get("battery", rules["initial_battery"]))
    sampled = set(initial.get("sampled_targets", []))
    targets_done = set(sampled)
    mission_targets = {}
    for target in world.get("targets", []):
        mission_targets[target["id"]] = target

    mode = "explore"
    waypoint = None
    path = []
    command_id = 0
    # At most a few commands are kept in flight. The local position is advanced
    # using the known map, then corrected whenever a delayed packet arrives.
    predicted = pos
    predicted_tick = tick
    last_packet_tick = tick
    queued_samples = set()

    def refresh():
        nonlocal pos, predicted, predicted_tick, tick, battery, last_packet_tick
        packets = tools.telemetry_log()
        for packet in packets:
            pt = int(packet.get("tick", 0))
            if pt < last_packet_tick:
                continue
            last_packet_tick = pt
            if "position" in packet:
                pos = tuple(map(float, packet["position"]))
            tick = max(tick, pt)
            battery = float(packet.get("battery", battery))
            sampled.update(packet.get("sampled_targets", []))
            for event in packet.get("events", []):
                if isinstance(event, dict) and event.get("target"):
                    item = event["target"]
                    if isinstance(item, dict) and "id" in item:
                        mission_targets[item["id"]] = item
            predicted = pos
            predicted_tick = pt
        for target in tools.map().get("targets", []):
            mission_targets[target["id"]] = target

    def choose_target():
        available = [t for t in mission_targets.values()
                     if t.get("id") not in sampled
                     and t.get("id") not in queued_samples
                     and int(t.get("appear_tick", 0)) <= tick]
        if not available:
            return None
        # Keep a substantial return reserve; target selection is intentionally
        # opportunistic rather than attempting a long, risky tour.
        reserve = distance(pos, (base_x, base_y)) / 0.65 + 45
        if tick + reserve > max_ticks - 8:
            return None
        feasible = []
        for t in available:
            d = distance(pos, (float(t["x"]), float(t["y"])))
            back = distance((float(t["x"]), float(t["y"])), (base_x, base_y))
            if tick + d / 0.6 + back / 0.6 + 12 < max_ticks:
                feasible.append(t)
        return max(feasible, key=lambda t: target_score(t, pos, tick)) if feasible else None

    def steer(point, from_pos):
        dx, dy = point[0] - from_pos[0], point[1] - from_pos[1]
        d = math.hypot(dx, dy)
        if d < 0.8:
            return None
        return {"action": "drive",
                "heading_deg": math.degrees(math.atan2(dy, dx)) % 360.0,
                "metres": min(5.0, max(0.5, d))}

    def estimate_drive(p, command):
        if surface is None:
            ang = math.radians(command["heading_deg"])
            return (min(width, max(0.0, p[0] + command["metres"] * math.cos(ang) * 0.88)),
                    min(height, max(0.0, p[1] + command["metres"] * math.sin(ang) * 0.88)))
        try:
            slip = {"bedrock": 0.03, "regolith": 0.085, "sand": 0.25, "rocks": 0.18}
            result = __import__("lightlag_surface").drive(
                surface, physics, p[0], p[1], command["heading_deg"],
                command["metres"], slip, 0.0)
            return result["x"], result["y"]
        except Exception:
            ang = math.radians(command["heading_deg"])
            return (p[0] + command["metres"] * math.cos(ang) * 0.85,
                    p[1] + command["metres"] * math.sin(ang) * 0.85)

    while True:
        state = tools.advance(min(5, max(1, max_ticks - tick)))
        if state.get("episode_complete"):
            return
        refresh()
        if tick >= max_ticks:
            return

        # Decide whether to head home, based on remaining time and battery.
        home_distance = distance(pos, (base_x, base_y))
        if tick + home_distance / 0.58 + 24 >= max_ticks or battery < home_distance * 0.65 + 18:
            mode = "home"

        if mode == "explore" and waypoint is None:
            chosen = choose_target()
            if chosen is None:
                mode = "home"
            else:
                waypoint = (float(chosen["x"]), float(chosen["y"]))
                waypoint_id = chosen["id"]
                path = route(pos, waypoint)

        if mode == "home":
            waypoint = (base_x, base_y)
            waypoint_id = None
            path = route(pos, waypoint)

        # Send a short block of commands. A sample is issued only when the
        # estimated rover position is close to the target.
        commands = []
        sim = predicted
        for _ in range(5):
            if tick + len(commands) + delay + 1 >= max_ticks:
                break
            if mode == "explore" and waypoint is not None:
                if distance(sim, waypoint) <= float(rules["target_radius"]) + 1.0:
                    if waypoint_id not in sampled and waypoint_id not in queued_samples:
                        commands.append({"action": "sample"})
                        queued_samples.add(waypoint_id)
                        continue
                    waypoint = None
                    path = []
                    break
                while path and distance(sim, path[0]) < 3.0:
                    path.pop(0)
                aim = path[0] if path else waypoint
            else:
                if distance(sim, (base_x, base_y)) <= float(rules["base_radius"]) - 0.7:
                    commands.append({"action": "wait"})
                    continue
                while path and distance(sim, path[0]) < 3.0:
                    path.pop(0)
                aim = path[0] if path else (base_x, base_y)

            cmd = steer(aim, sim)
            if cmd is None:
                if mode == "explore":
                    waypoint = None
                    path = []
                else:
                    commands.append({"action": "wait"})
                continue
            commands.append(cmd)
            sim = estimate_drive(sim, cmd)

        if not commands:
            commands = [{"action": "wait"}]

        try:
            acknowledgements = tools.uplink(commands)
        except ValueError:
            # Fall back to a single safe idle command if a batch is rejected.
            try:
                tools.uplink([{"action": "wait"}])
            except Exception:
                pass
        else:
            # Track the predicted endpoint for the next planning pass.
            predicted = sim
            predicted_tick = max(
                predicted_tick,
                max((int(a.get("execute_tick", tick)) for a in acknowledgements), default=tick)
            )

        # Allow the delayed commands and telemetry to progress; short increments
        # preserve opportunities to correct the position estimate.
        nxt = tools.advance(min(5, max(1, max_ticks - tick)))
        if nxt.get("episode_complete"):
            return
        refresh()
        if tick >= max_ticks:
            return

        # Samples are confirmed by telemetry. If a sample command has had time
        # to execute but did not collect, release its reservation for retry.
        if waypoint_id if mode == "explore" and waypoint is not None else False:
            if waypoint_id in sampled:
                queued_samples.discard(waypoint_id)
                waypoint = None
                path = []
        if mode == "home" and distance(pos, (base_x, base_y)) <= float(rules["base_radius"]):
            # Stay near the lander through the end of the mission.
            waypoint = (base_x, base_y)
```
