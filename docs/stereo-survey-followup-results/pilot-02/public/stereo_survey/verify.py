"""Chronological mission replay; imports no reference solver or search masks."""

from itertools import combinations
import math

from .geometry import EPS, angle, mono_mask, pair_mask, pointing, weight


def verify(mission, plan, objective="stereo"):
    if objective not in ("stereo", "mono"):
        raise ValueError("unknown objective")
    if (not isinstance(plan, dict) or set(plan) != {"images"}
            or not isinstance(plan["images"], list)
            or any(type(item) is not str for item in plan["images"])):
        return {"valid": False, "science": 0, "errors": ["expected {images: [image IDs]}"]}
    by_id = {image["id"]: image for image in mission["images"]}
    if len(set(plan["images"])) != len(plan["images"]) or any(identity not in by_id for identity in plan["images"]):
        return {"valid": False, "science": 0, "errors": ["unknown or duplicate image"]}
    selected = [by_id[identity] for identity in plan["images"]]
    errors, events, returned = [], [], []
    resources = {}
    for platform in mission["platforms"]:
        name = platform["id"]
        queue = []
        battery = platform["battery"]
        previous_end = platform["initial_tick"]
        previous_direction = platform["initial_pointing"]
        downlinks = {event["tick"]: event["capacity"] for event in platform["downlinks"]}
        images = sorted((image for image in selected if image["platform"] == name),
                        key=lambda image: (image["tick"], image["id"]))
        for image in images:
            if type(image["tick"]) is not int or not 0 <= image["tick"] < mission["horizon"]:
                errors.append(f"invalid image time: {image['id']}")
        peak_memory = 0
        for tick in range(mission["horizon"]):
            # Downlink old data first; a frame captured at this tick must wait.
            for _ in range(min(downlinks.get(tick, 0), len(queue))):
                image = queue.pop(0)
                returned.append(image)
                battery -= platform["transmit_energy"]
                events.append({"tick": tick, "platform": name, "event": "transmit", "image": image["id"]})
            for image in (im for im in images if im["tick"] == tick):
                direction = pointing(image)
                rotation = angle(previous_direction, direction)
                turn_ticks = math.ceil(rotation / platform["slew_rate"] - EPS)
                if tick - previous_end < turn_ticks:
                    errors.append(f"capture/slew conflict: {image['id']}")
                turn_energy = math.ceil(rotation / platform["slew_energy_angle"] - EPS)
                battery -= platform["capture_energy"] + turn_energy
                queue.append(image)
                peak_memory = max(peak_memory, len(queue))
                if len(queue) > platform["memory"]:
                    errors.append(f"memory capacity: {name} at {tick}")
                previous_end, previous_direction = tick + 1, direction
                events.append({"tick": tick, "platform": name, "event": "capture", "image": image["id"]})
            if battery < 0:
                errors.append(f"battery exhausted: {name} at {tick}")
        if queue:
            errors.append(f"images not returned: {name}")
        resources[name] = {"battery_remaining": battery, "peak_memory": peak_memory,
                           "captured": len(images), "unreturned": len(queue)}
    coverage, products = 0, []
    if objective == "stereo":
        for a, b in combinations(returned, 2):
            cells = pair_mask(mission, a, b)
            if cells:
                coverage |= cells
                products.append({"images": sorted([a["id"], b["id"]]),
                                 "cells": [cell["id"] for i, cell in enumerate(mission["cells"]) if cells & (1 << i)]})
    else:
        for image in returned:
            coverage |= mono_mask(mission, image)
    return {"valid": not errors, "science": 0 if errors else weight(mission, coverage),
            "errors": errors, "covered_cells": [cell["id"] for i, cell in enumerate(mission["cells"]) if coverage & (1 << i)],
            "resources": resources, "products": products,
            "events": sorted(events, key=lambda e: (e["tick"], e["platform"]))}
