"""The ghost demo's data and build step. Standard library only.

    python3 -m unittest discover -s tests/viewer -v

The page's looks are checked by opening it in a browser. These tests cover what it is fed:
that every run shown played the reference's missions, that the scores shown are the saved
ones, and that the committed standalone page matches its sources.
"""

import base64
import json
import re
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "viewer"))
import build_ghosts  # noqa: E402

FOLDERS = sorted(path.parent for path in build_ghosts.RUNS.glob("live-*/run.json"))
DATA = build_ghosts.gather(FOLDERS)
RUNS = {run["id"]: run for run in DATA["runs"]}


class EveryRun(unittest.TestCase):
    def test_the_reference_comes_first_and_claude_runs_follow_best_first(self):
        kinds = [run["kind"] for run in DATA["runs"]]
        self.assertEqual(kinds[0], "reference")
        self.assertNotIn("reference", kinds[1:])
        rewards = [run["reward"] for run in DATA["runs"][1:]]
        self.assertEqual(rewards, sorted(rewards, reverse=True))
        self.assertEqual(DATA["best"], DATA["runs"][1]["id"])

    def test_the_scores_shown_are_the_saved_ones(self):
        for folder in FOLDERS:
            result = json.loads((folder / "artifacts" / "evaluator" / "result.json").read_text(encoding="utf-8"))
            run = RUNS[folder.name]
            self.assertEqual(run["reward"], result["reward"])
            self.assertEqual([m["reward"] for m in run["missions"]], [m["reward"] for m in result["missions"]])
            reward_file = folder / "verifier" / "reward.txt"
            if reward_file.exists():  # a Harbor trial: the verifier's number is the one shown
                self.assertAlmostEqual(float(reward_file.read_text()), run["reward"], places=6)

    def test_every_run_played_all_of_the_reference_missions(self):
        self.assertEqual(len(DATA["missions"]), 6)
        for run in DATA["runs"]:
            self.assertEqual(len(run["missions"]), len(DATA["missions"]), run["id"])
            for mission, track in zip(DATA["missions"], run["missions"]):
                self.assertEqual(len(track["p"]), 2 * (mission["ticks"] + 1), run["id"])
                self.assertEqual(track["p"][:2], mission["base"], run["id"])  # every rover starts at base

    def test_a_different_mission_is_refused(self):
        other = dict(build_ghosts.load_run(FOLDERS[0]))
        other["replays"] = [dict(replay, seed=replay["seed"] + 1) for replay in other["replays"]]
        reference = next(folder for folder in FOLDERS if RUNS[folder.name]["kind"] == "reference")
        first = build_ghosts.mission_definition(build_ghosts.load_run(reference)["replays"][0])
        self.assertNotEqual(build_ghosts.mission_definition(other["replays"][0]), first)

    def test_the_reference_loses_no_rover_and_ends_every_mission_at_base(self):
        reference = DATA["runs"][0]
        self.assertEqual(reference["lost"], 0)
        self.assertTrue(all(m["alive"] and m["home"] for m in reference["missions"]))

    def test_samples_and_losses_are_inside_the_mission(self):
        for run in DATA["runs"]:
            for mission, track in zip(DATA["missions"], run["missions"]):
                ids = {target["id"] for target in mission["targets"]}
                for sample in track["samples"]:
                    self.assertIn(sample["id"], ids)
                    self.assertTrue(0 < sample["t"] <= mission["ticks"])
                dead = [event for event in track["events"] if event["k"] == "dead"]
                self.assertEqual(bool(dead), not track["alive"], run["id"])


class StandalonePage(unittest.TestCase):
    def setUp(self):
        self.page = build_ghosts.standalone(DATA)

    def test_it_is_one_file_with_no_outside_references(self):
        self.assertNotIn("<!--DEV-->", self.page)
        self.assertNotIn('href="style.css"', self.page)
        self.assertNotIn("fetch(", self.page.split("<body>")[0].split('<script id="src-core"')[0])
        for needle in ('src="http', "href=\"http", "cdn."):
            self.assertNotIn(needle, self.page)

    def test_the_embedded_data_is_exactly_the_gathered_runs(self):
        match = re.search(r'<script id="src-data" type="application/octet-stream">([^<]+)</script>', self.page)
        self.assertEqual(json.loads(base64.b64decode(match.group(1))), json.loads(json.dumps(DATA)))

    def test_the_embedded_app_and_library_are_the_files_in_the_repository(self):
        for element, path in (("src-app", build_ghosts.GHOSTS / "app.js"),
                              ("src-three", build_ghosts.VENDOR / "three.module.js"),
                              ("src-core", build_ghosts.VENDOR / "three.core.js")):
            match = re.search(r'<script id="{}" type="application/octet-stream">([^<]+)</script>'.format(element), self.page)
            self.assertEqual(base64.b64decode(match.group(1)), path.read_bytes(), path.name)

    def test_the_committed_page_and_data_are_up_to_date(self):
        hint = "run: python3 viewer/build_ghosts.py"
        self.assertEqual((REPO / "viewer" / "ghosts-demo.html").read_text(encoding="utf-8"), self.page, hint)
        self.assertEqual(json.loads((build_ghosts.GHOSTS / "data.json").read_text(encoding="utf-8")),
                         json.loads(json.dumps(DATA)), hint)


class RushSet(unittest.TestCase):
    """The same page fed the team's saved turn-based attempts on `rush` seed 501."""

    def setUp(self):
        self.path = build_ghosts.GHOSTS / "sets" / "rush-501.json"
        self.data = build_ghosts.gather([], json.loads(self.path.read_text(encoding="utf-8")))

    def test_it_shows_every_original_prompt_attempt_and_the_reference(self):
        runs = self.data["runs"]
        self.assertEqual([run["kind"] for run in runs], ["reference"] + ["claude"] * 6)
        self.assertEqual(len(self.data["missions"]), 1)
        self.assertAlmostEqual(runs[0]["reward"], 10 / 12)
        self.assertEqual(sum(run["lost"] for run in runs[1:]), 4)       # four rovers lost in six attempts
        self.assertEqual(runs[0]["lost"], 0)
        for run in runs:
            reward = float((build_ghosts.RUNS / run["id"] / "verifier" / "reward.txt").read_text())
            self.assertAlmostEqual(run["reward"], reward, places=5)

    def test_the_committed_page_is_up_to_date(self):
        page = build_ghosts.standalone(self.data)
        self.assertEqual((REPO / "viewer" / "ghosts-rush-501.html").read_text(encoding="utf-8"), page,
                         "run: python3 viewer/build_ghosts.py --set viewer/ghosts/sets/rush-501.json")


class RushControlSet(unittest.TestCase):
    """Seed 501 again: the six by-hand attempts beside the same model's own autopilot."""

    def setUp(self):
        self.path = build_ghosts.GHOSTS / "sets" / "rush-501-control.json"
        self.data = build_ghosts.gather([], json.loads(self.path.read_text(encoding="utf-8")))

    def test_the_autopilot_played_the_teams_mission_and_ties_the_reference(self):
        runs = self.data["runs"]
        self.assertEqual([run["kind"] for run in runs], ["reference"] + ["claude"] * 7)
        autopilot = next(run for run in runs if run["label"].endswith("own autopilot"))
        self.assertEqual(self.data["best"], autopilot["id"])            # the run the page opens on
        self.assertAlmostEqual(autopilot["reward"], runs[0]["reward"])  # 10 of 12, like the reference
        self.assertEqual(autopilot["lost"], 0)
        by_hand = [run for run in runs if "by hand" in run["label"]]
        self.assertEqual(len(by_hand), 6)
        self.assertEqual(sum(run["lost"] for run in by_hand), 4)
        # gather() refuses a run whose map, settings or targets differ from the reference's; say so here too
        folder = build_ghosts.RUNS / "explore-standard-noise" / "opus-a" / "rush-501"
        replay = build_ghosts.load_run(folder, {"kind": "claude", "label": ""})["replays"][0]
        reference = build_ghosts.load_run(build_ghosts.RUNS / "rush-seed501-delay3-kf-mpc",
                                          {"kind": "reference", "label": ""})["replays"][0]
        self.assertEqual(build_ghosts.mission_definition(replay), build_ghosts.mission_definition(reference))

    def test_the_committed_page_is_up_to_date(self):
        page = build_ghosts.standalone(self.data)
        self.assertEqual((REPO / "viewer" / "ghosts-rush-501-control.html").read_text(encoding="utf-8"), page,
                         "run: python3 viewer/build_ghosts.py --set viewer/ghosts/sets/rush-501-control.json")


if __name__ == "__main__":
    unittest.main()
