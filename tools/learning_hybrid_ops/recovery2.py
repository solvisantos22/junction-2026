"""Deliberate, separate attempts after two diagnosed infrastructure interruptions."""
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
from tools.learning_hybrid_ops import recovery as old

ROOT=Path(__file__).resolve().parents[2]
OPS_FILE='tools/learning_hybrid_ops/recovery2.py'
OPS_FILES=(old.OPS_FILE,OPS_FILE)
APP='junction-hybrid-development-recovery2'
RECOVERY='development-recovery-2'
KEY='recovery:development:v2'
STAGE='development'
ORIGINAL_CALL='fc-01M7E75QF1581XG9HXNT3K0D5Q'
ORIGINAL_FREEZE='ff04b33503f212b2e855d5d0a5843457be01cb22396bd42d27cafc72bad8dab7'
ORIGINAL_STAGE='393bc398a52f86a00be9c9da56c2240b013c2ed175b2437428aeadbd59ea6b5a'
ORIGINAL_STAGE_STATE='89f9a05555cc27e712804773d8eeaf062aed13beb244d4e82bf8b71ef4df152f'
TOTAL=8320
RETAINED=5810
RUN_COUNT=2510
RETRY_COUNT=2
NEW_COUNT=2508
PARENT_FREEZE='4c1c1d16cd54c754a81f7d1b984d4ed187706e6e41fd3c1068639819ee40906a'
PARENT_CALL='fc-01M7EB3DJ8C214Z7E14WCVVTNF'
PARENT_APP='ap-VMFyA1rZFxPhVr14SGth33'
PARENT_STATE_SHA256='ed946001ca0df00c8654e6453830441d955d44cdc2704d915ee6ac9fd96802f1'
FAILED_CALLS={'development-single-replay-17-rho095-610087':'fc-01M7EC2FSFHY4RVFKPMFPWH11S',
              'development-ensemble-replay-rho050-610088':'fc-01M7EC3M1P2T01C014NP812N1S'}
DEADLINE=1794720600.0
RESOURCES={**c.RESOURCES,'worker_nonpreemptible':True,'coordinator_nonpreemptible':True,
           'worker_rate_multiplier':3,'coordinator_rate_multiplier':3,
           'coordinator_timeout_seconds':21720,'recovery_job_count':RUN_COUNT,'max_campaign_attempts':18000}
DISCLOSURE='Two terminal failed attempts may have lost uncommitted computation. No committed completed result is repeated; all old attempts remain unchanged.'


def require(ok,message):
    if not ok:raise ValueError(message)


def guard_keys(name):return old.guard_keys(name)


def attempt_guard_keys(name,attempt=RECOVERY):
    worker=f'attempt:{attempt}:job:{STAGE}:{name}'
    return (KEY+':intent:'+name,KEY+':call:'+name,worker,worker+':owner',worker+':execution')


def control_keys(control):
    if not hasattr(control.keys,'aio'):return list(control.keys())
    async def collect():
        async with asyncio.timeout(300):return [key async for key in control.keys.aio()]
    return asyncio.run(collect())


class AttemptControl:
    """Expose only worker-local keys and the unchanged global stop marker."""
    def __init__(self,control,attempt,stage,job_id):
        self.control=control;self.attempt=attempt;self.base=f'job:{stage}:{job_id}'
    def key(self,key):
        if key=='stop':return key
        require(key in (self.base,self.base+':owner',self.base+':execution'),'unexpected worker control key')
        return f'attempt:{self.attempt}:'+key
    def get(self,key,default=None):return self.control.get(self.key(key),default)
    def put(self,key,value,skip_if_exists=False):
        require(key!='stop','worker cannot mutate global stop')
        return self.control.put(self.key(key),value,skip_if_exists=skip_if_exists)


def run_attempt_worker(plan,job,volume,control,*,attempt,root='/results',call_id=None,clock=time.time):
    expected={RECOVERY:'development','confirmation-ops2':'confirmation','final-ops2':'final'}
    require(attempt in expected and plan['stage']['name']==job['stage']==expected[attempt],'invalid attempt stage')
    volume.reload();original=Path(root)/job['stage']/'jobs'/job['id']
    require(not any((original/name).exists() for name in ('case.json.gz','case.json.gz.tmp','row.json.tmp')),
            'original completed or in-flight artifact exists; do not repeat')
    if attempt==RECOVERY:
        reservation=control.get(KEY+':reservation',{});intent=control.get(KEY+':intent:'+job['id'],{})
        compact={k:v for k,v in job.items() if k!='source_sha256'}
        require(reservation.get('freeze_sha256')==plan.get('attempt_freeze_sha256') is not None
                and intent.get('recovery_freeze_sha256')==reservation['freeze_sha256']
                and intent.get('job_sha256')==c.state_hash(compact),'worker admission differs')
        if job['id'] in FAILED_CALLS:
            row=c.read(original/'row.json');key=f'job:{STAGE}:{job["id"]}'
            require(row==control.get(key) and row.get('status')=='failed' and row.get('reward') is None
                    and row.get('audit') is None and row.get('call_id')==FAILED_CALLS[job['id']]
                    and control.get(key+':owner')==FAILED_CALLS[job['id']]
                    and control.get(key+':execution',{}).get('call_id')==FAILED_CALLS[job['id']],
                    'original failed worker identity differs')
        else:
            require(not (original/'row.json').exists()
                    and all(control.get(k) is None for k in guard_keys(job['id'])),
                    'original job has already started; do not repeat')
    else:
        key=f'job:{job["stage"]}:{job["id"]}'
        require(not (original/'row.json').exists() and all(control.get(k) is None for k in (key,key+':owner',key+':execution')),
                'original stage worker has already started')
    raw=c.run_worker(plan,job,volume,AttemptControl(control,attempt,job['stage'],job['id']),
                     root=Path(root)/attempt/'artifacts',call_id=call_id,clock=clock)
    prefix=attempt+'/artifacts/';artifact=prefix+raw['artifact']
    result={**raw,'artifact':artifact,'running_compute_estimate_usd':3*raw['running_compute_estimate_usd'],
            'allocation_rate_multiplier':3,
            'storage':{'volume':c.VOLUME_NAME,'artifact':artifact,
                       'raw_row':prefix+f'{job["stage"]}/jobs/{job["id"]}/row.json',
                       'raw_row_sha256':c.state_hash(raw),'original_artifact':raw['artifact'],
                       'raw_running_compute_estimate_usd':raw['running_compute_estimate_usd'],'attempt':attempt}}
    return result


def verify_rows(rows,plan,calls,allowed_attempts=None):
    jobs={j['id']:j for j in plan['stage']['jobs']};stage=plan['stage']['name']
    require(set(rows)==set(calls) and len(set(calls.values()))==len(calls),'missing or duplicate completed calls')
    for name,original in rows.items():
        row=dict(original);storage=row.pop('storage',None)
        if storage is not None:
            attempt=storage.get('attempt');require(attempt in (allowed_attempts or set()),'unapproved attempt storage')
            require({RECOVERY:'development','confirmation-ops2':'confirmation','final-ops2':'final'}.get(attempt)==stage,
                    'attempt stage differs')
            prefix=attempt+'/artifacts/';raw_artifact=f'{stage}/jobs/{name}/case.json.gz'
            require(storage.get('volume')==c.VOLUME_NAME and storage.get('artifact')==row['artifact']==prefix+raw_artifact
                    and storage.get('original_artifact')==raw_artifact
                    and storage.get('raw_row')==prefix+f'{stage}/jobs/{name}/row.json'
                    and row.pop('allocation_rate_multiplier',None)==3,'attempt storage mapping differs')
            raw_cost=storage.get('raw_running_compute_estimate_usd')
            require(type(raw_cost) in (float,int) and math.isfinite(raw_cost) and raw_cost>=0
                    and math.isclose(row['running_compute_estimate_usd'],3*raw_cost,rel_tol=1e-12),'attempt cost differs')
            row.update(artifact=raw_artifact,running_compute_estimate_usd=raw_cost)
            require(c.state_hash(row)==storage.get('raw_row_sha256'),'raw row identity differs')
        require(name in jobs,'unknown job');job={**jobs[name],'source_sha256':plan['freeze']['source_sha256']}
        require(row.get('status')=='complete' and row.get('id')==row.get('job_id')==name
                and row.get('stage')==stage and row.get('call_id')==calls[name]
                and row.get('job_sha256')==c.state_hash(job) and row.get('seed')==job['seed']
                and row.get('spec_id')==job['spec']['id'] and row.get('group')==job['spec']['group'],
                'completed row identity differs')
        require(row.get('artifact')==f'{stage}/jobs/{name}/case.json.gz'
                and all(isinstance(row.get(k),str) and re.fullmatch('[0-9a-f]{64}',row[k]) for k in ('sha256','case_sha256')),
                'artifact identity differs')
        require(row.get('error') is None and type(row.get('reward')) in (int,float) and math.isfinite(row['reward'])
                and 0<=row['reward']<=1 and type(row.get('home')) is bool and type(row.get('alive')) is bool
                and type(row.get('invalid_calls')) is int and row['invalid_calls']>=0,'outcome fields invalid')
        audit=row.get('audit') or {}
        require(audit.get('schema')=='learning-hybrid-case-audit-v1' and audit.get('job_id')==name
                and audit.get('physics_verified') is True and audit.get('case_sha256')==row.get('case_sha256')
                and audit.get('hybrid_choices_verified') is (job['spec']['id']!='beam')
                and (stage!='final' or audit.get('full_controller_replay') is True),'saved audit binding differs')


def budget_ledger(master,created_unix):
    require(master['created_unix']<=created_unix<DEADLINE,'invalid allocation time basis')
    prior=9.092736;past=(created_unix-master['created_unix'])*67*c.RATE
    future_rate=65*3*c.RATE;future=(DEADLINE-created_unix)*future_rate
    return {'cap_usd':75,'basis_created_unix':created_unix,'deadline_unix':DEADLINE,
            'previous_training_allocation_bound_usd':prior,'previous_hybrid_allocation_bound_usd':past,
            'future_rate_per_second':future_rate,'future_allocation_envelope_usd':future,
            'total_running_allocation_bound_usd':prior+past+future,
            'exclusions':'Build/startup/storage/egress and platform scheduling overlap are ancillary; this is a running allocation estimate, not an invoice.'}


def aggregate_provenance(freeze,freeze_sha256,call_id):
    return {'recovery_id':RECOVERY,'recovery_freeze_sha256':freeze_sha256,'recovery_call_id':call_id,
            'original_freeze_sha256':ORIGINAL_FREEZE,'original_stage_sha256':ORIGINAL_STAGE,
            'original_coordinator_call_id':ORIGINAL_CALL,'parent_recovery_freeze_sha256':PARENT_FREEZE,
            'parent_recovery_state_sha256':PARENT_STATE_SHA256,'retained_state_sha256':freeze['retained_state_sha256'],
            'retained_calls':RETAINED,'new_calls':RUN_COUNT,'retried_failed_calls':RETRY_COUNT,
            'never_started_calls':NEW_COUNT,'failed_attempts_sha256':c.state_hash(freeze['failed_attempts']),
            'storage_prefix':RECOVERY+'/artifacts','disclosure':DISCLOSURE}


def source_context(root):
    from lightlag_hybrid import worker,policy
    root=Path(root).resolve()
    require(root==ROOT.resolve() and all(Path(module.__file__).resolve().is_relative_to(root)
            for module in (c,old,worker,policy)),
            'execute recovery2 from the frozen snapshot; --root does not redirect imports')


def validate(freeze,root=ROOT,*,check_sources=True,now=None):
    now=time.time() if now is None else now
    require(freeze.get('schema')=='learning-hybrid-recovery2-freeze-v1' and freeze.get('recovery_id')==RECOVERY
            and freeze.get('resources')==RESOURCES and freeze.get('deadline_unix')==DEADLINE
            and freeze.get('runtime')==c.RUNTIME,'recovery identity/resources differ')
    require(freeze['created_unix']<=now<DEADLINE,'recovery deadline expired or future freeze')
    plan=freeze['original_plan'];base=freeze['retained_state'];parent=freeze['parent_recovery_state'];prior=freeze['parent_recovery_freeze']
    require(plan['freeze_sha256']==ORIGINAL_FREEZE and c.state_hash(plan['freeze'])==ORIGINAL_FREEZE
            and plan['stage_sha256']==ORIGINAL_STAGE and c.state_hash(plan['stage'])==ORIGINAL_STAGE_STATE,
            'original frozen plan differs')
    require(c.state_hash(prior)==PARENT_FREEZE and c.state_hash(parent)==PARENT_STATE_SHA256
            and prior['original_plan']==plan and parent['freeze_sha256']==PARENT_FREEZE
            and parent['coordinator_call_id']==PARENT_CALL and parent['status']=='failed'
            and parent['spawn_intent'] is None and set(parent['rows'])==set(parent['calls']),
            'failed parent lineage differs')
    original=prior['retained_state'];complete={k:v for k,v in parent['rows'].items() if v['status']=='complete'}
    failed={k:v for k,v in parent['rows'].items() if v['status']!='complete'}
    require(set(failed)==set(FAILED_CALLS) and {k:parent['calls'][k] for k in failed}==FAILED_CALLS,
            'failed attempts differ')
    require(not set(original['rows'])&set(parent['rows']) and
            base['rows']=={**original['rows'],**complete} and
            base['calls']=={**original['calls'],**{k:parent['calls'][k] for k in complete}}
            and c.state_hash(base)==freeze['retained_state_sha256'] and len(base['rows'])==RETAINED,
            'retained completed rows changed')
    verify_rows(base['rows'],plan,base['calls'])
    jobs=plan['stage']['jobs'];ids=[j['id'] for j in jobs];remaining=freeze['remaining_ids'];retry=freeze['retry_ids']
    require(len(ids)==len(set(ids))==TOTAL and len(remaining)==NEW_COUNT and len(retry)==RETRY_COUNT
            and retry==[name for name in ids if name in failed]
            and remaining==[name for name in ids if name not in base['calls'] and name not in failed]
            and freeze['run_ids']==[name for name in ids if name not in base['calls']]
            and len(freeze['run_ids'])==RUN_COUNT and TOTAL+RETRY_COUNT+65+5376+2560<=18000,
            'recovery attempt matrix differs')
    attempts={v['job_id']:v for v in freeze['failed_attempts']}
    proof=freeze['quiescence'];rechecks={v['job_id']:v for v in proof['stable_rechecks']}
    outputs={v['call_id']:v for v in proof['terminal_output_metadata']}
    require(set(attempts)==set(failed) and set(rechecks)==set(failed),'failed proof matrix differs')
    for name,row in failed.items():
        entry=attempts[name];check=rechecks[name];ctrl=entry['control']
        require(entry['function_result']==row==ctrl[f'job:{STAGE}:{name}']
                and entry['call_id']==FAILED_CALLS[name]==ctrl[f'job:{STAGE}:{name}:owner']
                and ctrl[f'job:{STAGE}:{name}:execution']['call_id']==FAILED_CALLS[name]
                and row.get('reward') is None and row.get('audit') is None
                and entry['files']['case.json.gz']['status']=='missing'
                and entry['files']['row.json']['sha256']==check['row_sha256']==c.state_hash(row),
                'failed row evidence differs')
        require(check['result_unchanged'] and check['row_unchanged'] and not check['case_present']
                and check['elapsed_since_execution_marker']>180 and check['elapsed_since_first_read']>=60
                and outputs[FAILED_CALLS[name]]['num_unfinished_inputs']==0
                and [v['path'] for v in proof['failed_folder_inventory']['folders'][name]]==[f'{STAGE}/jobs/{name}/row.json'],
                'failed attempt not proven quiescent')
    apps=proof['app_status'];match=[v for v in apps if v.get('App ID')==PARENT_APP or v.get('app_id')==PARENT_APP]
    require(len(match)==1 and str(match[0].get('State',match[0].get('state'))).lower()=='stopped'
            and int(match[0].get('Tasks',match[0].get('tasks',-1)))==0,'parent app not stopped')
    inventory=freeze['absence_proof']['keys'];present=set(inventory)
    require(len(inventory)==len(present) and c.state_hash(inventory)==freeze['absence_proof']['keys_sha256'],
            'absence inventory changed')
    require(not any(k in present for name in remaining for k in guard_keys(name))
            and not any(k in present for name in freeze['run_ids'] for k in attempt_guard_keys(name)),
            'new candidate has execution evidence')
    ledger=budget_ledger(plan['freeze'],freeze['created_unix'])
    require(freeze['budget_ledger']==ledger and ledger['total_running_allocation_bound_usd']<=75,'allocation bound differs')
    if check_sources:
        source_context(root)
        root=Path(root)
        from lightlag_hybrid.worker import source_manifest
        require(source_manifest(root)==plan['freeze']['source_sha256'],'protected source drift')
        require(c.digest(root/c.POLICY_FILE)==plan['freeze']['policy_freeze_sha256'],'protected policy drift')
        require(freeze['ops_source_sha256']=={name:c.digest(root/name) for name in OPS_FILES},'ops source drift')
        require(c.digest(__file__)==freeze['ops_source_sha256'][OPS_FILE]
                and c.digest(old.__file__)==freeze['ops_source_sha256'][old.OPS_FILE]
                and c.digest(c.__file__)==plan['freeze']['source_sha256']['tools/learning_hybrid/cloud.py'],
                'executing imports differ from frozen snapshot')
    return plan


def write_freeze(path,diagnosis,root=ROOT,now=None,app_status=None):
    now=time.time() if now is None else now;diagnosis=Path(diagnosis);root=Path(root)
    require(app_status is not None,'--app-status terminal snapshot required')
    prior=c.read(diagnosis/'freeze.json');parent=c.read(diagnosis/'state.json');plan=prior['original_plan']
    original=prior['retained_state'];complete={k:v for k,v in parent['rows'].items() if v['status']=='complete'}
    retained={**original,'rows':{**original['rows'],**complete},
              'calls':{**original['calls'],**{k:parent['calls'][k] for k in complete}}}
    inventory=c.read(diagnosis/'control-key-inventory.json');failed=c.read(diagnosis/'failed-evidence.json')
    names=('diagnosis.json','failed-evidence.json','stable-failure-recheck.json','failed-folder-inventory.json',
           'terminal-output-metadata.json','control-key-inventory.json','state.json','freeze.json','receipt.json')
    freeze={'schema':'learning-hybrid-recovery2-freeze-v1','recovery_id':RECOVERY,'created_unix':now,
            'deadline_unix':DEADLINE,'resources':RESOURCES,'runtime':c.RUNTIME,'original_plan':plan,
            'parent_recovery_freeze':prior,'parent_recovery_state':parent,'parent_recovery_receipt':c.read(diagnosis/'receipt.json'),
            'retained_state':retained,'retained_state_sha256':c.state_hash(retained),'failed_attempts':failed,
            'remaining_ids':c.read(diagnosis/'remaining-job-ids.json'),
            'retry_ids':[j['id'] for j in plan['stage']['jobs'] if j['id'] in FAILED_CALLS],
            'run_ids':[j['id'] for j in plan['stage']['jobs'] if j['id'] not in retained['calls']],
            'absence_proof':{**inventory,'keys_sha256':c.state_hash(inventory['keys'])},
            'quiescence':{'stable_rechecks':c.read(diagnosis/'stable-failure-recheck.json'),
                          'terminal_output_metadata':c.read(diagnosis/'terminal-output-metadata.json'),
                          'failed_folder_inventory':c.read(diagnosis/'failed-folder-inventory.json'),
                          'app_status':c.read(app_status)},
            'ops_source_sha256':{name:c.digest(root/name) for name in OPS_FILES},
            'evidence_sha256':{**{name:c.digest(diagnosis/name) for name in names},'app_status.json':c.digest(app_status)},
            'budget_ledger':budget_ledger(plan['freeze'],now),'model_api_calls':0,'disclosure':DISCLOSURE}
    validate(freeze,root,now=now);path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as stream:stream.write(json.dumps(freeze,sort_keys=True,separators=(',',':'))+'\n')
    return {'freeze_sha256':c.digest(path),'retained':RETAINED,'new_attempts':RUN_COUNT,'retried_failed':RETRY_COUNT,
            'never_started':NEW_COUNT,'budget_ledger':freeze['budget_ledger']}


def verify_parents(control,freeze,get_call=None):
    original=control.get('coordinator:'+STAGE,{})
    require(not control.get('stop') and original.get('status')=='failed' and original.get('error_type')=='KeyboardInterrupt'
            and original.get('coordinator_call_id')==ORIGINAL_CALL and original.get('spawn_intent') is None
            and control.get('coordinator:'+STAGE+':owner')==ORIGINAL_CALL,'original coordinator state differs or stopped')
    parent=control.get(old.KEY+':state',{})
    require(parent.get('status')=='failed' and parent.get('coordinator_call_id')==PARENT_CALL
            and parent.get('freeze_sha256')==PARENT_FREEZE and parent.get('jobs_complete')==RETAINED-old.RETAINED
            and control.get(old.KEY+':owner')==PARENT_CALL
            and control.get(old.KEY+':receipt')==freeze['parent_recovery_receipt'], 'parent live state differs')
    require(control.get('campaign',{}).get('freeze_sha256')==ORIGINAL_FREEZE,'campaign source identity differs')
    for entry in freeze['failed_attempts']:
        require(all(control.get(k)==v for k,v in entry['control'].items()),'old failed attempt changed')
    if get_call is not None:
        require(c.state_hash(get_call(PARENT_CALL).get(timeout=0))==PARENT_STATE_SHA256,'terminal parent result changed')


def verify_failed_artifacts(volume,freeze):
    for entry in freeze['failed_attempts']:
        prefix=f'{STAGE}/jobs/{entry["job_id"]}/'
        require(json.loads(b''.join(volume.read_file(prefix+'row.json')))==entry['function_result'],
                'original failed row bytes changed')
        for name in ('case.json.gz','case.json.gz.tmp','row.json.tmp'):
            try:next(iter(volume.read_file(prefix+name)),b'')
            except FileNotFoundError:pass
            else:raise ValueError('original completed or in-flight artifact appeared; do not repeat')



def reserve(control,freeze,freeze_sha256,now=None,get_call=None,volume=None):
    now=time.time() if now is None else now
    require(now<DEADLINE and not control.get('stop'),'campaign stopped or expired')
    require(get_call is not None and volume is not None,'live parent and volume readers required')
    verify_parents(control,freeze,get_call)
    present=set(control_keys(control))
    require(not any(k in present for name in freeze['remaining_ids'] for k in guard_keys(name))
            and not any(k in present for name in freeze['run_ids'] for k in attempt_guard_keys(name)),
            'new jobs no longer unlaunched')
    require(time.time()<DEADLINE and not control.get('stop'),'campaign stopped or expired during inventory')
    verify_failed_artifacts(volume,freeze)
    for entry in freeze['failed_attempts']:
        require(get_call(entry['call_id']).get(timeout=0)==entry['function_result'],'failed call result changed')
    require(time.time()<DEADLINE and not control.get('stop'),'campaign stopped or expired before reservation')
    reservation={'freeze_sha256':freeze_sha256,'recovery_id':RECOVERY,'deadline_unix':DEADLINE,
                 'reserved_unix':now,'retained_state_sha256':freeze['retained_state_sha256'],'budget_ledger':freeze['budget_ledger']}
    require(control.put(KEY+':reservation',reservation,skip_if_exists=True),'recovery already reserved; never repeat')
    return reservation



def coordinate(freeze,freeze_sha256,worker,volume,control,*,root='/results',call_id=None,
               clock=time.time,sleeper=time.sleep,get_call=None):
    import modal
    call_id=call_id or modal.current_function_call_id();get_call=get_call or modal.FunctionCall.from_id
    validate(freeze,Path('/app'),now=clock())
    require(c.state_hash(freeze)==freeze_sha256,'recovery freeze serialization differs')
    require(control.get(KEY+':reservation',{}).get('freeze_sha256')==freeze_sha256,'recovery reservation differs')
    verify_parents(control,freeze,get_call)
    control.put(KEY+':owner',call_id,skip_if_exists=True)
    require(control.get(KEY+':owner')==call_id,'recovery belongs to another call')
    volume.reload();folder=Path(root)/RECOVERY;state_path=folder/'state.json'
    if (folder/'freeze.json').exists():require(c.digest(folder/'freeze.json')==freeze_sha256,'saved recovery freeze differs')
    else:c.atomic(folder/'freeze.json',freeze)
    state=c.read(state_path) if state_path.exists() else {
        'schema':'learning-hybrid-recovery2-state-v1','recovery_id':RECOVERY,'freeze_sha256':freeze_sha256,
        'coordinator_call_id':call_id,'status':'running','calls':{},'rows':{},'spawn_intent':None,
        'started_unix':clock(),'jobs_total':RUN_COUNT,'parent_state_sha256':PARENT_STATE_SHA256}
    require(state['freeze_sha256']==freeze_sha256 and state['coordinator_call_id']==call_id,'retained recovery identity differs')
    if state['status'] in c.TERMINAL:return state
    jobs={j['id']:j for j in freeze['original_plan']['stage']['jobs']};remaining=freeze['run_ids']
    worker_plan={'freeze':freeze['original_plan']['freeze'],'freeze_sha256':ORIGINAL_FREEZE,'stage':{'name':STAGE},
                 'attempt_freeze_sha256':freeze_sha256}
    def persist():
        state['updated_unix']=clock();state['jobs_complete']=sum(r['status']=='complete' for r in state['rows'].values())
        c.atomic(state_path,state);volume.commit()
        control.put(KEY+':state',{k:v for k,v in state.items() if k not in ('calls','rows')})
    def aggregate():
        base=freeze['retained_state'];rows={**base['rows'],**state['rows']};calls={**base['calls'],**state['calls']}
        require(len(rows)==len(calls)==TOTAL and set(rows)==set(jobs),'aggregate incomplete')
        verify_rows(rows,freeze['original_plan'],calls,allowed_attempts={RECOVERY})
        result={'schema':'learning-hybrid-stage-status-v1','stage':STAGE,'status':'complete',
                'freeze_sha256':ORIGINAL_FREEZE,'stage_sha256':ORIGINAL_STAGE,'coordinator_call_id':ORIGINAL_CALL,
                'calls':calls,'rows':rows,'jobs_total':TOTAL,'jobs_complete':TOTAL,'spawn_intent':None,
                'recovery2_provenance':aggregate_provenance(freeze,freeze_sha256,call_id),
                'budget_ledger':freeze['budget_ledger'],
                'started_unix':base['started_unix'],'ended_unix':clock(),'updated_unix':clock()}
        c.atomic(folder/'aggregate-state.json',result);state['aggregate_sha256']=c.digest(folder/'aggregate-state.json')
    try:
        # Recover only saved handles; a handle-less intent is never resubmitted.
        for name in remaining:
            receipt=control.get(KEY+':call:'+name)
            if receipt:
                require(receipt['job_sha256']==c.state_hash(jobs[name]) and receipt.get('recovery_freeze_sha256')==freeze_sha256,
                        'saved receipt identity differs')
                state['calls'][name]=receipt['call_id'];c.atomic(folder/'receipts'/(name+'.json'),receipt)
            elif any(control.get(k) is not None for k in attempt_guard_keys(name)):
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
            def clear(name):return not any(control.get(k) is not None for k in attempt_guard_keys(name))
            with ThreadPoolExecutor(max_workers=min(16,max(1,len(wave)))) as pool:
                require(all(pool.map(clear,wave)),'candidate has execution evidence')
            for name in wave:
                if clock()>=DEADLINE or control.get('stop'):break
                state['spawn_intent']=name
                require(control.put(KEY+':intent:'+name,{'job_sha256':c.state_hash(jobs[name]),
                        'recovery_freeze_sha256':freeze_sha256},skip_if_exists=True),'previous intent requires diagnosis')
                call=worker.spawn(worker_plan,{**jobs[name],'source_sha256':freeze['original_plan']['freeze']['source_sha256']})
                receipt={'job_id':name,'call_id':call.object_id,'job_sha256':c.state_hash(jobs[name]),'recovery_freeze_sha256':freeze_sha256}
                control.put(KEY+':call:'+name,receipt);state['calls'][name]=call.object_id;state['spawn_intent']=None
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
                if row.get('status')=='complete':verify_rows({name:row},freeze['original_plan'],{name:state['calls'][name]},allowed_attempts={RECOVERY})
                state['rows'][name]=row
            if len(state['rows'])==RUN_COUNT:
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
    receipt={'schema':'learning-hybrid-recovery2-receipt-v1','recovery_id':RECOVERY,'status':'preparing',
             'freeze_sha256':hashed,'original_freeze_sha256':ORIGINAL_FREEZE,'volume':c.VOLUME_NAME,'created_unix':now}
    receipt_path.parent.mkdir(parents=True,exist_ok=True)
    with receipt_path.open('x') as stream:json.dump(receipt,stream)
    try:
        control=sdk.Dict.from_name(c.CONTROL_NAME);volume=sdk.Volume.from_name(c.VOLUME_NAME)
        receipt['reservation']=reserve(control,freeze,hashed,now,get_call=sdk.FunctionCall.from_id,volume=volume);c.atomic(receipt_path,receipt)
        with tempfile.TemporaryDirectory(prefix='hybrid-recovery-source-') as directory:
            destination=Path(directory);expected={**freeze['original_plan']['freeze']['source_sha256'],
                                                  c.POLICY_FILE:freeze['original_plan']['freeze']['policy_freeze_sha256']}
            for name,digest in expected.items():
                source=Path(root)/name;require(c.digest(source)==digest and not source.is_symlink(),'protected image source differs')
                target=destination/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
            for name,digest in freeze['ops_source_sha256'].items():
                source=Path(root)/name;require(c.digest(source)==digest and not source.is_symlink(),'ops source differs')
                target=destination/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
            image=(sdk.Image.debian_slim(python_version='3.12').pip_install('torch==2.9.1',index_url=c.RUNTIME['torch_index'])
                   .pip_install('numpy==2.3.4').env({'PYTHONPATH':'/app','PYTHONDONTWRITEBYTECODE':'1',
                    'OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1'})
                   .add_local_dir(directory,remote_path='/app',copy=True))
            app=sdk.App(APP);options={'image':image,'cpu':(1,1),'memory':(2048,2048),'min_containers':0,
                'buffer_containers':0,'retries':0,'startup_timeout':120,'scaledown_window':10,
                'volumes':{'/results':volume},'serialized':True,'include_source':False,'nonpreemptible':True}
            def worker_entry(plan,job):
                from tools.learning_hybrid_ops.recovery2 import run_attempt_worker, RECOVERY
                return run_attempt_worker(plan,job,volume,control,attempt=RECOVERY)
            worker=app.function(max_containers=64,timeout=180,**options)(worker_entry)
            def coordinator_entry(value,value_hash):
                from tools.learning_hybrid_ops.recovery2 import coordinate
                return coordinate(value,value_hash,worker,volume,control)
            coordinator=app.function(max_containers=1,timeout=21720,**options)(coordinator_entry)
            with sdk.enable_output(),app.run(detach=True):
                require(time.time()<DEADLINE and not control.get('stop'),'campaign stopped or expired before launch')
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
    require(receipt['schema']=='learning-hybrid-recovery2-receipt-v1' and receipt['recovery_id']==RECOVERY,'invalid recovery receipt')
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
    parser.add_argument('--diagnosis',type=Path);parser.add_argument('--app-status',type=Path);parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--receipt',type=Path);parser.add_argument('--output',type=Path);args=parser.parse_args(argv)
    if args.write_freeze:
        require(args.diagnosis is not None,'--diagnosis required');value=write_freeze(args.write_freeze,args.diagnosis,args.root,app_status=args.app_status)
    elif args.launch:
        require(args.receipt is not None,'--receipt required');value=launch(args.launch,args.receipt,args.root)
    elif args.status:value=status(args.status)
    else:
        require(args.output is not None,'--output required');value=download(args.download,args.output)
    print(json.dumps(value,sort_keys=True))


if __name__=='__main__':main()
