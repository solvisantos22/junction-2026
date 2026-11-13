"""Telemetry reconciliation, slip fitting and acknowledged-command prediction.

All inputs are public dictionaries. No simulator state or seed enters this model.
"""

from copy import deepcopy
from dataclasses import dataclass
import math

from .geometry import MapGeometry, distance


@dataclass
class PredictedState:
    tick: int
    position: tuple
    battery: float
    sampled: set
    alive: bool


class Predictor:
    def __init__(self, rules, public_map, initial):
        self.rules = rules
        self.geometry = MapGeometry(public_map)
        self.slip = {terrain: sum(bounds) / 2 for terrain, bounds in rules["slip_ranges"].items()}
        self.observed_wheel = dict.fromkeys(self.slip, 0.0)
        self.slip_weight = dict.fromkeys(self.slip, 0.0)
        self.commands = {}
        self.cancelled = set()
        self.reserved_until = 0
        self.packets = {initial["tick"]: deepcopy(initial)}
        self.anchor = self.state_from_packet(initial)

    @staticmethod
    def state_from_packet(packet):
        return PredictedState(packet["tick"], tuple(packet["position"]), packet["battery"],
                              set(packet["sampled_targets"]), packet["alive"])

    def acknowledge(self, acknowledgements):
        for acknowledgement in acknowledgements:
            self.commands[acknowledgement["command_id"]] = deepcopy(acknowledgement)
            self.reserved_until = max(self.reserved_until, acknowledgement["execute_tick"])

    def next_execution_tick(self, current_tick):
        return max(current_tick + self.rules["delay_ticks"] + 1, self.reserved_until + 1)

    def observe(self, packets):
        for packet in sorted(packets, key=lambda item: item["tick"]):
            tick = packet["tick"]
            if tick in self.packets:
                continue
            self.packets[tick] = deepcopy(packet)
            events = packet["events"]
            if any(event["type"] == "safety_stop" for event in events):
                self.cancelled.update(command_id for command_id, ack in self.commands.items()
                                      if ack["execute_tick"] > tick and ack["sent_tick"] < tick)
            self.learn(packet)
            if tick > self.anchor.tick:
                self.anchor = self.state_from_packet(packet)

    def learn(self, packet):
        previous = self.packets.get(packet["tick"] - 1)
        if previous is None or not packet["alive"] or not previous["alive"]:
            return
        events = packet["events"]
        if any(event["type"] in ("safety_stop", "battery_depleted") for event in events):
            return
        executed = [event["command_id"] for event in events if event["type"] == "command_executed"]
        if len(executed) != 1:
            return
        acknowledgement = self.commands.get(executed[0])
        if acknowledgement is None or acknowledgement["command"]["action"] != "drive":
            return
        wheel, visual = packet["wheel_odometry"], packet["visual_odometry"]
        if wheel <= 1e-8 or not math.isclose(wheel, acknowledgement["command"]["metres"],
                                          rel_tol=1e-7, abs_tol=1e-7):
            return  # A partial command is not a calibration leg.
        if not math.isclose(distance(previous["position"], packet["position"]), visual,
                            rel_tol=1e-7, abs_tol=1e-7):
            return
        terrain = self.geometry.homogeneous_terrain(previous["position"], packet["position"])
        if terrain is None:
            return
        self.observed_wheel[terrain] += wheel
        self.slip_weight[terrain] += wheel - visual
        low, high = self.rules["slip_ranges"][terrain]
        self.slip[terrain] = min(high, max(low, self.slip_weight[terrain] / self.observed_wheel[terrain]))

    def forecast(self, tick, ignore_motion=False):
        """Replay unobserved actions once; the stale ablation discards motion."""
        state = deepcopy(self.anchor)
        scheduled = {ack["execute_tick"]: ack for command_id, ack in self.commands.items()
                     if command_id not in self.cancelled and ack["execute_tick"] > state.tick}
        cancelled = set(self.cancelled)
        for step in range(state.tick + 1, tick + 1):
            state.tick = step
            state.battery = max(0.0, state.battery - self.rules["idle_cost"])
            acknowledgement = scheduled.get(step)
            if (acknowledgement is not None and
                    acknowledgement["command_id"] not in cancelled and state.battery > 0):
                position = state.position
                stopped = self.apply(state, acknowledgement["command"])
                if ignore_motion:
                    state.position = position
                if stopped:
                    cancelled.update(command_id for command_id, ack in self.commands.items()
                                     if ack["execute_tick"] > step and ack["sent_tick"] < step)
            state.alive = state.battery > 0
        return state

    def apply(self, state, command):
        """Apply a public command using estimated slip; return a predicted stop."""
        if command["action"] == "sample":
            enough = state.battery >= self.rules["sample_cost"]
            state.battery = max(0.0, state.battery - self.rules["sample_cost"])
            candidates = [(distance(state.position, (target["x"], target["y"])), target["id"])
                          for target in self.geometry.map["targets"] if target["id"] not in state.sampled]
            separation, target_id = min(candidates, default=(math.inf, ""))
            if enough and separation <= self.rules["target_radius"]:
                state.sampled.add(target_id)
        elif command["action"] == "drive":
            heading = command["heading_deg"] % 360
            radians = math.radians(heading)
            dx, dy = {0: (1, 0), 90: (0, 1), 180: (-1, 0), 270: (0, -1)}.get(
                heading, (math.cos(radians), math.sin(radians)))
            remaining = command["metres"]
            while remaining > 1e-10 and state.battery > 0:
                terrain = self.geometry.terrain_at(state.position)
                cost = self.rules["drive_cost"] * self.rules["terrain_drive_multipliers"][terrain]
                wheel = min(remaining, self.rules["drive_integration_metres"], state.battery / cost)
                actual = wheel * (1 - self.slip[terrain])
                endpoint = (state.position[0] + dx * actual, state.position[1] + dy * actual)
                if not self.geometry.segment_clear(state.position, endpoint, margin=False):
                    return True
                state.position = endpoint
                state.battery = max(0.0, state.battery - cost * wheel)
                remaining -= wheel
        state.alive = state.battery > 0
        return False
