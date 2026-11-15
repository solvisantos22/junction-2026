"""Synthetic trainer lifecycle checks; no simulator worlds or paid work."""

import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from lightlag_hybrid_train import train as t


class FakeLearner:
    def __init__(self, algorithm, candidate_dim, global_dim, seed, total_episodes=4096):
        self.algorithm, self.seed, self.episodes_seen = algorithm, seed, 0
        self.schedule = total_episodes

    def state_dict(self):
        return {'algorithm': self.algorithm, 'seed': self.seed, 'episodes_seen': self.episodes_seen,
                'schedule': self.schedule, 'optimizer': {'synthetic': True}, 'rng': {'synthetic': True}}

    inference_state = state_dict

    def update(self, episodes):
        self.episodes_seen += len(episodes)
        return {'episodes_seen': self.episodes_seen}


def collect(pool, policy, maps, seed, offset=0, **kwargs):
    return [{'seed': world, 'action_seed': seed*1_000_000_000+offset+i, 'reward': .25,
             'decision_count': 1, 'result': {'at_base': True, 'alive': True}, 'invalid_calls': []}
            for i, world in enumerate(maps)]


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.stack.enter_context(patch.object(t, 'Learner', FakeLearner))
        self.stack.enter_context(patch.object(t, 'ProcessPoolExecutor', MagicMock()))
        self.stack.enter_context(patch.object(t, 'source_manifest', return_value={'synthetic': 'pin'}))
        self.mock_collect = self.stack.enter_context(patch.object(t, 'collect', side_effect=collect))
        self.clock = [1000.0]
        self.stack.enter_context(patch.object(t.time, 'time', side_effect=lambda: self.clock[0]))
        self.stack.enter_context(patch.object(t, 'ABSOLUTE_DEADLINE', 20000))

    def run_smoke(self, output, **kwargs):
        return t.train('prior', 17, 64, output, workers=1, smoke=True, **kwargs)

    def test_fixed_archives_policy_hashes_and_fresh_only_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)/'run'
            with patch.object(t, 'MILESTONES', (0, 32, 64)):
                result = self.run_smoke(output)
            self.assertEqual((result['status'], result['episodes_completed']), ('complete', 64))
            self.assertEqual(set(result['validations']), {'0', '32', '64'})
            self.assertEqual(result['deadline_unix'], 11800)
            self.assertEqual(result['experiment'], t.EXPERIMENT)
            self.assertEqual(len(result['history']), 2)
            for count in (0, 32, 64):
                pins = result['checkpoints'][str(count)]
                for prefix, suffix in (('policy', '.json'), ('checkpoint', '.json.gz'), ('validation', '.json.gz')):
                    path = output/f'{prefix}-{count:05d}{suffix}'
                    self.assertEqual(t.digest(path), pins[prefix+'_sha256'])
                saved = t.read_json(output/f'checkpoint-{count:05d}.json.gz')
                self.assertEqual(saved['learner']['episodes_seen'], count)
                self.assertIn('optimizer', saved['learner'])
                self.assertIn('rng', saved['learner'])
            with self.assertRaises(FileExistsError):
                self.run_smoke(output)

    def test_expired_deadline_retains_initial_weights_but_opens_no_rollouts(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)/'run'
            result = self.run_smoke(output, deadline_unix=999)
            self.assertEqual((result['status'], result['episodes_completed']), ('deadline', 0))
            self.assertEqual(result['validations'], {})
            self.assertEqual(set(result['checkpoints']), {'0'})
            self.mock_collect.assert_not_called()

    def test_completed_rollouts_after_deadline_are_retained_but_not_updated(self):
        def expire(*args, **kwargs):
            batch = collect(*args, **kwargs)
            if kwargs.get('explore'):
                self.clock[0] = 1101
            return batch
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)/'run'
            self.mock_collect.side_effect = expire
            result = self.run_smoke(output, deadline_unix=1100)
            self.assertEqual((result['status'], result['episodes_completed']), ('deadline', 0))
            self.assertEqual(result['history'], [])
            record = result['unapplied_batch']
            self.assertEqual(t.digest(output/record['artifact']), record['sha256'])
            self.assertEqual(len(t.read_json(output/record['artifact'])['episodes']), 32)

    def test_interrupted_collection_retains_partial_evidence(self):
        rows = [{'status': 'complete', 'episode': {'seed': 1}}, {'status': 'deadline', 'seed': 2}]
        self.mock_collect.side_effect = t.CollectionFailure(rows, 2)
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)/'run'
            result = self.run_smoke(output)
            self.assertEqual(result['status'], 'deadline')
            self.assertEqual(result['episodes_completed'], 0)
            self.assertEqual(t.read_json(output/'interrupted-rollouts.json.gz')['rows'], rows)

    def test_final_validation_finishing_after_cutoff_is_not_complete(self):
        def expire(pool, policy, maps, seed, **kwargs):
            batch = collect(pool, policy, maps, seed, **kwargs)
            if policy['episodes_seen'] == 64 and not kwargs.get('explore'):
                self.clock[0] = 1101
            return batch
        self.mock_collect.side_effect = expire
        with tempfile.TemporaryDirectory() as temporary:
            result = self.run_smoke(Path(temporary)/'run', deadline_unix=1100)
            self.assertEqual((result['status'], result['episodes_completed']), ('deadline', 64))
            self.assertIn('64', result['validations'])

    def test_optimizer_failure_does_not_advance_durable_checkpoint(self):
        def fail(learner, episodes):
            learner.episodes_seen += len(episodes)
            raise RuntimeError('interrupted optimizer')
        with tempfile.TemporaryDirectory() as temporary, patch.object(FakeLearner, 'update', fail):
            output = Path(temporary)/'run'
            with self.assertRaisesRegex(RuntimeError, 'interrupted optimizer'):
                self.run_smoke(output)
            report = t.read_json(output/'report.json')
            self.assertEqual((report['status'], report['episodes_completed']), ('failed', 0))
            self.assertEqual(report['history'], [])
            self.assertIn('pending_batch', report)
            self.assertEqual(t.read_json(output/'checkpoint-latest.json.gz')['episodes_completed'], 0)

    def test_failed_checkpoint_write_keeps_history_consistent(self):
        original = t.atomic_json
        def fail(path, value):
            if Path(path).name == 'checkpoint-latest.json.gz' and value['episodes_completed'] == 32:
                raise OSError('interrupted checkpoint')
            original(path, value)
        with tempfile.TemporaryDirectory() as temporary, patch.object(t, 'atomic_json', side_effect=fail):
            output = Path(temporary)/'run'
            with self.assertRaisesRegex(OSError, 'interrupted checkpoint'):
                self.run_smoke(output)
            report = t.read_json(output/'report.json')
            self.assertEqual(report['episodes_completed'], 0)
            self.assertEqual(report['history'], [])
            self.assertEqual(t.read_json(output/'checkpoint-latest.json.gz')['episodes_completed'], 0)


class MetadataTests(unittest.TestCase):
    def test_schedule_has_exact_disjoint_declared_ranges(self):
        self.assertEqual(t.MILESTONES, (0, 512, 2048, 4096))
        for epoch in (0, 1):
            self.assertEqual({t.training_map(i) for i in range(epoch*2048, (epoch+1)*2048)}, set(t.TRAIN_MAPS))
        self.assertEqual({t.training_map(i, True) for i in range(32)}, {1, 2})
        self.assertFalse(set(t.TRAIN_MAPS) & set(t.VALIDATION_MAPS))
        self.assertFalse(set(t.FINAL_MAPS) & (set(t.TRAIN_MAPS) | set(t.VALIDATION_MAPS)))
        self.assertEqual((t.TRAIN_MAPS[0], t.TRAIN_MAPS[-1]), (620000, 622047))

    def test_source_closure_excludes_secrets_and_old_hybrid(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for package in t.PACKAGES:
                path = root/package/'__init__.py'; path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('# synthetic source\n')
            protocol = root/'docs/learning-hybrid-training.md'
            protocol.parent.mkdir(); protocol.write_text('fixed protocol')
            (root/'.env').write_text('never copied')
            pins = t.source_manifest(root)
            self.assertEqual(len(pins), len(t.PACKAGES)+1)
            self.assertNotIn('.env', pins)
            self.assertFalse(any(name.startswith('lightlag_hybrid/') for name in pins))
            t.assert_source(pins, root)
            protocol.write_text('changed protocol')
            with self.assertRaisesRegex(ValueError, 'source manifest'):
                t.assert_source(pins, root)

    def test_atomic_write_preserves_complete_previous_artifact(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'checkpoint.json.gz'
            t.atomic_json(path, {'complete': 1})
            with patch.object(Path, 'replace', side_effect=OSError('interrupted')):
                with self.assertRaises(OSError):
                    t.atomic_json(path, {'complete': 2})
            self.assertEqual(t.read_json(path), {'complete': 1})

    def test_deadline_job_does_not_construct_policy_or_simulator(self):
        with patch.object(t, 'chooser_from_state') as choose, patch.object(t, 'run_episode') as run:
            result = t.episode_job(({}, 1, 17, True, True, 0))
            self.assertEqual(result['status'], 'deadline')
            choose.assert_not_called(); run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
