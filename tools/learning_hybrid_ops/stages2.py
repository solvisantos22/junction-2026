"""Gate untouched confirmation/final workers on the second diagnosed development recovery."""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import shutil
import sys
import tempfile
import time

from tools.learning_hybrid import cloud as c, experiment as e, manage as m
from tools.learning_hybrid_ops import recovery2 as r, recovery as first

ROOT=Path(__file__).resolve().parents[2]
OPS_FILES=('tools/learning_hybrid_ops/stages2.py','tools/learning_hybrid_ops/recovery2.py','tools/learning_hybrid_ops/recovery.py')
RESOURCES={**c.RESOURCES,'coordinator_nonpreemptible':True,'coordinator_rate_multiplier':3,
           'coordinator_timeout_seconds':21720,'workers_nonpreemptible':True,'worker_rate_multiplier':3}


def require(condition,message):
    if not condition:raise ValueError(message)


def encoded(value,encoding):
    if encoding=='canonical':return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
    if encoding=='pretty':return (json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    raise ValueError('undeclared evidence encoding')


def evidence(path):
    data=Path(path).read_bytes();value=json.loads(data)
    for encoding in ('canonical','pretty'):
        if encoded(value,encoding)==data:return {'sha256':c.digest(path),'encoding':encoding,'value':value}
    raise ValueError('evidence must retain original canonical or pretty JSON bytes')


def unpack(item):
    import hashlib
    require(hashlib.sha256(encoded(item['value'],item['encoding'])).hexdigest()==item['sha256'],
            'evidence bytes changed')
    return item['value']


def sources(root=ROOT):return {name:c.digest(Path(root)/name) for name in OPS_FILES}


def source_context(root):
    from lightlag_hybrid import worker,policy
    root=Path(root).resolve()
    require(root==ROOT.resolve() and all(Path(module.__file__).resolve().is_relative_to(root)
            for module in (c,e,m,r,first,worker,policy)) and e.PARENT.resolve()==root/c.POLICY_FILE,
            'execute stages2 from the frozen source snapshot; --root does not redirect imports')


def verify_complete(stage,state):
    jobs={j['id']:j for j in stage['jobs']};rows=state['rows'];calls=state['calls']
    require(state.get('schema')=='learning-hybrid-stage-status-v1' and state.get('stage')==stage['name']
            and state['status']=='complete' and state['freeze_sha256']==r.ORIGINAL_FREEZE
            and state['jobs_complete']==state['jobs_total']==len(jobs)
            and set(rows)==set(calls)==set(jobs) and len(set(calls.values()))==len(calls),'parent stage incomplete')
    attempt=r.RECOVERY if stage['name']=='development' else stage['name']+'-ops2'
    r.verify_rows(rows,{'stage':stage,'freeze':{'source_sha256':stage['source_sha256']}},calls,
                  allowed_attempts={attempt})
    if stage['name']!='development':
        require(all(row.get('storage',{}).get('attempt')==attempt for row in rows.values()),
                'parent attempt storage differs')


def recovery_proof(recovery_item,receipt_item,aggregate,root=ROOT,now=None):
    freeze=unpack(recovery_item);receipt=unpack(receipt_item)
    recovery_hash=recovery_item['sha256']
    require(c.state_hash(freeze)==recovery_hash,
            'recovery source freeze differs')
    r.validate(freeze,root,now=now)
    require(receipt['schema']=='learning-hybrid-recovery2-receipt-v1' and receipt['status']=='submitted'
            and receipt['recovery_id']==r.RECOVERY and receipt['freeze_sha256']==recovery_hash
            and isinstance(receipt['coordinator_call_id'],str) and receipt['coordinator_call_id'],
            'second recovery receipt differs')
    require(aggregate['stage_sha256']==r.ORIGINAL_STAGE and aggregate['coordinator_call_id']==r.ORIGINAL_CALL,
            'aggregate original stage/call differs')
    plan=freeze['original_plan'];base=freeze['retained_state'];provenance=aggregate.get('recovery2_provenance') or {}
    require(c.state_hash(plan['stage'])==first.ORIGINAL_STAGE_STATE and plan['freeze_sha256']==r.ORIGINAL_FREEZE,
            'recovery original plan differs')
    verify_complete(plan['stage'],aggregate)
    expected=r.aggregate_provenance(freeze,recovery_hash,receipt['coordinator_call_id'])
    require(provenance==expected and len(aggregate['rows'])==r.TOTAL
            and aggregate.get('budget_ledger')==freeze['budget_ledger'],'aggregate provenance differs')
    require(all(aggregate['rows'].get(n)==row and aggregate['calls'].get(n)==base['calls'][n]
                for n,row in base['rows'].items()),'retained original results changed')
    require(set(aggregate['rows'])-set(base['rows'])==set(freeze['run_ids'])
            and all(aggregate['rows'][n].get('storage',{}).get('attempt')==r.RECOVERY for n in freeze['run_ids']),
            'second recovery attempt set differs')
    return {'freeze_sha256':recovery_hash,'call_id':receipt['coordinator_call_id'],
            'aggregate_sha256':c.state_hash(aggregate),'retained_state_sha256':freeze['retained_state_sha256'],
            'parent_recovery_freeze_sha256':r.PARENT_FREEZE,'parent_recovery_state_sha256':r.PARENT_STATE_SHA256,
            'new_calls':r.RUN_COUNT,'failed_prior_attempts':r.RETRY_COUNT,'receipt':receipt,
            'budget_ledger':freeze['budget_ledger']}


def validate(freeze,root=ROOT,now=None):
    import numpy
    require(sys.version_info[:2]==(3,12) and numpy.__version__==c.RUNTIME['numpy'],'local analysis runtime differs')
    now=time.time() if now is None else now;root=Path(root)
    source_context(root)
    require(freeze['schema']=='learning-hybrid-ops-stage-freeze-v2' and freeze['resources']==RESOURCES
            and freeze['runtime']==c.RUNTIME and freeze['ops_source_sha256']==sources(ROOT)
            and freeze['created_unix']<=now<freeze['deadline_unix']==r.DEADLINE,'stage ops identity or deadline changed')
    items=freeze['evidence'];values={name:unpack(item) for name,item in items.items()}
    stage=values['stage'];name=stage['name'];parent_stage=values['parent_stage'];parent_state=values['parent_status']
    require(name in ('confirmation','final') and parent_stage['name']==('development' if name=='confirmation' else 'confirmation'),
            'stages must follow development, confirmation, final')
    require(items['master']['sha256']==r.ORIGINAL_FREEZE and c.state_hash(values['master'])==r.ORIGINAL_FREEZE,
            'original master freeze changed')
    require(parent_state['stage_sha256']==items['parent_stage']['sha256'],'parent status/stage differs')
    verify_complete(parent_stage,parent_state)
    if name=='confirmation':
        require(set(items)=={'master','stage','parent_stage','parent_status','parent_analysis','recovery_freeze','recovery_receipt'},
                'confirmation evidence fields differ')
        proof=recovery_proof(items['recovery_freeze'],items['recovery_receipt'],parent_state,root,now)
        require(items['parent_stage']['sha256']==r.ORIGINAL_STAGE,'original development stage file differs')
    else:
        require(set(items)=={'master','stage','parent_stage','parent_status','parent_analysis','previous_ops_freeze','previous_receipt'},
                'final evidence fields differ')
        previous=values['previous_ops_freeze'];prior=validate(previous,root,now)
        receipt=values['previous_receipt']
        require(prior['plan']['stage']['name']=='confirmation' and prior['plan']['stage']==parent_stage
                and receipt['schema']=='learning-hybrid-receipt-v1' and receipt['status']=='submitted'
                and receipt['stage']=='confirmation' and receipt['freeze_sha256']==r.ORIGINAL_FREEZE
                and receipt['stage_sha256']==items['parent_stage']['sha256']
                and receipt['ops_freeze_sha256']==items['previous_ops_freeze']['sha256']
                and parent_state['coordinator_call_id']==receipt['coordinator_call_id']
                and parent_state.get('ops_freeze_sha256')==items['previous_ops_freeze']['sha256']
                and parent_state.get('attempt')=='confirmation-ops2'
                and parent_state.get('budget_ledger')==previous['budget_ledger'],'confirmation provenance differs')
        proof=prior['recovery_proof']
    require(freeze['budget_ledger']==proof['budget_ledger']
            ==r.budget_ledger(values['master'],proof['budget_ledger']['basis_created_unix'])
            and freeze['budget_ledger']['total_running_allocation_bound_usd']<=75
            and freeze['campaign_cap_usd']==75,'stage allocation ledger differs')
    # Execute the unchanged selection and stage-construction code on saved data only.
    with tempfile.TemporaryDirectory(prefix='hybrid-stage-gate-') as temporary:
        paths={key:Path(temporary)/(key+'.json') for key in items}
        for key,item in items.items():paths[key].write_bytes(encoded(item['value'],item['encoding']))
        generated_analysis=Path(temporary)/'checked-analysis.json'
        e.analyze(paths['parent_stage'],paths['parent_status'],generated_analysis)
        require(c.read(generated_analysis)==values['parent_analysis'],'analysis differs from frozen selection rules')
        require(bool(values['parent_analysis']['selected_groups']),'no eligible group; fresh maps must stay unopened')
        generated_stage=Path(temporary)/'checked-stage.json'
        e.prepare(paths['master'],name,generated_stage,paths['parent_analysis'])
        require(c.read(generated_stage)==stage,'stage differs from frozen selection/maps/controls')
        plan=m.prepare(paths['master'],paths['stage'],root,now=now)
    require(plan==freeze['plan'] and proof==freeze['recovery_proof'],'plan or recovery proof changed')
    return {'plan':plan,'recovery_proof':proof}


def write_freeze(path,*,master,stage,parent_stage,parent_status,parent_analysis,recovery_freeze=None,
                 recovery_receipt=None,previous_ops_freeze=None,previous_receipt=None,root=ROOT,now=None):
    now=time.time() if now is None else now
    source_context(root)
    files={'master':master,'stage':stage,'parent_stage':parent_stage,'parent_status':parent_status,'parent_analysis':parent_analysis}
    name=c.read(stage)['name']
    if name=='confirmation':
        require(recovery_freeze is not None and recovery_receipt is not None,'recovery freeze and receipt required')
        files.update(recovery_freeze=recovery_freeze,recovery_receipt=recovery_receipt)
    elif name=='final':
        require(previous_ops_freeze is not None and previous_receipt is not None,'confirmation ops freeze and receipt required')
        files.update(previous_ops_freeze=previous_ops_freeze,previous_receipt=previous_receipt)
    else:raise ValueError('only confirmation/final allowed')
    items={key:evidence(value) for key,value in files.items()}
    if name=='confirmation':proof=recovery_proof(items['recovery_freeze'],items['recovery_receipt'],items['parent_status']['value'],root,now)
    else:proof=validate(items['previous_ops_freeze']['value'],root,now)['recovery_proof']
    freeze={'schema':'learning-hybrid-ops-stage-freeze-v2','created_unix':now,'deadline_unix':r.DEADLINE,
            'resources':RESOURCES,'runtime':c.RUNTIME,'ops_source_sha256':sources(),'campaign_cap_usd':75,
            'budget_ledger':proof['budget_ledger'],
            'evidence':items,'plan':m.prepare(master,stage,root,now=now),'recovery_proof':proof,
            'model_api_calls':0,'cost_note':'Unchanged recovery2 cumulative allocation ledger; all65 future containers nonpreemptible at3x, sequential stages, excludes ancillary charges.'}
    validate(freeze,root,now)
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as stream:stream.write(encoded(freeze,'canonical').decode())
    return {'ops_freeze_sha256':c.digest(path),'stage':name,'jobs':len(freeze['plan']['stage']['jobs']),
            'budget_ledger':freeze['budget_ledger']}


def verify_parents(control,freeze,get_call=None):
    plan=freeze['plan'];name=plan['stage']['name'];proof=freeze['recovery_proof']
    require(not control.get('stop'),'campaign stop marker present')
    require(control.get('campaign',{}).get('freeze_sha256')==r.ORIGINAL_FREEZE,'campaign source differs')
    recovery=control.get(r.KEY+':state',{});reservation=control.get(r.KEY+':reservation',{})
    require(reservation.get('freeze_sha256')==proof['freeze_sha256'] and recovery.get('status')=='complete'
            and recovery.get('coordinator_call_id')==proof['call_id'] and recovery.get('jobs_complete')==r.RUN_COUNT
            and recovery.get('aggregate_sha256')==proof['aggregate_sha256'],'recovery not fully complete or aggregate differs')
    require(control.get(r.KEY+':receipt')==proof['receipt'] and control.get(r.KEY+':owner')==proof['call_id'],
            'live recovery receipt or owner differs')
    previous=control.get(first.KEY+':state',{})
    require(previous.get('status')=='failed' and previous.get('coordinator_call_id')==r.PARENT_CALL
            and control.get(first.KEY+':owner')==r.PARENT_CALL
            and control.get(first.KEY+':reservation',{}).get('freeze_sha256')==r.PARENT_FREEZE,
            'first recovery failure must remain retained')
    original=control.get('coordinator:development',{})
    require(original.get('status')=='failed' and original.get('coordinator_call_id')==r.ORIGINAL_CALL
            and original.get('error_type')=='KeyboardInterrupt'
            and control.get('coordinator:development:owner')==r.ORIGINAL_CALL,
            'original development failure must remain retained')
    smoke=control.get('coordinator:smoke',{});smoke_reservation=control.get('stage:smoke',{})
    development=control.get('stage:development',{})
    require(smoke.get('status')=='complete' and smoke.get('jobs_complete')==smoke_reservation.get('jobs')==65
            and development.get('jobs')==r.TOTAL,'earlier stage reservations differ')
    # Retry attempts count against capacity, never as extra scientific samples.
    count=65+r.TOTAL+r.RETRY_COUNT
    require(get_call is not None,'stage gate requires the terminal second recovery result reader')
    recovered=get_call(proof['call_id']).get(timeout=0)
    require(recovered.get('status')=='complete' and recovered.get('coordinator_call_id')==proof['call_id']
            and recovered.get('freeze_sha256')==proof['freeze_sha256']
            and recovered.get('jobs_complete')==r.RUN_COUNT
            and recovered.get('aggregate_sha256')==proof['aggregate_sha256'],
            'second recovery terminal result differs')
    development_freeze=freeze
    if name=='final':development_freeze=freeze['evidence']['previous_ops_freeze']['value']
    aggregate=development_freeze['evidence']['parent_status']['value']
    recovery_freeze=development_freeze['evidence']['recovery_freeze']['value']
    require(recovered.get('calls')=={n:aggregate['calls'][n] for n in recovery_freeze['run_ids']}
            and recovered.get('rows')=={n:aggregate['rows'][n] for n in recovery_freeze['run_ids']},
            'second recovery terminal rows differ from aggregate')
    if name=='final':
        previous=freeze['evidence']['previous_ops_freeze'];receipt=freeze['evidence']['previous_receipt']['value']
        reserved=control.get('stage:confirmation',{});state=control.get('coordinator:confirmation',{})
        expected=len(previous['value']['plan']['stage']['jobs'])
        require(reserved.get('ops_freeze_sha256')==previous['sha256'] and reserved.get('jobs')==expected
                and state.get('status')=='complete' and state.get('jobs_complete')==expected
                and state.get('coordinator_call_id')==receipt['coordinator_call_id']
                and state.get('stage_sha256')==receipt['stage_sha256'],'confirmation not complete or provenance differs')
        require(control.get('coordinator-receipt:confirmation')==receipt,'live confirmation receipt differs')
        require(get_call is not None,'final gate requires a terminal confirmation result reader')
        result=get_call(receipt['coordinator_call_id']).get(timeout=0)
        require(c.state_hash(result)==c.state_hash(freeze['evidence']['parent_status']['value']),
                'saved confirmation results differ from original terminal call')
        count+=expected
    require(count+len(plan['stage']['jobs'])<=plan['freeze']['campaign']['max_jobs']==18000,'campaign job cap exceeded')
    return count


def reserve(control,freeze,ops_hash,now=None,get_call=None):
    now=time.time() if now is None else now
    require(now<r.DEADLINE,'absolute campaign deadline expired');verify_parents(control,freeze,get_call)
    plan=freeze['plan'];name=plan['stage']['name']
    reservation={'campaign_id':plan['freeze']['campaign']['campaign_id'],'deadline_unix':r.DEADLINE,
                 'freeze_sha256':r.ORIGINAL_FREEZE,'ops_freeze_sha256':ops_hash,'stage':name,
                 'stage_sha256':plan['stage_sha256'],'jobs':len(plan['stage']['jobs']),'reserved_unix':now,
                 'recovery_aggregate_sha256':freeze['recovery_proof']['aggregate_sha256']}
    require(control.put('stage:'+name,reservation,skip_if_exists=True),'stage already reserved; never repeat')
    return reservation


def launch(freeze_path,receipt_path,root=ROOT,sdk=None,now=None):
    now=time.time() if now is None else now;freeze=c.read(freeze_path);validated=validate(freeze,root,now)
    ops_hash=c.digest(freeze_path);require(c.state_hash(freeze)==ops_hash,'published ops freeze bytes changed')
    plan=validated['plan'];name=plan['stage']['name'];sdk=sdk or m.sdk_module();receipt_path=Path(receipt_path)
    receipt={'schema':'learning-hybrid-receipt-v1','status':'preparing','stage':name,'freeze_sha256':r.ORIGINAL_FREEZE,
             'stage_sha256':plan['stage_sha256'],'ops_freeze_sha256':ops_hash,
             'campaign_id':plan['freeze']['campaign']['campaign_id'],'volume':c.VOLUME_NAME,'created_unix':now,
             'coordinator_call_id':None}
    receipt_path.parent.mkdir(parents=True,exist_ok=True)
    with receipt_path.open('x') as stream:json.dump(receipt,stream)
    try:
        control=sdk.Dict.from_name(c.CONTROL_NAME);volume=sdk.Volume.from_name(c.VOLUME_NAME)
        reader=getattr(getattr(sdk,'FunctionCall',None),'from_id',None)
        receipt['reservation']=reserve(control,freeze,ops_hash,now,get_call=reader);c.atomic(receipt_path,receipt)
        with tempfile.TemporaryDirectory(prefix='hybrid-gated-stage-') as temporary:
            m.copy_sources(plan,temporary,root)
            for filename,digest in freeze['ops_source_sha256'].items():
                source=ROOT/filename;require(c.digest(source)==digest,'ops code changed during snapshot')
                target=Path(temporary)/filename;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
            image=(sdk.Image.debian_slim(python_version='3.12').pip_install('torch==2.9.1',index_url=c.RUNTIME['torch_index'])
                   .pip_install('numpy==2.3.4').env({'PYTHONPATH':'/app','PYTHONDONTWRITEBYTECODE':'1',
                    'OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1'})
                   .add_local_dir(temporary,remote_path='/app',copy=True))
            app=sdk.App('junction-hybrid-gated2-'+name);options={'image':image,'cpu':(1,1),'memory':(2048,2048),
                'min_containers':0,'buffer_containers':0,'retries':0,'startup_timeout':120,'scaledown_window':10,
                'volumes':{'/results':volume},'serialized':True,'include_source':False}
            def worker_entry(value,job):
                from tools.learning_hybrid_ops.recovery2 import run_attempt_worker
                return run_attempt_worker(value,job,volume,control,attempt=name+'-ops2')
            worker=app.function(max_containers=64,timeout=180,nonpreemptible=True,**options)(worker_entry)
            def coordinator_entry(value,ops_freeze,hashed):
                from tools.learning_hybrid_ops.stages2 import run_stage
                return run_stage(value,ops_freeze,hashed,worker,volume,control)
            coordinator=app.function(max_containers=1,timeout=21720,nonpreemptible=True,**options)(coordinator_entry)
            with sdk.enable_output(),app.run(detach=True):
                require(time.time()<r.DEADLINE and not control.get('stop'),'campaign stopped or expired before spawn')
                receipt.update(status='launching',app_id=app.app_id,spawn_intent=True);c.atomic(receipt_path,receipt)
                call=coordinator.spawn(plan,freeze,ops_hash)
                receipt.update(status='submitted',spawn_intent=False,coordinator_call_id=call.object_id)
                control.put('coordinator-receipt:'+name,receipt);c.atomic(receipt_path,receipt)
        return receipt
    except BaseException as error:
        receipt.update(status='launch_error',error_type=type(error).__name__);c.atomic(receipt_path,receipt);raise


def run_stage(plan,freeze,ops_hash,worker,volume,control,*,root='/results',get_call=None):
    require(c.state_hash(freeze)==ops_hash and plan==freeze['plan'],'cloud operations freeze differs')
    require(freeze['ops_source_sha256']==sources(),'cloud operations source differs')
    import modal
    require(time.time()<r.DEADLINE,'campaign deadline expired')
    verify_parents(control,freeze,get_call or modal.FunctionCall.from_id)
    name=plan['stage']['name']
    require(control.get('stage:'+name,{}).get('ops_freeze_sha256')==ops_hash,'stage reservation differs')
    volume.reload();path=Path(root)/name/'ops-freeze.json'
    if path.exists():require(c.digest(path)==ops_hash,'retained operations freeze differs')
    else:c.atomic(path,freeze);volume.commit()
    state=c.coordinate(plan,worker,volume,control)
    if state['status']=='complete':verify_complete(plan['stage'],state)
    state['ops_freeze_sha256']=ops_hash
    state['attempt']=name+'-ops2'
    state['coordinator_compute_estimate_usd']=(state['ended_unix']-state['started_unix'])*3*c.RATE
    state['worker_compute_estimate_usd']=sum(row.get('running_compute_estimate_usd',0.) for row in state['rows'].values())
    state['worker_estimates_missing']=sum('running_compute_estimate_usd' not in row for row in state['rows'].values())
    state['budget_ledger']=freeze['budget_ledger']
    c.atomic(Path(root)/name/'state.json',state);volume.commit()
    control.put('coordinator:'+name,{k:v for k,v in state.items() if k not in ('calls','rows')})
    return state


def status(receipt_path,sdk=None):return m.status(receipt_path,sdk)


def download(receipt_path,output,artifacts=False,sdk=None):
    sdk=sdk or m.sdk_module();state=m.download(receipt_path,output,artifacts=False,sdk=sdk)
    receipt=c.read(receipt_path);output=Path(output);name=receipt['stage'];volume=sdk.Volume.from_name(c.VOLUME_NAME)
    def fetch(relative):
        path=output/relative
        require(not Path(relative).is_absolute() and path.resolve().is_relative_to(output.resolve()),'unsafe artifact path')
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b''.join(volume.read_file(relative)));return path
    path=fetch(name+'/ops-freeze.json')
    require(c.digest(path)==receipt['ops_freeze_sha256'],'downloaded operations freeze hash differs')
    require(state.get('ops_freeze_sha256')==receipt['ops_freeze_sha256']
            and c.state_hash(sdk.FunctionCall.from_id(receipt['coordinator_call_id']).get(timeout=0))==c.state_hash(state),
            'downloaded state differs from terminal original call')
    plan=c.read(output/name/'plan.json')
    require(plan==c.read(path)['plan'],'downloaded plan differs from operations freeze')
    complete={n:row for n,row in state['rows'].items() if row['status']=='complete'}
    r.verify_rows(complete,plan,{n:state['calls'][n] for n in complete},allowed_attempts={name+'-ops2'})
    require(all(row.get('storage',{}).get('attempt')==name+'-ops2' for row in complete.values()),'downloaded attempt differs')
    if artifacts:
        for job_id,call_id in state['calls'].items():
            saved=c.read(fetch(f'{name}/receipts/{job_id}.json'))
            require(saved['call_id']==call_id,'downloaded receipt differs')
        for row in complete.values():
            storage=row['storage']
            require(c.digest(fetch(row['artifact']))==row['sha256'],'downloaded case hash differs')
            require(c.digest(fetch(storage['raw_row']))==storage['raw_row_sha256'],'downloaded raw worker row hash differs')
            c.atomic(output/name/'mapped-rows'/(row['job_id']+'.json'),row)
    c.atomic(output/'download.json',{'artifacts':artifacts,'files':{str(p.relative_to(output)):c.digest(p)
                        for p in output.rglob('*') if p.is_file() and p.name!='download.json'}})
    return {'output':str(output),'stage':receipt['stage'],'status':state['status']}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);actions=parser.add_mutually_exclusive_group(required=True)
    for name in ('write-freeze','launch','status','download'):actions.add_argument('--'+name,type=Path)
    for name in ('master','stage','parent-stage','parent-status','parent-analysis','recovery-freeze','recovery-receipt',
                 'previous-ops-freeze','previous-receipt','receipt','output'):parser.add_argument('--'+name,type=Path)
    parser.add_argument('--root',type=Path,default=ROOT);parser.add_argument('--artifacts',action='store_true');args=parser.parse_args(argv)
    if args.write_freeze:
        required=('master','stage','parent_stage','parent_status','parent_analysis')
        require(all(getattr(args,k) is not None for k in required),'master/stage/preceding evidence paths required')
        value=write_freeze(args.write_freeze,**{k:getattr(args,k) for k in required+('recovery_freeze','recovery_receipt','previous_ops_freeze','previous_receipt')},root=args.root)
    elif args.launch:
        require(args.receipt is not None,'receipt required');value=launch(args.launch,args.receipt,args.root)
    elif args.status:value=status(args.status)
    else:
        require(args.output is not None,'output required');value=download(args.download,args.output,args.artifacts)
    print(json.dumps(value,sort_keys=True))


if __name__=='__main__':main()
