"""Independently replay saved public calls and recompute the study arithmetic."""

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import sys

sys.dont_write_bytecode = True


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--reproduction-root", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    study = Path(__file__).resolve().parent
    repo = next(p for p in study.parents if (p / "AGENTS.md").exists())
    primary, reproduction = study / "primary", study / "reproduction"
    manifest, summary = read(primary / "source-manifest.json"), read(primary / "summary.json")
    for name, expected in manifest["source_sha256"].items():
        assert digest(args.source_root / name) == expected, name
    for name, expected in manifest["frozen_input_sha256"].items():
        assert digest(repo / name) == expected, name
    assert digest(primary / "runner.py") == manifest["runner"]["sha256"]
    assert digest(repo / manifest["runner"]["repository_path"]) == manifest["runner"]["sha256"]
    assert digest(primary / "protocol.md") == manifest["protocol"]["sha256"]
    assert summary["status"] == "complete"
    assert summary["attempted_episodes"] == summary["scored_episodes"] == summary["planned_episodes"] == 96
    assert not summary["execution_errors"] and not summary["unrun_cases"] and not summary["invalid_source_episodes"]
    assert len(summary["historical_reference_gate"]) == 8 and summary["historical_reference_gate_passed"]
    expected_cells = {(selection, profile, seed, policy)
                      for selection, seeds in (("historical", range(501, 505)), ("fresh", range(3000, 3020)))
                      for profile in manifest["profiles"] for seed in seeds for policy in manifest["policies"]}
    actual_cells = [(r["set"], r["profile"], r["seed"], r["policy"]) for r in summary["rows"]]
    assert len(actual_cells) == len(set(actual_cells)) == 96 and set(actual_cells) == expected_cells
    sys.path.insert(0, str(args.source_root.resolve()))
    from lightlag.model import Config
    from lightlag_dynamic.environment import DynamicEnvironment

    episodes = {}
    total_calls = 0
    for row in summary["rows"]:
        path = primary / row["episode_file"]
        assert digest(path) == row["episode_sha256"]
        artifact = read(path)
        assert artifact["status"] == "ok" and artifact["error"] is None
        episode = artifact["episode"]
        assert artifact["case"] == {k: row[k] for k in ("set", "profile", "seed", "policy")}
        assert episode["policy"] == row["policy"] and episode["seed"] == row["seed"] and episode["delay"] == 3
        env = DynamicEnvironment(seed=row["seed"], config=Config(delay_ticks=3, max_ticks=50),
                                 profile=row["profile"], noise_level=1.0, bumpiness=0.0)
        counts = Counter()
        for record in episode["transcript"]:
            counts[record["source"], record["tool"]] += 1
            actual = getattr(env, record["tool"])(**record["request"])
            assert actual == record["result"], (row["episode_file"], record["tool"])
        assert env.evaluate() == episode["result"] == episode["replay"]["result"]
        assert env.replay() == episode["replay"], row["episode_file"]
        assert episode["result"]["tick"] == 50
        for source in ("policy", "evaluator"):
            expected_count = sum(value for (who, _), value in counts.items() if who == source)
            assert expected_count == episode["tool_calls"][source] == row[source + "_calls"]
            for tool, count in episode["tool_calls"]["by_tool"][source].items():
                assert count == counts[source, tool]
        assert len(episode["transcript"]) == episode["tool_calls"]["total"] == row["total_calls"]
        total_calls += len(episode["transcript"])
        result = episode["result"]
        assert row["raw_score"] == result["raw_score"] and row["maximum"] == result["max_available_value"]
        assert row["normalized_score"] == result["raw_score"] / result["max_available_value"]
        assert row["alive"] == result["alive"] and row["at_base"] == result["at_base"]
        assert row["alive_and_at_base"] == (result["alive"] and result["at_base"])
        episodes[row["set"], row["profile"], row["seed"], row["policy"]] = episode
        if row["set"] == "historical" and row["policy"] == "kf_mpc":
            folder = repo / "docs/lightlag-runs" / f"{row['profile'].replace('_', '-')}-seed{row['seed']}-delay3-kf-mpc"
            assert episode["replay"] == read(folder / "artifacts/evaluator/replay.json")
            frozen = read(folder / "artifacts/evaluator/result.json")
            assert result == {k: v for k, v in frozen.items() if k != "tool_calls"}
            assert row["policy_calls"] == frozen["tool_calls"]
            assert f"{row['normalized_score']:.6f}" == (folder / "verifier/reward.txt").read_text().strip()

    for group in summary["paired_statistics"]:
        rows = [r for r in summary["rows"] if r["set"] == group["set"] and r["profile"] == group["profile"]]
        by_cell = {(r["seed"], r["policy"]): r for r in rows}
        diffs, raw_diffs = [], []
        for seed in sorted({r["seed"] for r in rows}):
            old, new = [by_cell[seed, p] for p in manifest["policies"]]
            diffs.append(new["normalized_score"] - old["normalized_score"])
            raw_diffs.append(new["raw_score"] - old["raw_score"])
        assert group["complete_pairs"] == len(diffs) and group["incomplete_pairs"] == 0
        assert math.isclose(group["mean_candidate_minus_original"], statistics.mean(diffs), abs_tol=1e-15)
        assert math.isclose(group["mean_raw_candidate_minus_original"], statistics.mean(raw_diffs), abs_tol=1e-15)
        assert group["median_candidate_minus_original"] == statistics.median(diffs)
        assert group["candidate_wins"] == sum(d > 1e-12 for d in diffs)
        assert group["ties"] == sum(abs(d) <= 1e-12 for d in diffs)
        assert group["original_wins"] == sum(d < -1e-12 for d in diffs)
        for policy in group["policies"]:
            selected = [r for r in rows if r["policy"] == policy["policy"]]
            assert policy["attempted"] == policy["scored"] == len(selected) and policy["errors"] == 0
            for field, source in (("mean_normalized_score", "normalized_score"),
                                  ("mean_raw_score", "raw_score"), ("mean_policy_calls", "policy_calls")):
                assert math.isclose(policy[field], statistics.mean(r[source] for r in selected), abs_tol=1e-14)
            for field in ("alive", "at_base", "alive_and_at_base"):
                assert policy[field] == sum(r[field] for r in selected)

    for row in summary["historical_original_model_vs_candidate"]["rows"]:
        result = read(repo / row["original_model_evidence"] / "artifacts/evaluator/result.json")
        assert row["model_score"] == result["raw_score"] / result["max_available_value"]
        for field, policy in (("original_reference_score", manifest["policies"][0]),
                              ("candidate_score", manifest["policies"][1])):
            result = episodes["historical", row["profile"], row["seed"], policy]["result"]
            assert row[field] == result["raw_score"] / result["max_available_value"]
        assert row["model_minus_candidate"] == row["model_score"] - row["candidate_score"]

    files = sorted(p.relative_to(primary).as_posix() for p in primary.rglob("*") if p.is_file())
    assert len(files) == 100
    reproduced = read(reproduction / "reproduction.json")
    assert reproduced["passed"] and reproduced["files_compared"] == 100 and not reproduced["byte_mismatches"]
    assert files == [record["path"] for record in reproduced["files"]]
    for record in reproduced["files"]:
        path = primary / record["path"]
        assert path.stat().st_size == record["bytes"]
        assert digest(path) == record["primary_sha256"] == record["reproduction_sha256"]
        if args.reproduction_root:
            assert path.read_bytes() == (args.reproduction_root / record["path"]).read_bytes()
    noisy_equal = sum(episodes[selection, "rush_noisy", seed, manifest["policies"][0]]["replay"]
                      == episodes[selection, "rush_noisy", seed, manifest["policies"][1]]["replay"]
                      for selection, seeds in (("historical", range(501, 505)), ("fresh", range(3000, 3020)))
                      for seed in seeds)
    # Inspect only the new scientific data, never credentials or private runtime state.
    patterns = [r"/Users/[^/\s]+/", r"/home/[^/\s]+/", r"sk-ant-[A-Za-z0-9_-]+",
                r"sk-proj-[A-Za-z0-9_-]+", r"ghp_[A-Za-z0-9]{20,}", r"Bearer [A-Za-z0-9_-]{20,}"]
    for path in primary.rglob("*.json"):
        assert not any(re.search(pattern, path.read_text()) for pattern in patterns), path.name
    report = {"passed": True, "source_files_verified": len(manifest["source_sha256"]),
              "frozen_input_files_verified": len(manifest["frozen_input_sha256"]),
              "unique_scored_cases": 96, "execution_errors": 0,
              "independent_full_transcript_replays": 96, "public_and_evaluator_calls_replayed": total_calls,
              "historical_full_harbor_replays_matched": 8, "paired_groups_recomputed": 4,
              "historical_model_results_checked": 8, "reproduction_files_byte_identical": 100,
              "reproduction_full_copy_rechecked": args.reproduction_root is not None,
              "reproduction_paired_hash_records_verified": len(reproduced["files"]),
              "noisy_cells_with_identical_original_and_candidate_replays": noisy_equal,
              "private_path_and_token_pattern_scan": "passed; scientific JSON only",
              "verification_script_sha256": digest(Path(__file__))}
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.report:
        with args.report.open("x") as stream:
            stream.write(encoded)
    print(encoded)


if __name__ == "__main__":
    main()
