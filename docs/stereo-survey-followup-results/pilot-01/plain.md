# Write a stereo-survey planner

Return one complete Python program in a single ```python code block. It must
define `solve(mission)` and return exactly `{"images": [image IDs]}`. It will be
run on many new missions, so write a general algorithm, not answers for examples.
Maximize the sum of weights of cells reconstructed by valid stereo pairs.

You have Python 3.12, its standard library, and the supplied `stereo_survey`
package containing `geometry.py` and `verify.py`. You can import these helpers,
call `verify(mission, plan)`, implement search/optimization and use all public
mission data. There is no external network or additional installed solver.
This is a single-generation test: you cannot execute code during this response.
Your program gets 30 seconds, one CPU and 512 MiB for each fresh mission, in a
new process. Return your best valid plan within that limit. Printing is not a
submission; return the plan. Runtime errors, timeouts and invalid plans earn zero.

## Rules

Two camera platforms have known candidate images. At each camera opportunity,
select at most one of two frames, or skip it. Compact missions offer 24 images
(six opportunities per camera); expanded missions offer 32 (eight per camera).
Both have 20 weighted ground cells. Every input is in `mission`; there are no
hidden parameters or stochastic transitions.

A cell earns its weight once if two returned images cover its centre, their
camera-to-cell rays make an allowed convergence angle, their capture times
differ by no more than the published maximum and their ground-sampling-distance
ratio is allowed. The thresholds are in `mission["stereo"]`. Images from the
same camera can form products too. One image can support several products.
Overlapping products never earn a cell twice. A single image earns no science.

Coordinates are metres, x east, y north, z up; ground is z=0. Supplied rectangular
footprints are orthorectified. Angles are degrees. For example, cameras at
(-5,0,10) and (5,0,10) looking at (0,0,0) make 53.1301 degrees of convergence.
No optics, terrain or orbit calculation is needed. The public geometry code
below defines boundary tolerances and the exact convention.

An exposure lasts one tick. Slewing from the previous pointing direction takes
`ceil(angle / slew_rate - 1e-9)` ticks and costs
`ceil(angle / slew_energy_angle - 1e-9)` energy, in addition to capture energy.
The initial pointing and previous end tick are supplied per platform. There is
no recharging. The next exposure must leave sufficient time for the slew.

Each captured image uses one memory slot. Public downlink windows transmit
oldest frames first up to their capacities, paying energy per frame. Downlink
happens BEFORE capture at the same tick; new data waits for a later window.
Channels are separate for the two cameras. All selected frames must be returned
by the horizon. Exceeding memory, exhausting battery, conflicting exposures,
insufficient slew time or unreturned data makes the entire plan invalid.

The supplied validator is authoritative, and returns raw science, validity,
errors and a resource trace. The evaluator independently calls the unchanged
validator on your returned plan. You receive no optimum, reference planner,
search implementation or evaluation answers. Try to get as close to the best
possible science score as you can on every mission.

## Public stereo_survey/geometry.py

```python
"""The public geometry contract: x east, y north, z up; metres and degrees.

Footprints are supplied orthorectified rectangles on z=0. This abstraction does
not simulate optics, orbital propagation, occlusion or stereo reconstruction.
"""

import math

EPS = 1e-9


def angle(a, b):
    denominator = math.sqrt(sum(x * x for x in a) * sum(x * x for x in b))
    if denominator == 0:
        raise ValueError("a viewing vector must have nonzero length")
    cosine = max(-1.0, min(1.0, sum(x * y for x, y in zip(a, b)) / denominator))
    return math.degrees(math.acos(cosine))


def pointing(image):
    x0, y0, x1, y1 = image["footprint"]
    x, y, z = image["camera"]
    return ((x0 + x1) / 2 - x, (y0 + y1) / 2 - y, -z)


def covers(image, cell):
    x0, y0, x1, y1 = image["footprint"]
    return x0 - EPS <= cell["x"] <= x1 + EPS and y0 - EPS <= cell["y"] <= y1 + EPS


def mono_mask(mission, image):
    return sum(1 << i for i, cell in enumerate(mission["cells"]) if covers(image, cell))


def pair_mask(mission, a, b):
    """Ground cells made into a valid stereo product by these two images."""
    rules = mission["stereo"]
    if a["id"] == b["id"] or abs(a["tick"] - b["tick"]) > rules["max_time_gap"]:
        return 0
    if max(a["gsd"], b["gsd"]) / min(a["gsd"], b["gsd"]) > rules["max_gsd_ratio"] + EPS:
        return 0
    mask = 0
    for i, cell in enumerate(mission["cells"]):
        if not (covers(a, cell) and covers(b, cell)):
            continue
        rays = [(image["camera"][0] - cell["x"], image["camera"][1] - cell["y"], image["camera"][2])
                for image in (a, b)]
        convergence = angle(*rays)
        if rules["min_angle"] - EPS <= convergence <= rules["max_angle"] + EPS:
            mask |= 1 << i
    return mask


def weight(mission, mask):
    return sum(cell["weight"] for i, cell in enumerate(mission["cells"]) if mask & (1 << i))
```

## Public stereo_survey/verify.py

```python
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
```

## Development example: compact

```json
{"version": "stereo-survey-v1", "profile": "compact", "horizon": 19, "cells": [{"id": "cell-0-0", "x": 5, "y": 5, "weight": 4}, {"id": "cell-0-1", "x": 15, "y": 5, "weight": 4}, {"id": "cell-0-2", "x": 25, "y": 5, "weight": 1}, {"id": "cell-0-3", "x": 35, "y": 5, "weight": 3}, {"id": "cell-0-4", "x": 45, "y": 5, "weight": 5}, {"id": "cell-1-0", "x": 5, "y": 15, "weight": 4}, {"id": "cell-1-1", "x": 15, "y": 15, "weight": 4}, {"id": "cell-1-2", "x": 25, "y": 15, "weight": 3}, {"id": "cell-1-3", "x": 35, "y": 15, "weight": 4}, {"id": "cell-1-4", "x": 45, "y": 15, "weight": 3}, {"id": "cell-2-0", "x": 5, "y": 25, "weight": 5}, {"id": "cell-2-1", "x": 15, "y": 25, "weight": 2}, {"id": "cell-2-2", "x": 25, "y": 25, "weight": 5}, {"id": "cell-2-3", "x": 35, "y": 25, "weight": 2}, {"id": "cell-2-4", "x": 45, "y": 25, "weight": 3}, {"id": "cell-3-0", "x": 5, "y": 35, "weight": 2}, {"id": "cell-3-1", "x": 15, "y": 35, "weight": 1}, {"id": "cell-3-2", "x": 25, "y": 35, "weight": 5}, {"id": "cell-3-3", "x": 35, "y": 35, "weight": 3}, {"id": "cell-3-4", "x": 45, "y": 35, "weight": 5}], "images": [{"id": "p0-t00-v0", "platform": "camera-0", "tick": 0, "camera": [-15.0, 8, 40], "footprint": [16, 14, 54, 32], "gsd": 1.9}, {"id": "p0-t00-v1", "platform": "camera-0", "tick": 0, "camera": [-15.0, 8, 40], "footprint": [-14, 27, 24, 45], "gsd": 1.9}, {"id": "p0-t01-v0", "platform": "camera-0", "tick": 3, "camera": [-1.0, 8, 40], "footprint": [11, 23, 39, 51], "gsd": 1.4}, {"id": "p0-t01-v1", "platform": "camera-0", "tick": 3, "camera": [-1.0, 8, 40], "footprint": [18, -3, 56, 15], "gsd": 1.9}, {"id": "p0-t02-v0", "platform": "camera-0", "tick": 6, "camera": [13.0, 8, 40], "footprint": [33, 14, 61, 32], "gsd": 1.4}, {"id": "p0-t02-v1", "platform": "camera-0", "tick": 6, "camera": [13.0, 8, 40], "footprint": [4, 23, 22, 51], "gsd": 0.9}, {"id": "p0-t03-v0", "platform": "camera-0", "tick": 9, "camera": [27.0, 8, 40], "footprint": [-6, 20, 12, 48], "gsd": 0.9}, {"id": "p0-t03-v1", "platform": "camera-0", "tick": 9, "camera": [27.0, 8, 40], "footprint": [-15, 15, 23, 33], "gsd": 1.9}, {"id": "p0-t04-v0", "platform": "camera-0", "tick": 12, "camera": [41.0, 8, 40], "footprint": [16, 28, 34, 46], "gsd": 0.9}, {"id": "p0-t04-v1", "platform": "camera-0", "tick": 12, "camera": [41.0, 8, 40], "footprint": [31, 18, 59, 36], "gsd": 1.4}, {"id": "p0-t05-v0", "platform": "camera-0", "tick": 15, "camera": [55.0, 8, 40], "footprint": [28, 0, 66, 28], "gsd": 1.9}, {"id": "p0-t05-v1", "platform": "camera-0", "tick": 15, "camera": [55.0, 8, 40], "footprint": [17, -11, 55, 17], "gsd": 1.9}, {"id": "p1-t00-v0", "platform": "camera-1", "tick": 0, "camera": [65.0, 32, 40], "footprint": [23, 10, 51, 38], "gsd": 1.4}, {"id": "p1-t00-v1", "platform": "camera-1", "tick": 0, "camera": [65.0, 32, 40], "footprint": [10, 25, 38, 43], "gsd": 1.4}, {"id": "p1-t01-v0", "platform": "camera-1", "tick": 3, "camera": [51.0, 32, 40], "footprint": [-1, -5, 27, 13], "gsd": 1.4}, {"id": "p1-t01-v1", "platform": "camera-1", "tick": 3, "camera": [51.0, 32, 40], "footprint": [24, 8, 42, 26], "gsd": 0.9}, {"id": "p1-t02-v0", "platform": "camera-1", "tick": 6, "camera": [37.0, 32, 40], "footprint": [10, 18, 38, 36], "gsd": 1.4}, {"id": "p1-t02-v1", "platform": "camera-1", "tick": 6, "camera": [37.0, 32, 40], "footprint": [2, 22, 30, 50], "gsd": 1.4}, {"id": "p1-t03-v0", "platform": "camera-1", "tick": 9, "camera": [23.0, 32, 40], "footprint": [2, 18, 30, 36], "gsd": 1.4}, {"id": "p1-t03-v1", "platform": "camera-1", "tick": 9, "camera": [23.0, 32, 40], "footprint": [5, -10, 43, 18], "gsd": 1.9}, {"id": "p1-t04-v0", "platform": "camera-1", "tick": 12, "camera": [9.0, 32, 40], "footprint": [-4, -5, 14, 13], "gsd": 0.9}, {"id": "p1-t04-v1", "platform": "camera-1", "tick": 12, "camera": [9.0, 32, 40], "footprint": [19, -1, 47, 27], "gsd": 1.4}, {"id": "p1-t05-v0", "platform": "camera-1", "tick": 15, "camera": [-5.0, 32, 40], "footprint": [-6, 4, 12, 22], "gsd": 0.9}, {"id": "p1-t05-v1", "platform": "camera-1", "tick": 15, "camera": [-5.0, 32, 40], "footprint": [18, 8, 56, 26], "gsd": 1.9}], "platforms": [{"id": "camera-0", "battery": 14, "memory": 3, "capture_energy": 2, "transmit_energy": 1, "slew_rate": 30, "slew_energy_angle": 30, "initial_tick": -4, "initial_pointing": [0, 0, -1], "downlinks": [{"tick": 7, "capacity": 2}, {"tick": 15, "capacity": 2}, {"tick": 18, "capacity": 2}]}, {"id": "camera-1", "battery": 14, "memory": 3, "capture_energy": 2, "transmit_energy": 1, "slew_rate": 30, "slew_energy_angle": 30, "initial_tick": -4, "initial_pointing": [0, 0, -1], "downlinks": [{"tick": 7, "capacity": 2}, {"tick": 15, "capacity": 2}, {"tick": 18, "capacity": 2}]}], "stereo": {"min_angle": 15, "max_angle": 55, "max_time_gap": 9, "max_gsd_ratio": 1.5}}
```

## Development example: expanded

```json
{"version": "stereo-survey-v1", "profile": "expanded", "horizon": 25, "cells": [{"id": "cell-0-0", "x": 5, "y": 5, "weight": 2}, {"id": "cell-0-1", "x": 15, "y": 5, "weight": 5}, {"id": "cell-0-2", "x": 25, "y": 5, "weight": 1}, {"id": "cell-0-3", "x": 35, "y": 5, "weight": 3}, {"id": "cell-0-4", "x": 45, "y": 5, "weight": 1}, {"id": "cell-1-0", "x": 5, "y": 15, "weight": 4}, {"id": "cell-1-1", "x": 15, "y": 15, "weight": 4}, {"id": "cell-1-2", "x": 25, "y": 15, "weight": 4}, {"id": "cell-1-3", "x": 35, "y": 15, "weight": 4}, {"id": "cell-1-4", "x": 45, "y": 15, "weight": 2}, {"id": "cell-2-0", "x": 5, "y": 25, "weight": 1}, {"id": "cell-2-1", "x": 15, "y": 25, "weight": 4}, {"id": "cell-2-2", "x": 25, "y": 25, "weight": 1}, {"id": "cell-2-3", "x": 35, "y": 25, "weight": 4}, {"id": "cell-2-4", "x": 45, "y": 25, "weight": 4}, {"id": "cell-3-0", "x": 5, "y": 35, "weight": 5}, {"id": "cell-3-1", "x": 15, "y": 35, "weight": 1}, {"id": "cell-3-2", "x": 25, "y": 35, "weight": 4}, {"id": "cell-3-3", "x": 35, "y": 35, "weight": 3}, {"id": "cell-3-4", "x": 45, "y": 35, "weight": 2}], "images": [{"id": "p0-t00-v0", "platform": "camera-0", "tick": 0, "camera": [-15.0, 8, 40], "footprint": [-1, 14, 27, 32], "gsd": 1.4}, {"id": "p0-t00-v1", "platform": "camera-0", "tick": 0, "camera": [-15.0, 8, 40], "footprint": [-3, -5, 35, 13], "gsd": 1.9}, {"id": "p0-t01-v0", "platform": "camera-0", "tick": 3, "camera": [-5.0, 8, 40], "footprint": [17, 17, 55, 35], "gsd": 1.9}, {"id": "p0-t01-v1", "platform": "camera-0", "tick": 3, "camera": [-5.0, 8, 40], "footprint": [-14, -5, 24, 13], "gsd": 1.9}, {"id": "p0-t02-v0", "platform": "camera-0", "tick": 6, "camera": [5.0, 8, 40], "footprint": [12, 8, 40, 26], "gsd": 1.4}, {"id": "p0-t02-v1", "platform": "camera-0", "tick": 6, "camera": [5.0, 8, 40], "footprint": [25, 16, 63, 34], "gsd": 1.9}, {"id": "p0-t03-v0", "platform": "camera-0", "tick": 9, "camera": [15.0, 8, 40], "footprint": [18, -10, 56, 18], "gsd": 1.9}, {"id": "p0-t03-v1", "platform": "camera-0", "tick": 9, "camera": [15.0, 8, 40], "footprint": [-7, 12, 21, 40], "gsd": 1.4}, {"id": "p0-t04-v0", "platform": "camera-0", "tick": 12, "camera": [25.0, 8, 40], "footprint": [-3, 25, 35, 43], "gsd": 1.9}, {"id": "p0-t04-v1", "platform": "camera-0", "tick": 12, "camera": [25.0, 8, 40], "footprint": [7, 10, 45, 38], "gsd": 1.9}, {"id": "p0-t05-v0", "platform": "camera-0", "tick": 15, "camera": [35.0, 8, 40], "footprint": [-6, 12, 32, 40], "gsd": 1.9}, {"id": "p0-t05-v1", "platform": "camera-0", "tick": 15, "camera": [35.0, 8, 40], "footprint": [5, 28, 43, 46], "gsd": 1.9}, {"id": "p0-t06-v0", "platform": "camera-0", "tick": 18, "camera": [45.0, 8, 40], "footprint": [12, 14, 40, 32], "gsd": 1.4}, {"id": "p0-t06-v1", "platform": "camera-0", "tick": 18, "camera": [45.0, 8, 40], "footprint": [0, 10, 28, 38], "gsd": 1.4}, {"id": "p0-t07-v0", "platform": "camera-0", "tick": 21, "camera": [55.0, 8, 40], "footprint": [18, 28, 36, 46], "gsd": 0.9}, {"id": "p0-t07-v1", "platform": "camera-0", "tick": 21, "camera": [55.0, 8, 40], "footprint": [18, 1, 36, 29], "gsd": 0.9}, {"id": "p1-t00-v0", "platform": "camera-1", "tick": 0, "camera": [65.0, 32, 40], "footprint": [21, 23, 49, 51], "gsd": 1.4}, {"id": "p1-t00-v1", "platform": "camera-1", "tick": 0, "camera": [65.0, 32, 40], "footprint": [17, 18, 55, 36], "gsd": 1.9}, {"id": "p1-t01-v0", "platform": "camera-1", "tick": 3, "camera": [55.0, 32, 40], "footprint": [-13, 4, 25, 22], "gsd": 1.9}, {"id": "p1-t01-v1", "platform": "camera-1", "tick": 3, "camera": [55.0, 32, 40], "footprint": [13, 23, 41, 51], "gsd": 1.4}, {"id": "p1-t02-v0", "platform": "camera-1", "tick": 6, "camera": [45.0, 32, 40], "footprint": [1, 2, 29, 30], "gsd": 1.4}, {"id": "p1-t02-v1", "platform": "camera-1", "tick": 6, "camera": [45.0, 32, 40], "footprint": [3, 28, 31, 46], "gsd": 1.4}, {"id": "p1-t03-v0", "platform": "camera-1", "tick": 9, "camera": [35.0, 32, 40], "footprint": [30, 25, 58, 43], "gsd": 1.4}, {"id": "p1-t03-v1", "platform": "camera-1", "tick": 9, "camera": [35.0, 32, 40], "footprint": [-16, 18, 22, 36], "gsd": 1.9}, {"id": "p1-t04-v0", "platform": "camera-1", "tick": 12, "camera": [25.0, 32, 40], "footprint": [14, 4, 52, 22], "gsd": 1.9}, {"id": "p1-t04-v1", "platform": "camera-1", "tick": 12, "camera": [25.0, 32, 40], "footprint": [1, -5, 29, 13], "gsd": 1.4}, {"id": "p1-t05-v0", "platform": "camera-1", "tick": 15, "camera": [15.0, 32, 40], "footprint": [16, 6, 54, 24], "gsd": 1.9}, {"id": "p1-t05-v1", "platform": "camera-1", "tick": 15, "camera": [15.0, 32, 40], "footprint": [25, -4, 43, 14], "gsd": 0.9}, {"id": "p1-t06-v0", "platform": "camera-1", "tick": 18, "camera": [5.0, 32, 40], "footprint": [-4, 22, 34, 50], "gsd": 1.9}, {"id": "p1-t06-v1", "platform": "camera-1", "tick": 18, "camera": [5.0, 32, 40], "footprint": [-13, 2, 25, 30], "gsd": 1.9}, {"id": "p1-t07-v0", "platform": "camera-1", "tick": 21, "camera": [-5.0, 32, 40], "footprint": [21, -8, 49, 20], "gsd": 1.4}, {"id": "p1-t07-v1", "platform": "camera-1", "tick": 21, "camera": [-5.0, 32, 40], "footprint": [-6, -9, 12, 19], "gsd": 0.9}], "platforms": [{"id": "camera-0", "battery": 20, "memory": 3, "capture_energy": 2, "transmit_energy": 1, "slew_rate": 30, "slew_energy_angle": 30, "initial_tick": -4, "initial_pointing": [0, 0, -1], "downlinks": [{"tick": 7, "capacity": 2}, {"tick": 15, "capacity": 2}, {"tick": 23, "capacity": 2}, {"tick": 24, "capacity": 2}]}, {"id": "camera-1", "battery": 20, "memory": 3, "capture_energy": 2, "transmit_energy": 1, "slew_rate": 30, "slew_energy_angle": 30, "initial_tick": -4, "initial_pointing": [0, 0, -1], "downlinks": [{"tick": 7, "capacity": 2}, {"tick": 15, "capacity": 2}, {"tick": 23, "capacity": 2}, {"tick": 24, "capacity": 2}]}], "stereo": {"min_angle": 15, "max_angle": 55, "max_time_gap": 9, "max_gsd_ratio": 1.5}}
```
