"""A shared candidate scorer trained with episodic policy gradients (NumPy only)."""

import numpy as np

FEATURE_COUNT = 14


class Policy:
    def __init__(self, seed=17, hidden=16):
        rng = np.random.default_rng(seed)
        self.W = rng.normal(0, .25, (FEATURE_COUNT, hidden))
        self.b = np.zeros(hidden)
        self.v = rng.normal(0, .1, hidden)

    def state_dict(self):
        return {"schema": "lightlag-rl-policy-v1", "W": self.W.tolist(),
                "b": self.b.tolist(), "v": self.v.tolist()}

    @classmethod
    def from_state(cls, state):
        if state.get("schema") != "lightlag-rl-policy-v1":
            raise ValueError("unknown policy format")
        obj = cls()
        obj.W, obj.b, obj.v = (np.array(state[k], dtype=np.float64) for k in ("W", "b", "v"))
        if (obj.W.ndim != 2 or obj.W.shape[0] != FEATURE_COUNT or
                obj.b.shape != (obj.W.shape[1],) or obj.v.shape != obj.b.shape or
                not all(np.isfinite(getattr(obj, k)).all() for k in ("W", "b", "v"))):
            raise ValueError("invalid policy weights")
        return obj

    def _forward(self, features):
        x = np.asarray(features, dtype=np.float64)
        if x.ndim != 2 or x.shape[1] != FEATURE_COUNT or len(x) < 1 or not np.isfinite(x).all():
            raise ValueError("expected finite nonempty candidate features")
        h = np.tanh(x @ self.W + self.b)
        logits = h @ self.v
        weights = np.exp(logits - logits.max())
        p = weights / weights.sum()
        return x, h, p

    def probabilities(self, features):
        return self._forward(features)[2]

    def choose(self, features, rng):
        return int(rng.choice(len(features), p=self.probabilities(features)))

    def gradient(self, features, action, advantage, entropy=.01):
        """Ascent gradient of advantage * log p(action) + entropy * H(p)."""
        x, h, p = self._forward(features)
        if not 0 <= action < len(p) or not np.isfinite([advantage, entropy]).all():
            raise ValueError("invalid action or objective")
        logp = np.log(np.maximum(p, 1e-300))
        H = -float(p @ logp)
        dz = -advantage * p
        dz[action] += advantage
        dz -= entropy * p * (logp + H)
        dh = dz[:, None] * self.v[None, :] * (1 - h * h)
        return {"W": x.T @ dh, "b": dh.sum(axis=0), "v": h.T @ dz}


class Adam:
    """Adam ascent with a recorded optimizer state and global gradient clipping."""
    def __init__(self, policy):
        self.policy = policy
        self.m = {k: np.zeros_like(getattr(policy, k)) for k in ("W", "b", "v")}
        self.v = {k: np.zeros_like(getattr(policy, k)) for k in ("W", "b", "v")}
        self.t = 0

    def step(self, gradient, lr=.02, max_norm=5.):
        if set(gradient) != set(self.m):
            raise ValueError("gradient fields mismatch")
        g = {k: np.asarray(gradient[k], dtype=np.float64) for k in self.m}
        if any(g[k].shape != self.m[k].shape or not np.isfinite(g[k]).all() for k in g):
            raise ValueError("nonfinite or malformed gradient")
        norm = float(np.sqrt(sum(np.sum(value * value) for value in g.values())))
        scale = min(1., max_norm / max(norm, 1e-12))
        self.t += 1
        for k in g:
            value = g[k] * scale
            self.m[k] = .9 * self.m[k] + .1 * value
            self.v[k] = .999 * self.v[k] + .001 * value * value
            update = (self.m[k] / (1 - .9 ** self.t)) / (np.sqrt(self.v[k] / (1 - .999 ** self.t)) + 1e-8)
            setattr(self.policy, k, getattr(self.policy, k) + lr * update)
        return norm

    def state_dict(self):
        return {"t": self.t, "m": {k: v.tolist() for k, v in self.m.items()},
                "v": {k: v.tolist() for k, v in self.v.items()}}
