"""Small fully connected networks with hand-written backpropagation, and Adam (NumPy only).

The repository's simulators and players need no deep-learning framework, and the networks of
this baseline are tiny (three layers of 128 units), so the gradients are written out here.
tests/lightlag_ppo_icm/test_nn.py checks every one of them against finite differences.
"""

import numpy as np


def orthogonal(rng, rows, cols, gain=1.0):
    """An orthogonal weight matrix (rows x cols), the usual PPO initialisation."""
    a = rng.standard_normal((max(rows, cols), min(rows, cols)))
    q, r = np.linalg.qr(a)
    q = q * np.sign(np.diag(r))  # make the decomposition unique
    return gain * (q if rows >= cols else q.T)


def log_softmax(logits):
    z = logits - logits.max(axis=-1, keepdims=True)
    return z - np.log(np.exp(z).sum(axis=-1, keepdims=True))


class MLP:
    """tanh hidden layers and a linear (or tanh) output. `forward` returns the output and a cache;
    `backward` turns the gradient at the output into gradients for every weight and for the input."""

    def __init__(self, sizes, rng, out_gain=1.0, out_tanh=False, dtype=np.float64):
        self.sizes = tuple(int(s) for s in sizes)
        self.out_tanh = bool(out_tanh)
        self.dtype = np.dtype(dtype)
        self.params = []  # W0, b0, W1, b1, ...
        last = len(self.sizes) - 2
        for i, (n_in, n_out) in enumerate(zip(self.sizes[:-1], self.sizes[1:])):
            gain = out_gain if i == last else np.sqrt(2.0)
            self.params.append(orthogonal(rng, n_in, n_out, gain).astype(self.dtype))
            self.params.append(np.zeros(n_out, dtype=self.dtype))

    @property
    def layers(self):
        return len(self.sizes) - 1

    def forward(self, x):
        """Output and the cache `backward` needs (the activations of every layer)."""
        acts = [np.asarray(x, dtype=self.dtype)]
        last = self.layers - 1
        for i in range(self.layers):
            z = acts[-1] @ self.params[2 * i] + self.params[2 * i + 1]
            acts.append(np.tanh(z) if (i < last or self.out_tanh) else z)
        return acts[-1], acts

    def __call__(self, x):
        return self.forward(x)[0]

    def backward(self, cache, d_out):
        """Gradients in the order of `params`, and the gradient at the input."""
        grads = [None] * len(self.params)
        d = np.asarray(d_out, dtype=self.dtype)
        last = self.layers - 1
        for i in range(last, -1, -1):
            if i < last or self.out_tanh:
                d = d * (1.0 - cache[i + 1] ** 2)
            grads[2 * i] = cache[i].T @ d
            grads[2 * i + 1] = d.sum(axis=0)
            d = d @ self.params[2 * i].T
        return grads, d

    def state(self):
        return [p.copy() for p in self.params]


class Adam:
    """Adam on a list of arrays that it updates in place, with a cap on the gradient norm."""

    def __init__(self, params, lr=3e-4, beta1=0.9, beta2=0.999, eps=1e-5, max_norm=None):
        self.params, self.lr, self.beta1, self.beta2, self.eps = params, lr, beta1, beta2, eps
        self.max_norm = max_norm
        self.m = [np.zeros_like(p) for p in params]
        self.v = [np.zeros_like(p) for p in params]
        self.t = 0

    def step(self, grads, lr=None):
        """One descent step. Returns the gradient norm before clipping."""
        if len(grads) != len(self.params):
            raise ValueError("one gradient per parameter array is needed")
        norm = float(np.sqrt(sum(float((g * g).sum()) for g in grads)))
        if not np.isfinite(norm):
            raise ValueError("the gradient is not finite")
        scale = 1.0 if self.max_norm is None or norm <= self.max_norm else self.max_norm / norm
        lr = self.lr if lr is None else lr
        self.t += 1
        correction = np.sqrt(1.0 - self.beta2 ** self.t) / (1.0 - self.beta1 ** self.t)
        for p, g, m, v in zip(self.params, grads, self.m, self.v):
            g = (g * scale).astype(p.dtype, copy=False)
            m *= self.beta1
            m += (1.0 - self.beta1) * g
            v *= self.beta2
            v += (1.0 - self.beta2) * g * g
            p -= (lr * correction * m / (np.sqrt(v) + self.eps)).astype(p.dtype, copy=False)
        return norm
