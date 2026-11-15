import math, heapq, random, sys, time
from lightlag_client import connect
from lightlag_surface import Surface, drive, PHYSICS

random.seed(91)
SLIP = {'bedrock':.03,'regolith':.085,'sand':.25,'rocks':.18}
CODE = {'b':'bedrock','r':'regolith','s':'sand','k':'rocks'}

class Navigator:
    def __init__(self,w):
        self.world=w; self.s=Surface(w['cell_m'],w['elevation_cm'],w['terrain'])
        self.nx=self.s.nx-1; self.ny=self.s.ny-1; self.n=self.nx*self.ny
        self.safe=[]; self.data=[]
        for j in range(self.ny):
            for i in range(self.nx):
                x=(i+.5)*5; y=(j+.5)*5
                self.safe.append(self.s.cell_max_slope(i,j)<.335)
                self.data.append(self.s.sample(x,y))
        self.edges=[[] for _ in range(self.n)]
        for j in range(self.ny):
            for i in range(self.nx):
                a=j*self.nx+i
                if not self.safe[a]: continue
                h,gx,gy,c=self.data[a]
                for dx,dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,1),(1,-1),(-1,-1)):
                    ii=i+dx; jj=j+dy
                    if not (0<=ii<self.nx and 0<=jj<self.ny):continue
                    b=jj*self.nx+ii
                    if not self.safe[b]:continue
                    if dx and dy and (not self.safe[j*self.nx+ii] or not self.safe[jj*self.nx+i]):continue
                    h2,gx2,gy2,c2=self.data[b]; d=5*math.hypot(dx,dy); ux=dx*5/d; uy=dy*5/d
                    grade=((gx+gx2)*ux+(gy+gy2)*uy)/2
                    slip=(SLIP[CODE[c]]+SLIP[CODE[c2]])/2 + (PHYSICS['slip_grade_gain'][CODE[c]]+PHYSICS['slip_grade_gain'][CODE[c2]])/2*max(0,grade)
                    # Include a small energy/roughness penalty so routes favor easy ground.
                    cost=d/(1-min(.8,slip)) * (1 + .07*(c=='k') + .06*(c=='s'))
                    self.edges[a].append((b,cost))
        self.cache={}

    def xy(self,n): return ((n%self.nx+.5)*5,(n//self.nx+.5)*5)
    def node(self,x,y):
        i=max(0,min(self.nx-1,int(x/5))); j=max(0,min(self.ny-1,int(y/5)))
        candidates=[]
        for r in range(5):
            for jj in range(max(0,j-r),min(self.ny,j+r+1)):
                for ii in range(max(0,i-r),min(self.nx,i+r+1)):
                    a=jj*self.nx+ii
                    if self.safe[a]: candidates.append((math.hypot(x-(ii+.5)*5,y-(jj+.5)*5),a))
            if candidates:return min(candidates)[1]
        return None
    def dijkstra(self,source):
        if source in self.cache:return self.cache[source]
        dist=[float('inf')]*self.n; prev=[-1]*self.n; dist[source]=0; q=[(0,source)]
        while q:
            d,a=heapq.heappop(q)
            if d!=dist[a]:continue
            for b,c in self.edges[a]:
                v=d+c
                if v<dist[b]:dist[b]=v;prev[b]=a;heapq.heappush(q,(v,b))
        self.cache[source]=(dist,prev)
        return dist,prev
    def path(self,start,end):
        a=self.node(*start); b=self.node(*end)
        if a is None or b is None:return []
        d,p=self.dijkstra(a)
        if not math.isfinite(d[b]):return []
        path=[]; u=b
        while u!=a and u!=-1:path.append(self.xy(u));u=p[u]
        path.reverse();path.append(tuple(end));return path
    def clear(self,a,b):
        # Check a narrow corridor, allowing modest heading/position errors.
        dx=b[0]-a[0];dy=b[1]-a[1];d=math.hypot(dx,dy)
        if not d:return True
        for k in range(1,int(d/1.5)+2):
            f=min(1,k*1.5/d); x=a[0]+f*dx;y=a[1]+f*dy
            for off in (-1.4,0,1.4):
                xx=x-dy/d*off; yy=y+dx/d*off
                if xx<1 or yy<1 or xx>self.s.width-1 or yy>self.s.height-1:return False
                if self.s.slope(xx,yy)>.30:return False
        return True

def optimize(nav, pos, base, targets, tick, budget=180000):
    targets=[t for t in targets if nav.node(t['x'],t['y']) is not None]
    pts=[pos,base]+[(t['x'],t['y']) for t in targets]; nodes=[nav.node(*p) for p in pts]
    mat=[]
    for i,n in enumerate(nodes):
        ds,_=nav.dijkstra(n)
        mat.append([ds[q]/4.25 + (0.4 if i!=j else 0) for j,q in enumerate(nodes)])
    count=len(targets)
    def value(route):
        tm=float(tick); loc=0; reward=0
        for z in route:
            tm+=mat[loc][z+2]+3.5
            t=targets[z]; reward+=t['value'] if t['deadline_tick'] is None or tm<=t['deadline_tick']-3 else t['late_value']
            loc=z+2
        tm+=mat[loc][1]
        # Reserve margin for feedback, localization and late return.
        excess=max(0,tm-398)
        return reward - excess*.65 - max(0,tm-388)*.015,tm,reward
    best=[]; bs=value(best)[0]; route=[]; cur=bs
    for it in range(budget):
        if it%30000==0:
            route=best[:] if it else [];cur=value(route)[0]
        r=route[:]; op=random.random()
        if op<.34 and len(r)<count:
            available=list(set(range(count))-set(r))
            if available:r.insert(random.randrange(len(r)+1),random.choice(available))
        elif op<.48 and r:r.pop(random.randrange(len(r)))
        elif op<.70 and r:
            i=random.randrange(len(r)); z=r.pop(i);r.insert(random.randrange(len(r)+1),z)
        elif op<.84 and len(r)>1:
            i,j=sorted(random.sample(range(len(r)),2));r[i:j+1]=reversed(r[i:j+1])
        elif r:
            available=list(set(range(count))-set(r))
            if available:r[random.randrange(len(r))]=random.choice(available)
        v,tm,rew=value(r)
        temp=.11 + .9*(1-(it%30000)/30000)
        if v>cur or random.random()<math.exp(max(-100,(v-cur)/temp)):
            route=r;cur=v
        if v>bs:
            best=r[:];bs=v
    return [targets[z] for z in best],value(best)

def run(tools,nav,world,base,route,tick,pos):
    commands={}; posterior=pos; posterior_tick=0; bias=0.; sampled=set(); attempted={}; current=None
    path=[]; path_target=None; done=False; last_replan=0; map_targets=world['targets']; observations=[]
    def simulate(p,c,apply_bias=True,odometry=None):
        if not c or c['action']!='drive':return p
        res=drive(nav.s,PHYSICS,p[0],p[1],c['heading_deg']+(bias if apply_bias else 0),c['metres'],SLIP)
        dx=res['x']-p[0];dy=res['y']-p[1]
        if odometry is not None and res['ground']>.1:
            factor=max(.65,min(1.35,odometry/res['ground']));dx*=factor;dy*=factor
        return (p[0]+dx,p[1]+dy)
    def target_xy(t):return (t['x'],t['y'])
    def choose_steering(p,goal):
        dx=goal[0]-p[0];dy=goal[1]-p[1]; d=math.hypot(dx,dy)
        if d<.04:return {'action':'wait'}
        desired=math.degrees(math.atan2(dy,dx))-bias
        best=None
        for delta in (0,-4,4,-9,9):
            h=desired+delta; metres=min(5,max(.05,d/.85))
            for _ in range(2):
                res=drive(nav.s,PHYSICS,p[0],p[1],h+bias,metres,SLIP)
                moved=res['ground']
                if moved>.05:metres=min(5,max(.05,metres*d/moved))
            res=drive(nav.s,PHYSICS,p[0],p[1],h+bias,metres,SLIP)
            score=math.hypot(res['x']-goal[0],res['y']-goal[1])+(100 if res['stop'] else 0)
            if best is None or score<best[0]:best=(score,h,metres,res)
        return {'action':'drive','heading_deg':best[1]%360,'metres':round(best[2],4)}
    print('starting control',flush=True)
    while tick<420 and not done:
        # Predict position at the moment the next uplinked command executes.
        predicted=posterior
        for s in range(posterior_tick+1,tick+4):predicted=simulate(predicted,commands.get(s))
        # Re-plan opportunistically at target boundaries, including new discoveries.
        if (current is None and tick-last_replan>=10 and tick<330):
            remaining=[t for t in map_targets if t['id'] not in sampled and t['id'] not in attempted]
            if remaining:
                route,stat=optimize(nav,predicted,base,remaining,tick+3,budget=45000)
                print('replan',tick,'battery',round(observations[-1]['battery'],1) if observations else 100,stat,[t['id'] for t in route],flush=True)
            last_replan=tick
        if current is None:
            while route and (route[0]['id'] in sampled or route[0]['id'] in attempted):route.pop(0)
            if route:current=route.pop(0);path_target=None
        # Keep a strict route-home budget with a generous feedback buffer.
        home_node=nav.node(*base); here_node=nav.node(*predicted)
        home_cost=nav.dijkstra(home_node)[0][here_node]/4.0 if here_node is not None else 999
        if current is not None and tick+home_cost+14>=420:
            print('return override',tick,round(home_cost,1),current['id'],flush=True)
            current=None;route=[];path_target=None
        goal=target_xy(current) if current else base
        dist=math.dist(predicted,goal)
        if current and dist<.65:
            cmd={'action':'sample'}
            attempted[current['id']]={'target':current,'execute':tick+4}
            print('sample queued',tick,current['id'],'prediction',tuple(round(z,2) for z in predicted),'distance',round(dist,2),'bias',round(bias,2),flush=True)
            current=None;path_target=None
        elif not current and dist<.75:
            cmd={'action':'wait'}
        else:
            key=current['id'] if current else 'BASE'
            if path_target!=key:
                path=nav.path(predicted,goal);path_target=key
                print('navigate',tick,key,'from',tuple(round(z,1) for z in predicted),'path',len(path),'return',round(home_cost,1),flush=True)
            # Remove passed path points and aim for the farthest locally visible point.
            if path:
                nearest=min(range(len(path)),key=lambda i:math.dist(path[i],predicted))
                if nearest>0:path=path[nearest:]
            waypoint=None
            if nav.clear(predicted,goal):waypoint=goal
            else:
                for p in path:
                    if math.dist(predicted,p)>60:break
                    if nav.clear(predicted,p):waypoint=p
                if waypoint is None and path:waypoint=path[0]
                if waypoint is None:waypoint=goal
            cmd=choose_steering(predicted,waypoint)
        # Avoid consuming the last reserves during unfavorable solar conditions.
        if observations and observations[-1]['battery']<13 and cmd['action']=='drive':
            cmd={'action':'wait'}
        ack=tools.uplink([cmd]); execute=ack[0]['execute_tick'];commands[execute]=cmd
        out=tools.advance(1);tick=out['current_tick'];done=out['episode_complete']
        for pkt in out['packets']:
            pt=pkt['tick'];c=commands.get(pt)
            prior=simulate(posterior,c,odometry=pkt.get('visual_odometry') if c and c['action']=='drive' else None)
            ox,oy=pkt['position'];rx=ox-prior[0];ry=oy-prior[1]
            if c and c['action']=='drive' and pkt.get('wheel_odometry',0)>1:
                theta=math.radians(c['heading_deg']+bias)
                cross=-math.sin(theta)*rx+math.cos(theta)*ry
                bias=max(-12,min(12,bias+.50*cross))
            posterior=(prior[0]+.42*rx,prior[1]+.42*ry);posterior_tick=pt
            observations.append(pkt)
            newly=set(pkt['sampled_targets'])-sampled
            if newly:
                sampled.update(newly)
                print('SAMPLED',pt,sorted(newly),'battery',round(pkt['battery'],1),'pos',tuple(round(v,1) for v in posterior),flush=True)
            for tid,info in list(attempted.items()):
                if pt>=info['execute']:
                    if tid not in sampled:
                        print('MISSED',pt,tid,'estimate',posterior,'reported',pkt['position'],flush=True)
                        route.insert(0,info['target'])
                    del attempted[tid]
            for event in pkt.get('events',[]):
                print('EVENT',pt,event,flush=True)
                text=str(event)
                if 'target_discovered' in text:
                    map_targets=tools.map()['targets'];last_replan=-100
                if 'stop' in text or 'tilt' in text:
                    # Safety stops clear the remaining queued commands, but preserve reserved ticks.
                    for k in list(commands):
                        if k>pt:commands[k]={'action':'wait'}
                    path_target=None
            if pt%25==0:
                print('STATUS',pt,'estimate',tuple(round(z,1) for z in posterior),'battery',round(pkt['battery'],1),'target',current['id'] if current else 'BASE','sampled',len(sampled),flush=True)
        if not out['packets'] and tick%25==0:print('no packets',tick,flush=True)
    print('COMPLETE',tick,'sampled',sorted(sampled),'last',observations[-1] if observations else None,flush=True)

def main():
    with connect('http://lightlag:8000/mcp') as tools:
        rules=tools.rules();w=tools.map();nav=Navigator(w)
        print('base',w['base'],flush=True)
        base=(w['base']['x'],w['base']['y']) if isinstance(w['base'],dict) else tuple(w['base'])
        pack=tools.telemetry_log(); tick=pack[-1]['received_tick']; pos=tuple(pack[-1]['position'])
        route,stat=optimize(nav,pos,base,w['targets'],tick)
        print('plan',stat,[(x['id'],x['value'],x['deadline_tick']) for x in route],flush=True)
        if '--plan' in sys.argv:return
        run(tools,nav,w,base,route,tick,pos)

if __name__=='__main__':main()
