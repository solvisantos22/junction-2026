"""Offline launcher tests: fake Modal SDK, synthetic sources, no training or network."""
from contextlib import nullcontext
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.learning_hybrid_train import modal_job as m

NOW=m.ABSOLUTE_DEADLINE-4*3600


def campaign():
    return {'campaign_id':'greedy-prior-20261115','deadline_unix':m.ABSOLUTE_DEADLINE,
            'max_seconds':10800,'jobs':copy.deepcopy(m.JOBS)}


class Control:
    def __init__(self):self.data={}
    def put(self,key,value,skip_if_exists=False):
        if skip_if_exists and key in self.data:return False
        self.data[key]=copy.deepcopy(value);return True
    def get(self,key,default=None):return copy.deepcopy(self.data.get(key,default))


class Volume:
    def __init__(self):self.commits=0
    def commit(self):self.commits+=1


class SDK:
    def __init__(self,receipt):
        self.receipt=Path(receipt);self.control=Control();self.volume=Volume();self.calls=[];self.apps=0;self.options=None;self.uploads=[];self.installs=[]
        self.Dict=SimpleNamespace(from_name=lambda *a,**kw:self.control)
        self.Volume=SimpleNamespace(from_name=self.volume_from_name)
        self.Image=SimpleNamespace(debian_slim=lambda **kw:self)
    def volume_from_name(self,name,**kwargs):
        assert name==m.VOLUME_NAME and kwargs=={'create_if_missing':True,'version':2};return self.volume
    def pip_install(self,*args,**kwargs):self.installs.append((args,kwargs));return self
    def add_local_dir(self,path,**kwargs):
        assert kwargs=={'remote_path':'/app','copy':True}
        self.uploads=[str(p.relative_to(path)) for p in Path(path).rglob('*') if p.is_file()];return self
    def App(self,name):
        assert name==m.APP_NAME;self.apps+=1
        return SimpleNamespace(app_id='ap-fake',function=self.function,run=lambda **kw:nullcontext())
    def function(self,**kwargs):self.options=kwargs;return lambda f:SimpleNamespace(spawn=self.spawn)
    def enable_output(self):return nullcontext()
    def spawn(self,plan,job):
        receipt=m.read(self.receipt)
        assert receipt['status']=='launching' and receipt['spawn_intent']==job['run_id'] and len(receipt['jobs'])==len(self.calls)
        self.calls.append((plan,job));return SimpleNamespace(object_id='fc-'+job['run_id'])


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup);self.root=Path(self.temporary.name)
        for package in m.PACKAGES:
            p=self.root/package;p.mkdir(parents=True,exist_ok=True);(p/'__init__.py').write_text('fixture\n')
        (self.root/'lightlag_hybrid_train/train.py').write_text('synthetic trainer\n')
        protocol=self.root/m.PROTOCOL;protocol.parent.mkdir(parents=True,exist_ok=True);protocol.write_text('synthetic protocol\n')
        (self.root/'.env').write_text('PRIVATE_TEST=not-uploaded\n');(self.root/'docs/private.md').write_text('private\n')
        self.freeze_path=self.root/'freeze.json';self.freeze=m.write_freeze(self.freeze_path,campaign(),self.root,NOW)
        self.plan=m.prepare(self.freeze_path,self.root,NOW)

    def test_exact_jobs_deadlines_budget_and_private_files(self):
        self.assertAlmostEqual(self.freeze['running_compute_envelope_usd'],9.092736)
        self.assertFalse(self.freeze['resume_allowed']);self.assertEqual(self.freeze['running_compute_cap_usd'],15)
        m.copy_sources(self.plan,self.root/'copied',self.root)
        uploaded={str(p.relative_to(self.root/'copied')) for p in (self.root/'copied').rglob('*') if p.is_file()}
        self.assertEqual(uploaded,set(self.freeze['source_sha256']))
        self.assertNotIn('.env',uploaded);self.assertNotIn('docs/private.md',uploaded)
        self.assertIn('lightlag_hybrid_train/train.py',uploaded)
        self.assertEqual((m.APP_NAME,m.VOLUME_NAME,m.CONTROL_NAME),('junction-greedy-prior',)*3)

    def test_rejects_subset_new_seed_resume_oversize_or_late_deadline(self):
        edits=[lambda x:x.update(deadline_unix=m.ABSOLUTE_DEADLINE+1),lambda x:x.update(max_seconds=10801),
               lambda x:x.update(campaign_id='other'),lambda x:x['jobs'].pop(),lambda x:x['jobs'][0].update(seed=18),
               lambda x:x['jobs'][0].update(episodes=8192),lambda x:x.update(resume=True),lambda x:x['jobs'].reverse()]
        for edit in edits:
            value=campaign();edit(value)
            with self.assertRaises(ValueError):m.validate_campaign(value,NOW)

    def test_exclusive_freeze_and_source_drift(self):
        with self.assertRaises(FileExistsError):m.write_freeze(self.freeze_path,campaign(),self.root,NOW)
        (self.root/'lightlag_hybrid_train/train.py').write_text('changed\n')
        with self.assertRaisesRegex(ValueError,'source changed'):m.prepare(self.freeze_path,self.root,NOW)
        (self.root/'lightlag_hybrid_train/leak.py').symlink_to(self.root/'.env')
        with self.assertRaisesRegex(ValueError,'escaping'):m.source_manifest(self.root)

    def test_launch_records_each_of_six_handles_and_caps_resources(self):
        path=self.root/'receipt.json';sdk=SDK(path)
        with patch.object(m.time,'time',return_value=NOW):receipt=m.launch(self.plan,path,self.root,sdk,NOW)
        self.assertEqual(receipt['status'],'submitted');self.assertEqual(len(receipt['jobs']),6)
        self.assertEqual({j['call_id'] for j in receipt['jobs']},{'fc-'+j['run_id'] for j in m.JOBS})
        self.assertEqual(sdk.options['cpu'],(8,8));self.assertEqual(sdk.options['memory'],(16384,16384))
        self.assertEqual(sdk.options['max_containers'],6);self.assertEqual(sdk.options['retries'],0)
        self.assertTrue(sdk.options['single_use_containers']);self.assertFalse(sdk.options['include_source']);self.assertNotIn('secrets',sdk.options)
        self.assertEqual(receipt['reservation']['deadline_unix'],NOW+10800)
        for job in m.JOBS:self.assertIsNotNone(sdk.control.get('receipt:'+job['run_id']))
        sdk.receipt=self.root/'second.json'
        with self.assertRaisesRegex(ValueError,'already reserved'):m.launch(self.plan,sdk.receipt,self.root,sdk,NOW)
        self.assertEqual(sdk.apps,1)

    def test_partial_spawn_preserves_handles_and_blocks_repeat(self):
        path=self.root/'partial.json';sdk=SDK(path);original=sdk.spawn
        def fail(plan,job):
            if len(sdk.calls)==2:raise RuntimeError('synthetic transport interruption')
            return original(plan,job)
        sdk.spawn=fail
        with patch.object(m.time,'time',return_value=NOW),self.assertRaises(RuntimeError):m.launch(self.plan,path,self.root,sdk,NOW)
        receipt=m.read(path);self.assertEqual(receipt['status'],'launch_error');self.assertEqual(len(receipt['jobs']),2)
        self.assertEqual(receipt['spawn_intent'],'prior-43')
        with self.assertRaises(ValueError):m.reserve(sdk.control,self.plan,NOW)

    def test_stop_and_absolute_expiry_prevent_submission(self):
        control=Control();control.put('stop',True)
        with self.assertRaisesRegex(ValueError,'stopped'):m.reserve(control,self.plan,NOW)
        with self.assertRaisesRegex(ValueError,'expired'):m.prepare(self.freeze_path,self.root,m.ABSOLUTE_DEADLINE)
        control=Control();reservation=m.reserve(control,self.plan,m.ABSOLUTE_DEADLINE-20)
        self.assertEqual(reservation['deadline_unix'],m.ABSOLUTE_DEADLINE)

    def test_same_call_execution_intent_rejects_automatic_resume(self):
        control=Control();m.reserve(control,self.plan,NOW);job=m.JOBS[0]
        control.put('execution:'+job['run_id'],{'call_id':'fc-existing'})
        fake=SimpleNamespace(current_function_call_id=lambda:'fc-existing')
        volume=Volume();runner=m.make_remote_runner(volume,control)
        with patch.dict('sys.modules',{'modal':fake}),patch('subprocess.Popen') as child:
            result=runner({**self.plan,'app_id':'ap-test'},job,str(self.root),str(self.root/'results'))
            self.assertEqual(result['status'],'ambiguous_execution');child.assert_not_called()
            second=runner({**self.plan,'app_id':'ap-test'},job,str(self.root),str(self.root/'results'))
            self.assertEqual(second['status'],'ambiguous_execution');child.assert_not_called()

    def test_completed_job_is_not_reexecuted_by_same_or_new_call(self):
        control=Control();m.reserve(control,self.plan,NOW);job=m.JOBS[0]
        control.put('owner:'+job['run_id'],'fc-original');control.put('job:'+job['run_id'],{'status':'completed','call_id':'fc-original'})
        runner=m.make_remote_runner(Volume(),control)
        with patch.dict('sys.modules',{'modal':SimpleNamespace(current_function_call_id=lambda:'fc-original')}):
            self.assertEqual(runner({**self.plan,'app_id':'ap-test'},job)['status'],'completed')
        with patch.dict('sys.modules',{'modal':SimpleNamespace(current_function_call_id=lambda:'fc-other')}):
            with self.assertRaisesRegex(ValueError,'another call'):runner({**self.plan,'app_id':'ap-test'},job)

    def test_completion_is_published_only_after_terminal_artifacts_commit(self):
        control=Control();m.reserve(control,self.plan,NOW);job=m.JOBS[0];states_at_commit=[]
        class RecordingVolume:
            def commit(self):states_at_commit.append(control.get('job:'+job['run_id'],{}).get('status'))
        output=self.root/'results';report={'schema':'hybrid-ppo-training-report-v1','experiment':m.EXPERIMENT,
            'variant':'prior','seed':17,'episodes_target':4096,'episodes_completed':4096,'status':'complete',
            'source_sha256':self.freeze['source_sha256'],'validations':{str(n):{} for n in (0,512,2048,4096)}}
        def completed_process(command,**kwargs):
            self.assertIn('--variant',command);self.assertNotIn('--resume',command)
            m.atomic(output/job['run_id']/'report.json',report)
            return SimpleNamespace(returncode=0,poll=lambda:0)
        fake_modules={'modal':SimpleNamespace(current_function_call_id=lambda:'fc-new'),
                      'numpy':SimpleNamespace(__version__='2.3.4'),
                      'torch':SimpleNamespace(__version__='2.9.1+cpu',version=SimpleNamespace(cuda=None))}
        with patch.dict('sys.modules',fake_modules),patch.object(m.time,'time',return_value=NOW),patch('subprocess.Popen',side_effect=completed_process):
            result=m.make_remote_runner(RecordingVolume(),control)({**self.plan,'app_id':'ap-test'},job,str(self.root),str(output))
        self.assertEqual(result['status'],'completed')
        self.assertTrue(states_at_commit);self.assertNotIn('completed',states_at_commit)
        self.assertEqual(control.get('job:'+job['run_id'])['status'],'completed')

    def test_failed_terminal_commit_does_not_publish_success(self):
        control=Control();m.reserve(control,self.plan,NOW);job=m.JOBS[0]
        control.put('execution:'+job['run_id'],{'call_id':'fc-existing'})
        control.put('job:'+job['run_id'],{'status':'running'})
        class BrokenVolume:
            def commit(self):raise RuntimeError('synthetic failed commit')
        with patch.dict('sys.modules',{'modal':SimpleNamespace(current_function_call_id=lambda:'fc-existing')}):
            with self.assertRaises(RuntimeError):
                m.make_remote_runner(BrokenVolume(),control)({**self.plan,'app_id':'ap-test'},job,str(self.root),str(self.root/'results'))
        self.assertEqual(control.get('job:'+job['run_id'])['status'],'running')

    def test_status_retains_validated_progress_missing_early_and_source_errors(self):
        receipt={'schema':'greedy-prior-receipt-v1','volume':m.VOLUME_NAME,'campaign_id':'greedy-prior-20261115',
                 'freeze_sha256':self.plan['freeze_sha256'],'source_sha256':self.freeze['source_sha256'],
                 'jobs':[{**job,'call_id':'fc-'+job['run_id']} for job in m.JOBS]}
        path=self.root/'status-receipt.json';m.atomic(path,receipt);control=Control();m.reserve(control,self.plan,NOW)
        def read_file(name):
            run_id=name.split('/')[0]
            if run_id=='prior-29':raise FileNotFoundError(name)
            job=next(job for job in m.JOBS if job['run_id']==run_id)
            report={'schema':'hybrid-ppo-training-report-v1','experiment':m.EXPERIMENT,'variant':job['variant'],
                    'seed':job['seed'],'episodes_target':4096,'episodes_completed':512,'status':'running',
                    'source_sha256':self.freeze['source_sha256'],'phase':'training-00512','updated_unix':NOW,'validations':{'0':{},'512':{}}}
            if run_id=='prior-43':report['source_sha256']={}
            yield json.dumps(report).encode()
        def pending(**kwargs):raise TimeoutError()
        sdk=SimpleNamespace(Dict=SimpleNamespace(from_name=lambda *a,**kw:control),
            Volume=SimpleNamespace(from_name=lambda *a,**kw:SimpleNamespace(read_file=read_file)),
            FunctionCall=SimpleNamespace(from_id=lambda identifier:SimpleNamespace(get=pending)))
        result=m.status(path,sdk)
        self.assertEqual(result['jobs'][0]['progress']['episodes_completed'],512)
        self.assertEqual(result['jobs'][0]['progress']['phase'],'training-00512')
        self.assertEqual(len(result['jobs'][0]['progress']['report_sha256']),64)
        self.assertIsNone(result['jobs'][1]['progress']);self.assertNotIn('progress_error_type',result['jobs'][1])
        self.assertEqual(result['jobs'][2]['progress_error_type'],'ValueError')


if __name__=='__main__':unittest.main()
