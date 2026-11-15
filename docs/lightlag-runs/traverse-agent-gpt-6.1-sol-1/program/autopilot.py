import json, math, time, traceback
from lightlag_client import connect
from lightlag_surface import drive,TERRAIN_CODES
from planner import Planner,optimize

def matmul(a,b):return [[sum(x*y for x,y in zip(row,col)) for col in zip(*b)] for row in a]
def trans(a):return list(map(list,zip(*a)))

class Pilot:
    def __init__(self,tools):
        self.tools=tools;self.w=tools.map();self.r=tools.rules();self.pl=Planner(self.w,self.r);self.slip=self.pl.slip.copy()
        self.tick=0;self.sched={};self.state=[*self.w['base'],0.];self.P=[[0.,0.,0.],[0.,0.,0.],[0.,0.,math.radians(3)**2]];self.ft=0;self.bat=100;self.sampled=set();self.pending={};self.route=json.load(open('/app/route.json'));self.target=None;self.last_replan=0;self.total=0;self.home=False
        self.log=open('/app/flight.jsonl','a',buffering=1)

    def motion(self,state,cmd):
        if cmd.get('action')!='drive':return state.copy(),None
        out=drive(self.pl.s,self.r['physics'],*state[:2],cmd['heading_deg']+math.degrees(state[2]),cmd['metres'],self.slip)
        return [out['x'],out['y'],state[2]],out

    def prop(self,state,P,cmd):
        ns,out=self.motion(state,cmd)
        if out is None:return ns,[row.copy() for row in P],out
        pert=state.copy();pert[2]+=.001;shift,_=self.motion(pert,cmd)
        J=[[1,0,(shift[0]-ns[0])/.001],[0,1,(shift[1]-ns[1])/.001],[0,0,1]]
        pp=matmul(matmul(J,P),trans(J));dx=ns[0]-state[0];dy=ns[1]-state[1];length=max(.1,math.hypot(dx,dy));ux=dx/length;uy=dy/length
        along=(.025*cmd['metres'])**2+.002;across=(math.radians(1.5)*length)**2+.002
        pp[0][0]+=along*ux*ux+across*uy*uy;pp[1][1]+=along*uy*uy+across*ux*ux;pp[0][1]+=(along-across)*ux*uy;pp[1][0]=pp[0][1];pp[2][2]+=math.radians(.2)**2
        return ns,pp,out

    def ingest(self,p):
        if p['tick']<=self.ft:return
        for t in range(self.ft+1,p['tick']+1):
            old=self.state.copy();cmd=self.sched.get(t,{'action':'wait'});self.state,self.P,out=self.prop(self.state,self.P,cmd)
        if out and p['wheel_odometry']>1 and not out['stop']:
            name=self.pl.s.terrain(*old[:2]);err=(out['ground']-p['visual_odometry'])/p['wheel_odometry'];lo,hi=self.r['physics']['slip_base_ranges'][name]
            self.slip[name]=max(lo,min(hi,self.slip[name]+.10*err))
        for axis in (0,1):
            residual=p['position'][axis]-self.state[axis];var=self.P[axis][axis]+1.;K=[self.P[i][axis]/var for i in range(3)];row=self.P[axis].copy()
            for i in range(3):
                self.state[i]+=K[i]*residual
                for j in range(3):self.P[i][j]-=K[i]*row[j]
        self.ft=p['tick'];self.bat=p['battery'];self.sampled=set(p['sampled_targets'])
        for event in p['events']:
            print('EVENT',p['tick'],event,flush=True)
            if 'target_discovered' in str(event):
                self.w=self.tools.map();self.pl.w=self.w
            if 'stop' in str(event) or 'tilt' in str(event):
                # All commands queued at a stop are cancelled by the simulator.
                for t in list(self.sched):
                    if t>p['tick']:self.sched[t]={'action':'wait'}
        for id,t in list(self.pending.items()):
            if p['tick']>=t:
                if id not in self.sampled:
                    print('SAMPLE RETRY',id,flush=True)
                    if id not in self.route:self.route.insert(0,id)
                del self.pending[id]
        self.log.write(json.dumps({'packet':p,'estimate':self.state,'slip':self.slip})+'\n')

    def forecast(self,through):
        s=self.state.copy();b=self.bat
        for t in range(self.ft+1,through+1):
            s,out=self.motion(s,self.sched.get(t,{'action':'wait'}));b=min(100,b+2.8*.88*math.sin(math.pi*(t+56)/532))-.15-(out['energy'] if out else (2 if self.sched.get(t,{}).get('action')=='sample' else 0))
        return s,b

    def visible(self,p,q):
        length=math.dist(p,q);n=max(1,math.ceil(length/.7))
        return all(self.pl.s.slope(p[0]+(q[0]-p[0])*i/n,p[1]+(q[1]-p[1])*i/n)<.322 for i in range(n+1))

    def waypoint(self,pos,goal):
        if math.dist(pos,goal)<17 and self.visible(pos,goal):return goal
        _,_,nxt=self.pl.field(goal);a=self.pl.node(pos);path=[]
        for i in range(14):
            path.append(self.pl.points[a]);a=nxt[a]
            if a<0:break
        best=path[0]
        for q in path:
            if math.dist(pos,q)>22:break
            if self.visible(pos,q):best=q
        if math.dist(pos,best)<.5 and len(path)>1:best=path[1]
        return best

    def command(self,s,b):
        self.route=[id for id in self.route if id not in self.sampled and id not in self.pending]
        goalid=self.route[0] if self.route else 'BASE';targets={t['id']:t for t in self.w['targets']}
        goal=self.w['base'] if goalid=='BASE' else [targets[goalid]['x'],targets[goalid]['y']]
        if goalid!=self.target:
            self.target=goalid;print('GOAL',self.tick,goalid,'position',[round(x,2) for x in s[:2]],'battery',round(b,1),'bias',round(math.degrees(s[2]),2),flush=True)
        distance=math.dist(s[:2],goal)
        if distance<(.55 if goalid!='BASE' else .65):
            if goalid=='BASE':self.home=True;return {'action':'wait'}
            self.pending[goalid]=self.tick+4;self.route.pop(0);return {'action':'sample'}
        waypoint=self.waypoint(s[:2],goal);dx=waypoint[0]-s[0];dy=waypoint[1]-s[1];heading=math.degrees(math.atan2(dy,dx))-math.degrees(s[2]);m=min(5,max(.05,math.hypot(dx,dy)/.88))
        # Invert the model locally to compensate slip and cross-slope drift.
        for _ in range(3):
            cmd={'action':'drive','heading_deg':heading%360,'metres':m};ns,out=self.motion(s,cmd);vx=ns[0]-s[0];vy=ns[1]-s[1];travel=math.hypot(vx,vy)
            if travel<.02:break
            heading+=math.degrees(math.atan2(dy,dx)-math.atan2(vy,vx));heading=(heading+180)%360-180
            m=max(.03,min(5,m*math.hypot(dx,dy)/travel))
        cmd={'action':'drive','heading_deg':heading%360,'metres':m};ns,out=self.motion(s,cmd)
        if out['stop']:
            print('PREDICTED STOP',self.tick,s,goalid,waypoint,flush=True)
            # A shorter drive can stay safely inside the traversable corridor.
            cmd['metres']=min(m,max(.1,out['wheel']*.7))
        if out['energy']>b+1.0-10:
            print('CHARGING',self.tick,round(b,1),flush=True);return {'action':'wait'}
        self.home=False;return cmd

    def replan(self):
        s,b=self.forecast(self.tick+3);remaining=[t for t in self.w['targets'] if t['id'] not in self.sampled and t['id'] not in self.pending]
        # Keep the next goal stable while revisiting the remainder of the tour.
        print('REPLAN',self.tick,'battery',b,flush=True)
        self.route=optimize(self.pl,remaining,s[:2],self.tick,b,seconds=7,seed_ids=self.route)
        self.last_replan=self.tick
        json.dump({'tick':self.tick,'route':self.route},open('/app/current_plan.json','w'))

    def run(self):
        while self.tick<420:
            if self.tick in (55,105,155,205,255,305,350):self.replan()
            # Commit only the next unreserved execution slot, keeping a four-tick horizon.
            if self.tick+4<=420:
                s,b=self.forecast(self.tick+3);cmd=self.command(s,b)
                ack=self.tools.uplink([cmd]);et=ack[0]['execute_tick'];self.sched[et]=cmd
            out=self.tools.advance(1);self.tick=out['current_tick']
            for packet in out['packets']:self.ingest(packet)
            if self.tick%10==0:print('STATUS',self.tick,'estimate',[round(x,2) for x in self.state],'bat',round(self.bat,1),'samples',len(self.sampled),'remaining',self.route,flush=True)
            if out['episode_complete']:
                print('COMPLETE',json.dumps(out),flush=True);break
        print('FINAL LOG',json.dumps(self.tools.telemetry_log()[-5:]),flush=True)

if __name__=='__main__':
    with connect('http://lightlag:8000/mcp') as tools:
        pilot=Pilot(tools)
        try:pilot.run()
        except Exception:
            traceback.print_exc()
            json.dump({'tick':pilot.tick,'schedule':pilot.sched,'route':pilot.route,'state':pilot.state,'P':pilot.P,'ft':pilot.ft,'battery':pilot.bat,'pending':pilot.pending,'sampled':list(pilot.sampled),'slip':pilot.slip},open('/app/recovery.json','w'))
            raise
