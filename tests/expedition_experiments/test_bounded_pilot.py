import json
from pathlib import Path
import tempfile
import unittest

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
