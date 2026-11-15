"""Synthetic operational recovery checks; never runs Modal or rover simulations."""
import copy
from contextlib import nullcontext
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from tools.learning_hybrid_ops import recovery2 as r

NOW=r.DEADLINE-1000

class Control(dict):
    def put(self,key,value,skip_if_exists=False):
        if skip_if_exists and key in self:return False
        self[key]=copy.deepcopy(value);return True

class Volume:
    def __init__(self):self.commits=0;self.files={}
    def reload(self):pass
    def commit(self):self.commits+=1
    def read_file(self,name):
        if name not in self.files:raise FileNotFoundError(name)
        yield self.files[name]

class Recovery2Tests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name)
        self.volume=Volume();jobs=[{'id':f'development-greedy-{n}','stage':'development','seed':n,
                                  'spec':{'id':'greedy','group':'greedy'}} for n in range(5)]
        master={'created_unix':NOW-2000,'source_sha256':{'a.py':'a'*64},'policy_freeze_sha256':'b'*64,
                'campaign':{'deadline_unix':r.DEADLINE}}
        self.plan={'freeze':master,'freeze_sha256':r.c.state_hash(master),'stage':{'name':'development','jobs':jobs},'stage_sha256':'d'*64}
        self.original={'coordinator_call_id':'fc-original','status':'failed','error_type':'KeyboardInterrupt','spawn_intent':None,
                       'freeze_sha256':self.plan['freeze_sha256'],'stage_sha256':'d'*64,'started_unix':NOW-1900,
                       'rows':{jobs[0]['id']:self.row(jobs[0],'fc-old')},'calls':{jobs[0]['id']:'fc-old'}}
        failed_calls={jobs[2]['id']:'fc-failed-2',jobs[3]['id']:'fc-failed-3'}
        parent_rows={jobs[1]['id']:self.row(jobs[1],'fc-parent-complete')}
        for j in jobs[2:4]:
            row=self.row(j,failed_calls[j['id']]);row.update(status='failed',reward=None,audit=None,error_type='KeyboardInterrupt')
            parent_rows[j['id']]=row
        parent={'coordinator_call_id':'fc-parent','status':'failed','spawn_intent':None,'freeze_sha256':None,
                'rows':parent_rows,'calls':{n:v['call_id'] for n,v in parent_rows.items()},'jobs_complete':1}
        prior={'original_plan':self.plan,'retained_state':self.original};parent_hash=r.c.state_hash(prior);parent['freeze_sha256']=parent_hash
        patches={'TOTAL':5,'RETAINED':2,'RUN_COUNT':3,'RETRY_COUNT':2,'NEW_COUNT':1,
                 'FAILED_CALLS':failed_calls,'ORIGINAL_CALL':'fc-original','ORIGINAL_FREEZE':self.plan['freeze_sha256'],
                 'ORIGINAL_STAGE':'d'*64,'ORIGINAL_STAGE_STATE':r.c.state_hash(self.plan['stage']),
                 'PARENT_FREEZE':parent_hash,'PARENT_STATE_SHA256':r.c.state_hash(parent),'PARENT_CALL':'fc-parent','PARENT_APP':'ap-parent'}
        for name,value in patches.items():
            p=patch.object(r,name,value);p.start();self.addCleanup(p.stop)
        p=patch.object(r.old,'RETAINED',1);p.start();self.addCleanup(p.stop)
        self.parent=parent;self.failed=[];rechecks=[];outputs=[];folders={}
        self.control=Control({'campaign':{'freeze_sha256':r.ORIGINAL_FREEZE},
                             'coordinator:development':{k:v for k,v in self.original.items() if k not in ('rows','calls')},
                             'coordinator:development:owner':r.ORIGINAL_CALL,
                             r.old.KEY+':state':{k:v for k,v in parent.items() if k not in ('rows','calls')},
                             r.old.KEY+':owner':r.PARENT_CALL,r.old.KEY+':receipt':{'app_id':'ap-parent','coordinator_call_id':'fc-parent'}})
        for name,call in failed_calls.items():
            row=parent_rows[name];key=f'job:development:{name}'
            ctrl={key:row,key+':owner':call,key+':execution':{'call_id':call,'started_unix':NOW-500},
                  f'call:development:{name}':{'call_id':call},f'intent:development:{name}':{'job_sha256':'x'}}
            self.control.update(ctrl);self.volume.files[f'development/jobs/{name}/row.json']=(json.dumps(row,sort_keys=True,separators=(',',':'))+'\n').encode()
            self.failed.append({'job_id':name,'call_id':call,'control':ctrl,'function_result':row,
                                'files':{'case.json.gz':{'status':'missing'},'row.json':{'sha256':r.c.state_hash(row)}}})
            rechecks.append({'job_id':name,'row_sha256':r.c.state_hash(row),'row_unchanged':True,'result_unchanged':True,
                             'case_present':False,'elapsed_since_execution_marker':400,'elapsed_since_first_read':100})
            outputs.append({'call_id':call,'num_unfinished_inputs':0})
            folders[name]=[{'path':f'development/jobs/{name}/row.json'}]
        base={**self.original,'rows':{**self.original['rows'],jobs[1]['id']:parent_rows[jobs[1]['id']]},
              'calls':{**self.original['calls'],jobs[1]['id']:'fc-parent-complete'}}
        self.freeze={'schema':'learning-hybrid-recovery2-freeze-v1','recovery_id':r.RECOVERY,'created_unix':NOW,
                     'deadline_unix':r.DEADLINE,'resources':r.RESOURCES,'runtime':r.c.RUNTIME,'original_plan':self.plan,
                     'parent_recovery_freeze':prior,'parent_recovery_state':parent,'parent_recovery_receipt':self.control[r.old.KEY+':receipt'],
                     'retained_state':base,'retained_state_sha256':r.c.state_hash(base),'failed_attempts':self.failed,
                     'remaining_ids':[jobs[4]['id']],'retry_ids':[j['id'] for j in jobs[2:4]],'run_ids':[j['id'] for j in jobs[2:]],
                     'absence_proof':{'keys':list(self.control),'keys_sha256':r.c.state_hash(list(self.control))},
                     'quiescence':{'stable_rechecks':rechecks,'terminal_output_metadata':outputs,'failed_folder_inventory':{'folders':folders},
                                   'app_status':[{'app_id':'ap-parent','state':'stopped','tasks':'0'}]},
                     'ops_source_sha256':{name:r.c.digest(Path(r.ROOT)/name) for name in r.OPS_FILES},
                     'budget_ledger':r.budget_ledger(master,NOW)}
        self.hashed=r.c.state_hash(self.freeze);self.spawned=[];self.calls={r.PARENT_CALL:SimpleNamespace(get=lambda timeout:copy.deepcopy(self.parent))}
        for entry in self.failed:
            row=entry['function_result'];self.calls[entry['call_id']]=SimpleNamespace(get=lambda timeout,row=row:copy.deepcopy(row))
        self.fail_job=None;self.spawn_error=None

    def row(self,job,call):
        return {'id':job['id'],'job_id':job['id'],'stage':job['stage'],'seed':job['seed'],'spec_id':job['spec']['id'],
                'group':job['spec']['group'],'call_id':call,'job_sha256':r.c.state_hash({**job,'source_sha256':self.plan['freeze']['source_sha256']}),
                'status':'complete','reward':.4,'home':True,'alive':True,'invalid_calls':0,'error':None,'sha256':'a'*64,'case_sha256':'b'*64,
                'artifact':f'{job["stage"]}/jobs/{job["id"]}/case.json.gz','running_compute_estimate_usd':.001,
                'audit':{'schema':'learning-hybrid-case-audit-v1','job_id':job['id'],'case_sha256':'b'*64,
                         'physics_verified':True,'hybrid_choices_verified':True,'full_controller_replay':True}}

    def reserve(self):return r.reserve(self.control,self.freeze,self.hashed,now=NOW,get_call=self.calls.__getitem__,volume=self.volume)
    def mapped(self,job,call,attempt=r.RECOVERY):
        raw=self.row(job,call);prefix=attempt+'/artifacts/'
        return {**raw,'artifact':prefix+raw['artifact'],'running_compute_estimate_usd':3*raw['running_compute_estimate_usd'],
                'allocation_rate_multiplier':3,'storage':{'volume':r.c.VOLUME_NAME,'artifact':prefix+raw['artifact'],
                'raw_row':prefix+f'{job["stage"]}/jobs/{job["id"]}/row.json','raw_row_sha256':r.c.state_hash(raw),
                'original_artifact':raw['artifact'],'raw_running_compute_estimate_usd':raw['running_compute_estimate_usd'],'attempt':attempt}}
    def spawn(self,plan,job):
        self.spawned.append(job['id'])
        if self.spawn_error:raise self.spawn_error
        call=f'fc-new-{len(self.spawned)}';row=self.mapped(job,call)
        if job['id']==self.fail_job:row.update(status='failed',error_type='WorkerError')
        self.calls[call]=SimpleNamespace(get=lambda timeout:copy.deepcopy(row),cancel=lambda:None)
        return SimpleNamespace(object_id=call)
    def coordinate(self):
        original=r.validate
        with patch.object(r,'validate',side_effect=lambda freeze,root,**kw:original(freeze,root,check_sources=False,**kw)):
            return r.coordinate(self.freeze,self.hashed,SimpleNamespace(spawn=self.spawn),self.volume,self.control,
                                root=self.root,call_id='fc-recovery2',clock=lambda:NOW+1,sleeper=lambda n:None,get_call=self.calls.__getitem__)

    def test_exact_retained_matrix_and_parent_hash(self):
        r.validate(self.freeze,check_sources=False,now=NOW)
        for mutate in (lambda f:f['run_ids'].append(f['run_ids'][0]),lambda f:f['retry_ids'].reverse(),
                       lambda f:f['retained_state']['rows'].clear(),lambda f:f['parent_recovery_state'].update(status='complete'),
                       lambda f:f['original_plan']['stage']['jobs'][0].update(seed=999)):
            value=copy.deepcopy(self.freeze);mutate(value)
            with self.assertRaises(ValueError):r.validate(value,check_sources=False,now=NOW)

    def test_quiescence_and_stopped_app_required(self):
        for mutate in (lambda f:f['quiescence']['stable_rechecks'][0].update(case_present=True),
                       lambda f:f['quiescence']['stable_rechecks'][0].update(elapsed_since_execution_marker=179),
                       lambda f:f['quiescence']['terminal_output_metadata'][0].update(num_unfinished_inputs=1),
                       lambda f:f['quiescence']['app_status'][0].update(tasks='1')):
            value=copy.deepcopy(self.freeze);mutate(value)
            with self.assertRaises(ValueError):r.validate(value,check_sources=False,now=NOW)

    def test_reserved_fresh_inventory_and_live_failed_artifact(self):
        name=self.freeze['remaining_ids'][0]
        for key in (*r.guard_keys(name),*r.attempt_guard_keys(name)):
            self.control[key]={}
            with self.assertRaisesRegex(ValueError,'no longer unlaunched'):self.reserve()
            self.control.pop(key)
        failed=self.freeze['retry_ids'][0];path=f'development/jobs/{failed}/case.json.gz';self.volume.files[path]=b'late completed case'
        with self.assertRaisesRegex(ValueError,'appeared'):self.reserve()
        self.volume.files.pop(path);self.reserve()
        with self.assertRaisesRegex(ValueError,'already reserved'):self.reserve()

    def test_parent_and_failed_terminal_results_must_match(self):
        original=self.calls[r.PARENT_CALL];self.calls[r.PARENT_CALL]=SimpleNamespace(get=lambda timeout:{'changed':True})
        with self.assertRaisesRegex(ValueError,'parent result'):self.reserve()
        self.calls[r.PARENT_CALL]=original;self.calls[next(iter(r.FAILED_CALLS.values()))]=SimpleNamespace(get=lambda timeout:{'changed':True})
        with self.assertRaisesRegex(ValueError,'failed call result'):self.reserve()

    def test_complete_aggregate_keeps_all_original_rows_and_guards(self):
        original=copy.deepcopy(self.control);self.reserve();state=self.coordinate()
        self.assertEqual(state['status'],'complete');self.assertEqual(self.spawned,self.freeze['run_ids'])
        result=r.c.read(self.root/r.RECOVERY/'aggregate-state.json');self.assertEqual(len(result['rows']),5)
        for name,row in self.freeze['retained_state']['rows'].items():self.assertEqual(result['rows'][name],row)
        for key,value in original.items():self.assertEqual(self.control[key],value)
        self.assertEqual(result['recovery2_provenance'],r.aggregate_provenance(self.freeze,self.hashed,'fc-recovery2'))
        self.coordinate();self.assertEqual(len(self.spawned),3)

    def test_ambiguous_spawn_never_repeats(self):
        self.reserve();self.spawn_error=KeyboardInterrupt();state=self.coordinate()
        self.assertEqual(state['status'],'failed');self.assertEqual(len(self.spawned),1)
        self.coordinate();self.assertEqual(len(self.spawned),1)
        self.assertFalse((self.root/r.RECOVERY/'aggregate-state.json').exists())

    def test_failed_new_attempt_retained_and_no_aggregate(self):
        self.reserve();self.fail_job=self.freeze['run_ids'][0];state=self.coordinate()
        self.assertEqual(state['status'],'failed');self.assertEqual(len(state['rows']),3)
        self.assertFalse((self.root/r.RECOVERY/'aggregate-state.json').exists())

    def test_handleless_intent_and_pause_fail_closed(self):
        self.reserve();self.control[r.KEY+':intent:'+self.freeze['run_ids'][0]]={'unknown':True}
        self.assertEqual(self.coordinate()['status'],'failed');self.assertEqual(self.spawned,[])
        self.control['stop']=True
        with self.assertRaisesRegex(ValueError,'stopped'):self.reserve()

    def test_attempt_facade_never_mutates_original_keys(self):
        facade=r.AttemptControl(self.control,r.RECOVERY,'development','a');facade.put('job:development:a:owner','new',skip_if_exists=True)
        self.assertNotIn('job:development:a:owner',self.control)
        self.assertEqual(self.control[f'attempt:{r.RECOVERY}:job:development:a:owner'],'new')
        with self.assertRaises(ValueError):facade.put('stop',True)
        with self.assertRaises(ValueError):facade.get('job:development:b')

    def test_storage_and_threefold_cost_are_bound(self):
        job=self.plan['stage']['jobs'][4];row=self.mapped(job,'fc-new');calls={job['id']:'fc-new'}
        r.verify_rows({job['id']:row},self.plan,calls,allowed_attempts={r.RECOVERY})
        for mutate in (lambda v:v.update(reward=.9),lambda v:v.update(running_compute_estimate_usd=.001),
                       lambda v:v['storage'].update(raw_row='../row.json'),lambda v:v['storage'].update(attempt='final-ops2')):
            value=copy.deepcopy(row);mutate(value)
            with self.assertRaises(ValueError):r.verify_rows({job['id']:value},self.plan,calls,allowed_attempts={r.RECOVERY})

    def test_worker_rejects_completed_original_and_checks_admission(self):
        job={**self.plan['stage']['jobs'][0],'source_sha256':self.plan['freeze']['source_sha256']}
        plan={**self.plan,'attempt_freeze_sha256':self.hashed};self.reserve()
        self.control[r.KEY+':intent:'+job['id']]={'recovery_freeze_sha256':self.hashed,'job_sha256':r.c.state_hash(self.plan['stage']['jobs'][0])}
        self.control[f'job:development:{job["id"]}']=self.original['rows'][job['id']]
        with patch.object(r.c,'run_worker') as invoke:
            with self.assertRaisesRegex(ValueError,'already started'):r.run_attempt_worker(plan,job,self.volume,self.control,attempt=r.RECOVERY,root=self.root)
            invoke.assert_not_called()
        target=self.root/'development'/'jobs'/job['id'];target.mkdir(parents=True);(target/'case.json.gz').write_bytes(b'case')
        with self.assertRaisesRegex(ValueError,'completed or in-flight artifact'):r.run_attempt_worker(plan,job,self.volume,self.control,attempt=r.RECOVERY,root=self.root)

    def test_worker_raw_artifact_remains_separate_and_cost_is_threefold(self):
        self.reserve();compact=self.plan['stage']['jobs'][4];job={**compact,'source_sha256':self.plan['freeze']['source_sha256']}
        self.control[r.KEY+':intent:'+job['id']]={'recovery_freeze_sha256':self.hashed,'job_sha256':r.c.state_hash(compact)}
        raw=self.row(job,'fc-new')
        with patch.object(r.c,'run_worker',return_value=raw) as invoke:
            result=r.run_attempt_worker({**self.plan,'attempt_freeze_sha256':self.hashed},job,self.volume,self.control,
                                       attempt=r.RECOVERY,root=self.root,call_id='fc-new')
            self.assertEqual(invoke.call_args.kwargs['root'],self.root/r.RECOVERY/'artifacts')
        self.assertEqual(result['running_compute_estimate_usd'],.003)
        self.assertEqual(raw['artifact'],f'development/jobs/{job["id"]}/case.json.gz')
        r.verify_rows({job['id']:result},self.plan,{job['id']:'fc-new'},allowed_attempts={r.RECOVERY})

    def test_worker_failed_retry_preserves_original_row_and_guards(self):
        self.reserve();compact=self.plan['stage']['jobs'][2];name=compact['id'];job={**compact,'source_sha256':self.plan['freeze']['source_sha256']}
        original=self.parent['rows'][name];path=self.root/'development'/'jobs'/name/'row.json';r.c.atomic(path,original)
        before=path.read_bytes();guards={k:copy.deepcopy(self.control[k]) for k in r.guard_keys(name)}
        self.control[r.KEY+':intent:'+name]={'recovery_freeze_sha256':self.hashed,'job_sha256':r.c.state_hash(compact)}
        with patch.object(r.c,'run_worker',return_value=self.row(job,'fc-new')):
            result=r.run_attempt_worker({**self.plan,'attempt_freeze_sha256':self.hashed},job,self.volume,self.control,
                                       attempt=r.RECOVERY,root=self.root,call_id='fc-new')
        self.assertEqual(result['status'],'complete');self.assertEqual(path.read_bytes(),before)
        for key,value in guards.items():self.assertEqual(self.control[key],value)
        (path.parent/'case.json.gz.tmp').write_bytes(b'partial artifact')
        with self.assertRaisesRegex(ValueError,'in-flight'):
            r.run_attempt_worker({**self.plan,'attempt_freeze_sha256':self.hashed},job,self.volume,self.control,attempt=r.RECOVERY,root=self.root)

    def test_source_root_cannot_redirect_loaded_science(self):
        with self.assertRaisesRegex(ValueError,'frozen snapshot'):r.source_context(self.root)

    def test_launcher_caps_allowlist_and_one_shot_receipt(self):
        captured={'functions':[],'files':[],'spawns':[]}
        root=self.root/'image';root.mkdir();(root/'a.py').write_text('# fixture')
        target=root/r.c.POLICY_FILE;target.parent.mkdir(parents=True);target.write_text('weights')
        freeze=copy.deepcopy(self.freeze);freeze['original_plan']['freeze']['source_sha256']={'a.py':r.c.digest(root/'a.py')}
        freeze['original_plan']['freeze']['policy_freeze_sha256']=r.c.digest(target)
        for name in r.OPS_FILES:
            path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes((Path(r.ROOT)/name).read_bytes())
        (root/'.env').write_text('private')
        path=self.root/'launch-freeze.json';r.c.atomic(path,freeze);receipt=self.root/'launch-receipt.json'
        class Image:
            def pip_install(self,*a,**kw):return self
            def env(self,*a,**kw):return self
            def add_local_dir(self,path,**kw):
                captured['files']=[str(v.relative_to(path)) for v in Path(path).rglob('*') if v.is_file()];return self
        class App:
            app_id='ap-fake'
            def __init__(self,name):captured['app']=name
            def function(self,**options):
                captured['functions'].append(options)
                def wrap(function):
                    def spawn(*args):
                        captured['spawns'].append(args)
                        assert r.c.read(receipt)['spawn_intent']
                        return SimpleNamespace(object_id='fc-new-coordinator')
                    return SimpleNamespace(spawn=spawn)
                return wrap
            def run(self,detach):captured['detach']=detach;return nullcontext()
        sdk=SimpleNamespace(Image=SimpleNamespace(debian_slim=lambda **kw:Image()),App=App,
                            Dict=SimpleNamespace(from_name=lambda name:self.control),Volume=SimpleNamespace(from_name=lambda name:self.volume),
                            FunctionCall=SimpleNamespace(from_id=self.calls.__getitem__),enable_output=nullcontext)
        with patch.object(r,'validate',return_value=freeze['original_plan']),patch.object(r,'reserve',return_value={'reserved':True}) as reserve:
            result=r.launch(path,receipt,root,sdk,now=NOW)
            self.assertIs(reserve.call_args.kwargs['volume'],self.volume)
            self.assertIsNotNone(reserve.call_args.kwargs['get_call'])
            with self.assertRaises(FileExistsError):r.launch(path,receipt,root,sdk,now=NOW)
        self.assertEqual(result['schema'],'learning-hybrid-recovery2-receipt-v1')
        self.assertEqual(set(captured['files']),{'a.py',r.c.POLICY_FILE,*r.OPS_FILES})
        self.assertEqual(len(captured['spawns']),1);self.assertTrue(captured['detach'])
        worker,coordinator=captured['functions'];self.assertEqual(worker['max_containers'],64)
        self.assertEqual(worker['timeout'],180);self.assertEqual(coordinator['max_containers'],1)
        for options in (worker,coordinator):
            self.assertTrue(options['nonpreemptible']);self.assertEqual(options['cpu'],(1,1));self.assertEqual(options['memory'],(2048,2048))
            self.assertEqual(options['retries'],0);self.assertEqual(options['min_containers'],0)

    def test_budget_is_one_shared_remaining_envelope(self):
        ledger=r.budget_ledger(self.plan['freeze'],NOW)
        self.assertAlmostEqual(ledger['future_rate_per_second'],65*3*r.c.RATE)
        self.assertLess(ledger['total_running_allocation_bound_usd'],75)
        value=copy.deepcopy(self.freeze);value['budget_ledger']['cap_usd']=76
        with self.assertRaisesRegex(ValueError,'allocation'):r.validate(value,check_sources=False,now=NOW)

if __name__=='__main__':unittest.main()
