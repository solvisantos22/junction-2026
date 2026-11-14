"""Delayed public actions with independent hidden states and one shared probe.

Only the five public callbacks are for agents. Fixture controls and evaluator
methods belong to the protected simulator, never the model's interface.
"""

from copy import deepcopy
from dataclasses import asdict
import random

from .model import (
    CONTEXTS, DELAY, HORIZON, INITIAL_ENERGY, MAX_ADVANCE_TICKS,
    MAX_BATCH_SIZE, NORMALIZATION, PENALTY_PER_TICK, SIGNAL_ACCURACY,
    UNCERTAIN_ROUTES, Context, route_specs,
)


class Environment:
    def __init__(self, seed=0, context="case_1", *, terrains=None, signals=None):
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise ValueError("seed must be an integer")
        if isinstance(context, str):
            if context not in CONTEXTS:
                raise ValueError("unknown context")
            context = CONTEXTS[context]
        if not isinstance(context, Context):
            raise ValueError("context must be a context id or Context")
        for name, values in (("terrains", terrains), ("signals", signals)):
            if values is not None and (not isinstance(values, dict)
                    or set(values) != set(UNCERTAIN_ROUTES)
                    or any(value not in ("firm", "soft") for value in values.values())):
                raise ValueError(name + " fixture must map exactly a and b to firm or soft")
        self._seed = seed
        self._context = context
        self._priors = {"a": context.prior_a, "b": context.prior_b}
        self._routes = route_specs(context)
        self._terrains, self._signals = {}, {}
        for route in UNCERTAIN_ROUTES:
            terrain_draw = random.Random(f"lightlag_information_allocation:terrain:{route}:{seed}").random()
            signal_draw = random.Random(f"lightlag_information_allocation:signal:{route}:{seed}").random()
            terrain = terrains[route] if terrains is not None else ("firm" if terrain_draw < self._priors[route] else "soft")
            opposite = "soft" if terrain == "firm" else "firm"
            self._terrains[route] = terrain
            self._signals[route] = signals[route] if signals is not None else (terrain if signal_draw < SIGNAL_ACCURACY else opposite)
        self._tick = 0
        self._energy = INITIAL_ENERGY
        self._status = "ready"
        self._route = None
        self._accepted_route = None
        self._probe_accepted = False
        self._probe_used = False
        self._probe_route = None
        self._completion_tick = None
        self._scheduled_completion = None
        self._queue = []
        self._last_reserved_tick = -1
        self._transcript = []
        self._events = []
        self._event("briefing", delivery_tick=0)

    def rules(self):
        result = {
            "context": asdict(self._context),
            "priors_firm": self._priors,
            "independence": "The ground states of a and b are independent. Each route has one fixed imperfect signal, generated independently conditional on its own ground state. Inspecting one route does not update the other route's ground probability.",
            "initial_energy": INITIAL_ENERGY,
            "horizon": HORIZON,
            "delay": DELAY,
            "signal_accuracy": SIGNAL_ACCURACY,
            "penalty_per_tick": PENALTY_PER_TICK,
            "normalization": NORMALIZATION,
            "max_advance_ticks": MAX_ADVANCE_TICKS,
            "max_batch_size": MAX_BATCH_SIZE,
            "routes": self._routes,
            "command_schema": [
                {"action": "probe", "route": "a|b"},
                {"action": "commit", "route": "a|b|detour"},
                {"action": "wait"},
            ],
            "command_timing": "First execution is sent_tick + delay + 1; FIFO, one command per tick, after earlier reservations.",
            "acceptance": "Validate the entire batch, including execution at or before horizon, atomically. One probe TOTAL across both routes, before at most one commitment. Commitment is immutable on acceptance.",
            "probe": "Spend probe_energy at execution to inspect a OR b. Its fixed signal equals that route's terrain with signal_accuracy. A probe event names probe_route. One shared inspection budget; inspecting both routes or repeating a probe is forbidden. Repeated log reads add no evidence.",
            "telemetry": "Briefing at tick 0 is known; every later event arrives at state_tick + delay. Reading is free.",
            "trip": "Choose one target via a, b or the safe detour; each trip includes return home. Completion tick is commitment execution tick + route duration. Expenditure occurs on departure; insufficient energy drains battery to zero and fails the trip. No idle drain.",
            "grading": "A completed trip by horizon earns max(0, target_value - penalty_per_tick * completion_tick) / normalization; all other outcomes earn zero. Scores are realized.",
        }
        return self._record("rules", {}, result)

    def map(self):
        return self._record("map", {}, {
            "context": asdict(self._context),
            "priors_firm": self._priors,
            "terrain_states": ["firm", "soft"],
            "routes": self._routes,
            "description": "Routes a and b have independent uncertain terrain and distinct targets. The detour reaches a third target on known safe terrain. One shared probe can inspect either a or b before choosing one immutable trip.",
        })

    def telemetry_log(self):
        return self._record("telemetry_log", {}, self._visible())

    def uplink(self, commands):
        if not isinstance(commands, list) or not 1 <= len(commands) <= MAX_BATCH_SIZE:
            raise ValueError("commands must be a list containing 1 to 5 commands")
        probe_accepted = self._probe_accepted
        accepted_route = self._accepted_route
        next_tick = max(self._tick + DELAY + 1, self._last_reserved_tick + 1)
        accepted = []
        for command in commands:
            if not isinstance(command, dict):
                raise ValueError("each command must be a dictionary")
            action = command.get("action")
            if action not in ("probe", "commit", "wait"):
                raise ValueError("unknown action")
            expected_keys = {"action", "route"} if action in ("probe", "commit") else {"action"}
            if set(command) != expected_keys:
                raise ValueError("command has missing or extra fields")
            if action == "probe":
                if command["route"] not in UNCERTAIN_ROUTES:
                    raise ValueError("probe route must be a or b")
                if probe_accepted or accepted_route is not None:
                    raise ValueError("one shared probe may be accepted, before commitment only")
                probe_accepted = True
            elif action == "commit":
                if command["route"] not in ("a", "b", "detour"):
                    raise ValueError("unknown route")
                if accepted_route is not None:
                    raise ValueError("a route commitment has already been accepted")
                accepted_route = command["route"]
            if next_tick > HORIZON:
                raise ValueError("all commands must execute by the horizon")
            accepted.append({**command, "execution_tick": next_tick})
            next_tick += 1
        self._probe_accepted = probe_accepted
        self._accepted_route = accepted_route
        self._last_reserved_tick = accepted[-1]["execution_tick"]
        self._queue.extend(deepcopy(accepted))
        return self._record("uplink", {"commands": commands},
                            {"sent_tick": self._tick, "accepted": accepted})

    def advance(self, ticks=1):
        if isinstance(ticks, bool) or not isinstance(ticks, int) or not 1 <= ticks <= MAX_ADVANCE_TICKS:
            raise ValueError("ticks must be an integer from 1 to 5, not bool")
        end = min(HORIZON, self._tick + ticks)
        while self._tick < end:
            self._tick += 1
            if self._queue and self._queue[0]["execution_tick"] == self._tick:
                self._execute(self._queue.pop(0))
            if self._scheduled_completion == self._tick:
                self._completion_tick = self._tick
                self._status = "complete"
                self._event("complete")
        return self._record("advance", {"ticks": ticks}, self._visible())

    def evaluate(self):
        self._require_horizon()
        completed = self._completion_tick is not None
        reward = 0
        if completed:
            value = self._routes[self._route]["target_value"]
            reward = max(0, value - PENALTY_PER_TICK * self._completion_tick) / NORMALIZATION
        return {
            "context_id": self._context.id, "reward": reward,
            "success": completed, "completed": completed, "route": self._route,
            "completion_tick": self._completion_tick, "energy": self._energy,
            "status": self._status, "probe_used": self._probe_used,
            "probe_route": self._probe_route,
        }

    def replay(self):
        self._require_horizon()
        return deepcopy({"seed": self._seed, "context": asdict(self._context),
                         "terrains": self._terrains, "signals": self._signals,
                         "transcript": self._transcript, "events": self._events,
                         "evaluation": self.evaluate()})

    def _execute(self, command):
        action = command["action"]
        if action == "probe":
            self._energy -= self._context.probe_energy
            self._probe_used = True
            self._probe_route = command["route"]
            self._event(action, signal=self._signals[self._probe_route])
            return
        if action == "commit":
            self._route = command["route"]
            route = self._routes[self._route]
            terrain = "firm" if self._route == "detour" else self._terrains[self._route]
            cost = route["energy"][terrain]
            if self._energy < cost:
                self._energy = 0
                self._status = "failed"
            else:
                self._energy -= cost
                self._status = "traveling"
                self._scheduled_completion = self._tick + route["duration"]
        self._event(action)

    def _event(self, action, *, delivery_tick=None, **extra):
        self._events.append({"action": action, "state_tick": self._tick,
                             "delivery_tick": self._tick + DELAY if delivery_tick is None else delivery_tick,
                             "energy": self._energy, "status": self._status,
                             "route": self._route, "probe_route": self._probe_route, **extra})

    def _visible(self):
        return {"current_tick": self._tick, "entries": [
            event for event in self._events if event["delivery_tick"] <= self._tick]}

    def _record(self, method, arguments, result):
        self._transcript.append(deepcopy({"method": method, "arguments": arguments, "result": result}))
        return deepcopy(result)

    def _require_horizon(self):
        if self._tick != HORIZON:
            raise ValueError("evaluator access is available only at horizon")
