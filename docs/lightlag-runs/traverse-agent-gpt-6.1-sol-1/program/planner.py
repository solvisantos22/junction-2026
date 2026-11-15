import math, heapq, json, random, time
from lightlag_surface import Surface, TERRAIN_CODES

class Planner:
    def __init__(self,w,r):
        self.w=w; self.r=r; self.s=Surface(w['cell_m'],w['elevation_cm'],w['terrain']); self.slip={k:sum(v)/2 for k,v in r['physics']['slip_base_ranges'].items()}
        self.nx=121; self.ny=81; self.graph=[[] for _ in range(self.nx*self.ny)]; self.cache={}
        self.points=[(i*5,j*5) for j in range(self.ny) for i in range(self.nx)]
        safe=[self.s.slope(*p)<.325 for p in self.points]
        for a,(x,y) in enumerate(self.points):
            if not safe[a]: continue
            i=a%self.nx; j=a//self.nx
            for di,dj in [(1,0),(0,1),(1,1),(-1,1)]:
                ni,nj=i+di,j+dj
                if not(0<=ni<self.nx and 0<=nj<self.ny):continue
                b=nj*self.nx+ni
                if not safe[b]:continue
                xx,yy=self.points[b]; length=math.hypot(xx-x,yy-y); ux=(xx-x)/length;uy=(yy-y)/length
                samples=[self.s.sample(x+(xx-x)*q/6,y+(yy-y)*q/6) for q in range(7)]
                if max(math.hypot(z[1],z[2]) for z in samples)>.325:continue
                for src,dst,sign in [(a,b,1),(b,a,-1)]:
                    wheel=energy=0
                    for h,gx,gy,c in samples:
                        name=TERRAIN_CODES[c]; grade=(gx*ux+gy*uy)*sign
                        slip=min(.90,self.slip[name]+r['physics']['slip_grade_gain'][name]*max(0,grade))
                        wh=length/7/(1-slip);wheel+=wh;energy+=wh*r['physics']['drive_cost_per_wheel_m'][name]+2*length/7*max(0,grade)
                    self.graph[src].append((dst,wheel/5,energy))
        self.rev=[[] for _ in self.graph]
        for a,edges in enumerate(self.graph):
            for b,t,e in edges:self.rev[b].append((a,t,e))

    def node(self,p):
        i=max(0,min(120,round(p[0]/5)));j=max(0,min(80,round(p[1]/5)));a=j*121+i
        if self.graph[a]:return a
        return min((b for b in range(len(self.graph)) if self.graph[b]),key=lambda b:math.dist(p,self.points[b]))

    def field(self,p):
        goal=self.node(p)
        if goal in self.cache:return self.cache[goal]
        d=[float('inf')]*len(self.graph); energy=d.copy();nxt=[-1]*len(d);d[goal]=0;energy[goal]=0;hq=[(0,goal)]
        while hq:
            cost,a=heapq.heappop(hq)
            if cost>d[a]+1e-8:continue
            for b,t,e in self.rev[a]:
                nd=cost+t+.025*e
                if nd<d[b]:d[b]=nd;energy[b]=energy[a]+e;nxt[b]=a;heapq.heappush(hq,(nd,b))
        # recover real drive time from weighted cost
        tt=[v-.025*en if math.isfinite(v) else v for v,en in zip(d,energy)]
        self.cache[goal]=(tt,energy,nxt);return self.cache[goal]

    def matrices(self,targets):
        pts=[self.w['base']]+[(t['x'],t['y']) for t in targets];n=len(pts)
        tm=[[0]*n for _ in pts];en=[[0]*n for _ in pts]
        for j,p in enumerate(pts):
            ts,es,_=self.field(p)
            for i,q in enumerate(pts):
                a=self.node(q);tm[i][j]=ts[a];en[i][j]=es[a]
        return tm,en

def optimize(pl,targets,start_pos,start_tick=0,battery=100,seconds=10,seed_ids=None):
    tm,en=pl.matrices(targets);n=len(targets); st=[];se=[]
    for p in [pl.w['base']]+[(t['x'],t['y']) for t in targets]:
        ts,es,_=pl.field(p);a=pl.node(start_pos);st.append(ts[a]);se.append(es[a])
    cap=pl.r['max_ticks']-13
    def evaluate(route,detail=False):
        tick=start_tick+4;bat=battery;score=0;prev=None;low=100;log=[]
        for k in route+[0]:
            dt=(st[k] if prev is None else tm[prev][k])*1.035
            energy=se[k] if prev is None else en[prev][k]
            if not math.isfinite(dt):return (-1e5,0,0) if detail else -1e5
            duration=dt+(2.2 if k else 0)
            charge=2.8*.85*math.sin(math.pi*(tick+duration/2+56)/532)*duration
            bat=min(100,bat+charge-energy-.15*duration-(2 if k else 0))
            low=min(low,bat);tick+=duration
            if k:
                t=targets[k-1];value=t['value'] if t['deadline_tick'] is None or tick<=t['deadline_tick'] else t['late_value'];score+=value
                log.append((t['id'],round(tick,1),value,round(bat,1)))
            prev=k
        val=score-.006*(tick-start_tick)-max(0,tick-cap)*1.8-max(0,14-low)*1.5
        return (val,tick,log) if detail else val
    rng=random.Random(83+start_tick);best=[i+1 for id in (seed_ids or []) for i,t in enumerate(targets) if t['id']==id];bestv=evaluate(best);route=best.copy();v=bestv;end=time.monotonic()+seconds;it=0
    while time.monotonic()<end:
        it+=1;prop=route.copy();u=rng.random();unused=[i for i in range(1,n+1) if i not in prop]
        if u<.40 and unused:prop.insert(rng.randrange(len(prop)+1),rng.choice(unused))
        elif u<.62 and prop:prop.pop(rng.randrange(len(prop)))
        elif u<.87 and len(prop)>1:
            a=rng.randrange(len(prop));b=rng.randrange(len(prop));prop.insert(b,prop.pop(a))
        elif len(prop)>1:
            a,b=sorted(rng.sample(range(len(prop)),2));prop[a:b+1]=reversed(prop[a:b+1])
        nv=evaluate(prop);temp=.12+1.5*(1-(it%18000)/18000)**3
        if nv>v or rng.random()<math.exp(max(-700,(nv-v)/temp)):route,v=prop,nv
        if nv>bestv:best,bestv=prop,nv
        if it%18000==0:route=best.copy();v=bestv
    print('PLAN',evaluate(best,True),flush=True)
    return [targets[k-1]['id'] for k in best]

if __name__=='__main__':
    w=json.load(open('/app/world.json'));r=json.load(open('/app/rules.json'));p=Planner(w,r)
    route=optimize(p,w['targets'],w['base'],seconds=35);print(route)
    json.dump(route,open('/app/route.json','w'))
