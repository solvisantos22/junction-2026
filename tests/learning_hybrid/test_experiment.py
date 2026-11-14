import copy
import json
from pathlib import Path
import unittest

from lightlag_hybrid.policy import build_specs
from tools.learning_hybrid.experiment import MAPS, select, specs_for, summarize


PARENT = Path(__file__).resolve().parents[2] / 'docs/learning-final-results/policy-freeze.json'


class SelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.specs = build_specs(json.loads(PARENT.read_text()))

    def test_final_retains_every_constituent_and_pure_ensemble(self):
        selection = {'stage': 'confirmation', 'selected_groups': ['blend-all-greedy050']}
        final = specs_for('final', self.specs, selection)
        self.assertEqual(len(final), 10)
        self.assertEqual(sum(s['family'] == 'single_shortlist' for s in final), 6)
        self.assertEqual({s['id'] for s in final if s['family'] == 'rank_ensemble'}, {'ensemble-all-rho000'})
        single = specs_for('final', self.specs, {
            'stage': 'confirmation', 'selected_groups': ['single-replay-rho090']})
        self.assertEqual(len(single), 8)
        self.assertEqual({s['training_seed'] for s in single if s['rho'] == .9}, {17, 29, 43})
        with self.assertRaisesRegex(ValueError, 'no qualified'):
            specs_for('final', self.specs, {'stage': 'confirmation', 'selected_groups': []})

    def test_map_ranges_are_disjoint_and_never_reserved(self):
        ranges = [set(MAPS[s]) for s in ('development', 'confirmation', 'final')]
        self.assertTrue(all(not a & b for i, a in enumerate(ranges) for b in ranges[i+1:]))
        excluded = set(range(500, 524)) | set(range(2026, 2030)) | set(range(82000, 82040)) | set(range(560000, 563000))
        self.assertTrue(all(not r & excluded for r in ranges))

    def test_summarize_averages_seed_scores_before_map_comparison_and_rejects_missing_seed(self):
        selected = [s for s in self.specs if s['id'] in ('greedy', 'beam')
                    or s['group'] == 'single-ppo-rho050']
        jobs, rows = [], {}
        rewards = {17: .9, 29: .1, 43: .2}
        for spec in selected:
            for seed in MAPS['development']:
                jid = f"{spec['id']}-{seed}"
                jobs.append({'id': jid, 'seed': seed, 'spec': spec})
                rows[jid] = {'job_id': jid, 'seed': seed, 'spec_id': spec['id'],
                             'status': 'complete', 'case_sha256': 'b'*64,
                             'audit': {'physics_verified': True, 'hybrid_choices_verified': True,
                                       'job_id': jid, 'case_sha256': 'b'*64},
                             'sha256': 'a'*64, 'home': True, 'alive': True,
                             'invalid_calls': 0, 'error': None,
                             'reward': rewards.get(spec['training_seed'], .3 if spec['id'] == 'greedy' else .5)}
        stage = {'name': 'development', 'jobs': jobs, 'freeze_sha256': 'freeze'}
        state = {'status': 'complete', 'rows': rows, 'freeze_sha256': 'freeze'}
        result = summarize(stage, state)['single-ppo-rho050']
        self.assertAlmostEqual(result['mean_reward'], .4)
        self.assertAlmostEqual(result['vs_greedy']['mean'], .1)
        self.assertEqual(result['episodes'], 384)
        broken = copy.deepcopy(state)
        broken['rows'][jobs[0]['id']]['audit']['physics_verified'] = False
        with self.assertRaisesRegex(ValueError, 'successful audit'):
            summarize(stage, broken)
        reduced = copy.deepcopy(stage)
        reduced['jobs'] = [j for j in jobs if j['spec']['training_seed'] != 43]
        reduced_state = dict(state, rows={j['id']: rows[j['id']] for j in reduced['jobs']})
        with self.assertRaisesRegex(ValueError, 'all three'):
            summarize(reduced, reduced_state)

    def test_selection_preserves_safety_and_never_promotes_confirmation_control(self):
        def item(family, score, rho=.5, deaths=0):
            return {'family': family, 'mean_reward': score, 'rho': rho, 'deaths': deaths,
                    'invalid_calls': 0, 'home_rate': 1, 'vs_greedy': {'mean': score-.4}}
        summary = {'greedy': item('control', .4), 'beam': item('control', .5),
                   'a': item('single_shortlist', .6, deaths=1),
                   'b': item('single_shortlist', .43), 'c': item('single_shortlist', .43),
                   'd': item('single_shortlist', .42), 'pure': item('single_shortlist', .7, rho=0),
                   'ens': item('rank_ensemble', .44, rho=0),
                   'blend': item('rank_blend', .45)}
        self.assertEqual(select({'name': 'development'}, summary), ['b', 'c', 'ens', 'blend'])
        stage = {'name': 'confirmation', 'candidate_groups': ['b', 'c']}
        self.assertEqual(select(stage, summary), ['b'])
        summary['b']['vs_greedy']['mean'] = 0
        summary['c']['vs_greedy']['mean'] = -.001
        self.assertEqual(select(stage, summary), [])


if __name__ == '__main__':
    unittest.main()
