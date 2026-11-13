"""Run a controller through an episode using only the five public methods.

Two entry points:

- `drive(tools, controller)` plays the episode through any object exposing
  rules(), map(), telemetry_log(), uplink() and advance(). It never scores.
- `as_policy(strategy)` wraps a controller as a `policy(tools)` callable for
  `lightlag.evaluation.run_episode`, the team's evaluator-side runner.

`run_episode(env, controller)` is a small evaluator-side helper for the pilot: it
drives the episode and then calls the evaluator-only `evaluate()`.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from .adapter import ack_exec_ticks, command_to_json, parse_map, parse_packets, parse_rules
from .controllers import Controller, Strategy, Tuning, make
from .model import Packet


def drive(tools: Any, controller: Controller) -> Dict[str, int]:
    """Play one episode to its horizon through the public tools. Returns usage counts."""
    rules = parse_rules(tools.rules())
    world = parse_map(tools.map())
    controller.reset(rules, world, parse_packets(tools.telemetry_log()))
    tick = 0
    new_packets: List[Packet] = []
    usage = {"uplinks": 0, "advances": 0, "commands_sent": 0, "rejected_uplinks": 0}
    while tick < rules.horizon:
        commands, ticks = controller.step(tick, new_packets)
        if commands:
            try:
                acks = tools.uplink([command_to_json(c) for c in commands])
            except ValueError:
                usage["rejected_uplinks"] += 1
            else:
                controller.on_ack(commands, ack_exec_ticks(acks), tick)
                usage["uplinks"] += 1
                usage["commands_sent"] += len(commands)
        ticks = max(1, min(rules.max_advance, ticks, rules.horizon - tick))
        result = tools.advance(ticks)
        usage["advances"] += 1
        new_packets = parse_packets(result["packets"])
        tick = int(result["current_tick"])
    return usage


def as_policy(strategy: Strategy, tuning: Optional[Tuning] = None) -> Callable[[Any], None]:
    """A `policy(tools)` callable for `lightlag.evaluation.run_episode`.

    A fresh controller is built for every episode, so no state carries over.
    """

    def policy(tools: Any) -> None:
        drive(tools, make(strategy, tuning))

    policy.__name__ = strategy.name
    return policy


def run_episode(env: Any, controller: Controller) -> Dict[str, Any]:
    """Drive `env` to its horizon, then score it with the evaluator-only evaluate()."""
    usage = drive(env, controller)
    evaluation = env.evaluate()
    outcome: Dict[str, Any] = {
        "controller": controller.name,
        "raw_score": evaluation["raw_score"],
        "max_value": evaluation["max_available_value"],
        "sampled": list(evaluation["sampled_targets"]),
        "alive": bool(evaluation["alive"]),
        "at_base": bool(evaluation["at_base"]),
    }
    outcome.update(usage)
    return outcome
