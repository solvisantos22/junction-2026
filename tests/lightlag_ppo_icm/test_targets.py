"""The target mode on the traverse (targets.py): the agent picks targets, Kristján's pilot drives."""

import json
import os
import tempfile
import unittest

import numpy as np

from helpers import numeric_gradient, some_entries
from lightlag_ppo_icm.agent import Agent, AgentConfig, Policy
from lightlag_ppo_icm.envs import FiveTools, finish, make_env, run_target_episode, share
from lightlag_ppo_icm.nn import log_softmax
from lightlag_ppo_icm.player import load_player, nearest_target_player
from lightlag_ppo_icm.targets import (CHECK_WORLDS, DEV_WORLDS, TRAIN_WORLDS, TargetConfig, TargetTask,
                                      check_worlds)
from lightlag_ppo_icm.train import train

WORLD = 410005          # a training world: these tests check the machinery, not a score


def random_chooser(config, seed=0, seen=None):
    rng = np.random.default_rng(seed)

    def choose(obs, mask):
        if seen is not None:
            seen.append((np.array(obs), np.array(mask)))
        allowed = np.flatnonzero(mask[:config.home_action])
        return int(rng.choice(allowed)) if len(allowed) else config.home_action

    return choose


class TargetMissionTests(unittest.TestCase):
    def test_a_mission_plays_and_its_rewards_add_up_to_the_score(self):
        config, seen = TargetConfig(), []
        out = run_target_episode("traverse", WORLD, random_chooser(config, seen=seen), config, record=True)
        self.assertGreater(out["decisions"], 5)
        self.assertEqual(out["decisions"], len(seen))
        self.assertAlmostEqual(float(out["ext"].sum()), out["share"], places=5)
        for obs, mask in seen:
            self.assertEqual(obs.shape, (config.obs_dim,))
            self.assertTrue(np.isfinite(obs).all())
            self.assertLessEqual(float(np.abs(obs).max()), 5.0)
            self.assertTrue(mask[config.home_action])                  # home is always allowed
            filled = obs[12::12][:config.slots] > 0                     # the "is there a target" entry of each slot
            np.testing.assert_array_equal(filled, mask[:config.slots])  # exactly the filled slots are allowed

    def test_home_is_final_and_the_rover_parks_at_the_lander(self):
        config, calls = TargetConfig(), []

        def home(obs, mask):
            calls.append(1)
            return config.home_action

        out = run_target_episode("traverse", WORLD, home, config)
        self.assertEqual(len(calls), 1)
        self.assertTrue(out["alive"] and out["at_base"])
        self.assertEqual(out["share"], 0.0)

    def test_a_masked_choice_is_an_error_not_a_move(self):
        config = TargetConfig()

        def bad(obs, mask):
            masked = np.flatnonzero(~mask)
            return int(masked[0]) if len(masked) else config.n_actions

        with self.assertRaises(ValueError):
            run_target_episode("traverse", WORLD, bad, config)

    def test_the_whole_campaign_plays_mission_after_mission(self):
        from lightlag_traverse.campaign import TraverseCampaign
        campaign = TraverseCampaign((410006, 410007))
        task = TargetTask(FiveTools(campaign))
        task.play(random_chooser(task.config))
        self.assertEqual(len(task.pilots), 2)
        self.assertTrue(campaign.complete)
        result = campaign.evaluate()
        self.assertEqual(len(result["mission_rewards"]), 2)

    def test_the_nearest_target_rule_beats_random_choices(self):
        worlds = (410010, 410011, 410012)
        nearest, scores = nearest_target_player(), []
        for world in worlds:
            env = make_env("traverse", world)
            nearest(FiveTools(env), env)
            scores.append(share(finish(env)))
        randoms = [run_target_episode("traverse", w, random_chooser(TargetConfig(), seed=w), TargetConfig())["share"]
                   for w in worlds]
        self.assertGreater(np.mean(scores), np.mean(randoms))


class CampaignToolTests(unittest.TestCase):
    def test_the_campaign_tool_scores_all_missions_together(self):
        from lightlag_ppo_icm.campaign import play_campaign
        out = play_campaign(("nearest", "nearest_targets", None, (410006, 410007)))
        self.assertEqual([m["seed"] for m in out["missions"]], [410006, 410007])
        self.assertAlmostEqual(out["score"], out["raw_score"] / out["max_available_value"])
        self.assertGreater(out["score"], 0.0)

    def test_the_campaign_tool_refuses_unknown_players(self):
        from lightlag_ppo_icm.campaign import campaign_player
        with self.assertRaises(ValueError):
            campaign_player("plain", None)


class MaskTests(unittest.TestCase):
    def test_a_policy_never_picks_a_masked_action(self):
        rng = np.random.default_rng(0)
        policy = Policy([rng.standard_normal((5, 6)), rng.standard_normal(6)])
        for _ in range(200):
            mask = rng.random(6) < 0.5
            mask[5] = True
            obs = rng.standard_normal(5)
            self.assertTrue(mask[policy.act(obs, rng, mask)[0]])
            self.assertTrue(mask[policy.act(obs, None, mask)[0]])

    def test_ppo_gradients_with_a_mask_match_finite_differences(self):
        agent = Agent(AgentConfig(obs_dim=6, n_actions=5, hidden=8, feature_dim=5, seed=3, dtype="float64",
                                  ent_coef=0.05))
        rng = np.random.default_rng(11)
        for p in agent.actor.params + agent.critic.params:
            p += 0.2 * rng.standard_normal(p.shape)
        n = 24
        obs = rng.standard_normal((n, 6))
        mask = rng.random((n, 5)) < 0.6
        mask[:, 4] = True
        actions = np.array([rng.choice(np.flatnonzero(row)) for row in mask])
        logits = np.where(mask, agent.actor(obs), -1e9)
        old_logp = log_softmax(logits)[np.arange(n), actions] + rng.uniform(-0.5, 0.5, size=n)
        adv, ret = rng.standard_normal(n), rng.standard_normal(n)

        def loss():
            return agent.ppo_loss(obs, actions, old_logp, adv, ret, mask)[0]

        _, parts, grads = agent.ppo_loss(obs, actions, old_logp, adv, ret, mask)
        self.assertTrue(np.isfinite(parts["entropy"]))
        for p, g in zip(agent.actor.params + agent.critic.params, grads):
            picks = some_entries(rng, p)
            np.testing.assert_allclose([g[i] for i in picks], numeric_gradient(loss, p, picks),
                                       rtol=1e-4, atol=1e-8)


class WorldTests(unittest.TestCase):
    def test_the_claimed_worlds_pass_and_reserved_ones_are_refused(self):
        for low, high in (TRAIN_WORLDS, DEV_WORLDS, CHECK_WORLDS):
            check_worlds(low, high)
        for low, high in ((2027, 2029), (82000, 82000), (500, 500), (600, 700), (99991, 99991), (1, 10)):
            with self.assertRaises(ValueError):
                check_worlds(low, high)

    def test_training_refuses_a_reserved_range(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                train(env="traverse", targets=True, out=os.path.join(folder, "run"), updates=1, episodes=1,
                      workers=1, train_seeds=(2026, 2029), quiet=True)


class TargetTrainingTests(unittest.TestCase):
    def test_a_short_run_writes_a_policy_that_plays_the_target_mode(self):
        with tempfile.TemporaryDirectory() as folder:
            out = os.path.join(folder, "run")
            result = train(env="traverse", targets=True, out=out, updates=2, episodes=2, workers=1,
                           dev_seeds=(420000, 420000), eval_every=1, int_coef=0.5, quiet=True)
            self.assertEqual(result["updates_done"], 2)
            with open(os.path.join(out, "summary.json")) as handle:
                settings = json.load(handle)["settings"]
            self.assertTrue(settings["targets"])
            play = load_player(os.path.join(out, "policy.npz"))
            self.assertEqual(play.extra["task"]["mode"], "targets")
            env = make_env("traverse", WORLD)
            play(FiveTools(env), env)
            self.assertTrue(np.isfinite(share(finish(env))))


if __name__ == "__main__":
    unittest.main()
