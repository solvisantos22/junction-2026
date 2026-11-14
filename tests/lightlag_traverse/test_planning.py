"""Planning from public information: the ground as a graph, and the choice and order of targets.

    python3 -m unittest discover -s tests/lightlag_traverse -v

Standard library only.
"""

import math
import random
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from lightlag_traverse.environment import MISSION, TraverseEnvironment  # noqa: E402
from lightlag_traverse.planning import INF, Ground, RouteProblem, Sun, plan_route  # noqa: E402
from lightlag_traverse.surface import PHYSICS, Surface  # noqa: E402

SLIP = {"bedrock": 0.03, "regolith": 0.08, "sand": 0.25, "rocks": 0.18}


def flat(code="r", nx=41, ny=41):
    return Surface(5.0, [[0] * nx for _ in range(ny)], [code * (nx - 1) for _ in range(ny - 1)])


def walled():
    """Flat ground cut by a north-south wall at x = 100..110 with one gap at y = 150..165."""
    rows = []
    for j in range(41):
        row = []
        for i in range(41):
            wall = 20 <= i <= 22 and not 30 <= j <= 33
            row.append(600 if wall and i == 21 else 0)
        rows.append(row)
    return Surface(5.0, rows, ["r" * 40 for _ in range(40)])


class GroundTest(unittest.TestCase):
    def test_cost_to_go_on_flat_ground_is_the_distance_at_full_speed(self):
        ground = Ground(flat(), PHYSICS, SLIP)
        goal = ground.node(150.0, 100.0)
        field = ground.field(goal)
        self.assertEqual((field.cost[goal], field.ticks[goal], field.energy[goal]), (0.0, 0.0, 0.0))
        start = ground.node(50.0, 100.0)
        straight = 100.0 / (1 - SLIP["regolith"]) / 5.0
        self.assertAlmostEqual(field.ticks[start], straight, places=6)          # due east: no zigzag
        self.assertAlmostEqual(field.energy[start], straight * 5.0 * PHYSICS["drive_cost_per_wheel_m"]["regolith"], places=6)
        skew = ground.node(50.0, 60.0)
        self.assertGreater(field.ticks[skew], math.hypot(100, 40) / (1 - SLIP["regolith"]) / 5.0 - 1e-9)
        self.assertLess(field.ticks[skew], 1.09 * math.hypot(100, 40) / (1 - SLIP["regolith"]) / 5.0)

    def test_sand_and_climbs_cost_more_than_firm_level_ground(self):
        rows = [[int(100 * 0.08 * i * 5.0) for i in range(41)] for _ in range(41)]
        hill = Ground(Surface(5.0, rows, ["r" * 40 for _ in range(40)]), PHYSICS, SLIP)
        up = hill.field(hill.node(150.0, 100.0))
        down = hill.field(hill.node(50.0, 100.0))
        a, b = hill.node(50.0, 100.0), hill.node(150.0, 100.0)
        self.assertGreater(up.ticks[a], down.ticks[b])            # uphill slips more
        self.assertGreater(up.energy[a], down.energy[b] + 0.9 * PHYSICS["climb_cost_per_m"] * 8.0)
        sand = Ground(flat("s"), PHYSICS, SLIP)
        firm = Ground(flat("b"), PHYSICS, SLIP)
        far, near = sand.node(150.0, 100.0), sand.node(50.0, 100.0)
        self.assertGreater(sand.field(far).ticks[near], 1.2 * firm.field(far).ticks[near])

    def test_steep_ground_is_driven_around(self):
        ground = Ground(walled(), PHYSICS, SLIP)
        self.assertFalse(ground.safe[20 * ground.nx + 21])                     # on the wall
        self.assertTrue(ground.safe[31 * ground.nx + 21])                      # in the gap
        goal = ground.node(150.0, 100.0)
        field = ground.field(goal)
        west = ground.node(60.0, 100.0)
        direct = 90.0 / (1 - SLIP["regolith"]) / 5.0
        self.assertGreater(field.ticks[west], 1.5 * direct)                    # through the gap 55 m to the north
        self.assertLess(field.ticks[west], INF)
        self.assertIsNone(ground.straight(60.0, 100.0, 150.0, 100.0))
        self.assertIsNotNone(ground.straight(60.0, 100.0, 60.0, 150.0))
        node = west
        for _ in range(200):                                                   # follow the field: it gets there
            if node == goal:
                break
            node = field.step[node]
            self.assertTrue(ground.safe[node])
        self.assertEqual(node, goal)

    def test_steering_heads_for_the_goal_and_takes_the_gap(self):
        ground = Ground(flat(), PHYSICS, SLIP)
        field = ground.field(ground.node(150.0, 100.0))
        aim = ground.steer(50.0, 100.0, field, (150.0, 100.0))
        self.assertAlmostEqual(aim[1], 100.0)
        self.assertGreater(aim[0], 55.0)
        close = ground.steer(145.0, 100.0, field, (150.0, 100.0))
        self.assertEqual((close[0], close[1]), (150.0, 100.0))                 # in reach: aim at the goal itself
        wall = Ground(walled(), PHYSICS, SLIP)
        through = wall.steer(60.0, 100.0, wall.field(wall.node(150.0, 100.0)), (150.0, 100.0))
        self.assertGreater(through[1], 100.0)                                  # north, toward the gap

    def test_new_slip_values_change_the_costs(self):
        ground = Ground(flat(), PHYSICS, SLIP)
        goal, start = ground.node(150.0, 100.0), ground.node(50.0, 100.0)
        before = ground.field(goal).ticks[start]
        ground.rebuild(dict(SLIP, regolith=0.12))
        self.assertGreater(ground.field(goal).ticks[start], before)


def toy(values, deadlines, legs, home, start, now=0, battery=100.0, thirst=1.5, **options):
    """A route problem from leg times alone; every tick of driving costs `thirst` energy."""
    rules = TraverseEnvironment(1).rules()
    return RouteProblem(Sun(rules, 0.9), now, battery, values, deadlines, MISSION["late_fraction"],
                        start, [t * thirst for t in start], legs, [[t * thirst for t in row] for row in legs],
                        home, [t * thirst for t in home], (0.0, 0.0), MISSION["sample_cost"], **options)


class RouteTest(unittest.TestCase):
    def test_the_sun_table_adds_up(self):
        rules = TraverseEnvironment(1).rules()
        sun = Sun(rules, 0.9)
        self.assertAlmostEqual(sun.gained(10, 20), sum(sun.rate[11:21]))
        self.assertAlmostEqual(sun.rate[210], 0.9 * rules["solar_peak"])
        self.assertAlmostEqual(sun.gained(0, 0.5), 0.5 * sun.rate[1])

    def test_a_route_is_worth_its_on_time_values_and_late_ones_count_less(self):
        legs = [[0, 10], [10, 0]]
        problem = toy([4.0, 2.0], [30, 15], legs, [20, 25], [20, 25])
        value, finish = problem.score([0, 1])
        self.assertAlmostEqual(value, 4.0 + 2.0 * MISSION["late_fraction"])     # second stop at tick 32, after 15
        self.assertEqual(finish, 20 + 1 + 10 + 1 + 25)
        self.assertAlmostEqual(problem.score([1, 0])[0], 2.0 * MISSION["late_fraction"] + 4.0 * MISSION["late_fraction"])
        self.assertAlmostEqual(problem.score([0])[0], 4.0)
        self.assertEqual(problem.score([]), (0.0, 0.0))

    def test_a_route_that_cannot_get_home_in_time_is_refused(self):
        legs = [[0, 150], [150, 0]]
        problem = toy([4.0, 2.0], [None, None], legs, [150, 150], [150, 150])
        self.assertEqual(problem.score([0, 1])[0], -1.0)
        self.assertGreater(problem.score([0])[0], 0.0)
        unreachable = toy([4.0], [None], [[0]], [10], [INF])
        self.assertEqual(unreachable.score([0])[0], -1.0)

    def test_a_low_battery_waits_for_the_sun(self):
        legs = [[0]]
        fresh = toy([4.0], [None], legs, [40], [40], now=150, thirst=3.5)
        tired = toy([4.0], [None], legs, [40], [40], now=150, battery=20.0, thirst=3.5)
        self.assertEqual(fresh.score([0])[0], 4.0)
        self.assertEqual(tired.score([0])[0], 4.0)
        self.assertGreater(tired.score([0])[1], fresh.score([0])[1])            # it had to stop and charge
        night = toy([4.0], [None], legs, [40], [40], now=330, battery=20.0, thirst=3.5)
        self.assertEqual(night.score([0])[0], -1.0)                             # no time left to wait

    def test_the_search_trades_cheap_targets_nearby_for_a_rich_cluster_far_away(self):
        # Sites 0-3: value 1, each 20 ticks from the lander and 30 from one another. Sites 4-6:
        # value 5, 160 ticks away, 5 ticks apart: each one alone is a poor buy, the three together
        # are the best there is. The best route is the cluster plus the three cheap sites that
        # still fit before it: 18. Filling up with cheap sites first leaves no time for the cluster.
        count = 7
        legs = [[0] * count for _ in range(count)]
        for a in range(count):
            for b in range(count):
                if a == b:
                    continue
                if a < 4 and b < 4:
                    legs[a][b] = 30
                elif a >= 4 and b >= 4:
                    legs[a][b] = 5
                else:
                    legs[a][b] = 160
        home = [20, 20, 20, 20, 160, 160, 160]
        problem = toy([1.0] * 4 + [5.0] * 3, [None] * count, legs, home, home)
        self.assertAlmostEqual(problem.score([0, 1, 2, 3])[0], 4.0)
        self.assertAlmostEqual(problem.score([4, 5, 6])[0], 15.0)
        self.assertEqual(problem.score([0, 1, 2, 4, 5, 6])[0], 18.0)
        self.assertEqual(problem.score([0, 1, 2, 3, 4, 5, 6])[0], -1.0)
        order, value = plan_route(problem, 4000, None, random.Random(1))
        self.assertEqual(sorted(order)[-3:], [4, 5, 6])
        self.assertAlmostEqual(value, 18.0)
        again, _ = plan_route(problem, 4000, None, random.Random(1))
        self.assertEqual(order, again)                                           # the same inputs, the same route

    def test_the_search_improves_on_a_given_route_and_never_returns_an_impossible_one(self):
        rng = random.Random(5)
        count = 14
        points = [(rng.uniform(0, 300), rng.uniform(0, 200)) for _ in range(count)]
        legs = [[math.hypot(a[0] - b[0], a[1] - b[1]) / 4.5 for b in points] for a in points]
        home = [math.hypot(p[0] - 150, p[1] - 100) / 4.5 for p in points]
        values = [float(rng.randint(1, 5)) for _ in range(count)]
        deadlines = [rng.randint(60, 400) if rng.random() < 0.7 else None for _ in range(count)]
        problem = toy(values, deadlines, legs, home, home)
        given = [0, 1, 2]
        order, value = plan_route(problem, 6000, given, random.Random(2))
        self.assertGreaterEqual(value, max(0.0, problem.score(given)[0]))
        self.assertGreaterEqual(problem.score(order)[0], 0.0)
        self.assertEqual(len(set(order)), len(order))
        self.assertGreater(value, 0.5 * sum(values))


if __name__ == "__main__":
    unittest.main()
