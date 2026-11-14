"""Verify archived physics, diagnostics, matrix completeness and frozen selection."""

import argparse
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
import json
import multiprocessing
from pathlib import Path
import time

from lightlag_traverse.environment import TraverseEnvironment
from .run import (OUTPUT, choose, collect, digest, load_bundle, metrics, normal, pins,
                  require, summarize, utc, write_json)


def audit_one(job):
    root, row = job
    bundle = load_bundle(Path(root), row)
    replay = bundle["replay"]
    require(row["name"] == bundle["job"]["name"] and row["seed"] == bundle["job"]["seed"], "job identity mismatch")
    require(row["error"] == bundle["error"] and row["invalid_calls"] == len(bundle["invalid"]), "error accounting")
    require(row["cpu_seconds"] == bundle["cpu_seconds"] and row["wall_seconds"] == bundle["wall_seconds"], "timing mismatch")
    env = TraverseEnvironment(replay["seed"], mission=replay["config"])
    schedule = defaultdict(list)
    for command in replay["commands"]:
        schedule[command["sent_tick"]].append(command)
    for tick in range(replay["config"]["max_ticks"]):
        for command in schedule.pop(tick, []):
            require(normal(env.uplink([command["command"]])) == [command], "acknowledgement mismatch")
        env.advance(1)
    require(not schedule, "commands after horizon")
    require(normal(env.replay()) == replay, "full physics replay mismatch")
    calculated = metrics(replay, bundle["beliefs"], bundle["predictions"])
    require(calculated == bundle["metrics"], "diagnostic recomputation mismatch")
    require(all(row[key] == value for key, value in calculated.items()), "ledger metrics mismatch")
    return {"name": row["name"], "seed": row["seed"], "commands": len(replay["commands"]),
            "states": len(replay["states"]), "beliefs": len(bundle["beliefs"]), "ok": True}


def audit(root, stage, workers=6, full=()):
    started = time.perf_counter()
    freeze = json.loads((root / stage / "freeze.json").read_text())
    report = json.loads((root / stage / "report.json").read_text())
    require(freeze["source"] == report["source"] == pins(), "pinned source mismatch")
    ledger = [json.loads(line) for line in (root / stage / "rows.jsonl").read_text().splitlines()]
    require(sorted(ledger, key=lambda r: (r["seed"], r["name"])) == report["rows"], "ledger/report mismatch")
    require(summarize(ledger, freeze["configs"], freeze["seeds"], freeze["primary"]) == report["summary"], "summary mismatch")
    for row in ledger:
        bundle = load_bundle(root, row)
        expected_job = {"stage": stage, "name": row["name"], "seed": row["seed"],
                        "spec": freeze["configs"][row["name"]], "options": freeze["options"]}
        require(bundle["job"] == expected_job, "job differs from frozen experiment")
    if stage == "confirmation":
        selection = json.loads((root / "selection.json").read_text())
        dev = json.loads((root / "development/report.json").read_text())
        selected = choose(dev["summary"])
        require(all(selection[key] == value for key, value in selected.items()), "selection rule mismatch")
        require(selection["source"] == pins(), "selection source mismatch")
        require(selection["development_report_sha256"] == digest(root / "development/report.json"), "development hash mismatch")
        require(selection["configs"] == freeze["configs"] and selection["primary"] == freeze["primary"], "confirmation selection mismatch")
    with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context("spawn")) as pool:
        checks = list(pool.map(audit_one, [(str(root), row) for row in ledger]))
    controllers = []
    for name in full:
        row = next(r for r in ledger if r["name"] == name and r["seed"] == freeze["seeds"][0])
        original = load_bundle(root, row)
        repeated = normal(collect(original["job"]))
        for key in ("replay", "beliefs", "predictions", "calls", "invalid", "error", "metrics"):
            require(repeated[key] == original[key], "controller repeat differs: " + key)
        controllers.append({"name": name, "seed": row["seed"], "identical": True})
    result = {"stage": stage, "verified_utc": utc(), "source": pins(),
              "report_sha256": digest(root / stage / "report.json"), "physics_missions": len(checks),
              "commands": sum(c["commands"] for c in checks), "states": sum(c["states"] for c in checks),
              "diagnostic_beliefs": sum(c["beliefs"] for c in checks), "full_controller_repeats": controllers,
              "matrix_statistics_selection": "verified", "seconds": time.perf_counter() - started,
              "checks": checks, "ok": True}
    write_json(root / stage / "audit.json", result)
    print(json.dumps({k: v for k, v in result.items() if k not in ("source", "checks")}, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["smoke", "development", "confirmation"])
    parser.add_argument("--out", type=Path, default=OUTPUT)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--full", default="", help="comma-separated configurations to fully repeat on this stage's first world")
    args = parser.parse_args()
    audit(args.out, args.stage, args.workers, [name for name in args.full.split(",") if name])


if __name__ == "__main__":
    main()
