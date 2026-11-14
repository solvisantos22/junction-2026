import os
import tempfile
import unittest

import numpy as np

from helpers import numeric_gradient, some_entries
from lightlag_ppo_icm.agent import Agent, AgentConfig, Policy, RunningStd, discounted, gae, load_policy
from lightlag_ppo_icm.nn import log_softmax


def small_agent(**kw):
    settings = dict(obs_dim=6, n_actions=4, hidden=8, feature_dim=5, seed=3, dtype="float64")
    settings.update(kw)
    agent = Agent(AgentConfig(**settings))
    rng = np.random.default_rng(11)
    for name in Agent.NETWORKS:  # move every weight off its initial value, biases included
        for p in getattr(agent, name).params:
            p += 0.2 * rng.standard_normal(p.shape)
    return agent, rng


class LossGradientTests(unittest.TestCase):
    def test_ppo_gradients_match_finite_differences(self):
        agent, rng = small_agent(ent_coef=0.05)
        n = 24
        obs = rng.standard_normal((n, 6))
        actions = rng.integers(0, 4, size=n)
        logp_now = log_softmax(agent.actor(obs))[np.arange(n), actions]
        old_logp = logp_now + rng.uniform(-0.5, 0.5, size=n)   # ratios on both sides of the clip
        adv = rng.standard_normal(n)
        ret = rng.standard_normal(n)

        def loss():
            return agent.ppo_loss(obs, actions, old_logp, adv, ret)[0]

        _, parts, grads = agent.ppo_loss(obs, actions, old_logp, adv, ret)
        self.assertGreater(parts["clip_frac"], 0.1)    # the clipped branch is exercised
        self.assertLess(parts["clip_frac"], 0.9)
        params = agent.actor.params + agent.critic.params
        self.assertEqual(len(grads), len(params))
        for p, g in zip(params, grads):
            picks = some_entries(rng, p)
            np.testing.assert_allclose([g[i] for i in picks], numeric_gradient(loss, p, picks),
                                       rtol=1e-4, atol=1e-8)

    def test_icm_gradients_match_finite_differences(self):
        n = 16
        # The forward loss does not train the encoder, so the encoder is checked on the inverse
        # loss alone (beta 0), and the two heads on the full loss.
        for beta, checked in ((0.0, ("encoder", "inverse")), (0.3, ("inverse", "forward_model"))):
            agent, rng = small_agent(icm_beta=beta)
            obs, nxt = rng.standard_normal((n, 6)), rng.standard_normal((n, 6))
            actions = rng.integers(0, 4, size=n)

            def loss():
                return agent.icm_loss(obs, actions, nxt)[0]

            _, _, grads = agent.icm_loss(obs, actions, nxt)
            params = agent.encoder.params + agent.inverse.params + agent.forward_model.params
            self.assertEqual(len(grads), len(params))
            offset = 0
            for name in ("encoder", "inverse", "forward_model"):
                count = len(getattr(agent, name).params)
                if name in checked:
                    for p, g in zip(params[offset:offset + count], grads[offset:offset + count]):
                        picks = some_entries(rng, p)
                        np.testing.assert_allclose([g[i] for i in picks], numeric_gradient(loss, p, picks),
                                                   rtol=1e-4, atol=1e-8)
                offset += count


class ReturnTests(unittest.TestCase):
    def test_discounted_and_gae(self):
        rewards = np.array([1.0, 0.0, 2.0])
        np.testing.assert_allclose(discounted(rewards, 0.5), [1.5, 1.0, 2.0])
        values = np.array([0.5, 0.25, 1.0])
        adv, ret = gae(rewards, values, gamma=1.0, lam=1.0)   # lambda 1: Monte Carlo return - value
        np.testing.assert_allclose(ret, [3.0, 2.0, 2.0])
        np.testing.assert_allclose(adv, [2.5, 1.75, 1.0])
        adv0, _ = gae(rewards, values, gamma=0.9, lam=0.0)    # lambda 0: the one-step error
        np.testing.assert_allclose(adv0, [1.0 + 0.9 * 0.25 - 0.5, 0.0 + 0.9 * 1.0 - 0.25, 2.0 - 1.0])

    def test_running_std(self):
        rng = np.random.default_rng(0)
        data = rng.normal(3.0, 2.0, size=5000)
        stats = RunningStd()
        for chunk in np.array_split(data, 17):
            stats.update(chunk)
        self.assertAlmostEqual(stats.mean, data.mean(), places=2)
        self.assertAlmostEqual(stats.std, data.std(), places=2)


def bandit_episodes(agent, rng, count=64, contexts=4):
    """One-step episodes: the observation names a context, the reward is 1 for the matching action."""
    policy = agent.policy()
    episodes = []
    for _ in range(count):
        context = int(rng.integers(contexts))
        obs = np.zeros(6)
        obs[context] = 1.0
        action, logp = policy.act(obs, rng)
        episodes.append({"obs": obs[None, :], "actions": np.array([action]), "logp": np.array([logp]),
                         "ext": np.array([float(action == context)])})
    return episodes


class LearningTests(unittest.TestCase):
    def test_ppo_learns_a_contextual_bandit(self):
        agent = Agent(AgentConfig(obs_dim=6, n_actions=4, hidden=32, feature_dim=8, lr=3e-3, ext_scale=1.0,
                                  int_coef=0.0, ent_coef=0.0, target_kl=None, seed=5))
        rng = np.random.default_rng(5)
        first = np.mean([e["ext"][0] for e in bandit_episodes(agent, rng, 256)])
        for _ in range(60):
            batch, _ = agent.prepare(bandit_episodes(agent, rng))
            agent.update(batch)
        last = np.mean([e["ext"][0] for e in bandit_episodes(agent, rng, 256)])
        self.assertLess(first, 0.45)
        self.assertGreater(last, 0.9)
        greedy = agent.policy()
        for context in range(4):
            obs = np.zeros(6)
            obs[context] = 1.0
            self.assertEqual(greedy.act(obs)[0], context)

    def test_curiosity_fades_on_transitions_seen_again_and_stays_on_new_ones(self):
        agent = Agent(AgentConfig(obs_dim=6, n_actions=4, hidden=32, feature_dim=8, icm_lr=3e-3, seed=7))
        rng = np.random.default_rng(7)
        # A deterministic little world: the action shifts the observation along one axis.
        obs = rng.uniform(-1, 1, size=(256, 6))
        actions = rng.integers(0, 4, size=256)
        nxt = obs.copy()
        nxt[np.arange(256), actions] += 0.5
        before = agent.intrinsic(obs, actions, nxt).mean()
        for _ in range(300):
            _, _, grads = agent.icm_loss(obs, actions, nxt)
            agent.icm_opt.step(grads)
        after = agent.intrinsic(obs, actions, nxt).mean()
        self.assertLess(after, 0.25 * before)
        _, parts, _ = agent.icm_loss(obs, actions, nxt)
        self.assertGreater(parts["inverse_accuracy"], 0.8)     # the features kept the action's effect
        surprise = nxt.copy()
        surprise[:, 4:] += 2.0                                  # a change no action explains
        self.assertGreater(agent.intrinsic(obs, actions, surprise).mean(), 2 * after)

    def test_curiosity_sees_only_its_inputs(self):
        agent, rng = small_agent(icm_inputs=(0, 2, 5))
        self.assertEqual(agent.encoder.sizes[0], 3)
        obs, nxt = rng.standard_normal((8, 6)), rng.standard_normal((8, 6))
        actions = rng.integers(0, 4, size=8)
        before = agent.intrinsic(obs, actions, nxt)
        changed, changed_next = obs.copy(), nxt.copy()
        changed[:, [1, 3, 4]] += 5.0        # entries the module is not shown
        changed_next[:, [1, 3, 4]] -= 5.0
        np.testing.assert_array_equal(agent.intrinsic(changed, actions, changed_next), before)
        changed_next[:, 2] += 1.0           # an entry it is shown
        self.assertFalse(np.array_equal(agent.intrinsic(changed, actions, changed_next), before))
        self.assertTrue(np.isfinite(agent.icm_loss(obs, actions, nxt)[0]))
        with self.assertRaises(ValueError):
            small_agent(icm_inputs=(0, 6))

    def test_prepare_shapes_and_episode_ends(self):
        agent, rng = small_agent(target_kl=None)
        policy = agent.policy()
        episodes = []
        for length in (3, 5, 1):
            obs = rng.standard_normal((length, 6))
            acted = [policy.act(row, rng) for row in obs]
            episodes.append({"obs": obs, "actions": np.array([a for a, _ in acted]),
                             "logp": np.array([lp for _, lp in acted]), "ext": rng.uniform(0, 0.1, size=length)})
        batch, stats = agent.prepare(episodes)
        self.assertEqual(stats["steps"], 9)
        self.assertEqual(batch["has_next"].tolist(), [True, True, False, True, True, True, True, False, False])
        np.testing.assert_allclose(batch["next_obs"][0], batch["obs"][1])
        for name in ("adv", "ret"):
            self.assertTrue(np.isfinite(batch[name]).all())
        plain, _ = agent.prepare(episodes, int_coef=0.0)       # no curiosity: the extrinsic reward alone
        last = episodes[0]["ext"][-1] * agent.config.ext_scale
        self.assertAlmostEqual(plain["ret"][2], last, places=9)
        stats_update = agent.update(batch)
        self.assertEqual(stats_update["epochs_run"], agent.config.epochs)
        for name in ("pg_loss", "v_loss", "entropy", "approx_kl", "inverse_loss", "forward_loss"):
            self.assertTrue(np.isfinite(stats_update[name]), name)


class SavingTests(unittest.TestCase):
    def test_save_and_load_give_the_same_agent(self):
        agent, rng = small_agent()
        obs = rng.standard_normal((5, 6))
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "agent.npz")
            agent.int_returns.update(rng.standard_normal(50))
            agent.save(path, extra={"task": {"headings": 16}})
            masked, _ = small_agent(icm_inputs=(1, 4))
            masked_path = os.path.join(folder, "masked.npz")
            masked.save(masked_path)
            self.assertEqual(Agent.load(masked_path)[0].icm_index.tolist(), [1, 4])
            loaded, extra = Agent.load(path)
            policy, extra_again = load_policy(path)
        self.assertEqual(extra, {"task": {"headings": 16}})
        self.assertEqual(extra_again, extra)
        np.testing.assert_array_equal(loaded.actor(obs), agent.actor(obs))
        np.testing.assert_array_equal(loaded.values(obs), agent.values(obs))
        np.testing.assert_array_equal(loaded.encoder(obs), agent.encoder(obs))
        self.assertAlmostEqual(loaded.int_returns.std, agent.int_returns.std)
        np.testing.assert_allclose(policy.logits(obs[0]), agent.actor(obs[:1])[0])
        self.assertEqual(policy.act(obs[0])[0], int(np.argmax(agent.actor(obs[:1])[0])))

    def test_sampling_follows_the_probabilities(self):
        agent, rng = small_agent()
        policy = agent.policy()
        obs = rng.standard_normal(6)
        p = np.exp(log_softmax(policy.logits(obs)))
        draws = np.bincount([policy.act(obs, rng)[0] for _ in range(4000)], minlength=4) / 4000
        np.testing.assert_allclose(draws, p, atol=0.04)
        with self.assertRaises(ValueError):
            Policy([np.zeros((2, 2))])


if __name__ == "__main__":
    unittest.main()
