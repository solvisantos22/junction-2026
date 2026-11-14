"""The 3D Mars demo's data and build step. Standard library only.

    python3 -m unittest discover -s tests/viewer -v

The page's looks are checked by opening it in a browser. These tests cover what it
is fed: that every call shown was really made in a saved trial, that the runs put
side by side are the same mission, and that the committed standalone page matches
its sources.
"""

import base64
import json
import re
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "viewer"))
import build_mars  # noqa: E402

DATA = build_mars.gather()
MISSIONS = {mission["id"]: mission for mission in DATA["missions"]}
ALL_RUNS = [(mission, run) for mission in DATA["missions"] for run in mission["runs"]]
PUBLIC_TOOLS = {"rules", "map", "telemetry_log", "uplink", "advance"}


def run_of(mission_id, run_id):
    return next(run for run in MISSIONS[mission_id]["runs"] if run["id"] == run_id)


def events(run, kind):
    return [(state["tick"], event) for state in run["replay"]["states"] for event in state["events"] if event["type"] == kind]


class EveryRun(unittest.TestCase):
    def test_every_simulator_call_in_the_saved_transcript_is_shown_in_order(self):
        for _, run in ALL_RUNS:
            text = (build_mars.RUNS / run["source"] / "artifacts" / "evaluator" / "transcript.jsonl").read_text(encoding="utf-8")
            transcript = [json.loads(line) for line in text.splitlines() if line.strip()]
            shown = [call for call in run["calls"] if call["kind"] == "mcp"]
            self.assertEqual(len(shown), len(transcript), run["source"])
            for call, record in zip(shown, transcript):
                self.assertEqual((call["tool"], call["arguments"], call["tick"], call["tick_after"], call["ok"]),
                                 (record["tool"], record["arguments"], record["tick_before"], record["tick_after"], record["ok"]), run["source"])

    def test_only_the_five_public_tools_reach_the_simulator(self):
        for _, run in ALL_RUNS:
            self.assertLessEqual({call["tool"] for call in run["calls"] if call["kind"] == "mcp"}, PUBLIC_TOOLS, run["source"])
            if run["kind"] == "reference":
                self.assertTrue(all(call["kind"] == "mcp" for call in run["calls"]), run["source"])

    def test_calls_never_go_back_in_time(self):
        for mission, run in ALL_RUNS:
            ticks = [call["tick"] for call in run["calls"]]
            self.assertEqual(ticks, sorted(ticks), run["source"])
            self.assertLessEqual(run["calls"][-1]["tick_after"], mission["ticks"], run["source"])

    def test_the_score_shown_is_the_saved_verifier_reward(self):
        for _, run in ALL_RUNS:
            saved = float((build_mars.RUNS / run["source"] / "verifier" / "reward.txt").read_text(encoding="utf-8"))
            result = run["replay"]["result"]
            self.assertEqual(run["reward"], saved, run["source"])
            self.assertAlmostEqual(saved, result["raw_score"] / result["max_available_value"], places=5, msg=run["source"])

    def test_model_runs_carry_the_models_own_closing_words(self):
        for _, run in ALL_RUNS:
            if run["kind"] == "model":
                self.assertEqual(run["label"], "Claude Opus 5.5")
                self.assertGreater(len(run["report"]), 80, run["source"])
            else:
                self.assertEqual(run["report"], "")


class Missions(unittest.TestCase):
    def test_runs_side_by_side_are_the_same_mission(self):
        for mission in DATA["missions"]:
            first = build_mars.mission_definition(mission["runs"][0]["replay"])
            for run in mission["runs"]:
                self.assertEqual(build_mars.mission_definition(run["replay"]), first, run["source"])
            self.assertEqual(first["config"]["delay_ticks"], mission["delay"])

    def test_each_mission_is_three_model_attempts_in_order_and_the_reference(self):
        for mission in DATA["missions"]:
            self.assertEqual([run["id"] for run in mission["runs"]], ["claude-1", "claude-2", "claude-3", "reference"])
            self.assertEqual([run["kind"] for run in mission["runs"]], ["model", "model", "model", "reference"])
            for attempt, run in enumerate(mission["runs"][:3], start=1):
                self.assertIn("-r{}-".format(attempt), run["source"])
            self.assertIn(mission["featured"], [run["id"] for run in mission["runs"]])

    def test_the_reference_gets_home_alive_in_both_missions(self):
        for mission in DATA["missions"]:
            result = mission["runs"][-1]["replay"]["result"]
            self.assertTrue(result["alive"] and result["at_base"], mission["id"])
            self.assertGreater(mission["runs"][-1]["reward"], 0.7, mission["id"])

    def test_deadlines_opens_on_the_run_that_took_every_sample_and_died_short_of_base(self):
        run = run_of("deadlines", MISSIONS["deadlines"]["featured"])
        result = run["replay"]["result"]
        self.assertEqual((result["alive"], result["at_base"], run["reward"]), (False, False, 0.0))
        self.assertEqual(len(result["sampled_targets"]), len(run["replay"]["world"]["targets"]))
        self.assertEqual(len(events(run, "battery_depleted")), 1)
        self.assertIn("ran out of energy", run["report"])
        self.assertEqual(sorted({call["tool"] for call in run["calls"] if call["kind"] != "mcp"}), ["bash", "invalid"])

    def test_sand_opens_on_a_run_that_slips_on_sand_and_misses_samples(self):
        run = run_of("sand", MISSIONS["sand"]["featured"])
        states = run["replay"]["states"]
        self.assertGreaterEqual(len(events(run, "sample_failed")), 2)
        self.assertGreater(sum(1 for state in states if state["terrain"] == "sand"), 5)
        self.assertLess(run["reward"], MISSIONS["sand"]["runs"][-1]["reward"])
        # a commanded drive on sand that came up at least a fifth short
        executed = {command["execute_tick"]: command["command"] for command in run["replay"]["commands"]}
        short = []
        for before, after in zip(states, states[1:]):
            command = executed.get(after["tick"])
            if command and command["action"] == "drive" and command["metres"] > 1 and after["terrain"] == "sand":
                moved = ((after["position"][0] - before["position"][0]) ** 2 + (after["position"][1] - before["position"][1]) ** 2) ** 0.5
                short.append(1 - moved / command["metres"])
        self.assertGreater(max(short), 0.2)

    def test_the_other_attempts_are_kept_including_the_ones_that_did_well(self):
        self.assertEqual([run["reward"] for run in MISSIONS["deadlines"]["runs"][:3]], [0.0, 0.833333, 0.0])
        sand = [run["reward"] for run in MISSIONS["sand"]["runs"]]
        self.assertGreater(sand[2], sand[3])     # the third attempt beat the reference, and is shown


class StandalonePage(unittest.TestCase):
    def setUp(self):
        self.page = build_mars.standalone(DATA)

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
        for element, path in (("src-app", "app.js"), ("src-three", "vendor/three.module.js"), ("src-core", "vendor/three.core.js")):
            match = re.search(r'<script id="{}" type="application/octet-stream">([^<]+)</script>'.format(element), self.page)
            self.assertEqual(base64.b64decode(match.group(1)), (build_mars.MARS / path).read_bytes(), path)

    def test_the_committed_page_and_data_are_up_to_date(self):
        self.assertEqual((REPO / "viewer" / "mars-demo.html").read_text(encoding="utf-8"), self.page, "run: python3 viewer/build_mars.py")
        self.assertEqual(json.loads((build_mars.MARS / "data.json").read_text(encoding="utf-8")), json.loads(json.dumps(DATA)), "run: python3 viewer/build_mars.py")


if __name__ == "__main__":
    unittest.main()
