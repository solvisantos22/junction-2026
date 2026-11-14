"""Protected evidence and public packet shape for the physical rover service."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from lightlag import Config
from lightlag_expedition.environment import ExpeditionEnvironment
from lightlag_expedition.service import ExpeditionService, ToolError


class ServiceTests(unittest.TestCase):
    def test_exact_public_shape_and_delayed_inspection_packet(self):
        service = ExpeditionService(7, mission_seed=2)
        direct = ExpeditionEnvironment(7, mission_seed=2)
        calls = [("rules", {}), ("map", {}), ("telemetry_log", {}),
                 ("uplink", {"commands": [{"action": "inspect", "region": "r2"}]}),
                 ("advance", {"ticks": 5}), ("telemetry_log", {}),
                 ("advance", {"ticks": 2}), ("telemetry_log", {})]
        for name, args in calls:
            self.assertEqual(service.call(name, args), getattr(direct, name)(**args))
        packets = service.telemetry_log()
        inspected = [packet for packet in packets if any(e["type"] == "inspection_result" for e in packet["events"])]
        self.assertEqual(len(inspected), 1)
        self.assertEqual((inspected[0]["tick"], inspected[0]["received_tick"]), (4, 7))
        self.assertIsInstance(service.transcript()[3]["result"], list)

    def test_initial_hidden_surfaces_do_not_disclose_seed_or_quality(self):
        services = [ExpeditionService(seed, mission_seed=2) for seed in range(8)]
        for tool, args in [("rules", {}), ("map", {}), ("telemetry_log", {}),
                           ("uplink", {"commands": [{"action": "inspect", "region": "r1"}]})]:
            results = [service.call(tool, args) for service in services]
            self.assertTrue(all(result == results[0] for result in results))
            for private_key in ('"seed":', '"mission_seed":', '"qualities":', '"signals":'):
                self.assertNotIn(private_key, json.dumps(results[0]))

    def test_invalid_requests_are_recorded_without_clock_or_reservation_changes(self):
        service = ExpeditionService(0)
        invalid = [("finish", {}), ("reset", {}), ("rules", {"seed": 4}),
                   ("uplink", {"commands": [{"action": "inspect", "region": "r1"}], "seed": 0}),
                   ("uplink", {"commands": [{"action": "inspect", "region": "r1"}, {"action": "inspect", "region": "r1"}]}),
                   ("advance", {"ticks": True}), ("advance", {"ticks": 0}),
                   ("advance", {"ticks": 2, "other": 1}), ("map", [])]
        for tool, args in invalid:
            with self.assertRaises(ToolError):
                service.call(tool, args)
        records = service.transcript()
        self.assertEqual(len(records), len(invalid))
        self.assertTrue(all(not record["ok"] and record["tick_after"] == 0 for record in records))
        ack = service.uplink([{"action": "inspect", "region": "r1"}])
        self.assertEqual((ack[0]["command_id"], ack[0]["execute_tick"]), (1, 4))

    def test_nonfinite_rejections_preserve_json_safe_evidence_and_atomic_state(self):
        # JSON 1e309 can decode to infinity. Keep the rejected numeric value in
        # the evidence without letting strict JSON logging mask its ToolError.
        invalid_numbers = ((float("nan"), "NaN"), (float("inf"), "Infinity"),
                           (float("-inf"), "-Infinity"))
        with tempfile.TemporaryDirectory() as directory:
            service = ExpeditionService(0, artifact_dir=directory)
            for value, label in invalid_numbers:
                commands = [{"action": "inspect", "region": "r1"},
                            {"action": "drive", "heading_deg": value, "metres": 1}]
                with self.subTest(label=label), self.assertRaisesRegex(ToolError, "finite number"):
                    service.uplink(commands)
                record = service.transcript()[-1]
                self.assertEqual(record["arguments"]["commands"][1]["heading_deg"],
                                 {"__nonfinite_float__": label})
                self.assertEqual((record["ok"], record["tick_before"], record["tick_after"]),
                                 (False, 0, 0))
                self.assertEqual(service._env.rules()["science"]["inspection_remaining"], 2)
                saved = [json.loads(line) for line in (Path(directory) / "transcript.jsonl").read_text().splitlines()]
                self.assertEqual(saved, service.transcript())
            ack = service.uplink([{"action": "inspect", "region": "r1"}])
            self.assertEqual((ack[0]["command_id"], ack[0]["execute_tick"]), (1, 4))
            result = service.finish()
            self.assertEqual(result["tool_calls"], 4)
            self.assertEqual([row["n"] for row in service.transcript()], [1, 2, 3, 4])
            self.assertEqual(len(service._env.replay()["expedition"]["inspection_executed"]), 1)
            saved = [json.loads(line) for line in (Path(directory) / "transcript.jsonl").read_text().splitlines()]
            self.assertEqual(saved, service.transcript())

    def test_nonfinite_evidence_is_json_safe_without_an_artifact_directory(self):
        service = ExpeditionService(0)
        with self.assertRaises(ToolError):
            service.advance(float("inf"))
        records = service.transcript()
        self.assertEqual(records[0]["arguments"], {"ticks": {"__nonfinite_float__": "Infinity"}})
        self.assertEqual(json.loads(json.dumps(records, allow_nan=False)), records)

    def test_finish_preserves_full_evaluation_and_replay_and_is_idempotent(self):
        # A public configuration fixture makes a successful sample reachable at
        # launch, independently testing score preservation without a controller.
        config = Config(max_ticks=8, target_radius=100)
        factory = lambda **kwargs: ExpeditionEnvironment(config=config, **kwargs)
        with tempfile.TemporaryDirectory() as directory, patch("lightlag_expedition.service.ExpeditionEnvironment", factory):
            service = ExpeditionService(7, artifact_dir=directory)
            direct = ExpeditionEnvironment(7, config=config)
            commands = [{"action": "inspect", "region": "r1"}, {"action": "sample"}]
            service.uplink(commands)
            direct.uplink(commands)
            direct.advance(5)
            direct.advance(3)
            result = service.finish()
            evaluation = direct.evaluate()
            for name, value in evaluation.items():
                self.assertEqual(result[name], value)
            self.assertGreater(result["raw_score"], 0)
            self.assertEqual(result["reward"], evaluation["raw_score"] / evaluation["max_available_value"])
            self.assertEqual((result["tick"], result["tool_calls"]), (8, 1))
            self.assertIn("quality_multiplier", result["samples"][0])
            saved = json.loads((Path(directory) / "result.json").read_text())
            replay = json.loads((Path(directory) / "replay.json").read_text())
            self.assertEqual(saved, result)
            self.assertEqual(replay, direct.replay())
            result["reward"] = -1
            self.assertEqual(service.finish(), saved)
            with self.assertRaisesRegex(ToolError, "closed"):
                service.advance(1)
            self.assertEqual(service.finish(), saved)
            records = [json.loads(line) for line in (Path(directory) / "transcript.jsonl").read_text().splitlines()]
            self.assertEqual(records, service.transcript())

    def test_horizon_auto_grades_and_return_values_are_copies(self):
        with tempfile.TemporaryDirectory() as directory:
            service = ExpeditionService(7, artifact_dir=directory)
            returned = service.rules()
            returned["science"]["inspection_budget"] = 999
            self.assertEqual(service.rules()["science"]["inspection_budget"], 2)
            for _ in range(12):
                service.advance(5)
            result = json.loads((Path(directory) / "result.json").read_text())
            self.assertEqual((result["tick"], result["reward"], result["tool_calls"]), (60, 0, 14))
            self.assertEqual(service.finish(), result)
            records = service.transcript()
            records.clear()
            self.assertTrue(service.transcript())

    def test_existing_episode_artifacts_are_not_overwritten_on_restart(self):
        for name in ("transcript.jsonl", "result.json", "replay.json"):
            with tempfile.TemporaryDirectory() as directory:
                artifact = Path(directory) / name
                artifact.write_text("keep me")
                with self.assertRaises(FileExistsError):
                    ExpeditionService(8, artifact_dir=directory)
                self.assertEqual(artifact.read_text(), "keep me")


if __name__ == "__main__":
    unittest.main()
