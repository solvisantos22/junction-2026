"""Descriptive diagnostics only; never alter model or strategy selection."""

from collections import Counter
import json
import statistics
import numpy as np

from lightlag_learned_portfolio.policy import PROFILE_NAMES
from lightlag_learned_portfolio.worker import load_model
from .run import OUT, TRAIN, VALIDATION, matrix, read_rows, stats, utc, write


def main():
    selection=json.loads((OUT/'selection.json').read_text())
    rows=read_rows('data');splits={};matrices={}
    for split,seeds in [('train',TRAIN),('validation',VALIDATION)]:
        data,by=matrix(rows,seeds,split);matrices[split]=data
        baseline=[by[s,'baseline'] for s in seeds]
        table={name:stats([by[s,name] for s in seeds],baseline) for name in PROFILE_NAMES}
        oracle=[max((by[s,name] for name in PROFILE_NAMES),key=lambda r:r['reward']) for s in seeds]
        splits[split]={'profiles':table,'hindsight_oracle':stats(oracle,baseline),
                       'oracle_warning':'Uses final scores unavailable to a policy; descriptive portfolio ceiling only.',
                       'worlds_with_any_improvement':sum(r['reward']>b['reward']+1e-12 for r,b in zip(oracle,baseline))}
    fits={}
    for algorithm,sha in selection['models'].items():
        model=load_model(OUT/'models'/(algorithm+'.pkl'),sha);record={}
        for split,data in matrices.items():
            actual=np.asarray(data['y']);prediction=model.predict(data['x'])
            record[split]={'mse':float(np.mean((actual-prediction)**2)),
                           'zero_delta_mse':float(np.mean(actual**2)),
                           'mean_absolute_error':float(np.mean(np.abs(actual-prediction)))}
        if hasattr(model,'feature_importances_'):
            record['feature_importance']=sorted(zip(model.feature_names_,map(float,model.feature_importances_)),
                                                key=lambda pair:-pair[1])
        meta=json.loads((OUT/'models'/(algorithm+'.json')).read_text())
        record['fit_seconds']=meta['seconds'];record['modal_call_id']=meta['modal_call_id']
        fits[algorithm]=record
    choices={}
    for candidate in selection['validation_candidates']:
        key=candidate['algorithm']+'@'+str(candidate['threshold'])
        choices[key]=dict(Counter(d['profile'] for d in candidate['decisions']))
    final_rows=read_rows('final')
    if final_rows:
        choices['fresh']={name:dict(Counter(r['decision']['profile'] for r in final_rows if r['name']==name))
                          for name in selection['specs']}
    result={'created_utc':utc(),'splits':splits,'fits':fits,'strategy_choices':choices,
            'successful_mission_seconds':sum(r['seconds'] for r in rows+final_rows),
            'successful_mission_cpu_seconds':sum(r['cpu_seconds'] for r in rows+final_rows),
            'successful_mission_compute_estimate_usd':sum(r['seconds'] for r in rows+final_rows)*(.0000131+.00000222),
            'compute_estimate_limits':'Allocation-rate estimate for recorded controller execution only, not a bill. Excludes environment initialization/serialization, preempted/lost work, startup/idle time, fitting, audits, builds, storage and network.'}
    write(OUT/'diagnostics.json',result)
    print(json.dumps({'fits':fits,'oracle_gains':{k:v['hindsight_oracle']['delta'] for k,v in splits.items()},
                      'successful_mission_compute_estimate_usd':result['successful_mission_compute_estimate_usd']},indent=2))


if __name__=='__main__':main()
