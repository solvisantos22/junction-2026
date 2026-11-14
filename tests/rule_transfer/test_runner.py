"""Integration checks for the frozen-policy broker; real Docker, no model calls.

Only temporary synthetic policies are executed. Docker tests skip when the
declared local image is unavailable; the experiment preflight must actually run
them, not count skips as verification.
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from unittest.mock import patch

from lightlag import Config
from lightlag_dynamic.environment import DynamicEnvironment
from lightlag_mcp.service import EpisodeService
from lightlag_shift.rule_change import RuleChangeEnvironment
from tools.rule_transfer.runner import run_case


IMAGE = "python:3.12-slim"


def normalized(value):
    return json.loads(json.dumps(value))


class RunnerIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("docker"):
            raise unittest.SkipTest("Docker is required for the actual broker checks")
        ready = subprocess.run(
            ["docker", "image", "inspect", IMAGE], capture_output=True, timeout=20,
        )
        if ready.returncode:
            raise unittest.SkipTest("The declared Docker image must already be installed")

    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="rule-transfer-tests-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)

    def run_policy(self, source, *, kind="ground", label="case", **options):
        policy = self.root / f"{label}.py"
        policy.write_text(textwrap.dedent(source), encoding="utf-8")
        output = self.root / label
        result = run_case(policy, 3200, kind, output, image=IMAGE, **options)
        self.assertEqual(json.loads((output / "result.json").read_text()), result)
        replay = json.loads((output / "replay.json").read_text())
        transcript = [json.loads(line) for line in (output / "transcript.jsonl").read_text().splitlines()]
        self.assertEqual(result["final_tick"], 50)
        self.assertEqual(replay["states"][-1]["tick"], 50)
        self.assertEqual(result["model_calls"], 0)
        return result, replay, transcript

    def assert_container_removed(self, name):
        checked = subprocess.run(
            ["docker", "inspect", name], capture_output=True, timeout=15,
        )
        self.assertNotEqual(checked.returncode, 0, "episode container survived cleanup")

    def test_scripted_public_actions_match_direct_episode(self):
        actions = [
            ("rules", {}), ("map", {}),
            ("uplink", {"commands": [{"action": "drive", "heading_deg": 30, "metres": 2}]}),
            ("advance", {"ticks": 5}), ("telemetry_log", {}),
            ("uplink", {"commands": [{"action": "sample"}]}),
            ("advance", {"ticks": 5}),
        ]
        source = "def play(tools):\n"
        for method, arguments in actions:
            source += f"    tools.{method}(**{arguments!r})\n"
        for kind in ("none", "ground"):
            with self.subTest(kind=kind):
                result, replay, transcript = self.run_policy(source, kind=kind, label=kind)
                config = Config(delay_ticks=3, max_ticks=50)
                service = EpisodeService(seed=3200, config=config)
                service._env = (
                    DynamicEnvironment(seed=3200, config=config, profile="rush_noisy")
                    if kind == "none" else
                    RuleChangeEnvironment(seed=3200, config=config, profile="rush_noisy", kind=kind)
                )
                observed = []
                for method, arguments in actions:
                    observed.append(normalized(service.call(method, arguments)))
                self.assertEqual(result["status"], "returned")
                self.assertEqual(result["evaluation"], normalized(service.finish()))
                self.assertEqual(replay, normalized(service._env.replay()))
                self.assertEqual([record["result"] for record in transcript], observed)
                self.assertEqual([record["tool"] for record in transcript], [a[0] for a in actions])
                self.assert_container_removed(result["container_name"])

    def test_policy_gets_only_public_environment_and_isolated_files(self):
        sentinel = self.root / "private-evaluator-sentinel.txt"
        sentinel.write_text("synthetic test data; not a real secret")
        source = f"""
        import importlib.util
        import json
        import os
        from pathlib import Path

        def play(tools):
            assert not Path({str(sentinel)!r}).exists()
            assert importlib.util.find_spec('lightlag_shift') is None
            assert 'JUNCTION_FAKE_PRIVATE_TEST_VALUE' not in os.environ
            assert not hasattr(tools, '_env')
            rules = tools.rules()
            assert set(rules['rule_change']['one_of']) == {{'ground', 'turning', 'link', 'relay'}}
            public = [rules, tools.map(), tools.telemetry_log()]
            def check(value):
                if isinstance(value, dict):
                    assert not ({{'seed', 'slip_coefficients', 'loss_probability_realized', 'kind'}} & set(value))
                    for item in value.values():
                        check(item)
                elif isinstance(value, list):
                    for item in value:
                        check(item)
            check(public)
            try:
                Path('/policy-root-write-test').write_text('test')
            except OSError:
                pass
            else:
                raise AssertionError('container root was writable')
        """
        with patch.dict(os.environ, {"JUNCTION_FAKE_PRIVATE_TEST_VALUE": "do-not-forward"}):
            result, _, _ = self.run_policy(source)
        self.assertEqual(result["status"], "returned", result)
        self.assertEqual(result["invalid_calls"], 0)

    def test_deliberation_does_not_advance_the_simulation(self):
        result, _, transcript = self.run_policy("""
            import time
            def play(tools):
                before = tools.telemetry_log()
                time.sleep(0.3)
                assert tools.telemetry_log() == before
                assert tools.advance(1)['current_tick'] == 1
            """)
        self.assertEqual(result["status"], "returned")
        self.assertEqual([(r["tick_before"], r["tick_after"]) for r in transcript], [(0, 0), (0, 0), (0, 1)])

    def test_policy_exception_preserves_failure_and_finishes_horizon(self):
        result, replay, _ = self.run_policy("""
            def play(tools):
                tools.uplink([{'action': 'drive', 'heading_deg': 0, 'metres': 1}])
                raise RuntimeError('synthetic-policy-failure')
            """)
        self.assertEqual(result["status"], "policy_error")
        self.assertIn("synthetic-policy-failure", json.dumps(result["errors"]))
        self.assertEqual(len(replay["commands"]), 1)
        self.assertNotEqual(replay["states"][0]["position"], replay["states"][4]["position"])
        self.assert_container_removed(result["container_name"])

    def test_caught_invalid_tool_call_is_not_reported_as_success(self):
        result, _, transcript = self.run_policy("""
            def play(tools):
                try:
                    tools.advance(0)
                except ValueError:
                    pass
            """)
        self.assertEqual(result["status"], "invalid_calls")
        self.assertEqual(result["invalid_calls"], 1)
        self.assertFalse(transcript[0]["ok"])
        self.assertEqual(transcript[0]["tick_after"], 0)
        self.assert_container_removed(result["container_name"])

    def test_timeout_is_distinct_from_policy_failure_and_cleans_up(self):
        result, _, _ = self.run_policy("""
            import time
            def play(tools):
                tools.rules()
                time.sleep(20)
            """, call_timeout=1.0, run_timeout=10.0)
        self.assertEqual(result["status"], "call_timeout")
        self.assert_container_removed(result["container_name"])

    def test_free_tool_loop_hits_explicit_call_cap(self):
        result, _, transcript = self.run_policy("""
            def play(tools):
                while True:
                    tools.rules()
            """, call_cap=5)
        self.assertEqual(result["status"], "call_cap")
        self.assertEqual(result["public_calls"], 5)
        self.assertEqual(len(transcript), 5)
        self.assert_container_removed(result["container_name"])

    def test_cleanup_failure_keeps_grade_and_is_a_container_error(self):
        real_run = subprocess.run

        def remove_then_report_timeout(command, *args, **kwargs):
            completed = real_run(command, *args, **kwargs)
            if command[:3] == ["docker", "rm", "-f"]:
                # Actually remove the synthetic container, then simulate the
                # cleanup transport failing so this check never leaks one.
                raise subprocess.TimeoutExpired(command, kwargs.get("timeout", 15))
            return completed

        with patch("subprocess.run", side_effect=remove_then_report_timeout):
            result, _, _ = self.run_policy("def play(tools):\n    tools.rules()\n")
        self.assertEqual(result["status"], "container_error")
        self.assertTrue(result["errors"])
        self.assertEqual(result["public_calls"], 1)
        self.assert_container_removed(result["container_name"])


if __name__ == "__main__":
    unittest.main()
