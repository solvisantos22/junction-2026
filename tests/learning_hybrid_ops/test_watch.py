"""Private watcher tests; every status command and queue dispatch is synthetic."""
import copy
import fcntl
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools.learning_hybrid_ops import watch

NOW = watch.DEADLINE - 3600


class WatchTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='hybrid-watch-test-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.monitor = self.root / 'monitor'
        self.monitor.mkdir()
        self.state = self.monitor / 'watch.json'
        self.config = {'monitor_directory': str(self.monitor), 'working_directory': str(self.root),
                       'python_path': str(self.root / 'fake-python'), 'codex_path': str(self.root / 'fake-codex'),
                       'thread_id': 'current-thread', 'deadline_unix': watch.DEADLINE, 'targets': []}
        self.target = self.add_target('development')
        self.responses = {}
        self.calls = []
        self.queue_effect = None
        self.receipt(self.target)
        self.set_hybrid(self.target)

    def add_target(self, name, kind='hybrid'):
        cwd = self.root / (name + '-frozen')
        module = watch.MODULES[kind]
        source = cwd / (module.replace('.', '/') + '.py')
        source.parent.mkdir(parents=True)
        source.write_text('# frozen synthetic status module\n')
        target = {'id': name, 'kind': kind, 'module': module, 'working_directory': str(cwd),
                  'receipt_path': str(self.monitor / (name + '-receipt.json')), 'freeze_sha256': 'a' * 64}
        self.config['targets'].append(target)
        return target

    def receipt(self, target, status='submitted'):
        value = {'schema': 'learning-hybrid-receipt-v1' if target['kind'] == 'hybrid' else 'greedy-prior-receipt-v1',
                 'status': status, 'freeze_sha256': target['freeze_sha256'], 'stage': target['id']}
        Path(target['receipt_path']).write_text(json.dumps(value))

    def set_hybrid(self, target, status='running', **extra):
        self.responses[target['id']] = {'schema': 'learning-hybrid-monitor-v1', 'stage': target['id'],
                                        'stop_marker': False, 'state': {'status': status, **extra}}

    def set_prior(self, target, statuses=None):
        statuses = statuses or ['running'] * 6
        self.responses[target['id']] = {'schema': 'greedy-prior-status-v1', 'stop_marker': False,
            'jobs': [{'job': {'variant': variant, 'seed': seed, 'run_id': f'{variant}-{seed}'},
                      'result': None, 'state': {'status': statuses[i]}, 'progress': {'episodes_completed': 512}}
                     for i, (variant, seed) in enumerate((v, s) for v in ('prior', 'plain') for s in (17, 29, 43))]}

    def runner(self, command, **kwargs):
        self.calls.append((command, kwargs))
        if command[1] == '-m':
            target = next(t for t in self.config['targets'] if t['receipt_path'] == command[-1])
            response = self.responses[target['id']]
            if isinstance(response, BaseException):
                raise response
            value = copy.deepcopy(response)
            value.setdefault('receipt_sha256', watch.digest(target['receipt_path']))
            return subprocess.CompletedProcess(command, 0, json.dumps(value), '')
        self.assertEqual(command[1], 'queue')
        saved = watch.read(self.state)
        self.assertTrue(any(event['status'] == 'reserved' for event in saved['events'].values()))
        if self.queue_effect:
            return self.queue_effect(command, kwargs)
        return subprocess.CompletedProcess(command, 0, 'queued\n', '')

    def tick(self, now=NOW, runner=None):
        return watch.tick(self.config, self.state, runner=runner or self.runner, now=now)

    def queues(self):
        return [c for c in self.calls if c[0][1] == 'queue']

    def test_running_status_keeps_private_progress_without_waking(self):
        prior = self.add_target('prior', 'prior')
        self.receipt(prior)
        self.set_prior(prior)
        state = self.tick()
        self.assertEqual(state['status'], 'watching')
        self.assertEqual(state['updated_unix'], NOW)
        self.assertEqual(state['targets']['prior']['progress']['prior-17']['episodes_completed'], 512)
        self.assertEqual(self.queues(), [])
        self.assertEqual(self.state.stat().st_mode & 0o777, 0o600)
        for command, options in self.calls:
            self.assertEqual(command[1:2], ['-m'])
            self.assertEqual(command[-2], '--status')
            self.assertEqual(options['env']['MODAL_PROFILE'], 'solvi-junction')
            self.assertNotIn('ANTHROPIC_API_KEY', options['env'])
            self.assertEqual(options['timeout'], 45)
        self.assertTrue((self.monitor / 'statuses' / 'prior.json').is_file())

    def test_missing_future_receipts_are_skipped_until_they_appear(self):
        future = self.add_target('confirmation')
        state = self.tick()
        self.assertEqual(state['targets']['confirmation']['status'], 'missing')
        self.assertEqual(state['targets']['confirmation']['read_errors'], 0)
        self.assertEqual(len(self.calls), 1)
        self.receipt(future, 'preparing')
        state = self.tick(NOW + 60)
        self.assertEqual(state['targets']['confirmation']['status'], 'pending_receipt')
        self.receipt(future)
        self.set_hybrid(future)
        state = self.tick(NOW + 120)
        self.assertEqual(state['targets']['confirmation']['status'], 'running')
        self.assertEqual(self.queues(), [])

    def test_hybrid_terminal_queues_once_with_required_context(self):
        self.set_hybrid(self.target, 'complete', jobs_complete=8320, jobs_total=8320)
        first = self.tick()
        self.assertEqual(first['status'], 'finished')
        self.assertEqual(first['events']['development:completion']['status'], 'queued')
        self.tick(NOW + 60)
        self.assertEqual(len(self.queues()), 1)
        command, options = self.queues()[0]
        self.assertEqual(command[:4], [self.config['codex_path'], 'queue', '--thread', 'current-thread'])
        self.assertEqual(command[-1], '--resume')
        message = command[command.index('--message') + 1]
        for phrase in ('AGENTS.md', 'junction-team-workflow', 'TEAM_STATUS.md', 'No Superpowers', 'never repeat completed jobs'):
            self.assertIn(phrase, message)
        self.assertEqual(options['cwd'], str(self.root))

    def test_training_requires_all_six_terminal_and_preserves_incomplete(self):
        prior = self.add_target('prior', 'prior')
        self.receipt(prior)
        self.set_prior(prior, ['completed'] * 5 + ['running'])
        self.tick()
        self.assertEqual(self.queues(), [])
        self.set_prior(prior, ['completed'] * 5 + ['stopped_deadline'])
        state = self.tick(NOW + 60)
        self.assertEqual(state['targets']['prior']['status'], 'terminal_with_incomplete')
        self.assertEqual(state['targets']['prior']['jobs_complete'], 5)
        self.tick(NOW + 120)
        self.assertEqual(len(self.queues()), 2)

    def test_one_failed_training_run_wakes_before_other_five_finish(self):
        prior = self.add_target('prior', 'prior')
        self.receipt(prior)
        self.set_prior(prior, ['wrapper_error'] + ['running'] * 5)
        state = self.tick()
        self.assertEqual(state['targets']['prior']['status'], 'running')
        self.assertTrue(state['targets']['prior']['failure_present'])
        self.assertEqual(state['targets']['prior']['failed_run_ids'], ['prior-17'])
        self.assertEqual(set(state['events']), {'prior:error'})
        self.tick(NOW + 60)
        self.assertEqual(len(self.queues()), 1)
        self.set_prior(prior, ['wrapper_error'] + ['completed'] * 5)
        state = self.tick(NOW + 120)
        self.assertEqual(set(state['events']), {'prior:error', 'prior:completion'})
        self.assertEqual(len(self.queues()), 2)

    def test_three_consecutive_errors_wake_once_then_completion_separately(self):
        self.responses['development'] = OSError('synthetic network issue')
        self.tick()
        self.tick(NOW + 60)
        self.assertEqual(self.queues(), [])
        self.tick(NOW + 120)
        self.tick(NOW + 180)
        self.assertEqual(len(self.queues()), 1)
        self.set_hybrid(self.target)
        recovered = self.tick(NOW + 240)
        self.assertEqual(recovered['targets']['development']['read_errors'], 0)
        self.set_hybrid(self.target, 'failed')
        state = self.tick(NOW + 300)
        self.assertEqual(set(state['events']), {'development:error', 'development:completion'})
        self.assertEqual(len(self.queues()), 2)

    def test_nonconsecutive_errors_do_not_reach_threshold(self):
        for n in range(3):
            self.responses['development'] = subprocess.TimeoutExpired('status', 45)
            self.tick(NOW + n * 120)
            self.set_hybrid(self.target)
            self.tick(NOW + n * 120 + 60)
        self.assertEqual(self.queues(), [])

    def test_each_local_stop_marker_suppresses_deadline_and_stays_disabled(self):
        for marker in ('pause.json', 'wake-stop', 'stop'):
            with self.subTest(marker=marker):
                self.state = self.monitor / (marker + '-state.json')
                path = self.monitor / marker
                path.write_text('stop')
                state = self.tick(watch.DEADLINE + 1)
                self.assertEqual(state['status'], 'disabled')
                path.unlink()
                self.assertEqual(self.tick(watch.DEADLINE + 60)['status'], 'disabled')
        self.assertEqual(self.calls, [])

    def test_remote_stop_from_any_target_suppresses_other_completion(self):
        prior = self.add_target('prior', 'prior')
        self.receipt(prior)
        self.set_prior(prior, ['completed'] * 5 + ['stopped_marker'])
        self.set_hybrid(self.target, 'complete')
        self.assertEqual(self.tick()['status'], 'disabled')
        self.assertEqual(self.queues(), [])

    def test_pause_created_during_read_wins_over_completion(self):
        self.set_hybrid(self.target, 'complete')
        def paused(command, **kwargs):
            result = self.runner(command, **kwargs)
            (self.monitor / 'wake-stop').write_text('stop')
            return result
        self.assertEqual(self.tick(runner=paused)['status'], 'disabled')
        self.assertEqual(self.queues(), [])

    def test_uncertain_queue_results_are_never_retried(self):
        self.set_hybrid(self.target, 'complete')
        effects = [lambda c, k: subprocess.CompletedProcess(c, 1, '', 'synthetic failure'),
                   lambda c, k: subprocess.CompletedProcess(c, 0, 'queued', 'Warning: resume failed'),
                   lambda c, k: (_ for _ in ()).throw(subprocess.TimeoutExpired(c, 45))]
        for index, effect in enumerate(effects):
            with self.subTest(index=index):
                self.state = self.monitor / f'uncertain-{index}.json'
                self.calls.clear()
                self.queue_effect = effect
                state = self.tick()
                self.assertEqual(state['events']['development:completion']['status'], 'uncertain')
                self.tick(NOW + 60)
                self.assertEqual(len(self.queues()), 1)

    def test_crash_after_durable_reservation_is_not_resent(self):
        self.set_hybrid(self.target, 'complete')
        self.queue_effect = lambda c, k: (_ for _ in ()).throw(KeyboardInterrupt())
        with self.assertRaises(KeyboardInterrupt):
            self.tick()
        self.assertEqual(watch.read(self.state)['events']['development:completion']['status'], 'reserved')
        self.queue_effect = None
        self.tick(NOW + 60)
        self.assertEqual(len(self.queues()), 1)

    def test_absolute_deadline_wakes_once_even_with_missing_future_receipt(self):
        self.add_target('final')
        state = self.tick(watch.DEADLINE)
        self.assertEqual(state['status'], 'deadline')
        self.assertEqual(set(state['events']), {'deadline'})
        self.tick(watch.DEADLINE + 60)
        self.assertEqual(len(self.queues()), 1)

    def test_config_code_and_status_module_drift_fail_closed(self):
        self.tick()
        original = copy.deepcopy(self.config)
        self.config['thread_id'] = 'different'
        with self.assertRaisesRegex(ValueError, 'identity changed'):
            self.tick()
        self.config = original
        with patch.object(watch, '__file__', str(self.root / 'missing-watcher.py')):
            with self.assertRaises(FileNotFoundError):
                self.tick()
        source = Path(self.target['working_directory']) / (self.target['module'].replace('.', '/') + '.py')
        source.write_text('# changed\n')
        with self.assertRaisesRegex(ValueError, 'identity changed'):
            self.tick()
        self.assertEqual(self.queues(), [])

    def test_submitted_receipt_and_response_hashes_must_remain_bound(self):
        self.tick()
        path = Path(self.target['receipt_path'])
        path.write_text(path.read_text() + '\n')
        state = self.tick(NOW + 60)
        self.assertEqual(state['targets']['development']['error_type'], 'ValueError')
        self.state = self.monitor / 'different-response.json'
        self.responses['development']['receipt_sha256'] = 'b' * 64
        state = self.tick(NOW + 120)
        self.assertEqual(state['targets']['development']['error_type'], 'ValueError')
        self.assertEqual(self.queues(), [])

    def test_existing_lock_prevents_second_process(self):
        with Path(str(self.state) + '.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):
                self.tick()
        self.assertEqual(self.calls, [])

    def test_disappearing_submitted_receipt_is_an_error(self):
        self.tick()
        Path(self.target['receipt_path']).unlink()
        state = self.tick(NOW + 60)
        self.assertEqual(state['targets']['development']['read_errors'], 1)
        self.assertEqual(state['targets']['development']['error_type'], 'FileNotFoundError')

    def test_cli_failure_records_private_error_without_overwriting_pinned_state(self):
        self.tick()
        original = self.state.read_bytes()
        config_path = self.monitor / 'config.json'
        config_path.write_text(json.dumps(self.config))
        with patch.object(watch, 'tick', side_effect=ValueError('synthetic identity mismatch')):
            with self.assertRaises(ValueError):
                watch.main(['--config', str(config_path), '--state', str(self.state), '--once'])
        self.assertEqual(self.state.read_bytes(), original)
        error_path = Path(str(self.state) + '.error.json')
        self.assertEqual(watch.read(error_path)['error_type'], 'ValueError')
        self.assertEqual(error_path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.queues(), [])

    def test_real_clock_heartbeat_updates_after_status_read(self):
        with patch.object(watch.time, 'time', side_effect=[NOW, NOW + 12]):
            state = watch.tick(self.config, self.state, runner=self.runner)
        self.assertEqual(state['poll_started_unix'], NOW)
        self.assertEqual(state['poll_finished_unix'], NOW + 12)
        self.assertEqual(state['updated_unix'], NOW + 12)

    def test_remote_read_errors_and_invalid_six_job_matrix_are_explicit(self):
        prior = self.add_target('prior', 'prior')
        self.receipt(prior)
        self.set_prior(prior)
        self.responses['prior']['jobs'][0]['progress_error_type'] = 'ConnectionError'
        state = self.tick()
        self.assertEqual(state['targets']['prior']['error_type'], 'RuntimeError')
        self.responses['prior']['jobs'].pop()
        state = self.tick(NOW + 60)
        self.assertEqual(state['targets']['prior']['error_type'], 'ValueError')
        self.assertEqual(self.queues(), [])


if __name__ == '__main__':
    unittest.main()
