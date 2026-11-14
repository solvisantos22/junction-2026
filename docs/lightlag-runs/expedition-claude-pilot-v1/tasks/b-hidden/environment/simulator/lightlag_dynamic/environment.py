"""The team's Lightlag Environment plus sample windows and mid-mission discoveries.

Physics, timing, energy, safety stops and the five public methods are inherited unchanged.
The noisy profiles ("noisy", "rush_noisy") add two published effects on top:
  * heading drift: every executed drive travels at the commanded heading plus a hidden bias
    (a slow random walk) plus independent noise; telemetry still reports the commanded heading;
  * noisy sensing: delivered position fixes and visual odometry carry seeded Gaussian noise.
The evaluator's truth (states in the replay, scoring) always uses the true position.

This subclass relies on these private hooks of lightlag.Environment (checked by
tests/lightlag_dynamic/test_dynamic.py): _sample, _snapshot, _step, _drive, _tick, _sampled, _world,
_config, _battery, _x, _y, _spend, _heading, _seed, _pending_packets, _slip, _commands.
The experimental bumpiness option repeats the parent's drive loop in _drive_rough.
"""

from dataclasses import asdict
import math
import random

from lightlag import Config, Environment
from lightlag.model import NOISE, SEGMENT_METRES, TERRAIN_COSTS

from .missions import ROUGHNESS, make_mission


class DynamicEnvironment(Environment):
    def __init__(self, seed=0, config=None, profile="dynamic", mission=None, noise_level=1.0,
                 bumpiness=0.0):
        if config is None:
            from .missions import PROFILES
            config = Config(max_ticks=PROFILES[profile][4])
        if mission is None:
            mission = make_mission(profile, seed, config.max_ticks, noise_level, bumpiness)
        # Set before the parent constructor: it takes the tick-0 snapshot through _snapshot.
        self._mission = mission
        self._plans = {plan.id: plan for plan in mission.plans}
        self._sample_ticks = {}
        self._sensing = mission.sensing
        self._heading_errors = []
        self._heading_bias = 0.0
        if self._sensing:
            limit = self._sensing["heading_bias_deg"]
            self._heading_bias = random.Random(f"lightlag-dynamic-heading:{seed}").uniform(-limit, limit)
        self._initial_heading_bias = self._heading_bias
        self._roughness = mission.roughness
        self._rough = self._rough_cells(seed, mission) if self._roughness else frozenset()
        self._spins = []
        super().__init__(seed=seed, config=config, world=mission.world)

    @staticmethod
    def _rough_cells(seed, mission):
        """Seeded rough 1 m cells. One draw per cell, so a higher bumpiness adds cells."""
        world, size = mission.world, ROUGHNESS["cell_m"]
        rng = random.Random(f"lightlag-dynamic-rough:{seed}")
        keep_clear = [world.base] + [(t.x, t.y) for t in world.targets]
        cells = set()
        for ix in range(int(math.ceil(world.width / size))):
            for iy in range(int(math.ceil(world.height / size))):
                draw = rng.random()
                centre = ((ix + 0.5) * size, (iy + 0.5) * size)
                if draw < mission.bumpiness and all(math.dist(centre, p) > 1.5 for p in keep_clear):
                    cells.add((ix, iy))
        return frozenset(cells)

    # ---- public tools -------------------------------------------------------------
    def rules(self):
        rules = super().rules()
        rules.update(self._mission.public_rules())
        rules.update({
            "version": "lightlag-dynamic-v1",
            "sampling": ("pay sampling cost; collect the nearest unsampled active target within "
                         "target_radius; a discovered target is active from its appear tick"),
            "reward": ("sum over sampled targets of value if the sample executed at or before "
                       "deadline_tick, otherwise value * late_fraction; times 1 at base, 0.5 alive "
                       "elsewhere, 0 if dead; scored at the horizon"),
            "sample_windows": {"late_fraction": self._mission.late_fraction,
                               "deadline": "deadline_tick per target in map(); null means no deadline"},
            "discoveries": ("new targets can appear mid-mission; a target_discovered event in the "
                            "telemetry packet for its appear tick announces it, so it arrives "
                            "delay_ticks later, and map() lists it from then on"),
        })
        if self._sensing:
            rules.update({
                "heading": ("0 degrees east, 90 north; each executed drive travels at the commanded "
                            "heading plus a heading error: a hidden bias, uniform in "
                            "+-heading_bias_deg at launch, which takes a Gaussian random-walk step of "
                            "heading_bias_walk_deg before every executed drive, plus independent "
                            "Gaussian noise of heading_noise_deg; telemetry heading_deg reports the "
                            "commanded heading"),
                "visual_odometry": ("reported distance = true distance * (1 + Gaussian noise with "
                                    "std dev visual_odometry_noise)"),
                "position_fix": ("every delivered position after the tick-0 briefing = true position + "
                                 "independent Gaussian noise with std dev position_noise_m per axis, "
                                 "clipped to the map; the tick-0 briefing position is exact; the "
                                 "terrain field reports the terrain under the rover"),
                "scoring_position": "sampling, base return and safety stops use the true position",
            })
        if self._roughness:
            rules["terrain_roughness"] = (
                "experimental: map() lists rough cells (rough_cell_m squares); each time a drive enters "
                "a rough cell it jolts sideways by Gaussian noise of jolt_m, and with probability "
                "spin_chance the wheels spin in place for a wheel distance uniform in spin_wheel_m: "
                "wheel odometry and energy count it, the rover does not move; spins and jolts are "
                "fixed by the seed and execution tick")
        return rules

    def map(self):
        public = super().map()
        public["targets"] = [self._public_target(t) for t in public["targets"]
                             if self._announced(self._plans[t["id"]])]
        if self._roughness:
            public["rough_cell_m"] = self._roughness["cell_m"]
            public["rough_cells"] = [list(cell) for cell in sorted(self._rough)]
        return public

    # ---- evaluator-only -----------------------------------------------------------
    def evaluate(self):
        result = super().evaluate()
        samples, value = [], 0.0
        for target in self._world.targets:
            if target.id not in self._sampled:
                continue
            plan, tick = self._plans[target.id], self._sample_ticks[target.id]
            on_time = plan.deadline_tick is None or tick <= plan.deadline_tick
            credited = target.value if on_time else target.value * self._mission.late_fraction
            value += credited
            samples.append({"target_id": target.id, "tick": tick, "on_time": on_time,
                            "credited_value": credited})
        result.update({"sampled_value": value, "raw_score": value * result["survival_factor"],
                       "samples": samples, "mission_profile": self._mission.profile})
        return result

    def replay(self):
        replay = super().replay()
        replay["world"] = self._world.public_map()  # full truth, including undiscovered targets
        replay["dynamic"] = {"version": "lightlag-dynamic-v1", **self._mission.to_dict()}
        if self._sensing:
            # states hold the true positions; received_telemetry holds what was reported.
            replay["dynamic"]["sensing"] = {**self._sensing,
                                            "initial_heading_bias_deg": self._initial_heading_bias,
                                            "heading_errors": list(self._heading_errors)}
        if self._roughness:
            replay["dynamic"]["roughness"] = {**self._roughness, "spins": list(self._spins)}
        return replay

    # ---- hooks into the team's simulator ------------------------------------------
    def _announced(self, plan):
        return plan.appear_tick == 0 or self._tick >= plan.appear_tick + self._config.delay_ticks

    def _public_target(self, target):
        plan = self._plans[target["id"]]
        late = target["value"] * self._mission.late_fraction if plan.deadline_tick is not None else target["value"]
        return {**target, "deadline_tick": plan.deadline_tick, "late_value": late,
                "appear_tick": plan.appear_tick}

    def _sample(self, events):
        enough_energy = self._battery >= self._config.sample_cost
        self._spend(self._config.sample_cost)
        if not enough_energy:
            events.append({"type": "sample_failed", "reason": "insufficient_energy"})
            return
        candidates = [(math.hypot(t.x - self._x, t.y - self._y), t.id) for t in self._world.targets
                      if t.id not in self._sampled and self._plans[t.id].appear_tick <= self._tick]
        distance, target_id = min(candidates, default=(math.inf, ""))
        if distance <= self._config.target_radius:
            self._sampled.add(target_id)
            self._sample_ticks[target_id] = self._tick
            plan = self._plans[target_id]
            on_time = plan.deadline_tick is None or self._tick <= plan.deadline_tick
            events.append({"type": "sample_taken", "target_id": target_id, "on_time": on_time})
        else:
            events.append({"type": "sample_failed", "reason": "no_unsampled_target_in_range"})

    def _step(self):
        super()._step()
        if self._sensing:
            # The truth list already holds an exact copy; only the delivered packet is measured.
            self._pending_packets[-1] = self._measured(self._pending_packets[-1])

    def _measured(self, packet):
        rng = random.Random(f"{self._seed}:sense:{packet['tick']}")
        sigma = self._sensing["position_noise_m"]
        x, y = packet["position"]
        x = min(self._world.width, max(0.0, x + rng.gauss(0.0, sigma)))
        y = min(self._world.height, max(0.0, y + rng.gauss(0.0, sigma)))
        visual = packet["visual_odometry"]
        if visual > 0:
            visual = max(0.0, visual * (1.0 + rng.gauss(0.0, self._sensing["visual_odometry_noise"])))
        return {**packet, "position": [round(x, 10), round(y, 10)],
                "visual_odometry": round(visual, 10)}

    def _drive(self, command, events):
        commanded = command["heading_deg"]
        if self._sensing:
            rng = random.Random(f"{self._seed}:heading:{self._tick}")
            self._heading_bias += rng.gauss(0.0, self._sensing["heading_bias_walk_deg"])
            error = self._heading_bias + rng.gauss(0.0, self._sensing["heading_noise_deg"])
            self._heading_errors.append({"tick": self._tick, "error_deg": round(error, 6),
                                         "bias_deg": round(self._heading_bias, 6)})
            command = dict(command, heading_deg=(commanded + error) % 360.0)
        if self._rough:
            result = self._drive_rough(command, events)
        else:
            result = super()._drive(command, events)
        self._heading = commanded  # telemetry reports the commanded heading
        return result

    def _cell(self, x, y):
        size = self._roughness["cell_m"]
        return (int(x // size), int(y // size))

    def _drive_rough(self, command, events):
        """The team's drive loop (lightlag.Environment._drive) plus spins and jolts in rough cells.

        Kept line-for-line with the parent where it overlaps; a test checks that with no rough
        cell on the path it gives the parent's result.
        """
        self._heading = command["heading_deg"]
        radians = math.radians(self._heading)
        cardinal = {0: (1, 0), 90: (0, 1), 180: (-1, 0), 270: (0, -1)}
        dx, dy = cardinal.get(self._heading, (math.cos(radians), math.sin(radians)))
        noise = random.Random(f"{self._seed}:drive:{self._tick}").uniform(-NOISE, NOISE)
        rough = random.Random(f"{self._seed}:rough:{self._tick}")
        cell = self._cell(self._x, self._y)
        remaining = command["metres"]
        wheel, visual = 0.0, 0.0
        while remaining > 1e-10 and self._battery > 0:
            terrain = self._world.terrain_at(self._x, self._y)
            cost = self._config.drive_cost * TERRAIN_COSTS[terrain]
            segment = min(SEGMENT_METRES, remaining, self._battery / cost)
            slip = min(0.9, max(0.0, self._slip[terrain] + noise))
            distance = segment * (1 - slip)
            next_x, next_y = self._x + dx * distance, self._y + dy * distance
            if not self._safe_move(next_x, next_y, events):
                break
            self._x, self._y = next_x, next_y
            self._spend(segment * cost)
            wheel += segment
            visual += distance
            remaining -= segment
            entered = self._cell(self._x, self._y)
            if entered == cell:
                continue
            cell = entered
            if cell not in self._rough:
                continue
            jolt = rough.gauss(0.0, self._roughness["jolt_m"])
            jolt_x, jolt_y = self._x - dy * jolt, self._y + dx * jolt
            if not self._safe_move(jolt_x, jolt_y, events):
                break
            self._x, self._y = jolt_x, jolt_y
            spun = 0.0
            if rough.random() < self._roughness["spin_chance"]:
                spun = min(rough.uniform(*self._roughness["spin_wheel_m"]), remaining,
                           self._battery / cost)
                self._spend(spun * cost)
                wheel += spun
                remaining -= spun
            self._spins.append({"tick": self._tick, "cell": list(cell), "jolt_m": round(jolt, 6),
                                "spin_wheel_m": round(spun, 6)})
        return wheel, visual

    def _safe_move(self, x, y, events):
        if not (0 <= x <= self._world.width and 0 <= y <= self._world.height):
            events.append({"type": "safety_stop", "reason": "map_boundary"})
            self._commands.clear()
            return False
        if any(region.intersects_segment(self._x, self._y, x, y) for region in self._world.hazards):
            events.append({"type": "safety_stop", "reason": "hazard"})
            self._commands.clear()
            return False
        return True

    def _snapshot(self, wheel, visual, events):
        for plan in self._mission.plans:
            if plan.appear_tick and plan.appear_tick == self._tick:
                target = next(asdict(t) for t in self._world.targets if t.id == plan.id)
                events.append({"type": "target_discovered", "target": self._public_target(target)})
        return super()._snapshot(wheel, visual, events)
