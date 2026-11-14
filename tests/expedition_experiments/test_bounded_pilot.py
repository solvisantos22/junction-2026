import contextlib
import io
import json
import signal
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tools.expedition_experiments import bounded_pilot as pilot
from tools.expedition_experiments.bounded_pilot import previous_usage, reported_usage


class SpendGuardTests(unittest.TestCase):
    def test_stream_deduplicates_finishes_and_rejects_unknown_usage(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'opencode.txt'
            self.assertEqual(reported_usage(path)['finished_steps'], 0)
            event = {'type': 'step_finish', 'sessionID': 's', 'part': {'id': 'p', 'cost': .2}}
            path.write_text(json.dumps(event)+'\n'+json.dumps(event)+'\n{"unfinished":')
            self.assertEqual(reported_usage(path), {'cost_usd': .2, 'finished_steps': 1, 'unknown': False})
            event['part'] = {'id': 'p2', 'cost': None}
            with path.open('a') as f:
                f.write('\n'+json.dumps(event)+'\n')
            self.assertTrue(reported_usage(path)['unknown'])

    def test_malformed_complete_events_fail_closed_and_partial_utf8_waits(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'stream'
            for invalid in (b'not-json\n', b'null\n', b'[]\n',
                            b'{"type":"step_finish","part":[]}\n',
                            b'{"type":"step_finish","sessionID":[],"part":{"id":[]}}\n'):
                path.write_bytes(invalid)
                self.assertTrue(reported_usage(path)['unknown'])
            path.write_bytes(b'{"type":"text","value":"\xe2')
            self.assertFalse(reported_usage(path)['unknown'])
            self.assertTrue(reported_usage(path, final=True)['unknown'])

    def test_order_unknown_censored_and_spend_stop_launch(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            (root/'assignments.private.json').write_text(json.dumps([{'assignment_id': x} for x in ['a','b']]))
            self.assertEqual(previous_usage(root, 'a'), 0)
            with self.assertRaises(ValueError): previous_usage(root, 'b')
            (root/'started-a.json').write_text('{}')
            path = root/'jobs/model-a/trial/result.json'
            path.parent.mkdir(parents=True)
            for cost, censored, valid in [(None,None,False),(.4,'guard',False),(1.5,None,False),(.4,None,True)]:
                path.write_text(json.dumps({'finished_at':'time','agent_result':{'cost_usd':cost}}))
                (root/'monitor-a.json').write_text(json.dumps({'censored_reason': censored}))
                if valid:self.assertEqual(previous_usage(root,'b'),.4)
                else:
                    with self.assertRaises(ValueError):previous_usage(root,'b')

    def test_live_container_uses_exact_trial_name_and_exports_only_usage_scalars(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            trial = root / 'task__aBc123'
            trial.mkdir()
            stream = root / 'private-stream'
            stream.write_text(json.dumps({'type': 'text', 'part': {'text': 'PRIVATE MODEL TEXT'}}) + '\n'
                              + json.dumps({'type': 'step_finish', 'sessionID': 's',
                                            'part': {'id': 'p', 'cost': .125}}) + '\n')
            name = 'task__abc123__env-main-1'
            calls = []

            def docker(command, **kwargs):
                calls.append(command)
                if command[1] == 'ps':
                    return SimpleNamespace(returncode=0, stdout=name + '\n')
                self.assertEqual(command[:5], ['/fake/docker', 'exec', name, 'python', '-c'])
                # Execute the real generated extractor against a local synthetic log.
                # It may see provider text internally but must export only scalars.
                stdout = io.StringIO()
                with patch('pathlib.Path', return_value=stream), contextlib.redirect_stdout(stdout):
                    exec(command[5], {})
                self.assertNotIn('PRIVATE MODEL TEXT', stdout.getvalue())
                return SimpleNamespace(returncode=0, stdout=stdout.getvalue())

            with patch.object(pilot.subprocess, 'run', side_effect=docker):
                usage = pilot.container_usage(root, docker='/fake/docker')
            self.assertEqual(usage, {'cost_usd': .125, 'finished_steps': 1, 'unknown': False, 'present': True})
            self.assertEqual(calls[0], ['/fake/docker', 'ps', '--filter',
                                       'name=^/' + name + '$', '--format', '{{.Names}}'])

    def test_live_container_startup_absence_and_teardown_do_not_inspect_teammates(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.object(pilot.subprocess, 'run') as docker:
                self.assertIsNone(pilot.container_usage(root))
                docker.assert_not_called()
            (root / 'ours__abc').mkdir()
            with patch.object(pilot.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout='teammate__env-main-1\n')) as docker:
                self.assertIsNone(pilot.container_usage(root))
                self.assertEqual(docker.call_count, 1)
            results = [SimpleNamespace(returncode=0, stdout='ours__abc__env-main-1\n'),
                       SimpleNamespace(returncode=1, stdout=''),
                       SimpleNamespace(returncode=0, stdout='teammate__env-main-1\n')]
            with patch.object(pilot.subprocess, 'run', side_effect=results):
                self.assertIsNone(pilot.container_usage(root))

    def test_live_container_ambiguity_and_docker_failure_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'ours__abc').mkdir()
            with patch.object(pilot.subprocess, 'run', return_value=SimpleNamespace(returncode=1, stdout='')):
                self.assertTrue(pilot.container_usage(root)['unknown'])
            results = [SimpleNamespace(returncode=0, stdout='ours__abc__env-main-1\n'),
                       SimpleNamespace(returncode=1, stdout=''),
                       SimpleNamespace(returncode=0, stdout='ours__abc__env-main-1\n')]
            with patch.object(pilot.subprocess, 'run', side_effect=results):
                self.assertTrue(pilot.container_usage(root)['unknown'])
            (root / 'unexpected__second').mkdir()
            with patch.object(pilot.subprocess, 'run') as docker:
                self.assertTrue(pilot.container_usage(root)['unknown'])
                docker.assert_not_called()

    def test_run_uses_live_container_guard_when_host_logs_are_absent(self):
        for observation, reason in [({'cost_usd': 2.3, 'finished_steps': 1, 'unknown': False}, 'reported_usage_guard'),
                                    ({'cost_usd': 0, 'finished_steps': 0, 'unknown': True}, 'unknown_inflight_usage')]:
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / 'tasks/a').mkdir(parents=True)
                (root / 'tasks/a/experiment.json').write_text('{"task_sha256": {}}')
                (root / 'opencode-config.json').write_text('{}')
                process = Mock()
                process.poll.side_effect = [None, 0]
                process.wait.return_value = 0
                with patch.object(pilot, 'previous_usage', return_value=0), \
                     patch.object(pilot, 'read_key', return_value='test-only-not-a-key'), \
                     patch.object(pilot.os, 'environ', {}), \
                     patch.object(pilot.subprocess, 'Popen', return_value=process), \
                     patch.object(pilot, 'container_usage', return_value=observation) as live, \
                     patch.object(pilot.time, 'sleep'):
                    report = pilot.run(root, 'a', '/never/read', '/never/harbor')
                live.assert_called_once_with(root.resolve() / 'jobs/model-a')
                process.send_signal.assert_called_once_with(signal.SIGINT)
                self.assertEqual(report['censored_reason'], reason)
                self.assertEqual(report['live_observations'][0]['cost_usd'], observation['cost_usd'])
                self.assertTrue(report['final_stream_usage']['unknown'])
                self.assertTrue((root / 'monitor-a.json').exists())
