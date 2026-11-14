#!/usr/bin/env python3
"""Prepare and export predeclared Block B. Never launches a model or a scheduler.

prepare-B makes three treatment tasks and public/private plans; export-B retains
all twelve assignments, including failed and partial attempts. Pass credentials
only as --env-file; their contents are used privately for redaction checks.
"""

import argparse
import copy
from datetime import datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import shutil
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
FROZEN_COMMIT = "02e4f7062ec3feaca14d9cc2eeb953af870ba769"
PROTOCOL_COMMIT = "6e1cfe3112985cd3caccc0af809d9c6c72bd59de"
AID_SHA256 = "a9315a4a09621bbcbf7587512f69c1757fdbc903f8bc3fc63e7aaee407eadf04"
DEFAULT_RUNTIME = Path("/tmp/lightlag-6974-overnight-v1/block-b")
DEFAULT_TASKS = Path("/tmp/lightlag-6974-fixed501-504-v1/tasks")
IDENTITY = {"name": "opencode", "version": "1.19.5",
            "model_info": {"name": "claude-opus-5-5", "provider": "anthropic"}}
PAIRS = [("rush_noisy", 504, 1, "TC"), ("rush_noisy", 502, 1, "TC"),
         ("rush", 501, 1, "CT"), ("rush", 501, 2, "TC"),
         ("rush_noisy", 502, 2, "CT"), ("rush_noisy", 504, 2, "CT")]
PROVIDER_ERROR = re.compile(r"provider.?error|api.?error|authentication|unauthorized|insufficient.{0,30}(?:credit|fund)|credit balance|rate.?limit|HTTP\s*(?:401|403|429|50[0234])", re.I)
spec = importlib.util.spec_from_file_location("overnight_save_run", REPO / "harbor/save_run.py")
saver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(saver)


def sha256(content):
    return hashlib.sha256(content).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def json_text(value):
    return json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"


def task_digest(hashes):
    """Harbor 0.25 Packager hash over these frozen, fully inventoried task files.

    experiment.json is metadata and is not in Harbor's package file selection.
    The original result is checked against the saved Harbor reference digest.
    """
    payload = "".join(f"{name}\0{digest}\n" for name, digest in sorted(hashes.items()))
    return "sha256:" + sha256(payload.encode())


def verify_manifest(repo, task, manifest):
    if manifest["source_commit"] != FROZEN_COMMIT or manifest["source_dirty"]:
        raise ValueError("task source is not the clean frozen source")
    actual = {}
    for path in task.rglob("*"):
        if path.is_symlink():
            raise ValueError("task symlinks are not part of the frozen inventory")
        if path.is_file() and path.name != "experiment.json":
            actual[path.relative_to(task).as_posix()] = sha256(path.read_bytes())
    if actual != manifest["task_sha256"]:
        raise ValueError("task file inventory or bytes differ from its manifest")
    for name, digest in manifest["source_sha256"].items():
        path = Path(name)
        if path.is_absolute() or ".." in path.parts or sha256((repo / path).read_bytes()) != digest:
            raise ValueError("frozen source bytes differ: " + name)


def verify_auditor(repo, expected):
    for name, digest in expected.items():
        if sha256((repo / name).read_bytes()) != digest:
            raise ValueError("frozen auditor bytes differ: " + name)


def prepare_b(repo, originals, runtime, public_plan, aid):
    repo, originals, runtime, public_plan, aid = map(Path, (repo, originals, runtime, public_plan, aid))
    if runtime.exists() or runtime.is_symlink() or public_plan.exists() or public_plan.is_symlink():
        raise FileExistsError("preparation outputs already exist; nothing was overwritten")
    aid_bytes = aid.read_bytes()
    if sha256(aid_bytes) != AID_SHA256:
        raise ValueError("appendix differs from the predeclared ledger_aid_v1 bytes")
    prior = read_json(repo / "docs/lightlag-runs/fixed-seeds501-504-summary.json")
    verify_auditor(repo, prior["auditor_sha256"])
    tasks = {}
    # Complete all source checks before creating any output directory.
    for profile, seed in sorted({(p, s) for p, s, _, _ in PAIRS}):
        source = originals / f"{profile}-{seed}"
        manifest = read_json(source / "experiment.json")
        reference = next(r for r in prior["reference_runs"] if (r["profile"], r["seed"]) == (profile, seed))
        if manifest != read_json(repo / "docs/lightlag-runs" / reference["evidence"] / "experiment.json"):
            raise ValueError("original task manifest differs from saved reference")
        expected_settings = {"profile": profile, "seed": seed, "delay": 3, "horizon": 50,
                             "noise_level": 1.0, "bumpiness": 0.0, "policy": "kf_mpc"}
        if manifest["settings"] != expected_settings:
            raise ValueError("original task settings differ from the Block B protocol")
        verify_manifest(repo, source, manifest)
        if task_digest(manifest["task_sha256"]) != reference["task_digest"]:
            raise ValueError("original task digest differs from saved Harbor reference")
        for condition in "CT":
            key = f"{profile}-{seed}-{condition}"
            changed = copy.deepcopy(manifest)
            if condition == "T":
                changed["task_sha256"]["instruction.md"] = sha256((source / "instruction.md").read_bytes() + b"\n" + aid_bytes)
                changed["intervention"] = {"name": "ledger_aid_v1", "protocol_commit": PROTOCOL_COMMIT,
                                           "appendix_sha256": AID_SHA256,
                                           "control_instruction_sha256": manifest["task_sha256"]["instruction.md"],
                                           "changed_task_files": ["instruction.md"]}
            tasks[key] = {"manifest": changed, "task_digest": task_digest(changed["task_sha256"]),
                          "instruction_sha256": changed["task_sha256"]["instruction.md"],
                          "reference": reference, "condition": condition, "case": f"{profile}-{seed}"}
    entries = []
    for pair, (profile, seed, repetition, order) in enumerate(PAIRS, 1):
        for condition in order:
            index = len(entries) + 1
            stem = f"overnight-b{index:02d}-{condition.lower()}-{profile.replace('_', '-') }"
            entries.append({"index": index, "block": "B", "pair": pair, "profile": profile,
                            "seed": seed, "condition": condition, "repetition": repetition,
                            "task_key": f"{profile}-{seed}-{condition}",
                            "job": f"{stem}-{seed}-r{repetition}",
                            "evidence": f"{stem}-seed{seed}-r{repetition}-opus-5-5"})
    plan = {"schema_version": 1, "block": "B", "protocol_commit": PROTOCOL_COMMIT,
            "source_commit": FROZEN_COMMIT, "appendix_sha256": AID_SHA256,
            "appendix_path": "tools/lightlag_experiments/ledger_aid_v1.md",
            "auditor_sha256": prior["auditor_sha256"], "agent": IDENTITY,
            "max_retries": 0, "max_concurrent": 2, "agent_timeout_seconds": 1800,
            "launch_guard_usd": 12.0, "user_reported_ceiling_usd": 15.70,
            "selection": "selected diagnostic maps; prospective paired prompt intervention, not population inference",
            "tasks": tasks, "entries": entries}
    plan["plan_id"] = sha256(json_text(plan).encode())
    runtime.mkdir(parents=True, exist_ok=False)
    for key, task in tasks.items():
        if task["condition"] == "T":
            source = originals / task["case"]
            dest = runtime / "tasks" / key
            shutil.copytree(source, dest)
            (dest / "instruction.md").write_bytes((source / "instruction.md").read_bytes() + b"\n" + aid_bytes)
            (dest / "experiment.json").write_text(json_text(task["manifest"]))
            verify_manifest(repo, dest, task["manifest"])
    public_plan.parent.mkdir(parents=True, exist_ok=True)
    public_plan.write_text(json_text(plan))
    private = copy.deepcopy(plan)
    private["runtime_root"] = str(runtime.absolute())
    for entry in private["entries"]:
        entry["task"] = str((originals / f"{entry['profile']}-{entry['seed']}" if entry["condition"] == "C"
                             else runtime / "tasks" / entry["task_key"]).absolute())
    (runtime / "plan.json").write_text(json_text(private))
    return private


def read_key(env_file):
    # Deliberately does not read shell environment or an implicit credential path.
    text = Path(env_file).read_text(encoding="utf-8")
    match = re.search(r"(?m)^\s*(?:export\s+)?ANTHROPIC_API_KEY\s*=\s*(.+?)\s*$", text)
    if not match:
        raise ValueError("the supplied env file has no ANTHROPIC_API_KEY")
    value = match.group(1)
    if value[:1] in ("'", '"'):
        quote = value[0]
        end = value.find(quote, 1)
        value = value[1:end] if end >= 1 else ""
    else:
        value = value.split(" #", 1)[0].strip()
    if not value:
        raise ValueError("the supplied env file has an empty API key")
    return value


def sanitizer(key, paths):
    replacements = []
    for path, label in paths:
        for value in {str(Path(path).absolute()), str(Path(path).resolve())}:
            replacements.append((value, label))
    replacements.sort(key=lambda item: len(item[0]), reverse=True)

    def clean(text):
        text = text.replace(key, "<redacted-api-key>")
        for pattern in saver.SECRET_PATTERNS:
            text = pattern.sub("<redacted-credential>", text)
        for value, label in replacements:
            text = text.replace(value, label)
        text = re.sub(r"/(?:Users|home|private/tmp|tmp)/[^\s\"'<>{}\\]+", "<local-path>", text)
        if key in text or saver.find_secrets(text):
            raise ValueError("credential sanitization did not remove all detected secrets")
        return text
    return clean


def snapshot(trial, clean):
    files, redacted = {}, []
    for path in sorted(trial.rglob("*")):
        relative = path.relative_to(trial)
        if relative.parts[:2] == ("agent", "opencode") or path.is_symlink() or not path.is_file():
            continue
        if path.suffix.lower() not in saver.TEXT_SUFFIXES:
            continue
        raw = path.read_text(encoding="utf-8", errors="replace")
        value = clean(raw)
        if "<redacted-" in value:
            redacted.append(relative.as_posix())
        files[relative.as_posix()] = value
    return files, redacted


def save_owned(destination, files, owner):
    """Update only an export bearing our exact owner marker; preserve unknown files."""
    marker = destination / "export-metadata.json"
    if destination.exists():
        if destination.is_symlink() or not marker.is_file():
            raise FileExistsError("unknown evidence destination; preserved")
        previous = read_json(marker)
        if previous.get("owner") != owner:
            raise FileExistsError("evidence destination belongs to a different plan or job")
        allowed = set(previous["files"]) | {"export-metadata.json"}
        if any(p.is_symlink() or (p.is_file() and p.relative_to(destination).as_posix() not in allowed)
               for p in destination.rglob("*")):
            raise FileExistsError("unknown files in evidence destination; preserved")
    destination.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    all_files = {p.relative_to(destination).as_posix(): sha256(p.read_bytes())
                 for p in destination.rglob("*") if p.is_file() and p.name != "export-metadata.json"}
    marker.write_text(json_text({"owner": owner, "files": all_files}))


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def verified_call_counts(replay, transcript, reported_count):
    """Check the frozen service's cached grade count without discarding later calls.

    The first successful call reaching the horizon caches the grade. Subsequent
    successful read tools and no-op advances may be logged without regrading.
    Reconstruct exact call records and prove that suffix leaves the terminal
    environment unchanged; the existing auditor still checks the saved replay.
    """
    from lightlag import Config
    from lightlag_audit.counterfactual import make_environment
    from lightlag_mcp.service import EpisodeService, PUBLIC_TOOLS, ToolError

    if type(reported_count) is not int or reported_count < 0:
        raise ValueError("invalid graded call count")
    service = EpisodeService(seed=replay["seed"], config=Config(**replay["config"]), artifact_dir=None)
    service._env = make_environment(replay)  # Same frozen public-call wrapper, exact saved mission.
    terminal = None
    for index, record in enumerate(transcript, 1):
        if (type(record["n"]) is not int or record["n"] != index or
                type(record["tick_before"]) is not int or type(record["tick_after"]) is not int or
                record["tool"] not in PUBLIC_TOOLS or not isinstance(record["arguments"], dict)):
            raise ValueError("malformed public-call transcript")
        if terminal is not None and (record["ok"] is not True or
                                     record["tool"] not in ("rules", "map", "telemetry_log", "advance")):
            raise ValueError("unverified postterminal call")
        try:
            service.call(record["tool"], record["arguments"])
        except ToolError:
            pass  # A preterminal failure is still counted and must reproduce exactly.
        if json_text(service.transcript()[-1]) != json_text(record):
            raise ValueError("public-call record does not reproduce")
        if terminal is not None:
            if service._env.replay() != terminal:
                raise ValueError("postterminal call changed the environment")
        elif service.result is not None:
            terminal = service._env.replay()
    # If the agent stopped earlier, the trusted collect hook grades after all
    # recorded calls; its advances are not additional public tool calls.
    grade = service.result if service.result is not None else service.finish()
    if grade["tool_calls"] != reported_count:
        raise ValueError("grade count differs from the first horizon reach or trusted finish")
    return {"tool_calls": len(transcript), "graded_call_count": reported_count,
            "postterminal_count": len(transcript) - reported_count}


def inspect_trial(files, expected_digest):
    """Read cost first. Bad or absent grading never prevents cost/attempt retention."""
    issues = []

    def get(name, required=False):
        if name not in files:
            if required: issues.append("missing " + name)
            return {}
        try:
            result = json.loads(files[name])
            if not isinstance(result, dict): raise ValueError()
            return result
        except (ValueError, TypeError):
            issues.append("invalid " + name)
            return {}

    trial = get("result.json", True)
    trajectory = get("agent/trajectory.json")
    def mapping(value):
        return value if isinstance(value, dict) else {}

    result_cost = mapping(trial.get("agent_result")).get("cost_usd")
    metrics_cost = mapping(trajectory.get("final_metrics")).get("total_cost_usd")
    available = [cost for cost in (result_cost, metrics_cost) if number(cost)]
    cost = max(available) if available else None
    if len(available) == 2 and abs(available[0] - available[1]) > 1e-9:
        issues.append("reported cost sources disagree; retained larger available amount")
    exception = trial.get("exception_info")
    provider = bool(PROVIDER_ERROR.search(json.dumps(exception) + files.get("trial.log", "") +
                                         files.get("launcher.log", "") + files.get("agent/opencode.txt", "")))
    row = {"reported_cost_usd": cost, "cost_sources_usd": {"trial": result_cost if number(result_cost) else None,
           "trajectory": metrics_cost if number(metrics_cost) else None}, "exception": exception,
           "provider_error": provider, "agent": trial.get("agent_info"), "trial_id": trial.get("id"),
           "trial_name": trial.get("trial_name"), "started_at": trial.get("started_at"),
           "finished_at": trial.get("finished_at"), "status": "failed" if exception else "partial",
           "reward": None, "raw_score": None, "alive": None, "at_base": None, "sampled_value": None,
           "samples": [], "late_samples": None, "tool_calls": None, "graded_call_count": None,
           "postterminal_count": None, "duration_seconds": None,
           "task_digest": None, "audit": None, "issues": issues}
    try:
        if row["started_at"] and row["finished_at"]:
            row["duration_seconds"] = (datetime.fromisoformat(row["finished_at"].replace("Z", "+00:00")) -
                                       datetime.fromisoformat(row["started_at"].replace("Z", "+00:00"))).total_seconds()
    except (AttributeError, TypeError, ValueError):
        issues.append("invalid duration timestamps")
    identity = trial.get("agent_info")
    if identity != IDENTITY: issues.append("missing or incorrect model/harness identity")
    configuration = mapping(trial.get("config"))
    agent_config = mapping(configuration.get("agent"))
    if agent_config.get("resume_trajectory") is not False or agent_config.get("load_trajectory", "missing") is not None:
        issues.append("fresh-session configuration absent or incorrect")
    if (agent_config.get("model_name") != "anthropic/claude-opus-5-5" or
            mapping(agent_config.get("kwargs")).get("version") != "1.19.5" or
            any(agent_config.get(k) for k in ("base_url", "skills", "mcp_servers", "override_timeout_sec", "max_timeout_sec")) or
            any(configuration.get(k) for k in ("extra_instructions", "extra_instruction_paths", "source_trial")) or
            configuration.get("timeout_multiplier", 1.0) != 1.0 or
            configuration.get("agent_timeout_multiplier") is not None):
        issues.append("unplanned prompt, provider or harness configuration")
    lock = get("lock.json", True)
    row["task_digest"] = mapping(lock.get("task")).get("digest")
    if row["task_digest"] != expected_digest: issues.append("task digest absent or incorrect")
    evaluation = get("artifacts/evaluator/result.json", True)
    replay = get("artifacts/evaluator/replay.json", True)
    details = get("verifier/lightlag-details.json", True)
    try:
        reward = float(files["verifier/reward.txt"].strip())
        raw, maximum = evaluation["raw_score"], evaluation["max_available_value"]
        if not number(reward) or reward > 1 or not number(raw) or not number(maximum) or maximum <= 0:
            raise ValueError()
        if evaluation["tick"] != 50 or [s["tick"] for s in replay["states"]] != list(range(51)):
            raise ValueError()
        if {k: v for k, v in evaluation.items() if k != "tool_calls"} != replay["result"]:
            raise ValueError()
        if details["raw_score"] != raw or abs(raw / maximum - reward) > .00000051:
            raise ValueError()
        if trial["verifier_result"]["rewards"]["reward"] != reward:
            raise ValueError()
        transcript = [json.loads(line) for line in files["artifacts/evaluator/transcript.jsonl"].splitlines() if line.strip()]
        row["tool_calls"] = len(transcript)
        row["graded_call_count"] = evaluation["tool_calls"] if type(evaluation["tool_calls"]) is int else None
        row.update(verified_call_counts(replay, transcript, evaluation["tool_calls"]))
        if type(evaluation["alive"]) is not bool or type(evaluation["at_base"]) is not bool:
            raise ValueError()
        sampled_value = evaluation["sampled_value"]
        samples = evaluation.get("samples", [])
        if not number(sampled_value) or not isinstance(samples, list):
            raise ValueError()
        if any(not isinstance(s, dict) or type(s.get("on_time")) is not bool for s in samples):
            raise ValueError()
    except (KeyError, TypeError, ValueError):
        issues.append("missing, invalid or inconsistent terminal grading")
    else:
        if not issues:
            row.update(reward=raw/maximum, raw_score=raw, maximum=maximum, alive=evaluation["alive"],
                       at_base=evaluation["at_base"], sampled_value=sampled_value,
                       samples=samples, tool_calls=len(transcript),
                       late_samples=sum(not s["on_time"] for s in samples),
                       status="failed" if exception else "complete")
    if row["finished_at"] and row["reward"] is None:
        row["status"] = "failed"
    return row


def audit_evidence(destination, audit_root, expected_reference, expected_raw):
    from lightlag_audit.runs import load_run
    from lightlag_audit.report import audit_run, write
    evidence_path = (Path(destination.parent.name) / destination.name
                     if destination.name.startswith("unexpected-attempt-") else Path(destination.name))
    folder = audit_root / evidence_path
    snapshot_hashes = read_json(destination / "export-metadata.json")["files"]
    marker = folder / "export-metadata.json"
    if folder.exists():
        if not marker.is_file(): raise FileExistsError("unknown audit directory; preserved")
        ownership = read_json(marker)
        if ownership.get("evidence_path") != evidence_path.as_posix():
            raise FileExistsError("audit directory belongs to another evidence path; preserved")
        if ownership.get("files") == snapshot_hashes:
            report = read_json(folder / "audit.json")
        else:
            report = audit_run(load_run(destination))
    else:
        report = audit_run(load_run(destination))
    if (not report["replay_matches"] or not report["decomposition"]["adds_up"] or
            report["score"]["agent_raw"] != expected_raw or report["score"]["reference_raw"] != expected_reference):
        raise ValueError("full replay audit or frozen reference score differs")
    report["run"] = evidence_path.as_posix()
    write(report, folder)
    marker.write_text(json_text({"evidence_path": evidence_path.as_posix(), "files": snapshot_hashes}))
    return report


def aggregate_rows(rows):
    def stats(group):
        rewards = [r["reward"] for r in group if r["reward"] is not None]
        unknown = len(group) - len(rewards)
        return {"n_planned": len(group), "n_valid_reward": len(rewards),
                "mean_reward": sum(rewards)/len(group) if not unknown else None,
                "observed_mean_reward": sum(rewards)/len(rewards) if rewards else None,
                "mean_reward_bounds": [sum(rewards)/len(group), (sum(rewards)+unknown)/len(group)],
                "deaths": sum(r["alive"] is False for r in group),
                "alive_unknown": sum(r["alive"] is None for r in group),
                "deficits": sum(r["reward"] is not None and r["reward"] < r.get("reference_reward", 0)-1e-9 for r in group)}
    pairs = []
    for pair in sorted({r["pair"] for r in rows}):
        members = {r["condition"]: r for r in rows if r["pair"] == pair}
        c, t = members["C"]["reward"], members["T"]["reward"]
        bounds = [(t if t is not None else 0)-(c if c is not None else 1),
                  (t if t is not None else 1)-(c if c is not None else 0)]
        pairs.append({"pair": pair, "profile": members["C"]["profile"], "seed": members["C"]["seed"],
                      "repetition": members["C"]["repetition"], "C": c, "T": t,
                      "difference": t-c if t is not None and c is not None else None, "difference_bounds": bounds})
    cases = []
    for profile, seed in sorted({(r["profile"], r["seed"]) for r in rows}):
        group = [r for r in rows if (r["profile"], r["seed"]) == (profile, seed)]
        conditions = {c: stats([r for r in group if r["condition"] == c]) for c in "CT"}
        ref = group[0].get("reference_reward")
        for value in conditions.values():
            value["reference_minus_mean"] = ref-value["mean_reward"] if ref is not None and value["mean_reward"] is not None else None
        cases.append({"profile": profile, "seed": seed, "reference_reward": ref, "conditions": conditions})
    differences = [p["difference"] for p in pairs]
    return {"pairs": pairs, "cases": cases, "conditions": {c: stats([r for r in rows if r["condition"] == c]) for c in "CT"},
            "paired_mean_gain": sum(differences)/len(pairs) if all(d is not None for d in differences) else None,
            "paired_mean_gain_bounds": [sum(p["difference_bounds"][i] for p in pairs)/len(pairs) for i in (0, 1)]}


def validate_plan(repo, plan, plan_path):
    """Fail before exports if the private plan differs from the published assignment.

    Only runtime_root and each entry's task path are private. The public file is
    the protocol artifact committed before B launches; neither plan is repaired
    or rewritten here. A validation failure makes any previous summary stale.
    """
    try:
        public = read_json(repo / "docs/lightlag-runs/overnight-b-plan.json")
        projection = copy.deepcopy(plan)
        runtime = Path(projection.pop("runtime_root"))
        if not runtime.is_absolute() or runtime.resolve() != plan_path.parent.resolve():
            raise ValueError("plan runtime must contain the private plan file")
        paths = []
        for entry in projection["entries"]:
            path = Path(entry.pop("task"))
            if not path.is_absolute(): raise ValueError("plan task paths must be absolute")
            paths.append(path.resolve())
        if projection != public:
            raise ValueError("private plan projection differs from the published plan")
        unsigned = copy.deepcopy(public)
        plan_id = unsigned.pop("plan_id")
        if sha256(json_text(unsigned).encode()) != plan_id:
            raise ValueError("plan_id does not match the complete public plan content")
        expected = []
        for pair, (profile, seed, repetition, order) in enumerate(PAIRS, 1):
            for condition in order:
                index = len(expected) + 1
                stem = f"overnight-b{index:02d}-{condition.lower()}-{profile.replace('_', '-')}"
                expected.append({"index": index, "block": "B", "pair": pair, "profile": profile,
                                 "seed": seed, "condition": condition, "repetition": repetition,
                                 "task_key": f"{profile}-{seed}-{condition}",
                                 "job": f"{stem}-{seed}-r{repetition}",
                                 "evidence": f"{stem}-seed{seed}-r{repetition}-opus-5-5"})
        if public["entries"] != expected:
            raise ValueError("plan must retain all 12 unique assignments in protocol order")
        if set(public["tasks"]) != {entry["task_key"] for entry in expected}:
            raise ValueError("plan task inventory differs from the six assigned tasks")
        by_key, control_parents = {}, set()
        for entry, path in zip(expected, paths):
            key, case = entry["task_key"], f"{entry['profile']}-{entry['seed']}"
            task = public["tasks"][key]
            if (task["condition"] != entry["condition"] or task["case"] != case or
                    (task["manifest"]["settings"]["profile"], task["manifest"]["settings"]["seed"]) != (entry["profile"], entry["seed"]) or
                    (task["reference"]["profile"], task["reference"]["seed"]) != (entry["profile"], entry["seed"]) or
                    task_digest(task["manifest"]["task_sha256"]) != task["task_digest"] or
                    task["manifest"]["task_sha256"]["instruction.md"] != task["instruction_sha256"]):
                raise ValueError("plan task identity or hashes are inconsistent")
            if key in by_key and by_key[key] != path:
                raise ValueError("plan repetitions disagree on the assigned task path")
            by_key[key] = path
            if entry["condition"] == "T":
                if path != (runtime / "tasks" / key).resolve():
                    raise ValueError("plan treatment path escaped its prepared task directory")
            else:
                if path.name != case or runtime.resolve() in path.parents:
                    raise ValueError("plan control path is not a separate original task")
                control_parents.add(path.parent)
        if len(control_parents) != 1 or len(set(by_key.values())) != 6:
            raise ValueError("plan private paths do not identify six distinct C/T tasks")
    except (KeyError, TypeError, OSError, ValueError) as error:
        raise ValueError("Block B plan integrity failed; no export was performed") from error


def export_b(repo, plan_path, env_file, out, audits, a_summary):
    repo, plan_path, env_file, out, audits = map(Path, (repo, plan_path, env_file, out, audits))
    plan = read_json(plan_path)
    validate_plan(repo, plan, plan_path)
    key = read_key(env_file)
    runtime = Path(plan["runtime_root"])
    clean = sanitizer(key, [(env_file, "<credentials-file>"), (runtime / "jobs", "<jobs-dir>"),
                           (runtime, "<block-b-runtime>"), (repo, "<repository>")] +
                      [(Path(e["task"]), "<frozen-task>" if e["condition"] == "C" else "<treatment-task>") for e in plan["entries"]])
    global_issues = []
    try:
        prior = read_json(repo / "docs/lightlag-runs/fixed-seeds501-504-summary.json")
        if prior["auditor_sha256"] != plan["auditor_sha256"]:
            raise ValueError("auditor plan mismatch")
        verify_auditor(repo, plan["auditor_sha256"])
    except Exception as error:
        global_issues.append("frozen auditor validation failed: " + type(error).__name__)
    try:
        previous = read_json(a_summary)
        if previous["auditor_sha256"] != plan["auditor_sha256"]:
            global_issues.append("Block A auditor hashes differ")
    except Exception as error:
        previous = {"runs": [], "n_completed": 0, "n_planned": 9, "reported_cost_usd": None}
        global_issues.append("Block A ledger unavailable: " + type(error).__name__)
    rows, reports = [], []
    for entry in plan["entries"]:
        row = {k: v for k, v in entry.items() if k != "task"}
        task = plan["tasks"][entry["task_key"]]
        ref = task["reference"]
        row.update(status="pending", reward=None, raw_score=None, maximum=ref["maximum"], alive=None,
                   at_base=None, reported_cost_usd=None, known_reported_cost_usd=0, provider_error=False,
                   reference_reward=ref["raw_score"]/ref["maximum"], reference_raw=ref["raw_score"],
                   reference_evidence=ref["evidence"], issues=[], trials=[], audit=None)
        rows.append(row)  # Assignment exists in the ledger before any fallible attempt processing.
        job = runtime / "jobs" / entry["job"]
        launcher_log = runtime / (entry["job"] + ".log")
        trials = sorted(p for p in job.iterdir() if p.is_dir() and not p.is_symlink()) if job.is_dir() else []
        if not trials and job.is_dir() and any(job.iterdir()):
            trials = [job]  # A setup/provider failure may have only job-level logs.
        if not trials and launcher_log.is_file():
            trials = [None]  # A launcher failure may precede all Harbor directories.
        if not trials: continue
        manifest_issues = list(global_issues)
        try:
            manifest = read_json(Path(entry["task"]) / "experiment.json")
            if manifest != task["manifest"]: raise ValueError("manifest changed")
            verify_manifest(repo, Path(entry["task"]), manifest)
        except Exception as error:
            manifest_issues.append("frozen manifest validation failed: " + type(error).__name__)
        for index, trial in enumerate(trials, 1):
            info = {"reward": None, "raw_score": None, "alive": None, "at_base": None,
                    "reported_cost_usd": None, "provider_error": False, "status": "failed", "issues": [], "audit": None}
            row["trials"].append(info)
            try:
                files, redacted = snapshot(trial, clean) if trial is not None else ({}, [])
                if launcher_log.is_file():
                    log = clean(launcher_log.read_text(encoding="utf-8", errors="replace"))
                    files["launcher.log" if trial is not None else "trial.log"] = log
                info.update(inspect_trial(files, task["task_digest"]))
                info["redacted_files"] = redacted
                info["issues"].extend(manifest_issues)
                files["experiment.json"] = json_text(task["manifest"])
                destination = out / entry["evidence"]
                if len(trials) > 1: destination /= f"unexpected-attempt-{index}"
                save_owned(destination, files, {"plan_id": plan["plan_id"], "job": entry["job"], "attempt": index})
                if info["reward"] is not None and not manifest_issues:
                    report = audit_evidence(destination, audits, ref["raw_score"], info["raw_score"])
                    reports.append(report)
                    info["audit"] = {"path": destination.relative_to(out).as_posix(), "replay_matches": report["replay_matches"],
                                     "decomposition_adds_up": report["decomposition"]["adds_up"],
                                     "infrastructure_findings": len(report["infrastructure"]),
                                     "reference_minus_model": report["score"]["gap_reward"],
                                     "main_decisions": [{"call": d["n"], "tick": d["tick"], "points_lost": d["points_lost"],
                                                         "tags": [f["tag"] for f in d["findings"]]} for d in report["main_mistakes"]]}
            except Exception as error:
                info["issues"].append("export/audit failed: " + type(error).__name__)
            if info["reward"] is not None and info["audit"] is None:
                info.update(reward=None, raw_score=None, alive=None, at_base=None, status="failed")
        if len(row["trials"]) == 1:
            row.update(row["trials"][0])
        else:
            row.update(status="failed", issues=["unexpected multiple attempts; all available costs and evidence retained"])
        costs = [t["reported_cost_usd"] for t in row["trials"]]
        row["known_reported_cost_usd"] = sum(c for c in costs if c is not None)
        row["reported_cost_usd"] = sum(costs) if all(c is not None for c in costs) else None
        row["provider_error"] = any(t["provider_error"] for t in row["trials"])
    # A copied trial must not count as a fresh assignment. Keep its available
    # cost and raw evidence, but invalidate every affected B outcome.
    for field in ("trial_id", "trial_name"):
        previous_values = {r[field] for r in previous["runs"]
                           if isinstance(r.get(field), str) and r[field].strip()}
        groups = {}
        for row in rows:
            for trial in row["trials"]:
                value = trial.get(field)
                if isinstance(value, str) and value.strip():
                    groups.setdefault(value, []).append((row, trial))
        for value, members in groups.items():
            reasons = []
            if len(members) > 1: reasons.append(f"duplicate {field} across Block B")
            if value in previous_values: reasons.append(f"{field} reused from Block A")
            for row, trial in members if reasons else []:
                trial["issues"].extend(reasons)
                trial.update(status="failed", reward=None, raw_score=None, alive=None, at_base=None)
                row.update(status="failed", reward=None, raw_score=None, alive=None, at_base=None)
                if len(row["trials"]) > 1: row["issues"].extend(reasons)
    previous_costs = [r.get("reported_cost_usd") for r in previous["runs"]]
    a_known = sum(c for c in previous_costs if number(c))
    a_unknown = any(not number(c) for c in previous_costs) or not number(previous.get("reported_cost_usd"))
    if not a_unknown and abs(a_known-previous["reported_cost_usd"]) > 1e-8:
        global_issues.append("Block A cost total differs from its retained rows")
        a_unknown = True
    attempted = [r for r in rows if r["status"] != "pending"]
    b_known = sum(r["known_reported_cost_usd"] for r in attempted)
    unknown = a_unknown or any(r["reported_cost_usd"] is None for r in attempted)
    known_total = a_known + b_known
    stop = []
    if unknown: stop.append("unknown_cost")
    if any(r["provider_error"] for r in rows) or any(PROVIDER_ERROR.search(json.dumps(r.get("exception"))) for r in previous["runs"]): stop.append("provider_error")
    if previous.get("n_completed") != previous.get("n_planned"): stop.append("block_a_incomplete")
    if any(r["status"] == "partial" for r in rows): stop.append("partial_attempt_requires_reconciliation")
    if any(t["issues"] or (t.get("audit") or {}).get("infrastructure_findings", 0)
           for r in rows for t in r["trials"]):
        stop.append("trial_integrity_failure")
    if any(len(r["trials"]) > 1 for r in rows) and "trial_integrity_failure" not in stop:
        stop.append("trial_integrity_failure")
    if known_total >= 12: stop.append("cumulative_launch_guard")
    if global_issues: stop.append("validation_requires_reconciliation")
    summary = {"schema_version": 1, "block": "B", "plan_id": plan["plan_id"], "protocol_commit": PROTOCOL_COMMIT,
               "source_commit": FROZEN_COMMIT, "auditor_sha256": plan["auditor_sha256"], "n_planned": 12,
               "n_attempted": len(attempted), "n_valid_reward": sum(r["reward"] is not None for r in rows),
               "n_pending": sum(r["status"] == "pending" for r in rows),
               "n_failed": sum(r["status"] == "failed" for r in rows), "runs": rows,
               "reported_cost_usd": b_known if all(r["reported_cost_usd"] is not None for r in attempted) else None,
               "known_reported_cost_usd": b_known, "block_a_known_reported_cost_usd": a_known,
               "cumulative_reported_cost_usd": None if unknown else known_total,
               "cumulative_known_reported_cost_usd": known_total, "launch_guard_usd": 12,
               "user_reported_ceiling_usd": 15.70, "account_balance_independently_verified": False,
               "stop_launches": bool(stop), "stop_reasons": stop, "validation_issues": global_issues,
               "cost_note": "Available reported usage only; partial attempts may still accrue cost. Unknown usage is never assumed zero.",
               **aggregate_rows(rows)}
    out.mkdir(parents=True, exist_ok=True)
    summary_path = out / "overnight-b-summary.json"
    if summary_path.exists() and read_json(summary_path).get("plan_id") != plan["plan_id"]:
        raise FileExistsError("unknown summary destination; preserved")
    summary_path.write_text(clean(json_text(summary)))
    if reports:
        from lightlag_audit.__main__ import _write_index
        _write_index(audits, reports)
        for path in audits.rglob("*"):
            if path.is_file():
                raw = path.read_text()
                if clean(raw) != raw: path.write_text(clean(raw))
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare-B")
    prep.add_argument("--tasks-root", type=Path, default=DEFAULT_TASKS)
    prep.add_argument("--runtime", type=Path, default=DEFAULT_RUNTIME)
    prep.add_argument("--public-plan", type=Path, default=REPO / "docs/lightlag-runs/overnight-b-plan.json")
    export = sub.add_parser("export-B")
    export.add_argument("--plan", type=Path, default=DEFAULT_RUNTIME / "plan.json")
    export.add_argument("--env-file", type=Path, required=True)
    export.add_argument("--out", type=Path, default=REPO / "docs/lightlag-runs")
    export.add_argument("--audits", type=Path, default=REPO / "docs/lightlag-audits/overnight/block-b")
    export.add_argument("--a-summary", type=Path, default=REPO / "docs/lightlag-runs/overnight-a-summary.json")
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare-B":
            plan = prepare_b(REPO, args.tasks_root, args.runtime, args.public_plan,
                             REPO / "tools/lightlag_experiments/ledger_aid_v1.md")
            print(f"Prepared {len(plan['entries'])} assignments and three treatment tasks; no calls launched.")
        else:
            summary = export_b(REPO, args.plan, args.env_file, args.out, args.audits, args.a_summary)
            print(f"B: {summary['n_attempted']}/12 attempted, {summary['n_valid_reward']} valid rewards, {summary['n_pending']} pending.")
            print(f"Known A+B usage: ${summary['cumulative_known_reported_cost_usd']:.7f}; stop_launches={summary['stop_launches']}; reasons={','.join(summary['stop_reasons']) or 'none'}")
    except (ValueError, OSError, KeyError) as error:
        # Never interpolate raw file contents, provider exceptions or credential values.
        parser.exit(1, f"{args.command} could not finish ({type(error).__name__}); outputs were preserved.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
