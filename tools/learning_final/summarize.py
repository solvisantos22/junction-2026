"""Aggregate an already audited final evaluation; never construct an environment."""

import argparse
import math
from pathlib import Path

import numpy as np

from . import evaluate as evidence

ALGORITHMS = ('ppo', 'replay')
ROLES = ('initial', 'matched2048', 'last')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def method_statistics(rows, manifest):
    """Average the three initialization scores within each map before bootstrap."""
    arms = manifest['arms']
    require(len(arms) == len({a['id'] for a in arms}), 'duplicate arm identifiers')
    runs = manifest['runs']
    identities = [(r['algorithm'], r['seed']) for r in runs]
    require(len(identities) == 6 and set(identities) == {
        (a, s) for a in ALGORITHMS for s in evidence.INITIALIZATIONS}, 'all six training runs are required')
    # This also rejects omitted, extra or duplicate arm/map cases.
    canonical = evidence.summarize(rows, manifest)
    for row in rows:
        require(math.isfinite(row['reward']) and 0 <= row['reward'] <= 1
                and type(row['home']) is bool and type(row['alive']) is bool
                and type(row['invalid_calls']) is int and row['invalid_calls'] >= 0,
                'invalid case reward or outcome counts')
    indexed = {(r['arm'], r['seed']): r for r in rows}
    scores = {a['id']: np.asarray([indexed[a['id'], m]['reward'] for m in manifest['maps']]) for a in arms}
    references = {name: canonical['arms'][name] for name in ('greedy', 'beam')}
    methods = {}
    for algorithm in ALGORITHMS:
        groups, contrasts, reference_comparisons = {}, {}, {}
        for role in ROLES:
            selected, per_seed = [], {}
            for seed in evidence.INITIALIZATIONS:
                matches = [a for a in arms if a.get('algorithm') == algorithm
                           and a.get('training_seed') == seed and role in a['roles']]
                require(len(matches) <= 1, 'multiple arms have the same method/seed/role')
                if not matches:
                    require(role == 'matched2048', 'missing initial or last policy')
                    continue
                arm = matches[0]
                training = next(r for r in runs if (r['algorithm'], r['seed']) == (algorithm, seed))
                selected.append(scores[arm['id']])
                per_seed[str(seed)] = {
                    'arm': arm['id'], 'policy_episodes': arm['episodes'],
                    'training_status': training['status'],
                    'training_episodes_completed': training['episodes_completed'],
                    'training_episodes_target': training['episodes_target'],
                    **canonical['arms'][arm['id']]}
            all_present = len(selected) == 3
            map_means = np.mean(selected, axis=0) if all_present else None
            groups[role] = {
                'all_initializations_present': all_present,
                'per_training_seed': per_seed,
                'policy_budgets_differ': len({r['policy_episodes'] for r in per_seed.values()}) > 1,
                'mean_reward': float(map_means.mean()) if all_present else None,
                'map_mean_rewards': map_means.tolist() if all_present else None,
                'n': sum(r['n'] for r in per_seed.values()),
                **{key: sum(r[key] for r in per_seed.values()) for key in ('home', 'alive', 'invalid_calls')}}
            if all_present:
                reference_comparisons[role] = {name: evidence.contrast(map_means-scores[name])
                                               for name in ('greedy', 'beam')}
        for later, earlier in (('last', 'initial'), ('last', 'matched2048'), ('matched2048', 'initial')):
            available = groups[later]['all_initializations_present'] and groups[earlier]['all_initializations_present']
            contrasts[f'{later}_minus_{earlier}'] = evidence.contrast(
                np.asarray(groups[later]['map_mean_rewards'])-np.asarray(groups[earlier]['map_mean_rewards'])) if available else None
        methods[algorithm] = {'checkpoints': groups, 'paired_map_contrasts': contrasts,
                              'paired_reference_comparisons': reference_comparisons}
    return {'methods': methods, 'references': references, 'canonical': canonical}


def summarize(report_path, audit_path):
    report_path, audit_path = Path(report_path).resolve(), Path(audit_path).resolve()
    freeze_path = report_path.parent/'freeze.json'
    report, manifest, audit = map(evidence.read_json, (report_path, freeze_path, audit_path))
    evidence.verify_manifest(manifest)
    require(manifest['smoke'] is False and report.get('schema') == 'learning-final-report-v1'
            and report.get('experiment') == evidence.EXPERIMENT
            and report.get('status') == 'complete' and report.get('complete') is True
            and report.get('smoke') is False
            and report['freeze_sha256'] == evidence.digest(freeze_path),
            'complete production report and matching freeze required')
    require(audit.get('schema') == 'learning-final-audit-v1'
            and audit.get('experiment') == evidence.EXPERIMENT and audit.get('smoke') is False
            and audit.get('report_sha256') == evidence.digest(report_path)
            and audit.get('cases_verified') == len(report['cases'])
            and audit.get('summary') == report['summary'], 'audit does not match this complete report')
    result = method_statistics(report['cases'], manifest)
    require(result.pop('canonical') == report['summary'], 'retained evaluator summary differs from case arithmetic')
    return {'schema': 'learning-final-method-summary-v1', 'experiment': evidence.EXPERIMENT,
            'provenance': {'report_sha256': evidence.digest(report_path),
                           'freeze_sha256': evidence.digest(freeze_path),
                           'audit_sha256': evidence.digest(audit_path),
                           'summarizer_sha256': evidence.digest(__file__),
                           'evaluator_sha256': evidence.digest(evidence.__file__)},
            'maps': manifest['maps'], 'unique_cases': len(report['cases']),
            'conditional_on_training_seeds': list(evidence.INITIALIZATIONS),
            'bootstrap_draws': evidence.BOOTSTRAP_DRAWS, 'bootstrap_seed': evidence.BOOTSTRAP_SEED,
            **result,
            'limit': 'Derivative of the hash-bound completed physics/choice audit; no physics rerun here. '
                     'Each paired bootstrap averages the three initialization scores per map before '
                     'resampling maps, conditional on those training seeds. Latest policy budgets may '
                     'differ. One arm may serve both latest and matched2048 roles without duplicating '
                     'evaluation cases. No checkpoint is selected by its score.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--audit', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = summarize(args.report, args.audit)
    evidence.atomic_json(args.output, result)
    print({algorithm: {role: group['mean_reward'] for role, group in method['checkpoints'].items()}
           for algorithm, method in result['methods'].items()})


if __name__ == '__main__':
    main()
