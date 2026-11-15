"""Rebuild saved commands on the same Linux image as the original missions."""

import argparse
import gzip
import json
import time
import modal

from .cloud import image
from .run import OUT, file_hash, read_rows, utc, write
from .audit import read_bundle
from lightlag_learned_portfolio.worker import canonical

app=modal.App('lightlag-portfolio-replay-audit',image=image)


@app.function(cpu=1.,memory=1024,timeout=600,max_containers=32,retries=0,scaledown_window=10,include_source=False)
def physics(bundles,keep_replay=False):
    from collections import defaultdict
    from lightlag_traverse.environment import TraverseEnvironment
    from lightlag_learned_portfolio.worker import digest,source_manifest
    results=[]
    for bundle in bundles:
        assert digest(source_manifest())==bundle['source_sha256']
        env=TraverseEnvironment(bundle['job']['seed']);commands=defaultdict(list)
        for command in bundle['commands']:commands[command['sent_tick']].append(command)
        for tick in range(env.rules()['max_ticks']):
            for command in commands.pop(tick,[]):
                assert digest(env.uplink([command['command']]))==digest([command])
            env.advance(1)
        assert not commands
        replay=env.replay()
        assert digest(replay)==bundle['replay_sha256'], (bundle['job']['seed'],bundle['job']['name'],'trajectory mismatch')
        assert replay['result']==bundle['result']
        assert replay['result']['raw_score']/replay['result']['max_available_value']==bundle['reward']
        result={'seed':bundle['job']['seed'],'name':bundle['job']['name'],
                'replay_sha256':digest(replay),'commands':len(bundle['commands']),
                'states':len(replay['states']),'ok':True,
                'parts_sha256':{**{k:digest(v) for k,v in replay.items() if k!='world'},
                    'world_without_features':digest({k:v for k,v in replay['world'].items() if k!='features'}),
                    'world_features':digest(replay['world']['features'])}}
        if keep_replay:result['replay']=replay
        results.append(result)
    return {'results':results,'modal_call_id':modal.current_function_call_id()}


@app.function(cpu=1.,memory=1024,timeout=600,max_containers=2,retries=0,scaledown_window=10,include_source=False)
def original_reference(bundle):
    from lightlag_traverse.environment import TraverseEnvironment
    from lightlag_traverse.pilot import fly
    from lightlag_traverse.play import PublicTools
    from lightlag_learned_portfolio.worker import digest,source_manifest
    assert digest(source_manifest())==bundle['source_sha256']
    env=TraverseEnvironment(bundle['job']['seed']);started=time.perf_counter()
    fly(PublicTools(env));replay=env.replay()
    result={'seed':bundle['job']['seed'],'full_budget':True,'original_pilot':True,
            'ok':digest(replay)==bundle['replay_sha256'],'replay_sha256':digest(replay),
            'expected_replay_sha256':bundle['replay_sha256'],'seconds':time.perf_counter()-started,
            'modal_call_id':modal.current_function_call_id()}
    if not result['ok']:result['replay']=replay
    return result


@app.function(cpu=1.,memory=1024,timeout=600,max_containers=2,retries=0,scaledown_window=10,include_source=False)
def repeat_policy(bundle):
    from lightlag_learned_portfolio.worker import load_model,run_episode
    spec=bundle['job']['spec'];model=load_model('/root/project/models/'+spec['algorithm']+'.pkl',spec['model_sha256'])
    repeated=run_episode(bundle['job'],model)
    result={'seed':bundle['job']['seed'],'name':bundle['job']['name'],
            'ok':repeated['replay_sha256']==bundle['replay_sha256'] and repeated['decision']==bundle['decision'],
            'expected_replay_sha256':bundle['replay_sha256'],'replay_sha256':repeated['replay_sha256'],
            'seconds':repeated['seconds'],'modal_call_id':modal.current_function_call_id()}
    if not result['ok']:result['repeated']=repeated
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=['diagnose','data','final','reference','repeat'])
    p.add_argument('--system-dns',action='store_true');a=p.parse_args()
    if not a.system_dns:
        from .dns_run import install_resolver
        install_resolver()
    stage='data' if a.stage in ('diagnose','reference') else ('final' if a.stage=='repeat' else a.stage)
    rows=read_rows(stage)
    if a.stage=='reference':
        row=next(r for r in rows if r['seed']==560000 and r['name']=='baseline')
        with modal.enable_output(),app.run():
            result=original_reference.remote(read_bundle(row))
            result.update({'created_utc':utc(),'app_id':app.app_id,'artifact_sha256':row['sha256']})
        write(OUT/'reference-parity.json',result)
        assert result['ok'], 'Original Linux reference differs; full replay retained'
        print(json.dumps(result,indent=2));return
    if a.stage=='repeat':
        selection=json.loads((OUT/'selection.json').read_text())
        row=next(r for r in rows if r['seed']==min(selection['fresh_seeds']) and r['name']==selection['primary'])
        with modal.enable_output(),app.run():
            result=repeat_policy.remote(read_bundle(row))
            result.update({'created_utc':utc(),'app_id':app.app_id,'artifact_sha256':row['sha256']})
        write(OUT/'final/controller-repeat.json',result)
        assert result['ok'],'Learned controller repeat differs; result retained'
        print(json.dumps(result,indent=2));return
    if a.stage=='diagnose':rows=[r for r in rows if r['seed']==560007 and r['name']=='baseline']
    else:
        freeze=json.loads((OUT/stage/'freeze.json').read_text())
        assert len(rows)==len(freeze['jobs'])
    bundles=[read_bundle(r) for r in rows]
    chunks=[bundles[i:i+24] for i in range(0,len(bundles),24)]
    started=time.perf_counter();results=[]
    with modal.enable_output(),app.run():
        receipt={'app_id':app.app_id,'created_utc':utc(),'stage':a.stage,'missions':len(rows)}
        write(OUT/stage/(a.stage+'-cloud-audit-app.json'),receipt)
        for batch in physics.starmap([(chunk,a.stage=='diagnose') for chunk in chunks],order_outputs=True):
            results.append(batch)
    if a.stage=='diagnose':
        path=OUT/stage/'cross-platform'/'560007-baseline-linux-replay.json.gz';path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(gzip.compress(canonical(results[0]),mtime=0))
        print(path)
    else:
        report={**receipt,'ok':True,'seconds':time.perf_counter()-started,
                'rows_sha256':file_hash(OUT/stage/'rows.jsonl'),
                'commands':sum(r['commands'] for b in results for r in b['results']),
                'states':sum(r['states'] for b in results for r in b['results']),'batches':results}
        write(OUT/stage/'cloud-audit.json',report)
        print(json.dumps({k:v for k,v in report.items() if k!='batches'},indent=2))


if __name__=='__main__':main()
