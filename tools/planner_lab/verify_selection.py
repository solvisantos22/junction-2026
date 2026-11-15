"""Independent reconstruction of model selection and final paired statistics."""

import argparse
from collections import Counter
import json
import random
import statistics

import numpy as np

from lightlag_planner_lab.model import ALGORITHMS, settings
from lightlag_planner_lab.policy import PROFILE_NAMES
from lightlag_planner_lab.worker import LEGACY_SHA, digest, file_hash, load_model, source_manifest
from .common import OUT, TRAIN, VALIDATION, FRESH, matrix, rows, require, utc, write


def measure(mine,reference):
    delta=[m['reward']-b['reward'] for m,b in zip(mine,reference)]
    return {'n':len(mine),'mean':statistics.mean(r['reward'] for r in mine),
        'delta':statistics.mean(delta),'home_alive':sum(bool(r['alive'] and r['at_base']) for r in mine),
        'deaths':sum(not r['alive'] for r in mine),'errors':sum(bool(r['error']) for r in mine),
        'invalid':sum(r['invalid'] for r in mine),'cpu_seconds':statistics.mean(r['cpu_seconds'] for r in mine),
        'higher':sum(d>1e-12 for d in delta),'equal':sum(abs(d)<=1e-12 for d in delta),
        'lower':sum(d< -1e-12 for d in delta)}


def close(actual,expected):
    if isinstance(actual,dict):
        require(actual.keys()==expected.keys(),'metric keys differ')
        for key in actual: close(actual[key],expected[key])
    elif isinstance(actual,(float,int)):
        require(abs(actual-expected)<1e-12,'metric value differs')
    else: require(actual==expected,'value differs')


def selection():
    selected=json.loads((OUT/'selection.json').read_text()); all_rows=rows('data')
    require(selected['source']==source_manifest(),'selection source differs')
    require(selected['data_report_sha256']==file_hash(OUT/'data/report.json'),'data report differs')
    require(selected['training_data_sha256']==file_hash(OUT/'training-data.json'),'training data file differs')
    training,train_by=matrix(all_rows,TRAIN,'train'); validation,by=matrix(all_rows,VALIDATION,'validation')
    require(training==json.loads((OUT/'training-data.json').read_text()),'training labels/features differ')
    require(len(set(TRAIN+VALIDATION+FRESH))==len(TRAIN)+len(VALIDATION)+len(FRESH),'split leakage')
    base=[by[s,'baseline'] for s in VALIDATION]; base_stats=measure(base,base)
    candidates=[]; model_checks={}
    for algorithm in ALGORITHMS:
        sha=selected['models'][algorithm]; model=load_model(OUT/'models'/(algorithm+'.pkl'),sha)
        metadata=json.loads((OUT/'models'/(algorithm+'.json')).read_text())
        require(metadata['sha256']==sha and metadata['source_sha256']==digest(source_manifest()),'model provenance differs')
        require(metadata['training_data_sha256']==digest(training),'model training data differs')
        require(metadata['training_worlds']==len(TRAIN) and metadata['features']==61,'training dimensions differ')
        train_pred=model.predict(training['x'])[0]
        difference=float(np.max(np.abs(train_pred-np.asarray(metadata['training_predictions']))))
        require(difference<1e-12,'remote checkpoint predictions differ')
        close(float(np.mean((train_pred-np.asarray(training['y']))**2)),metadata['training_mse'])
        model_checks[algorithm]={'sha256':sha,'max_prediction_error':difference,'training_mse':metadata['training_mse']}
        mean,std,failure=model.predict(validation['x'])
        for setting in settings(algorithm):
            utility=mean-setting['disagreement']*std-setting['risk_penalty']*failure
            choices=[]; chosen=[]
            for i,seed in enumerate(VALIDATION):
                best=max(range(len(PROFILE_NAMES)-1),key=lambda k:(float(utility[i,k]),-k))
                profile=PROFILE_NAMES[best+1] if float(utility[i,best])>setting['threshold'] else 'baseline'
                choices.append({'seed':seed,'profile':profile}); chosen.append(by[seed,profile])
            stats=measure(chosen,base)
            eligible=(stats['home_alive']>=base_stats['home_alive'] and stats['deaths']<=base_stats['deaths']
                and stats['errors']==0 and stats['invalid']==0)
            candidates.append({'algorithm':algorithm,'setting':setting,'stats':stats,'eligible':eligible,
                'choices':choices,'spec':{'kind':'learned','algorithm':algorithm,'setting':setting,'model_sha256':sha}})
    require(len(candidates)==len(selected['validation_candidates'])==24,'candidate grid differs')
    for a,b in zip(candidates,selected['validation_candidates']): close(a,b)
    ranked=sorted(candidates,key=lambda c:(not c['eligible'],-c['stats']['delta'],c['algorithm'],
        -c['setting']['threshold'],-c['setting']['disagreement'],-c['setting']['risk_penalty']))
    winners=[]
    for candidate in ranked:
        if candidate['algorithm'] not in [w['algorithm'] for w in winners]: winners.append(candidate)
        if len(winners)==2: break
    learned=[a for a in selected['arms'] if a['spec']['kind']=='learned']
    require(learned==[{'name':'learned_'+w['algorithm'],'spec':w['spec']} for w in winners],'selected families differ')
    require(selected['primary']=='learned_'+winners[0]['algorithm'] and selected['primary_eligible']==winners[0]['eligible'],
            'primary ranking differs')
    fixed={n:measure([by[s,n] for s in VALIDATION],base) for n in PROFILE_NAMES}
    close(fixed,selected['fixed_validation'])
    best=max(PROFILE_NAMES,key=lambda n:(fixed[n]['mean'],-PROFILE_NAMES.index(n)))
    require(best==selected['best_static'],'best fixed strategy differs')
    require(selected['arms'][:3]==[
        {'name':'reference','spec':{'kind':'fixed','profile':'baseline'}},
        {'name':'old_extra_trees','spec':{'kind':'legacy','model_sha256':LEGACY_SHA}},
        {'name':'static_best','spec':{'kind':'fixed','profile':best}}], 'control arms differ')
    require(selected['fresh_seeds']==FRESH,'fresh seeds differ')
    old={r['seed']:r for r in all_rows if r['split']=='validation' and r['name']=='old_extra_trees'}
    close(measure([old[s] for s in VALIDATION],base),selected['old_policy_validation'])
    oracle=statistics.mean(max(by[s,n]['reward'] for n in PROFILE_NAMES) for s in VALIDATION)
    proof={'created_utc':utc(),'selection_sha256':file_hash(OUT/'selection.json'),'model_checks':model_checks,
        'settings_verified':len(candidates),'primary':selected['primary'],'reference':base_stats,
        'validation_oracle_mean':oracle,'validation_oracle_gain':oracle-base_stats['mean'],
        'selected_profile_counts':{w['algorithm']:dict(Counter(c['profile'] for c in w['choices'])) for w in winners}}
    write(OUT/'selection-audit.json',proof); print(json.dumps(proof,indent=2))


def final():
    chosen=json.loads((OUT/'selection.json').read_text()); saved=json.loads((OUT/'final/summary.json').read_text())
    require(saved['primary']==chosen['primary'],'summary primary differs from frozen selection')
    all_rows=rows('final'); lookup={(r['name'],r['seed']):r for r in all_rows}
    names=[a['name'] for a in chosen['arms']]
    require(len(all_rows)==len(lookup)==len(FRESH)*5,'final grid count differs')
    require(set(lookup)=={(n,s) for n in names for s in FRESH},'final grid differs')
    reference=[lookup['reference',s] for s in FRESH]; old=[lookup['old_extra_trees',s] for s in FRESH]
    rng=random.Random(572192)
    indices=np.array([[rng.randrange(len(FRESH)) for _ in FRESH] for _ in range(20000)])
    def interval(delta,alpha=.05):
        averages=sorted(float(x) for x in np.asarray(delta)[indices].mean(axis=1))
        return [averages[int(alpha/2*20000)],averages[int((1-alpha/2)*20000)]]
    table={}
    for name in names:
        mine=[lookup[name,s] for s in FRESH]; stats=measure(mine,reference)
        delta=[a['reward']-b['reward'] for a,b in zip(mine,reference)]
        old_delta=[a['reward']-b['reward'] for a,b in zip(mine,old)]
        stats.update(ci95=interval(delta),ci_family95=interval(delta,.0125),
            vs_old_delta=sum(old_delta)/len(FRESH),vs_old_ci95=interval(old_delta))
        table[name]=stats
    close(table,saved['table']); p,b,o=(table[n] for n in (chosen['primary'],'reference','old_extra_trees'))
    gate={'validation_eligible':chosen['primary_eligible'],'mean_gain':p['delta']>=.01,
        'positive_interval':p['ci95'][0]>0,'nonnegative_vs_old':p['vs_old_delta']>=0,
        'home':p['home_alive']>=max(b['home_alive'],o['home_alive']),
        'deaths':p['deaths']<=min(b['deaths'],o['deaths']),'valid':p['errors']==0 and p['invalid']==0}
    require(saved['gate']==gate and saved['confirmed']==all(gate.values()),'practical gate differs')
    proof={'created_utc':utc(),'missions':len(all_rows),'summary_sha256':file_hash(OUT/'final/summary.json'),
        'selection_sha256':file_hash(OUT/'selection.json'),'bootstrap_draws':20000,'table':table,'gate':gate,
        'confirmed':all(gate.values())}
    write(OUT/'final/statistics-audit.json',proof); print(json.dumps(proof,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('stage',choices=['selection','final'])
    args=parser.parse_args(); selection() if args.stage=='selection' else final()
