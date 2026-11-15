"""Freeze and explicitly launch six fresh PPO runs; no extension or automatic retry."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
APP_NAME = VOLUME_NAME = CONTROL_NAME = 'junction-greedy-prior'
PROFILE = 'solvi-junction'
PACKAGES = ('lightlag_learning_final','lightlag_learning','lightlag_traverse','lightlag',
            'lightlag_mcp','lightlag_rl','lightlag_rl_feasible','lightlag_hybrid_train','tools/learning_hybrid_train')
PROTOCOL = 'docs/learning-hybrid-training.md'
ABSOLUTE_DEADLINE = 1794720600.0  # 2026-11-15T05:30:00Z
RATE_PER_SECOND = 8*.0000131 + 16*.00000222
MAX_COMPUTE_ESTIMATE = 15.0
EXPERIMENT = 'learning-hybrid-training-20261115'
JOBS = [{'run_id':f'{variant}-{seed}','variant':variant,'seed':seed,'episodes':4096}
        for variant in ('prior','plain') for seed in (17,29,43)]
RESOURCES = {'cpu_request':8,'cpu_limit':8,'memory_mib':16384,'memory_limit_mib':16384,
             'max_containers':6,'min_containers':0,'buffer_containers':0,'retries':0,
             'startup_timeout_seconds':120,'function_timeout_seconds':10920,'workers':6,'gpu':None}
RUNTIME = {'python':'3.12','numpy':'2.3.4','torch':'2.9.1','modal_client':'1.6.4',
           'torch_index':'https://download.pytorch.org/whl/cpu'}
TERMINAL = {'completed','training_incomplete','training_error','stopped_deadline','stopped_marker',
            'wrapper_error','ambiguous_execution','cancelled'}


def require(condition,message):
    if not condition:raise ValueError(message)


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):return json.loads(Path(path).read_text())


def atomic(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);temporary=path.with_name(path.name+'.tmp')
    with temporary.open('w') as stream:
        json.dump(value,stream,sort_keys=True,indent=2,allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    temporary.replace(path)


def validate_campaign(campaign,now=None):
    now=time.time() if now is None else now
    require(set(campaign)=={'campaign_id','deadline_unix','max_seconds','jobs'},'campaign fields differ')
    require(campaign['campaign_id']=='greedy-prior-20261115','fixed campaign ID required')
    deadline=campaign['deadline_unix']
    require(type(deadline) in (int,float) and math.isfinite(deadline) and now<deadline<=ABSOLUTE_DEADLINE,
            'campaign deadline must be future and no later than 05:30 UTC')
    require(type(campaign['max_seconds']) is int and campaign['max_seconds']==10800,'fixed three-hour run limit required')
    require(campaign['jobs']==JOBS,'exactly six fixed prior/plain jobs required, in declared order')
    require(all(type(job['seed']) is int and type(job['episodes']) is int for job in campaign['jobs']),
            'seed and episode count must be integers')
    envelope=min(deadline-now,campaign['max_seconds'])*6*RATE_PER_SECOND
    require(envelope<=MAX_COMPUTE_ESTIMATE,'running-compute estimate exceeds $15')
    return envelope


def source_manifest(root=ROOT):
    root=Path(root).resolve();files={root/PROTOCOL}
    for package in PACKAGES:
        directory=root/package
        require(directory.is_dir() and not directory.is_symlink(),'required source package missing or symlinked')
        sources=set(directory.rglob('*.py'));require(bool(sources),'source package is empty');files.update(sources)
    require((root/'lightlag_hybrid_train/train.py').is_file(),'trainer entrypoint missing')
    for path in files:
        require(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(root),'source allowlist contains missing/escaping file')
    return {str(p.relative_to(root)):digest(p) for p in sorted(files)}


def write_freeze(path,campaign,root=ROOT,now=None):
    now=time.time() if now is None else now;path=Path(path)
    envelope=validate_campaign(campaign,now);sources=source_manifest(root)
    freeze={'schema':'greedy-prior-freeze-v1','experiment':EXPERIMENT,'campaign':campaign,
            'created_unix':now,'source_sha256':sources,'resources':RESOURCES,'runtime':RUNTIME,'required_profile':PROFILE,
            'running_compute_envelope_usd':envelope,'running_compute_cap_usd':MAX_COMPUTE_ESTIMATE,
            'cost_note':'CPU/memory allocation estimate; excludes startup/build/storage/egress, not invoice or balance.',
            'model_api_calls':0,'gpu_jobs':0,'resume_allowed':False}
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as stream:json.dump(freeze,stream,sort_keys=True,indent=2,allow_nan=False);stream.write('\n')
    return freeze


def prepare(freeze_path,root=ROOT,now=None):
    now=time.time() if now is None else now;freeze=read(freeze_path)
    require(freeze.get('schema')=='greedy-prior-freeze-v1' and freeze.get('experiment')==EXPERIMENT
            and freeze.get('resources')==RESOURCES and freeze.get('runtime')==RUNTIME
            and freeze.get('required_profile')==PROFILE and freeze.get('resume_allowed') is False
            and freeze.get('running_compute_cap_usd')==MAX_COMPUTE_ESTIMATE,'freeze configuration differs')
    envelope=validate_campaign(freeze['campaign'],freeze['created_unix'])
    require(freeze['running_compute_envelope_usd']==envelope and now<freeze['campaign']['deadline_unix'],
            'freeze envelope changed or deadline expired')
    require(freeze['source_sha256']==source_manifest(root),'source changed since freeze')
    return {'schema':'greedy-prior-plan-v1','freeze':freeze,'freeze_sha256':digest(freeze_path)}


def copy_sources(plan,destination,root=ROOT):
    root=Path(root).resolve();destination=Path(destination)
    require(source_manifest(root)==plan['freeze']['source_sha256'],'source changed before image snapshot')
    for name,expected in plan['freeze']['source_sha256'].items():
        source=root/name;target=destination/name
        require(not source.is_symlink() and digest(source)==expected,'source changed while copying')
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
        require(digest(target)==expected,'copied source differs')


def reserve(control,plan,now=None):
    now=time.time() if now is None else now;campaign=plan['freeze']['campaign']
    identity={'campaign_id':campaign['campaign_id'],'freeze_sha256':plan['freeze_sha256'],'deadline_unix':campaign['deadline_unix']}
    control.put('campaign',identity,skip_if_exists=True)
    require(control.get('campaign')==identity,'isolated control already owns another source/campaign')
    require(not control.get('stop') and now<campaign['deadline_unix'],'campaign stopped or expired')
    reservation={**identity,'reserved_unix':now,'deadline_unix':min(now+10800,campaign['deadline_unix']), 'jobs':JOBS}
    require(control.put('launch',reservation,skip_if_exists=True),'one-shot launch already reserved; inspect receipt, never repeat')
    return reservation


def make_remote_runner(volume,control):
    """Self-contained closure; only allowlisted image files are uploaded."""
    def remote_train(plan,job,source_root='/app',result_root='/results'):
        import hashlib
        import json
        import os
        from pathlib import Path
        import signal
        import subprocess
        import sys
        import threading
        import time
        import traceback
        import modal
        freeze=plan['freeze'];campaign=freeze['campaign'];run_id=job['run_id'];call_id=modal.current_function_call_id()
        identity={'campaign_id':campaign['campaign_id'],'freeze_sha256':plan['freeze_sha256'],'deadline_unix':campaign['deadline_unix']}
        reservation=control.get('launch')
        if control.get('campaign')!=identity or not reservation or reservation['freeze_sha256']!=plan['freeze_sha256'] or job not in reservation['jobs']:
            raise ValueError('remote job differs from reserved campaign')
        key='job:'+run_id;owner='owner:'+run_id
        control.put(owner,call_id,skip_if_exists=True)
        if control.get(owner)!=call_id:raise ValueError('job already belongs to another call')
        previous=control.get(key,{})
        if previous.get('status') in ('completed','training_incomplete','training_error','stopped_deadline','stopped_marker','wrapper_error','ambiguous_execution'):
            return previous
        deadline=min(reservation['deadline_unix'],campaign['deadline_unix'],1794720600.0)
        folder=Path(result_root)/'_runs'/run_id;folder.mkdir(parents=True,exist_ok=True)
        metadata_path=folder/'run.json';log_path=folder/'stdout.txt'
        metadata={'schema':'greedy-prior-run-v1','job':job,'campaign_id':campaign['campaign_id'],
                  'freeze_sha256':plan['freeze_sha256'],'source_sha256':freeze['source_sha256'],
                  'call_id':call_id,'app_id':plan['app_id'],'started_unix':time.time(),'deadline_unix':deadline,
                  'status':'running','model_api_calls':0,'gpu_jobs':0,'commit_errors':[]}
        def persist(publish=True):
            temporary=metadata_path.with_suffix('.tmp');temporary.write_text(json.dumps(metadata,sort_keys=True,indent=2)+'\n');temporary.replace(metadata_path)
            if publish:
                control.put(key,{k:v for k,v in metadata.items() if k not in ('source_sha256','trainer_report','command')})
        if not control.put('execution:'+run_id,{'call_id':call_id,'started_unix':time.time()},skip_if_exists=True):
            metadata.update(status='ambiguous_execution',error_type='InterruptedRunRequiresDiagnosis')
            persist(False);volume.commit();persist();return metadata
        process=None;done=threading.Event();commit_thread=None
        def terminate():
            if process is not None and process.poll() is None:
                try:
                    os.killpg(process.pid,signal.SIGTERM);process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=5)
                except ProcessLookupError:pass
        def watchdog():
            if not done.wait(max(0.,deadline-time.time())):terminate()
        def commit_loop():
            while not done.wait(120):
                try:volume.commit()
                except Exception as error:metadata['commit_errors'].append(type(error).__name__)
        try:
            root=Path(source_root)
            actual={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in freeze['source_sha256']}
            if actual!=freeze['source_sha256']:raise ValueError('uploaded source changed')
            import numpy
            import torch
            if sys.version_info[:2]!=(3,12) or numpy.__version__!='2.3.4' or torch.__version__.split('+')[0]!='2.9.1' or torch.version.cuda is not None:
                raise ValueError('runtime differs from frozen CPU image')
            metadata.update(python_actual=sys.version,numpy_actual=numpy.__version__,torch_actual=torch.__version__)
            command=[sys.executable,'-m','lightlag_hybrid_train.train','--variant',job['variant'],'--seed',str(job['seed']),
                     '--episodes','4096','--output',str(Path(result_root)/run_id),'--workers','6','--deadline-unix',str(deadline)]
            metadata['command']=command;persist();volume.commit()
            commit_thread=threading.Thread(target=commit_loop,daemon=True);commit_thread.start()
            if time.time()>=deadline:metadata['status']='stopped_deadline'
            elif control.get('stop'):metadata['status']='stopped_marker'
            else:
                child_env={'PATH':os.environ.get('PATH',''),'PYTHONPATH':str(root),'PYTHONUNBUFFERED':'1','PYTHONHASHSEED':'0',
                           'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1'}
                with log_path.open('x') as stream:
                    process=subprocess.Popen(command,cwd=root,env=child_env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
                    threading.Thread(target=watchdog,daemon=True).start();next_poll=0.
                    while process.poll() is None:
                        if time.time()>=deadline:metadata['status']='stopped_deadline';terminate();break
                        if time.monotonic()>=next_poll:
                            next_poll=time.monotonic()+10
                            if control.get('stop'):metadata['status']='stopped_marker';terminate();break
                        try:process.wait(timeout=min(1.,max(.01,deadline-time.time())))
                        except subprocess.TimeoutExpired:pass
                    metadata['returncode']=process.returncode
                if metadata['status']=='running':metadata['status']='training_error'
                report_path=Path(result_root)/run_id/'report.json'
                if report_path.is_file():
                    report=json.loads(report_path.read_text());metadata.update(trainer_report=report,trainer_report_sha256=hashlib.sha256(report_path.read_bytes()).hexdigest())
                    matches=(report.get('schema')=='hybrid-ppo-training-report-v1' and report.get('experiment')=='learning-hybrid-training-20261115'
                             and report.get('variant')==job['variant'] and report.get('seed')==job['seed'] and report.get('episodes_target')==4096
                             and report.get('source_sha256')==freeze['source_sha256'])
                    if metadata['status']=='training_error' and process.returncode==0 and matches:
                        metadata['status']=('completed' if report.get('status')=='complete' and report.get('episodes_completed')==4096
                                            and set(report.get('validations',{}))=={'0','512','2048','4096'}
                                            else 'stopped_deadline' if report.get('status')=='deadline' else 'training_incomplete')
        except BaseException as error:
            metadata.update(status='wrapper_error',error_type=type(error).__name__,traceback=traceback.format_exc()[-12000:])
        finally:
            terminate();done.set()
            if commit_thread is not None:commit_thread.join(timeout=10)
            metadata['finished_unix']=time.time();metadata['elapsed_seconds']=metadata['finished_unix']-metadata['started_unix']
            metadata['running_compute_estimate_usd']=metadata['elapsed_seconds']*(8*.0000131+16*.00000222)
            persist(False);volume.commit();persist()
        return {k:v for k,v in metadata.items() if k not in ('source_sha256','command','trainer_report')}
    return remote_train


def sdk_module():
    require(os.environ.get('MODAL_PROFILE')==PROFILE,'set MODAL_PROFILE=solvi-junction explicitly')
    from importlib.metadata import version
    import modal
    require(version('modal')==RUNTIME['modal_client'],'Modal SDK version changed')
    return modal


def launch(plan,receipt_path,root=ROOT,sdk=None,now=None):
    sdk=sdk or sdk_module();now=time.time() if now is None else now;receipt_path=Path(receipt_path)
    receipt={'schema':'greedy-prior-receipt-v1','status':'preparing','campaign_id':plan['freeze']['campaign']['campaign_id'],
             'freeze_sha256':plan['freeze_sha256'],'created_unix':now,'jobs':[],'volume':VOLUME_NAME,'resources':RESOURCES,
             'source_sha256':plan['freeze']['source_sha256']}
    receipt_path.parent.mkdir(parents=True,exist_ok=True)
    with receipt_path.open('x') as stream:json.dump(receipt,stream)
    try:
        with tempfile.TemporaryDirectory(prefix='greedy-prior-source-') as temporary:
            copy_sources(plan,temporary,root)
            control=sdk.Dict.from_name(CONTROL_NAME,create_if_missing=True)
            receipt['reservation']=reserve(control,plan,now);atomic(receipt_path,receipt)
            image=(sdk.Image.debian_slim(python_version='3.12').pip_install('torch==2.9.1',index_url=RUNTIME['torch_index'])
                   .pip_install('numpy==2.3.4').add_local_dir(temporary,remote_path='/app',copy=True))
            volume=sdk.Volume.from_name(VOLUME_NAME,create_if_missing=True,version=2)
            app=sdk.App(APP_NAME)
            remote=app.function(image=image,cpu=(8,8),memory=(16384,16384),max_containers=6,min_containers=0,buffer_containers=0,
                                retries=0,timeout=10920,startup_timeout=120,single_use_containers=True,
                                volumes={'/results':volume},serialized=True,include_source=False)(make_remote_runner(volume,control))
            with sdk.enable_output(),app.run(detach=True):
                receipt.update(status='launching',app_id=app.app_id);atomic(receipt_path,receipt)
                for job in JOBS:
                    require(time.time()<receipt['reservation']['deadline_unix'] and not control.get('stop'),'deadline/stop before all six submissions')
                    receipt['spawn_intent']=job['run_id'];atomic(receipt_path,receipt)
                    control.put('spawn-intent:'+job['run_id'],{'freeze_sha256':plan['freeze_sha256']},skip_if_exists=True)
                    call=remote.spawn({**plan,'app_id':app.app_id},job)
                    saved={**job,'call_id':call.object_id};control.put('receipt:'+job['run_id'],saved)
                    receipt['jobs'].append(saved);receipt['spawn_intent']=None;atomic(receipt_path,receipt)
                receipt['status']='submitted';atomic(receipt_path,receipt)
        return receipt
    except BaseException as error:
        receipt.update(status='launch_error',error_type=type(error).__name__);atomic(receipt_path,receipt);raise


def status(receipt_path,sdk=None):
    sdk=sdk or sdk_module();receipt=read(receipt_path)
    require(receipt.get('schema')=='greedy-prior-receipt-v1' and receipt['volume']==VOLUME_NAME,'invalid receipt')
    control=sdk.Dict.from_name(CONTROL_NAME)
    require(control.get('campaign',{}).get('freeze_sha256')==receipt['freeze_sha256'],'cloud campaign differs')
    volume=sdk.Volume.from_name(VOLUME_NAME)
    rows=[]
    for job in receipt['jobs']:
        require({k:job[k] for k in ('run_id','variant','seed','episodes')} in JOBS,'invalid saved job identity')
        state=control.get('job:'+job['run_id'],{'status':'pending'});result=None;error=None
        try:result=sdk.FunctionCall.from_id(job['call_id']).get(timeout=0)
        except TimeoutError:pass
        except Exception as exc:error=type(exc).__name__
        row={'job':job,'state':state,'result':result,'poll_error_type':error,'progress':None}
        try:
            chunks=[];size=0
            for chunk in volume.read_file(job['run_id']+'/report.json'):
                size+=len(chunk);require(size<=2*1024*1024,'progress report exceeds size bound');chunks.append(chunk)
            data=b''.join(chunks);report=json.loads(data)
            require(report.get('schema')=='hybrid-ppo-training-report-v1' and report.get('experiment')==EXPERIMENT
                    and report.get('variant')==job['variant'] and report.get('seed')==job['seed']
                    and report.get('episodes_target')==4096 and report.get('source_sha256')==receipt['source_sha256']
                    and type(report.get('episodes_completed')) is int and 0<=report['episodes_completed']<=4096
                    and report.get('status') in ('running','complete','deadline','failed')
                    and set(report.get('validations',{}))<={'0','512','2048','4096'},'progress identity/source differs')
            row['progress']={k:report.get(k) for k in ('episodes_completed','episodes_target','phase','validations','updated_unix','status')}
            row['progress'].update(report_sha256=hashlib.sha256(data).hexdigest(),
                                   source_manifest_sha256=hashlib.sha256(json.dumps(report['source_sha256'],sort_keys=True).encode()).hexdigest())
        except Exception as exc:
            if type(exc).__name__ not in ('FileNotFoundError','NotFoundError'):
                row['progress_error_type']=type(exc).__name__
        rows.append(row)
    return {'schema':'greedy-prior-status-v1','receipt_sha256':digest(receipt_path),'campaign_id':receipt['campaign_id'],
            'app_id':receipt.get('app_id'),'stop_marker':bool(control.get('stop')),'jobs':rows}


def stop(receipt_path,sdk=None):
    sdk=sdk or sdk_module();receipt=read(receipt_path);control=sdk.Dict.from_name(CONTROL_NAME)
    require(control.get('campaign',{}).get('freeze_sha256')==receipt['freeze_sha256'],'cloud campaign differs')
    control.put('stop',{'campaign_id':receipt['campaign_id'],'requested_unix':time.time()})
    return {'status':'stop_requested','campaign_id':receipt['campaign_id']}


def download(receipt_path,output,sdk=None,archives=False):
    sdk=sdk or sdk_module();receipt=read(receipt_path);observed=status(receipt_path,sdk)
    require(len(receipt['jobs'])==6 and all(row['result'] is not None for row in observed['jobs']),'all six original calls must be terminal before download')
    output=Path(output);output.mkdir(parents=True,exist_ok=False);volume=sdk.Volume.from_name(VOLUME_NAME)
    atomic(output/'receipt.json',receipt);atomic(output/'status.json',observed)
    def fetch(relative):
        path=output/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b''.join(volume.read_file(relative)));return path
    for job in receipt['jobs']:
        run_id=job['run_id'];fetch(f'_runs/{run_id}/run.json')
        try:report=read(fetch(f'{run_id}/report.json'))
        except FileNotFoundError:continue
        for count in sorted(map(int,report.get('validations',{}))):
            require(count in (0,512,2048,4096),'undeclared downloaded milestone')
            fetch(f'{run_id}/policy-{count:05d}.json');fetch(f'{run_id}/validation-{count:05d}.json.gz')
            if archives:fetch(f'{run_id}/checkpoint-{count:05d}.json.gz')
    atomic(output/'download.json',{'archives':archives,'files':{str(p.relative_to(output)):digest(p) for p in output.rglob('*') if p.is_file()}})
    return {'status':'downloaded','runs':6,'output':str(output),'archives':archives}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);action=parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--write-freeze',type=Path);action.add_argument('--prepare',type=Path);action.add_argument('--launch',type=Path)
    action.add_argument('--status',type=Path);action.add_argument('--stop',type=Path);action.add_argument('--download',type=Path)
    parser.add_argument('--campaign',type=Path);parser.add_argument('--receipt',type=Path);parser.add_argument('--output',type=Path)
    parser.add_argument('--root',type=Path,default=ROOT);parser.add_argument('--archives',action='store_true');args=parser.parse_args(argv)
    if args.write_freeze:
        require(args.campaign is not None,'--campaign required');result=write_freeze(args.write_freeze,read(args.campaign),args.root)
    elif args.prepare or args.launch:
        plan=prepare(args.prepare or args.launch,args.root)
        if args.launch:
            require(args.receipt is not None,'--receipt required');result=launch(plan,args.receipt,args.root)
        else:result={'status':'dry_run','jobs':JOBS,'freeze_sha256':plan['freeze_sha256']}
    elif args.status:result=status(args.status)
    elif args.stop:result=stop(args.stop)
    else:
        require(args.output is not None,'--output required');result=download(args.download,args.output,archives=args.archives)
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
