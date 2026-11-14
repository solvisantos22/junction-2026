"""Compare frozen original/adapted programs with Prepared; no model calls.

Fresh cases are fixed at 52000–52039. Development smoke mode is restricted to
already-consumed 3200–3239 and cannot be represented as the fresh check.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

from lightlag_mcp.service import ToolError
from .audit import _derive, _normal, _within
from .runner import make_service, run_case
from .study import ROOT, POLICY, POLICY_HASH, KINDS, gate, metrics, reference_case

POLICIES = ("original", "adapted", "prepared")
PACKAGES = ("lightlag", "lightlag_dynamic", "lightlag_controllers", "lightlag_shift", "lightlag_mcp")
DOCUMENTS = ("docs/rule-transfer.md", "docs/rule-transfer-results/adaptation-protocol.md")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_paths():
    return sorted({p for package in (*PACKAGES, "tools/rule_transfer")
                   for p in (ROOT / package).rglob("*.py")} | {ROOT / p for p in DOCUMENTS})


def freeze_inputs(policy, freeze_path, image):
    freeze = json.loads(Path(freeze_path).read_text())
    expected = freeze.get("final_policy_sha256", freeze.get("policy_sha256"))
    if (freeze.get("schema") != "rule-transfer-adaptation-freeze-v1"
            or freeze.get("status") != "complete" or freeze.get("fresh_check_opened") is not False
            or freeze.get("model") != "claude-opus-5-5"
            or freeze.get("base_policy_sha256") != POLICY_HASH
            or freeze.get("docker_image_id") != image
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", image)
            or digest(policy) != expected or digest(POLICY) != POLICY_HASH):
        raise ValueError("incomplete or mismatched policy/freeze/image; no check case opened")
    required = {str(p.relative_to(ROOT)) for package in PACKAGES for p in (ROOT / package).rglob("*.py")}
    required.update((*DOCUMENTS, "tools/rule_transfer/adapt.py", "tools/rule_transfer/runner.py", "tools/rule_transfer/worker.py"))
    hashes = freeze.get("source_sha256", {})
    if not required.issubset(hashes):
        raise ValueError("incomplete adaptation source manifest; no check case opened")
    for relative, expected_hash in hashes.items():
        if digest(_within(ROOT, relative)) != expected_hash:
            raise ValueError("adaptation source changed; no check case opened: " + relative)
    return freeze, expected


def validate_range(start, count, development):
    if type(start) is not int or type(count) is not int or count < 1:
        raise ValueError("integer start and positive count required")
    if development:
        if start < 3200 or start + count > 3240:
            raise ValueError("development smoke must use consumed seeds 3200–3239")
    elif (start, count) != (52000, 40):
        raise ValueError("the frozen fresh check is exactly seeds 52000–52039")


def mapped(rows, target):
    return [{**r, "policy": "saved_opus" if r["policy"] == target else "prepared"}
            for r in rows if r["policy"] in (target, "prepared")]


def summarize(rows):
    return {p: {k: metrics([r for r in rows if r["policy"] == p and
                           (r["kind"] != "none" if k == "changed" else r["kind"] == k)])
                for k in (*KINDS, "changed")} for p in POLICIES}


def policy_case(name, policy, seed, kind, scratch, image):
    directory = scratch / f"{name}-{kind}-{seed}"
    result = run_case(policy, seed, kind, directory, image=image)
    return {"policy": name, "seed": seed, "kind": kind, "result": result,
            "transcript": [json.loads(s) for s in (directory / "transcript.jsonl").read_text().splitlines()],
            "replay": json.loads((directory / "replay.json").read_text()),
            "stderr": (directory / "stderr.txt").read_text(errors="replace")}


def run(policy, freeze_path, output, image, start=52000, count=40, parallel=2, development=False):
    policy, freeze_path, output = Path(policy), Path(freeze_path), Path(output)
    validate_range(start, count, development)
    if type(parallel) is not int or parallel < 1:
        raise ValueError("parallel must be a positive integer")
    _, final_hash = freeze_inputs(policy, freeze_path, image)  # before any generation
    image_id = subprocess.check_output(["docker", "image", "inspect", image, "--format", "{{.Id}}"], text=True, timeout=15).strip()
    if image_id != image:
        raise ValueError("Docker resolved a different image")
    output.mkdir(parents=True, exist_ok=False)
    (output / "cases").mkdir()
    (output / "freeze.json").write_bytes(freeze_path.read_bytes())
    paths = {"original": output / "original-policy.py", "adapted": output / "final-policy.py"}
    paths["original"].write_bytes(POLICY.read_bytes())
    paths["adapted"].write_bytes(policy.read_bytes())
    freeze_inputs(paths["adapted"], output / "freeze.json", image)
    if digest(paths["original"]) != POLICY_HASH:
        raise ValueError("original policy changed while copying; no check case opened")
    sources = source_paths()
    protocol = {"split": "development-smoke" if development else "fresh-check",
                "start": start, "count": count, "parallel": parallel, "kinds": list(KINDS),
                "profile": "rush_noisy", "delay": 3, "horizon": 50, "noise_level": 1.0,
                "policies": {name: {"artifact": path.name, "sha256": digest(path)} for name, path in paths.items()},
                "freeze": {"artifact": "freeze.json", "sha256": digest(output / "freeze.json")},
                "docker_image_id": image, "final_policy_sha256": final_hash, "model_calls": 0,
                "source_sha256": {str(p.relative_to(ROOT)): digest(p) for p in sources},
                "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()}
    report = {"schema": "rule-transfer-fresh-check-v1", "protocol": protocol, "complete": False, "cases": []}

    def persist():
        temporary = output / "report.json.tmp"
        temporary.write_text(json.dumps(report, indent=2) + "\n")
        temporary.replace(output / "report.json")

    def save(bundle):
        artifact = "cases/{}-{}-{}.json.gz".format(bundle["policy"], bundle["kind"], bundle["seed"])
        path = output / artifact
        path.write_bytes(gzip.compress(json.dumps(bundle, separators=(",", ":")).encode(), mtime=0))
        report["cases"].append({**{k: bundle[k] for k in ("policy", "seed", "kind", "result")},
                                "artifact": artifact, "sha256": digest(path)})
        persist()
        if len(report["cases"]) % 60 == 0:
            print(json.dumps({"completed": len(report["cases"]), "total": count * 15}), flush=True)

    persist()  # incomplete reports are visibly incomplete even before the first case
    for kind in KINDS:
        for seed in range(start, start + count):
            save(reference_case(seed, kind))
    with tempfile.TemporaryDirectory(prefix="rule-transfer-check-") as scratch:
        with ThreadPoolExecutor(max_workers=parallel) as pool:
            jobs = [pool.submit(policy_case, name, path, seed, kind, Path(scratch), image)
                    for name, path in paths.items() for kind in KINDS for seed in range(start, start + count)]
            for job in as_completed(jobs):
                save(job.result())
    for relative, expected in protocol["source_sha256"].items():
        if digest(ROOT / relative) != expected:
            raise RuntimeError("source changed during check: " + relative)
    if {str(path.relative_to(ROOT)) for path in source_paths()} != set(protocol["source_sha256"]):
        raise RuntimeError("source file set changed during check")
    if any(digest(paths[n]) != protocol["policies"][n]["sha256"] for n in paths):
        raise RuntimeError("policy changed during check")
    if digest(output / "freeze.json") != protocol["freeze"]["sha256"]:
        raise RuntimeError("freeze changed during check")
    for row in report["cases"]:
        if row["policy"] == "prepared":
            continue
        result = row["result"]
        if (result["policy_sha256"] != protocol["policies"][row["policy"]]["sha256"]
                or result["image_id"] != image
                or any(result[field] != protocol["source_sha256"][source] for field, source in
                       (("runner_sha256", "tools/rule_transfer/runner.py"), ("worker_sha256", "tools/rule_transfer/worker.py")))):
            raise RuntimeError("worker provenance changed during check")
    report["cases"].sort(key=lambda r: (r["policy"], r["kind"], r["seed"]))
    report["summary"] = summarize(report["cases"])
    report["gate"] = gate(mapped(report["cases"], "adapted"),
                          {"saved_opus": report["summary"]["adapted"], "prepared": report["summary"]["prepared"]})
    report["complete"] = True
    persist()
    print(json.dumps({"summary": report["summary"], "gate": report["gate"]}, indent=2))
    return report


def audit(report_path):
    if not __debug__:
        raise RuntimeError("run this assertion-based auditor without Python -O")
    report_path = Path(report_path).resolve()
    report = json.loads(report_path.read_text())
    assert report["schema"] == "rule-transfer-fresh-check-v1" and report["complete"] is True
    p, rows = report["protocol"], report["cases"]
    assert p["split"] in ("fresh-check", "development-smoke")
    validate_range(p["start"], p["count"], p["split"] == "development-smoke")
    assert tuple(p["kinds"]) == KINDS and p["model_calls"] == 0
    assert (p["profile"], p["delay"], p["horizon"], p["noise_level"]) == ("rush_noisy", 3, 50, 1.0)
    expected = {(name, seed, kind) for name in POLICIES for kind in KINDS for seed in range(p["start"], p["start"] + p["count"])}
    identities = [(r["policy"], r["seed"], r["kind"]) for r in rows]
    assert len(identities) == len(expected) and set(identities) == expected, "missing/duplicate/unexpected cases"
    assert set(p["source_sha256"]) == {str(path.relative_to(ROOT)) for path in source_paths()}, "incomplete source manifest"
    for relative, hashed in p["source_sha256"].items():
        assert digest(_within(ROOT, relative)) == hashed, ("source hash", relative)
    freeze_path = _within(report_path.parent, p["freeze"]["artifact"])
    assert digest(freeze_path) == p["freeze"]["sha256"], "freeze hash"
    for name, spec in p["policies"].items():
        assert name in ("original", "adapted")
        assert digest(_within(report_path.parent, spec["artifact"])) == spec["sha256"], ("policy hash", name)
    assert p["policies"]["original"]["sha256"] == POLICY_HASH
    _, final_hash = freeze_inputs(_within(report_path.parent, p["policies"]["adapted"]["artifact"]), freeze_path, p["docker_image_id"])
    assert final_hash == p["final_policy_sha256"] == p["policies"]["adapted"]["sha256"]
    seen, call_count = set(), 0
    for row in rows:
        path = _within(report_path.parent, row["artifact"])
        assert path not in seen and digest(path) == row["sha256"], "reused or changed artifact"
        seen.add(path)
        bundle = json.loads(gzip.decompress(path.read_bytes()))
        assert all(bundle[k] == row[k] for k in ("policy", "seed", "kind", "result"))
        result = row["result"]
        assert result["seed"] == row["seed"] and result["kind"] == row["kind"] and result["model_calls"] == 0
        if row["policy"] != "prepared":
            assert result["policy_sha256"] == p["policies"][row["policy"]]["sha256"]
            assert result["image_id"] == p["docker_image_id"]
            for field, source in (("runner_sha256", "tools/rule_transfer/runner.py"), ("worker_sha256", "tools/rule_transfer/worker.py")):
                assert result[field] == p["source_sha256"][source]
        service, rejected = make_service(row["seed"], row["kind"]), 0
        for number, record in enumerate(bundle["transcript"], 1):
            reconstructed = {"n": number, "tool": record["tool"], "arguments": record["arguments"], "tick_before": service._tick}
            try:
                reconstructed.update(ok=True, result=service.call(record["tool"], record["arguments"]))
            except ToolError as error:
                rejected += 1
                reconstructed.update(ok=False, error=str(error))
            reconstructed["tick_after"] = service._tick
            assert _normal(reconstructed) == record, "public call mismatch"
        evaluation = _normal(service.finish())
        assert evaluation == result["evaluation"] and _normal(service._env.replay()) == bundle["replay"], "grade/replay mismatch"
        assert result["final_tick"] == evaluation["tick"] == 50
        assert result["public_calls"] == len(bundle["transcript"]) and result["invalid_calls"] == rejected
        assert result["normalized_score"] == evaluation["raw_score"] / evaluation["max_available_value"]
        call_count += len(bundle["transcript"])
    derived = {}
    for name in ("original", "adapted"):
        summary, decision = _derive(mapped(rows, name), p["count"])
        derived[name], derived["prepared"] = summary["saved_opus"], summary["prepared"]
        if name == "adapted":
            assert decision == report["gate"], "gate mismatch"
    assert derived == report["summary"], "summary mismatch"
    return {"schema": "rule-transfer-fresh-audit-v1", "report_sha256": digest(report_path),
            "split": p["split"], "cases_verified": len(rows), "public_calls_reconstructed": call_count,
            "source_files_verified": len(p["source_sha256"]), "full_replays_match": True,
            "summary_and_gate_independently_recomputed": True, "audit_model_calls": 0,
            "gate": report["gate"], "limits": "Reconstructs saved behavior; does not independently attest Docker or model generation."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--freeze", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--image")
    parser.add_argument("--start", type=int, default=52000)
    parser.add_argument("--count", type=int, default=40)
    parser.add_argument("--parallel", type=int, default=2)
    parser.add_argument("--development", action="store_true")
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--audit-output", type=Path)
    args = parser.parse_args()
    if args.audit:
        result = audit(args.audit)
        text = json.dumps(result, indent=2) + "\n"
        if args.audit_output:
            args.audit_output.write_text(text)
        print(text, end="")
    else:
        if not all((args.policy, args.freeze, args.output, args.image)):
            parser.error("--policy, --freeze, --output and immutable --image are required")
        run(args.policy, args.freeze, args.output, args.image, args.start, args.count, args.parallel, args.development)


if __name__ == "__main__":
    main()
