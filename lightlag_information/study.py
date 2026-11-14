"""Reproducible scripted mechanism study; no provider calls or model claims."""

import argparse
import hashlib
import json
import math
from pathlib import Path

from .environment import Environment
from .model import CONTEXTS
from .policies import POLICIES, expected_values, run_policy


class PublicTools:
    """A callback boundary, not a security sandbox."""

    __slots__ = ("rules", "map", "telemetry_log", "uplink", "advance")

    def __init__(self, environment):
        for name in self.__slots__:
            setattr(self, name, getattr(environment, name))


def _source_hashes():
    root = Path(__file__).resolve().parents[1]
    paths = sorted((root / "lightlag_information").glob("*.py"))
    paths += sorted((root / "tests" / "lightlag_information").glob("test_*.py"))
    paths += [root / "docs/superpowers/specs/2026-11-14-lightlag-information-choice-design.md",
              root / "docs/superpowers/plans/2026-11-14-lightlag-information-choice.md"]
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in paths}


def _write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def _line(handle, value):
    handle.write(json.dumps(value, sort_keys=True, allow_nan=False) + "\n")


def _episode(context_id, policy, episode_id, *, seed=0, terrain=None, signal=None):
    environment = Environment(seed=seed, context=context_id, terrain=terrain, signal=signal)
    decisions = run_policy(PublicTools(environment), policy)
    evaluation = environment.evaluate()
    row = {"episode_id": episode_id, "context_id": context_id, "policy": policy,
           "reward": evaluation["reward"], "evaluation": evaluation,
           "decisions": decisions}
    return row, {"episode_id": episode_id, "replay": environment.replay()}


def run_study(output):
    """Write the full predeclared matrix into a new directory and return summary."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    hashes = _source_hashes()
    context_rules = {context_id: Environment(context=context_id).rules() for context_id in CONTEXTS}
    protocol = {
        "schema_version": 1,
        "study_id": "information-choice-v1",
        "scope": "Scripted structural check of a route-decision abstraction, not the continuous rover or a model benchmark.",
        "paid_provider_calls": 0,
        "contexts": context_rules,
        "policies": list(POLICIES),
        "policy_ties": "selective skips probing on an equal value; route ties use lexical order (detour first)",
        "blind_control": "blind_probe matches always_probe cost and signal-delivery waiting, then uses the prior and ignores the signal value",
        "exact_enumeration": {
            "terrains": ["firm", "soft"], "signals": ["firm", "soft"],
            "weight": "P(terrain) * P(signal | terrain)",
            "aggregate": "Equal mean over four declared contexts; probability weighting within each context",
            "rows": len(CONTEXTS) * len(POLICIES) * 4,
        },
        "seeded_smoke": {"seeds": list(range(40)), "rows": len(CONTEXTS) * len(POLICIES) * 40,
                         "interpretation": "Separate deterministic smoke matrix in this independent environment; not a hidden holdout or population estimate"},
        "gate": "Exact selective aggregate strictly exceeds both always_probe and never_probe; selective chooses each behavior in at least one context; analytical and realized branch means match",
        "source_hashes": hashes,
        "replay": "Evaluator-only terrain, signal and transcript retained for every exact and seeded row",
        "next_step": "Only if the mechanism gate passes: separately freeze a protected Harbor model pilot with clear instructions and scripting; no automatic expansion",
    }
    # Publish the declared plan before constructing any evaluated branch.
    _write_json(output / "protocol.json", protocol)
    exact_means = {context: {policy: 0.0 for policy in POLICIES} for context in CONTEXTS}
    seeded_means = {context: {policy: 0.0 for policy in POLICIES} for context in CONTEXTS}
    with (output / "exact_rows.jsonl").open("w", encoding="utf-8") as exact_file, \
            (output / "seeded_rows.jsonl").open("w", encoding="utf-8") as seeded_file, \
            (output / "replays.jsonl").open("w", encoding="utf-8") as replay_file:
        for context_id, rules in context_rules.items():
            prior = rules["context"]["prior_firm"]
            accuracy = rules["signal_accuracy"]
            for policy in POLICIES:
                for terrain in ("firm", "soft"):
                    for signal in ("firm", "soft"):
                        weight = (prior if terrain == "firm" else 1 - prior)
                        weight *= accuracy if signal == terrain else 1 - accuracy
                        episode_id = "/".join(("exact", context_id, policy, terrain, signal))
                        row, replay = _episode(context_id, policy, episode_id, terrain=terrain, signal=signal)
                        row.update(terrain=terrain, signal=signal, weight=weight,
                                   weighted_reward=weight * row["reward"])
                        exact_means[context_id][policy] += row["weighted_reward"]
                        _line(exact_file, row)
                        _line(replay_file, replay)
                for seed in range(40):
                    episode_id = "/".join(("seeded", context_id, policy, str(seed)))
                    row, replay = _episode(context_id, policy, episode_id, seed=seed)
                    row["seed"] = seed
                    seeded_means[context_id][policy] += row["reward"] / 40
                    _line(seeded_file, row)
                    _line(replay_file, replay)
    analytical = {context: expected_values(rules) for context, rules in context_rules.items()}
    matches = all(math.isclose(exact_means[context][policy], analytical[context][policy], abs_tol=1e-12)
                  for context in CONTEXTS for policy in POLICIES)
    exact_aggregate = {policy: sum(values[policy] for values in exact_means.values()) / len(CONTEXTS)
                       for policy in POLICIES}
    seeded_aggregate = {policy: sum(values[policy] for values in seeded_means.values()) / len(CONTEXTS)
                        for policy in POLICIES}
    choices = {context: ("probe" if values["always_probe"] > values["never_probe"] else "no_probe")
               for context, values in analytical.items()}
    checks = {
        "analytical_matches_realized": matches,
        "beats_never_probe": exact_aggregate["selective"] > exact_aggregate["never_probe"],
        "beats_always_probe": exact_aggregate["selective"] > exact_aggregate["always_probe"],
        "uses_both_behaviors": set(choices.values()) == {"probe", "no_probe"},
        "source_unchanged": hashes == _source_hashes(),
    }
    summary = {
        "schema_version": 1,
        "scope": protocol["scope"],
        "exact": {"contexts": exact_means, "aggregate": exact_aggregate,
                  "analytical": analytical, "selective_choices": choices, "rows": 64},
        "seeded_smoke": {"contexts": seeded_means, "aggregate": seeded_aggregate, "rows": 640},
        "gate": {**checks, "passed": all(checks.values())},
        "limitations": ["Four hand-designed development contexts, not a population benchmark or hidden holdout.",
                        "Scripted success is not evidence of Claude difficulty or any model failure.",
                        "This finite route-choice reference does not establish continuous-rover performance.",
                        "Always probing loses expected reward in likely_firm, likely_soft and costly_probe.",
                        "No paid provider calls or protected model pilot were run."],
    }
    _write_json(output / "summary.json", summary)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args(argv)
    try:
        summary = run_study(arguments.output)
    except FileExistsError:
        parser.error("Output already exists; choose a new path to preserve previous results")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["gate"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
