import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from lightlag_learning.train import (TRAIN_MAPS, VALIDATION_MAPS, FINAL_MAPS,
                                    atomic_json, read_json, training_map, train)


class TrainingLifecycleTests(unittest.TestCase):
    def test_common_map_schedule_is_permutation_and_disjoint(self):
        self.assertEqual(set(training_map(i) for i in range(512)), set(TRAIN_MAPS))
        self.assertEqual(set(training_map(i) for i in range(512,1024)),set(TRAIN_MAPS))
        self.assertFalse(set(TRAIN_MAPS)&set(VALIDATION_MAPS))
        self.assertFalse(set(FINAL_MAPS)&(set(TRAIN_MAPS)|set(VALIDATION_MAPS)))
        self.assertEqual(set(training_map(i,True) for i in range(32)),{1,2})

    def test_atomic_compressed_roundtrip_and_no_temporary(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'nested/checkpoint.json.gz'
            atomic_json(path,{'a':[1,2,3]})
            self.assertEqual(read_json(path),{'a':[1,2,3]})
            self.assertFalse(path.with_suffix('.gz.tmp').exists())
            atomic_json(path,{'a':4})
            self.assertEqual(read_json(path),{'a':4})

    def test_expired_run_does_not_open_worlds_and_rejects_wrong_resume(self):
        with tempfile.TemporaryDirectory() as root, patch('lightlag_learning.train.source_pins',return_value={'test':'pin'}):
            with patch('lightlag_learning.train.episode_job',side_effect=AssertionError('no episode permitted')):
                result=train('ppo',17,32,root,workers=1,deadline_unix=0,smoke=True)
            self.assertEqual(result['status'],'deadline')
            self.assertEqual(result['episodes_completed'],0)
            with self.assertRaisesRegex(ValueError,'identity'):
                train('ppo',29,32,root,workers=1,deadline_unix=0,smoke=True)
            with self.assertRaisesRegex(ValueError,'identity'):
                train('replay',17,32,root,workers=1,deadline_unix=0,smoke=True)
            resumed=train('ppo',17,32,root,workers=1,deadline_unix=0,smoke=True)
            self.assertEqual(resumed['status'],'deadline')

    def test_nonempty_destination_and_undeclared_budget_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root)/'unrelated').write_text('retain')
            with self.assertRaisesRegex(ValueError,'nonempty'):
                train('ppo',17,32,root,smoke=True)
            with self.assertRaisesRegex(ValueError,'declared'):
                train('ppo',17,32,root)
            self.assertEqual((Path(root)/'unrelated').read_text(),'retain')


if __name__=='__main__':unittest.main()
