"""Rebuild all saved calls and verify four preselected policy repetitions."""

import argparse
import ast
from collections import Counter
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import statistics
import subprocess
import sys

sys.dont_write_bytecode = True


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_text())


def close(left, right):
    assert math.isclose(left, right, abs_tol=1e-14), (left, right)


def mission_inputs(replay):
    """Separate fixed mission metadata from policy-dependent event histories."""
    dynamic = json.loads(json.dumps(replay["dynamic"]))
    for section, events in (("sensing", "heading_errors"), ("roughness", "spins")):
        if section in dynamic:
            dynamic[section].pop(events, None)
    return dynamic


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--write-reports", action="store_true")
    args = parser.parse_args()
    study = Path(__file__).resolve().parent
    repo = next(p for p in study.parents if (p / "AGENTS.md").exists())
    primary = study / "primary"
    if args.write_reports:
        for name in ("verification.json", "representative-reruns.json"):
            if (study / name).exists():
                raise FileExistsError("Verification output already exists: " + name)
    manifest, summary = read(primary / "source-manifest.json"), read(primary / "summary.json")
    for path, expected in manifest["source_sha256"].items():
        committed = subprocess.check_output(["git", "show", manifest["source_commit"] + ":" + path], cwd=repo)
        assert sha(committed) == expected == sha((args.source_root / path).read_bytes())
    for path, expected in manifest["input_sha256"].items():
        assert sha((repo / path).read_bytes()) == expected
    runner_path = repo / "tools/lightlag_experiments/overnight_reference27.py"
    assert sha(runner_path.read_bytes()) == manifest["runner_sha256"] == sha((primary / "runner.py").read_bytes())
    assert sha((primary / "shared-runner.py").read_bytes()) == manifest["shared_helper_sha256"]
    assert sha((primary / "protocol.md").read_bytes()) == manifest["protocol_sha256"]
    prior_manifest = read(repo / "docs/lightlag-runs/overnight-reference-study/primary/source-manifest.json")
    unchanged = [p for p in manifest["source_sha256"] if p != "lightlag_dynamic/manh_controllers/controllers.py"]
    assert len(unchanged) == 18
    assert all(manifest["source_sha256"][p] == prior_manifest["source_sha256"][p] for p in unchanged)
    path = "lightlag_dynamic/manh_controllers/controllers.py"
    old = subprocess.check_output(["git", "show", manifest["prior_source_commit"] + ":" + path], cwd=repo).decode()
    new = (args.source_root / path).read_text()
    definitions = lambda text: {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(text).body
                               if isinstance(n, (ast.ClassDef, ast.FunctionDef))}
    old_defs, new_defs = definitions(old), definitions(new)
    assert len(old_defs) == 39 and all(new_defs.get(name) == value for name, value in old_defs.items())
    assert manifest["compatibility"]["preserved_existing_definition_ast_sha256"] == {
        name: sha(value.encode()) for name, value in old_defs.items()}
    assert summary["status"] == "complete" and summary["attempted"] == summary["scored"] == 48
    assert not summary["execution_errors"] and not summary["source_mismatch_rows"] and not summary["unrun_cases"]
    expected_cells = {(selection, profile, seed)
                      for selection, seeds in (("historical", range(501, 505)), ("inspected_controller", range(3000, 3020)))
                      for profile in ("rush", "rush_noisy") for seed in seeds}
    actual_cells = [(r["set"], r["profile"], r["seed"]) for r in summary["rows"]]
    assert len(actual_cells) == len(set(actual_cells)) == 48 and set(actual_cells) == expected_cells
    sys.path.insert(0, str(args.source_root.resolve()))
    from lightlag.model import Config
    from lightlag_dynamic.environment import DynamicEnvironment

    baselines = {}
    for row in summary["reused_baseline_rows"]:
        path = repo / row["source_episode"]
        assert sha(path.read_bytes()) == row["episode_sha256"]
        artifact = read(path)
        episode, result = artifact["episode"], artifact["episode"]["result"]
        assert episode["policy"] == row["policy"] and episode["seed"] == row["seed"]
        assert artifact["case"]["set"] == row["original_set_label"]
        assert result["mission_profile"] == row["profile"] and result["raw_score"] == row["raw_score"]
        assert row["normalized_score"] == result["raw_score"] / result["max_available_value"]
        assert row["maximum"] == result["max_available_value"]
        for name in ("alive", "at_base", "sampled_value"):
            assert row[name] == result[name]
        for name in ("policy", "evaluator", "total"):
            assert row[name + "_calls"] == episode["tool_calls"][name]
        baselines[row["set"], row["profile"], row["seed"], row["policy"]] = artifact
    assert len(baselines) == len(summary["reused_baseline_rows"]) == 96

    saved = {}
    total_calls = 0
    for row in summary["rows"]:
        path = primary / row["episode_file"]
        assert sha(path.read_bytes()) == row["episode_sha256"]
        artifact = read(path)
        assert artifact["status"] == "ok" and artifact["error"] is None
        assert artifact["case"] == {k: row[k] for k in ("set", "profile", "seed", "policy")}
        episode = artifact["episode"]
        assert episode["policy"] == row["policy"] == manifest["policy"] and episode["seed"] == row["seed"]
        env = DynamicEnvironment(seed=row["seed"], config=Config(delay_ticks=3, max_ticks=50),
                                 profile=row["profile"], noise_level=1.0, bumpiness=0.0)
        counts = Counter()
        for record in episode["transcript"]:
            counts[record["source"], record["tool"]] += 1
            assert getattr(env, record["tool"])(**record["request"]) == record["result"]
        assert env.replay() == episode["replay"], row["episode_file"]
        assert env.evaluate() == episode["result"] == episode["replay"]["result"]
        result = episode["result"]
        assert result["tick"] == 50 and episode["delay"] == 3
        assert row["raw_score"] == result["raw_score"] and row["maximum"] == result["max_available_value"]
        assert row["normalized_score"] == result["raw_score"] / result["max_available_value"]
        for name in ("alive", "at_base", "sampled_value"):
            assert row[name] == result[name]
        assert row["alive_and_at_base"] == (result["alive"] and result["at_base"])
        for who in ("policy", "evaluator"):
            assert sum(v for (source, _), v in counts.items() if source == who) == row[who + "_calls"] == episode["tool_calls"][who]
            assert all(counts[who, tool] == count for tool, count in episode["tool_calls"]["by_tool"][who].items())
        assert len(episode["transcript"]) == row["total_calls"] == episode["tool_calls"]["total"]
        total_calls += len(episode["transcript"])
        for key, old_artifact in baselines.items():
            if key[:3] == (row["set"], row["profile"], row["seed"]):
                old_episode = old_artifact["episode"]
                for field in ("world", "config", "seed"):
                    assert old_episode["replay"][field] == episode["replay"][field]
                assert mission_inputs(old_episode["replay"]) == mission_inputs(episode["replay"])
                assert old_episode["rules"] == episode["rules"]
                assert old_episode["result"]["max_available_value"] == row["maximum"]
        saved[row["set"], row["profile"], row["seed"]] = (row, artifact)

    for group in summary["aggregates"]:
        rows = [r for r in summary["rows"] if (r["set"], r["profile"]) == (group["set"], group["profile"])]
        assert group["attempted"] == group["scored"] == len(rows) and group["errors"] == 0
        for field, source in (("mean_normalized_score", "normalized_score"), ("mean_raw_score", "raw_score"),
                              ("mean_policy_calls", "policy_calls")):
            close(group[field], statistics.mean(r[source] for r in rows))
        for field in ("alive", "at_base", "alive_and_at_base"):
            assert group[field] == sum(r[field] for r in rows)
    for group in summary["paired_vs_original"] + summary["paired_vs_candidate24"]:
        differences, raw, new_scores, old_scores = [], [], [], []
        for pair in group["pairs"]:
            _, artifact = saved[group["set"], group["profile"], pair["seed"]]
            new_result = artifact["episode"]["result"]
            old_result = baselines[group["set"], group["profile"], pair["seed"], group["baseline_policy"]]["episode"]["result"]
            new_score = new_result["raw_score"] / new_result["max_available_value"]
            old_score = old_result["raw_score"] / old_result["max_available_value"]
            assert pair["candidate27"] == new_score and pair["baseline"] == old_score
            assert pair["candidate27_minus_baseline"] == new_score - old_score
            assert pair["raw_difference"] == new_result["raw_score"] - old_result["raw_score"]
            differences.append(new_score - old_score); raw.append(pair["raw_difference"])
            new_scores.append(new_score); old_scores.append(old_score)
        assert len(differences) == group["complete_pairs"] == (4 if group["set"] == "historical" else 20)
        assert group["incomplete_pairs"] == 0
        close(group["mean_candidate27_minus_baseline"], statistics.mean(differences))
        close(group["mean_raw_difference"], statistics.mean(raw))
        close(group["mean_candidate27"], statistics.mean(new_scores))
        close(group["mean_baseline"], statistics.mean(old_scores))
        assert group["median_candidate27_minus_baseline"] == statistics.median(differences)
        assert group["candidate27_wins"] == sum(d > 1e-12 for d in differences)
        assert group["ties"] == sum(abs(d) <= 1e-12 for d in differences)
        assert group["baseline_wins"] == sum(d < -1e-12 for d in differences)
    models = summary["historical_original_model_comparison"]
    assert len(models["rows"]) == 8
    for row in models["rows"]:
        result = read(repo / row["model_evidence"] / "artifacts/evaluator/result.json")
        assert row["model_score"] == result["raw_score"] / result["max_available_value"]
        candidate = saved["historical", row["profile"], row["seed"]][0]
        assert row["candidate27"] == candidate["normalized_score"]
        assert row["model_minus_candidate27"] == row["model_score"] - row["candidate27"]
    for group in models["by_profile"]:
        rows = [r for r in models["rows"] if r["profile"] == group["profile"]]
        assert group["paired_cells"] == len(rows) == 4
        close(group["mean_model"], statistics.mean(r["model_score"] for r in rows))
        close(group["mean_candidate27"], statistics.mean(r["candidate27"] for r in rows))
        assert group["model_wins"] == sum(r["model_minus_candidate27"] > 1e-12 for r in rows)
        assert group["ties"] == sum(abs(r["model_minus_candidate27"]) <= 1e-12 for r in rows)
        assert group["candidate27_wins"] == sum(r["model_minus_candidate27"] < -1e-12 for r in rows)

    spec = importlib.util.spec_from_file_location("supplement_verified", runner_path)
    runner = importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)
    common = runner.load_common(repo)
    invoke, boundary, dependencies = runner.public_runtime(args.source_root, common)
    assert boundary == manifest["boundary_preflight"] and dependencies == manifest["dependencies"]
    reruns = []
    for cell in runner.RERUN_CELLS:
        common.verify_hashes(args.source_root, manifest["source_sha256"])
        row, original = saved[cell]
        outcome = common.attempt_episode(lambda: invoke(original["case"]))
        common.verify_hashes(args.source_root, manifest["source_sha256"])
        artifact = dict(case=original["case"], **outcome)
        record = {"case": original["case"], "status": outcome["status"], "error": outcome["error"],
                  "normalized_score": None if outcome["status"] != "ok" else outcome["episode"]["result"]["raw_score"] / outcome["episode"]["result"]["max_available_value"],
                  "primary_episode_sha256": row["episode_sha256"],
                  "rerun_episode_sha256": sha(common.canonical(artifact)),
                  "full_episode_equal": artifact == original}
        reruns.append(record)
    proof = {"passed": all(r["full_episode_equal"] for r in reruns), "repetitions": len(reruns),
             "role": "Four predetermined deterministic verification repetitions; outside the 48 primary study rows",
             "rows": reruns, "duplicate_trajectory_files_stored": 0}
    assert len(reruns) == 4
    patterns = [r"/Users/[^/\s]+/", r"/home/[^/\s]+/", r"sk-ant-[A-Za-z0-9_-]+",
                r"sk-proj-[A-Za-z0-9_-]+", r"ghp_[A-Za-z0-9]{20,}", r"Bearer [A-Za-z0-9_-]{20,}"]
    for path in primary.rglob("*.json"):
        assert not any(re.search(pattern, path.read_text()) for pattern in patterns), path.name
    report = {"passed": proof["passed"], "primary_unique_attempts": 48, "primary_execution_errors": 0,
              "source_files_verified_against_commit": 19, "unchanged_dependency_files": 18,
              "preserved_existing_class_and_helper_definitions": 39,
              "verified_input_files": len(manifest["input_sha256"]), "reused_baseline_rows_verified": 96,
              "independent_full_transcript_replays": 48, "public_and_evaluator_calls_replayed": total_calls,
              "paired_comparison_groups_recomputed": 8, "historical_model_results_checked": 8,
              "preselected_deterministic_policy_repetitions": 4,
              "full_episode_equal_repetitions": sum(r["full_episode_equal"] for r in reruns),
              "private_path_and_token_pattern_scan": "passed; scientific JSON only",
              "verification_script_sha256": sha(Path(__file__).read_bytes())}
    if args.write_reports:
        for name, data in (("representative-reruns.json", proof), ("verification.json", report)):
            with (study / name).open("x") as stream:
                stream.write(json.dumps(data, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
