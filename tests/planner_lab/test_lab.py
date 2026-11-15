import ast
import copy
from pathlib import Path
import pickle
import unittest
import numpy as np

from lightlag_traverse.environment import TraverseEnvironment
from lightlag_traverse.pilot import fly
from lightlag_traverse.play import PublicTools
from lightlag_traverse_max.heldout import check_training_seeds
from lightlag_learned_portfolio.policy import play as old_play
from lightlag_planner_lab.policy import PROFILE_NAMES
from lightlag_planner_lab.worker import (LEGACY, LEGACY_SHA, QUICK, digest, load_model, make_prefix,
    run_batch, run_without_copy, source_manifest)
from tools.planner_lab.run import fixed, legacy, jobs_for
from tools.planner_lab.common import TRAIN, VALIDATION, FRESH


class ControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.job = {"id":"test-1","split":"smoke","seed":1,"arms":[fixed('baseline'),fixed('aggressive_guarded'),fixed('baseline')],
                   "quick":True,"keep_replay":True,"source":source_manifest()}
        cls.result = run_batch(cls.job)

    def test_shared_prefix_and_copy_isolation(self):
        a,b,c = self.result['episodes']
        self.assertEqual(a['replay_sha256'],c['replay_sha256'])
        self.assertEqual(a['prefix_sha256'],b['prefix_sha256'])
        self.assertEqual(a['decision']['features'],b['decision']['features'])
        self.assertEqual(len(a['decision']['features']),61)
        self.assertTrue(all(e['error'] is None and not e['invalid'] for e in (a,b,c)))

    def test_clone_equals_ordinary_continuation(self):
        result = run_without_copy(self.job,fixed('aggressive_guarded'))
        self.assertEqual(result['replay_sha256'],self.result['episodes'][1]['replay_sha256'])

    def test_baseline_equals_original_reference(self):
        env = TraverseEnvironment(1); fly(PublicTools(env),QUICK)
        self.assertEqual(digest(env.replay()),self.result['episodes'][0]['replay_sha256'])

    def test_prior_policy_is_preserved(self):
        model = load_model(LEGACY,LEGACY_SHA)
        env = TraverseEnvironment(1)
        old_play(PublicTools(env),{'kind':'learned','threshold':0},model,QUICK)
        result = run_without_copy(self.job,legacy(),model)
        self.assertEqual(digest(env.replay()),result['replay_sha256'])

    def test_delayed_activation_and_reset(self):
        context,_,_ = make_prefix(1,True); p = copy.deepcopy(context)[0]
        p.configure('aggressive_late'); p.before_step()
        self.assertFalse(p.activated); self.assertEqual(p.opt,p.initial_options)
        p.now=140; p.before_step(); self.assertEqual(p.opt['floor'],2.)
        p = copy.deepcopy(context)[0]; p.configure('aggressive_safe300'); p.before_step()
        p.now=300; p.before_step(); self.assertTrue(p.reset_done); self.assertEqual(p.opt,p.initial_options)

    def test_public_policy_boundary_and_seeds(self):
        tree=ast.parse((Path(__file__).parents[2]/'lightlag_planner_lab/policy.py').read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.ImportFrom): self.assertNotIn('environment',node.module or '')
            if isinstance(node,ast.Attribute): self.assertNotIn(node.attr,('_env','_world','_seed','_truth','replay','evaluate'))
        self.assertEqual(len(set(TRAIN+VALIDATION+FRESH)),len(TRAIN+VALIDATION+FRESH))
        check_training_seeds(TRAIN+VALIDATION+FRESH)
        for seed in (500,523,2026,2029,99991):
            with self.assertRaises(ValueError): check_training_seeds([seed])

    def test_fixed_job_grid(self):
        jobs=jobs_for('data')
        self.assertEqual(sum(len(j['arms']) for j in jobs),7232)
        self.assertEqual(len({j['id'] for j in jobs}),len(jobs))
        self.assertEqual(len(PROFILE_NAMES),16)


class ModelTests(unittest.TestCase):
    def test_models_fit_and_checkpoint_roundtrip(self):
        from lightlag_planner_lab.model import ALGORITHMS,fit
        rng=np.random.default_rng(37);x=rng.normal(size=(128,8))
        y=np.column_stack([.025*x[:,0]+.01*(i+1)/15*x[:,1] for i in range(15)])
        data={'x':x.tolist(),'y':y.tolist(),'home_alive':np.ones_like(y,dtype=int).tolist(),
              'feature_names':['f'+str(i) for i in range(8)]}
        for algorithm in ALGORITHMS:
            with self.subTest(algorithm=algorithm):
                result=fit(algorithm,data);model=pickle.loads(result['weights'])
                mean,spread,risk=model.predict(x)
                self.assertTrue(np.isfinite(mean).all() and np.isfinite(spread).all() and np.isfinite(risk).all())
                np.testing.assert_allclose(mean,result['training_predictions'],rtol=0,atol=0)
                self.assertLess(result['training_mse'],float(np.mean(y*y)))
                name,_=model.choose(dict(zip(data['feature_names'],x[0])),{'threshold':100.})
                self.assertEqual(name,'baseline')


if __name__ == '__main__': unittest.main()
