"""Story mode's moments, checked on the committed campaign runs. Standard library only.

    python3 -m unittest discover -s tests/viewer -p "test_traverse_story.py" -v

The moments are computed from the evaluator's replays (viewer/traverse_story.py). These tests hold
them to facts that can be read off the replays directly, and to the point-of-no-return ticks Kristján's
other session found independently with tools/traverse_farm/analysis.py on the same runs.
"""

import json
import math
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "viewer"))
import build_traverse  # noqa: E402
import traverse_story  # noqa: E402

FOLDERS = [folder for folder in build_traverse.run_folders(build_traverse.RUNS, "campaign-")
           if json.loads((folder / "run.json").read_text(encoding="utf-8")).get("kind") in build_traverse.KINDS]


def site(number):
    return traverse_story.moments([build_traverse.load_run(folder, number) for folder in FOLDERS])


def find(moments, kind, run):
    return [m for m in moments if m["kind"] == kind and m["run"] == run]


@unittest.skipUnless(any(f.name == "campaign-agent-opus-2" for f in FOLDERS), "no campaign agent runs saved")
class CampaignMoments(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sites = {number: site(number) for number in (1, 2, 3)}

    def test_a_battery_run_flat_with_the_way_home_open_shows_that_way(self):
        lost = find(self.sites[1], "lost", "campaign-agent-opus-2")
        self.assertEqual([m["t"] for m in lost], [409])
        moment = lost[0]
        self.assertTrue(moment["open"])
        self.assertEqual(moment["wait"], 7)
        replay = build_traverse.load_run(build_traverse.RUNS / "campaign-agent-opus-2", 1)["replay"]
        self.assertEqual(moment["path"][-1], [round(v, 1) for v in replay["world"]["base"]])
        x, y = replay["states"][408]["position"]
        self.assertLess(math.hypot(moment["path"][0][0] - x, moment["path"][0][1] - y), 0.2)
        self.assertIn("13 m from the lander", moment["did"])
        self.assertEqual(moment["better_title"], "What would have saved it")

    def test_the_point_of_no_return_matches_the_farms_independent_check(self):
        # tools/traverse_farm/analysis.py on the same replays: 314 for Opus agent 2 at site 3, 397 for Sonnet agent 1
        self.assertEqual([m["t"] for m in find(self.sites[3], "no_return", "campaign-agent-opus-2")], [314])
        self.assertEqual([m["t"] for m in find(self.sites[3], "lost", "campaign-agent-opus-2")], [351])
        self.assertEqual([m["t"] for m in find(self.sites[3], "no_return", "campaign-agent-sonnet-1")], [397])
        self.assertEqual([m["t"] for m in find(self.sites[3], "away", "campaign-agent-sonnet-1")], [420])
        self.assertFalse(find(self.sites[3], "no_return", "campaign-agent-opus-2")[0]["open"])

    def test_every_moment_is_inside_the_mission_and_names_a_run_of_the_page(self):
        names = {folder.name for folder in FOLDERS}
        for number, moments in self.sites.items():
            self.assertEqual([m["t"] for m in moments], sorted(m["t"] for m in moments), number)
            for m in moments:
                self.assertIn(m["run"], names)
                self.assertTrue(0 <= m["t"] <= 420)
                self.assertTrue(m["did"])
                self.assertEqual(m["kind"].startswith("ref_"), m["run"] == "campaign-reference", m)

    def test_runs_that_came_home_safely_have_no_loss_moments(self):
        for moments in self.sites.values():
            for kind in ("lost", "no_return", "away"):
                self.assertFalse(find(moments, kind, "campaign-reference"))
                self.assertFalse(find(moments, kind, "campaign-agent-sonnet-2"))      # home at all three sites
        self.assertTrue(find(self.sites[1], "ref_wait", "campaign-reference"))
        self.assertTrue(find(self.sites[1], "ref_home", "campaign-reference"))

    def test_a_close_call_is_the_runs_lowest_battery(self):
        close = find(self.sites[1], "close", "campaign-agent-opus-1")
        self.assertEqual(len(close), 1)
        replay = build_traverse.load_run(build_traverse.RUNS / "campaign-agent-opus-1", 1)["replay"]
        lowest = min(replay["states"], key=lambda s: s["battery"])
        self.assertEqual(close[0]["t"], lowest["tick"])
        self.assertLess(lowest["battery"], traverse_story.CLOSE_SHARE * replay["config"]["battery_capacity"])


class PagesCarryMoments(unittest.TestCase):
    def test_the_built_pages_carry_the_moments_and_the_app_knows_every_kind(self):
        app = (build_traverse.TRAVERSE / "app.js").read_text(encoding="utf-8")
        for kind in traverse_story.BETTER:
            self.assertIn(kind + ":", app.split("const KIND = ")[1].split("};")[0], kind)
        if FOLDERS:
            for page in build_traverse.campaign(build_traverse.RUNS):
                self.assertTrue(page["moments"])


if __name__ == "__main__":
    unittest.main()
