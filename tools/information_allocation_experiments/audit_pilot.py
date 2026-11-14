#!/usr/bin/env python3
"""Audit the exported six-context information-allocation pilot without network or model calls.

Run from a checkout containing the commits named in the task manifests. Replay
uses those committed simulator sources, not imports from the current worktree.
Smoke controls are reported separately and excluded from the 24-run gate.
"""

import argparse
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import math
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile


REPO = Path(__file__).resolve().parents[2]
CONTEXTS = tuple("case_" + str(i) for i in range(1, 7))
REPEATS = (1, 2)
PLANNED_MODELS = len(CONTEXTS) * len(REPEATS)
PLANNED_RUNS = 2 * PLANNED_MODELS
SOURCE_COPIES = {
    "environment/Dockerfile": "harbor/lightlag/environment/Dockerfile",
    "tests/Dockerfile": "harbor/lightlag/tests/Dockerfile",
    "tests/grade.py": "harbor/lightlag/tests/grade.py",
    "environment/simulator/finish.py": "lightlag_mcp/finish.py",
    "solution/mcp_client.py": "lightlag_mcp/client.py",
    "solution/play_policy.py": "tools/information_allocation_experiments/play_policy.py",
    "solution/lightlag_information_allocation/policies.py": "lightlag_information_allocation/policies.py",
    **{"environment/simulator/lightlag_information_allocation/" + name:
       "lightlag_information_allocation/" + name for name in
       ("__init__.py", "environment.py", "model.py", "service.py", "server.py", "serve.py")},
}
SOURCE_PATHS = set(SOURCE_COPIES.values()) | {"tools/information_allocation_experiments/prepare.py"}


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
    raise AuditError("nonfinite JSON number: " + value)


def parse_json(text):
    return json.loads(text, object_pairs_hook=_object, parse_constant=_bad_constant)


def read_json(path):
    return parse_json(path.read_text(encoding="utf-8"))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def same(actual, expected, label):
    # Canonical JSON distinguishes booleans from integers, unlike Python ==.
    encode = lambda value: json.dumps(value, sort_keys=True, allow_nan=False)
    require(encode(actual) == encode(expected), label + " mismatch")


def finite_number(value, label):
    require(type(value) in (int, float) and math.isfinite(value), label + " must be a finite number")
    return value


def config_subset(actual, specified, label="Harbor embedded/exported config"):
    # Harbor's result expands Pydantic defaults; config.json omits defaults.
    if isinstance(specified, dict):
        require(isinstance(actual, dict), label + " mismatch")
        for key, value in specified.items():
            require(key in actual, label + " missing field: " + key)
            config_subset(actual[key], value, label + "." + key)
    else:
        same(actual, specified, label)


def relative_file(root, name):
    require(isinstance(name, str), "file path must be a string")
    relative = PurePosixPath(name)
    require(not relative.is_absolute() and bool(relative.parts)
            and ".." not in relative.parts, "unsafe relative path")
    path = root.joinpath(*relative.parts)
    require(root.resolve() in path.resolve().parents, "file path escapes evidence directory")
    require(not path.is_symlink(), "symlinked evidence file")
    return path


def committed_sources(manifest, cache):
    commit = manifest["source_commit"]
    require(isinstance(commit, str) and re.fullmatch(r"[0-9a-f]{40,64}", commit), "invalid source commit")
    require(manifest["source_dirty"] is False, "pilot task was generated from dirty source")
    hashes = manifest["source_sha256"]
    require(set(hashes) == SOURCE_PATHS, "source manifest has missing or unexpected paths")
    sources = {}
    for name, expected in hashes.items():
        key = (commit, name)
        if key not in cache:
            process = subprocess.run(["git", "show", commit + ":" + name], cwd=REPO,
                                     capture_output=True, check=False)
            require(process.returncode == 0, "committed source unavailable: " + name)
            cache[key] = process.stdout
        sources[name] = cache[key]
        require(digest(sources[name]) == expected, "committed source hash mismatch: " + name)
    return sources


@contextmanager
def pinned_modules(sources, directory):
    package = directory / "source"
    package.mkdir()
    for name in ("__init__.py", "environment.py", "model.py", "service.py"):
        (package / name).write_bytes(sources["lightlag_information_allocation/" + name])
    name = "_information_allocation_pilot_audit"
    require(not any(key == name or key.startswith(name + ".") for key in sys.modules),
            "audit module namespace is already in use")
    spec = importlib.util.spec_from_file_location(name, package / "__init__.py",
                                                submodule_search_locations=[str(package)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
        service = __import__(name + ".service", fromlist=["InformationService"])
        model = __import__(name + ".model", fromlist=["Context"])
        yield service, model
    finally:
        for key in list(sys.modules):
            if key == name or key.startswith(name + "."):
                del sys.modules[key]


def replay_run(run, manifest, sources):
    evaluator = run / "artifacts/evaluator"
    replay = read_json(evaluator / "replay.json")
    protected = read_json(evaluator / "result.json")
    transcript = [parse_json(line) for line in
                  (evaluator / "transcript.jsonl").read_text(encoding="utf-8").splitlines()]
    settings = manifest["settings"]
    same(replay["seed"], settings["seed"], "replay seed")
    require(replay["context"]["id"] == settings["context"], "replay context mismatch")
    with tempfile.TemporaryDirectory(prefix="information-allocation-audit-") as temporary:
        directory = Path(temporary)
        with pinned_modules(sources, directory) as (service_module, model):
            context = model.Context(**replay["context"])
            require(context == model.CONTEXTS[settings["context"]], "replay uses modified context parameters")
            service = service_module.InformationService(replay["seed"], context, directory / "evaluator")
            for index, record in enumerate(transcript, 1):
                require(record["n"] == index and type(record["ok"]) is bool,
                        "invalid transcript sequence or success flag")
                try:
                    service.call(record["tool"], record["arguments"])
                except service_module.ToolError:
                    require(record["ok"] is False, "unexpected tool rejection at call " + str(index))
                else:
                    require(record["ok"] is True, "expected tool rejection missing at call " + str(index))
                same(service.transcript()[-1], record, "service call " + str(index))
            same(service.finish(), protected, "reconstructed protected result")
            same(service.transcript(), transcript, "reconstructed service transcript")
            same(read_json(directory / "evaluator/replay.json"), replay, "reconstructed hidden replay")
            same(read_json(directory / "evaluator/result.json"), protected, "saved protected result")
    raw = finite_number(protected["raw_score"], "raw score")
    available = finite_number(protected["max_available_value"], "maximum score")
    require(available > 0 and 0 <= raw <= available, "invalid protected score range")
    normalized = raw / available
    details = read_json(run / "verifier/information-details.json")
    same(details, dict(protected, reward=normalized), "verifier detail")
    reward = float((run / "verifier/reward.txt").read_text(encoding="utf-8").strip())
    finite_number(reward, "verifier reward")
    require(reward == float(format(normalized, ".6f")), "verifier reward mismatch")
    return protected, reward, sum(record["ok"] is False for record in transcript)


def verify_export(pilot, run, manifest):
    export = read_json(run / "export.json")
    paths = set()
    for entry in export["files"]:
        name = entry["path"]
        require(name not in paths, "duplicate export file")
        paths.add(name)
        require(digest(relative_file(run, name).read_bytes()) == entry["export_sha256"],
                "export hash mismatch: " + name)
        if name.startswith(("artifacts/evaluator/", "verifier/")):
            require(entry["paths_redacted"] is False
                    and entry["original_sha256"] == entry["export_sha256"],
                    "evaluator or verifier evidence was transformed")
    required = {"result.json", "config.json", "artifacts/evaluator/result.json",
                "artifacts/evaluator/replay.json", "artifacts/evaluator/transcript.jsonl",
                "verifier/reward.txt", "verifier/information-details.json"}
    require(required <= paths, "export manifest omits required evidence")
    task = relative_file(pilot, export["task_path"])
    same(read_json(task / "experiment.json"), manifest, "run/task experiment manifest")
    actual = {path.relative_to(task).as_posix() for path in task.rglob("*") if path.is_file()}
    require(actual == set(manifest["task_sha256"]) | {"experiment.json"}, "task file inventory mismatch")
    for name, expected in manifest["task_sha256"].items():
        require(digest(relative_file(task, name).read_bytes()) == expected,
                "task hash mismatch: " + name)
    for target, source in SOURCE_COPIES.items():
        require(manifest["task_sha256"][target] == manifest["source_sha256"][source],
                "task copy differs from committed source: " + target)


def audit_run(pilot, run, role, context, assignment, protocol, cache):
    manifest = read_json(run / "experiment.json")
    require(manifest["schema_version"] == 1, "unknown task manifest schema")
    same(manifest["settings"], {"context": context, "seed": assignment["seed"],
                               "horizon": 30, "policy": "selective"}, "task settings")
    sources = committed_sources(manifest, cache)
    verify_export(pilot, run, manifest)
    trial = read_json(run / "result.json")
    config = read_json(run / "config.json")
    require(trial["exception_info"] is None, "Harbor trial has an exception")
    require(bool(trial["started_at"]) and bool(trial["finished_at"]), "Harbor trial is incomplete")
    require(trial["verifier_environment_mode"] == "separate", "verifier was not separate")
    config_subset(trial["config"], config)
    require(not trial["config"]["extra_instructions"]
            and not trial["config"]["extra_instruction_paths"], "unregistered extra instructions")
    require(trial["config"]["verifier"]["disable"] is False, "verifier was disabled")
    protected, reward, errors = replay_run(run, manifest, sources)
    same(trial["verifier_result"]["rewards"], {"reward": reward}, "Harbor reward")
    reported_cost = None
    info = trial["agent_info"]
    if role == "model":
        agent = config["agent"]
        require(info["name"] == agent["name"] == "opencode", "unexpected model agent")
        require(agent["model_name"] == protocol["model"], "model differs from protocol")
        require(info["model_info"]["provider"] + "/" + info["model_info"]["name"] == protocol["model"],
                "reported model differs from protocol")
        same(agent["kwargs"]["opencode_config"], protocol["opencode_config"], "OpenCode protocol config")
        require(info["version"] == agent["kwargs"]["version"], "OpenCode version mismatch")
        require("OpenCode " + info["version"] in protocol["harness"], "OpenCode version differs from protocol")
        usage = trial["agent_result"]
        reported_cost = finite_number(usage["cost_usd"], "reported model cost")
        require(reported_cost >= 0, "reported model cost is negative")
        model_usage = usage["model_usage"]
        require(set(model_usage) == {protocol["model"]}, "unexpected model usage entry")
        same(model_usage[protocol["model"]]["cost_usd"], reported_cost, "model usage cost")
        for field in ("n_input_tokens", "n_cache_tokens", "n_output_tokens"):
            require(type(usage[field]) is int and usage[field] >= 0, "invalid token count: " + field)
            same(model_usage[protocol["model"]][field], usage[field], "model usage " + field)
    else:
        require(info["name"] == "oracle" and info["model_info"] is None,
                "matched reference is not Harbor oracle")
        require((config.get("agent") or {}).get("name", "oracle") == "oracle", "reference agent config mismatch")
    return {
        "run": run.name, "role": role, "context": context, "passed": True,
        "assignment_id": assignment["assignment_id"], "repeat": assignment["repeat"],
        "source_commit": manifest["source_commit"], "source_files_verified": len(sources),
        "task_files_verified": len(manifest["task_sha256"]),
        "reward": reward, "reported_cost_usd": reported_cost,
        "public_tool_calls": protected["tool_calls"], "reproduced_tool_errors": errors,
        "started_at": trial["started_at"], "finished_at": trial["finished_at"],
    }, manifest


def audit(pilot):
    pilot = Path(pilot).resolve()
    summary = {"schema_version": 1, "passed": False, "errors": [], "runs": [],
               "planned_model_trials": PLANNED_MODELS, "expected_runs": PLANNED_RUNS,
               "excluded_smoke_runs": [], "checks": [
                   "seed commitments and complete six-context, two-repeat model/reference coverage",
                   "committed source, copied task source, generated task and export file hashes",
                   "all public successes/errors and full hidden replay reconstructed from pinned source",
                   "protected result, verifier detail, reward.txt and Harbor reward agree",
                   "completed exception-free trials, protocol model/config and known reported costs"],
               "limits": ["Reported cost is harness evidence, not provider billing reconciliation.",
                          "Commitments establish assignment consistency, not proof of when they were published.",
                          "Smoke controls are excluded from the clean frozen pilot audit.",
                          "Missing or unrun assignments make the complete-pilot gate fail; verified rows remain reported.",
                          "This audits reproducibility and evidence consistency, not decision optimality or population reliability."]}
    try:
        protocol = read_json(pilot / "protocol.json")
        require(protocol["schema_version"] == 1, "unknown protocol schema")
        require(type(protocol["attempts_per_context"]) is int
                and protocol["attempts_per_context"] == len(REPEATS)
                and protocol["retries"] == 0, "unsupported attempt/retry protocol")
        order = protocol["order"]
        require(len(order) == PLANNED_MODELS, "protocol must contain twelve assignments")
        expected_assignments = {
            context + "-r" + str(repeat): (context, repeat)
            for context in CONTEXTS for repeat in REPEATS
        }
        ordered_ids = [entry["assignment_id"] for entry in order]
        require(len(set(ordered_ids)) == PLANNED_MODELS
                and set(ordered_ids) == set(expected_assignments), "protocol assignment inventory mismatch")
        for item in order:
            context, repeat = expected_assignments[item["assignment_id"]]
            same({"context": item["context"], "repeat": item["repeat"]},
                 {"context": context, "repeat": repeat}, "protocol context/repeat")
        reveal = read_json(pilot / "assignments-reveal.json")
        assignments = reveal["assignments"]
        require(len(assignments) == PLANNED_MODELS, "reveal must contain twelve assignments")
        by_id = {entry["assignment_id"]: entry for entry in assignments}
        require(len(by_id) == PLANNED_MODELS and set(by_id) == set(expected_assignments),
                "reveal assignment inventory mismatch")
        for item in order:
            assignment = by_id[item["assignment_id"]]
            same({key: assignment[key] for key in ("assignment_id", "context", "repeat")},
                 {key: item[key] for key in ("assignment_id", "context", "repeat")},
                 "revealed assignment identity")
            require(type(assignment["seed"]) is int and assignment["seed"] >= 0,
                    "revealed seed must be a nonnegative integer")
            require(isinstance(assignment["salt"], str) and assignment["salt"], "missing commitment salt")
            payload = {key: assignment[key] for key in ("assignment_id", "context", "seed", "salt")}
            commitment = digest(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
            require(commitment == item["seed_commitment"], "commitment mismatch: " + item["assignment_id"])
            require(assignment["commitment"] == commitment, "reveal commitment mismatch")
        expected_names = {prefix + assignment_id for assignment_id in ordered_ids
                          for prefix in ("model-", "matched-reference-")}
        names = {path.name for path in (pilot / "runs").iterdir() if path.is_dir()}
        summary["excluded_smoke_runs"] = sorted(names & {"smoke-nop", "smoke-reference", "smoke-isolation", "smoke-isolation-live"})
        require(not names - expected_names - set(summary["excluded_smoke_runs"]), "unexpected run directories")
        cache, manifests = {}, {}
        for item in order:
            assignment_id = item["assignment_id"]
            context = item["context"]
            for role, prefix in (("model", "model-"), ("reference", "matched-reference-")):
                name = prefix + assignment_id
                try:
                    require(name in names, "required run is missing or unrun")
                    row, manifest = audit_run(pilot, pilot / "runs" / name, role, context,
                                              by_id[assignment_id], protocol, cache)
                    summary["runs"].append(row)
                    manifests[(assignment_id, role)] = manifest
                except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
                    summary["runs"].append({"run": name, "role": role, "context": context,
                                            "assignment_id": assignment_id, "repeat": item["repeat"],
                                            "passed": False, "error": str(error)})
                    summary["errors"].append(name + ": " + str(error))
        for assignment_id in ordered_ids:
            if (assignment_id, "model") in manifests and (assignment_id, "reference") in manifests:
                same(manifests[(assignment_id, "model")], manifests[(assignment_id, "reference")],
                     assignment_id + " matched-reference task manifest")
        commits = {manifest["source_commit"] for manifest in manifests.values()}
        require(len(commits) <= 1, "pilot cases used different source commits")
        models = [row for row in summary["runs"] if row["role"] == "model" and row["passed"]]
        summary["verified_reported_cost_usd"] = math.fsum(row["reported_cost_usd"] for row in models)
        summary["model_costs_complete"] = len(models) == PLANNED_MODELS
        require(protocol["parallelism"] == 1, "unsupported model parallelism")
        for previous, current in zip(models, models[1:]):
            require(previous["finished_at"] <= current["started_at"], "model launch order/parallelism mismatch")
        summary["source_commits"] = sorted(commits)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        summary["errors"].append(str(error))
    summary["verified_runs"] = sum(row["passed"] for row in summary["runs"])
    summary["passed"] = not summary["errors"] and summary["verified_runs"] == PLANNED_RUNS
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pilotdir", type=Path)
    parser.add_argument("--output", type=Path, help="write the JSON summary to this NEW file; never overwrite")
    args = parser.parse_args(argv)
    if args.output is not None and (args.output.exists() or args.output.is_symlink()):
        parser.error("output already exists; choose a new path")
    summary = audit(args.pilotdir)
    encoded = json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output is not None:
        try:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(encoded)
        except OSError as error:
            parser.error("cannot write new output: " + str(error))
    print(encoded, end="")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
