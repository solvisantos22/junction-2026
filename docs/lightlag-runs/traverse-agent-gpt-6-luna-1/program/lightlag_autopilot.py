import heapq
import json
import math
import os
import time

from lightlag_client import connect
from lightlag_surface import Surface, drive as model_drive


URL = "http://lightlag:8000/mcp"
LOG = "/app/autopilot.log"


def log(message):
    text = str(message)
    print(text, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(text + "\n")


def distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def main():
    with connect(URL) as tools:
        rules = tools.rules()
        world = tools.map()
        surface = Surface(world["cell_m"], world["elevation_cm"], world["terrain"])
        phys = rules["physics"]
        terrain_mid = {"bedrock": 0.03, "regolith": 0.085, "sand": 0.25, "rocks": 0.18}
        known = {t["id"]: t for t in world["targets"]}
        # Prioritise the early eastern finds, then sweep the central and north-east
        # clusters while leaving a full return leg to the lander.
        preferred = [
            "t12", "t25", "t28", "t23", "t38", "t11", "t31", "t6",
            "t2", "t30",
            "t8", "t17", "t13", "t4", "t14", "t36",
        ]
        base = tuple(world["base"])
        nx, ny = surface.nx, surface.ny

        def pos(node):
            return (node[0] * surface.cell, node[1] * surface.cell)

        def node_slope(node):
            x, y = pos(node)
            return surface.slope(x, y)

        safe = {}
        for j in range(ny):
            for i in range(nx):
                safe[(i, j)] = node_slope((i, j)) < 0.325

        def edge_ok(a, b):
            ax, ay = pos(a)
            bx, by = pos(b)
            n = max(2, int(distance((ax, ay), (bx, by)) / 1.0))
            for k in range(n + 1):
                q = k / n
                if surface.slope(ax + q * (bx - ax), ay + q * (by - ay)) >= 0.345:
                    return False
            return True

        def nearest_safe(point):
            best, bd = None, float("inf")
            ci = round(point[0] / surface.cell)
            cj = round(point[1] / surface.cell)
            for radius in range(0, 8):
                for j in range(max(0, cj - radius), min(ny - 1, cj + radius) + 1):
                    for i in range(max(0, ci - radius), min(nx - 1, ci + radius) + 1):
                        n = (i, j)
                        if not safe[n]:
                            continue
                        p = pos(n)
                        d = distance(p, point)
                        if d < bd and edge_ok(n, n):
                            best, bd = n, d
                if best is not None and bd <= (radius + 0.75) * surface.cell:
                    break
            return best

        def astar(start, goal):
            s = nearest_safe(start)
            g = nearest_safe(goal)
            if s is None or g is None:
                raise RuntimeError(f"No safe grid endpoint for {start} -> {goal}")
            frontier = [(distance(pos(s), pos(g)), 0.0, s)]
            came, cost = {}, {s: 0.0}
            while frontier:
                _, gcost, cur = heapq.heappop(frontier)
                if gcost != cost.get(cur):
                    continue
                if cur == g:
                    break
                for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                    nxt = (cur[0] + di, cur[1] + dj)
                    if not (0 <= nxt[0] < nx and 0 <= nxt[1] < ny) or not safe[nxt] or not edge_ok(cur, nxt):
                        continue
                    p = pos(nxt)
                    h, _, _, code = surface.sample(*p)
                    terrain = {"b": "bedrock", "r": "regolith", "s": "sand", "k": "rocks"}[code]
                    factor = {"bedrock": 1.0, "regolith": 1.0, "sand": 1.22, "rocks": 1.12}[terrain]
                    slope = surface.slope(*p)
                    step = distance(pos(cur), p) * factor * (1 + 0.7 * slope)
                    ng = gcost + step
                    if ng < cost.get(nxt, float("inf")):
                        cost[nxt], came[nxt] = ng, cur
                        heuristic = distance(p, pos(g))
                        heapq.heappush(frontier, (ng + heuristic, ng, nxt))
            if g not in cost:
                raise RuntimeError(f"No safe route {start} -> {goal}")
            nodes = [g]
            while nodes[-1] != s:
                nodes.append(came[nodes[-1]])
            nodes.reverse()
            points = [pos(n) for n in nodes]
            if distance(start, points[0]) > 0.5:
                points.insert(0, tuple(start))
            if distance(goal, points[-1]) > 0.5:
                if distance(goal, points[-1]) <= 3.2 and edge_ok(g, g):
                    points.append(tuple(goal))
            return points, cost[g], s, g

        route_points = []
        route_targets = []
        current = base
        selected = []
        for tid in preferred:
            if tid in known:
                selected.append(known[tid])
        # A* legs define a safe path and each target stays an explicit sample waypoint.
        current = base
        total_path = 0.0
        for target in selected:
            goal = (target["x"], target["y"])
            points, leg_cost, _, gnode = astar(current, goal)
            total_path += leg_cost
            for p in points[1:]:
                if not route_points or distance(route_points[-1][0], p) > 0.1:
                    route_points.append((p, None))
            if not route_points or distance(route_points[-1][0], goal) > 0.1:
                route_points.append((goal, target["id"]))
            else:
                route_points[-1] = (goal, target["id"])
            route_targets.append(target)
            current = goal
        ret_points, ret_cost, _, _ = astar(current, base)
        total_path += ret_cost
        for p in ret_points[1:]:
            if not route_points or distance(route_points[-1][0], p) > 0.1:
                route_points.append((p, None))
        if distance(current, base) < 1:
            route_points.append((base, None))
        log(f"Planned {len(selected)} targets; safe-route estimate {total_path:.0f} m; route waypoints {len(route_points)}")
        log("Target order: " + ", ".join(t["id"] for t in selected))

        # Drop the most distant tail targets if the safe path is too long to leave
        # enough ticks for sampling and a reliable return.
        if total_path > 1650:
            raise RuntimeError(f"Planned route too long ({total_path:.0f} m); refusing unsafe schedule")

        telemetry = tools.telemetry_log()
        initial = telemetry[-1]
        px, py = initial["position"]
        current_tick = 0
        command_schedule = {}
        queue_tail = 0
        route_index = 0
        sample_at = {}
        verified_samples = set()
        expected_samples = set()
        stop_reason = None

        def simulate_from_packet(packet, through_tick):
            x, y = packet["position"]
            for tick in range(packet["tick"] + 1, through_tick + 1):
                cmd = command_schedule.get(tick)
                if cmd and cmd["action"] == "drive":
                    out = model_drive(surface, phys, x, y, cmd["heading_deg"], cmd["metres"], terrain_mid, 0.0)
                    x, y = out["x"], out["y"]
            return x, y

        while current_tick < rules["max_ticks"]:
            latest = tools.telemetry_log()
            if latest:
                packet = latest[-1]
                verified_samples.update(packet.get("sampled_targets", []))
                if not packet.get("alive", True):
                    stop_reason = "rover not alive"
                    break
                px, py = simulate_from_packet(packet, max(current_tick, queue_tail))

            if route_index >= len(route_points) and queue_tail <= current_tick:
                cmds = [{"action": "wait"} for _ in range(min(5, rules["max_ticks"] - current_tick))]
            else:
                start_tick = max(current_tick + rules["delay_ticks"] + 1, queue_tail + 1)
                # The queued rover position, not the stale packet position, is the
                # correct origin for steering the next FIFO block.
                plan_x, plan_y = px, py
                planned = []
                for _ in range(5):
                    while route_index < len(route_points):
                        goal, target_id = route_points[route_index]
                        d = distance((plan_x, plan_y), goal)
                        if target_id is None and d < 3.4:
                            route_index += 1
                            continue
                        if target_id is not None and target_id in expected_samples:
                            route_index += 1
                            continue
                        break
                    if route_index >= len(route_points):
                        planned.append({"action": "wait"})
                        continue
                    goal, target_id = route_points[route_index]
                    d = distance((plan_x, plan_y), goal)
                    if target_id is not None and d <= 1.05:
                        cmd = {"action": "sample"}
                        expected_samples.add(target_id)
                        sample_at[target_id] = start_tick + len(planned)
                        route_index += 1
                    else:
                        if d < 0.15:
                            route_index += 1
                            planned.append({"action": "wait"})
                            continue
                        heading = math.degrees(math.atan2(goal[1] - plan_y, goal[0] - plan_x)) % 360
                        metres = min(5.0, max(1.0, d / 0.88))
                        cmd = {"action": "drive", "heading_deg": heading, "metres": metres}
                        out = model_drive(surface, phys, plan_x, plan_y, heading, metres, terrain_mid, 0.0)
                        if out["stop"]:
                            log(f"Local route model stopped at {out['stop']} near {(plan_x, plan_y)} toward {goal}; using shorter step")
                            metres = min(2.0, metres)
                            cmd["metres"] = metres
                            out = model_drive(surface, phys, plan_x, plan_y, heading, metres, terrain_mid, 0.0)
                        plan_x, plan_y = out["x"], out["y"]
                    planned.append(cmd)
                cmds = planned

            if current_tick + rules["delay_ticks"] + 1 > rules["max_ticks"]:
                break
            # Keep each uplink within the published batch limit and don't reserve
            # command ticks beyond mission end.
            limit = rules["max_ticks"]
            safe_cmds = []
            for cmd in cmds:
                if max(current_tick + rules["delay_ticks"] + 1, queue_tail + 1) + len(safe_cmds) > limit:
                    break
                safe_cmds.append(cmd)
            if not safe_cmds:
                break
            acknowledgements = tools.uplink(safe_cmds)
            ticks = [a["execute_tick"] for a in acknowledgements]
            for tick, cmd in zip(ticks, safe_cmds):
                command_schedule[tick] = cmd
            queue_tail = max(queue_tail, ticks[-1])
            advance_n = min(5, rules["max_ticks"] - current_tick)
            result = tools.advance(advance_n)
            current_tick = result["current_tick"]
            for packet in result.get("packets", []):
                verified_samples.update(packet.get("sampled_targets", []))
                if not packet.get("alive", True):
                    stop_reason = "rover not alive"
            if current_tick % 25 == 0 or current_tick >= rules["max_ticks"]:
                log(f"tick={current_tick} pos~({px:.1f},{py:.1f}) battery={latest[-1]['battery']:.1f} route={route_index}/{len(route_points)} samples={len(verified_samples)} queued_through={queue_tail}")
            if stop_reason:
                break

        final_log = tools.telemetry_log()
        if final_log:
            last = final_log[-1]
            log("FINAL " + json.dumps({
                "tick": last["tick"], "received_tick": last["received_tick"],
                "position": last["position"], "battery": last["battery"],
                "alive": last["alive"], "sampled_targets": last["sampled_targets"],
                "events": last["events"], "verified_sample_count": len(verified_samples),
                "expected_samples": sorted(expected_samples), "stop_reason": stop_reason,
            }))


if __name__ == "__main__":
    main()
