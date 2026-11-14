import tempfile
from pathlib import Path
import unittest
import subprocess
import sys
import platform

from tools.learning_final import compatibility as c


class CompatibilityTests(unittest.TestCase):
    def test_schedule_is_matched_used_maps_without_final_or_submission_worlds(self):
        manifest = {'maps': list(c.MAPS), 'arms': [{'id': f'{a}-{s}'} for a in ('ppo', 'replay')
                    for s in c.SEEDS]+[{'id': 'greedy'}]}
        jobs = c.jobs(manifest)
        self.assertEqual(len(jobs), 112)
        self.assertEqual(len({tuple(sorted(j.items())) for j in jobs}),112)
        self.assertFalse(set(c.MAPS)&({2026,2027,2028,2029}|set(range(82000,82040))))

    def test_gate_keeps_return_failure_even_with_score_improvement(self):
        arms = [{'id': a, 'algorithm': a} for a in ('ppo','replay','greedy')]
        manifest = {'maps':[1,2], 'arms':arms, 'gate':{'minimum_mean_new_minus_old':-.01,
                    'maximum_home_loss':1,'maximum_deaths':0,'maximum_invalid_calls':0}}
        rows = [{'version':v,'arm':a,'seed':s,'reward':.2 if v=='new' else .1,
                 'home':v=='old','alive':True,'invalid_calls':0}
                for a in ('ppo','replay','greedy') for v in ('old','new') for s in (1,2)]
        result=c.summarize(rows,manifest)
        self.assertFalse(result['ppo']['gate_pass'])
        self.assertIsNone(result['greedy']['gate_pass'])
        with self.assertRaises(ValueError):c.summarize(rows[:-1],manifest)

    def test_compressed_artifact_roundtrip_and_source_hash_changes(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'docs').mkdir();(root/'docs/learning-campaign.md').write_text('protocol')
            (root/'lightlag_learning').mkdir();p=root/'lightlag_learning/a.py';p.write_text('x=1')
            before=c.sources(root);p.write_text('x=2')
            self.assertNotEqual(before,c.sources(root))
            c.save(root/'case.json.gz',{'seed':1,'reward':.2})
            self.assertEqual(c.read(root/'case.json.gz'),{'seed':1,'reward':.2})

    def test_used_seed_worker_binds_public_choices_and_loaded_source(self):
        root=Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);(folder/'cases').mkdir()
            version={'root':str(root),'source_sha256':c.sources(root)}
            manifest={'schema':'learning-compatibility-freeze-v1','versions':{'old':version,'new':version},
                      'arms':[{'id':'greedy','algorithm':'greedy'}],'maps':[1,2],'smoke':True,
                      'script_sha256':c.digest(c.SCRIPT),'python':platform.python_version()}
            c.save(folder/'freeze.json',manifest)
            result=subprocess.run([sys.executable,str(c.SCRIPT),'--worker',str(folder/'freeze.json'),
                                   '--index','0'],capture_output=True,text=True,cwd='/tmp')
            self.assertEqual(result.returncode,0,result.stderr)
            bundle=c.read(folder/'cases/000.json.gz')
            self.assertTrue(all(bundle['audit'].values()))
            self.assertEqual(bundle['episode']['result']['tick'],420)
            proof=bundle['loaded_modules']['lightlag_traverse.pilot']
            self.assertEqual(proof['path'],str(root/'lightlag_traverse/pilot.py'))
            self.assertEqual(proof['sha256'],version['source_sha256']['lightlag_traverse/pilot.py'])


if __name__=='__main__':unittest.main()
