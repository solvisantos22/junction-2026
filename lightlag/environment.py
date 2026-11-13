"""Tick-based rover physics and delayed, copy-safe public observations."""

from collections import deque
from copy import deepcopy
from dataclasses import asdict
import math
import random

from .model import (Config, World, MAX_BATCH, MAX_METRES, NOISE, SEGMENT_METRES,
                    SLIP_RANGES, TERRAIN_COSTS, decode_command)


class Environment:
    def __init__(self, seed=0, config=None, world=None):
        if type(seed) is not int:
            raise ValueError("seed must be an integer")
        self._seed = seed
        self._config = config if config is not None else Config()
        self._world = world if world is not None else World()
        rng = random.Random(seed)
        self._slip = {terrain: rng.uniform(*limits) for terrain, limits in SLIP_RANGES.items()}
        self._tick = 0
        self._x, self._y = self._world.base
        self._heading = 0.0
        self._battery = self._config.initial_battery
        self._sampled = set()
        self._commands = deque()
        self._reserved_until = 0
        self._sent = []
        self._pending_packets = deque()
        initial = self._snapshot(0, 0, [])
        initial["received_tick"] = 0  # Known launch state, not a delayed measurement.
        self._received = [initial]
        self._truth = [deepcopy(initial)]

    def rules(self):
        return {
            "version": "lightlag-core-v1",
            **asdict(self._config),
            "supported_actions": ["drive", "wait"],
            "first_execution_tick": "sent_tick + delay_ticks + 1; FIFO, one command per tick",
            "telemetry_arrival_tick": "state_tick + delay_ticks; tick 0 is the initial briefing",
            "max_commands_per_uplink": MAX_BATCH,
            "max_metres_per_drive": MAX_METRES,
            "max_advance_ticks": 5,
            "slip_ranges": {name: list(bounds) for name, bounds in SLIP_RANGES.items()},
            "slip_noise": [-NOISE, NOISE],
            "terrain_drive_multipliers": dict(TERRAIN_COSTS),
            "energy_order": "idle drain, then command; drive costs per wheel metre",
            "map_edge_safety": "stop at last safe position and clear queued commands; reservations remain",
            "heading": "0 degrees east, 90 north",
            "visual_odometry": "exact in this prototype",
        }

    def map(self):
        return self._world.public_map()

    def telemetry_log(self):
        return deepcopy(self._received)

    def uplink(self, commands):
        if not isinstance(commands, list) or not 1 <= len(commands) <= MAX_BATCH:
            raise ValueError(f"commands must be a list of 1..{MAX_BATCH} commands")
        if self._tick >= self._config.max_ticks:
            raise ValueError("episode complete")
        decoded = [decode_command(command) for command in commands]
        first_tick = max(self._tick + self._config.delay_ticks + 1, self._reserved_until + 1)
        if first_tick + len(decoded) - 1 > self._config.max_ticks:
            raise ValueError("commands would execute beyond the episode horizon")
        acknowledgements = [
            {"command_id": len(self._sent) + index + 1, "sent_tick": self._tick,
             "execute_tick": first_tick + index, "command": command}
            for index, command in enumerate(decoded)
        ]
        self._commands.extend(deepcopy(acknowledgements))
        self._sent.extend(deepcopy(acknowledgements))
        self._reserved_until = acknowledgements[-1]["execute_tick"]
        return acknowledgements

    def advance(self, ticks=1):
        if type(ticks) is not int or not 1 <= ticks <= 5:
            raise ValueError("ticks must be an integer from 1 to 5")
        arrived = []
        for _ in range(min(ticks, self._config.max_ticks - self._tick)):
            self._step()
            while self._pending_packets and self._pending_packets[0]["received_tick"] <= self._tick:
                packet = self._pending_packets.popleft()
                self._received.append(packet)
                arrived.append(packet)
        return {"current_tick": self._tick,
                "episode_complete": self._tick == self._config.max_ticks,
                "packets": deepcopy(arrived)}

    def _step(self):
        self._tick += 1
        events = []
        wheel, visual = 0.0, 0.0
        was_alive = self._battery > 0
        self._spend(self._config.idle_cost)
        if self._battery > 0 and self._commands and self._commands[0]["execute_tick"] == self._tick:
            queued = self._commands.popleft()
            command = queued["command"]
            events.append({"type": "command_executed", "command_id": queued["command_id"]})
            if command["action"] == "drive":
                wheel, visual = self._drive(command, events)
        if self._battery == 0:
            self._commands.clear()
            if was_alive:
                events.append({"type": "battery_depleted"})
        snapshot = self._snapshot(wheel, visual, events)
        self._truth.append(deepcopy(snapshot))
        self._pending_packets.append(snapshot)

    def _spend(self, amount):
        self._battery = max(0.0, self._battery - amount)
        if self._battery < 1e-10:
            self._battery = 0.0

    def _drive(self, command, events):
        self._heading = command["heading_deg"]
        radians = math.radians(self._heading)
        # Exact cardinal vectors avoid tiny outward drift when following an edge.
        cardinal = {0: (1, 0), 90: (0, 1), 180: (-1, 0), 270: (0, -1)}
        dx, dy = cardinal.get(self._heading, (math.cos(radians), math.sin(radians)))
        noise = random.Random(f"{self._seed}:drive:{self._tick}").uniform(-NOISE, NOISE)
        remaining = command["metres"]
        wheel, visual = 0.0, 0.0
        while remaining > 1e-10 and self._battery > 0:
            terrain = self._world.terrain_at(self._x, self._y)
            cost = self._config.drive_cost * TERRAIN_COSTS[terrain]
            segment = min(SEGMENT_METRES, remaining, self._battery / cost)
            slip = min(0.9, max(0.0, self._slip[terrain] + noise))
            distance = segment * (1 - slip)
            next_x, next_y = self._x + dx * distance, self._y + dy * distance
            if not (0 <= next_x <= self._world.width and 0 <= next_y <= self._world.height):
                events.append({"type": "safety_stop", "reason": "map_boundary"})
                self._commands.clear()
                break
            self._x, self._y = next_x, next_y
            self._spend(segment * cost)
            wheel += segment
            visual += distance
            remaining -= segment
        return wheel, visual

    def _snapshot(self, wheel, visual, events):
        return {
            "tick": self._tick, "received_tick": self._tick + self._config.delay_ticks,
            "position": [round(self._x, 10), round(self._y, 10)],
            "heading_deg": self._heading, "battery": round(self._battery, 10),
            "terrain": self._world.terrain_at(self._x, self._y),
            "wheel_odometry": round(wheel, 10), "visual_odometry": round(visual, 10),
            "sampled_targets": sorted(self._sampled), "alive": self._battery > 0,
            "events": events,
        }
