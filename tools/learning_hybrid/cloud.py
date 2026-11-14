"""Isolated, bounded rollout workers and a durable cloud coordinator."""
from __future__ import annotations

import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

APP_NAME = VOLUME_NAME = CONTROL_NAME = 'junction-learning-hybrid'
PROFILE = 'solvi-junction'
POLICY_FILE = 'docs/learning-final-results/policy-freeze.json'
MAX_CONTAINERS = 64
JOB_SECONDS = 180
STARTUP_SECONDS = 120
RATE = .0000131 + 2 * .00000222
RESOURCES = {'worker_cpu': [1, 1], 'worker_memory_mib': [2048, 2048],
             'worker_max_containers': 64, 'coordinator_cpu': [1, 1],
             'coordinator_memory_mib': [2048, 2048], 'coordinator_max_containers': 1,
             'min_containers': 0, 'buffer_containers': 0, 'retries': 0,
             'job_seconds': JOB_SECONDS, 'startup_seconds': STARTUP_SECONDS,
             'scaledown_seconds': 10, 'gpu': None}
RUNTIME = {'python': '3.12', 'numpy': '2.3.4', 'torch': '2.9.1', 'modal': '1.6.4',
           'torch_index': 'https://download.pytorch.org/whl/cpu'}
TERMINAL = {'complete', 'failed', 'deadline', 'stopped'}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def state_hash(value):
    return hashlib.sha256((json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()).hexdigest()


def read(path):
    path = Path(path)
    data = path.read_bytes()
    return json.loads(gzip.decompress(data) if path.suffix == '.gz' else data)


def atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()
    if path.suffix == '.gz':
        data = gzip.compress(data, mtime=0)
    temporary = path.with_name(path.name+'.tmp')
    with temporary.open('wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def policies_from_file(path):
    parent = read(path)
    if parent.get('schema') != 'learning-final-freeze-v1' or parent.get('smoke') is not False:
        raise ValueError('production parent policy freeze required')
    arms = [arm for arm in parent['arms'] if arm['kind'] == 'policy' and 'last' in arm['roles']]
    if {(a['algorithm'], a['training_seed']) for a in arms} != {(a, s) for a in ('ppo', 'replay') for s in (17, 29, 43)} or len(arms) != 6:
        raise ValueError('all six latest policies required')
    for arm in arms:
        if state_hash(arm['policy']) != arm['policy_sha256']:
            raise ValueError('policy state hash changed')
    return {a['id']: a['policy'] for a in arms}


def execute_job(job_path, output):
    """Child process: a timeout cannot leave simulator work running in the worker."""
    from lightlag_hybrid.worker import run_job, audit_job, assert_source, row_for
    import torch
    import numpy as np
    import traceback
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    if sys.version_info[:2] != (3,12) or np.__version__ != RUNTIME['numpy'] or torch.__version__.split('+')[0] != RUNTIME['torch']:
        raise ValueError('remote runtime differs from frozen runtime')
    request = read(job_path)
    job = request['job']
    assert_source(job['source_sha256'])
    policies = policies_from_file('/app/'+POLICY_FILE)
    bundle = run_job(job, policies)
    audit, error = None, None
    try:
        if bundle.get('status') == 'complete':
            audit = audit_job(bundle, policies)
    except Exception as exc:
        error = {'type': type(exc).__name__, 'traceback': traceback.format_exc()[-12000:]}
    atomic(output, {'bundle': bundle, 'audit': audit, 'row': row_for(bundle,audit), 'audit_error': error})


def run_worker(plan, job, volume, control, *, root='/results', call_id=None, clock=time.time):
    """Each job owns its files; infrastructure restarts reuse a completed artifact."""
    import modal
    call_id = call_id or modal.current_function_call_id()
    stage = plan['stage']['name']
    if job['stage'] != stage or job['source_sha256'] != plan['freeze']['source_sha256']:
        raise ValueError('worker job differs from frozen stage/source')
    if digest('/app/'+POLICY_FILE) != plan['freeze']['policy_freeze_sha256']:
        raise ValueError('uploaded parent policy freeze changed')
    key = f'job:{stage}:{job["id"]}'
    owner = key+':owner'
    control.put(owner, call_id, skip_if_exists=True)
    if control.get(owner) != call_id:
        raise ValueError('job already belongs to another function call')
    volume.reload()
    folder = Path(root)/stage/'jobs'/job['id']
    row_path = folder/'row.json'
    if row_path.exists():
        row = read(row_path)
        if row['job_sha256'] != state_hash(job) or row['call_id'] != call_id:
            raise ValueError('saved job identity differs')
        return row
    started = clock()
    row = {'job_id': job['id'], 'job_sha256': state_hash(job), 'stage': stage,
           'call_id': call_id, 'status': 'running', 'started_unix': started,
           'artifact': f'{stage}/jobs/{job["id"]}/case.json.gz', 'audit': None,
           'id': job['id'], 'seed': job['seed'], 'spec_id': job['spec']['id'],
           'group': job['spec']['group'], 'reward': None, 'home': None,
           'alive': None, 'invalid_calls': None, 'error': None}
    control.put(key, row)
    deadline = plan['freeze']['campaign']['deadline_unix']
    child = None
    try:
        if started >= deadline:
            row['status'] = 'deadline'
        elif control.get('stop'):
            row['status'] = 'stopped'
        elif not control.put(key+':execution', {'call_id':call_id, 'started_unix':started}, skip_if_exists=True):
            row.update(status='failed', error_type='AmbiguousExecutionRequiresDiagnosis',
                       error={'type':'AmbiguousExecutionRequiresDiagnosis'})
        else:
            with tempfile.TemporaryDirectory(prefix='hybrid-job-') as temporary:
                request, result = Path(temporary)/'request.json', Path(temporary)/'result.json.gz'
                atomic(request, {'job': job})
                log_path = Path(temporary)/'worker.log'
                log = log_path.open('wb')
                child = subprocess.Popen([sys.executable, '-m', 'tools.learning_hybrid.cloud',
                                          '--execute-job', str(request), '--output', str(result)],
                                         stdout=log, stderr=subprocess.STDOUT)
                timeout = min(deadline, started+JOB_SECONDS-10)
                while child.poll() is None:
                    if clock() >= timeout or control.get('stop'):
                        child.terminate()
                        try:
                            child.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            child.kill(); child.wait()
                        row['status'] = 'stopped' if control.get('stop') else 'deadline'
                        break
                    time.sleep(.5)
                if row['status'] == 'running':
                    if child.returncode != 0 or not result.exists():
                        row.update(status='failed', error_type='WorkerProcessError')
                    else:
                        saved = read(result)
                        bundle, audit = saved['bundle'], saved['audit']
                        artifact = Path(root)/row['artifact']
                        atomic(artifact, bundle)
                        row.update(saved['row'])
                        row.update(status='complete' if bundle.get('status') == 'complete' and audit is not None else 'failed',
                                   sha256=digest(artifact), audit=audit)
                        if saved.get('audit_error'):
                            row['error'] = saved['audit_error']
                log.close()
                if row['status'] != 'complete':
                    with log_path.open('rb') as stream:
                        stream.seek(max(0,log_path.stat().st_size-65536))
                        tail=stream.read().decode('utf-8',errors='replace')
                    atomic(folder/'failure-log.json',{'tail':tail,'truncated':log_path.stat().st_size>65536})
                    if not row.get('error'):
                        row['error']={'type':row.get('error_type',row['status']),'traceback':tail[-12000:]}
    except BaseException as error:
        row.update(status='failed', error_type=type(error).__name__)
    finally:
        if child is not None and child.poll() is None:
            child.kill(); child.wait()
        row.update(ended_unix=clock(), elapsed_seconds=clock()-started)
        row['running_compute_estimate_usd'] = row['elapsed_seconds']*RATE
        atomic(row_path, row)
        volume.commit()
        control.put(key, row)
    return row


def coordinate(plan, worker, volume, control, *, root='/results', call_id=None, clock=time.time, sleeper=time.sleep, get_call=None):
    """Durable per-call receipts, bounded fan-out, no automatic ambiguous retry."""
    import modal
    call_id = call_id or modal.current_function_call_id()
    get_call = get_call or modal.FunctionCall.from_id
    stage = plan['stage']['name']; key = 'coordinator:'+stage
    control.put(key+':owner', call_id, skip_if_exists=True)
    if control.get(key+':owner') != call_id:
        raise ValueError('stage already has a coordinator')
    volume.reload()
    folder = Path(root)/stage; state_path = folder/'state.json'
    state = read(state_path) if state_path.exists() else {
        'schema': 'learning-hybrid-stage-status-v1', 'stage': stage, 'status': 'running',
        'freeze_sha256': plan['freeze_sha256'], 'stage_sha256': plan['stage_sha256'],
        'coordinator_call_id': call_id, 'calls': {}, 'rows': {}, 'spawn_intent': None,
        'started_unix': clock(), 'jobs_total': len(plan['stage']['jobs'])}
    if state['freeze_sha256'] != plan['freeze_sha256'] or state['stage_sha256'] != plan['stage_sha256'] or state['coordinator_call_id'] != call_id:
        raise ValueError('retained stage identity differs')
    if state['status'] in TERMINAL:
        return state
    jobs = {j['id']:j for j in plan['stage']['jobs']}
    # Per-call Dict receipts survive a crash between spawn and the next volume snapshot.
    # A reservation with no returned handle is intentionally not retried.
    for name in jobs:
        receipt=control.get(f'call:{stage}:{name}')
        if receipt:
            if receipt['job_sha256'] != state_hash(jobs[name]):
                raise ValueError('durable per-call identity differs')
            state['calls'][name]=receipt['call_id']
            atomic(folder/'receipts'/f'{name}.json',receipt)
        elif control.get(f'intent:{stage}:{name}'):
            state.update(status='failed',error_type='AmbiguousSpawnRequiresDiagnosis',spawn_intent=name)
            break
        else:
            break
    if state.get('spawn_intent') in state['calls']:
        state['spawn_intent']=None
    atomic(folder/'plan.json',plan)
    def save():
        state['updated_unix']=clock()
        state['jobs_complete']=sum(r['status']=='complete' for r in state['rows'].values())
        atomic(state_path,state);volume.commit()
        # Keep bounded summary metadata in Dict; full rows live in the volume.
        control.put(key,{k:v for k,v in state.items() if k not in ('calls','rows')})
    save()
    worker_plan={'freeze':plan['freeze'],'freeze_sha256':plan['freeze_sha256'], 'stage':{'name':stage}}
    deadline=plan['freeze']['campaign']['deadline_unix']; transport_errors=0
    try:
        while state['status']=='running':
            if clock()>=deadline or control.get('stop'):
                state['status']='stopped' if control.get('stop') else 'deadline';break
            failed=any(row['status']!='complete' for row in state['rows'].values())
            pending=[name for name in state['calls'] if name not in state['rows']]
            unsent=[name for name in jobs if name not in state['calls']]
            while not failed and unsent and len(pending)<MAX_CONTAINERS:
                if clock()>=deadline or control.get('stop'):break
                name=unsent.pop(0);state['spawn_intent']=name
                if not control.put(f'intent:{stage}:{name}',{'job_sha256':state_hash(jobs[name])},skip_if_exists=True):
                    raise ValueError('previous spawn intent requires diagnosis')
                job={**jobs[name],'source_sha256':plan['freeze']['source_sha256']}
                call=worker.spawn(worker_plan,job)
                receipt={'job_id':name,'call_id':call.object_id,'job_sha256':state_hash(jobs[name])}
                control.put(f'call:{stage}:{name}',receipt)
                state['calls'][name]=call.object_id;state['spawn_intent']=None
                atomic(folder/'receipts'/f'{name}.json',receipt)
                pending.append(name)
            save()
            for name in pending:
                try:
                    row=get_call(state['calls'][name]).get(timeout=0)
                except TimeoutError:
                    continue
                except Exception as error:
                    # Infrastructure polling failures do not prove a worker failed.
                    if type(error).__name__ in ('ConnectionError','GRPCError','TransportError','StreamTerminatedError'):
                        transport_errors+=1
                        state['last_poll_error']={'type':type(error).__name__,'count':transport_errors,'unix':clock()}
                        if transport_errors>=10:raise
                        continue
                    row={'job_id':name,'call_id':state['calls'][name],'status':'failed','error_type':type(error).__name__}
                if row.get('job_id')!=name or row.get('call_id')!=state['calls'][name]:
                    raise ValueError('remote job receipt mismatch')
                state['rows'][name]=row
            if len(state['rows'])==len(jobs):
                state['status']='complete' if all(r['status']=='complete' for r in state['rows'].values()) else 'failed'
            elif any(r['status']!='complete' for r in state['rows'].values()) and len(state['rows'])==len(state['calls']):
                state.update(status='failed',error_type='JobFailureRequiresDiagnosis')
            save()
            if state['status']=='running':sleeper(2)
        if state['status'] in {'deadline','stopped'}:
            for name,remote_id in state['calls'].items():
                if name not in state['rows']:
                    try:get_call(remote_id).cancel()
                    except Exception:pass
    except BaseException as error:
        state.update(status='failed',error_type=type(error).__name__)
    finally:
        state['ended_unix']=clock();save()
    return state


def build_app(sdk, image, volume, control):
    app = sdk.App(APP_NAME)
    options = dict(image=image, cpu=(1,1), memory=(2048,2048), min_containers=0,
                   buffer_containers=0, retries=0, startup_timeout=STARTUP_SECONDS,
                   scaledown_window=10, volumes={'/results':volume}, serialized=True, include_source=False)
    def job_entry(plan, job):
        from tools.learning_hybrid.cloud import run_worker
        return run_worker(plan, job, volume, control)
    worker = app.function(max_containers=MAX_CONTAINERS, timeout=JOB_SECONDS, **options)(job_entry)
    def coordinator_entry(plan):
        from tools.learning_hybrid.cloud import coordinate
        return coordinate(plan, worker, volume, control)
    coordinator = app.function(max_containers=1, timeout=21720, **options)(coordinator_entry)
    return app, coordinator


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--execute-job',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();execute_job(args.execute_job,args.output)
