"""Reproduce the retained four-rule comparison on already-used seeds; no model calls."""
import argparse, hashlib, json, math, statistics, subprocess, sys, time
from pathlib import Path
import numpy
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--repo',default=str(Path.cwd()))
parser.add_argument('--output',default='rule-change-reproduction.json')
args=parser.parse_args()
task_repo=Path(args.repo).resolve()
sys.path.insert(0,str(task_repo))
from lightlag import Config
from lightlag_dynamic.environment import DynamicEnvironment
from lightlag_dynamic.tools import PublicTools
from lightlag_dynamic.controllers import POLICIES
from lightlag_dynamic.manh_controllers.controllers import REGISTRY, number
from lightlag_shift.rule_change import RuleChangeEnvironment, KINDS
from lightlag_shift.reference import play as prepared

def digest(x):
 return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()

manh36=next(name for name in REGISTRY if number(name)==36)
policies={'prepared':prepared,'manh_36':REGISTRY[manh36]['play'],'kf_mpc':lambda tools,env: POLICIES['kf_mpc'](tools),'open_loop':lambda tools,env: POLICIES['open_loop'](tools)}
rows=[]; summaries=[];start=time.time()
for name,play in policies.items():
 for kind in ['none',*KINDS]:
  for seed in range(3200,3240):
   kw=dict(seed=seed,config=Config(delay_ticks=3,max_ticks=50),profile='rush_noisy')
   env=DynamicEnvironment(**kw) if kind=='none' else RuleChangeEnvironment(**kw,kind=kind)
   tools=PublicTools(env)
   play(tools,env)
   while not env.advance(5)['episode_complete']: pass
   replay=env.replay();result=env.evaluate()
   final=replay['states'][-1]
   rows.append(dict(policy=name,kind=kind,seed=seed,result=result,alive=result['alive'],home=result['alive'] and result['at_base'],final=final,public_calls=tools.calls,replay_sha256=digest(replay)))
  group=[r for r in rows if r['policy']==name and r['kind']==kind]
  summary=dict(policy=name,kind=kind,n=len(group),mean_raw=statistics.mean(r['result']['raw_score'] for r in group),mean_normalized=statistics.mean(r['result']['raw_score']/r['result']['max_available_value'] for r in group),home=sum(r['home'] for r in group),alive=sum(r['alive'] for r in group))
  summaries.append(summary);print(json.dumps(summary),flush=True)
packages=['lightlag','lightlag_dynamic','lightlag_controllers','lightlag_shift','lightlag_mcp']
files=sorted(p for package in packages for p in (task_repo/package).rglob('*.py'))
source_hashes={str(p.relative_to(task_repo)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
repo_commit=subprocess.check_output(['git','-C',str(task_repo),'rev-parse','HEAD'],text=True).strip()
checks={}
for kind in KINDS:
 env=RuleChangeEnvironment(seed=3200,config=Config(delay_ticks=3,max_ticks=50),kind=kind)
 before=env.uplink([dict(action='drive',heading_deg=0,metres=1)])[0]
 for ticks in [5,5,5,5,5,5,2]:env.advance(ticks)
 after=env.uplink([dict(action='drive',heading_deg=0,metres=1)])[0]
 checks[kind]={'ack_at_tick0':before,'ack_at_tick32_open_relay_phase':after}
out=dict(purpose='Reproduce already-used forced-kind scripted table; no paid/model calls or new held-out evidence',profile='rush_noisy',delay=3,horizon=50,seeds=[3200,3239],python=sys.version,numpy_version=numpy.__version__,source_sha256=source_hashes,repo_commit_observed_after_run=repo_commit,summaries=summaries,rows=rows,contract_checks={'ack_schema':checks,'no_change_control':'DynamicEnvironment supplies no rule_change menu: Prepared is exactly controller36, not a sham case with a published menu'},seconds=time.time()-start)
Path(args.output).write_text(json.dumps(out,indent=2)+'\n')
