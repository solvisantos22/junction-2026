"""Frozen complete-branch mechanism study, with no model or provider calls."""

import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path

from .environment import Environment
from .model import CONTEXTS
from .policies import POLICIES, acquisition_values, choose_acquisition, expected_values, run_policy


class PublicTools:
    __slots__ = ("rules", "map", "telemetry_log", "uplink", "advance")

    def __init__(self, environment):
        for name in self.__slots__:
            setattr(self, name, getattr(environment, name))


def _source_hashes():
    root = Path(__file__).resolve().parents[1]
    files = sorted((root / "lightlag_information_allocation").glob("*.py"))
    files += sorted((root / "tests/lightlag_information_allocation").glob("test_*.py"))
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in files}


def _write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def _line(stream, value):
    stream.write(json.dumps(value, sort_keys=True, allow_nan=False) + "\n")


def _episode(context, policy, episode_id, *, seed=0, terrains=None, signals=None):
    environment = Environment(seed=seed, context=context, terrains=terrains, signals=signals)
    decisions = run_policy(PublicTools(environment), policy)
    evaluation = environment.evaluate()
    row = {"episode_id": episode_id, "context_id": context, "policy": policy,
           "reward": evaluation["reward"], "evaluation": evaluation, "decisions": decisions}
    return row, {"episode_id": episode_id, "replay": environment.replay()}


def run_study(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    source_hashes = _source_hashes()
    rules_by_context = {name: Environment(context=name).rules() for name in CONTEXTS}
    exact_count = len(CONTEXTS) * len(POLICIES) * 16
    seeded_count = len(CONTEXTS) * len(POLICIES) * 20
    protocol = {
        "schema_version": 1,
        "study_id": "information-allocation-v1",
        "scope": "Two independent route unknowns, one shared inspection; constructed development cases, not continuous rover control or a model benchmark.",
        "paid_provider_calls": 0,
        "contexts": rules_by_context,
        "policies": list(POLICIES),
        "ties": "Acquisition prefers none, then a, then b; route ties are lexical; least-useful and entropy ties prefer a.",
        "exact_enumeration": {"state_fields": ["terrain_a", "terrain_b", "signal_a", "signal_b"],
                              "values": ["firm", "soft"], "rows": exact_count,
                              "weight": "Product of independent route priors and each signal likelihood conditional on its own terrain.",
                              "aggregate": "Equal weight across contexts; probability weight within each context."},
        "seeded_smoke": {"seeds": list(range(20)), "rows": seeded_count,
                         "interpretation": "Separate deterministic smoke matrix, paired across policies; not independent model repetitions."},
        "controls": {"least_useful_probe": "Always choose the lower-value inspection and then use its signal; it is not guaranteed irrelevant.",
                     "blind_selected_probe": "Match selective acquisition target, resource cost and timing but ignore its signal.",
                     "most_uncertain": "Always inspect the terrain prior closest to 0.5, then use its signal.",
                     "entropy_matched_gate": "Match selective probe/skip choice; when probing choose the prior closest to 0.5.",
                     "least_useful_matched_gate": "Match selective probe/skip choice; when probing choose the lower-value inspection."},
        "gate": "Selective matches analytical branch expectations, dominates each declared policy per context, strictly beats never/fixed-a/fixed-b in aggregate and chooses a/b/none across contexts.",
        "source_hashes": source_hashes,
        "next_step": "Only after structural validation, separately freeze a protected model pilot. Retain all successes and failures; no automatic expansion.",
    }
    _write_json(output / "protocol.json", protocol)
    exact = {context: {policy: 0.0 for policy in POLICIES} for context in CONTEXTS}
    seeded = {context: {policy: 0.0 for policy in POLICIES} for context in CONTEXTS}
    mass_checks = []
    with (output / "exact_rows.jsonl").open("w") as exact_file, \
            (output / "seeded_rows.jsonl").open("w") as seeded_file, \
            (output / "replays.jsonl").open("w") as replay_file:
        for context, rules in rules_by_context.items():
            for policy in POLICIES:
                mass = 0.0
                for ta, tb, sa, sb in itertools.product(("firm", "soft"), repeat=4):
                    terrains, signals = {"a": ta, "b": tb}, {"a": sa, "b": sb}
                    weight = 1.0
                    for route in ("a", "b"):
                        prior = rules["priors_firm"][route]
                        weight *= prior if terrains[route] == "firm" else 1 - prior
                        accuracy = rules["signal_accuracy"]
                        weight *= accuracy if signals[route] == terrains[route] else 1 - accuracy
                    episode_id = "/".join(("exact", context, policy, ta, tb, sa, sb))
                    row, replay = _episode(context, policy, episode_id, terrains=terrains, signals=signals)
                    row.update(terrains=terrains, signals=signals, weight=weight,
                               weighted_reward=weight * row["reward"])
                    mass += weight
                    exact[context][policy] += row["weighted_reward"]
                    _line(exact_file, row)
                    _line(replay_file, replay)
                mass_checks.append(math.isclose(mass, 1.0, abs_tol=1e-12))
                for seed in range(20):
                    episode_id = "/".join(("seeded", context, policy, str(seed)))
                    row, replay = _episode(context, policy, episode_id, seed=seed)
                    row["seed"] = seed
                    seeded[context][policy] += row["reward"] / 20
                    _line(seeded_file, row)
                    _line(replay_file, replay)
    analytical = {context: expected_values(rules) for context, rules in rules_by_context.items()}
    exact_mean = {policy: sum(values[policy] for values in exact.values()) / len(CONTEXTS)
                  for policy in POLICIES}
    seeded_mean = {policy: sum(values[policy] for values in seeded.values()) / len(CONTEXTS)
                   for policy in POLICIES}
    choices = {context: choose_acquisition(rules) for context, rules in rules_by_context.items()}
    checks = {
        "branch_probability_mass_one": all(mass_checks),
        "analytical_matches_realized": all(math.isclose(exact[c][p], analytical[c][p], abs_tol=1e-12)
                                            for c in CONTEXTS for p in POLICIES),
        "selective_dominates_each_context": all(exact[c]["selective"] + 1e-12 >= exact[c][p]
                                                for c in CONTEXTS for p in POLICIES),
        "strict_aggregate_gain_over_never_and_fixed_probes": all(
            exact_mean["selective"] > exact_mean[policy] for policy in ("never_probe", "probe_a", "probe_b")),
        "chooses_a_b_and_none": set(choices.values()) == {"a", "b", None},
        "source_unchanged": source_hashes == _source_hashes(),
    }
    summary = {
        "schema_version": 1,
        "scope": protocol["scope"],
        "exact": {"contexts": exact, "aggregate": exact_mean, "analytical": analytical,
                  "acquisition_values": {c: acquisition_values(r) for c, r in rules_by_context.items()},
                  "selective_choices": choices, "rows": exact_count},
        "seeded_smoke": {"contexts": seeded, "aggregate": seeded_mean, "rows": seeded_count},
        "gate": {**checks, "passed": all(checks.values())},
        "limitations": ["Hand-designed development cases, not an unseen population or model reliability sample.",
                        "Some lower-value inspections are still useful; least-useful is not synonymous with irrelevant.",
                        "Exact weighting and finite seeded outcomes are distinct estimates; paired seeds are not model repetitions.",
                        "This structural study makes no paid calls and establishes no model reasoning failure.",
                        "The reference is for this finite abstraction, not for continuous rover control."],
    }
    _write_json(output / "summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    result = run_study(parser.parse_args().output)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["gate"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
