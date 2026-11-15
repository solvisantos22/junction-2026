import gzip
import json
import os
from pathlib import Path
import random
import statistics
import time
from functools import lru_cache

from lightlag_planner_lab.policy import PROFILE_NAMES
from lightlag_planner_lab.worker import canonical, digest, file_hash, source_manifest

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/"docs/planner-lab-results"
TRAIN = list(range(570000, 570384))
VALIDATION = list(range(571000, 571064))
FRESH = list(range(572000, 572192))


def require(ok, message):
    if not ok: raise ValueError(message)


def utc(): return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def write(path, value, exclusive=False):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    if exclusive and path.exists(): raise FileExistsError(path)
    tmp = path.with_name(path.name+".tmp")
    tmp.write_bytes(canonical(value)+b"\n"); tmp.replace(path)


def orchestration():
    paths = sorted((ROOT/"tools/planner_lab").glob("*.py"))+[ROOT/"tools/learned_portfolio/dns_run.py"]
    return {str(p.relative_to(ROOT)): file_hash(p) for p in paths}


def receipt(result, relative):
    rows = []; job = result["job"]
    for index, episode in enumerate(result["episodes"]):
        grade = episode["result"]
        rows.append({"seed": job["seed"], "split": job["split"], "name": episode["arm"]["name"],
            "arm": episode["arm"], "reward": episode["reward"], "alive": grade["alive"], "at_base": grade["at_base"],
            "samples": len(grade["samples"]), "late_samples": sum(not s["on_time"] for s in grade["samples"]),
            "error": episode["error"], "invalid": len(episode["invalid"]), "seconds": episode["seconds"],
            "cpu_seconds": episode["cpu_seconds"], "decision": episode["decision"],
            "legacy_decision": episode["legacy_decision"], "prefix_sha256": episode["prefix_sha256"],
            "replay_sha256": episode["replay_sha256"], "artifact": relative, "index": index})
    return {"job_id": job["id"], "artifact": relative, "sha256": file_hash(OUT/relative), "rows": rows,
            "wall_seconds": result["wall_seconds"], "cpu_seconds": result["cpu_seconds"],
            "modal_call_id": result.get("modal_call_id"), "modal_task_id": result.get("modal_task_id")}


def archive(result, stage):
    relative = stage+"/batches/"+result["job"]["id"]+".json.gz"; path = OUT/relative
    path.parent.mkdir(parents=True, exist_ok=True)
    require(not path.exists(), "existing batch artifact")
    tmp = path.with_name(path.name+".tmp")
    tmp.write_bytes(gzip.compress(canonical(result), mtime=0)); tmp.replace(path)
    item = receipt(result, relative)
    with (OUT/stage/"receipts.jsonl").open("ab") as handle:
        handle.write(canonical(item)+b"\n"); handle.flush(); os.fsync(handle.fileno())
    return item


def read_receipts(stage):
    path = OUT/stage/"receipts.jsonl"
    return [json.loads(s) for s in path.read_text().splitlines()] if path.exists() else []


def rows(stage): return [r for item in read_receipts(stage) for r in item["rows"]]


def read_batch(item):
    path = (OUT/item["artifact"]).resolve()
    require(path.is_relative_to(OUT.resolve()) and file_hash(path) == item["sha256"], "batch path/hash mismatch")
    return json.loads(gzip.decompress(path.read_bytes()))


def recover(stage, expected):
    """Archives are authoritative; rebuild metadata after an interrupted append."""
    ledger = OUT/stage/"receipts.jsonl"
    try:
        existing = read_receipts(stage)
        paths = {OUT/r["artifact"] for r in existing}
        require(len(paths) == len(existing), "duplicate receipt")
        if paths == set((OUT/stage/"batches").glob("*.json.gz")):
            for r in existing: read_batch(r)
            return existing
    except (ValueError, KeyError): pass
    recovered = []
    for path in sorted((OUT/stage/"batches").glob("*.json.gz")):
        result = json.loads(gzip.decompress(path.read_bytes())); job = result["job"]
        require(job == expected[job["id"]], "orphan job differs from freeze")
        require(result["source_sha256"] == digest(source_manifest()), "orphan source differs")
        recovered.append(receipt(result, str(path.relative_to(OUT))))
    if ledger.exists():
        backup = ledger.with_name("receipts-before-recovery-"+str(time.time_ns())+".jsonl")
        ledger.replace(backup)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_bytes(b"".join(canonical(r)+b"\n" for r in recovered))
    return recovered


def matrix(all_rows, seeds, split):
    by = {(r["seed"],r["name"]):r for r in all_rows if r["split"] == split and r["name"] in PROFILE_NAMES}
    require(set(by) == {(s,n) for s in seeds for n in PROFILE_NAMES}, "incomplete counterfactual matrix")
    x, y, home = [], [], []; names = None
    for seed in seeds:
        base = by[seed,"baseline"]; state = base["decision"]["features"]
        if names is None: names = sorted(state)
        for name in PROFILE_NAMES:
            r = by[seed,name]
            require(not r["error"] and not r["invalid"], "invalid controller result")
            require(r["decision"]["features"] == state and r["prefix_sha256"] == base["prefix_sha256"], "counterfactual prefix differs")
        x.append([state[n] for n in names])
        y.append([by[seed,n]["reward"]-base["reward"] for n in PROFILE_NAMES[1:]])
        home.append([int(by[seed,n]["alive"] and by[seed,n]["at_base"]) for n in PROFILE_NAMES[1:]])
    return {"seeds":seeds,"feature_names":names,"x":x,"y":y,"home_alive":home}, by


def stats(mine, base):
    require([r["seed"] for r in mine] == [r["seed"] for r in base], "unpaired rows")
    delta = [r["reward"]-b["reward"] for r,b in zip(mine,base)]
    return {"n":len(mine), "mean":statistics.mean(r["reward"] for r in mine), "delta":statistics.mean(delta),
            "home_alive":sum(r["alive"] and r["at_base"] for r in mine), "deaths":sum(not r["alive"] for r in mine),
            "errors":sum(bool(r["error"]) for r in mine), "invalid":sum(r["invalid"] for r in mine),
            "cpu_seconds":statistics.mean(r["cpu_seconds"] for r in mine),
            "higher":sum(d>1e-12 for d in delta), "equal":sum(abs(d)<=1e-12 for d in delta), "lower":sum(d< -1e-12 for d in delta)}


@lru_cache(maxsize=2)
def draws(n):
    import numpy as np
    rng = random.Random(572192)
    return np.asarray([[rng.randrange(n) for _ in range(n)] for _ in range(20000)])


def bootstrap(values, alpha=.05):
    import numpy as np
    means = np.sort(np.asarray(values)[draws(len(values))].mean(axis=1))
    return [float(means[int(alpha/2*len(means))]), float(means[min(len(means)-1, int((1-alpha/2)*len(means)))])]
