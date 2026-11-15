import heapq
import json
import math
import sys

from lightlag_client import connect
from lightlag_surface import Surface


def build_graph(surface):
    adj = {}
    dirs = ((1, 0), (-1, 0), (0, 1), (0, -1),
            (1, 1), (1, -1), (-1, 1), (-1, -1))
    for iy in range(81):
        for ix in range(121):
            x, y = ix * 5.0, iy * 5.0
            edges = []
            for dx, dy in dirs:
                nx, ny = ix + dx, iy + dy
                if not (0 <= nx <= 120 and 0 <= ny <= 80):
                    continue
                xx, yy = nx * 5.0, ny * 5.0
                length = math.hypot(xx - x, yy - y)
                safe = True
                for k in range(11):
                    f = k / 10
                    if surface.slope(x + (xx - x) * f, y + (yy - y) * f) > 0.30:
                        safe = False
                        break
                if not safe:
                    continue
                # Slightly favor firm terrain and gentle grades while retaining short routes.
                midx, midy = (x + xx) / 2, (y + yy) / 2
                terr = surface.terrain(midx, midy)
                factor = {"bedrock": 1.0, "regolith": 1.015, "rocks": 1.06, "sand": 1.12}[terr]
                factor += surface.slope(midx, midy) * 0.15
                edges.append(((nx, ny), length * factor))
            adj[(ix, iy)] = edges
    return adj


def shortest_path(adj, start, goal):
    if start == goal:
        return [start]
    dist = {start: 0.0}
    prev = {}
    heap = [(0.0, start)]
    while heap:
        cost, node = heapq.heappop(heap)
        if cost != dist[node]:
            continue
        if node == goal:
            break
        for nxt, weight in adj[node]:
            nc = cost + weight
            if nc < dist.get(nxt, float("inf")):
                dist[nxt] = nc
                prev[nxt] = node
                heapq.heappush(heap, (nc, nxt))
    if goal not in dist:
        raise RuntimeError(f"no safe path from {start} to {goal}")
    path = [goal]
    while path[-1] != start:
        path.append(prev[path[-1]])
    path.reverse()
    return path


def path_commands(path):
    if len(path) < 2:
        return []
    commands = []
    run_heading = None
    run_metres = 0.0
    for a, b in zip(path, path[1:]):
        dx, dy = (b[0] - a[0]) * 5.0, (b[1] - a[1]) * 5.0
        heading = math.degrees(math.atan2(dy, dx)) % 360
        length = math.hypot(dx, dy)
        if run_heading is None or abs((heading - run_heading + 180) % 360 - 180) < 1e-6:
            run_heading = heading
            run_metres += length
        else:
            commands.extend(split_drive(run_heading, run_metres))
            run_heading, run_metres = heading, length
    commands.extend(split_drive(run_heading, run_metres))
    return commands


def split_drive(heading, metres):
    out = []
    while metres > 1e-7:
        step = min(5.0, metres)
        out.append({"action": "drive", "heading_deg": round(heading, 5), "metres": round(step, 4)})
        metres -= step
    return out


ROUTE = ["t6", "t38", "t23", "t11", "t31", "t37", "t2", "t30",
         "t1", "t28", "t34", "t25", "t12", "t32", "t33", "t3"]


def main():
    with connect("http://lightlag:8000/mcp") as tools:
        rules = tools.rules()
        world = tools.map()
        surface = Surface(world["cell_m"], world["elevation_cm"], world["terrain"])
        adj = build_graph(surface)
        targets = {t["id"]: t for t in world["targets"]}
        base = tuple(round(v / 5) for v in world["base"])
        targets_by_xy = {k: (round(v["x"] / 5), round(v["y"] / 5)) for k, v in targets.items()}

        plan = []
        node = base
        order = []
        for target_id in ROUTE:
            goal = targets_by_xy[target_id]
            path = shortest_path(adj, node, goal)
            plan.extend(path_commands(path))
            plan.append({"action": "sample"})
            order.append(target_id)
            node = goal
        path = shortest_path(adj, node, base)
        plan.extend(path_commands(path))
        drives = sum(c["action"] == "drive" for c in plan)
        print(f"plan targets={order} commands={len(plan)} drives={drives} end_route_tick~{len(plan)+rules['delay_ticks']}", flush=True)

        if len(plan) + rules["delay_ticks"] > rules["max_ticks"] - 8:
            raise RuntimeError("planned route does not leave enough time to finish safely")

        for i in range(0, len(plan), 5):
            batch = plan[i:i + 5]
            tools.uplink(batch)
            out = tools.advance(min(5, rules["max_ticks"] - (i // 5) * 5))
            if (i // 5) % 8 == 0 or i + 5 >= len(plan):
                packets = tools.telemetry_log()
                last = packets[-1]
                sampled = sorted({sid for p in packets for sid in p.get("sampled_targets", [])})
                print(f"sent={min(i+5,len(plan))}/{len(plan)} tick={out['current_tick']} state_tick={last['tick']} pos={last['position']} battery={last['battery']:.1f} sampled={sampled}", flush=True)
                if not last.get("alive", True):
                    print("rover no longer alive", flush=True)
                    return

        # Drain the delayed command pipeline, then remain at the lander through tick 420.
        current = out["current_tick"]
        while True:
            result = tools.advance(min(5, rules["max_ticks"] - current))
            current = result["current_tick"]
            if result["episode_complete"]:
                break
            if current % 20 == 0 or current == len(plan) + rules["delay_ticks"]:
                packets = tools.telemetry_log()
                p = packets[-1]
                sampled = sorted({sid for packet in packets for sid in packet.get("sampled_targets", [])})
                print(f"tick={current} state_tick={p['tick']} pos={p['position']} battery={p['battery']:.1f} sampled={sampled}", flush=True)
        packets = tools.telemetry_log()
        p = packets[-1]
        sampled = sorted({sid for packet in packets for sid in packet.get("sampled_targets", [])})
        print(f"COMPLETE tick={current} alive={p['alive']} pos={p['position']} battery={p['battery']:.1f} sampled={sampled}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR {type(exc).__name__}: {exc}", flush=True)
        raise
