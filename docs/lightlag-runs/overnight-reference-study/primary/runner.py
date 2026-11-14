"""Execute the fixed, predeclared overnight controller study without paid calls.

Use a new output directory and an isolated source tree copied from SOURCE_COMMIT.
Only read-only Git commands are used. Completed attempts are never retried; an
execution error has a null score. A source or historical-reference mismatch
aborts the study and preserves its manifest, completed attempts and checkpoint.
"""

import argparse
import ast
import hashlib
import inspect
import json
import math
import os
from pathlib import Path
import platform
import re
import statistics
import subprocess
import sys

sys.dont_write_bytecode = True

SOURCE_COMMIT = "5ff2ca2caf175b63243532a500104f26952df3db"
PROTOCOL_COMMIT = "f72f479a0a2cefb1eb96305d2628b8eaae9a19bd"
PROTOCOL_PATH = "docs/lightlag-overnight-evaluation.md"
MODEL_SUMMARY = "docs/lightlag-runs/fixed-seeds501-504-summary.json"
ORIGINAL = "kf_mpc"
CANDIDATE = "EKF_sandodo_stayalive_aimdisc_turncost_window_MPC_manh_controller_24"
PROFILES = ("rush", "rush_noisy")
PUBLIC_NAMES = ("rules", "map", "telemetry_log", "uplink", "advance")
SOURCE_PATHS = (
    "lightlag/__init__.py", "lightlag/controllers/__init__.py",
    "lightlag/controllers/api.py", "lightlag/controllers/baselines.py",
    "lightlag/controllers/geometry.py", "lightlag/controllers/predictor.py",
    "lightlag/controllers/reference.py", "lightlag/environment.py",
    "lightlag/evaluation.py", "lightlag/model.py", "lightlag_dynamic/__init__.py",
    "lightlag_dynamic/controllers.py", "lightlag_dynamic/environment.py",
    "lightlag_dynamic/kf_mpc.py", "lightlag_dynamic/manh_controllers/__init__.py",
    "lightlag_dynamic/manh_controllers/controllers.py",
    "lightlag_dynamic/manh_controllers/estimators.py", "lightlag_dynamic/missions.py",
    "lightlag_dynamic/tools.py",
)


class SourceMismatch(RuntimeError):
    pass


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def canonical(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode() + b"\n"


def write_json(path, data):
    path.write_bytes(canonical(data))


def read_json(path):
    return json.loads(path.read_text())


def claim_output(path):
    """mkdir is the exclusive claim; never touch an existing output directory."""
    path.mkdir(exist_ok=False)
    return path


def verify_hashes(root, expected):
    mismatches = [name for name, digest in expected.items()
                  if not (root / name).is_file() or sha256((root / name).read_bytes()) != digest]
    if mismatches:
        raise SourceMismatch("Frozen bytes differ: " + ", ".join(sorted(mismatches)))


def clean_error(failure):
    # Exceptions contain no credentials by design; still remove local machine paths.
    message = str(failure)
    for prefix in (str(Path.home()), str(Path.cwd())):
        message = message.replace(prefix, "<LOCAL_PATH>")
    message = re.sub(r"/(?:private/)?tmp/[^\s'\"]+", "<TEMP_PATH>", message)
    return {"type": type(failure).__name__, "message": message}


def attempt_episode(invoke):
    """Exactly one invocation; failures are observations, never zero rewards."""
    try:
        return {"status": "ok", "episode": invoke(), "error": None}
    except Exception as failure:
        return {"status": "execution_error", "episode": None,
                "error": clean_error(failure),
                "limitation": "Shared run_episode propagates failures without returning a partial transcript."}


def episode_row(case, outcome, filename):
    row = dict(case, status=outcome["status"], error=outcome["error"], episode_file=filename)
    fields = ("raw_score", "maximum", "normalized_score", "sampled_value", "alive", "at_base",
              "alive_and_at_base", "policy_calls", "evaluator_calls", "total_calls")
    row.update(dict.fromkeys(fields))
    if outcome["status"] == "ok":
        episode, result = outcome["episode"], outcome["episode"]["result"]
        row.update(raw_score=result["raw_score"], maximum=result["max_available_value"],
                   normalized_score=result["raw_score"] / result["max_available_value"],
                   sampled_value=result["sampled_value"], alive=result["alive"], at_base=result["at_base"],
                   alive_and_at_base=result["alive"] and result["at_base"],
                   policy_calls=episode["tool_calls"]["policy"],
                   evaluator_calls=episode["tool_calls"]["evaluator"],
                   total_calls=episode["tool_calls"]["total"])
    return row


def compare_reference(episode, replay, result, reward_text):
    expected_result = {key: value for key, value in result.items() if key != "tool_calls"}
    score = episode["result"]["raw_score"] / episode["result"]["max_available_value"]
    checks = {
        "replay_equal": episode["replay"] == replay,
        "result_equal": episode["result"] == expected_result,
        "policy_call_count_equal": episode["tool_calls"]["policy"] == result["tool_calls"],
        "six_decimal_harbor_reward_equal": f"{score:.6f}" == reward_text.strip(),
        "replay_canonical_sha256": sha256(canonical(episode["replay"])),
        "frozen_replay_canonical_sha256": sha256(canonical(replay)),
    }
    checks["passed"] = all(value for value in checks.values() if isinstance(value, bool))
    return checks


def mean(values):
    return math.fsum(values) / len(values) if values else None


def paired_statistics(rows):
    groups = []
    for selection in ("historical", "fresh"):
        for profile in PROFILES:
            selected = [r for r in rows if r["set"] == selection and r["profile"] == profile]
            if not selected:
                continue
            by_cell = {(r["seed"], r["policy"]): r for r in selected}
            pairs = []
            for seed in sorted({r["seed"] for r in selected}):
                old, new = (by_cell.get((seed, name)) for name in (ORIGINAL, CANDIDATE))
                if old and new and old["status"] == new["status"] == "ok":
                    pairs.append({"seed": seed,
                                  "original": old["normalized_score"],
                                  "candidate": new["normalized_score"],
                                  "candidate_minus_original": new["normalized_score"] - old["normalized_score"],
                                  "raw_candidate_minus_original": new["raw_score"] - old["raw_score"]})
            differences = [p["candidate_minus_original"] for p in pairs]
            policies = []
            for name in (ORIGINAL, CANDIDATE):
                attempted = [r for r in selected if r["policy"] == name]
                valid = [r for r in attempted if r["status"] == "ok"]
                policies.append({"policy": name, "attempted": len(attempted), "scored": len(valid),
                                 "errors": len(attempted) - len(valid),
                                 "mean_normalized_score": mean([r["normalized_score"] for r in valid]),
                                 "mean_raw_score": mean([r["raw_score"] for r in valid]),
                                 "alive": sum(r["alive"] for r in valid),
                                 "at_base": sum(r["at_base"] for r in valid),
                                 "alive_and_at_base": sum(r["alive"] and r["at_base"] for r in valid),
                                 "mean_policy_calls": mean([r["policy_calls"] for r in valid])})
            groups.append({"set": selection, "profile": profile, "policies": policies,
                           "complete_pairs": len(pairs),
                           "incomplete_pairs": len({r["seed"] for r in selected}) - len(pairs),
                           "mean_candidate_minus_original": mean(differences),
                           "median_candidate_minus_original": statistics.median(differences) if differences else None,
                           "mean_raw_candidate_minus_original": mean([p["raw_candidate_minus_original"] for p in pairs]),
                           "candidate_wins": sum(d > 1e-12 for d in differences),
                           "ties": sum(abs(d) <= 1e-12 for d in differences),
                           "original_wins": sum(d < -1e-12 for d in differences),
                           "pairs": pairs})
    return groups


def plan():
    # All eight original historical runs must pass before any candidate outcome.
    cases = [{"set": "historical", "profile": profile, "seed": seed, "policy": policy}
             for policy in (ORIGINAL, CANDIDATE) for profile in PROFILES for seed in range(501, 505)]
    cases.extend({"set": "fresh", "profile": profile, "seed": seed, "policy": policy}
                 for profile in PROFILES for seed in range(3000, 3020)
                 for policy in (ORIGINAL, CANDIDATE))
    return cases


def reference_path(case):
    profile = case["profile"].replace("_", "-")
    return f"docs/lightlag-runs/{profile}-seed{case['seed']}-delay3-kf-mpc"


def git_bytes(repo, revision, relative):
    return subprocess.check_output(["git", "show", f"{revision}:{relative}"], cwd=repo,
                                   stderr=subprocess.DEVNULL)


def build_manifest(repo, source_root):
    source_hashes = {path: sha256(git_bytes(repo, SOURCE_COMMIT, path)) for path in SOURCE_PATHS}
    inputs = [MODEL_SUMMARY]
    for case in plan()[:8]:
        base = reference_path(case)
        inputs.extend(base + "/" + suffix for suffix in (
            "experiment.json", "artifacts/evaluator/replay.json",
            "artifacts/evaluator/result.json", "verifier/reward.txt"))
    input_hashes = {path: sha256(git_bytes(repo, SOURCE_COMMIT, path)) for path in inputs}
    protocol = git_bytes(repo, PROTOCOL_COMMIT, PROTOCOL_PATH)
    script = Path(__file__).read_bytes()
    manifest = {
        "schema_version": 1, "source_commit": SOURCE_COMMIT, "protocol_commit": PROTOCOL_COMMIT,
        "source_sha256": source_hashes, "frozen_input_sha256": input_hashes,
        "protocol": {"path": PROTOCOL_PATH, "sha256": sha256(protocol)},
        "runner": {"repository_path": "tools/lightlag_experiments/overnight_references.py",
                   "sha256": sha256(script), "snapshot": "runner.py"},
        "source_location": "isolated snapshot; every file compared with git show at source_commit",
        "settings": {"delay": 3, "horizon": 50, "noise_level": 1.0, "bumpiness": 0.0},
        "policies": [ORIGINAL, CANDIDATE], "sets": {"historical": list(range(501, 505)),
                                                   "fresh": list(range(3000, 3020))},
        "profiles": list(PROFILES), "planned_episodes": 96,
        "normalization": "raw_score / max_available_value; never divided by a reference score",
        "execution_order": "historical original/profile/seed, historical candidate/profile/seed, fresh profile/seed/policy",
        "retries": 0, "paid_inference_calls": 0, "reported_api_cost_usd": 0,
    }
    return manifest, protocol, script


def preflight(source_root):
    if os.environ.get("LIGHTLAG_REPO"):
        raise RuntimeError("Unset LIGHTLAG_REPO; an alternate source injection is not allowed")
    sys.path.insert(0, str(source_root))
    import numpy
    from lightlag.controllers.api import PublicTools
    from lightlag.evaluation import run_episode
    from lightlag.model import Config
    from lightlag_dynamic.controllers import kf_mpc
    from lightlag_dynamic.environment import DynamicEnvironment
    from lightlag_dynamic.manh_controllers.controllers import (
        Current, EKF_sandodo_stayalive_aimdisc_turncost_window_MPC as Candidate)

    if platform.python_version() != "3.12.16" or numpy.__version__ != "2.5.4":
        raise RuntimeError("This study requires Python 3.12.16 and numpy 2.5.4")
    loaded = sorted({str(Path(module.__file__).resolve().relative_to(source_root))
                     for name, module in sys.modules.items()
                     if name.split(".")[0] in {"lightlag", "lightlag_dynamic"}
                     and getattr(module, "__file__", None)})
    if loaded != sorted(SOURCE_PATHS):
        raise SourceMismatch("Imported repository module closure differs from the declared 19 files")
    mro = [cls.__module__ + "." + cls.__name__ for cls in Candidate.__mro__]
    expected_names = ["EKF_sandodo_stayalive_aimdisc_turncost_window_MPC", "_StayAlive", "_WindowAware",
                      "_AimDisc", "_TurnCost", "_SandOdometer", "EKF_MPC", "LogMixin",
                      "KalmanMPCController", "Controller", "object"]
    if [cls.__name__ for cls in Candidate.__mro__] != expected_names:
        raise RuntimeError("Candidate MRO differs from the statically reviewed public controller")
    if tuple(inspect.signature(Candidate).parameters) != ("tools",):
        raise RuntimeError("Candidate constructor must receive only tools")
    if tuple(PublicTools.__slots__) != PUBLIC_NAMES:
        raise RuntimeError("Public callback interface changed")
    accesses = set()
    for cls in Candidate.__mro__[:-1]:
        tree = ast.parse(inspect.getsource(cls))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                if node.attr in {"_env", "__closure__", "__globals__"}:
                    raise RuntimeError("Privileged or introspective attribute in candidate MRO")
                receiver = node.value
                if ((isinstance(receiver, ast.Name) and receiver.id == "tools")
                    or (isinstance(receiver, ast.Attribute) and receiver.attr == "tools")):
                    accesses.add(node.attr)
    if not accesses <= set(PUBLIC_NAMES):
        raise RuntimeError("Candidate uses a nonpublic tool attribute")
    Current.logger = None
    evidence = {"candidate_mro": mro, "candidate_constructor": str(inspect.signature(Candidate)),
                "public_tool_attributes_in_mro": sorted(accesses), "logger": None,
                "environment": "lightlag_dynamic.environment.DynamicEnvironment",
                "runner_boundary": "lightlag.evaluation.run_episode -> PublicTools callbacks",
                "registry_wrapper_used": False, "oracle_used": False, "scenario_environment_used": False,
                "static_review": "Inspected all MRO classes, their planner/filter helpers and the shared runner before outcomes.",
                "limitation": "Trusted Python callback boundary, not a sandbox against introspection.",
                "loaded_source_files": loaded}
    dependencies = {"python": platform.python_version(), "python_implementation": platform.python_implementation(),
                    "python_build": sys.version, "numpy": numpy.__version__,
                    "os": platform.system(), "architecture": platform.machine(),
                    "third_party_requirements": ["numpy==2.5.4"]}

    def invoke(case):
        Current.logger = None

        def policy(tools):
            if type(tools) is not PublicTools:
                raise RuntimeError("Expected only the shared PublicTools callbacks")
            if case["policy"] == ORIGINAL:
                kf_mpc(tools)
            else:
                Candidate(tools).run()
            if Current.logger is not None:
                raise RuntimeError("Privileged logger must remain disabled")

        def factory(*, seed, config, world):
            if world is not None:
                raise RuntimeError("This study generates the declared seeded mission")
            return DynamicEnvironment(seed=seed, config=config, profile=case["profile"],
                                      noise_level=1.0, bumpiness=0.0)

        return run_episode(policy, seed=case["seed"], config=Config(delay_ticks=3, max_ticks=50),
                           policy_name=case["policy"], environment_factory=factory)

    return invoke, evidence, dependencies


def historical_model_comparison(rows, model_summary):
    lookup = {(r["profile"], r["seed"], r["policy"]): r for r in rows if r["set"] == "historical"}
    comparisons = []
    for old in model_summary["model_runs"]:
        candidate = lookup.get((old["profile"], old["seed"], CANDIDATE))
        original = lookup.get((old["profile"], old["seed"], ORIGINAL))
        if not candidate or candidate["status"] != "ok" or not original or original["status"] != "ok":
            continue
        model = old["raw_score"] / old["maximum"]
        comparisons.append({"profile": old["profile"], "seed": old["seed"],
                            "original_model_evidence": "docs/lightlag-runs/" + old["evidence"],
                            "model_score": model, "original_reference_score": original["normalized_score"],
                            "candidate_score": candidate["normalized_score"],
                            "model_minus_candidate": model - candidate["normalized_score"]})
    groups = []
    for profile in PROFILES:
        cells = [r for r in comparisons if r["profile"] == profile]
        groups.append({"profile": profile, "paired_cells": len(cells),
                       "mean_model": mean([r["model_score"] for r in cells]),
                       "mean_original_reference": mean([r["original_reference_score"] for r in cells]),
                       "mean_candidate": mean([r["candidate_score"] for r in cells]),
                       "model_wins": sum(r["model_minus_candidate"] > 1e-12 for r in cells),
                       "ties": sum(abs(r["model_minus_candidate"]) <= 1e-12 for r in cells),
                       "candidate_wins": sum(r["model_minus_candidate"] < -1e-12 for r in cells)})
    return {"label": "Post-hoc reference substitution for the eight ORIGINAL model attempts; no new model runs",
            "limitation": "Does not replace canonical references or original audit attribution. Fresh controller seeds have no model outcomes.",
            "rows": comparisons, "by_profile": groups}


def summary_for(rows, cases, checks, model_summary, status, abort):
    return {"schema_version": 1, "status": status, "abort": abort, "planned_episodes": len(cases),
            "attempted_episodes": len(rows), "scored_episodes": sum(r["status"] == "ok" for r in rows),
            "execution_errors": [r for r in rows if r["status"] == "execution_error"],
            "invalid_source_episodes": [r for r in rows if r["status"] == "source_mismatch"],
            "unrun_cases": cases[len(rows):], "historical_reference_gate": checks,
            "historical_reference_gate_passed": len(checks) == 8 and all(c["passed"] for c in checks),
            "rows": rows, "paired_statistics": paired_statistics(rows),
            "historical_original_model_vs_candidate": historical_model_comparison(rows, model_summary),
            "interpretation_limits": ["One fixed candidate; no per-map selection or tuning on these outcomes.",
                                      "Fresh set measures controller strength, not model performance.",
                                      "A deterministic reproduction is not an independent sample.",
                                      "Both controllers are feasible public-information baselines, not optima.",
                                      "Per-policy means use successful executions only; all error and pair counts are explicit."],
            "paid_inference_calls": 0, "reported_api_cost_usd": 0}


def compare_outputs(output, prior):
    names = sorted(p.relative_to(output).as_posix() for p in output.rglob("*")
                   if p.is_file() and p.name != "reproduction.json")
    previous = sorted(p.relative_to(prior).as_posix() for p in prior.rglob("*")
                      if p.is_file() and p.name != "reproduction.json")
    mismatches = [name for name in names if not (prior / name).is_file()
                  or (prior / name).read_bytes() != (output / name).read_bytes()]
    check = {"same_file_set": names == previous, "files_compared": len(names),
             "byte_mismatches": mismatches, "passed": names == previous and not mismatches,
             "note": "Deterministic reproduction only; not additional independent samples."}
    write_json(output / "reproduction.json", check)
    return check["passed"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--compare-to", type=Path)
    args = parser.parse_args()
    repo = next(p for p in Path(__file__).resolve().parents if (p / "AGENTS.md").exists())
    source_root = args.source_root.resolve()
    output = claim_output(args.output.resolve())
    rows, checks, cases = [], [], plan()
    model_summary = {"model_runs": []}
    try:
        manifest, protocol, script = build_manifest(repo, source_root)
        write_json(output / "source-manifest.json", manifest)
        (output / "protocol.md").write_bytes(protocol)
        (output / "runner.py").write_bytes(script)

        def verify():
            verify_hashes(source_root, manifest["source_sha256"])
            verify_hashes(repo, manifest["frozen_input_sha256"])
            if sha256(Path(__file__).read_bytes()) != manifest["runner"]["sha256"]:
                raise SourceMismatch("Study runner changed during execution")

        verify()
        invoke, boundary, dependencies = preflight(source_root)
        manifest.update(boundary_preflight=boundary, dependencies=dependencies)
        write_json(output / "source-manifest.json", manifest)
        # The original simulator/controller bytes also match all historical task manifests.
        for case in cases[:8]:
            frozen = read_json(repo / reference_path(case) / "experiment.json")
            for path, digest in frozen["source_sha256"].items():
                if path in manifest["source_sha256"] and digest != manifest["source_sha256"][path]:
                    raise SourceMismatch("Historical task source mismatch: " + path)
        model_summary = read_json(repo / MODEL_SUMMARY)
        (output / "episodes").mkdir()
        for index, case in enumerate(cases, 1):
            verify()
            outcome = attempt_episode(lambda: invoke(case))
            source_failure = None
            try:
                verify()
            except SourceMismatch as failure:
                source_failure = failure
                outcome.update(status="source_mismatch", error=clean_error(failure))
            short = "kf_mpc" if case["policy"] == ORIGINAL else "candidate24"
            filename = f"episodes/{index:03d}-{case['set']}-{case['profile']}-{case['seed']}-{short}.json"
            write_json(output / filename, dict(case=case, **outcome))
            row = episode_row(case, outcome, filename)
            row["episode_sha256"] = sha256((output / filename).read_bytes())
            rows.append(row)
            if case["set"] == "historical" and case["policy"] == ORIGINAL:
                if outcome["status"] == "ok":
                    base = repo / reference_path(case)
                    check = compare_reference(outcome["episode"], read_json(base / "artifacts/evaluator/replay.json"),
                                              read_json(base / "artifacts/evaluator/result.json"),
                                              (base / "verifier/reward.txt").read_text())
                else:
                    check = {"passed": False, "reason": "Original reference execution did not succeed"}
                checks.append(dict(profile=case["profile"], seed=case["seed"], **check))
            write_json(output / "summary.json", summary_for(rows, cases, checks, model_summary, "running", None))
            print(json.dumps({"attempt": index, "set": case["set"], "profile": case["profile"],
                              "seed": case["seed"], "policy": short, "status": row["status"],
                              "normalized_score": row["normalized_score"]}), flush=True)
            if source_failure:
                raise source_failure
            if checks and not checks[-1]["passed"]:
                raise RuntimeError("Historical full-replay gate failed; candidate interpretation is blocked")
        verify()
        status = "complete" if all(r["status"] == "ok" for r in rows) else "complete_with_execution_errors"
        write_json(output / "summary.json", summary_for(rows, cases, checks, model_summary, status, None))
    except (Exception, KeyboardInterrupt) as failure:
        write_json(output / "summary.json", summary_for(rows, cases, checks, model_summary, "aborted", clean_error(failure)))
        print(json.dumps({"status": "aborted", "error": clean_error(failure)}), flush=True)
        return 1
    if args.compare_to and not compare_outputs(output, args.compare_to.resolve()):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
