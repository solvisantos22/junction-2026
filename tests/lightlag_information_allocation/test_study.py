"""Complete evidence retention and mechanism gate tests."""

import json
from pathlib import Path
import tempfile
import unittest

from lightlag_information_allocation.study import run_study


class StudyTests(unittest.TestCase):
    def test_study_retains_full_matrix_and_reports_distinct_controls(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "study"
            summary = run_study(output)
            protocol = json.loads((output / "protocol.json").read_text())
            exact = [json.loads(line) for line in (output / "exact_rows.jsonl").read_text().splitlines()]
            seeded = [json.loads(line) for line in (output / "seeded_rows.jsonl").read_text().splitlines()]
            replays = [json.loads(line) for line in (output / "replays.jsonl").read_text().splitlines()]
            self.assertEqual(len(exact), 864)
            self.assertEqual(len(seeded), 1080)
            self.assertEqual(len(replays), 1944)
            self.assertEqual(protocol["seeded_smoke"]["seeds"], list(range(20)))
            self.assertEqual(set(row["seed"] for row in seeded), set(range(20)))
            self.assertTrue(protocol["source_hashes"])
            self.assertFalse(any("superpowers" in path for path in protocol["source_hashes"]))
            self.assertEqual(summary, json.loads((output / "summary.json").read_text()))
            self.assertTrue(summary["gate"]["passed"])
            expected = {"selective": .6743, "never_probe": .63, "probe_a": .63245,
                        "probe_b": .63245, "blind_selected_probe": .60125,
                        "most_uncertain": .6410166666666667, "least_useful_probe": .61435,
                        "entropy_matched_gate": .6647666666666667,
                        "least_useful_matched_gate": .6381}
            for policy, value in expected.items():
                self.assertAlmostEqual(summary["exact"]["aggregate"][policy], value)
            self.assertEqual(summary["exact"]["selective_choices"],
                             {"case_1": "a", "case_2": "b", "case_3": "a", "case_4": "b",
                              "case_5": None, "case_6": None})
            rows = {row["episode_id"]: row for row in exact + seeded}
            self.assertEqual(len(rows), 1944)
            for record in replays:
                self.assertEqual(record["replay"]["evaluation"]["reward"],
                                 rows[record["episode_id"]]["reward"])

    def test_existing_output_is_refused_without_modification(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            marker = output / "keep.txt"
            marker.write_text("original")
            with self.assertRaises(FileExistsError):
                run_study(output)
            self.assertEqual(list(output.iterdir()), [marker])
            self.assertEqual(marker.read_text(), "original")


if __name__ == "__main__":
    unittest.main()
