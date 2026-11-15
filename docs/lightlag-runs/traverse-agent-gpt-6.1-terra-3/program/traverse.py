import math, random, heapq, time, traceback
from lightlag_client import connect
from lightlag_surface import Surface, drive, PHYSICS

random.seed(24)
SPEED = 4.15
OVERHEAD = 6.0
SLIP = {'bedrock':.03,'regolith':.085,'sand':.25,'rocks':.18}

class Navigator:
    def __init__(self, world):
        self.world=world
        self.s=Surface(world['cell_m'],world['elevation_cm'],world['terrain'])
        self.nx=self.s.nx; self.ny=self.s.ny; self.n=self.nx*self.ny
        self.base=world['base']; self.fields={}; self.targets={}
        self.adj=[[] for _ in range(self.n)]
        self.build_graph()
        self.add_targets(world['targets'])
        self.field('base',*self.base)

    def idx(self,x,y):
        i=max(1,min(self.nx-2,round(x/5))); j=max(1,min(self.ny-2,round(y/5)))
        return j*self.nx+i
    def xy(self,k): return ((k%self.nx)*5.,(k//self.nx)*5.)
    def safe_line(self,x,y,xx,yy,margin=1.0):
        d=math.hypot(xx-x,yy-y)
        if d<1e-6: return True
        ux=(xx-x)/d; uy=(yy-y)/d
        for k in range(int(d/1.5)+2):
            t=min(1,k/(int(d/1.5)+1)); px=x+t*(xx-x); py=y+t*(yy-y)
            for off in (-margin,0,margin):
                qx=px-uy*off; qy=py+ux*off
                if not (0.4<qx<self.s.width-.4 and 0.4<qy<self.s.height-.4): return False
                if self.s.slope(qx,qy)>.325: return False
        return True
    def build_graph(self):
        for j in range(1,self.ny-1):
            for i in range(1,self.nx-1):
                k=j*self.nx+i; x=i*5; y=j*5
                for di,dj in ((1,0),(0,1),(1,1),(-1,1)):
                    ii=i+di; jj=j+dj
                    if not(1<=ii<self.nx-1 and 1<=jj<self.ny-1): continue
                    xx=ii*5; yy=jj*5
                    if not self.safe_line(x,y,xx,yy,1.1): continue
                    midx=(x+xx)/2; midy=(y+yy)/2
                    _,gx,gy,terrain=self.s.sample(midx,midy)
                    factor={'b':1.045,'r':1.10,'s':1.29,'k':1.21}[terrain] + .75*math.hypot(gx,gy)
                    cost=math.hypot(xx-x,yy-y)*factor
                    q=jj*self.nx+ii
                    self.adj[k].append((q,cost)); self.adj[q].append((k,cost))
        print('graph ready',flush=True)
    def field(self,key,x,y):
        k=self.idx(x,y)
        if not self.adj[k]:
            options=[(math.hypot(*[a-b for a,b in zip(self.xy(i),(x,y))]),i) for i in range(self.n) if self.adj[i]]
            k=min(options)[1]
            print('isolated',key,x,y,'node',self.xy(k),flush=True)
        dist=[float('inf')]*self.n; dist[k]=0.; h=[(0.,k)]
        while h:
            d,p=heapq.heappop(h)
            if d!=dist[p]: continue
            for q,c in self.adj[p]:
                nd=d+c
                if nd<dist[q]: dist[q]=nd; heapq.heappush(h,(nd,q))
        self.fields[key]=dist
    def add_targets(self,targets):
        for t in targets:
            key=t['id']
            if key not in self.targets:
                self.targets[key]=t
                self.field(key,t['x'],t['y'])
                print('target',key,t['x'],t['y'],'value',t['value'],'deadline',t['deadline_tick'],flush=True)
    def dist(self,key,x,y):
        k=self.idx(x,y); d=self.fields[key][k]
        if math.isinf(d):
            choices=[]
            for dj in range(-2,3):
                for di in range(-2,3):
                    q=k+dj*self.nx+di
                    if 0<=q<self.n and self.adj[q] and self.safe_line(x,y,*self.xy(q),.3):
                        choices.append((self.fields[key][q]+math.dist((x,y),self.xy(q))*1.2,q))
            return min(choices)[0] if choices else 1e6
        return d+math.dist((x,y),self.xy(k))*.6
    def waypoint(self,key,x,y):
        dest=self.base if key=='base' else (self.targets[key]['x'],self.targets[key]['y'])
        if math.dist((x,y),dest)<18 and self.safe_line(x,y,*dest,.8): return dest
        k=self.idx(x,y); field=self.fields[key]
        if not self.adj[k] or math.isinf(field[k]):
            choices=[]
            for dj in range(-3,4):
                for di in range(-3,4):
                    q=k+dj*self.nx+di
                    if 0<=q<self.n and self.adj[q] and self.safe_line(x,y,*self.xy(q),.5):
                        choices.append((field[q]+math.dist((x,y),self.xy(q))*1.15,q))
            if not choices: return dest
            k=min(choices)[1]
        path=[k]
        for _ in range(12):
            if not self.adj[k] or field[k]<.01: break
            q=min(self.adj[k],key=lambda v: v[1]+field[v[0]])[0]
            if field[q]>=field[k]-.001: break
            path.append(q); k=q
        # Use the furthest path vertex reachable without crossing unsafe ground.
        best=self.xy(path[0])
        for q in path[1:]:
            xx,yy=self.xy(q)
            if math.dist((x,y),(xx,yy))>25: break
            if self.safe_line(x,y,xx,yy,1.2): best=(xx,yy)
            else: break
        if math.dist((x,y),best)<1.0 and len(path)>1: best=self.xy(path[1])
        return best

def plan(nav,pos,tick,sampled,oldroute,iterations=14000):
    ids=[k for k in nav.targets if k not in sampled]
    if not ids: return []
    matrix={}
    for a in ids:
        matrix['start',a]=nav.dist(a,*pos)
        matrix[a,'base']=nav.dist('base',nav.targets[a]['x'],nav.targets[a]['y'])
        for b in ids:
            if a!=b:
                matrix[a,b]=nav.dist(b,nav.targets[a]['x'],nav.targets[a]['y'])
    startbase=nav.dist('base',*pos)
    def score(route):
        elapsed=float(tick); prev='start'; reward=0.
        for k in route:
            elapsed+=matrix[prev,k]/SPEED+OVERHEAD
            target=nav.targets[k]; dl=target['deadline_tick']
            if dl is None: value=target['value']
            elif elapsed<=dl-3: value=target['value']
            elif elapsed>=dl+5: value=target['late_value']
            else: value=target['late_value']+(target['value']-target['late_value'])*(dl+5-elapsed)/8
            reward+=value; prev=k
        elapsed+=(matrix[prev,'base'] if route else startbase)/SPEED
        # Keep time for return localization and unmodelled terrain.
        excess=max(0,elapsed-405)
        return reward - excess*.24 - (elapsed-tick)*.008
    route=[x for x in oldroute if x in ids]
    cur=score(route); best=route[:]; bestscore=cur
    for it in range(iterations):
        p=it/iterations; temp=.85*(1-p)+.04
        new=route[:]; r=random.random()
        available=[k for k in ids if k not in new]
        if r<.30 and available:
            new.insert(random.randrange(len(new)+1),random.choice(available))
        elif r<.44 and new:
            new.pop(random.randrange(len(new)))
        elif r<.66 and len(new)>1:
            a=random.randrange(len(new)); b=random.randrange(len(new)); v=new.pop(a); new.insert(b,v)
        elif r<.82 and len(new)>1:
            a,b=sorted(random.sample(range(len(new)),2)); new[a:b+1]=reversed(new[a:b+1])
        elif new and available:
            new[random.randrange(len(new))]=random.choice(available)
        else: continue
        ns=score(new)
        if ns>cur or random.random()<math.exp(max(-100,(ns-cur)/temp)):
            route=new; cur=ns
        if ns>bestscore: best=new[:]; bestscore=ns
    print('PLAN',tick,'pos',tuple(round(z,1) for z in pos),'score',round(bestscore,1),'route',best,flush=True)
    return best

def run():
  with connect('http://lightlag:8000/mcp') as tools:
    rules=tools.rules(); world=tools.map(); packets=tools.telemetry_log()
    nav=Navigator(world)
    p=packets[-1]; tick=p['tick']; estimate=tuple(p['position']); cov=.1
    seen_tick=tick; cmd_by_tick={}; sampled=set(p['sampled_targets']); route=[]
    pending_sample=None; target=None; mode='moving'; last_plan=-100; battery=100.; idle_energy=False
    route=plan(nav,estimate,tick,sampled,[],28000)
    complete=False
    while not complete:
        # Estimate state at latest received tick using map physics and noisy GPS.
        for pkt in packets:
            if pkt['tick']<=seen_tick: continue
            pt=pkt['tick']; cmd=cmd_by_tick.get(pt,{'action':'wait'})
            if cmd['action']=='drive' and pkt['wheel_odometry']>0:
                result=drive(nav.s,PHYSICS,*estimate,cmd['heading_deg'],pkt['wheel_odometry'],SLIP)
                dx=result['x']-estimate[0]; dy=result['y']-estimate[1]
                predicted=math.hypot(dx,dy)
                if predicted>.01:
                    ratio=max(.75,min(1.25,pkt['visual_odometry']/predicted))
                    estimate=(estimate[0]+dx*ratio,estimate[1]+dy*ratio)
                cov+=.17
            else: cov+=.025
            gain=cov/(cov+1.)
            estimate=(estimate[0]+gain*(pkt['position'][0]-estimate[0]),estimate[1]+gain*(pkt['position'][1]-estimate[1]))
            cov=(1-gain)*cov
            seen_tick=pt; battery=pkt['battery']; sampled=set(pkt['sampled_targets'])
            for event in pkt.get('events',[]):
                print('EVENT',pt,event,flush=True)
                if event.get('type')=='target_discovered':
                    nav.add_targets(tools.map()['targets']); last_plan=-100
                if event.get('type') in ('safety_stop','tilt_stop'):
                    print('STOP',event,flush=True)
        # Project from the last observed state through all commands that may be in flight.
        projected=estimate
        for pt in range(seen_tick+1,tick+4):
            cmd=cmd_by_tick.get(pt)
            if cmd and cmd['action']=='drive':
                r=drive(nav.s,PHYSICS,*projected,cmd['heading_deg'],cmd['metres'],SLIP)
                projected=(r['x'],r['y'])
        if pending_sample is not None and seen_tick>=pending_sample:
            if target in sampled:
                print('SAMPLED',target,'tick',pending_sample,'battery',round(battery,1),flush=True)
                route=[v for v in route if v!=target]; target=None; last_plan=-100
            else:
                print('MISSED',target,'tick',pending_sample,'estimate',tuple(round(z,2) for z in estimate),flush=True)
            pending_sample=None
        if not pending_sample and (tick-last_plan>38 or (target is None and tick-last_plan>2)) and tick<360:
            newroute=plan(nav,projected,tick+3,sampled,route,10000)
            route=newroute; last_plan=tick
            target=route[0] if route else 'base'
        if target in sampled:
            target=None
        if target is None: target=route[0] if route else 'base'
        # At late times, ensure a generous final approach margin.
        return_dist=nav.dist('base',*projected)
        if tick+return_dist/3.55+17>=420 and target!='base':
            print('RETURN',tick,'distance',round(return_dist,1),flush=True)
            target='base'; route=[]; last_plan=10000
        if battery<22: idle_energy=True
        if battery>37: idle_energy=False
        action={'action':'wait'}
        if pending_sample is None and not idle_energy:
            dest=nav.base if target=='base' else (nav.targets[target]['x'],nav.targets[target]['y'])
            distance=math.dist(projected,dest)
            if target!='base' and distance<1.1:
                action={'action':'sample'}
                pending_sample=tick+4
            elif target=='base' and distance<1.0:
                pass
            else:
                waypoint=nav.waypoint(target,*projected)
                dx=waypoint[0]-projected[0]; dy=waypoint[1]-projected[1]; d=math.hypot(dx,dy)
                if d>.15:
                    heading=math.degrees(math.atan2(dy,dx))%360
                    # Adjust wheel distance through local surface model.
                    trial=drive(nav.s,PHYSICS,*projected,heading,min(5.,max(.1,d*1.16)),SLIP)
                    moved=math.dist(projected,(trial['x'],trial['y']))
                    wheel=min(5.,max(.1,d*min(1.8, min(5.,max(.1,d*1.16))/max(.1,moved))))
                    action={'action':'drive','heading_deg':heading,'metres':wheel}
        if tick<417:
            ack=tools.uplink([action]); et=ack[0]['execute_tick']; cmd_by_tick[et]=action
        out=tools.advance(1); tick=out['current_tick']; complete=out['episode_complete']; packets=out['packets']
        if tick%20==0 or complete:
            print('STATE',tick,'obs',seen_tick,'est',tuple(round(z,1) for z in estimate),'projected',tuple(round(z,1) for z in projected),'target',target,'battery',round(battery,1),'sampled',len(sampled),'action',action,flush=True)
    print('COMPLETE',out,flush=True)
    print('LOG_FINAL',tools.telemetry_log()[-8:],flush=True)

if __name__=='__main__':
    try: run()
    except Exception: traceback.print_exc()
