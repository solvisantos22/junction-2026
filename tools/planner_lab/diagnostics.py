"""Development-only diagnostics; never changes selected weights or settings."""

from collections import Counter
import json
import statistics

import numpy as np

from lightlag_planner_lab.model import ALGORITHMS
from lightlag_planner_lab.policy import PROFILE_NAMES
from lightlag_planner_lab.worker import load_model, file_hash
from .common import OUT, TRAIN, VALIDATION, matrix, rows, utc, write


def summarize():
    data=rows('data'); training,train_by=matrix(data,TRAIN,'train'); validation,valid_by=matrix(data,VALIDATION,'validation')
    selected=json.loads((OUT/'selection.json').read_text()); train_y=np.asarray(training['y']); valid_y=np.asarray(validation['y'])
    output={'created_utc':utc(),'scope':'Training/validation only; descriptive, no further tuning.',
        'selection_sha256':file_hash(OUT/'selection.json'),'splits':{},'models':{},'strategy_pairs':{}}
    for split,seeds,lookup in [('training',TRAIN,train_by),('validation',VALIDATION,valid_by)]:
        rewards=np.asarray([[lookup[s,n]['reward'] for n in PROFILE_NAMES] for s in seeds])
        homes=np.asarray([[lookup[s,n]['alive'] and lookup[s,n]['at_base'] for n in PROFILE_NAMES] for s in seeds])
        best=rewards.argmax(axis=1)
        output['splits'][split]={'worlds':len(seeds),'reference_mean':float(rewards[:,0].mean()),
            'hindsight_oracle_mean':float(rewards.max(axis=1).mean()),
            'hindsight_oracle_gain':float((rewards.max(axis=1)-rewards[:,0]).mean()),
            'hindsight_oracle_home_alive':int(homes[np.arange(len(seeds)),best].sum()),
            'worlds_with_any_improvement':int((rewards.max(axis=1)>rewards[:,0]+1e-12).sum()),
            'oracle_program_counts':dict(Counter(PROFILE_NAMES[i] for i in best)),
            'fixed':{n:{'mean':float(rewards[:,i].mean()),'delta':float((rewards[:,i]-rewards[:,0]).mean()),
                'home_alive':int(homes[:,i].sum()),'deaths':sum(not lookup[s,n]['alive'] for s in seeds)}
                for i,n in enumerate(PROFILE_NAMES)}}
    zero_mse=float(np.mean(valid_y**2)); constant_mse=float(np.mean((valid_y-train_y.mean(axis=0))**2))
    for algorithm in ALGORITHMS:
        model=load_model(OUT/'models'/(algorithm+'.pkl'),selected['models'][algorithm]); predicted=model.predict(validation['x'])[0]
        options=[c for c in selected['validation_candidates'] if c['algorithm']==algorithm]
        best=sorted(options,key=lambda c:(not c['eligible'],-c['stats']['delta'],
            -c['setting']['threshold'],-c['setting']['disagreement'],-c['setting']['risk_penalty']))[0]
        importance=getattr(model.estimator,'feature_importances_',None)
        labels=list(model.feature_names)
        if algorithm=='pooled_forest': labels += ['strategy_'+n for n in ('energy_weight','floor','home_floor','home_margin',
            'home_slack','deadline_margin','leg_slack','arrive_m','guard','activate','reset','late_fraction','searches')]
        output['models'][algorithm]={'validation_prediction_mse':float(np.mean((predicted-valid_y)**2)),
            'zero_gain_mse':zero_mse,'training_mean_gain_mse':constant_mse,
            'best_validation_setting':best['setting'],'eligible':best['eligible'],'stats':best['stats'],
            'program_counts':dict(Counter(c['profile'] for c in best['choices'])),
            'impurity_importance_not_causal':sorted(zip(labels,map(float,importance)),key=lambda p:-p[1])[:12] if importance is not None else None}
    pairs=[('aggressive_guarded','aggressive_early'),('aggressive_safe300','aggressive_early'),
        ('aggressive_safe340','aggressive_early'),('aggressive_early','aggressive_late'),
        ('energy_strong','balanced_early'),('multistart','refresh'),('deadline_focus','refresh'),
        ('late_value_optimist','refresh'),('fast_guarded','deadline_push')]
    for a,b in pairs:
        delta=[valid_by[s,a]['reward']-valid_by[s,b]['reward'] for s in VALIDATION]
        output['strategy_pairs'][a+' vs '+b]={'validation_mean_delta':statistics.mean(delta),
            'higher':sum(v>1e-12 for v in delta),'equal':sum(abs(v)<=1e-12 for v in delta),
            'lower':sum(v< -1e-12 for v in delta),
            'note':'Descriptive validation comparison; not a new held-out confirmation.'}
    write(OUT/'development-diagnostics.json',output)
    print(json.dumps(output,indent=2))


if __name__=='__main__': summarize()
