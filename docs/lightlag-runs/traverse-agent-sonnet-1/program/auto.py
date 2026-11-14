import json, math, heapq, sys, time, random
sys.path.insert(0,'/app')
from lightlag_surface import Surface, drive as sdrive, PHYSICS, TERRAIN_CODES
PH=PHYSICS
MID={'bedrock':.03,'regolith':.085,'sand':.25,'rocks':.18}
MAXT=420
def log(*a):
    print(*a,flush=True)

class Brain:
    def __init__(s,world,tools):
        s.tools=tools
        s.S=Surface(world['cell_m'],world['elevation_cm'],world['terrain'])
        s.base=tuple(world['base'])
        s.nx,s.ny=s.S.nx,s.S.ny
        s.build_edges()
        s.targets={}
        s.update_targets(world)
        s.done=set(); s.attempt={}  # id->exec tick
        s.fails={}
        s.cmds={}   # exec tick -> cmd
        s.est=(s.base[0],s.base[1]); s.est_T=0
        s.bias=0.0
        s.hist=[]   # (T, raw meas, est)
        s.plan=[]; s.eff=0.9
        s.last_exec=3
        s.meas={0:s.base}
        s.pending_plan=True
        s.battery=100
    def update_targets(s,world):
        for t in world['targets']:
            if t['id'] not in s.targets: s.targets[t['id']]=t
    # ---- edges
    def build_edges(s):
        S=s.S; c=S.cell
        dirs=[(1,0),(1,1),(0,1),(-1,1),(-1,0),(-1,-1),(0,-1),(1,-1)]
        s.dirs=dirs
        s.edges={}
        for lim in (0.30,0.34):
            E=[[None]*s.nx for _ in range(s.ny)]
            for j in range(s.ny):
                for i in range(s.nx):
                    out=[]
                    for di,dj in dirs:
                        i2,j2=i+di,j+dj
                        if not(0<=i2<s.nx and 0<=j2<s.ny): continue
                        x0,y0=i*c,j*c; L=c*math.hypot(di,dj); ux,uy=di*c/L,dj*c/L
                        n=int(L/1.25+0.5); ok=True; wheel=0; en=0
                        h0=S.elevation(x0,y0)
                        for k in range(n+1):
                            x=x0+ux*L*k/n; y=y0+uy*L*k/n
                            h,gx,gy,code=S.sample(min(x,S.width-1e-6),min(y,S.height-1e-6))
                            if math.hypot(gx,gy)>lim: ok=False;break
                            if k<n:
                                xm=x0+ux*L*(k+.5)/n; ym=y0+uy*L*(k+.5)/n
                                h,gx,gy,code=S.sample(min(xm,S.width-1e-6),min(ym,S.height-1e-6))
                                nm=TERRAIN_CODES[code]
                                gr=max(0,gx*ux+gy*uy)
                                sl=MID[nm]+PH['slip_grade_gain'][nm]*gr
                                w=(L/n)/(1-min(sl,.9)); wheel+=w; en+=w*PH['drive_cost_per_wheel_m'][nm]
                        if not ok: continue
                        h1=S.elevation(i2*c,j2*c)
                        en+=2*max(0,h1-h0)
                        out.append((i2,j2,wheel/5.0,en))
                    E[j][i]=out
            s.edges[lim]=E
    def node(s,p):
        return (min(s.nx-1,max(0,int(round(p[0]/s.S.cell)))),min(s.ny-1,max(0,int(round(p[1]/s.S.cell)))))
    def dijk(s,src,goal=None,lim=0.30):
        E=s.edges[lim]
        INF=1e18
        d={src:0.0}; tk={src:0.0}; en={src:0.0}; pr={}
        pq=[(0.0,src)]
        while pq:
            c,u=heapq.heappop(pq)
            if c>d.get(u,INF): continue
            if goal is not None and u==goal: break
            for i2,j2,t,e in E[u[1]][u[0]]:
                v=(i2,j2); nc=c+t+0.1*e
                if nc<d.get(v,INF):
                    d[v]=nc; tk[v]=tk[u]+t; en[v]=en[u]+e; pr[v]=u
                    heapq.heappush(pq,(nc,v))
        return d,tk,en,pr
    def path(s,src,goal):
        for lim in (0.30,0.34):
            d,tk,en,pr=s.dijk(src,goal,lim)
            if goal in d:
                p=[goal]
                while p[-1]!=src: p.append(pr[p[-1]])
                return p[::-1]
        return None
    # ---- model
    def model_drive(s,pos,h,m,bias=None):
        b=s.bias if bias is None else bias
        r=sdrive(s.S,PH,pos[0],pos[1],h+b,m,MID,0.0)
        return (r['x'],r['y']),r
    def solar(s,t):
        return 2.8*s.eff*math.sin(math.pi*(t+56)/(MAXT+112))
    def pred_pos(s):
        # position after all queued commands
        p=s.est
        for t in sorted(s.cmds):
            if t<=s.est_T: continue
            c=s.cmds[t]
            if c[0]=='drive': p,_=s.model_drive(p,c[1],c[2])
        return p
    # ---- telemetry
    def ingest(s,packets):
        for pk in packets:
            T=pk['tick']
            if T<=s.est_T and T!=0: continue
            if T==0: continue
            meas=tuple(pk['position'])
            s.meas[T]=meas
            p=s.est
            c=s.cmds.get(T)
            if c and c[0]=='drive':
                if pk['wheel_odometry']<c[2]-0.4:
                    # stopped -> queue cleared
                    for t in [t for t in s.cmds if t>T]: del s.cmds[t]
                    log('STOP at',T,pk['wheel_odometry'],c)
                    s.pending_plan=True
                p,_=s.model_drive(p,c[1],c[2])
            # blend
            K=0.4
            s.est=(p[0]+K*(meas[0]-p[0]),p[1]+K*(meas[1]-p[1]))
            s.est_T=T
            s.hist.append((T,meas,s.est,p))
            s.battery=pk['battery']
            if pk['charge']>0.3:
                base=2.8*math.sin(math.pi*(T+56)/(MAXT+112))
                s.eff=min(1.0,max(0.8,pk['charge']/base))
            sampled=set(pk.get('sampled_targets',[]))
            for tid in sampled:
                if tid not in s.done: s.done.add(tid); s.pending_plan=True
            for tid,et in list(s.attempt.items()):
                if et<=T and tid not in s.done:
                    del s.attempt[tid]; s.fails[tid]=s.fails.get(tid,0)+1
                    log('sample FAILED',tid,'fails',s.fails[tid]); s.pending_plan=True
                elif tid in s.done: s.attempt.pop(tid,None)
            if any(e.get('type')=='target_discovered' for e in pk.get('events',[])):
                try:
                    w=s.tools.map(); s.update_targets(w); s.pending_plan=True
                    log('events',pk['events'])
                except Exception as e: log('map err',e)
            s.update_bias()
    def update_bias(s):
        # use window of raw measurements vs model displacement with zero extra bias
        if len(s.hist)<14: return
        T2=s.hist[-1][0]; T1=T2-12
        if T1 not in s.meas or T2 not in s.meas: return
        # smoothed measured positions
        def sm(T): 
            ps=[s.meas[t] for t in (T-1,T,T+1) if t in s.meas and t<=T2]
            return (sum(p[0] for p in ps)/len(ps),sum(p[1] for p in ps)/len(ps))
        # model displacement: replay from sm(T1) with zero bias commands in (T1,T2]
        p0=sm(T1); p=p0; moved=0
        for t in range(T1+1,T2+1):
            c=s.cmds.get(t)
            if c and c[0]=='drive': p,_=s.model_drive(p,c[1],c[2],bias=0.0)
        vp=(p[0]-p0[0],p[1]-p0[1]); pm=sm(T2); vm=(pm[0]-p0[0],pm[1]-p0[1])
        if math.hypot(*vp)<25: return
        a=math.atan2(vm[1],vm[0])-math.atan2(vp[1],vp[0])
        a=(a+math.pi)%(2*math.pi)-math.pi
        a=math.degrees(a)
        if abs(a)>12: return
        s.bias=0.85*s.bias+0.15*a
    # ---- planning
    def active(s):
        return {k:v for k,v in s.targets.items() if k not in s.done and k not in s.attempt and s.fails.get(k,0)<3}
    def make_plan(s,P,t0):
        act=s.active()
        names=list(act)
        src=s.node(P)
        d0,tk0,en0,_=s.dijk(src)
        bn=s.node(s.base)
        tn={k:s.node((act[k]['x'],act[k]['y'])) for k in names}
        M={}
        for k in names+['B']:
            nd=tn[k] if k!='B' else bn
            d,tk,en,_=s.dijk(nd)
            for k2 in names+['B']:
                if k2==k: continue
                n2=tn[k2] if k2!='B' else bn
                if n2 in tk: M[(k,k2)]=(tk[n2],en[n2])
        start={}
        for k in names+['B']:
            n2=tn[k] if k!='B' else bn
            if n2 in tk0: start[k]=(tk0[n2],en0[n2])
        FAC=1.1; END=412
        def bat(t,e,n): 
            return 100+sum(s.solar(x) for x in range(int(s.est_T),int(t)))*0.97-0.15*(t-s.est_T)-e-2*n-0
        beam=[(0.0,t0,0.0,None,0,0.0,())]   # rank,t,en,last,mask,val,seq  (rank unused)
        best=((0.0,t0),())
        bat0=s.battery
        idx={k:i for i,k in enumerate(names)}
        for depth in range(30):
            cand={}
            for (_,t,e,last,mask,val,seq) in beam:
                for k in names:
                    if mask>>idx[k]&1: continue
                    leg=start.get(k) if last is None else M.get((last,k))
                    if leg is None: continue
                    t2=t+leg[0]*FAC+1.3; e2=e+leg[1]+2
                    back=M.get((k,'B'))
                    if back is None: continue
                    if t2+back[0]*FAC+2>END: continue
                    # battery check at end
                    if bat0-(e2+back[1])-0.15*(t2+back[0]*FAC-t0)+sum(s.solar(x) for x in range(int(t0),int(t2+back[0]*FAC)))*0.97<12: continue
                    tg=act[k]
                    dl=tg['deadline_tick']
                    v=tg['value'] if (dl is None or t2<=dl-1) else tg['late_value']
                    val2=val+v
                    m2=mask|1<<idx[k]
                    key=(m2,k)
                    rank=val2+0.12*(END-t2)
                    if key not in cand or cand[key][0]<rank:
                        cand[key]=(rank,t2,e2,k,m2,val2,seq+(k,))
            if not cand: break
            beam=sorted(cand.values(),key=lambda x:-x[0])[:250]
            for b in beam:
                if (b[5],-b[1])>(best[0][0],-best[0][1]) : best=((b[5],b[1]),b[6])
        s.plan=list(best[1])
        log('PLAN t0=%d val=%.1f end=%.0f'%(t0,best[0][0],best[0][1]),s.plan[:8],'n=',len(s.plan))
    # ---- control
    def next_command(s,t):
        et=max(t+4,s.last_exec+1)
        P=s.pred_pos()
        if s.pending_plan or (t%25==0) or (not s.plan and t%6==0):
            s.make_plan(P,et); s.pending_plan=False
        # goal
        while s.plan and (s.plan[0] in s.done or s.plan[0] in s.attempt): s.plan.pop(0)
        if s.plan:
            tg=s.targets[s.plan[0]]; G=(tg['x'],tg['y']); gid=s.plan[0]; tol=0.9
        else:
            G=s.base; gid=None; tol=1.5
        dx,dy=G[0]-P[0],G[1]-P[1]; dist=math.hypot(dx,dy)
        if dist<=tol:
            if gid:
                s.attempt[gid]=et; s.plan.pop(0); s.pending_plan=True
                return et,('sample',gid)
            return et,('wait',)
        # aim
        aim=G
        if dist>5.5 or not s.straight_ok(P,G):
            path=s.path(s.node(P),s.node(G))
            if path:
                aim=None
                for q in path[1:]:
                    qp=(q[0]*s.S.cell,q[1]*s.S.cell)
                    if math.hypot(qp[0]-P[0],qp[1]-P[1])>3.0: aim=qp;break
                if aim is None: aim=G
                # skip-ahead if straight to further node is ok
                best=aim
                for q in path[1:7]:
                    qp=(q[0]*s.S.cell,q[1]*s.S.cell)
                    if math.hypot(qp[0]-P[0],qp[1]-P[1])>3.0 and s.straight_ok(P,qp): best=qp
                aim=best
        dx,dy=aim[0]-P[0],aim[1]-P[1]; d=math.hypot(dx,dy)
        h=math.degrees(math.atan2(dy,dx))-s.bias
        want=min(d,5.0) if aim is G else min(5.0,d)
        m=min(5.0,want*1.1 if want<5 else 5.0)
        if aim is G:
            m=want
            for _ in range(3):
                pp,r=s.model_drive(P,h,max(0.1,m))
                gd=math.hypot(pp[0]-P[0],pp[1]-P[1])
                if gd>1e-6: m=min(5.0,m*want/gd)
        m=max(0.1,min(5.0,m))
        return et,('drive',round(h,2),round(m,2))
    def straight_ok(s,P,G):
        d=math.hypot(G[0]-P[0],G[1]-P[1])
        n=max(1,int(d/1.0))
        for k in range(1,n+1):
            x=P[0]+(G[0]-P[0])*k/n; y=P[1]+(G[1]-P[1])*k/n
            if not s.S.inside(x,y) or s.S.slope(x,y)>0.28: return False
        return True

def run(tools):
    world=tools.map()
    b=Brain(world,tools)
    log('built',len(b.targets))
    t=0
    import os
    if os.environ.get('RESUME'):
        out=tools.advance(1); t=out['current_tick']
        for _ in range(2):
            out=tools.advance(4); t=out['current_tick']
        L=tools.telemetry_log()
        last=L[-3:]
        b.est=(sum(p['position'][0] for p in last)/3,sum(p['position'][1] for p in last)/3)
        b.est_T=L[-1]['tick']; b.last_exec=t+3
        b.battery=L[-1]['battery']
        for p in L:
            for tid in p.get('sampled_targets',[]): b.done.add(tid)
            b.meas[p['tick']]=tuple(p['position'])
        log('resumed',t,b.est,b.est_T)
    while True:
        et,c=b.next_command(t)
        cmd={'action':c[0]}
        if c[0]=='drive': cmd.update(heading_deg=c[1],metres=c[2])
        try:
            ack=tools.uplink([cmd])
        except ValueError as e:
            log('uplink err',e,cmd); ack=tools.uplink([{'action':'wait'}]); c=('wait',)
        ex=ack[0].get('execute_tick',et) if isinstance(ack,list) else et
        b.cmds[ex]=c; b.last_exec=ex
        if c[0]=='sample': b.attempt[c[1]]=ex
        out=tools.advance(1)
        t=out['current_tick']
        b.ingest(out['packets'])
        if t%10==0: log('t',t,'est',tuple(round(x,1) for x in b.est),'pred',tuple(round(x,1) for x in b.pred_pos()),'bias %.2f bat %.1f done %d'%(b.bias,b.battery,len(b.done)),'cmd',c)
        if out['episode_complete'] or t>=MAXT: break
    log('FINISHED',t,len(b.done))

if __name__=='__main__':
    from lightlag_client import connect
    with connect("http://lightlag:8000/mcp") as tools:
        run(tools)
