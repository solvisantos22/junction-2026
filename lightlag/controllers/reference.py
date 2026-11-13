"""A small public-information navigator with full-horizon return budgeting."""

import math

from .api import PublicTools
from .geometry import distance
from .predictor import Predictor


class Mission:
    """Per-episode state shared by explicitly named controller ablations."""

    def __init__(self, tools, mode="reference", stop_fraction=None):
        self.tools = tools
        self.rules = tools.rules()
        self.public_map = tools.map()
        briefing = tools.telemetry_log()
        self.predictor = Predictor(self.rules, self.public_map, briefing[0])
        self.predictor.observe(briefing[1:])
        self.geometry = self.predictor.geometry
        self.mode = mode
        self.current_tick = 0
        self.cutoff = (self.rules["max_ticks"] if stop_fraction is None
                       else self.rules["max_ticks"] // stop_fraction)
        self.goal = None
        self.returning = False

    def route_budget(self, route):
        """Wheel energy and command count, with public slip uncertainty."""
        if route is None:
            return math.inf, math.inf
        energy, commands = 0.0, 0
        for start, end in zip(route, route[1:]):
            wheel = 0.0
            for terrain, metres in self.geometry.terrain_distances(start, end):
                low, high = self.rules["slip_ranges"][terrain]
                # Unseen terrain uses the public upper bound. Observed terrain
                # retains headroom for noise and a finite number of measurements.
                learned = self.predictor.observed_wheel[terrain]
                uncertainty = (high - low) / (2 + learned) + max(self.rules["slip_noise"])
                slip = min(0.9, max(high if learned == 0 else 0,
                                    self.predictor.slip[terrain] + uncertainty))
                terrain_wheel = metres / (1 - slip)
                wheel += terrain_wheel
                energy += (terrain_wheel * self.rules["drive_cost"] *
                           self.rules["terrain_drive_multipliers"][terrain])
            commands += int(math.ceil(wheel / self.rules["max_metres_per_drive"] - 1e-10))
        return energy, commands

    def feasible(self, state, target):
        point = (target["x"], target["y"])
        outbound = self.geometry.route(state.position, point)
        home = self.geometry.route(point, self.public_map["base"])
        out_energy, out_actions = self.route_budget(outbound)
        home_energy, home_actions = self.route_budget(home)
        idle_remaining = (self.rules["max_ticks"] - state.tick) * self.rules["idle_cost"]
        # This pays for a failed sample/correction and keeps terminal energy
        # positive even after all remaining idle drain, rather than only arrival.
        reserve = self.rules["sample_cost"] + 2 * self.rules["drive_cost"]
        energy = out_energy + home_energy + self.rules["sample_cost"] + idle_remaining + reserve
        cadence = 2 * self.rules["delay_ticks"] + 1 if self.mode == "move_and_wait" else 1
        actions = out_actions + 1 + home_actions + 2  # sample and two correction opportunities
        last_action = state.tick + (actions - 1) * cadence
        enough_time = last_action + self.rules["delay_ticks"] < self.rules["max_ticks"]
        return energy < state.battery and enough_time, outbound, out_energy + home_energy

    def choose_target(self, state):
        candidates = []
        for target in self.public_map["targets"]:
            if target["id"] in state.sampled:
                continue
            feasible, route, travel = self.feasible(state, target)
            if feasible:
                priority = target["value"] / (travel + self.rules["sample_cost"])
                candidates.append((-priority, target["id"], target, route))
        return min(candidates, default=(None, None, None, None))[2:]

    def drive_towards(self, state, route):
        if route is None:
            return None
        waypoint = next((point for point in route[1:] if distance(state.position, point) > 1e-7), None)
        if waypoint is None:
            return None
        wheel = sum(metres / (1 - self.predictor.slip[terrain])
                    for terrain, metres in self.geometry.terrain_distances(state.position, waypoint))
        wheel = min(wheel, self.rules["max_metres_per_drive"])
        if wheel <= 1e-7:
            return None
        heading = math.degrees(math.atan2(waypoint[1] - state.position[1],
                                          waypoint[0] - state.position[0])) % 360
        return {"action": "drive", "heading_deg": heading, "metres": wheel}

    def decide(self, state):
        if not state.alive:
            return None
        if self.goal is not None and self.goal["id"] in state.sampled:
            if (self.mode != "nominal_open_loop" and
                    self.goal["id"] not in self.predictor.anchor.sampled):
                # A predicted success is enough to stop sending duplicate
                # samples, but only delivered telemetry retires the target.
                return None
            self.goal = None
        route = None
        if not self.returning:
            if self.goal is not None:
                feasible, route, _ = self.feasible(state, self.goal)
                if not feasible:
                    self.goal = None
                    self.returning = True
            else:
                self.goal, route = self.choose_target(state)
                self.returning = self.goal is None
        if self.goal is not None:
            point = (self.goal["x"], self.goal["y"])
            if distance(state.position, point) <= self.rules["target_radius"] * 0.4:
                return {"action": "sample"}
            return self.drive_towards(state, route)
        base = self.public_map["base"]
        if distance(state.position, base) <= self.rules["base_radius"] * 0.35:
            return None
        route = self.geometry.route(state.position, base)
        command = self.drive_towards(state, route)
        if command is None:
            return None
        # If return is already difficult, spend only energy above the fixed
        # horizon's idle requirement and a positive terminal margin.
        idle_remaining = (self.rules["max_ticks"] - state.tick) * self.rules["idle_cost"]
        spare = state.battery - idle_remaining - max(0.1, self.rules["drive_cost"])
        multiplier = max(self.rules["terrain_drive_multipliers"].values())
        command["metres"] = min(command["metres"], max(0.0, spare) /
                                (self.rules["drive_cost"] * multiplier))
        return command if command["metres"] > 1e-7 else None

    def run(self):
        while self.current_tick < self.cutoff:
            execution = self.predictor.next_execution_tick(self.current_tick)
            if execution > self.rules["max_ticks"]:
                return
            state = self.predictor.forecast(execution - 1, ignore_motion=self.mode == "stale_telemetry")
            # The anchor packet already paid its own tick. Pay the proposed
            # action tick now; feasible() reserves only ticks strictly after it.
            state.tick = execution
            state.battery = max(0.0, state.battery - self.rules["idle_cost"])
            state.alive = state.battery > 0
            command = self.decide(state)
            wait_until = self.current_tick + 1
            if command is not None:
                acknowledgements = self.tools.uplink([command])
                self.predictor.acknowledge(acknowledgements)
                if self.mode == "move_and_wait":
                    wait_until = acknowledgements[-1]["execute_tick"] + self.rules["delay_ticks"]
            elif (self.predictor.anchor.tick >= self.predictor.reserved_until or
                  self.mode == "nominal_open_loop"):
                return
            wait_until = min(wait_until, self.cutoff)
            while self.current_tick < wait_until:
                reply = self.tools.advance(min(wait_until - self.current_tick,
                                               self.rules["max_advance_ticks"]))
                self.current_tick = reply["current_tick"]
                if self.mode != "nominal_open_loop":
                    self.predictor.observe(reply["packets"])
                if reply["episode_complete"]:
                    return


def reference(tools: PublicTools):
    """Learn from delivered telemetry and forecast acknowledged pending motion."""
    Mission(tools).run()
