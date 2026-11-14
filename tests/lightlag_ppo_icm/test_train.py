import contextlib
import io
import json
import os
import tempfile
import unittest

import numpy as np

from lightlag_dynamic.tools import PublicTools
from lightlag_ppo_icm import check
from lightlag_ppo_icm.agent import Agent, load_policy
from lightlag_ppo_icm.envs import finish, make_env, share
from lightlag_ppo_icm.player import load_player, random_player
from lightlag_ppo_icm.task import SAMPLE, WAIT, TaskConfig
from lightlag_ppo_icm.train import collect, drive_lengths, rollouts, summary, train


class TrainingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.out = os.path.join(cls.folder.name, "run")
        # In this process (workers=1), two small updates on the max env, on training seeds only.
        cls.result = train(env="max", out=cls.out, updates=2, episodes=6, workers=1, eval_every=1,
                           dev_seeds=(300000, 300002), quiet=True)

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def test_a_run_leaves_a_log_checkpoints_and_a_policy(self):
        self.assertEqual(self.result["updates_done"], 2)
        self.assertEqual(self.result["steps"], 2 * 6 * 47)
        with open(os.path.join(self.out, "log.jsonl")) as log:
            rows = [json.loads(line) for line in log]
        self.assertEqual([row["update"] for row in rows], [1, 2])
        self.assertEqual([row["steps"] for row in rows], [6 * 47, 2 * 6 * 47])     # decisions so far
        self.assertEqual(rows[0]["batch_steps"], 6 * 47)
        for row in rows:
            for name in ("train_share", "dev_share", "entropy", "inverse_loss", "forward_loss", "int_raw"):
                self.assertTrue(np.isfinite(row[name]), name)
        self.assertLess(rows[1]["int_coef"], rows[0]["int_coef"])      # curiosity is annealed
        for name in ("best.npz", "last.npz", "policy.npz", "summary.json"):
            self.assertTrue(os.path.exists(os.path.join(self.out, name)), name)
        agent, extra = Agent.load(os.path.join(self.out, "last.npz"))
        self.assertEqual(extra["env"], "max")
        self.assertEqual(extra["update"], 2)
        self.assertEqual(agent.config.obs_dim, TaskConfig.from_dict(extra["task"]).obs_dim)
        with self.assertRaises(ValueError):                             # a run folder is never reused
            train(env="max", out=self.out, updates=1, episodes=2, workers=1, quiet=True)

    def test_drive_lengths_fit_the_sampling_disc(self):
        self.assertEqual(drive_lengths("max"), (0.25, 0.5, 1.0))            # 0.5, 1 and 2 m of a 2 m drive
        self.assertEqual(drive_lengths("rush"), (0.1, 0.2, 0.4))            # the same metres of a 5 m drive
        self.assertEqual(drive_lengths("traverse"), (0.3333, 0.6667, 1.0))  # 1.7 and 3.3 m, then the 5 m cap
        self.assertEqual(TaskConfig.from_dict(Agent.load(os.path.join(self.out, "last.npz"))[1]["task"]).metres,
                         (0.25, 0.5, 1.0))

    def test_the_untrained_policy_starts_by_waiting_half_the_time(self):
        agent = Agent.load(os.path.join(self.out, "last.npz"))[0]
        bias = agent.actor.params[-1]
        self.assertGreater(bias[WAIT], bias[SAMPLE])
        self.assertGreater(bias[SAMPLE], bias[2:].max())

    def test_the_policy_file_plays_through_the_five_public_tools(self):
        path = os.path.join(self.out, "policy.npz")
        policy, extra = load_policy(path)
        self.assertEqual(len(policy.arrays), 6)
        self.assertEqual(extra["delay"], 3)
        shares = []
        for player in (load_player(path), load_player(path, sample_seed=1), random_player()):
            env = make_env("max", 300003)
            player(PublicTools(env))          # the repository's own five-tool boundary
            shares.append(share(finish(env)))
            self.assertEqual(len(env.replay()["commands"]), 47)
        self.assertTrue(all(0.0 <= s <= 1.0 for s in shares))

    def test_rollouts_keep_their_order_and_training_data_matches_the_score(self):
        agent = Agent.load(os.path.join(self.out, "last.npz"))[0]
        task = TaskConfig()
        keys = [(200001, 5), (200002, 6), (200003, 7)]
        played = rollouts(None, 2, agent.actor.state(), task, "max", 3, keys)
        self.assertEqual([e["seed"] for e in played], [200001, 200002, 200003])
        for episode in played:
            self.assertEqual(episode["obs"].shape, (47, task.obs_dim))
            self.assertEqual(len(episode["actions"]), 47)
            self.assertAlmostEqual(float(episode["ext"].sum()), episode["share"], places=6)
            self.assertTrue((episode["logp"] <= 0).all())
        again = collect({"actor": agent.actor.state(), "task": task.to_dict(), "env": "max", "delay": 3,
                         "episodes": keys[:1], "greedy": False})[0]
        np.testing.assert_array_equal(again["actions"], played[0]["actions"])    # same seeds, same episode
        self.assertEqual(set(summary(played)), {"share", "alive", "home", "samples"})

    def test_the_check_prints_the_policy_beside_scripted_players(self):
        out = os.path.join(self.folder.name, "rows.json")
        with contextlib.redirect_stdout(io.StringIO()) as printed:
            rows = check.main(["--policy", os.path.join(self.out, "policy.npz"), "--seeds", "300004-300005",
                               "--players", "ppo_icm,plain,random,nothing,blind", "--workers", "1", "--out", out,
                               "--also", "last=" + os.path.join(self.out, "last.npz")])
        self.assertEqual(len(rows), 12)
        self.assertEqual([row["player"] for row in rows[::2]], ["ppo_icm", "last", "plain", "random", "nothing", "blind"])
        self.assertTrue(all(row["crash"] is None for row in rows))
        text = printed.getvalue()
        self.assertIn("max, delay 3, seeds 300004-300005", text)
        self.assertIn("ppo_icm - blind", text)
        with open(out) as handle:
            saved = json.load(handle)
        self.assertEqual(saved["env"], "max")
        self.assertEqual(len(saved["rows"]), 12)
        with self.assertRaises(ValueError):
            check.player("teleport", None, "max")


if __name__ == "__main__":
    unittest.main()
