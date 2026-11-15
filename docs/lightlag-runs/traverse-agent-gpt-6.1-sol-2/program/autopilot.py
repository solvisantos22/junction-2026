import json,math,time,traceback,sys,os,pickle
import numpy as np
from lightlag_client import connect
from lightlag_surface import Surface,drive,PHYSICS
from mission_plan import Planner

NAMES=['bedrock','regolith','sand','rocks']

class Filter:
    def __init__(self,s,packet):
        self.s=s;self.x=np.array(list(packet['position'])+[0,.03,.085,.25,.18],float)
        self.P=np.diag([.0001,.0001,25/3,.04**2/12,.07**2/12,.2**2/12,.12**2/12])
        self.tick=0;self.battery=100.;self.lastpacket=packet
    def result(self,x,c):
        if c['action']!='drive':return dict(x=x[0],y=x[1],ground=0.,energy=0.,stop=None,wheel=0)
        return drive(self.s,PHYSICS,x[0],x[1],c['heading_deg']+x[2],c['metres'],dict(zip(NAMES,x[3:])))
    def predict(self,x,c):
        y=x.copy();r=self.result(x,c);y[:2]=[r['x'],r['y']];return y,r
    def update(self,p,c):
        x=self.x;oldbattery=self.battery
        xp,r=self.predict(x,c)
        # Joint prediction includes visual odometry and drive energy.
        mean=np.r_[xp,r['ground'],r['energy']]
        J=np.zeros((9,7));eps=[.05,.05,.2,.002,.002,.002,.002]
        for j,e in enumerate(eps):
            xx=x.copy();xx[j]+=e;yy,rr=self.predict(xx,c)
            J[:,j]=(np.r_[yy,rr['ground'],rr['energy']]-mean)/e
        V=J@self.P@J.T
        Q=np.zeros((9,9))
        if c['action']=='drive':
            # Per-command heading noise and uniform slip noise.
            g=J[:,2].copy();g[2]=0;Q+=np.outer(g,g)*1.5**2
            g=J[:,3:7].sum(axis=1);g[3:7]=0;Q+=np.outer(g,g)*(.02**2/3)
            Q[0,0]+=.045**2;Q[1,1]+=.045**2;Q[2,2]+=.2**2
            Q[7,7]+=.02**2;Q[8,8]+=.08**2
        V+=Q
        indices=[0,1];obs=list(p['position']);R=[1.,1.]
        stopped=c['action']=='drive' and p['wheel_odometry']<c['metres']-.05
        if c['action']=='drive' and not stopped:
            indices+=[7,8]
            spent=min(100.,oldbattery+p['charge'])-.15-p['battery']
            obs+=[p['visual_odometry'],spent]
            R+=[max(.06,p['visual_odometry']*.05)**2,.15**2]
        innov=np.array(obs)-mean[indices]
        if stopped:
            V[0,0]+=2;V[1,1]+=2
        S=V[np.ix_(indices,indices)]+np.diag(R)
        K=V[:7,indices]@np.linalg.inv(S)
        self.x=mean[:7]+K@innov
        self.P=V[:7,:7]-K@V[indices,:7]
        self.P=(self.P+self.P.T)/2
        # Only the published parameter ranges are used.
        for k,(lo,hi) in enumerate([[.01,.05],[.05,.12],[.15,.35],[.12,.24]],3):
            self.x[k]=np.clip(self.x[k],lo,hi)
        self.x[2]=np.clip(self.x[2],-12,12)
        self.tick=p['tick'];self.battery=p['battery'];self.lastpacket=p
        return stopped

class Pilot:
    def __init__(self,t):
        if os.path.exists('/app/checkpoint.pkl'):
            self.__dict__.update(pickle.load(open('/app/checkpoint.pkl','rb')))
            self.t=t;self.pl=Planner(self.w);self.s=self.pl.s
            self.log=open('/app/flight.jsonl','a',buffering=1)
            print('RESUMED',self.tick,flush=True)
            return
        self.t=t;self.w=t.map();self.rules=t.rules();self.pl=Planner(self.w);self.s=self.pl.s
        packets=t.telemetry_log()
        self.f=Filter(self.s,packets[0]);self.commands={4:{'action':'wait'}};self.sent={4:0};self.tick=1
        self.done=set();self.pending={};self.route=json.load(open('/app/route.json'))
        self.optimized=0;self.discovered=False;self.lasttarget=None;self.samples=[]
        self.log=open('/app/flight.jsonl','a',buffering=1)
        self.complete=False;self.returns=False;self.eff=.9
        if len(packets)>1:raise ValueError('Use saved controller for resume')

    def forecast(self):
        x=self.f.x.copy();bat=self.f.battery
        end=max(self.tick+3,max(self.commands,default=0))
        for k in range(self.f.tick+1,end+1):
            c=self.commands.get(k,{'action':'wait'})
            x,r=self.f.predict(x,c)
            charge=2.8*self.eff*math.sin(math.pi*(k+56)/532)
            bat=min(100,bat+charge)-.15-r['energy']-(2 if c['action']=='sample' else 0)
        return x,bat,end

    def safe_line(self,a,b,margin=1.7):
        dist=math.dist(a,b)
        for frac in np.linspace(0,1,max(2,int(dist/.8)+1)):
            x=a[0]+frac*(b[0]-a[0]);y=a[1]+frac*(b[1]-a[1])
            if not self.s.inside(x,y) or self.s.slope(x,y)>.305:return False
            # Side clearance protects against residual localization uncertainty.
            if dist>0:
                dx=(b[1]-a[1])/dist*margin;dy=-(b[0]-a[0])/dist*margin
                for xx,yy in [(x+dx,y+dy),(x-dx,y-dy)]:
                    if not self.s.inside(xx,yy) or self.s.slope(xx,yy)>.325:return False
        return True

    def steer(self,x,target):
        pos=x[:2];goal=(target['x'],target['y'])
        path=self.pl.path(pos,target)
        # Follow the cost-aware path, smoothing only local grid stair steps.
        waypoint=path[0]
        for p in path:
            d=math.dist(pos,p)
            if d>13:break
            if self.safe_line(pos,p):waypoint=p
        if math.dist(pos,goal)<13 and self.safe_line(pos,goal):waypoint=goal
        dist=math.dist(pos,waypoint)
        if dist<.05:
            waypoint=path[min(2,len(path)-1)];dist=math.dist(pos,waypoint)
        heading=math.degrees(math.atan2(waypoint[1]-pos[1],waypoint[0]-pos[0]))-x[2]
        c={'action':'drive','heading_deg':heading,'metres':min(5,max(.02,dist/0.85))}
        for _ in range(4):
            y,r=self.f.predict(x,c)
            moved=y[:2]-pos
            want=np.array(waypoint)-pos
            if np.linalg.norm(moved)<.01:break
            err=math.atan2(want[1],want[0])-math.atan2(moved[1],moved[0])
            err=(err+math.pi)%(2*math.pi)-math.pi
            c['heading_deg']+=math.degrees(err)
            c['metres']=min(5,max(.02,c['metres']*dist/np.linalg.norm(moved)))
        y,r=self.f.predict(x,c)
        if r['stop']:
            # Shorter wheel step is preferable to touching an unsafe wall.
            for factor in [.65,.4,.2]:
                cc=dict(c,metres=c['metres']*factor);_,rr=self.f.predict(x,cc)
                if not rr['stop']:return cc,rr
            print('PREDICTED STOP',self.tick,pos,target['id'],flush=True)
            return {'action':'wait'},{'energy':0}
        return c,r

    def replan(self,x,end):
        locked=self.done|set(self.pending)
        route,stats=self.pl.optimize(x[:2],end-3,locked,iterations=50000,seedroute=self.route,limit=403)
        self.route=route;self.optimized=self.tick
        print('PLAN',self.tick,route,stats,flush=True)

    def command(self):
        x,bat,end=self.forecast()
        if self.discovered or self.tick-self.optimized>=35:
            if self.discovered:
                self.w=self.t.map();self.pl.update(self.w);self.discovered=False
            self.replan(x,end)
        self.route=[i for i in self.route if i not in self.done and i not in self.pending]
        # Check the shortest return on every command, including the queued horizon.
        base=self.pl.targets[0]
        n=self.pl.node(x[:2])
        if ('rev',self.pl.nodes[0]) not in self.pl.cache:self.pl.path(x[:2],base)
        returntime=self.pl.cache['rev',self.pl.nodes[0]][0][n]
        if end+returntime+10>=419:
            if not self.returns:print('RETURN COMMITTED',self.tick,returntime,bat,flush=True)
            self.returns=True;self.route=[]
        id=self.route[0] if self.route and not self.returns else 'base'
        target=self.pl.targets[self.pl.ids[id]]
        if id!=self.lasttarget:
            print('TARGET',self.tick,id,'pos',x[:2].round(2).tolist(),'bat',round(bat,1),'bias',round(x[2],2),'slip',x[3:].round(3).tolist(),flush=True)
            self.lasttarget=id
        distance=math.dist(x[:2],(target['x'],target['y']))
        if id=='base' and distance<.85:
            return {'action':'wait'},None
        if id!='base' and distance<.32:
            return {'action':'sample'},id
        c,r=self.steer(x,target)
        charge=2.8*self.eff*math.sin(math.pi*(end+1+56)/532)
        if bat+charge-.15-r['energy']<15:
            print('ENERGY WAIT',self.tick,round(bat,2),flush=True)
            return {'action':'wait'},None
        return c,None

    def step(self):
        c,sample=self.command()
        acks=self.t.uplink([c]);ack=acks[0];k=ack['execute_tick']
        self.commands[k]=c;self.sent[k]=self.tick
        if sample:
            self.pending[sample]=k
            print('SAMPLE QUEUED',self.tick,k,sample,flush=True)
        out=self.t.advance(1);self.tick=out['current_tick'];self.complete=out['episode_complete']
        for p in out['packets']:
            k=p['tick'];cmd=self.commands.get(k,{'action':'wait'})
            stopped=self.f.update(p,cmd)
            if p['charge']:
                self.eff=p['charge']/(2.8*math.sin(math.pi*(k+56)/532))
            self.done.update(p['sampled_targets'])
            for id,kt in list(self.pending.items()):
                if k>=kt:
                    del self.pending[id]
                    if id not in self.done:
                        print('SAMPLE FAILED',id,k,p,flush=True)
                        self.route.insert(0,id)
                    else:
                        self.samples.append((id,k));print('COLLECTED',id,k,'battery',p['battery'],flush=True)
            if stopped:
                print('SAFETY STOP',p,flush=True)
                for kk in list(self.commands):
                    if kk>k and self.sent[kk]<k:
                        self.commands[kk]={'action':'wait'}
                        for id,kt in list(self.pending.items()):
                            if kt==kk:del self.pending[id];self.route.insert(0,id)
                self.optimized=-100
            for ev in p['events']:
                if 'discover' in str(ev):
                    self.discovered=True;print('DISCOVERY',self.tick,ev,flush=True)
            self.log.write(json.dumps({'received':self.tick,'packet':p,'estimate':self.f.x.tolist(),'std':np.sqrt(np.diag(self.f.P)).tolist(),'command':cmd})+'\n')
            if not p['alive']:raise RuntimeError('ROVER LOST')
        if self.tick%20==0:
            print('STATUS',self.tick,'filter_tick',self.f.tick,'pos',self.f.x[:2].round(2).tolist(),'battery',round(self.f.battery,2),'collected',len(self.done),'route',self.route,flush=True)
        state={k:v for k,v in self.__dict__.items() if k not in ['t','pl','s','log']}
        with open('/app/checkpoint.pkl.tmp','wb') as file:pickle.dump(state,file)
        os.replace('/app/checkpoint.pkl.tmp','/app/checkpoint.pkl')
        return out

def main():
    import pickle
    with connect('http://lightlag:8000/mcp') as t:
        pilot=Pilot(t)
        while not pilot.complete:
            pilot.step()
        final=t.telemetry_log()
        json.dump(final,open('/app/final_telemetry.json','w'))
        json.dump(t.map(),open('/app/final_world.json','w'))
        print('MISSION COMPLETE',pilot.tick,'sampled',pilot.done,'final_received',final[-1],flush=True)

if __name__=='__main__':
    try:main()
    except Exception:
        traceback.print_exc()
        raise
