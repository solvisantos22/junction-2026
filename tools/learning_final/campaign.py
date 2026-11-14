"""Freeze every learned arm, then run and audit the exact submission campaign."""

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
import multiprocessing
from pathlib import Path
import time

from lightlag_learning.environment import OptionPilot, greedy_choice
from lightlag_traverse.campaign import TraverseCampaign
from lightlag_traverse.environment import MISSION
from lightlag_traverse.pilot import Pilot
from . import evaluate as e

SEEDS = (2027, 2028, 2029)
TASK = e.ROOT / "harbor/lightlag-traverse-campaign"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sources():
    pins = e.evaluation_sources()
    paths = [Path(__file__), TASK/'manifest.json', TASK/'task.toml', TASK/'instruction.md']
    for name in ('environment.py', 'surface.py', 'terrain.py', 'campaign.py'):
        copied = TASK/'environment/simulator/lightlag_traverse'/name
        require(copied.read_bytes() == (e.ROOT/'lightlag_traverse'/name).read_bytes(),
                'task simulator differs from evaluated source')
        paths.append(copied)
    for name in ('pilot.py', 'planning.py'):
        copied = TASK/'solution/lightlag_traverse'/name
        require(copied.read_bytes() == (e.ROOT/'lightlag_traverse'/name).read_bytes(),
                'task reference differs from evaluated source')
        paths.append(copied)
    for path in paths:
        pins[str(path.relative_to(e.ROOT))] = e.digest(path)
    return dict(sorted(pins.items()))


def freeze(output, policy_freeze, smoke=False):
    output = Path(output)
    if output.exists():
        raise FileExistsError(output)
    policies = e.read_json(policy_freeze)
    e.verify_manifest(policies)  # Metadata only: no world is constructed.
    require(smoke or policies['smoke'] is False, 'production requires a production policy freeze')
    task = e.read_json(TASK/'manifest.json')
    require(task['settings']['seeds'] == list(SEEDS) and task['settings']['mission'] == MISSION,
            'submission campaign settings differ from the frozen single-mission rules')
    manifest = {'schema': 'learning-submission-campaign-freeze-v1', 'experiment': e.EXPERIMENT,
                'smoke': smoke, 'seeds': [1, 2] if smoke else list(SEEDS), 'mission': deepcopy(MISSION),
                'policy_freeze_sha256': e.digest(policy_freeze),
                'policy_freeze_state_sha256': e.state_hash(policies), 'policy_freeze': policies,
                'source_sha256': sources(), 'selection': 'Every arm of the published policy freeze, unchanged.',
                'limit': 'Fixed submission-world showcase, not a fresh generalization test or a new LLM/Harbor run.'}
    verify_manifest(manifest)
    e.atomic_json(output, manifest)
    return manifest


def verify_manifest(manifest):
    require(manifest['schema'] == 'learning-submission-campaign-freeze-v1'
            and manifest['experiment'] == e.EXPERIMENT and type(manifest['smoke']) is bool
            and manifest['seeds'] == ([1, 2] if manifest['smoke'] else list(SEEDS))
            and manifest['mission'] == MISSION and manifest['source_sha256'] == sources()
            and manifest['policy_freeze_sha256'] == manifest['policy_freeze_state_sha256']
            == e.state_hash(manifest['policy_freeze']),
            'campaign freeze/source/settings changed')
    e.verify_manifest(manifest['policy_freeze'])
    require(manifest['smoke'] or manifest['policy_freeze']['smoke'] is False,
            'production cannot use smoke policies')


def evaluate_arm(job):
    arm, seeds, mission = job
    env, episodes, endings = TraverseCampaign(seeds, mission), [], []
    for number, seed in enumerate(seeds, 1):
        counts, commands, invalid = Counter(), Counter(), []

        class Tools:
            def __getattr__(self, name):
                if name not in ('rules', 'map', 'telemetry_log', 'uplink', 'advance'):
                    raise AttributeError(name)
                def call(*args):
                    counts[name] += 1
                    try:
                        result = getattr(env, name)(*args)
                    except ValueError as error:
                        invalid.append({'tool': name, 'error': str(error)})
                        raise
                    if name == 'uplink':
                        commands.update(ack['command']['action'] for ack in result)
                    return result
                return call

        tools = Tools()
        started = time.monotonic()
        if arm['kind'] == 'beam':
            pilot = Pilot(tools)
        else:
            choose = greedy_choice if arm['kind'] == 'greedy' else e.chooser_from_state(
                arm['policy'], e.np.random.default_rng(seed), explore=False)
            pilot = OptionPilot(tools, choose)
        while True:
            pilot.act()
            out = tools.advance(1)
            pilot.observe(out['packets'], out['current_tick'])
            if out['episode_complete']:
                break
        require(out['mission'] == number and out['campaign_complete'] is (number == len(seeds)),
                'campaign terminated or changed mission unexpectedly')
        endings.append({key: out[key] for key in ('mission', 'current_tick', 'episode_complete', 'campaign_complete')})
        # Evaluator-only access after the mission; the next controller never receives its grade.
        record = env.mission_records()[-1]
        result = {k: v for k, v in record['result'].items() if k not in ('mission', 'seed', 'reward')}
        reward = result['raw_score']/result['max_available_value']
        episode = {'seed': seed, 'result': result, 'reward': reward, 'replay': record['replay'],
                   'invalid_calls': invalid, 'public_calls': sum(counts.values()),
                   'calls_by_tool': dict(counts), 'commands_by_action': dict(commands),
                   'seconds': time.monotonic()-started}
        if arm['kind'] != 'beam':
            pilot.finish(reward)
            episode.update(transitions=pilot.transitions, decision_count=pilot.decision_count)
        episodes.append({'schema': 'learning-final-case-v1', 'experiment': e.EXPERIMENT,
                         'arm': arm['id'], 'seed': seed, 'action_seed': seed, 'episode': episode})
        if out['campaign_complete']:
            break
    require(len(episodes) == len(seeds) and env.complete, 'campaign did not play every mission')
    result = env.evaluate()
    return {'schema': 'learning-submission-campaign-case-v1', 'arm': arm['id'], 'seeds': list(seeds),
            'mission_endings': endings, 'missions': episodes, 'result': result, 'replay': env.replay(),
            'reward': result['raw_score']/result['max_available_value']}


def row_for(bundle, artifact, hashed):
    return {'arm': bundle['arm'], 'artifact': artifact, 'sha256': hashed, 'reward': bundle['reward'],
            'raw_score': bundle['result']['raw_score'], 'max_available_value': bundle['result']['max_available_value'],
            'missions': len(bundle['missions']),
            'home': sum(m['episode']['result']['at_base'] for m in bundle['missions']),
            'alive': sum(m['episode']['result']['alive'] for m in bundle['missions']),
            'invalid_calls': sum(len(m['episode']['invalid_calls']) for m in bundle['missions'])}


def summarize(rows, manifest):
    arms = manifest['policy_freeze']['arms']
    require(len(rows) == len(arms) and {r['arm'] for r in rows} == {a['id'] for a in arms},
            'campaign requires every frozen arm exactly once')
    indexed = {row['arm']: row for row in rows}
    methods = {}
    for algorithm in ('ppo', 'replay'):
        members = [a for a in arms if a.get('algorithm') == algorithm]
        if not members:
            continue
        methods[algorithm] = {}
        for role in ('initial', 'matched2048', 'last'):
            selected = [a for a in members if role in a['roles']]
            by_seed = {str(a['training_seed']): {'episodes': a['episodes'], **indexed[a['id']]} for a in selected}
            complete = set(by_seed) == {str(seed) for seed in e.INITIALIZATIONS}
            methods[algorithm][role] = {'per_training_seed': by_seed, 'all_initializations_present': complete,
                                       'mean_reward': sum(r['reward'] for r in by_seed.values())/3 if complete else None}
    return {'arms': indexed, 'methods': methods,
            'reference_differences': {a['id']: {ref: indexed[a['id']]['reward']-indexed[ref]['reward']
                                               for ref in ('greedy', 'beam')} for a in arms if a['kind'] == 'policy'},
            'limit': 'One fixed campaign per frozen arm. No campaign-based model selection or uncertainty/generalization claim.'}


def run(freeze_path, output, workers=4):
    require(type(workers) is int and 1 <= workers <= 6, 'workers must be in 1..6')
    manifest = e.read_json(freeze_path)
    verify_manifest(manifest)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output/'cases').mkdir()
    (output/'freeze.json').write_bytes(Path(freeze_path).read_bytes())
    report = {'schema': 'learning-submission-campaign-report-v1', 'freeze_sha256': e.digest(output/'freeze.json'),
              'complete': False, 'status': 'incomplete', 'smoke': manifest['smoke'], 'cases': []}
    e.atomic_json(output/'report.json', report)
    jobs = [(arm, manifest['seeds'], manifest['mission']) for arm in manifest['policy_freeze']['arms']]

    def save(bundle):
        artifact = f"cases/{bundle['arm']}.json.gz"
        require(not (output/artifact).exists(), 'duplicate campaign arm')
        e.atomic_json(output/artifact, bundle)
        report['cases'].append(row_for(bundle, artifact, e.digest(output/artifact)))
        report['cases'].sort(key=lambda r: r['arm'])
        e.atomic_json(output/'report.json', report)

    try:
        if workers == 1:
            e.torch.set_num_threads(1)
            for job in jobs:
                save(evaluate_arm(job))
        else:
            with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context('spawn'),
                                     initializer=e.worker_init) as pool:
                for future in as_completed([pool.submit(evaluate_arm, job) for job in jobs]):
                    save(future.result())
        verify_manifest(manifest)
        require(e.digest(freeze_path) == report['freeze_sha256'], 'campaign freeze changed during run')
        report.update(complete=True, status='complete', summary=summarize(report['cases'], manifest))
    except BaseException as error:
        report['error_type'] = type(error).__name__
        e.atomic_json(output/'report.json', report)
        raise
    e.atomic_json(output/'report.json', report)
    return report


def audit_case(bundle, arm, manifest):
    require(bundle['schema'] == 'learning-submission-campaign-case-v1' and bundle['arm'] == arm['id']
            and bundle['seeds'] == manifest['seeds'] and len(bundle['missions']) == len(manifest['seeds']),
            'campaign case identity differs')
    env = TraverseCampaign(manifest['seeds'], manifest['mission'])
    for number, mission in enumerate(bundle['missions'], 1):
        require(mission['seed'] == manifest['seeds'][number-1], 'mission order differs')
        e.audit_case(mission, arm)
        sent = defaultdict(list)
        for command in mission['episode']['replay']['commands']:
            sent[command['sent_tick']].append(command)
        for tick in range(420):
            for command in sent.pop(tick, []):
                expected = [{**command, 'mission': number}]
                require(e.normal(env.uplink([command['command']])) == expected, 'campaign acknowledgement differs')
            out = env.advance(1)
        require(not sent and {k: out[k] for k in bundle['mission_endings'][number-1]} == bundle['mission_endings'][number-1],
                'campaign mission boundary differs')
    require(env.complete and e.normal(env.replay()) == bundle['replay']
            and e.normal(env.evaluate()) == bundle['result'], 'campaign physics or aggregation differs')
    raw = sum(m['episode']['result']['raw_score'] for m in bundle['missions'])
    available = sum(m['episode']['result']['max_available_value'] for m in bundle['missions'])
    require(bundle['reward'] == raw/available == bundle['result']['raw_score']/bundle['result']['max_available_value'],
            'campaign must aggregate sum(raw)/sum(max), not mean mission ratios')


def audit(report_path):
    if not __debug__:
        raise RuntimeError('audit requires assertions enabled')
    e.torch.set_num_threads(1)
    path = Path(report_path).resolve()
    report, manifest = e.read_json(path), e.read_json(path.parent/'freeze.json')
    verify_manifest(manifest)
    require(report['schema'] == 'learning-submission-campaign-report-v1' and report['complete'] is True
            and report['status'] == 'complete' and report['smoke'] is manifest['smoke']
            and report['freeze_sha256'] == e.digest(path.parent/'freeze.json'), 'campaign report identity differs')
    arms, seen = {a['id']: a for a in manifest['policy_freeze']['arms']}, set()
    for row in report['cases']:
        artifact = (path.parent/row['artifact']).resolve()
        require(artifact.is_relative_to(path.parent) and artifact not in seen and e.digest(artifact) == row['sha256'],
                'campaign artifact/hash differs')
        seen.add(artifact)
        bundle = e.read_json(artifact)
        require(row_for(bundle, row['artifact'], row['sha256']) == row, 'campaign row differs')
        audit_case(bundle, arms[row['arm']], manifest)
    require(summarize(report['cases'], manifest) == report['summary'], 'campaign summary differs')
    return {'schema': 'learning-submission-campaign-audit-v1', 'report_sha256': e.digest(path),
            'campaigns_verified': len(seen), 'missions_verified': len(seen)*len(manifest['seeds']),
            'smoke': manifest['smoke'], 'summary': report['summary'],
            'limit': 'Mission and campaign physics, aggregation and retained-observation choices verified; '
                     'observation generation and controller linkage remain source-pinned, not independently reconstructed.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--freeze', type=Path)
    action.add_argument('--run', type=Path)
    action.add_argument('--audit', type=Path)
    parser.add_argument('--policy-freeze', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--smoke', action='store_true')
    args = parser.parse_args()
    if args.smoke and not args.freeze:
        parser.error('--smoke belongs to --freeze only')
    if args.freeze:
        if not args.policy_freeze:
            parser.error('--freeze requires --policy-freeze')
        result = freeze(args.freeze, args.policy_freeze, args.smoke)
        print(e.json.dumps({'arms': len(result['policy_freeze']['arms']), 'seeds': result['seeds']}))
    elif args.run:
        if not args.output:
            parser.error('--run requires --output')
        result = run(args.run, args.output, args.workers)
        print(e.json.dumps({'complete': result['complete'], 'summary': result.get('summary')}))
    else:
        result = audit(args.audit)
        if args.output:
            if args.output.exists():
                raise FileExistsError(args.output)
            e.atomic_json(args.output, result)
        print(e.json.dumps(result))


if __name__ == '__main__':
    main()
