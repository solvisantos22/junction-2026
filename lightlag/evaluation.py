"""Trusted episode execution and deterministic evaluation artifacts."""

import argparse
from collections.abc import Mapping
from copy import deepcopy
import csv
from inspect import signature
import json
from pathlib import Path
import re
import sys

from .controllers import POLICIES
from .controllers.api import PublicTools
from .environment import Environment
from .model import Config


def run_episode(policy, seed=0, config=None, world=None, policy_name=None):
    """Run one policy through public tools, then finish and grade the episode.

    Exceptions propagate to the caller: an invalid action or broken policy is
    an execution failure, not a benchmark score. A policy that catches a tool
    failure still fails the run when it returns. Transcript records contain
    copied ``source``, ``tool``, ``request`` and ``result`` fields. ``source``
    distinguishes policy calls from the evaluator's initial rules read and
    any advances needed after the policy returns.
    """
    env = Environment(seed=seed, config=deepcopy(config), world=deepcopy(world))
    transcript = []
    tool_names = ("rules", "map", "telemetry_log", "uplink", "advance")
    methods = {name: getattr(env, name) for name in tool_names}
    signatures = {name: signature(method) for name, method in methods.items()}
    counts = {source: dict.fromkeys(tool_names, 0) for source in ("policy", "evaluator")}
    current_tick = 0
    first_policy_failure = None

    def call(source, tool, args, kwargs):
        nonlocal current_tick, first_policy_failure
        record = {"source": source, "tool": tool}
        transcript.append(record)
        counts[source][tool] += 1
        try:
            record["request"] = {"args": deepcopy(list(args)), "kwargs": deepcopy(kwargs)}
            bound = signatures[tool].bind(*args, **kwargs)
            bound.apply_defaults()
            record["request"] = deepcopy(dict(bound.arguments))
            result = methods[tool](**deepcopy(record["request"]))
            record["result"] = deepcopy(result)
            if tool == "advance":
                current_tick = result["current_tick"]
            return deepcopy(result)
        except Exception as failure:
            record["error"] = {"type": type(failure).__name__, "message": str(failure)}
            if source == "policy" and first_policy_failure is None:
                first_policy_failure = failure
            raise

    def public_callback(tool):
        def invoke(*args, **kwargs):
            return call("policy", tool, args, kwargs)
        return invoke

    public_rules = call("evaluator", "rules", (), {})
    tools = PublicTools(**{name: public_callback(name) for name in tool_names})
    policy(tools)
    if first_policy_failure is not None:
        raise first_policy_failure
    while current_tick < public_rules["max_ticks"]:
        remaining = public_rules["max_ticks"] - current_tick
        ticks = min(remaining, public_rules["max_advance_ticks"])
        call("evaluator", "advance", (), {"ticks": ticks})

    return {
        "policy": policy_name if policy_name is not None else getattr(policy, "__name__", type(policy).__name__),
        "seed": seed,
        "delay": public_rules["delay_ticks"],
        "rules": public_rules,
        "result": env.evaluate(),
        "replay": env.replay(),
        "transcript": deepcopy(transcript),
        "tool_calls": {
            "policy": sum(counts["policy"].values()),
            "evaluator": sum(counts["evaluator"].values()),
            "total": len(transcript),
            "by_tool": deepcopy(counts),
        },
    }


def run_comparison(policies=None, seeds=range(10), delays=(0, 3), ticks=80,
                   reference_policy="reference", output_dir=None):
    """Compare policies on fresh default-world episodes in policy/delay/seed order.

    ``policies`` is an ordered name-to-callable mapping, defaulting to the six
    local ``POLICIES``. The return value separates the compact scientific
    ``summary`` from full ``episodes`` (including replay and call transcript).
    Deterministic policies and inputs produce deterministic results. Ratios use
    the matching seed/delay reference score, and their mean includes defined
    ratios only, with both counts reported. ``return_rate`` requires being alive
    and at base at the horizon. Names must match ``[A-Za-z0-9_][A-Za-z0-9_.-]*``.
    Replay basenames must fit 255 ASCII bytes. An output directory must be new
    and its parent must already exist. Export writes unchanged replays and CSV
    rows (null values are empty cells), then ``summary.json`` last. Policy or
    export failures propagate; partial files from an I/O failure are preserved.
    """
    policies = _validate_policies(POLICIES if policies is None else policies)
    seeds = _integer_selection(seeds, "seeds")
    delays = _integer_selection(delays, "delays")
    _validate_name(reference_policy, "reference_policy")
    configs = [Config(delay_ticks=delay, max_ticks=ticks) for delay in delays]
    output_dir = _new_output_path(output_dir)
    cases = [(name, policy, seed, config) for name, policy in policies.items()
             for config in configs for seed in seeds]
    replay_files = [_replay_filename(index, name, seed, config.delay_ticks)
                    for index, (name, _, seed, config) in enumerate(cases)]
    episodes = [run_episode(policy, seed=seed, config=config, policy_name=name)
                for name, policy, seed, config in cases]
    rows = []
    for episode, replay_file in zip(episodes, replay_files):
        result = episode["result"]
        rows.append({
            "policy": episode["policy"], "seed": episode["seed"], "delay": episode["delay"],
            "raw_score": result["raw_score"], "sampled_value": result["sampled_value"],
            "alive": result["alive"], "at_base": result["at_base"],
            "alive_and_at_base": result["alive"] and result["at_base"],
            "policy_calls": episode["tool_calls"]["policy"],
            "evaluator_calls": episode["tool_calls"]["evaluator"],
            "replay_file": replay_file,
        })
    _add_reference_ratios(rows, reference_policy)
    rules = {episode["delay"]: episode["rules"] for episode in episodes}
    summary = {
        "version": "lightlag-comparison-v1", "rules_version": episodes[0]["rules"]["version"],
        "seeds": list(seeds), "delays": list(delays), "ticks": ticks,
        "policies": list(policies), "reference_policy": reference_policy,
        "run_order": "policy/delay/seed",
        "rules": [deepcopy(rules[delay]) for delay in delays],
        "world": deepcopy(episodes[0]["replay"]["world"]), "runs": rows,
        "aggregates": _aggregate_rows(rows, policies, delays),
    }
    if output_dir is not None:
        _write_artifacts(output_dir, summary, episodes)
    return {"summary": summary, "episodes": episodes}


def _validate_name(name, label):
    if not isinstance(name, str) or re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", name) is None:
        raise ValueError(f"{label} must match [A-Za-z0-9_][A-Za-z0-9_.-]*")


def _validate_policies(policies):
    if not isinstance(policies, Mapping) or not policies:
        raise ValueError("policies must be a nonempty ordered name-to-callable mapping")
    selected = dict(policies)
    for name, policy in selected.items():
        _validate_name(name, "policy name")
        if not callable(policy):
            raise ValueError(f"policy {name!r} must be callable")
    return selected


def _integer_selection(values, label):
    try:
        selected = tuple(values)
    except TypeError as error:
        raise ValueError(f"{label} must be a nonempty iterable of integers") from error
    if not selected or any(type(value) is not int for value in selected):
        raise ValueError(f"{label} must be a nonempty iterable of integers (not booleans)")
    if len(set(selected)) != len(selected):
        raise ValueError(f"{label} must not contain duplicates")
    return selected


def _new_output_path(output_dir):
    if output_dir is None:
        return None
    try:
        path = Path(output_dir).expanduser().absolute()
    except TypeError as error:
        raise ValueError("output_dir must be a path") from error
    if "\x00" in str(path):
        raise ValueError("output_dir must not contain a null byte")
    if path.exists() or path.is_symlink():
        raise ValueError(f"output_dir must be new: {path}")
    if not path.parent.is_dir():
        raise ValueError(f"output_dir parent must already exist as a directory: {path.parent}")
    return path


def _replay_filename(index, policy, seed, delay):
    # The stable ordinal also prevents case-only policy names from colliding on
    # filesystems that do not distinguish upper- and lower-case letters.
    filename = f"{index:06d}__{policy}__seed-{seed}__delay-{delay}.json"
    if len(filename) > 255:
        raise ValueError("policy/seed/delay produce a replay filename longer than 255 bytes")
    return "replays/" + filename


def _write_json(path, value):
    with path.open("x", encoding="utf-8") as output:
        json.dump(value, output, indent=2, sort_keys=True, allow_nan=False)
        output.write("\n")


def _write_artifacts(output_dir, summary, episodes):
    # Exclusive directory/file creation rechecks ownership after the episodes.
    # Do not remove partial artifacts on failure: another writer may own them.
    output_dir.mkdir()
    (output_dir / "replays").mkdir()
    for row, episode in zip(summary["runs"], episodes):
        _write_json(output_dir / row["replay_file"], episode["replay"])
    with (output_dir / "scores.csv").open("x", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(summary["runs"][0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(summary["runs"])
    _write_json(output_dir / "summary.json", summary)


def _add_reference_ratios(rows, reference_policy):
    references = {(row["seed"], row["delay"]): row["raw_score"]
                  for row in rows if row["policy"] == reference_policy}
    for row in rows:
        reference = references.get((row["seed"], row["delay"]))
        ratio, reason = None, None
        if reference is None:
            reason = "missing_reference"
        elif reference <= 0:
            reason = "zero_reference_score" if reference == 0 else "negative_reference_score"
        else:
            ratio = row["raw_score"] / reference
        row["reference_ratio"] = ratio
        row["reference_ratio_reason"] = reason


def _aggregate_rows(rows, policies, delays):
    aggregates = []
    for name in policies:
        for delay in delays:
            group = [row for row in rows if row["policy"] == name and row["delay"] == delay]
            scores = [row["raw_score"] for row in group]
            ratios = [row["reference_ratio"] for row in group
                      if row["reference_ratio"] is not None]
            count = len(group)
            aggregates.append({
                "policy": name, "delay": delay, "run_count": count,
                "mean_raw_score": sum(scores) / count,
                "min_raw_score": min(scores), "max_raw_score": max(scores),
                "survival_rate": sum(row["alive"] for row in group) / count,
                "return_rate": sum(row["alive_and_at_base"] for row in group) / count,
                "mean_policy_calls": sum(row["policy_calls"] for row in group) / count,
                "mean_evaluator_calls": sum(row["evaluator_calls"] for row in group) / count,
                "mean_reference_ratio": sum(ratios) / len(ratios) if ratios else None,
                "reference_ratio_defined_count": len(ratios),
                "reference_ratio_undefined_count": count - len(ratios),
            })
    return aggregates


def _cli_policies():
    from lightlag_controllers import ALL_STRATEGIES, as_policy

    return {**POLICIES, **{"team_" + strategy.name: as_policy(strategy)
                          for strategy in ALL_STRATEGIES}}


def main(argv=None):
    """Run a comparison, printing only the compact deterministic JSON summary."""
    available = _cli_policies()
    parser = argparse.ArgumentParser(
        description="Compare Lightlag policies on the default world and current simulator rules.")
    parser.add_argument("--seeds", type=int, nargs="+", default=list(range(10)),
                        help="distinct episode seeds, in requested order (default: 0 through 9)")
    parser.add_argument("--delays", type=int, nargs="+", default=[0, 3],
                        help="distinct one-way delays in ticks (default: 0 3)")
    parser.add_argument("--ticks", type=int, default=80, help="fixed episode horizon (default: 80)")
    parser.add_argument("--policies", nargs="+", choices=list(available), default=list(POLICIES),
                        help="distinct policy names, in requested order (default: six local policies)")
    parser.add_argument("--reference-policy", default="reference",
                        help="ratio denominator; may be unselected, giving null ratios (default: reference)")
    parser.add_argument("--output-dir", type=Path,
                        help="new artifact directory; its parent directory must already exist")
    args = parser.parse_args(argv)
    try:
        if len(set(args.policies)) != len(args.policies):
            raise ValueError("policies must not contain duplicates")
        batch = run_comparison({name: available[name] for name in args.policies},
                               seeds=args.seeds, delays=args.delays, ticks=args.ticks,
                               reference_policy=args.reference_policy, output_dir=args.output_dir)
        print(json.dumps(batch["summary"], indent=2, sort_keys=True, allow_nan=False))
    except Exception as error:
        # A controller bug or invalid tool request is an execution error, never
        # a fabricated zero score or a partially successful scientific summary.
        print(f"lightlag.evaluation: {type(error).__name__}: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
