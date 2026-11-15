#!/usr/bin/env python3
"""Closed-loop Lightlag traverse controller."""

from __future__ import annotations

import heapq
import json
import math
import time
from typing import Dict, List, Optional, Sequence, Tuple

from lightlag_client import connect
from lightlag_surface import PHYSICS, Surface

URL = "http://lightlag:8000/mcp"
MAX_TICK = 420
SAFE_SLOPE = 0.335
SLIP = {"bedrock": 0.03, "regolith": 0.085, "sand": 0.25, "rocks": 0.18}


def dist(a: Sequence[float], b: Sequence[float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


class Planner:
    def __init__(self, world: dict):
        self.world = world
        self.surface = Surface(world["cell_m"], world["elevation_cm"], world["terrain"])
        self.step = 5.0
        self.nx = int(world["width"] / self.step)
        self.ny = int(world["height"] / self.step)
        self.points = [(i * self.step + 2.5, j * self.step + 2.5)
                       for j in range(self.ny) for i in range(self.nx)]
        self.valid = [self.surface.slope(x, y) < SAFE_SLOPE for x, y in self.points]
        self.adj: List[List[Tuple[int, float]]] = [[] for _ in self.points]
        for j in range(self.ny):
            for i in range(self.nx):
                a = j * self.nx + i
                if not self.valid[a]:
                    continue
                for dj in (-1, 0, 1):
                    for di in (-1, 0, 1):
                        if (di, dj) == (0, 0):
                            continue
                        ii, jj = i + di, j + dj
                        if not (0 <= ii < self.nx and 0 <= jj < self.ny):
                            continue
                        b = jj * self.nx + ii
                        if not self.valid[b] or a >= b:
                            continue
                        if self.clear_segment(self.points[a], self.points[b]):
                            d = dist(self.points[a], self.points[b])
                            self.adj[a].append((b, d))
                            self.adj[b].append((a, d))

    def clear_segment(self, a: Sequence[float], b: Sequence[float]) -> bool:
        length = dist(a, b)
        n = max(1, int(math.ceil(length / 0.5)))
        for k in range(n + 1):
            f = k / n
            x = a[0] + (b[0] - a[0]) * f
            y = a[1] + (b[1] - a[1]) * f
            if not self.surface.inside(x, y) or self.surface.slope(x, y) >= SAFE_SLOPE:
                return False
        return True

    def local_nodes(self, p: Sequence[float], radius: float = 9.0) -> List[Tuple[int, float]]:
        i0 = max(0, int((p[0] - radius - 2.5) // self.step))
        i1 = min(self.nx - 1, int((p[0] + radius - 2.5) // self.step))
        j0 = max(0, int((p[1] - radius - 2.5) // self.step))
        j1 = min(self.ny - 1, int((p[1] + radius - 2.5) // self.step))
        out = []
        for j in range(j0, j1 + 1):
            for i in range(i0, i1 + 1):
                node = j * self.nx + i
                d = dist(p, self.points[node])
                if self.valid[node] and d <= radius and self.clear_segment(p, self.points[node]):
                    out.append((node, d))
        return out

    def route(self, start: Sequence[float], goal: Sequence[float]) -> Optional[List[Tuple[float, float]]]:
        if not self.surface.inside(*start) or not self.surface.inside(*goal):
            return None
        if dist(start, goal) <= 1.0 and self.clear_segment(start, goal):
            return [tuple(start), tuple(goal)]
        starts = self.local_nodes(start, 11.0)
        goals = self.local_nodes(goal, 11.0)
        if not starts or not goals:
            return None
        goal_cost = {n: d for n, d in goals}
        goal_pt = {n: self.points[n] for n, _ in goals}
        goal_ids = set(goal_cost)
        best: Dict[int, float] = {}
        prev: Dict[int, int] = {}
        heap: List[Tuple[float, float, int]] = []
        for n, d in starts:
            if d < best.get(n, float("inf")):
                best[n] = d
                heapq.heappush(heap, (d + min(dist(self.points[n], goal_pt[g]) + goal_cost[g]
                                               for g in goal_ids), d, n))
        found = None
        while heap:
            _, cost, node = heapq.heappop(heap)
            if cost != best.get(node):
                continue
            if node in goal_ids:
                found = node
                break
            for nxt, edge in self.adj[node]:
                new = cost + edge
                if new < best.get(nxt, float("inf")):
                    best[nxt] = new
                    prev[nxt] = node
                    # Include the connector to the closest feasible goal node.
                    h = min(dist(self.points[nxt], self.points[g]) + goal_cost[g] for g in goal_ids)
                    heapq.heappush(heap, (new + h, new, nxt))
        if found is None:
            return None
        ids = [found]
        while ids[-1] in prev:
            ids.append(prev[ids[-1]])
        ids.reverse()
        points = [tuple(start)] + [self.points[n] for n in ids] + [tuple(goal)]
        # Remove duplicated and collinear graph points to keep route state compact.
        compact: List[Tuple[float, float]] = []
        for p in points:
            if compact and dist(compact[-1], p) < 0.25:
                continue
            compact.append(p)
        return compact


def sim_drive(surface: Surface, p: Sequence[float], cmd: dict) -> Tuple[float, float]:
    out = surface_drive(surface, p, cmd)
    return out


def surface_drive(surface: Surface, p: Sequence[float], cmd: dict) -> Tuple[float, float]:
    out = surface.drive if hasattr(surface, "drive") else None
    # The published helper is a module function; keep prediction on its same integration model.
    from lightlag_surface import drive
    result = drive(surface, PHYSICS, p[0], p[1], cmd["heading_deg"], cmd["metres"], SLIP)
    if result["stop"]:
        return p[0], p[1]
    return result["x"], result["y"]


def main() -> None:
    with connect(URL) as tools:
        rules = tools.rules()
        world = tools.map()
        planner = Planner(world)
        base = tuple(world["base"])
        # Tick-indexed actions let us reconstruct the rover beyond delayed telemetry.
        commands: Dict[int, dict] = {}
        last_scheduled = 0
        current_tick = 0
        known_sampled = set()
        pending_samples: Dict[str, int] = {}
        failures: Dict[str, int] = {}
        active_target: Optional[dict] = None
        route: Optional[List[Tuple[float, float]]] = None
        route_index = 0
        mode = "science"
        cycles = 0
        print("controller online", json.dumps({"base": base, "targets": len(world["targets"]),
                                                "delay": rules["delay_ticks"]}), flush=True)

        while current_tick < MAX_TICK:
            packets = tools.telemetry_log()
            if packets:
                for target_id in (packets[-1].get("sampled_targets") or []):
                    if isinstance(target_id, dict):
                        known_sampled.add(target_id.get("id"))
                    else:
                        known_sampled.add(target_id)
            for target_id, sample_tick in list(pending_samples.items()):
                if target_id in known_sampled:
                    pending_samples.pop(target_id, None)
                elif current_tick >= sample_tick + rules["delay_ticks"] + 3:
                    pending_samples.pop(target_id, None)
                    failures[target_id] = failures.get(target_id, 0) + 1
                    if active_target and active_target["id"] == target_id:
                        active_target = None
                        route = None

            # Refresh the map to include targets whose discovery packets have arrived.
            world = tools.map()
            if (world.get("width") != planner.world.get("width") or
                    len(world.get("targets", [])) != len(planner.world.get("targets", []))):
                planner = Planner(world)

            if not packets:
                raise RuntimeError("no telemetry available")
            latest = packets[-1]
            pos = tuple(latest["position"])
            packet_tick = latest["tick"]
            # Replay acknowledged actions from the newest delayed state to the end of the queue.
            exec_start = max(current_tick + rules["delay_ticks"] + 1, last_scheduled + 1)
            forecast_end = max(current_tick, last_scheduled)
            for tick in range(packet_tick + 1, forecast_end + 1):
                cmd = commands.get(tick)
                if cmd and cmd["action"] == "drive":
                    pos = sim_drive(planner.surface, pos, cmd)

            battery = latest.get("battery", 0.0)
            home_dist = dist(pos, base)
            if mode != "home" and (current_tick >= 325 or current_tick + home_dist / 2.2 + 25 >= 405 or battery < 18):
                mode = "home"
                active_target = None
                route = None
                print("returning", json.dumps({"tick": current_tick, "pos": pos,
                                               "home_distance": round(home_dist, 1),
                                               "battery": round(battery, 1)}), flush=True)

            count = min(5, MAX_TICK - max(current_tick + rules["delay_ticks"] + 1, last_scheduled + 1))
            if count < 0:
                count = 0
            batch: List[dict] = []
            batch_ticks: List[int] = []

            def choose_target(at: Sequence[float], tick_est: int) -> Optional[dict]:
                options = []
                for target in world["targets"]:
                    tid = target["id"]
                    if tid in known_sampled or tid in pending_samples or failures.get(tid, 0) >= 2:
                        continue
                    d = dist(at, (target["x"], target["y"]))
                    # Leave enough time for a return, allowing for substantial detours.
                    projected = tick_est + (d + dist((target["x"], target["y"]), base)) / 2.3 + 22
                    if projected > 420:
                        continue
                    reward = target["value"]
                    deadline = target.get("deadline_tick")
                    if deadline is not None and tick_est + d / 2.5 > deadline:
                        reward = target.get("late_value", reward * 0.25)
                    # Nearby clusters are valuable; deadlines gently favor timely sampling.
                    score = reward / ((d + 22.0) ** 0.82)
                    if deadline is not None and deadline >= tick_est and deadline - (tick_est + d / 2.5) < 35:
                        score *= 1.15
                    options.append((score, -d, target))
                return max(options, key=lambda x: (x[0], x[1]))[2] if options else None

            for n in range(max(0, count)):
                tick = exec_start + n
                if tick > MAX_TICK:
                    break
                if mode == "home":
                    if dist(pos, base) <= 1.4:
                        cmd = {"action": "wait"}
                    else:
                        if route is None:
                            route = planner.route(pos, base)
                            route_index = 0
                        if not route:
                            cmd = {"action": "wait"}
                        else:
                            while route_index + 1 < len(route) - 1 and dist(pos, route[route_index + 1]) < 2.4:
                                route_index += 1
                            waypoint = route[min(route_index + 1, len(route) - 1)]
                            dwp = dist(pos, waypoint)
                            if dwp < 0.35:
                                route_index = min(route_index + 1, len(route) - 1)
                                waypoint = route[min(route_index + 1, len(route) - 1)]
                                dwp = dist(pos, waypoint)
                            if dwp <= 1.4:
                                cmd = {"action": "wait"}
                            else:
                                heading = math.degrees(math.atan2(waypoint[1] - pos[1], waypoint[0] - pos[0])) % 360
                                metres = min(4.5, max(0.7, dwp * 0.78))
                                cmd = {"action": "drive", "heading_deg": heading, "metres": metres}
                else:
                    if active_target is None:
                        active_target = choose_target(pos, tick)
                        route = None
                        route_index = 0
                        if active_target:
                            print("target", json.dumps({"tick": tick, "id": active_target["id"],
                                                         "value": active_target["value"],
                                                         "at": [round(pos[0], 1), round(pos[1], 1)]}), flush=True)
                    if active_target is None:
                        mode = "home"
                        route = None
                        cmd = {"action": "wait"}
                    else:
                        goal = (active_target["x"], active_target["y"])
                        dgoal = dist(pos, goal)
                        if dgoal <= 1.35:
                            cmd = {"action": "sample"}
                            pending_samples[active_target["id"]] = tick
                            print("sample queued", json.dumps({"tick": tick, "id": active_target["id"],
                                                               "distance": round(dgoal, 2)}), flush=True)
                            active_target = None
                            route = None
                            route_index = 0
                        else:
                            if route is None:
                                route = planner.route(pos, goal)
                                route_index = 0
                                if not route:
                                    print("no safe route", json.dumps({"tick": tick, "id": active_target["id"],
                                                                       "at": [round(pos[0], 1), round(pos[1], 1)]}), flush=True)
                                    failures[active_target["id"]] = failures.get(active_target["id"], 0) + 1
                                    active_target = None
                                    cmd = {"action": "wait"}
                            if active_target is not None:
                                while route_index + 1 < len(route) - 1 and dist(pos, route[route_index + 1]) < 2.4:
                                    route_index += 1
                                waypoint = route[min(route_index + 1, len(route) - 1)]
                                dwp = dist(pos, waypoint)
                                heading = math.degrees(math.atan2(waypoint[1] - pos[1], waypoint[0] - pos[0])) % 360
                                metres = min(4.5, max(0.7, dwp * 0.78))
                                cmd = {"action": "drive", "heading_deg": heading, "metres": metres}
                batch.append(cmd)
                batch_ticks.append(tick)
                if cmd["action"] == "drive":
                    newpos = sim_drive(planner.surface, pos, cmd)
                    if dist(pos, newpos) < 0.03 and dist(pos, base) > 2.5:
                        route = None
                    pos = newpos

            if batch:
                acks = tools.uplink(batch)
                for cmd, ack in zip(batch, acks):
                    execute_tick = int(ack.get("execute_tick", ack.get("tick", 0)))
                    commands[execute_tick] = cmd
                    last_scheduled = max(last_scheduled, execute_tick)

            advanced = tools.advance(min(5, MAX_TICK - current_tick))
            current_tick = int(advanced.get("current_tick", current_tick + 5))
            cycles += 1
            if cycles % 8 == 0 or current_tick >= MAX_TICK:
                print("status", json.dumps({"tick": current_tick, "mode": mode,
                                            "position": [round(pos[0], 1), round(pos[1], 1)],
                                            "battery": round(battery, 1),
                                            "sampled": len(known_sampled),
                                            "pending": sorted(pending_samples)}), flush=True)
            if advanced.get("episode_complete"):
                break
        print("mission complete", json.dumps({"tick": current_tick, "sampled": sorted(known_sampled),
                                                "mode": mode}), flush=True)


if __name__ == "__main__":
    main()
