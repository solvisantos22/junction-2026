"""Fresh final-version training with atomic, resumable milestone retention."""
from __future__ import annotations
import argparse
from concurrent.futures import ProcessPoolExecutor
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
from lightlag_learning.environment import CANDIDATE_FEATURES, GLOBAL_FEATURES, greedy_choice, run_episode
from lightlag_learning.learners import Learner, chooser_from_state

ROOT = Path(__file__).resolve().parents[1]
TRAIN_MAPS = tuple(range(80000, 80512))
VALIDATION_MAPS = tuple(range(81000, 81032))
FINAL_MAPS = tuple(range(82000, 82040))
MILESTONES = (0, 512, 2048, 8192, 16384, 24576, 32768)
EXPERIMENT = 'learning-final-20261114'
BATCH = 32


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic_bytes(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_bytes(data)
    temporary.replace(path)


def atomic_json(path, value):
    path = Path(path)
    data = (json.dumps(value, sort_keys=True, allow_nan=False, separators=(',', ':')) + '\n').encode()
    if path.suffix == '.gz':
        data = gzip.compress(data, compresslevel=3, mtime=0)
    atomic_bytes(path, data)


def read_json(path):
    data = Path(path).read_bytes()
    return json.loads(gzip.decompress(data) if str(path).endswith('.gz') else data)


def source_pins():
    files = [ROOT / 'docs/learning-final.md']
    for package in ('lightlag_learning', 'lightlag_traverse', 'lightlag', 'lightlag_mcp', 'lightlag_rl', 'lightlag_rl_feasible', 'lightlag_learning_final'):
        files.extend((ROOT / package).rglob('*.py'))
    return {str(p.relative_to(ROOT)): digest(p) for p in sorted(files)}


def training_map(index, smoke=False):
    maps = (1, 2) if smoke else TRAIN_MAPS
    # Common map order for every algorithm and initialization; action RNG is separate.
    order = np.random.default_rng(20261114 + index // len(maps)).permutation(maps)
    return int(order[index % len(maps)])


def worker_init():
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)


def episode_job(job):
    policy, seed, action_seed, explore, keep_replay = job
    rng = np.random.default_rng(action_seed)
    if policy == 'greedy':
        choose = greedy_choice
    elif policy == 'beam':
        from lightlag_traverse.environment import TraverseEnvironment
        from lightlag_traverse.pilot import fly
        env = TraverseEnvironment(seed)
        started = time.monotonic()
        fly(env)
        result = env.evaluate()
        return {'seed': seed, 'result': result, 'reward': result['raw_score']/result['max_available_value'],
                'replay': env.replay(), 'seconds': time.monotonic()-started}
    else:
        choose = chooser_from_state(policy, rng, explore=explore)
    result = run_episode(seed, choose, keep_replay=keep_replay)
    result['action_seed'] = action_seed
    return result


def summarize(episodes):
    return {'count': len(episodes), 'mean_reward': float(np.mean([e['reward'] for e in episodes])),
            'home': sum(e['result']['at_base'] for e in episodes),
            'alive': sum(e['result']['alive'] for e in episodes),
            'invalid_calls': sum(len(e.get('invalid_calls', [])) for e in episodes),
            'mean_decisions': float(np.mean([e.get('decision_count', 0) for e in episodes]))}


def collect(pool, policy, maps, seed, offset=0, explore=False, keep_replay=True):
    jobs = [(policy, world, seed*1_000_000_000 + offset+i, explore, keep_replay) for i, world in enumerate(maps)]
    return list(pool.map(episode_job, jobs, chunksize=1))


def milestone(learner, output, pool, smoke):
    count = learner.episodes_seen
    policy = learner.inference_state()
    policy_path = output / f'policy-{count:05d}.json'
    validation_path = output / f'validation-{count:05d}.json.gz'
    atomic_json(policy_path, policy)
    if validation_path.exists():
        retained = read_json(validation_path)
        if retained['policy_sha256'] != digest(policy_path):
            raise ValueError('retained validation belongs to different policy')
        return retained['summary']
    maps = (1, 2) if smoke else VALIDATION_MAPS
    episodes = collect(pool, policy, maps, learner.seed, explore=False)
    summary = summarize(episodes)
    atomic_json(validation_path, {'schema':'learning-validation-v1', 'episodes_completed':count,
                                 'policy_sha256':digest(policy_path), 'maps':list(maps),
                                 'summary':summary, 'episodes':episodes})
    return summary


def train(algorithm, seed, episodes, output, workers=4, deadline_unix=None, smoke=False):
    if algorithm not in ('ppo', 'replay') or not 1 <= workers <= 6:
        raise ValueError('invalid algorithm or worker count')
    if episodes not in (8192, 32768) and not (smoke and episodes in (32, 64)):
        raise ValueError('target must be a declared milestone (smoke:32 or64)')
    if not 0 <= seed < 2**31 or (not smoke and seed not in (17, 29, 43)):
        raise ValueError('invalid seed')
    torch.set_num_threads(1)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    identity = {'experiment':EXPERIMENT, 'algorithm':algorithm, 'seed':seed, 'smoke':smoke, 'source_sha256':source_pins(),
                'numpy':np.__version__, 'torch':torch.__version__, 'python':platform.python_version(),
                'batch_episodes':BATCH, 'schedule_episodes':2048}
    latest = output / 'checkpoint-latest.json.gz'
    if latest.exists():
        checkpoint = read_json(latest)
        if checkpoint['identity'] != identity:
            raise ValueError('resume identity/source/runtime differs from checkpoint')
        learner = Learner.from_state(checkpoint['learner'])
        history, validations = checkpoint['history'], checkpoint['validations']
        cursor = 0
        for record in history:
            artifact = (output / record['artifact']).resolve()
            if (record['first_episode'] != cursor or record['last_episode'] != cursor+BATCH
                    or not artifact.is_relative_to(output.resolve()) or digest(artifact) != record['sha256']):
                raise ValueError('checkpoint history is incomplete or changed')
            cursor += BATCH
        if cursor != learner.episodes_seen:
            raise ValueError('checkpoint counter differs from retained history')
    else:
        if any(output.iterdir()):
            raise ValueError('nonempty output without a resumable checkpoint')
        learner = Learner(algorithm, len(CANDIDATE_FEATURES), len(GLOBAL_FEATURES), seed, total_episodes=2048)
        history, validations = [], {}
    if learner.episodes_seen > episodes:
        raise ValueError('cannot resume toward an earlier target')
    started = time.time()
    report = {'schema':'learning-training-report-v1', **identity, 'episodes_target':episodes,
              'episodes_completed':learner.episodes_seen, 'status':'running', 'started_unix':started,
              'deadline_unix':deadline_unix, 'history':history, 'validations':validations}
    def save(status='running', full=True):
        report.update(status=status, episodes_completed=learner.episodes_seen, updated_unix=time.time())
        if full:
            atomic_json(latest, {'schema':'learning-run-checkpoint-v1', 'identity':identity,
                                'learner':learner.state_dict(), 'history':history, 'validations':validations})
        atomic_json(output/'report.json', report)
    def retain_milestone():
        count = learner.episodes_seen
        if str(count) not in validations:
            return
        destination = output/f'checkpoint-{count:05d}.json.gz'
        if destination.exists():
            retained = read_json(destination)
            if retained['identity'] != identity or retained['learner'] != learner.state_dict():
                raise ValueError('milestone checkpoint differs from resumed state')
        else:
            atomic_bytes(destination, latest.read_bytes())
    def validate_archives():
        for retained_count in validations:
            destination = output/f'checkpoint-{int(retained_count):05d}.json.gz'
            if not destination.is_file():
                raise ValueError('completed milestone checkpoint is missing')
            retained = read_json(destination)
            if (retained['identity'] != identity
                    or retained['learner']['episodes_seen'] != int(retained_count)
                    or retained['validations'].get(retained_count) != validations[retained_count]):
                raise ValueError('completed milestone checkpoint identity differs')
    def time_left():
        return float('inf') if deadline_unix is None else deadline_unix-time.time()
    save()
    try:
        with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context('spawn'),
                                 initializer=worker_init) as pool:
            if (learner.episodes_seen in MILESTONES or learner.episodes_seen == episodes) and str(learner.episodes_seen) not in validations:
                if time_left() < 120:
                    save('deadline')
                    return report
                validations[str(learner.episodes_seen)] = milestone(learner,output,pool,smoke)
                save()
            # Recover a crash after validation was committed but before archival.
            retain_milestone()
            validate_archives()
            while learner.episodes_seen < episodes:
                # Bounded cloud wrapper enforces an absolute subprocess deadline too.
                estimate = max([h['batch_seconds'] for h in history[-4:]] or [120])
                if time_left() < max(120, estimate*1.5+30):
                    save('deadline')
                    return report
                count = learner.episodes_seen
                before = time.time()
                policy = learner.inference_state()
                maps = [training_map(i,smoke) for i in range(count,count+BATCH)]
                batch = collect(pool,policy,maps,seed,offset=count,explore=True,keep_replay=False)
                rollout_seconds = time.time()-before
                metrics = learner.update(batch)
                update_seconds = time.time()-before-rollout_seconds
                artifact = f'batches/batch-{count:05d}.json.gz'
                atomic_json(output/artifact, {'schema':'learning-batch-v1','first_episode':count,
                                             'policy':policy,'episodes':batch,'metrics':metrics})
                record = {'first_episode':count, 'last_episode':learner.episodes_seen,
                          'artifact':artifact,'sha256':digest(output/artifact),
                          'rollout_seconds':rollout_seconds,'update_seconds':update_seconds,
                          'batch_seconds':time.time()-before, **summarize(batch), **metrics}
                history.append(record)
                save()
                print(json.dumps({'algorithm':algorithm,'seed':seed,'episodes':learner.episodes_seen,
                                  'reward':record['mean_reward'],'batch_seconds':record['batch_seconds']}),flush=True)
                if learner.episodes_seen in MILESTONES or learner.episodes_seen == episodes:
                    if time_left() < 120:
                        save('deadline')
                        return report
                    validations[str(learner.episodes_seen)] = milestone(learner,output,pool,smoke)
                    save()
                    # Full replay/optimizer checkpoint only at milestones; latest replaces each batch.
                    retain_milestone()
            save('complete')
    except BaseException as error:
        report['error_type'] = type(error).__name__
        save('failed',full=False)
        raise
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--algorithm',choices=('ppo','replay'),required=True)
    parser.add_argument('--seed',type=int,required=True)
    parser.add_argument('--episodes',type=int,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--workers',type=int,default=4)
    parser.add_argument('--deadline-unix',type=float)
    parser.add_argument('--smoke',action='store_true')
    args=parser.parse_args()
    report=train(**vars(args))
    print(json.dumps({k:report[k] for k in ('status','algorithm','seed','episodes_completed','validations')}))


if __name__ == '__main__': main()
