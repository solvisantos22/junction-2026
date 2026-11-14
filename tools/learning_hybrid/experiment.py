"""Prepare fixed hybrid stages and select groups using audited development data."""

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path

import numpy as np

from lightlag_hybrid.policy import build_specs

ROOT = Path(__file__).resolve().parents[2]
PARENT = ROOT / "docs/learning-final-results/policy-freeze.json"
MAPS = {"smoke": [1], "development": list(range(610000, 610128)),
        "confirmation": list(range(611000, 611256)), "final": list(range(612000, 612256))}
FAMILIES = ("single_shortlist", "rank_ensemble", "rank_blend")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as handle:
        json.dump(value, handle, sort_keys=True, indent=2, allow_nan=False)
        handle.write("\n")


def pure(spec):
    return (spec["family"] == "control"
            or (spec["family"] in ("single_shortlist", "rank_ensemble")
                and spec["rho"] == 0))


def specs_for(stage, specs, selection=None):
    if stage in ("smoke", "development"):
        return specs
    prior = "development" if stage == "confirmation" else "confirmation"
    require(selection is not None and selection["stage"] == prior,
            "selection must come from the preceding declared stage")
    groups = selection["selected_groups"]
    require(groups and (stage != "final" or len(groups) == 1), "no qualified primary group")
    selected = [s for s in specs if s["group"] in groups]
    require(set(s["group"] for s in selected) == set(groups), "unknown selected group")
    if stage == "confirmation":
        controls = [s for s in specs if pure(s)]
    else:
        members = {m for s in selected for m in s["members"]}
        pools = {s["pool"] for s in selected if s["family"] != "single_shortlist"}
        controls = [s for s in specs if s["family"] == "control"
                    or (s["family"] == "single_shortlist" and s["rho"] == 0
                        and set(s["members"]).issubset(members))
                    or (s["family"] == "rank_ensemble" and s["rho"] == 0
                        and s["pool"] in pools)]
    ids = {s["id"] for s in selected + controls}
    return [s for s in specs if s["id"] in ids]


def prepare(freeze_path, stage, output, selection_path=None):
    from lightlag_hybrid.worker import source_manifest
    freeze = read(freeze_path)
    require(stage in MAPS, "undeclared stage")
    require(freeze["source_sha256"] == source_manifest(), "frozen sources changed")
    require(freeze["policy_freeze_sha256"] == digest(PARENT), "parent policy file changed")
    selection = read(selection_path) if selection_path else None
    if selection is not None:
        require(selection["freeze_sha256"] == digest(freeze_path), "selection belongs to another freeze")
    specs = specs_for(stage, build_specs(read(PARENT)), selection)
    jobs = [{"id": f"{stage}-{spec['id']}-{seed}", "stage": stage,
             "seed": seed, "spec": spec}
            for seed in MAPS[stage] for spec in specs]
    payload = {"schema": "learning-hybrid-stage-v1", "name": stage,
               "freeze_sha256": digest(freeze_path), "source_sha256": freeze["source_sha256"],
               "selection_sha256": digest(selection_path) if selection_path else None,
               "primary_groups": selection["selected_groups"] if stage == "final" else [],
               "candidate_groups": selection["selected_groups"] if stage == "confirmation" else [],
               "jobs": jobs}
    write_new(output, payload)
    return {"stage": stage, "arms": len(specs), "maps": len(MAPS[stage]), "jobs": len(jobs)}


def paired(values):
    values = np.asarray(values, dtype=float)
    # One map is the unit; average training seeds before arriving here.
    indices = np.random.default_rng(612256).integers(0, len(values), size=(20000, len(values)))
    means = values[indices].mean(axis=1)
    return {"mean": float(values.mean()),
            "bootstrap_95_percentile": np.quantile(means, [.025, .975]).tolist()}


def summarize(stage, state):
    require(state["status"] == "complete", "stage must be terminal and complete")
    require(state["freeze_sha256"] == stage["freeze_sha256"], "stage freeze mismatch")
    rows = state["rows"]
    if isinstance(rows, list):
        require(len({r["job_id"] for r in rows}) == len(rows), "duplicate job rows")
        rows = {r["job_id"]: r for r in rows}
    jobs = stage["jobs"]
    require(len({j["id"] for j in jobs}) == len(jobs), "duplicate jobs")
    require(set(rows) == {j["id"] for j in jobs}, "missing or unexpected results")
    expected_maps = MAPS[stage["name"]]
    by_arm, specs = defaultdict(dict), {}
    for job in jobs:
        row = rows[job["id"]]
        audit = row.get("audit")
        require(row["status"] == "complete" and isinstance(audit, dict)
                and audit.get("physics_verified") is True
                and audit.get("job_id") == job["id"]
                and audit.get("case_sha256") == row.get("case_sha256")
                and isinstance(row.get("case_sha256"), str)
                and (job["spec"]["kind"] == "beam" or audit.get("hybrid_choices_verified") is True)
                and (stage["name"] != "final" or audit.get("full_controller_replay") is True),
                "missing successful audit")
        require(not row.get("error"), "controller error")
        require(row["seed"] == job["seed"] and row["spec_id"] == job["spec"]["id"], "row identity mismatch")
        require(isinstance(row["sha256"], str) and len(row["sha256"]) == 64, "missing artifact hash")
        require(np.isfinite(row["reward"]) and 0 <= row["reward"] <= 1, "invalid reward")
        require(type(row["home"]) is bool and type(row["alive"]) is bool, "missing safety outcomes")
        require(type(row["invalid_calls"]) is int and row["invalid_calls"] >= 0, "invalid call count")
        name, seed = job["spec"]["id"], job["seed"]
        require(seed not in by_arm[name], "duplicate arm-map")
        by_arm[name][seed] = row
        require(name not in specs or specs[name] == job["spec"], "changing arm spec")
        specs[name] = job["spec"]
    for name, records in by_arm.items():
        require(sorted(records) == expected_maps, "incomplete arm maps: " + name)
    require("greedy" in by_arm and "beam" in by_arm, "missing matched controls")
    grouped = defaultdict(list)
    for spec in specs.values():
        grouped[spec["group"]].append(spec)
    summary = {}
    for group, members in sorted(grouped.items()):
        first = members[0]
        require(all(m["family"] == first["family"] for m in members), "mixed group family")
        if first["family"] == "single_shortlist":
            require(sorted(m["training_seed"] for m in members) == [17, 29, 43], "all three training seeds required")
        else:
            require(len(members) == 1, "duplicate ensemble/control group")
        records = [by_arm[m["id"]][s] for m in members for s in expected_maps]
        scores = [float(np.mean([by_arm[m["id"]][s]["reward"] for m in members])) for s in expected_maps]
        safety = {"deaths": sum(not r["alive"] for r in records),
                  "home_rate": sum(r["home"] and r["alive"] for r in records) / len(records),
                  "invalid_calls": sum(r["invalid_calls"] for r in records)}
        summary[group] = {"family": first["family"], "arms": sorted(m["id"] for m in members),
                          "pool": first["pool"], "rho": first["rho"],
                          "maps": len(expected_maps), "episodes": len(records),
                          "mean_reward": float(np.mean(scores)), "map_rewards": scores, **safety,
                          "vs_greedy": paired([v - by_arm["greedy"][s]["reward"] for s, v in zip(expected_maps, scores)]),
                          "vs_beam": paired([v - by_arm["beam"][s]["reward"] for s, v in zip(expected_maps, scores)])}
    return summary


def select(stage, summary):
    n = len(MAPS[stage["name"]])
    greedy = summary["greedy"]
    eligible = [g for g, s in summary.items()
                if s["family"] in FAMILIES
                and not (s["family"] == "single_shortlist" and s["rho"] == 0)
                and s["deaths"] == 0 and s["invalid_calls"] == 0
                and s["home_rate"] >= greedy["home_rate"] - 1/n]
    ranking = lambda group: (-summary[group]["mean_reward"], group)
    if stage["name"] == "development":
        return [g for family in FAMILIES for g in sorted(
            [g for g in eligible if summary[g]["family"] == family], key=ranking)[:2]]
    if stage["name"] == "confirmation":
        eligible = [g for g in eligible if g in stage["candidate_groups"]
                    and summary[g]["vs_greedy"]["mean"] > 0]
        return sorted(eligible, key=ranking)[:1]
    return []


def analyze(stage_path, status_path, output):
    stage, state = read(stage_path), read(status_path)
    require(state["stage_sha256"] == digest(stage_path), "status belongs to another stage file")
    summary = summarize(stage, state)
    selected = select(stage, summary)
    success = {}
    if stage["name"] == "final":
        for group in stage["primary_groups"]:
            item = summary[group]
            success[group] = (item["vs_greedy"]["mean"] >= .01
                              and item["vs_greedy"]["bootstrap_95_percentile"][0] > 0
                              and item["deaths"] == 0 and item["invalid_calls"] == 0
                              and item["home_rate"] >= summary["greedy"]["home_rate"] - 1/256)
    result = {"schema": "learning-hybrid-analysis-v1", "stage": stage["name"],
              "freeze_sha256": stage["freeze_sha256"], "stage_sha256": digest(stage_path),
              "status_sha256": digest(status_path), "summary": summary,
              "selected_groups": selected, "primary_success": success,
              "artifacts": {k: r["sha256"] for k, r in sorted(state["rows"].items())},
              "limit": "Map bootstrap conditional on retained policies; development/confirmation are selection data."}
    write_new(output, result)
    return {"stage": stage["name"], "groups": len(summary), "selected_groups": selected,
            "primary_success": success}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("--freeze", required=True, type=Path)
    prep.add_argument("--stage", required=True, choices=MAPS)
    prep.add_argument("--selection", type=Path)
    prep.add_argument("--output", required=True, type=Path)
    summary = commands.add_parser("analyze")
    summary.add_argument("--stage-file", required=True, type=Path)
    summary.add_argument("--status", required=True, type=Path)
    summary.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = (prepare(args.freeze, args.stage, args.output, args.selection)
              if args.command == "prepare" else analyze(args.stage_file, args.status, args.output))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
