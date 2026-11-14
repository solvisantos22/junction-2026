import unittest

from tools.learning_final.plot_results import common_means


class CurveTests(unittest.TestCase):
    def rows(self):
        rows=[]
        for algorithm in ('ppo','replay'):
            for seed in (17,29,43):
                checkpoints={str(count):{'mean_reward':count/10000+seed/1000,'home':32,
                                        'alive':32,'invalid_calls':0}
                             for count in (0,512,2048,8192) if not (algorithm=='replay' and seed==43 and count==8192)}
                rows.append({'algorithm':algorithm,'training_seed':seed,'checkpoints':checkpoints})
        return rows

    def test_missing_final_seed_is_not_replaced_or_averaged_with_earlier_checkpoint(self):
        result=common_means(self.rows())
        self.assertEqual([r['episodes'] for r in result['ppo']],[0,512,2048,8192])
        self.assertEqual([r['episodes'] for r in result['replay']],[0,512,2048])
        self.assertAlmostEqual(result['replay'][-1]['mean_reward'],.2048+(17+29+43)/3000)
        self.assertEqual(result['replay'][-1]['validation_cases'],96)

    def test_missing_or_duplicate_initialization_is_rejected(self):
        with self.assertRaises(ValueError):common_means(self.rows()[:-1])
        rows=self.rows();rows[-1]['training_seed']=29
        with self.assertRaises(ValueError):common_means(rows)


if __name__=='__main__':unittest.main()
