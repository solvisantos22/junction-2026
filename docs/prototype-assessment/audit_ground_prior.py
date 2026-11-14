"""Read-only reproduction of already-used shift seeds; run from repository root."""
import argparse, hashlib, json, math, statistics, subprocess, sys, time
import numpy
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--repo', default=str(Path.cwd()))
parser.add_argument('--output', default='shift-public-range-diagnostic.json')
args=parser.parse_args()
task_repo=Path(args.repo).resolve()
sys.path.insert(0, str(task_repo))
from lightlag import Config
from lightlag_dynamic.environment import DynamicEnvironment
from lightlag_dynamic.missions import PROFILES
from lightlag_dynamic.tools import PublicTools
from lightlag_dynamic.controllers import POLICIES
from lightlag_dynamic.manh_controllers.controllers import REGISTRY, number
from lightlag_shift import ShiftEnvironment, SLIP_AFTER
import numpy

class PublicRangeUnionTools(PublicTools):
    def rules(self):
        rules = super().rules()
        after = rules.get('ground_change', {}).get('slip_after', SLIP_AFTER)
        rules['slip_ranges'] = {t: [min(lo, after[t][0]), max(hi, after[t][1])] for t, (lo, hi) in rules['slip_ranges'].items()}
        return rules


def digest(x):
    return hashlib.sha256(json.dumps(x, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

rows=[]
policies={'kf_mpc_public_union_prior': lambda tools, env: POLICIES['kf_mpc'](tools)}
start=time.time()
for name, play in policies.items():
    for changed, cls in [(False,DynamicEnvironment),(True,ShiftEnvironment)]:
        for seed in range(3100,3140):
            env=cls(seed=seed, config=Config(delay_ticks=3,max_ticks=PROFILES['rush_noisy'][4]),profile='rush_noisy')
            tools=PublicRangeUnionTools(env)
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
out=dict(purpose='Exploratory fixed public-range sensitivity diagnostic on used seeds: range union changes both bounds and initial prior, not a change-aware reference or model run; unchanged controls also receive the declared shift-family ranges', numpy_version=numpy.__version__,profile='rush_noisy',delay=3,seeds=[3100,3139],python=sys.version,source_sha256=source_hashes,repo_commit_observed_after_run=repo_commit,rows=rows,seconds=time.time()-start)
Path(args.output).write_text(json.dumps(out,indent=2)+'\n')
