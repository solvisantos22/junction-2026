import gzip
import json
import multiprocessing as mp
from pathlib import Path
import tempfile
import unittest

import numpy as np

from lightlag_rl import train


def fake_collect(jobs, timeout):
    if timeout <= 0:
        raise AssertionError("nonpositive worker timeout")
    features = np.zeros((2, 14))
    features[0, 0], features[1, 8] = 1., 1.
    return [{"seed": job["seed"], "policy_seed": job["policy_seed"],
             "reward": float(i % 2), "episode": {"reward": float(i % 2)},
             "trajectory": [{"ids": ["base", "t1"], "features": features.tolist(), "action": i % 2}]}
            for i, job in enumerate(jobs)]


class TrainTests(unittest.TestCase):
    def run_fake(self, output, **kwargs):
        return train.run(output, updates=2, batch_size=4, workers=1, train_seed=17,
                         max_seconds=30, smoke=True, collector=kwargs.pop("collector", fake_collect),
                         pin_source=lambda: {"fixture": "hash"},
                         check_pins=kwargs.pop("check_pins", lambda _: None), **kwargs)

    def test_pair_baseline_removes_map_reward_offset(self):
        rows = [{"seed": seed, "reward": reward} for seed, reward in
                ((1, .2), (1, .4), (2, .6), (2, .8))]
        np.testing.assert_allclose(train.advantages(rows), [-1, 1, -1, 1])
        np.testing.assert_equal(train.advantages([{"seed": 1, "reward": .5}] * 2), [0, 0])
        rows[1]["seed"] = 9
        with self.assertRaises(ValueError):
            train.advantages(rows)

    def test_gradient_averages_episodes_not_number_of_decisions(self):
        class Policy:
            def state_dict(self):
                return {name: [0.] for name in train.PARAMETERS}

            def gradient(self, features, action, advantage, entropy):
                return {name: np.array([advantage]) for name in train.PARAMETERS}

        decision = {"features": [[0]], "action": 0}
        rows = [{"seed": 1, "reward": 1., "trajectory": [decision, decision]},
                {"seed": 1, "reward": 0., "trajectory": [decision]}]
        gradient, _ = train.batch_gradient(Policy(), rows)
        for value in gradient.values():
            np.testing.assert_allclose(value, [.5])

    def test_complete_training_retains_initial_final_checkpoints_and_rollouts(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            report = self.run_fake(output)
            self.assertEqual(report["status"], "complete")
            self.assertEqual(report["episodes_completed"], 8)
            self.assertEqual(report["updates_completed"], 2)
            self.assertEqual(report["config"]["training_seeds"], [1, 2])
            self.assertNotEqual(report["initial_policy_sha256"], report["final_policy_sha256"])
            checkpoint = json.loads((output / "checkpoint-0002.json").read_text())
            self.assertEqual(checkpoint["optimizer"]["t"], 2)
            self.assertIn("bit_generator", checkpoint["rng_state"])
            for index in (1, 2):
                batch = json.loads(gzip.decompress((output / "batches" / f"update-{index:04d}.json.gz").read_bytes()))
                self.assertEqual(len(batch["rows"]), 4)
                self.assertEqual(batch["rows"][0]["seed"], batch["rows"][1]["seed"])
                self.assertNotEqual(batch["rows"][0]["policy_seed"], batch["rows"][1]["policy_seed"])
            self.assertEqual(report["model_api_calls"], report["fresh_cases"])
            self.assertEqual(report["fresh_cases"], 0)

    def test_worker_timeout_is_incomplete_and_never_writes_final(self):
        def timeout(jobs, limit):
            raise mp.TimeoutError()

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            report = self.run_fake(output, collector=timeout)
            self.assertEqual(report["incomplete_reason"], "training_time_limit")
            self.assertEqual(report["updates_completed"], 0)
            self.assertFalse((output / "final-policy.json").exists())
            self.assertTrue((output / "checkpoint-0000.json").exists())

    def test_source_drift_keeps_completed_batch_but_never_updates_or_freezes(self):
        calls = []

        def check(pins):
            calls.append(pins)
            if len(calls) == 2:
                raise RuntimeError("fixture source drift")

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            report = self.run_fake(output, check_pins=check)
            self.assertEqual(report["status"], "incomplete")
            self.assertIn("source drift", report["incomplete_reason"])
            self.assertEqual(report["episodes_completed"], 4)
            self.assertEqual(report["updates_completed"], 0)
            self.assertTrue((output / "batches/update-0001.json.gz").exists())
            self.assertFalse((output / "final-policy.json").exists())

    def test_training_range_is_fixed_and_disjoint_from_reserved_check(self):
        seen = []

        def collect(jobs, timeout):
            seen.extend(job["seed"] for job in jobs)
            return fake_collect(jobs, timeout)

        with tempfile.TemporaryDirectory() as directory:
            report = train.run(Path(directory) / "run", updates=1, batch_size=4, workers=1,
                               collector=collect, pin_source=lambda: {}, check_pins=lambda _: None)
            self.assertEqual(report["status"], "complete")
        self.assertEqual(set(train.TRAIN_SEEDS), set(range(71000, 71128)))
        self.assertTrue(set(seen) <= set(train.TRAIN_SEEDS))
        self.assertFalse(set(seen) & set(range(72000, 72040)))

    def test_output_overwrite_and_bad_smoke_budget_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                self.run_fake(Path(directory))
            with self.assertRaises(ValueError):
                train.run(Path(directory) / "new", smoke=True, updates=16)


if __name__ == "__main__":
    unittest.main()
