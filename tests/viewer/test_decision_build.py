"""Evidence and information-boundary checks for the offline decision demo."""

import importlib.util
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "viewer"))
SPEC = importlib.util.find_spec("decision_build")
if SPEC:
    import decision_build
else:
    decision_build = None


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


class DecisionBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = decision_build.build_payload(REPO) if decision_build else None

    def setUp(self):
        self.assertIsNotNone(decision_build, "the decision demo builder is not implemented")

    def test_selected_scores_and_comparison_labels_are_exact(self):
        cases = self.payload["cases"]
        self.assertEqual([c["profile"] for c in cases], ["rush", "rush_noisy", "rush_noisy"])
        self.assertEqual([c["seed"] for c in cases], [501, 502, 504])
        self.assertEqual([c["actual"]["replay"]["result"]["raw_score"] for c in cases], [0, 8.25, 0])
        self.assertEqual([c["alternative"]["replay"]["result"]["raw_score"] for c in cases], [5.25, 10, 6])
        self.assertEqual([c["actual"]["replay"]["result"]["max_available_value"] for c in cases], [12, 13, 10])
        self.assertEqual([c["alternative"]["kind"] for c in cases], ["post_hoc", "reference", "post_hoc"])
        self.assertEqual([c["actual"]["label"] for c in cases], ["Actual model run"] * 3)
        self.assertEqual([c["alternative"]["label"] for c in cases], [
            "Post-hoc: no new commands after call 12",
            "Independent KF + MPC reference",
            "Post-hoc: no new commands after call 20",
        ])
        self.assertEqual([c["decision"]["call"] for c in cases], [13, 10, 21])
        self.assertEqual([c["decision"]["tick"] for c in cases], [20, 12, 25])

    def test_actual_and_independent_reference_replays_are_unchanged(self):
        for case in self.payload["cases"]:
            source = REPO / case["actual"]["source_path"]
            self.assertEqual(case["actual"]["replay"], read_json(source))
            self.assertEqual(case["actual"]["identity"]["model"], "anthropic/claude-opus-5-5")
            self.assertEqual(case["actual"]["identity"]["harness"], "OpenCode 1.19.5")
        reference = self.payload["cases"][1]["alternative"]
        self.assertEqual(reference["replay"], read_json(REPO / reference["source_path"]))
        self.assertNotIn("cutoff_call", reference)

    def test_post_hoc_results_match_the_published_checks(self):
        for case, filename, cutoff in [(self.payload["cases"][0], "salvage-check.json", 12),
                                       (self.payload["cases"][2], "stop-check.json", 20)]:
            directory = REPO / "docs/lightlag-audits/fixed-seeds501-504" / case["run_name"]
            checked = next(x for x in read_json(directory / filename)["counterfactuals"]
                           if x["after_call"] == cutoff)
            alternative = case["alternative"]
            self.assertEqual(alternative["cutoff_call"], cutoff)
            self.assertEqual(alternative["replay"]["result"], checked["result"])
            self.assertAlmostEqual(alternative["replay"]["states"][-1]["battery"], checked["final_battery"])
            self.assertEqual(alternative["replay"]["states"][:case["decision"]["tick"] + 1],
                             case["actual"]["replay"]["states"][:case["decision"]["tick"] + 1])
            self.assertTrue(all(c["sent_tick"] < case["decision"]["tick"]
                                for c in alternative["replay"]["commands"]))

    def test_branch_replays_only_the_requested_public_call_prefix(self):
        case = self.payload["cases"][2]
        transcript_path = REPO / "docs/lightlag-runs" / case["run_name"] / "artifacts/evaluator/transcript.jsonl"
        transcript = [json.loads(line) for line in transcript_path.read_text().splitlines()]
        before = json.dumps(case["actual"]["replay"], sort_keys=True)
        branch = decision_build.make_branch(case["actual"]["replay"], transcript, 21)
        self.assertEqual(branch["result"]["raw_score"], 0)
        self.assertFalse(branch["result"]["alive"])
        self.assertEqual(json.dumps(case["actual"]["replay"], sort_keys=True), before)
        with self.assertRaises(ValueError):
            decision_build.make_branch(case["actual"]["replay"], transcript, 999)

    def test_no_packet_is_visible_before_its_recorded_arrival(self):
        replay = {"received_telemetry": [
            {"tick": 0, "received_tick": 0, "position": [0, 0]},
            {"tick": 1, "received_tick": 4, "position": [1.3, 0.2]},
            {"tick": 2, "received_tick": 8, "position": [1.8, -0.1]},
        ], "states": [{"tick": 3, "position": [99, 99]}]}
        self.assertIsNone(decision_build.latest_visible_packet(replay, -1))
        self.assertEqual(decision_build.latest_visible_packet(replay, 3)["tick"], 0)
        self.assertEqual(decision_build.latest_visible_packet(replay, 4)["position"], [1.3, 0.2])
        self.assertEqual(decision_build.latest_visible_packet(replay, 7)["tick"], 1)
        self.assertEqual(decision_build.latest_visible_packet(replay, 8)["tick"], 2)
        self.assertIsNone(decision_build.latest_visible_packet({"states": replay["states"]}, 8))

    def test_page_observation_indices_use_delivered_packets_and_keep_noise(self):
        for case in self.payload["cases"]:
            for name in ["actual", "alternative"]:
                track = case[name]
                replay = track["replay"]
                self.assertEqual(len(track["observation_indices"]), 51)
                for tick, index in enumerate(track["observation_indices"]):
                    packet = replay["received_telemetry"][index]
                    self.assertLessEqual(packet["received_tick"], tick)
                    self.assertEqual(packet, decision_build.latest_visible_packet(replay, tick))
                if case["profile"] == "rush_noisy":
                    packet = replay["received_telemetry"][track["observation_indices"][4]]
                    self.assertNotEqual(packet["position"], replay["states"][packet["tick"]]["position"])

    def test_full_horizon_energy_and_death_markers_use_evaluator_states(self):
        self.assertEqual([c["actual"]["death_tick"] for c in self.payload["cases"]], [49, None, 47])
        for case in self.payload["cases"]:
            for name in ["actual", "alternative"]:
                replay = case[name]["replay"]
                self.assertEqual([s["tick"] for s in replay["states"]], list(range(51)))
                self.assertEqual(replay["config"]["idle_cost"] * replay["config"]["max_ticks"], 25)

    def test_payload_roundtrips_and_cannot_close_its_script_element(self):
        template = (REPO / "viewer/decision_template.html").read_text()
        payload = {"cases": [], "hostile_example": "</script><script>alert('x')</script>",
                   "tokenizer_example": "<!--<script>"}
        page = decision_build.render_page(payload, template)
        match = re.search(r'<script id="decision-data" type="application/json">(.*?)</script>', page, re.S)
        self.assertIsNotNone(match)
        self.assertNotIn("</script>", match.group(1))
        self.assertNotIn("<", match.group(1))
        self.assertEqual(json.loads(match.group(1)), payload)
        with self.assertRaises(ValueError):
            decision_build.render_page(payload, "missing marker")

    def test_cli_builds_an_offline_page_with_complete_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "decisions.html"
            self.assertEqual(decision_build.main(["--out", str(out)]), 0)
            page = out.read_text()
        match = re.search(r'<script id="decision-data" type="application/json">(.*?)</script>', page, re.S)
        self.assertEqual(json.loads(match.group(1)), self.payload)
        self.assertNotRegex(page, r'<(?:script|link|img)\b[^>]*(?:src|href)=["\']https?://')
        self.assertNotIn("fetch(", page)
        self.assertIn("../docs/lightlag-fixed-seed-comparison.md", page)
        self.assertIn("3 wins", page)
        self.assertIn("2 ties", page)
        self.assertIn("3 deficits", page)


if __name__ == "__main__":
    unittest.main()
