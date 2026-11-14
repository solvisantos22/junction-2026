"""Freeze, explicitly launch, inspect and download bounded hybrid evaluations."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import shutil
import tempfile
import time

from . import cloud as c

ROOT = Path(__file__).resolve().parents[2]
ABSOLUTE_DEADLINE = datetime(2026, 11, 15, 5, 30, tzinfo=timezone.utc).timestamp()
STAGES = ['smoke', 'development', 'confirmation', 'final']
COST_CAP_USD = 75.0


def require(condition, message):
    if not condition:
        raise ValueError(message)


def identifier(value):
    require(isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,100}', value) is not None,
            'invalid identifier')
    return value


def source_manifest(root=ROOT):
    from lightlag_hybrid.worker import source_manifest as sources
    return sources(root)


def validate_freeze(freeze, root=ROOT):
    root = Path(root).resolve()
    require(freeze['schema'] == 'learning-hybrid-freeze-v1' and freeze['resources'] == c.RESOURCES
            and freeze['runtime'] == c.RUNTIME and freeze['required_profile'] == c.PROFILE
            and freeze['cost_cap_usd'] == COST_CAP_USD, 'freeze configuration differs')
    campaign = freeze['campaign']; identifier(campaign['campaign_id'])
    require(campaign['stages'] == STAGES and type(campaign['max_jobs']) is int
            and 1 <= campaign['max_jobs'] <= 18000, 'invalid stage order or job limit')
    created, deadline = freeze['created_unix'], campaign['deadline_unix']
    require(type(created) in (int,float) and type(deadline) in (int,float)
            and created < deadline <= min(ABSOLUTE_DEADLINE, created+21600), 'invalid absolute campaign deadline')
    require(freeze['source_sha256'] == source_manifest(root), 'source closure changed')
    for name, expected in freeze['source_sha256'].items():
        path = root/name
        require(path.resolve().is_relative_to(root) and not path.is_symlink() and c.digest(path)==expected,
                'unsafe or changed source path')
    require(c.digest(root/c.POLICY_FILE) == freeze['policy_freeze_sha256'], 'parent policy freeze changed')
    policies = c.policies_from_file(root/c.POLICY_FILE)
    require(freeze['policy_ids'] == sorted(policies), 'latest policy set changed')
    envelope = (c.MAX_CONTAINERS+1)*c.RATE*(deadline-created)
    require(freeze['running_compute_envelope_usd'] == envelope and envelope <= COST_CAP_USD,
            'resource/time envelope exceeds budget')
    return policies


def write_freeze(path, campaign, root=ROOT, now=None):
    now = time.time() if now is None else now
    path = Path(path)
    if path.exists():raise FileExistsError(path)
    freeze = {'schema':'learning-hybrid-freeze-v1','campaign':campaign,'created_unix':now,
              'resources':c.RESOURCES,'runtime':c.RUNTIME,'required_profile':c.PROFILE,
              'source_sha256':source_manifest(root), 'policy_freeze_sha256':c.digest(Path(root)/c.POLICY_FILE),
              'policy_ids':sorted(c.policies_from_file(Path(root)/c.POLICY_FILE)),
              'cost_cap_usd':COST_CAP_USD,
              'running_compute_envelope_usd':(c.MAX_CONTAINERS+1)*c.RATE*(campaign['deadline_unix']-now),
              'cost_limit':'Running allocation estimate, excludes build/startup/storage/egress; not an invoice or account balance.',
              'no_gpu':True,'model_api_calls':0}
    validate_freeze(freeze,root); c.atomic(path,freeze)
    return freeze


def prepare(freeze_path, stage_path, root=ROOT, now=None):
    from lightlag_hybrid.policy import validate_spec
    from lightlag_hybrid.worker import STAGE_MAPS
    now = time.time() if now is None else now
    freeze, stage = c.read(freeze_path), c.read(stage_path)
    policies = validate_freeze(freeze,root)
    require(now < freeze['campaign']['deadline_unix'], 'campaign deadline expired')
    require(stage['schema']=='learning-hybrid-stage-v1' and stage['name'] in STAGES
            and stage['freeze_sha256']==c.digest(freeze_path)
            and stage['source_sha256']==freeze['source_sha256'], 'stage identity/source differs')
    jobs = stage['jobs']; require(isinstance(jobs,list) and 1<=len(jobs)<=freeze['campaign']['max_jobs'],'invalid job count')
    ids = set(); pairs=set()
    for job in jobs:
        identifier(job['id'])
        require(job['id'] not in ids and job['stage']==stage['name'] and type(job['seed']) is int
                and job['seed'] in STAGE_MAPS[stage['name']], 'duplicate/invalid job identity or seed')
        require(set(job)=={'id','stage','seed','spec'},'job must use compact declared fields')
        validate_spec(job['spec'],policies)
        pair=(job['seed'],job['spec']['id'])
        require(pair not in pairs,'duplicate policy/world pair')
        ids.add(job['id']); pairs.add(pair)
    return {'freeze':freeze,'stage':stage,'freeze_sha256':c.digest(freeze_path),'stage_sha256':c.digest(stage_path)}


def reserve(control, plan, now=None):
    now = time.time() if now is None else now
    freeze,stage=plan['freeze'],plan['stage']; campaign=freeze['campaign']
    identity={'campaign_id':campaign['campaign_id'],'freeze_sha256':plan['freeze_sha256'],'deadline_unix':campaign['deadline_unix']}
    control.put('campaign',identity,skip_if_exists=True)
    require(control.get('campaign')==identity,'another campaign already owns this isolated control store')
    require(not control.get('stop') and now<campaign['deadline_unix'],'campaign stopped or expired')
    count=0
    for previous in campaign['stages'][:campaign['stages'].index(stage['name'])]:
        prior=control.get('stage:'+previous)
        require(prior is not None,'earlier stage not reserved')
        terminal=control.get('coordinator:'+previous,{})
        require(terminal.get('status')=='complete' and terminal.get('jobs_complete')==prior['jobs'],
                'earlier stage not fully complete and audited; diagnosis required')
        count+=prior['jobs']
    require(count+len(stage['jobs'])<=campaign['max_jobs'],'total campaign job cap exceeded')
    reservation={**identity,'stage':stage['name'],'stage_sha256':plan['stage_sha256'],
                 'jobs':len(stage['jobs']),'reserved_unix':now}
    require(control.put('stage:'+stage['name'],reservation,skip_if_exists=True),'stage already reserved; never relaunch blindly')
    return reservation


def sdk_module():
    require(os.environ.get('MODAL_PROFILE')==c.PROFILE,'set MODAL_PROFILE=solvi-junction explicitly')
    from importlib.metadata import version
    import modal
    require(version('modal')==c.RUNTIME['modal'],'Modal SDK version changed')
    return modal


def copy_sources(plan, destination, root=ROOT):
    root=Path(root).resolve();destination=Path(destination)
    expected=dict(plan['freeze']['source_sha256']);expected[c.POLICY_FILE]=plan['freeze']['policy_freeze_sha256']
    for name,hashed in expected.items():
        source=root/name;target=destination/name
        require(source.resolve().is_relative_to(root) and not source.is_symlink() and c.digest(source)==hashed,'source changed before copying')
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
        require(c.digest(target)==hashed,'source changed while copying')


def launch(plan, receipt_path, root=ROOT, sdk=None, now=None):
    now=time.time() if now is None else now
    sdk=sdk or sdk_module();receipt_path=Path(receipt_path)
    receipt={'schema':'learning-hybrid-receipt-v1','status':'preparing','campaign_id':plan['freeze']['campaign']['campaign_id'],
             'freeze_sha256':plan['freeze_sha256'],'stage_sha256':plan['stage_sha256'],'stage':plan['stage']['name'],
             'created_unix':now,'volume':c.VOLUME_NAME,'coordinator_call_id':None}
    receipt_path.parent.mkdir(parents=True,exist_ok=True)
    with receipt_path.open('x') as stream:stream.write(c.json.dumps(receipt))
    try:
        validate_freeze(plan['freeze'],root)
        with tempfile.TemporaryDirectory(prefix='hybrid-source-') as temporary:
            copy_sources(plan,temporary,root)
            control=sdk.Dict.from_name(c.CONTROL_NAME,create_if_missing=True)
            receipt['reservation']=reserve(control,plan,now);c.atomic(receipt_path,receipt)
            image=(sdk.Image.debian_slim(python_version='3.12')
                   .pip_install('torch==2.9.1',index_url=c.RUNTIME['torch_index']).pip_install('numpy==2.3.4')
                   .env({'PYTHONPATH':'/app','PYTHONDONTWRITEBYTECODE':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1'})
                   .add_local_dir(temporary,remote_path='/app',copy=True))
            volume=sdk.Volume.from_name(c.VOLUME_NAME,create_if_missing=True,version=2)
            app,coordinator=c.build_app(sdk,image,volume,control)
            with sdk.enable_output(),app.run(detach=True):
                receipt.update(status='launching',app_id=app.app_id);c.atomic(receipt_path,receipt)
                call=coordinator.spawn(plan)
                receipt.update(status='submitted',coordinator_call_id=call.object_id)
                control.put('coordinator-receipt:'+receipt['stage'],receipt)
                c.atomic(receipt_path,receipt)
        return receipt
    except BaseException as error:
        receipt.update(status='launch_error',error_type=type(error).__name__);c.atomic(receipt_path,receipt)
        raise


def status(receipt_path, sdk=None):
    sdk=sdk or sdk_module();receipt=c.read(receipt_path)
    require(receipt['schema']=='learning-hybrid-receipt-v1' and receipt['volume']==c.VOLUME_NAME,
            'invalid local receipt')
    control=sdk.Dict.from_name(c.CONTROL_NAME)
    require(control.get('campaign',{}).get('freeze_sha256')==receipt['freeze_sha256'],'cloud campaign identity differs')
    result=control.get('coordinator:'+receipt['stage'],{'status':'pending'})
    call_id=receipt.get('coordinator_call_id')
    if call_id:
        try:result=sdk.FunctionCall.from_id(call_id).get(timeout=0)
        except TimeoutError:pass
        except Exception as error:
            result={**result,'poll_error_type':type(error).__name__}
    return {'schema':'learning-hybrid-monitor-v1','receipt_sha256':c.digest(receipt_path),
            'stop_marker':bool(control.get('stop')),'stage':receipt['stage'],'state':result}


def download(receipt_path, output, *, artifacts=False, sdk=None):
    sdk=sdk or sdk_module(); receipt=c.read(receipt_path); observed=status(receipt_path,sdk)
    require(observed['state'].get('status') in c.TERMINAL,'download only after coordinator is terminal')
    root=Path(output);root.mkdir(parents=True,exist_ok=False)
    volume=sdk.Volume.from_name(c.VOLUME_NAME);stage=receipt['stage']
    def fetch(relative):
        path=root/relative;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(b''.join(volume.read_file(relative)))
        return path
    c.atomic(root/'receipt.json',receipt);c.atomic(root/'status.json',observed)
    state=c.read(fetch(stage+'/state.json'));plan=c.read(fetch(stage+'/plan.json'))
    jobs={job['id']:job for job in plan['stage']['jobs']}
    require(state['freeze_sha256']==plan['freeze_sha256']==receipt['freeze_sha256']
            and state['stage_sha256']==plan['stage_sha256']==receipt['stage_sha256']
            and state['coordinator_call_id']==receipt['coordinator_call_id']
            and set(state['rows'])<=set(state['calls'])<=set(jobs)
            and len(set(state['calls'].values()))==len(state['calls']), 'downloaded stage identities differ')
    if state['status']=='complete':
        require(set(state['rows'])==set(state['calls'])==set(jobs),'complete stage is missing jobs')
    for name,row in state['rows'].items():
        require(row['job_id']==name and row['call_id']==state['calls'][name],'downloaded row/call differs')
        if row['status']=='complete':
            job=jobs[name];audit=row.get('audit') or {}
            require(row['seed']==job['seed'] and row['spec_id']==job['spec']['id']
                    and row['group']==job['spec']['group'] and audit.get('physics_verified') is True
                    and audit.get('case_sha256')==row['case_sha256']
                    and (stage!='final' or audit.get('full_controller_replay') is True), 'downloaded audited row differs')
    if artifacts:
        for name,call_id in state['calls'].items():
            saved=c.read(fetch(f'{stage}/receipts/{name}.json'))
            require(saved['call_id']==call_id,'downloaded receipt differs')
        for row in state['rows'].values():
            if row.get('sha256'):
                require(row['artifact']==f'{stage}/jobs/{row["job_id"]}/case.json.gz','unsafe artifact path')
                path=fetch(row['artifact']);require(c.digest(path)==row['sha256'],'downloaded case hash differs')
    c.atomic(root/'download.json',{'artifacts':artifacts,'files':{str(p.relative_to(root)):c.digest(p) for p in root.rglob('*') if p.is_file()}})
    return state


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    actions=parser.add_mutually_exclusive_group(required=True)
    actions.add_argument('--write-freeze',type=Path);actions.add_argument('--prepare',type=Path)
    actions.add_argument('--launch',type=Path);actions.add_argument('--status',type=Path);actions.add_argument('--download',type=Path)
    parser.add_argument('--campaign',type=Path);parser.add_argument('--stage',type=Path);parser.add_argument('--receipt',type=Path)
    parser.add_argument('--output',type=Path);parser.add_argument('--root',type=Path,default=ROOT);parser.add_argument('--artifacts',action='store_true')
    args=parser.parse_args(argv)
    if args.write_freeze:
        require(args.campaign is not None,'--campaign required');result=write_freeze(args.write_freeze,c.read(args.campaign),args.root)
    elif args.prepare or args.launch:
        require(args.stage is not None,'--stage required');plan=prepare(args.prepare or args.launch,args.stage,args.root)
        if args.launch:
            require(args.receipt is not None,'--receipt required');result=launch(plan,args.receipt,args.root)
        else:result={'status':'dry_run','jobs':len(plan['stage']['jobs']),'freeze_sha256':plan['freeze_sha256'],'stage_sha256':plan['stage_sha256']}
    elif args.status:result=status(args.status)
    else:
        require(args.output is not None,'--output required');result=download(args.download,args.output,artifacts=args.artifacts)
    print(c.json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
