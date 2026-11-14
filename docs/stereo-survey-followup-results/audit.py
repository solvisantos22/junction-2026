"""Reproduce retained stereo pilot metrics without executing generated programs.

Run from the repository root:
  python3 docs/stereo-survey-followup-results/audit.py
"""

from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from stereo_survey.mission import generate
from stereo_survey.verify import verify
from tools.stereo_survey_experiments.pilot import check_bundle, extract_program


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    bundle = Path(__file__).resolve().parent / "pilot-02"
    protocol = check_bundle(bundle)
    protocol_hash = sha((bundle / "protocol.json").read_bytes())
    preflight = json.loads((bundle / "preflight.json").read_text())
    assert preflight["passed"] and preflight["protocol_sha256"] == protocol_hash
    expected_cases = [(profile, seed) for profile in protocol["check"]["profiles"]
                      for seed in range(protocol["check"]["start"],
                                        protocol["check"]["start"] + protocol["check"]["count"])]
    output = {"protocol_sha256": protocol_hash, "attempts": {}, "total_reported_cost_usd": 0}
    for attempt in protocol["attempts"]:
        directory = bundle / "attempts" / attempt["id"]
        started = json.loads((directory / "started.json").read_text())
        meta = json.loads((directory / "meta.json").read_text())
        response = (directory / "response.md").read_bytes()
        assert sha(response) == meta["response_sha256"]
        assert sha((bundle / attempt["prompt"]).read_bytes()) == started["prompt_sha256"]
        assert started["model"] == meta["served_model"] == protocol["model"]
        assert started["max_tokens"] == protocol["max_tokens"]
        assert started["effort"] == protocol["effort"]
        if "policy_sha256" in meta:
            code = (directory / "policy.py").read_bytes()
            assert sha(code) == meta["policy_sha256"]
            assert extract_program(response.decode()).encode() == code
        else:
            assert "extraction_error" in meta
        usage = meta["usage"]
        assert usage.get("cache_creation_input_tokens", 0) == 0
        assert usage.get("cache_read_input_tokens", 0) == 0
        assert usage.get("speed", "standard") == "standard"
        assert usage.get("inference_geo", "global") == "global"
        assert usage["output_tokens"] <= started["max_tokens"]
        prices = protocol["prices_per_million"]
        cost = (usage["input_tokens"] * prices["input"] + usage["output_tokens"] * prices["output"]) / 1_000_000
        assert abs(cost - meta["cost_usd"]) < 1e-12
        assert cost <= started["request_reserve_usd"] + 0.01
        output["total_reported_cost_usd"] += cost

        report = json.loads((directory / "evaluation.json").read_text())
        assert report["protocol_sha256"] == protocol_hash
        assert report["policy_sha256"] == meta.get("policy_sha256")
        assert [(case["profile"], case["seed"]) for case in report["cases"]] == expected_cases
        for case in report["cases"]:
            mission = generate(case["seed"], case["profile"])
            assert mission == case["mission"]
            reference = case["reference"]
            replay = verify(mission, reference["plan"])
            assert replay == reference["replay"]
            assert replay["valid"] and replay["science"] == reference["science"] > 0
            assert reference["proven_optimal"]
            execution = case["execution"]
            if execution["status"] == "ok":
                assert json.loads(execution["stdout"]) == execution["plan"]
                submitted = verify(mission, execution["plan"])
            else:
                submitted = {"valid": False, "science": 0, "errors": [execution["status"]]}
            assert submitted == case["replay"]
            assert 0 <= submitted["science"] <= reference["science"]
            assert case["fraction_of_optimum"] == submitted["science"] / reference["science"]
        summaries = {}
        for profile in protocol["check"]["profiles"]:
            cases = [case for case in report["cases"] if case["profile"] == profile]
            scores = [case["fraction_of_optimum"] for case in cases]
            summaries[profile] = {"count": len(cases), "certified_nonzero": len(cases),
                                  "mean_fraction": sum(scores) / len(scores),
                                  "optimal": sum(score == 1 for score in scores),
                                  "valid": sum(case["replay"]["valid"] for case in cases)}
        assert summaries == report["summary"]
        output["attempts"][attempt["id"]] = {
            "summary": summaries, "cost_usd": cost, "usage": usage,
            "stop_reason": meta["stop_reason"],
            "execution_statuses": dict(Counter(case["execution"]["status"] for case in report["cases"])),
            "max_execution_seconds": max(case["execution"].get("seconds", 0) for case in report["cases"]),
        }
    assert output["total_reported_cost_usd"] <= protocol["proposed_budget_usd"]
    output["unique_missions"] = len(expected_cases)
    output["model_case_records"] = len(expected_cases) * len(protocol["attempts"])
    output["passed"] = True
    (bundle / "audit.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
