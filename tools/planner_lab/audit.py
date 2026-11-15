"""Rebuild archived missions and check source, decisions, selection and statistics."""

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
import json
import time

from lightlag_planner_lab.worker import (LEGACY, LEGACY_SHA, digest, file_hash,
    load_model, replay_episode, source_manifest)
from lightlag_planner_lab.policy import PROFILE_NAMES
from .common import (OUT, TRAIN, VALIDATION, FRESH, matrix, orchestration,
    read_batch, read_receipts, receipt, require, rows, utc, write)
from .run import jobs_for


def inventory(stage, tag):
    directory = OUT/tag
    freeze = json.loads((directory/'freeze.json').read_text())
    report = json.loads((directory/'report.json').read_text())
    source = source_manifest()
    require(freeze['source'] == report['source'] == source, 'source freeze changed')
    expected = {j['id']:{k:v for k,v in j.items() if k != 'source'} for j in jobs_for(stage)}
    require(freeze['jobs'] == list(expected.values()), 'frozen job grid changed')
    ledger = read_receipts(tag)
    require(report['receipts_sha256'] == file_hash(directory/'receipts.jsonl'), 'receipt hash changed')
    require(len(ledger) == len(expected) and {r['job_id'] for r in ledger} == set(expected), 'incomplete/duplicate batches')
    all_rows = []; prefixes = {}; same_program = {}; bundles = []
    for item in ledger:
        result = read_batch(item); job = result['job']; seed = job['seed']
        require(job == expected[item['job_id']], 'job differs from freeze')
        require(result['source_sha256'] == digest(source), 'remote source differs')
        require(receipt(result, item['artifact']) == item, 'receipt differs from raw batch')
        require([e['arm'] for e in result['episodes']] == job['arms'], 'arm grid differs')
        for episode in result['episodes']:
            require(not episode['error'] and not episode['invalid'], 'invalid controller outcome')
            state = episode['decision']['features']; prefix = (state, episode['prefix_sha256'])
            require(episode['decision']['tick'] == 70 and len(state) == 61, 'feature schema/tick changed')
            require(prefixes.setdefault(seed, prefix) == prefix, 'shared initial state differs')
            if 'replay' in episode:
                require(digest(episode['replay']) == episode['replay_sha256'], 'stored replay differs')
                require(episode['replay']['commands'] == episode['commands'], 'stored commands differ')
                # The full replay stays in the hash-checked archive. Keeping every
                # decoded replay would multiply memory across concurrent audits.
                del episode['replay']
            kind = episode['arm']['spec']['kind']
            if kind != 'legacy':
                key = seed, episode['decision']['profile']
                require(same_program.setdefault(key, episode['replay_sha256']) == episode['replay_sha256'],
                        'same program produced different trajectory')
        bundles.append(result); all_rows.extend(item['rows'])
    require(report['rows'] == all_rows and report['missions'] == len(all_rows), 'report differs from raw results')
    require(report['batches'] == len(ledger), 'batch count differs')
    if stage == 'data':
        matrix(all_rows, TRAIN, 'train'); matrix(all_rows, VALIDATION, 'validation')
    elif stage == 'smoke': matrix(all_rows, [1,2], 'smoke')
    proof = {'created_utc':utc(), 'stage':stage, 'tag':tag, 'missions':len(all_rows),
        'batches':len(ledger), 'worlds':len(prefixes), 'source_sha256':digest(source),
        'receipts_sha256':file_hash(directory/'receipts.jsonl'), 'orchestration':orchestration()}
    write(directory/'inventory-audit.json', proof)
    print(json.dumps(proof), flush=True)
    return bundles


def slim(bundle):
    keys = ('arm','commands','replay_sha256','parts_sha256','result','reward')
    return {'job':bundle['job'], 'source_sha256':bundle['source_sha256'],
            'episodes':[{k:e[k] for k in keys} for e in bundle['episodes']]}


def local_batch(bundle):
    return [{'job_id':bundle['job']['id'], 'seed':bundle['job']['seed'],
             'name':episode['arm']['name'], **replay_episode(bundle['job']['seed'], episode, strict=False)}
            for episode in bundle['episodes']]


def physics(stage, tag, cloud=False):
    bundles = [slim(b) for b in inventory(stage,tag)]; started = time.perf_counter(); checked = []
    calls = []; app_id = None
    if cloud:
        import modal
        from .cloud import app, verify
        chunks = [bundles[i:i+4] for i in range(0,len(bundles),4)]
        with modal.enable_output(), app.run():
            app_id = app.app_id
            write(OUT/tag/'cloud-audit-launch.json', {'app_id':app_id,'created_utc':utc(),
                'orchestration':orchestration(),'batches':len(chunks),'source':source_manifest()})
            for result in verify.map(chunks,order_outputs=False):
                checked.extend(result.pop('checked')); calls.append(result)
                print(f"physics {len(checked)} missions",flush=True)
    else:
        with ProcessPoolExecutor(max_workers=6) as pool:
            for result in pool.map(local_batch,bundles,chunksize=4): checked.extend(result)
    expected = {(b['job']['id'],e['arm']['name']):e['replay_sha256'] for b in bundles for e in b['episodes']}
    actual = {(r['job_id'],r['name']):r['replay_sha256'] for r in checked}
    require(len(checked) == len(expected) and actual == expected, 'physics audit grid differs')
    checked.sort(key=lambda r:(r['job_id'],r['name']))
    proof = {'created_utc':utc(),'source_sha256':digest(source_manifest()),'missions':len(checked),
        'exact':sum(r['exact'] for r in checked),'metadata_only_differences':sum(not r['exact'] for r in checked),
        'elapsed_seconds':time.perf_counter()-started,'app_id':app_id,'calls':calls,'checked':checked,
        'receipts_sha256':file_hash(OUT/tag/'receipts.jsonl'),'orchestration':orchestration()}
    write(OUT/tag/('cloud-audit.json' if cloud else 'local-audit.json'),proof)
    print(json.dumps({k:v for k,v in proof.items() if k not in ('checked','calls','orchestration')}),flush=True)


def repeats(stage,tag):
    import modal
    from .cloud import app,repeat
    bundles = inventory(stage,tag); seed = min(b['job']['seed'] for b in bundles)
    lookup = {e['arm']['name']:(b,e) for b in bundles if b['job']['seed']==seed for e in b['episodes']}
    base = 'reference' if stage == 'final' else 'baseline'
    candidate = (json.loads((OUT/'selection.json').read_text())['primary'] if stage == 'final' else 'aggressive_guarded')
    specs = [(base,True),(candidate,False)]
    if 'old_extra_trees' in lookup: specs.append(('old_extra_trees','legacy'))
    calls = []; checked = []
    with modal.enable_output(), app.run():
        for name,original in specs:
            bundle,episode = lookup[name]; job = {**bundle['job'],'source':source_manifest()}
            call = repeat.spawn(job,episode['arm'],original)
            calls.append((name,original,call,episode))
        write(OUT/tag/'repeat-launch.json',{'app_id':app.app_id,'created_utc':utc(),
            'calls':[{'name':n,'original':o,'call_id':c.object_id} for n,o,c,e in calls],
            'source':source_manifest(),'orchestration':orchestration()})
        for name,original,call,expected in calls:
            actual = call.get()
            require(actual['replay_sha256']==expected['replay_sha256'] and actual['result']==expected['result'],
                    'full controller repeat differs: '+name)
            if not original:
                require(actual['decision']==expected['decision'] and actual['legacy_decision']==expected['legacy_decision'],
                        'repeat decisions differ')
            checked.append({'seed':seed,'name':name,'original':original,**actual})
    write(OUT/tag/'repeat-audit.json',{'created_utc':utc(),'app_id':app.app_id,'checked':checked,
        'source_sha256':digest(source_manifest()),'orchestration':orchestration()})
    print(f"Full controller repeats passed: {len(checked)}",flush=True)


def decisions(tag):
    import numpy as np
    from lightlag_learned_portfolio.policy import choose as old_choose
    selection = json.loads((OUT/'selection.json').read_text()); models = {}
    for name,sha in selection['models'].items(): models[name] = load_model(OUT/'models'/(name+'.pkl'),sha)
    old = load_model(LEGACY,LEGACY_SHA); checked = Counter(); largest = 0.
    for r in rows(tag):
        spec = r['arm']['spec']; dec = r['decision']
        if spec['kind']=='learned':
            name,prediction = models[spec['algorithm']].choose(dec['features'],spec['setting'])
            require(name==dec['profile'],'learned choice differs')
            for key,values in prediction.items():
                error=float(np.max(np.abs(np.asarray(values)-np.asarray(dec['prediction'][key]))))
                largest=max(largest,error); require(error<1e-12,'learned predictions differ')
            checked['new_model']+=1
        elif spec['kind']=='legacy':
            dec = r['legacy_decision']; name,prediction=old_choose(old,dec['features'],0.)
            require(name==dec['profile'] and np.allclose(prediction,dec['prediction'],atol=1e-12,rtol=0),
                    'old model choice/predictions differ')
            checked['old_model']+=1
        else: require(dec['profile']==spec['profile'],'fixed choice differs'); checked['fixed']+=1
    proof={'created_utc':utc(),'checked':dict(checked),'max_prediction_error':largest,
        'selection_sha256':file_hash(OUT/'selection.json'),'receipts_sha256':file_hash(OUT/tag/'receipts.jsonl')}
    write(OUT/tag/'decision-audit.json',proof); print(json.dumps(proof),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage',choices=['smoke','data','final'])
    p.add_argument('mode',choices=['inventory','local','cloud','repeats','decisions'])
    p.add_argument('--tag'); a=p.parse_args(); tag=a.tag or a.stage
    if a.mode in ('cloud','repeats'):
        from tools.learned_portfolio.dns_run import install_resolver
        install_resolver()
    if a.mode=='inventory': inventory(a.stage,tag)
    elif a.mode in ('local','cloud'): physics(a.stage,tag,a.mode=='cloud')
    elif a.mode=='repeats': repeats(a.stage,tag)
    else: decisions(tag)


if __name__=='__main__': main()
