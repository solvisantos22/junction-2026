"""Free exhaustive closure of the prior-leader inspection blind spot.

This imports the unchanged allocation simulator and constructs two new Context
fixtures without modifying its published registry. It makes no model calls.
"""

import argparse
from dataclasses import asdict, dataclass
from fractions import Fraction
import gzip
import hashlib
from itertools import product
import json
from pathlib import Path
from typing import Optional

from lightlag_information_allocation.environment import Environment
from lightlag_information_allocation.model import Context
from lightlag_information_allocation.policies import acquisition_values


REPO = Path(__file__).resolve().parents[1]
ROUTES = ("a", "b", "detour")
CASES = (
    Context("challenger_b", .85, .50, 7, 10),
    Context("challenger_a", .50, .85, 10, 7),
)
EXPECTED = {"skip": Fraction(51, 100), "leader_probe": Fraction(3939, 8000),
            "challenger_probe": Fraction(951, 1600), "blind_probe": Fraction(357, 800)}


def fraction(value):
    return Fraction(str(value))


@dataclass(frozen=True)
class Strategy:
    inspection: Optional[str]
    firm_route: str
    soft_route: str

    @property
    def id(self):
        if self.inspection is None:
            return "direct_" + self.firm_route
        return "probe_{}_firm_{}_soft_{}".format(self.inspection, self.firm_route, self.soft_route)


def strategies():
    return tuple(Strategy(None, route, route) for route in ROUTES) + tuple(
        Strategy(inspected, firm, soft)
        for inspected in ("a", "b") for firm, soft in product(ROUTES, repeat=2))


def worlds(rules):
    result = []
    for ta, tb, sa, sb in product(("firm", "soft"), repeat=4):
        terrains, signals = {"a": ta, "b": tb}, {"a": sa, "b": sb}
        weight = Fraction(1)
        for route in ("a", "b"):
            prior = fraction(rules["priors_firm"][route])
            weight *= prior if terrains[route] == "firm" else 1 - prior
            accuracy = fraction(rules["signal_accuracy"])
            weight *= accuracy if signals[route] == terrains[route] else 1 - accuracy
        result.append((terrains, signals, weight))
    if sum(row[2] for row in result) != 1:
        raise ValueError("joint outcome probability mass is not one")
    return tuple(result)


def arithmetic_reward(rules, strategy, terrains, signals):
    """Realized branch score from published costs/timing, without policy helpers."""
    route = strategy.firm_route
    if strategy.inspection is not None and signals[strategy.inspection] == "soft":
        route = strategy.soft_route
    inspected = strategy.inspection is not None
    departure = 3 * rules["delay"] + 2 if inspected else rules["delay"] + 1
    trip = rules["routes"][route]
    completion = departure + trip["duration"]
    energy = rules["initial_energy"] - (rules["context"]["probe_energy"] if inspected else 0)
    state = terrains.get(route, "firm")
    if trip["energy"][state] > energy or completion > rules["horizon"]:
        return Fraction(0)
    return max(Fraction(0), fraction(trip["target_value"]) -
               fraction(rules["penalty_per_tick"]) * completion) / fraction(rules["normalization"])


def exact_strategy_values(rules):
    branches = worlds(rules)
    return {strategy: sum(weight * arithmetic_reward(rules, strategy, terrains, signals)
                          for terrains, signals, weight in branches)
            for strategy in strategies()}


class PublicTools:
    __slots__ = ("rules", "map", "telemetry_log", "uplink", "advance")

    def __init__(self, environment):
        for name in self.__slots__:
            setattr(self, name, getattr(environment, name))


def play_strategy(tools, strategy):
    """Follow one contingent plan using only delivered public observations."""
    rules = tools.rules()
    tick = tools.telemetry_log()["current_tick"]
    if tick != 0:
        raise ValueError("a fresh episode is required")

    def advance_to(target, current):
        while current < target:
            response = tools.advance(min(rules["max_advance_ticks"], target - current))
            if response["current_tick"] <= current:
                raise ValueError("public clock did not advance")
            current = response["current_tick"]
        return current

    route = strategy.firm_route
    if strategy.inspection is not None:
        tools.uplink([{"action": "probe", "route": strategy.inspection}])
        tick = advance_to(2 * rules["delay"] + 1, tick)
        signal = next(event["signal"] for event in tools.telemetry_log()["entries"]
                      if event["action"] == "probe" and event["probe_route"] == strategy.inspection)
        if signal == "soft":
            route = strategy.soft_route
    tools.uplink([{"action": "commit", "route": route}])
    advance_to(rules["horizon"], tick)


def case_summary(context, values):
    direct = {plan.firm_route: value for plan, value in values.items() if plan.inspection is None}
    leader = max(ROUTES, key=lambda route: direct[route])
    by_acquisition = {inspection: max(value for plan, value in values.items()
                                      if plan.inspection == inspection) for inspection in (None, "a", "b")}
    chosen = max(by_acquisition, key=by_acquisition.get)
    challenger = "b" if leader == "a" else "a"
    blind = values[Strategy(challenger, leader, leader)]
    actual = {"skip": by_acquisition[None], "leader_probe": by_acquisition[leader],
              "challenger_probe": by_acquisition[challenger], "blind_probe": blind}
    if leader not in ("a", "b") or chosen != challenger or actual != EXPECTED:
        raise ValueError("frozen challenger case does not have the declared exact result")
    reference = acquisition_values(Environment(context=context).rules())
    if any(abs(reference[key or "none"] - float(value)) > 1e-12
           for key, value in by_acquisition.items()):
        raise ValueError("public Bayesian reference differs from independent enumeration")
    best = max(values.values())
    return {"context": asdict(context), "prior_best_route": leader, "best_inspection": chosen,
            "prior_route_expected_rewards": {k: float(v) for k, v in direct.items()},
            "expected_rewards": {k: float(v) for k, v in actual.items()},
            "exact_expected_rewards": {k: str(v) for k, v in actual.items()},
            "gain_over_skip": float(best - actual["skip"]),
            "gain_over_leader_matched_gate": float(best - actual["leader_probe"]),
            "optimal_strategies": [dict(asdict(plan), strategy_id=plan.id)
                                   for plan, value in values.items() if value == best],
            "all_strategy_values": [{"strategy_id": plan.id, "expected_reward": float(value),
                                     "exact_expected_reward": str(value)} for plan, value in values.items()]}


def robustness_check():
    """Predeclared nearby public inputs; no simulator or model outcome selection."""
    minimum_gap, minimum_lead, count = Fraction(1), Fraction(1), 0
    for pa, pb, va, vb in product((.825, .85, .875), (.475, .50, .525),
                                  (6.75, 7, 7.25), (9.75, 10)):
        rules = Environment(context=Context("nearby", pa, pb, va, vb)).rules()
        values = exact_strategy_values(rules)
        direct = {s.firm_route: value for s, value in values.items() if s.inspection is None}
        by_probe = {p: max(v for s, v in values.items() if s.inspection == p) for p in (None, "a", "b")}
        lead = direct["a"] - max(direct["b"], direct["detour"])
        gap = by_probe["b"] - max(by_probe[None], by_probe["a"])
        if lead <= 0 or gap <= 0:
            raise ValueError("nearby public case loses its challenger-inspection distinction")
        minimum_gap, minimum_lead = min(minimum_gap, gap), min(minimum_lead, lead)
        count += 1
    return {"cases": count, "method": "Exact arithmetic over the 21 strategies, no model trials.",
            "grid": {"prior_a": [.825, .85, .875], "prior_b": [.475, .50, .525],
                     "value_a": [6.75, 7, 7.25], "value_b": [9.75, 10]},
            "minimum_challenger_gain": float(minimum_gap),
            "minimum_prior_leader_margin": float(minimum_lead), "all_passed": True}


def source_hashes():
    paths = sorted((REPO / "lightlag_information_allocation").glob("*.py")) + [Path(__file__).resolve()]
    return {str(path.relative_to(REPO)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def write_json(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def run_check(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    hashes = source_hashes()
    write_json(output / "protocol.json", {
        "schema_version": 1, "study_id": "challenger-closure-v1", "paid_provider_calls": 0,
        "selection": "Two constructed public cases selected by free parameter search before any new model trial.",
        "contexts": [asdict(context) for context in CASES], "strategies_per_case": 21,
        "worlds_per_strategy": 16, "branch_evaluations": 672, "source_hashes": hashes,
        "reference": "Enumerate all direct routes and all contingent route choices after either single inspection.",
        "timing": "Earliest legal actions; uninformative waiting only reduces reward in this fixed-state one-shot task.",
        "control": "Inspect the prior-leading route at the same cost/time, then choose the posterior-best route.",
        "scope": "Free closure of an identified diagnostic blind spot; no Claude difficulty or continuous-rover claim.",
    })
    summaries, count = [], 0
    raw_hash, raw_bytes = hashlib.sha256(), 0
    with (output / "weighted_rows.jsonl").open("x", encoding="utf-8") as rows, \
            (output / "replays.jsonl.gz").open("xb") as binary, \
            gzip.GzipFile(filename="", fileobj=binary, mode="wb", mtime=0) as replays:
        for context in CASES:
            rules = Environment(context=context).rules()
            values = exact_strategy_values(rules)
            simulated = {}
            for strategy in strategies():
                weighted = Fraction(0)
                for terrains, signals, weight in worlds(rules):
                    environment = Environment(seed=0, context=context, terrains=terrains, signals=signals)
                    play_strategy(PublicTools(environment), strategy)
                    evaluation = environment.evaluate()
                    expected = arithmetic_reward(rules, strategy, terrains, signals)
                    if fraction(evaluation["reward"]) != expected:
                        raise ValueError("simulated branch reward differs from independent arithmetic")
                    weighted += weight * expected
                    episode_id = "/".join((context.id, strategy.id, terrains["a"], terrains["b"], signals["a"], signals["b"]))
                    row = {"episode_id": episode_id, "context_id": context.id, "strategy": asdict(strategy),
                           "terrains": terrains, "signals": signals, "weight": float(weight),
                           "exact_weight": str(weight), "reward": evaluation["reward"],
                           "exact_reward": str(expected), "weighted_reward": float(weight * expected)}
                    rows.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
                    encoded = (json.dumps({"episode_id": episode_id, "replay": environment.replay()},
                                          sort_keys=True, allow_nan=False) + "\n").encode()
                    replays.write(encoded)
                    raw_hash.update(encoded)
                    raw_bytes += len(encoded)
                    count += 1
                simulated[strategy] = weighted
            if simulated != values:
                raise ValueError("simulated strategy expectation differs from exact enumeration")
            summaries.append(case_summary(context, simulated))
    robust = robustness_check()
    if source_hashes() != hashes or count != 672:
        raise ValueError("source changed during execution or branch coverage is incomplete")
    summary = {
        "schema_version": 1, "passed": True, "paid_provider_calls": 0, "model_trials": 0,
        "branch_evaluations": count, "cases": summaries, "nearby_public_robustness": robust,
        "aggregate_expected_rewards": {k: float(v) for k, v in EXPECTED.items()},
        "source_unchanged": True, "all_branch_rewards_and_strategy_expectations_match": True,
        "limitations": ["Constructed development fixtures, not an unseen distribution or a Claude result.",
                        "The challenger also has greater target value and uncertainty in these two cases.",
                        "When either probe switches only between a/b, equal sensor costs/reliability give probe-A minus probe-B value = (2q-1)*pA*pB*(R_A-R_B), with R the post-probe firm payoff. This one-shot reduction remains simple.",
                        "A harder mission must test interacting future route/resource decisions; these checks alone establish no difficulty gap."],
    }
    write_json(output / "summary.json", summary)
    artifacts = {p.name: {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size}
                 for p in sorted(output.iterdir()) if p.is_file()}
    write_json(output / "artifact-manifest.json", {
        "files": artifacts, "replay_uncompressed_sha256": raw_hash.hexdigest(),
        "replay_uncompressed_bytes": raw_bytes, "replay_count": count,
    })
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        summary = run_check(args.output)
    except (OSError, ValueError) as error:
        parser.exit(1, "cannot run challenger check: " + str(error) + "\n")
    print(json.dumps({k: summary[k] for k in ("passed", "branch_evaluations", "model_trials", "aggregate_expected_rewards")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
