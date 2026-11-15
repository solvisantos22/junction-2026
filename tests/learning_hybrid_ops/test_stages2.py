"""Synthetic rows only; protected science/selection code is never modified."""
import copy
from contextlib import nullcontext
import hashlib
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from lightlag_hybrid import worker as scientific_worker
from tools.learning_hybrid_ops import stages2 as s

NOW=s.r.DEADLINE-1000
FROZEN=Path('/tmp/junction-hybrid-frozen')


class Control(dict):
    def put(self,key,value,skip_if_exists=False):
        if skip_if_exists and key in self:return False
        self[key]=copy.deepcopy(value);return True


class Stage2Tests(unittest.TestCase):
    def patch(self,obj,name,value):
        p=patch.object(obj,name,value);p.start();self.addCleanup(p.stop)

    @staticmethod
    def item(value):
        return {'value':value,'encoding':'canonical','sha256':s.c.state_hash(value)}

    @staticmethod
    def mapped(raw,attempt):
        original=raw['artifact'];cost=raw['running_compute_estimate_usd']
        artifact=f'{attempt}/artifacts/{original}'
        return {**raw,'artifact':artifact,'running_compute_estimate_usd':3*cost,'allocation_rate_multiplier':3,
                'storage':{'volume':s.c.VOLUME_NAME,'artifact':artifact,'raw_row':artifact.replace('case.json.gz','row.json'),
                           'raw_row_sha256':s.c.state_hash(raw),'original_artifact':original,
                           'raw_running_compute_estimate_usd':cost,'attempt':attempt}}

    def complete(self,stage,hashed,call,attempt=None):
        rows={};calls={}
        for i,job in enumerate(stage['jobs']):
            name=job['id'];identifier=f'fc-{stage["name"]}-{i}';calls[name]=identifier;spec=job['spec']
            value=.4 if spec['id']=='greedy' else .5 if spec['id']=='beam' else .45
            case_hash=hashlib.sha256(name.encode()).hexdigest()
            row={'id':name,'job_id':name,'stage':stage['name'],'call_id':identifier,'seed':job['seed'],
                 'spec_id':spec['id'],'group':spec['group'],'status':'complete','reward':value,'home':True,
                 'alive':True,'invalid_calls':0,'error':None,'job_sha256':s.c.state_hash({**job,'source_sha256':stage['source_sha256']}),
                 'artifact':f'{stage["name"]}/jobs/{name}/case.json.gz','sha256':case_hash,'case_sha256':case_hash,
                 'running_compute_estimate_usd':.001,
                 'audit':{'schema':'learning-hybrid-case-audit-v1','job_id':name,'case_sha256':case_hash,
                          'physics_verified':True,'hybrid_choices_verified':spec['kind']!='beam',
                          'full_controller_replay':stage['name']=='final'}}
            rows[name]=self.mapped(row,attempt) if attempt else row
        return {'schema':'learning-hybrid-stage-status-v1','stage':stage['name'],'status':'complete',
                'freeze_sha256':stage['freeze_sha256'],'stage_sha256':hashed,'coordinator_call_id':call,
                'rows':rows,'calls':calls,'jobs_total':len(rows),'jobs_complete':len(rows),
                'started_unix':NOW,'ended_unix':NOW+5}

    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='hybrid-stage2-test-');self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        self.patch(s.e,'MAPS',{'smoke':[1],'development':[610000,610001],
                              'confirmation':[611000,611001],'final':[612000,612001]})
        self.master=self.root/'master.json'
        self.master.write_bytes((s.ROOT/'docs/learning-hybrid-results/freeze.json').read_bytes())
        self.master_value=s.c.read(self.master)
        # Main legitimately differs from the old scientific freeze. These are
        # metadata-unit fixtures, not a bypass usable by production validation.
        self.patch(scientific_worker,'source_manifest',lambda root=None:self.master_value['source_sha256'])
        self.patch(s.m,'validate_freeze',lambda value,root:s.c.policies_from_file(s.e.PARENT))
        self.patch(s.r,'validate',lambda value,root,now=None:value['original_plan'])
        self.patch(s.r,'TOTAL',130);self.patch(s.r,'RETAINED',80);self.patch(s.r,'RUN_COUNT',50)
        self.patch(s.r,'RETRY_COUNT',2);self.patch(s.r,'NEW_COUNT',48)
        self.development=self.root/'development.json';s.e.prepare(self.master,'development',self.development)
        self.dev=s.c.read(self.development)
        self.patch(s.r,'ORIGINAL_STAGE',s.c.digest(self.development))
        self.patch(s.first,'ORIGINAL_STAGE_STATE',s.c.state_hash(self.dev))
        self.aggregate=self.complete(self.dev,s.c.digest(self.development),s.r.ORIGINAL_CALL)
        ids=list(self.aggregate['rows']);self.run_ids=ids[80:]
        base={**self.aggregate,'rows':{n:self.aggregate['rows'][n] for n in ids[:80]},
              'calls':{n:self.aggregate['calls'][n] for n in ids[:80]}}
        for n in self.run_ids:self.aggregate['rows'][n]=self.mapped(self.aggregate['rows'][n],s.r.RECOVERY)
        self.recovery={'original_plan':{'freeze':self.master_value,'stage':self.dev,'freeze_sha256':s.r.ORIGINAL_FREEZE},
                       'retained_state':base,'retained_state_sha256':s.c.state_hash(base),'run_ids':self.run_ids,
                       'retry_ids':self.run_ids[:2],'failed_attempts':[{'job_id':n,'call_id':'fc-failed-'+str(i)}
                                                                      for i,n in enumerate(self.run_ids[:2])],
                       'budget_ledger':s.r.budget_ledger(self.master_value,NOW)}
        self.recovery_path=self.root/'recovery2.json';s.c.atomic(self.recovery_path,self.recovery)
        self.recovery_hash=s.c.digest(self.recovery_path)
        self.recovery_receipt={'schema':'learning-hybrid-recovery2-receipt-v1','status':'submitted',
                               'recovery_id':s.r.RECOVERY,'freeze_sha256':self.recovery_hash,'coordinator_call_id':'fc-recovery2'}
        self.recovery_receipt_path=self.root/'recovery2-receipt.json';s.c.atomic(self.recovery_receipt_path,self.recovery_receipt)
        self.aggregate['recovery2_provenance']=s.r.aggregate_provenance(self.recovery,self.recovery_hash,'fc-recovery2')
        self.aggregate['budget_ledger']=self.recovery['budget_ledger']
        self.aggregate_path=self.root/'aggregate.json';s.c.atomic(self.aggregate_path,self.aggregate)
        self.analysis=self.root/'development-analysis.json';s.e.analyze(self.development,self.aggregate_path,self.analysis)
        self.confirmation=self.root/'confirmation.json';s.e.prepare(self.master,'confirmation',self.confirmation,self.analysis)
        self.ops_path=self.root/'confirmation-ops.json'
        s.write_freeze(self.ops_path,master=self.master,stage=self.confirmation,parent_stage=self.development,
                       parent_status=self.aggregate_path,parent_analysis=self.analysis,
                       recovery_freeze=self.recovery_path,recovery_receipt=self.recovery_receipt_path,now=NOW)
        self.ops=s.c.read(self.ops_path)
        self.recovery_result={'status':'complete','coordinator_call_id':'fc-recovery2','freeze_sha256':self.recovery_hash,
                 'jobs_complete':50,'aggregate_sha256':s.c.state_hash(self.aggregate),
                 'rows':{n:self.aggregate['rows'][n] for n in self.run_ids},'calls':{n:self.aggregate['calls'][n] for n in self.run_ids}}
        self.control=Control({'campaign':{'freeze_sha256':s.r.ORIGINAL_FREEZE},
                 s.r.KEY+':reservation':{'freeze_sha256':self.recovery_hash},s.r.KEY+':state':self.recovery_result,
                 s.r.KEY+':owner':'fc-recovery2',s.r.KEY+':receipt':self.recovery_receipt,
                 s.first.KEY+':state':{'status':'failed','coordinator_call_id':s.r.PARENT_CALL},
                 s.first.KEY+':owner':s.r.PARENT_CALL,s.first.KEY+':reservation':{'freeze_sha256':s.r.PARENT_FREEZE},
                 'coordinator:development':{'status':'failed','coordinator_call_id':s.r.ORIGINAL_CALL,'error_type':'KeyboardInterrupt'},
                 'coordinator:development:owner':s.r.ORIGINAL_CALL,'stage:development':{'jobs':130},
                 'stage:smoke':{'jobs':65},'coordinator:smoke':{'status':'complete','jobs_complete':65}})

    def get_call(self,identifier):
        value=self.recovery_result if identifier=='fc-recovery2' else self.confirmation_result
        return SimpleNamespace(get=lambda timeout:copy.deepcopy(value))

    def final_fixture(self):
        stage=s.c.read(self.confirmation)
        self.confirmation_result=self.complete(stage,s.c.digest(self.confirmation),'fc-confirmation','confirmation-ops2')
        self.confirmation_result.update(ops_freeze_sha256=s.c.digest(self.ops_path),attempt='confirmation-ops2',
                                        budget_ledger=self.ops['budget_ledger'])
        status=self.root/'confirmation-status.json';s.c.atomic(status,self.confirmation_result)
        analysis=self.root/'confirmation-analysis.json';s.e.analyze(self.confirmation,status,analysis)
        stage_path=self.root/'final.json';s.e.prepare(self.master,'final',stage_path,analysis)
        receipt={'schema':'learning-hybrid-receipt-v1','status':'submitted','stage':'confirmation',
                 'freeze_sha256':s.r.ORIGINAL_FREEZE,'stage_sha256':s.c.digest(self.confirmation),
                 'ops_freeze_sha256':s.c.digest(self.ops_path),'coordinator_call_id':'fc-confirmation'}
        receipt_path=self.root/'confirmation-receipt.json';s.c.atomic(receipt_path,receipt)
        path=self.root/'final-ops.json'
        s.write_freeze(path,master=self.master,stage=stage_path,parent_stage=self.confirmation,parent_status=status,
                       parent_analysis=analysis,previous_ops_freeze=self.ops_path,previous_receipt=receipt_path,now=NOW)
        self.control['stage:confirmation']={'jobs':len(stage['jobs']),'ops_freeze_sha256':s.c.digest(self.ops_path)}
        self.control['coordinator:confirmation']={'status':'complete','jobs_complete':len(stage['jobs']),
                'coordinator_call_id':'fc-confirmation','stage_sha256':s.c.digest(self.confirmation)}
        self.control['coordinator-receipt:confirmation']=receipt
        return path,s.c.read(path)

    def test_complete_chain_reconstructs_original_science_and_counts_failed_attempts(self):
        self.assertEqual(s.validate(self.ops,now=NOW)['plan']['stage'],s.c.read(self.confirmation))
        count=s.verify_parents(self.control,self.ops,self.get_call)
        self.assertEqual(count,65+130+2)
        path,final=self.final_fixture();s.validate(final,now=NOW)
        s.reserve(self.control,final,s.c.digest(path),now=NOW,get_call=self.get_call)
        self.assertEqual(final['budget_ledger'],self.ops['budget_ledger'])
        self.assertEqual(self.control[s.first.KEY+':state']['status'],'failed')

    def test_incomplete_or_changed_retained_rows_cannot_open_confirmation(self):
        bad=copy.deepcopy(self.ops);state=bad['evidence']['parent_status']['value'];state['rows'].pop(next(iter(state['rows'])))
        bad['evidence']['parent_status']=self.item(state)
        with self.assertRaisesRegex(ValueError,'incomplete'):s.validate(bad,now=NOW)
        bad=copy.deepcopy(self.ops);state=bad['evidence']['parent_status']['value'];first=next(iter(state['rows']))
        state['rows'][first]['reward']=.99;bad['evidence']['parent_status']=self.item(state)
        with self.assertRaisesRegex(ValueError,'retained original'):s.validate(bad,now=NOW)

    def test_wrong_attempt_storage_raw_hash_and_lineage_are_rejected(self):
        for mutation in ('attempt','raw_hash','lineage'):
            bad=copy.deepcopy(self.ops);state=bad['evidence']['parent_status']['value']
            row=state['rows'][self.run_ids[0]]
            if mutation=='attempt':row['storage']['attempt']='final-ops2'
            elif mutation=='raw_hash':row['storage']['raw_row_sha256']='f'*64
            else:state['recovery2_provenance']['retained_state_sha256']='e'*64
            bad['evidence']['parent_status']=self.item(state)
            with self.assertRaises(ValueError):s.validate(bad,now=NOW)

    def test_terminal_recovery_and_confirmation_results_bound_to_original_calls(self):
        bad=copy.deepcopy(self.recovery_result);bad['aggregate_sha256']='wrong'
        with self.assertRaisesRegex(ValueError,'terminal result differs'):
            s.reserve(self.control,self.ops,'ops',NOW,get_call=lambda _:SimpleNamespace(get=lambda timeout:bad))
        path,final=self.final_fixture()
        self.confirmation_result['rows'][next(iter(self.confirmation_result['rows']))]['reward']=.99
        with self.assertRaisesRegex(ValueError,'original terminal call'):
            s.reserve(self.control,final,s.c.digest(path),NOW,get_call=self.get_call)

    def test_selection_map_source_and_budget_changes_are_rejected(self):
        for key in ('parent_analysis','stage'):
            bad=copy.deepcopy(self.ops)
            if key=='parent_analysis':bad['evidence'][key]['value']['selected_groups']=[]
            else:bad['evidence'][key]['value']['jobs'][0]['seed']=500
            bad['evidence'][key]=self.item(bad['evidence'][key]['value'])
            with self.assertRaises(ValueError):s.validate(bad,now=NOW)
        bad=copy.deepcopy(self.ops);bad['budget_ledger']['future_rate_per_second']/=3
        with self.assertRaisesRegex(ValueError,'allocation ledger'):s.validate(bad,now=NOW)
        bad=copy.deepcopy(self.ops);bad['ops_source_sha256'][s.OPS_FILES[0]]='changed'
        with self.assertRaisesRegex(ValueError,'ops identity'):s.validate(bad,now=NOW)
        with self.assertRaisesRegex(ValueError,'does not redirect imports'):s.source_context(self.root)

    def test_duplicate_stop_deadline_and_preserved_parent_failure(self):
        self.control['stop']=True
        with self.assertRaisesRegex(ValueError,'stop marker'):s.reserve(self.control,self.ops,'ops',NOW,self.get_call)
        self.control.pop('stop')
        with self.assertRaisesRegex(ValueError,'deadline'):s.reserve(self.control,self.ops,'ops',s.r.DEADLINE,self.get_call)
        self.control[s.first.KEY+':state']['status']='complete'
        with self.assertRaisesRegex(ValueError,'failure must remain'):s.reserve(self.control,self.ops,'ops',NOW,self.get_call)
        self.control[s.first.KEY+':state']['status']='failed'
        s.reserve(self.control,self.ops,'ops',NOW,self.get_call)
        with self.assertRaisesRegex(ValueError,'already reserved'):s.reserve(self.control,self.ops,'ops',NOW,self.get_call)

    def test_launcher_all_workers_nonpreemptible_receipts_and_three_file_ops_closure(self):
        captured={'functions':[],'spawns':[]};receipt_path=self.root/'receipt.json';test=self
        original_copy=s.m.copy_sources
        self.patch(s.m,'copy_sources',lambda plan,destination,root:original_copy(plan,destination,FROZEN))
        class Image:
            def pip_install(self,*a,**kw):return self
            def env(self,*a,**kw):return self
            def add_local_dir(self,path,**kw):
                captured['files']={str(p.relative_to(path)) for p in Path(path).rglob('*') if p.is_file()};return self
        class App:
            app_id='ap-synthetic'
            def __init__(self,name):pass
            def function(self,**options):
                captured['functions'].append(options)
                def decorate(fn):
                    def spawn(*args):
                        test.assertTrue(s.c.read(receipt_path)['spawn_intent']);captured['spawns'].append(args)
                        return SimpleNamespace(object_id='fc-confirmation')
                    return SimpleNamespace(spawn=spawn)
                return decorate
            def run(self,**kw):return nullcontext()
        sdk=SimpleNamespace(Image=SimpleNamespace(debian_slim=lambda **kw:Image()),App=App,enable_output=nullcontext,
                Dict=SimpleNamespace(from_name=lambda _:self.control),Volume=SimpleNamespace(from_name=lambda _:object()),
                FunctionCall=SimpleNamespace(from_id=self.get_call))
        receipt=s.launch(self.ops_path,receipt_path,sdk=sdk,now=NOW)
        self.assertEqual(receipt['schema'],'learning-hybrid-receipt-v1');self.assertEqual(receipt['status'],'submitted')
        self.assertEqual(len(captured['spawns']),1)
        self.assertEqual([v['max_containers'] for v in captured['functions']],[64,1])
        for options in captured['functions']:
            self.assertTrue(options['nonpreemptible']);self.assertEqual(options['retries'],0)
            self.assertEqual(options['cpu'],(1,1));self.assertEqual(options['memory'],(2048,2048))
        self.assertEqual(captured['files'],set(self.master_value['source_sha256'])|{s.c.POLICY_FILE}|set(s.OPS_FILES))

    def test_coordinator_preserves_original_science_and_saves_threefold_ledger(self):
        hashed=s.c.digest(self.ops_path);s.reserve(self.control,self.ops,hashed,NOW,self.get_call)
        stage=s.c.read(self.confirmation)
        state=self.complete(stage,s.c.digest(self.confirmation),'fc-confirmation','confirmation-ops2')
        volume=SimpleNamespace(reload=lambda:None,commit=lambda:None);worker=object()
        with patch.object(s.c,'coordinate',return_value=state) as coordinate:
            actual=s.run_stage(self.ops['plan'],self.ops,hashed,worker,volume,self.control,
                               root=self.root/'remote',get_call=self.get_call)
        coordinate.assert_called_once_with(self.ops['plan'],worker,volume,self.control)
        self.assertAlmostEqual(actual['coordinator_compute_estimate_usd'],5*3*s.c.RATE)
        self.assertEqual(actual['budget_ledger'],self.ops['budget_ledger'])
        self.assertEqual(s.c.read(self.root/'remote/confirmation/state.json'),actual)
        self.assertEqual(self.control['coordinator:confirmation']['ops_freeze_sha256'],hashed)

    def test_attempt_worker_bridge_and_full_download_keep_raw_and_mapped_rows(self):
        stage=s.c.read(self.confirmation);job={**stage['jobs'][0],'source_sha256':stage['source_sha256']}
        raw=self.complete(stage,s.c.digest(self.confirmation),'fc-unused')['rows'][job['id']]
        raw['call_id']='fc-bridge'
        remote=self.root/'remote';volume=SimpleNamespace(reload=lambda:None,commit=lambda:None)
        data=b'synthetic case bytes';raw['sha256']=hashlib.sha256(data).hexdigest()
        def original_worker(plan,received,volume,control,**kwargs):
            self.assertEqual(received,job)
            base=Path(kwargs['root']);path=base/raw['artifact'];path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(data);s.c.atomic(path.parent/'row.json',raw)
            return copy.deepcopy(raw)
        with patch.object(s.c,'run_worker',side_effect=original_worker):
            mapped=s.r.run_attempt_worker(self.ops['plan'],job,volume,self.control,attempt='confirmation-ops2',
                                          root=remote,call_id='fc-bridge')
        s.r.verify_rows({job['id']:mapped},self.ops['plan'],{job['id']:'fc-bridge'},allowed_attempts={'confirmation-ops2'})
        self.assertEqual(mapped['allocation_rate_multiplier'],3)
        self.assertEqual(mapped['running_compute_estimate_usd'],3*raw['running_compute_estimate_usd'])
        state={'status':'failed','rows':{job['id']:mapped},'calls':{job['id']:'fc-bridge'},
               'ops_freeze_sha256':s.c.digest(self.ops_path)}
        receipt={'stage':'confirmation','ops_freeze_sha256':s.c.digest(self.ops_path),'coordinator_call_id':'fc-stage'}
        receipt_path=self.root/'download-receipt.json';s.c.atomic(receipt_path,receipt)
        s.c.atomic(remote/'confirmation/ops-freeze.json',self.ops)
        s.c.atomic(remote/'confirmation/receipts'/f'{job["id"]}.json',{'call_id':'fc-bridge'})
        output=self.root/'download'
        def original_download(receipt,output,*,artifacts,sdk):
            self.assertFalse(artifacts);Path(output).mkdir()
            s.c.atomic(Path(output)/'confirmation/plan.json',self.ops['plan'])
            s.c.atomic(Path(output)/'confirmation/state.json',state)
            return state
        sdk=SimpleNamespace(Volume=SimpleNamespace(from_name=lambda _:SimpleNamespace(read_file=lambda path:[(remote/path).read_bytes()])),
                            FunctionCall=SimpleNamespace(from_id=lambda _:SimpleNamespace(get=lambda timeout:state)))
        with patch.object(s.m,'download',side_effect=original_download):
            s.download(receipt_path,output,artifacts=True,sdk=sdk)
        self.assertEqual((output/mapped['artifact']).read_bytes(),data)
        self.assertEqual(s.c.digest(output/mapped['storage']['raw_row']),mapped['storage']['raw_row_sha256'])
        self.assertEqual(s.c.read(output/'confirmation/mapped-rows'/f'{job["id"]}.json'),mapped)
        self.assertIn(mapped['storage']['raw_row'],s.c.read(output/'download.json')['files'])


if __name__=='__main__':unittest.main()
