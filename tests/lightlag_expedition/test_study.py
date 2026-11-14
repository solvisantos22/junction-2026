"""Exact discrete weights, paired fixtures, complete records and new-path protection."""

import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from lightlag_expedition.environment import ExpeditionEnvironment
from lightlag_expedition.model import INSPECTION_ACCURACY, PRIORS, REGIONS
from lightlag_expedition.study import RecordingPublicTools, run_study, science_worlds, summarize


class ExactScienceWeights(unittest.TestCase):
    def test_complete_joint_distribution_and_public_marginals(self):
        worlds = science_worlds()
        self.assertEqual(len(worlds), 64)
        self.assertEqual(len({world["id"] for world in worlds}), 64)
        self.assertAlmostEqual(sum(world["weight"] for world in worlds), 1.0)
        self.assertTrue(all(world["weight"] > 0 for world in worlds))
        for region in REGIONS:
            self.assertAlmostEqual(sum(world["weight"] for world in worlds
                                       if world["qualities"][region] == "rich"), PRIORS[region])
            self.assertAlmostEqual(sum(world["weight"] for world in worlds
                                       if world["signals"][region] == world["qualities"][region]),
                                   INSPECTION_ACCURACY)

    def test_summary_keeps_losses_and_is_weighted_not_episode_mean(self):
        rows = []
        for weight, raw in ((.9, 0), (.1, 20)):
            for policy in ("reference", "no_probe"):
                score = raw if policy == "reference" else 4
                rows.append({"mission_seed": 0, "policy": policy, "weight": weight,
                             "raw_score": score, "normalized_score": score / 20,
                             "alive": True, "at_base": True, "inspections_reserved": 0,
                             "inspections_executed": 0, "public_calls": 2,
                             "first_probe_region": None, "first_probe_is_leader": None})
        summary = summarize(rows)
        self.assertAlmostEqual(summary["aggregate"]["reference"]["raw_score"], 2)
        self.assertAlmostEqual(summary["reference_minus_control_normalized"]["no_probe"], -.1)


class RecordedStudy(unittest.TestCase):
    def test_new_directory_pairing_hashes_full_transcript_and_replay(self):
        world = science_worlds()[0]
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "new-study"
            summary = run_study(output, map_seeds=(0,), worlds=[world],
                                policies=("reference", "no_probe", "public_reference"))
            self.assertEqual(summary["episodes"], 3)
            self.assertTrue(summary["source_unchanged"])
            config = json.loads((output / "config.json").read_text())
            self.assertFalse(config["full_discrete_enumeration"])
            self.assertEqual(config["physics_seeds"], {"0": 100})
            for name, digest in json.loads((output / "sha256.json").read_text()).items():
                self.assertEqual(hashlib.sha256((output / name).read_bytes()).hexdigest(), digest)
            with gzip.open(output / "episodes.jsonl.gz", "rt") as stream:
                records = [json.loads(line) for line in stream]
            self.assertEqual(len(records), 3)
            for record in records:
                row = record["episode"]
                self.assertEqual(row["physics_seed"], 100)
                self.assertEqual(row["qualities"], world["qualities"])
                self.assertEqual(row["signals"], world["signals"])
                self.assertEqual(row["weight"], world["weight"])
                visibility = "public" if row["policy"] == "public_reference" else "hidden"
                replayed = ExpeditionEnvironment(seed=100, mission_seed=0, visibility=visibility,
                                                 quality_fixture=world["qualities"],
                                                 signal_fixture=world["signals"])
                for call in record["transcript"]:
                    self.assertIn(call["tool"], ("rules", "map", "telemetry_log", "uplink", "advance"))
                    self.assertEqual(getattr(replayed, call["tool"])(**call["arguments"]), call["result"])
                self.assertEqual(replayed.evaluate(), record["result"])
                self.assertEqual(replayed.replay(), record["replay"])
            before = (output / "sha256.json").read_bytes()
            with self.assertRaises(FileExistsError):
                run_study(output, map_seeds=(0,), worlds=[world], policies=("no_probe",))
            self.assertEqual((output / "sha256.json").read_bytes(), before)

    def test_policy_facade_has_no_environment_or_scoring_attribute(self):
        tools = RecordingPublicTools(lambda name, arguments: {"name": name})
        self.assertFalse(hasattr(tools, "_env"))
        self.assertFalse(hasattr(tools, "evaluate"))
        self.assertFalse(hasattr(tools, "replay"))
        self.assertEqual(tools.rules(), {"name": "rules"})
        self.assertEqual(len(tools.transcript), 1)


if __name__ == "__main__":
    unittest.main()
