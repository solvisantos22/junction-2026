"""Run one controller through one episode using only the five public methods."""

from __future__ import annotations

from typing import Any, Dict, List

from .adapter import ack_exec_ticks, command_to_json, parse_map, parse_packets, parse_rules
from .controllers import Controller
from .model import Packet


def run_episode(env: Any, controller: Controller) -> Dict[str, Any]:
    """Drive `env` to its horizon, then score it.

    The controller sees rules(), map(), telemetry_log(), uplink() and advance().
    evaluate() is the evaluator's method and is called only here, after the horizon.
    """
    rules = parse_rules(env.rules())
    world = parse_map(env.map())
    controller.reset(rules, world, parse_packets(env.telemetry_log()))
    tick = 0
    new_packets: List[Packet] = []
    uplinks = advances = commands_sent = rejected = 0
    while tick < rules.horizon:
        commands, ticks = controller.step(tick, new_packets)
        if commands:
            try:
                acks = env.uplink([command_to_json(c) for c in commands])
            except ValueError:
                rejected += 1
            else:
                controller.on_ack(commands, ack_exec_ticks(acks), tick)
                uplinks += 1
                commands_sent += len(commands)
        ticks = max(1, min(rules.max_advance, ticks, rules.horizon - tick))
        result = env.advance(ticks)
        advances += 1
        new_packets = parse_packets(result["packets"])
        tick = int(result["current_tick"])
    evaluation = env.evaluate()
    return {
        "controller": controller.name,
        "raw_score": evaluation["raw_score"],
        "max_value": evaluation["max_available_value"],
        "sampled": list(evaluation["sampled_targets"]),
        "alive": bool(evaluation["alive"]),
        "at_base": bool(evaluation["at_base"]),
        "uplinks": uplinks,
        "advances": advances,
        "commands_sent": commands_sent,
        "rejected_uplinks": rejected,
    }
