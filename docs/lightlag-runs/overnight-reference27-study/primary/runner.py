"""Run the separately declared candidate-27 supplement on 48 inspected cells.

No paid calls, retries, seed replacements or canonical-reference changes.
The approved first study supplies immutable comparison rows and small helpers.
"""

import argparse
import ast
import hashlib
import importlib.util
import inspect
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys

sys.dont_write_bytecode = True

SOURCE_COMMIT = "bdb77f629d1cee55d12c4275e5f31d351143361e"
PROTOCOL_COMMIT = "d9d5d32d244e52293c7bdfc0ad317f4d57962529"
PRIOR_STUDY_COMMIT = "187601048b30c0686d5867ebc76781baf65b25a8"
PRIOR = "docs/lightlag-runs/overnight-reference-study/primary"
HELPER = "tools/lightlag_experiments/overnight_references.py"
MANH_PATH = "lightlag_dynamic/manh_controllers/controllers.py"
POLICY = "EKF_fading_sandfilter_sandodo_guarded_aimdisc_turncost_window_MPC_manh_controller_27"
SETS = ("historical", "inspected_controller")
PROFILES = ("rush", "rush_noisy")
RERUN_CELLS = (("historical", "rush", 501), ("historical", "rush_noisy", 504),
               ("inspected_controller", "rush", 3000), ("inspected_controller", "rush_noisy", 3019))


def repository_root():
    return next(p for p in Path(__file__).resolve().parents if (p / "AGENTS.md").exists())


def git_bytes(repo, commit, path):
    return subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=repo,
                                   stderr=subprocess.DEVNULL)


def load_common(repo):
    data = git_bytes(repo, PRIOR_STUDY_COMMIT, HELPER)
    if (repo / HELPER).read_bytes() != data:
        raise RuntimeError("First-study helper differs from its published bytes")
    spec = importlib.util.spec_from_file_location("reference_study_common", repo / HELPER)
    common = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(common)
    return common


def compatible_dependencies(prior, current):
    if set(prior) != set(current):
        raise RuntimeError("Source closure differs from the first study")
    unchanged = [path for path in sorted(prior) if path != MANH_PATH and prior[path] == current[path]]
    if len(unchanged) != len(prior) - 1:
        raise RuntimeError("Simulator/original-reference dependency changed; baseline reuse is blocked")
    return unchanged


def preserved_definitions(old, new):
    def definitions(text):
        return {node.name: ast.dump(node, include_attributes=False) for node in ast.parse(text).body
                if isinstance(node, (ast.ClassDef, ast.FunctionDef))}
    previous, current = definitions(old), definitions(new)
    if any(current.get(name) != definition for name, definition in previous.items()):
        raise RuntimeError("An existing candidate-24 class/helper changed; baseline reuse is blocked")
    return {name: hashlib.sha256(value.encode()).hexdigest() for name, value in sorted(previous.items())}


def plan():
    return [{"set": selection, "profile": profile, "seed": seed, "policy": POLICY}
            for selection, seeds in ((SETS[0], range(501, 505)), (SETS[1], range(3000, 3020)))
            for profile in PROFILES for seed in seeds]


def mark_source_failure(outcome, error):
    if outcome["status"] == "execution_error":
        outcome["execution_error"] = outcome["error"]
    outcome.update(status="source_mismatch", error=error)


def mean(values):
    return math.fsum(values) / len(values) if values else None


def paired_statistics(rows, baselines, baseline_policy):
    prior = {(r["set"], r["profile"], r["seed"]): r for r in baselines if r["policy"] == baseline_policy}
    groups = []
    for selection in SETS:
        for profile in PROFILES:
            selected = [r for r in rows if r["set"] == selection and r["profile"] == profile]
            if not selected:
                continue
            pairs = []
            for row in selected:
                baseline = prior.get((selection, profile, row["seed"]))
                if row["status"] == "ok" and baseline and baseline["status"] == "ok":
                    pairs.append({"seed": row["seed"], "candidate27": row["normalized_score"],
                                  "baseline": baseline["normalized_score"],
                                  "candidate27_minus_baseline": row["normalized_score"] - baseline["normalized_score"],
                                  "raw_difference": row["raw_score"] - baseline["raw_score"]})
            differences = [p["candidate27_minus_baseline"] for p in pairs]
            groups.append({"set": selection, "profile": profile, "baseline_policy": baseline_policy,
                           "complete_pairs": len(pairs), "incomplete_pairs": len(selected) - len(pairs),
                           "mean_candidate27": mean([p["candidate27"] for p in pairs]),
                           "mean_baseline": mean([p["baseline"] for p in pairs]),
                           "mean_candidate27_minus_baseline": mean(differences),
                           "median_candidate27_minus_baseline": statistics.median(differences) if differences else None,
                           "mean_raw_difference": mean([p["raw_difference"] for p in pairs]),
                           "candidate27_wins": sum(d > 1e-12 for d in differences),
                           "ties": sum(abs(d) <= 1e-12 for d in differences),
                           "baseline_wins": sum(d < -1e-12 for d in differences), "pairs": pairs})
    return groups


def source_manifest(repo, source_root, common):
    prior_manifest = common.read_json(repo / PRIOR / "source-manifest.json")
    prior_summary = common.read_json(repo / PRIOR / "summary.json")
    if (common.canonical(prior_manifest) != git_bytes(repo, PRIOR_STUDY_COMMIT, PRIOR + "/source-manifest.json")
        or common.canonical(prior_summary) != git_bytes(repo, PRIOR_STUDY_COMMIT, PRIOR + "/summary.json")):
        raise RuntimeError("First-study manifest/summary differs from published evidence")
    source_hashes = {path: common.sha256(git_bytes(repo, SOURCE_COMMIT, path))
                     for path in prior_manifest["source_sha256"]}
    unchanged = compatible_dependencies(prior_manifest["source_sha256"], source_hashes)
    old = git_bytes(repo, prior_manifest["source_commit"], MANH_PATH).decode()
    new = git_bytes(repo, SOURCE_COMMIT, MANH_PATH).decode()
    preserved = preserved_definitions(old, new)
    inputs = [PRIOR + "/" + name for name in ("source-manifest.json", "summary.json", "runner.py", "protocol.md")]
    inputs += [PRIOR + "/" + row["episode_file"] for row in prior_summary["rows"]]
    inputs += [HELPER, common.MODEL_SUMMARY]
    models = common.read_json(repo / common.MODEL_SUMMARY)
    inputs += ["docs/lightlag-runs/" + row["evidence"] + "/artifacts/evaluator/result.json"
               for row in models["model_runs"]]
    hashes = {path: common.sha256(git_bytes(repo, PRIOR_STUDY_COMMIT, path)) for path in inputs}
    common.verify_hashes(repo, hashes)
    common.verify_hashes(source_root, source_hashes)
    if (prior_summary["status"] != "complete" or prior_summary["scored_episodes"] != 96
        or not prior_summary["historical_reference_gate_passed"]):
        raise RuntimeError("First-study comparison rows are incomplete or not verified")
    baselines = []
    for row in prior_summary["rows"]:
        saved = dict(row, original_set_label=row["set"],
                     source_episode=PRIOR + "/" + row["episode_file"], source_study_commit=PRIOR_STUDY_COMMIT)
        saved["set"] = "inspected_controller" if row["set"] == "fresh" else row["set"]
        baselines.append(saved)
    expected = {(r["set"], r["profile"], r["seed"], p) for r in plan()
                for p in (common.ORIGINAL, common.CANDIDATE)}
    actual = [(r["set"], r["profile"], r["seed"], r["policy"]) for r in baselines]
    if len(actual) != 96 or set(actual) != expected or any(r["status"] != "ok" for r in baselines):
        raise RuntimeError("Baseline rows do not contain exactly the 96 approved comparison outcomes")
    protocol = git_bytes(repo, PROTOCOL_COMMIT, common.PROTOCOL_PATH)
    script = Path(__file__).read_bytes()
    manifest = {"schema_version": 1, "source_commit": SOURCE_COMMIT, "protocol_commit": PROTOCOL_COMMIT,
                "prior_study_commit": PRIOR_STUDY_COMMIT, "prior_source_commit": prior_manifest["source_commit"],
                "source_sha256": source_hashes, "input_sha256": hashes,
                "runner_sha256": common.sha256(script), "shared_helper_path": HELPER,
                "shared_helper_sha256": hashes[HELPER], "protocol_sha256": common.sha256(protocol),
                "compatibility": {"unchanged_dependency_files": unchanged,
                                  "changed_file": MANH_PATH, "preserved_existing_definition_ast_sha256": preserved,
                                  "passed": True},
                "policy": POLICY, "planned_new_attempts": 48, "reused_baseline_rows": 96,
                "selection": "Additional selected-policy comparison on already inspected cells; not an independent holdout",
                "settings": {"delay": 3, "horizon": 50, "noise_level": 1.0, "bumpiness": 0.0},
                "normalization": "raw_score / max_available_value",
                "sets": {"historical": list(range(501, 505)), "inspected_controller": list(range(3000, 3020))},
                "profiles": list(PROFILES), "execution_order": "set/profile/seed", "retries": 0,
                "representative_rerun_cells": [list(cell) for cell in RERUN_CELLS],
                "rerun_role": "Four predetermined verification repetitions, outside the 48 primary rows",
                "paid_inference_calls": 0, "reported_api_cost_usd": 0}
    return manifest, protocol, script, baselines, models


def public_runtime(source_root, common):
    if os.environ.get("LIGHTLAG_REPO"):
        raise RuntimeError("Unset LIGHTLAG_REPO before using the frozen source snapshot")
    sys.path.insert(0, str(source_root.resolve()))
    import numpy
    from lightlag.controllers.api import PublicTools
    from lightlag.evaluation import run_episode
    from lightlag.model import Config
    from lightlag_dynamic.environment import DynamicEnvironment
    from lightlag_dynamic.manh_controllers.controllers import (
        Current, EKF_fading_sandfilter_sandodo_guarded_aimdisc_turncost_window_MPC as Candidate)

    if platform.python_version() != "3.12.16" or numpy.__version__ != "2.5.4":
        raise RuntimeError("Requires Python 3.12.16 and numpy 2.5.4")
    loaded = sorted({str(Path(module.__file__).resolve().relative_to(source_root.resolve()))
                     for name, module in sys.modules.items()
                     if name.split(".")[0] in {"lightlag", "lightlag_dynamic"}
                     and getattr(module, "__file__", None)})
    if loaded != sorted(common.SOURCE_PATHS):
        raise RuntimeError("Imported source closure differs from the 19 frozen files")
    names = [cls.__name__ for cls in Candidate.__mro__]
    expected = ["EKF_fading_sandfilter_sandodo_guarded_aimdisc_turncost_window_MPC", "_GuardedMove", "_StayAlive",
                "_WindowAware", "_AimDisc", "_TurnCost", "_Unverified", "_FadingFilter", "_SandAwareFilter",
                "_SandOdometer", "EKF_MPC", "LogMixin", "KalmanMPCController", "Controller", "object"]
    if names != expected or tuple(inspect.signature(Candidate).parameters) != ("tools",):
        raise RuntimeError("Candidate constructor/MRO differs from the statically reviewed class")
    accesses = set()
    for cls in Candidate.__mro__[:-1]:
        for node in ast.walk(ast.parse(inspect.getsource(cls))):
            if isinstance(node, ast.Attribute):
                if node.attr in {"_env", "__closure__", "__globals__"}:
                    raise RuntimeError("Privileged/introspective attribute in candidate MRO")
                receiver = node.value
                if ((isinstance(receiver, ast.Name) and receiver.id == "tools")
                    or (isinstance(receiver, ast.Attribute) and receiver.attr == "tools")):
                    accesses.add(node.attr)
    if not accesses <= set(common.PUBLIC_NAMES) or tuple(PublicTools.__slots__) != common.PUBLIC_NAMES:
        raise RuntimeError("Candidate/public callback interface accesses an unexpected tool")
    Current.logger = None
    boundary = {"candidate_mro": [cls.__module__ + "." + cls.__name__ for cls in Candidate.__mro__],
                "constructor": str(inspect.signature(Candidate)), "public_tool_attributes": sorted(accesses),
                "logger": None, "registry_wrapper_used": False, "oracle_used": False,
                "scenario_environment_used": False, "scenario_factors_used": False,
                "environment": "plain lightlag_dynamic.environment.DynamicEnvironment",
                "evaluation": "lightlag.evaluation.run_episode with public callbacks only",
                "review": "Reviewed MRO and helpers before outcomes: terrain labels from public battery/packets; fading from public fixes; guarded prefixes from controller estimates and public rules.",
                "limitation": "Auditable trusted Python interface, not an introspection security sandbox",
                "loaded_source_files": loaded}
    dependencies = {"python": platform.python_version(), "python_implementation": platform.python_implementation(),
                    "python_build": sys.version, "numpy": numpy.__version__,
                    "third_party_requirements": ["numpy==2.5.4"],
                    "os": platform.system(), "architecture": platform.machine()}

    def policy(tools):
        if type(tools) is not PublicTools:
            raise RuntimeError("Candidate must receive only shared PublicTools callbacks")
        Current.logger = None
        Candidate(tools).run()
        if Current.logger is not None:
            raise RuntimeError("Privileged logging must remain disabled")

    def invoke(case):
        def factory(*, seed, config, world):
            if world is not None:
                raise RuntimeError("Only the declared seeded mission is allowed")
            return DynamicEnvironment(seed=seed, config=config, profile=case["profile"], noise_level=1.0, bumpiness=0.0)
        return run_episode(policy, seed=case["seed"], config=Config(delay_ticks=3, max_ticks=50),
                           policy_name=POLICY, environment_factory=factory)

    return invoke, boundary, dependencies


def summary_for(rows, baselines, models, common, status, abort):
    groups = []
    for selection in SETS:
        for profile in PROFILES:
            selected = [r for r in rows if r["set"] == selection and r["profile"] == profile]
            valid = [r for r in selected if r["status"] == "ok"]
            groups.append({"set": selection, "profile": profile, "attempted": len(selected),
                           "scored": len(valid), "errors": len(selected) - len(valid),
                           "mean_normalized_score": mean([r["normalized_score"] for r in valid]),
                           "mean_raw_score": mean([r["raw_score"] for r in valid]),
                           "mean_policy_calls": mean([r["policy_calls"] for r in valid]),
                           "alive": sum(r["alive"] for r in valid), "at_base": sum(r["at_base"] for r in valid),
                           "alive_and_at_base": sum(r["alive_and_at_base"] for r in valid)})
    lookup = {(r["profile"], r["seed"]): r for r in rows if r["set"] == "historical"}
    model_rows = []
    for old in models.get("model_runs", []):
        candidate = lookup.get((old["profile"], old["seed"]))
        if candidate and candidate["status"] == "ok":
            model = old["raw_score"] / old["maximum"]
            cell = {"profile": old["profile"], "seed": old["seed"], "model_score": model,
                    "model_evidence": "docs/lightlag-runs/" + old["evidence"],
                    "candidate27": candidate["normalized_score"],
                    "model_minus_candidate27": model - candidate["normalized_score"]}
            for label, name in (("original_reference", common.ORIGINAL), ("candidate24", common.CANDIDATE)):
                cell[label] = next(r["normalized_score"] for r in baselines
                                   if r["policy"] == name and r["profile"] == old["profile"] and r["seed"] == old["seed"])
            model_rows.append(cell)
    model_groups = []
    for profile in PROFILES:
        cells = [r for r in model_rows if r["profile"] == profile]
        model_groups.append({"profile": profile, "paired_cells": len(cells),
                             "mean_model": mean([r["model_score"] for r in cells]),
                             "mean_candidate27": mean([r["candidate27"] for r in cells]),
                             "model_wins": sum(r["model_minus_candidate27"] > 1e-12 for r in cells),
                             "ties": sum(abs(r["model_minus_candidate27"]) <= 1e-12 for r in cells),
                             "candidate27_wins": sum(r["model_minus_candidate27"] < -1e-12 for r in cells)})
    return {"schema_version": 1, "status": status, "abort": abort, "planned_new_attempts": 48,
            "attempted": len(rows), "scored": sum(r["status"] == "ok" for r in rows),
            "unrun_cases": plan()[len(rows):], "rows": rows, "aggregates": groups,
            "execution_errors": [r for r in rows if r["status"] == "execution_error" or r.get("execution_error")],
            "source_mismatch_rows": [r for r in rows if r["status"] == "source_mismatch"],
            "reused_baseline_rows": baselines,
            "paired_vs_original": paired_statistics(rows, baselines, common.ORIGINAL),
            "paired_vs_candidate24": paired_statistics(rows, baselines, common.CANDIDATE),
            "historical_original_model_comparison": {
                "label": "Retrospective reference substitution for the eight ORIGINAL model attempts; no new model runs",
                "rows": model_rows, "by_profile": model_groups},
            "limits": ["Additional selected policy on already inspected cells; not a new independent holdout.",
                       "Original and candidate-24 scores are reused after source compatibility and evidence checks.",
                       "No model outcomes exist for seeds 3000-3019.",
                       "Neither reference is an optimum; canonical references and audit attributions remain unchanged.",
                       "Successful-execution means exclude errors, whose null scores and counts are retained.",
                       "Representative reruns verify determinism, not additional independent samples."],
            "paid_inference_calls": 0, "reported_api_cost_usd": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output, repo = args.output.resolve(), repository_root()
    output.mkdir(exist_ok=False)
    rows, baselines, models, common = [], [], {}, None
    try:
        common = load_common(repo)
        manifest, protocol, script, baselines, models = source_manifest(repo, args.source_root, common)
        common.write_json(output / "source-manifest.json", manifest)
        (output / "runner.py").write_bytes(script)
        (output / "shared-runner.py").write_bytes((repo / HELPER).read_bytes())
        (output / "protocol.md").write_bytes(protocol)

        def verify():
            common.verify_hashes(args.source_root, manifest["source_sha256"])
            common.verify_hashes(repo, manifest["input_sha256"])
            if common.sha256(Path(__file__).read_bytes()) != manifest["runner_sha256"]:
                raise common.SourceMismatch("Supplement runner changed during execution")

        verify()
        invoke, boundary, dependencies = public_runtime(args.source_root, common)
        manifest.update(boundary_preflight=boundary, dependencies=dependencies)
        common.write_json(output / "source-manifest.json", manifest)
        (output / "episodes").mkdir()
        for index, case in enumerate(plan(), 1):
            verify()
            outcome = common.attempt_episode(lambda: invoke(case))
            source_failure = None
            try:
                verify()
            except common.SourceMismatch as failure:
                source_failure = failure
                mark_source_failure(outcome, common.clean_error(failure))
            filename = f"episodes/{index:03d}-{case['set']}-{case['profile']}-{case['seed']}-candidate27.json"
            common.write_json(output / filename, dict(case=case, **outcome))
            row = common.episode_row(case, outcome, filename)
            if outcome.get("execution_error"):
                row["execution_error"] = outcome["execution_error"]
            row["episode_sha256"] = common.sha256((output / filename).read_bytes())
            rows.append(row)
            common.write_json(output / "summary.json", summary_for(rows, baselines, models, common, "running", None))
            print(json.dumps({"attempt": index, "set": case["set"], "profile": case["profile"],
                              "seed": case["seed"], "status": row["status"],
                              "normalized_score": row["normalized_score"]}), flush=True)
            if source_failure:
                raise source_failure
        verify()
        status = "complete" if all(r["status"] == "ok" for r in rows) else "complete_with_execution_errors"
        common.write_json(output / "summary.json", summary_for(rows, baselines, models, common, status, None))
        return 0
    except (Exception, KeyboardInterrupt) as failure:
        error = common.clean_error(failure) if common else {"type": type(failure).__name__, "message": "Published helper failed verification"}
        result = summary_for(rows, baselines, models, common, "aborted", error) if common else {
            "status": "aborted", "abort": error, "rows": [], "unrun_cases": plan()}
        (output / "summary.json").write_text(json.dumps(result, sort_keys=True) + "\n")
        print(json.dumps({"status": "aborted", "error": error}), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
