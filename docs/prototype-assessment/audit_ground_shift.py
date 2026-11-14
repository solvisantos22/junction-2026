"""Read-only reproduction of already-used shift seeds; run from repository root."""
import argparse, hashlib, json, math, statistics, subprocess, sys, time
import numpy
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--repo', default=str(Path.cwd()))
parser.add_argument('--output', default='shift-reproduction.json')
args=parser.parse_args()
task_repo=Path(args.repo).resolve()
sys.path.insert(0, str(task_repo))
from lightlag import Config
from lightlag_dynamic.environment import DynamicEnvironment
from lightlag_dynamic.missions import PROFILES
from lightlag_dynamic.tools import PublicTools
from lightlag_dynamic.controllers import POLICIES
from lightlag_dynamic.manh_controllers.controllers import REGISTRY, number
from lightlag_shift import ShiftEnvironment

def digest(x):
    return hashlib.sha256(json.dumps(x, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

rows=[]
policies={name: (lambda tools, env, name=name: POLICIES[name](tools)) for name in ['kf_mpc','open_loop','leg_and_wait']}
for n in [27,36]:
    name=next(nm for nm in REGISTRY if number(nm)==n)
    policies['manh_'+str(n)] = REGISTRY[name]['play']
start=time.time()
for name, play in policies.items():
    for changed, cls in [(False,DynamicEnvironment),(True,ShiftEnvironment)]:
        for seed in range(3100,3140):
            env=cls(seed=seed, config=Config(delay_ticks=3,max_ticks=PROFILES['rush_noisy'][4]),profile='rush_noisy')
            tools=PublicTools(env)
            play(tools, env)
            while not env.advance(5)['episode_complete']:
                pass
            replay=env.replay()
            final=replay['states'][-1]
            base=replay['world']['base']
            alive=final['battery']>0
            home=alive and math.dist(final['position'],base)<=env.rules()['base_radius']+1e-9
            rows.append(dict(policy=name, shifted=changed, seed=seed, result=env.evaluate(),alive=alive,home=home,final=final,public_calls=tools.calls,replay_sha256=digest(replay)))
        group=[r for r in rows if r['policy']==name and r['shifted']==changed]
        summary=dict(policy=name,shifted=changed,n=len(group),mean_raw=statistics.mean(r['result']['raw_score'] for r in group),mean_normalized=statistics.mean(r['result']['raw_score'] / r['result']['max_available_value'] for r in group),home=sum(r['home'] for r in group),alive=sum(r['alive'] for r in group))
        print(json.dumps(summary),flush=True)
packages=['lightlag','lightlag_dynamic','lightlag_controllers','lightlag_shift','lightlag_mcp']
files=sorted(p for package in packages for p in (task_repo/package).rglob('*.py'))
source_hashes={str(p.relative_to(task_repo)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
repo_commit=subprocess.check_output(['git','-C',str(task_repo),'rev-parse','HEAD'],text=True).strip()
out=dict(purpose='Reproduce previously used seeds, no model runs; reference/controller implementations unchanged',profile='rush_noisy',delay=3,seeds=[3100,3139],python=sys.version,numpy_version=numpy.__version__,source_sha256=source_hashes,repo_commit_observed_after_run=repo_commit,rows=rows,seconds=time.time()-start)
# Small contract checks use an already-used seed and no policy tuning.
from lightlag_dynamic.kf_mpc import DriveFilter
edge=ShiftEnvironment(seed=3100,config=Config(max_ticks=10))
while not edge.advance(5)['episode_complete']:
    pass
f=DriveFilter(ShiftEnvironment(seed=3100).rules(),(0,0))
forced={'bedrock':.2,'sand':.6}
for terrain,value in forced.items():
    f.mean[f.index[terrain]]=value
out['contract_checks']={'short_horizon':{'seed':3100,'horizon':10,'published':edge.rules()['ground_change'],'drawn_tick':edge.shift['tick'],'applied_tick':edge._slip_changed_at},'filter_accessor':{'forced_mean':forced,'effective_slip':{t:f.slip(t) for t in forced}}}
Path(args.output).write_text(json.dumps(out,indent=2)+'\n')
