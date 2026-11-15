"""Synthetic recovery checks: no real Modal calls, rollouts or queue dispatches."""
import copy
from contextlib import nullcontext
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.learning_hybrid_ops import recovery as r

NOW=r.DEADLINE-1000


class Control(dict):
    def put(self,key,value,skip_if_exists=False):
        if skip_if_exists and key in self:return False
        self[key]=copy.deepcopy(value);return True


class Volume:
    def __init__(self):self.commits=0
    def reload(self):pass
    def commit(self):self.commits+=1


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='hybrid-recovery-test-');self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.volume=Volume()
        jobs=[{'id':f'development-greedy-{n}','stage':'development','seed':n,
               'spec':{'id':'greedy','group':'greedy'}} for n in range(3)]
        (self.root/'a.py').write_text('# protected fixture\n')
        (self.root/r.c.POLICY_FILE).parent.mkdir(parents=True)
        (self.root/r.c.POLICY_FILE).write_text('original fixture weights')
        master={'source_sha256':{'a.py':r.c.digest(self.root/'a.py')},
                'policy_freeze_sha256':r.c.digest(self.root/r.c.POLICY_FILE),'campaign':{'deadline_unix':r.DEADLINE}}
        stage={'name':'development','jobs':jobs}
        self.plan={'freeze':master,'freeze_sha256':r.c.state_hash(master),'stage':stage,'stage_sha256':'d'*64}
        for name,value in {'TOTAL':3,'RETAINED':1,'REMAINING':2,'ORIGINAL_CALL':'fc-parent',
                           'ORIGINAL_FREEZE':self.plan['freeze_sha256'],'ORIGINAL_STAGE':'d'*64,
                           'ORIGINAL_STAGE_STATE':r.c.state_hash(stage)}.items():
            patcher=patch.object(r,name,value);patcher.start();self.addCleanup(patcher.stop)
        self.base={'coordinator_call_id':'fc-parent','status':'failed','error_type':'KeyboardInterrupt',
                   'spawn_intent':None,'freeze_sha256':self.plan['freeze_sha256'],'stage_sha256':'d'*64,
                   'started_unix':NOW-100,'rows':{},'calls':{jobs[0]['id']:'fc-old'}}
        self.base['rows'][jobs[0]['id']]=self.row(jobs[0],'fc-old')
        self.freeze={'schema':'learning-hybrid-recovery-freeze-v1','recovery_id':r.RECOVERY,'created_unix':NOW,
                     'deadline_unix':r.DEADLINE,'resources':r.RESOURCES,'runtime':r.c.RUNTIME,'original_plan':self.plan,
                     'stage_state_sha256':r.c.state_hash(stage),'retained_state':self.base,
                     'retained_state_sha256':r.c.state_hash(self.base),'remaining_ids':[j['id'] for j in jobs[1:]],
                     'absence_proof':{'keys':[],'keys_sha256':r.c.state_hash([])},'ops_sha256':r.c.digest(r.__file__),
                     'evidence_sha256':{'state.json':'e'*64},
                     'remaining_allocation_envelope_usd':(r.DEADLINE-NOW)*(r.c.MAX_CONTAINERS+3)*r.c.RATE}
        self.control=Control({'campaign':{'freeze_sha256':self.plan['freeze_sha256']},
                              'coordinator:development':{k:v for k,v in self.base.items() if k not in ('rows','calls')},
                              'coordinator:development:owner':'fc-parent'})
        self.calls={};self.spawned=[];self.cancelled=[];self.spawn_error=None;self.fail_job=None
        self.original_validate=r.validate
        self.hashed=r.c.state_hash(self.freeze)

    def row(self,job,call):
        full={**job,'source_sha256':self.plan['freeze']['source_sha256']}
        return {'id':job['id'],'job_id':job['id'],'stage':job['stage'],'seed':job['seed'],
                'spec_id':job['spec']['id'],'group':job['spec']['group'],'call_id':call,
                'job_sha256':r.c.state_hash(full),'status':'complete','reward':.4,'home':True,'alive':True,
                'invalid_calls':0,'error':None,'sha256':'a'*64,'case_sha256':'b'*64,
                'artifact':f'development/jobs/{job["id"]}/case.json.gz',
                'audit':{'schema':'learning-hybrid-case-audit-v1','job_id':job['id'],'case_sha256':'b'*64,
                         'physics_verified':True,'hybrid_choices_verified':True}}

    def reserve(self):
        return r.reserve(self.control,self.freeze,self.hashed,now=NOW)

    def spawn(self,plan,job):
        self.spawned.append(job['id'])
        if self.spawn_error:raise self.spawn_error
        identifier=f'fc-new-{len(self.spawned)}'
        result=self.row(job,identifier)
        if job['id']==self.fail_job:result.update(status='failed',error_type='WorkerProcessError')
        self.calls[identifier]=SimpleNamespace(get=lambda timeout:copy.deepcopy(result),cancel=lambda:self.cancelled.append(identifier))
        return SimpleNamespace(object_id=identifier)

    def coordinate(self,**kwargs):
        def checked(freeze,root,**options):
            return self.original_validate(freeze,root,check_sources=False,now=options.get('now',NOW))
        with patch.object(r,'validate',side_effect=checked):
            return r.coordinate(self.freeze,self.hashed,SimpleNamespace(spawn=self.spawn),self.volume,self.control,
                                root=self.root,call_id='fc-recovery',clock=lambda:NOW+1,sleeper=lambda n:None,
                                get_call=lambda identifier:self.calls[identifier],**kwargs)

    def test_exact_suffix_source_and_frozen_stage_validation(self):
        r.validate(self.freeze,check_sources=False,now=NOW)
        for mutate in (lambda f:f['remaining_ids'].append(f['remaining_ids'][0]),
                       lambda f:f['retained_state']['rows'].clear(),
                       lambda f:f['original_plan']['stage']['jobs'][2].update(seed=99),
                       lambda f:f.update(deadline_unix=r.DEADLINE+1)):
            frozen=copy.deepcopy(self.freeze);mutate(frozen)
            if frozen['original_plan']['stage']!=self.plan['stage']:
                frozen['stage_state_sha256']=r.c.state_hash(frozen['original_plan']['stage'])
            with self.assertRaises(ValueError):r.validate(frozen,check_sources=False,now=NOW)

    def test_all_remaining_absence_guard_keys_and_repeated_reservation(self):
        name=self.freeze['remaining_ids'][0]
        for key in r.guard_keys(name):
            self.control[key]={}
            with self.assertRaisesRegex(ValueError,'no longer unlaunched'):self.reserve()
            self.control.pop(key)
        self.reserve()
        with self.assertRaisesRegex(ValueError,'already reserved'):self.reserve()

    def test_inventory_proof_cannot_include_an_unstarted_owner(self):
        frozen=copy.deepcopy(self.freeze)
        frozen['absence_proof']['keys']=[r.guard_keys(frozen['remaining_ids'][1])[-2]]
        frozen['absence_proof']['keys_sha256']=r.c.state_hash(frozen['absence_proof']['keys'])
        with self.assertRaisesRegex(ValueError,'prior execution evidence'):
            r.validate(frozen,check_sources=False,now=NOW)

    def test_aggregate_complete_preserves_parent_and_never_repeats_completed(self):
        original=copy.deepcopy(self.control['coordinator:development']);self.reserve()
        state=self.coordinate()
        self.assertEqual(state['status'],'complete')
        self.assertEqual(self.spawned,self.freeze['remaining_ids'])
        self.assertEqual(self.control['coordinator:development'],original)
        aggregate=r.c.read(self.root/r.RECOVERY/'aggregate-state.json')
        self.assertEqual(len(aggregate['rows']),3)
        self.assertEqual(aggregate['rows'][self.plan['stage']['jobs'][0]['id']],self.base['rows'][self.plan['stage']['jobs'][0]['id']])
        self.assertEqual(aggregate['recovery_provenance']['original_status'],'failed')
        self.assertEqual(r.c.digest(self.root/r.RECOVERY/'aggregate-state.json'),state['aggregate_sha256'])
        self.coordinate()
        self.assertEqual(len(self.spawned),2)

    def test_durable_existing_recovery_receipt_is_retrieved_not_spawned_again(self):
        self.reserve();name=self.freeze['remaining_ids'][0];job=self.plan['stage']['jobs'][1]
        self.control[f'call:development:{name}']={'job_id':name,'call_id':'fc-existing',
                                               'job_sha256':r.c.state_hash(job),'recovery_freeze_sha256':self.hashed}
        self.calls['fc-existing']=SimpleNamespace(get=lambda timeout:self.row(job,'fc-existing'))
        state=self.coordinate()
        self.assertEqual(state['status'],'complete')
        self.assertEqual(self.spawned,[self.freeze['remaining_ids'][1]])

    def test_handleless_intent_fails_without_any_new_spawn(self):
        self.reserve();name=self.freeze['remaining_ids'][0]
        self.control[f'intent:development:{name}']={'job_sha256':'unknown'}
        state=self.coordinate()
        self.assertEqual(state['status'],'failed');self.assertEqual(self.spawned,[])
        self.assertFalse((self.root/r.RECOVERY/'aggregate-state.json').exists())

    def test_interrupted_spawn_retains_intent_and_is_never_repeated(self):
        self.reserve();self.spawn_error=KeyboardInterrupt()
        state=self.coordinate()
        self.assertEqual(state['status'],'failed')
        self.assertEqual(state['spawn_intent'],self.freeze['remaining_ids'][0])
        self.coordinate()
        self.assertEqual(len(self.spawned),1)

    def test_failed_worker_retained_without_fabricating_aggregate(self):
        self.reserve();self.fail_job=self.freeze['remaining_ids'][0]
        state=self.coordinate()
        self.assertEqual(state['status'],'failed')
        self.assertEqual(len(state['rows']),2)
        self.assertFalse((self.root/r.RECOVERY/'aggregate-state.json').exists())

    def test_stop_and_expiry_refuse_reservation(self):
        self.control['stop']={'requested':True}
        with self.assertRaisesRegex(ValueError,'stopped'):self.reserve()
        self.control.pop('stop')
        with self.assertRaisesRegex(ValueError,'expired'):
            r.reserve(self.control,self.freeze,self.hashed,now=r.DEADLINE)

    def test_stop_after_reservation_never_launches_worker(self):
        self.reserve();self.control['stop']={'requested':True}
        state=self.coordinate()
        self.assertEqual(state['status'],'stopped');self.assertEqual(self.spawned,[])

    def test_invalid_outcome_and_audit_fields_rejected(self):
        name=next(iter(self.base['rows']))
        for key,value in (('error',{'type':'bad'}),('reward',float('nan')),('alive',1),
                          ('case_sha256',None),('invalid_calls',-1),('stage','confirmation')):
            row=copy.deepcopy(self.base['rows'][name]);row[key]=value
            with self.assertRaises(ValueError):r.verify_rows({name:row},self.plan,self.base['calls'])

    def test_sources_and_ops_code_must_match_before_launch(self):
        with patch('lightlag_hybrid.worker.source_manifest',return_value={'changed':'hash'}):
            with self.assertRaisesRegex(ValueError,'protected source drift'):
                r.validate(self.freeze,self.root,now=NOW)
        (self.root/r.c.POLICY_FILE).write_text('changed weights')
        with patch('lightlag_hybrid.worker.source_manifest',return_value=self.plan['freeze']['source_sha256']):
            with self.assertRaisesRegex(ValueError,'policy drift'):r.validate(self.freeze,self.root,now=NOW)

    def test_foreign_recovery_receipt_is_not_adopted(self):
        self.reserve();job=self.plan['stage']['jobs'][1]
        self.control[f'call:development:{job["id"]}']={'call_id':'fc-foreign','job_sha256':r.c.state_hash(job)}
        state=self.coordinate()
        self.assertEqual(state['status'],'failed');self.assertEqual(self.spawned,[])

    def test_launcher_uses_exact_caps_detachment_allowlist_and_one_shot_receipt(self):
        captured={'functions':[],'spawns':[],'files':[]}
        state_path=self.root/'freeze.json';r.c.atomic(state_path,self.freeze)
        receipt_path=self.root/'receipt.json';(self.root/'.env').write_text('must never upload')
        test=self
        class Image:
            def pip_install(self,*args,**kwargs):return self
            def env(self,value):return self
            def add_local_dir(self,path,**kwargs):
                captured['files']=[str(p.relative_to(path)) for p in Path(path).rglob('*') if p.is_file()]
                return self
        class App:
            app_id='ap-fake-recovery'
            def __init__(self,name):captured['app']=name
            def function(self,**options):
                captured['functions'].append(options)
                def decorate(function):
                    def spawn(*args):
                        captured['spawns'].append(args)
                        test.assertEqual(r.c.read(receipt_path)['status'],'launching')
                        test.assertTrue(r.c.read(receipt_path)['spawn_intent'])
                        test.assertIn(r.KEY+':reservation',test.control)
                        return SimpleNamespace(object_id='fc-recovery')
                    return SimpleNamespace(spawn=spawn)
                return decorate
            def run(self,detach):captured['detached']=detach;return nullcontext()
        sdk=SimpleNamespace(Image=SimpleNamespace(debian_slim=lambda **kwargs:Image()),App=App,
                            Dict=SimpleNamespace(from_name=lambda name:self.control),
                            Volume=SimpleNamespace(from_name=lambda name:self.volume),enable_output=nullcontext)
        with patch('lightlag_hybrid.worker.source_manifest',return_value=self.plan['freeze']['source_sha256']):
            receipt=r.launch(state_path,receipt_path,self.root,sdk,now=NOW)
            with self.assertRaisesRegex(ValueError,'already reserved'):
                r.launch(state_path,self.root/'second-receipt.json',self.root,sdk,now=NOW)
        self.assertEqual(receipt['status'],'submitted')
        self.assertEqual(len(captured['spawns']),1)
        self.assertEqual(captured['app'],r.APP);self.assertTrue(captured['detached'])
        self.assertEqual(set(captured['files']),{'a.py',r.c.POLICY_FILE,r.OPS_FILE})
        worker,coordinator=captured['functions']
        self.assertEqual(worker['max_containers'],64);self.assertEqual(worker['timeout'],180)
        self.assertEqual(coordinator['max_containers'],1);self.assertTrue(coordinator['nonpreemptible'])
        for options in (worker,coordinator):
            self.assertEqual(options['cpu'],(1,1));self.assertEqual(options['memory'],(2048,2048))
            self.assertEqual(options['retries'],0);self.assertEqual(options['min_containers'],0)
            self.assertEqual(options['buffer_containers'],0);self.assertFalse(options['include_source'])


if __name__=='__main__':unittest.main()
