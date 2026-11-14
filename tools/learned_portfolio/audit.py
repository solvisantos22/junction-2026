"""Rebuild saved missions and check the recorded classical-model decisions."""

import argparse
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
import gzip
import json
import multiprocessing
import random
import statistics
import time

from lightlag_traverse.environment import TraverseEnvironment
from lightlag_learned_portfolio.policy import PROFILE_NAMES, choose
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
    exact=digest(replay)==bundle["replay_sha256"]
    proof=row.get('_linux_audit')
    require(exact or (proof and proof['replay_sha256']==bundle['replay_sha256'] and proof['ok']),
            'full trajectory digest mismatch; needs independent Linux verification')
    differences=[]
    if proof:
        parts={**{k:digest(v) for k,v in replay.items() if k!='world'},
               'world_without_features':digest({k:v for k,v in replay['world'].items() if k!='features'}),
               'world_features':digest(replay['world']['features'])}
        differences=[k for k,h in parts.items() if h!=proof['parts_sha256'][k]]
    if 'replay' in bundle:require(digest(bundle['replay'])==bundle['replay_sha256'],'saved replay digest')
    require(replay["result"]==bundle["result"],"grade mismatch")
    reward=replay["result"]["raw_score"]/replay["result"]["max_available_value"]
    require(reward==row["reward"]==bundle["reward"],"reward mismatch")
    require(row["decision"]==bundle["decision"] and row["error"]==bundle["error"]
            and row["invalid"]==len(bundle["invalid"]),"ledger mismatch")
    require(row["alive"]==replay["result"]["alive"] and row["at_base"]==replay["result"]["at_base"],"return mismatch")
    require(digest([c for c in bundle["commands"] if c["sent_tick"]<140])==row["prefix_sha256"],"prefix digest mismatch")
    return {"seed":row["seed"],"name":row["name"],"commands":len(bundle["commands"]),
            "states":len(replay["states"]),"ok":True,'exact_local_digest':exact,
            'cross_platform_differing_parts':differences}


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
    local_rows=rows;cloud_path=OUT/stage/'cloud-audit.json'
    if cloud_path.exists():
        cloud=json.loads(cloud_path.read_text())
        require(cloud['ok'] and cloud['rows_sha256']==file_hash(OUT/stage/'rows.jsonl'),'cloud audit ledger mismatch')
        proofs={(r['seed'],r['name']):r for batch in cloud['batches'] for r in batch['results']}
        require(len(proofs)==len(rows) and set(proofs)=={(r['seed'],r['name']) for r in rows},'cloud audit grid mismatch')
        local_rows=[{**r,'_linux_audit':proofs[r['seed'],r['name']]} for r in rows]
    with ProcessPoolExecutor(max_workers=workers,mp_context=multiprocessing.get_context("spawn")) as pool:
        checks=list(pool.map(replay_one,local_rows,chunksize=4))
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
            "exact_local_digests":sum(c['exact_local_digest'] for c in checks),
            "cross_platform_differences":[{k:c[k] for k in ('seed','name','cross_platform_differing_parts')}
                                           for c in checks if not c['exact_local_digest']],
            "linux_audit_sha256":file_hash(cloud_path) if cloud_path.exists() else None,
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


def independent_metrics(rows, baseline):
    require([r['seed'] for r in rows]==[r['seed'] for r in baseline], 'unpaired rows')
    differences=[r['reward']-b['reward'] for r,b in zip(rows,baseline)]
    return {'n':len(rows),'mean':statistics.fmean(r['reward'] for r in rows),
            'delta':statistics.fmean(differences),
            'home_alive':sum(bool(r['alive'] and r['at_base']) for r in rows),
            'deaths':sum(not r['alive'] for r in rows),'errors':sum(bool(r['error']) for r in rows),
            'invalid':sum(r['invalid'] for r in rows),
            'cpu_seconds':statistics.fmean(r['cpu_seconds'] for r in rows),
            'higher':sum(d>1e-12 for d in differences),'equal':sum(abs(d)<=1e-12 for d in differences),
            'lower':sum(d< -1e-12 for d in differences)}


def same_metrics(actual, expected):
    for key,value in expected.items():
        require(key in actual and abs(actual[key]-value)<1e-10, 'metric mismatch: '+key)


def audit_selection():
    import numpy as np
    selection=json.loads((OUT/'selection.json').read_text())
    require(selection['source']==source_manifest(), 'selection source changed')
    require(selection['fresh_seeds']==CHECK, 'fresh split changed')
    require(selection['data_report_sha256']==file_hash(OUT/'data/report.json'), 'data report changed')
    require(selection['training_data_sha256']==file_hash(OUT/'training-data.json'), 'training data changed')
    rows=read_rows('data');training,by_train=matrix(rows,TRAIN,'train')
    require(training==json.loads((OUT/'training-data.json').read_text()), 'training matrix changed')
    _,by=matrix(rows,VALIDATION,'validation')
    baseline=[by[s,'baseline'] for s in VALIDATION]
    baseline_metrics=independent_metrics(baseline,baseline)
    require({(c['algorithm'],c['threshold']) for c in selection['validation_candidates']}==
            {(a,t) for a in ('extra_trees','hist_boost','ridge') for t in (0.,.002,.005)}, 'candidate grid changed')
    require(len(selection['validation_candidates'])==9, 'duplicate candidates')
    for candidate in selection['validation_candidates']:
        algorithm=candidate['algorithm'];sha=selection['models'][algorithm]
        model=load_model(OUT/'models'/(algorithm+'.pkl'),sha)
        x=[[by[s,'baseline']['decision']['features'][n] for n in model.feature_names_] for s in VALIDATION]
        predictions=model.predict(x);chosen=[]
        require(len(candidate['decisions'])==len(VALIDATION), 'decision count')
        for seed,values,recorded in zip(VALIDATION,predictions,candidate['decisions']):
            index=int(np.argmax(values))
            name=PROFILE_NAMES[index+1] if values[index]>candidate['threshold'] else 'baseline'
            require(recorded['seed']==seed and recorded['profile']==name, 'validation choice mismatch')
            np.testing.assert_allclose(recorded['predictions'],values,rtol=1e-10,atol=1e-12)
            chosen.append(by[seed,name])
        measured=independent_metrics(chosen,baseline);same_metrics(candidate['stats'],measured)
        eligible=(measured['home_alive']>=baseline_metrics['home_alive'] and
                  measured['deaths']<=baseline_metrics['deaths'] and not measured['errors'] and not measured['invalid'])
        require(candidate['eligible']==eligible, 'eligibility mismatch')
        require(candidate['spec']=={'kind':'learned','algorithm':algorithm,'threshold':candidate['threshold'],
                                    'model_sha256':sha}, 'candidate spec mismatch')
    ranked=sorted(selection['validation_candidates'],key=lambda c:(not c['eligible'],-c['stats']['delta'],c['algorithm'],-c['threshold']))
    winners=[]
    for candidate in ranked:
        if candidate['algorithm'] not in [c['algorithm'] for c in winners]:winners.append(candidate)
        if len(winners)==2:break
    require(selection['primary']==winners[0]['algorithm'] and
            selection['primary_validation_eligible']==winners[0]['eligible'], 'primary mismatch')
    for name in PROFILE_NAMES:
        same_metrics(selection['static_comparisons'][name],independent_metrics([by[s,name] for s in VALIDATION],baseline))
    best=max(PROFILE_NAMES,key=lambda n:(selection['static_comparisons'][n]['mean'],-PROFILE_NAMES.index(n)))
    require(selection['best_static']==best, 'fixed strategy mismatch')
    specs={'baseline':{'kind':'fixed','profile':'baseline'},'static_best':{'kind':'fixed','profile':best},
           **{c['algorithm']:c['spec'] for c in winners}}
    require(selection['specs']==specs, 'fresh specs mismatch')
    result={'ok':True,'created_utc':utc(),'selection_sha256':file_hash(OUT/'selection.json'),
            'validation_candidates':9,'validation_decisions':9*len(VALIDATION),
            'training_worlds':len(by_train)//len(PROFILE_NAMES),'primary':selection['primary'],'specs':specs}
    write(OUT/'selection-audit.json',result);print(json.dumps(result,indent=2))


def audit_summary():
    import numpy as np
    selection=json.loads((OUT/'selection.json').read_text())
    summary=json.loads((OUT/'final/summary.json').read_text())
    rows=read_rows('final');by={(r['name'],r['seed']):r for r in rows}
    require(len(rows)==len(by)==4*len(CHECK), 'incomplete final matrix')
    require(set(by)=={(name,s) for name in selection['specs'] for s in CHECK}, 'final grid mismatch')
    base=[by['baseline',s] for s in CHECK]
    rng=random.Random(562096)
    draws=np.asarray([[rng.randrange(len(CHECK)) for _ in CHECK] for _ in range(20000)])
    for name in selection['specs']:
        mine=[by[name,s] for s in CHECK]
        same_metrics(summary['table'][name],independent_metrics(mine,base))
        differences=np.asarray([r['reward']-b['reward'] for r,b in zip(mine,base)])
        means=np.sort(np.mean(differences[draws],axis=1))
        for key,alpha in [('ci95',.05),('ci_family95',.05/3)]:
            bounds=means[[int(alpha/2*len(means)),min(len(means)-1,int((1-alpha/2)*len(means)))]]
            np.testing.assert_allclose(summary['table'][name][key],bounds,rtol=1e-10,atol=1e-12)
    primary=summary['table'][selection['primary']];baseline=summary['table']['baseline']
    gates={'mean_gain':primary['delta']>=.01,'positive_interval':primary['ci95'][0]>0,
           'home':primary['home_alive']>=baseline['home_alive'],'deaths':primary['deaths']<=baseline['deaths'],
           'valid':not primary['errors'] and not primary['invalid']}
    require(summary['primary']==selection['primary'] and summary['gate']==gates and
            summary['confirmed']==all(gates.values()), 'final gate mismatch')
    result={'ok':True,'created_utc':utc(),'summary_sha256':file_hash(OUT/'final/summary.json'),
            'paired_worlds':len(CHECK),'bootstrap_draws':len(draws),'confirmed':summary['confirmed']}
    write(OUT/'final/summary-audit.json',result);print(json.dumps(result,indent=2))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("stage",choices=["smoke","data","final","models","selection","summary"])
    p.add_argument("--workers",type=int,default=6)
    p.add_argument("--full",default="")
    a=p.parse_args()
    if a.stage=="models":audit_models()
    elif a.stage=="selection":audit_selection()
    elif a.stage=="summary":audit_summary()
    else:audit(a.stage,a.workers,[n for n in a.full.split(',') if n])


if __name__=='__main__':main()
