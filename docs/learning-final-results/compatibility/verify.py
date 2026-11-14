"""Recheck retained compatibility hashes, identities, import proofs and paired summaries.

Run with Python from any directory; no simulator, learner, training, or network call.
Per-case physics and complete controller reproduction were performed by the pinned
evaluator during collection, and their successful audit records are checked here.
"""
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
digest = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(path):
    raw = Path(path).read_bytes()
    return json.loads(gzip.decompress(raw) if str(path).endswith('.gz') else raw)


manifest, report = read(ROOT/'freeze.json'), read(ROOT/'report.json')
assert report['status'] == 'complete' and not report['failures']
assert digest(ROOT/'freeze.json') == report['freeze_sha256']
expected = {(version, arm['id'], seed) for version in ('old', 'new')
            for arm in manifest['arms'] for seed in manifest['maps']}
assert len(expected) == 112 and manifest['maps'] == list(range(80000,80008))
seen, bundles = set(), {}
for row in report['cases']:
    key = (row['version'], row['arm'], row['seed'])
    assert key in expected and key not in seen
    seen.add(key)
    path = ROOT/row['artifact']
    assert path.resolve().is_relative_to(ROOT) and digest(path) == row['sha256']
    case = read(path)
    assert tuple(case[k] for k in ('version','arm','seed')) == key
    assert case['freeze_sha256'] == report['freeze_sha256']
    assert case['audit'] == {'full_physics':True,'retained_choices':True,'public_controller_rerun':True}
    assert case['numpy'] == manifest['numpy'] and case['torch'] == manifest['torch']
    version = manifest['versions'][key[0]]
    for proof in case['loaded_modules'].values():
        relative = str(Path(proof['path']).relative_to(version['root']))
        assert proof['sha256'] == version['source_sha256'][relative]
    for module in ('lightlag_learning.environment','lightlag_learning.learners',
                   'lightlag_learning.models','lightlag_traverse.environment',
                   'lightlag_traverse.pilot','lightlag_traverse.planning','lightlag_rl_feasible.adapter'):
        assert module in case['loaded_modules']
    episode = case['episode']; grade = episode['result']
    assert grade['tick'] == 420 and episode['seed'] == key[2]
    assert row['reward'] == episode['reward'] == grade['raw_score']/grade['max_available_value']
    assert row['home'] == grade['at_base'] and row['alive'] == grade['alive']
    assert row['invalid_calls'] == len(episode['invalid_calls'])
    bundles[key] = case
assert seen == expected
summary = {}
for algorithm in ('ppo','replay','greedy'):
    ids = {a['id'] for a in manifest['arms'] if a['algorithm']==algorithm}
    stats = {}
    for version in ('old','new'):
        rows = [r for r in report['cases'] if r['version']==version and r['arm'] in ids]
        stats[version] = {'cases':len(rows),'mean_reward':sum(r['reward'] for r in rows)/len(rows),
                          'home':sum(r['home'] for r in rows),'deaths':sum(not r['alive'] for r in rows),
                          'invalid_calls':sum(r['invalid_calls'] for r in rows)}
    gain = stats['new']['mean_reward']-stats['old']['mean_reward']
    passed = (gain >= -.01 and stats['new']['home'] >= stats['old']['home']-1
              and all(s['deaths']==s['invalid_calls']==0 for s in stats.values()))
    summary[algorithm] = {**stats,'mean_new_minus_old':gain,'gate_pass':None if algorithm=='greedy' else passed}
assert summary == report['summary']
per_policy={}
for arm in manifest['arms']:
    per_policy[arm['id']]={}
    for version in ('old','new'):
        rows=[r for r in report['cases'] if r['arm']==arm['id'] and r['version']==version]
        per_policy[arm['id']][version]={'mean_reward':sum(r['reward'] for r in rows)/len(rows),
                                      'home':sum(r['home'] for r in rows),'cases':len(rows)}
same_episode, same_rules, same_grade, same_choices = 0, 0, 0, 0
differences = []
for arm in manifest['arms']:
    for seed in manifest['maps']:
        old,new = (bundles[(v,arm['id'],seed)] for v in ('old','new'))
        stable = lambda b:{k:v for k,v in b['episode'].items() if k!='seconds'}
        same_episode += stable(old)==stable(new)
        same_rules += old['rules']==new['rules']
        old_episode,new_episode=old['episode'],new['episode']
        same_grade += old_episode['result']==new_episode['result']
        ot,nt=old_episode['transitions'],new_episode['transitions']
        same_choices += [(t['obs'],t['action']) for t in ot]==[(t['obs'],t['action']) for t in nt]
        if old_episode['replay']!=new_episode['replay']:
            oc,nc=old_episode['replay']['commands'],new_episode['replay']['commands']
            first=next(i for i,(x,y) in enumerate(zip(oc,nc)) if x!=y)
            tick=min(oc[first]['sent_tick'],nc[first]['sent_tick'])
            active=next(t for t in ot if t['obs']['tick']<=tick<t['next_obs']['tick'])
            only_terminal=(ot[:-1]==nt[:-1] and {k:v for k,v in ot[-1].items() if k!='next_obs'}
                           =={k:v for k,v in nt[-1].items() if k!='next_obs'})
            differences.append({'arm':arm['id'],'seed':seed,'first_different_command_tick':tick,
                                'active_goal':active['obs']['ids'][active['action']],
                                'only_terminal_next_observation_differs_in_transitions':only_terminal})
result = {'schema':'learning-compatibility-verification-v1',
          'freeze_sha256':digest(ROOT/'freeze.json'),'report_sha256':digest(ROOT/'report.json'),
          'verifier_sha256':digest(__file__),'unique_cases_verified':112,'matched_pairs':56,
          'pairs_with_identical_episode_excluding_elapsed_seconds':same_episode,
          'pairs_with_identical_grade':same_grade,'pairs_with_identical_decision_observations_and_actions':same_choices,
          'changed_trajectories':differences,
          'pairs_with_identical_rules':same_rules,'controller_executions_including_audit_reruns':224,
          'physics_reconstructions_during_collection':112,'summary':summary,'per_policy':per_policy,
          'limit':'Reused training maps only. No universal equivalence or fresh learning/generalization claim.'}
(ROOT/'verification.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
print(json.dumps(result,sort_keys=True))
