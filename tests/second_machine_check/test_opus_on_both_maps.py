"""The both-maps table reads its saved rows and pairs every player on the same worlds.

    python3 -m unittest discover -s tests/second_machine_check -v

Standard library only; under a second. Reads the saved rows, plays nothing.
"""

import contextlib
import io
import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools" / "second_machine_check"))

import opus_on_both_maps as both  # noqa: E402


@unittest.skipUnless(both.ROWS.exists(), "the saved rows are not here")
class BothMapsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with contextlib.redirect_stdout(io.StringIO()) as printed:
            cls.table = both.table(both.ROWS)
        cls.printed = printed.getvalue()

    def test_every_player_is_paired_on_the_same_thirty_worlds(self):
        self.assertEqual(self.table["worlds"], list(range(600, 630)))
        rows = [json.loads(line) for line in both.ROWS.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(rows), 150)
        self.assertEqual({(r["program"], r["map"]) for r in rows},
                         {(name, "normal") for name in both.PROGRAMS} | {("M-opus-1", "max")})
        self.assertTrue(all(r["status"] == "returned" and not r["errors"] for r in rows))

    def test_the_reference_leads_on_the_normal_map_and_the_max_map_is_level(self):
        players = self.table["players"]
        reference = players[both.REFERENCE]
        self.assertAlmostEqual(reference["normal"]["score"], 0.500, places=3)
        self.assertAlmostEqual(reference["max"]["score"], 0.306, places=3)
        for label in both.LABELS.values():
            self.assertLess(players[label]["normal"]["score"], reference["normal"]["score"])
            self.assertGreater(players[label]["normal"]["score"], players[both.OLDER]["normal"]["score"])
            self.assertLessEqual(players[label]["vs_reference_normal"]["worlds_higher"], 2)
        self.assertGreaterEqual(players[both.LABELS["K-opus-1"]]["vs_manh_max_max"]["worlds_higher"], 15)

    def test_the_judged_worlds_file_holds_the_campaign_scores(self):
        saved = json.loads((both.ROWS.parent / "opus-judged-worlds.json").read_text(encoding="utf-8"))
        mine = [r for r in saved["rows"] if r["program"] == "M-opus-1" and r["map"] == "normal" and r["seed"] != 2026]
        campaign = sum(r["raw_score"] for r in mine) / sum(r["max_value"] for r in mine)
        self.assertAlmostEqual(campaign, 169.75 / 358.0, places=9)
        self.assertLess(campaign, saved["reference"]["normal"]["campaign_2027_2029"])
        repeats = [r for r in saved["repeats_of_M-opus-1_on_the_normal_map"] if r["seed"] != 2026]
        self.assertEqual(sorted(r["raw_score"] for r in repeats), sorted([r["raw_score"] for r in mine] * 2))


if __name__ == "__main__":
    unittest.main()
