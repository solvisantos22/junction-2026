"""Pinned, resumable paired reference sweep. Standard library only.

python3 -m tools.reference_ablation.run development --workers 6
python3 -m tools.reference_ablation.run select
python3 -m tools.reference_ablation.run confirmation --workers 6
"""

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
import gzip
import hashlib
import json
import math
import multiprocessing
from pathlib import Path
import platform
import random
import statistics
import subprocess
import time
import traceback

from lightlag_traverse.environment import TraverseEnvironment
from lightlag_traverse_max.heldout import check_training_seeds
from .variants import VARIANTS, combine, fly

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "docs/reference-ablation-results"
DEVELOPMENT = list(range(450000, 450012))
CONFIRMATION = list(range(451000, 451032))
SMOKE_OPTIONS = {"plan_steps": 12000, "replan_steps": 2000, "beam": 60, "rebeam": 20}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def normal(value):
    return json.loads(json.dumps(value, allow_nan=False))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pins():
    files = [ROOT / "docs/reference-ablation.md", ROOT / "lightlag_traverse_max/heldout.py"]
    for folder in ("tools/reference_ablation", "lightlag_traverse"):
        files += sorted((ROOT / folder).glob("*.py"))
    return {str(p.relative_to(ROOT)): digest(p) for p in sorted(files)}


def write_json(path, value, exclusive=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    if exclusive:
        with path.open("x") as stream:
            json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
    else:
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")
        temp.replace(path)


def utc():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def metrics(replay, beliefs, predictions):
    result = replay["result"]
    states = {s["tick"]: s for s in replay["states"]}
    def error(row, offset=0):
        x, y = states[row["tick"] + offset]["position"]
        return math.hypot(row["x"] - x, row["y"] - y)
    errors = [error(row) for row in beliefs]
    future_errors = [error(row, -1) for row in predictions if row["tick"] - 1 in states]
    events = Counter(e["type"] for s in states.values() for e in s["events"])
    commands = Counter(c["command"]["action"] for c in replay["commands"])
    return {
        "reward": result["raw_score"] / result["max_available_value"],
        "science": result["sampled_value"] / result["max_available_value"],
        "alive": result["alive"], "at_base": result["at_base"],
        "samples": len(result["samples"]), "late_samples": sum(not s["on_time"] for s in result["samples"]),
        "pose_rmse": math.sqrt(statistics.mean(e * e for e in errors)) if errors else None,
        "pose_p95": sorted(errors)[int(.95 * (len(errors) - 1))] if errors else None,
        "prediction_rmse": math.sqrt(statistics.mean(e * e for e in future_errors)) if future_errors else None,
        "minimum_battery": min(s["battery"] for s in states.values()),
        "safety_stops": events["safety_stop"], "failed_samples": events["sample_failed"],
        "commands": dict(commands), "belief_count": len(beliefs), "prediction_count": len(predictions),
    }


def collect(job):
    """Only the closure-backed five public methods are passed to the controller."""
    env = TraverseEnvironment(job["seed"])
    calls, invalid = Counter(), []
    def call(name, *args):
        calls[name] += 1
        try:
            return getattr(env, name)(*args)
        except ValueError as error:
            invalid.append({"method": name, "error": str(error)})
            raise
    class Tools:
        def rules(self): return call("rules")
        def map(self): return call("map")
        def telemetry_log(self): return call("telemetry_log")
        def uplink(self, commands): return call("uplink", commands)
        def advance(self, ticks=1): return call("advance", ticks)
        def __getattr__(self, name): raise AssertionError("non-public tool: " + name)
    wall, cpu = time.perf_counter(), time.process_time()
    failure, pilot = None, None
    try:
        pilot = fly(Tools(), job["spec"], job.get("options"))
    except Exception:
        failure = traceback.format_exc()
    elapsed, cpu_seconds = time.perf_counter() - wall, time.process_time() - cpu
    while not env.advance(1)["episode_complete"]:
        pass
    replay = env.replay()
    beliefs = pilot.beliefs if pilot else []
    predictions = pilot.predictions if pilot else []
    return {"job": job, "replay": replay, "beliefs": beliefs, "predictions": predictions,
            "calls": dict(calls), "invalid": invalid, "error": failure,
            "wall_seconds": elapsed, "cpu_seconds": cpu_seconds,
            "metrics": metrics(replay, beliefs, predictions)}


def load_bundle(root, row):
    path = (root / row["artifact"]).resolve()
    require(path.is_relative_to(root.resolve()), "artifact outside output directory")
    require(digest(path) == row["sha256"], "artifact hash mismatch")
    return json.loads(gzip.decompress(path.read_bytes()))


def save_bundle(root, bundle):
    job = bundle["job"]
    relative = f'{job["stage"]}/episodes/{job["name"]}/{job["seed"]}.json.gz'
    path = root / relative
    require(not path.exists(), "refusing to overwrite a mission")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(json.dumps(bundle, allow_nan=False, separators=(",", ":")).encode(), mtime=0))
    return {"name": job["name"], "seed": job["seed"], "artifact": relative, "sha256": digest(path),
            **bundle["metrics"], "cpu_seconds": bundle["cpu_seconds"], "wall_seconds": bundle["wall_seconds"],
            "invalid_calls": len(bundle["invalid"]), "error": bundle["error"]}


def bootstrap(differences, alpha=.05):
    rng = random.Random(450011)
    n = len(differences)
    means = sorted(sum(differences[rng.randrange(n)] for _ in range(n)) / n for _ in range(20000))
    return [means[int(alpha / 2 * len(means))], means[min(len(means) - 1, int((1 - alpha / 2) * len(means)))]]


def summarize(rows, configs, seeds, primary=None):
    require(len(rows) == len(configs) * len(seeds), "incomplete result matrix")
    by = {(r["name"], r["seed"]): r for r in rows}
    require(len(by) == len(rows), "duplicate result")
    require(set(by) == {(name, seed) for name in configs for seed in seeds}, "unexpected matrix cells")
    table = {}
    count = max(1, len(configs) - 1)
    base = [by[("baseline", seed)] for seed in seeds]
    for name in configs:
        mine = [by[(name, seed)] for seed in seeds]
        entry = {"n": len(mine), "home_alive": sum(r["alive"] and r["at_base"] for r in mine),
                 "deaths": sum(not r["alive"] for r in mine),
                 "invalid_calls": sum(r["invalid_calls"] for r in mine),
                 "errors": sum(bool(r["error"]) for r in mine)}
        for field in ("reward", "science", "samples", "late_samples", "pose_rmse", "pose_p95",
                      "prediction_rmse", "minimum_battery", "safety_stops", "failed_samples",
                      "cpu_seconds", "wall_seconds"):
            values = [r[field] for r in mine if r[field] is not None]
            entry[field] = statistics.mean(values) if values else None
        if name != "baseline":
            differences = [r["reward"] - b["reward"] for r, b in zip(mine, base)]
            entry.update(delta=statistics.mean(differences), ci95=bootstrap(differences),
                         ci_family95=bootstrap(differences, .05 / count),
                         higher=sum(d > 1e-12 for d in differences), lower=sum(d < -1e-12 for d in differences),
                         equal=sum(abs(d) <= 1e-12 for d in differences),
                         cpu_ratio=entry["cpu_seconds"] / statistics.mean(r["cpu_seconds"] for r in base),
                         home_gained=sum(r["alive"] and r["at_base"] and not (b["alive"] and b["at_base"])
                                         for r, b in zip(mine, base)),
                         home_lost=sum(b["alive"] and b["at_base"] and not (r["alive"] and r["at_base"])
                                       for r, b in zip(mine, base)))
        table[name] = entry
    result = {"table": table, "primary": primary}
    if primary:
        p, b = table[primary], table["baseline"]
        result["primary_gate"] = {
            "gain_at_least_001": p["delta"] >= .01, "positive_interval": p["ci95"][0] > 0,
            "home_not_worse": p["home_alive"] >= b["home_alive"], "deaths_not_worse": p["deaths"] <= b["deaths"],
            "valid": not p["invalid_calls"] and not p["errors"], "runtime": p["cpu_ratio"] <= 1.75}
        result["confirmed_gain"] = all(result["primary_gate"].values())
    return result


def choose(summary):
    table = summary["table"]
    b = table["baseline"]
    eligible = [name for name, r in table.items() if name != "baseline" and r["delta"] > 0
                and r["home_alive"] >= b["home_alive"] and r["deaths"] <= b["deaths"]
                and r["cpu_ratio"] <= 1.75 and not r["invalid_calls"] and not r["errors"]]
    eligible.sort(key=lambda name: (-table[name]["delta"], name))
    distinct, seen = [], set()
    for name in eligible:
        component = VARIANTS[name]["component"]
        if component not in seen:
            distinct.append(name)
            seen.add(component)
    selected = distinct[:2]
    configs = {"baseline": VARIANTS["baseline"], **{n: VARIANTS[n] for n in selected}}
    primary = selected[0] if selected else None
    if len(distinct) >= 2:
        configs["combined"] = combine(distinct[:3])
        primary = "combined"
    return {"eligible": eligible, "distinct_ranked": distinct, "configs": configs, "primary": primary}


def select(root):
    frozen = json.loads((root / "development/freeze.json").read_text())
    require(frozen["source"] == pins(), "source changed since development")
    report = json.loads((root / "development/report.json").read_text())
    selection = {**choose(report["summary"]), "created_utc": utc(), "source": pins(),
                 "development_report_sha256": digest(root / "development/report.json"),
                 "confirmation_seeds": CONFIRMATION}
    write_json(root / "selection.json", selection, exclusive=True)
    print(json.dumps(selection, indent=2), flush=True)


def run_stage(root, stage, workers=6):
    require(workers >= 1, "workers must be positive")
    primary = None
    if stage == "smoke":
        configs = VARIANTS
        seeds = [1]
    elif stage == "development":
        configs, seeds = VARIANTS, DEVELOPMENT
    else:
        selection = json.loads((root / "selection.json").read_text())
        require(selection["source"] == pins(), "source changed after candidate selection")
        require(selection["development_report_sha256"] == digest(root / "development/report.json"), "development changed")
        require(selection["primary"] is not None, "no eligible candidate; no confirmation required")
        require(selection["confirmation_seeds"] == CONFIRMATION, "confirmation seeds changed")
        configs, seeds, primary = selection["configs"], CONFIRMATION, selection["primary"]
    check_training_seeds(seeds)
    source = pins()
    freeze_path = root / stage / "freeze.json"
    expected = {"stage": stage, "seeds": seeds, "configs": configs, "source": source,
                "options": SMOKE_OPTIONS if stage == "smoke" else {}, "primary": primary}
    if freeze_path.exists():
        old = json.loads(freeze_path.read_text())
        require(all(old[k] == v for k, v in expected.items()), "freeze mismatch; use original source")
    else:
        write_json(freeze_path, {**expected, "created_utc": utc(), "python": platform.python_version(),
                   "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                   "workers": workers, "cloud_jobs": 0, "model_api_calls": 0}, exclusive=True)
    ledger = root / stage / "rows.jsonl"
    rows = [json.loads(line) for line in ledger.read_text().splitlines()] if ledger.exists() else []
    done = {(r["name"], r["seed"]) for r in rows}
    require(len(done) == len(rows), "duplicate ledger rows")
    for row in rows:
        bundle = load_bundle(root, row)
        require(bundle["job"]["spec"] == configs[row["name"]], "resume configuration mismatch")
    jobs = [{"stage": stage, "name": name, "seed": seed, "spec": spec, "options": expected["options"]}
            for seed in seeds for name, spec in configs.items() if (name, seed) not in done]
    started = time.perf_counter()
    print(f"{stage}: {len(jobs)} missions remaining, {workers} workers", flush=True)
    with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context("spawn")) as pool:
        futures = {pool.submit(collect, job): job for job in jobs}
        for future in as_completed(futures):
            bundle = future.result()
            row = save_bundle(root, bundle)
            with ledger.open("a") as stream:
                stream.write(json.dumps(row, allow_nan=False, separators=(",", ":")) + "\n")
            rows.append(row)
            write_json(root / stage / "progress.json", {"completed": len(rows), "expected": len(configs) * len(seeds),
                       "updated_utc": utc(), "elapsed_this_invocation": time.perf_counter() - started,
                       "errors": sum(bool(r["error"]) for r in rows)})
            print(f'{len(rows)}/{len(configs)*len(seeds)} {row["name"]} {row["seed"]} '
                  f'score={row["reward"]:.4f} home={row["alive"] and row["at_base"]} '
                  f'cpu={row["cpu_seconds"]:.1f}s error={bool(row["error"])}', flush=True)
    require(pins() == source, "source changed during run")
    report = {"stage": stage, "rows": sorted(rows, key=lambda r: (r["seed"], r["name"])),
              "summary": summarize(rows, configs, seeds, primary), "completed_utc": utc(),
              "elapsed_this_invocation": time.perf_counter() - started,
              "source": source}
    write_json(root / stage / "report.json", report)
    print(json.dumps(report["summary"], indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["smoke", "development", "select", "confirmation"])
    parser.add_argument("--out", type=Path, default=OUTPUT)
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    if args.stage == "select":
        select(args.out)
    else:
        run_stage(args.out, args.stage, args.workers)


if __name__ == "__main__":
    main()
