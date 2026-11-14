import contextlib
import copy
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from lightlag_learning_final import train as runner


class FakeLearner:
    """Exercise persistence without simulator worlds or optimizer work."""
    def __init__(self, algorithm, candidate_dim, global_dim, seed, total_episodes=2048):
        self.algorithm, self.seed, self.episodes_seen = algorithm, seed, 0
        self.schedule = total_episodes

    def state_dict(self):
        return dict(algorithm=self.algorithm, seed=self.seed,
                    episodes_seen=self.episodes_seen, schedule=self.schedule)

    @classmethod
    def from_state(cls, state):
        obj = cls(state['algorithm'], 20, 14, state['seed'], state['schedule'])
        obj.episodes_seen = state['episodes_seen']
        return obj

    inference_state = state_dict

    def update(self, episodes):
        self.episodes_seen += len(episodes)
        return {'episodes_seen': self.episodes_seen}


def synthetic_collect(pool, policy, maps, seed, offset=0, **kwargs):
    return [{'seed': world, 'reward': .25, 'decision_count': 1,
             'action_seed': seed * 1_000_000_000 + offset + index,
             'result': {'at_base': True, 'alive': True}}
            for index, world in enumerate(maps)]


class TrainingLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.stack.enter_context(patch.object(runner, 'Learner', FakeLearner))
        self.stack.enter_context(patch.object(runner, 'ProcessPoolExecutor', MagicMock()))
        self.stack.enter_context(patch.object(runner, 'source_pins', return_value={'synthetic': 'pin'}))
        self.collect = self.stack.enter_context(patch.object(runner, 'collect', side_effect=synthetic_collect))

    def run_smoke(self, output, episodes=32, **kwargs):
        return runner.train('ppo', 17, episodes, output, workers=1, smoke=True, **kwargs)

    def test_frozen_schedule_and_intermediate_milestones(self):
        for epoch in range(2):
            self.assertEqual({runner.training_map(i) for i in range(epoch*512, (epoch+1)*512)},
                             set(runner.TRAIN_MAPS))
        self.assertFalse(set(runner.TRAIN_MAPS) & set(runner.VALIDATION_MAPS))
        self.assertFalse(set(runner.FINAL_MAPS) & (set(runner.TRAIN_MAPS) | set(runner.VALIDATION_MAPS)))
        self.assertEqual({runner.training_map(i, True) for i in range(32)}, {1, 2})
        self.assertEqual(runner.MILESTONES, (0, 512, 2048, 8192, 16384, 24576, 32768))

    def test_atomic_replace_preserves_previous_complete_bytes_on_failure(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'checkpoint.json.gz'
            runner.atomic_json(path, {'a': 1})
            with patch.object(Path, 'replace', side_effect=OSError('interrupted')):
                with self.assertRaises(OSError):
                    runner.atomic_json(path, {'a': 2})
            self.assertEqual(runner.read_json(path), {'a': 1})
            runner.atomic_json(path, {'a': 3})
            self.assertEqual(runner.read_json(path), {'a': 3})
            self.assertFalse(path.with_suffix('.gz.tmp').exists())

    def test_archive_crash_recovers_without_rerunning_validation(self):
        with tempfile.TemporaryDirectory() as root:
            atomic = runner.atomic_bytes

            def interrupted(path, data):
                if Path(path).name == 'checkpoint-00032.json.gz':
                    raise OSError('archive interrupted')
                atomic(path, data)

            with patch.object(runner, 'atomic_bytes', side_effect=interrupted):
                with self.assertRaisesRegex(OSError, 'archive interrupted'):
                    self.run_smoke(root)
            latest = runner.read_json(Path(root) / 'checkpoint-latest.json.gz')
            self.assertIn('32', latest['validations'])
            self.collect.reset_mock()
            resumed = self.run_smoke(root, deadline_unix=0)
            self.assertEqual(resumed['status'], 'complete')
            self.collect.assert_not_called()
            self.assertEqual(runner.read_json(Path(root) / 'checkpoint-00032.json.gz'), latest)
            self.assertEqual(resumed['experiment'], 'learning-final-20261114')

    def test_continuation_keeps_history_and_rejects_missing_or_wrong_archive(self):
        with tempfile.TemporaryDirectory() as root:
            self.run_smoke(root)
            continued = self.run_smoke(root, episodes=64)
            self.assertEqual(continued['episodes_completed'], 64)
            self.assertEqual(set(continued['validations']), {'0', '32', '64'})
            archive = Path(root) / 'checkpoint-00032.json.gz'
            original = runner.read_json(archive)
            tampered = copy.deepcopy(original)
            tampered['identity']['experiment'] = 'old-pilot'
            runner.atomic_json(archive, tampered)
            with self.assertRaisesRegex(ValueError, 'milestone checkpoint identity'):
                self.run_smoke(root, episodes=64)
            archive.unlink()
            with self.assertRaisesRegex(ValueError, 'milestone checkpoint is missing'):
                self.run_smoke(root, episodes=64)

    def test_deadline_honest_and_resume_rejects_old_identity_or_changed_history(self):
        with tempfile.TemporaryDirectory() as root:
            report = self.run_smoke(root, deadline_unix=0)
            self.assertEqual((report['status'], report['episodes_completed']), ('deadline', 0))
            self.assertEqual(report['validations'], {})
            self.collect.assert_not_called()
            path = Path(root) / 'checkpoint-latest.json.gz'
            checkpoint = runner.read_json(path)
            for field, value in [('experiment', 'old-pilot'), ('numpy', 'other-version'),
                                 ('source_sha256', {'synthetic': 'changed'})]:
                bad = copy.deepcopy(checkpoint)
                bad['identity'][field] = value
                runner.atomic_json(path, bad)
                with self.assertRaisesRegex(ValueError, 'identity/source/runtime'):
                    self.run_smoke(root)
            runner.atomic_json(path, checkpoint)
            self.run_smoke(root)
            (Path(root) / 'batches/batch-00000.json.gz').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'history is incomplete or changed'):
                self.run_smoke(root, episodes=64)

    def test_nonempty_destination_and_protocol_limits(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / 'unrelated').write_text('retain')
            with self.assertRaisesRegex(ValueError, 'nonempty'):
                self.run_smoke(root)
            for options in ({'episodes': 2048}, {'workers': 7}, {'seed': 99}):
                args = dict(algorithm='ppo', seed=17, episodes=8192, output=root, workers=1)
                args.update(options)
                with self.assertRaises(ValueError):
                    runner.train(**args)
            self.assertEqual((Path(root) / 'unrelated').read_text(), 'retain')


class SourcePinTests(unittest.TestCase):
    def test_pins_final_protocol_and_all_seven_packages_only(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            for package in ('lightlag_learning', 'lightlag_traverse', 'lightlag', 'lightlag_mcp',
                            'lightlag_rl', 'lightlag_rl_feasible', 'lightlag_learning_final'):
                (root / package).mkdir()
                (root / package / '__init__.py').write_text('# source\n')
            (root / 'docs').mkdir()
            (root / 'docs/learning-final.md').write_text('frozen final protocol')
            (root / 'docs/learning-campaign.md').write_text('old protocol')
            (root / '.env').write_text('synthetic-secret-never-read')
            with patch.object(runner, 'ROOT', root):
                pins = runner.source_pins()
            self.assertEqual(len(pins), 8)
            self.assertIn('docs/learning-final.md', pins)
            self.assertNotIn('docs/learning-campaign.md', pins)
            self.assertNotIn('.env', pins)


if __name__ == '__main__':
    unittest.main()
