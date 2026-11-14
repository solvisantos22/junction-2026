"""Synthetic storage/call tests; no Modal service, inference or maps are used."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.learning_hybrid import cloud as c, manage as m


class MemoryDict:
    def __init__(self):self.data={}
    def put(self,key,value,skip_if_exists=False):
        if skip_if_exists and key in self.data:return False
        self.data[key]=deepcopy(value);return True
    def get(self,key,default=None):return deepcopy(self.data.get(key,default))


class Volume:
    def __init__(self):self.commits=0
    def reload(self):pass
    def commit(self):self.commits+=1


class Call:
    def __init__(self,identifier,row):self.object_id=identifier;self.row=row;self.cancelled=False
    def get(self,timeout=0):
        if isinstance(self.row,Exception):raise self.row
        return deepcopy(self.row)
    def cancel(self):self.cancelled=True


class Worker:
    def __init__(self,fail=False):self.calls={};self.inputs=[];self.fail=fail
    def spawn(self,plan,job):
        self.inputs.append((deepcopy(plan),deepcopy(job)));identifier='fc-'+job['id']
        call=Call(identifier,{'job_id':job['id'],'call_id':identifier,'status':'failed' if self.fail else 'complete',
                              'audit':{'physics_verified':True},'reward':.3})
        self.calls[identifier]=call;return call


def plan(count=3):
    sources={'a.py':'1'*64}
    return {'freeze':{'campaign':{'campaign_id':'test','deadline_unix':1000,'stages':m.STAGES,'max_jobs':18000},'source_sha256':sources},
            'freeze_sha256':'a'*64,'stage_sha256':'b'*64,
            'stage':{'name':'smoke','source_sha256':sources,'jobs':[{'id':f'j{i}','stage':'smoke','seed':1,'spec':{'id':f's{i}'}} for i in range(count)]}}


class CoordinatorTests(unittest.TestCase):
    def test_same_worker_call_reentry_does_not_reexecute_uncommitted_job(self):
        with tempfile.TemporaryDirectory() as temporary:
            p=plan(1);p['freeze']['policy_freeze_sha256']='policy-hash'
            job={**p['stage']['jobs'][0],'source_sha256':p['freeze']['source_sha256']}
            job['spec']['group']='test-group'
            control=MemoryDict();control.put('job:smoke:j0:execution',{'call_id':'same'})
            with patch.object(c,'digest',return_value='policy-hash'),patch.object(c.subprocess,'Popen') as child:
                row=c.run_worker(p,job,Volume(),control,root=temporary,call_id='same',clock=lambda:100)
                self.assertEqual(row['error_type'],'AmbiguousExecutionRequiresDiagnosis')
                self.assertEqual(row['status'],'failed');child.assert_not_called()
                again=c.run_worker(p,job,Volume(),control,root=temporary,call_id='same',clock=lambda:100)
                self.assertEqual(row,again);child.assert_not_called()

    def test_injects_source_keeps_call_receipts_and_never_repeats_completed(self):
        with tempfile.TemporaryDirectory() as temporary:
            worker,volume,control=Worker(),Volume(),MemoryDict();p=plan()
            kwargs=dict(root=temporary,call_id='coordinator',clock=lambda:100,get_call=worker.calls.__getitem__,sleeper=lambda x:None)
            result=c.coordinate(p,worker,volume,control,**kwargs)
            self.assertEqual(result['status'],'complete');self.assertEqual(result['jobs_complete'],3)
            self.assertEqual(len(worker.inputs),3)
            for minimal,job in worker.inputs:
                self.assertNotIn('jobs',minimal['stage']);self.assertEqual(job['source_sha256'],p['freeze']['source_sha256'])
                self.assertTrue((Path(temporary)/'smoke/receipts'/f'{job["id"]}.json').exists())
                self.assertIsNotNone(control.get('call:smoke:'+job['id']))
            self.assertEqual(c.coordinate(p,worker,volume,control,**kwargs),result)
            self.assertEqual(len(worker.inputs),3)

    def test_ambiguous_spawn_fails_without_resubmission(self):
        with tempfile.TemporaryDirectory() as temporary:
            worker,volume,control=Worker(),Volume(),MemoryDict()
            control.put('intent:smoke:j0',{'job_sha256':'anything'})
            result=c.coordinate(plan(),worker,volume,control,root=temporary,call_id='same',clock=lambda:100,sleeper=lambda x:None,get_call=worker.calls.__getitem__)
            self.assertEqual(result['status'],'failed');self.assertEqual(result['error_type'],'AmbiguousSpawnRequiresDiagnosis')
            self.assertFalse(worker.inputs)

    def test_receipt_survives_missing_local_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary:
            worker,volume,control=Worker(),Volume(),MemoryDict();p=plan(1)
            call=worker.spawn({},p['stage']['jobs'][0]);control.put('intent:smoke:j0',{})
            control.put('call:smoke:j0',{'job_id':'j0','call_id':call.object_id,'job_sha256':c.state_hash(p['stage']['jobs'][0])})
            result=c.coordinate(p,worker,volume,control,root=temporary,call_id='same',clock=lambda:100,sleeper=lambda x:None,get_call=worker.calls.__getitem__)
            self.assertEqual(result['status'],'complete');self.assertEqual(len(worker.inputs),1)

    def test_failure_stops_new_wave_without_zero_score(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(c,'MAX_CONTAINERS',1):
            worker,volume,control=Worker(fail=True),Volume(),MemoryDict()
            result=c.coordinate(plan(3),worker,volume,control,root=temporary,call_id='same',clock=lambda:100,sleeper=lambda x:None,get_call=worker.calls.__getitem__)
            self.assertEqual(result['status'],'failed');self.assertEqual(len(worker.inputs),1)
            self.assertEqual(len(result['rows']),1)

    def test_expired_stage_never_submits(self):
        with tempfile.TemporaryDirectory() as temporary:
            worker,volume,control=Worker(),Volume(),MemoryDict()
            result=c.coordinate(plan(),worker,volume,control,root=temporary,call_id='same',clock=lambda:1000,sleeper=lambda x:None,get_call=worker.calls.__getitem__)
            self.assertEqual(result['status'],'deadline');self.assertFalse(worker.inputs)

    def test_other_coordinator_cannot_multiply_stage(self):
        with tempfile.TemporaryDirectory() as temporary:
            control=MemoryDict();control.put('coordinator:smoke:owner','original')
            with self.assertRaisesRegex(ValueError,'coordinator'):
                c.coordinate(plan(),Worker(),Volume(),control,root=temporary,call_id='new')


class ReservationTests(unittest.TestCase):
    def test_metadata_download_reads_two_remote_files_not_every_call_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);p=plan(1);p['stage']['jobs'][0]['spec']['group']='test'
            row={'job_id':'j0','call_id':'fc-j0','status':'complete','seed':1,'spec_id':'s0','group':'test',
                 'case_sha256':'case-hash','audit':{'physics_verified':True,'case_sha256':'case-hash'}}
            state={'status':'complete','freeze_sha256':p['freeze_sha256'],'stage_sha256':p['stage_sha256'],
                   'coordinator_call_id':'coord','calls':{'j0':'fc-j0'},'rows':{'j0':row}}
            receipt={'stage':'smoke','freeze_sha256':p['freeze_sha256'],'stage_sha256':p['stage_sha256'],'coordinator_call_id':'coord'}
            c.atomic(root/'receipt.json',receipt)
            reads=[]
            class SDK:
                class Volume:
                    @staticmethod
                    def from_name(name):return SDK.Volume()
                    def read_file(self,name):
                        reads.append(name)
                        yield c.json.dumps({'smoke/state.json':state,'smoke/plan.json':p}[name]).encode()
            with patch.object(m,'status',return_value={'state':state}):
                self.assertEqual(m.download(root/'receipt.json',root/'download',sdk=SDK),state)
            self.assertEqual(reads,['smoke/state.json','smoke/plan.json'])

    def test_reservation_is_single_use_and_previous_stage_must_finish(self):
        control=MemoryDict();p=plan();m.reserve(control,p,100)
        with self.assertRaisesRegex(ValueError,'already reserved'):m.reserve(control,p,100)
        later=deepcopy(p);later['stage']['name']='development'
        with self.assertRaisesRegex(ValueError,'audited'):m.reserve(control,later,100)
        control.put('coordinator:smoke',{'status':'complete','jobs_complete':3})
        m.reserve(control,later,100)
        other=deepcopy(p);other['freeze_sha256']='x'*64
        with self.assertRaisesRegex(ValueError,'another campaign'):m.reserve(control,other,100)

    def test_stop_and_aggregate_job_budget_are_enforced(self):
        control=MemoryDict();control.put('stop',True)
        with self.assertRaisesRegex(ValueError,'stopped'):m.reserve(control,plan(),100)
        control=MemoryDict();p=plan();p['freeze']['campaign']['max_jobs']=2
        with self.assertRaisesRegex(ValueError,'cap exceeded'):m.reserve(control,p,100)


class FreezeTests(unittest.TestCase):
    def fixture(self,root):
        (root/'a.py').write_text('safe=1\n')
        parent={'schema':'learning-final-freeze-v1','smoke':False,'arms':[]}
        for algorithm in ('ppo','replay'):
            for seed in (17,29,43):
                policy={'algorithm':algorithm,'episodes_seen':8192}
                parent['arms'].append({'id':f'{algorithm}-{seed}-08192','kind':'policy','roles':['last'],
                                      'algorithm':algorithm,'training_seed':seed,'policy':policy,'policy_sha256':c.state_hash(policy)})
        c.atomic(root/c.POLICY_FILE,parent)
        return {'a.py':c.digest(root/'a.py')}

    def test_freeze_time_resource_policy_and_source_guards(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);pins=self.fixture(root);now=m.ABSOLUTE_DEADLINE-100
            campaign={'campaign_id':'test','deadline_unix':m.ABSOLUTE_DEADLINE,'stages':m.STAGES,'max_jobs':18000}
            with patch.object(m,'source_manifest',return_value=pins):
                freeze=m.write_freeze(root/'freeze.json',campaign,root,now)
                self.assertLess(freeze['running_compute_envelope_usd'],75)
                with self.assertRaises(FileExistsError):m.write_freeze(root/'freeze.json',campaign,root,now)
                for mutation in ('resource','deadline','policy','source'):
                    changed=deepcopy(freeze)
                    if mutation=='resource':changed['resources']['worker_max_containers']=100
                    if mutation=='deadline':changed['campaign']['deadline_unix']=now+21601
                    if mutation=='policy':changed['policy_freeze_sha256']='0'*64
                    if mutation=='source':changed['source_sha256']['a.py']='0'*64
                    with self.assertRaises(ValueError):m.validate_freeze(changed,root)

    def test_prepare_rejects_duplicate_jobs_and_used_worlds(self):
        from lightlag_hybrid.policy import build_specs
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);pins=self.fixture(root);now=m.ABSOLUTE_DEADLINE-100
            campaign={'campaign_id':'test','deadline_unix':m.ABSOLUTE_DEADLINE,'stages':m.STAGES,'max_jobs':18000}
            with patch.object(m,'source_manifest',return_value=pins):
                m.write_freeze(root/'freeze.json',campaign,root,now)
                spec=build_specs(c.read(root/c.POLICY_FILE))[0]
                stage={'schema':'learning-hybrid-stage-v1','name':'smoke','freeze_sha256':c.digest(root/'freeze.json'),
                       'source_sha256':pins,'jobs':[{'id':'one','stage':'smoke','seed':1,'spec':spec}]}
                c.atomic(root/'stage.json',stage);m.prepare(root/'freeze.json',root/'stage.json',root,now)
                stage['jobs'].append(deepcopy(stage['jobs'][0]));c.atomic(root/'stage.json',stage)
                with self.assertRaises(ValueError):m.prepare(root/'freeze.json',root/'stage.json',root,now)
                stage['jobs']=stage['jobs'][:1];stage['jobs'][0]['seed']=82001;c.atomic(root/'stage.json',stage)
                with self.assertRaises(ValueError):m.prepare(root/'freeze.json',root/'stage.json',root,now)

    def test_local_receipt_survives_launch_failure_and_blocks_repeat(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'receipt.json'
            class SDK:
                class Dict:
                    @staticmethod
                    def from_name(*args,**kwargs):raise RuntimeError('simulated before any cloud call')
            with patch.object(m,'validate_freeze'),patch.object(m,'copy_sources'):
                with self.assertRaises(RuntimeError):m.launch(plan(),path,sdk=SDK,now=100)
                self.assertEqual(c.read(path)['status'],'launch_error')
                with self.assertRaises(FileExistsError):m.launch(plan(),path,sdk=SDK,now=100)


if __name__=='__main__':unittest.main()
