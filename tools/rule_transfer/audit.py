"""Reconstruct retained transfer evidence without executing a policy or model.

The replay engine is the declared simulator. Summary statistics and the screen
are recomputed here independently of the study writer. No pickle or generated
policy is loaded, and no container is started.
"""

from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
from statistics import mean

from lightlag_mcp.service import ToolError
from .runner import make_service


REPO = Path(__file__).resolve().parents[2]
POLICIES = ("saved_opus", "prepared")
KINDS = ("none", "ground", "turning", "link", "relay")
SAVED_POLICY = "docs/lightlag-runs/live-oneshot-opus-1/policy.py"


def _normal(value):
    return json.loads(json.dumps(value, sort_keys=True))


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _within(directory, relative):
    path = (directory / relative).resolve()
    path.relative_to(directory.resolve())
    return path


def _metrics(rows):
    evaluations = [row["result"]["evaluation"] for row in rows]
    return {
        "n": len(rows),
        "mean_sampled_value": mean(e["sampled_value"] for e in evaluations),
        "mean_raw_score": mean(e["raw_score"] for e in evaluations),
        "mean_normalized_score": mean(e["raw_score"] / e["max_available_value"] for e in evaluations),
        "deaths": sum(not e["alive"] for e in evaluations),
        "alive_home": sum(e["alive"] and e["at_base"] for e in evaluations),
        "statuses": dict(Counter(row["result"]["status"] for row in rows)),
        "invalid_calls": sum(row["result"]["invalid_calls"] for row in rows),
    }


def _derive(rows, count):
    summary = {}
    for policy in POLICIES:
        chosen = [r for r in rows if r["policy"] == policy]
        summary[policy] = {kind: _metrics([r for r in chosen if r["kind"] == kind]) for kind in KINDS}
        summary[policy]["changed"] = _metrics([r for r in chosen if r["kind"] != "none"])
    agent, reference = summary["saved_opus"], summary["prepared"]
    gate = {
        "all_returned": all(r["result"]["status"] == "returned" and r["result"]["invalid_calls"] == 0 for r in rows),
        "pooled_reward": agent["changed"]["mean_normalized_score"] >= reference["changed"]["mean_normalized_score"] - .05,
        "each_kind_reward": {k: agent[k]["mean_normalized_score"] >= reference[k]["mean_normalized_score"] - .10 for k in KINDS[1:]},
        "zero_deaths": agent["changed"]["deaths"] == 0,
        "pooled_home": agent["changed"]["alive_home"] >= .9625 * (4 * count),
        "each_kind_home": {k: agent[k]["alive_home"] >= .9 * count for k in KINDS[1:]},
    }
    gate["retire"] = (gate["all_returned"] and gate["pooled_reward"] and all(gate["each_kind_reward"].values())
                      and gate["zero_deaths"] and gate["pooled_home"] and all(gate["each_kind_home"].values()))
    return summary, gate


def audit(report_path):
    """Raise on an incomplete or inconsistent report; return compact audit evidence."""
    if not __debug__:
        raise RuntimeError("run this assertion-based auditor without Python -O")
    report_path = Path(report_path).resolve()
    report = json.loads(report_path.read_text())
    protocol, rows = report["protocol"], report["cases"]
    assert protocol["model_calls"] == 0, "this auditor is for the free transfer screen"
    assert tuple(protocol["kinds"]) == KINDS
    start, count = protocol["start"], protocol["count"]
    assert type(start) is int and type(count) is int and count > 0
    expected = {(p, seed, k) for p in POLICIES for seed in range(start, start + count) for k in KINDS}
    actual = [(r["policy"], r["seed"], r["kind"]) for r in rows]
    assert len(actual) == len(expected) and set(actual) == expected, "missing, duplicate or unexpected cases"
    source_hashes = protocol["source_sha256"]
    assert source_hashes, "empty source manifest"
    for relative, expected_hash in source_hashes.items():
        assert _digest(_within(REPO, relative)) == expected_hash, ("source hash", relative)
    policy_path = _within(REPO, protocol.get("policy_path", SAVED_POLICY))
    assert _digest(policy_path) == protocol["policy_sha256"], "saved policy hash"
    seen_artifacts, public_calls, invalid_calls = set(), 0, 0
    for row in rows:
        artifact = _within(report_path.parent, row["artifact"])
        assert artifact not in seen_artifacts, "reused artifact path"
        seen_artifacts.add(artifact)
        assert _digest(artifact) == row["sha256"], ("artifact hash", row["artifact"])
        bundle = json.loads(gzip.decompress(artifact.read_bytes()))
        identity = (row["policy"], row["seed"], row["kind"])
        assert tuple(bundle[k] for k in ("policy", "seed", "kind")) == identity
        saved = row["result"]
        assert bundle["result"] == saved
        assert saved["seed"] == row["seed"] and saved["kind"] == row["kind"]
        assert saved.get("model_calls", 0) == 0
        if row["policy"] == "saved_opus":
            assert saved["policy_sha256"] == protocol["policy_sha256"]
            assert saved["image_id"] == protocol["docker_image_id"], (identity, "Docker image")
            for field, source in (("runner_sha256", "tools/rule_transfer/runner.py"),
                                  ("worker_sha256", "tools/rule_transfer/worker.py")):
                assert saved[field] == source_hashes[source], (identity, field)
        service = make_service(row["seed"], row["kind"])
        rejected = 0
        for number, record in enumerate(bundle["transcript"], 1):
            reconstructed = {"n": number, "tool": record["tool"], "arguments": record["arguments"],
                             "tick_before": service._tick}
            try:
                result = service.call(record["tool"], record["arguments"])
                reconstructed.update(ok=True, result=result)
            except ToolError as error:
                rejected += 1
                reconstructed.update(ok=False, error=str(error))
            reconstructed["tick_after"] = service._tick
            assert _normal(reconstructed) == record, (identity, "public call", number)
        evaluation = service.finish()
        replay = service._env.replay()
        assert _normal(evaluation) == saved["evaluation"], (identity, "evaluation")
        assert _normal(replay) == bundle["replay"], (identity, "replay")
        assert saved["final_tick"] == evaluation["tick"] == replay["states"][-1]["tick"] == 50
        assert saved["public_calls"] == len(bundle["transcript"])
        assert saved["invalid_calls"] == rejected
        assert saved["normalized_score"] == evaluation["raw_score"] / evaluation["max_available_value"]
        public_calls += len(bundle["transcript"])
        invalid_calls += rejected
    summary, gate = _derive(rows, count)
    assert summary == report["summary"], "summary differs from independently recomputed metrics"
    assert gate == report["gate"], "gate differs from independently recomputed decision"
    return {
        "schema": "rule-transfer-audit-v1", "audit_model_calls": 0,
        "report_sha256": _digest(report_path), "source_files_verified": len(source_hashes),
        "policy_sha256": protocol["policy_sha256"], "cases_verified": len(rows),
        "public_calls_reconstructed": public_calls, "invalid_calls_reconstructed": invalid_calls,
        "full_replays_match": True, "evaluations_match": True,
        "summary_independently_recomputed": True, "gate_independently_recomputed": True,
        "gate": gate,
        "limits": "Reconstructs saved public behavior and simulator outcomes; does not re-execute generated code or independently attest the Docker runtime.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.report)
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered)
    print(rendered, end="")


if __name__ == "__main__":
    main()
