"""Compare old/new public references on previously used three-region development maps.

All four modes share each mission/episode seed. This is comparator development,
not fresh model validation. Output is new-only and retains every complete replay.
"""

from copy import deepcopy
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys
import time

from lightlag_expedition.environment import ExpeditionEnvironment
from lightlag_expedition.reference import run_policy as run_old
from lightlag_expedition.reference_v2 import run_policy as run_new

POLICIES = ('old_reference', 'new_reference', 'old_no_probe', 'new_no_probe')


class PublicTools:
    __slots__ = ('__call', 'transcript')

    def __init__(self, call):
        self.__call, self.transcript = call, []

    def _request(self, name, **arguments):
        record = {'tool': name, 'arguments': deepcopy(arguments)}
        try:
            result = self.__call(name, arguments)
        except Exception as error:
            record.update(ok=False, error={'type': type(error).__name__, 'message': str(error)})
            self.transcript.append(record)
            raise
        record.update(ok=True, result=deepcopy(result))
        self.transcript.append(record)
        return result

    def rules(self): return self._request('rules')
    def map(self): return self._request('map')
    def telemetry_log(self): return self._request('telemetry_log')
    def uplink(self, commands): return self._request('uplink', commands=commands)
    def advance(self, ticks=1): return self._request('advance', ticks=ticks)


def sources():
    root = Path(__file__).resolve().parents[1]
    paths = {Path(__file__).resolve()}
    for name, module in list(sys.modules.items()):
        if name.split('.')[0] in ('lightlag', 'lightlag_dynamic', 'lightlag_expedition'):
            path = getattr(module, '__file__', None)
            if path and Path(path).suffix == '.py': paths.add(Path(path).resolve())
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(paths)}


def run_episode(mission_seed, seed, policy):
    env = ExpeditionEnvironment(mission_seed=mission_seed, seed=seed)
    allowed = {name: getattr(env, name) for name in ('rules', 'map', 'telemetry_log', 'uplink', 'advance')}
    tools = PublicTools(lambda name, args: allowed[name](**args))
    runner = run_old if policy.startswith('old_') else run_new
    mode = 'no_probe' if policy.endswith('no_probe') else 'reference'
    started = time.monotonic()
    controller, error = None, None
    try:
        controller = runner(tools, mode)
    except Exception as failure:
        error = {'type': type(failure).__name__, 'message': str(failure)}
    evaluator_advances = []
    # Trusted evaluator closes failed/early controllers; the policy has no env handle.
    while env._tick < env.rules()['max_ticks']:
        ticks = min(5, env.rules()['max_ticks'] - env._tick)
        env.advance(ticks)
        evaluator_advances.append(ticks)
    result, replay = env.evaluate(), env.replay()
    # An independent fresh environment must reproduce every public response and grade.
    check = ExpeditionEnvironment(mission_seed=mission_seed, seed=seed)
    for record in tools.transcript:
        try:
            actual = getattr(check, record['tool'])(**record['arguments'])
        except Exception as failure:
            if record.get('ok') is not False or record['error'] != {'type': type(failure).__name__, 'message': str(failure)}:
                raise AssertionError('public error mismatch') from failure
        else:
            if record.get('ok') is False or actual != record['result']:
                raise AssertionError('public transcript mismatch')
    for ticks in evaluator_advances: check.advance(ticks)
    if check.replay() != replay or check.evaluate() != result:
        raise AssertionError('full replay/grade mismatch')
    row = {'mission_seed': mission_seed, 'seed': seed, 'policy': policy,
           'status': 'error' if error else 'completed', 'error': error,
           'raw_score': None if error else result['raw_score'],
           'normalized_score': None if error else result['raw_score'] / 20,
           'alive': result['alive'], 'at_base': result['at_base'],
           'sampled_value': result['sampled_value'], 'tool_calls': len(tools.transcript),
           'inspection_count': len(replay['expedition']['inspection_executed']),
           'elapsed_seconds': time.monotonic() - started, 'reconstruction_passed': True}
    return row, {'row': row, 'result': result, 'replay': replay,
                 'transcript': tools.transcript, 'decisions': controller.decision_log if controller else [],
                 'evaluator_advances': evaluator_advances}


def summarize(rows):
    groups = {policy: [row for row in rows if row['policy'] == policy and row['status'] == 'completed'] for policy in POLICIES}
    means = {policy: {'episodes': len(group),
                     'mean_raw_score': sum(r['raw_score'] for r in group) / len(group),
                     'mean_normalized_score': sum(r['normalized_score'] for r in group) / len(group),
                     'deaths': sum(not r['alive'] for r in group),
                     'home': sum(r['at_base'] for r in group)}
             for policy, group in groups.items() if group}
    return {'episodes': len(rows), 'policies': means,
            'errors': sum(row['status'] != 'completed' for row in rows),
            'all_completed': all(row['status'] == 'completed' for row in rows),
            'all_replays_reconstructed': all(r['reconstruction_passed'] for r in rows),
            'interpretation': 'Paired development seeds; no fresh model validation or optimality claim.'}


def run_study(output, maps=(0, 1, 2, 3), seeds=tuple(range(100, 108))):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    hashes = sources()
    config = {'maps': list(maps), 'episode_seeds': list(seeds), 'policies': POLICIES,
              'source_sha256': hashes, 'python': sys.version, 'paid_calls': 0}
    (output / 'config.json').write_text(json.dumps(config, indent=2, sort_keys=True)+'\n')
    rows = []
    with (output / 'episodes.jsonl.gz').open('wb') as raw, gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0) as compressed:
        for mission_seed in maps:
            for seed in seeds:
                for policy in POLICIES:
                    row, record = run_episode(mission_seed, seed, policy)
                    rows.append(row)
                    compressed.write((json.dumps(record, sort_keys=True, allow_nan=False)+'\n').encode())
                print(json.dumps({'completed': len(rows), 'map': mission_seed, 'seed': seed}), flush=True)
    summary = summarize(rows)
    summary['source_unchanged'] = sources() == hashes
    (output / 'rows.jsonl').write_text(''.join(json.dumps(row, sort_keys=True)+'\n' for row in rows))
    (output / 'summary.json').write_text(json.dumps(summary, indent=2, sort_keys=True)+'\n')
    manifest = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.is_file()}
    (output / 'sha256.json').write_text(json.dumps(manifest, indent=2, sort_keys=True)+'\n')
    if not summary['source_unchanged']: raise AssertionError('source changed during comparison')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run_study(args.output), indent=2, sort_keys=True))
