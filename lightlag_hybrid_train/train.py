"""Fresh, bounded greedy-prior/plain PPO runs; old checkpoints are never resumed."""

import argparse
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import gzip
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import platform
import time

import numpy as np
import torch

from lightlag_learning.environment import CANDIDATE_FEATURES, GLOBAL_FEATURES, run_episode
from lightlag_hybrid_train.learner import Learner, chooser_from_state

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = 'learning-hybrid-training-20261115'
TRAIN_MAPS = tuple(range(620000, 622048))
VALIDATION_MAPS = tuple(range(628000, 628064))
FINAL_MAPS = tuple(range(629000, 629128))
MILESTONES = (0, 512, 2048, 4096)
BATCH = 32
ABSOLUTE_DEADLINE = datetime(2026, 11, 15, 5, 30, tzinfo=timezone.utc).timestamp()
RATE = 8*.0000131 + 16*.00000222
PACKAGES = ('lightlag_learning', 'lightlag_traverse', 'lightlag', 'lightlag_mcp',
            'lightlag_rl', 'lightlag_rl_feasible', 'lightlag_learning_final',
            'lightlag_hybrid_train', 'tools/learning_hybrid_train')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def state_hash(value):
    return hashlib.sha256((json.dumps(value, sort_keys=True, allow_nan=False,
                                     separators=(',', ':'))+'\n').encode()).hexdigest()


def atomic_bytes(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name+'.tmp')
    with temporary.open('wb') as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def atomic_json(path, value):
    data = (json.dumps(value, sort_keys=True, allow_nan=False, separators=(',', ':'))+'\n').encode()
    if str(path).endswith('.gz'):
        data = gzip.compress(data, compresslevel=3, mtime=0)
    atomic_bytes(path, data)


def read_json(path):
    data = Path(path).read_bytes()
    return json.loads(gzip.decompress(data) if str(path).endswith('.gz') else data)


def source_manifest(root=None):
    root = ROOT if root is None else Path(root)
    paths = {root/'docs/learning-hybrid-training.md'}
    for package in PACKAGES:
        found = set((root/package).rglob('*.py'))
        if not found:
            raise ValueError(f'missing source package: {package}')
        paths.update(found)
    return {str(path.relative_to(root)): digest(path) for path in sorted(paths)}


source_pins = source_manifest


def assert_source(expected, root=None):
    if expected != source_manifest(root):
        raise ValueError('training source manifest changed')


def training_map(index, smoke=False):
    maps = (1, 2) if smoke else TRAIN_MAPS
    order = np.random.default_rng(20261115 + index//len(maps)).permutation(maps)
    return int(order[index % len(maps)])


def worker_init():
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)


def episode_job(job):
    policy, seed, action_seed, explore, keep_replay, deadline = job
    row = {'seed': seed, 'action_seed': action_seed, 'status': 'deadline'}
    if time.time() >= deadline:
        return row
    try:
        choose = chooser_from_state(policy, np.random.default_rng(action_seed), explore=explore)
        episode = run_episode(seed, choose, keep_replay=keep_replay)
        episode['action_seed'] = action_seed
        row.update(status='complete', episode=episode)
    except Exception as error:
        row.update(status='failed', error={'type': type(error).__name__, 'message': str(error)[:1000]})
    return row


class CollectionFailure(RuntimeError):
    def __init__(self, rows, expected, error=None):
        super().__init__('rollout collection did not complete')
        self.rows, self.expected, self.error = rows, expected, error
        incomplete = [row for row in rows if row['status'] != 'complete']
        self.deadline = error is None and len(rows) == expected and all(
            row['status'] == 'deadline' for row in incomplete)


def collect(pool, policy, maps, seed, offset=0, explore=False, keep_replay=True,
            deadline_unix=float('inf')):
    jobs = [(policy, world, seed*1_000_000_000+offset+index, explore, keep_replay, deadline_unix)
            for index, world in enumerate(maps)]
    rows = []
    try:
        for row in pool.map(episode_job, jobs, chunksize=1):
            rows.append(row)
    except Exception as error:
        raise CollectionFailure(rows, len(jobs), type(error).__name__) from error
    if any(row['status'] != 'complete' for row in rows):
        raise CollectionFailure(rows, len(jobs))
    return [row['episode'] for row in rows]


def summarize(episodes):
    return {'count': len(episodes), 'mean_reward': float(np.mean([e['reward'] for e in episodes])),
            'home': sum(e['result']['at_base'] for e in episodes),
            'alive': sum(e['result']['alive'] for e in episodes),
            'invalid_calls': sum(len(e.get('invalid_calls', [])) for e in episodes),
            'mean_decisions': float(np.mean([e.get('decision_count', 0) for e in episodes]))}


def train(variant, seed, episodes, output, workers=6, deadline_unix=None, smoke=False):
    if variant not in ('prior', 'plain') or type(workers) is not int or not 1 <= workers <= 6:
        raise ValueError('invalid variant or worker count')
    if type(episodes) is not int or (episodes != 4096 and not (smoke and episodes in (32, 64))):
        raise ValueError('target must be4096 (smoke:32 or64)')
    if type(seed) is not int or seed not in (17, 29, 43) or type(smoke) is not bool:
        raise ValueError('invalid seed or smoke flag')
    if deadline_unix is not None and (type(deadline_unix) not in (int, float)
                                     or not np.isfinite(deadline_unix)):
        raise ValueError('invalid deadline')
    pins = source_manifest()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(1)
    started, cpu_started = time.time(), time.process_time()
    deadline = min(started+10800, ABSOLUTE_DEADLINE,
                   float('inf') if deadline_unix is None else deadline_unix)
    identity = {'experiment': EXPERIMENT, 'variant': variant, 'algorithm': variant, 'seed': seed,
                'smoke': smoke, 'source_sha256': pins, 'numpy': np.__version__,
                'torch': torch.__version__, 'python': platform.python_version(),
                'batch_episodes': BATCH, 'schedule_episodes': 4096}
    learner = Learner(variant, len(CANDIDATE_FEATURES), len(GLOBAL_FEATURES), seed, total_episodes=4096)
    history, validations, checkpoints = [], {}, {}
    report = {'schema': 'hybrid-ppo-training-report-v1', **identity, 'episodes_target': episodes,
              'episodes_completed': 0, 'status': 'running', 'started_unix': started,
              'deadline_unix': deadline, 'history': history, 'validations': validations,
              'checkpoints': checkpoints, 'phase': 'initial',
              'cost_limit': '8CPU/16GiB elapsed-allocation estimate; excludes startup/build/storage/egress, not an invoice.'}

    def report_save(status='running'):
        elapsed = time.time()-started
        report.update(status=status, updated_unix=time.time(), elapsed_seconds=elapsed,
                      parent_cpu_seconds=time.process_time()-cpu_started,
                      running_compute_estimate_usd=elapsed*RATE)
        atomic_json(output/'report.json', report)

    def checkpoint_save():
        atomic_json(output/'checkpoint-latest.json.gz', {
            'schema': 'hybrid-ppo-checkpoint-v1', 'identity': identity,
            'episodes_completed': learner.episodes_seen, 'learner': learner.state_dict(), 'history': history})
        report['episodes_completed'] = learner.episodes_seen

    def retain_checkpoint():
        count = learner.episodes_seen
        policy_path = output/f'policy-{count:05d}.json'
        checkpoint_path = output/f'checkpoint-{count:05d}.json.gz'
        if policy_path.exists() or checkpoint_path.exists():
            raise FileExistsError('milestone artifacts are immutable')
        atomic_json(policy_path, learner.inference_state())
        atomic_bytes(checkpoint_path, (output/'checkpoint-latest.json.gz').read_bytes())
        checkpoints[str(count)] = {'policy_sha256': digest(policy_path),
                                   'checkpoint_sha256': digest(checkpoint_path)}
        report_save()

    def validate(pool):
        count = learner.episodes_seen
        report['phase'] = f'validation-{count:05d}'
        report_save()
        maps = (1, 2) if smoke else VALIDATION_MAPS
        policy = learner.inference_state()
        retained = collect(pool, policy, maps, seed, explore=False, deadline_unix=deadline)
        artifact = output/f'validation-{count:05d}.json.gz'
        summary = summarize(retained)
        atomic_json(artifact, {'schema': 'hybrid-ppo-validation-v1', 'experiment': EXPERIMENT,
                              'variant': variant, 'seed': seed, 'episodes_completed': count,
                              'policy_sha256': checkpoints[str(count)]['policy_sha256'],
                              'maps': list(maps), 'summary': summary, 'episodes': retained})
        validations[str(count)] = summary
        checkpoints[str(count)]['validation_sha256'] = digest(artifact)
        report_save()

    try:
        checkpoint_save()
        retain_checkpoint()
        if time.time() >= deadline:
            report_save('deadline')
            return report
        with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context('spawn'),
                                 initializer=worker_init) as pool:
            validate(pool)
            while learner.episodes_seen < episodes:
                if time.time() >= deadline:
                    report_save('deadline')
                    return report
                count = learner.episodes_seen
                report['phase'] = f'training-{count:05d}'
                report_save()
                policy = learner.inference_state()
                maps = [training_map(i, smoke) for i in range(count, count+BATCH)]
                batch = collect(pool, policy, maps, seed, offset=count, explore=True, deadline_unix=deadline)
                artifact = f'batches/batch-{count//BATCH:05d}.json.gz'
                atomic_json(output/artifact, {'schema': 'hybrid-ppo-batch-v1', 'first_episode': count,
                                             'last_episode': count+BATCH, 'policy_sha256': state_hash(policy),
                                             'episodes': batch})
                report['pending_batch'] = {'artifact': artifact, 'sha256': digest(output/artifact)}
                if time.time() >= deadline:
                    report['unapplied_batch'] = report.pop('pending_batch')
                    report_save('deadline')
                    return report
                metrics = learner.update(batch)
                if learner.episodes_seen != count+BATCH:
                    raise ValueError('learner episode counter differs from batch size')
                history.append({'first_episode': count, 'last_episode': learner.episodes_seen,
                                'artifact': artifact, 'sha256': digest(output/artifact),
                                'summary': summarize(batch), 'metrics': metrics})
                checkpoint_save()
                report.pop('pending_batch')
                report_save()
                if learner.episodes_seen in MILESTONES or learner.episodes_seen == episodes:
                    retain_checkpoint()
                    if time.time() >= deadline:
                        report_save('deadline')
                        return report
                    validate(pool)
                print(json.dumps({'variant': variant, 'seed': seed, 'episodes': learner.episodes_seen,
                                  'reward': history[-1]['summary']['mean_reward']}), flush=True)
        if time.time() >= deadline:
            report_save('deadline')
            return report
        report['phase'] = 'finished'
        report_save('complete')
    except CollectionFailure as error:
        artifact = 'interrupted-rollouts.json.gz'
        atomic_json(output/artifact, {'phase': report['phase'], 'expected': error.expected,
                                     'rows': error.rows, 'error_type': error.error})
        report['interrupted_rollouts'] = {'artifact': artifact, 'sha256': digest(output/artifact)}
        report['error_type'] = type(error).__name__
        report_save('deadline' if error.deadline else 'failed')
        if not error.deadline:
            raise
    except BaseException as error:
        # A failed optimizer/checkpoint write must not advance the durable count
        # or claim an uncommitted batch as part of checkpoint history.
        while history and history[-1]['last_episode'] > report['episodes_completed']:
            history.pop()
        report['error_type'] = type(error).__name__
        report['error_message'] = str(error)[:1000]
        report_save('failed')
        raise
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--variant', choices=('prior', 'plain'), required=True)
    parser.add_argument('--seed', type=int, required=True)
    parser.add_argument('--episodes', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=6)
    parser.add_argument('--deadline-unix', type=float)
    parser.add_argument('--smoke', action='store_true')
    report = train(**vars(parser.parse_args()))
    print(json.dumps({k: report[k] for k in ('status', 'variant', 'seed', 'episodes_completed', 'validations')}))


if __name__ == '__main__':
    main()
