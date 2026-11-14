"""Audit a frozen expedition task and protected Harbor artifacts without credentials.

Replay imports the simulator copied into the task in an isolated Python process,
never the current checkout's simulator. Reported costs and trial exceptions are
retained even when reconstruction or provenance checks fail. This is an evidence
audit, not a model-success classification or a decision-optimality test.
"""

import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys


SOURCE_COPIES = {
    "environment/Dockerfile": "harbor/lightlag/environment/Dockerfile",
    "tests/Dockerfile": "harbor/lightlag/tests/Dockerfile",
    "tests/grade.py": "harbor/lightlag/tests/grade.py",
    "environment/simulator/finish.py": "lightlag_mcp/finish.py",
    "solution/mcp_client.py": "lightlag_mcp/client.py",
    "solution/play_policy.py": "tools/expedition_experiments/play_policy.py",
    "solution/lightlag_expedition/reference.py": "lightlag_expedition/reference.py",
    "solution/lightlag_dynamic/controllers.py": "lightlag_dynamic/controllers.py",
    "solution/lightlag_dynamic/kf_mpc.py": "lightlag_dynamic/kf_mpc.py",
}
for _package, _modules in {
    "lightlag": ("__init__", "environment", "model"),
    "lightlag_dynamic": ("__init__", "environment", "missions", "tools", "controllers", "kf_mpc"),
    "lightlag_expedition": ("__init__", "environment", "model", "missions", "service", "server", "serve"),
}.items():
    for _module in _modules:
        _source = _package + "/" + _module + ".py"
        SOURCE_COPIES["environment/simulator/" + _source] = _source
UNRETAINED_SOURCE = "tools/expedition_experiments/prepare.py"


class AuditError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise AuditError(message)


def _object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key: " + key)
        result[key] = value
    return result


def _bad_constant(value):
    raise AuditError("nonfinite JSON literal: " + value)


def parse_json(text):
    value = json.loads(text, object_pairs_hook=_object, parse_constant=_bad_constant)
    # parse_constant does not catch valid JSON numeric exponents overflowing float.
    json.dumps(value, allow_nan=False)
    return value


def read_json(path):
    return parse_json(Path(path).read_text(encoding="utf-8"))


def same(actual, expected, label):
    encode = lambda value: json.dumps(value, sort_keys=True, allow_nan=False)
    require(encode(actual) == encode(expected), label + " mismatch")


def finite_number(value, label):
    require(type(value) in (int, float) and math.isfinite(value), label + " must be finite numeric")
    return value


def sha(data):
    return hashlib.sha256(data).hexdigest()


def task_digest(hashes):
    """Harbor 0.25 package digest; experiment.json is metadata outside the package."""
    payload = "".join(f"{name}\0{digest}\n" for name, digest in sorted(hashes.items()))
    return "sha256:" + sha(payload.encode())


def relative_file(root, name):
    require(isinstance(name, str), "manifest path must be a string")
    relative = PurePosixPath(name)
    require(bool(relative.parts) and not relative.is_absolute() and ".." not in relative.parts,
            "unsafe manifest path")
    path = root.joinpath(*relative.parts)
    require(root.resolve() in path.resolve().parents and not path.is_symlink(),
            "manifest path escapes snapshot or is a symlink")
    return path


def verify_task(task):
    manifest = read_json(task / "experiment.json")
    require(manifest["schema_version"] == 1, "unknown task manifest schema")
    hashes, sources = manifest["task_sha256"], manifest["source_sha256"]
    expected_sources = set(SOURCE_COPIES.values()) | {UNRETAINED_SOURCE}
    require(set(sources) == expected_sources, "source manifest inventory mismatch")
    require(set(SOURCE_COPIES) <= set(hashes), "task manifest omits copied sources")
    actual = {p.relative_to(task).as_posix() for p in task.rglob("*") if p.is_file()}
    require(actual == set(hashes) | {"experiment.json"}, "task file inventory mismatch")
    for name, digest in hashes.items():
        require(isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest), "invalid task hash")
        require(sha(relative_file(task, name).read_bytes()) == digest, "task hash mismatch: " + name)
    for target, source in SOURCE_COPIES.items():
        require(hashes[target] == sources[source], "source copy hash mismatch: " + source)
    require(isinstance(sources[UNRETAINED_SOURCE], str)
            and re.fullmatch(r"[0-9a-f]{64}", sources[UNRETAINED_SOURCE]), "invalid preparer source hash")
    return manifest, {
        "task_files_verified": len(hashes), "copied_source_files_verified": len(set(SOURCE_COPIES.values())),
        "source_hashes_declared_without_retained_bytes": [UNRETAINED_SOURCE],
        "source_commit": manifest.get("source_commit"), "source_dirty": manifest.get("source_dirty"),
        "task_digest": task_digest(hashes), "experiment_manifest_sha256": sha((task / "experiment.json").read_bytes()),
    }


def _restore_nonfinite(value):
    """Restore service evidence tags solely to reproduce rejected calls."""
    if isinstance(value, dict):
        if set(value) == {"__nonfinite_float__"}:
            label = value["__nonfinite_float__"]
            require(label in ("NaN", "Infinity", "-Infinity"), "unknown nonfinite evidence tag")
            return float(label)
        return {key: _restore_nonfinite(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_restore_nonfinite(item) for item in value]
    return value


def _reconstruct(task, artifacts):
    """Run only in the isolated worker after the parent verifies snapshot bytes."""
    simulator = (task / "environment/simulator").resolve()
    os.environ.pop("LIGHTLAG_REPO", None)
    sys.path.insert(0, str(simulator))
    from lightlag_expedition.service import ExpeditionService, ToolError

    for name, module in list(sys.modules.items()):
        if name.split(".")[0] in ("lightlag", "lightlag_dynamic", "lightlag_expedition"):
            require(simulator in Path(module.__file__).resolve().parents,
                    "simulator import escaped the frozen task: " + name)
    manifest = read_json(task / "experiment.json")
    replay, protected = read_json(artifacts / "replay.json"), read_json(artifacts / "result.json")
    settings = manifest["settings"]
    same(replay["seed"], settings["seed"], "episode seed")
    same(replay["expedition"]["mission_seed"], settings["mission_seed"], "mission seed")
    same(replay["expedition"]["visibility"], settings["visibility"], "visibility")
    same(replay["config"]["max_ticks"], settings["horizon"], "horizon")
    same(replay["config"]["delay_ticks"], settings["delay"], "delay")
    service = ExpeditionService(seed=replay["seed"], mission_seed=replay["expedition"]["mission_seed"],
                                visibility=replay["expedition"]["visibility"])
    transcript = [parse_json(line) for line in (artifacts / "transcript.jsonl").read_text().splitlines()]
    errors = 0
    for index, record in enumerate(transcript, 1):
        require(type(record["n"]) is int and record["n"] == index and type(record["ok"]) is bool,
                "invalid transcript sequence or success flag")
        # Trusted finish is not a public call. Infer closure only from its explicit
        # rejection evidence, retaining every later rejected public request.
        if not record["ok"] and record.get("error") == "episode is closed":
            service.finish()
        try:
            service.call(record["tool"], _restore_nonfinite(record["arguments"]))
        except ToolError:
            errors += 1
            require(record["ok"] is False, "unexpected tool rejection at call " + str(index))
        else:
            require(record["ok"] is True, "expected rejection missing at call " + str(index))
        same(service.transcript()[-1], record, "public call " + str(index))
    same(service.finish(), protected, "protected result")
    same(service.transcript(), transcript, "full public transcript")
    same(service._env.replay(), replay, "full hidden replay")
    same(service._env.evaluate(), replay["result"], "horizon evaluation")
    spec = importlib.util.spec_from_file_location("_frozen_expedition_grade", task / "tests/grade.py")
    grade = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(grade)
    normalized = grade.reward_from(protected)
    same(normalized, protected["reward"], "protected normalized reward")
    require(protected["max_available_value"] == 20, "normalizer differs from public all-rich total")
    require(protected["tick"] == settings["horizon"], "grade not at horizon")
    return {"public_tool_calls": len(transcript), "reproduced_tool_errors": errors,
            "graded_call_count": protected["tool_calls"],
            "post_closure_calls": len(transcript) - protected["tool_calls"],
            "raw_score": protected["raw_score"], "max_available_value": protected["max_available_value"],
            "reward": normalized, "rounded_reward": format(normalized, ".6f"),
            "protected_result": protected}


def _trial_metadata(trial, report):
    usage = trial.get("agent_result") or {}
    cost = usage.get("cost_usd")
    report["harbor"] = {"exception_info": deepcopy(trial.get("exception_info")),
                        "started_at": trial.get("started_at"), "finished_at": trial.get("finished_at"),
                        "agent_info": deepcopy(trial.get("agent_info")), "agent_result": deepcopy(usage)}
    report["reported_cost_usd"] = cost if type(cost) in (int, float) and math.isfinite(cost) and cost >= 0 else None
    if trial.get("exception_info"):
        report["issues"].append("Harbor trial has an exception; preserve as failed/censored evidence")
    if not trial.get("started_at") or not trial.get("finished_at"):
        report["issues"].append("Harbor trial is incomplete")
    info = trial.get("agent_info") or {}
    if (info.get("name") == "opencode" or info.get("model_info")) and report["reported_cost_usd"] is None:
        report["issues"].append("reported model cost is missing or invalid")


def _evidence_hashes(artifacts, trial_dir):
    paths = {"evaluator/" + name: artifacts / name
             for name in ("replay.json", "result.json", "transcript.jsonl")}
    if trial_dir is not None:
        paths.update({"harbor/" + name: trial_dir / name for name in
                      ("result.json", "lock.json", "verifier/reward.txt", "verifier/expedition-details.json")})
    return {label: sha(path.read_bytes()) for label, path in paths.items() if path.is_file()}


def audit(task_dir, artifact_dir, trial_dir=None):
    task, artifacts = Path(task_dir).resolve(), Path(artifact_dir).resolve()
    trial_dir = Path(trial_dir).resolve() if trial_dir is not None else None
    report = {"schema_version": 1, "passed": False, "issues": [], "checks": {},
              "reported_cost_usd": None, "limits": [
                  "Reproducibility and evidence consistency only; not policy optimality or model capability.",
                  "Reported usage is harness evidence, not provider billing reconciliation.",
                  "The task preparer's declared hash has no retained source bytes in this task format; copied runtime, reference and verifier source bytes are checked."]}
    trial = None
    if trial_dir is not None:
        try:
            trial = read_json(trial_dir / "result.json")
            _trial_metadata(trial, report)
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
            report["issues"].append("Harbor metadata: " + str(error))
    try:
        report["evidence_sha256"] = _evidence_hashes(artifacts, trial_dir)
        manifest, provenance = verify_task(task)
        report["provenance"] = provenance
        report["settings"] = manifest["settings"]
        report["checks"]["frozen_task_and_copied_source_hashes"] = True
        process = subprocess.run([sys.executable, "-I", "-B", str(Path(__file__).resolve()),
                                  "--worker", "--task", str(task), "--artifacts", str(artifacts)],
                                 cwd=task, env={"PATH": os.defpath}, capture_output=True, text=True, timeout=120)
        require(process.returncode == 0, "isolated reconstruction process failed")
        reconstruction = parse_json(process.stdout)
        require(reconstruction.get("passed") is True,
                "reconstruction: " + str(reconstruction.get("error", "invalid worker report")))
        evidence = reconstruction["evidence"]
        report["reconstruction"] = {key: value for key, value in evidence.items() if key != "protected_result"}
        report["checks"].update(public_calls_and_errors=True, full_hidden_replay=True,
                                horizon_score_and_normalization=True, frozen_source_import_isolation=True)
        # Recheck after replay so concurrent task edits cannot silently pass.
        _, after = verify_task(task)
        same(after, provenance, "post-reconstruction task provenance")
        if trial_dir is not None:
            lock = read_json(trial_dir / "lock.json")
            same(lock["task"]["digest"], provenance["task_digest"], "Harbor task digest")
            report["checks"]["harbor_task_digest"] = True
            text = (trial_dir / "verifier/reward.txt").read_text().strip()
            require(text == evidence["rounded_reward"], "verifier reward text mismatch")
            details = read_json(trial_dir / "verifier/expedition-details.json")
            same(details, evidence["protected_result"], "verifier details")
            require(trial is not None, "Harbor trial metadata unavailable")
            same(trial["verifier_result"]["rewards"], {"reward": float(text)}, "Harbor reward")
            require(trial.get("verifier_environment_mode") == "separate", "Harbor verifier was not separate")
            report["checks"]["verifier_details_and_harbor_reward"] = True
        else:
            report["limits"].append("No Harbor trial directory supplied: reward file, verifier details and Harbor task digest were not checked.")
        same(_evidence_hashes(artifacts, trial_dir), report["evidence_sha256"], "post-audit evidence hashes")
    except (OSError, ValueError, TypeError, KeyError, AttributeError, subprocess.SubprocessError) as error:
        report["issues"].append(str(error))
    report["passed"] = not report["issues"]
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--trial", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        try:
            report = {"passed": True, "evidence": _reconstruct(args.task, args.artifacts)}
        except Exception as error:
            report = {"passed": False, "error": type(error).__name__ + ": " + str(error)}
        print(json.dumps(report, sort_keys=True, allow_nan=False))
        return 0
    report = audit(args.task, args.artifacts, args.trial)
    text = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(text)
    print(text, end="")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
