"""The traverse reference: a pilot that plays one mission through the five public tools.

    from lightlag_traverse.pilot import fly
    fly(tools)                       # the reference
    fly(tools, {"route": "greedy"})  # the same pilot without route optimisation
    fly(tools, {"terrain": False})   # ... and without reading the ground

What it does, all from `rules()`, `map()` and telemetry:

  * Estimation. A three-state filter (position and heading bias) fed by the delayed, noisy fixes
    and the odometry; the slip of each terrain class learned from wheel against visual odometry;
    the panels' efficiency read off the first charge that was not capped.
  * Driving. For each goal a cost-to-go field over the height grid (`planning.Ground.field`),
    so the next heading is the start of the cheapest way on from wherever the rover really is,
    around crater walls and through passes, with the published slip, slide and energy.
  * Planning. Which targets, in which order: `planning.plan_route`, replanned when a target
    appears, a sample fails or the estimates move.
  * The delay. A command sent now runs `delay_ticks + 1` later, so every command is computed
    for the state the rover is predicted to be in then, given everything already queued.

Standard library only, Python 3.9+. No simulator code is imported: `surface` is the published
geometry and `planning` works on public data.
"""

from __future__ import annotations

import math
import random
from typing import Any, Dict, List, Optional, Tuple

from .planning import INF, Field, Ground, RouteProblem, Sun, plan_route
from .surface import TERRAIN_CODES, Surface, drive

DEFAULTS: Dict[str, Any] = {
    "route": "optimise",        # "optimise", or "greedy": always the best next target by value per tick
    "terrain": True,            # False: drive straight at the goal and ignore the ground
    "plan_steps": 300000,       # annealing moves for the first route
    "replan_steps": 25000,      # ... and for each later one
    "replan_every": 12,         # ticks between routine replans
    "arrive_m": 0.9,            # sample when the predicted distance to the target is under this
    "floor": 5.0,               # never start a drive that would leave less battery than this
    "home_margin": 4.0,         # be home this many ticks before the end
    "home_slack": 1.08,         # ... and count the way home this much longer than the ground model says
    "deadline_margin": 2,       # plan to sample this many ticks before a deadline
    "leg_slack": 1.0,           # a leg takes this much longer than the ground model says
    "stop_ticks": 1,            # ticks a stop costs beyond the drive to it: the sample itself
    "energy_weight": 0.25,      # ticks one unit of energy is worth when choosing a way
    "rebuild_shift": 0.035,     # rebuild the ground costs when a slip estimate has moved this much
}


class Filter:
    """Position and heading bias (degrees) with a 3 by 3 covariance."""

    def __init__(self, x: float, y: float, sensing: Dict[str, float]) -> None:
        self.x, self.y, self.bias = x, y, 0.0
        self.P = [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, sensing["heading_bias_deg"] ** 2 / 3.0]]
        self.fix_var = sensing["position_noise_m"] ** 2
        self.walk_var = sensing["heading_bias_walk_deg"] ** 2
        self.heading_noise = math.radians(sensing["heading_noise_deg"])

    def move(self, dx: float, dy: float, distance: float, heading_rad: float) -> None:
        self.x += dx
        self.y += dy
        k = math.pi / 180.0
        a, b = -distance * math.sin(heading_rad) * k, distance * math.cos(heading_rad) * k
        P = self.P
        # F = [[1, 0, a], [0, 1, b], [0, 0, 1]];  P <- F P F^T + Q
        fp = [[P[0][c] + a * P[2][c] for c in range(3)], [P[1][c] + b * P[2][c] for c in range(3)], list(P[2])]
        new = [[fp[r][0] + a * fp[r][2], fp[r][1] + b * fp[r][2], fp[r][2]] for r in range(3)]
        q = (0.04 * distance) ** 2 + (distance * self.heading_noise) ** 2 + 0.01
        new[0][0] += q
        new[1][1] += q
        new[2][2] += self.walk_var
        self.P = new

    def fix(self, zx: float, zy: float) -> None:
        P, r = self.P, self.fix_var
        s00, s01, s11 = P[0][0] + r, P[0][1], P[1][1] + r
        det = s00 * s11 - s01 * s01
        if det <= 1e-12:
            return
        i00, i01, i11 = s11 / det, -s01 / det, s00 / det
        gain = [[P[r_][0] * i00 + P[r_][1] * i01, P[r_][0] * i01 + P[r_][1] * i11] for r_ in range(3)]
        vx, vy = zx - self.x, zy - self.y
        self.x += gain[0][0] * vx + gain[0][1] * vy
        self.y += gain[1][0] * vx + gain[1][1] * vy
        self.bias += gain[2][0] * vx + gain[2][1] * vy
        self.P = [[P[r_][c] - gain[r_][0] * P[0][c] - gain[r_][1] * P[1][c] for c in range(3)] for r_ in range(3)]

    @property
    def sigma(self) -> float:
        return math.sqrt(max(self.P[0][0], self.P[1][1], 0.0))


class Pilot:
    def __init__(self, tools: Any, options: Optional[Dict[str, Any]] = None) -> None:
        self.tools = tools
        self.opt = dict(DEFAULTS, **(options or {}))
        self.rules = tools.rules()
        world = tools.map()
        self.physics = self.rules["physics"]
        self.surface = Surface(world["cell_m"], world["elevation_cm"], world["terrain"])
        self.base = tuple(world["base"])
        self.delay, self.horizon = self.rules["delay_ticks"], self.rules["max_ticks"]
        self.capacity = self.rules["battery_capacity"]
        self.max_metres = self.rules["max_metres_per_drive"]
        self.rng = random.Random(1)
        ranges = self.physics["slip_base_ranges"]
        self.slip = {name: 0.5 * (low + high) for name, (low, high) in ranges.items()}
        self.slip_seen = {name: [1.0, self.slip[name]] for name in ranges}        # weight, mean
        low, high = self.rules["solar_efficiency_range"]
        self.efficiency, self.efficiency_known = low + 0.25 * (high - low), False
        self.sun = Sun(self.rules, self.efficiency)
        self.filter = Filter(self.base[0], self.base[1], self.rules["sensing"])
        self.anchor_tick, self.anchor_battery = 0, self.rules["initial_battery"]
        self.now = 0
        self.alive = True
        self.schedule: Dict[int, Dict[str, Any]] = {}       # execute tick -> {"command", "sent"}
        self.by_id: Dict[int, int] = {}                      # command id -> execute tick
        self.reserved_until = 0
        self.targets: Dict[str, Dict[str, Any]] = {t["id"]: t for t in world["targets"]}
        self.sampled: set = set()
        self.pending: Dict[str, int] = {}                    # target id -> tick its sample runs
        self.route: List[str] = []
        self.full_plan = True                               # the next plan gets the large search budget
        self.need_plan = True
        self.last_plan = -999
        self.ground = Ground(self.surface, self.physics, self.slip, self.max_metres, self.opt["energy_weight"])
        self.built_slip = dict(self.slip)
        self.fields: Dict[str, Field] = {}
        self.nodes: Dict[str, Optional[int]] = {}
        self._field("base")
        for target_id in self.targets:
            self._field(target_id)

    # ---- geometry helpers ---------------------------------------------------------
    def _spot(self, name: str) -> Tuple[float, float]:
        if name == "base":
            return self.base
        target = self.targets[name]
        return target["x"], target["y"]

    def _field(self, name: str) -> Optional[Field]:
        if name not in self.fields:
            node = self.ground.node(*self._spot(name))
            self.nodes[name] = node
            if node is None:
                return None
            self.fields[name] = self.ground.field(node)
        return self.fields[name]

    def _rebuild(self) -> None:
        """New slip estimates: recost the ground and every cost-to-go still needed."""
        self.ground.rebuild(self.slip)
        self.built_slip = dict(self.slip)
        keep = ["base"] + [t for t in self.targets if t not in self.sampled]
        self.fields = {}
        for name in keep:
            self._field(name)
        self.need_plan = True

    def _to(self, name: str, x: float, y: float) -> Tuple[float, float]:
        """Ticks and energy from a point to a named spot, by the cost-to-go field."""
        field = self._field(name)
        node = self.ground.node(x, y)
        if field is None or node is None or field.cost[node] == INF:
            return INF, INF
        px, py = self.ground.point(node)
        hop = math.hypot(px - x, py - y) / self.max_metres
        return field.ticks[node] + hop, field.energy[node] + hop * 2.0

    # ---- telemetry ----------------------------------------------------------------
    def observe(self, packets: List[Dict[str, Any]], now: int) -> None:
        self.now = now
        for packet in packets:
            if packet["tick"] <= self.anchor_tick:
                continue
            self._packet(packet)
        moved = max(abs(self.slip[name] - self.built_slip[name]) for name in self.slip)
        if moved > self.opt["rebuild_shift"] and self.opt["terrain"]:
            self._rebuild()

    def _packet(self, packet: Dict[str, Any]) -> None:
        tick = packet["tick"]
        events = packet["events"]
        ran = self.schedule.get(tick)
        executed = any(e["type"] == "command_executed" for e in events)
        f = self.filter
        if executed and ran and ran["command"]["action"] == "drive":
            command = ran["command"]
            heading = command["heading_deg"] + f.bias
            model = drive(self.surface, self.physics, f.x, f.y, heading, command["metres"], self.slip)
            dx, dy = model["x"] - f.x, model["y"] - f.y
            expected = math.hypot(dx, dy)
            seen, wheel = packet["visual_odometry"], packet["wheel_odometry"]
            scale = seen / expected if expected > 0.2 else (1.0 if seen > 0 else 0.0)
            scale = min(2.0, max(0.0, scale))
            self._learn_slip(f.x, f.y, heading, wheel, seen)
            f.move(dx * scale, dy * scale, seen, math.radians(heading))
        f.fix(*packet["position"])
        # the panels: a charge that did not fill the battery shows their efficiency exactly
        rate = self.rules["solar_peak"] * math.sin(
            math.pi * (tick + self.rules["sun_margin_ticks"]) / (self.horizon + 2 * self.rules["sun_margin_ticks"]))
        if (not self.efficiency_known and packet["charge"] > 0 and rate > 0
                and self.anchor_battery + packet["charge"] < self.capacity - 1e-6):
            self.efficiency, self.efficiency_known = packet["charge"] / rate, True
            self.sun = Sun(self.rules, self.efficiency)
            self.need_plan = self.full_plan = True      # the first plan was made on a cautious guess
        self.anchor_tick, self.anchor_battery = tick, packet["battery"]
        if not packet["alive"]:
            self.alive = False
        for event in events:
            kind = event["type"]
            if kind == "sample_taken":
                self.sampled.add(event["target_id"])
                self.pending.pop(event["target_id"], None)
                self.need_plan = True
            elif kind == "sample_failed":
                for target_id, when in list(self.pending.items()):
                    if when == tick:
                        del self.pending[target_id]          # it is open again
                self.need_plan = True
            elif kind == "target_discovered":
                target = event["target"]
                self.targets[target["id"]] = target
                self._field(target["id"])
                self.need_plan = True
            elif kind == "safety_stop":
                # everything sent before this tick and not yet run was cleared
                for when in [w for w, item in self.schedule.items() if w > tick and item["sent"] < tick]:
                    cleared = self.schedule.pop(when)
                    if cleared["command"]["action"] == "sample":
                        for target_id, at in list(self.pending.items()):
                            if at == when:
                                del self.pending[target_id]
                if event.get("reason") == "tilt" and self.opt["terrain"]:
                    self._block(f.x, f.y)
                self.need_plan = True

    def _learn_slip(self, x: float, y: float, heading_deg: float, wheel: float, seen: float) -> None:
        if wheel < 1.5:
            return
        radians = math.radians(heading_deg)
        ux, uy = math.cos(radians), math.sin(radians)
        reach = max(seen, 0.5)
        codes, grades = set(), []
        for k in range(8):
            at = reach * (k + 0.5) / 8
            _, gx, gy, code = self.surface.sample(x + ux * at, y + uy * at)
            codes.add(code)
            grades.append(max(0.0, gx * ux + gy * uy))
        if len(codes) != 1:
            return
        name = TERRAIN_CODES[codes.pop()]
        observed = 1.0 - seen / wheel - self.physics["slip_grade_gain"][name] * sum(grades) / len(grades)
        weight, mean = self.slip_seen[name]
        weight += 1.0
        mean += (observed - mean) / weight
        self.slip_seen[name] = [weight, mean]
        low, high = self.physics["slip_base_ranges"][name]
        self.slip[name] = min(high, max(low, mean))

    def _block(self, x: float, y: float) -> None:
        """The ground stopped the rover here although the plan thought it drivable: stay away from it."""
        ground = self.ground
        for j in range(ground.ny):
            for i in range(ground.nx):
                if math.hypot(i * ground.cell - x, j * ground.cell - y) <= 7.5:
                    ground.safe[j * ground.nx + i] = False
        self._rebuild()

    # ---- prediction ---------------------------------------------------------------
    def predict(self, tick: int) -> Tuple[float, float, float, float]:
        """Position, uncertainty and battery at the start of `tick`, given what is already queued."""
        f = self.filter
        x, y, battery, sigma = f.x, f.y, self.anchor_battery, f.sigma
        for t in range(self.anchor_tick + 1, tick):
            battery = min(self.capacity, battery + self.sun.rate[min(t, self.horizon + 1)]) - self.sun.idle
            item = self.schedule.get(t)
            if item is None:
                continue
            command = item["command"]
            if command["action"] == "drive":
                model = drive(self.surface, self.physics, x, y, command["heading_deg"] + f.bias,
                              command["metres"], self.slip)
                x, y = model["x"], model["y"]
                battery -= model["energy"]
                sigma = math.hypot(sigma, 0.06 * command["metres"] + 0.1)
            elif command["action"] == "sample":
                battery -= self.rules["sample_cost"]
        return x, y, sigma, battery

    # ---- route ------------------------------------------------------------------------
    def _open(self, tick: int) -> List[str]:
        return [t for t in self.targets if t not in self.sampled and t not in self.pending
                and self.nodes.get(t) is not None]

    def _plan(self, tick: int, x: float, y: float, battery: float, steps: int) -> None:
        open_ids = self._open(tick)
        home_now = self._to("base", x, y)
        if not open_ids:
            self.route = []
        elif self.opt["route"] == "greedy":
            self.route = self._greedy(tick, x, y, open_ids)
        else:
            nodes = [self.nodes[t] for t in open_ids]
            start = [self._to(t, x, y) for t in open_ids]
            fields = [self.fields[t] for t in open_ids]
            ticks = [[fields[b].ticks[nodes[a]] for b in range(len(open_ids))] for a in range(len(open_ids))]
            energy = [[fields[b].energy[nodes[a]] for b in range(len(open_ids))] for a in range(len(open_ids))]
            base = self.fields["base"]
            problem = RouteProblem(
                self.sun, float(tick), battery,
                [self.targets[t]["value"] for t in open_ids], [self.targets[t]["deadline_tick"] for t in open_ids],
                self.rules["sample_windows"]["late_fraction"],
                [s[0] for s in start], [s[1] for s in start], ticks, energy,
                [base.ticks[n] * self.opt["home_slack"] for n in nodes], [base.energy[n] for n in nodes],
                (home_now[0] * self.opt["home_slack"], home_now[1]), self.rules["sample_cost"],
                stop_ticks=self.opt["stop_ticks"],
                home_margin=int(self.opt["home_margin"]), deadline_margin=self.opt["deadline_margin"],
                floor=self.opt["floor"] + 1.0, slack=self.opt["leg_slack"])
            previous = [open_ids.index(t) for t in self.route if t in open_ids]
            order, _ = plan_route(problem, steps, previous, self.rng)
            self.route = [open_ids[i] for i in order]
        self.need_plan = False
        self.last_plan = tick

    def _greedy(self, tick: int, x: float, y: float, open_ids: List[str]) -> List[str]:
        """No look-ahead: the target with the most value per tick that still leaves time to get home."""
        best = None
        for target_id in open_ids:
            ticks, _ = self._to(target_id, x, y)
            home = self.fields["base"].ticks[self.nodes[target_id]]
            arrive = tick + ticks + 1.0
            if ticks == INF or arrive + home * self.opt["home_slack"] > self.horizon - self.opt["home_margin"]:
                continue
            target = self.targets[target_id]
            deadline = target["deadline_tick"]
            value = target["value"] if deadline is None or arrive <= deadline - 2 else target["late_value"]
            if best is None or value / (ticks + 1.0) > best[0]:
                best = (value / (ticks + 1.0), target_id)
        return [best[1]] if best else []

    # ---- one decision ---------------------------------------------------------------
    def act(self) -> None:
        if not self.alive:
            return
        tick = max(self.now + self.delay + 1, self.reserved_until + 1)
        if tick > self.horizon:
            return
        x, y, sigma, battery = self.predict(tick)
        command = self._decide(tick, x, y, sigma, battery)
        if command is None:
            return
        try:
            acks = self.tools.uplink([command])
        except ValueError:
            return
        for ack in acks:
            self.schedule[ack["execute_tick"]] = {"command": ack["command"], "sent": ack["sent_tick"]}
            self.by_id[ack["command_id"]] = ack["execute_tick"]
            self.reserved_until = max(self.reserved_until, ack["execute_tick"])

    def _decide(self, tick: int, x: float, y: float, sigma: float, battery: float) -> Optional[Dict[str, Any]]:
        self.route = [t for t in self.route if t not in self.sampled and t not in self.pending]
        if self.need_plan or tick - self.last_plan >= self.opt["replan_every"] or (
                not self.route and self.opt["route"] == "greedy"):
            self._plan(tick, x, y, battery, self.opt["plan_steps"] if self.full_plan else self.opt["replan_steps"])
            self.full_plan = False
        left = self.horizon - tick
        home_ticks, _ = self._to("base", x, y)
        if home_ticks * self.opt["home_slack"] + self.opt["home_margin"] >= left:
            self.route = []                                    # time to go home whatever is still open
        goal = "base"
        while self.route:
            candidate = self.route[0]
            there, _ = self._to(candidate, x, y)
            back = self.fields["base"].ticks[self.nodes[candidate]]
            if there + 1.0 + back * self.opt["home_slack"] + self.opt["home_margin"] > left:
                self.route.pop(0)                              # no longer reachable in time
                self.need_plan = True
                continue
            goal = candidate
            break
        gx, gy = self._spot(goal)
        distance = math.hypot(gx - x, gy - y)
        if goal != "base" and distance <= self.opt["arrive_m"]:
            if battery - self.rules["sample_cost"] < 1.0:
                return {"action": "wait"}
            self.pending[goal] = tick
            self.route.pop(0)
            return {"action": "sample"}
        if goal == "base" and distance <= 1.2:
            return None                                        # parked at the lander
        return self._drive(goal, x, y, gx, gy, distance, battery)

    def _drive(self, goal: str, x: float, y: float, gx: float, gy: float, distance: float,
               battery: float) -> Optional[Dict[str, Any]]:
        aim = None
        if self.opt["terrain"]:
            field = self._field(goal)
            if field is not None:
                aim = self.ground.steer(x, y, field, (gx, gy))
        if aim is None:
            aim = (gx, gy, 0.0, 0.0)
        ax, ay = aim[0], aim[1]
        reach = math.hypot(ax - x, ay - y)
        if reach < 1e-6:
            return {"action": "wait"}
        want = math.atan2(ay - y, ax - x)
        ux, uy = math.cos(want), math.sin(want)
        _, sx, sy, code = self.surface.sample(x, y)
        name = TERRAIN_CODES[code]
        grade, cross = sx * ux + sy * uy, -sx * uy + sy * ux
        slip = min(0.9, self.slip[name] + self.physics["slip_grade_gain"][name] * max(0.0, grade))
        lean = math.degrees(self.physics["side_slip_gain"][name] * cross / (1.0 - slip))   # steer up the cross slope
        heading = math.degrees(want) + lean
        metres = self.max_metres
        final = (ax, ay) == (gx, gy)
        if final or reach < self.max_metres * (1.0 - slip):
            metres = min(self.max_metres, max(0.05, reach / (1.0 - slip)))
        # try the drive on the model first; shorten it rather than run onto steep ground
        for _ in range(5):
            model = drive(self.surface, self.physics, x, y, heading, metres, self.slip)
            if model["stop"] is None and self.surface.slope(model["x"], model["y"]) <= self.ground.tilt_safe * 1.08:
                break
            metres *= 0.5
            if metres < 0.2:
                return {"action": "wait"} if not self.opt["terrain"] else self._sidestep(x, y, want)
        if battery - model["energy"] - self.sun.idle < self.opt["floor"]:
            return {"action": "wait"}                          # let the sun catch up
        return {"action": "drive", "heading_deg": (heading - self.filter.bias) % 360.0, "metres": round(metres, 3)}

    def _sidestep(self, x: float, y: float, want: float) -> Dict[str, Any]:
        """Boxed in by the model: take the safest short step that does not go backwards."""
        for turn in (30, -30, 60, -60, 90, -90, 120, -120, 180):
            heading = math.degrees(want) + turn
            model = drive(self.surface, self.physics, x, y, heading, 2.0, self.slip)
            if model["stop"] is None and self.surface.slope(model["x"], model["y"]) <= self.ground.tilt_safe:
                return {"action": "drive", "heading_deg": (heading - self.filter.bias) % 360.0, "metres": 2.0}
        return {"action": "wait"}


def fly(tools: Any, options: Optional[Dict[str, Any]] = None) -> Pilot:
    """Play the whole mission. Returns the pilot, for anyone who wants to look at what it believed."""
    pilot = Pilot(tools, options)
    while True:
        pilot.act()
        out = tools.advance(1)
        pilot.observe(out["packets"], out["current_tick"])
        if out["episode_complete"]:
            return pilot
