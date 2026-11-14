"""The replay check: a saved run plays again to its saved score, and a changed one is caught.

    python3 -m unittest discover -s tests/second_machine_check -v

Standard library only; a few seconds. Uses two of Kristján's saved runs, read-only.
"""

import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools" / "second_machine_check"))

import verify_replays  # noqa: E402

RUNS = REPO / "docs" / "lightlag-runs"
CAMPAIGN = RUNS / "campaign-stop-early"      # the reference plays site 1 and stops: three missions
SINGLE = RUNS / "traverse-stop-early"        # the reference stopped at tick 105: one mission


@unittest.skipUnless(CAMPAIGN.exists() and SINGLE.exists(), "the saved runs are not here")
class VerifyReplaysTest(unittest.TestCase):
    def test_saved_runs_play_again_to_their_saved_scores(self):
        campaign = verify_replays.check_run(CAMPAIGN)
        self.assertEqual(campaign["problems"], [])
        self.assertEqual(campaign["missions"], 3)
        self.assertAlmostEqual(campaign["reward"], float((CAMPAIGN / "verifier" / "reward.txt").read_text()), places=6)
        single = verify_replays.check_run(SINGLE)
        self.assertEqual(single["problems"], [])
        self.assertAlmostEqual(single["reward"], 0.073276, places=6)

    def test_a_changed_command_is_caught(self):
        replay = json.loads((SINGLE / "artifacts" / "evaluator" / "replay.json").read_text(encoding="utf-8"))
        self.assertEqual(verify_replays.replay_mission(copy.deepcopy(replay))[0], [])
        drive = next(c for c in replay["commands"] if c["command"]["action"] == "drive")
        drive["command"]["heading_deg"] = (drive["command"]["heading_deg"] + 90.0) % 360.0
        problems, _ = verify_replays.replay_mission(replay)
        self.assertTrue(problems)

    def test_a_changed_score_is_caught(self):
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder) / "traverse-stop-early"
            shutil.copytree(SINGLE, run)
            (run / "verifier" / "reward.txt").write_text("0.500000", encoding="utf-8")
            problems = verify_replays.check_run(run)["problems"]
            self.assertEqual(len(problems), 1)
            self.assertIn("verifier", problems[0])
            result = run / "artifacts" / "evaluator" / "result.json"
            saved = json.loads(result.read_text(encoding="utf-8"))
            saved["raw_score"] += 10.0
            result.write_text(json.dumps(saved), encoding="utf-8")
            self.assertGreater(len(verify_replays.check_run(run)["problems"]), 1)

    def test_it_finds_the_traverse_and_campaign_runs(self):
        names = [path.name for path in verify_replays.find_runs()]
        self.assertIn("campaign-reference", names)
        self.assertIn("traverse-reference", names)
        self.assertTrue(all(name.startswith(("traverse-", "campaign-")) for name in names))


if __name__ == "__main__":
    unittest.main()
