"""Isolated hybrid rollouts and replay audits over the unchanged public navigator."""

from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import platform
import re
import time

import numpy as np
import torch

from lightlag_learning.environment import CANDIDATE_FEATURES, GLOBAL_FEATURES, run_episode
from lightlag_learning.models import batch_observations
from lightlag_traverse.environment import TraverseEnvironment
from tools.learning_final.evaluate import evaluate_job

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ('lightlag_learning', 'lightlag_traverse', 'lightlag', 'lightlag_mcp',
            'lightlag_rl', 'lightlag_rl_feasible', 'lightlag_learning_final', 'lightlag_hybrid')
REQUIRED = ('docs/learning-final.md', 'docs/learning-hybrid.md',
            'tools/learning_final/__init__.py', 'tools/learning_final/evaluate.py')
SCHEMA = 'learning-hybrid-case-v1'
STAGE_MAPS = {'smoke': (1, 2), 'development': range(610000, 610128),
              'confirmation': range(611000, 611256), 'final': range(612000, 612256)}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, allow_nan=False, separators=(',', ':')) + '\n'


def state_hash(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def source_manifest(root=ROOT):
    """Pin the executable closure without invoking the old experiment's map rules."""
    root = Path(root)
    files = {root/name for name in REQUIRED}
    for package in (*PACKAGES, 'tools/learning_hybrid'):
        sources = set((root/package).rglob('*.py'))
        require(bool(sources), f'missing source package: {package}')
        files.update(sources)
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(files)}


def assert_source(expected, root=ROOT):
    require(isinstance(expected, dict) and expected == source_manifest(root),
            'hybrid source manifest changed')


def _identity(job, policies):
    require(isinstance(job, dict) and isinstance(job.get('id'), str)
            and re.fullmatch(r'[A-Za-z0-9_-]{1,100}', job['id']) is not None,
            'invalid job identity')
    require(isinstance(job.get('stage'), str)
            and job['stage'] in STAGE_MAPS and type(job.get('seed')) is int
            and job['seed'] in STAGE_MAPS[job['stage']],
            'invalid job stage or seed')
    require(isinstance(job.get('spec'), dict) and isinstance(policies, dict),
            'missing hybrid spec or policies')
    assert_source(job.get('source_sha256'))
    return {name: state_hash(policy) for name, policy in sorted(policies.items())}


def _runtime():
    return {'python': platform.python_version(), 'numpy': np.__version__,
            'torch': torch.__version__}


def run_job(job, policies):
    """Return complete evidence or an explicit failed case, never a guessed reward.

    Source/identity errors raise before execution. Controller failures retain any
    decisions collected before failure; the unchanged runner cannot expose a
    partial simulator after an exception, so such cases have no episode.
    """
    from lightlag_hybrid.policy import make_chooser, validate_spec

    hashes = _identity(job, policies)
    job = deepcopy(job)
    started, cpu_started = time.monotonic(), time.process_time()
    bundle = {'schema': SCHEMA, 'job': job, 'policy_sha256': hashes,
              'runtime': _runtime(), 'status': 'failed', 'episode': None,
              'diagnostics': []}
    chooser = None
    try:
        validate_spec(job['spec'], policies)
        if job['spec']['kind'] == 'beam':
            # The old runner executes the exact frozen reference, not OptionPilot.
            episode = evaluate_job({'arm': {'id': job['id'], 'kind': 'beam'},
                                    'seed': job['seed'], 'action_seed': job['seed']})['episode']
        else:
            chooser = make_chooser(job['spec'], policies)
            episode = run_episode(job['seed'], chooser, keep_replay=True)
        bundle.update(status='complete', episode=episode)
    except Exception as error:
        bundle['error'] = {'type': type(error).__name__, 'message': str(error)[:1000]}
    finally:
        if chooser is not None:
            bundle['diagnostics'] = deepcopy(chooser.diagnostics)
        bundle['seconds'] = time.monotonic() - started
        bundle['cpu_seconds'] = time.process_time() - cpu_started
    # Enforce a detached, JSON-only artifact with no hidden model or RNG objects.
    return json.loads(canonical(bundle))


def row_for(bundle, audit=None):
    """Small selection-facing record; failures retain null scores, not zeroes."""
    job, episode = bundle['job'], bundle['episode']
    result = episode['result'] if episode is not None else None
    return {'id': job['id'], 'stage': job['stage'], 'seed': job['seed'],
            'spec_id': job['spec']['id'], 'group': job['spec']['group'],
            'status': bundle['status'], 'reward': episode['reward'] if episode else None,
            'home': result['at_base'] if result else None,
            'alive': result['alive'] if result else None,
            'invalid_calls': len(episode['invalid_calls']) if episode else None,
            'error': bundle.get('error'), 'audit': audit, 'case_sha256': state_hash(bundle),
            'seconds': bundle['seconds'], 'cpu_seconds': bundle['cpu_seconds']}


def _same(left, right, path='diagnostics'):
    """Exact structure/integers, close floating scores across CPU kernels."""
    if isinstance(left, float) or isinstance(right, float):
        require(type(left) in (int, float) and type(right) in (int, float)
                and math.isfinite(left) and math.isfinite(right)
                and math.isclose(left, right, rel_tol=1e-6, abs_tol=1e-6),
                f'{path} numeric mismatch')
    elif isinstance(left, dict):
        require(isinstance(right, dict) and left.keys() == right.keys(), f'{path} keys mismatch')
        for key in left:
            _same(left[key], right[key], f'{path}.{key}')
    elif isinstance(left, list):
        require(isinstance(right, list) and len(left) == len(right), f'{path} length mismatch')
        for index, (a, b) in enumerate(zip(left, right)):
            _same(a, b, f'{path}[{index}]')
    else:
        require(type(left) is type(right) and left == right, f'{path} mismatch')


def audit_job(bundle, policies, *, full_rerun=False):
    """Reconstruct official physics and every retained hybrid decision.

    With full_rerun=True, also run the public controller again and compare all
    observations, choices, calls and commands, excluding only wall/CPU timing.
    """
    from lightlag_hybrid.policy import make_chooser

    started, cpu_started = time.monotonic(), time.process_time()
    require(bundle.get('schema') == SCHEMA and bundle.get('status') == 'complete'
            and 'error' not in bundle, 'cannot audit failed or incomplete hybrid case')
    hashes = _identity(bundle['job'], policies)
    require(bundle['policy_sha256'] == hashes, 'policy hashes changed')
    require(bundle['runtime'] == _runtime(), 'audit runtime changed')
    require(all(type(bundle.get(key)) in (int, float) and math.isfinite(bundle[key])
                and bundle[key] >= 0 for key in ('seconds', 'cpu_seconds')), 'invalid timing')
    job, episode = bundle['job'], bundle['episode']
    full_rerun = bool(full_rerun or job['stage'] == 'final')
    replay = episode['replay']
    require(job['seed'] == episode['seed'] == replay['seed'], 'episode seed changed')
    env, sent = TraverseEnvironment(job['seed']), defaultdict(list)
    horizon = env.rules()['max_ticks']
    for command in replay['commands']:
        sent[command['sent_tick']].append(command)
    for tick in range(horizon):
        for command in sent.pop(tick, []):
            require(json.loads(canonical(env.uplink([command['command']]))) == [command],
                    'physics command acknowledgement changed')
        env.advance(1)
    require(not sent and json.loads(canonical(env.replay())) == replay,
            'physics replay changed')
    require(json.loads(canonical(env.evaluate())) == episode['result']
            and episode['result']['tick'] == horizon, 'official terminal result changed')
    require(episode['reward'] == episode['result']['raw_score']/episode['result']['max_available_value'],
            'official reward changed')
    require(episode['commands_by_action'] == dict(Counter(c['command']['action'] for c in replay['commands']))
            and episode['calls_by_tool']['advance'] == horizon
            and episode['public_calls'] == sum(episode['calls_by_tool'].values())
            and episode['invalid_calls'] == [], 'public call accounting changed')
    beam = job['spec']['kind'] == 'beam'
    if beam:
        require(bundle['diagnostics'] == [], 'beam must not claim learned decisions')
    else:
        chooser = make_chooser(job['spec'], policies)
        transitions = episode['transitions']
        require(transitions and len(transitions) == episode['decision_count'],
                'missing option transitions')
        require(transitions[0]['obs']['tick'] == 0
                and transitions[-1]['next_obs']['tick'] == horizon, 'transition horizon changed')
        batch_observations([t['obs'] for t in transitions] + [transitions[-1]['next_obs']],
                           len(CANDIDATE_FEATURES), len(GLOBAL_FEATURES))
        terminal = transitions[-1]['next_obs']
        require(terminal['ids'][0] == 'base'
                and terminal['mask'] == [True]+[False]*(len(terminal['ids'])-1),
                'terminal action mask changed')
        for index, transition in enumerate(transitions):
            obs, next_obs = transition['obs'], transition['next_obs']
            action = transition['action']
            require(type(action) is int and 0 <= action < len(obs['ids'])
                    and obs['mask'][action] and chooser(deepcopy(obs)) == action,
                    'hybrid action changed')
            require(type(transition['elapsed_ticks']) is int and transition['elapsed_ticks'] > 0
                    and transition['elapsed_ticks'] == next_obs['tick']-obs['tick'],
                    'option duration changed')
            last = index == len(transitions)-1
            require(transition['done'] is last
                    and transition['reward'] == (episode['reward'] if last else 0)
                    and transition['termination_reason'] in (
                        'sample_queued', 'goal_infeasible', 'return_guard', 'navigator_return', 'horizon')
                    and (transition['termination_reason'] == 'horizon') is last,
                    'transition termination or reward changed')
            if not last:
                require(next_obs == transitions[index+1]['obs'], 'transition linkage changed')
        require(sum(t['elapsed_ticks'] for t in transitions) == horizon,
                'option durations do not span mission')
        _same(bundle['diagnostics'], chooser.diagnostics)
    if full_rerun:
        rerun = run_job(job, policies)
        require(rerun['status'] == 'complete', 'full controller replay failed')
        expected = {k: v for k, v in episode.items() if k != 'seconds'}
        observed = {k: v for k, v in rerun['episode'].items() if k != 'seconds'}
        require(expected == observed, 'full controller observation/command linkage changed')
        _same(bundle['diagnostics'], rerun['diagnostics'])
    return {'schema': 'learning-hybrid-case-audit-v1', 'job_id': job['id'],
            'case_sha256': state_hash(bundle), 'physics_verified': True,
            'hybrid_choices_verified': not beam, 'full_controller_replay': full_rerun,
            'seconds': time.monotonic()-started, 'cpu_seconds': time.process_time()-cpu_started,
            'limit': ('Complete public controller replay also verified.' if full_rerun else
                      'Observation generation, controller linkage and beam planning are source-pinned.'),
            'diagnostic_float_tolerance': {'rtol': 1e-6, 'atol': 1e-6}}
