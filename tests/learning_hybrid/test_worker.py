"""Worker checks use synthetic metadata and already-used worlds 1/2 only."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import torch

from lightlag_hybrid import worker as w


def spec(kind='greedy'):
    return {'schema': 'learning-hybrid-spec-v1', 'id': kind, 'kind': kind,
            'family': 'control', 'group': kind, 'pool': None, 'members': [],
            'rho': 0.0, 'greedy_weight': 0.0, 'training_seed': None}


def job(kind='greedy', seed=1):
    return {'id': f'smoke-{kind}-{seed}', 'stage': 'smoke', 'seed': seed,
            'spec': spec(kind), 'source_sha256': {'synthetic': '0'*64}}


class IdentityTests(unittest.TestCase):
    def test_source_manifest_binds_original_and_new_closure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for package in (*w.PACKAGES, 'tools/learning_hybrid'):
                path = root/package/'__init__.py'
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('# synthetic source fixture\n')
            for name in w.REQUIRED:
                path = root/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('# synthetic frozen source fixture\n')
            pins = w.source_manifest(root)
            self.assertIn('lightlag_hybrid/__init__.py', pins)
            self.assertIn('tools/learning_final/evaluate.py', pins)
            self.assertIn('docs/learning-hybrid.md', pins)
            w.assert_source(pins, root)
            (root/'lightlag_learning/__init__.py').write_text('# changed\n')
            with self.assertRaisesRegex(ValueError, 'source manifest'):
                w.assert_source(pins, root)
            (root/'docs/learning-hybrid.md').unlink()
            with self.assertRaises(FileNotFoundError):
                w.source_manifest(root)

    def test_bad_identity_and_source_never_open_worlds(self):
        with patch.object(w, 'TraverseEnvironment', side_effect=AssertionError('no worlds')):
            for key, value in (('id', '../escape'), ('seed', True), ('seed', 2027),
                               ('stage', 'unknown')):
                changed = job()
                changed[key] = value
                with self.assertRaises(ValueError):
                    w._identity(changed, {})
            with patch.object(w, 'source_manifest', return_value={'other': '1'*64}):
                with self.assertRaisesRegex(ValueError, 'source manifest'):
                    w._identity(job(), {})

    def test_failed_rollout_is_retained_without_reward_or_automatic_retry(self):
        def fail(seed, choose, keep_replay):
            choose.diagnostics.append({'partial': True})
            raise RuntimeError('deliberate controller failure')
        with patch.object(w, 'assert_source'), patch.object(w, 'run_episode', side_effect=fail) as run:
            bundle = w.run_job(job(), {})
        self.assertEqual(run.call_count, 1)
        self.assertEqual(bundle['status'], 'failed')
        self.assertIsNone(bundle['episode'])
        self.assertEqual(bundle['diagnostics'], [{'partial': True}])
        row = w.row_for(bundle)
        self.assertIsNone(row['reward'])
        self.assertIsNone(row['home'])
        self.assertEqual(row['error']['type'], 'RuntimeError')
        with self.assertRaisesRegex(ValueError, 'failed or incomplete'):
            w.audit_job(bundle, {})


class UsedWorldWorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)
        # Other agents are still building source files. Source completeness is
        # independently tested above; no production source freeze is fabricated.
        cls.pin_patch = patch.object(w, 'assert_source')
        cls.pin_patch.start()
        cls.greedy = w.run_job(job(), {})
        cls.beam = w.run_job(job('beam', 2), {})

    @classmethod
    def tearDownClass(cls):
        cls.pin_patch.stop()

    def test_physics_choices_and_full_controller_replay(self):
        for bundle in (self.greedy, self.beam):
            self.assertEqual(bundle['status'], 'complete', bundle.get('error'))
            audit = w.audit_job(bundle, {}, full_rerun=True)
            self.assertTrue(audit['physics_verified'])
            self.assertTrue(audit['full_controller_replay'])
            self.assertEqual(audit['case_sha256'], w.state_hash(bundle))
            self.assertEqual(audit['hybrid_choices_verified'], bundle is self.greedy)
            row = w.row_for(bundle, audit)
            self.assertEqual(row['audit'], audit)
            self.assertEqual(row['reward'], bundle['episode']['reward'])

    def test_reward_choice_duration_and_diagnostic_tampering_rejected(self):
        for mutate in (
            lambda b: b['episode'].__setitem__('reward', b['episode']['reward']+.01),
            lambda b: b['episode']['transitions'][0].__setitem__('action', -1),
            lambda b: b['episode']['transitions'][0].__setitem__('elapsed_ticks', 0),
            lambda b: b['diagnostics'][0].__setitem__('action', -1),
            lambda b: b.__setitem__('policy_sha256', {'extra': '0'*64}),
        ):
            altered = deepcopy(self.greedy)
            mutate(altered)
            with self.assertRaises(ValueError):
                w.audit_job(altered, {})

    def test_full_replay_catches_observation_that_does_not_change_saved_action(self):
        altered = deepcopy(self.greedy)
        # Greedy does not consume this global feature. A choices-only audit
        # cannot establish that it came from the public navigator; a rerun can.
        altered['episode']['transitions'][0]['obs']['global'][13] += .01
        w.audit_job(altered, {})
        with self.assertRaisesRegex(ValueError, 'observation/command linkage'):
            w.audit_job(altered, {}, full_rerun=True)

    def test_six_network_hybrid_and_final_stage_force_full_replay(self):
        from lightlag_hybrid.policy import build_specs

        parent = json.loads((w.ROOT/'docs/learning-final-results/policy-freeze.json').read_text())
        policies = {a['id']: a['policy'] for a in parent['arms']
                    if a['kind'] == 'policy' and 'last' in a['roles']}
        selected = next(s for s in build_specs(parent) if s['id'] == 'ensemble-all-rho075')
        request = job()
        request['spec'] = selected
        request['id'] = 'smoke-ensemble-all-rho075-1'
        bundle = w.run_job(request, policies)
        self.assertEqual(bundle['status'], 'complete', bundle.get('error'))
        self.assertEqual(len(bundle['policy_sha256']), 6)
        self.assertEqual(len(bundle['diagnostics']), bundle['episode']['decision_count'])
        # Exercise the mandatory final audit branch on old world 1 only.
        bundle['job']['stage'] = 'final'
        with patch.dict(w.STAGE_MAPS, {'final': (1,)}):
            audit = w.audit_job(bundle, policies, full_rerun=False)
        self.assertTrue(audit['full_controller_replay'])
        self.assertTrue(audit['hybrid_choices_verified'])


if __name__ == '__main__':
    unittest.main()
