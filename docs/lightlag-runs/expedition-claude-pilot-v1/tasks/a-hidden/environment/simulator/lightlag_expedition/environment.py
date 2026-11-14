"""Delayed physical rover mission with a limited choice of regional science inspections."""

from copy import deepcopy
import random

from lightlag import Config
from lightlag.model import MAX_BATCH
from lightlag_dynamic.environment import DynamicEnvironment

from .missions import generator_rules, make_mission
from .model import (HORIZON, INSPECTION_ACCURACY, INSPECTION_BUDGET, INSPECTION_ENERGY,
                    PRIORS, QUALITY_MULTIPLIERS, REGIONS, TARGET_REGIONS, VERSION,
                    decode_command, validate_fixture)


class ExpeditionEnvironment(DynamicEnvironment):
    def __init__(self, seed=0, mission_seed=0, visibility="hidden", config=None,
                 quality_fixture=None, signal_fixture=None):
        if type(seed) is not int:
            raise ValueError("seed must be an integer")
        if visibility not in ("hidden", "public"):
            raise ValueError("visibility must be hidden or public")
        self._mission_seed = mission_seed
        self._visibility = visibility
        quality_fixture = validate_fixture(quality_fixture, "quality_fixture")
        signal_fixture = validate_fixture(signal_fixture, "signal_fixture")
        self._qualities = quality_fixture if quality_fixture is not None else {
            region: ("rich" if random.Random(f"lightlag-expedition-quality:{seed}:{region}").random()
                     < PRIORS[region] else "poor") for region in REGIONS}
        self._signals = signal_fixture if signal_fixture is not None else {
            region: (self._qualities[region]
                     if random.Random(f"lightlag-expedition-signal:{seed}:{region}").random() < INSPECTION_ACCURACY
                     else ("poor" if self._qualities[region] == "rich" else "rich")) for region in REGIONS}
        self._inspection_reserved = set()
        self._inspection_executed = []
        super().__init__(seed=seed, config=config if config is not None else Config(max_ticks=HORIZON),
                         profile="rush_noisy", mission=make_mission(mission_seed))

    def rules(self):
        rules = super().rules()
        science = {
            "regions": {region: {"prior_rich": PRIORS[region]} for region in REGIONS},
            "quality_multipliers": dict(QUALITY_MULTIPLIERS),
            "quality_model": "independent region qualities, fixed for the episode; every target in a region shares its quality",
            "inspection_budget": INSPECTION_BUDGET,
            "inspection_energy": INSPECTION_ENERGY,
            "inspection_accuracy": INSPECTION_ACCURACY,
            "inspection_model": "one fixed signal per region; correct with inspection_accuracy independently conditional on quality",
            "inspection_reservation": "at most once per region, two globally; accepted commands reserve budget even if the queue is later cleared",
            "inspection_reserved_regions": sorted(self._inspection_reserved),
            "inspection_remaining": INSPECTION_BUDGET - len(self._inspection_reserved),
            "sample_learning": "a successful physical sample reveals that region's exact quality in its delayed telemetry packet",
            "visibility": self._visibility,
        }
        if self._visibility == "public":
            science["public_qualities"] = dict(self._qualities)
        rules.update({
            "version": VERSION, "mission_profile": "expedition", "profile_default_horizon": HORIZON,
            "map_generator": generator_rules(), "science": science,
            "supported_actions": ["drive", "sample", "wait", "inspect"],
            "inspection": ("inspect(region: r1|r2|r3) uses the normal FIFO queue and telemetry delay; "
                           "pays inspection_energy after idle drain; insufficient energy spends the remainder without a signal"),
            "reward": ("sum base_value * region quality multiplier * deadline factor for successful samples, "
                       "times 1 at base, 0.5 alive elsewhere, or 0 if dead at the horizon; "
                       "max_available_value is the public all-rich upper bound 20, never the realized hidden total"),
        })
        return deepcopy(rules)

    def _public_target(self, target):
        return {**super()._public_target(target), "region": TARGET_REGIONS[target["id"]],
                "base_value": target["value"]}

    def uplink(self, commands):
        if not isinstance(commands, list) or not 1 <= len(commands) <= MAX_BATCH:
            raise ValueError(f"commands must be a list of 1..{MAX_BATCH} commands")
        if self._tick >= self._config.max_ticks:
            raise ValueError("episode complete")
        decoded = [decode_command(command) for command in commands]
        reserved = set(self._inspection_reserved)
        for command in decoded:
            if command["action"] != "inspect":
                continue
            region = command["region"]
            if region in reserved:
                raise ValueError("each region may be inspected at most once")
            reserved.add(region)
            if len(reserved) > INSPECTION_BUDGET:
                raise ValueError("global inspection budget exhausted")
        first_tick = max(self._tick + self._config.delay_ticks + 1, self._reserved_until + 1)
        if first_tick + len(decoded) - 1 > self._config.max_ticks:
            raise ValueError("commands would execute beyond the episode horizon")
        acknowledgements = [
            {"command_id": len(self._sent) + index + 1, "sent_tick": self._tick,
             "execute_tick": first_tick + index, "command": command}
            for index, command in enumerate(decoded)]
        # Commit every reservation only after validating the entire batch and its horizon.
        self._commands.extend(deepcopy(acknowledgements))
        self._sent.extend(deepcopy(acknowledgements))
        self._reserved_until = acknowledgements[-1]["execute_tick"]
        self._inspection_reserved = reserved
        return deepcopy(acknowledgements)

    def _step(self):
        # Mirrors lightlag.Environment._step with only the inspect dispatch added. Keep
        # DynamicEnvironment's measured-packet transformation after the truth snapshot.
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
            elif command["action"] == "sample":
                self._sample(events)
            elif command["action"] == "inspect":
                self._inspect(command["region"], events)
        if self._battery == 0:
            self._commands.clear()
            if was_alive:
                events.append({"type": "battery_depleted"})
        snapshot = self._snapshot(wheel, visual, events)
        self._truth.append(deepcopy(snapshot))
        self._pending_packets.append(self._measured(snapshot) if self._sensing else snapshot)

    def _inspect(self, region, events):
        enough_energy = self._battery >= INSPECTION_ENERGY
        self._spend(INSPECTION_ENERGY)
        self._inspection_executed.append({"region": region, "tick": self._tick, "success": enough_energy})
        if enough_energy:
            events.append({"type": "inspection_result", "region": region, "signal": self._signals[region]})
        else:
            events.append({"type": "inspection_failed", "region": region, "reason": "insufficient_energy"})

    def _sample(self, events):
        start = len(events)
        super()._sample(events)
        for event in events[start:]:
            if event["type"] == "sample_taken":
                target_id = event["target_id"]
                region = TARGET_REGIONS[target_id]
                events.append({"type": "region_quality", "region": region,
                               "quality": self._qualities[region], "target_id": target_id})

    def evaluate(self):
        result = super().evaluate()
        samples, value = [], 0.0
        for sample in result["samples"]:
            target_id = sample["target_id"]
            region = TARGET_REGIONS[target_id]
            quality = self._qualities[region]
            multiplier = QUALITY_MULTIPLIERS[quality]
            credited = sample["credited_value"] * multiplier
            value += credited
            samples.append({**sample, "region": region, "quality": quality,
                            "base_value": self._plans[target_id].value, "quality_multiplier": multiplier,
                            "base_credited_value": sample["credited_value"], "credited_value": credited})
        result.update({"mission_profile": "expedition", "sampled_value": value,
                       "raw_score": value * result["survival_factor"], "samples": samples})
        return result

    def replay(self):
        replay = super().replay()
        replay["world"]["targets"] = [self._public_target(target) for target in replay["world"]["targets"]]
        replay["expedition"] = {
            "version": VERSION, "mission_seed": self._mission_seed, "visibility": self._visibility,
            "qualities": dict(self._qualities), "signals": dict(self._signals),
            "inspection_reserved_regions": sorted(self._inspection_reserved),
            "inspection_executed": deepcopy(self._inspection_executed),
            "map_generator": generator_rules(),
        }
        return deepcopy(replay)
