from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from lightlag_survey import repair_study


class RepairStudyTests(unittest.TestCase):
    def test_real_old_policy_public_transcript_reconstructs(self):
        row, record = repair_study.run_episode(0, 100, 'old_no_probe')
        self.assertEqual(row['status'], 'completed')
        self.assertTrue(row['reconstruction_passed'])
        self.assertTrue(row['alive'])
        self.assertEqual(record['result']['tick'], 60)
        self.assertGreater(len(record['transcript']), 10)

    def test_controller_error_is_retained_not_scored_as_weak_play(self):
        def failing(tools, mode):
            tools.rules()
            raise RuntimeError('deliberate failure')
        with patch.object(repair_study, 'run_new', failing):
            row, record = repair_study.run_episode(0, 100, 'new_reference')
        self.assertEqual(row['status'], 'error')
        self.assertIsNone(row['raw_score'])
        self.assertEqual(record['result']['tick'], 60)
        self.assertTrue(record['evaluator_advances'])
        self.assertTrue(row['reconstruction_passed'])
        summary = repair_study.summarize([row])
        self.assertFalse(summary['all_completed'])
        self.assertEqual(summary['errors'], 1)
        self.assertEqual(summary['policies'], {})

    def test_existing_directory_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as root:
            marker = Path(root) / 'keep'
            marker.write_text('original')
            with self.assertRaises(FileExistsError):
                repair_study.run_study(root)
            self.assertEqual(marker.read_text(), 'original')
