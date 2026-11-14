"""Progress collection uses only a synthetic Volume and local metadata."""

import copy
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from tools.learning_final import progress as p


def encoded(value):
    return (json.dumps(value, sort_keys=True) + "\n").encode()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded(value))


class Volume:
    def __init__(self):
        self.files, self.reads, self.listings = {}, [], []

    def iterdir(self, directory, recursive=False):
        self.listings.append(directory)
        return [SimpleNamespace(path="/"+name) for name in self.files
                if str(Path(name).parent) == directory]

    def read_file(self, name):
        self.reads.append(name)
        assert "/batches/" not in name and "report" not in name and "checkpoint" not in name
        yield self.files[name]

    def pair(self, run, milestone, score=.2):
        algorithm, seed = run.split("-")
        policy = {"schema": "lightlag-learning-policy-v1", "algorithm": algorithm,
                  "episodes_seen": milestone, "model": {"candidate_dim": 20, "global_dim": 14, "hidden": 64},
                  "config": {"gamma": 1, "schedule_episodes": 2048}}
        policy_bytes = encoded(policy)
        episodes = [{"seed": world, "action_seed": int(seed)*1_000_000_000+index,
                     "reward": score, "invalid_calls": [], "decision_count": 2,
                     "result": {"tick": 420, "alive": True, "at_base": True,
                                "max_available_value": 1, "raw_score": score}}
                    for index, world in enumerate(p.evidence.MAPS)]
        validation = {"schema": "learning-validation-v1", "episodes_completed": milestone,
                      "policy_sha256": hashlib.sha256(policy_bytes).hexdigest(),
                      "maps": p.evidence.MAPS, "episodes": episodes,
                      "summary": {"count": 32, "home": 32, "alive": 32, "invalid_calls": 0,
                                  "mean_reward": score, "mean_decisions": 2}}
        self.files[f"{run}/policy-{milestone:05d}.json"] = policy_bytes
        self.files[f"{run}/validation-{milestone:05d}.json.gz"] = gzip.compress(encoded(validation), mtime=0)


class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.monitor, self.cache = self.root/'monitor', self.root/'cache'
        self.freeze_path = self.root/'freeze.json'
        self.freeze = {"schema": "learning-final-freeze-v1", "campaign": {
            "campaign_id": p.evidence.EXPERIMENT, "deadline_unix": 2000,
            "stages": [{"name": stage, "jobs": [self.job(run, target) for run in p.RUNS]}
                       for stage, target in (("fit", 8192), ("extend", 32768))]}}
        write(self.freeze_path, self.freeze)
        self.state = {"schema": "learning-final-supervisor-v1", "campaign_id": p.evidence.EXPERIMENT,
                      "identity": {"freeze_sha256": p.evidence.digest(self.freeze_path)},
                      "stage": "fit", "status": "monitoring", "updated_unix": 199, "receipts": {}}
        self.receipt('fit', p.RUNS)
        self.volume = Volume()
        for run in p.RUNS:
            self.volume.pair(run, 0, .1)
            self.volume.pair(run, 512, .2)
            # Forbidden growing artifacts must never be downloaded.
            self.volume.files[f'{run}/report.json'] = b'live-report'
            self.volume.files[f'{run}/checkpoint-latest.json.gz'] = b'live-checkpoint'
            for first in (0, 32, 96):
                self.volume.files[f'{run}/batches/batch-{first:05d}.json.gz'] = b'never-read'

    @staticmethod
    def job(run, target):
        algorithm, seed = run.split('-')
        return dict(run_id=run, algorithm=algorithm, seed=int(seed), episodes=target)

    def receipt(self, stage, runs):
        target = 8192 if stage == 'fit' else 32768
        jobs = [self.job(run, target) for run in runs]
        receipt = {"schema": "learning-final-receipt-v1", "stage": stage, "status": "submitted",
                   "campaign_id": p.evidence.EXPERIMENT, "app_id": f'app-{stage}', "created_unix": 90,
                   "freeze_sha256": p.evidence.digest(self.freeze_path),
                   "jobs": [{**job, "call_id": stage+'-'+job['run_id']} for job in jobs],
                   "reservation": {"stage": stage, "jobs": jobs,
                                   "freeze_sha256": p.evidence.digest(self.freeze_path), "deadline_unix": 1000}}
        path = self.monitor/stage/'receipt.json'
        write(path, receipt)
        self.state['receipts'][stage] = dict(path=f'{stage}/receipt.json', sha256=p.evidence.digest(path))
        if stage == 'fit':
            self.state['identity']['fit_receipt_sha256'] = p.evidence.digest(path)
        self.state['stage'] = stage
        write(self.monitor/'state.json', self.state)
        write(self.monitor/stage/'status.json', {
            'campaign_id': p.evidence.EXPERIMENT, 'app_id': f'app-{stage}', 'stage': stage,
            'jobs': [{'run_id': job['run_id'], 'pending': True,
                      'state': {'call_id': stage+'-'+job['run_id'], 'status': 'running', 'started_unix': 100}}
                     for job in jobs]})

    def collect(self, now=200):
        return p.collect(self.freeze_path, self.monitor, self.cache, self.volume, now=now)

    def test_common_milestone_lower_bound_and_read_allowlist(self):
        self.volume.pair('ppo-17', 2048, .05)  # Latest wins even with a worse score.
        result = self.collect()
        self.assertEqual(result['schema'], 'learning-final-progress-v1')
        self.assertEqual(set(result['runs']), set(p.RUNS))
        self.assertFalse(result['errors'])
        self.assertEqual(result['runs']['ppo-17']['latest_checkpoint']['milestone'], 2048)
        self.assertEqual(result['runs']['ppo-17']['batch_episodes_at_least'], 64)
        self.assertEqual(result['runs']['ppo-17']['episodes_at_least'], 2048)
        self.assertEqual(result['algorithms']['ppo']['common_milestone'], 512)
        self.assertAlmostEqual(result['algorithms']['ppo']['mean_reward'], .2)
        rendered = p.render(result)
        self.assertIn('UTC', rendered)
        self.assertIn('EET', rendered)
        self.assertIn('not the untouched final check', rendered)
        self.assertIn('hard stage cutoff', rendered)
        self.assertEqual(len(self.volume.reads), 26)
        self.volume.reads.clear()
        later = self.collect(now=250)
        self.assertEqual(self.volume.reads, [])  # Immutable cache prevents repeat downloads.
        self.assertEqual(p.checkpoint_key(result), p.checkpoint_key(later))

    def test_bad_new_read_preserves_verified_cached_results(self):
        previous = self.collect()
        self.volume.pair('ppo-17', 2048, .3)
        self.volume.files['ppo-17/validation-02048.json.gz'] = b'transient-corrupt-read'
        current = self.collect()
        self.assertEqual(current['runs']['ppo-17']['latest_checkpoint']['milestone'], 512)
        self.assertEqual(p.checkpoint_key(previous), p.checkpoint_key(current))
        self.assertTrue(any(e['operation'] == 'checkpoint_2048' for e in current['errors']))
        self.assertFalse((self.cache/'runs/ppo-17/validation-02048.json.gz').exists())

    def test_changed_cached_checkpoint_is_not_silently_replaced(self):
        self.collect()
        path = self.cache/'runs/ppo-17/policy-00512.json'
        path.write_bytes(b'tampered')
        current = self.collect()
        self.assertEqual(current['runs']['ppo-17']['latest_checkpoint']['milestone'], 0)
        self.assertEqual(current['algorithms']['ppo']['common_milestone'], 0)
        self.assertEqual(path.read_bytes(), b'tampered')
        self.assertTrue(any(e['operation'] == 'checkpoint_512' for e in current['errors']))

    def test_receipt_tampering_rejected_before_volume_access(self):
        (self.monitor/'fit/receipt.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'receipt hash'):
            self.collect()
        self.assertEqual(self.volume.listings, [])
        self.assertFalse(self.cache.exists())

    def test_extension_retains_six_runs_and_separates_eta_from_cutoff(self):
        self.receipt('extend', [run for run in p.RUNS if run.startswith('ppo-')])
        for run in p.RUNS:
            if run.startswith('ppo-'):
                self.volume.pair(run, 8192, .3)
                self.volume.pair(run, 16384, .4)
        result = self.collect()
        self.assertEqual(len(result['runs']), 6)
        self.assertEqual(result['runs']['replay-17']['stage'], 'fit')
        self.assertEqual(result['runs']['replay-17']['target_episodes'], 8192)
        run = result['runs']['ppo-17']
        self.assertEqual(run['target_episodes'], 32768)
        self.assertEqual(run['rough_eta_seconds'], 200)
        self.assertEqual(run['rough_finish_unix'], 400)
        self.assertEqual(run['stage_cutoff_unix'], 1000)
        self.assertEqual(run['stage_seconds_remaining'], 800)
        self.assertEqual(result['algorithms']['ppo']['common_milestone'], 16384)

    def test_partial_seed_extension_rejected_and_common_key_changes_only_when_shared(self):
        first = self.collect()
        for run in ('ppo-17', 'ppo-29'):
            self.volume.pair(run, 2048, .3)
        second = self.collect()
        self.assertEqual(p.checkpoint_key(first), p.checkpoint_key(second))
        self.volume.pair('ppo-43', 2048, .3)
        third = self.collect()
        self.assertNotEqual(p.checkpoint_key(second), p.checkpoint_key(third))
        self.receipt('extend', ('ppo-17',))
        with self.assertRaisesRegex(ValueError, 'whole-method'):
            self.collect()

    def test_adopts_preverified_local_pairs_without_download(self):
        for name, data in self.volume.files.items():
            if '/policy-' in name or '/validation-' in name:
                target = self.cache/'runs'/name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
        result = self.collect()
        self.assertFalse(result['errors'])
        self.assertFalse(self.volume.reads)
        self.assertEqual(result['algorithms']['replay']['count'], 96)


if __name__ == '__main__':
    unittest.main()
