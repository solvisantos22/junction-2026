from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from tools.learning_final import summarize as s


def fixture():
    arms, runs, rows = [], [], []
    for algorithm in ('ppo', 'replay'):
        for seed in (17, 29, 43):
            last = 2048 if (algorithm,seed)==('replay',43) else 8192
            runs.append({'algorithm':algorithm,'seed':seed,'status':'deadline' if last==2048 else 'complete',
                         'episodes_completed':6880 if last==2048 else 8192,'episodes_target':8192})
            for count in sorted({0,2048,last}):
                roles=(['initial'] if count==0 else [])+(['matched2048'] if count==2048 else [])+(['last'] if count==last else [])
                arms.append({'id':f'{algorithm}-{seed}-{count}','kind':'policy','algorithm':algorithm,
                             'training_seed':seed,'episodes':count,'roles':roles})
    arms.extend({'id':name,'kind':name,'roles':['reference']} for name in ('greedy','beam'))
    for arm in arms:
        for world in (1,2):
            reward=.5 if arm['kind']=='beam' else .3 if arm['kind']=='greedy' else (
                .1 if arm['episodes']==0 else .2 if arm['episodes']==2048 else .25)
            rows.append({'arm':arm['id'],'seed':world,'reward':reward+(world-1)*.02,
                         'home':True,'alive':True,'invalid_calls':0})
    return rows,{'arms':arms,'runs':runs,'maps':[1,2]}


class MethodSummaryTests(unittest.TestCase):
    def test_average_within_map_before_bootstrap_and_keep_shared_role_once(self):
        rows,manifest=fixture();result=s.method_statistics(rows,manifest)
        replay=result['methods']['replay'];latest=replay['checkpoints']['last']
        self.assertTrue(latest['policy_budgets_differ'])
        self.assertEqual(latest['n'],6)
        self.assertEqual(latest['per_training_seed']['43']['policy_episodes'],2048)
        self.assertEqual(len(rows),38)
        expected=np.array([(.25+.25+.2)/3-.1]*2)
        contrast=replay['paired_map_contrasts']['last_minus_initial']
        np.testing.assert_allclose(contrast['map_differences'],expected)
        np.testing.assert_allclose(contrast['bootstrap_95_percentile'],[expected[0],expected[0]])
        self.assertAlmostEqual(replay['paired_reference_comparisons']['last']['beam']['mean_paired_gain'],(.25+.25+.2)/3-.5)

    def test_missing_seed_duplicate_arm_or_duplicate_case_is_rejected(self):
        rows,manifest=fixture()
        bad=deepcopy(manifest);bad['runs'].pop()
        with self.assertRaises(ValueError):s.method_statistics(rows,bad)
        bad=deepcopy(manifest);bad['arms'].append(deepcopy(bad['arms'][0]))
        with self.assertRaises(ValueError):s.method_statistics(rows,bad)
        with self.assertRaises(ValueError):s.method_statistics(rows+[rows[0]],manifest)

    def test_changed_report_cannot_borrow_an_old_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);rows,manifest=fixture()
            manifest['smoke']=False
            s.evidence.atomic_json(root/'freeze.json',manifest)
            report={'schema':'learning-final-report-v1','experiment':s.evidence.EXPERIMENT,
                    'status':'complete','complete':True,'smoke':False,'cases':rows,
                    'summary':s.evidence.summarize(rows,manifest),
                    'freeze_sha256':s.evidence.digest(root/'freeze.json')}
            s.evidence.atomic_json(root/'report.json',report)
            audit={'schema':'learning-final-audit-v1','experiment':s.evidence.EXPERIMENT,
                   'smoke':False,'report_sha256':'0'*64,'cases_verified':len(rows),'summary':report['summary']}
            s.evidence.atomic_json(root/'audit.json',audit)
            with patch.object(s.evidence,'verify_manifest') as verified:
                with self.assertRaisesRegex(ValueError,'audit does not match'):
                    s.summarize(root/'report.json',root/'audit.json')
                verified.assert_called_once()


if __name__=='__main__':unittest.main()
