"""The boundary the integrity review leans on, checked in-process: no Docker, no network.

    python3 -m unittest discover -s tests/traverse_integrity -v

The live attacks are tools/traverse_integrity (through Harbor, in the agent's container). These
tests cover what a client library cannot send (numbers that are not finite) and what must stay
true of the task's files.
"""

from __future__ import annotations

import importlib.util
import re
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from lightlag.model import decode_command  # noqa: E402
from lightlag_mcp.service import ToolError  # noqa: E402
from lightlag_traverse.campaign import TraverseCampaignService  # noqa: E402
from lightlag_traverse.environment import TraverseEnvironment  # noqa: E402
from tools.traverse_integrity.probe import FORBIDDEN, forbidden_keys  # noqa: E402

TASK = REPO / "harbor" / "lightlag-traverse-campaign"
SEEDS = (1201, 1202)          # the integrity review's own worlds, never the judged ones


def load_grader():
    spec = importlib.util.spec_from_file_location("campaign_grade", TASK / "tests" / "grade.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CommandTest(unittest.TestCase):
    def test_numbers_that_are_not_finite_or_not_numbers_are_refused(self) -> None:
        for field in ("metres", "heading_deg"):
            for value in (float("nan"), float("inf"), float("-inf"), True, False, "5", None, [5], {"m": 5}, 10 ** 400):
                command = {"action": "drive", "heading_deg": 0, "metres": 1}
                command[field] = value
                with self.subTest(field=field, value=repr(value)), self.assertRaises(ValueError):
                    decode_command(command)

    def test_metres_outside_the_limit_and_extra_fields_are_refused(self) -> None:
        for command in ({"action": "drive", "heading_deg": 0, "metres": 0}, {"action": "drive", "heading_deg": 0, "metres": -1},
                        {"action": "drive", "heading_deg": 0, "metres": 5.000001},
                        {"action": "drive", "heading_deg": 0, "metres": 1, "x": 300},
                        {"action": "wait", "ticks": 50}, {"action": "sample", "target_id": "T01"}, {"action": "teleport"}):
            with self.subTest(command=command), self.assertRaises(ValueError):
                decode_command(command)

    def test_a_refused_batch_queues_nothing(self) -> None:
        env = TraverseEnvironment(SEEDS[0])
        delay = env.rules()["delay_ticks"]
        with self.assertRaises(ValueError):
            env.uplink([{"action": "wait"}, {"action": "drive", "heading_deg": 0, "metres": 50}])
        self.assertEqual(env.uplink([{"action": "wait"}])[0]["execute_tick"], delay + 1)
        for ticks in (0, 6, -1, 1.5, True, "1", None):
            with self.subTest(ticks=repr(ticks)), self.assertRaises(ValueError):
                env.advance(ticks)


class ServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = TraverseCampaignService(list(SEEDS))

    def test_only_the_five_tools_answer(self) -> None:
        for tool in ("evaluate", "replay", "finish", "reset", "mission_records", "run_out", "_grade", "result"):
            with self.subTest(tool=tool), self.assertRaises(ToolError):
                self.service.call(tool)

    def test_public_replies_carry_no_hidden_key(self) -> None:
        self.service.advance(5)
        for tool in ("rules", "map", "telemetry_log"):
            with self.subTest(tool=tool):
                self.assertEqual(forbidden_keys(self.service.call(tool)), [])
        self.assertEqual(forbidden_keys(self.service.advance(1)), [])
        text = repr(self.service.call("rules"))
        for seed in SEEDS:
            self.assertIsNone(re.search(r"(?<![0-9.]){}(?![0-9.])".format(seed), text))

    def test_the_evaluator_files_do_carry_them(self) -> None:
        """The scan is not blind: the same keys are found where they are meant to be."""
        result = self.service.finish()
        self.assertTrue(set(key.rsplit("/", 1)[-1] for key in forbidden_keys(result)) & FORBIDDEN)

    def test_a_finished_campaign_is_closed_and_graded_once(self) -> None:
        first = self.service.finish()
        with self.assertRaises(ToolError):
            self.service.call("uplink", {"commands": [{"action": "wait"}]})
        with self.assertRaises(ToolError):
            self.service.call("advance", {"ticks": 1})
        self.assertEqual(self.service.finish(), first)
        self.assertEqual(first["raw_score"], 0.0)          # nothing was sampled


class TaskFilesTest(unittest.TestCase):
    def test_the_grader_refuses_what_the_simulator_never_writes(self) -> None:
        grade = load_grader()
        self.assertEqual(grade.reward_from({"raw_score": 1.0, "max_available_value": 4.0}), 0.25)
        for result in ({"raw_score": 5.0, "max_available_value": 4.0}, {"raw_score": -1.0, "max_available_value": 4.0},
                       {"raw_score": float("nan"), "max_available_value": 4.0}, {"raw_score": 1.0, "max_available_value": 0},
                       {"raw_score": True, "max_available_value": 4.0}, {"raw_score": "4", "max_available_value": 4.0},
                       {"reward": 1.0}, [1.0], None):
            with self.subTest(result=repr(result)), self.assertRaises(grade.BadResult):
                grade.reward_from(result)

    def test_the_agent_image_copies_three_helper_files_and_nothing_of_the_simulator(self) -> None:
        dockerfile = (TASK / "environment" / "Dockerfile").read_text()
        copied = sorted(line.split()[1] for line in dockerfile.splitlines() if line.startswith("COPY "))
        self.assertEqual(copied, ["detach.py", "lightlag_client.py", "lightlag_surface.py"])
        ignored = (TASK / "environment" / ".dockerignore").read_text().split()
        self.assertIn("simulator/", ignored)
        self.assertIn("docker-compose.yaml", ignored)

    def test_no_file_given_to_the_agent_names_a_seed(self) -> None:
        compose = (TASK / "environment" / "docker-compose.yaml").read_text()
        seeds = re.search(r'LIGHTLAG_SEEDS: "([0-9, ]+)"', compose).group(1).split(",")
        for name in ("instruction.md", "environment/lightlag_client.py", "environment/lightlag_surface.py",
                     "environment/detach.py", "environment/Dockerfile"):
            text = (TASK / name).read_text()
            for seed in seeds:
                with self.subTest(file=name, seed=seed):
                    self.assertIsNone(re.search(r"(?<![0-9.]){}(?![0-9.])".format(seed.strip()), text))

    def test_the_verifier_runs_apart_and_the_result_comes_from_the_simulator(self) -> None:
        task = (TASK / "task.toml").read_text()
        self.assertIn('environment_mode = "separate"', task)
        self.assertIn('artifacts = [{ source = "/evaluator", service = "lightlag" }]', task)
        self.assertIn("--result /evaluator/result.json", (TASK / "tests" / "test.sh").read_text())


if __name__ == "__main__":
    unittest.main()
