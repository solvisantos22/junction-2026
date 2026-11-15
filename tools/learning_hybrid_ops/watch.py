"""Read-only bounded status watcher with durable, at-most-once Codex wake-ups."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import time

DEADLINE = 1794720900.0  # 2026-11-15 05:35 UTC; never extend on restart.
POLL_SECONDS = 60
PROCESS_SECONDS = 45
MODULES = {'hybrid':'tools.learning_hybrid.manage','prior':'tools.learning_hybrid_train.modal_job',
           'recovery':'tools.learning_hybrid_ops.recovery',
           'recovery2':'tools.learning_hybrid_ops.recovery2'}
RECEIPT_SCHEMAS = {'hybrid':'learning-hybrid-receipt-v1','prior':'greedy-prior-receipt-v1',
                   'recovery':'learning-hybrid-recovery-receipt-v1',
                   'recovery2':'learning-hybrid-recovery2-receipt-v1'}
TRAIN_TERMINAL = {'completed','training_incomplete','training_error','stopped_deadline',
                  'stopped_marker','wrapper_error','ambiguous_execution','cancelled'}
END_STATES = {'disabled','finished','deadline'}


def read(path):
    value=json.loads(Path(path).read_text())
    if not isinstance(value,dict):raise ValueError('expected JSON object')
    return value


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    temporary=path.with_name(path.name+'.tmp')
    with temporary.open('w') as stream:
        json.dump(value,stream,sort_keys=True,indent=2,allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    os.chmod(temporary,0o600);temporary.replace(path)


def identity(config):
    required={'monitor_directory','working_directory','python_path','codex_path','thread_id','deadline_unix','targets'}
    if set(config)!=required:raise ValueError('invalid watcher configuration fields')
    for name in required-{'targets','deadline_unix','thread_id'}:
        if not isinstance(config[name],str) or not Path(config[name]).is_absolute():raise ValueError('absolute configuration paths required')
    if not isinstance(config['thread_id'],str) or not config['thread_id']:raise ValueError('thread ID required')
    deadline=config['deadline_unix']
    if type(deadline) not in (int,float) or not math.isfinite(deadline) or not 0<deadline<=DEADLINE:
        raise ValueError('invalid watcher absolute deadline')
    targets=config['targets'];ids=set();sources={}
    if not isinstance(targets,list) or not 1<=len(targets)<=4:raise ValueError('one to four explicit targets required')
    for target in targets:
        if set(target)!={'id','kind','module','working_directory','receipt_path','freeze_sha256'}:
            raise ValueError('invalid target fields')
        identifier=target['id']
        if not isinstance(identifier,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',identifier) or identifier in ids:
            raise ValueError('invalid or duplicate target ID')
        ids.add(identifier)
        if target['kind'] not in MODULES or target['module']!=MODULES[target['kind']]:raise ValueError('status module not allowed')
        if any(not isinstance(target[k],str) or not Path(target[k]).is_absolute() for k in ('working_directory','receipt_path')):
            raise ValueError('absolute target paths required')
        if not isinstance(target['freeze_sha256'],str) or not re.fullmatch('[0-9a-f]{64}',target['freeze_sha256']):
            raise ValueError('target freeze hash required')
        module=Path(target['working_directory'])/(target['module'].replace('.','/')+'.py')
        sources[str(module)]=digest(module)
    return {'config':config,'watcher_sha256':digest(__file__),'status_modules_sha256':sources}


def local_pause(config):
    roots={Path(config['monitor_directory']),Path(config['working_directory'])}
    roots.update(Path(t['receipt_path']).parent for t in config['targets'])
    roots.update(Path(t['working_directory']) for t in config['targets'])
    for root in sorted(roots):
        for marker in ('pause.json','wake-stop','stop'):
            if (root/marker).exists():return str(root/marker)
    return None


def interpret(value,target):
    if not isinstance(value,dict):raise ValueError('status is not an object')
    if value.get('stop_marker') is True:return {'status':'stopped','paused':True,'terminal':False}
    if target['kind'] in {'hybrid','recovery','recovery2'}:
        if value.get('schema')!='learning-hybrid-monitor-v1':raise ValueError('unexpected hybrid status schema')
        state=value['state'];status=state['status']
        if status in {'user_paused','stopped_marker','stopped'}:return {'status':status,'paused':True,'terminal':False}
        if status not in {'pending','running','complete','failed','deadline'}:raise ValueError('unknown hybrid status')
        if state.get('poll_error_type'):raise RuntimeError('status reports a polling error')
        return {'status':status,'paused':False,'terminal':status in {'complete','failed','deadline'},
                'jobs_total':state.get('jobs_total'),'jobs_complete':state.get('jobs_complete')}
    if value.get('schema')!='greedy-prior-status-v1':raise ValueError('unexpected training status schema')
    jobs=value.get('jobs',[])
    if len(jobs)!=6:raise ValueError('training receipt must retain all six jobs')
    identities={(r['job']['variant'],r['job']['seed']) for r in jobs}
    if identities!={(variant,seed) for variant in ('prior','plain') for seed in (17,29,43)}:
        raise ValueError('training job identities differ')
    statuses=[(r.get('result') or r.get('state') or {}).get('status','pending') for r in jobs]
    if any(s in {'user_paused','stopped_marker','stopped'} for s in statuses):
        return {'status':'stopped','paused':True,'terminal':False}
    if any(s not in TRAIN_TERMINAL|{'pending','running'} for s in statuses):raise ValueError('unknown training status')
    failed_run_ids=[r['job']['run_id'] for r,s in zip(jobs,statuses) if s in TRAIN_TERMINAL-{'completed'}]
    read_error=any(r.get('poll_error_type') or r.get('progress_error_type') for r in jobs)
    if read_error and not failed_run_ids:
        raise RuntimeError('training status reports a read error')
    terminal=all(s in TRAIN_TERMINAL for s in statuses)
    return {'status':('complete' if all(s=='completed' for s in statuses) else 'terminal_with_incomplete') if terminal else 'running',
            'paused':False,'terminal':terminal,'jobs_complete':sum(s=='completed' for s in statuses),
            'failure_present':bool(failed_run_ids),'failed_run_ids':failed_run_ids,'read_error_present':read_error,
            'job_statuses':statuses,'progress':{r['job']['run_id']:r.get('progress') for r in jobs}}


def poll(config,target,previous,runner):
    receipt_path=Path(target['receipt_path'])
    if not receipt_path.exists():
        return {'kind':'error','error_type':'FileNotFoundError'} if previous.get('receipt_sha256') else {'kind':'missing'}
    try:
        receipt=read(receipt_path)
        if receipt.get('freeze_sha256')!=target['freeze_sha256']:raise ValueError('receipt freeze differs')
        schema=RECEIPT_SCHEMAS[target['kind']]
        if receipt.get('schema')!=schema:raise ValueError('receipt schema differs')
        if receipt.get('status') in {'preparing','launching'}:return {'kind':'pending_receipt'}
        if receipt.get('status')!='submitted':raise ValueError('receipt launch requires diagnosis')
        hashed=digest(receipt_path)
        if previous.get('receipt_sha256') not in (None,hashed):raise ValueError('submitted receipt changed')
        command=[config['python_path'],'-m',target['module'],'--status',str(receipt_path)]
        environment={k:os.environ[k] for k in ('PATH','HOME','TMPDIR','SYSTEMROOT') if k in os.environ}
        environment.update(MODAL_PROFILE='solvi-junction',PYTHONUNBUFFERED='1')
        result=runner(command,cwd=target['working_directory'],env=environment,capture_output=True,text=True,timeout=PROCESS_SECONDS)
        if result.returncode:raise RuntimeError('read-only status process failed')
        value=json.loads(result.stdout)
        if value.get('receipt_sha256')!=hashed:raise ValueError('observed receipt identity differs')
        stage_field='recovery_id' if target['kind'] in {'recovery','recovery2'} else 'stage'
        if target['kind'] in {'hybrid','recovery','recovery2'} and value.get('stage')!=receipt.get(stage_field):
            raise ValueError('observed stage differs')
        summary=interpret(value,target)
        return {'kind':'status','receipt_sha256':hashed,'summary':summary,'value':value}
    except Exception as error:
        return {'kind':'error','error_type':type(error).__name__}


def message(config,target,event,reason):
    label=target['id'] if target else 'deadline'
    return (f'Automatic read-only experiment watcher wake-up for {label}: {event} ({reason}). '
            'Read AGENTS.md, the required junction-team-workflow skill, TEAM_STATUS.md, '
            'docs/learning-hybrid.md, docs/learning-hybrid-results/README.md, '
            'docs/learning-hybrid-training.md and docs/learning-hybrid-training-results/README.md, '
            f'and private watcher state in {config["monitor_directory"]}. Reconcile the original saved call IDs and '
            'current statuses before continuing the authorized workflow. Preserve every protected source/weight freeze. '
            'Publish any required selection or all-six-run policy freeze before opening the next reserved maps; '
            'retain failures and partial results. Diagnose errors before new spend; never repeat completed jobs, '
            'restart old training or bypass a user pause/stop. The watcher performed no launches, downloads or selection. '
            'No Superpowers. Record verified decisions, evidence and handoff in the repository.')


def dispatch(config,state,state_path,event_key,target,reason,runner,now):
    if event_key in state['events']:return
    if local_pause(config) or any(t.get('paused') for t in state['targets'].values()):
        state.update(status='disabled',reason='pause_or_stop');save(state_path,state);return
    event={'status':'reserved','reserved_unix':now,'reason':reason}
    state['events'][event_key]=event;save(state_path,state)
    # A newly created local marker between observation and dispatch still wins.
    if local_pause(config):
        event['status']='suppressed';state.update(status='disabled',reason='pause_or_stop');save(state_path,state);return
    command=[config['codex_path'],'queue','--thread',config['thread_id'],'--message',
             message(config,target,event_key.rsplit(':',1)[-1],reason),'--resume']
    try:
        result=runner(command,cwd=config['working_directory'],capture_output=True,text=True,timeout=PROCESS_SECONDS)
        output=((result.stdout or '')+'\n'+(result.stderr or '')).lower()
        warning=any('resum' in line and re.search(r'fail|error|unable|cannot|can.t|could not|warning',line) for line in output.splitlines())
        event.update(status='uncertain' if result.returncode or warning else 'queued',returncode=result.returncode)
        if result.returncode or warning:event['error']='queue_failed_or_resume_unconfirmed'
    except (subprocess.TimeoutExpired,OSError) as error:
        event.update(status='uncertain',error=type(error).__name__)
    save(state_path,state)


def tick(config,state_path,runner=subprocess.run,now=None):
    injected_clock=now is not None
    now=time.time() if now is None else now;state_path=Path(state_path)
    state_path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    with Path(str(state_path)+'.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        expected=identity(config)
        state=read(state_path) if state_path.exists() else {'schema':'learning-hybrid-ops-watch-v1','identity':expected,
              'status':'watching','started_unix':now,'events':{},'targets':{t['id']:{'read_errors':0} for t in config['targets']}}
        if state.get('schema')!='learning-hybrid-ops-watch-v1' or state.get('identity')!=expected:
            raise ValueError('watcher code/config/status-module identity changed')
        if state['status'] in END_STATES:return state
        state.update(updated_unix=now,poll_started_unix=now);save(state_path,state)
        if local_pause(config):
            state.update(status='disabled',reason='local_pause_or_stop');save(state_path,state);return state
        # Terminal results are cached, avoiding repeated large stage-result reads.
        # Thereafter local wake-stop/pause/stop markers remain authoritative;
        # remote stop is checked by every still-active target in its control store.
        active=[t for t in config['targets'] if not state['targets'][t['id']].get('terminal')]
        with ThreadPoolExecutor(max_workers=max(1,len(active))) as pool:
            outcomes=list(pool.map(lambda target:poll(config,target,state['targets'][target['id']],runner),active))
        for target,outcome in zip(active,outcomes):
            current=state['targets'][target['id']];current['checked_unix']=now
            if outcome['kind']=='status':
                read_errors=current.get('read_errors',0)+1 if outcome['summary'].get('read_error_present') else 0
                current.update(outcome['summary'],read_errors=read_errors,receipt_sha256=outcome['receipt_sha256'])
                if read_errors:current['error_type']='ReportedReadError'
                else:current.pop('error_type',None)
                save(Path(config['monitor_directory'])/'statuses'/(target['id']+'.json'),
                     {'checked_unix':now,'receipt_sha256':outcome['receipt_sha256'],'status':outcome['value']})
            elif outcome['kind']=='error':
                current.update(read_errors=current.get('read_errors',0)+1,error_type=outcome['error_type'])
            else:current.update(status=outcome['kind'],read_errors=0)
        now=now if injected_clock else time.time()
        state.update(poll_finished_unix=now,updated_unix=now)
        if local_pause(config) or any(t.get('paused') for t in state['targets'].values()):
            state.update(status='disabled',reason='local_or_remote_pause_stop');save(state_path,state);return state
        save(state_path,state)
        for target in config['targets']:
            current=state['targets'][target['id']]
            if current.get('failure_present'):
                dispatch(config,state,state_path,target['id']+':error',target,'terminal_training_failure',runner,now)
            elif current.get('read_errors',0)>=3:
                dispatch(config,state,state_path,target['id']+':error',target,'three_consecutive_read_errors',runner,now)
            if current.get('terminal'):
                dispatch(config,state,state_path,target['id']+':completion',target,current['status'],runner,now)
            if state['status']=='disabled':return state
        if now>=config['deadline_unix']:
            dispatch(config,state,state_path,'deadline',None,'absolute_watcher_deadline',runner,now)
            if state['status']!='disabled':state.update(status='deadline',reason='absolute_watcher_deadline')
        elif all(t.get('terminal') for t in state['targets'].values()):
            state.update(status='finished',reason='all_targets_terminal')
        save(state_path,state);return state


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--state',type=Path,required=True);mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--once',action='store_true');mode.add_argument('--follow',action='store_true');args=parser.parse_args(argv)
    config=read(args.config)
    while True:
        started=time.monotonic()
        try:state=tick(config,args.state)
        except Exception as error:
            # Preserve the pinned state and fail closed, with a private diagnostic.
            save(Path(str(args.state)+'.error.json'),{'schema':'learning-hybrid-ops-watch-error-v1',
                 'status':'error','updated_unix':time.time(),'error_type':type(error).__name__})
            raise
        if not args.follow or state['status'] in END_STATES:
            print(json.dumps({'status':state['status'],'events':{k:v['status'] for k,v in state['events'].items()}}));return
        time.sleep(max(0,POLL_SECONDS-(time.monotonic()-started)))


if __name__=='__main__':main()
