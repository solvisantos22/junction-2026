"""PPO with an Intrinsic Curiosity Module (ICM), written out in NumPy.

PPO (Schulman et al. 2017): a clipped policy-gradient update on the advantages of the rollouts
just collected, with generalised advantage estimation, a value network and an entropy bonus.

ICM (Pathak et al. 2017, "Curiosity-driven Exploration by Self-supervised Prediction"): three
small networks beside the policy.

    encoder   phi(observation)                      features (of the entries in `icm_inputs`)
    inverse   (phi(s), phi(s'))  ->  action         trains the encoder: features keep what the
                                                    agent's own action explains
    forward   (phi(s), action)   ->  phi(s')        its error is the curiosity reward

    intrinsic reward = 1/2 * || forward(phi(s), a) - phi(s') ||^2

The forward model does not train the encoder here (its inputs and target are held fixed), a
common variant that keeps the features from collapsing to something trivially predictable. The
intrinsic reward is divided by a running standard deviation of its discounted return (as in
Burda et al. 2018), so its weight `int_coef` means the same thing all through training. The
policy is trained on  ext_scale * extrinsic + int_coef * intrinsic  with one value network.
With int_coef = 0 this is plain PPO, which is the ablation the tester offers.

`icm_inputs` matters: if the observation echoes the agent's last action, the inverse model
reads the action straight off that echo, the features hold nothing about the world, and
curiosity ends up rewarding whatever makes the echo jump. The task adapter therefore shows the
curiosity module only the entries that say where the rover is and what is around it.
"""

from dataclasses import asdict, dataclass
import json

import numpy as np

from .nn import Adam, MLP, log_softmax


@dataclass
class AgentConfig:
    obs_dim: int
    n_actions: int
    hidden: int = 128
    feature_dim: int = 64       # size of the ICM features
    gamma: float = 0.995
    lam: float = 0.95           # GAE
    clip: float = 0.2
    epochs: int = 4
    minibatches: int = 8
    lr: float = 3e-4
    icm_lr: float = 3e-4
    ent_coef: float = 0.01
    vf_coef: float = 0.5
    max_grad_norm: float = 0.5
    target_kl: float = 0.03     # stop an update's epochs early past 1.5 x this; None: never
    icm_beta: float = 0.2       # weight of the forward loss; the inverse loss gets 1 - beta
    ext_scale: float = 10.0     # the extrinsic reward is a share in 0..1 per episode
    int_coef: float = 0.5       # weight of the normalised curiosity reward; 0: plain PPO
    int_gamma: float = 0.99
    seed: int = 0
    dtype: str = "float32"      # of the networks; the gradient checks in the tests use float64
    icm_inputs: tuple = ()      # the observation entries the curiosity module sees; empty: all of them


class RunningStd:
    """Mean and variance of a stream, updated a batch at a time."""

    def __init__(self):
        self.count, self.mean, self.var = 1e-4, 0.0, 1.0

    def update(self, values):
        values = np.asarray(values, dtype=np.float64).ravel()
        if not len(values):
            return
        n, mean, var = len(values), float(values.mean()), float(values.var())
        total = self.count + n
        delta = mean - self.mean
        self.var = (self.var * self.count + var * n + delta * delta * self.count * n / total) / total
        self.mean += delta * n / total
        self.count = total

    @property
    def std(self):
        return float(np.sqrt(self.var))


class Policy:
    """The actor alone: what a rollout worker or a player needs. Greedy unless given an rng."""

    def __init__(self, arrays):
        self.arrays = [np.asarray(a, dtype=np.float64) for a in arrays]
        if len(self.arrays) % 2 or len(self.arrays) < 2:
            raise ValueError("a policy is a list of weight and bias arrays")

    def logits(self, obs):
        h = np.asarray(obs, dtype=np.float64)
        last = len(self.arrays) // 2 - 1
        for i in range(last + 1):
            h = h @ self.arrays[2 * i] + self.arrays[2 * i + 1]
            if i < last:
                h = np.tanh(h)
        return h

    def act(self, obs, rng=None):
        """(action, log-probability). With an rng the action is sampled, without it the mode."""
        logp = log_softmax(self.logits(obs))
        if rng is None:
            action = int(np.argmax(logp))
        else:
            action = min(len(logp) - 1, int(np.searchsorted(np.cumsum(np.exp(logp)), rng.random())))
        return action, float(logp[action])


def discounted(rewards, gamma):
    """Return-to-go of one episode."""
    out = np.zeros(len(rewards))
    running = 0.0
    for t in range(len(rewards) - 1, -1, -1):
        running = rewards[t] + gamma * running
        out[t] = running
    return out


def gae(rewards, values, gamma, lam):
    """Advantages and value targets of one complete episode (nothing follows the last step)."""
    adv = np.zeros(len(rewards))
    running = 0.0
    for t in range(len(rewards) - 1, -1, -1):
        following = values[t + 1] if t + 1 < len(rewards) else 0.0
        delta = rewards[t] + gamma * following - values[t]
        running = delta + gamma * lam * running
        adv[t] = running
    return adv, adv + values


class Agent:
    NETWORKS = ("actor", "critic", "encoder", "inverse", "forward_model")

    def __init__(self, config):
        c = self.config = config
        rng = np.random.default_rng(c.seed)
        d = np.dtype(c.dtype)
        self.icm_index = np.array(c.icm_inputs if len(c.icm_inputs) else range(c.obs_dim), dtype=np.int64)
        if len(self.icm_index) and not (0 <= self.icm_index.min() and self.icm_index.max() < c.obs_dim):
            raise ValueError("icm_inputs must be observation indices")
        self.actor = MLP((c.obs_dim, c.hidden, c.hidden, c.n_actions), rng, out_gain=0.01, dtype=d)
        self.critic = MLP((c.obs_dim, c.hidden, c.hidden, 1), rng, out_gain=1.0, dtype=d)
        self.encoder = MLP((len(self.icm_index), c.hidden, c.feature_dim), rng, out_gain=1.0, out_tanh=True, dtype=d)
        self.inverse = MLP((2 * c.feature_dim, c.hidden, c.n_actions), rng, out_gain=0.01, dtype=d)
        self.forward_model = MLP((c.feature_dim + c.n_actions, c.hidden, c.feature_dim), rng, out_gain=1.0, dtype=d)
        self.opt = Adam(self.actor.params + self.critic.params, lr=c.lr, max_norm=c.max_grad_norm)
        self.icm_opt = Adam(self.encoder.params + self.inverse.params + self.forward_model.params,
                            lr=c.icm_lr, max_norm=5.0)
        self.int_returns = RunningStd()
        self.rng = rng
        self.updates = 0

    # ---- acting -----------------------------------------------------------------------------
    def policy(self):
        return Policy(self.actor.state())

    def values(self, obs):
        return self.critic(obs)[:, 0].astype(np.float64)

    def _onehot(self, actions):
        out = np.zeros((len(actions), self.config.n_actions), dtype=self.actor.dtype)
        out[np.arange(len(actions)), actions] = 1.0
        return out

    def intrinsic(self, obs, actions, next_obs):
        """The curiosity reward of each transition: half the squared forward-model error."""
        phi, phi_next = self.encoder(obs[:, self.icm_index]), self.encoder(next_obs[:, self.icm_index])
        predicted = self.forward_model(np.concatenate([phi, self._onehot(actions)], axis=1))
        return 0.5 * ((predicted - phi_next) ** 2).sum(axis=1).astype(np.float64)

    # ---- losses and their gradients (checked against finite differences in the tests) ----------
    def ppo_loss(self, obs, actions, old_logp, adv, ret):
        """(loss, parts, gradients for actor.params + critic.params)."""
        c, n = self.config, len(obs)
        rows = np.arange(n)
        logits, actor_cache = self.actor.forward(obs)
        logp_all = log_softmax(logits)
        p = np.exp(logp_all)
        logp = logp_all[rows, actions]
        ratio = np.exp(logp - old_logp)
        plain, clipped = ratio * adv, np.clip(ratio, 1.0 - c.clip, 1.0 + c.clip) * adv
        entropy = -(p * logp_all).sum(axis=1)
        value, critic_cache = self.critic.forward(obs)
        value = value[:, 0]
        pg_loss = -np.minimum(plain, clipped).mean()
        v_loss = 0.5 * ((value - ret) ** 2).mean()
        loss = pg_loss - c.ent_coef * entropy.mean() + c.vf_coef * v_loss

        d_logp = -(adv * ratio * (plain <= clipped)) / n         # the clipped branch has no gradient
        d_logits = -p * d_logp[:, None]
        d_logits[rows, actions] += d_logp
        d_logits += c.ent_coef / n * p * (logp_all + entropy[:, None])
        actor_grads, _ = self.actor.backward(actor_cache, d_logits)
        critic_grads, _ = self.critic.backward(critic_cache, (c.vf_coef * (value - ret) / n)[:, None])
        parts = {"pg_loss": float(pg_loss), "v_loss": float(v_loss), "entropy": float(entropy.mean()),
                 "approx_kl": float((old_logp - logp).mean()),
                 "clip_frac": float((np.abs(ratio - 1.0) > c.clip).mean())}
        return float(loss), parts, actor_grads + critic_grads

    def icm_loss(self, obs, actions, next_obs):
        """(loss, parts, gradients for encoder.params + inverse.params + forward_model.params)."""
        c, n = self.config, len(obs)
        rows = np.arange(n)
        phi, cache_now = self.encoder.forward(obs[:, self.icm_index])
        phi_next, cache_next = self.encoder.forward(next_obs[:, self.icm_index])
        logits, inverse_cache = self.inverse.forward(np.concatenate([phi, phi_next], axis=1))
        logp_all = log_softmax(logits)
        inverse_loss = -logp_all[rows, actions].mean()
        predicted, forward_cache = self.forward_model.forward(
            np.concatenate([phi, self._onehot(actions)], axis=1))
        error = predicted - phi_next
        forward_loss = 0.5 * (error ** 2).sum(axis=1).mean()
        loss = (1.0 - c.icm_beta) * inverse_loss + c.icm_beta * forward_loss

        d_logits = np.exp(logp_all)
        d_logits[rows, actions] -= 1.0
        d_logits *= (1.0 - c.icm_beta) / n
        inverse_grads, d_pair = self.inverse.backward(inverse_cache, d_logits)
        grads_now, _ = self.encoder.backward(cache_now, d_pair[:, :c.feature_dim])
        grads_next, _ = self.encoder.backward(cache_next, d_pair[:, c.feature_dim:])
        encoder_grads = [a + b for a, b in zip(grads_now, grads_next)]
        forward_grads, _ = self.forward_model.backward(forward_cache, c.icm_beta * error / n)
        parts = {"inverse_loss": float(inverse_loss), "forward_loss": float(forward_loss),
                 "inverse_accuracy": float((logp_all.argmax(axis=1) == actions).mean())}
        return float(loss), parts, encoder_grads + inverse_grads + forward_grads

    # ---- one training update -------------------------------------------------------------------
    def prepare(self, episodes, int_coef=None):
        """Turn complete episodes into one training batch.

        Each episode: {"obs": (T, D), "actions": (T,), "logp": (T,), "ext": (T,)}, with `ext` the
        extrinsic reward of every decision. Returns (batch, stats).
        """
        c = self.config
        int_coef = c.int_coef if int_coef is None else int_coef
        lengths = [len(e["actions"]) for e in episodes]
        obs = np.concatenate([e["obs"] for e in episodes]).astype(self.actor.dtype)
        actions = np.concatenate([e["actions"] for e in episodes]).astype(np.int64)
        logp = np.concatenate([e["logp"] for e in episodes]).astype(np.float64)
        ext = np.concatenate([e["ext"] for e in episodes]).astype(np.float64)
        ends = np.cumsum(lengths)
        starts = ends - lengths
        has_next = np.ones(len(obs), dtype=bool)
        has_next[ends - 1] = False
        next_obs = np.roll(obs, -1, axis=0)   # rows where has_next is False are never used

        raw = np.zeros(len(obs))
        if has_next.any():
            raw[has_next] = self.intrinsic(obs[has_next], actions[has_next], next_obs[has_next])
        self.int_returns.update(np.concatenate([discounted(raw[a:b], c.int_gamma)
                                                for a, b in zip(starts, ends)]))
        intrinsic = raw / (self.int_returns.std + 1e-8)
        rewards = c.ext_scale * ext + int_coef * intrinsic
        values = self.values(obs)
        adv, ret = np.zeros(len(obs)), np.zeros(len(obs))
        for a, b in zip(starts, ends):
            adv[a:b], ret[a:b] = gae(rewards[a:b], values[a:b], c.gamma, c.lam)
        batch = {"obs": obs, "actions": actions, "logp": logp, "adv": adv, "ret": ret,
                 "next_obs": next_obs, "has_next": has_next}
        variance = float(ret.var())
        stats = {"steps": int(len(obs)), "episodes": len(episodes),
                 "ext_return": float(ext.sum() / len(episodes)),
                 "int_raw": float(raw[has_next].mean()) if has_next.any() else 0.0,
                 "int_return": float(int_coef * intrinsic.sum() / len(episodes)),
                 "explained_variance": float(1.0 - (ret - values).var() / variance) if variance > 0 else 0.0}
        return batch, stats

    def update(self, batch, lr_scale=1.0):
        """PPO epochs over the batch, the ICM trained on the same minibatches. Returns averages."""
        c = self.config
        n = len(batch["obs"])
        size = max(2, -(-n // c.minibatches))
        totals, counts, stop = {}, {}, False
        for epoch in range(c.epochs):
            order = self.rng.permutation(n)
            for start in range(0, n, size):
                idx = order[start:start + size]
                if len(idx) < 2:
                    continue
                adv = batch["adv"][idx]
                adv = (adv - adv.mean()) / (adv.std() + 1e-8)
                _, parts, grads = self.ppo_loss(batch["obs"][idx], batch["actions"][idx],
                                                batch["logp"][idx], adv, batch["ret"][idx])
                parts["grad_norm"] = self.opt.step(grads, lr=c.lr * lr_scale)
                pairs = idx[batch["has_next"][idx]]
                if len(pairs) >= 2:
                    _, icm_parts, icm_grads = self.icm_loss(batch["obs"][pairs], batch["actions"][pairs],
                                                            batch["next_obs"][pairs])
                    self.icm_opt.step(icm_grads, lr=c.icm_lr * lr_scale)
                    parts.update(icm_parts)
                for name, value in parts.items():
                    totals[name] = totals.get(name, 0.0) + value
                    counts[name] = counts.get(name, 0) + 1
                if c.target_kl is not None and parts["approx_kl"] > 1.5 * c.target_kl:
                    stop = True
                    break
            if stop:
                break
        self.updates += 1
        stats = {name: value / counts[name] for name, value in totals.items()}
        stats["epochs_run"] = epoch + 1
        return stats

    # ---- saving ----------------------------------------------------------------------------------
    def save(self, path, extra=None):
        """Every network, the reward normaliser and the configuration, in one .npz file."""
        arrays = {}
        for name in self.NETWORKS:
            for i, p in enumerate(getattr(self, name).params):
                arrays[f"{name}_{i}"] = p
        meta = {"format": "lightlag-ppo-icm-v1", "config": asdict(self.config), "updates": self.updates,
                "int_returns": [self.int_returns.count, self.int_returns.mean, self.int_returns.var],
                "extra": extra or {}}
        np.savez(path, meta=np.array(json.dumps(meta)), **arrays)

    @classmethod
    def load(cls, path):
        """(agent, extra) from a file written by `save`."""
        with np.load(path, allow_pickle=False) as data:
            meta = json.loads(str(data["meta"]))
            if meta.get("format") != "lightlag-ppo-icm-v1":
                raise ValueError("not a lightlag_ppo_icm checkpoint")
            agent = cls(AgentConfig(**{**meta["config"], "icm_inputs": tuple(meta["config"].get("icm_inputs", ()))}))
            for name in cls.NETWORKS:
                network = getattr(agent, name)
                saved = [data[f"{name}_{i}"] for i in range(len(network.params))]
                for target, source in zip(network.params, saved):
                    if target.shape != source.shape or not np.isfinite(source).all():
                        raise ValueError(f"the saved {name} weights do not fit")
                    target[...] = source
        agent.updates = meta["updates"]
        agent.int_returns.count, agent.int_returns.mean, agent.int_returns.var = meta["int_returns"]
        return agent, meta["extra"]


def load_policy(path):
    """(Policy, extra) from a checkpoint, without building the training networks."""
    with np.load(path, allow_pickle=False) as data:
        meta = json.loads(str(data["meta"]))
        if meta.get("format") != "lightlag-ppo-icm-v1":
            raise ValueError("not a lightlag_ppo_icm checkpoint")
        arrays, i = [], 0
        while f"actor_{i}" in data:
            arrays.append(data[f"actor_{i}"])
            i += 1
    return Policy(arrays), meta["extra"]
