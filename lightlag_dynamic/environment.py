"""The team's Lightlag Environment plus sample windows and mid-mission discoveries.

Physics, timing, energy, safety stops and the five public methods are inherited unchanged.
This subclass relies on these private hooks of lightlag.Environment (checked by
tests/lightlag_dynamic/test_dynamic.py): _sample, _snapshot, _tick, _sampled, _world, _config, _battery,
_x, _y, _spend.
"""

from dataclasses import asdict
import math

from lightlag import Config, Environment

from .missions import make_mission


class DynamicEnvironment(Environment):
    def __init__(self, seed=0, config=None, profile="dynamic", mission=None):
        if config is None:
            from .missions import PROFILES
            config = Config(max_ticks=PROFILES[profile][4])
        mission = mission if mission is not None else make_mission(profile, seed, config.max_ticks)
        # Set before the parent constructor: it takes the tick-0 snapshot through _snapshot.
        self._mission = mission
        self._plans = {plan.id: plan for plan in mission.plans}
        self._sample_ticks = {}
        super().__init__(seed=seed, config=config, world=mission.world)

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
        return rules

    def map(self):
        public = super().map()
        public["targets"] = [self._public_target(t) for t in public["targets"]
                             if self._announced(self._plans[t["id"]])]
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

    def _snapshot(self, wheel, visual, events):
        for plan in self._mission.plans:
            if plan.appear_tick and plan.appear_tick == self._tick:
                target = next(asdict(t) for t in self._world.targets if t.id == plan.id)
                events.append({"type": "target_discovered", "target": self._public_target(target)})
        return super()._snapshot(wheel, visual, events)
