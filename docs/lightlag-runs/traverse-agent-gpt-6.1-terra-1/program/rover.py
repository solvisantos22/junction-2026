import math, heapq, random, time, sys
from lightlag_client import connect
from lightlag_surface import Surface, drive, PHYSICS

URL='http://lightlag:8000/mcp'
SLIP={'bedrock':.03,'regolith':.085,'sand':.25,'rocks':.18}

class Planner:
    def __init__(self,w):
        self.w=w; self.s=Surface(w['cell_m'],w['elevation_cm'],w['terrain'])
        self.nx=self.s.nx-1; self.ny=self.s.ny-1; self.n=self.nx*self.ny
        self.ok=[]; self.pts=[]; self.fwd=[[] for _ in range(self.n)]; self.rev=[[] for _ in range(self.n)]
        for j in range(self.ny):
            for i in range(self.nx):
                x=(i+.5)*5; y=(j+.5)*5
                self.pts.append((x,y)); self.ok.append(self.s.cell_max_slope(i,j)<.335 and 1<i<self.nx-2 and 1<j<self.ny-2)
        for j in range(self.ny):
            for i in range(self.nx):
                a=j*self.nx+i
                if not self.ok[a]: continue
                x,y=self.pts[a]
                for di,dj in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
                    ii=i+di; jj=j+dj
                    if not (0<=ii<self.nx and 0<=jj<self.ny): continue
                    b=jj*self.nx+ii
                    if not self.ok[b] or (di and dj and (not self.ok[j*self.nx+ii] or not self.ok[jj*self.nx+i])): continue
                    xx,yy=self.pts[b]; dist=math.hypot(xx-x,yy-y); ux=(xx-x)/dist; uy=(yy-y)/dist
                    h,gx,gy,code=self.s.sample((x+xx)/2,(y+yy)/2)
                    name={'b':'bedrock','r':'regolith','s':'sand','k':'rocks'}[code]
                    slip=min(.8,SLIP[name]+PHYSICS['slip_grade_gain'][name]*max(0,gx*ux+gy*uy))
                    cost=dist/(1-slip)/5
                    self.fwd[a].append((b,cost)); self.rev[b].append((a,cost))
        self.cache={}
    def node(self,x,y):
        i=int(x/5);j=int(y/5); best=None
        for dj in range(-3,4):
            for di in range(-3,4):
                ii=i+di;jj=j+dj
                if 0<=ii<self.nx and 0<=jj<self.ny:
                    n=jj*self.nx+ii
                    if self.ok[n]:
                        d=math.hypot(self.pts[n][0]-x,self.pts[n][1]-y)
                        if best is None or d<best[0]:best=(d,n)
        return best[1] if best else None
    def distances(self,dest):
        node=self.node(*dest)
        if node in self.cache:return self.cache[node]
        dist=[float('inf')]*self.n; dist[node]=0.; heap=[(0.,node)]
        while heap:
            d,n=heapq.heappop(heap)
            if d!=dist[n]:continue
            for p,c in self.rev[n]:
                v=d+c
                if v<dist[p]:dist[p]=v;heapq.heappush(heap,(v,p))
        self.cache[node]=dist
        return dist
    def travel(self,a,b):
        n=self.node(*a)
        return self.distances(b)[n] if n is not None else 9999
    def waypoint(self,pos,dest):
        if math.dist(pos,dest)<7:
            return dest
        n=self.node(*pos); dist=self.distances(dest)
        if n is None or not math.isfinite(dist[n]):return dest
        path=[n]
        for _ in range(8):
            p=path[-1]
            if dist[p]<.01:break
            opts=[(c+dist[q],q) for q,c in self.fwd[p]]
            if not opts:break
            _,q=min(opts)
            if q in path:break
            path.append(q)
        # Follow grid edges, avoiding corners of blocked cells.
        for p in reversed(path[:4]):
            pt=self.pts[p]
            if self.line_safe(pos,pt): return pt
        return self.pts[path[0]]
    def line_safe(self,a,b):
        d=math.dist(a,b); steps=max(1,int(d/.7))
        for k in range(steps+1):
            f=k/steps; x=a[0]+f*(b[0]-a[0]); y=a[1]+f*(b[1]-a[1])
            if x<2 or y<2 or x>self.s.width-2 or y>self.s.height-2:return False
            i=int(x/5);j=int(y/5)
            if not self.ok[j*self.nx+i]:return False
        return True

def optimize(planner, targets, pos, tick, old=None, loops=40000):
    ts=list(targets); n=len(ts); base=planner.w['base']; pts=[(t['x'],t['y']) for t in ts]+[tuple(pos),tuple(base)]
    mat=[[planner.travel(a,b) for b in pts] for a in pts]
    # Allow for steering, position corrections and the sample command.
    def evaluate(route):
        tm=float(tick); prev=n; val=0.
        for i in route:
            tm+=mat[prev][i]*1.13+5.5
            t=ts[i]; val+=t['value'] if t['deadline_tick'] is None or tm<=t['deadline_tick']-2 else t['late_value']
            prev=i
        end=tm+mat[prev][n+1]*1.13+6
        return val-max(0,end-405)*.65, end, val
    ids={t['id']:i for i,t in enumerate(ts)}
    start=[ids[x] for x in (old or []) if x in ids]
    best=start[:]; bestscore=evaluate(best)[0]
    route=start[:]; score=bestscore
    for k in range(loops):
        if k%10000==0 and k:
            route=best[:];score=evaluate(route)[0]
        candidate=route[:]; r=random.random()
        if r<.36 and len(candidate)<n:
            unused=list(set(range(n))-set(candidate)); v=random.choice(unused); candidate.insert(random.randrange(len(candidate)+1),v)
        elif r<.52 and candidate:
            candidate.pop(random.randrange(len(candidate)))
        elif r<.76 and len(candidate)>=2:
            i=random.randrange(len(candidate));v=candidate.pop(i);candidate.insert(random.randrange(len(candidate)+1),v)
        elif r<.90 and len(candidate)>=2:
            i,j=sorted(random.sample(range(len(candidate)),2));candidate[i:j+1]=reversed(candidate[i:j+1])
        elif candidate and len(candidate)<n:
            unused=list(set(range(n))-set(candidate));candidate[random.randrange(len(candidate))]=random.choice(unused)
        ns=evaluate(candidate)[0]; temp=.45*(1-(k%10000)/10000)+.035
        if ns>score or random.random()<math.exp(max(-100,(ns-score)/temp)):
            route=candidate;score=ns
            if ns>bestscore:best=route[:];bestscore=ns
    return [ts[i]['id'] for i in best],evaluate(best)

class Filter:
    def __init__(self,pos,planner):
        self.x=[pos[0],pos[1],0.]
        self.P=[[.01,0.,0.],[0.,.01,0.],[0.,0.,(math.radians(5)**2)/3]]
        self.p=planner; self.tick=0
    def move(self,cmd,odo=None):
        x,y,b=self.x
        if cmd and cmd['action']=='drive':
            z=drive(self.p.s,PHYSICS,x,y,cmd['heading_deg']+math.degrees(b),cmd['metres'],SLIP)
            dx=z['x']-x;dy=z['y']-y
            if odo is not None and z['ground']>.01:
                scale=odo/z['ground']; dx*=scale;dy*=scale
            self.x[0]+=dx;self.x[1]+=dy
            F=[[1.,0.,-dy],[0.,1.,dx],[0.,0.,1.]]
            P=self.P
            FP=[[sum(F[i][k]*P[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
            self.P=[[sum(FP[i][k]*F[j][k] for k in range(3)) for j in range(3)] for i in range(3)]
            q=.08+(0.05*math.hypot(dx,dy))**2
            self.P[0][0]+=q;self.P[1][1]+=q;self.P[2][2]+=math.radians(.2)**2
    def observe(self,pkt,cmd):
        self.move(cmd,pkt.get('visual_odometry',0))
        for axis in (0,1):
            P=self.P; v=pkt['position'][axis]-self.x[axis]; s=P[axis][axis]+1.
            gain=[P[i][axis]/s for i in range(3)]; row=P[axis][:]
            for i in range(3):
                self.x[i]+=gain[i]*v
                for j in range(3): self.P[i][j]-=gain[i]*row[j]
        self.x[2]=max(-.25,min(.25,self.x[2]));self.tick=pkt['tick']
    def project(self,commands,lasttick):
        x,y,b=self.x
        for tick in range(self.tick+1,lasttick+1):
            cmd=commands.get(tick)
            if cmd and cmd['action']=='drive':
                z=drive(self.p.s,PHYSICS,x,y,cmd['heading_deg']+math.degrees(b),cmd['metres'],SLIP)
                x,y=z['x'],z['y']
        return x,y

def run(tools,world,planner,route):
    filt=Filter(world['base'],planner); cmds={}; sampled=set(); pending={}; tick=0
    targets={t['id']:t for t in world['targets']}; base=tuple(world['base']); battery=100.
    current=None; last_replan=0; last_log=-1; returning=False; stuck=0
    while tick<420:
        # Discard routes already visited or awaiting confirmation.
        route=[v for v in route if v not in sampled and v not in pending and v in targets]
        predicted=filt.project(cmds,tick+3)
        if not returning:
            home=planner.travel(predicted,base)*1.19+8
            if tick+home>=413:
                returning=True;route=[];print('RETURN',tick,'eta',round(home,1),'pos',tuple(round(v,1) for v in predicted),flush=True)
        if route:
            current=route[0]; tar=targets[current]; dest=(tar['x'],tar['y'])
        else:
            current=None;dest=base
        d=math.dist(predicted,dest)
        cmd={'action':'wait'}
        if current and d<.65:
            cmd={'action':'sample'};pending[current]=tick+4;route.pop(0)
            print('SAMPLE QUEUED',tick+4,current,'distance',round(d,2),'est',tuple(round(v,1) for v in predicted),'battery',round(battery,1),flush=True)
        elif (current or d>1.0) and battery>12:
            wp=planner.waypoint(predicted,dest)
            dd=math.dist(predicted,wp)
            if dd<.8 and math.dist(predicted,dest)>7:
                wp=dest;dd=math.dist(predicted,wp)
            ang=math.degrees(math.atan2(wp[1]-predicted[1],wp[0]-predicted[0]))-math.degrees(filt.x[2])
            # A little under-steering near a target reduces overshoot.
            m=min(5.,max(.12,dd/0.88))
            cmd={'action':'drive','heading_deg':ang%360,'metres':m}
        ack=tools.uplink([cmd]); et=ack[0]['execute_tick'];cmds[et]=cmd
        result=tools.advance(1); tick=result['current_tick']
        for pkt in result['packets']:
            pt=pkt['tick']; observedcmd=cmds.get(pt)
            filt.observe(pkt,observedcmd);battery=pkt['battery']
            new=set(pkt.get('sampled_targets',[]));
            if new-sampled:
                print('COLLECTED',pt,sorted(new-sampled),'battery',round(battery,1),flush=True)
            sampled |= new
            for k,when in list(pending.items()):
                if pt>=when:
                    del pending[k]
                    if k not in sampled:
                        print('MISSED',k,pt,'position',pkt['position'],flush=True);route.insert(0,k)
            for event in pkt.get('events',[]):
                print('EVENT',pt,event,flush=True)
                if isinstance(event,dict) and event.get('type')=='target_discovered':
                    world=tools.map();targets={t['id']:t for t in world['targets']}
                    print('DISCOVERED',len(targets),flush=True)
                if isinstance(event,dict) and ('stop' in str(event).lower() or 'tilt' in str(event).lower()):
                    for k in list(cmds):
                        if k>pt: del cmds[k]
                    stuck+=1
        if tick%25==0:
            print('STATE',tick,'estimated',tuple(round(v,1) for v in predicted),'battery',round(battery,1),'bias',round(math.degrees(filt.x[2]),2),'target',current,'remaining',route,flush=True)
        # React to discoveries and trajectory deviations, preserving the running route as a seed.
        if not returning and tick-last_replan>=45 and tick<310:
            available=[v for v in targets.values() if v['id'] not in sampled and v['id'] not in pending]
            fresh,score=optimize(planner,available,predicted,tick,old=route,loops=30000)
            if fresh:
                route=fresh
                print('REPLAN',tick,route,score,flush=True)
            last_replan=tick
        if result['episode_complete']:
            print('COMPLETE',result,flush=True);break

if __name__=='__main__':
    random.seed(15)
    with connect(URL) as tools:
        world=tools.map(); planner=Planner(world)
        print('planning',flush=True)
        seed=['t12','t25','t28','t1','t13','t8','t17','t14','t36','t27','t22','t10','t20','t26','t15','t16']
        route,score=optimize(planner,world['targets'],world['base'],0,old=seed,loops=400000)
        print('plan',route,score,flush=True)
        if '--preview' not in sys.argv:run(tools,world,planner,route)
