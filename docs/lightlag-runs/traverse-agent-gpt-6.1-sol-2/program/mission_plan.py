import json, math, random, time, heapq
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.ndimage import distance_transform_edt
from lightlag_surface import Surface

class Planner:
    def __init__(self,w):
        self.w=w; self.s=Surface(w['cell_m'],w['elevation_cm'],w['terrain'])
        self.step=2.5; self.nx=241; self.ny=161
        self.points=np.array([(i*self.step,j*self.step) for j in range(self.ny) for i in range(self.nx)])
        a=np.array([self.s.sample(*p)[:3] for p in self.points])
        self.heights=a[:,0]; self.gx=a[:,1]; self.gy=a[:,2]
        self.slope=np.hypot(self.gx,self.gy)
        safe=(self.slope<.315).reshape(self.ny,self.nx)
        self.clearance=distance_transform_edt(safe)*self.step
        self.safe=(self.clearance.ravel()>=3.5)
        self.safe[:self.nx]=False; self.safe[-self.nx:]=False
        self.safe[::self.nx]=False; self.safe[self.nx-1::self.nx]=False
        codes=[self.s.sample(*p)[3] for p in self.points]
        slip=np.array([{'b':.03,'r':.085,'s':.25,'k':.18}[c] for c in codes])
        gain=np.array([{'b':.8,'r':1.5,'s':3.5,'k':1.2}[c] for c in codes])
        cost=np.array([{'b':.3,'r':.36,'s':.5,'k':.6}[c] for c in codes])
        rows=[]; cols=[]; vals=[]
        grid=np.arange(len(a)).reshape(self.ny,self.nx)
        for dx,dy in [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]:
            xx0=max(0,-dx);xx1=min(self.nx,self.nx-dx)
            yy0=max(0,-dy);yy1=min(self.ny,self.ny-dy)
            u=grid[yy0:yy1,xx0:xx1].ravel();v=grid[yy0+dy:yy1+dy,xx0+dx:xx1+dx].ravel()
            good=self.safe[u]&self.safe[v];u=u[good];v=v[good]
            dist=math.hypot(dx,dy)*self.step
            grade=(self.heights[v]-self.heights[u])/dist
            ss=(slip[u]+slip[v])/2+(gain[u]+gain[v])/2*np.maximum(0,grade)
            wheel=dist/np.clip(1-ss,.1,1)
            # Favor efficient ground slightly, and stay away from steep walls.
            val=wheel/5*(1+np.maximum(0,5-self.clearance.ravel()[v])*.03)
            rows.extend(u);cols.extend(v);vals.extend(val)
        self.graph=csr_matrix((vals,(rows,cols)),shape=(len(a),len(a)))
        self.cache={}
        self.update(w)

    def node(self,p):
        i=int(round(p[0]/self.step));j=int(round(p[1]/self.step))
        i=max(0,min(self.nx-1,i));j=max(0,min(self.ny-1,j))
        n=j*self.nx+i
        if self.safe[n]:return n
        for rad in range(1,10):
            near=[]
            for jj in range(max(0,j-rad),min(self.ny,j+rad+1)):
                for ii in range(max(0,i-rad),min(self.nx,i+rad+1)):
                    nn=jj*self.nx+ii
                    if self.safe[nn]:near.append(nn)
            if near:return min(near,key=lambda n:np.linalg.norm(self.points[n]-p))
        raise ValueError(('no safe node',p))

    def update(self,w):
        self.targets=[dict(id='base',x=w['base'][0],y=w['base'][1],value=0,deadline_tick=None,late_value=0)]+w['targets']
        self.ids={t['id']:i for i,t in enumerate(self.targets)}
        self.nodes=[self.node((t['x'],t['y'])) for t in self.targets]
        self.ds=[];self.preds=[]
        for n in self.nodes:
            if n not in self.cache:
                self.cache[n]=dijkstra(self.graph,directed=True,indices=n,return_predecessors=True)
            d,p=self.cache[n];self.ds.append(d);self.preds.append(p)
        self.D=np.array([[d[n] for n in self.nodes] for d in self.ds])

    def path(self,p,target):
        # Target-source reversed graph permits optimal current-position routes.
        idx=self.ids[target['id']];n=self.node(p)
        if ('rev',self.nodes[idx]) not in self.cache:
            self.cache['rev',self.nodes[idx]]=dijkstra(self.graph.T.tocsr(),directed=True,indices=self.nodes[idx],return_predecessors=True)
        d,pred=self.cache['rev',self.nodes[idx]]
        if not math.isfinite(d[n]):raise ValueError(('unreachable',p,target))
        nodes=[n]
        while n!=self.nodes[idx]:
            n=int(pred[n]);nodes.append(n)
            if n<0:raise ValueError('path error')
        return [tuple(self.points[n]) for n in nodes]+[(target['x'],target['y'])]

    def optimize(self,p,tick,done,iterations=45000,seedroute=None,limit=405):
        random.seed(416+tick)
        n=self.node(p)
        startdist=dijkstra(self.graph,directed=True,indices=n)[self.nodes]
        allowed=[i for i in range(1,len(self.targets)) if self.targets[i]['id'] not in done and math.isfinite(startdist[i]) and math.isfinite(self.D[i,0])]
        D=self.D;T=self.targets
        # Continuous travel estimates plus sampling/roundoff/occasional correction.
        def evaluate(route,detail=False):
            clock=tick+4;value=0.;prev=-1;out=[]
            for i in route:
                clock+=(startdist[i] if prev<0 else D[prev,i])*.99+1.8
                tt=T[i]
                val=tt['value'] if tt['deadline_tick'] is None or clock<=tt['deadline_tick'] else tt['late_value']
                value+=val;out.append((tt['id'],round(clock,1),val));prev=i
            end=clock+(startdist[0] if prev<0 else D[prev,0])*.99
            score=value-.009*(end-tick)-max(0,end-limit)*1.8
            if detail:return score,value,end,out
            return score
        current=[self.ids[x] for x in (seedroute or []) if x in self.ids and self.ids[x] in allowed]
        best=current[:];bs=cs=evaluate(current)
        for it in range(iterations):
            cand=current[:];op=random.random()
            unused=[x for x in allowed if x not in cand]
            if (op<.37 or not cand) and unused:
                x=random.choice(unused);cand.insert(random.randrange(len(cand)+1),x)
            elif op<.51 and cand:
                cand.pop(random.randrange(len(cand)))
            elif op<.72 and len(cand)>1:
                a,b=random.sample(range(len(cand)),2);x=cand.pop(a);cand.insert(b,x)
            elif op<.9 and len(cand)>1:
                a,b=sorted(random.sample(range(len(cand)),2));cand[a:b+1]=reversed(cand[a:b+1])
            elif cand and unused:
                cand[random.randrange(len(cand))]=random.choice(unused)
            ns=evaluate(cand)
            temp=1.1*(1-it/iterations)**2+.025
            if ns>cs or random.random()<math.exp(max(-700,(ns-cs)/temp)):
                current=cand;cs=ns
            if ns>bs:best=cand[:];bs=ns
        return [T[i]['id'] for i in best],evaluate(best,True)

if __name__=='__main__':
    w=json.load(open('/app/world.json'));p=Planner(w)
    route,score=p.optimize(w['base'],0,set(),120000)
    print('ROUTE',route,score,flush=True)
    json.dump(route,open('/app/route.json','w'))
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.figure(figsize=(15,10));plt.imshow(p.slope.reshape(p.ny,p.nx),origin='lower',extent=(0,600,0,400),vmin=0,vmax=.36,cmap='terrain');plt.colorbar()
    for t in p.targets:plt.text(t['x'],t['y'],t['id']+':'+str(int(t['value'])),fontsize=8)
    pos=w['base']
    for id in route+['base']:
        tt=p.targets[p.ids[id]];path=p.path(pos,tt);a=np.array([pos]+path);plt.plot(a[:,0],a[:,1],'r-',linewidth=1);pos=[tt['x'],tt['y']]
    plt.savefig('/app/route.png')
