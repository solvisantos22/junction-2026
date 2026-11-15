"""One diagnosed continuation of the untouched hybrid development job suffix."""
from __future__ import annotations
import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import re
import tempfile
import time

from tools.learning_hybrid import cloud as c

ROOT=Path(__file__).resolve().parents[2]
OPS_FILE='tools/learning_hybrid_ops/recovery.py'
APP='junction-hybrid-development-recovery'
RECOVERY='development-recovery-1'
KEY='recovery:development:v1'
STAGE='development'
ORIGINAL_CALL='fc-01M7E75QF1581XG9HXNT3K0D5Q'
ORIGINAL_FREEZE='ff04b33503f212b2e855d5d0a5843457be01cb22396bd42d27cafc72bad8dab7'
ORIGINAL_STAGE='393bc398a52f86a00be9c9da56c2240b013c2ed175b2437428aeadbd59ea6b5a'
ORIGINAL_STAGE_STATE='89f9a05555cc27e712804773d8eeaf062aed13beb244d4e82bf8b71ef4df152f'
TOTAL=8320
RETAINED=3145
REMAINING=5175
DEADLINE=1794720600.0
RESOURCES={**c.RESOURCES,'coordinator_nonpreemptible':True,'coordinator_rate_multiplier':3,
           'coordinator_timeout_seconds':21720,'recovery_job_count':REMAINING}


def require(ok,message):
    if not ok:raise ValueError(message)


def guard_keys(name):
    return (f'intent:{STAGE}:{name}',f'call:{STAGE}:{name}',f'job:{STAGE}:{name}',
            f'job:{STAGE}:{name}:owner',f'job:{STAGE}:{name}:execution')


def control_keys(control):
    if not hasattr(control.keys,'aio'):return list(control.keys())
    async def collect():
        async with asyncio.timeout(300):return [key async for key in control.keys.aio()]
    return asyncio.run(collect())


def verify_rows(rows,plan,calls,jobs=None):
    jobs=jobs or {j['id']:j for j in plan['stage']['jobs']}
    require(set(rows)==set(calls) and len(set(calls.values()))==len(calls),'missing or duplicate completed calls')
    for name,row in rows.items():
        require(name in jobs,'unknown job')
        job={**jobs[name],'source_sha256':plan['freeze']['source_sha256']}
        require(row.get('status')=='complete' and row.get('id')==row.get('job_id')==name
                and row.get('stage')==STAGE
                and row.get('call_id')==calls[name] and row.get('job_sha256')==c.state_hash(job)
                and row.get('seed')==job['seed'] and row.get('spec_id')==job['spec']['id']
                and row.get('group')==job['spec']['group'],'completed row identity differs')
        require(row.get('artifact')==f'{STAGE}/jobs/{name}/case.json.gz'
                and all(isinstance(row.get(k),str) and re.fullmatch('[0-9a-f]{64}',row[k]) for k in ('sha256','case_sha256')),
                'artifact identity differs')
        require(row.get('error') is None and type(row.get('reward')) in (int,float) and math.isfinite(row['reward'])
                and 0<=row['reward']<=1 and type(row.get('home')) is bool and type(row.get('alive')) is bool
                and type(row.get('invalid_calls')) is int and row['invalid_calls']>=0,'outcome fields invalid')
        audit=row.get('audit') or {}
        require(audit.get('schema')=='learning-hybrid-case-audit-v1' and audit.get('job_id')==name
                and audit.get('physics_verified') is True and audit.get('case_sha256')==row.get('case_sha256')
                and audit.get('hybrid_choices_verified') is (job['spec']['id']!='beam'),'saved audit binding differs')


def validate(freeze,root=ROOT,*,check_sources=True,now=None):
    now=time.time() if now is None else now
    require(freeze.get('schema')=='learning-hybrid-recovery-freeze-v1' and freeze.get('recovery_id')==RECOVERY
            and freeze.get('resources')==RESOURCES and freeze.get('deadline_unix')==DEADLINE
            and freeze.get('runtime')==c.RUNTIME,'recovery identity/resources differ')
    require(freeze['created_unix']<=now<DEADLINE,'recovery deadline expired or future freeze')
    plan=freeze['original_plan'];base=freeze['retained_state']
    require(plan['freeze_sha256']==ORIGINAL_FREEZE and plan['stage_sha256']==ORIGINAL_STAGE
            and c.state_hash(plan['freeze'])==ORIGINAL_FREEZE
            and c.state_hash(plan['stage'])==freeze['stage_state_sha256']==ORIGINAL_STAGE_STATE,'original frozen plan differs')
    require(base['coordinator_call_id']==ORIGINAL_CALL and base['status']=='failed'
            and base['error_type']=='KeyboardInterrupt' and base['spawn_intent'] is None
            and base['freeze_sha256']==ORIGINAL_FREEZE and base['stage_sha256']==ORIGINAL_STAGE,
            'original failed coordinator identity differs')
    jobs=plan['stage']['jobs'];remaining=freeze['remaining_ids']
    require(len(jobs)==TOTAL and len({j['id'] for j in jobs})==TOTAL
            and len(base['rows'])==len(base['calls'])==RETAINED
            and set(base['calls'])=={j['id'] for j in jobs[:RETAINED]}
            and remaining==[j['id'] for j in jobs[RETAINED:]] and len(remaining)==REMAINING,
            'recovery must be exact never-launched suffix')
    require(c.state_hash(base)==freeze['retained_state_sha256'],'retained rows changed')
    verify_rows(base['rows'],plan,base['calls'])
    inventory=freeze['absence_proof']['keys']
    require(len(inventory)==len(set(inventory)) and c.state_hash(inventory)==freeze['absence_proof']['keys_sha256'],
            'absence inventory changed')
    present=set(inventory)
    require(not any(k in present for name in remaining for k in guard_keys(name)),'remaining job has prior execution evidence')
    rate=(c.MAX_CONTAINERS+3)*c.RATE
    require(math.isclose(freeze['remaining_allocation_envelope_usd'],(DEADLINE-freeze['created_unix'])*rate,
                         rel_tol=1e-12,abs_tol=1e-12)
            and freeze['remaining_allocation_envelope_usd']<=30,'recovery allocation bound differs')
    if check_sources:
        root=Path(root)
        from lightlag_hybrid.worker import source_manifest
        require(source_manifest(root)==plan['freeze']['source_sha256'],'protected source drift')
        require(c.digest(root/c.POLICY_FILE)==plan['freeze']['policy_freeze_sha256'],'protected policy drift')
        require(freeze['ops_sha256']==c.digest(__file__),'recovery code drift')
    return plan


def write_freeze(path,diagnosis,root=ROOT,now=None):
    now=time.time() if now is None else now;diagnosis=Path(diagnosis)
    plan=c.read(diagnosis/'plan.json');base=c.read(diagnosis/'reconciled-state.json')
    summary=c.read(diagnosis/'reconciliation.json');inventory=c.read(diagnosis/'control-key-inventory.json')
    require(summary['completed_audited']==RETAINED and summary['remaining_unlaunched']==REMAINING
            and not summary['remaining_control_key_collisions'] and summary['failed_workers']==0,
            'diagnosis not complete')
    freeze={'schema':'learning-hybrid-recovery-freeze-v1','recovery_id':RECOVERY,'created_unix':now,
            'deadline_unix':DEADLINE,'resources':RESOURCES,'runtime':c.RUNTIME,'original_plan':plan,
            'stage_state_sha256':c.state_hash(plan['stage']),'retained_state':base,
            'retained_state_sha256':c.state_hash(base),'remaining_ids':c.read(diagnosis/'remaining-job-ids.json'),
            'absence_proof':{**inventory,'keys_sha256':c.state_hash(inventory['keys'])},
            'ops_sha256':c.digest(__file__),
            'evidence_sha256':{name:c.digest(diagnosis/name) for name in ('state.json','coordinator-result.json','reconciled-state.json','reconciliation.json','control-key-inventory.json')},
            'remaining_allocation_envelope_usd':(DEADLINE-now)*(c.MAX_CONTAINERS+3)*c.RATE,
            'model_api_calls':0,'cost_note':'Remaining allocation ceiling includes 3x coordinator CPU/memory; excludes startup/build/storage/egress. Shared campaign cap remains $75; not an invoice.'}
    validate(freeze,root,now=now)
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as stream:stream.write(json.dumps(freeze,sort_keys=True,separators=(',',':'))+'\n')
    return {'freeze_sha256':c.digest(path),'retained':RETAINED,'remaining':REMAINING,
            'remaining_allocation_envelope_usd':freeze['remaining_allocation_envelope_usd']}


def reserve(control,freeze,freeze_sha256,now=None):
    now=time.time() if now is None else now
    require(now<DEADLINE and not control.get('stop'),'campaign stopped or expired')
    original=control.get('coordinator:'+STAGE,{})
    require(original.get('status')=='failed' and original.get('error_type')=='KeyboardInterrupt'
            and original.get('coordinator_call_id')==ORIGINAL_CALL and original.get('spawn_intent') is None
            and control.get('coordinator:'+STAGE+':owner')==ORIGINAL_CALL,'original coordinator state differs')
    require(control.get('campaign',{}).get('freeze_sha256')==ORIGINAL_FREEZE,'campaign source identity differs')
    present=set(control_keys(control))
    require(not any(k in present for name in freeze['remaining_ids'] for k in guard_keys(name)),
            'remaining jobs no longer unlaunched')
    require(time.time()<DEADLINE and not control.get('stop'),'campaign stopped or expired during inventory')
    reservation={'freeze_sha256':freeze_sha256,'recovery_id':RECOVERY,'deadline_unix':DEADLINE,
                 'reserved_unix':now,'retained_state_sha256':freeze['retained_state_sha256']}
    require(control.put(KEY+':reservation',reservation,skip_if_exists=True),'recovery already reserved; never repeat')
    return reservation


def coordinate(freeze,freeze_sha256,worker,volume,control,*,root='/results',call_id=None,
               clock=time.time,sleeper=time.sleep,get_call=None):
    import modal
    call_id=call_id or modal.current_function_call_id();get_call=get_call or modal.FunctionCall.from_id
    validate(freeze,Path('/app'),now=clock())
    require(c.state_hash(freeze)==freeze_sha256,'recovery freeze serialization differs')
    require(control.get(KEY+':reservation',{}).get('freeze_sha256')==freeze_sha256,'recovery reservation differs')
    control.put(KEY+':owner',call_id,skip_if_exists=True)
    require(control.get(KEY+':owner')==call_id,'recovery belongs to another call')
    volume.reload();folder=Path(root)/RECOVERY;state_path=folder/'state.json'
    if (folder/'freeze.json').exists():require(c.digest(folder/'freeze.json')==freeze_sha256,'saved recovery freeze differs')
    else:c.atomic(folder/'freeze.json',freeze)
    state=c.read(state_path) if state_path.exists() else {
        'schema':'learning-hybrid-recovery-state-v1','recovery_id':RECOVERY,'freeze_sha256':freeze_sha256,
        'coordinator_call_id':call_id,'status':'running','calls':{},'rows':{},'spawn_intent':None,
        'started_unix':clock(),'jobs_total':REMAINING,'original_state_sha256':freeze['evidence_sha256']['state.json']}
    require(state['freeze_sha256']==freeze_sha256 and state['coordinator_call_id']==call_id,'retained recovery identity differs')
    if state['status'] in c.TERMINAL:return state
    jobs={j['id']:j for j in freeze['original_plan']['stage']['jobs']};remaining=freeze['remaining_ids']
    worker_plan={'freeze':freeze['original_plan']['freeze'],'freeze_sha256':ORIGINAL_FREEZE,'stage':{'name':STAGE}}
    def persist():
        state['updated_unix']=clock();state['jobs_complete']=sum(r['status']=='complete' for r in state['rows'].values())
        c.atomic(state_path,state);volume.commit()
        control.put(KEY+':state',{k:v for k,v in state.items() if k not in ('calls','rows')})
    def aggregate():
        base=freeze['retained_state'];rows={**base['rows'],**state['rows']};calls={**base['calls'],**state['calls']}
        require(len(rows)==len(calls)==TOTAL and set(rows)==set(jobs),'aggregate incomplete')
        verify_rows(rows,freeze['original_plan'],calls)
        result={'schema':'learning-hybrid-stage-status-v1','stage':STAGE,'status':'complete',
                'freeze_sha256':ORIGINAL_FREEZE,'stage_sha256':ORIGINAL_STAGE,'coordinator_call_id':ORIGINAL_CALL,
                'calls':calls,'rows':rows,'jobs_total':TOTAL,'jobs_complete':TOTAL,'spawn_intent':None,
                'recovery_provenance':{'recovery_id':RECOVERY,'recovery_freeze_sha256':freeze_sha256,
                  'recovery_call_id':call_id,'original_state_sha256':freeze['evidence_sha256']['state.json'],
                  'retained_state_sha256':freeze['retained_state_sha256'],'original_status':'failed',
                  'original_error_type':'KeyboardInterrupt','retained_calls':RETAINED,'new_calls':REMAINING},
                'started_unix':base['started_unix'],'ended_unix':clock(),'updated_unix':clock()}
        c.atomic(folder/'aggregate-state.json',result);state['aggregate_sha256']=c.digest(folder/'aggregate-state.json')
    try:
        # Recover only saved handles; a handle-less intent is never resubmitted.
        for name in remaining:
            receipt=control.get(f'call:{STAGE}:{name}')
            if receipt:
                require(receipt['job_sha256']==c.state_hash(jobs[name]) and receipt.get('recovery_freeze_sha256')==freeze_sha256,
                        'saved receipt identity differs')
                state['calls'][name]=receipt['call_id'];c.atomic(folder/'receipts'/(name+'.json'),receipt)
            elif any(control.get(k) is not None for k in guard_keys(name)):
                raise ValueError('ambiguous prior execution requires diagnosis')
            else:break
        if state.get('spawn_intent') in state['calls']:state['spawn_intent']=None
        persist();transport_errors=0
        while state['status']=='running':
            if clock()>=DEADLINE or control.get('stop'):
                state['status']='stopped' if control.get('stop') else 'deadline';break
            pending=[n for n in state['calls'] if n not in state['rows']]
            unsent=[n for n in remaining if n not in state['calls']]
            failed=any(r['status']!='complete' for r in state['rows'].values())
            wave=[] if failed else unsent[:max(0,c.MAX_CONTAINERS-len(pending))]
            def clear(name):return not any(control.get(k) is not None for k in guard_keys(name))
            with ThreadPoolExecutor(max_workers=min(16,max(1,len(wave)))) as pool:
                require(all(pool.map(clear,wave)),'candidate has execution evidence')
            for name in wave:
                if clock()>=DEADLINE or control.get('stop'):break
                state['spawn_intent']=name
                require(control.put(f'intent:{STAGE}:{name}',{'job_sha256':c.state_hash(jobs[name]),
                        'recovery_freeze_sha256':freeze_sha256},skip_if_exists=True),'previous intent requires diagnosis')
                call=worker.spawn(worker_plan,{**jobs[name],'source_sha256':freeze['original_plan']['freeze']['source_sha256']})
                receipt={'job_id':name,'call_id':call.object_id,'job_sha256':c.state_hash(jobs[name]),'recovery_freeze_sha256':freeze_sha256}
                control.put(f'call:{STAGE}:{name}',receipt);state['calls'][name]=call.object_id;state['spawn_intent']=None
                c.atomic(folder/'receipts'/(name+'.json'),receipt);pending.append(name)
            persist()
            for name in pending:
                try:row=get_call(state['calls'][name]).get(timeout=0)
                except TimeoutError:continue
                except Exception as error:
                    if type(error).__name__ in ('ConnectionError','GRPCError','TransportError','StreamTerminatedError'):
                        transport_errors+=1;state['last_poll_error']={'type':type(error).__name__,'count':transport_errors}
                        if transport_errors>=10:raise
                        continue
                    row={'job_id':name,'call_id':state['calls'][name],'status':'failed','error_type':type(error).__name__}
                require(row.get('job_id')==name and row.get('call_id')==state['calls'][name],'worker receipt mismatch')
                if row.get('status')=='complete':verify_rows({name:row},freeze['original_plan'],{name:state['calls'][name]},jobs)
                state['rows'][name]=row
            if len(state['rows'])==REMAINING:
                state['status']='complete' if all(r['status']=='complete' for r in state['rows'].values()) else 'failed'
                if state['status']=='complete':aggregate()
            elif any(r['status']!='complete' for r in state['rows'].values()) and len(state['rows'])==len(state['calls']):
                state.update(status='failed',error_type='JobFailureRequiresDiagnosis')
            persist()
            if state['status']=='running':sleeper(2)
        if state['status'] in ('deadline','stopped'):
            for name,identifier in state['calls'].items():
                if name not in state['rows']:
                    try:get_call(identifier).cancel()
                    except Exception:pass
    except BaseException as error:
        import traceback
        state.update(status='failed',error_type=type(error).__name__,traceback=traceback.format_exc()[-12000:])
    finally:
        state['ended_unix']=clock();state['coordinator_compute_estimate_usd']=(state['ended_unix']-state['started_unix'])*3*c.RATE;persist()
    return state


def sdk_module():
    require(os.environ.get('MODAL_PROFILE')==c.PROFILE,'explicit solvi-junction profile required')
    from importlib.metadata import version
    require(version('modal')==c.RUNTIME['modal'],'Modal SDK drift')
    import modal
    return modal


def launch(freeze_path,receipt_path,root=ROOT,sdk=None,now=None):
    now=time.time() if now is None else now;freeze=c.read(freeze_path);validate(freeze,root,now=now)
    hashed=c.digest(freeze_path);require(c.state_hash(freeze)==hashed,'freeze must retain canonical published bytes')
    sdk=sdk or sdk_module();receipt_path=Path(receipt_path)
    receipt={'schema':'learning-hybrid-recovery-receipt-v1','recovery_id':RECOVERY,'status':'preparing',
             'freeze_sha256':hashed,'original_freeze_sha256':ORIGINAL_FREEZE,'volume':c.VOLUME_NAME,'created_unix':now}
    receipt_path.parent.mkdir(parents=True,exist_ok=True)
    with receipt_path.open('x') as stream:json.dump(receipt,stream)
    try:
        control=sdk.Dict.from_name(c.CONTROL_NAME);volume=sdk.Volume.from_name(c.VOLUME_NAME)
        receipt['reservation']=reserve(control,freeze,hashed,now);c.atomic(receipt_path,receipt)
        with tempfile.TemporaryDirectory(prefix='hybrid-recovery-source-') as directory:
            destination=Path(directory);expected={**freeze['original_plan']['freeze']['source_sha256'],
                                                  c.POLICY_FILE:freeze['original_plan']['freeze']['policy_freeze_sha256']}
            for name,digest in expected.items():
                source=Path(root)/name;require(c.digest(source)==digest and not source.is_symlink(),'protected image source differs')
                target=destination/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
            target=destination/OPS_FILE;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(__file__,target)
            require(c.digest(target)==freeze['ops_sha256'],'ops source changed during snapshot')
            image=(sdk.Image.debian_slim(python_version='3.12').pip_install('torch==2.9.1',index_url=c.RUNTIME['torch_index'])
                   .pip_install('numpy==2.3.4').env({'PYTHONPATH':'/app','PYTHONDONTWRITEBYTECODE':'1',
                    'OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1'})
                   .add_local_dir(directory,remote_path='/app',copy=True))
            app=sdk.App(APP);options={'image':image,'cpu':(1,1),'memory':(2048,2048),'min_containers':0,
                'buffer_containers':0,'retries':0,'startup_timeout':120,'scaledown_window':10,
                'volumes':{'/results':volume},'serialized':True,'include_source':False}
            def worker_entry(plan,job):
                from tools.learning_hybrid.cloud import run_worker
                return run_worker(plan,job,volume,control)
            worker=app.function(max_containers=64,timeout=180,**options)(worker_entry)
            def coordinator_entry(value,value_hash):
                from tools.learning_hybrid_ops.recovery import coordinate
                return coordinate(value,value_hash,worker,volume,control)
            coordinator=app.function(max_containers=1,timeout=21720,nonpreemptible=True,**options)(coordinator_entry)
            with sdk.enable_output(),app.run(detach=True):
                receipt.update(status='launching',app_id=app.app_id);c.atomic(receipt_path,receipt)
                receipt['spawn_intent']=True;c.atomic(receipt_path,receipt)
                call=coordinator.spawn(freeze,hashed)
                receipt.update(status='submitted',spawn_intent=False,coordinator_call_id=call.object_id)
                control.put(KEY+':receipt',receipt);c.atomic(receipt_path,receipt)
        return receipt
    except BaseException as error:
        receipt.update(status='launch_error',error_type=type(error).__name__);c.atomic(receipt_path,receipt);raise


def status(receipt_path,sdk=None):
    sdk=sdk or sdk_module();receipt=c.read(receipt_path)
    require(receipt['schema']=='learning-hybrid-recovery-receipt-v1' and receipt['recovery_id']==RECOVERY,'invalid recovery receipt')
    control=sdk.Dict.from_name(c.CONTROL_NAME)
    require(control.get(KEY+':reservation',{}).get('freeze_sha256')==receipt['freeze_sha256'],'recovery reservation differs')
    state=control.get(KEY+':state',{'status':'pending'})
    if receipt.get('coordinator_call_id'):
        try:state=sdk.FunctionCall.from_id(receipt['coordinator_call_id']).get(timeout=0)
        except TimeoutError:pass
        except Exception as error:state={**state,'poll_error_type':type(error).__name__}
    return {'schema':'learning-hybrid-monitor-v1','receipt_sha256':c.digest(receipt_path),'stage':RECOVERY,
            'stop_marker':bool(control.get('stop')),'state':state}


def download(receipt_path,output,sdk=None):
    sdk=sdk or sdk_module();observed=status(receipt_path,sdk);root=Path(output);root.mkdir(parents=True,exist_ok=False)
    volume=sdk.Volume.from_name(c.VOLUME_NAME)
    c.atomic(root/'receipt.json',c.read(receipt_path));c.atomic(root/'status.json',observed)
    for name in ['freeze.json','state.json']+(['aggregate-state.json'] if observed['state'].get('status')=='complete' else []):
        data=b''.join(volume.read_file(RECOVERY+'/'+name));path=root/name;path.write_bytes(data)
        value=json.loads(data)
        if name=='freeze.json':require(c.digest(path)==c.read(receipt_path)['freeze_sha256'],'downloaded freeze hash differs')
        elif name=='aggregate-state.json':require(c.digest(path)==observed['state']['aggregate_sha256'],'aggregate download hash differs')
        else:require(value['freeze_sha256']==c.read(receipt_path)['freeze_sha256'],'downloaded recovery identity differs')
    return {'output':str(root),'status':observed['state'].get('status')}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);mode=parser.add_mutually_exclusive_group(required=True)
    for flag in ('write-freeze','launch','status','download'):mode.add_argument('--'+flag,type=Path)
    parser.add_argument('--diagnosis',type=Path);parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--receipt',type=Path);parser.add_argument('--output',type=Path);args=parser.parse_args(argv)
    if args.write_freeze:
        require(args.diagnosis is not None,'--diagnosis required');value=write_freeze(args.write_freeze,args.diagnosis,args.root)
    elif args.launch:
        require(args.receipt is not None,'--receipt required');value=launch(args.launch,args.receipt,args.root)
    elif args.status:value=status(args.status)
    else:
        require(args.output is not None,'--output required');value=download(args.download,args.output)
    print(json.dumps(value,sort_keys=True))


if __name__=='__main__':main()
