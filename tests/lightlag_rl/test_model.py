import json
import unittest
import numpy as np

from lightlag_rl.model import Policy, Adam


class ModelTests(unittest.TestCase):
    def test_objective_gradient_matches_finite_differences(self):
        p = Policy(5, hidden=3)
        x = np.random.default_rng(8).normal(size=(4, 14))
        analytic = p.gradient(x, 2, .7, entropy=.03)
        def objective():
            probs = p.probabilities(x)
            return .7 * np.log(probs[2]) - .03 * np.sum(probs * np.log(probs))
        for key in ("W", "b", "v"):
            a = getattr(p, key)
            for index in np.ndindex(a.shape):
                original = a[index]
                a[index] = original + 1e-6
                high = objective()
                a[index] = original - 1e-6
                low = objective()
                a[index] = original
                self.assertAlmostEqual(analytic[key][index], (high-low)/2e-6, places=7)

    def test_positive_reward_makes_chosen_action_more_likely(self):
        p = Policy(7)
        x = np.zeros((2, 14)); x[1, 0] = 1
        before = p.probabilities(x)[1]
        opt = Adam(p)
        for _ in range(20):
            opt.step(p.gradient(x, 1, 1.0, entropy=0))
        self.assertGreater(p.probabilities(x)[1], before + .3)
        self.assertEqual(opt.state_dict()["t"], 20)

    def test_serialization_and_candidate_permutation(self):
        p = Policy(2); x = np.random.default_rng(4).normal(size=(5, 14))
        loaded = Policy.from_state(json.loads(json.dumps(p.state_dict())))
        np.testing.assert_array_equal(p.probabilities(x), loaded.probabilities(x))
        np.testing.assert_allclose(p.probabilities(x)[::-1], p.probabilities(x[::-1]))

    def test_single_candidate_gradient_is_zero(self):
        p = Policy(); x = np.ones((1, 14))
        self.assertEqual(p.choose(x, np.random.default_rng(2)), 0)
        for value in p.gradient(x, 0, .4).values():
            np.testing.assert_allclose(value, 0, atol=1e-15)


if __name__ == "__main__":
    unittest.main()
