import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from lightlag import Config, Environment


ROOT = Path(__file__).resolve().parents[2]


def run_cli(text, *arguments):
    return subprocess.run([sys.executable, "-m", "lightlag", *arguments], input=text,
                          capture_output=True, text=True, cwd=ROOT, timeout=10)


def request(method, params=None, request_id=1):
    return json.dumps({"id": request_id, "method": method, "params": params or {}}) + "\n"


class ReplayTests(unittest.TestCase):
    def test_replay_requires_completion_and_returns_independent_truth(self):
        env = Environment(seed=7, config=Config(delay_ticks=3, max_ticks=5))
        with self.assertRaises(ValueError):
            env.replay()
        env.uplink([{"action": "drive", "heading_deg": 0, "metres": 2}])
        env.advance(5)
        replay = env.replay()
        self.assertEqual(len(replay["states"]), 6)
        self.assertGreater(replay["states"][4]["position"][0], 20)
        self.assertEqual(replay["received_telemetry"][-1]["tick"], 2)
        self.assertEqual(replay["commands"][0]["execute_tick"], 4)
        self.assertEqual(replay["seed"], 7)
        replay["states"][0]["position"][0] = -100
        replay["slip_coefficients"]["sand"] = -100
        self.assertEqual(env.replay()["states"][0]["position"], [20, 20])
        self.assertGreaterEqual(env.replay()["slip_coefficients"]["sand"], 0.2)


class CliTests(unittest.TestCase):
    def test_dispatch_returns_only_public_results(self):
        script = (request("rules", request_id="rules") + request("map")
                  + request("telemetry_log")
                  + request("uplink", {"commands": [{"action": "drive", "heading_deg": 0, "metres": 2}]})
                  + request("advance", {"ticks": 5}))
        process = run_cli(script, "--ticks", "5")
        self.assertEqual(process.returncode, 0, process.stderr)
        replies = [json.loads(line) for line in process.stdout.splitlines()]
        self.assertEqual(replies[0]["id"], "rules")
        self.assertTrue(all(reply["ok"] for reply in replies))
        self.assertEqual(replies[-1]["result"]["packets"][-1]["position"], [20, 20])
        self.assertNotIn('"seed"', process.stdout)
        self.assertNotIn('"slip_coefficients"', process.stdout)

    def test_private_methods_are_not_dispatchable(self):
        script = "".join(request(method) for method in
                         ("evaluate", "replay", "_step", "__dict__", "__init__"))
        process = run_cli(script)
        self.assertEqual(process.returncode, 0, process.stderr)
        replies = [json.loads(line) for line in process.stdout.splitlines()]
        self.assertEqual(len(replies), 5)
        self.assertTrue(all(not reply["ok"] for reply in replies))

    def test_malformed_requests_recover_without_mutating_clock_or_queue(self):
        invalid = ["not json\n", "[]\n", request("advance", {"ticks": True}),
                   request("advance", {"ticks": 1, "other": 3}),
                   request("uplink"), request("rules", {"seed": 0}),
                   '{"method":"uplink","params":{"commands":[{"action":"drive","heading_deg":0,"metres":NaN}]}}\n',
                   '{"method":"uplink","params":{"commands":[{"action":"drive","heading_deg":0,"metres":1e999}]}}\n',
                   '{"method":"rules","id":[]}\n',
                   '{"method":"rules","params":null}\n']
        script = "".join(invalid) + request("uplink", {"commands": [{"action": "wait"}]}) + request("advance")
        process = run_cli(script)
        self.assertEqual(process.returncode, 0, process.stderr)
        replies = [json.loads(line) for line in process.stdout.splitlines()]
        self.assertEqual(len(replies), len(invalid) + 2)
        self.assertTrue(all(not reply["ok"] for reply in replies[:-2]))
        self.assertEqual(replies[-2]["result"][0]["command_id"], 1)
        self.assertEqual(replies[-1]["result"]["current_tick"], 1)

    def test_incomplete_episode_writes_no_final_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            result, replay = Path(directory) / "result.json", Path(directory) / "replay.json"
            process = run_cli(request("advance"), "--result", str(result), "--replay", str(replay))
            self.assertEqual(process.returncode, 2)
            self.assertIn("horizon", process.stderr)
            self.assertFalse(result.exists())
            self.assertFalse(replay.exists())

    def test_over_nested_json_does_not_kill_the_session(self):
        script = "[" * 1200 + "0" + "]" * 1200 + "\n" + request("advance")
        process = run_cli(script)
        self.assertEqual(process.returncode, 0, process.stderr)
        replies = [json.loads(line) for line in process.stdout.splitlines()]
        self.assertFalse(replies[0]["ok"])
        self.assertEqual(replies[1]["result"]["current_tick"], 1)

    def test_example_has_reproducible_replay_and_score_at_both_delays(self):
        example = (ROOT / "lightlag/examples/return_to_base.jsonl").read_text()
        with tempfile.TemporaryDirectory() as directory:
            for delay in (0, 3):
                replays = []
                for repeat in range(2):
                    result = Path(directory) / f"result-{delay}-{repeat}.json"
                    replay = Path(directory) / f"replay-{delay}-{repeat}.json"
                    process = run_cli(example, "--seed", "7", "--delay", str(delay), "--ticks", "20",
                                      "--result", str(result), "--replay", str(replay))
                    self.assertEqual(process.returncode, 0, process.stderr)
                    self.assertTrue(all(json.loads(line)["ok"] for line in process.stdout.splitlines()))
                    self.assertEqual(json.loads(result.read_text())["raw_score"], 1)
                    replays.append(replay.read_text())
                self.assertEqual(replays[0], replays[1])

    def test_existing_or_shared_artifact_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "output.json"
            path.write_text("existing")
            process = run_cli("", "--result", str(path))
            self.assertEqual(process.returncode, 2)
            self.assertEqual(path.read_text(), "existing")
            shared = str(Path(directory) / "shared.json")
            process = run_cli("", "--result", shared, "--replay", shared)
            self.assertEqual(process.returncode, 2)
            self.assertFalse(Path(shared).exists())


if __name__ == "__main__":
    unittest.main()
