"""Execute frozen, resumable Modal experiments and publish their selection."""

import argparse
import json
import subprocess
import time

from lightlag_planner_lab.model import ALGORITHMS, settings
from lightlag_planner_lab.policy import PROFILE_NAMES
from lightlag_planner_lab.worker import LEGACY_SHA, digest, file_hash, load_model, source_manifest
from .common import (ROOT, OUT, TRAIN, VALIDATION, FRESH, archive, bootstrap, canonical, matrix,
                     orchestration, read_batch, read_receipts, receipt, recover, require, rows, stats, utc, write)


def fixed(name): return {"name":name, "spec":{"kind":"fixed", "profile":name}}
def legacy(): return {"name":"old_extra_trees", "spec":{"kind":"legacy", "model_sha256":LEGACY_SHA}}


def jobs_for(stage):
    jobs = []; source = source_manifest()
    if stage == "final":
        selection = json.loads((OUT/"selection.json").read_text())
        require(selection["source"] == source, "source changed after model selection")
        for name, sha in selection["models"].items():
            require(file_hash(OUT/"models"/(name+".pkl")) == sha, "checkpoint changed after selection")
        for seed in FRESH:
            jobs.append({"id":f"final-{seed}", "split":"final", "seed":seed, "arms":selection["arms"]})
    else:
        splits = {"smoke":[1,2]} if stage == "smoke" else {"train":TRAIN, "validation":VALIDATION}
        for split, seeds in splits.items():
            for seed in seeds:
                for g in range(0, len(PROFILE_NAMES), 4):
                    jobs.append({"id":f"{split}-{seed}-g{g//4}", "split":split, "seed":seed,
                                 "arms":[fixed(n) for n in PROFILE_NAMES[g:g+4]]})
                if split != "train":
                    jobs.append({"id":f"{split}-{seed}-legacy", "split":split, "seed":seed, "arms":[legacy()]})
    return [{**j, "source":source, "quick":stage == "smoke", "keep_replay":stage != "data"} for j in jobs]


def collect(stage, tag):
    import modal
    from .cloud import app, batch
    jobs = jobs_for(stage); directory = OUT/tag
    clean = [{k:v for k,v in j.items() if k != "source"} for j in jobs]
    expected = {j["id"]:j for j in clean}
    freeze = {"stage":stage, "source":source_manifest(), "jobs":clean,
              "resources":{"cpu":1,"memory_mib":1536,"max_containers":100,"timeout":900,"retries":0}}
    path = directory/"freeze.json"
    if path.exists():
        saved = json.loads(path.read_text()); require(all(saved[k] == v for k,v in freeze.items()), "stage freeze changed")
    else:
        write(path, {**freeze, "created_utc":utc(), "commit":subprocess.check_output(
            ["git","rev-parse","HEAD"], cwd=ROOT, text=True).strip()}, exclusive=True)
    completed = recover(tag, expected)
    for item in completed:
        saved = read_batch(item)
        require(saved["job"] == expected[item["job_id"]] and saved["source_sha256"] == digest(freeze["source"]), "resume provenance mismatch")
        require(item["rows"] == receipt(saved, item["artifact"])["rows"], "resume row mismatch")
    done = {r["job_id"] for r in completed}; todo = [j for j in jobs if j["id"] not in done]
    if not todo:
        print("Stage already complete; original outcomes and report retained.", flush=True); return
    attempt = directory/"attempts"/f"{len(list((directory/'attempts').glob('*')))+1:02d}"
    attempt.mkdir(parents=True, exist_ok=False)
    write(attempt/"launch.json", {"created_utc":utc(), "pending_batches":len(todo), "orchestration":orchestration(),
                                  "frozen_source_sha256":digest(freeze["source"])})
    started = time.perf_counter(); failures = []
    print(f"{tag}: {len(todo)} batches, {sum(len(j['arms']) for j in todo)} missions, up to 100 workers", flush=True)
    try:
        with modal.enable_output(), app.run():
            write(attempt/"app.json", {"app_id":app.app_id,"started_utc":utc(),"pending_batches":len(todo)})
            for result in batch.map(todo, order_outputs=False, return_exceptions=True):
                if isinstance(result, BaseException):
                    failures.append({"error":repr(result),"created_utc":utc()})
                    write(attempt/"returned-errors.json", failures)
                    continue
                job_id = result["job"]["id"]
                require(job_id not in done and result["job"] == expected[job_id], "unexpected or duplicate batch")
                require(result["source_sha256"] == digest(freeze["source"]), "remote source mismatch")
                item = archive(result, tag); completed.append(item); done.add(job_id)
                count = sum(len(r["rows"]) for r in completed)
                write(directory/"progress.json", {"completed_batches":len(done),"expected_batches":len(jobs),
                    "completed_missions":count,"expected_missions":sum(len(j["arms"]) for j in jobs),
                    "updated_utc":utc(),"errors":sum(bool(row["error"]) for item in completed for row in item["rows"])})
                print(f"{count}/{sum(len(j['arms']) for j in jobs)} missions; {job_id}", flush=True)
    except BaseException as error:
        write(attempt/"interruption.json", {"created_utc":utc(),"error":repr(error),"archived_batches":len(done),
              "missing_batches":sorted(set(expected)-done),"orchestration":orchestration()})
        raise
    require(source_manifest() == freeze["source"], "runtime changed during collection")
    missing = sorted(set(expected)-done)
    if missing:
        write(attempt/"incomplete.json", {"created_utc":utc(),"missing_batches":missing,"errors":failures})
        raise RuntimeError("Incomplete infrastructure batch; retained successes, resume only missing batches")
    write(attempt/"completion.json", {"completed_utc":utc(),"elapsed_seconds":time.perf_counter()-started,
                                      "returned_errors":failures})
    write(directory/"report.json", {"stage":stage,"source":freeze["source"],"completed_utc":utc(),
        "batches":len(completed),"missions":sum(len(r["rows"]) for r in completed),
        "receipts_sha256":file_hash(directory/"receipts.jsonl"),
        "batch_wall_seconds":sum(r["wall_seconds"] for r in completed),
        "batch_cpu_seconds":sum(r["cpu_seconds"] for r in completed),
        "rows":[row for item in completed for row in item["rows"]]})


def fit_and_select():
    import modal
    import numpy as np
    from .cloud import app, train
    report = json.loads((OUT/"data/report.json").read_text())
    require(report["source"] == source_manifest(), "source changed since data collection")
    require(report["receipts_sha256"] == file_hash(OUT/"data/receipts.jsonl"), "data receipts changed")
    for item in read_receipts("data"):
        result = read_batch(item)
        require(receipt(result,item["artifact"])["rows"] == item["rows"], "data ledger mismatch")
    all_rows = rows("data"); training,_ = matrix(all_rows, TRAIN, "train"); validation,by = matrix(all_rows, VALIDATION, "validation")
    write(OUT/"training-data.json", training, exclusive=True)
    with modal.enable_output(), app.run():
        calls = {name:train.spawn(name, training) for name in ALGORITHMS}
        write(OUT/"fit-receipt.json", {"app_id":app.app_id,"created_utc":utc(),"source":source_manifest(),
            "training_data_sha256":file_hash(OUT/"training-data.json"),"calls":{n:c.object_id for n,c in calls.items()},
            "orchestration":orchestration()}, exclusive=True)
        for name, call in calls.items():
            result = call.get(); weights = result.pop("weights")
            require(result["source_sha256"] == digest(source_manifest()) and result["training_data_sha256"] == digest(training),
                    "remote fitting provenance mismatch")
            path = OUT/"models"/(name+".pkl"); path.parent.mkdir(parents=True,exist_ok=True)
            with path.open("xb") as handle: handle.write(weights)
            require(file_hash(path) == result["sha256"], "model transfer hash mismatch")
            write(OUT/"models"/(name+".json"), result, exclusive=True)
    baseline = [by[s,"baseline"] for s in VALIDATION]; base_stats = stats(baseline,baseline)
    old_by = {r["seed"]:r for r in all_rows if r["split"] == "validation" and r["name"] == "old_extra_trees"}
    require(set(old_by) == set(VALIDATION), "missing matched old-policy validation")
    old_stats = stats([old_by[s] for s in VALIDATION], baseline)
    models, candidates = {}, []
    for algorithm in ALGORITHMS:
        path = OUT/"models"/(algorithm+".pkl"); sha = file_hash(path); models[algorithm] = sha
        model = load_model(path,sha); means,spread,failures = model.predict(validation["x"])
        require(np.isfinite(means).all() and np.isfinite(spread).all() and np.isfinite(failures).all(), "nonfinite predictions")
        for setting in settings(algorithm):
            utility = means-setting["disagreement"]*spread-setting["risk_penalty"]*failures
            choices, picked = [], []
            for i, seed in enumerate(VALIDATION):
                index = int(np.argmax(utility[i])); name = PROFILE_NAMES[index+1] if utility[i,index] > setting["threshold"] else "baseline"
                picked.append(by[seed,name]); choices.append({"seed":seed,"profile":name})
            measured = stats(picked, baseline)
            eligible = (measured["home_alive"] >= base_stats["home_alive"] and measured["deaths"] <= base_stats["deaths"]
                        and not measured["errors"] and not measured["invalid"])
            candidates.append({"algorithm":algorithm,"setting":setting,"stats":measured,"eligible":eligible,"choices":choices,
                "spec":{"kind":"learned","algorithm":algorithm,"setting":setting,"model_sha256":sha}})
    ranked = sorted(candidates,key=lambda c:(not c["eligible"],-c["stats"]["delta"],c["algorithm"],
                    -c["setting"]["threshold"],-c["setting"]["disagreement"],-c["setting"]["risk_penalty"]))
    winners = []
    for candidate in ranked:
        if candidate["algorithm"] not in [w["algorithm"] for w in winners]: winners.append(candidate)
        if len(winners) == 2: break
    fixed_table = {n:stats([by[s,n] for s in VALIDATION],baseline) for n in PROFILE_NAMES}
    best = max(PROFILE_NAMES,key=lambda n:(fixed_table[n]["mean"],-PROFILE_NAMES.index(n)))
    arms = [{"name":"reference","spec":{"kind":"fixed","profile":"baseline"}}, legacy(),
            {"name":"static_best","spec":{"kind":"fixed","profile":best}}]
    arms += [{"name":"learned_"+w["algorithm"],"spec":w["spec"]} for w in winners]
    selection = {"created_utc":utc(),"source":source_manifest(),"models":models,"arms":arms,
        "primary":"learned_"+winners[0]["algorithm"],"primary_eligible":winners[0]["eligible"],
        "fresh_seeds":FRESH,"best_static":best,"validation_candidates":candidates,
        "fixed_validation":fixed_table,"old_policy_validation":old_stats,
        "data_report_sha256":file_hash(OUT/"data/report.json"),"training_data_sha256":file_hash(OUT/"training-data.json")}
    write(OUT/"selection.json", selection, exclusive=True)
    print(json.dumps({"primary":selection["primary"],"arms":arms,"best_static":fixed_table[best],
                      "reference":base_stats,"old_policy":old_stats,"selected":[{k:v for k,v in w.items() if k!='choices'} for w in winners]},indent=2))


def final_summary():
    selection = json.loads((OUT/"selection.json").read_text()); all_rows = rows("final")
    by = {(r["name"],r["seed"]):r for r in all_rows}; names = [a["name"] for a in selection["arms"]]
    require(len(by) == len(all_rows) and set(by) == {(n,s) for n in names for s in FRESH}, "incomplete fresh matrix")
    base = [by["reference",s] for s in FRESH]; old = [by["old_extra_trees",s] for s in FRESH]; table = {}
    for name in names:
        mine = [by[name,s] for s in FRESH]; measured = stats(mine,base)
        delta = [a["reward"]-b["reward"] for a,b in zip(mine,base)]
        vs_old = [a["reward"]-b["reward"] for a,b in zip(mine,old)]
        measured.update({"ci95":bootstrap(delta),"ci_family95":bootstrap(delta,.05/4),
                         "vs_old_delta":sum(vs_old)/len(vs_old),"vs_old_ci95":bootstrap(vs_old)})
        table[name] = measured
    p,b,o = table[selection["primary"]],table["reference"],table["old_extra_trees"]
    gate = {"validation_eligible":selection["primary_eligible"],"mean_gain":p["delta"] >= .01,
            "positive_interval":p["ci95"][0] > 0,"nonnegative_vs_old":p["vs_old_delta"] >= 0,
            "home":p["home_alive"] >= max(b["home_alive"],o["home_alive"]),
            "deaths":p["deaths"] <= min(b["deaths"],o["deaths"]),"valid":not p["errors"] and not p["invalid"]}
    result = {"primary":selection["primary"],"table":table,"gate":gate,"confirmed":all(gate.values())}
    write(OUT/"final/summary.json",result); print(json.dumps(result,indent=2))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("stage",choices=["smoke","data","fit","final","summary"])
    p.add_argument("--tag"); p.add_argument("--system-dns",action="store_true"); a=p.parse_args()
    if a.stage != "summary" and not a.system_dns:
        from tools.learned_portfolio.dns_run import install_resolver
        install_resolver()
    if a.stage == "fit": fit_and_select()
    elif a.stage == "summary": final_summary()
    else: collect(a.stage, a.tag or a.stage)


if __name__ == "__main__": main()
