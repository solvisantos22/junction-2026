"""Launch pinned Modal data/fit/final stages and retain every result."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import pickle
import random
import statistics
import subprocess
import time

from lightlag_learned_portfolio.policy import PROFILE_NAMES, choose
from lightlag_learned_portfolio.worker import canonical, digest, source_manifest

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/learned-portfolio-results"
TRAIN = list(range(560000, 560192))
VALIDATION = list(range(561000, 561048))
CHECK = list(range(562000, 562096))
ALGORITHMS = ("extra_trees", "hist_boost", "ridge")


def require(ok, message):
    if not ok: raise ValueError(message)


def file_hash(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data, exclusive=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    if exclusive:
        with path.open("x") as f: json.dump(data, f, indent=2, sort_keys=True, allow_nan=False)
    else:
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n")
        temp.replace(path)


def utc(): return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def read_rows(stage):
    p = OUT / stage / "rows.jsonl"
    return [json.loads(line) for line in p.read_text().splitlines()] if p.exists() else []


def archive(result, stage):
    job = result["job"]
    relative = f'{stage}/episodes/{job["split"]}/{job["name"]}/{job["seed"]}.json.gz'
    path = OUT / relative
    require(not path.exists(), "existing mission artifact")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(canonical(result), mtime=0))
    grade = result["result"]
    row = {"name": job["name"], "split": job["split"], "seed": job["seed"],
           "reward": result["reward"], "alive": grade["alive"], "at_base": grade["at_base"],
           "samples": len(grade["samples"]), "late_samples": sum(not s["on_time"] for s in grade["samples"]),
           "decision": result["decision"], "prefix_sha256": result["prefix_sha256"],
           "seconds": result["seconds"], "cpu_seconds": result["cpu_seconds"],
           "error": result["error"], "invalid": len(result["invalid"]),
           "modal_call_id": result.get("modal_call_id"), "artifact": relative, "sha256": file_hash(path)}
    with (OUT / stage / "rows.jsonl").open("a") as f: f.write(json.dumps(row, allow_nan=False) + "\n")
    return row


def jobs_for(stage):
    if stage == "smoke":
        splits = {"smoke": [1]}
        specs = {name: {"kind": "fixed", "profile": name} for name in PROFILE_NAMES}
    elif stage == "data":
        splits = {"train": TRAIN, "validation": VALIDATION}
        specs = {name: {"kind": "fixed", "profile": name} for name in PROFILE_NAMES}
    else:
        selection = json.loads((OUT / "selection.json").read_text())
        require(selection["source"] == source_manifest(), "source changed since selection")
        for name, sha in selection["models"].items():
            require(file_hash(OUT / "models" / (name + ".pkl")) == sha, "model changed since selection")
        specs, splits = selection["specs"], {"final": CHECK}
    source = source_manifest()
    return [{"split": split, "seed": seed, "name": name, "spec": spec, "source": source,
             "quick": stage == "smoke", "keep_replay": stage != "data"}
            for split, seeds in splits.items() for seed in seeds for name, spec in specs.items()]


def collect(stage):
    import modal
    from .cloud import app, mission
    jobs = jobs_for(stage)
    expected = {"stage": stage, "source": source_manifest(),
                "jobs": [{k: v for k, v in j.items() if k != "source"} for j in jobs],
                "resources": {"max_containers": 100, "cpu": 1, "memory_mib": 1024, "timeout": 600, "retries": 0}}
    freeze = OUT / stage / "freeze.json"
    if freeze.exists():
        old = json.loads(freeze.read_text())
        require(all(old[k] == v for k, v in expected.items()), "stage freeze mismatch")
    else:
        write(freeze, {**expected, "created_utc": utc(), "commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()}, exclusive=True)
    rows = read_rows(stage)
    done = {(r["split"], r["seed"], r["name"]) for r in rows}
    require(len(done) == len(rows), "duplicate ledger rows")
    todo = [j for j in jobs if (j["split"], j["seed"], j["name"]) not in done]
    for row in rows: require(file_hash(OUT / row["artifact"]) == row["sha256"], "resume artifact mismatch")
    if not todo:
        print("Stage already complete; retained original report.", flush=True)
        return
    start = time.perf_counter()
    print(f"{stage}: {len(todo)} jobs, up to 100 parallel containers", flush=True)
    with modal.enable_output(), app.run():
        write(OUT / stage / "app.json", {"app_id": app.app_id, "started_utc": utc(), "jobs": len(todo)})
        for index, result in enumerate(mission.map(todo, order_outputs=True, return_exceptions=True)):
            job = todo[index]  # Exhaust the remote iterator so the SDK can close its stream cleanly.
            if isinstance(result, BaseException):
                write(OUT / stage / ("failure-" + str(job["seed"]) + "-" + job["name"] + ".json"),
                      {"job": {k:v for k,v in job.items() if k != "source"}, "error": repr(result), "time": utc()})
                raise RuntimeError("Modal job failed; original failure retained: " + repr(result))
            require(result["job"] == {k:v for k,v in job.items() if k != "source"}, "job mismatch")
            row = archive(result, stage); rows.append(row)
            if len(rows) % 12 == 0 or len(rows) == len(jobs):
                write(OUT / stage / "progress.json", {"completed": len(rows), "expected": len(jobs),
                      "updated_utc": utc(), "elapsed_invocation": time.perf_counter()-start,
                      "errors": sum(bool(r["error"]) for r in rows)})
                print(f'{len(rows)}/{len(jobs)} {job["split"]} seed={job["seed"]}', flush=True)
    require(source_manifest() == expected["source"], "source changed during stage")
    require(len(rows) == len(jobs), "incomplete matrix")
    write(OUT / stage / "report.json", {"stage": stage, "source": expected["source"], "rows": rows,
              "completed_utc": utc(), "elapsed_invocation": time.perf_counter()-start,
              "mission_cpu_seconds": sum(r["cpu_seconds"] for r in rows),
              "mission_wall_seconds": sum(r["seconds"] for r in rows)})


def matrix(rows, seeds, split):
    by = {(r["seed"], r["name"]): r for r in rows if r["split"] == split}
    require(set(by) == {(s, n) for s in seeds for n in PROFILE_NAMES}, "incomplete matrix")
    x, y, names = [], [], None
    for seed in seeds:
        base = by[seed, "baseline"]
        require(base["decision"] is not None, "missing decision")
        f = base["decision"]["features"]
        if names is None: names = sorted(f)
        for name in PROFILE_NAMES:
            r = by[seed, name]
            require(not r["error"] and not r["invalid"], "invalid training/validation trajectory")
            require(r["prefix_sha256"] == base["prefix_sha256"], "strategy prefixes differ")
            require(r["decision"]["features"] == f, "strategy features differ before switching")
        x.append([f[n] for n in names])
        y.append([by[seed,n]["reward"]-base["reward"] for n in PROFILE_NAMES[1:]])
    return {"feature_names": names, "x": x, "y": y, "seeds": seeds}, by


def bootstrap(values, alpha=.05):
    rng = random.Random(562096); n = len(values)
    means = sorted(sum(values[rng.randrange(n)] for _ in range(n))/n for _ in range(20000))
    return [means[int(alpha/2*len(means))], means[min(len(means)-1,int((1-alpha/2)*len(means)))]]


def stats(rows, baseline):
    require([r["seed"] for r in rows] == [r["seed"] for r in baseline], "unpaired comparison")
    differences = [r["reward"]-b["reward"] for r,b in zip(rows,baseline)]
    return {"n":len(rows), "mean":statistics.mean(r["reward"] for r in rows),
            "delta":statistics.mean(differences), "home_alive":sum(r["alive"] and r["at_base"] for r in rows),
            "deaths":sum(not r["alive"] for r in rows), "errors":sum(bool(r["error"]) for r in rows),
            "invalid":sum(r["invalid"] for r in rows), "cpu_seconds":statistics.mean(r["cpu_seconds"] for r in rows),
            "higher":sum(d>1e-12 for d in differences), "equal":sum(abs(d)<=1e-12 for d in differences),
            "lower":sum(d< -1e-12 for d in differences)}


def fit_and_select():
    import modal
    from .cloud import app, train
    from lightlag_learned_portfolio.worker import load_model
    rows = read_rows("data")
    report = json.loads((OUT/"data/report.json").read_text())
    require(report["source"] == source_manifest(), "training source changed")
    training, _ = matrix(rows, TRAIN, "train")
    _, validation = matrix(rows, VALIDATION, "validation")
    write(OUT/"training-data.json", training, exclusive=True)
    with modal.enable_output(), app.run():
        calls = {name:train.spawn(name, training) for name in ALGORITHMS}
        write(OUT/"fit-receipt.json", {"app_id":app.app_id,"calls":{n:c.object_id for n,c in calls.items()},"created_utc":utc()}, exclusive=True)
        for name, call in calls.items():
            result = call.get()
            weights = result.pop("weights")
            p=OUT/"models"/(name+".pkl");p.parent.mkdir(parents=True,exist_ok=True)
            require(not p.exists(),"checkpoint already exists");p.write_bytes(weights)
            require(file_hash(p)==result["sha256"],"checkpoint transfer hash")
            write(OUT/"models"/(name+".json"),result,exclusive=True)
    base = [validation[s,"baseline"] for s in VALIDATION]
    base_stats = stats(base,base)
    models, candidates = {}, []
    for algorithm in ALGORITHMS:
        path=OUT/"models"/(algorithm+".pkl");sha=file_hash(path);models[algorithm]=sha
        model=load_model(path,sha)
        for threshold in (0.,.002,.005):
            selected, decisions = [], []
            for seed in VALIDATION:
                state=validation[seed,"baseline"]["decision"]["features"]
                name,prediction=choose(model,state,threshold)
                selected.append(validation[seed,name]);decisions.append({"seed":seed,"profile":name,"predictions":prediction})
            measured=stats(selected,base)
            eligible=(measured["home_alive"]>=base_stats["home_alive"] and measured["deaths"]<=base_stats["deaths"]
                      and not measured["errors"] and not measured["invalid"])
            candidates.append({"algorithm":algorithm,"threshold":threshold,"stats":measured,"eligible":eligible,
                               "decisions":decisions,"spec":{"kind":"learned","algorithm":algorithm,"threshold":threshold,"model_sha256":sha}})
    ranked=sorted(candidates,key=lambda c:(not c["eligible"],-c["stats"]["delta"],c["algorithm"],-c["threshold"]))
    winners=[]
    for c in ranked:
        if c["algorithm"] not in [w["algorithm"] for w in winners]: winners.append(c)
        if len(winners)==2:break
    static={name:stats([validation[s,name] for s in VALIDATION],base) for name in PROFILE_NAMES}
    best_static=max(PROFILE_NAMES,key=lambda n:(static[n]["mean"],-PROFILE_NAMES.index(n)))
    specs={"baseline":{"kind":"fixed","profile":"baseline"},"static_best":{"kind":"fixed","profile":best_static},
           **{w["algorithm"]:w["spec"] for w in winners}}
    selection={"source":source_manifest(),"created_utc":utc(),"models":models,"primary":winners[0]["algorithm"],
               "primary_validation_eligible":winners[0]["eligible"],"specs":specs,"fresh_seeds":CHECK,
               "data_report_sha256":file_hash(OUT/"data/report.json"),"training_data_sha256":file_hash(OUT/"training-data.json"),
               "validation_candidates":candidates,"static_comparisons":static,"best_static":best_static}
    write(OUT/"selection.json",selection,exclusive=True)
    print(json.dumps({"primary":selection["primary"],"specs":specs,"static":best_static,
                      "validation":[{"algorithm":w["algorithm"],"threshold":w["threshold"],"stats":w["stats"]} for w in winners]},indent=2))


def final_summary():
    selection=json.loads((OUT/"selection.json").read_text());rows=read_rows("final")
    by={(r["name"],r["seed"]):r for r in rows}
    require(set(by)=={(n,s) for n in selection["specs"] for s in CHECK},"incomplete final matrix")
    base=[by["baseline",s] for s in CHECK];table={}
    for name in selection["specs"]:
        mine=[by[name,s] for s in CHECK];r=stats(mine,base)
        differences=[a["reward"]-b["reward"] for a,b in zip(mine,base)]
        r["ci95"]=bootstrap(differences);r["ci_family95"]=bootstrap(differences,.05/3)
        table[name]=r
    p,b=table[selection["primary"]],table["baseline"]
    gate={"mean_gain":p["delta"]>=.01,"positive_interval":p["ci95"][0]>0,
          "home":p["home_alive"]>=b["home_alive"],"deaths":p["deaths"]<=b["deaths"],"valid":not p["errors"] and not p["invalid"]}
    result={"table":table,"primary":selection["primary"],"gate":gate,"confirmed":all(gate.values())}
    write(OUT/"final/summary.json",result);print(json.dumps(result,indent=2))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage",choices=["smoke","data","fit","final","summary"])
    args=parser.parse_args()
    if args.stage=="fit":fit_and_select()
    elif args.stage=="summary":final_summary()
    else:collect(args.stage)


if __name__=="__main__":main()
