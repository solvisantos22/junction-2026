"""Synthetic learner tests: no simulator, cloud, or reserved map is opened."""

import copy
import json
import unittest

import numpy as np
import torch

from lightlag_learning.learners import (Learner, PrioritizedReplay, chooser_from_state,
                                        double_dqn_targets, n_step_transitions, ppo_surrogate)
from lightlag_learning.models import CandidateNetwork, batch_observations


def observation(size=3, tick=0):
    return {"ids": ["base"] + [f"target-{i}" for i in range(1, size)],
            "candidates": [[i / 4, (i - 1) / 3, tick / 420] for i in range(size)],
            "global": [tick / 420, .6], "mask": [True] * size,
            "tick": tick, "planned_tick": tick}


def episode(reward=.8, length=4, action=1):
    observations = [observation(tick=index * 7) for index in range(length)]
    transitions = [{"obs": obs, "action": action,
                    "next_obs": observations[index + 1] if index + 1 < length else None,
                    "reward": reward if index + 1 == length else 0.,
                    "done": index + 1 == length, "elapsed_ticks": 7 + index,
                    "termination_reason": "horizon" if index + 1 == length else "sample_pending"}
                   for index, obs in enumerate(observations)]
    return {"reward": reward, "transitions": transitions}


class LearningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def test_candidate_permutation_and_padding_preserve_scores_and_value(self):
        learner = Learner("ppo", 3, 2, 17)
        obs = observation()
        obs["mask"][1] = False
        permutation = [2, 0, 1]
        reordered = {**obs, **{key: [obs[key][i] for i in permutation]
                               for key in ("ids", "candidates", "mask")}}
        with torch.no_grad():
            scores, value = learner.model.observations([obs])
            mixed, mixed_value = learner.model.observations([obs, observation(7)])
            permuted, permuted_value = learner.model.observations([reordered])
        torch.testing.assert_close(scores[0], mixed[0, :3], rtol=1e-6, atol=1e-7)
        torch.testing.assert_close(value, mixed_value[:1], rtol=1e-6, atol=1e-7)
        torch.testing.assert_close(scores[0, permutation], permuted[0], rtol=1e-6, atol=1e-7)
        torch.testing.assert_close(value, permuted_value, rtol=1e-6, atol=1e-7)
        batch = batch_observations([obs, observation(7)], 3, 2)
        self.assertTrue(batch["present"][0, 1])
        self.assertFalse(batch["mask"][0, 1])
        self.assertFalse(batch["present"][0, 3])
        # An observed but invalid candidate contributes context; padding does not.
        changed = copy.deepcopy(obs)
        changed["candidates"][1] = [100., -100., 50.]
        with torch.no_grad():
            _, changed_value = learner.model.observations([changed])
        self.assertNotEqual(float(value[0]), float(changed_value[0]))

    def test_action_mask_is_respected_in_every_inference_mode(self):
        obs = observation()
        obs["mask"] = [False, False, True]
        for algorithm in ("ppo", "replay"):
            learner = Learner(algorithm, 3, 2, 17)
            for explore in (False, True):
                choose = chooser_from_state(learner.inference_state(), np.random.default_rng(6), explore)
                self.assertEqual([choose(obs) for _ in range(20)], [2] * 20)
        obs["mask"] = [False] * 3
        with self.assertRaisesRegex(ValueError, "masked"):
            learner.act(obs, np.random.default_rng(3))

    def test_n_step_windows_stop_at_terminal_and_sum_elapsed_ticks(self):
        rows = n_step_transitions(episode(length=5), steps=3)
        self.assertEqual([r["steps"] for r in rows], [3, 3, 3, 2, 1])
        self.assertEqual([r["done"] for r in rows], [False, False, True, True, True])
        self.assertEqual([r["reward"] for r in rows], [0., 0., .8, .8, .8])
        self.assertEqual(rows[0]["elapsed_ticks"], 7 + 8 + 9)
        self.assertEqual(rows[0]["next_obs"]["tick"], 21)
        self.assertIsNone(rows[2]["next_obs"])
        other = n_step_transitions(episode(reward=.2, length=1))
        self.assertEqual(other[0]["reward"], .2)

    def test_double_target_uses_online_argmax_and_never_bootstraps_terminal(self):
        class Scores:
            def __init__(self, values):
                self.values, self.seen = values, []

            def observations(self, observations):
                self.seen.extend(observations)
                scores = torch.tensor([self.values for _ in observations], dtype=torch.float32)
                mask = torch.tensor([obs["mask"] for obs in observations])
                return scores.masked_fill(~mask, -1e30), torch.zeros(len(observations))

        obs = observation()
        obs["mask"] = [True, False, True]
        online, target = Scores([1., 100., 5.]), Scores([9., 200., 2.])
        rows = [{"reward": .25, "done": False, "next_obs": obs},
                {"reward": .75, "done": True, "next_obs": obs}]
        values = double_dqn_targets(online, target, rows)
        torch.testing.assert_close(values, torch.tensor([2.25, .75]))
        self.assertEqual(len(online.seen), 1)
        self.assertEqual(len(target.seen), 1)

    def test_terminal_public_observation_is_validated_but_not_an_extra_transition(self):
        data = episode(length=1)
        terminal = observation(tick=420)
        terminal["mask"] = [True, False, False]
        data["transitions"][-1]["next_obs"] = terminal
        for algorithm in ("ppo", "replay"):
            learner = Learner(algorithm, 3, 2, 17)
            metrics = learner.update([data])
            self.assertEqual(metrics["transitions_seen"], 1)
            if algorithm == "replay":
                row = learner.replay.rows[0]
                self.assertTrue(row["done"])
                self.assertEqual(row["next_obs"]["tick"], 420)
                target = double_dqn_targets(learner.model, learner.target, [row])
                self.assertAlmostEqual(float(target[0]), .8, places=6)

    def test_per_probabilities_weights_and_ring_checkpoint(self):
        replay = PrioritizedReplay(capacity=3, alpha=.6)
        for row in n_step_transitions(episode(length=3)):
            replay.append(row)
        replay.update_priorities([0, 1, 2], [1., 3., 9.])
        expected = (np.array([1., 3., 9.]) + 1e-6) ** .6
        expected /= expected.sum()
        np.testing.assert_allclose(replay.probabilities(), expected)
        indices, _, weights = replay.sample(100, beta=.7, rng=np.random.default_rng(17))
        expected_weights = (expected[indices] / expected.min()) ** (-.7)
        np.testing.assert_allclose(weights, expected_weights, rtol=1e-6)
        replay.append(n_step_transitions(episode(reward=.1, length=1))[0])
        self.assertEqual(len(replay), 3)
        self.assertEqual(replay.rows[0]["reward"], .1)
        self.assertEqual(replay.position, 1)

    def test_ppo_clipping_handles_both_advantage_signs(self):
        log_ratio = torch.log(torch.tensor([1.5, .5, 1.5, .5])).requires_grad_()
        objective = ppo_surrogate(log_ratio, torch.zeros(4), torch.tensor([1., 1., -1., -1.]))
        self.assertAlmostEqual(float(objective.detach()), (1.2 + .5 - 1.5 - .8) / 4, places=6)
        objective.backward()
        torch.testing.assert_close(log_ratio.grad, torch.tensor([0., .125, -.375, 0.]))

    def test_ppo_learns_reward_preference_and_uses_completed_episode_returns(self):
        learner = Learner("ppo", 3, 2, 17)
        obs = observation()
        initial_scores = learner.model.observations([obs])[0][0]
        before = float((initial_scores[1] - initial_scores[0]).detach())
        episodes = [episode(reward=1., length=1, action=1) if i % 2 else
                    episode(reward=0., length=1, action=0) for i in range(64)]
        metrics = learner.update(episodes)
        final_scores = learner.model.observations([obs])[0][0]
        after = float((final_scores[1] - final_scores[0]).detach())
        self.assertGreater(after, before)
        self.assertEqual(metrics["batch_gradient_steps"], 4)
        self.assertEqual(metrics["episodes_seen"], 64)
        self.assertTrue(np.isfinite(metrics["value_loss"]))

    def test_replay_warmup_ratio_target_sync_and_fixed_schedule(self):
        learner = Learner("replay", 3, 2, 17)
        metrics = learner.update([episode(length=3)])
        self.assertEqual(metrics["batch_gradient_steps"], 0)
        metrics = learner.update([episode(length=4) for _ in range(32)])
        self.assertEqual(metrics["batch_gradient_steps"], 32)
        self.assertEqual(metrics["replay_size"], 131)
        learner.gradient_steps = 99
        scores, _ = learner.model.observations([observation()])
        learner._step(scores[0, 1].square())
        self.assertEqual(learner.gradient_steps, 100)
        for key, value in learner.model.state_dict().items():
            torch.testing.assert_close(value, learner.target.state_dict()[key], rtol=0, atol=0)
        learner.episodes_seen = 8192
        self.assertAlmostEqual(learner.epsilon, .05)
        self.assertEqual(learner.beta, 1.)

    def test_complete_json_checkpoint_reproduces_actions_and_next_update(self):
        episodes = [episode(reward=(i % 3) / 2, length=4, action=i % 3) for i in range(32)]
        for algorithm in ("ppo", "replay"):
            with self.subTest(algorithm=algorithm):
                learner = Learner(algorithm, 3, 2, 29)
                learner.update(episodes)
                payload = json.loads(json.dumps(learner.state_dict(), allow_nan=False))
                restored = Learner.from_state(payload)
                self.assertEqual(restored.state_dict(), payload)
                rng_a, rng_b = np.random.default_rng(9), np.random.default_rng(9)
                self.assertEqual([learner.act(observation(), rng_a) for _ in range(10)],
                                 [restored.act(observation(), rng_b) for _ in range(10)])
                first_metrics, second_metrics = learner.update(episodes), restored.update(episodes)
                self.assertEqual(first_metrics, second_metrics)
                self.assertEqual(learner.state_dict(), restored.state_dict())

    def test_bad_episode_and_checkpoint_configuration_are_rejected(self):
        learner = Learner("ppo", 3, 2, 17)
        invalid = episode()
        invalid["transitions"][0]["reward"] = .3
        with self.assertRaisesRegex(ValueError, "terminal reward"):
            learner.update([invalid])
        invalid = episode()
        invalid["transitions"][-1]["done"] = False
        with self.assertRaisesRegex(ValueError, "terminal reward"):
            learner.update([invalid])
        payload = learner.state_dict()
        payload["config"]["gamma"] = .99
        with self.assertRaisesRegex(ValueError, "hyperparameters"):
            Learner.from_state(payload)


if __name__ == "__main__":
    unittest.main()
