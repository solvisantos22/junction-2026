import copy
import json
import unittest

import numpy as np

from lightlag_rl.adapter import run_episode
from lightlag_rl.model import Policy
from lightlag_rl_persistence import GoalChooser


def features(count):
    return np.arange(count * 14, dtype=float).reshape(count, 14) / 100


class GoalChooserTests(unittest.TestCase):
    def test_retains_id_across_reordering_and_new_alternatives(self):
        proposals = iter([np.int64(1), 0, 2])
        calls = []

        def choose(ids, x):
            calls.append((ids, x.copy()))
            return next(proposals)

        wrapper = GoalChooser(choose, persistent=True)
        self.assertEqual(wrapper(("base", "a", "b"), features(3)), 1)
        self.assertEqual(wrapper(("base", "new", "b", "a"), features(4)), 3)
        self.assertEqual(wrapper(("base", "a", "b"), features(3) * 2), 1)
        self.assertEqual(len(calls), 3)
        self.assertEqual([d["reason"] for d in wrapper.decisions],
                         ["initial_select", "retain", "retain"])
        self.assertEqual([d["proposed_action"] for d in wrapper.decisions], [1, 0, 2])
        self.assertEqual(wrapper.held_goal, "a")

    def test_missing_goal_releases_for_every_candidate_removal_cause(self):
        # The frozen adapter masks these causes; the wrapper only sees IDs.
        for cause in ("sampled", "pending", "unreachable", "return_time_infeasible"):
            with self.subTest(cause=cause):
                wrapper = GoalChooser(lambda ids, x: 1, persistent=True)
                wrapper(("base", "a"), features(2))
                self.assertEqual(wrapper(("base", "b"), features(2)), 1)
                row = wrapper.decisions[-1]
                self.assertEqual((row["prior_goal"], row["held_goal"], row["reason"]),
                                 ("a", "b", "release_missing"))

    def test_base_is_not_held_and_single_base_releases_science_goal(self):
        proposals = iter([0, 1, 0, 1])
        wrapper = GoalChooser(lambda ids, x: next(proposals), persistent=True)
        self.assertEqual(wrapper(("base", "a"), features(2)), 0)
        self.assertIsNone(wrapper.held_goal)
        self.assertEqual(wrapper(("base", "a"), features(2)), 1)
        self.assertEqual(wrapper(("base",), features(1)), 0)
        self.assertIsNone(wrapper.held_goal)
        self.assertEqual(wrapper(("base", "b"), features(2)), 1)
        self.assertEqual([d["reason"] for d in wrapper.decisions],
                         ["initial_select", "unheld_select", "release_missing", "unheld_select"])

    def test_invalid_proposal_fails_before_retention_without_state_change(self):
        for invalid in (True, np.bool_(False), 1.0, -1, 2, None):
            with self.subTest(invalid=invalid):
                proposals = iter([1, invalid])
                wrapper = GoalChooser(lambda ids, x: next(proposals), persistent=True)
                wrapper(("base", "a"), features(2))
                before = copy.deepcopy(wrapper.decisions)
                with self.assertRaises(ValueError):
                    wrapper(("base", "a"), features(2))
                self.assertEqual(wrapper.decisions, before)
                self.assertEqual(wrapper.held_goal, "a")

    def test_inputs_and_trace_do_not_alias_chooser_or_caller_arrays(self):
        def mutating_chooser(ids, x):
            x[:] = -123
            return 1

        x = features(2)
        before = x.copy()
        ids = ["base", "a"]
        wrapper = GoalChooser(mutating_chooser, persistent=True)
        wrapper(ids, x)
        np.testing.assert_array_equal(x, before)
        x[:] = 456
        ids[1] = "changed"
        self.assertEqual(wrapper.decisions[0]["features"], before.tolist())
        self.assertEqual(wrapper.decisions[0]["ids"], ["base", "a"])
        json.dumps(wrapper.decisions, allow_nan=False)

    def test_passthrough_does_not_hold_and_instances_are_independent(self):
        proposals = iter([1, 2, 0])
        wrapper = GoalChooser(lambda ids, x: next(proposals), persistent=False)
        self.assertEqual([wrapper(("base", "a", "b"), features(3)) for _ in range(3)],
                         [1, 2, 0])
        self.assertTrue(all(d["reason"] == "pass_through" and d["held_goal"] is None
                            and d["prior_goal"] is None for d in wrapper.decisions))
        a = GoalChooser(lambda ids, x: 1, persistent=True)
        b = GoalChooser(lambda ids, x: 2, persistent=True)
        a(("base", "a", "b"), features(3))
        self.assertEqual(b(("base", "a", "b"), features(3)), 2)
        self.assertEqual((a.held_goal, b.held_goal), ("a", "b"))

    def test_used_seed_passthrough_matches_original_replay_and_rng_exactly(self):
        def make_choose():
            policy, rng = Policy(seed=17), np.random.default_rng(17)
            state = copy.deepcopy(policy.state_dict())
            return policy, rng, state, lambda ids, x: policy.choose(x, rng)

        original_policy, original_rng, original_weights, original_choose = make_choose()
        wrapped_policy, wrapped_rng, wrapped_weights, wrapped_choose = make_choose()
        direct = run_episode(1, original_choose, keep_replay=True)
        wrapper = GoalChooser(wrapped_choose, persistent=False)
        wrapped = run_episode(1, wrapper, keep_replay=True)
        direct.pop("seconds")
        wrapped.pop("seconds")
        self.assertEqual(wrapped, direct)
        self.assertEqual(original_rng.bit_generator.state, wrapped_rng.bit_generator.state)
        self.assertEqual(original_policy.state_dict(), original_weights)
        self.assertEqual(wrapped_policy.state_dict(), wrapped_weights)
        self.assertEqual(len(wrapper.decisions), wrapped["decision_count"])

    def test_used_seed_persistence_keeps_original_full_horizon_and_grading(self):
        policy, rng = Policy(seed=17), np.random.default_rng(17)
        weights = copy.deepcopy(policy.state_dict())
        wrapper = GoalChooser(lambda ids, x: policy.choose(x, rng), persistent=True)
        run = run_episode(1, wrapper, keep_replay=True)
        self.assertEqual(run["result"]["tick"], 420)
        self.assertEqual(run["calls_by_tool"]["advance"], 420)
        self.assertEqual(run["reward"], run["result"]["raw_score"] / run["result"]["max_available_value"])
        self.assertEqual(run["replay"]["result"], run["result"])
        self.assertEqual(run["invalid_calls"], [])
        self.assertEqual(policy.state_dict(), weights)
        self.assertEqual(len(wrapper.decisions), run["decision_count"])
        self.assertTrue(any(d["reason"] == "retain" for d in wrapper.decisions))


if __name__ == "__main__":
    unittest.main()
