"""Protected service contract independent of the MCP transport."""

import json
from pathlib import Path
import tempfile
import unittest

from lightlag_information_allocation import Environment
from lightlag_information_allocation.policies import run_policy
from lightlag_information_allocation.service import InformationService, ToolError


class ServiceTests(unittest.TestCase):
    def test_exact_public_shape_and_delayed_signal(self):
        service = InformationService(7)
        direct = Environment(7)
        for name, args in [("rules", {}), ("map", {}),
                           ("uplink", {"commands": [{"action": "probe", "route": "a"}]}),
                           ("advance", {"ticks": 2}), ("telemetry_log", {}),
                           ("advance", {"ticks": 1})]:
            self.assertEqual(service.call(name, args), getattr(direct, name)(**args))
        signal = service.telemetry_log()["entries"][-1]
        self.assertEqual((signal["action"], signal["delivery_tick"]), ("probe", 3))

    def test_initial_surfaces_and_ack_do_not_disclose_seed_or_hidden_state(self):
        services = [InformationService(seed) for seed in range(8)]
        for tool, args in [("rules", {}), ("map", {}), ("telemetry_log", {}),
                           ("uplink", {"commands": [{"action": "probe", "route": "a"}]})]:
            results = [service.call(tool, args) for service in services]
            self.assertTrue(all(result == results[0] for result in results))
            self.assertNotIn('"seed"', json.dumps(results[0]))

    def test_invalid_requests_are_recorded_but_do_not_change_clock_or_reservations(self):
        service = InformationService(0)
        invalid = [("finish", {}), ("reset", {}), ("rules", {"seed": 4}),
                   ("uplink", {"commands": [{"action": "probe", "route": "a"}], "seed": 0}),
                   ("advance", {"ticks": True}), ("advance", {"ticks": 0}),
                   ("advance", {"ticks": 2, "other": 1}), ("map", [])]
        for tool, args in invalid:
            with self.assertRaises(ToolError):
                service.call(tool, args)
        records = service.transcript()
        self.assertEqual(len(records), len(invalid))
        self.assertTrue(all(not record["ok"] and record["tick_after"] == 0 for record in records))
        self.assertEqual(service.uplink([{"action": "commit", "route": "detour"}])["accepted"][0]["execution_tick"], 2)

    def test_early_finish_executes_accepted_commit_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            service = InformationService(7, artifact_dir=directory)
            service.uplink([{"action": "commit", "route": "detour"}])
            result = service.finish()
            self.assertEqual((result["reward"], result["raw_score"], result["max_available_value"]), (.4, 4, 10))
            self.assertEqual(result["completion_tick"], 8)
            result["reward"] = -1
            self.assertEqual(service.finish()["reward"], .4)
            with self.assertRaisesRegex(ToolError, "closed"):
                service.advance(1)
            self.assertFalse(service.transcript()[-1]["ok"])
            self.assertEqual(json.loads((Path(directory) / "result.json").read_text())["reward"], .4)
            replay = json.loads((Path(directory) / "replay.json").read_text())
            self.assertEqual(replay["evaluation"]["reward"], .4)
            records = [json.loads(line) for line in (Path(directory) / "transcript.jsonl").read_text().splitlines()]
            self.assertEqual(records, service.transcript())

    def test_horizon_auto_grades_and_reads_cannot_modify_results(self):
        with tempfile.TemporaryDirectory() as directory:
            service = InformationService(7, artifact_dir=directory)
            returned = service.rules()
            returned["routes"]["a"]["target_value"] = 9999
            self.assertEqual(service.rules()["routes"]["a"]["target_value"], 10)
            for _ in range(6):
                service.advance(5)
            self.assertEqual(json.loads((Path(directory) / "result.json").read_text())["reward"], 0)
            records = service.transcript()
            records.clear()
            self.assertTrue(service.transcript())

    def test_saved_episode_is_not_overwritten_on_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            service = InformationService(7, artifact_dir=directory)
            service.rules()
            before = (Path(directory) / "transcript.jsonl").read_bytes()
            with self.assertRaises(FileExistsError):
                InformationService(8, artifact_dir=directory)
            self.assertEqual((Path(directory) / "transcript.jsonl").read_bytes(), before)

    def test_reference_rewards_match_direct_environment_for_every_context(self):
        for context in ("case_1", "case_2", "case_3", "case_4", "case_5", "case_6"):
            service = InformationService(100, context)
            env = Environment(100, context)
            run_policy(service, "selective")
            run_policy(env, "selective")
            self.assertEqual(service.finish()["reward"], env.evaluate()["reward"])


if __name__ == "__main__":
    unittest.main()
