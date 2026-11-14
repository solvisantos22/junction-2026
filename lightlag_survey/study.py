"""Free paired survey study with a separate, source-frozen check preparation step.

Development: ``python -m lightlag_survey.study --stage development --output NEW``.
Prepare check: add ``--stage prepare-check --development DEV --output NEW_CHECK``.
Execute check: ``--stage check --output NEW_CHECK``. No check policy runs during
preparation. Failed/missing episodes remain evidence and cannot make a gate pass.
"""

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from fractions import Fraction
import gzip
import hashlib
import itertools
import json
import math
import multiprocessing
from pathlib import Path
import platform
import time

from lightlag_expedition.reference_v2 import run_policy
from .environment import SurveyEnvironment
from .model import REGIONS

ROOT = Path(__file__).resolve().parents[1]
PAIRS = tuple(itertools.combinations(REGIONS, 2))
DEVELOPMENT_POLICIES = ("adaptive", "no_probe", "entropy") + tuple(
    "fixed:" + "+".join(pair) for pair in PAIRS)
SOURCE_FILES = tuple(
    package + "/" + module + ".py"
    for package, modules in (
        ("lightlag", ("__init__", "environment", "model")),
        ("lightlag_dynamic", ("__init__", "environment", "missions", "tools", "controllers", "kf_mpc")),
        ("lightlag_expedition", ("__init__", "environment", "missions", "model", "reference", "reference_v2")),
        ("lightlag_survey", ("__init__", "environment", "missions", "model", "study")),
    ) for module in modules
) + ("docs/lightlag-survey-gate.md",)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_hashes():
    return {name: sha(ROOT / name) for name in SOURCE_FILES}


LOADED_SOURCE_HASHES = source_hashes()


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _evidence(value):
    if isinstance(value, float) and not math.isfinite(value):
        return {"__nonfinite_float__": repr(value)}
    if isinstance(value, dict):
        return {key: _evidence(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_evidence(item) for item in value]
    return deepcopy(value)


def _write_new(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def policy_arguments(label):
    if label in ("adaptive", "no_probe", "entropy"):
        return {"name": "reference" if label == "adaptive" else label}
    if label in DEVELOPMENT_POLICIES:
        return {"name": "fixed_pair", "fixed_pair": tuple(label[6:].split("+"))}
    raise ValueError("unknown policy label: " + str(label))


def configuration(stage, selected_pair=None):
    if stage == "development":
        maps, seeds, policies = list(range(4)), list(range(100, 108)), list(DEVELOPMENT_POLICIES)
    elif stage == "check":
        pair = tuple(selected_pair or ())
        if pair not in PAIRS:
            raise ValueError("check needs a canonical development-selected pair")
        maps, seeds = list(range(4, 8)), list(range(200, 208))
        policies = ["adaptive", "no_probe", "entropy", "fixed:" + "+".join(pair)]
    else:
        raise ValueError("stage must be development or check")
    return {"stage": stage, "mission_seeds": maps, "episode_seeds": seeds,
            "policies": policies, "visibility": "hidden", "horizon": 60, "delay": 3,
            "normalization": 36, "selected_pair": list(selected_pair) if stage == "check" else None,
            "episodes": len(maps) * len(seeds) * len(policies)}


def cases(config):
    return [{"id": f"m{mission}-s{seed}-{policy}", "mission_seed": mission,
             "episode_seed": seed, "policy": policy}
            for mission in config["mission_seeds"] for seed in config["episode_seeds"]
            for policy in config["policies"]]


class PublicTools:
    """Five-method recording facade; an API boundary, not an adversarial sandbox."""
    __slots__ = ("__dispatch", "transcript")

    def __init__(self, dispatch):
        self.__dispatch, self.transcript = dispatch, []

    def _call(self, tool, arguments=None):
        arguments = {} if arguments is None else arguments
        row = {"n": len(self.transcript) + 1, "tool": tool, "arguments": _evidence(arguments)}
        try:
            result = self.__dispatch(tool, arguments)
        except Exception as error:
            row.update(ok=False, error={"type": type(error).__name__, "message": str(error)})
            self.transcript.append(row)
            raise
        row.update(ok=True, result=_evidence(result))
        self.transcript.append(row)
        return deepcopy(result)

    def rules(self):
        return self._call("rules")

    def map(self):
        return self._call("map")

    def telemetry_log(self):
        return self._call("telemetry_log")

    def uplink(self, commands):
        return self._call("uplink", {"commands": commands})

    def advance(self, ticks=1):
        return self._call("advance", {"ticks": ticks})


def _facade(environment):
    methods = {name: getattr(environment, name) for name in
               ("rules", "map", "telemetry_log", "uplink", "advance")}
    return PublicTools(lambda name, arguments: methods[name](**arguments))


def _finish(environment):
    while not environment.advance(5)["episode_complete"]:
        pass


def verify_replay(spec, transcript, replay):
    """Reconstruct every tool result and final hidden replay independently of policy."""
    env = SurveyEnvironment(seed=spec["episode_seed"], mission_seed=spec["mission_seed"])
    for call in transcript:
        try:
            result = getattr(env, call["tool"])(**call["arguments"])
        except Exception as error:
            actual = {"type": type(error).__name__, "message": str(error)}
            if call["ok"] or actual != call["error"]:
                raise AssertionError("tool error does not reconstruct")
        else:
            if not call["ok"] or _evidence(result) != call["result"]:
                raise AssertionError("tool result does not reconstruct")
    _finish(env)
    if env.replay() != replay:
        raise AssertionError("full replay does not reconstruct")
    evaluation = env.evaluate()
    if (evaluation["tick"] != 60 or evaluation["max_available_value"] != 36
            or not 0 <= evaluation["raw_score"] <= 36
            or not math.isclose(evaluation["raw_score"],
                                evaluation["sampled_value"] * evaluation["survival_factor"], abs_tol=1e-10)):
        raise AssertionError("grade/horizon/normalization mismatch")
    return True


def first_batch_coverage(transcript, replay, all_at_first_tick=False):
    first = next((call["result"] for call in transcript
                  if call["tool"] == "uplink" and call["ok"]), [])
    if all_at_first_tick and first:
        tick = first[0]["sent_tick"]
        first = [ack for call in transcript if call["tool"] == "uplink" and call["ok"]
                 for ack in call["result"] if ack["sent_tick"] == tick]
    ids = {ack["command_id"] for ack in first}
    sampled, inspected, ticks = set(), set(), []
    for packet in replay["received_telemetry"]:
        if not any(event.get("command_id") in ids for event in packet["events"]
                   if event["type"] == "command_executed"):
            continue
        ticks.append(packet["received_tick"])
        for event in packet["events"]:
            if event["type"] == "region_quality":
                sampled.add(event["region"])
            elif event["type"] == "inspection_result":
                inspected.add(event["region"])
    return {"scope": "all uplinks at first submission tick" if all_at_first_tick else "first successful uplink (transport batch; at most five commands)",
            "acknowledged_commands": deepcopy(first), "sample_quality_regions": sorted(sampled),
            "signal_regions": sorted(inspected), "observed_regions": sorted(sampled | inspected),
            "unobserved_regions": sorted(set(REGIONS) - sampled - inspected),
            "last_delivery_tick": max(ticks) if ticks else None}


def considered_regions(transcript, decisions):
    """Announced unsampled/nonpending regions available to planning at a decision.

    This is the candidate input set, not a claim that every possible route was
    exhaustively enumerated. Feasible first-region routes are counted separately.
    """
    snapshots, tick = [], 0
    for call in transcript:
        if not call["ok"]:
            continue
        if call["tool"] == "advance":
            tick = call["result"]["current_tick"]
        elif call["tool"] == "map":
            snapshots.append((tick, call["result"]["targets"]))
    regions = set()
    for decision in decisions:
        known = [targets for tick, targets in snapshots if tick <= decision["tick"]]
        if known:
            excluded = set(decision.get("confirmed_sampled", [])) | set(decision.get("pending_samples", []))
            regions.update(target["region"] for target in known[-1] if target["id"] not in excluded)
    return sorted(regions)


def run_episode(spec):
    """Return (row, full evidence), retaining policy or evaluator failures explicitly."""
    row = dict(spec, status="error", errors=[], raw_score=None, sampled_value=None,
               normalized_score=None, replay_verified=False)
    env = tools = controller = None
    result = replay = None
    try:
        arguments = policy_arguments(spec["policy"])
        env = SurveyEnvironment(seed=spec["episode_seed"], mission_seed=spec["mission_seed"])
        tools = _facade(env)
        controller = run_policy(tools, **arguments)
    except Exception as error:
        row["errors"].append({"phase": "policy", "type": type(error).__name__, "message": str(error)})
    if env is not None:
        try:
            _finish(env)
            result, replay = env.evaluate(), env.replay()
            row["replay_verified"] = verify_replay(spec, tools.transcript if tools else [], replay)
        except Exception as error:
            row["errors"].append({"phase": "finish/audit", "type": type(error).__name__, "message": str(error)})
    transcript = tools.transcript if tools else []
    decisions = deepcopy(getattr(controller, "decision_log", []))
    row["tool_errors"] = sum(not call["ok"] for call in transcript)
    if row["tool_errors"]:
        row["errors"].append({"phase": "public_tools", "type": "RejectedCall", "message": "public tool errors retained"})
    if result is not None and replay is not None:
        events = [event for state in replay["states"] for event in state["events"]]
        inspections = replay["survey"]["inspection_executed"]
        reserved = replay["survey"]["inspection_reserved_regions"]
        feasible = {region for decision in decisions for region, value in decision.get("first_region_values", {}).items() if value > 0}
        row.update(alive=result["alive"], at_base=result["at_base"],
                   terminal_battery=replay["states"][-1]["battery"],
                   sampled_targets=result["sampled_targets"],
                   sampled_regions=sorted({sample["region"] for sample in result["samples"]}),
                   samples_on_time=sum(sample["on_time"] for sample in result["samples"]),
                   samples_late=sum(not sample["on_time"] for sample in result["samples"]),
                   failed_samples=sum(event["type"] == "sample_failed" for event in events),
                   failed_inspections=sum(not inspection["success"] for inspection in inspections),
                   canceled_inspections=len(reserved) - len(inspections),
                   reserved_probe_set=reserved,
                   probe_set=sorted(inspection["region"] for inspection in inspections if inspection["success"]),
                   considered_regions=considered_regions(transcript, decisions), feasible_regions=sorted(feasible),
                   initial_single_region_values=_evidence(getattr(controller, "initial_single_region_values", {})),
                   initial_single_region_plans=_evidence(getattr(controller, "initial_single_region_plans", {})),
                   first_batch_info=first_batch_coverage(transcript, replay),
                   initial_submission_info=first_batch_coverage(transcript, replay, all_at_first_tick=True),
                   public_calls=len(transcript))
        if not row["errors"]:
            row.update(status="ok", raw_score=result["raw_score"], sampled_value=result["sampled_value"],
                       normalized_score=result["raw_score"] / result["max_available_value"])
    return row, _evidence({"episode": row, "evaluation": result, "replay": replay,
                           "transcript": transcript, "decisions": decisions})


def _score(row):
    return Fraction(str(row["raw_score"]))


def _valid(row):
    return (row.get("status") == "ok" and row.get("replay_verified") is True
            and row.get("tool_errors") == 0
            and not row.get("errors")
            and all(type(row.get(key)) in (int, float) and math.isfinite(row[key])
                    for key in ("raw_score", "sampled_value", "normalized_score", "terminal_battery"))
            and type(row.get("alive")) is bool and type(row.get("at_base")) is bool
            and 0 <= row["raw_score"] <= 36)


def select_fixed_pair(rows):
    config = configuration("development")
    indexed = {row["id"]: row for row in rows}
    expected = cases(config)
    if (len(rows) != len(expected) or set(indexed) != {case["id"] for case in expected}
            or not all(_valid(row) for row in rows)
            or any(any(indexed[case["id"]].get(key) != value for key, value in case.items()) for case in expected)):
        raise ValueError("best pair selection requires a complete valid development matrix")
    totals = {pair: sum((_score(row) for row in rows if row["policy"] == "fixed:" + "+".join(pair)), Fraction())
              for pair in PAIRS}
    return min(PAIRS, key=lambda pair: (-totals[pair], pair))


def structural_gate(rows):
    adaptive = [row for row in rows if row["policy"] == "adaptive" and _valid(row)]
    by_map = defaultdict(list)
    for row in adaptive:
        by_map[row["mission_seed"]].append(row)
    per_map = {}
    for mission, group in sorted(by_map.items()):
        values = group[0].get("initial_single_region_values", {})
        plans = group[0].get("initial_single_region_plans", {})
        consistent = all(row.get("initial_single_region_values") == values and
                         row.get("initial_single_region_plans") == plans for row in group)
        valid = (set(values) == set(REGIONS) and set(plans) == set(REGIONS)
                 and all(type(value) in (int, float) and math.isfinite(value) and value > 0 for value in values.values()))
        best = max(map(lambda value: Fraction(str(value)), values.values())) if valid else Fraction()
        competitive = valid and all(2 * Fraction(str(values[region])) >= best
                                    and plans[region].get("feasible") is True
                                    and len(plans[region].get("targets", [])) == 2 for region in REGIONS)
        per_map[str(mission)] = {"all_six_competitive": bool(consistent and competitive),
                                "diagnostics_consistent_across_seeds": consistent,
                                "single_region_values": values, "single_region_plans": plans}
    sampled = sorted({region for row in adaptive for region in row.get("sampled_regions", [])})
    probe_sets = sorted({tuple(row.get("probe_set", [])) for row in adaptive if row.get("probe_set")})
    passed = (sum(item["all_six_competitive"] for item in per_map.values()) >= 2
              and len(sampled) >= 4 and len(probe_sets) >= 2)
    return {"passed": passed, "per_map": per_map, "sampled_regions": sampled,
            "distinct_nonempty_probe_sets": [list(pair) for pair in probe_sets]}


def summarize(rows, config):
    expected = cases(config)
    indexed = defaultdict(list)
    for row in rows:
        indexed[row.get("id")].append(row)
    expected_ids = {case["id"] for case in expected}
    missing, extra = sorted(expected_ids - set(indexed)), sorted(set(indexed) - expected_ids)
    duplicates = sorted(key for key, group in indexed.items() if len(group) != 1)
    invalid = sorted(row.get("id", "<missing-id>") for row in rows if not _valid(row))
    identities_match = all(len(indexed[case["id"]]) == 1 and
                           all(indexed[case["id"]][0].get(key) == value for key, value in case.items())
                           for case in expected if case["id"] in indexed)
    complete = not (missing or extra or duplicates or invalid) and identities_match
    groups = defaultdict(list)
    for row in rows:
        if _valid(row):
            groups[row["policy"]].append(row)
    def aggregate(group):
        return {"valid_episodes": len(group),
                              "raw_score": float(sum(map(_score, group), Fraction()) / len(group)),
                              "sampled_value": sum(row["sampled_value"] for row in group) / len(group),
                              "normalized_score": sum(row["normalized_score"] for row in group) / len(group),
                              "alive": sum(row["alive"] for row in group),
                              "home": sum(row["alive"] and row["at_base"] for row in group),
                              "terminal_battery": sum(row["terminal_battery"] for row in group) / len(group),
                              "per_region_episode_counts": {
                                  field: {region: sum(region in row.get(field, []) for row in group) for region in REGIONS}
                                  for field in ("considered_regions", "feasible_regions", "probe_set", "sampled_regions")}}
    aggregates = {policy: aggregate(group) for policy, group in sorted(groups.items())}
    per_map = {str(mission): {policy: aggregate([row for row in group if row["mission_seed"] == mission])
                              for policy, group in sorted(groups.items())
                              if any(row["mission_seed"] == mission for row in group)}
               for mission in config["mission_seeds"]}
    selected = list(select_fixed_pair(rows)) if complete and config["stage"] == "development" else config["selected_pair"]
    structural = structural_gate(rows) if config["stage"] == "development" else None
    comparisons, gate = {}, False
    if complete:
        adaptive = {row["mission_seed"]: {} for row in groups["adaptive"]}
        for row in groups["adaptive"]:
            adaptive[row["mission_seed"]][row["episode_seed"]] = row
        comparator_labels = ["no_probe", "entropy", "fixed:" + "+".join(selected)]
        for label in comparator_labels:
            differences = defaultdict(list)
            for row in groups[label]:
                differences[row["mission_seed"]].append(_score(adaptive[row["mission_seed"]][row["episode_seed"]]) - _score(row))
            means = {str(mission): sum(values, Fraction()) / len(values) for mission, values in differences.items()}
            mean = sum((value for values in differences.values() for value in values), Fraction()) / 32
            threshold = Fraction(1) if label == "no_probe" else Fraction(1, 2)
            comparisons[label] = {"mean_raw_gain": float(mean), "exact_mean_raw_gain": str(mean),
                                  "per_map_raw_gain": {key: float(value) for key, value in means.items()},
                                  "nonnegative_maps": sum(value >= 0 for value in means.values()),
                                  "required_raw_gain": float(threshold),
                                  "margin_pass": mean >= threshold,
                                  "maps_pass": sum(value >= 0 for value in means.values()) >= 3}
        safe = aggregates["adaptive"]["alive"] == 32 and aggregates["adaptive"]["home"] >= 31
        gate = safe and all(item["margin_pass"] and item["maps_pass"] for item in comparisons.values())
    return {"stage": config["stage"], "expected_episodes": len(expected), "retained_rows": len(rows),
            "complete": complete, "missing": missing, "unexpected": extra, "duplicates": duplicates,
            "invalid": invalid, "identities_match": identities_match,
            "aggregate": aggregates, "per_map": per_map, "development_selected_pair": selected,
            "structural_gate": structural, "paired_comparisons": comparisons,
            "check_gate_passed": bool(complete and config["stage"] == "check" and gate),
            "development_gate_passed": bool(complete and structural and structural["passed"]),
            "limits": ["Paired prior-generated science/physics seeds, not exact world integration.",
                       "Four maps per split; no population significance or optimal-policy claim.",
                       "Partial aggregates describe valid rows only; any missing/error row prevents gate passage.",
                       "Considered regions are announced unsampled/nonpending candidate inputs; feasible regions have retained feasible first-region routes.",
                       "First-batch coverage means one transport uplink; initial_submission_info includes all uplinks at that first tick.",
                       "Signal-flip causal diagnostic is optional and not executed by this matrix runner.",
                       "Raw score is primary; the larger normalization denominator is not hardness evidence."]}


def _assert_loaded_sources():
    current = source_hashes()
    if current != LOADED_SOURCE_HASHES:
        raise ValueError("source changed after this process imported the runner; use a fresh frozen process")
    return current


def _protocol(config, sources):
    return {"schema_version": 1, "config": config, "source_sha256": sources,
            "python_version": platform.python_version(),
            "evidence": "full public transcript, independent replay reconstruction, deterministic gzip",
            "selection": "greatest complete development mean raw score; exact ties lexicographic",
            "gate": {"zero_deaths": True, "minimum_home": 31, "cases_per_policy": 32,
                     "minimum_raw_gain": {"no_probe": 1.0, "entropy": 0.5, "fixed_pair": 0.5},
                     "minimum_nonnegative_maps_per_control": 3}}


def prepare_check(output, development):
    """Freeze selection/source/config before any check rollout; do not instantiate a world."""
    output, development = Path(output).resolve(), Path(development).resolve()
    if output.exists():
        raise FileExistsError("check output already exists; choose a new directory")
    sources = _assert_loaded_sources()
    manifest = json.loads((development / "sha256.json").read_text())
    required = {"protocol.json", "started.json", "rows.jsonl", "episodes.jsonl.gz", "summary.json"}
    if not required <= set(manifest):
        raise ValueError("development manifest lacks required full evidence")
    for name, digest in manifest.items():
        path = development / name
        if path.parent != development or sha(path) != digest:
            raise ValueError("development artifact hash mismatch: " + name)
    dev_protocol = json.loads((development / "protocol.json").read_text())
    if dev_protocol["config"] != configuration("development") or dev_protocol["source_sha256"] != sources:
        raise ValueError("development configuration or source does not match current frozen code")
    saved = json.loads((development / "summary.json").read_text())
    if (not saved.get("source_unchanged") or saved.get("runner_error")
            or saved.get("complete") is not True or saved.get("development_gate_passed") is not True):
        raise ValueError("development source changed or evidence is incomplete")
    rows = [json.loads(line) for line in (development / "rows.jsonl").read_text().splitlines()]
    with gzip.open(development / "episodes.jsonl.gz", "rt", encoding="utf-8") as stream:
        full_rows = [json.loads(line) for line in stream]
    if (len(full_rows) != len(rows) or any(full.get("episode") != row or full.get("replay") is None
                                         or not isinstance(full.get("transcript"), list)
                                         for row, full in zip(rows, full_rows))):
        raise ValueError("development full records do not match rows/replays/transcripts")
    summary = summarize(rows, dev_protocol["config"])
    if any(saved.get(key) != value for key, value in summary.items()):
        raise ValueError("saved development summary does not match retained rows")
    if not summary["development_gate_passed"]:
        raise ValueError("complete development structural gate must pass before preparing check")
    pair = tuple(summary["development_selected_pair"])
    protocol = _protocol(configuration("check", pair), sources)
    protocol["development_evidence"] = {
        "sha256_manifest": sha(development / "sha256.json"),
        "artifacts": manifest, "selected_pair": list(pair),
        "selection_cases": len(rows), "structural_gate": summary["structural_gate"],
        "selection_means": {label: data["raw_score"] for label, data in summary["aggregate"].items()
                            if label.startswith("fixed:")}}
    output.mkdir(parents=True, exist_ok=False)
    _write_new(output / "protocol.json", protocol)
    with (output / "protocol.sha256").open("x") as stream:
        stream.write(sha(output / "protocol.json") + "\n")
    return protocol


def _worker_failure(spec, error):
    row = dict(spec, status="error", raw_score=None, sampled_value=None, normalized_score=None,
               replay_verified=False, tool_errors=0,
               errors=[{"phase": "worker", "type": type(error).__name__, "message": str(error)}])
    return row, {"episode": row, "evaluation": None, "replay": None, "transcript": [], "decisions": []}


def run_study(output, stage="development", workers=1, progress=None):
    if type(workers) is not int or not 1 <= workers <= 3:
        raise ValueError("workers must be 1, 2 or 3")
    sources = _assert_loaded_sources()
    output = Path(output).resolve()
    if stage == "development":
        if output.exists():
            raise FileExistsError("output already exists; choose a new directory")
        protocol = _protocol(configuration(stage), sources)
        output.mkdir(parents=True, exist_ok=False)
        _write_new(output / "protocol.json", protocol)
    elif stage == "check":
        if not output.is_dir() or {path.name for path in output.iterdir()} != {"protocol.json", "protocol.sha256"}:
            raise ValueError("check needs a pristine directory from prepare-check; no reruns or overwrites")
        if sha(output / "protocol.json") != (output / "protocol.sha256").read_text().strip():
            raise ValueError("prepared check protocol changed after selection/source freeze")
        protocol = json.loads((output / "protocol.json").read_text())
        expected = configuration("check", protocol["config"].get("selected_pair"))
        if (protocol["config"] != expected or protocol["source_sha256"] != sources
                or "development_evidence" not in protocol):
            raise ValueError("prepared check configuration/source mismatch")
    else:
        raise ValueError("stage must be development or check")
    # Exclusive claim happens before the first worker/environment is created.
    _write_new(output / "started.json", {"workers": workers, "protocol_sha256": sha(output / "protocol.json")})
    specifications = cases(protocol["config"])
    rows, runner_error, executor, futures = [], None, None, None
    started = time.monotonic()
    try:
        with (output / "rows.jsonl").open("x", encoding="utf-8") as table, \
             (output / "episodes.jsonl.gz").open("xb") as raw, \
             gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            if workers > 1:
                executor = ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context("spawn"))
                futures = []
                for spec in specifications:
                    futures.append(executor.submit(run_episode, spec))
            else:
                futures = None
            for index, spec in enumerate(specifications):
                try:
                    row, full = run_episode(spec) if futures is None else futures[index].result()
                except Exception as error:
                    row, full = _worker_failure(spec, error)
                rows.append(row)
                table.write(_json(row) + "\n")
                table.flush()
                compressed.write((_json(full) + "\n").encode())
                if progress:
                    progress({"completed": len(rows), "total": len(specifications),
                              "elapsed_seconds": time.monotonic() - started})
    except BaseException as error:
        runner_error = {"type": type(error).__name__, "message": str(error)}
    finally:
        if executor is not None:
            executor.shutdown(wait=True, cancel_futures=True)
            if runner_error:
                # Cancel work that never began, but preserve every worker that did
                # finish while an earlier result/progress callback was interrupted.
                with (output / "rows.jsonl").open("a", encoding="utf-8") as table, \
                     (output / "episodes.jsonl.gz").open("ab") as raw, \
                     gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
                    for spec, future in zip(specifications[len(rows):], futures[len(rows):]):
                        if future.cancelled():
                            continue
                        try:
                            row, full = future.result()
                        except Exception as error:
                            row, full = _worker_failure(spec, error)
                        rows.append(row)
                        table.write(_json(row) + "\n")
                        compressed.write((_json(full) + "\n").encode())
    summary = summarize(rows, protocol["config"])
    source_error = None
    try:
        after = source_hashes()
    except Exception as error:
        after, source_error = {}, {"type": type(error).__name__, "message": str(error)}
    summary.update(source_unchanged=sources == after, source_sha256_after=after,
                   source_read_error=source_error, runner_error=runner_error,
                   elapsed_seconds=time.monotonic() - started)
    if runner_error or not summary["source_unchanged"]:
        summary.update(complete=False, development_gate_passed=False, check_gate_passed=False)
    _write_new(output / "summary.json", summary)
    _write_new(output / "sha256.json", {path.name: sha(path) for path in sorted(output.iterdir()) if path.is_file()})
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("development", "prepare-check", "check"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--development", type=Path)
    parser.add_argument("--workers", type=int, choices=(1, 2, 3), default=1)
    args = parser.parse_args()
    if args.stage == "prepare-check":
        if args.development is None:
            parser.error("prepare-check requires --development")
        protocol = prepare_check(args.output, args.development)
        print(_json({"prepared": str(args.output), "config": protocol["config"], "rollouts": 0}))
        return 0
    if args.development is not None:
        parser.error("--development is only used by prepare-check")

    def progress(item):
        if item["completed"] % 32 == 0 or item["completed"] == item["total"]:
            print(_json(item), flush=True)

    summary = run_study(args.output, args.stage, args.workers, progress)
    print(_json({"complete": summary["complete"], "development_gate_passed": summary["development_gate_passed"],
                 "check_gate_passed": summary["check_gate_passed"],
                 "selected_pair": summary["development_selected_pair"]}))
    return 0 if summary["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
