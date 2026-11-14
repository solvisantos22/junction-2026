import json, math, random, sys
sys.path.insert(0,'/app')
from lightlag_surface import Surface, drive, PHYSICS
import auto
class Fake:
    def __init__(s,seed=1):
        s.m=json.load(open('/tmp/map.json')); s.r=random.Random(seed)
        s.S=Surface(5.0,s.m['elevation_cm'],s.m['terrain'])
        s.slip={k:s.r.uniform(*v) for k,v in PHYSICS['slip_base_ranges'].items()}
        s.bias=s.r.uniform(-5,5); s.eff=s.r.uniform(.8,1)
        s.t=0; s.pos=list(s.m['base']); s.bat=100; s.q={}; s.last=0; s.done=[]
        s.pk=[]; s.alive=True
        s.tg=s.m['targets']
        s.pend=[s.mk(0)]
    def map(s): 
        m=dict(s.m); return m
    def mk(s,odo,ev=()):
        return {'tick':s.t,'position':[s.pos[0]+s.r.gauss(0,1),s.pos[1]+s.r.gauss(0,1)] if s.t else list(s.pos),'battery':s.bat,'charge':s.ch if s.t else 0,'wheel_odometry':odo,'sampled_targets':list(s.done),'events':[],'alive':True}
    def uplink(s,cmds):
        out=[]
        for c in cmds:
            e=max(s.t+4,s.last+1); s.last=e; s.q[e]=c; out.append({'execute_tick':e})
        return out
    def advance(s,n):
        pk=[]
        for _ in range(n):
            s.t+=1
            s.ch=2.8*s.eff*math.sin(math.pi*(s.t+56)/532); s.bat=min(100,s.bat+s.ch)-0.15
            c=s.q.get(s.t); odo=0
            if c:
                if c['action']=='drive':
                    s.bias+=s.r.gauss(0,.2)
                    h=c['heading_deg']+s.bias+s.r.gauss(0,1.5)
                    r=drive(s.S,PHYSICS,s.pos[0],s.pos[1],h,c['metres'],s.slip,s.r.uniform(-.02,.02))
                    s.pos=[r['x'],r['y']]; s.bat-=r['energy']; odo=r['wheel']
                    if r['stop']:
                        for k in [k for k in s.q if k>s.t]: del s.q[k]
                elif c['action']=='sample':
                    s.bat-=2
                    best=None
                    for t in s.tg:
                        if t['id'] in s.done: continue
                        d=math.hypot(t['x']-s.pos[0],t['y']-s.pos[1])
                        if d<=2.5 and (best is None or d<best[0]): best=(d,t)
                    if best:
                        s.done.append(best[1]['id']); s.val=getattr(s,'val',0)+(best[1]['value'] if (best[1]['deadline_tick'] is None or s.t<=best[1]['deadline_tick']) else best[1]['late_value'])
            s.pend.append(s.mk(odo))
        out=[p for p in s.pend if p['tick']<=s.t-3]
        s.pend=[p for p in s.pend if p['tick']>s.t-3]
        return {'current_tick':s.t,'episode_complete':s.t>=420,'packets':out}
if __name__=='__main__':
    f=Fake(int(sys.argv[1]) if len(sys.argv)>1 else 1)
    auto.run(f)
    print('val',getattr(f,'val',0),'pos',f.pos,'base',f.m['base'],'bat',f.bat)
