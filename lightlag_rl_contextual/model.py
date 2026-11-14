"""A contextual scorer; the original tested gradient and Adam math are reused."""

import numpy as np

from lightlag_rl.model import Policy as IndependentPolicy

FEATURE_COUNT = 60
HIDDEN = 32


class Policy(IndependentPolicy):
    def __init__(self, seed=17):
        rng = np.random.default_rng(seed)
        self.W = rng.normal(0, .15, (FEATURE_COUNT, HIDDEN))
        self.b = np.zeros(HIDDEN)
        self.v = rng.normal(0, .1, HIDDEN)

    def state_dict(self):
        return {"schema": "rl-contextual-policy-v1", **{k: getattr(self, k).tolist() for k in ("W", "b", "v")}}

    @classmethod
    def from_state(cls, state):
        if state.get("schema") != "rl-contextual-policy-v1":
            raise ValueError("unknown contextual policy")
        obj = cls()
        for k, shape in (("W", (FEATURE_COUNT, HIDDEN)), ("b", (HIDDEN,)), ("v", (HIDDEN,))):
            value = np.array(state[k], dtype=np.float64)
            if value.shape != shape or not np.isfinite(value).all():
                raise ValueError("invalid contextual weights")
            setattr(obj, k, value)
        return obj

    def _forward(self, features):
        x = np.asarray(features, dtype=np.float64)
        if x.ndim != 2 or x.shape[1] != FEATURE_COUNT or not len(x) or not np.isfinite(x).all():
            raise ValueError("expected finite nonempty 60-feature candidates")
        h = np.tanh(x @ self.W + self.b)
        logits = h @ self.v
        weights = np.exp(logits - logits.max())
        return x, h, weights / weights.sum()
