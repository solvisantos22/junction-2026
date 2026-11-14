"""Campaign tests open only already-used worlds 1/2; other metadata is synthetic."""

from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from lightlag_learning.environment import run_episode, greedy_choice
from lightlag_learning.learners import Learner
from tools.learning_final import campaign as c


def policies(root, full=False):
    e = c.e
    records, arms = [], []
    identities = [(a, s) for a in ('ppo', 'replay') for s in e.INITIALIZATIONS] if full else [('ppo', 17)]
    for algorithm, seed in identities:
        last = 2048 if (algorithm, seed) == ('replay', 43) else (8192 if full else 32)
        initial = Learner(algorithm, 20, 14, seed).inference_state()
        records.append({'algorithm': algorithm, 'seed': seed, 'experiment': e.EXPERIMENT,
                        'episodes_target': 8192 if full else 32, 'episodes_completed': last,
                        'last_milestone': last})
        for count in sorted({0, last} | ({2048} if full else set())):
            policy = deepcopy(initial)
            policy['episodes_seen'] = count
            roles = (['initial'] if count == 0 else []) + (['last'] if count == last else [])
            if count == 2048:
                roles.append('matched2048')
            arms.append({'id': f'{algorithm}-{seed}-{count:05d}', 'kind': 'policy', 'algorithm': algorithm,
                         'training_seed': seed, 'episodes': count, 'roles': roles, 'policy': policy,
                         'policy_sha256': e.state_hash(policy)})
    arms.extend({'id': name, 'kind': name, 'roles': ['reference']} for name in ('greedy', 'beam'))
    manifest = {'schema': 'learning-final-freeze-v1', 'experiment': e.EXPERIMENT, 'smoke': not full,
                'maps': list(e.FINAL_MAPS) if full else [1, 2], 'arms': arms, 'runs': records,
                'source_sha256': e.evaluation_sources(), 'explore': False,
                'bootstrap_draws': e.BOOTSTRAP_DRAWS, 'bootstrap_seed': e.BOOTSTRAP_SEED,
                'numpy': e.np.__version__, 'torch': e.torch.__version__, 'python': e.platform.python_version()}
    path = root/'policy-freeze.json'
    e.atomic_json(path, manifest)
    return path


class FreezeTests(unittest.TestCase):
    def test_freeze_keeps_every_arm_and_opens_no_submission_world(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            parent = policies(root, full=True)
            with patch.object(c, 'TraverseCampaign', side_effect=AssertionError('worlds stay unopened')):
                manifest = c.freeze(root/'campaign-freeze.json', parent)
            self.assertEqual(manifest['seeds'], [2027, 2028, 2029])
            self.assertEqual(len(manifest['policy_freeze']['arms']), 19)
            self.assertEqual(manifest['policy_freeze'], c.e.read_json(parent))
            self.assertEqual(manifest['policy_freeze_sha256'], c.e.digest(parent))
            self.assertIn('tools/learning_final/campaign.py', manifest['source_sha256'])
            self.assertIn('harbor/lightlag-traverse-campaign/manifest.json', manifest['source_sha256'])
            altered = deepcopy(manifest)
            altered['policy_freeze']['arms'].pop()
            with self.assertRaises(ValueError):
                c.verify_manifest(altered)
            altered = deepcopy(manifest)
            altered['policy_freeze_sha256'] = '0'*64
            with self.assertRaisesRegex(ValueError, 'freeze/source/settings'):
                c.verify_manifest(altered)
            with self.assertRaises(FileExistsError):
                c.freeze(root/'campaign-freeze.json', parent)

    def test_smoke_policy_cannot_be_used_for_submission(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(ValueError, 'production policy freeze'):
                c.freeze(root/'rejected.json', policies(root))


class UsedWorldCampaignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        c.e.torch.set_num_threads(1)
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        cls.freeze_path = cls.root/'campaign-freeze.json'
        cls.manifest = c.freeze(cls.freeze_path, policies(cls.root), smoke=True)
        cls.output = cls.root/'campaign'
        cls.report = c.run(cls.freeze_path, cls.output, workers=1)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def bundle(self, name):
        row = next(row for row in self.report['cases'] if row['arm'] == name)
        return c.e.read_json(self.output/row['artifact'])

    def test_real_campaign_reaches_every_mission_and_audits(self):
        self.assertEqual(len(self.report['cases']), 4)
        self.assertTrue(self.report['complete'])
        result = c.audit(self.output/'report.json')
        self.assertEqual((result['campaigns_verified'], result['missions_verified']), (4, 8))
        self.assertTrue(result['smoke'])
        for row in self.report['cases']:
            bundle = self.bundle(row['arm'])
            self.assertEqual([b['campaign_complete'] for b in bundle['mission_endings']], [False, True])
            self.assertEqual(bundle['result']['tick'], 840)
            raw = sum(m['episode']['result']['raw_score'] for m in bundle['missions'])
            maximum = sum(m['episode']['result']['max_available_value'] for m in bundle['missions'])
            self.assertEqual(bundle['reward'], raw/maximum)
        with self.assertRaises(FileExistsError):
            c.run(self.freeze_path, self.output, workers=1)

    def test_public_features_and_controller_reset_match_single_missions(self):
        bundle = self.bundle('greedy')
        for mission in bundle['missions']:
            standalone = run_episode(mission['seed'], greedy_choice, keep_replay=True)
            for key in ('transitions', 'result', 'replay', 'decision_count'):
                self.assertEqual(mission['episode'][key], standalone[key])

    def test_mission_order_aggregate_and_physics_tampering_rejected(self):
        arm = next(a for a in self.manifest['policy_freeze']['arms'] if a['id'] == 'greedy')
        original = self.bundle('greedy')
        changed = deepcopy(original)
        changed['missions'].reverse()
        with self.assertRaisesRegex(ValueError, 'order'):
            c.audit_case(changed, arm, self.manifest)
        changed = deepcopy(original)
        changed['reward'] += .01
        with self.assertRaisesRegex(ValueError, 'aggregate'):
            c.audit_case(changed, arm, self.manifest)
        changed = deepcopy(original)
        changed['mission_endings'][0]['campaign_complete'] = True
        with self.assertRaisesRegex(ValueError, 'boundary'):
            c.audit_case(changed, arm, self.manifest)
        changed = deepcopy(original)
        changed['missions'][0]['episode']['transitions'][0]['action'] = -1
        with self.assertRaises(AssertionError):
            c.audit_case(changed, arm, self.manifest)

    def test_report_summary_and_hash_tampering_rejected(self):
        path = self.output/'report.json'
        original = path.read_bytes()
        try:
            changed = deepcopy(self.report)
            changed['cases'][0]['sha256'] = '0'*64
            c.e.atomic_json(path, changed)
            with self.assertRaisesRegex(ValueError, 'artifact/hash'):
                c.audit(path)
        finally:
            path.write_bytes(original)


if __name__ == '__main__':
    unittest.main()
