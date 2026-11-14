"""The 3D Mars demo's data and build step. Standard library only.

    python3 -m unittest discover -s tests/viewer -v

The page's looks are checked by opening it in a browser. These tests cover what it
is fed: that every call shown was really made, and that the committed standalone
page matches its sources.
"""

import base64
import json
import re
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "viewer"))
import build_mars  # noqa: E402

DATA = build_mars.gather()
RUNS = {run["id"]: run for run in DATA["runs"]}


def reward(run):
    result = run["replay"]["result"]
    return result["raw_score"] / result["max_available_value"]


class ModelRun(unittest.TestCase):
    def setUp(self):
        self.run_dir = build_mars.MODEL_RUN
        self.model = RUNS["claude"]

    def test_every_simulator_call_in_the_saved_transcript_is_shown_in_order(self):
        transcript = [
            json.loads(line)
            for line in (self.run_dir / "artifacts" / "evaluator" / "transcript.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        shown = [c for c in self.model["calls"] if c["kind"] == "mcp"]
        self.assertEqual(len(shown), len(transcript))
        for call, record in zip(shown, transcript):
            self.assertEqual((call["tool"], call["arguments"], call["tick"], call["tick_after"], call["ok"]),
                             (record["tool"], record["arguments"], record["tick_before"], record["tick_after"], record["ok"]))

    def test_only_the_five_public_tools_and_the_agents_own_shell_appear(self):
        tools = {c["tool"] for c in self.model["calls"] if c["kind"] == "mcp"}
        self.assertLessEqual(tools, {"rules", "map", "telemetry_log", "uplink", "advance"})
        self.assertEqual({c["tool"] for c in self.model["calls"] if c["kind"] == "shell"}, {"bash"})

    def test_the_rejected_command_is_kept_with_its_reason(self):
        rejected = [c for c in self.model["calls"] if not c["ok"]]
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0]["tool"], "uplink")
        self.assertIn("metres must be in", rejected[0]["error"])

    def test_calls_never_go_back_in_time(self):
        ticks = [c["tick"] for c in self.model["calls"]]
        self.assertEqual(ticks, sorted(ticks))
        self.assertEqual(self.model["calls"][-1]["tick_after"], self.model["replay"]["config"]["max_ticks"])

    def test_the_final_report_and_score_are_the_models_own(self):
        self.assertIn("The episode has ended", self.model["report"])
        saved = json.loads((self.run_dir / "verifier" / "reward.txt").read_text(encoding="utf-8"))
        self.assertEqual(reward(self.model), saved)
        self.assertEqual(self.model["label"], "Claude Opus 5.5")


class ScriptedRuns(unittest.TestCase):
    def test_all_runs_share_the_models_seed_and_delay(self):
        for run in DATA["runs"]:
            self.assertEqual(run["replay"]["seed"], DATA["seed"], run["id"])
            self.assertEqual(run["replay"]["config"]["delay_ticks"], DATA["delay"], run["id"])
            self.assertEqual(run["replay"]["world"], RUNS["claude"]["replay"]["world"], run["id"])

    def test_scripted_scores_match_the_harbor_task(self):
        self.assertEqual(reward(RUNS["reference"]), 1.0)
        self.assertEqual(reward(RUNS["stale_telemetry"]), 0.0)
        self.assertEqual(reward(RUNS["move_and_wait"]), 0.75)

    def test_the_reference_matches_its_saved_harbor_run(self):
        saved = json.loads((build_mars.RUNS / "reference-seed7-delay3" / "artifacts" / "evaluator" / "replay.json").read_text(encoding="utf-8"))
        self.assertEqual(RUNS["reference"]["replay"]["states"], saved["states"])

    def test_scripted_runs_carry_their_calls_and_beliefs(self):
        for name in ("reference", "stale_telemetry", "move_and_wait"):
            run = RUNS[name]
            self.assertTrue(all(c["kind"] == "mcp" for c in run["calls"]), name)
            self.assertGreater(len(run["belief"]), 3, name)
        last = len(RUNS["reference"]["replay"]["states"]) - 1
        self.assertTrue(all(0 <= note["tick"] <= last for note in RUNS["reference"]["belief"]))


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

    def test_the_committed_page_is_up_to_date(self):
        """Everything but the data must match byte for byte; the data to nine decimals.

        The reference controller's command values differ in the last float digit
        between Python versions (math.hypot changed in 3.10), so the data cannot be
        compared as text. The rover states it produces are identical either way.
        """
        pattern = re.compile(r'(<script id="src-data" type="application/octet-stream">)([^<]+)(</script>)')
        committed = (REPO / "viewer" / "mars-demo.html").read_text(encoding="utf-8")

        def split(page):
            match = pattern.search(page)
            return page[:match.start(2)] + page[match.end(2):], json.loads(base64.b64decode(match.group(2)))

        def rounded(value):
            if isinstance(value, float):
                return round(value, 9)
            if isinstance(value, list):
                return [rounded(item) for item in value]
            if isinstance(value, dict):
                return {key: rounded(item) for key, item in value.items()}
            return value

        committed_shell, committed_data = split(committed)
        rebuilt_shell, rebuilt_data = split(self.page)
        self.assertEqual(committed_shell, rebuilt_shell, "run: python3 viewer/build_mars.py")
        self.assertEqual(rounded(committed_data), rounded(rebuilt_data), "run: python3 viewer/build_mars.py")


if __name__ == "__main__":
    unittest.main()
