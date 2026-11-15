import math, json, heapq, random, pickle, os
from lightlag_surface import Surface, TERRAIN_CODES

class Planner:
    def __init__(self, world, rules):
        self.w=world; self.r=rules
        self.s=Surface(world['cell_m'],world['elevation_cm'],world['terrain'])
        self.slip={k:sum(v)/2 for k,v in rules['physics']['slip_base_ranges'].items()}
        self.nodes=[(float(x),float(y)) for y in range(0,401,5) for x in range(0,601,5)]
        self.graph=[[] for p in self.nodes]
        safe=[self.s.slope(*p)<.325 for p in self.nodes]
        for n,(x,y) in enumerate(self.nodes):
            if not safe[n]: continue
            i=n%121;j=n//121
            for di,dj in ((1,0),(0,1),(1,1),(-1,1)):
                ii=i+di;jj=j+dj
                if not(0<=ii<=120 and 0<=jj<=80):continue
                m=jj*121+ii
                if not safe[m]:continue
                xx,yy=self.nodes[m];dx=xx-x;dy=yy-y;dist=math.hypot(dx,dy);ux=dx/dist;uy=dy/dist
                probes=[self.s.sample(x+dx*f,y+dy*f) for f in (.0,.2,.4,.6,.8,1.)]
                if max(math.hypot(a[1],a[2]) for a in probes)>.335:continue
                for a,b,sign in ((n,m,1),(m,n,-1)):
                    wh=en=0
                    for h,gx,gy,c in probes:
                        ter=TERRAIN_CODES[c];grade=(gx*ux+gy*uy)*sign
                        sl=min(.95,self.slip[ter]+rules['physics']['slip_grade_gain'][ter]*max(0,grade))
                        wheel=dist/len(probes)/(1-sl)
                        wh+=wheel;en+=wheel*rules['physics']['drive_cost_per_wheel_m'][ter]+2*max(0,grade)*dist/len(probes)
                    # A small energy premium avoids costly hills and rock fields.
                    cost=wh/5+.025*en
                    self.graph[a].append((b,cost,wh/5,en))
        self.targets={'base':{'id':'base','x':world['base'][0],'y':world['base'][1],'value':0,'deadline_tick':None}}
        self.targets.update({t['id']:t for t in world['targets']})
        self.cache={}

    def node(self,p):
        x,y=p;i=round(x/5);j=round(y/5)
        options=[]
        for dj in range(-2,3):
            for di in range(-2,3):
                ii=i+di;jj=j+dj
                if 0<=ii<=120 and 0<=jj<=80:
                    n=jj*121+ii
                    if self.graph[n]:options.append((math.hypot(ii*5-x,jj*5-y),n))
        return min(options)[1]

    def tree(self,start):
        if start in self.cache:return self.cache[start]
        d=[math.inf]*len(self.nodes);tt=d.copy();ee=d.copy();prev=[-1]*len(d)
        d[start]=tt[start]=ee[start]=0.;q=[(0.,start)]
        while q:
            cost,n=heapq.heappop(q)
            if cost!=d[n]:continue
            for m,c,t,e in self.graph[n]:
                nc=cost+c
                if nc<d[m]:
                    d[m]=nc;tt[m]=tt[n]+t;ee[m]=ee[n]+e;prev[m]=n
                    heapq.heappush(q,(nc,m))
        result=(tt,ee,prev);self.cache[start]=result
        return result

    def path(self,start,end):
        a=self.node(start);b=self.node(end);tt,ee,prev=self.tree(a)
        if not math.isfinite(tt[b]):return [],math.inf,math.inf
        p=[];n=b
        while n!=a:p.append(self.nodes[n]);n=prev[n]
        p.reverse();p.append(tuple(end))
        return p,tt[b],ee[b]

    def matrix(self,position,excluded):
        ids=['here','base']+[i for i in self.targets if i!='base' and i not in excluded]
        coords=[position,tuple(self.w['base'])]+[(self.targets[i]['x'],self.targets[i]['y']) for i in ids[2:]]
        ns=[self.node(p) for p in coords]
        times=[];energy=[]
        for n in ns:
            t,e,_=self.tree(n)
            times.append([t[m] for m in ns]);energy.append([e[m] for m in ns])
        return ids,times,energy

    def optimize(self,position,tick,battery,excluded,old=None,iterations=18000):
        ids,tm,en=self.matrix(position,excluded);N=len(ids)
        target=[self.targets.get(i,{}) for i in ids]
        solar=[self.r['solar_peak']*getattr(self,'efficiency',.88)*math.sin(math.pi*(t+56)/532)-.15 for t in range(421)]
        integral=[0.]
        for v in solar:integral.append(integral[-1]+v)
        def evaluate(route,ret=False):
            time=float(tick+4);bat=battery;score=0.;cur=0;minbat=bat
            for nxt in route+[1]:
                dt=tm[cur][nxt]*1.025+(1.65 if nxt!=1 else 0)
                if not math.isfinite(dt):return (-1e4,999,0) if ret else -1e4
                tend=time+dt
                finish=getattr(self,'finish_tick',405)
                if tend>finish:return (-1e3-(tend-finish),tend,bat) if ret else -1e3-(tend-finish)
                gain=integral[min(420,int(tend))]-integral[min(420,int(time))]
                spent=en[cur][nxt]+(2 if nxt!=1 else 0)
                # Estimate battery continuously over each leg, including cap.
                bat=min(100.,bat+gain-spent)
                minbat=min(minbat,bat)
                if nxt!=1:
                    t=target[nxt];d=t['deadline_tick'];score+=t['value'] if d is None or tend<=d else t['late_value']
                time=tend;cur=nxt
            penalty=max(0,10-minbat)*.9
            value=score-penalty-.002*time
            return (value,time,bat) if ret else value
        rng=random.Random(730+int(tick));best=[];bestval=evaluate([])
        if old:
            trial=[ids.index(i) for i in old if i in ids]
            val=evaluate(trial)
            if val>bestval:best,bestval=trial,val
        current=best[:];cv=bestval
        for it in range(iterations):
            trial=current[:];unused=[n for n in range(2,N) if n not in trial]
            mode=rng.random()
            if mode<.43 and unused:
                trial.insert(rng.randrange(len(trial)+1),rng.choice(unused))
            elif mode<.60 and trial:
                trial.pop(rng.randrange(len(trial)))
            elif mode<.83 and len(trial)>1:
                a=rng.randrange(len(trial));b=rng.randrange(len(trial));v=trial.pop(a);trial.insert(b,v)
            elif len(trial)>1:
                a,b=sorted(rng.sample(range(len(trial)),2));trial[a:b+1]=reversed(trial[a:b+1])
            val=evaluate(trial)
            temp=.08+1.8*(1-(it%4000)/4000)**2
            if val>cv or rng.random()<math.exp(max(-700,(val-cv)/temp)):
                current=trial;cv=val
            if val>bestval:
                best=trial[:];bestval=val
            if it%4000==3999:current=best[:];cv=bestval
        # Polish with exhaustive profitable insertions and relocations; random
        # search otherwise sometimes misses a nearby newly discovered target.
        for sweep in range(12):
            improved=False
            candidates=[]
            for n in range(2,N):
                if n not in best:
                    for j in range(len(best)+1):
                        trial=best[:j]+[n]+best[j:]
                        val=evaluate(trial)
                        if val>bestval+1e-7:candidates.append((val,trial))
            for a in range(len(best)):
                shortened=best[:a]+best[a+1:]
                val=evaluate(shortened)
                if val>bestval+1e-7:candidates.append((val,shortened))
                for b in range(len(shortened)+1):
                    trial=shortened[:b]+[best[a]]+shortened[b:]
                    val=evaluate(trial)
                    if val>bestval+1e-7:candidates.append((val,trial))
            if not candidates:break
            bestval,best=max(candidates,key=lambda v:v[0])
        route=[ids[n] for n in best]
        return route,evaluate(best,True)

if __name__=='__main__':
    d=json.load(open('/app/mission.json'));p=Planner(d['world'],d['rules'])
    route,metrics=p.optimize(d['world']['base'],0,100,set(),iterations=120000)
    print('ROUTE',route,'metrics',metrics,flush=True)
    with open('/app/planner.pkl','wb') as f:pickle.dump(p,f)
