"""Freeze all campaign policies before opening final maps; retain and audit results."""

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
import multiprocessing
from pathlib import Path
import platform
import time

import numpy as np
import torch

from lightlag_learning.environment import CANDIDATE_FEATURES, GLOBAL_FEATURES, greedy_choice, run_episode
from lightlag_learning.learners import chooser_from_state
from lightlag_learning.models import batch_observations
from lightlag_learning.train import (ROOT, FINAL_MAPS, VALIDATION_MAPS, atomic_json,
                                    digest, read_json, source_pins, worker_init)
from lightlag_traverse.environment import TraverseEnvironment
from lightlag_traverse.pilot import fly

INITIALIZATIONS = (17, 29, 43)
MILESTONES = (512, 2048, 8192, 32768)
BOOTSTRAP_DRAWS, BOOTSTRAP_SEED = 10000, 17


def state_hash(value):
    return hashlib.sha256((json.dumps(value, sort_keys=True, allow_nan=False,
                                     separators=(',', ':'))+'\n').encode()).hexdigest()


def evaluation_sources():
    pins = source_pins()
    for name in ('tools/learning_campaign/evaluate.py', 'tools/learning_campaign/__init__.py'):
        pins[name] = digest(ROOT/name)
    return dict(sorted(pins.items()))


def freeze(output, roots, smoke=False):
    """Read completed validation artifacts only; no simulator is constructed."""
    output = Path(output)
    if output.exists():
        raise FileExistsError(output)
    pins, records, arms, identities = source_pins(), [], [], set()
    paths = set()
    for root in map(Path, roots):
        if root.is_file(): paths.add(root.resolve())
        elif (root/'report.json').is_file(): paths.add((root/'report.json').resolve())
        else: paths.update(p.resolve() for p in root.rglob('report.json'))
    for path in sorted(paths):
        report = read_json(path)
        if report.get('schema') != 'learning-training-report-v1':
            continue
        algorithm, seed = report['algorithm'], report['seed']
        identity = (algorithm, seed)
        if (algorithm not in ('ppo', 'replay') or seed not in INITIALIZATIONS
                or identity in identities or report['source_sha256'] != pins
                or report['smoke'] is not smoke
                or report['status'] not in ('complete', 'deadline', 'failed')):
            raise ValueError('training identity, source, completion status or duplicate run mismatch')
        identities.add(identity)
        available = {int(k) for k in report['validations']}
        declared = (*MILESTONES, 32, 64) if smoke else MILESTONES
        last = max(available.intersection(declared), default=0)
        selected = sorted({0, last} | ({2048} if last >= 2048 else set()))
        if not set(selected).issubset(available) or report['episodes_completed'] < last:
            raise ValueError('missing initial/matched validation or incomplete milestone')
        record = {'algorithm': algorithm, 'seed': seed, 'status': report['status'],
                  'episodes_completed': report['episodes_completed'], 'last_milestone': last,
                  'no_completed_training_milestone': last == 0,
                  'report_sha256': digest(path), 'selected_artifacts': {}}
        for count in selected:
            policy_path = path.parent/f'policy-{count:05d}.json'
            validation_path = path.parent/f'validation-{count:05d}.json.gz'
            policy, validation = read_json(policy_path), read_json(validation_path)
            if (policy['algorithm'] != algorithm or policy['episodes_seen'] != count
                    or policy['model']['candidate_dim'] != len(CANDIDATE_FEATURES)
                    or policy['model']['global_dim'] != len(GLOBAL_FEATURES)
                    or state_hash(policy) != digest(policy_path)
                    or validation['schema'] != 'learning-validation-v1'
                    or validation['episodes_completed'] != count
                    or validation['policy_sha256'] != digest(policy_path)
                    or validation['maps'] != list((1, 2) if smoke else VALIDATION_MAPS)
                    or [e['seed'] for e in validation['episodes']] != validation['maps']
                    or validation['summary'] != report['validations'][str(count)]):
                raise ValueError('selected policy or validation provenance mismatch')
            chooser_from_state(policy, np.random.default_rng(0), explore=False)
            roles = (["initial"] if count == 0 else []) + (["last"] if count == last else [])
            if count == 2048: roles.append('matched2048')
            arms.append({'id': f'{algorithm}-{seed}-{count:05d}', 'kind': 'policy',
                         'algorithm': algorithm, 'training_seed': seed, 'episodes': count,
                         'roles': roles, 'policy_sha256': digest(policy_path), 'policy': policy})
            record['selected_artifacts'][policy_path.name] = digest(policy_path)
            record['selected_artifacts'][validation_path.name] = digest(validation_path)
        records.append(record)
    expected = {(a, s) for a in ('ppo', 'replay') for s in INITIALIZATIONS}
    if not identities or (not smoke and identities != expected):
        raise ValueError('production freeze requires all six declared training runs')
    arms.extend({'id': name, 'kind': name, 'roles': ['reference']} for name in ('greedy', 'beam'))
    manifest = {'schema': 'learning-final-freeze-v1', 'smoke': smoke,
                'maps': list((1, 2) if smoke else FINAL_MAPS), 'arms': arms, 'runs': records,
                'source_sha256': evaluation_sources(), 'explore': False,
                'bootstrap_draws': BOOTSTRAP_DRAWS, 'bootstrap_seed': BOOTSTRAP_SEED,
                'numpy': np.__version__, 'torch': torch.__version__, 'python': platform.python_version(),
                'selection': 'initial, last completed declared milestone, and matched2048; no score selection',
                'limit': 'Map bootstrap conditional on retained training initializations. Incomplete runs retained.'}
    atomic_json(output, manifest)
    return manifest


def verify_manifest(manifest):
    if (manifest['schema'] != 'learning-final-freeze-v1' or type(manifest['smoke']) is not bool
            or manifest['maps'] != list((1, 2) if manifest['smoke'] else FINAL_MAPS)
            or manifest['source_sha256'] != evaluation_sources() or manifest['explore'] is not False
            or manifest['bootstrap_draws'] != BOOTSTRAP_DRAWS or manifest['bootstrap_seed'] != BOOTSTRAP_SEED
            or manifest['numpy'] != np.__version__ or manifest['torch'] != torch.__version__):
        raise ValueError('frozen evaluation configuration/source/runtime changed')
    ids = [a['id'] for a in manifest['arms']]
    if len(ids) != len(set(ids)) or {'greedy', 'beam'} - set(ids):
        raise ValueError('duplicate/missing evaluation arms')
    identities = [(r['algorithm'], r['seed']) for r in manifest['runs']]
    expected_runs = {(a, s) for a in ('ppo', 'replay') for s in INITIALIZATIONS}
    if (not identities or len(identities) != len(set(identities))
            or not set(identities).issubset(expected_runs)
            or (not manifest['smoke'] and set(identities) != expected_runs)):
        raise ValueError('frozen run identities changed')
    expected_arms = {'greedy', 'beam'}
    for record in manifest['runs']:
        last = record['last_milestone']
        if last not in (0, *MILESTONES, *((32, 64) if manifest['smoke'] else ())):
            raise ValueError('undeclared final milestone')
        for count in sorted({0, last} | ({2048} if last >= 2048 else set())):
            name = f"{record['algorithm']}-{record['seed']}-{count:05d}"
            expected_arms.add(name)
            arm = next((a for a in manifest['arms'] if a['id'] == name), None)
            roles = (['initial'] if count == 0 else []) + (['last'] if count == last else [])
            if count == 2048: roles.append('matched2048')
            if (arm is None or arm['kind'] != 'policy' or arm['episodes'] != count
                    or arm['algorithm'] != record['algorithm'] or arm['training_seed'] != record['seed']
                    or arm['roles'] != roles or arm['policy']['algorithm'] != record['algorithm']
                    or arm['policy']['episodes_seen'] != count
                    or state_hash(arm['policy']) != arm['policy_sha256']):
                raise ValueError('frozen policy identity, selection or weights changed')
    if set(ids) != expected_arms or any(a['kind'] != a['id'] for a in manifest['arms'] if a['id'] in ('greedy', 'beam')):
        raise ValueError('unexpected evaluation arm')


def jobs(manifest):
    return [{'arm': arm, 'seed': seed, 'action_seed': seed} for arm in manifest['arms'] for seed in manifest['maps']]


def evaluate_job(job):
    arm, seed = job['arm'], job['seed']
    if arm['kind'] == 'beam':
        env, calls, sent, invalid = TraverseEnvironment(seed), Counter(), Counter(), []

        class Tools:
            def __getattr__(self, name):
                if name not in ('rules', 'map', 'telemetry_log', 'uplink', 'advance'):
                    raise AttributeError(name)
                def call(*args):
                    calls[name] += 1
                    try: result = getattr(env, name)(*args)
                    except ValueError as error:
                        invalid.append({'tool': name, 'error': str(error)})
                        raise
                    if name == 'uplink': sent.update(a['command']['action'] for a in result)
                    return result
                return call

        started = time.monotonic()
        fly(Tools())
        result = env.evaluate()
        episode = {'seed': seed, 'result': result, 'reward': result['raw_score']/result['max_available_value'],
                   'replay': env.replay(), 'invalid_calls': invalid, 'public_calls': sum(calls.values()),
                   'calls_by_tool': dict(calls), 'commands_by_action': dict(sent),
                   'seconds': time.monotonic()-started}
    else:
        choose = greedy_choice if arm['kind'] == 'greedy' else chooser_from_state(
            arm['policy'], np.random.default_rng(job['action_seed']), explore=False)
        episode = run_episode(seed, choose, keep_replay=True)
    return {'schema': 'learning-final-case-v1', 'arm': arm['id'], 'seed': seed,
            'action_seed': job['action_seed'], 'episode': episode}


def row_for(bundle, artifact, hashed):
    episode, result = bundle['episode'], bundle['episode']['result']
    return {'arm': bundle['arm'], 'seed': bundle['seed'], 'artifact': artifact, 'sha256': hashed,
            'reward': episode['reward'], 'home': result['at_base'], 'alive': result['alive'],
            'invalid_calls': len(episode['invalid_calls']), 'decision_count': episode.get('decision_count')}


def contrast(values):
    values = np.asarray(values, dtype=float)
    sampled = np.random.default_rng(BOOTSTRAP_SEED).choice(
        values, size=(BOOTSTRAP_DRAWS, len(values)), replace=True).mean(axis=1)
    return {'map_differences': values.tolist(), 'mean_paired_gain': float(values.mean()),
            'bootstrap_95_percentile': np.quantile(sampled, [.025, .975]).tolist()}


def summarize(rows, manifest):
    expected = {(j['arm']['id'], j['seed']) for j in jobs(manifest)}
    identities = [(r['arm'], r['seed']) for r in rows]
    if len(identities) != len(expected) or set(identities) != expected:
        raise ValueError('evaluation requires each frozen arm/map exactly once')
    indexed = {(r['arm'], r['seed']): r for r in rows}
    scores = {a['id']: np.asarray([indexed[a['id'], m]['reward'] for m in manifest['maps']]) for a in manifest['arms']}
    arms = {}
    for arm in manifest['arms']:
        subset = [indexed[arm['id'], m] for m in manifest['maps']]
        arms[arm['id']] = {'n': len(subset), 'mean_reward': float(scores[arm['id']].mean()),
                           'home': sum(r['home'] for r in subset), 'alive': sum(r['alive'] for r in subset),
                           'invalid_calls': sum(r['invalid_calls'] for r in subset)}
    learning = {}
    for algorithm in ('ppo', 'replay'):
        seeds = sorted({a['training_seed'] for a in manifest['arms'] if a.get('algorithm') == algorithm})
        if not seeds: continue
        learning[algorithm] = {}
        for role in ('last', 'matched2048'):
            selected, per_seed = [], {}
            for seed in seeds:
                eligible = [a for a in manifest['arms'] if a.get('algorithm') == algorithm and a.get('training_seed') == seed]
                initial = next(a for a in eligible if 'initial' in a['roles'])
                final = next((a for a in eligible if role in a['roles']), None)
                if final is None: continue
                delta = scores[final['id']] - scores[initial['id']]
                selected.append(delta)
                per_seed[str(seed)] = {'episodes': final['episodes'], **contrast(delta)}
            learning[algorithm][role] = {'per_training_seed': per_seed,
                'all_initializations_present': len(selected) == len(seeds),
                'conditional_on_training_seeds': list(map(int, per_seed)),
                'across_seed_map_average': contrast(np.mean(selected, axis=0)) if len(selected) == len(seeds) else None}
    references = {a['id']: {ref: contrast(scores[a['id']]-scores[ref]) for ref in ('greedy', 'beam')}
                  for a in manifest['arms'] if a['kind'] == 'policy'}
    return {'arms': arms, 'learning': learning, 'reference_comparisons': references,
            'map_order': manifest['maps'], 'bootstrap_draws': BOOTSTRAP_DRAWS, 'bootstrap_seed': BOOTSTRAP_SEED,
            'limit': 'Maps are the bootstrap units, conditional on retained training seeds; later budgets may differ.'}


def run(freeze_path, output, workers=4):
    if type(workers) is not int or not 1 <= workers <= 14:
        raise ValueError('workers must be an integer in 1..14')
    manifest = read_json(freeze_path)
    verify_manifest(manifest)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output/'cases').mkdir()
    (output/'freeze.json').write_bytes(Path(freeze_path).read_bytes())
    report = {'schema': 'learning-final-report-v1', 'freeze_sha256': digest(output/'freeze.json'),
              'status': 'incomplete', 'complete': False, 'smoke': manifest['smoke'], 'cases': []}
    atomic_json(output/'report.json', report)

    def save(bundle, job):
        episode = bundle['episode']
        if (bundle['arm'] != job['arm']['id'] or bundle['seed'] != job['seed']
                or bundle['action_seed'] != job['action_seed'] or episode['seed'] != job['seed']
                or episode['result']['tick'] != 420 or not np.isfinite(episode['reward'])
                or not 0 <= episode['reward'] <= 1):
            raise ValueError('worker returned an inconsistent or incomplete case')
        name = f"cases/{bundle['arm']}-{bundle['seed']}.json.gz"
        if (output/name).exists(): raise ValueError('duplicate case artifact')
        atomic_json(output/name, bundle)
        report['cases'].append(row_for(bundle, name, digest(output/name)))
        report['cases'].sort(key=lambda r: (r['arm'], r['seed']))
        atomic_json(output/'report.json', report)

    try:
        if workers == 1:
            torch.set_num_threads(1)
            for job in jobs(manifest): save(evaluate_job(job), job)
        else:
            with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context('spawn'),
                                     initializer=worker_init) as pool:
                futures = {pool.submit(evaluate_job, job): job for job in jobs(manifest)}
                for future in as_completed(futures): save(future.result(), futures[future])
        verify_manifest(manifest)
        if digest(freeze_path) != report['freeze_sha256']:
            raise ValueError('freeze file changed while evaluating')
        report.update(summary=summarize(report['cases'], manifest), status='complete', complete=True)
        atomic_json(output/'report.json', report)
    except BaseException as error:
        report['error_type'] = type(error).__name__
        atomic_json(output/'report.json', report)
        raise
    return report


def normal(value): return json.loads(json.dumps(value, allow_nan=False))


def audit_case(bundle, arm):
    if not __debug__: raise RuntimeError('audit requires assertions enabled')
    episode, replay = bundle['episode'], bundle['episode']['replay']
    assert bundle['schema'] == 'learning-final-case-v1' and bundle['arm'] == arm['id']
    assert bundle['seed'] == episode['seed'] == replay['seed'] == bundle['action_seed']
    env, sent = TraverseEnvironment(bundle['seed']), defaultdict(list)
    for command in replay['commands']: sent[command['sent_tick']].append(command)
    for tick in range(420):
        for command in sent.pop(tick, []): assert normal(env.uplink([command['command']])) == [command]
        env.advance(1)
    assert not sent and normal(env.replay()) == replay
    assert normal(env.evaluate()) == episode['result'] and episode['result']['tick'] == 420
    assert episode['reward'] == episode['result']['raw_score']/episode['result']['max_available_value']
    assert episode['commands_by_action'] == dict(Counter(c['command']['action'] for c in replay['commands']))
    assert episode['calls_by_tool']['advance'] == 420
    assert episode['public_calls'] == sum(episode['calls_by_tool'].values())
    if arm['kind'] != 'beam':
        choose = greedy_choice if arm['kind'] == 'greedy' else chooser_from_state(
            arm['policy'], np.random.default_rng(bundle['action_seed']), explore=False)
        transitions = episode['transitions']
        assert len(transitions) == episode['decision_count'] and transitions
        assert transitions[0]['obs']['tick'] == 0 and transitions[-1]['next_obs']['tick'] == 420
        batch_observations([t['obs'] for t in transitions] + [transitions[-1]['next_obs']],
                           len(CANDIDATE_FEATURES), len(GLOBAL_FEATURES))
        terminal = transitions[-1]['next_obs']
        assert terminal['ids'][0] == 'base' and terminal['mask'] == [True]+[False]*(len(terminal['ids'])-1)
        for i, transition in enumerate(transitions):
            obs, next_obs = transition['obs'], transition['next_obs']
            assert type(transition['action']) is int and choose(obs) == transition['action']
            assert obs['mask'][transition['action']]
            assert type(transition['elapsed_ticks']) is int and transition['elapsed_ticks'] > 0
            assert transition['elapsed_ticks'] == next_obs['tick'] - obs['tick']
            assert transition['done'] is (i == len(transitions)-1)
            assert transition['reward'] == (episode['reward'] if transition['done'] else 0)
            assert transition['termination_reason'] in ('sample_queued', 'goal_infeasible', 'return_guard', 'navigator_return', 'horizon')
            assert (transition['termination_reason'] == 'horizon') is transition['done']
            if not transition['done']: assert next_obs == transitions[i+1]['obs']
        assert sum(t['elapsed_ticks'] for t in transitions) == 420
    return {'physics_verified': True, 'policy_choices_verified': arm['kind'] != 'beam'}


def audit(path):
    if not __debug__: raise RuntimeError('audit requires assertions enabled; do not use Python -O')
    path = Path(path).resolve()
    report, manifest = read_json(path), read_json(path.parent/'freeze.json')
    verify_manifest(manifest)
    assert report['schema'] == 'learning-final-report-v1' and report['complete'] is True and report['status'] == 'complete'
    assert report['smoke'] is manifest['smoke'] and digest(path.parent/'freeze.json') == report['freeze_sha256']
    arms, seen = {a['id']: a for a in manifest['arms']}, set()
    for row in report['cases']:
        artifact = (path.parent/row['artifact']).resolve()
        assert artifact.is_relative_to(path.parent) and artifact not in seen
        assert digest(artifact) == row['sha256']
        seen.add(artifact)
        bundle = read_json(artifact)
        assert row_for(bundle, row['artifact'], row['sha256']) == row
        audit_case(bundle, arms[row['arm']])
    assert summarize(report['cases'], manifest) == report['summary']
    return {'schema': 'learning-final-audit-v1', 'report_sha256': digest(path), 'cases_verified': len(seen),
            'smoke': manifest['smoke'], 'summary': report['summary'],
            'limit': 'Physics, grades and learned/greedy choices verified. Observation reconstruction and choice-to-command linkage are source-pinned; original beam decision logic is source-pinned.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--freeze', type=Path, help='new immutable manifest JSON; does not open maps')
    group.add_argument('--run', type=Path, help='explicitly open maps from this frozen manifest')
    group.add_argument('--audit', type=Path, help='audit a completed report and saved cases')
    parser.add_argument('--runs', nargs='+', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--smoke', action='store_true')
    args = parser.parse_args()
    if args.smoke and not args.freeze: parser.error('--smoke belongs to --freeze; execution uses its frozen maps')
    if args.freeze:
        if not args.runs: parser.error('--freeze requires --runs')
        result = freeze(args.freeze, args.runs, args.smoke)
        print(json.dumps({'freeze': str(args.freeze), 'arms': len(result['arms']), 'maps': result['maps']}))
    elif args.run:
        if not args.output: parser.error('--run requires --output')
        result = run(args.run, args.output, args.workers)
        print(json.dumps({'complete': result['complete'], 'cases': len(result['cases']), 'summary': result['summary']}))
    else:
        result = audit(args.audit)
        if args.output:
            if args.output.exists(): raise FileExistsError(args.output)
            atomic_json(args.output, result)
        print(json.dumps(result))


if __name__ == '__main__': main()
