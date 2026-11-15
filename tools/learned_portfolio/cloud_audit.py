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


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=['diagnose','data','final'])
    p.add_argument('--system-dns',action='store_true');a=p.parse_args()
    if not a.system_dns:
        from .dns_run import install_resolver
        install_resolver()
    stage='data' if a.stage=='diagnose' else a.stage
    rows=read_rows(stage)
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
