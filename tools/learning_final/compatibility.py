"""Frozen, matched old/new controller compatibility; no training or final maps."""
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import gzip
import hashlib
from importlib.metadata import version as package_version
import json
from pathlib import Path
import platform
import subprocess
import sys
import time
import traceback

PACKAGES = ('lightlag_learning', 'lightlag_traverse', 'lightlag', 'lightlag_mcp',
            'lightlag_rl', 'lightlag_rl_feasible')
MAPS = tuple(range(80000, 80008))
SEEDS = (17, 29, 43)
SCRIPT = Path(__file__).resolve()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    data = Path(path).read_bytes()
    return json.loads(gzip.decompress(data) if str(path).endswith('.gz') else data)


def save(path, value):
    path = Path(path)
    data = (json.dumps(value, sort_keys=True, allow_nan=False, separators=(',', ':'))+'\n').encode()
    if str(path).endswith('.gz'):
        data = gzip.compress(data, compresslevel=3, mtime=0)
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_bytes(data)
    temporary.replace(path)


def sources(root):
    root = Path(root)
    files = [root/'docs/learning-campaign.md']
    for package in PACKAGES:
        files.extend((root/package).rglob('*.py'))
    if any(p.is_symlink() for p in files):
        raise ValueError('source symlink')
    return {str(p.relative_to(root)): digest(p) for p in sorted(files)}


def freeze(output, old, new, runs, smoke=False):
    output, old, new, runs = map(lambda p: Path(p).resolve(), (output, old, new, runs))
    if output.exists():
        raise FileExistsError(output)
    versions = {name: {'root': str(root), 'source_sha256': sources(root)}
                for name, root in (('old', old), ('new', new))}
    arms = []
    for algorithm in ('ppo', 'replay'):
        for seed in SEEDS:
            directory = runs/f'{algorithm}-{seed}'
            policy_path, report_path = directory/'policy-02048.json', directory/'report.json'
            policy, report = read(policy_path), read(report_path)
            if (report['algorithm'] != algorithm or report['seed'] != seed
                    or report['status'] != 'complete' or report['episodes_completed'] != 2048
                    or report['source_sha256'] != versions['old']['source_sha256']
                    or policy['algorithm'] != algorithm or policy['episodes_seen'] != 2048
                    or policy['model']['candidate_dim'] != 20 or policy['model']['global_dim'] != 14):
                raise ValueError('old completed policy provenance mismatch')
            arms.append({'id': f'{algorithm}-{seed}', 'algorithm': algorithm, 'training_seed': seed,
                         'policy': policy, 'policy_path': str(policy_path), 'policy_sha256': digest(policy_path),
                         'report_path': str(report_path), 'report_sha256': digest(report_path)})
    arms.append({'id': 'greedy', 'algorithm': 'greedy'})
    manifest = {'schema': 'learning-compatibility-freeze-v1', 'versions': versions, 'arms': arms,
                'maps': [1, 2] if smoke else list(MAPS), 'smoke': smoke,
                'script_sha256': digest(SCRIPT), 'python': platform.python_version(),
                'numpy': package_version('numpy'), 'torch': package_version('torch'),
                'protocol_path': str(new/'docs/learning-final.md'),
                'protocol_sha256': digest(new/'docs/learning-final.md'),
                'created_unix': time.time(), 'policy_mode': 'deterministic argmax; explore=False',
                'gate': {'minimum_mean_new_minus_old': -.01, 'maximum_home_loss': 1,
                         'maximum_deaths': 0, 'maximum_invalid_calls': 0},
                'scope': 'Compatibility on reused training maps, not fresh generalization or learning gain.'}
    output.mkdir(parents=True)
    save(output/'freeze.json', manifest)
    return manifest


def verify(manifest):
    if (manifest['schema'] != 'learning-compatibility-freeze-v1'
            or manifest['script_sha256'] != digest(SCRIPT)
            or manifest['maps'] != ([1, 2] if manifest['smoke'] else list(MAPS))
            or manifest['python'] != platform.python_version()):
        raise ValueError('compatibility configuration/runtime changed')
    for version in manifest['versions'].values():
        if sources(version['root']) != version['source_sha256']:
            raise ValueError('source changed')
    if 'protocol_path' in manifest and digest(manifest['protocol_path']) != manifest['protocol_sha256']:
        raise ValueError('protocol changed')
    for package in ('numpy', 'torch'):
        if package in manifest and manifest[package] != package_version(package):
            raise ValueError('runtime changed')
    for arm in manifest['arms']:
        if arm['algorithm'] != 'greedy':
            if (digest(arm['policy_path']) != arm['policy_sha256']
                    or read(arm['policy_path']) != arm['policy']
                    or digest(arm['report_path']) != arm['report_sha256']):
                raise ValueError('policy/report changed')


def jobs(manifest):
    return [{'version': version, 'arm': arm['id'], 'seed': seed}
            for version in ('old', 'new') for arm in manifest['arms'] for seed in manifest['maps']]


def module_proof(root, pins):
    proof = {}
    for name, module in sorted(sys.modules.items()):
        if name.split('.')[0] not in PACKAGES or not getattr(module, '__file__', None):
            continue
        path = Path(module.__file__).resolve()
        relative = str(path.relative_to(root))
        if relative not in pins or digest(path) != pins[relative]:
            raise ValueError('loaded module differs from frozen version')
        proof[name] = {'path': str(path), 'sha256': digest(path)}
    return proof


def worker(freeze_path, index):
    """Run in a fresh interpreter; select import root before importing any project code."""
    freeze_path = Path(freeze_path).resolve()
    manifest = read(freeze_path)
    verify(manifest)
    job = jobs(manifest)[index]
    root = Path(manifest['versions'][job['version']]['root']).resolve()
    sys.path = [str(root)] + [p for p in sys.path if p and Path(p).resolve() not in
                             (SCRIPT.parents[2], SCRIPT.parent, Path.cwd())]
    import numpy as np
    import torch
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    from lightlag_learning.environment import run_episode, greedy_choice
    from lightlag_learning.learners import chooser_from_state
    from lightlag_traverse.environment import TraverseEnvironment
    arm = next(a for a in manifest['arms'] if a['id'] == job['arm'])
    def chooser():
        return greedy_choice if arm['algorithm'] == 'greedy' else chooser_from_state(
            arm['policy'], np.random.default_rng(job['seed']), explore=False)
    normal = lambda value: json.loads(json.dumps(value, allow_nan=False))
    episode = normal(run_episode(job['seed'], chooser(), keep_replay=True))
    save(freeze_path.parent/'cases'/f'{index:03d}.json.gz',
         {'schema':'learning-compatibility-case-v1', **job, 'episode':episode,
          'status':'awaiting_audit', 'freeze_sha256':digest(freeze_path)})
    env = TraverseEnvironment(job['seed'])
    rules, sent = normal(env.rules()), defaultdict(list)
    for command in episode['replay']['commands']:
        sent[command['sent_tick']].append(command)
    for tick in range(420):
        for command in sent.pop(tick, []):
            if normal(env.uplink([command['command']])) != [command]:
                raise AssertionError('command acknowledgement differs')
        env.advance(1)
    if (sent or normal(env.replay()) != episode['replay']
            or normal(env.evaluate()) != episode['result'] or episode['result']['tick'] != 420
            or episode['reward'] != episode['result']['raw_score']/episode['result']['max_available_value']):
        raise AssertionError('full physics/grade mismatch')
    select = chooser()
    for transition in episode['transitions']:
        if select(transition['obs']) != transition['action']:
            raise AssertionError('retained choice mismatch')
    reproduced = normal(run_episode(job['seed'], chooser(), keep_replay=True))
    stable = lambda run: {k: v for k, v in run.items() if k != 'seconds'}
    if stable(reproduced) != stable(episode):
        raise AssertionError('public controller binding mismatch')
    verify(manifest)
    bundle = {'schema': 'learning-compatibility-case-v1', **job, 'episode': episode, 'rules': rules,
              'freeze_sha256': digest(freeze_path), 'numpy': np.__version__, 'torch': torch.__version__,
              'loaded_modules': module_proof(root, manifest['versions'][job['version']]['source_sha256']),
              'audit': {'full_physics': True, 'retained_choices': True, 'public_controller_rerun': True}}
    save(freeze_path.parent/'cases'/f'{index:03d}.json.gz', bundle)


def summarize(rows, manifest):
    results = {}
    for algorithm in ('ppo', 'replay', 'greedy'):
        arm_ids = {a['id'] for a in manifest['arms'] if a['algorithm'] == algorithm}
        grouped = {v: [r for r in rows if r['version'] == v and r['arm'] in arm_ids] for v in ('old', 'new')}
        old, new = grouped['old'], grouped['new']
        expected = len(arm_ids)*len(manifest['maps'])
        if len(old) != expected or len(new) != expected:
            raise ValueError('incomplete matched comparison')
        stats = {v: {'mean_reward': sum(r['reward'] for r in rr)/len(rr),
                     'home': sum(r['home'] for r in rr), 'deaths': sum(not r['alive'] for r in rr),
                     'invalid_calls': sum(r['invalid_calls'] for r in rr), 'cases': len(rr)}
                 for v, rr in grouped.items()}
        gain = stats['new']['mean_reward']-stats['old']['mean_reward']
        gate = manifest['gate']
        passed = (gain >= gate['minimum_mean_new_minus_old']
                  and stats['new']['home'] >= stats['old']['home']-gate['maximum_home_loss']
                  and all(s['deaths'] <= gate['maximum_deaths'] and
                          s['invalid_calls'] <= gate['maximum_invalid_calls'] for s in stats.values()))
        results[algorithm] = {**stats, 'mean_new_minus_old': gain,
                              'gate_pass': passed if algorithm != 'greedy' else None}
    return results


def run(freeze_path, workers=4):
    freeze_path = Path(freeze_path).resolve()
    manifest = read(freeze_path)
    verify(manifest)
    if not 1 <= workers <= 4:
        raise ValueError('workers must be1–4')
    folder = freeze_path.parent
    (folder/'cases').mkdir()
    report = {'schema': 'learning-compatibility-report-v1', 'freeze_sha256': digest(freeze_path),
              'status': 'running', 'cases': [], 'failures': [], 'workers': workers, 'started_unix': time.time()}
    save(folder/'report.json', report)
    def launch(index):
        process = subprocess.run([sys.executable, str(SCRIPT), '--worker', str(freeze_path), '--index', str(index)],
                                 cwd='/tmp', capture_output=True, text=True)
        if process.returncode:
            failure = {'index': index, 'job': jobs(manifest)[index], 'returncode': process.returncode,
                       'stdout': process.stdout, 'stderr': process.stderr}
            save(folder/'cases'/f'{index:03d}-failure.json', failure)
            return failure
        bundle = read(folder/'cases'/f'{index:03d}.json.gz')
        episode, result = bundle['episode'], bundle['episode']['result']
        return {**jobs(manifest)[index], 'artifact': f'cases/{index:03d}.json.gz',
                'sha256': digest(folder/'cases'/f'{index:03d}.json.gz'), 'reward': episode['reward'],
                'home': result['at_base'], 'alive': result['alive'], 'invalid_calls': len(episode['invalid_calls'])}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending = [pool.submit(launch, i) for i in range(len(jobs(manifest)))]
        for future in as_completed(pending):
            row = future.result()
            report['failures' if 'returncode' in row else 'cases'].append(row)
            save(folder/'report.json', report)
    verify(manifest)
    if digest(freeze_path) != report['freeze_sha256']:
        raise ValueError('freeze changed')
    report['cases'].sort(key=lambda r: (r['version'], r['arm'], r['seed']))
    report['status'] = 'incomplete' if report['failures'] else 'complete'
    if not report['failures']:
        report['summary'] = summarize(report['cases'], manifest)
    report['finished_unix'] = time.time()
    save(folder/'report.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--freeze', type=Path)
    mode.add_argument('--run', type=Path)
    mode.add_argument('--worker', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--old', type=Path)
    parser.add_argument('--new', type=Path)
    parser.add_argument('--runs', type=Path)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--index', type=int)
    parser.add_argument('--smoke', action='store_true')
    args = parser.parse_args()
    if args.freeze:
        result = freeze(args.freeze, args.old, args.new, args.runs, args.smoke)
        print(json.dumps({'freeze': str(args.freeze/'freeze.json'), 'cases': len(jobs(result))}))
    elif args.run:
        result = run(args.run, args.workers)
        print(json.dumps({'status': result['status'], 'summary': result.get('summary'), 'failures': result['failures']}))
    else:
        worker(args.worker, args.index)


if __name__ == '__main__':
    main()
