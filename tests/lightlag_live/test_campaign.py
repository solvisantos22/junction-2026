"""The campaign service: clock, mission hand-over, grading and what an agent can reach.

Standard library only; a fake clock stands in for wall time, so nothing here sleeps.

    python3 -m unittest discover -s tests/lightlag_live -v
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from lightlag_dynamic.controllers import POLICIES  # noqa: E402
from lightlag_dynamic.tools import run_episode  # noqa: E402
from lightlag_live import CampaignService, ToolError, play_campaign  # noqa: E402

MISSIONS = [{"seed": 8000, "profile": "rush"}, {"seed": 8001, "profile": "rush_noisy"},
            {"seed": 8002, "profile": "rush"}]


class FakeClock:
    """Wall time that only moves when the service sleeps or a test says so."""

    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def service(missions=MISSIONS, **kwargs):
    clock = FakeClock()
    return CampaignService(missions, clock=clock, sleep=clock.sleep, **kwargs), clock


class ClockTest(unittest.TestCase):
    def test_reading_is_free_until_the_first_command(self):
        campaign, clock = service()
        for _ in range(3):
            campaign.rules()
            campaign.map()
            campaign.telemetry_log()
            clock.now += 500  # a long think before starting costs nothing
        rules = campaign.rules()
        self.assertFalse(rules["clock"]["started"])
        self.assertEqual(rules["campaign"]["mission"], 1)
        self.assertEqual(campaign.advance(1)["current_tick"], 1)

    def test_uplink_starts_the_clock_and_thinking_then_costs_ticks(self):
        campaign, clock = service()
        ack = campaign.uplink([{"action": "wait"}])
        self.assertEqual(ack[0]["sent_tick"], 0)
        self.assertTrue(campaign.rules()["clock"]["started"])
        clock.now += 7.4  # no calls for 7.4 seconds
        late = campaign.uplink([{"action": "wait"}])
        self.assertEqual(late[0]["sent_tick"], 7)
        self.assertEqual(campaign.advance(1)["current_tick"], 8)

    def test_advance_waits_and_returns_every_packet_since_the_last_one(self):
        campaign, clock = service()
        campaign.uplink([{"action": "wait"}])
        clock.now += 6.2
        before = clock.now
        out = campaign.advance(2)
        self.assertAlmostEqual(clock.now - before, 1.8, places=6)  # waited to the tick-8 boundary
        self.assertEqual(out["current_tick"], 8)
        self.assertEqual([p["tick"] for p in out["packets"]], [1, 2, 3, 4, 5])  # delay is 3

    def test_advance_never_runs_past_the_end_of_a_mission(self):
        campaign, clock = service()
        campaign.advance(1)
        clock.now += 47.5
        out = campaign.advance(5)
        self.assertEqual((out["current_tick"], out["episode_complete"], out["campaign_complete"], out["mission"]),
                         (50, True, False, 1))
        self.assertEqual(campaign.rules()["campaign"]["mission"], 2)
        self.assertEqual(campaign.telemetry_log()[0]["tick"], 0)  # the new mission's briefing

    def test_missions_follow_each_other_on_the_clock_without_any_call(self):
        campaign, clock = service()
        campaign.advance(1)
        clock.now += 129.0  # 130 s since the start: mission 3, tick 30
        self.assertEqual(campaign.rules()["campaign"]["mission"], 3)
        self.assertEqual(campaign.advance(1)["current_tick"], 31)
        clock.now += 1000
        out = campaign.advance(3)
        self.assertTrue(out["campaign_complete"] and out["episode_complete"])
        self.assertTrue(campaign.rules()["campaign"]["complete"])
        with self.assertRaises(ToolError):
            campaign.uplink([{"action": "wait"}])


class GradingTest(unittest.TestCase):
    def test_an_instant_controller_scores_what_it_scores_turn_based(self):
        campaign, _ = service()
        play_campaign(campaign, POLICIES["kf_mpc"])
        result = campaign.result
        self.assertEqual(result["finished_by"], "clock")
        for mission, graded in zip(MISSIONS, result["missions"]):
            alone = run_episode(POLICIES["kf_mpc"], mission["seed"], delay=3, profile=mission["profile"])["result"]
            for key in ("raw_score", "sampled_targets", "alive", "at_base", "max_available_value"):
                self.assertEqual(graded[key], alone[key], (mission, key))
        rewards = [m["raw_score"] / m["max_available_value"] for m in result["missions"]]
        self.assertAlmostEqual(result["reward"], sum(rewards) / len(rewards))
        self.assertGreater(result["reward"], 0.5)

    def test_doing_nothing_scores_zero(self):
        campaign, _ = service()
        result = campaign.finish()
        self.assertEqual(result["reward"], 0.0)
        self.assertFalse(result["clock_started"])
        self.assertEqual(result["finished_by"], "evaluator")
        self.assertEqual([m["mission"] for m in result["missions"]], [1, 2, 3])
        self.assertTrue(all(m["alive"] and m["at_base"] and m["raw_score"] == 0 for m in result["missions"]))

    def test_stopping_early_keeps_only_what_was_earned(self):
        campaign, _ = service()
        POLICIES["kf_mpc"](campaign)  # the first mission only, then the agent walks away
        result = campaign.finish()
        first = result["missions"][0]["reward"]
        self.assertGreater(first, 0.5)
        self.assertEqual([m["reward"] for m in result["missions"][1:]], [0.0, 0.0])
        self.assertAlmostEqual(result["reward"], first / 3)

    def test_queued_commands_still_execute_after_the_agent_stops(self):
        campaign, _ = service()
        target = min(campaign.map()["targets"], key=lambda t: (t["x"] - 20) ** 2 + (t["y"] - 20) ** 2)
        campaign.uplink([{"action": "drive", "heading_deg": 0, "metres": 5}])
        result = campaign.finish()
        self.assertFalse(result["missions"][0]["at_base"])  # the drive ran after the agent left
        self.assertIsNotNone(target)

    def test_finish_is_idempotent_and_closes_the_tools(self):
        campaign, _ = service()
        campaign.advance(1)
        first = campaign.finish()
        self.assertEqual(first, campaign.finish())
        for call in (campaign.rules, campaign.map, campaign.telemetry_log, campaign.advance):
            with self.assertRaises(ToolError):
                call()

    def test_artifacts_hold_one_replay_per_mission(self):
        with tempfile.TemporaryDirectory() as folder:
            campaign, _ = service(artifact_dir=folder)
            play_campaign(campaign, POLICIES["kf_mpc"])
            with open(os.path.join(folder, "result.json"), encoding="utf-8") as stream:
                result = json.load(stream)
            self.assertEqual(result["version"], "lightlag-live-v1")
            for number in ("01", "02", "03"):
                with open(os.path.join(folder, "missions", number, "replay.json"), encoding="utf-8") as stream:
                    self.assertEqual(json.load(stream)["version"], "lightlag-replay-v1")
                with open(os.path.join(folder, "missions", number, "transcript.jsonl"), encoding="utf-8") as stream:
                    records = [json.loads(line) for line in stream]
                self.assertTrue(records and all(r["mission"] == int(number) for r in records))
            with open(os.path.join(folder, "transcript.jsonl"), encoding="utf-8") as stream:
                self.assertEqual(sum(1 for _ in stream), len(campaign.transcript()))


class SurfaceTest(unittest.TestCase):
    def test_nothing_public_reveals_a_seed_a_score_or_a_later_map(self):
        campaign, _ = service()
        campaign.advance(1)
        public = json.dumps([campaign.rules(), campaign.map(), campaign.telemetry_log(), campaign.advance(1)])
        # rules() describes how a mission is scored and says the noise is "fixed by seed";
        # neither is a seed or a score.
        for word in ("seed", "raw_score", "sampled_value", "survival_factor", "slip_coefficients", "8001", "8002"):
            self.assertNotIn(word, public.replace("fixed by seed", ""))

    def test_bad_requests_are_refused_and_change_nothing(self):
        campaign, clock = service()
        for tool, arguments in (("reset", {}), ("finish", {}), ("rules", {"x": 1}), ("advance", {"ticks": 0}),
                                ("advance", {"ticks": 6}), ("advance", {"ticks": 1, "x": 1}),
                                ("uplink", {}), ("uplink", {"commands": []})):
            with self.assertRaises(ToolError):
                campaign.call(tool, arguments)
        self.assertFalse(campaign.rules()["clock"]["started"])
        failed = [r for r in campaign.transcript() if not r["ok"]]
        self.assertEqual(len(failed), 8)

    def test_a_rejected_first_uplink_does_not_start_the_clock(self):
        campaign, clock = service()
        with self.assertRaises(ToolError):
            campaign.uplink([{"action": "drive", "heading_deg": 0, "metres": 50}])
        clock.now += 300
        self.assertFalse(campaign.rules()["clock"]["started"])
        self.assertEqual(campaign.uplink([{"action": "wait"}])[0]["sent_tick"], 0)
        self.assertEqual(campaign.advance(1)["mission"], 1)


if __name__ == "__main__":
    unittest.main()
