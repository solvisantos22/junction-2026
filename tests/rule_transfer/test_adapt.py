"""Adaptation state/budget boundaries using synthetic provider and evaluator only.

These tests never make API requests, start Docker, or construct mission cases.
"""

import copy
import json
from pathlib import Path
import stat
import tempfile
import unittest

from tools.rule_transfer import adapt


IMAGE_ID = "sha256:" + "1" * 64
FAKE_KEY = "test-key-never-send-this"
THINKING = "private-reasoning-sentinel"
HIDDEN = "evaluator-hidden-state-sentinel"


def response(turn, arguments=None, **updates):
    body = {
        "id": "test-response-{}".format(turn), "model": adapt.MODEL,
        "stop_reason": "tool_use", "usage": {"input_tokens": 100, "output_tokens": 100},
        "content": [
            {"type": "thinking", "thinking": THINKING, "signature": "private-signature"},
            {"type": "redacted_thinking", "data": "private-redacted-data"},
            {"type": "tool_use", "id": "test-tool-{}".format(turn),
             "name": "evaluate_policy" if turn == 1 else "submit_policy",
             "input": arguments if arguments is not None else {"code": "def play(tools):\n    pass\n"}},
        ],
    }
    body.update(updates)
    return body


class FakeProvider:
    def __init__(self, responses=None, counts=None, hook=None):
        self.responses = list(responses or [response(1), response(2)])
        self.counts = list(counts if counts is not None else [{"input_tokens": 100}] * 2)
        self.calls = []
        self.hook = hook

    def __call__(self, endpoint, payload, key):
        if key != FAKE_KEY:
            raise AssertionError("unexpected test credential")
        self.calls.append((endpoint, copy.deepcopy(payload)))
        if self.hook:
            self.hook(endpoint, payload)
        if endpoint == "/v1/messages/count_tokens":
            value = self.counts.pop(0)
        elif endpoint == "/v1/messages":
            value = self.responses.pop(0)
        else:
            raise AssertionError("unexpected endpoint")
        if isinstance(value, Exception):
            raise value
        return copy.deepcopy(value), "test-request-{}".format(len(self.calls))

    @property
    def generations(self):
        return [p for endpoint, p in self.calls if endpoint == "/v1/messages"]


class AdaptationTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="rule-adapt-tests-", dir="/tmp")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.prompt = self.root / "prompt.md"
        self.prompt.write_text("Synthetic test instructions\n" + adapt.BASE_POLICY.read_text())
        self.env = self.root / "test.env"
        self.env.write_text("ANTHROPIC_API_KEY='{}'\n".format(FAKE_KEY))
        self.evaluated = []
        self.status = "returned"

    def evaluator(self, policy_path, seed, kind, out_dir, *, image):
        self.evaluated.append((policy_path.read_text(), seed, kind, image))
        out_dir.mkdir(parents=True)
        invalid = {"n": 1, "tool": "uplink", "arguments": {"commands": []},
                   "ticks": [0, 0], "ok": False, "error": "synthetic invalid public request"}
        (out_dir / "transcript.jsonl").write_text(json.dumps(invalid) + "\n")
        return {"status": self.status, "seed": seed, "kind": kind, "private": HIDDEN,
                "evaluation": {"sampled_value": 2, "raw_score": 2, "max_available_value": 4,
                               "alive": True, "at_base": True},
                "errors": ["synthetic policy exception"]}

    def run_adaptation(self, provider=None, *, label="run", **options):
        provider = provider or FakeProvider()
        output, private = self.root / label, self.root / (label + "-private")
        report = adapt.run(self.prompt, output, private, self.env,
                           provider=provider, evaluator=self.evaluator,
                           image_resolver=lambda _: IMAGE_ID, **options)
        if not options.get("dry_run"):
            self.assertEqual(report, json.loads((output / "adaptation.json").read_text()))
        return report, output, private, provider

    def assert_incomplete(self, report, output):
        self.assertEqual(report["status"], "incomplete")
        self.assertFalse((output / "freeze.json").exists())
        self.assertFalse((output / "final-policy.py").exists())

    def test_two_responses_freeze_only_final_and_keep_private_material_out(self):
        old = "def play(tools):"
        first = {"replacements": [{"old": old, "new": old + "\n    # practice marker"}]}
        second = {"replacements": [{"old": old, "new": old + "\n    # final marker"}]}
        provider = FakeProvider([response(1, first), response(2, second)])
        report, output, private, _ = self.run_adaptation(provider)
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["model_calls"], 2)
        self.assertEqual(len(provider.generations), 2)
        self.assertEqual([(seed, kind) for _, seed, kind, _ in self.evaluated],
                         [(seed, kind) for seed in range(3200, 3204) for kind in adapt.KINDS])
        self.assertTrue(all("# practice marker" in source and image == IMAGE_ID
                            for source, _, _, image in self.evaluated))
        final_source = (output / "final-policy.py").read_text()
        self.assertIn("# final marker", final_source)
        self.assertNotIn("# practice marker", final_source)
        freeze = json.loads((output / "freeze.json").read_text())
        self.assertEqual(freeze["final_policy_sha256"], adapt.digest(output / "final-policy.py"))
        self.assertEqual(freeze["final_policy_sha256"], report["final_policy_sha256"])
        self.assertFalse(freeze["fresh_check_opened"])
        self.assertFalse(freeze["final_practice_evaluated"])
        feedback = json.loads(provider.generations[1]["messages"][-1]["content"][0]["content"])
        self.assertEqual(len(feedback["cases"]), 20)
        self.assertEqual(feedback["cases"][0]["invalid_calls"][0]["tool"], "uplink")
        self.assertNotIn(HIDDEN, json.dumps(feedback))
        self.assertTrue(all(not ({"seed", "kind", "rule_change"} & row.keys())
                            for row in feedback["cases"]))
        public_text = "\n".join(p.read_text() for p in output.rglob("*") if p.is_file())
        for private_value in (FAKE_KEY, THINKING, "private-signature", "private-redacted-data", HIDDEN):
            self.assertNotIn(private_value, public_text)
        self.assertIn(THINKING, (private / "response_1-response.json").read_text())
        self.assertEqual(stat.S_IMODE(private.stat().st_mode), 0o700)
        self.assertTrue(all(stat.S_IMODE(p.stat().st_mode) == 0o600 for p in private.iterdir()))

    def test_budget_reserves_full_generation_before_any_paid_request(self):
        provider = FakeProvider(counts=[{"input_tokens": 200_000}])
        report, output, _, _ = self.run_adaptation(provider)
        self.assert_incomplete(report, output)
        self.assertEqual(report["incomplete_reason"], "budget_reservation_limit")
        self.assertEqual(report["model_calls"], 0)
        self.assertEqual(provider.generations, [])
        self.assertGreater(report["counts"][0]["reserved_cost_usd"], 1)
        self.assertEqual(self.evaluated, [])

    def test_second_reservation_includes_actual_first_usage_without_fallback(self):
        provider = FakeProvider(
            [response(1, usage={"input_tokens": 40_000, "output_tokens": 16_000})],
            counts=[{"input_tokens": 40_000}, {"input_tokens": 70_000}])
        report, output, _, _ = self.run_adaptation(provider)
        self.assert_incomplete(report, output)
        self.assertEqual(report["incomplete_reason"], "budget_reservation_limit")
        self.assertAlmostEqual(report["total_reported_cost_usd"], .48)
        self.assertEqual(len(provider.generations), 1)
        self.assertEqual(len(self.evaluated), 20)
        self.assertTrue((output / "candidate-policy.py").exists())

    def test_invalid_or_failed_count_never_launches_generation(self):
        values = [{}, {"input_tokens": -1}, {"input_tokens": True}, {"input_tokens": 1.5},
                  adapt.ProviderError(503, "test-count-error", FAKE_KEY)]
        for index, value in enumerate(values):
            with self.subTest(value=type(value).__name__, index=index):
                provider = FakeProvider(counts=[value])
                report, output, _, _ = self.run_adaptation(provider, label="count-{}".format(index))
                self.assert_incomplete(report, output)
                self.assertEqual(provider.generations, [])
                self.assertNotIn(FAKE_KEY, json.dumps(report))

    def test_incomplete_second_response_never_falls_back_to_practice_policy(self):
        failures = [
            response(2, stop_reason="max_tokens"),
            response(2, {"code": "def play(:\n"}),
            response(2, {"replacements": [{"old": "absent sentinel", "new": ""}]}),
            response(2, model="unexpected-model"),
            response(2, content=[{"type": "text", "text": "def play(tools): pass"}]),
            adapt.ProviderError(500, "test-response-error", FAKE_KEY + THINKING),
            RuntimeError(FAKE_KEY + THINKING),
        ]
        for index, failure in enumerate(failures):
            with self.subTest(index=index):
                provider = FakeProvider([response(1), failure])
                report, output, _, _ = self.run_adaptation(provider, label="second-{}".format(index))
                self.assert_incomplete(report, output)
                self.assertEqual(len(provider.generations), 2)
                self.assertTrue((output / "candidate-policy.py").exists())
                public_text = "\n".join(p.read_text() for p in output.rglob("*") if p.is_file())
                self.assertNotIn(FAKE_KEY, public_text)
                self.assertNotIn(THINKING, public_text)

    def test_missing_invalid_or_excess_usage_stops_spending(self):
        usages = [{}, {"input_tokens": 1, "output_tokens": True},
                  {"input_tokens": -1, "output_tokens": 1},
                  {"input_tokens": 1, "output_tokens": 1, "cache_read_input_tokens": -2},
                  {"input_tokens": 1, "output_tokens": 50_000}]
        for index, usage in enumerate(usages):
            with self.subTest(usage=usage):
                provider = FakeProvider([response(1, usage=usage)])
                report, output, _, _ = self.run_adaptation(provider, label="usage-{}".format(index))
                self.assert_incomplete(report, output)
                self.assertEqual(len(provider.generations), 1)
        self.assertEqual(self.evaluated, [])

    def test_invalid_first_patch_is_retained_feedback_and_can_be_corrected_once(self):
        provider = FakeProvider([
            response(1, {"replacements": [{"old": "absent sentinel", "new": ""}]}), response(2)])
        report, output, _, _ = self.run_adaptation(provider)
        self.assertEqual(report["status"], "complete")
        self.assertEqual(self.evaluated, [])
        feedback = json.loads((output / "practice-feedback.json").read_text())
        self.assertFalse(feedback["practice_executed"])
        self.assertIn("matched 0 times", feedback["submission_error"])
        second_feedback = json.loads(provider.generations[1]["messages"][-1]["content"][0]["content"])
        self.assertEqual(second_feedback["submission_error"], feedback["submission_error"])

    def test_practice_infrastructure_failure_is_incomplete_without_second_request(self):
        self.status = "call_timeout"
        report, output, _, provider = self.run_adaptation()
        self.assert_incomplete(report, output)
        self.assertEqual(len(provider.generations), 1)
        self.assertEqual(len(self.evaluated), 1)

    def test_source_pin_drift_during_final_response_does_not_leave_final_policy(self):
        generations = []

        def drift(endpoint, payload):
            if endpoint == "/v1/messages":
                generations.append(1)
                if len(generations) == 2:
                    self.prompt.write_text(self.prompt.read_text() + "\nchanged after launch")

        report, output, _, _ = self.run_adaptation(FakeProvider(hook=drift))
        self.assert_incomplete(report, output)
        self.assertEqual(len(generations), 2)

    def test_dry_run_neither_calls_provider_nor_evaluates_or_writes_outputs(self):
        report, output, private, provider = self.run_adaptation(dry_run=True)
        self.assertEqual(report["status"], "dry_run")
        self.assertEqual(provider.calls, [])
        self.assertEqual(self.evaluated, [])
        self.assertFalse(output.exists())
        self.assertFalse(private.exists())

    def test_submission_patches_require_unique_literals_and_compile_without_execution(self):
        base = "def play(tools):\n    pass\n# duplicate\n# duplicate\n"
        bad = [
            {}, {"code": base, "replacements": []},
            {"replacements": [{"old": "missing", "new": "x"}]},
            {"replacements": [{"old": "duplicate", "new": "x"}]},
            {"replacements": [{"old": "", "new": "x"}]},
            {"code": "async def play(tools):\n    pass\n"},
            {"code": "def other(tools):\n    pass\n"},
            {"code": "def play(:\n"},
        ]
        for arguments in bad:
            with self.subTest(arguments=arguments):
                with self.assertRaises((ValueError, SyntaxError)):
                    adapt.apply_submission(base, arguments)
        marker = self.root / "must-not-execute"
        code = "from pathlib import Path\nPath({!r}).touch()\ndef play(tools):\n    pass\n".format(str(marker))
        self.assertEqual(adapt.apply_submission(base, {"code": code}), code)
        self.assertFalse(marker.exists())
        edited = adapt.apply_submission(base, {"replacements": [
            {"old": "def play(tools):", "new": "def play(agent):"},
            {"old": "def play(agent):", "new": "def play(public_tools):"}]})
        self.assertIn("def play(public_tools):", edited)

    def test_prompt_requires_exactly_one_copy_of_original(self):
        for prompt in ("omitted base", adapt.BASE_POLICY.read_text() * 2):
            self.prompt.write_text(prompt)
            with self.assertRaisesRegex(ValueError, "exactly once"):
                adapt.prepare_material(self.prompt, image_resolver=lambda _: IMAGE_ID)

    def test_provider_schema_avoids_top_level_unions_but_runtime_is_exclusive(self):
        # The real token-count endpoint rejected a top-level oneOf before any
        # generation. Mock responses alone cannot detect provider schema limits.
        for tool in adapt.TOOLS:
            with self.subTest(tool=tool["name"]):
                schema = tool["input_schema"]
                self.assertEqual(schema["type"], "object")
                self.assertFalse({"oneOf", "allOf", "anyOf"} & schema.keys())
                self.assertEqual(set(schema["properties"]), {"code", "replacements"})
        base = "def play(tools):\n    pass\n"
        self.assertEqual(adapt.apply_submission(base, {"code": base}), base)
        self.assertEqual(adapt.apply_submission(base, {"replacements": []}), base)
        for invalid in ({}, {"code": base, "replacements": []}):
            with self.subTest(arguments=invalid):
                with self.assertRaisesRegex(ValueError, "exactly code or replacements"):
                    adapt.apply_submission(base, invalid)


if __name__ == "__main__":
    unittest.main()
