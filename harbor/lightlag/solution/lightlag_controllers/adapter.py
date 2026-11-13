"""Translate the simulator's public JSON (lightlag-core-v1) into controller-side types.

This is the only module that knows field names. It reads nothing but the results
of the five public methods.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Sequence

from .model import Command, Packet, Rect, Rules, Target, TerrainSpec, World

EVENT_NAMES = {"battery_depleted": "battery_dead"}


def _rect(value: Mapping[str, Any]) -> Rect:
    return Rect(float(value["x1"]), float(value["y1"]), float(value["x2"]), float(value["y2"]))


def parse_rules(data: Mapping[str, Any]) -> Rules:
    noise = data["slip_noise"]
    noise = max(abs(float(v)) for v in noise) if isinstance(noise, (list, tuple)) else abs(float(noise))
    base_cost = float(data["drive_cost"])
    terrains: Dict[str, TerrainSpec] = {
        name: TerrainSpec(
            name, float(low), float(high), base_cost * float(data["terrain_drive_multipliers"][name])
        )
        for name, (low, high) in data["slip_ranges"].items()
    }
    return Rules(
        delay=int(data["delay_ticks"]),
        horizon=int(data["max_ticks"]),
        battery=float(data["initial_battery"]),
        idle_cost=float(data["idle_cost"]),
        sample_cost=float(data["sample_cost"]),
        sample_radius=float(data["target_radius"]),
        base_radius=float(data["base_radius"]),
        max_drive=float(data["max_metres_per_drive"]),
        max_uplink=int(data["max_commands_per_uplink"]),
        max_advance=int(data["max_advance_ticks"]),
        segment=float(data["drive_integration_metres"]),
        slip_noise=noise,
        terrains=terrains,
    )


def parse_map(data: Mapping[str, Any]) -> World:
    return World(
        width=float(data["width"]),
        height=float(data["height"]),
        base=(float(data["base"][0]), float(data["base"][1])),
        targets=tuple(
            Target(str(t["id"]), float(t["x"]), float(t["y"]), float(t["value"])) for t in data["targets"]
        ),
        hazards=tuple(_rect(h) for h in data["hazards"]),
        patches=tuple((_rect(r), "sand") for r in data["sand"]),
        default_terrain=str(data["default_terrain"]),
    )


def parse_packet(data: Mapping[str, Any]) -> Packet:
    events = tuple(EVENT_NAMES.get(e["type"], e["type"]) for e in data["events"])
    return Packet(
        tick=int(data["tick"]),
        x=float(data["position"][0]),
        y=float(data["position"][1]),
        battery=float(data["battery"]),
        terrain=str(data["terrain"]),
        wheel_m=float(data["wheel_odometry"]),
        moved_m=float(data["visual_odometry"]),
        sampled=tuple(data["sampled_targets"]),
        alive=bool(data["alive"]),
        events=events,
    )


def parse_packets(items: Iterable[Mapping[str, Any]]) -> List[Packet]:
    return [parse_packet(item) for item in items]


def command_to_json(command: Command) -> Dict[str, Any]:
    if command.kind == "drive":
        return {"action": "drive", "heading_deg": command.heading_deg, "metres": command.metres}
    return {"action": command.kind}


def ack_exec_ticks(acks: Sequence[Mapping[str, Any]]) -> List[int]:
    return [int(ack["execute_tick"]) for ack in acks]
