import copy
import json
import unittest

import numpy as np
import torch

from lightlag_hybrid_train.learner import Learner, chooser_from_state
from lightlag_hybrid_train.model import PriorNetwork
from lightlag_learning.environment import greedy_choice, run_episode
from lightlag_learning.learners import Learner as FrozenLearner


def observation(tick=0):
    rows = [[0.0] * 20 for _ in range(4)]
    rows[0][0] = 1
    for i, credit in enumerate((0, 1, .5, 99)):
        rows[i][14], rows[i][19] = .1, credit
    return {"ids": ["base", "a", "b", "masked"], "candidates": rows,
            "global": [0.0] * 14, "mask": [True, True, True, False],
            "tick": tick, "planned_tick": tick + 3}


def synthetic_episodes():
    obs = observation()
    terminal = observation(420)
    terminal["mask"] = [True, False, False, False]
    return [{"reward": reward, "transitions": [
        {"obs": copy.deepcopy(obs), "action": action, "next_obs": copy.deepcopy(terminal),
         "reward": reward, "done": True, "elapsed_ticks": 420,
         "termination_reason": "horizon"}]} for action, reward in ((1, .2), (2, .8))]


class PriorModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def learner(self, algorithm="prior", seed=17):
        return Learner(algorithm, 20, 14, seed, 4096)

    def test_initial_prior_exact_greedy_plain_uniform_and_same_residual(self):
        obs = observation()
        prior, plain = self.learner(), self.learner("plain")
        self.assertEqual(prior.model.residual.export(), plain.model.residual.export())
        for learner, expected in ((prior, [1/15, 13/15, 1/15, 0]),
                                  (plain, [1/3, 1/3, 1/3, 0])):
            scores, _ = learner.model.observations([obs])
            np.testing.assert_allclose(scores.softmax(-1).detach().numpy()[0], expected,
                                       rtol=1e-6, atol=1e-7)
            self.assertTrue(torch.all(learner.model.residual.score[-1].weight == 0))
        self.assertEqual(prior.act(obs, np.random.default_rng(0), False), greedy_choice(obs))
        self.assertEqual(plain.act(obs, np.random.default_rng(0), False), 0)
        rng = np.random.default_rng(17)
        actions = [plain.act(obs, rng, True) for _ in range(600)]
        self.assertEqual(set(actions), {0, 1, 2})
        self.assertTrue(all(160 <= actions.count(i) <= 240 for i in (0, 1, 2)))

    def test_greedy_raw_precision_ties_and_home_only(self):
        learner = self.learner()
        obs = observation()
        obs["candidates"][2][19] = 1.0000000001
        self.assertEqual(np.float32(obs["candidates"][2][19]), np.float32(1))
        self.assertEqual(greedy_choice(obs), 2)
        self.assertEqual(learner.act(obs, np.random.default_rng(0), False), 2)
        obs["candidates"][2][19] = 1
        self.assertEqual(learner.act(obs, np.random.default_rng(0), False), 1)
        obs["mask"] = [True, False, False, False]
        logits, _ = learner.model.observations([obs])
        np.testing.assert_allclose(logits.softmax(-1).detach().numpy(), [[1, 0, 0, 0]])

    def test_sampling_inference_and_update_use_effective_probabilities(self):
        obs, episodes = observation(), synthetic_episodes()
        learner = self.learner()
        logits, _ = learner.model.observations([obs])
        distribution = torch.distributions.Categorical(logits=logits)
        expected_entropy = float(distribution.entropy().detach()[0])
        probabilities = logits.softmax(-1).detach().numpy()[0].astype(float)
        probabilities /= probabilities.sum()
        rng, expected_rng = np.random.default_rng(29), np.random.default_rng(29)
        choose = chooser_from_state(learner.inference_state(), rng, explore=True)
        self.assertEqual([choose(obs) for _ in range(100)],
                         [int(expected_rng.choice(4, p=probabilities)) for _ in range(100)])
        # No parameter movement: all four inherited PPO epochs must report the
        # transformed distribution entropy and exactly zero importance-ratio KL.
        learner.optimizer.param_groups[0]["lr"] = 0
        metrics = learner.update(episodes)
        self.assertAlmostEqual(metrics["entropy"], expected_entropy, places=6)
        self.assertAlmostEqual(metrics["approx_kl"], 0, places=7)
        self.assertEqual(metrics["algorithm"], "prior")
        self.assertEqual(metrics["batch_gradient_steps"], 4)

    def test_update_changes_residual_and_checkpoint_roundtrip_reproduces_next_update(self):
        for variant in ("prior", "plain"):
            learner = self.learner(variant)
            before = copy.deepcopy(learner.model.export())
            learner.update(synthetic_episodes())
            self.assertNotEqual(learner.model.export(), before)
            state = json.loads(json.dumps(learner.state_dict(), allow_nan=False))
            restored = Learner.from_state(state)
            self.assertEqual(restored.state_dict(), state)
            learner.update(synthetic_episodes())
            restored.update(synthetic_episodes())
            self.assertEqual(learner.state_dict(), restored.state_dict())
            policy = json.loads(json.dumps(learner.inference_state(), allow_nan=False))
            choose = chooser_from_state(policy, np.random.default_rng(43))
            self.assertEqual(choose(observation()),
                             learner.act(observation(), np.random.default_rng(43), False))

    def test_plain_ppo_gradient_matches_frozen_implementation_from_identical_zero_head(self):
        plain = self.learner("plain")
        frozen = FrozenLearner("ppo", 20, 14, 17, 4096)
        frozen.model.load_state_dict(plain.model.residual.state_dict())
        plain.update(synthetic_episodes())
        frozen.update(synthetic_episodes())
        for left, right in zip(plain.model.residual.parameters(), frozen.model.parameters()):
            torch.testing.assert_close(left, right, atol=1e-7, rtol=1e-6)

    def test_observation_weights_and_global_rng_unchanged_by_loading_and_inference(self):
        learner = self.learner()
        obs = observation()
        policy = learner.inference_state()
        original_obs, original_policy = copy.deepcopy(obs), copy.deepcopy(policy)
        random_state = torch.random.get_rng_state().clone()
        choose = chooser_from_state(policy, np.random.default_rng(0))
        choose(obs)
        self.assertEqual(obs, original_obs)
        self.assertEqual(policy, original_policy)
        self.assertTrue(torch.equal(random_state, torch.random.get_rng_state()))
        bad = copy.deepcopy(policy)
        bad["model"]["variant"] = "plain"
        with self.assertRaises(ValueError):
            chooser_from_state(bad, np.random.default_rng(0))
        bad = copy.deepcopy(policy["model"])
        bad["greedy_mass"] = .9
        with self.assertRaises(ValueError):
            PriorNetwork.from_export(bad)
        obs["mask"] = [False] * 4
        with self.assertRaises(ValueError):
            choose(obs)

    def test_initial_prior_used_map_full_horizon_equals_original_greedy(self):
        chooser = chooser_from_state(self.learner().inference_state(), np.random.default_rng(17))
        prior = run_episode(1, chooser, keep_replay=True)
        greedy = run_episode(1, greedy_choice, keep_replay=True)
        self.assertEqual(prior["replay"], greedy["replay"])
        self.assertEqual(prior["transitions"], greedy["transitions"])
        self.assertEqual(prior["result"], greedy["result"])
        self.assertEqual(prior["reward"], greedy["reward"])
        self.assertEqual(prior["result"]["tick"], 420)


if __name__ == "__main__":
    unittest.main()
