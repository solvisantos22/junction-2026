#!/usr/bin/env python3
"""Assess exported allocation-pilot decisions without provider calls or hidden lookahead.

This is a decision analysis, complementary to audit_pilot's replay/hash audit.
Only exported completed model episodes are read. Missing exports are retained
as unrun rows; during an active pilot they may simply not have been exported yet.
"""

import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import sys


REPO = Path(__file__).resolve().parents[2]
if __package__ in (None, ""):
    sys.path.insert(0, str(REPO))
REFERENCE_FILES = tuple("lightlag_information_allocation/" + name for name in
                        ("__init__.py", "environment.py", "model.py", "policies.py", "service.py"))
TOLERANCE = 1e-12


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def numeric(value):
    return type(value) in (int, float) and math.isfinite(value)


def verify_sources(manifest):
    """Fail closed if analysis would use different public reference code."""
    hashes = manifest["source_sha256"]
    for name in REFERENCE_FILES:
        actual = hashlib.sha256((REPO / name).read_bytes()).hexdigest()
        if hashes.get(name) != actual:
            raise ValueError("analysis reference source mismatch: " + name)
    if manifest.get("source_dirty") is not False:
        raise ValueError("model task manifest does not record a clean source checkout")


def assess_trace(trace, rules):
    """Judge public actions from observations available at commitment acceptance.

    A future queued probe costs energy before departure but supplies no evidence
    before its result is actually delivered through a public tool response.
    """
    from lightlag_information_allocation.policies import (
        _route_value, _signal_posterior, acquisition_values, choose_acquisition,
    )

    acquisition = acquisition_values(rules)
    best_initial = max(acquisition.values())
    optimal_acquisitions = [name for name, value in acquisition.items()
                            if best_initial - value <= TOLERANCE]
    expected_probe = choose_acquisition(rules)
    posterior = dict(rules["priors_firm"])
    observed = {}
    actions = []
    probe = commit = None
    posterior_at_commit = None
    signal_at_commit = None
    schedule_consistent = True
    last_reserved = -1
    errors = 0
    for record in trace:
        if record["ok"] is not True:
            errors += 1
            continue
        tool, result = record["tool"], record["result"]
        if tool in ("advance", "telemetry_log"):
            for event in result["entries"]:
                if event["action"] != "probe":
                    continue
                target = event["probe_route"]
                if (probe is None or target != probe["route"]
                        or event["state_tick"] != probe["execution_tick"]):
                    raise ValueError("observed signal does not belong to the accepted inspection")
                if event["delivery_tick"] > result["current_tick"]:
                    raise ValueError("trace reports a probe signal before its delivery tick")
                identity = (event["signal"], event["state_tick"], event["delivery_tick"])
                if target in observed:
                    if observed[target] != identity:
                        raise ValueError("one physical probe has conflicting observations")
                    continue
                observed[target] = identity
                if commit is None:
                    posterior[target] = _signal_posterior(
                        rules["priors_firm"][target], rules["signal_accuracy"], event["signal"])[1]
        elif tool == "uplink":
            expected_execution = max(record["tick_before"] + rules["delay"] + 1,
                                     last_reserved + 1)
            accepted = result["accepted"]
            if len(accepted) != len(record["arguments"]["commands"]):
                raise ValueError("accepted command count disagrees with public request")
            for command, requested in zip(accepted, record["arguments"]["commands"]):
                if {k: v for k, v in command.items() if k != "execution_tick"} != requested:
                    raise ValueError("accepted command differs from public request")
                schedule_consistent &= command["execution_tick"] == expected_execution
                last_reserved = command["execution_tick"]
                expected_execution += 1
                action = dict(command, sent_tick=record["tick_before"], call_n=record["n"])
                actions.append(action)
                if command["action"] == "probe":
                    if probe is not None or commit is not None:
                        raise ValueError("successful trace violates the shared probe budget/order")
                    probe = action
                elif command["action"] == "commit":
                    if commit is not None:
                        raise ValueError("successful trace has multiple commitments")
                    commit = action
                    posterior_at_commit = dict(posterior)
                    signal_at_commit = (observed.get(probe["route"]) if probe else None)

    actual_probe = probe["route"] if probe else None
    acquisition_name = actual_probe or "none"
    # Without any probe or commitment there is no observed acquisition decision.
    acquisition_decided = probe is not None or commit is not None
    initial_optimal = acquisition_decided and acquisition_name in optimal_acquisitions
    conditional_values = None
    optimal_routes = []
    conditional_optimal = False
    conditional_regret = None
    energy = rules["initial_energy"]
    if commit is not None:
        if probe is not None and probe["execution_tick"] < commit["execution_tick"]:
            energy -= rules["context"]["probe_energy"]
        conditional_values = {route: _route_value(rules, route, posterior_at_commit, energy,
                                                 commit["execution_tick"])
                              for route in rules["routes"]}
        maximum = max(conditional_values.values())
        optimal_routes = [route for route, value in conditional_values.items()
                          if maximum - value <= TOLERANCE]
        conditional_optimal = commit["route"] in optimal_routes
        conditional_regret = maximum - conditional_values[commit["route"]]
    expected_sent = 2 * rules["delay"] + 1 if expected_probe is not None else 0
    actual_earliest_sent = 2 * rules["delay"] + 1 if probe is not None else 0
    probe_timing = (probe is None or (probe["sent_tick"] == 0
                                    and probe["execution_tick"] == rules["delay"] + 1))
    actual_timing = bool(commit is not None and probe_timing and schedule_consistent
                         and commit["sent_tick"] == actual_earliest_sent
                         and commit["execution_tick"] == actual_earliest_sent + rules["delay"] + 1
                         and (probe is None or signal_at_commit is not None))
    reference_timing = bool(actual_timing and commit["sent_tick"] == expected_sent
                            and (probe is not None) == (expected_probe is not None))
    return {
        "actions": actions,
        "decision_complete": commit is not None,
        "actual_probe_route": actual_probe,
        "actual_route": commit["route"] if commit else None,
        "reference_probe_route": expected_probe,
        "acquisition_expected_values": acquisition,
        "optimal_initial_acquisitions": optimal_acquisitions,
        "initial_acquisition_optimal": bool(initial_optimal),
        "initial_acquisition_expected_regret": (best_initial - acquisition[acquisition_name]
                                                if acquisition_decided else None),
        "posterior_firm_at_commit": posterior_at_commit,
        "signal_observed_before_commit": ({"probe_route": actual_probe, "signal": signal_at_commit[0],
                                            "state_tick": signal_at_commit[1], "delivery_tick": signal_at_commit[2]}
                                           if signal_at_commit is not None else None),
        "observed_signals": [{"probe_route": route, "signal": item[0],
                              "state_tick": item[1], "delivery_tick": item[2]}
                             for route, item in sorted(observed.items())],
        "energy_available_at_commit_execution": energy if commit else None,
        "conditional_route_expected_values": conditional_values,
        "optimal_routes_given_observed_information": optimal_routes,
        "conditional_route_optimal": conditional_optimal,
        "conditional_route_expected_regret": conditional_regret,
        "commit_sent_tick": commit["sent_tick"] if commit else None,
        "commit_execution_tick": commit["execution_tick"] if commit else None,
        "reference_earliest_commit_sent_tick": expected_sent,
        "earliest_commit_sent_tick_for_actual_acquisition": actual_earliest_sent,
        "timing_optimal_for_actual_acquisition": actual_timing,
        "matches_reference_timing": reference_timing,
        "command_delay_consistent": bool(schedule_consistent),
        "all_decisions_and_timing_optimal": bool(initial_optimal and conditional_optimal and reference_timing),
        "public_service_calls": len(trace),
        "invalid_service_calls": errors,
    }


def run_state(run):
    result_file = run / "result.json"
    if not run.exists():
        return "unrun", None
    if not result_file.exists():
        return "incomplete", None
    trial = read_json(result_file)
    if trial.get("exception_info") is not None:
        return "error", trial
    if not trial.get("finished_at"):
        return "incomplete", trial
    return "complete", trial


def analyze(pilot):
    pilot = Path(pilot)
    protocol = read_json(pilot / "protocol.json")
    rows, sources = [], {}
    for assignment in protocol["order"]:
        identifier, context = assignment["assignment_id"], assignment["context"]
        run = pilot / "runs" / ("model-" + identifier)
        status, trial = run_state(run)
        row = {"assignment_id": identifier, "context": context, "repeat": assignment["repeat"],
               "status": status, "reported_cost_usd": None, "reported_cost_known": False,
               "reward": None, "reference_status": "unrun", "reference_reward": None,
               "same_seed_reward_difference": None, "decision_analysis": None}
        rows.append(row)
        if trial is not None:
            cost = (trial.get("agent_result") or {}).get("cost_usd")
            if numeric(cost) and cost >= 0:
                row.update(reported_cost_usd=cost, reported_cost_known=True)
            row.update(trial_name=trial.get("trial_name"), exception_info=trial.get("exception_info"),
                       agent_info=trial.get("agent_info"), usage=trial.get("agent_result"))
        if status != "complete":
            continue
        manifest_path = run / "experiment.json"
        if not manifest_path.exists():
            row.update(status="incomplete", reason="missing exported experiment manifest")
            continue
        manifest = read_json(manifest_path)
        verify_sources(manifest)
        if manifest["settings"]["context"] != context:
            raise ValueError("assignment context disagrees with run manifest: " + identifier)
        fingerprint = tuple((name, manifest["source_sha256"][name]) for name in REFERENCE_FILES)
        sources[manifest["source_commit"]] = fingerprint
        if len(set(sources.values())) != 1:
            raise ValueError("pilot cases use different reference source hashes")
        from lightlag_information_allocation.environment import Environment
        rules = Environment(context=context).rules()
        artifact = run / "artifacts/evaluator"
        required = [artifact / "transcript.jsonl", artifact / "result.json", artifact / "replay.json"]
        if not all(path.exists() for path in required):
            row.update(status="incomplete", reason="missing exported protected episode evidence")
            continue
        transcript = [json.loads(line) for line in required[0].read_text().splitlines()]
        grade, replay = read_json(required[1]), read_json(required[2])
        info = trial.get("agent_info") or {}
        model_info = info.get("model_info") or {}
        identity = model_info.get("provider", "") + "/" + model_info.get("name", "")
        if identity != protocol["model"] or info.get("name") != "opencode":
            raise ValueError("model identity differs from frozen protocol: " + identifier)
        if "OpenCode " + str(info.get("version")) not in protocol["harness"]:
            raise ValueError("agent version differs from frozen protocol: " + identifier)
        assessment = assess_trace(transcript, rules)
        row.update(reward=grade["reward"], episode_status=grade["status"],
                   completion_tick=grade["completion_tick"], decision_analysis=assessment)
        ref = pilot / "runs" / ("matched-reference-" + identifier)
        ref_status, ref_trial = run_state(ref)
        row["reference_status"] = ref_status
        if ref_status == "complete" and not all((ref / relative).exists() for relative in (
                "experiment.json", "artifacts/evaluator/result.json", "artifacts/evaluator/transcript.jsonl")):
            ref_status = row["reference_status"] = "incomplete"
        if ref_status == "complete":
            ref_manifest = read_json(ref / "experiment.json")
            verify_sources(ref_manifest)
            if ref_manifest != manifest:
                raise ValueError("model/reference task manifests differ: " + identifier)
            ref_grade = read_json(ref / "artifacts/evaluator/result.json")
            ref_trace = [json.loads(line) for line in
                         (ref / "artifacts/evaluator/transcript.jsonl").read_text().splitlines()]
            ref_assessment = assess_trace(ref_trace, rules)
            row.update(reference_reward=ref_grade["reward"],
                       same_seed_reward_difference=grade["reward"] - ref_grade["reward"],
                       reference_decisions_and_timing_optimal=ref_assessment["all_decisions_and_timing_optimal"],
                       reference_probe_route=ref_assessment["actual_probe_route"],
                       reference_route=ref_assessment["actual_route"])
        if grade["reward"] == 0:
            route = assessment["actual_route"]
            if (assessment["all_decisions_and_timing_optimal"] and grade["status"] == "failed"
                    and replay["terrains"].get(route) == "soft"):
                row["zero_reward_interpretation"] = "stochastic terrain loss after optimal public-information decisions"
            else:
                row["zero_reward_interpretation"] = "zero reward; inspect incomplete actions or decision/timing findings before attributing it to terrain luck"
        else:
            row["zero_reward_interpretation"] = None

    # Public context values need no held-out seed. Use them only after one
    # exported clean manifest has verified the analysis source provenance.
    expected_by_context = {}
    if sources:
        from lightlag_information_allocation.environment import Environment
        from lightlag_information_allocation.policies import expected_values
        for assignment in protocol["order"]:
            context = assignment["context"]
            if context not in expected_by_context:
                expected_by_context[context] = expected_values(Environment(context=context).rules())["selective"]
    completed = [row for row in rows if row["status"] == "complete"]
    decisions = [row["decision_analysis"] for row in completed]
    counts = Counter(row["status"] for row in rows)
    known_cost = sum((Decimal(str(row["reported_cost_usd"])) for row in rows if row["reported_cost_known"]), Decimal(0))
    costs_complete = bool(rows) and all(row["reported_cost_known"] for row in completed) and not any(
        row["status"] in ("incomplete", "error") and not row["reported_cost_known"] for row in rows)
    coverage = {route: {signal: 0 for signal in ("firm", "soft")} for route in ("a", "b")}
    precommit_coverage = {route: dict(values) for route, values in coverage.items()}
    context_coverage = {a["context"]: {route: {signal: 0 for signal in ("firm", "soft")}
                                           for route in ("a", "b")} for a in protocol["order"]}
    for row in completed:
        analysis = row["decision_analysis"]
        for signal in analysis["observed_signals"]:
            coverage[signal["probe_route"]][signal["signal"]] += 1
        signal = analysis["signal_observed_before_commit"]
        if signal:
            precommit_coverage[signal["probe_route"]][signal["signal"]] += 1
            context_coverage[row["context"]][signal["probe_route"]][signal["signal"]] += 1
    paired = [row for row in completed if row["reference_status"] == "complete"]
    all_complete = len(completed) == len(rows)
    return {
        "schema_version": 1, "model": protocol["model"], "harness": protocol["harness"],
        "source_commits": sorted(sources), "analysis_source_files_verified": list(REFERENCE_FILES) if sources else [],
        "planned_model_trials": len(rows), "completed_model_trials": len(completed),
        "status_counts": {status: counts[status] for status in ("complete", "unrun", "incomplete", "error")},
        "all_planned_trials_complete": all_complete,
        "all_planned_trials_decisions_and_timing_optimal": bool(all_complete and all(
            decision["all_decisions_and_timing_optimal"] for decision in decisions)),
        "known_reported_cost_usd": float(known_cost),
        "completed_or_exported_attempt_costs_known": costs_complete,
        "total_reported_cost_usd": float(known_cost) if all_complete and costs_complete else None,
        "unknown_cost_assignment_ids": [row["assignment_id"] for row in rows
                                        if row["status"] != "unrun" and not row["reported_cost_known"]],
        "mean_realized_reward_completed": (sum(row["reward"] for row in completed) / len(completed)
                                            if completed else None),
        "paired_model_reference_trials": len(paired),
        "all_planned_model_and_reference_trials_complete": all_complete and len(paired) == len(rows),
        "paired_reward_match_count": sum(abs(row["same_seed_reward_difference"]) <= TOLERANCE for row in paired),
        "mean_reference_reward_paired": (sum(row["reference_reward"] for row in paired) / len(paired)
                                         if paired else None),
        "mean_model_reward_paired": (sum(row["reward"] for row in paired) / len(paired) if paired else None),
        "optimal_initial_acquisition_count": sum(d["initial_acquisition_optimal"] for d in decisions),
        "optimal_conditional_route_count": sum(d["conditional_route_optimal"] for d in decisions),
        "reference_timing_match_count": sum(d["matches_reference_timing"] for d in decisions),
        "decision_complete_count": sum(d["decision_complete"] for d in decisions),
        "invalid_service_call_count": sum(d["invalid_service_calls"] for d in decisions),
        "observed_commit_routes": dict(Counter(d["actual_route"] for d in decisions if d["actual_route"] is not None)),
        "observed_signal_branch_counts": coverage,
        "precommit_signal_branch_counts": precommit_coverage,
        "precommit_signal_branch_counts_by_context": context_coverage,
        "selective_expected_reward_by_context": expected_by_context,
        "planned_selective_expected_mean": (sum(expected_by_context[a["context"]] for a in protocol["order"]) / len(rows)
                                              if expected_by_context else None),
        "rows": rows,
        "limitations": ["This is a public-decision analysis; run audit_pilot separately for exact replay, grade and commitment checks.",
                        "Unrun means no exported run is available; while the pilot is active it can mean not exported yet.",
                        "The route assessment uses only signals delivered in public responses before commitment acceptance.",
                        "Signal availability does not prove how a model internally reasoned; no reasoning text is analyzed.",
                        "A zero realized reward can follow optimal expected-reward decisions; hindsight terrain knowledge is excluded from decision scoring.",
                        "The cases are hand-designed development contexts with two sessions each, not a population reliability estimate.",
                        "Costs are reported harness usage, not independently reconciled provider billing."],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pilotdir", type=Path)
    parser.add_argument("--output", type=Path, help="write full JSON to this new file; never overwrite")
    args = parser.parse_args(argv)
    if args.output is not None and (args.output.exists() or args.output.is_symlink()):
        parser.error("output already exists; choose a new path")
    try:
        summary = analyze(args.pilotdir)
        if args.output is not None:
            with args.output.open("x", encoding="utf-8") as stream:
                json.dump(summary, stream, indent=2, sort_keys=True, allow_nan=False)
                stream.write("\n")
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, "cannot analyze pilot: " + str(error) + "\n")
    print(json.dumps({key: summary[key] for key in (
        "planned_model_trials", "completed_model_trials", "status_counts", "known_reported_cost_usd",
        "optimal_initial_acquisition_count", "optimal_conditional_route_count", "reference_timing_match_count",
        "all_planned_trials_decisions_and_timing_optimal")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
