"""Synthetic metadata only; no real rollouts, cloud jobs or selection evidence."""
import copy
from contextlib import nullcontext
import hashlib
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.learning_hybrid_ops import stages as s

NOW=s.r.DEADLINE-1000


class Control(dict):
    def put(self,key,value,skip_if_exists=False):
        if skip_if_exists and key in self:return False
        self[key]=copy.deepcopy(value);return True


class StageTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='hybrid-gated-test-');self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.patch(s.e,'MAPS',{'smoke':[1],'development':[610000,610001],
                              'confirmation':[611000,611001],'final':[612000,612001]})
        self.master=self.root/'master.json'
        self.master.write_bytes((s.ROOT/'docs/learning-hybrid-results/freeze.json').read_bytes())
        self.development=self.root/'development.json'
        s.e.prepare(self.master,'development',self.development)
        self.dev=s.c.read(self.development);self.master_value=s.c.read(self.master)
        self.patch(s.r,'ORIGINAL_STAGE',s.c.digest(self.development))
        self.patch(s.r,'ORIGINAL_STAGE_STATE',s.c.state_hash(self.dev))
        self.patch(s.r,'TOTAL',130);self.patch(s.r,'RETAINED',65);self.patch(s.r,'REMAINING',65)
        self.aggregate=self.complete(self.dev,s.c.digest(self.development),s.r.ORIGINAL_CALL)
        retained={**self.aggregate,'rows':dict(list(self.aggregate['rows'].items())[:65]),
                  'calls':dict(list(self.aggregate['calls'].items())[:65])}
        self.recovery={'original_plan':{'stage':self.dev,'freeze':self.master_value,'freeze_sha256':s.r.ORIGINAL_FREEZE},
                       'retained_state':retained,'retained_state_sha256':s.c.state_hash(retained),
                       'evidence_sha256':{'state.json':'e'*64}}
        self.recovery_path=self.root/'recovery.json';s.c.atomic(self.recovery_path,self.recovery)
        self.patch(s,'RECOVERY_FREEZE',s.c.digest(self.recovery_path))
        self.recovery_receipt_path=self.root/'recovery-receipt.json'
        s.c.atomic(self.recovery_receipt_path,{'schema':'learning-hybrid-recovery-receipt-v1','status':'submitted',
                    'freeze_sha256':s.RECOVERY_FREEZE,'coordinator_call_id':s.RECOVERY_CALL})
        self.aggregate['recovery_provenance']={'recovery_id':s.r.RECOVERY,'recovery_freeze_sha256':s.RECOVERY_FREEZE,
                'recovery_call_id':s.RECOVERY_CALL,'original_state_sha256':'e'*64,
                'retained_state_sha256':self.recovery['retained_state_sha256'],'original_status':'failed',
                'original_error_type':'KeyboardInterrupt','retained_calls':65,'new_calls':65}
        self.aggregate_path=self.root/'aggregate.json';s.c.atomic(self.aggregate_path,self.aggregate)
        self.dev_analysis=self.root/'development-analysis.json'
        s.e.analyze(self.development,self.aggregate_path,self.dev_analysis)
        self.confirmation=self.root/'confirmation.json'
        s.e.prepare(self.master,'confirmation',self.confirmation,self.dev_analysis)
        self.ops_path=self.root/'confirmation-ops.json'
        s.write_freeze(self.ops_path,master=self.master,stage=self.confirmation,parent_stage=self.development,
                       parent_status=self.aggregate_path,parent_analysis=self.dev_analysis,
                       recovery_freeze=self.recovery_path,recovery_receipt=self.recovery_receipt_path,now=NOW)
        self.ops=s.c.read(self.ops_path)
        self.control=Control({'campaign':{'freeze_sha256':s.r.ORIGINAL_FREEZE},
            s.r.KEY+':reservation':{'freeze_sha256':s.RECOVERY_FREEZE},
            s.r.KEY+':state':{'status':'complete','coordinator_call_id':s.RECOVERY_CALL,'jobs_complete':65,
                             'aggregate_sha256':s.c.state_hash(self.aggregate)},
            s.r.KEY+':receipt':s.c.read(self.recovery_receipt_path),s.r.KEY+':owner':s.RECOVERY_CALL,
            'coordinator:development':{'status':'failed','coordinator_call_id':s.r.ORIGINAL_CALL,'error_type':'KeyboardInterrupt'},
            'coordinator:development:owner':s.r.ORIGINAL_CALL,
            'coordinator:smoke':{'status':'complete','jobs_complete':65},'stage:smoke':{'jobs':65},
            'stage:development':{'jobs':130}})

    def patch(self,obj,name,value):
        patcher=patch.object(obj,name,value);patcher.start();self.addCleanup(patcher.stop)

    def complete(self,stage,stage_hash,call):
        rows={};calls={}
        for index,job in enumerate(stage['jobs']):
            name=job['id'];identifier=f'fc-synthetic-{stage["name"]}-{index}';calls[name]=identifier
            spec=job['spec'];score=.4 if spec['id']=='greedy' else .5 if spec['id']=='beam' else .45
            hashed=hashlib.sha256(name.encode()).hexdigest()
            rows[name]={'id':name,'job_id':name,'stage':stage['name'],'call_id':identifier,
                'seed':job['seed'],'spec_id':spec['id'],'group':spec['group'],'status':'complete',
                'job_sha256':s.c.state_hash({**job,'source_sha256':stage['source_sha256']}),
                'reward':score,'home':True,'alive':True,'invalid_calls':0,'error':None,
                'artifact':f'{stage["name"]}/jobs/{name}/case.json.gz','sha256':hashed,'case_sha256':hashed,
                'audit':{'schema':'learning-hybrid-case-audit-v1','job_id':name,'case_sha256':hashed,
                         'physics_verified':True,'hybrid_choices_verified':spec['kind']!='beam',
                         'full_controller_replay':stage['name']=='final'}}
        return {'schema':'learning-hybrid-stage-status-v1','stage':stage['name'],'status':'complete',
                'freeze_sha256':stage['freeze_sha256'],'stage_sha256':stage_hash,'coordinator_call_id':call,
                'rows':rows,'calls':calls,'jobs_total':len(rows),'jobs_complete':len(rows)}

    def final_fixture(self):
        confirmation=s.c.read(self.confirmation)
        state=self.complete(confirmation,s.c.digest(self.confirmation),'fc-confirmation')
        state_path=self.root/'confirmation-status.json';s.c.atomic(state_path,state)
        analysis=self.root/'confirmation-analysis.json';s.e.analyze(self.confirmation,state_path,analysis)
        final_stage=self.root/'final.json';s.e.prepare(self.master,'final',final_stage,analysis)
        receipt_path=self.root/'confirmation-receipt.json'
        s.c.atomic(receipt_path,{'schema':'learning-hybrid-receipt-v1','status':'submitted','stage':'confirmation',
               'freeze_sha256':s.r.ORIGINAL_FREEZE,'stage_sha256':s.c.digest(self.confirmation),
               'ops_freeze_sha256':s.c.digest(self.ops_path),'coordinator_call_id':'fc-confirmation'})
        path=self.root/'final-ops.json'
        s.write_freeze(path,master=self.master,stage=final_stage,parent_stage=self.confirmation,
            parent_status=state_path,parent_analysis=analysis,previous_ops_freeze=self.ops_path,
            previous_receipt=receipt_path,now=NOW)
        self.control['stage:confirmation']={'jobs':len(confirmation['jobs']),'ops_freeze_sha256':s.c.digest(self.ops_path)}
        self.control['coordinator:confirmation']={'status':'complete','jobs_complete':len(confirmation['jobs']),
                 'coordinator_call_id':'fc-confirmation','stage_sha256':s.c.digest(self.confirmation)}
        self.control['coordinator-receipt:confirmation']=s.c.read(receipt_path)
        self.final_parent_result=state
        return path,s.c.read(path)

    def get_confirmation(self,identifier):
        self.assertEqual(identifier,'fc-confirmation')
        return SimpleNamespace(get=lambda timeout:copy.deepcopy(self.final_parent_result))

    def test_original_selection_and_stage_functions_reproduce_complete_chain(self):
        result=s.validate(self.ops,now=NOW)
        self.assertEqual(result['plan']['stage'],s.c.read(self.confirmation))
        path,final=self.final_fixture();s.validate(final,now=NOW)
        self.assertEqual(len(final['plan']['stage']['primary_groups']),1)
        s.reserve(self.control,final,s.c.digest(path),now=NOW,get_call=self.get_confirmation)
        self.assertEqual(self.control['coordinator:development']['status'],'failed')

    def test_no_eligible_groups_never_open_following_maps(self):
        bad=copy.deepcopy(self.ops)
        bad['evidence']['parent_analysis']['value']['selected_groups']=[]
        bad['evidence']['parent_analysis']=self.item(bad['evidence']['parent_analysis']['value'],'pretty')
        with self.assertRaisesRegex(ValueError,'analysis differs|no eligible'):
            s.validate(bad,now=NOW)

    def test_genuine_empty_selection_refuses_confirmation(self):
        bad=copy.deepcopy(self.ops);state=bad['evidence']['parent_status']['value']
        for job in self.dev['jobs']:
            if job['spec']['family'] in s.e.FAMILIES:
                state['rows'][job['id']].update(alive=False,home=False)
        recovery=bad['evidence']['recovery_freeze']['value'];base=recovery['retained_state']
        base['rows']={name:state['rows'][name] for name in base['rows']}
        recovery['retained_state_sha256']=s.c.state_hash(base)
        recovery_hash=s.c.state_hash(recovery)
        state['recovery_provenance'].update(recovery_freeze_sha256=recovery_hash,
                                          retained_state_sha256=recovery['retained_state_sha256'])
        bad['evidence']['recovery_receipt']['value']['freeze_sha256']=recovery_hash
        for key in ('parent_status','recovery_freeze','recovery_receipt'):
            bad['evidence'][key]=self.item(bad['evidence'][key]['value'])
        state_path=self.root/'negative-status.json';s.c.atomic(state_path,state)
        analysis_path=self.root/'negative-analysis.json';s.e.analyze(self.development,state_path,analysis_path)
        self.assertEqual(s.c.read(analysis_path)['selected_groups'],[])
        bad['evidence']['parent_analysis']=s.evidence(analysis_path)
        with patch.object(s,'RECOVERY_FREEZE',recovery_hash):
            with self.assertRaisesRegex(ValueError,'no eligible group'):s.validate(bad,now=NOW)

    @staticmethod
    def item(value,encoding='canonical'):
        return {'value':value,'encoding':encoding,'sha256':hashlib.sha256(s.encoded(value,encoding)).hexdigest()}

    def test_evidence_hash_and_recovery_call_tampering_refused(self):
        for key in ('parent_analysis','parent_status','recovery_receipt'):
            bad=copy.deepcopy(self.ops);bad['evidence'][key]['sha256']='0'*64
            with self.assertRaisesRegex(ValueError,'evidence bytes changed'):s.validate(bad,now=NOW)
        bad=copy.deepcopy(self.ops);bad['evidence']['recovery_receipt']['value']['coordinator_call_id']='fc-wrong'
        bad['evidence']['recovery_receipt']=self.item(bad['evidence']['recovery_receipt']['value'])
        with self.assertRaisesRegex(ValueError,'receipt differs'):s.validate(bad,now=NOW)

    def test_changed_stage_or_reserved_map_refused_even_with_updated_evidence_hash(self):
        for seed in (500,82000,2027):
            bad=copy.deepcopy(self.ops);bad['evidence']['stage']['value']['jobs'][0]['seed']=seed
            bad['evidence']['stage']=self.item(bad['evidence']['stage']['value'],'pretty')
            with self.assertRaisesRegex(ValueError,'stage differs'):s.validate(bad,now=NOW)

    def test_parent_must_be_complete_and_retain_exact_original_rows(self):
        bad=copy.deepcopy(self.ops);state=bad['evidence']['parent_status']['value'];state['status']='failed'
        bad['evidence']['parent_status']=self.item(state)
        with self.assertRaisesRegex(ValueError,'incomplete'):s.validate(bad,now=NOW)
        bad=copy.deepcopy(self.ops);state=bad['evidence']['parent_status']['value']
        first=next(iter(state['rows']));state['rows'][first]['reward']=.99
        bad['evidence']['parent_status']=self.item(state)
        with self.assertRaisesRegex(ValueError,'retained original results changed'):s.validate(bad,now=NOW)

    def test_duplicate_reservation_and_live_aggregate_mismatch_fail_closed(self):
        hashed=s.c.digest(self.ops_path)
        self.control[s.r.KEY+':state']['aggregate_sha256']='wrong'
        with self.assertRaisesRegex(ValueError,'aggregate differs'):s.reserve(self.control,self.ops,hashed,now=NOW)
        self.control[s.r.KEY+':state']['aggregate_sha256']=s.c.state_hash(self.aggregate)
        s.reserve(self.control,self.ops,hashed,now=NOW)
        with self.assertRaisesRegex(ValueError,'already reserved'):s.reserve(self.control,self.ops,hashed,now=NOW)

    def test_final_requires_completed_confirmation_and_correct_ops_reservation(self):
        path,final=self.final_fixture();self.control['coordinator:confirmation']['status']='running'
        with self.assertRaisesRegex(ValueError,'confirmation not complete'):
            s.reserve(self.control,final,s.c.digest(path),now=NOW)
        self.control['coordinator:confirmation']['status']='complete'
        self.control['stage:confirmation']['ops_freeze_sha256']='wrong'
        with self.assertRaisesRegex(ValueError,'confirmation not complete'):
            s.reserve(self.control,final,s.c.digest(path),now=NOW)

    def test_final_parent_rows_are_bound_to_original_terminal_result_and_live_receipt(self):
        path,final=self.final_fixture()
        forged=copy.deepcopy(final)
        row=next(iter(forged['evidence']['parent_status']['value']['rows'].values()));row['reward']=.99
        with self.assertRaisesRegex(ValueError,'results differ from original terminal call'):
            s.reserve(self.control,forged,s.c.digest(path),now=NOW,get_call=self.get_confirmation)
        self.control['coordinator-receipt:confirmation']['app_id']='different-app'
        with self.assertRaisesRegex(ValueError,'live confirmation receipt differs'):
            s.reserve(self.control,final,s.c.digest(path),now=NOW,get_call=self.get_confirmation)

    def test_pause_deadline_and_original_failure_preservation(self):
        self.control['stop']={'user':True}
        with self.assertRaisesRegex(ValueError,'stop marker'):s.reserve(self.control,self.ops,'ops',now=NOW)
        self.control.pop('stop')
        with self.assertRaisesRegex(ValueError,'deadline'):s.reserve(self.control,self.ops,'ops',now=s.r.DEADLINE)
        self.control['coordinator:development']['status']='complete'
        with self.assertRaisesRegex(ValueError,'failure must remain'):s.reserve(self.control,self.ops,'ops',now=NOW)

    def test_ops_source_drift_refused(self):
        bad=copy.deepcopy(self.ops);bad['ops_source_sha256'][s.OPS_FILES[0]]='changed'
        with self.assertRaisesRegex(ValueError,'ops identity'):s.validate(bad,now=NOW)

    def test_cloud_wrapper_retains_manifest_and_uses_original_coordinator(self):
        hashed=s.c.digest(self.ops_path);s.reserve(self.control,self.ops,hashed,now=NOW)
        volume=SimpleNamespace(reload=lambda:None,commit=lambda:None);worker=object()
        with patch.object(s.c,'coordinate',return_value={'status':'synthetic'}) as coordinate:
            result=s.run_stage(self.ops['plan'],self.ops,hashed,worker,volume,self.control,root=self.root/'remote')
        self.assertEqual(result,{'status':'synthetic'})
        coordinate.assert_called_once_with(self.ops['plan'],worker,volume,self.control)
        self.assertEqual(s.c.digest(self.root/'remote/confirmation/ops-freeze.json'),hashed)

    def test_launcher_caps_receipt_compatibility_and_ambiguous_reservation(self):
        captured={'functions':[],'spawns':[],'files':[]}
        receipt_path=self.root/'launch-receipt.json';test=self
        class Image:
            def pip_install(self,*args,**kwargs):return self
            def env(self,value):return self
            def add_local_dir(self,path,**kwargs):
                captured['files']=[str(p.relative_to(path)) for p in Path(path).rglob('*') if p.is_file()]
                return self
        class App:
            app_id='ap-synthetic-confirmation'
            def __init__(self,name):captured['app']=name
            def function(self,**options):
                captured['functions'].append(options)
                def decorate(function):
                    def spawn(*args):
                        captured['spawns'].append(args)
                        test.assertEqual(s.c.read(receipt_path)['status'],'launching')
                        test.assertTrue(s.c.read(receipt_path)['spawn_intent'])
                        test.assertIn('stage:confirmation',test.control)
                        return SimpleNamespace(object_id='fc-synthetic-confirmation')
                    return SimpleNamespace(spawn=spawn)
                return decorate
            def run(self,detach):captured['detached']=detach;return nullcontext()
        sdk=SimpleNamespace(Image=SimpleNamespace(debian_slim=lambda **kwargs:Image()),App=App,
              Dict=SimpleNamespace(from_name=lambda name:self.control),Volume=SimpleNamespace(from_name=lambda name:object()),
              enable_output=nullcontext)
        receipt=s.launch(self.ops_path,receipt_path,sdk=sdk,now=NOW)
        self.assertEqual(receipt['schema'],'learning-hybrid-receipt-v1')
        self.assertEqual(receipt['freeze_sha256'],s.r.ORIGINAL_FREEZE)
        self.assertEqual(receipt['ops_freeze_sha256'],s.c.digest(self.ops_path))
        self.assertEqual(receipt['status'],'submitted');self.assertTrue(captured['detached'])
        self.assertEqual(len(captured['spawns']),1)
        worker,coordinator=captured['functions']
        self.assertEqual(worker['max_containers'],64);self.assertEqual(worker['timeout'],180)
        self.assertEqual(coordinator['max_containers'],1);self.assertTrue(coordinator['nonpreemptible'])
        for options in (worker,coordinator):
            self.assertEqual(options['cpu'],(1,1));self.assertEqual(options['memory'],(2048,2048))
            self.assertEqual(options['retries'],0);self.assertFalse(options['include_source'])
        expected=set(self.master_value['source_sha256'])|{s.c.POLICY_FILE}|set(s.OPS_FILES)
        self.assertEqual(set(captured['files']),expected)
        with self.assertRaisesRegex(ValueError,'already reserved'):
            s.launch(self.ops_path,self.root/'duplicate-receipt.json',sdk=sdk,now=NOW)
        self.assertEqual(len(captured['spawns']),1)


if __name__=='__main__':unittest.main()
