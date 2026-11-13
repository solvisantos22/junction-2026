"""What an agent can and cannot do through the Lightlag episode service.

Standard library only. Run from the repository root:

    python3 -m unittest discover -s tests/lightlag_mcp -v
"""

import json
import os
import tempfile
import threading
import unittest

from lightlag import Config, Environment

from lightlag_controllers import REFERENCE, drive, make
from lightlag_mcp import PUBLIC_TOOLS, EpisodeService, ToolError

DRIVE_WEST = [{"action": "drive", "heading_deg": 180, "metres": 2}]


class PublicSurface(unittest.TestCase):
    def test_exactly_five_tools_are_public(self):
        self.assertEqual(PUBLIC_TOOLS, ("rules", "map", "telemetry_log", "uplink", "advance"))

    def test_evaluator_and_private_names_are_not_dispatchable(self):
        service = EpisodeService(seed=7)
        for name in ("evaluate", "replay", "finish", "reset", "result", "transcript", "_step", "_env", "__init__", ""):
            with self.assertRaises(ToolError, msg=name):
                service.call(name)
        self.assertEqual(service.call("advance")["current_tick"], 1)

    def test_results_are_the_simulators_own(self):
        service = EpisodeService(seed=7, config=Config(delay_ticks=3))
        env = Environment(seed=7, config=Config(delay_ticks=3))
        self.assertEqual(service.call("rules"), env.rules())
        self.assertEqual(service.call("map"), env.map())
        self.assertEqual(service.call("uplink", {"commands": DRIVE_WEST}), env.uplink(DRIVE_WEST))
        self.assertEqual(service.call("advance", {"ticks": 5}), env.advance(5))
        self.assertEqual(service.call("telemetry_log"), env.telemetry_log())

    def test_invalid_requests_explain_themselves_and_change_nothing(self):
        service = EpisodeService(seed=7, config=Config(delay_ticks=3))
        bad_calls = [
            ("uplink", {"commands": []}),
            ("uplink", {"commands": [{"action": "fly"}]}),
            ("uplink", {"commands": [{"action": "drive", "heading_deg": 0, "metres": 9}]}),
            ("uplink", {"commands": DRIVE_WEST, "seed": 3}),
            ("uplink", {}),
            ("advance", {"ticks": 99}),
            ("advance", {"ticks": "2"}),
            ("advance", {"ticks": 1, "to": 80}),
            ("rules", {"verbose": True}),
        ]
        for tool, arguments in bad_calls:
            with self.assertRaises(ToolError) as caught:
                service.call(tool, arguments)
            self.assertTrue(str(caught.exception), (tool, arguments))
        # Nothing was queued and no time passed: the first valid command still gets slot 4.
        self.assertEqual(service.call("uplink", {"commands": DRIVE_WEST})[0]["execute_tick"], 4)
        self.assertEqual(service.call("advance")["current_tick"], 1)

    def test_no_public_result_reveals_the_seed_or_the_hidden_slip(self):
        seed = 424242
        with tempfile.TemporaryDirectory() as directory:
            service = EpisodeService(seed=seed, config=Config(delay_ticks=3), artifact_dir=directory)
            seen = []

            class Recording:
                """The five tools, keeping a copy of everything they return."""

                def __getattr__(self, name):
                    def call(*args, **kwargs):
                        result = getattr(service, name)(*args, **kwargs)
                        seen.append(json.dumps(result))
                        return result
                    return call

            drive(Recording(), make(REFERENCE))
            service.finish()
            with open(os.path.join(directory, "replay.json"), encoding="utf-8") as stream:
                slip = json.load(stream)["slip_coefficients"]
        everything = "\n".join(seen)
        self.assertGreater(len(seen), 50)
        self.assertNotIn(str(seed), everything)
        self.assertNotIn("slip_coefficients", everything)
        for value in slip.values():
            self.assertNotIn(repr(value), everything)
            self.assertNotIn(str(round(value, 6)), everything)


class EvaluatorSide(unittest.TestCase):
    def test_finish_closes_grades_and_writes_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            service = EpisodeService(seed=7, config=Config(delay_ticks=0, max_ticks=20), artifact_dir=directory)
            service.call("uplink", {"commands": DRIVE_WEST})
            service.call("advance", {"ticks": 2})
            self.assertFalse(os.path.exists(os.path.join(directory, "result.json")))
            result = service.finish()
            self.assertTrue(service.closed)
            self.assertEqual(result["tick"], 20)
            self.assertEqual(result["raw_score"], 0.0)
            self.assertEqual(result["tool_calls"], 2)
            with self.assertRaises(ToolError) as caught:
                service.call("rules")
            self.assertIn("closed", str(caught.exception))
            self.assertEqual(service.finish(), result)
            with open(os.path.join(directory, "result.json"), encoding="utf-8") as stream:
                self.assertEqual(json.load(stream), result)
            with open(os.path.join(directory, "replay.json"), encoding="utf-8") as stream:
                replay = json.load(stream)
            self.assertEqual(replay["seed"], 7)
            self.assertEqual(len(replay["states"]), 21)
            with open(os.path.join(directory, "transcript.jsonl"), encoding="utf-8") as stream:
                lines = [json.loads(line) for line in stream]
            self.assertEqual([line["tool"] for line in lines], ["uplink", "advance", "rules"])
            self.assertEqual([line["ok"] for line in lines], [True, True, False])

    def test_reaching_the_horizon_grades_without_a_finish_call(self):
        with tempfile.TemporaryDirectory() as directory:
            service = EpisodeService(seed=7, config=Config(delay_ticks=0, max_ticks=6), artifact_dir=directory)
            self.assertIsNone(service.result)
            service.call("advance", {"ticks": 5})
            self.assertIsNone(service.result)
            self.assertTrue(service.call("advance", {"ticks": 5})["episode_complete"])
            self.assertEqual(service.result["tick"], 6)
            self.assertTrue(os.path.exists(os.path.join(directory, "result.json")))
            # Reads still work after the horizon; new commands do not.
            self.assertEqual(len(service.call("telemetry_log")), 7)
            with self.assertRaises(ToolError):
                service.call("uplink", {"commands": DRIVE_WEST})

    def test_doing_nothing_and_stopping_early_are_graded_at_the_full_horizon(self):
        nothing = EpisodeService(seed=3).finish()
        self.assertEqual((nothing["tick"], nothing["raw_score"], nothing["tool_calls"]), (80, 0.0, 0))
        early = EpisodeService(seed=3, config=Config(delay_ticks=0))
        early.call("uplink", {"commands": [{"action": "drive", "heading_deg": 180, "metres": 5}]})
        early.call("advance")
        stopped = early.finish()
        self.assertEqual(stopped["tick"], 80)
        self.assertEqual(stopped["raw_score"], 0.0)
        self.assertFalse(stopped["at_base"])

    def test_a_scripted_policy_scores_the_same_through_the_service(self):
        direct = Environment(seed=5, config=Config(delay_ticks=3))
        drive(direct, make(REFERENCE))
        service = EpisodeService(seed=5, config=Config(delay_ticks=3))
        drive(service, make(REFERENCE))
        result = service.finish()
        self.assertEqual(result["raw_score"], direct.evaluate()["raw_score"])
        self.assertGreater(result["raw_score"], 0.0)

    def test_concurrent_calls_are_serialized(self):
        service = EpisodeService(seed=1)
        errors = []

        def worker():
            try:
                for _ in range(5):
                    service.call("advance")
            except Exception as failure:  # pragma: no cover - reported below
                errors.append(failure)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        transcript = service.transcript()
        self.assertEqual([entry["n"] for entry in transcript], list(range(1, 41)))
        for entry in transcript:
            self.assertEqual(entry["tick_after"], entry["tick_before"] + 1)
        self.assertEqual(service.call("advance")["current_tick"], 41)


if __name__ == "__main__":
    unittest.main()
