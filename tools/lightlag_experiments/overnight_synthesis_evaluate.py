"""Evaluate only a frozen successful response; no provider SDK or credentials.

The CLI constructs the declared fresh maps only after an explicit root flag.
Tests use existing historical episodes, deterministic fixtures and canaries.
"""

import argparse
from collections import Counter
from copy import deepcopy
import math
import json
from pathlib import Path
import platform
import signal
import time

try:
    from . import overnight_synthesis as common
except ImportError:
    import overnight_synthesis as common

PROFILES = ("rush", "rush_noisy")
POLICIES = ("generated", "kf_mpc")


def blank_row(profile, seed, policy, index):
    return {"profile": profile, "seed": seed, "policy": policy, "index": index,
            "policy_status": "unrun", "grading_status": "unrun", "error": None,
            "reward": None, "raw_score": None, "maximum": None, "sampled_value": None,
            "alive": None, "at_base": None, "policy_calls": None, "graded_service_call_count": None,
            "elapsed_seconds": None, "episode_file": None}


def planned_rows():
    rows = []
    for profile in PROFILES:
        for seed in range(60000, 60020):
            for policy in POLICIES:
                rows.append(blank_row(profile, seed, policy, len(rows) + 1))
    return rows


def verification_plan():
    return [blank_row(profile, seed, "generated", i + 1)
            for i, (profile, seed) in enumerate((p, s) for p in PROFILES for s in (60000, 60019))]


def episode_row(case, episode, filename):
    row = blank_row(case["profile"], case["seed"], case["policy"], case.get("index"))
    execution = episode["execution"]
    row.update(policy_status=execution["status"], grading_status=episode["grading_status"],
               error=execution.get("error"), elapsed_seconds=execution.get("elapsed_seconds"),
               policy_calls=episode.get("policy_calls"), episode_file=filename,
               protected_diagnostic_grade_retained=episode.get("result") is not None,
               replay_verification=episode.get("replay_verification"), recording_status="complete")
    if episode["grading_status"] == "scored":
        result = episode["result"]
        maximum, raw = result["max_available_value"], result["raw_score"]
        if not maximum > 0 or not math.isfinite(raw) or not 0 <= raw <= maximum:
            raise common.GuardError("terminal reward is outside its declared range")
        row.update(reward=raw / maximum, raw_score=raw, maximum=maximum,
                   sampled_value=result["sampled_value"], alive=result["alive"], at_base=result["at_base"],
                   graded_service_call_count=result["tool_calls"])
    return row


def run_candidate(base, runtime, seed, profile, policy, worker, image, docker):
    broker = base.Broker(runtime, seed, profile)
    try:
        execution = base.run_container(broker, policy, worker, image, docker)
    except BaseException as error:
        execution = {"status": "infrastructure_error", "error": base.error_record(error),
                     "elapsed_seconds": None, "interrupted": isinstance(error, KeyboardInterrupt)}
    try:
        episode = broker.finish(execution)
        if execution["status"] == "infrastructure_error":
            episode["grading_status"] = "infrastructure_null"
            episode["diagnostic_note"] = "A protected finish is retained, but no primary policy score is attributed to an infrastructure failure."
        return episode
    except BaseException as error:
        interrupted = isinstance(error, KeyboardInterrupt) or execution.get("interrupted", False)
        return {"seed": seed, "profile": profile, "execution": {"status": "infrastructure_error",
                "error": base.error_record(error), "policy_execution": execution,
                "interrupted": interrupted, "abort": interrupted, "cleanup": execution.get("cleanup")}, "grading_status": "infrastructure_null",
                "result": None, "replay": None, "policy_calls": broker.policy_calls,
                "transcript": broker.transcript, "diagnostic_note": "Trusted finish failed; terminal grade is unavailable, never fabricated as zero."}


def run_trusted_reference(base, runtime, seed, profile):
    class ReferenceBroker(base.Broker):
        infrastructure_failure = False

        def call(self, tool, arguments):
            try:
                return super().call(tool, arguments)
            except base.PublicCallError:
                raise
            except BaseException:
                self.infrastructure_failure = True
                raise

    broker = ReferenceBroker(runtime, seed, profile)
    started = time.monotonic()
    execution = {"status": "returned", "error": None}
    try:
        runtime.reference(broker.tools())
    except BaseException as error:
        interrupted = isinstance(error, KeyboardInterrupt)
        execution = {"status": "infrastructure_error" if broker.infrastructure_failure or interrupted else "policy_error",
                     "error": base.error_record(error), "interrupted": interrupted}
    execution.update(elapsed_seconds=time.monotonic() - started, runtime="trusted local Python", wall_limit_seconds=None)
    episode = broker.finish(execution)
    if execution["status"] == "infrastructure_error":
        episode["grading_status"] = "infrastructure_null"
    return episode


def verified_attempt(base, runtime, case, invoke, source_root, source_hashes):
    """One invocation, with per-attempt state and durable failure artifacts."""
    episode = None
    try:
        episode = invoke()
        if episode.get("result") is not None:
            episode["replay_verification"] = base.replay_episode(runtime, episode)
        base.verify_source(source_root, source_hashes)
    except BaseException as error:
        if episode is None:
            episode = {"seed": case["seed"], "profile": case["profile"], "result": None,
                       "replay": None, "transcript": [], "policy_calls": None}
        previous = episode.get("execution")
        episode["grading_status"] = "infrastructure_null"
        episode["execution"] = {"status": "infrastructure_error", "error": base.error_record(error),
                                "abort": True, "policy_execution": previous}
    episode["policy"] = case["policy"]
    return episode


def must_stop(episode):
    execution = episode["execution"]
    cleanup = execution.get("cleanup")
    return (execution.get("abort") or execution.get("interrupted")
            or cleanup is not None and not cleanup["confirmed_absent"])


def paired_statistics(rows):
    groups = []
    for profile in PROFILES:
        selected = [r for r in rows if r["profile"] == profile]
        by_cell = {(r["seed"], r["policy"]): r for r in selected}
        policies = {}
        for policy in POLICIES:
            own = [r for r in selected if r["policy"] == policy]
            valid = [r for r in own if r["reward"] is not None]
            score_sum = math.fsum(r["reward"] for r in valid)
            missing = 20 - len(valid)
            policies[policy] = {
                "n_planned": 20, "n_scored": len(valid), "n_missing": missing,
                "mean_reward": score_sum / 20 if not missing else None,
                "mean_reward_bounds": [score_sum / 20, (score_sum + missing) / 20],
                "observed_mean_reward": score_sum / len(valid) if valid else None,
                "alive": sum(r["alive"] is True for r in valid),
                "deaths": sum(r["alive"] is False for r in valid),
                "home": sum(r["at_base"] is True for r in valid),
                "alive_and_home": sum(r["alive"] is True and r["at_base"] is True for r in valid),
                "terminal_unknown": missing, "policy_status_counts": dict(Counter(r["policy_status"] for r in own)),
            }
        pairs, low, high = [], [], []
        for seed in range(60000, 60020):
            generated, reference = (by_cell[(seed, policy)]["reward"] for policy in POLICIES)
            low.append((0 if generated is None else generated) - (1 if reference is None else reference))
            high.append((1 if generated is None else generated) - (0 if reference is None else reference))
            if generated is not None and reference is not None:
                pairs.append({"seed": seed, "generated": generated, "kf_mpc": reference,
                              "generated_minus_kf_mpc": generated - reference})
        differences = [p["generated_minus_kf_mpc"] for p in pairs]
        groups.append({"profile": profile, "n_cells": 20, "policies": policies,
                       "complete_pairs": len(pairs), "incomplete_pairs": 20 - len(pairs),
                       "paired_mean": math.fsum(differences) / 20 if len(pairs) == 20 else None,
                       "observed_complete_pair_mean": math.fsum(differences) / len(pairs) if pairs else None,
                       "paired_mean_bounds": [math.fsum(low) / 20, math.fsum(high) / 20],
                       "generated_wins": sum(value > 1e-12 for value in differences),
                       "ties": sum(abs(value) <= 1e-12 for value in differences),
                       "generated_deficits": sum(value < -1e-12 for value in differences), "pairs": pairs})
    return groups


def compare_verification(base, primary, repeat):
    available = all(episode.get("grading_status") == "scored" and episode.get("result") is not None
                    and episode.get("replay_verification", {}).get("exact") is True
                    for episode in (primary, repeat))
    if not available:
        return {"exact": None, "available": False,
                "reason": "comparison requires scored, independently reconstructed primary and repeat evidence",
                "verification_only_not_an_independent_sample": True}
    keys = ("transcript", "result", "replay", "policy_calls", "grading_status")
    old, new = ({key: episode.get(key) for key in keys} for episode in (primary, repeat))
    old["policy_status"] = primary["execution"]["status"]
    new["policy_status"] = repeat["execution"]["status"]
    different = [key for key in old if old[key] != new[key]]
    return {"exact": not different, "available": True, "different_fields": different,
            "primary_behavior_sha256": base.sha256(base.canonical(old)),
            "repeated_behavior_sha256": base.sha256(base.canonical(new)),
            "timing_excluded": True, "verification_only_not_an_independent_sample": True}


def summary(rows, verification, status, error=None):
    attempted = [r for r in verification if r["policy_status"] != "unrun"]
    completed = [r for r in attempted if r.get("recording_status") != "interrupted"]
    checks = [r.get("comparison", {}).get("exact") for r in attempted]
    exact = False if any(value is False for value in checks) else True if len(checks) == 4 and all(value is True for value in checks) else None
    return {"schema_version": 1, "condition": "one sampled program transferred across forty cells",
            "status": status, "error": error, "n_cells": 40, "n_primary_planned": 80,
            "n_primary_attempted": sum(r["policy_status"] != "unrun" for r in rows),
            "n_primary_unrun": sum(r["policy_status"] == "unrun" for r in rows),
            "n_primary_scored": sum(r["reward"] is not None for r in rows),
            "n_primary_infrastructure_null": sum(r["grading_status"] == "infrastructure_null" for r in rows),
            "n_verification_planned": 4, "n_verification_attempted": len(attempted), "n_verification_completed": len(completed),
            "policy_exactly_reproducible_in_four_checks": exact,
            "verification_status": "complete" if len(completed) == 4 else "incomplete",
            "groups": paired_statistics(rows), "rows": rows, "verification": verification,
            "call_count_note": "policy_calls counts all attempted policy RPCs, including a rejected 501st call. graded_service_call_count is the frozen service's cached count when it first graded; later calls can make it smaller than total attempts.",
            "runtime_asymmetry": "generated policy uses fresh constrained Docker; trusted original KF runs locally. Timing is descriptive only; no speed or cost-efficiency comparison.",
            "limits": common.LIMITS, "no_retries_or_replacement_cells": True,
            "interpretation": "This measures one frozen program under the declared generation/runtime limits, separately from online agents, A/B and reference selection. A failure does not establish general model incapability."}


def verify_runtime_inputs(base, preparation, manifest, source_root, policy, policy_digest):
    base.verify_preparation(preparation, manifest)
    base.verify_source(source_root, manifest["source_sha256"])
    if policy.is_symlink() or base.sha256(policy.read_bytes()) != policy_digest:
        raise base.GuardError("frozen model module changed; no repairs are allowed")


def retain_inflight(base, output, inflight, rows, verification, error):
    """Reconcile a durable start marker with a row after a soft interruption."""
    if inflight is None:
        return
    def matches(record):
        return (all(record.get(key) == inflight["case"][key] for key in ("index", "profile", "seed", "policy"))
                and bool(record.get("verification_only")) == inflight["verification_only"])
    def records(path):
        if not path.exists():
            return []
        parsed = []
        for line in path.read_text().splitlines():
            try:
                parsed.append(json.loads(line))
            except ValueError:
                pass  # Keep any partial line in place; never overwrite it.
        return parsed
    if not any(matches(record) for record in records(output / "attempt-starts.jsonl")):
        return
    collection = verification if inflight["verification_only"] else rows
    row = collection[inflight["position"]]
    if row["policy_status"] == "unrun":
        case = inflight["case"]
        row = blank_row(case["profile"], case["seed"], case["policy"], case["index"])
        row.update(policy_status="infrastructure_error", grading_status="infrastructure_null",
                   error=base.error_record(error), recording_status="interrupted",
                   episode_file=inflight["filename"] if (output / inflight["filename"]).exists() else None,
                   evidence_note="Attempt started; required evidence was not durably completed. Grade remains unknown.")
        if inflight["verification_only"]:
            row["comparison"] = {"exact": None, "available": False, "reason": "attempt recording was interrupted"}
        collection[inflight["position"]] = row
    ledger = output / "completed-rows.jsonl"
    if not any(matches(record) for record in records(ledger)):
        payload = dict(row, verification_only=inflight["verification_only"], recovered_after_interruption=True)
        with ledger.open("ab") as stream:
            if ledger.stat().st_size and not ledger.read_bytes().endswith(b"\n"):
                stream.write(b"\n")
            stream.write(base.canonical(payload))


def evaluate(base, preparation, generation, source_root, repo, output, docker):
    preparation, generation, source_root, repo = map(Path, (preparation, generation, source_root, repo))
    manifest = base.read_json(preparation / "preparation.json")
    base.verify_preparation(preparation, manifest)
    base.verify_source(source_root, manifest["source_sha256"])
    base.verify_historical_inputs(repo, manifest)
    synthesis = base.read_json(generation / "synthesis.json")
    if synthesis.get("artifact_sha256"):
        base.verify_preparation(generation, synthesis)
    link = base.read_json(generation / "preparation-link.json")
    if link["preparation_sha256"] != base.sha256((preparation / "preparation.json").read_bytes()) or link["request_sha256"] != manifest["request_sha256"]:
        raise base.GuardError("generation belongs to a different preparation")
    output = base.claim_output(output)
    base.write_json(preparation.parent / "evaluation-claim.json",
                    {"synthesis_sha256": base.sha256((generation / "synthesis.json").read_bytes()),
                     "primary_episodes": 80, "generated_verification_repetitions": 4, "one_execution_only": True})
    rows, verification = planned_rows(), verification_plan()
    base.write_json(output / "plan.json", {"primary": rows, "verification": verification})
    implementation_dir = output / "implementation"
    implementation_dir.mkdir()
    code = {"broker.py": Path(base.__file__).read_bytes(), "evaluate.py": Path(__file__).read_bytes()}
    for name, data in code.items():
        (implementation_dir / name).write_bytes(data)
    provenance = {"source_commit": manifest["source_commit"], "protocol_commit": manifest["protocol_commit"],
                  "source_sha256": manifest["source_sha256"], "worker_sha256": manifest["artifact_sha256"]["worker.py"],
                  "worker_image": manifest["worker_image"], "host_python": platform.python_version(),
                  "preparation_sha256": link["preparation_sha256"], "request_sha256": manifest["request_sha256"],
                  "synthesis_sha256": base.sha256((generation / "synthesis.json").read_bytes()),
                  "policy_sha256": synthesis.get("policy_sha256"),
                  "implementation_sha256": {name: base.sha256(data) for name, data in code.items()},
                  "saved_preparer_is_provenance_only": True, "current_sanitized_broker_is_used": True}
    base.write_json(output / "provenance.json", provenance)
    if not synthesis.get("evaluation_eligible"):
        report = summary(rows, verification, "unrun_synthesis_failed", synthesis.get("error"))
        base.write_json(output / "summary.json", report)
        return report
    policy, worker = generation / "policy.py", preparation / "worker.py"
    runtime = None
    status, failure, inflight = "complete", None, None
    output.joinpath("episodes").mkdir()
    output.joinpath("verification").mkdir()
    try:
        if manifest["source_commit"] != base.SOURCE_COMMIT or manifest["protocol_commit"] != base.PROTOCOL_COMMIT:
            raise base.GuardError("unexpected frozen source or protocol")
        if not manifest["historical_gate_passed"] or not manifest["isolation_passed"]:
            raise base.GuardError("preparation did not pass its gates")
        if platform.python_version() != manifest["host_runtime"]["python"]:
            raise base.GuardError("trusted Python runtime differs from preparation")
        verify_runtime_inputs(base, preparation, manifest, source_root, policy, synthesis["policy_sha256"])
        runtime = base.load_runtime(source_root, manifest["source_sha256"])
        # Reconstruct the eight saved historical public transcripts again before
        # any fresh construction. No duplicate historical trajectories are saved.
        historical = []
        for profile in PROFILES:
            for seed in range(501, 505):
                episode = base.read_json(preparation / "historical" / f"historical-{profile}-{seed}.json")
                historical.append({"profile": profile, "seed": seed, **base.replay_episode(runtime, episode)})
        base.write_json(output / "historical-reverification.json", historical)
        primary_by_cell = {}
        with (output / "attempt-starts.jsonl").open("xb") as starts, (output / "completed-rows.jsonl").open("xb") as ledger:
            for index, case in enumerate(rows):
                verify_runtime_inputs(base, preparation, manifest, source_root, policy, synthesis["policy_sha256"])
                filename = f"episodes/{case['index']:02d}-{case['profile']}-{case['seed']}-{case['policy']}.json"
                inflight = {"position": index, "case": deepcopy(case), "filename": filename, "verification_only": False}
                starts.write(base.canonical({key: case[key] for key in ("index", "profile", "seed", "policy")}))
                starts.flush()
                if case["policy"] == "generated":
                    invoke = lambda: run_candidate(base, runtime, case["seed"], case["profile"], policy, worker,
                                                   manifest["worker_image"]["reference"], docker)
                else:
                    invoke = lambda: run_trusted_reference(base, runtime, case["seed"], case["profile"])
                episode = verified_attempt(base, runtime, case, invoke, source_root, manifest["source_sha256"])
                base.write_json(output / filename, episode)
                row = episode_row(case, episode, filename)
                rows[index] = row
                ledger.write(base.canonical(row))
                ledger.flush()
                inflight = None
                if case["policy"] == "generated":
                    primary_by_cell[(case["profile"], case["seed"])] = episode
                if must_stop(episode):
                    raise base.GuardError("primary execution aborted; remaining planned rows retained unrun")
                print(f"primary {index + 1}/80: {row['policy_status']}; grading={row['grading_status']}", flush=True)
            for index, case in enumerate(verification):
                verify_runtime_inputs(base, preparation, manifest, source_root, policy, synthesis["policy_sha256"])
                filename = f"verification/{index + 1}-{case['profile']}-{case['seed']}.json"
                inflight = {"position": index, "case": deepcopy(case), "filename": filename, "verification_only": True}
                starts.write(base.canonical({"verification_only": True, **{key: case[key] for key in ("index", "profile", "seed", "policy")}}))
                starts.flush()
                repeat = verified_attempt(base, runtime, case,
                                          lambda: run_candidate(base, runtime, case["seed"], case["profile"], policy, worker,
                                                                manifest["worker_image"]["reference"], docker),
                                          source_root, manifest["source_sha256"])
                base.write_json(output / filename, repeat)
                row = episode_row(case, repeat, filename)
                row["comparison"] = compare_verification(base, primary_by_cell[(case["profile"], case["seed"])], repeat)
                verification[index] = row
                ledger.write(base.canonical(dict(row, verification_only=True)))
                ledger.flush()
                inflight = None
                if must_stop(repeat):
                    raise base.GuardError("verification aborted; remaining declared repetitions retained unrun")
            verify_runtime_inputs(base, preparation, manifest, source_root, policy, synthesis["policy_sha256"])
    except BaseException as error:
        status, failure = "incomplete", base.error_record(error)
        retain_inflight(base, output, inflight, rows, verification, error)
    report = summary(rows, verification, status, failure)
    report["artifact_sha256"] = {str(path.relative_to(output)): base.sha256(path.read_bytes())
                                 for path in sorted(output.rglob("*")) if path.is_file()}
    base.write_json(output / "summary.json", report)
    return report


def main(argv=None, *, base=common):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--preparation", type=Path, required=True)
    parser.add_argument("--generation", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--docker", default="/usr/local/bin/docker")
    parser.add_argument("--root-authorized-fresh-evaluation", action="store_true")
    args = parser.parse_args(argv)
    if not args.root_authorized_fresh_evaluation:
        parser.error("fresh-map evaluation requires root authorization; no maps were constructed")
    def stop(signum, frame):
        raise KeyboardInterrupt("root interrupted evaluation")
    signal.signal(signal.SIGTERM, stop)
    result = evaluate(base, args.preparation, args.generation, args.source_root, args.repo, args.output, args.docker)
    print(base.canonical({key: result[key] for key in ("status", "n_primary_attempted", "n_primary_scored", "n_primary_unrun", "verification_status")}).decode().strip())
    return 0 if result["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
