"""The published ground model: heights, slopes and one drive command. Standard library only.

    python3 -m unittest discover -s tests/lightlag_traverse -v
"""

import math
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from lightlag_traverse.surface import PHYSICS, Surface, drive  # noqa: E402

SLIP = {"bedrock": 0.0, "regolith": 0.1, "sand": 0.3, "rocks": 0.2}


def plane(rise_x=0.0, rise_y=0.0, code="r", nx=21, ny=21, cell=5.0):
    """A tilted plane: `rise_x` metres up per metre east, `rise_y` per metre north."""
    rows = [[int(round(100 * (rise_x * i * cell + rise_y * j * cell))) for i in range(nx)] for j in range(ny)]
    return Surface(cell, rows, [code * (nx - 1) for _ in range(ny - 1)])


class SurfaceTest(unittest.TestCase):
    def test_height_is_bilinear_and_the_gradient_is_its_slope(self):
        surface = Surface(5.0, [[0, 100], [200, 500]], ["r"])
        self.assertAlmostEqual(surface.elevation(0, 0), 0.0)
        self.assertAlmostEqual(surface.elevation(5, 5), 5.0)
        self.assertAlmostEqual(surface.elevation(2.5, 2.5), (0 + 1 + 2 + 5) / 4)
        height, gx, gy, code = surface.sample(2.5, 0.0)
        self.assertAlmostEqual(height, 0.5)
        self.assertAlmostEqual(gx, 1.0 / 5.0)           # along the south edge: 1 m over 5 m
        self.assertAlmostEqual(gy, (2.0 + 4.0) / 2 / 5.0)   # halfway between the west and east edges
        self.assertEqual(code, "r")

    def test_the_steepest_slope_of_a_cell_is_at_a_corner(self):
        surface = Surface(5.0, [[0, 100], [200, 500]], ["r"])
        corner = surface.cell_max_slope(0, 0)
        inside = max(surface.slope(x / 4.0, y / 4.0) for x in range(21) for y in range(21))
        self.assertAlmostEqual(corner, inside)
        self.assertAlmostEqual(corner, math.hypot(3.0 / 5.0, 4.0 / 5.0))

    def test_points_and_cells_line_up_with_the_grid(self):
        rows = [[0] * 4 for _ in range(3)]
        surface = Surface(5.0, rows, ["rsk", "bbb"])
        self.assertEqual((surface.width, surface.height), (15.0, 10.0))
        self.assertEqual(surface.terrain(1.0, 1.0), "regolith")
        self.assertEqual(surface.terrain(6.0, 1.0), "sand")
        self.assertEqual(surface.terrain(14.9, 4.9), "rocks")
        self.assertEqual(surface.terrain(15.0, 10.0), "bedrock")      # the far corner belongs to the last cell
        with self.assertRaises(ValueError):
            Surface(5.0, rows, ["rs", "bbb"])


class DriveTest(unittest.TestCase):
    def test_on_flat_ground_a_drive_goes_straight_and_loses_the_slip(self):
        moved = drive(plane(), PHYSICS, 50.0, 50.0, 0.0, 5.0, SLIP)
        self.assertAlmostEqual(moved["x"], 50.0 + 5.0 * 0.9)
        self.assertAlmostEqual(moved["y"], 50.0)
        self.assertAlmostEqual(moved["wheel"], 5.0)
        self.assertAlmostEqual(moved["ground"], 4.5)
        self.assertAlmostEqual(moved["energy"], 5.0 * PHYSICS["drive_cost_per_wheel_m"]["regolith"])
        self.assertIsNone(moved["stop"])

    def test_climbing_slips_more_and_costs_the_height_gained(self):
        uphill = drive(plane(rise_x=0.1), PHYSICS, 20.0, 50.0, 0.0, 5.0, SLIP)
        downhill = drive(plane(rise_x=0.1), PHYSICS, 80.0, 50.0, 180.0, 5.0, SLIP)
        slip = SLIP["regolith"] + PHYSICS["slip_grade_gain"]["regolith"] * 0.1
        self.assertAlmostEqual(uphill["ground"], 5.0 * (1 - slip))
        self.assertAlmostEqual(downhill["ground"], 5.0 * (1 - SLIP["regolith"]))     # no bonus downhill
        climbed = 0.1 * uphill["ground"]
        self.assertAlmostEqual(uphill["energy"], 5.0 * PHYSICS["drive_cost_per_wheel_m"]["regolith"]
                               + PHYSICS["climb_cost_per_m"] * climbed)
        self.assertAlmostEqual(downhill["energy"], 5.0 * PHYSICS["drive_cost_per_wheel_m"]["regolith"])

    def test_on_a_cross_slope_the_rover_slides_downhill(self):
        # The ground rises to the north; driving east, north is to the left, so the slide is to the south.
        moved = drive(plane(rise_y=0.1, code="s"), PHYSICS, 30.0, 50.0, 0.0, 5.0, SLIP)
        self.assertAlmostEqual(moved["y"], 50.0 - 5.0 * PHYSICS["side_slip_gain"]["sand"] * 0.1)
        self.assertAlmostEqual(moved["x"], 30.0 + 5.0 * (1 - SLIP["sand"]))
        west = drive(plane(rise_y=0.1, code="s"), PHYSICS, 30.0, 50.0, 180.0, 5.0, SLIP)
        self.assertLess(west["y"], 50.0)                 # still downhill, whichever way it drives

    def test_slip_is_capped_and_noise_shifts_it(self):
        steep = plane(rise_x=0.3, code="s")
        crawl = drive(steep, PHYSICS, 20.0, 50.0, 0.0, 5.0, SLIP)
        self.assertAlmostEqual(crawl["ground"], 5.0 * (1 - PHYSICS["slip_max"]))
        more = drive(plane(), PHYSICS, 50.0, 50.0, 0.0, 5.0, SLIP, noise=0.02)
        self.assertAlmostEqual(more["ground"], 5.0 * (1 - 0.12))

    def test_ground_steeper_than_the_tilt_limit_stops_the_rover(self):
        # flat to the west of x = 50, a wall to the east of it
        rows = [[0 if i <= 10 else int(100 * 0.5 * (i - 10) * 5.0) for i in range(21)] for _ in range(21)]
        surface = Surface(5.0, rows, ["r" * 20 for _ in range(20)])
        moved = drive(surface, PHYSICS, 47.0, 50.0, 0.0, 5.0, SLIP)
        self.assertEqual(moved["stop"], "tilt")
        self.assertLessEqual(moved["x"], 50.0)
        self.assertLessEqual(surface.slope(moved["x"], moved["y"]), PHYSICS["max_tilt"])
        self.assertLess(moved["wheel"], 5.0)             # the rest of the command was not driven

    def test_the_map_edge_and_an_empty_battery_end_a_drive(self):
        edge = drive(plane(), PHYSICS, 98.0, 50.0, 0.0, 5.0, SLIP)
        self.assertEqual(edge["stop"], "map_boundary")
        self.assertLessEqual(edge["x"], 100.0)
        flat = drive(plane(), PHYSICS, 50.0, 50.0, 0.0, 5.0, SLIP, battery=0.5)
        self.assertEqual(flat["stop"], "battery")
        self.assertAlmostEqual(flat["energy"], 0.5)      # it spends what it has and no more
        self.assertLess(flat["wheel"], 5.0)


if __name__ == "__main__":
    unittest.main()
