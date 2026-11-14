"""Verify retained public usage/provenance; no model or environment calls."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify():
    old = json.loads((DIRECTORY / "adaptation/adaptation.json").read_text())
    assert old["status"] == "incomplete" and old["model_calls"] == 0
    assert old["total_reported_cost_usd"] == 0 and old["usage_unknown"] is False
    path = DIRECTORY / "adaptation-v2/adaptation.json"
    report = json.loads(path.read_text())
    assert report["status"] == "incomplete" and report["model_calls"] == 1
    assert report["incomplete_reason"] == "response_1:ValueError"
    assert report["usage_unknown"] is False
    assert len(report["responses"]) == len(report["counts"]) == 1
    response = report["responses"][0]
    assert response == json.loads((path.parent / "response_1-public.json").read_text())
    assert response["model"] == "claude-opus-5-5" and response["stop_reason"] == "max_tokens"
    assert response["content"] == []
    usage = response["usage"]
    assert usage["input_tokens"] == 17914
    assert usage["output_tokens"] == usage["output_tokens_details"]["thinking_tokens"] == 16000
    assert usage["cache_creation_input_tokens"] == usage["cache_read_input_tokens"] == 0
    cost = (usage["input_tokens"] * 4 + usage["output_tokens"] * 20) / 1_000_000
    assert cost == response["reported_cost_usd"] == report["total_reported_cost_usd"] == .391656
    assert cost <= report["counts"][0]["reserved_cost_usd"] <= report["protocol"]["budget_cap_usd"]
    pins = report["protocol"]["source_sha256"]
    for name, expected in pins.items():
        assert digest(ROOT / name) == expected, name
    assert digest(path.parent / "prompt.txt") == report["protocol"]["prompt_sha256"]
    assert digest(DIRECTORY / "adaptation-prompt.md") == report["protocol"]["prompt_sha256"]
    for name in ("candidate-policy.py", "final-policy.py", "freeze.json", "practice"):
        assert not (path.parent / name).exists(), name
    assert not (DIRECTORY / "fresh").exists()
    return {"report_sha256": digest(path), "source_files_verified": len(pins),
            "generation_requests": 1, "reported_cost_usd": cost,
            "classification": "incomplete: output limit exhausted by thinking before submission",
            "candidate_produced": False, "practice_cases": 0, "fresh_cases": 0,
            "public_artifacts_contain_thinking_blocks": False,
            "limit": "Verifies retained provider-reported usage and source pins, not independent provider billing."}


if __name__ == "__main__":
    if not __debug__:
        raise RuntimeError("Run without Python -O")
    print(json.dumps(verify(), indent=2))
