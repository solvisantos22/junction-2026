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
