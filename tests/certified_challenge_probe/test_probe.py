import copy
from itertools import product
import random
import unittest

from tools.certified_challenge_probe.model import generate, verify
from tools.certified_challenge_probe.search import EMPTY, add, beam, compile_choices, exact, fits, greedy


def brute_force(mission):
    """Tiny independent oracle: enumerate times and ask only the public checker."""
    options = []
    for job in mission["jobs"]:
        valid = [None]
        for collect, process, transmit in product(range(mission["horizon"]), repeat=3):
            action = {"job": job["id"], "collect": collect, "process": process, "transmit": transmit}
            if verify(mission, [action])["valid"]:
                valid.append(action)
        options.append(valid)
    return max(verify(mission, [a for a in schedule if a is not None])["value"]
               for schedule in product(*options))


class ProbeTests(unittest.TestCase):
    def test_reference_matches_independent_tiny_exhaustive_search(self):
        for seed in range(8):
            mission = generate(seed, 2)
            solved = exact(mission)
            with self.subTest(seed=seed):
                self.assertTrue(solved["proven_optimal"])
                self.assertEqual(solved["value"], brute_force(mission))
                self.assertEqual(verify(mission, solved["plan"])["value"], solved["value"])

    def test_half_open_precedence_and_expiry_boundaries(self):
        mission = generate(0, 1)
        mission["jobs"] = [{"id": "a", "value": 9, "collect_duration": 1,
                            "process_duration": 2, "shelf_life": 2,
                            "collect_slots": [0], "deadline": 6}]
        action = {"job": "a", "collect": 0, "process": 1, "transmit": 5}
        self.assertEqual(verify(mission, [action])["value"], 9)
        for change in ({"process": 0}, {"process": 2}, {"transmit": 4}, {"collect": -1}):
            with self.subTest(change=change):
                self.assertFalse(verify(mission, [{**action, **change}])["valid"])
        mission["jobs"][0]["deadline"] = 5
        self.assertFalse(verify(mission, [action])["valid"])

    def test_invalid_or_duplicate_actions_never_score(self):
        mission = generate(1, 2)
        action = next(c for choices in compile_choices(mission).values() for c in choices).action()
        for plan in ([action, action], [{**action, "job": "unknown"}],
                     [{**action, "collect": True}], [{**action, "extra": 1}],
                     [{**action, "job": []}], [None], "plan"):
            with self.subTest(plan=plan):
                result = verify(mission, plan)
                self.assertFalse(result["valid"])
                self.assertEqual(result["value"], 0)

    def test_power_can_bind_without_machine_overlap(self):
        mission = generate(0, 4)
        mission["downlink_slots"] = [5, 9, 13]
        mission["jobs"] = [
            {"id": name, "value": 1, "collect_duration": 1, "process_duration": 2,
             "shelf_life": 8, "collect_slots": [collect], "deadline": 16}
            for name, collect in (("a", 0), ("b", 2), ("c", 5))
        ]
        plan = [{"job": name, "collect": collect, "process": process, "transmit": transmit}
                for name, collect, process, transmit in (("a", 0, 1, 5), ("b", 2, 4, 9), ("c", 5, 6, 13))]
        result = verify(mission, plan)
        self.assertFalse(result["valid"])
        self.assertEqual(result["errors"], ["power capacity at 5: 3"])

    def test_memory_can_bind_before_downlink(self):
        mission = generate(0, 6)
        mission["downlink_slots"] = [9, 13, 17]
        mission["jobs"] = [
            {"id": str(i), "value": 1, "collect_duration": 1, "process_duration": 1,
             "shelf_life": 2, "collect_slots": [i], "deadline": 20} for i in range(3)
        ]
        plan = [{"job": str(i), "collect": i, "process": i + 1, "transmit": 9 + 4 * i} for i in range(3)]
        result = verify(mission, plan)
        self.assertFalse(result["valid"])
        self.assertTrue(all(e.startswith("data capacity") for e in result["errors"]))

    def test_compiler_and_aggregate_masks_agree_with_independent_replay(self):
        rng = random.Random(180)
        for seed in range(5):
            mission = generate(seed, 6)
            choices = compile_choices(mission)
            for options in choices.values():
                for choice in options:
                    self.assertTrue(verify(mission, [choice.action()])["valid"])
            for _ in range(100):
                state, plan = EMPTY, []
                for job in rng.sample(mission["jobs"], len(mission["jobs"])):
                    if not choices[job["id"]]:
                        continue
                    choice = rng.choice(choices[job["id"]])
                    replay = verify(mission, plan + [choice.action()])
                    self.assertEqual(fits(state, choice), replay["valid"])
                    if fits(state, choice):
                        state = add(state, choice)
                        plan.append(choice.action())

    def test_capped_search_does_not_claim_optimality(self):
        result = exact(generate(5, 6), max_nodes=0)
        self.assertFalse(result["proven_optimal"])
        self.assertEqual(result["nodes"], 0)

    def test_baselines_and_reference_use_only_public_input(self):
        mission = generate(7, 4)
        before = copy.deepcopy(mission)
        choices = compile_choices(mission)
        reference = exact(mission, choices)
        controls = [beam(mission, choices)]
        controls.extend(greedy(mission, choices, rule) for rule in ("value", "deadline", "density", "scarcity"))
        for control in controls:
            self.assertTrue(verify(mission, control["plan"])["valid"])
            self.assertLessEqual(control["value"], reference["value"])
        self.assertEqual(mission, before)
        self.assertEqual(generate(7, 4), before)

    def test_empty_mission_has_zero_optimum(self):
        mission = generate(0, 1)
        mission["jobs"] = []
        result = exact(mission)
        self.assertTrue(result["proven_optimal"])
        self.assertEqual(result["value"], 0)
        self.assertEqual(verify(mission, [])["value"], 0)


if __name__ == "__main__":
    unittest.main()
