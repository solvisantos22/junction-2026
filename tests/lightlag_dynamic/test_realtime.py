"""Real-time clock: ticks follow the wall clock, thinking costs ticks, nothing else changes.

Standard library only: a fake clock stands in for time, so these run in milliseconds.
"""

import ast
import types
import unittest
from pathlib import Path

from lightlag import Config
from lightlag_dynamic import DynamicEnvironment
from lightlag_dynamic.controllers import POLICIES
from lightlag_dynamic.realtime import RealTimeEpisodeService, patch_tool_wording
from lightlag_dynamic.serve import DynamicEpisodeService
from lightlag_mcp.service import ToolError

SPT = 5.0
REPO = Path(__file__).resolve().parents[2]


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds


class Thinking:
    """A scripted policy's tools, spending `latency` seconds before every call."""

    def __init__(self, service, clock, latency):
        self.service, self.clock, self.latency = service, clock, latency

    def _call(self, tool, arguments=None):
        self.clock.t += self.latency
        return self.service.call(tool, arguments)

    def rules(self):
        return self._call("rules")

    def map(self):
        return self._call("map")

    def telemetry_log(self):
        return self._call("telemetry_log")

    def uplink(self, commands):
        return self._call("uplink", {"commands": commands})

    def advance(self, ticks=1):
        return self._call("advance", {"ticks": ticks})


def real_time(seed=7, profile="rush_noisy", ticks=50):
    clock = FakeClock()
    service = RealTimeEpisodeService(seed=seed, seconds_per_tick=SPT, clock=clock, sleep=clock.sleep,
                                     profile=profile, config=Config(delay_ticks=3, max_ticks=ticks))
    return service, clock


def reward(service):
    result = service.finish()
    return result["raw_score"] / result["max_available_value"]


class ClockTest(unittest.TestCase):
    def test_clock_starts_at_first_call_and_runs_without_calls(self):
        service, clock = real_time()
        clock.t += 100  # harness start-up before the agent's first call costs nothing
        rules = service.rules()
        self.assertEqual(rules["clock"]["current_tick"], 0)
        self.assertEqual(rules["clock"]["seconds_per_tick"], SPT)
        clock.t += 3 * SPT + 0.1  # thinking, no calls
        self.assertEqual(service.rules()["clock"]["current_tick"], 3)
        moved = [r for r in service.transcript() if r["tool"] == "clock"]
        self.assertEqual(sum(r["arguments"]["ticks"] for r in moved), 3)

    def test_commands_are_stamped_on_arrival(self):
        service, clock = real_time()
        service.map()
        clock.t += 4 * SPT
        ack = service.uplink([{"action": "wait"}])[0]
        self.assertEqual(ack["sent_tick"], 4)
        self.assertEqual(ack["execute_tick"], 4 + 3 + 1)

    def test_advance_waits_and_returns_packets_that_arrived(self):
        service, clock = real_time()
        start = clock.t
        service.rules()
        first = service.advance(5)
        self.assertEqual(first["current_tick"], 5)
        self.assertAlmostEqual(clock.t - start, 5 * SPT)
        self.assertEqual([p["received_tick"] for p in first["packets"]], [4, 5])
        clock.t += 2 * SPT  # think; the clock runs on
        second = service.advance(1)
        self.assertEqual(second["current_tick"], 8)  # 5 + 2 thinking + 1 waited
        self.assertEqual([p["received_tick"] for p in second["packets"]], [6, 7, 8])
        agent = [r for r in service.transcript() if r["tool"] == "advance"]
        self.assertTrue(all(r["tick_before"] == r["tick_after"] for r in agent), "agent advances move no ticks")

    def test_bad_advance_is_rejected_without_waiting(self):
        service, clock = real_time()
        service.rules()
        before = clock.t
        for arguments in ({"ticks": 9}, {"ticks": True}, {"tick": 1}):
            with self.assertRaises(ToolError):
                service.call("advance", arguments)
        self.assertEqual(clock.t, before)

    def test_horizon_passes_in_real_time(self):
        service, clock = real_time()
        service.rules()
        clock.t += 60 * SPT
        self.assertEqual(service.rules()["clock"]["current_tick"], 50)
        self.assertIsNotNone(service.result)
        with self.assertRaises(ToolError):
            service.uplink([{"action": "wait"}])
        self.assertTrue(service.advance(1)["episode_complete"])

    def test_transcript_replays_from_clock_records(self):
        service, clock = real_time(seed=3)
        POLICIES["kf_mpc"](Thinking(service, clock, 0.3 * SPT))
        env = DynamicEnvironment(seed=3, config=Config(delay_ticks=3, max_ticks=50), profile="rush_noisy")
        for record in service.transcript():
            if record["tool"] == "clock":
                env.advance(record["arguments"]["ticks"])
            elif record["tool"] == "uplink" and record["ok"]:
                env.uplink(record["arguments"]["commands"])
        self.assertEqual(env.replay()["states"], service._env.replay()["states"])

    def test_tool_wording_names_the_real_time_clock(self):
        source = (REPO / "lightlag_mcp" / "server.py").read_text(encoding="utf-8")
        texts = {node.targets[0].id: ast.literal_eval(node.value) for node in ast.parse(source).body
                 if isinstance(node, ast.Assign) and len(node.targets) == 1
                 and isinstance(node.targets[0], ast.Name) and node.targets[0].id.isupper()
                 and _is_literal(node.value)}
        module = types.SimpleNamespace(**texts)
        patch_tool_wording(module, SPT)  # raises if the turn-based wording moved
        self.assertIn("real time", module.INSTRUCTIONS)
        self.assertNotIn("Only `advance` moves the clock", module.INSTRUCTIONS)
        self.assertIn("5 seconds", module.ADVANCE_DESCRIPTION)
        for name in ("RULES_DESCRIPTION", "MAP_DESCRIPTION", "TELEMETRY_DESCRIPTION"):
            self.assertNotIn("does not advance time", getattr(module, name))


def _is_literal(node):
    try:
        ast.literal_eval(node)
        return True
    except ValueError:
        return False


class ScoreTest(unittest.TestCase):
    def test_instant_controller_loses_nothing(self):
        for seed in (0, 7):
            for policy in ("kf_mpc", "open_loop"):
                with self.subTest(seed=seed, policy=policy):
                    turn_based = DynamicEpisodeService(seed=seed, profile="rush_noisy",
                                                       config=Config(delay_ticks=3, max_ticks=50))
                    POLICIES[policy](turn_based)
                    service, _ = real_time(seed=seed)
                    POLICIES[policy](service)
                    self.assertEqual(reward(service), reward(turn_based))
                    self.assertEqual(service._env.replay()["commands"], turn_based._env.replay()["commands"])

    def test_slow_thinking_costs_score(self):
        fast, slow = [], []
        for seed in range(6):
            for latency, out in ((0.0, fast), (1.0 * SPT, slow)):
                service, clock = real_time(seed=seed)
                try:
                    POLICIES["kf_mpc"](Thinking(service, clock, latency))
                except ToolError:
                    pass  # kf_mpc is not real-time aware: late uplinks near the horizon are rejected
                out.append(reward(service))
        self.assertLess(sum(slow), sum(fast))


if __name__ == "__main__":
    unittest.main()
