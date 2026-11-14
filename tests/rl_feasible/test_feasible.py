import copy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from lightlag_rl.adapter import run_episode as original_episode, greedy_choice
from lightlag_rl_feasible.adapter import FeasiblePilot, run_episode, visit_return
from lightlag_rl_persistence import GoalChooser
from lightlag_traverse.planning import Sun
from tools.rl_feasible.run import jobs, normal, summarize


def public_pilot(peak=1.0, sample_cost=2.0):
    """Only published model inputs; deliberately no simulator/private state."""
    rules = dict(max_ticks=100, battery_capacity=100, idle_cost=.1,
                 sun_margin_ticks=0, solar_peak=peak, sample_cost=sample_cost,
                 sample_windows={"late_fraction": .25})
    return SimpleNamespace(
        rules=rules, sun=Sun(rules, 1.0), nodes={"science": 0},
        fields={"base": SimpleNamespace(ticks=[10.], energy=[20.])},
        targets={"science": {"value": 8., "deadline_tick": None}},
        opt=dict(home_slack=1., stop_ticks=1, home_margin=4., deadline_margin=1,
                 floor=5., leg_slack=1.),
        _to=lambda name, x, y: (10., 20.),
    )


class FeasibilityTests(unittest.TestCase):
    def test_waits_for_charging_and_preserves_complete_round_trip(self):
        pilot = public_pilot()
        charged = visit_return(pilot, 30, 0, 0, 90, "science")
        waiting = visit_return(pilot, 30, 0, 0, 6, "science")
        self.assertEqual(charged["finish_tick"], 51)
        self.assertGreater(waiting["finish_tick"], charged["finish_tick"])
        self.assertLessEqual(waiting["finish_tick"], waiting["limit_tick"])
        self.assertLess(waiting["sample_tick"], waiting["finish_tick"])

    def test_late_trip_fits_travel_but_not_charging(self):
        pilot = public_pilot()
        self.assertLess(70 + 10 + 1 + 10, 96)
        self.assertIsNone(visit_return(pilot, 70, 0, 0, 6, "science"))
        self.assertIsNotNone(visit_return(pilot, 70, 0, 0, 90, "science"))

    def test_sample_and_return_energy_and_unreachable_costs_are_checked(self):
        pilot = public_pilot(peak=0)
        self.assertIsNone(visit_return(pilot, 30, 0, 0, 30, "science"))
        self.assertIsNotNone(visit_return(pilot, 30, 0, 0, 90, "science"))
        pilot.rules["sample_cost"] = 100
        self.assertIsNone(visit_return(pilot, 30, 0, 0, 90, "science"))
        pilot._to = lambda *args: (float("inf"), 1.)
        self.assertIsNone(visit_return(pilot, 30, 0, 0, 90, "science"))

    def test_mask_retains_base_and_releases_newly_infeasible_held_goal(self):
        chooser = GoalChooser(lambda ids, features: len(ids) - 1, persistent=True)
        pilot = public_pilot()
        pilot.choose, pilot.feasibility, pilot.decision_count = chooser, [], 0
        ids, features = ("base", "science"), np.zeros((2, 14))
        with patch("lightlag_rl_feasible.adapter.candidates", return_value=(ids, features)):
            FeasiblePilot._plan(pilot, 30, 0, 0, 90, 0)
            self.assertEqual(pilot.route, ["science"])
            FeasiblePilot._plan(pilot, 70, 0, 0, 6, 0)
        self.assertEqual(pilot.route, [])
        self.assertEqual(chooser.decisions[-1]["reason"], "release_missing")
        self.assertEqual(pilot.feasibility[-1]["offered_ids"], ["base"])
        self.assertEqual(pilot.decision_count, 2)

    def test_runner_control_is_identical_to_existing_scaffold(self):
        old_chooser = GoalChooser(greedy_choice, persistent=True)
        new_chooser = GoalChooser(greedy_choice, persistent=True)
        old = original_episode(1, old_chooser, keep_replay=True)
        new, checks = run_episode(1, new_chooser, charge_aware=False)
        old.pop("seconds")
        new.pop("seconds")
        self.assertEqual(normal(old), normal(new))
        self.assertEqual(old_chooser.decisions, new_chooser.decisions)
        self.assertEqual(checks, [])

    def test_treatment_runs_full_horizon_with_public_inputs(self):
        chooser = GoalChooser(greedy_choice, persistent=True)
        episode, checks = run_episode(1, chooser, charge_aware=True)
        self.assertEqual(episode["result"]["tick"], 420)
        self.assertEqual(episode["calls_by_tool"]["advance"], 420)
        self.assertEqual(episode["invalid_calls"], [])
        self.assertEqual(len(checks), len(chooser.decisions))
        self.assertTrue(all(r["offered_ids"][0] == "base" for r in checks))

    def test_gate_pairs_draws_within_maps_and_rejects_missing_or_unsafe_results(self):
        rows = [{**j, "reward": .1 + .01 * j["draw"], "alive": True,
                 "at_base": True, "samples": 1, "invalid_calls": 0,
                 "rejected_candidates": 0} for j in jobs((1, 2))]
        summary = summarize(rows, (1, 2))
        self.assertTrue(summary["screen_passes"])
        self.assertEqual(summary["contrasts"]["final"]["bootstrap_95"], [0., 0.])
        changed = copy.deepcopy(rows)
        next(r for r in changed if r["policy"] == "final" and r["mode"] == "charge_aware")["at_base"] = False
        self.assertFalse(summarize(changed, (1, 2))["screen_passes"])
        with self.assertRaises(ValueError):
            summarize(rows[:-1] + [rows[0]], (1, 2))


if __name__ == "__main__":
    unittest.main()
