"""Frozen-policy transfer screen; retain all episodes and make no model calls."""

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import gzip
import hashlib
import json
from pathlib import Path
from statistics import mean
import subprocess
import tempfile

from lightlag_shift.reference import play as prepared
from lightlag_mcp.service import ToolError
from .runner import make_service, run_case

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "docs/lightlag-runs/live-oneshot-opus-1/policy.py"
POLICY_HASH = "288279ff7a4fcc545df26526b4bb82fec33808a829494a6b356da8754831c6fe"
KINDS = ("none", "ground", "turning", "link", "relay")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def normal(value):
    return json.loads(json.dumps(value))


def reference_case(seed, kind):
    service = make_service(seed, kind)
    transcript = []

    class Tools:
        def call(self, name, arguments):
            record = {"n": len(transcript) + 1, "tool": name, "arguments": normal(arguments),
                      "tick_before": service._tick}
            try:
                result = service.call(name, arguments)
                record.update(ok=True, result=normal(result))
                return result
            except ToolError as error:
                record.update(ok=False, error=str(error))
                raise
            finally:
                record["tick_after"] = service._tick
                transcript.append(record)

        def rules(self): return self.call("rules", {})
        def map(self): return self.call("map", {})
        def telemetry_log(self): return self.call("telemetry_log", {})
        def uplink(self, commands): return self.call("uplink", {"commands": commands})
        def advance(self, ticks=1): return self.call("advance", {"ticks": ticks})

    errors = []
    try:
        prepared(Tools())
    except Exception as error:
        errors.append(type(error).__name__ + ": " + str(error))
    evaluation = normal(service.finish())
    result = {"schema": "rule-transfer-reference-v1", "seed": seed, "kind": kind,
              "status": "reference_error" if errors else "returned", "errors": errors,
              "invalid_calls": sum(not r.get("ok", False) for r in transcript),
              "public_calls": len(transcript), "evaluation": evaluation,
              "normalized_score": evaluation["raw_score"] / evaluation["max_available_value"],
              "final_tick": evaluation["tick"], "model_calls": 0}
    return {"policy": "prepared", "seed": seed, "kind": kind, "result": result,
            "transcript": transcript, "replay": normal(service._env.replay()), "stderr": ""}


def policy_case(seed, kind, scratch, image):
    directory = scratch / f"{kind}-{seed}"
    result = run_case(POLICY, seed, kind, directory, image=image)
    return {"policy": "saved_opus", "seed": seed, "kind": kind, "result": result,
            "transcript": [json.loads(line) for line in (directory / "transcript.jsonl").read_text().splitlines()],
            "replay": json.loads((directory / "replay.json").read_text()),
            "stderr": (directory / "stderr.txt").read_text(errors="replace")}


def metrics(cases):
    values = [r["result"]["evaluation"] for r in cases]
    return {"n": len(cases), "mean_sampled_value": mean(v["sampled_value"] for v in values),
            "mean_raw_score": mean(v["raw_score"] for v in values),
            "mean_normalized_score": mean(v["raw_score"] / v["max_available_value"] for v in values),
            "deaths": sum(not v["alive"] for v in values),
            "alive_home": sum(v["alive"] and v["at_base"] for v in values),
            "statuses": dict(sorted(Counter(r["result"]["status"] for r in cases).items())),
            "invalid_calls": sum(r["result"]["invalid_calls"] for r in cases)}


def summarize(cases):
    return {p: {kind: metrics([r for r in cases if r["policy"] == p and
                              (r["kind"] != "none" if kind == "changed" else r["kind"] == kind)])
                for kind in (*KINDS, "changed")} for p in ("prepared", "saved_opus")}


def gate(cases, summary):
    agent, ref = summary["saved_opus"], summary["prepared"]
    result = {
        "all_returned": all(r["result"]["status"] == "returned" and r["result"]["invalid_calls"] == 0 for r in cases),
        "pooled_reward": agent["changed"]["mean_normalized_score"] >= ref["changed"]["mean_normalized_score"] - .05,
        "each_kind_reward": {k: agent[k]["mean_normalized_score"] >= ref[k]["mean_normalized_score"] - .10 for k in KINDS[1:]},
        "zero_deaths": agent["changed"]["deaths"] == 0,
        "pooled_home": agent["changed"]["alive_home"] >= .9625 * agent["changed"]["n"],
        "each_kind_home": {k: agent[k]["alive_home"] >= .9 * agent[k]["n"] for k in KINDS[1:]},
    }
    result["retire"] = all(all(v.values()) if isinstance(v, dict) else v for v in result.values())
    return result


def run(output, start=3200, count=40, parallel=2):
    if count < 1 or parallel < 1:
        raise ValueError("count and parallel must be positive")
    if digest(POLICY) != POLICY_HASH:
        raise ValueError("the preselected saved policy changed")
    output.mkdir(parents=True, exist_ok=False)
    (output / "cases").mkdir()
    packages = ("lightlag", "lightlag_dynamic", "lightlag_controllers", "lightlag_shift", "lightlag_mcp", "tools/rule_transfer")
    sources = sorted(p for package in packages for p in (ROOT / package).rglob("*.py"))
    sources.append(ROOT / "docs/rule-transfer.md")
    image = subprocess.check_output(["docker", "image", "inspect", "python:3.12-slim", "--format", "{{.Id}}"], text=True).strip()
    report = {"schema": "rule-transfer-study-v1", "protocol": {
        "start": start, "count": count, "kinds": list(KINDS), "parallel": parallel,
        "profile": "rush_noisy", "delay": 3, "horizon": 50, "noise_level": 1.0,
        "policy_path": str(POLICY.relative_to(ROOT)), "policy_sha256": POLICY_HASH,
        "source_sha256": {str(p.relative_to(ROOT)): digest(p) for p in sources},
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "docker_image_id": image, "model_calls": 0}, "cases": []}

    def save(bundle):
        name = f"{bundle['policy']}-{bundle['kind']}-{bundle['seed']}.json.gz"
        path = output / "cases" / name
        path.write_bytes(gzip.compress(json.dumps(bundle, separators=(",", ":")).encode(), mtime=0))
        row = {k: bundle[k] for k in ("policy", "seed", "kind", "result")}
        row.update(artifact="cases/" + name, sha256=digest(path))
        report["cases"].append(row)
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        if len(report["cases"]) % 40 == 0:
            print(json.dumps({"completed": len(report["cases"]), "total": count * len(KINDS) * 2}), flush=True)

    for kind in KINDS:
        for seed in range(start, start + count):
            save(reference_case(seed, kind))
    with tempfile.TemporaryDirectory(prefix="rule-transfer-study-") as scratch:
        with ThreadPoolExecutor(max_workers=parallel) as pool:
            jobs = [pool.submit(policy_case, seed, kind, Path(scratch), image)
                    for kind in KINDS for seed in range(start, start + count)]
            for job in as_completed(jobs):
                save(job.result())
    report["cases"].sort(key=lambda r: (r["policy"], r["kind"], r["seed"]))
    # Preserve every artifact, then refuse a mixed-source performance claim.
    for name, expected in report["protocol"]["source_sha256"].items():
        if digest(ROOT / name) != expected:
            raise RuntimeError("source changed during study: " + name)
    for row in report["cases"]:
        if row["policy"] == "saved_opus":
            result = row["result"]
            if (result["policy_sha256"] != POLICY_HASH or result["image_id"] != image or
                result["worker_sha256"] != report["protocol"]["source_sha256"]["tools/rule_transfer/worker.py"] or
                result["runner_sha256"] != report["protocol"]["source_sha256"]["tools/rule_transfer/runner.py"]):
                raise RuntimeError("worker provenance changed during study")
    report["summary"] = summarize(report["cases"])
    report["gate"] = gate(report["cases"], report["summary"])
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"summary": report["summary"], "gate": report["gate"]}, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--start", type=int, default=3200)
    parser.add_argument("--count", type=int, default=40)
    parser.add_argument("--parallel", type=int, default=2)
    args = parser.parse_args()
    run(args.output, args.start, args.count, args.parallel)


if __name__ == "__main__":
    main()
