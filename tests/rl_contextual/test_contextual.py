import unittest
from unittest.mock import patch

import numpy as np

from lightlag_rl.adapter import greedy_choice
from lightlag_rl_contextual.adapter import ContextPilot, context_candidates, executed_decisions, run_episode
from lightlag_rl_contextual.model import Policy
from lightlag_traverse.environment import TraverseEnvironment
from tools.rl_contextual.run import STAGES, TRAIN_SEEDS, evaluation_jobs, fit_metrics, imitate, summarize


class ContextualTests(unittest.TestCase):
    def test_context_is_public_finite_and_contains_science_pool(self):
        env = TraverseEnvironment(1)
        with patch.object(env, "evaluate", side_effect=AssertionError("truth queried")):
            pilot = ContextPilot(env, greedy_choice)
            x, y, _, battery = pilot.predict(1)
            ids, features, checks = context_candidates(pilot, 1, x, y, battery)
        self.assertEqual(features.shape, (len(ids), 60))
        self.assertEqual(ids[0], "base")
        self.assertTrue(np.isfinite(features).all())
        self.assertTrue(all(checks[name] is not None for name in ids[1:]))
        np.testing.assert_allclose(features[:, 20:40], np.tile(features[1:, :20].mean(axis=0), (len(ids), 1)))
        np.testing.assert_allclose(features[:, 40:], np.tile(features[1:, :20].max(axis=0), (len(ids), 1)))

    def test_model_gradient_matches_finite_difference(self):
        policy = Policy(17)
        x = np.random.default_rng(1).normal(0, .2, (4, 60))
        grad = policy.gradient(x, 2, .7, entropy=.005)
        def objective():
            p = policy.probabilities(x)
            return .7 * np.log(p[2]) - .005 * float(p @ np.log(p))
        for key, index in (("W", (2, 3)), ("W", (42, 7)), ("b", (5,)), ("v", (4,))):
            weight = getattr(policy, key)
            saved = weight[index]
            weight[index] = saved + 1e-5
            plus = objective()
            weight[index] = saved - 1e-5
            minus = objective()
            weight[index] = saved
            self.assertAlmostEqual(grad[key][index], (plus - minus) / 2e-5, places=7)
        self.assertEqual(sum(getattr(policy, k).size for k in ("W", "b", "v")), 1984)
        np.testing.assert_allclose(policy.probabilities(x)[[2, 0, 3, 1]], policy.probabilities(x[[2, 0, 3, 1]]))

    def test_context_can_change_pairwise_odds(self):
        policy = Policy()
        policy.W[:] = 0; policy.b[:] = 0; policy.v[:] = 0
        policy.W[1, 0] = 1; policy.W[20, 0] = 1; policy.v[0] = 1
        x = np.zeros((3, 60)); x[0, 1] = .5; x[1, 1] = -.5
        before = policy.probabilities(x)
        x[:, 20] = 1
        after = policy.probabilities(x)
        self.assertNotAlmostEqual(before[0] / before[1], after[0] / after[1])

    def test_imitation_learns_synthetic_label_and_retained_proposals_are_excluded(self):
        x = np.zeros((3, 60)); x[1, 8] = 1
        data = [{"features": x.tolist(), "action": 1, "ids": ["base", "a", "b"]}]
        policy = Policy()
        before = fit_metrics(policy, data)
        imitate(policy, data, 17, 30)
        self.assertLess(fit_metrics(policy, data)["cross_entropy"], before["cross_entropy"] * .8)
        records = [{"ids": d["ids"], "features": d["features"], "proposed_action": d["action"], "reason": r}
                   for d in data for r in ("initial_select", "retain", "release_missing")]
        self.assertEqual(len(executed_decisions(records)), 2)

    def test_learner_never_calls_teacher_and_runs_to_terminal_reward(self):
        with patch("lightlag_traverse.pilot.Pilot._plan", side_effect=AssertionError("teacher called")):
            result = run_episode(1, "policy", Policy().state_dict(), 17)
        self.assertEqual(result["result"]["tick"], 420)
        self.assertEqual(result["public_calls"]["advance"], 420)
        self.assertEqual(result["invalid_calls"], [])
        self.assertTrue(all(r["teacher_route"] is None for r in result["planning"]))
        self.assertEqual(result["reward"], result["result"]["raw_score"] / result["result"]["max_available_value"])

    def test_evaluation_pairs_all_seeds_and_stages_and_rejects_omissions(self):
        states = {(t, s): {} for t in TRAIN_SEEDS for s in STAGES}
        jobs = evaluation_jobs((74000, 74001), states)
        self.assertEqual(len(jobs), 40)
        rows = [{**{k: v for k, v in j.items() if k != "policy_state"},
                 "reward": .23 if j.get("stage") == "rl" else .2,
                 "alive": True, "home": True, "invalid": 0} for j in jobs]
        result = summarize(rows, (74000, 74001))
        self.assertTrue(result["screen_passes"])
        self.assertAlmostEqual(result["primary"]["mean_gain"], .03)
        with self.assertRaises(ValueError):
            summarize(rows[:-1] + [rows[0]], (74000, 74001))


if __name__ == "__main__":
    unittest.main()
