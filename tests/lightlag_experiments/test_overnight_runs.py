"""Block B is preparation/export only: no provider, scheduler or Docker calls."""

import importlib.util
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
SPEC = importlib.util.find_spec("tools.lightlag_experiments.overnight_runs")
if SPEC:
    from tools.lightlag_experiments import overnight_runs as runs
else:
    runs = None


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


class OvernightRuns(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(runs, "Block B preparation/export is not implemented")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.tasks = self.root / "original-tasks"
        self.runtime = self.root / "block-b"
        self.public = self.repo / "docs/lightlag-runs/overnight-b-plan.json"
        self.aid = REPO / "tools/lightlag_experiments/ledger_aid_v1.md"
        self.repo.mkdir()
        for profile, seed in [("rush", 501), ("rush_noisy", 502), ("rush_noisy", 504)]:
            name = f"{profile}-{seed}"
            task = self.tasks / name
            task.mkdir(parents=True)
            files = {"instruction.md": b"Original public mission.\n", "task.toml": b'name = "fixture"\n',
                     "environment/simulator/rules.py": b"idle_cost = 0.5\n"}
            for filename, content in files.items():
                dest = task / filename
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(content)
            source = self.repo / "rules.py"
            source.write_bytes(files["environment/simulator/rules.py"])
            manifest = {"source_commit": runs.FROZEN_COMMIT, "source_dirty": False,
                        "settings": {"profile": profile, "seed": seed, "delay": 3, "horizon": 50,
                                     "noise_level": 1.0, "bumpiness": 0.0, "policy": "kf_mpc"},
                        "source_sha256": {"rules.py": runs.sha256(source.read_bytes())},
                        "task_sha256": {n: runs.sha256(b) for n, b in files.items()}}
            write_json(task / "experiment.json", manifest)
            reference = self.repo / "docs/lightlag-runs" / f"{profile.replace('_', '-')}-seed{seed}-delay3-kf-mpc"
            write_json(reference / "experiment.json", manifest)
        refs = [{"profile": p, "seed": s, "raw_score": v, "maximum": m, "reward": v/m,
                 "evidence": f"{p.replace('_','-')}-seed{s}-delay3-kf-mpc",
                 "task_digest": runs.task_digest(json.loads((self.tasks/f'{p}-{s}'/'experiment.json').read_text())["task_sha256"])}
                for p,s,v,m in [("rush",501,10,12),("rush_noisy",502,10,13),("rush_noisy",504,7,10)]]
        write_json(self.repo / "docs/lightlag-runs/fixed-seeds501-504-summary.json",
                   {"claim_commit": runs.FROZEN_COMMIT, "auditor_sha256": {}, "reference_runs": refs})
        self.a_summary = self.repo / "docs/lightlag-runs/overnight-a-summary.json"
        write_json(self.a_summary, {"block": "A", "n_planned": 9, "n_completed": 9,
                                  "auditor_sha256": {}, "reported_cost_usd": 3.0,
                                  "runs": [{"reported_cost_usd": 1.0, "exception": None}] * 3})

    def prepare(self):
        return runs.prepare_b(self.repo, self.tasks, self.runtime, self.public, self.aid)

    def test_prepare_preserves_originals_and_appends_only_the_exact_aid(self):
        before = {str(p.relative_to(self.tasks)): p.read_bytes() for p in self.tasks.rglob('*') if p.is_file()}
        plan = self.prepare()
        self.assertEqual(before, {str(p.relative_to(self.tasks)): p.read_bytes() for p in self.tasks.rglob('*') if p.is_file()})
        self.assertEqual([(e['condition'], e['profile'], e['seed'], e['repetition']) for e in plan['entries']], [
            ('T','rush_noisy',504,1),('C','rush_noisy',504,1),('T','rush_noisy',502,1),('C','rush_noisy',502,1),
            ('C','rush',501,1),('T','rush',501,1),('T','rush',501,2),('C','rush',501,2),
            ('C','rush_noisy',502,2),('T','rush_noisy',502,2),('C','rush_noisy',504,2),('T','rush_noisy',504,2)])
        for entry in plan['entries']:
            original = self.tasks / f"{entry['profile']}-{entry['seed']}"
            target = Path(entry['task'])
            expected = (original/'instruction.md').read_bytes() + (b'\n'+self.aid.read_bytes() if entry['condition']=='T' else b'')
            self.assertEqual((target/'instruction.md').read_bytes(), expected)
            for path in original.rglob('*'):
                if path.is_file() and path.name not in ['instruction.md','experiment.json']:
                    self.assertEqual((target/path.relative_to(original)).read_bytes(), path.read_bytes())
        public_text = self.public.read_text()
        self.assertNotIn(str(self.root), public_text)
        self.assertEqual(json.loads(public_text)['protocol_commit'], runs.PROTOCOL_COMMIT)

    def test_prepare_rejects_existing_outputs_without_touching_them(self):
        self.runtime.mkdir()
        keep = self.runtime/'unknown.txt'; keep.write_text('untouched')
        with self.assertRaises(FileExistsError): self.prepare()
        self.assertEqual(keep.read_text(),'untouched')
        self.assertFalse(self.public.exists())

    def test_prepare_rejects_tampered_task_source_or_aid_before_writing(self):
        source = self.repo/'rules.py'; source.write_text('changed')
        with self.assertRaises(ValueError): self.prepare()
        self.assertFalse(self.runtime.exists())
        source.write_text('idle_cost = 0.5\n')
        (self.tasks/'rush-501/instruction.md').write_text('changed')
        with self.assertRaises(ValueError): self.prepare()
        self.assertFalse(self.runtime.exists())

    def test_failed_and_partial_attempts_keep_costs_null_rewards_and_sanitized_evidence(self):
        plan = self.prepare()
        credentials = self.root/'private.env'; secret = 'fixture-exact-key-without-a-known-prefix'
        credentials.write_text('ANTHROPIC_API_KEY="'+secret+'"\n')
        first, second = plan['entries'][:2]
        trial = self.runtime/'jobs'/first['job']/'trial-failed'
        write_json(trial/'result.json', {'agent_result': {'cost_usd': .25},
                   'exception_info': {'exception_type': 'ProviderError', 'exception_message': 'HTTP 429 rate limit '+secret},
                   'finished_at':'2026-11-14T07:00:00+00:00'})
        (trial/'trial.log').write_text(str(credentials.resolve())+' /Users/person/private '+secret+' sk-ant-abcdefghijk\n')
        write_json(trial/'agent/opencode/private.json', {'private':secret})
        partial = self.runtime/'jobs'/second['job']/'trial-partial'
        write_json(partial/'agent/trajectory.json', {'final_metrics':{'total_cost_usd':.1}})
        write_json(partial/'config.json', {'task':{'path':str(Path(second['task']).resolve())}})
        summary = runs.export_b(self.repo, self.runtime/'plan.json', credentials,
                                self.root/'evidence', self.root/'audits', self.a_summary)
        self.assertEqual(len(summary['runs']),12)
        a,b=summary['runs'][:2]
        self.assertEqual(a['reported_cost_usd'],.25)
        self.assertEqual(b['reported_cost_usd'],.1)
        self.assertIsNone(a['reward']); self.assertIsNone(b['reward'])
        self.assertEqual(a['status'],'failed'); self.assertEqual(b['status'],'partial')
        self.assertEqual(summary['n_pending'],10)
        self.assertAlmostEqual(summary['cumulative_reported_cost_usd'],3.35)
        self.assertTrue(summary['stop_launches'])
        self.assertIn('provider_error',summary['stop_reasons'])
        self.assertEqual(summary['paired_mean_gain_bounds'],[-1.0,1.0])
        for path in (self.root/'evidence').rglob('*'):
            if path.is_file():
                text=path.read_text()
                self.assertNotIn(secret,text);self.assertNotIn('/Users/',text);self.assertNotIn(str(self.root),text)
                self.assertNotIn('sk-ant-',text)
        self.assertFalse(any((self.root/'evidence').rglob('private.json')))

    def test_unknown_cost_stops_launches_and_unknown_destinations_are_preserved(self):
        plan=self.prepare(); credentials=self.root/'private.env'; credentials.write_text('ANTHROPIC_API_KEY=fixture-key')
        entry=plan['entries'][0]; trial=self.runtime/'jobs'/entry['job']/'trial'
        write_json(trial/'result.json',{'exception_info':{'exception_type':'SetupError'},'agent_result':None})
        out=self.root/'evidence'; occupied=out/entry['evidence'];occupied.mkdir(parents=True)
        (occupied/'keep.txt').write_text('untouched')
        summary=runs.export_b(self.repo,self.runtime/'plan.json',credentials,out,self.root/'audits',self.a_summary)
        self.assertEqual(len(summary['runs']),12)
        self.assertIsNone(summary['runs'][0]['reported_cost_usd'])
        self.assertTrue(summary['stop_launches']);self.assertIn('unknown_cost',summary['stop_reasons'])
        self.assertEqual((occupied/'keep.txt').read_text(),'untouched')
        self.assertFalse((occupied/'result.json').exists())

    def test_missing_rewards_bound_the_planned_paired_mean_without_becoming_zero(self):
        plan=self.prepare()
        rows=[dict(e, reward=None, alive=None, reported_cost_usd=None, status='pending') for e in plan['entries']]
        rows[0].update(reward=.8,alive=True,status='complete')
        rows[1].update(reward=.3,alive=True,status='complete')
        summary=runs.aggregate_rows(rows)
        self.assertEqual(summary['pairs'][0]['difference'],.5)
        self.assertAlmostEqual(summary['paired_mean_gain_bounds'][0],(-5+.5)/6)
        self.assertAlmostEqual(summary['paired_mean_gain_bounds'][1],(5+.5)/6)
        self.assertIsNone(summary['paired_mean_gain'])
        self.assertEqual(summary['conditions']['T']['n_valid_reward'],1)
        self.assertEqual(summary['conditions']['T']['deaths'],0)
        self.assertEqual(summary['conditions']['T']['alive_unknown'],5)

    def test_valid_zero_reward_is_retained_and_real_replay_audits_exactly(self):
        source=REPO/'docs/lightlag-runs/rush-seed501-delay3-opus-5-5'
        files,_=runs.snapshot(source,lambda text:text)
        digest=json.loads(files['lock.json'])['task']['digest']
        info=runs.inspect_trial(files,digest)
        self.assertEqual(info['issues'],[])
        self.assertEqual(info['status'],'complete')
        self.assertEqual(info['reward'],0)
        self.assertFalse(info['alive'])
        destination=self.root/'retained-run'
        runs.save_owned(destination,files,{'plan_id':'test','job':'test','attempt':1})
        audit=runs.audit_evidence(destination,self.root/'audits',10,0)
        self.assertTrue(audit['replay_matches'])
        self.assertTrue(audit['decomposition']['adds_up'])

    def test_malformed_result_shape_does_not_hide_trajectory_cost(self):
        files={'result.json':json.dumps({'agent_result':'malformed','exception_info':{'exception_type':'SetupError'}}),
               'agent/trajectory.json':json.dumps({'final_metrics':{'total_cost_usd':.125}})}
        try:
            info=runs.inspect_trial(files,'expected-digest')
        except Exception as error:
            self.fail('Malformed metadata hid an available cost: '+type(error).__name__)
        self.assertEqual(info['reported_cost_usd'],.125)
        self.assertIsNone(info['reward'])

    def test_launcher_failure_without_a_trial_is_an_attempt_not_a_pending_row(self):
        plan=self.prepare();credentials=self.root/'private.env';credentials.write_text('ANTHROPIC_API_KEY=fixture-key')
        entry=plan['entries'][0]
        (self.runtime/(entry['job']+'.log')).write_text('ProviderError: HTTP 401 authentication failed\n')
        summary=runs.export_b(self.repo,self.runtime/'plan.json',credentials,self.root/'evidence',self.root/'audits',self.a_summary)
        self.assertEqual(summary['n_attempted'],1)
        self.assertEqual(summary['n_pending'],11)
        self.assertIsNone(summary['runs'][0]['reward'])
        self.assertIsNone(summary['runs'][0]['reported_cost_usd'])
        self.assertTrue(summary['runs'][0]['provider_error'])
        self.assertTrue((self.root/'evidence'/entry['evidence']/'trial.log').exists())

    def test_unplanned_prompt_additions_invalidate_condition_but_keep_cost(self):
        source=REPO/'docs/lightlag-runs/rush-seed501-delay3-opus-5-5'
        files,_=runs.snapshot(source,lambda text:text)
        trial=json.loads(files['result.json'])
        trial['config']['extra_instructions']=['Unplanned additional advice']
        files['result.json']=json.dumps(trial)
        info=runs.inspect_trial(files,json.loads(files['lock.json'])['task']['digest'])
        self.assertIsNone(info['reward'])
        self.assertEqual(info['reported_cost_usd'],trial['agent_result']['cost_usd'])

    def test_manifest_integrity_failure_stops_launches_even_with_known_cost(self):
        plan=self.prepare();credentials=self.root/'private.env';credentials.write_text('ANTHROPIC_API_KEY=fixture-key')
        entry=plan['entries'][0]
        (Path(entry['task'])/'instruction.md').write_text('Unexpected task mutation')
        trial=self.runtime/'jobs'/entry['job']/'trial'
        write_json(trial/'result.json',{'agent_result':{'cost_usd':.2},
                   'exception_info':{'exception_type':'SetupError'},'finished_at':'2026-11-14T07:00:00+00:00'})
        summary=runs.export_b(self.repo,self.runtime/'plan.json',credentials,self.root/'evidence',self.root/'audits',self.a_summary)
        self.assertEqual(summary['runs'][0]['reported_cost_usd'],.2)
        self.assertIsNone(summary['runs'][0]['reward'])
        self.assertFalse(summary['runs'][0]['provider_error'])
        self.assertTrue(summary['stop_launches'])
        self.assertIn('trial_integrity_failure',summary['stop_reasons'])

    def test_dropped_pair_fails_before_overwriting_outputs_or_omitting_its_cost(self):
        plan=self.prepare();credentials=self.root/'private.env';credentials.write_text('ANTHROPIC_API_KEY=fixture-key')
        first=plan['entries'][0]
        trial=self.runtime/'jobs'/first['job']/'trial'
        write_json(trial/'result.json',{'agent_result':{'cost_usd':.25},'exception_info':{'exception_type':'SetupError'}})
        raw_before=(trial/'result.json').read_bytes()
        out=self.root/'evidence';summary_path=out/'overnight-b-summary.json'
        write_json(summary_path,{'plan_id':plan['plan_id'],'sentinel':'preserve earlier ledger'})
        before=summary_path.read_bytes()
        plan['entries']=plan['entries'][2:]
        write_json(self.runtime/'plan.json',plan)
        with self.assertRaisesRegex(ValueError,'plan'):
            runs.export_b(self.repo,self.runtime/'plan.json',credentials,out,self.root/'audits',self.a_summary)
        self.assertEqual(summary_path.read_bytes(),before)
        self.assertEqual((trial/'result.json').read_bytes(),raw_before)
        self.assertFalse((self.root/'audits').exists())

    def test_plan_hash_order_and_private_path_mutations_fail_closed(self):
        original=self.prepare();public=json.loads(self.public.read_text())
        credentials=self.root/'private.env';credentials.write_text('ANTHROPIC_API_KEY=fixture-key')
        mutations=['stale_hash','short_rehashed','reordered_rehashed','runtime_redirect','task_redirect']
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                private=copy.deepcopy(original);published=copy.deepcopy(public)
                if mutation=='stale_hash':
                    private['plan_id']=published['plan_id']='not-the-content-hash'
                elif mutation in ('short_rehashed','reordered_rehashed'):
                    if mutation=='short_rehashed':
                        private['entries']=private['entries'][2:];published['entries']=published['entries'][2:]
                    else:
                        private['entries'].reverse();published['entries'].reverse()
                    published.pop('plan_id')
                    private['plan_id']=published['plan_id']=runs.sha256(runs.json_text(published).encode())
                elif mutation=='runtime_redirect': private['runtime_root']=str(self.root/'empty-runtime')
                else: private['entries'][0]['task']=str(self.root/'other-treatment-task')
                write_json(self.runtime/'plan.json',private);write_json(self.public,published)
                destination=self.root/('evidence-'+mutation)
                with self.assertRaisesRegex(ValueError,'plan'):
                    runs.export_b(self.repo,self.runtime/'plan.json',credentials,destination,self.root/'audits',self.a_summary)
                self.assertFalse(destination.exists())

    def test_unexpected_attempt_audits_from_distinct_assignments_do_not_collide(self):
        sources=[('assignment-one','rush-seed501-delay3-opus-5-5',0),
                 ('assignment-two','overnight-a04-rush-seed501-r2-opus-5-5',10)]
        audit_root=self.root/'audits'
        for assignment,source_name,score in sources:
            files,_=runs.snapshot(REPO/'docs/lightlag-runs'/source_name,lambda text:text)
            destination=self.root/'evidence'/assignment/'unexpected-attempt-1'
            runs.save_owned(destination,files,{'plan_id':'test','job':assignment,'attempt':1})
            runs.audit_evidence(destination,audit_root,10,score)
        for assignment,_,score in sources:
            path=audit_root/assignment/'unexpected-attempt-1/audit.json'
            self.assertTrue(path.is_file(), 'each assignment must retain its own attempt audit')
            report=json.loads(path.read_text())
            self.assertEqual(report['score']['agent_raw'],score)
            self.assertEqual(report['run'],assignment+'/unexpected-attempt-1')
        self.assertFalse((audit_root/'unexpected-attempt-1').exists())

    def test_reused_trial_ids_and_names_fail_closed_without_discarding_cost(self):
        plan=self.prepare();credentials=self.root/'private.env';credentials.write_text('ANTHROPIC_API_KEY=fixture-key')
        a=json.loads(self.a_summary.read_text())
        a['runs'][0].update(trial_id='from-a',trial_name='name-from-a')
        write_json(self.a_summary,a)
        for index,entry in enumerate(plan['entries'][:3]):
            trial=self.runtime/'jobs'/entry['job']/'trial'
            write_json(trial/'result.json',{'id':'duplicate-b' if index<2 else 'from-a',
                       'trial_name':'duplicate-name-b' if index<2 else 'name-from-a',
                       'agent_result':{'cost_usd':.2},'exception_info':{'exception_type':'SetupError'},
                       'finished_at':'2026-11-14T07:00:00+00:00'})
        summary=runs.export_b(self.repo,self.runtime/'plan.json',credentials,self.root/'evidence',self.root/'audits',self.a_summary)
        self.assertTrue(summary['stop_launches'])
        self.assertIn('trial_integrity_failure',summary['stop_reasons'])
        self.assertAlmostEqual(summary['known_reported_cost_usd'],.6)
        for row in summary['runs'][:3]:
            self.assertEqual(row['reported_cost_usd'],.2)
            self.assertIsNone(row['reward'])
        for row in summary['runs'][:2]:
            self.assertIn('duplicate trial_id across Block B',row['issues'])
            self.assertIn('duplicate trial_name across Block B',row['issues'])
        self.assertIn('trial_id reused from Block A',summary['runs'][2]['issues'])
        self.assertIn('trial_name reused from Block A',summary['runs'][2]['issues'])

    def test_b01_cached_grade_accepts_verified_postterminal_advance_and_audits_full_trace(self):
        source=REPO/'docs/lightlag-runs/overnight-b01-t-rush-noisy-seed504-r1-opus-5-5'
        files,_=runs.snapshot(source,lambda text:text)
        before=dict(files)
        info=runs.inspect_trial(files,json.loads(files['lock.json'])['task']['digest'])
        self.assertEqual(info['issues'],[])
        self.assertEqual(info['reward'],.325)
        self.assertEqual(info['tool_calls'],25)
        self.assertEqual(info['graded_call_count'],24)
        self.assertEqual(info['postterminal_count'],1)
        self.assertEqual(files,before)
        destination=self.root/'b01-regression'
        runs.save_owned(destination,files,{'plan_id':'test','job':'b01','attempt':1})
        audit=runs.audit_evidence(destination,self.root/'audits',7,3.25)
        self.assertTrue(audit['replay_matches'])
        self.assertTrue(audit['decomposition']['adds_up'])
        self.assertEqual(audit['infrastructure'],[])

    def test_postterminal_read_tools_are_verified_without_changing_the_graded_count(self):
        source=REPO/'docs/lightlag-runs/overnight-b01-t-rush-noisy-seed504-r1-opus-5-5'
        files,_=runs.snapshot(source,lambda text:text)
        transcript=[json.loads(line) for line in files['artifacts/evaluator/transcript.jsonl'].splitlines()]
        packets=len(json.loads(files['artifacts/evaluator/replay.json'])['received_telemetry'])
        for tool,summary in [('rules',{}),('map',{}),('telemetry_log',{'packets':packets})]:
            transcript.append({'n':len(transcript)+1,'tool':tool,'arguments':{},'ok':True,
                               'tick_before':50,'tick_after':50,'summary':summary})
        files['artifacts/evaluator/transcript.jsonl']='\n'.join(json.dumps(row) for row in transcript)
        info=runs.inspect_trial(files,json.loads(files['lock.json'])['task']['digest'])
        self.assertEqual(info['issues'],[])
        self.assertEqual((info['tool_calls'],info['graded_call_count'],info['postterminal_count']),(28,24,4))

    def test_trusted_finish_grades_all_calls_when_agent_stops_before_horizon(self):
        source=REPO/'docs/lightlag-runs/overnight-b01-t-rush-noisy-seed504-r1-opus-5-5'
        files,_=runs.snapshot(source,lambda text:text)
        transcript=[json.loads(line) for line in files['artifacts/evaluator/transcript.jsonl'].splitlines()][:23]
        self.assertEqual(transcript[-1]['tick_after'],45)
        files['artifacts/evaluator/transcript.jsonl']='\n'.join(json.dumps(row) for row in transcript)
        evaluation=json.loads(files['artifacts/evaluator/result.json']);evaluation['tool_calls']=23
        files['artifacts/evaluator/result.json']=json.dumps(evaluation)
        info=runs.inspect_trial(files,json.loads(files['lock.json'])['task']['digest'])
        self.assertEqual(info['issues'],[])
        self.assertEqual(info['reward'],.325)
        self.assertEqual((info['tool_calls'],info.get('graded_call_count'),info.get('postterminal_count')),(23,23,0))

    def test_grade_count_and_malformed_postterminal_suffixes_are_rejected(self):
        source=REPO/'docs/lightlag-runs/overnight-b01-t-rush-noisy-seed504-r1-opus-5-5'
        original,_=runs.snapshot(source,lambda text:text)
        for mutation in ['grade_too_early','grade_includes_suffix','extra_packets','tick_advanced',
                         'successful_uplink','duplicate_call_number','invalid_advance','failed_postterminal']:
            with self.subTest(mutation=mutation):
                files=dict(original)
                evaluation=json.loads(files['artifacts/evaluator/result.json'])
                transcript=[json.loads(line) for line in files['artifacts/evaluator/transcript.jsonl'].splitlines()]
                last=transcript[-1]
                if mutation=='grade_too_early': evaluation['tool_calls']=23
                elif mutation=='grade_includes_suffix': evaluation['tool_calls']=25
                elif mutation=='extra_packets': last['summary']['packet_ticks']=[48]
                elif mutation=='tick_advanced': last['tick_after']=51
                elif mutation=='successful_uplink':
                    last.update(tool='uplink',arguments={'commands':[{'action':'wait'}]},summary={'execute_ticks':[]})
                elif mutation=='duplicate_call_number': last['n']=24
                elif mutation=='invalid_advance': last['arguments']['ticks']=0
                else:
                    last.update(tool='uplink',arguments={'commands':[{'action':'wait'}]},ok=False,error='episode complete')
                    last.pop('summary')
                files['artifacts/evaluator/result.json']=json.dumps(evaluation)
                files['artifacts/evaluator/transcript.jsonl']='\n'.join(json.dumps(row) for row in transcript)
                info=runs.inspect_trial(files,json.loads(files['lock.json'])['task']['digest'])
                self.assertIsNone(info['reward'])
                self.assertIn('missing, invalid or inconsistent terminal grading',info['issues'])


if __name__=='__main__': unittest.main()
