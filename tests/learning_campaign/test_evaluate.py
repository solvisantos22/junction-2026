"""Evaluator tests use synthetic training metadata and already-used maps 1/2."""

from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import torch

from lightlag_learning.environment import CANDIDATE_FEATURES, GLOBAL_FEATURES
from lightlag_learning.learners import Learner
from lightlag_learning.train import VALIDATION_MAPS, atomic_json, digest, read_json, source_pins
from tools.learning_campaign import evaluate as e


def fixture(root, algorithm='ppo', seed=17, counts=(0, 32), smoke=True):
    """A format fixture, deliberately not evidence that training was run."""
    directory = root/f'{algorithm}-{seed}'
    directory.mkdir()
    base = Learner(algorithm, len(CANDIDATE_FEATURES), len(GLOBAL_FEATURES), seed).inference_state()
    report = {'schema':'learning-training-report-v1', 'algorithm':algorithm, 'seed':seed,
              'source_sha256':source_pins(), 'smoke':smoke, 'status':'complete',
              'episodes_completed':max(counts), 'validations':{}}
    for count in counts:
        state = deepcopy(base)
        state['episodes_seen'] = count
        policy_path = directory/f'policy-{count:05d}.json'
        atomic_json(policy_path, state)
        maps = list((1, 2) if smoke else VALIDATION_MAPS)
        # A later checkpoint deliberately has a lower validation score.
        summary = {'count':len(maps), 'mean_reward':.9 if count == 2048 else .1}
        report['validations'][str(count)] = summary
        atomic_json(directory/f'validation-{count:05d}.json.gz', {
            'schema':'learning-validation-v1', 'episodes_completed':count,
            'policy_sha256':digest(policy_path), 'maps':maps, 'summary':summary,
            'episodes':[{'seed':seed} for seed in maps]})
    atomic_json(directory/'report.json', report)
    return directory


class FreezeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): torch.set_num_threads(1)

    def test_all_initializations_and_matched_budget_freeze_without_opening_maps(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            runs=[fixture(root, a, s, (0,2048,8192), False)
                  for a in ('ppo','replay') for s in e.INITIALIZATIONS]
            with patch.object(e,'TraverseEnvironment',side_effect=AssertionError('maps must stay unopened')):
                manifest=e.freeze(root/'freeze.json',runs)
            self.assertEqual(len(manifest['arms']),20)
            self.assertEqual(manifest['maps'],list(e.FINAL_MAPS))
            for record in manifest['runs']: self.assertEqual(record['last_milestone'],8192)
            e.verify_manifest(manifest)
            with self.assertRaises(FileExistsError):e.freeze(root/'freeze.json',runs)
            changed=deepcopy(manifest)
            changed['arms'][0]['policy']['epsilon']=.123
            with self.assertRaises(ValueError):e.verify_manifest(changed)

    def test_missing_initialization_and_validation_hash_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            run=fixture(root,counts=(0,2048),smoke=False)
            with self.assertRaisesRegex(ValueError,'six'):e.freeze(root/'freeze.json',[run])
            validation=read_json(run/'validation-02048.json.gz')
            validation['policy_sha256']='0'*64
            atomic_json(run/'validation-02048.json.gz',validation)
            with self.assertRaisesRegex(ValueError,'provenance'):e.freeze(root/'bad.json',[run])

    def test_no_completed_milestone_keeps_initial_as_explicit_last(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);run=fixture(root,counts=(0,))
            report=read_json(run/'report.json');report['status']='deadline'
            atomic_json(run/'report.json',report)
            manifest=e.freeze(root/'freeze.json',[run],smoke=True)
            self.assertTrue(manifest['runs'][0]['no_completed_training_milestone'])
            self.assertEqual(manifest['arms'][0]['roles'],['initial','last'])
            self.assertEqual(len(manifest['arms']),3)

    def test_summary_bootstraps_maps_after_averaging_training_initializations(self):
        arms=[]
        for seed in e.INITIALIZATIONS:
            arms.extend([
                {'id':f'initial-{seed}','kind':'policy','algorithm':'ppo','training_seed':seed,'episodes':0,'roles':['initial']},
                {'id':f'last-{seed}','kind':'policy','algorithm':'ppo','training_seed':seed,'episodes':2048,'roles':['last','matched2048']}])
        arms.extend({'id':name,'kind':name} for name in ('greedy','beam'))
        manifest={'arms':arms,'maps':[1,2]}
        rows=[]
        for arm in arms:
            for seed in (1,2):
                reward=.1 if arm['id'].startswith('initial') else (.2 if seed==1 else .4)
                rows.append({'arm':arm['id'],'seed':seed,'reward':reward,'home':True,'alive':True,'invalid_calls':0})
        summary=e.summarize(rows,manifest)
        primary=summary['learning']['ppo']['last']
        self.assertEqual(primary['conditional_on_training_seeds'],[17,29,43])
        self.assertAlmostEqual(primary['across_seed_map_average']['mean_paired_gain'],.2)
        self.assertEqual(len(primary['across_seed_map_average']['map_differences']),2)
        lower,upper=primary['across_seed_map_average']['bootstrap_95_percentile']
        self.assertAlmostEqual(lower,.1)
        self.assertAlmostEqual(upper,.3)
        with self.assertRaises(ValueError):e.summarize(rows+rows[:1],manifest)


class UsedMapEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)
        cls.temporary=tempfile.TemporaryDirectory()
        cls.root=Path(cls.temporary.name)
        run=fixture(cls.root)
        cls.freeze=cls.root/'freeze.json'
        cls.manifest=e.freeze(cls.freeze,[run],smoke=True)
        cls.output=cls.root/'evaluation'
        cls.report=e.run(cls.freeze,cls.output,workers=1)

    @classmethod
    def tearDownClass(cls):cls.temporary.cleanup()

    def test_complete_smoke_report_replays_and_choices_audit(self):
        self.assertTrue(self.report['complete'])
        self.assertEqual(len(self.report['cases']),8)
        audited=e.audit(self.output/'report.json')
        self.assertEqual(audited['cases_verified'],8)
        self.assertTrue(audited['smoke'])
        with self.assertRaises(FileExistsError):e.run(self.freeze,self.output,workers=1)

    def test_choice_grade_and_physics_tampering_are_rejected(self):
        row=next(r for r in self.report['cases'] if r['arm']=='greedy' and r['seed']==1)
        original=read_json(self.output/row['artifact'])
        arm=next(a for a in self.manifest['arms'] if a['id']=='greedy')
        changed=deepcopy(original)
        changed['episode']['transitions'][0]['action']=-1
        with self.assertRaises(AssertionError):e.audit_case(changed,arm)
        changed=deepcopy(original);changed['episode']['reward']+=.1
        with self.assertRaises(AssertionError):e.audit_case(changed,arm)
        changed=deepcopy(original)
        command=next(c['command'] for c in changed['episode']['replay']['commands'] if c['command']['action']=='drive')
        command['heading_deg']=(command['heading_deg']+180)%360
        with self.assertRaises(AssertionError):e.audit_case(changed,arm)

    def test_report_summary_and_case_hash_tampering_are_rejected(self):
        path=self.output/'report.json'
        original=path.read_bytes()
        try:
            changed=deepcopy(self.report)
            changed['summary']['arms']['greedy']['mean_reward']+=.1
            atomic_json(path,changed)
            with self.assertRaises(AssertionError):e.audit(path)
            changed=deepcopy(self.report);changed['cases'][0]['sha256']='0'*64
            atomic_json(path,changed)
            with self.assertRaises(AssertionError):e.audit(path)
        finally:path.write_bytes(original)


if __name__=='__main__':unittest.main()
