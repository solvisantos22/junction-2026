"""No network: fake provider exercises the single-request state machine."""

import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from tools.lightlag_experiments import overnight_synthesis as base

SPEC = importlib.util.find_spec("tools.lightlag_experiments.overnight_synthesis_api")
if SPEC:
    from tools.lightlag_experiments import overnight_synthesis_api as api
else:
    api = None


class Payload:
    def __init__(self, data):
        self.data = data
        self.input_tokens = data.get("input_tokens")
        self._request_id = "count-fixture"

    def model_dump(self, **kwargs):
        return self.data


class FakeStream:
    request_id = "stream-fixture"

    def __init__(self, message, error=None):
        self.message, self.error = message, error

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def __iter__(self):
        yield Payload({"type": "content_block_delta", "delta": {"type": "text_delta", "text": "partial fixture"}})
        if self.error:
            raise self.error
        yield Payload({"type": "message_stop"})

    def get_final_message(self):
        return Payload(self.message)


class FakeProvider:
    def __init__(self, tokens=100, message=None, error=None):
        self.messages = self
        self.tokens, self.error = tokens, error
        self.message = message or {"id": "message-fixture", "model": "claude-opus-5-5", "stop_reason": "end_turn",
                                  "content": [{"type": "text", "text": "```python\ndef play(tools):\n    return None\n```\n"}],
                                  "usage": {"input_tokens": 100, "output_tokens": 40,
                                            "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}}
        self.count_calls, self.stream_calls = [], []

    def count_tokens(self, **kwargs):
        self.count_calls.append(kwargs)
        return Payload({"input_tokens": self.tokens})

    def stream(self, **kwargs):
        self.stream_calls.append(kwargs)
        return FakeStream(self.message, self.error)


class ApiGuards(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(api, "bounded root-only API phase is not implemented")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name)
        self.request = base.read_json(REPO / "docs/lightlag-runs/overnight-synthesis/preparation-v1/request.json")

    def perform(self, client):
        return api.perform_request(base, self.request, self.output, {"cumulative_reported_usd": 9.4355068}, client)

    def test_allowance_and_reservation_boundaries(self):
        priced = api.price_preflight(101, 9.4355068)
        self.assertEqual(priced["allowed_input_tokens"], 1127)
        self.assertAlmostEqual(priced["maximum_calculated_usd"], 0.484508)
        for tokens, cumulative in [(None, 1), (-1, 1), (True, 1), (1000000, 1), (100, 12), (100, 15.0)]:
            with self.assertRaises(base.GuardError):
                api.price_preflight(tokens, cumulative)

    def test_exactly_one_count_and_response_with_verbatim_text(self):
        client = FakeProvider()
        result = self.perform(client)
        self.assertEqual(len(client.count_calls), 1)
        self.assertEqual(len(client.stream_calls), 1)
        self.assertEqual(client.stream_calls[0], self.request)
        self.assertNotIn("max_tokens", client.count_calls[0])
        self.assertTrue(result["evaluation_eligible"])
        self.assertEqual((self.output / "response-text.txt").read_text(), client.message["content"][0]["text"])
        self.assertEqual((self.output / "policy.py").read_text(), "def play(tools):\n    return None")
        self.assertAlmostEqual(result["calculated_provider_usage_cost_usd"], 0.0012)

    def test_excessive_count_prevents_any_generation(self):
        client = FakeProvider(tokens=1000000)
        result = self.perform(client)
        self.assertEqual(len(client.count_calls), 1)
        self.assertEqual(len(client.stream_calls), 0)
        self.assertFalse(result["evaluation_eligible"])
        self.assertEqual(result["status"], "budget_preflight_failed")
        self.assertIsNone(result["calculated_provider_usage_cost_usd"])
        self.assertEqual(len(result["unrun_cells"]), 40)

    def test_provider_error_preserves_partial_response_without_retry_or_secret(self):
        client = FakeProvider(error=RuntimeError("fake-secret-value-do-not-publish"))
        result = self.perform(client)
        self.assertEqual(len(client.stream_calls), 1)
        self.assertEqual(result["status"], "provider_error")
        self.assertTrue(result["usage_unknown"])
        self.assertIn("partial fixture", (self.output / "stream-events.jsonl").read_text())
        self.assertNotIn("fake-secret-value-do-not-publish", json.dumps(result))

    def test_truncated_or_invalid_response_is_retained_without_repair(self):
        for stop, content in [("max_tokens", "def play(tools):\n    return None"), ("end_turn", "def play(:")]:
            child = self.output / stop
            child.mkdir()
            provider = FakeProvider()
            provider.message["stop_reason"] = stop
            provider.message["content"][0]["text"] = content
            result = api.perform_request(base, self.request, child, {"cumulative_reported_usd": 9.4355068}, provider)
            self.assertFalse(result["evaluation_eligible"])
            self.assertEqual((child / "policy.py").read_text(), content)
            self.assertEqual(len(result["unrun_cells"]), 40)
            self.assertAlmostEqual(result["calculated_provider_usage_cost_usd"], 0.0012)
            self.assertFalse(result["usage_unknown"])

    def test_unknown_usage_and_cache_charges_stop(self):
        provider = FakeProvider()
        provider.message["usage"]["cache_creation_input_tokens"] = 10
        result = self.perform(provider)
        self.assertEqual(result["status"], "usage_or_price_unverified")
        self.assertFalse(result["evaluation_eligible"])
        self.assertIsNone(result["calculated_provider_usage_cost_usd"])

    def test_sdk_constructs_with_fake_key_without_environment_auth_or_requests(self):
        self.assertTrue(hasattr(api, "make_client"), "explicit SDK construction is not implemented")
        client = api.make_client("offline-fixture-not-a-real-key")
        try:
            self.assertEqual(client.max_retries, 0)
            self.assertEqual(str(client.base_url), "https://api.anthropic.com")
            self.assertEqual(client.api_key, "offline-fixture-not-a-real-key")
            self.assertIsNone(client.credentials)
        finally:
            client.close()

    def test_custom_header_environment_is_rejected_without_reading_its_value(self):
        with patch.dict(os.environ, {"ANTHROPIC_CUSTOM_HEADERS": "Authorization: synthetic-test-only"}):
            with self.assertRaises(base.GuardError):
                api.make_client("offline-fixture-not-a-real-key")

    def test_actual_sdk_eof_without_terminal_event_has_unknown_usage(self):
        # Fully local HTTP mock: no endpoint is contacted and no real credentials.
        import anthropic
        import httpx2
        events = [
            {"type": "message_start", "message": {"id": "fixture-eof", "type": "message", "role": "assistant", "content": [],
              "model": "claude-opus-5-5", "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens": 100, "output_tokens": 1}}},
            {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
            {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "def play(tools): return None"}},
            {"type": "content_block_stop", "index": 0},
        ]
        def handle(request):
            if request.url.path.endswith("count_tokens"):
                return httpx2.Response(200, json={"input_tokens": 100})
            payload = "".join("event: " + e["type"] + "\ndata: " + json.dumps(e) + "\n\n" for e in events)
            return httpx2.Response(200, headers={"content-type": "text/event-stream", "request-id": "mock-eof"}, text=payload)
        client = anthropic.Anthropic(api_key="offline-fixture-not-a-real-key", webhook_key="", max_retries=0,
                                     base_url="https://api.anthropic.com", open_telemetry=False,
                                     http_client=httpx2.Client(transport=httpx2.MockTransport(handle), trust_env=False))
        try:
            result = self.perform(client)
        finally:
            client.close()
        self.assertEqual(result["status"], "provider_error")
        self.assertTrue(result["usage_unknown"])
        self.assertIsNone(result["calculated_provider_usage_cost_usd"])
        self.assertFalse(result["evaluation_eligible"])
        self.assertIn("def play", (self.output / "stream-events.jsonl").read_text())

    def test_actual_cost_overrun_is_known_but_blocks_evaluation(self):
        provider = FakeProvider()
        provider.message["usage"].update(input_tokens=200000, output_tokens=24000)
        result = self.perform(provider)
        self.assertEqual(result["status"], "actual_cost_overrun")
        self.assertFalse(result["evaluation_eligible"])
        self.assertFalse(result["usage_unknown"])
        self.assertAlmostEqual(result["calculated_provider_usage_cost_usd"], 1.28)
        self.assertTrue((self.output / "response.json").exists())


if __name__ == "__main__":
    unittest.main()
