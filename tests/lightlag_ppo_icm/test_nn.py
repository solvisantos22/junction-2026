import unittest

import numpy as np

from helpers import numeric_gradient, some_entries
from lightlag_ppo_icm.nn import Adam, MLP, log_softmax, orthogonal


class NetworkTests(unittest.TestCase):
    def test_orthogonal_columns_and_rows(self):
        rng = np.random.default_rng(0)
        tall = orthogonal(rng, 8, 3)
        wide = orthogonal(rng, 3, 8)
        self.assertEqual(tall.shape, (8, 3))
        self.assertEqual(wide.shape, (3, 8))
        np.testing.assert_allclose(tall.T @ tall, np.eye(3), atol=1e-10)
        np.testing.assert_allclose(wide @ wide.T, np.eye(3), atol=1e-10)

    def test_log_softmax_normalises_and_survives_large_logits(self):
        logits = np.array([[1000.0, 1001.0, 999.0], [-5.0, 0.0, 5.0]])
        logp = log_softmax(logits)
        self.assertTrue(np.isfinite(logp).all())
        np.testing.assert_allclose(np.exp(logp).sum(axis=1), 1.0, atol=1e-12)

    def test_backward_matches_finite_differences(self):
        for out_tanh in (False, True):
            rng = np.random.default_rng(1)
            net = MLP((5, 7, 6, 3), rng, out_tanh=out_tanh)
            for p in net.params:  # biases start at zero; give every weight a gradient worth checking
                p += 0.3 * rng.standard_normal(p.shape)
            x = rng.standard_normal((4, 5))
            target = rng.standard_normal((4, 3))

            def loss():
                return 0.5 * float(((net(x) - target) ** 2).sum())

            out, cache = net.forward(x)
            grads, d_input = net.backward(cache, out - target)
            for p, g in zip(net.params, grads):
                picks = some_entries(rng, p)
                np.testing.assert_allclose([g[i] for i in picks], numeric_gradient(loss, p, picks),
                                           rtol=1e-5, atol=1e-8)
            picks = some_entries(rng, x)
            np.testing.assert_allclose([d_input[i] for i in picks], numeric_gradient(loss, x, picks),
                                       rtol=1e-5, atol=1e-8)

    def test_adam_minimises_and_clips(self):
        rng = np.random.default_rng(2)
        w = [rng.standard_normal(4), rng.standard_normal((2, 2))]
        opt = Adam(w, lr=0.05, max_norm=1.0)
        first = opt.step([2 * w[0], 2 * w[1]])
        self.assertGreater(first, 0)
        for _ in range(400):
            opt.step([2 * w[0], 2 * w[1]])
        self.assertLess(max(abs(w[0]).max(), abs(w[1]).max()), 1e-2)
        with self.assertRaises(ValueError):
            opt.step([np.full(4, np.nan), np.zeros((2, 2))])
        with self.assertRaises(ValueError):
            opt.step([np.zeros(4)])


if __name__ == "__main__":
    unittest.main()
