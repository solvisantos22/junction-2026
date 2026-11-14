"""A traverse campaign: missions follow one another under unchanged rules, and the grade covers them all.

    python3 -m unittest discover -s tests/lightlag_traverse -v

Standard library only. Development worlds 5 and 6; the campaign task's own worlds are not played here.
"""

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from lightlag_traverse import make_task  # noqa: E402
from lightlag_traverse import server  # noqa: E402
from lightlag_traverse.campaign import TEXTS, TraverseCampaign, TraverseCampaignService  # noqa: E402
from lightlag_traverse.environment import MISSION, TraverseEnvironment  # noqa: E402
from lightlag_traverse.pilot import Pilot, fly_campaign  # noqa: E402

SEEDS = (5, 6)
TICKS = MISSION["max_ticks"]
QUICK = {"plan_steps": 8000, "replan_steps": 1500, "beam": 40, "rebeam": 15}
SCRIPT = [{"action": "drive", "heading_deg": 0, "metres": 5}, {"action": "drive", "heading_deg": 90, "metres": 3.5},
          {"action": "sample"}, {"action": "wait"}, {"action": "drive", "heading_deg": 200, "metres": 4}]


def to_end(tools):
    """Advance to the end of the mission in play; the last reply."""
    while True:
        out = tools.advance(5)
        if out["episode_complete"]:
            return out


def load_grade():
    spec = importlib.util.spec_from_file_location("lightlag_traverse_grade",
                                                  make_task.CAMPAIGN_TASK / "tests" / "grade.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CampaignTest(unittest.TestCase):
    def test_the_next_mission_begins_when_the_last_tick_of_one_has_passed(self):
        campaign = TraverseCampaign(SEEDS)
        first = campaign.map()
        self.assertEqual((first["mission"], first["missions"]), (1, 2))
        out = to_end(campaign)
        self.assertEqual((out["current_tick"], out["mission"], out["campaign_complete"]), (TICKS, 1, False))
        second = campaign.map()
        self.assertEqual(second["mission"], 2)
        self.assertNotEqual(second["elevation_cm"], first["elevation_cm"])
        self.assertEqual(second, dict(TraverseEnvironment(SEEDS[1]).map(), mission=2, missions=2))
        log = campaign.telemetry_log()
        self.assertEqual([(packet["tick"], packet["mission"]) for packet in log], [(0, 2)])
        self.assertEqual(log[0]["battery"], MISSION["initial_battery"])
        self.assertEqual(campaign.rules()["campaign"]["mission"], 2)
        self.assertEqual(campaign.elapsed, TICKS)

    def test_a_mission_in_a_campaign_is_the_same_mission_as_on_its_own(self):
        alone = TraverseEnvironment(SEEDS[1])
        alone.uplink(SCRIPT)
        to_end(alone)
        campaign = TraverseCampaign(SEEDS)
        to_end(campaign)
        acks = campaign.uplink(SCRIPT)
        self.assertEqual({ack["mission"] for ack in acks}, {2})
        to_end(campaign)
        result = campaign.evaluate()["missions"][1]
        expected = alone.evaluate()
        self.assertEqual({key: result[key] for key in expected}, expected)
        self.assertEqual(campaign.mission_records()[1]["replay"]["states"], alone.replay()["states"])

    def test_after_the_last_mission_time_stands_still_and_commands_are_refused(self):
        campaign = TraverseCampaign(SEEDS)
        to_end(campaign)
        out = to_end(campaign)
        self.assertTrue(out["campaign_complete"])
        again = campaign.advance(5)
        self.assertEqual((again["campaign_complete"], again["packets"], campaign.elapsed), (True, [], 2 * TICKS))
        with self.assertRaises(ValueError):
            campaign.uplink([{"action": "wait"}])

    def test_advance_takes_one_to_five_whole_ticks(self):
        campaign = TraverseCampaign(SEEDS)
        for bad in (0, 6, 1.5, True, "1"):
            with self.assertRaises(ValueError):
                campaign.advance(bad)
        self.assertEqual(campaign.elapsed, 0)

    def test_the_score_is_all_value_earned_over_all_value_there_was(self):
        campaign = TraverseCampaign(SEEDS)
        campaign.uplink(SCRIPT)
        campaign.run_out()
        result = campaign.evaluate()
        missions = result["missions"]
        self.assertEqual([m["mission"] for m in missions], [1, 2])
        self.assertEqual([m["seed"] for m in missions], list(SEEDS))
        self.assertAlmostEqual(result["raw_score"], sum(m["raw_score"] for m in missions))
        self.assertAlmostEqual(result["max_available_value"], sum(m["max_available_value"] for m in missions))
        self.assertEqual(result["mission_rewards"], [m["raw_score"] / m["max_available_value"] for m in missions])
        with self.assertRaises(ValueError):
            TraverseCampaign(SEEDS).evaluate()                  # only once every mission has ended
        for bad in ((), (5, "6"), (5.0,)):
            with self.assertRaises(ValueError):
                TraverseCampaign(bad)


class CampaignServiceTest(unittest.TestCase):
    """From a campaign to the number Harbor reads, with the service and the grader the task ships."""

    def grade(self, folder, name, play):
        artifacts = os.path.join(folder, name)
        service = TraverseCampaignService(SEEDS, artifact_dir=artifacts)
        play(service)
        result = service.finish()
        reward_file = os.path.join(folder, name + "-reward.txt")
        self.assertEqual(load_grade().main(["--result", os.path.join(artifacts, "result.json"),
                                            "--reward", reward_file]), 0)
        with open(reward_file, encoding="utf-8") as stream:
            reward = float(stream.read())
        self.assertAlmostEqual(reward, result["raw_score"] / result["max_available_value"], places=6)
        for number in (1, 2):
            for kind in ("result", "replay"):
                self.assertTrue(os.path.exists(os.path.join(artifacts, "missions", "{:02d}".format(number),
                                                            kind + ".json")))
        return reward, result, service

    def test_reference_do_nothing_and_stop_after_the_first_mission(self):
        def first_only(service):
            pilot = Pilot(service, QUICK)
            while True:
                pilot.act()
                out = service.advance(1)
                pilot.observe(out["packets"], out["current_tick"])
                if out["episode_complete"]:
                    return

        with tempfile.TemporaryDirectory() as folder:
            reference, result, service = self.grade(folder, "reference", lambda s: fly_campaign(s, QUICK))
            self.assertGreater(reference, 0.3)
            self.assertTrue(all(m["alive"] and m["at_base"] for m in result["missions"]))
            nothing, _, _ = self.grade(folder, "nothing", lambda s: None)
            self.assertEqual(nothing, 0.0)
            early, early_result, _ = self.grade(folder, "early", first_only)
            self.assertGreater(early_result["mission_rewards"][0], 0.3)
            self.assertEqual(early_result["mission_rewards"][1], 0.0)   # the second site earned nothing
            self.assertLess(early, 0.6 * reference)
            with self.assertRaises(ValueError):                         # a finished campaign takes no more calls
                service.call("advance", {"ticks": 1})
            ticks = [row["tick_after"] for row in service.transcript()]
            self.assertEqual(max(ticks), 2 * TICKS)

    def test_it_grades_once_when_the_last_mission_has_ended(self):
        service = TraverseCampaignService(SEEDS)
        out = to_end(service)
        self.assertEqual((out["mission"], out["campaign_complete"]), (1, False))
        self.assertIsNone(service.result)
        out = to_end(service)
        self.assertTrue(out["campaign_complete"])
        self.assertEqual(service.result["seeds"], list(SEEDS))

    def test_the_service_offers_exactly_the_five_tools(self):
        service = TraverseCampaignService(SEEDS)
        for tool in ("evaluate", "replay", "reset", "finish", "seed", "run_out", "mission_records"):
            with self.assertRaises(ValueError):
                service.call(tool, {})
        self.assertEqual(service.call("rules")["campaign"]["missions"], 2)
        self.assertEqual(service.call("map")["mission"], 1)
        self.assertEqual(json.loads(json.dumps(service.call("telemetry_log")))[0]["mission"], 1)

    def test_the_server_tells_an_agent_about_the_missions(self):
        self.assertEqual(set(TEXTS), set(server.TEXTS))
        for key in ("instructions", "rules", "map", "telemetry_log", "uplink", "advance"):
            self.assertIn("mission", TEXTS[key], key)
        self.assertNotIn("mission in play", server.TEXTS["advance"])     # one mission is served as before


class CampaignTaskTest(unittest.TestCase):
    TASK = make_task.CAMPAIGN_TASK

    def test_the_committed_task_matches_its_sources(self):
        self.assertEqual(make_task.stale(self.TASK, make_task.build_campaign()), [],
                         "run `python3 -m lightlag_traverse.make_task --all` and commit the result")

    def test_the_seeds_live_in_the_simulator_only(self):
        compose = (self.TASK / "environment" / "docker-compose.yaml").read_text(encoding="utf-8")
        seeds = ",".join(str(seed) for seed in make_task.CAMPAIGN_SEEDS)
        self.assertIn('LIGHTLAG_SEEDS: "{}"'.format(seeds), compose)
        self.assertNotIn("LIGHTLAG_SEED:", compose)
        for path in [self.TASK / "instruction.md", self.TASK / "task.toml"] + list((self.TASK / "solution").rglob("*")):
            if path.is_file():
                text = path.read_text(encoding="utf-8")
                for seed in make_task.CAMPAIGN_SEEDS:
                    self.assertNotIn(str(seed), text, path.name)

    def test_the_agent_gets_the_same_image_as_for_one_mission(self):
        for name in ("Dockerfile", ".dockerignore", "lightlag_client.py", "lightlag_surface.py", "detach.py"):
            self.assertEqual((self.TASK / "environment" / name).read_bytes(),
                             (make_task.TASK / "environment" / name).read_bytes(), name)

    def test_the_instruction_states_the_campaign_it_serves(self):
        instruction = (self.TASK / "instruction.md").read_text(encoding="utf-8")
        for phrase in ("three missions", "campaign_complete", "do not finish before `campaign_complete` is true",
                       "limited to 45 minutes", "drawn afresh for every mission", "no reset and no practice run",
                       "{} ticks".format(TICKS)):
            self.assertIn(phrase, instruction)
        toml = (self.TASK / "task.toml").read_text(encoding="utf-8")
        self.assertIn("timeout_sec = {}.0".format(make_task.CAMPAIGN_AGENT_TIMEOUT_SEC), toml)
        self.assertIn("lightlag_mcp.finish", toml)
        play = (self.TASK / "solution" / "play_reference.py").read_text(encoding="utf-8")
        self.assertIn("fly_campaign", play)


if __name__ == "__main__":
    unittest.main()
