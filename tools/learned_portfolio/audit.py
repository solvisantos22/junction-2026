"""Rebuild saved missions and check the recorded classical-model decisions."""

import argparse
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
import gzip
import json
import multiprocessing
from pathlib import Path
import time

from lightlag_traverse.environment import TraverseEnvironment
from lightlag_learned_portfolio.policy import choose
from lightlag_learned_portfolio.worker import digest, load_model, run_episode, source_manifest
from .run import OUT, TRAIN, VALIDATION, CHECK, file_hash, matrix, read_rows, require, utc, write


def read_bundle(row):
    path=(OUT/row["artifact"]).resolve()
    require(path.is_relative_to(OUT.resolve()) and file_hash(path)==row["sha256"],"artifact path/hash")
    return json.loads(gzip.decompress(path.read_bytes()))


def replay_one(row):
    bundle=read_bundle(row)
    require(bundle["job"]["name"]==row["name"] and bundle["job"]["seed"]==row["seed"],"job identity")
    env=TraverseEnvironment(row["seed"])
    by_tick=defaultdict(list)
    for command in bundle["commands"]:by_tick[command["sent_tick"]].append(command)
    for tick in range(env.rules()["max_ticks"]):
        for command in by_tick.pop(tick,[]):
            require(digest(env.uplink([command["command"]]))==digest([command]),"acknowledgement mismatch")
        env.advance(1)
    require(not by_tick,"commands after horizon")
    replay=env.replay()
    require(digest(replay)==bundle["replay_sha256"],"full trajectory digest mismatch")
    require(replay["result"]==bundle["result"],"grade mismatch")
    reward=replay["result"]["raw_score"]/replay["result"]["max_available_value"]
    require(reward==row["reward"]==bundle["reward"],"reward mismatch")
    require(row["decision"]==bundle["decision"] and row["error"]==bundle["error"]
            and row["invalid"]==len(bundle["invalid"]),"ledger mismatch")
    require(row["alive"]==replay["result"]["alive"] and row["at_base"]==replay["result"]["at_base"],"return mismatch")
    require(digest([c for c in bundle["commands"] if c["sent_tick"]<140])==row["prefix_sha256"],"prefix digest mismatch")
    return {"seed":row["seed"],"name":row["name"],"commands":len(bundle["commands"]),
            "states":len(replay["states"]),"ok":True}


def audit(stage, workers=6, full=()):
    started=time.perf_counter()
    freeze=json.loads((OUT/stage/"freeze.json").read_text())
    current=source_manifest()
    differences=[p for p,h in freeze["source"].items() if current.get(p)!=h]
    if stage=="smoke":
        require(set(differences)<=set(["tools/learned_portfolio/cloud.py","tools/learned_portfolio/run.py"]),
                "smoke execution source changed beyond documented orchestration fix")
    else:require(not differences,"runtime source differs from freeze")
    rows=read_rows(stage)
    expected={(j["split"],j["seed"],j["name"]):j for j in freeze["jobs"]}
    require(len(rows)==len(expected),"incomplete matrix")
    require(len({(r["split"],r["seed"],r["name"]) for r in rows})==len(rows),"duplicate rows")
    for row in rows:
        bundle=read_bundle(row)
        require(bundle["job"]==expected[row["split"],row["seed"],row["name"]],"frozen job mismatch")
        require(bundle["source_sha256"]==digest(freeze["source"]),"remote source digest mismatch")
    if stage=="smoke":matrix(rows,[1],"smoke")
    if stage=="data":
        training,_=matrix(rows,TRAIN,"train");matrix(rows,VALIDATION,"validation")
        if (OUT/"training-data.json").exists():
            require(training==json.loads((OUT/"training-data.json").read_text()),"training matrix mismatch")
    with ProcessPoolExecutor(max_workers=workers,mp_context=multiprocessing.get_context("spawn")) as pool:
        checks=list(pool.map(replay_one,rows,chunksize=4))
    models={}
    decisions=0
    if stage=="final":
        import numpy as np
        selection=json.loads((OUT/"selection.json").read_text())
        require(selection["source"]==current,"selection source mismatch")
        require(selection["data_report_sha256"]==file_hash(OUT/"data/report.json"),"data changed after selection")
        require(selection["training_data_sha256"]==file_hash(OUT/"training-data.json"),"training data changed")
        for name,sha in selection["models"].items():models[name]=load_model(OUT/"models"/(name+".pkl"),sha)
        for row in rows:
            spec=selection["specs"][row["name"]]
            decision=row["decision"]
            require(decision is not None and decision["tick"]==140,"missing/incorrect switch decision")
            if spec["kind"]=="fixed":
                require(decision["profile"]==spec["profile"],"fixed strategy mismatch")
            else:
                name,prediction=choose(models[spec["algorithm"]],decision["features"],spec["threshold"])
                require(name==decision["profile"],"learned choice mismatch")
                np.testing.assert_allclose(prediction,decision["predictions"],rtol=1e-10,atol=1e-12)
                decisions+=1
    repeats=[]
    first=min(r["seed"] for r in rows)
    for name in full:
        row=next(r for r in rows if r["name"]==name and r["seed"]==first)
        old=read_bundle(row);model=None
        if old["job"]["spec"]["kind"]=="learned":model=models[old["job"]["spec"]["algorithm"]]
        new=run_episode(old["job"],model)
        require(new["replay_sha256"]==old["replay_sha256"] and new["prefix_sha256"]==old["prefix_sha256"],"full controller mismatch")
        require(new["result"]==old["result"] and new["decision"]["profile"]==old["decision"]["profile"],"full decision mismatch")
        repeats.append({"name":name,"seed":first,"identical_trajectory":True})
    report={"stage":stage,"created_utc":utc(),"missions":len(checks),"commands":sum(c["commands"] for c in checks),
            "states":sum(c["states"] for c in checks),"learned_choices_recomputed":decisions,
            "full_controller_repeats":repeats,"seconds":time.perf_counter()-started,"source":current,
            "documented_smoke_coordinator_changes":differences,"ok":True,
            "limits":"All physics/grades/digests and stored learned choices verified. Public-feature construction and reference-prefix logic are source-pinned, with selected full-controller repeats, not independently reconstructed for every mission."}
    write(OUT/stage/"audit.json",report);print(json.dumps({k:v for k,v in report.items() if k!='source'},indent=2))


def audit_models():
    import numpy as np
    from lightlag_learned_portfolio.model import ALGORITHMS,fit
    data=json.loads((OUT/"training-data.json").read_text())
    require(data["seeds"]==TRAIN and not set(data["seeds"])&set(VALIDATION+CHECK),"training split leak")
    results=[]
    for name in ALGORITHMS:
        recorded=json.loads((OUT/"models"/(name+".json")).read_text())
        model=load_model(OUT/"models"/(name+".pkl"),recorded["sha256"])
        np.testing.assert_allclose(model.predict(data["x"]),recorded["train_predictions"],rtol=1e-9,atol=1e-11)
        repeated=fit(name,data)
        np.testing.assert_allclose(repeated["train_predictions"],recorded["train_predictions"],rtol=1e-8,atol=1e-10)
        results.append({"algorithm":name,"training_predictions_reproduced":True,"modal_call_id":recorded["modal_call_id"]})
    write(OUT/"model-audit.json",{"created_utc":utc(),"fits":results,"ok":True})
    print(json.dumps(results,indent=2))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("stage",choices=["smoke","data","final","models"])
    p.add_argument("--workers",type=int,default=6)
    p.add_argument("--full",default="")
    a=p.parse_args()
    if a.stage=="models":audit_models()
    else:audit(a.stage,a.workers,[n for n in a.full.split(',') if n])


if __name__=='__main__':main()
