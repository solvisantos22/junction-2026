import copy
import math
import unittest

from stereo_survey.geometry import angle, pair_mask
from stereo_survey.mission import generate
from stereo_survey.search import Problem, beam, exact, greedy
from stereo_survey.verify import verify


def tiny(seed):
    mission = generate(seed)
    mission["images"] = [image for image in mission["images"] if image["tick"] <= 3]
    return mission


def geometric_fixture():
    mission = generate(0)
    mission["cells"] = [{"id": "origin", "x": 0, "y": 0, "weight": 7}]
    mission["images"] = [
        {"id": name, "platform": "camera-0", "tick": tick,
         "camera": camera, "footprint": [-10, -10, 10, 10], "gsd": 1}
        for name, tick, camera in (("left", 0, [-5, 0, 10]),
                                  ("right", 3, [5, 0, 10]),
                                  ("north", 6, [0, 5, 10]))
    ]
    return mission


class GeometryTests(unittest.TestCase):
    def test_known_convergence_angle(self):
        mission = geometric_fixture()
        a, b, _ = mission["images"]
        self.assertAlmostEqual(angle(a["camera"], b["camera"]), 2 * math.degrees(math.atan(0.5)))
        self.assertEqual(pair_mask(mission, a, b), 1)

    def test_pair_requirements_are_independently_necessary(self):
        mission = geometric_fixture()
        a, b, _ = mission["images"]
        for changes in ({"camera": a["camera"]}, {"tick": 10}, {"gsd": 2},
                        {"footprint": [20, 20, 30, 30]}, {"id": a["id"]}):
            with self.subTest(changes=changes):
                self.assertEqual(pair_mask(mission, a, {**b, **changes}), 0)

    def test_geometry_boundaries_and_coordinate_translation(self):
        mission = geometric_fixture()
        a, b, _ = mission["images"]
        mission["stereo"]["min_angle"] = mission["stereo"]["max_angle"] = angle(a["camera"], b["camera"])
        b["gsd"] = 1.5
        b["tick"] = 9
        self.assertEqual(pair_mask(mission, a, b), 1)
        moved = copy.deepcopy(mission)
        for cell in moved["cells"]:
            cell["x"] += 123
            cell["y"] -= 50
        for image in moved["images"]:
            image["camera"][0] += 123
            image["camera"][1] -= 50
            image["footprint"] = [image["footprint"][0] + 123, image["footprint"][1] - 50,
                                  image["footprint"][2] + 123, image["footprint"][3] - 50]
        self.assertEqual(pair_mask(moved, *moved["images"][:2]), 1)


class ReplayTests(unittest.TestCase):
    def test_complementarity_reuse_and_no_duplicate_cell_reward(self):
        mission = geometric_fixture()
        self.assertEqual(verify(mission, {"images": ["left"]})["science"], 0)
        self.assertEqual(verify(mission, {"images": ["left"]}, "mono")["science"], 7)
        result = verify(mission, {"images": ["left", "right", "north"]})
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["science"], 7)
        self.assertEqual(len(result["products"]), 3)

    def test_schema_and_repeated_image_errors_score_zero(self):
        mission = geometric_fixture()
        for plan in (["left"], {"images": "left"}, {"images": [False]},
                     {"images": ["left", "left"]}, {"images": ["missing"]},
                     {"images": [], "science": 100}):
            with self.subTest(plan=plan):
                result = verify(mission, plan)
                self.assertFalse(result["valid"])
                self.assertEqual(result["science"], 0)

    def test_slew_battery_memory_and_return_constraints(self):
        base = geometric_fixture()
        plan = {"images": ["left", "right", "north"]}
        for violation in ("slew", "battery", "memory", "return"):
            mission = copy.deepcopy(base)
            platform = mission["platforms"][0]
            if violation == "slew":
                mission["images"][1]["tick"] = 1
            elif violation == "battery":
                platform["battery"] = 1
            elif violation == "memory":
                platform["memory"] = 2
            else:
                platform["downlinks"] = [{"tick": 7, "capacity": 1}]
            result = verify(mission, plan)
            with self.subTest(violation=violation):
                self.assertFalse(result["valid"], result)
                self.assertEqual(result["science"], 0)

    def test_downlink_precedes_capture_at_same_tick(self):
        mission = geometric_fixture()
        mission["images"][2]["tick"] = 7
        mission["platforms"][0]["memory"] = 2
        result = verify(mission, {"images": ["left", "right", "north"]})
        self.assertTrue(result["valid"], result["errors"])
        tick7 = [e["event"] for e in result["events"] if e["tick"] == 7]
        self.assertEqual(tick7, ["transmit", "transmit", "capture"])
        events = [e for e in result["events"] if e["image"] == "north"]
        self.assertEqual(events[-1]["tick"], 15)


class ReferenceTests(unittest.TestCase):
    def test_reference_equals_all_subsets_through_separate_replay(self):
        for seed in range(6):
            mission = tiny(seed)
            problem = Problem(mission)
            for objective in ("stereo", "mono"):
                maximum = 0
                for mask in range(1 << problem.n):
                    replay = verify(mission, problem.plan(mask), objective)
                    self.assertEqual(problem.feasible(mask), replay["valid"])
                    if replay["valid"]:
                        self.assertEqual(problem.science(mask, objective), replay["science"])
                        maximum = max(maximum, replay["science"])
                solved = exact(problem, objective)
                self.assertTrue(solved["proven_optimal"])
                self.assertEqual(solved["science"], maximum)

    def test_reference_handles_shared_image_products(self):
        mission = geometric_fixture()
        solved = exact(Problem(mission))
        self.assertTrue(solved["proven_optimal"])
        self.assertEqual(solved["science"], 7)
        self.assertTrue(verify(mission, solved["plan"])["valid"])

    def test_caps_never_claim_unfinished_search_is_optimal(self):
        problem = Problem(geometric_fixture())
        self.assertFalse(exact(problem, max_local=1)["proven_optimal"])
        self.assertFalse(exact(problem, max_joint=0)["proven_optimal"])

    def test_all_controls_are_valid_and_bounded_by_reference(self):
        mission = generate(3)
        before = copy.deepcopy(mission)
        problem = Problem(mission)
        for objective in ("stereo", "mono"):
            reference = exact(problem, objective)
            self.assertTrue(reference["proven_optimal"])
            controls = [greedy(problem, objective), greedy(problem, objective, density=True),
                        greedy(problem, objective, units="images"),
                        beam(problem, objective), beam(problem, objective, units="images")]
            for control in controls:
                result = verify(mission, control["plan"], objective)
                self.assertTrue(result["valid"], result["errors"])
                self.assertEqual(result["science"], control["science"])
                self.assertLessEqual(control["science"], reference["science"])
        self.assertEqual(mission, before)

    def test_input_order_does_not_change_optimum(self):
        mission = generate(5)
        expected = exact(Problem(mission))["science"]
        mission["images"].reverse()
        self.assertEqual(exact(Problem(mission))["science"], expected)


if __name__ == "__main__":
    unittest.main()
