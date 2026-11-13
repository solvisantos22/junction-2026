"""Deterministic routes and terrain queries using only a public map."""

import heapq
import math


def distance(start, end):
    return math.hypot(end[0] - start[0], end[1] - start[1])


def segment_intersects(start, end, rect):
    """Closed rectangle intersection, including arbitrarily thin crossings."""
    enter, leave = 0.0, 1.0
    for origin, delta, low, high in (
            (start[0], end[0] - start[0], rect[0], rect[2]),
            (start[1], end[1] - start[1], rect[1], rect[3])):
        if abs(delta) < 1e-14:
            if not low <= origin <= high:
                return False
            continue
        near, far = sorted(((low - origin) / delta, (high - origin) / delta))
        enter, leave = max(enter, near), min(leave, far)
        if enter > leave:
            return False
    return True


class MapGeometry:
    def __init__(self, public_map, margin=0.35):
        self.map = public_map
        self.margin = margin
        self.hazards = [self.rectangle(rect) for rect in public_map["hazards"]]
        self.sand = [self.rectangle(rect) for rect in public_map["sand"]]
        self.obstacles = [(x1 - margin, y1 - margin, x2 + margin, y2 + margin)
                          for x1, y1, x2, y2 in self.hazards]

    @staticmethod
    def rectangle(rect):
        return tuple(rect[key] for key in ("x1", "y1", "x2", "y2"))

    def inside_map(self, point):
        return (0 <= point[0] <= self.map["width"] and
                0 <= point[1] <= self.map["height"])

    def terrain_at(self, point):
        x, y = point
        if any(x1 <= x <= x2 and y1 <= y <= y2 for x1, y1, x2, y2 in self.sand):
            return "sand"
        return self.map["default_terrain"]

    def terrain_breaks(self, start, end):
        """Parameter values at every possible terrain transition."""
        breaks = {0.0, 1.0}
        for rect in self.sand:
            for axis, limits in ((0, (rect[0], rect[2])), (1, (rect[1], rect[3]))):
                delta = end[axis] - start[axis]
                if delta:
                    for edge in limits:
                        fraction = (edge - start[axis]) / delta
                        if 0 < fraction < 1:
                            breaks.add(fraction)
        return sorted(breaks)

    @staticmethod
    def interpolate(start, end, fraction):
        return tuple(a + (b - a) * fraction for a, b in zip(start, end))

    def homogeneous_terrain(self, start, end):
        breaks = self.terrain_breaks(start, end)
        fractions = breaks + [(a + b) / 2 for a, b in zip(breaks, breaks[1:])]
        terrains = {self.terrain_at(self.interpolate(start, end, t)) for t in fractions}
        return terrains.pop() if len(terrains) == 1 else None

    def terrain_distances(self, start, end):
        length = distance(start, end)
        breaks = self.terrain_breaks(start, end)
        return [(self.terrain_at(self.interpolate(start, end, (a + b) / 2)),
                 length * (b - a)) for a, b in zip(breaks, breaks[1:])]

    def segment_clear(self, start, end, margin=True):
        if not self.inside_map(start) or not self.inside_map(end):
            return False
        rectangles = self.obstacles if margin else self.hazards
        for x1, y1, x2, y2 in rectangles:
            # Waypoints may touch the inflated rectangle's boundary. The real
            # closed hazard remains a full margin away from those waypoints.
            inset = 1e-9 if margin else 0
            if segment_intersects(start, end, (x1 + inset, y1 + inset,
                                               x2 - inset, y2 - inset)):
                return False
        return True

    def endpoint_connectors(self, point):
        """Short, physical-hazard-free exits from an endpoint's margin zone.

        Only these endpoint stubs may relax clearance. They are at most one
        margin long, end outside every expanded obstacle, and cannot cross
        another obstacle's margin unless the endpoint is already inside it.
        """
        if self.segment_clear(point, point):
            return []
        containing = {index for index, (x1, y1, x2, y2) in enumerate(self.obstacles)
                      if x1 < point[0] < x2 and y1 < point[1] < y2}
        candidates = set()
        for index in sorted(containing):
            x1, y1, x2, y2 = self.obstacles[index]
            candidates.update(((x1, point[1]), (x2, point[1]),
                               (point[0], y1), (point[0], y2)))
        connectors = []
        for candidate in sorted(candidates):
            if (distance(point, candidate) > self.margin + 1e-8 or
                    not self.segment_clear(candidate, candidate) or
                    not self.segment_clear(point, candidate, margin=False)):
                continue
            if any(segment_intersects(point, candidate, (x1 + 1e-9, y1 + 1e-9,
                                                          x2 - 1e-9, y2 - 1e-9))
                   for index, (x1, y1, x2, y2) in enumerate(self.obstacles)
                   if index not in containing):
                continue
            connectors.append(candidate)
        return connectors

    def route(self, start, end):
        """Visible margin-expanded graph, with bounded endpoint access stubs."""
        start, end = tuple(start), tuple(end)
        if (not self.segment_clear(start, start, margin=False) or
                not self.segment_clear(end, end, margin=False)):
            return None
        if start == end or self.segment_clear(start, end):
            return [start, end]
        vertices = [start, end]
        for x1, y1, x2, y2 in self.obstacles:
            for point in ((x1, y1), (x1, y2), (x2, y1), (x2, y2)):
                if self.inside_map(point) and self.segment_clear(point, point):
                    vertices.append(point)
        endpoint_edges = set()
        for endpoint_index, point in enumerate((start, end)):
            for connector in self.endpoint_connectors(point):
                connector_index = len(vertices)
                vertices.append(connector)
                endpoint_edges.add((endpoint_index, connector_index))
                endpoint_edges.add((connector_index, endpoint_index))
        best = {0: 0.0}
        previous = {}
        queue = [(0.0, 0)]
        while queue:
            length, index = heapq.heappop(queue)
            if length != best[index]:
                continue
            if index == 1:
                path = [1]
                while path[-1] != 0:
                    path.append(previous[path[-1]])
                return [vertices[i] for i in reversed(path)]
            for other, point in enumerate(vertices):
                if other == index or ((index, other) not in endpoint_edges and
                                      not self.segment_clear(vertices[index], point)):
                    continue
                candidate = length + distance(vertices[index], point)
                if candidate < best.get(other, math.inf):
                    best[other] = candidate
                    previous[other] = index
                    heapq.heappush(queue, (candidate, other))
        return None

    @staticmethod
    def route_length(route):
        return sum(distance(start, end) for start, end in zip(route, route[1:]))
