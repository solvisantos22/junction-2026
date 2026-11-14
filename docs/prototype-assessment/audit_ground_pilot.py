"""Audit six retained ground-change runs without executing model calls."""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import platform
from statistics import mean
import sys

p = argparse.ArgumentParser()
p.add_argument('--repo', type=Path, default=Path.cwd())
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
sys.path.insert(0, str(a.repo.resolve()))
from lightlag import Config
from lightlag_shift.environment import ShiftEnvironment
from lightlag_mcp.service import EpisodeService, ToolError

def norm(value):
    return json.loads(json.dumps(value, sort_keys=True))

def read(path):
    return json.loads(path.read_text())

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

report = {'python': platform.python_version(), 'audit_model_calls': 0, 'runs': [], 'pairs': [],
          'provenance_limit': 'experiment.json explicitly records post-generation task edits and stale task hashes; added shift/scenario source is absent from the frozen source manifest.'}
for seed in range(3100,3103):
    pair = {}
    for player in ('kf-mpc','opus-5-5'):
        path = a.repo / f'docs/lightlag-runs/shift-ground-seed{seed}-{player}'
        replay = read(path/'artifacts/evaluator/replay.json')
        evaluation = read(path/'artifacts/evaluator/result.json')
        details = read(path/'verifier/lightlag-details.json')
        result = read(path/'result.json')
        lock = read(path/'lock.json')
        experiment = read(path/'experiment.json')
        transcript = [json.loads(line) for line in (path/'artifacts/evaluator/transcript.jsonl').read_text().splitlines() if line.strip()]
        env = ShiftEnvironment(seed=seed, config=Config(**replay['config']), profile=replay['dynamic']['profile'], noise_level=replay['dynamic']['noise_level'])
        service = EpisodeService(seed=seed, config=Config(**replay['config']))
        service._env = env
        for index, record in enumerate(transcript,1):
            assert record['n'] == index
            try:
                service.call(record['tool'], record['arguments'])
            except ToolError:
                assert not record['ok']
            assert norm(service.transcript()[-1]) == record, (path.name,index)
        recomputed = service.finish()
        assert norm(recomputed) == evaluation, path.name
        assert norm(env.replay()) == replay, path.name
        assert replay['result'] == {k:v for k,v in evaluation.items() if k != 'tool_calls'}
        score = evaluation['raw_score']/evaluation['max_available_value']
        reward_text = (path/'verifier/reward.txt').read_text().strip()
        assert reward_text == f'{score:.6f}'
        assert result['verifier_result']['rewards']['reward'] == float(reward_text)
        assert details == {**evaluation,'reward':score}
        assert [s['tick'] for s in replay['states']] == list(range(replay['config']['max_ticks']+1))
        assert result['exception_info'] is None
        durations = result['agent_execution']
        seconds = (datetime.fromisoformat(durations['finished_at'].replace('Z','+00:00')) - datetime.fromisoformat(durations['started_at'].replace('Z','+00:00'))).total_seconds()
        row = {'run':path.name,'seed':seed,'player':player,'score':score,'raw_score':evaluation['raw_score'],
               'max_available_value':evaluation['max_available_value'],'alive':evaluation['alive'],'at_base':evaluation['at_base'],
               'full_replay_matches':True,'public_transcript_matches':True,'evaluation_and_reward_match':True,
               'public_calls':len(transcript),'graded_calls':evaluation['tool_calls'],'invalid_public_calls':sum(not r['ok'] for r in transcript),
               'recorded_trial_exception':None,'agent_execution_seconds':seconds,'agent_info':result['agent_info'],
               'reported_cost_usd':result['agent_result'].get('cost_usd'),'task_digest':lock['task']['digest'],
               'experiment_source_dirty':experiment['source_dirty'],'experiment_declares_stale_task_hashes':bool(experiment.get('hand_edit_after_generation')),
               'artifact_sha256':{f:digest(path/f) for f in ('experiment.json','lock.json','result.json','artifacts/evaluator/replay.json','artifacts/evaluator/result.json','artifacts/evaluator/transcript.jsonl','verifier/reward.txt')}}
        source_matches = []
        source_differences = []
        for name, expected in experiment['source_sha256'].items():
            current = a.repo/name
            (source_matches if current.exists() and digest(current)==expected else source_differences).append(name)
        row['declared_source_hashes_matching_current_count'] = len(source_matches)
        row['declared_source_hashes_differing_current'] = source_differences
        if player == 'opus-5-5':
            trajectory = read(path/'agent/trajectory.json')
            assert trajectory['agent']['model_name'] == 'anthropic/claude-opus-5-5'
            assert trajectory['final_metrics']['total_cost_usd'] == row['reported_cost_usd']
            row['observed_tool_functions'] = dict(Counter(t['function_name'] for step in trajectory['steps'] for t in step.get('tool_calls',[])))
            instruction = trajectory['steps'][0]['message']
            row['instruction_discloses_ground_change'] = '**The ground changes once.**' in instruction and 'ground_change' in instruction
            row['instruction_sha256'] = hashlib.sha256(instruction.encode()).hexdigest()
            row['trajectory_steps'] = len(trajectory['steps'])
        report['runs'].append(row)
        pair[player] = {'row':row,'replay':replay,'experiment':experiment}
    left,right = pair['kf-mpc'],pair['opus-5-5']
    paired = {'seed':seed,'task_digest_equal':left['row']['task_digest']==right['row']['task_digest'],
              'world_config_and_change_equal':all(left['replay'][k]==right['replay'][k] for k in ('world','config','ground_change','slip_coefficients')),
              'dynamic_parameters_equal_excluding_action_dependent_heading_errors':all(
                  ({sk:sv for sk,sv in left['replay']['dynamic'][k].items() if sk != 'heading_errors'} == {sk:sv for sk,sv in right['replay']['dynamic'][k].items() if sk != 'heading_errors'}) if k=='sensing' else left['replay']['dynamic'][k]==right['replay']['dynamic'][k] for k in left['replay']['dynamic']),
              'experiment_metadata_equal':left['experiment']==right['experiment'],
              'model_minus_reference':right['row']['score']-left['row']['score']}
    assert paired['task_digest_equal'] and paired['world_config_and_change_equal'] and paired['dynamic_parameters_equal_excluding_action_dependent_heading_errors'] and paired['experiment_metadata_equal']
    report['pairs'].append(paired)
report['means'] = {player:mean(r['score'] for r in report['runs'] if r['player']==player) for player in ('kf-mpc','opus-5-5')}
report['reported_model_cost_usd'] = sum(r['reported_cost_usd'] or 0 for r in report['runs'])
report['current_reconstruction_source_sha256'] = {name:digest(a.repo/name) for name in ('lightlag_shift/environment.py','lightlag_dynamic/manh_controllers/scenarios.py','lightlag_dynamic/environment.py','lightlag/environment.py','lightlag/model.py','lightlag_mcp/service.py')}
a.output.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'runs':len(report['runs']),'means':report['means'],'reported_model_cost_usd':report['reported_model_cost_usd'],'pairs':report['pairs']},indent=2))
