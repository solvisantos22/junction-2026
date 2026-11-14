"""Synthetic retained artifacts only; never open a simulator or cloud job."""

import contextlib
import copy
import gzip
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.learning_campaign.decide import MAPS, decide, digest, main, read


def write(path, value):
    raw = json.dumps(value, sort_keys=True).encode()
    path.write_bytes(gzip.compress(raw, mtime=0) if path.suffix == ".gz" else raw)


def add_validation(path, count, reward):
    report = read(path / "report.json")
    policy = {"schema": "lightlag-learning-policy-v1", "algorithm": report["algorithm"],
              "episodes_seen": count, "model": {"candidate_dim": 20, "global_dim": 14, "hidden": 64},
              "config": {"gamma": 1., "schedule_episodes": 2048}}
    policy_path = path / f"policy-{count:05d}.json"
    write(policy_path, policy)
    episodes = [{"seed": world, "action_seed": report["seed"] * 1_000_000_000 + index,
                 "reward": reward, "result": {"tick": 420, "alive": True, "at_base": index < 20,
                                               "max_available_value": 64., "raw_score": reward * 64},
                 "invalid_calls": [], "decision_count": 4} for index, world in enumerate(MAPS)]
    summary = {"count": 32, "mean_reward": reward, "home": 20, "alive": 32,
               "invalid_calls": 0, "mean_decisions": 4.}
    write(path / f"validation-{count:05d}.json.gz",
          {"schema": "learning-validation-v1", "episodes_completed": count, "maps": MAPS,
           "policy_sha256": digest(policy_path), "episodes": episodes, "summary": summary})
    report["validations"][str(count)] = summary
    write(path / "report.json", report)


def make_run(parent, algorithm, seed, final=.125):
    path = parent / f"{algorithm}-{seed}"
    path.mkdir()
    report = {"schema": "learning-training-report-v1", "algorithm": algorithm, "seed": seed,
              "smoke": False, "status": "complete", "episodes_target": 2048, "episodes_completed": 2048,
              "batch_episodes": 32, "schedule_episodes": 2048,
              "source_sha256": {"docs/learning-campaign.md": "a" * 64, "lightlag_learning/train.py": "b" * 64},
              "python": "3.12.16", "numpy": "2.3.4", "torch": "2.9.1", "validations": {},
              "history": [{"first_episode": i * 32, "last_episode": (i + 1) * 32,
                           "count": 32, "sha256": "c" * 64} for i in range(64)]}
    write(path / "report.json", report)
    for count, reward in ((0, .0625), (512, .09375), (2048, final)):
        add_validation(path, count, reward)
    return path


def advance(path):
    report = read(path / "report.json")
    report["episodes_target"] = report["episodes_completed"] = 8192
    report["history"] = [{"first_episode": i * 32, "last_episode": (i + 1) * 32,
                          "count": 32, "sha256": "c" * 64} for i in range(256)]
    write(path / "report.json", report)
    add_validation(path, 8192, .15625)


class DecisionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.parent = Path(self.temporary.name)
        self.paths = [make_run(self.parent, algorithm, seed)
                      for algorithm in ("ppo", "replay") for seed in (17, 29, 43)]

    def test_all_seeds_and_source_bound_means_are_retained(self):
        result = decide(self.paths, "pilot")
        self.assertEqual(result["eligible_algorithms"], ["ppo", "replay"])
        for algorithm in result["algorithms"].values():
            self.assertEqual(algorithm["mean_gain"], .0625)
            self.assertEqual([row["seed"] for row in algorithm["seeds"]], [17, 29, 43])
            self.assertEqual(algorithm["positive_initializations"], 3)
            self.assertTrue(all(row["validations"]["2048"]["home"] == 20 for row in algorithm["seeds"]))
            self.assertTrue(all(len(row["report_sha256"]) == 64 for row in algorithm["seeds"]))

    def test_missing_duplicate_seed_and_unmatched_sources_are_rejected(self):
        for paths in (self.paths[:-1], self.paths[:-1] + [self.paths[0]]):
            with self.assertRaisesRegex(ValueError, "three seeds"):
                decide(paths, "pilot")
        report = read(self.paths[0] / "report.json")
        report["source_sha256"]["lightlag_learning/train.py"] = "d" * 64
        write(self.paths[0] / "report.json", report)
        with self.assertRaisesRegex(ValueError, "source or runtime"):
            decide(self.paths, "pilot")

    def test_incomplete_run_is_disqualified_without_extrapolation(self):
        path = self.paths[0]
        report = read(path / "report.json")
        report["status"], report["episodes_completed"] = "deadline", 512
        report["history"] = report["history"][:16]
        del report["validations"]["2048"]
        write(path / "report.json", report)
        (path / "validation-02048.json.gz").unlink()
        (path / "policy-02048.json").unlink()
        result = decide(self.paths, "pilot")
        self.assertFalse(result["algorithms"]["ppo"]["eligible"])
        self.assertIn("one_or_more_runs_incomplete", result["algorithms"]["ppo"]["reasons"])
        self.assertIsNone(result["algorithms"]["ppo"]["mean_gain"])
        self.assertEqual(set(result["algorithms"]["ppo"]["seeds"][0]["validations"]), {"0", "512"})
        self.assertTrue(result["algorithms"]["replay"]["eligible"])

    def test_death_at_earlier_milestone_disqualifies_and_two_positive_rule_applies(self):
        path = self.paths[0]
        file = path / "validation-00512.json.gz"
        data = read(file)
        data["episodes"][0]["result"]["alive"] = False
        data["summary"]["alive"] = 31
        write(file, data)
        report = read(path / "report.json")
        report["validations"]["512"] = data["summary"]
        write(path / "report.json", report)
        # One very large gain cannot replace the required two positive seeds.
        for index, reward in zip((3, 4, 5), (.5, .0625, .0625)):
            add_validation(self.paths[index], 2048, reward)
        result = decide(self.paths, "pilot")
        self.assertIn("validation_deaths", result["algorithms"]["ppo"]["reasons"])
        self.assertIn("fewer_than_two_positive_initializations", result["algorithms"]["replay"]["reasons"])

    def test_hash_maps_and_grade_tampering_are_rejected(self):
        path = self.paths[0]
        policy = path / "policy-02048.json"
        original = policy.read_bytes()
        policy.write_bytes(original + b" ")
        with self.assertRaisesRegex(ValueError, "policy hash"):
            decide(self.paths, "pilot")
        policy.write_bytes(original)
        file = path / "validation-02048.json.gz"
        data = read(file)
        data["episodes"][0]["seed"] = MAPS[1]
        write(file, data)
        with self.assertRaisesRegex(ValueError, "32 fixed maps"):
            decide(self.paths, "pilot")
        data["episodes"][0]["seed"] = MAPS[0]
        data["episodes"][0]["reward"] += .01
        write(file, data)
        with self.assertRaisesRegex(ValueError, "reward arithmetic"):
            decide(self.paths, "pilot")

    def test_expanded_requires_all_qualified_algorithms_and_unchanged_pilot_evidence(self):
        pilot = decide(self.paths, "pilot")
        previous = self.parent / "pilot.json"
        write(previous, pilot)
        for path in self.paths:
            advance(path)
        result = decide(self.paths, "expanded", previous)
        self.assertEqual(result["eligible_algorithms"], ["ppo", "replay"])
        self.assertEqual(result["algorithms"]["ppo"]["mean_gain"], .03125)
        self.assertEqual(result["previous_decision_sha256"], digest(previous))
        with self.assertRaisesRegex(ValueError, "three seeds"):
            decide(self.paths[:3], "expanded", previous)
        with self.assertRaisesRegex(ValueError, "preceding pilot"):
            decide(self.paths, "expanded")
        file = self.paths[0] / "validation-00512.json.gz"
        file.write_bytes(gzip.compress(json.dumps(read(file), indent=1).encode(), mtime=0))
        with self.assertRaisesRegex(ValueError, "pilot evidence changed"):
            decide(self.paths, "expanded", previous)

    def test_cli_refuses_overwriting_decision_file(self):
        output = self.parent / "decision.json"
        arguments = ["decide", *map(str, self.paths), "--stage", "pilot", "--output", str(output)]
        with patch("sys.argv", arguments), contextlib.redirect_stdout(io.StringIO()):
            main()
        retained = output.read_bytes()
        with patch("sys.argv", arguments), self.assertRaises(FileExistsError):
            main()
        self.assertEqual(output.read_bytes(), retained)


if __name__ == "__main__":
    unittest.main()
