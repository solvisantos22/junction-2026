"""The decision auditor on scripted episodes with known mistakes, and on the saved Harbor runs.

Scripted episodes go through lightlag_mcp's EpisodeService, so their transcript, replay and
result files have exactly the shape a Harbor run leaves behind.
"""

import json
from pathlib import Path
import shutil
import tempfile
import unittest

from lightlag_audit.__main__ import main
from lightlag_audit.report import audit_run, to_markdown
from lightlag_audit.runs import load_run
from lightlag_mcp.service import EpisodeService

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "docs" / "lightlag-runs"

WEST = [{"action": "drive", "heading_deg": 180, "metres": 5},
        {"action": "drive", "heading_deg": 180, "metres": 1},
        {"action": "sample"}]
# North target (20, 28) aimed from base (20, 20): right only if the rover were still at base.
NORTH_FROM_BASE = [{"action": "drive", "heading_deg": 90, "metres": 5},
                   {"action": "drive", "heading_deg": 90, "metres": 3},
                   {"action": "sample"}]


def advance_to_end(ticks=80, start=0):
    calls, tick = [], start
    while tick < ticks:
        calls.append(("advance", {"ticks": min(5, ticks - tick)}))
        tick += min(5, ticks - tick)
    return calls


class Scripted(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp(prefix="lightlag-audit-"))

    def tearDown(self):
        shutil.rmtree(self.folder, ignore_errors=True)

    def play(self, calls, seed=7):
        service = EpisodeService(seed=seed, artifact_dir=str(self.folder / "artifacts" / "evaluator"))
        for tool, arguments in calls:
            try:
                service.call(tool, arguments)
            except ValueError:
                pass  # a rejected call, recorded in the transcript
        service.finish()
        return audit_run(load_run(self.folder))

    @staticmethod
    def tags(audit, n=None):
        decisions = audit["decisions"] if n is None else [d for d in audit["decisions"] if d["n"] == n]
        return {f["tag"] for d in decisions for f in d["findings"]}

    def check_accounting(self, audit):
        self.assertTrue(audit["replay_matches"])
        self.assertTrue(audit["decomposition"]["adds_up"])
        self.assertEqual(audit["infrastructure"], [])
        self.assertIn("# Decision audit", to_markdown(audit))

    def test_reference_controller_makes_no_costly_decision(self):
        from lightlag_controllers import REFERENCE, make
        from lightlag_controllers.runner import drive
        service = EpisodeService(seed=7, artifact_dir=str(self.folder / "artifacts" / "evaluator"))
        drive(service, make(REFERENCE))
        service.finish()
        audit = audit_run(load_run(self.folder))
        self.check_accounting(audit)
        self.assertEqual(audit["main_mistakes"], [])
        self.assertIn("PERFECT", {f["tag"] for f in audit["outcome"]})

    def test_stale_aim_is_named_with_the_packet_and_the_commands_in_transit(self):
        audit = self.play([("uplink", {"commands": WEST}), ("advance", {"ticks": 2}),
                           ("uplink", {"commands": NORTH_FROM_BASE})] + advance_to_end(start=2))
        self.check_accounting(audit)
        self.assertIn("STALE_AIM", self.tags(audit, 3))
        missed = [f for d in audit["decisions"] for f in d["findings"] if f["tag"] == "SAMPLE_MISSED"]
        self.assertEqual([f["evidence"]["cause"] for f in missed], ["stale_aim"])
        stale = next(f for f in audit["decisions"][2]["findings"] if f["tag"] == "STALE_AIM")
        self.assertEqual(stale["evidence"]["aimed_at"], "north")
        self.assertEqual(stale["evidence"]["packet"]["state_tick"], 0)  # only the briefing had arrived
        self.assertEqual(len(stale["evidence"]["in_transit"]), 3)

    def test_chained_plan_that_accounts_for_transit_is_not_stale(self):
        north_from_west = [{"action": "drive", "heading_deg": 53.13, "metres": 5},
                           {"action": "drive", "heading_deg": 53.13, "metres": 5}, {"action": "sample"}]
        audit = self.play([("uplink", {"commands": WEST}), ("advance", {"ticks": 2}),
                           ("uplink", {"commands": north_from_west})] + advance_to_end(start=2))
        self.check_accounting(audit)
        self.assertNotIn("STALE_AIM", self.tags(audit))

    def test_repeating_an_uplink_in_transit(self):
        audit = self.play([("uplink", {"commands": WEST}), ("advance", {"ticks": 1}),
                           ("uplink", {"commands": WEST})] + advance_to_end(start=1))
        self.check_accounting(audit)
        self.assertIn("REPEATED_IN_TRANSIT", self.tags(audit, 3))

    def test_rejected_call_costs_nothing_and_points_to_the_rule(self):
        audit = self.play([("uplink", {"commands": [{"action": "wait"}] * 6})] + advance_to_end())
        self.check_accounting(audit)
        rejected = audit["decisions"][0]
        self.assertFalse(rejected["ok"])
        self.assertEqual(rejected["points_lost"], 0)
        finding = rejected["findings"][0]
        self.assertEqual((finding["tag"], finding["kind"]), ("REJECTED_BY_RULES", "reasoning"))
        self.assertEqual(finding["evidence"]["rule"], "max_commands_per_uplink")

    def test_safety_stop_names_the_hazard(self):
        audit = self.play([("uplink", {"commands": [{"action": "drive", "heading_deg": 90, "metres": 5}] * 3})]
                          + advance_to_end())
        self.check_accounting(audit)
        stop = next(f for f in audit["decisions"][0]["findings"] if f["tag"] == "SAFETY_STOP")
        self.assertEqual(stop["evidence"]["reason"], "hazard")
        self.assertEqual(stop["evidence"]["hazard"], {"x1": 18, "y1": 30, "x2": 22, "y2": 32})

    def test_waiting_out_the_clock_loses_everything_through_idle_advances(self):
        audit = self.play(advance_to_end())
        self.check_accounting(audit)
        self.assertEqual(audit["score"]["agent_raw"], 0)
        self.assertGreater(audit["score"]["reference_raw"], 0)
        self.assertEqual(audit["decomposition"]["stop_loss_raw"], 0)
        self.assertEqual(self.tags(audit), {"WAITED_WITH_EMPTY_QUEUE"})
        self.assertAlmostEqual(sum(d["points_lost"] for d in audit["decisions"]), audit["score"]["gap_raw"])

    def test_stopping_without_a_call_is_stopped_early_not_infrastructure(self):
        audit = self.play([])
        self.check_accounting(audit)
        self.assertEqual(audit["decisions"], [])
        tags = {f["tag"]: f["kind"] for f in audit["outcome"]}
        self.assertEqual(tags.get("STOPPED_EARLY"), "reasoning")
        self.assertIn("NOTHING_SAMPLED", tags)
        self.assertEqual(audit["main_mistakes"][0]["points_lost"], audit["score"]["gap_raw"])


@unittest.skipUnless((RUNS / "opencode-opus-5-5-seed7-delay3").exists(), "saved Harbor runs not present")
class SavedRuns(unittest.TestCase):
    NAMES = ("opencode-opus-5-5-seed7-delay3", "reference-seed7-delay3", "do-nothing-seed7-delay3",
             "rush-seed500-delay3-open-loop")

    @classmethod
    def setUpClass(cls):
        cls.audits = {name: audit_run(load_run(RUNS / name)) for name in cls.NAMES}

    def test_every_saved_run_rebuilds_and_its_losses_add_up_to_the_gap(self):
        for name, audit in self.audits.items():
            with self.subTest(run=name):
                self.assertTrue(audit["replay_matches"])
                self.assertTrue(audit["decomposition"]["adds_up"])
                self.assertEqual(audit["infrastructure"], [])

    def test_model_run_quotes_the_agent_or_says_nothing_was_recorded(self):
        audit = self.audits["opencode-opus-5-5-seed7-delay3"]
        self.assertIn("opus", (audit["model"] or "").lower())
        self.assertTrue(all(d["agent_step"] is not None for d in audit["decisions"]))
        quoted = {d["n"] for d in audit["decisions"] if d["agent_words"]}
        self.assertEqual(quoted, set(range(20, 27)))  # the only steps with a message in this trajectory
        self.assertIsNone(next(d for d in audit["decisions"] if d["n"] == 3)["agent_words"])
        # Matched the reference overall: no main mistakes and no generic "worse than reference" tags.
        self.assertEqual(audit["main_mistakes"], [])
        self.assertNotIn("PLAN_WORSE_THAN_REFERENCE", {f["tag"] for d in audit["decisions"] for f in d["findings"]})
        self.assertIn("REJECTED_BY_RULES", {f["tag"] for d in audit["decisions"] for f in d["findings"]})

    def test_open_loop_rush_mistakes(self):
        audit = self.audits["rush-seed500-delay3-open-loop"]
        top = audit["main_mistakes"][0]
        self.assertEqual((top["n"], top["points_lost"]), (10, 1.5))
        self.assertEqual({f["tag"] for f in top["findings"]}, {"WAITED_WITH_EMPTY_QUEUE", "DISCOVERY_MISSED"})
        discovery = next(f for f in top["findings"] if f["tag"] == "DISCOVERY_MISSED")
        self.assertEqual(discovery["evidence"]["packet"], {"state_tick": 9, "received_tick": 12})
        # The discovered target d1 was unknown at tick 0, so no uplink at tick 0 can be "aimed" at it.
        self.assertNotIn("STALE_AIM", {f["tag"] for d in audit["decisions"] for f in d["findings"]})

    def test_superlog_labels_ride_along(self):
        try:
            import numpy  # noqa: F401  superlog needs it
        except ImportError:
            self.skipTest("numpy not installed")
        open_loop = self.audits["rush-seed500-delay3-open-loop"]["superlog"]
        self.assertTrue(open_loop["available"])
        self.assertEqual(open_loop["labels"], ["DISCOVERY_MISSED", "SKIPPED_WITH_ENERGY"])
        self.assertAlmostEqual(open_loop["share"], self.audits["rush-seed500-delay3-open-loop"]["score"]["agent_reward"])
        core = self.audits["opencode-opus-5-5-seed7-delay3"]["superlog"]
        self.assertIn("PERFECT", core["labels"])
        self.assertIn("superlog labels", to_markdown(self.audits["rush-seed500-delay3-open-loop"]))

    def test_tool_failures_stay_out_of_the_reasoning_findings(self):
        with tempfile.TemporaryDirectory() as scratch:
            copy = Path(scratch) / "broken"
            shutil.copytree(RUNS / "opencode-opus-5-5-seed7-delay3", copy)
            trajectory = json.loads((copy / "agent" / "trajectory.json").read_text())
            first = next(s for s in trajectory["steps"] if s.get("source") == "agent" and s.get("tool_calls"))
            first["tool_calls"].insert(0, {"tool_call_id": "lost", "function_name": "lightlag_advance",
                                           "arguments": {"ticks": 1}})
            (copy / "agent" / "trajectory.json").write_text(json.dumps(trajectory))
            trial = json.loads((copy / "result.json").read_text())
            trial["exception_info"] = {"exception_type": "McpError", "exception_message": "connection reset"}
            (copy / "result.json").write_text(json.dumps(trial))
            (copy / "verifier" / "reward.txt").write_text("0.5\n")
            original = self.audits["opencode-opus-5-5-seed7-delay3"]
            broken = audit_run(load_run(copy))
        self.assertEqual({f["tag"] for f in broken["infrastructure"]},
                         {"INFRA_CALL_NOT_RECORDED", "INFRA_HARBOR_EXCEPTION", "INFRA_REWARD_MISMATCH"})
        self.assertEqual([d["findings"] for d in broken["decisions"]],
                         [d["findings"] for d in original["decisions"]])
        self.assertEqual(broken["counts"]["reasoning"], original["counts"]["reasoning"])

    def test_cli_writes_reports_and_an_index(self):
        with tempfile.TemporaryDirectory() as scratch:
            out = Path(scratch)
            self.assertEqual(main([str(RUNS / "opencode-opus-5-5-seed7-delay3"), "--out", str(out)]), 0)
            self.assertTrue((out / "opencode-opus-5-5-seed7-delay3" / "audit.md").exists())
            audit = json.loads((out / "opencode-opus-5-5-seed7-delay3" / "audit.json").read_text())
            self.assertEqual(audit["reference"], "team")
            self.assertIn("opencode-opus-5-5-seed7-delay3", (out / "README.md").read_text())


if __name__ == "__main__":
    unittest.main()
