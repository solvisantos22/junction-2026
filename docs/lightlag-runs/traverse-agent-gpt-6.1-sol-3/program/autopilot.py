import math, json, pickle, sys, time
from planner import Planner
from lightlag_client import connect
from lightlag_surface import drive, TERRAIN_CODES

def mm(a,b):return [[sum(x*y for x,y in zip(row,col)) for col in zip(*b)] for row in a]
def tr(a):return list(map(list,zip(*a)))

class Controller:
    def __init__(self,tools):
        self.r=tools.rules();self.w=tools.map();self.p=Planner(self.w,self.r)
        self.x=list(self.w['base'])+[0.];self.P=[[0.,0.,0.],[0.,0.,0.],[0.,0.,8.33]]
        self.slip=self.p.slip.copy();self.svar={k:((v[1]-v[0])/3.46)**2 for k,v in self.r['physics']['slip_base_ranges'].items()}
        self.tick=0;self.etick=0;self.cmd={};self.taken=set();self.planned=set();self.route=[];self.paths={};self.battery=100.;self.last_packet=None
        self.credited=0.;self.pending={};self.discover=False;self.done=False;self.lastopt=-100
        self.route,met=self.p.optimize(self.x[:2],0,100,set(),iterations=160000)
        print('INITIAL ROUTE',self.route,met,flush=True)

    def motion(self,x,cmd):
        if not cmd or cmd['action']!='drive':return x[:],None
        z=drive(self.p.s,self.r['physics'],x[0],x[1],cmd['heading_deg']+x[2],cmd['metres'],self.slip)
        return [z['x'],z['y'],x[2]],z

    def assimilate(self,packet):
        t=packet['tick']
        if t<=self.etick:return
        cmd=self.cmd.get(t)
        old=self.x[:];pred,z=self.motion(old,cmd)
        if z and z['wheel']>1 and not z['stop']:
            name=self.p.s.terrain(*old[:2]);endname=self.p.s.terrain(*pred[:2])
            if name==endname:
                nominal=z['ground'];self.slip[name]+=.002
                _,zz=self.motion(old,cmd);self.slip[name]-=.002
                der=(zz['ground']-nominal)/.002
                var=self.svar[name];noise=(nominal*.05)**2+.003
                K=var*der/(der*der*var+noise)
                self.slip[name]+=K*(packet['visual_odometry']-nominal)
                lo,hi=self.r['physics']['slip_base_ranges'][name]
                self.slip[name]=max(lo,min(hi,self.slip[name]))
                self.svar[name]=max(.000005,(1-K*der)*var)
                pred,z=self.motion(old,cmd)
        F=[[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]]
        if z:
            for j,delta in enumerate((.05,.05,.1)):
                xx=old[:];xx[j]+=delta;pp,_=self.motion(xx,cmd)
                for i in range(2):
                    v=(pp[i]-pred[i])/delta
                    F[i][j]=max(-.4,min(.4,v)) if i!=j else max(.6,min(1.4,v))
        P=mm(mm(F,self.P),tr(F))
        for i,q in enumerate((.018 if z else .00001,.018 if z else .00001,.04 if z else .00001)):P[i][i]+=q
        self.x=pred
        for j in (0,1):
            residual=packet['position'][j]-self.x[j]
            gain=[P[i][j]/(P[j][j]+1.) for i in range(3)]
            self.x=[v+gain[i]*residual for i,v in enumerate(self.x)]
            row=P[j][:]
            P=[[P[i][k]-gain[i]*row[k] for k in range(3)] for i in range(3)]
        self.P=P;self.etick=t;self.battery=packet['battery'];self.last_packet=packet
        if 5<packet['battery']<90 and packet['charge']>0:
            self.p.efficiency=packet['charge']/(self.r['solar_peak']*math.sin(math.pi*(t+56)/532))
        for ev in packet['events']:
            if ev.get('type')!='command_executed':print('EVENT',t,ev,flush=True)
            if 'target_discovered' in str(ev):self.discover=True
        new=set(packet['sampled_targets'])-self.taken
        for i in new:
            target=self.p.targets[i];d=target['deadline_tick'];value=target['value'] if d is None or t<=d else target['late_value'];self.credited+=value
            print('SAMPLED',i,'tick',t,'credit',value,'total',self.credited,'battery',packet['battery'],flush=True)
        self.taken.update(packet['sampled_targets'])
        if cmd and cmd['action']=='sample':
            i=self.pending.get(t)
            if i and i not in self.taken:
                print('SAMPLE MISSED',i,'estimate',self.x,flush=True)
                self.planned.discard(i);self.lastopt=-100
        if z and z['stop']:
            print('PREDICTED STOP',t,z,flush=True)
        if any('stop' in str(ev) or 'tilt' in str(ev) for ev in packet['events']):
            # Safety stops clear the queue; reserved execution ticks remain unavailable.
            for tt in list(self.cmd):
                if tt>t:self.cmd[tt]={'action':'wait'}
            self.paths={};self.lastopt=-100

    def forecast(self,end):
        x=self.x[:];bat=self.battery
        for t in range(self.etick+1,end+1):
            bat=min(100,bat+self.r['solar_peak']*getattr(self.p,'efficiency',.88)*math.sin(math.pi*(t+56)/532))-.15
            x,z=self.motion(x,self.cmd.get(t))
            if z:bat-=z['energy']
            if self.cmd.get(t,{}).get('action')=='sample':bat-=2
        return x,bat

    def safe_line(self,a,b):
        d=math.dist(a,b);steps=max(1,math.ceil(d/.6))
        for n in range(steps+1):
            f=n/steps;x=a[0]+(b[0]-a[0])*f;y=a[1]+(b[1]-a[1])*f
            if not self.p.s.inside(x,y) or self.p.s.slope(x,y)>.332:return False
        return True

    def waypoint(self,x,goal,key):
        if key not in self.paths:
            path,_,_=self.p.path(x[:2],goal);self.paths[key]=path
        path=self.paths[key]
        if not path:return goal
        # Discard already passed waypoints, then smooth only short safe sections.
        nearest=min(range(min(8,len(path))),key=lambda j:math.dist(path[j],x[:2]))
        if nearest>0:path[:nearest]=[]
        chosen=None;idx=0
        for j,point in enumerate(path[:7]):
            dist=math.dist(x[:2],point)
            if dist>16:break
            if self.safe_line(x[:2],point):chosen=point;idx=j
        if chosen is None:
            self.paths.pop(key,None)
            path,_,_=self.p.path(x[:2],goal);self.paths[key]=path
            for point in path[:4]:
                if self.safe_line(x[:2],point):return point
            return goal
        if idx>0:path[:idx]=[]
        return chosen

    def driving(self,x,waypoint):
        d=math.dist(x[:2],waypoint)
        heading=math.degrees(math.atan2(waypoint[1]-x[1],waypoint[0]-x[0]))-x[2]
        m=min(5.,max(.05,d/(1-self.slip[self.p.s.terrain(*x[:2])])))
        for _ in range(3):
            cmd={'action':'drive','heading_deg':heading%360,'metres':m}
            xx,z=self.motion(x,cmd);actual=math.dist(x[:2],xx[:2])
            if actual<.01:break
            desired_angle=math.atan2(waypoint[1]-x[1],waypoint[0]-x[0]);actual_angle=math.atan2(xx[1]-x[1],xx[0]-x[0])
            delta=(desired_angle-actual_angle+math.pi)%(2*math.pi)-math.pi
            heading+=math.degrees(delta)
            m=min(5.,max(.03,m*d/actual))
        cmd={'action':'drive','heading_deg':heading%360,'metres':m}
        xx,z=self.motion(x,cmd)
        if z['stop']:
            # Search nearby headings for a safe continuation instead of touching a wall.
            options=[]
            for dh in (-70,-45,-25,-12,0,12,25,45,70,110,-110):
                for dm in (5.,2.,.7):
                    cc={'action':'drive','heading_deg':(heading+dh)%360,'metres':dm}
                    xxx,zz=self.motion(x,cc)
                    if not zz['stop']:options.append((math.dist(xxx[:2],waypoint)+.04*zz['energy'],cc))
            if options:cmd=min(options,key=lambda a:a[0])[1]
            else:cmd={'action':'wait'}
            self.paths={}
        return cmd

    def command(self,tools):
        execution=self.tick+4
        if execution>self.r['max_ticks']:return {'action':'wait'}
        x,bat=self.forecast(execution-1)
        if self.tick>=300:self.p.finish_tick=410
        if self.discover:
            w=tools.map()
            self.p.targets.update({t['id']:t for t in w['targets']});self.w=w;self.discover=False;self.lastopt=-100
        # Re-optimize with actual progress and all known discoveries.
        if self.tick-self.lastopt>=35:
            old=self.route[:]
            self.route,met=self.p.optimize(x[:2],self.tick,bat,self.planned|self.taken,old,iterations=22000 if self.tick else 5000)
            self.paths={};self.lastopt=self.tick
            print('PLAN',self.tick,self.route,'metrics',met,'pos',[round(v,2) for v in x],'battery',round(bat,2),'slip',self.slip,flush=True)
        self.route=[i for i in self.route if i not in self.planned and i not in self.taken]
        key=self.route[0] if self.route else 'base';tar=self.p.targets[key];goal=(tar['x'],tar['y'])
        dist=math.dist(x[:2],goal)
        if key!='base' and dist<.7:
            self.planned.add(key);self.pending[execution]=key;self.route.pop(0)
            self.paths.pop(key,None)
            print('SAMPLE QUEUED',key,'execute',execution,'predicted',x[:2],flush=True)
            cmd={'action':'sample'}
        elif key=='base' and dist<.65:
            cmd={'action':'wait'}
        else:
            waypoint=self.waypoint(x,goal,key)
            if math.dist(x[:2],waypoint)<.8 and math.dist(x[:2],goal)>2:
                self.paths.pop(key,None);waypoint=self.waypoint(x,goal,key)
            cmd=self.driving(x,waypoint)
        # Preserve battery through the low sun, using exact forecast command energy.
        if cmd['action']=='drive':
            _,z=self.motion(x,cmd)
            if bat-z['energy']<8:
                print('CHARGE WAIT',self.tick,round(bat,2),flush=True);cmd={'action':'wait'}
        ack=tools.uplink([cmd]);actual=ack[0]['execute_tick']
        self.cmd[actual]=cmd
        if actual!=execution:
            print('EXECUTION SHIFT',execution,actual,flush=True)
        return cmd

def main():
    until=int(sys.argv[1]) if len(sys.argv)>1 else 420
    with connect('http://lightlag:8000/mcp') as tools:
        try:
            with open('/app/controller.pkl','rb') as f:c=pickle.load(f)
            print('RESUME',c.tick,flush=True)
        except FileNotFoundError:c=Controller(tools)
        while c.tick<until and not c.done:
            cmd=c.command(tools)
            out=tools.advance(1);c.tick=out['current_tick'];c.done=out['episode_complete']
            for packet in out['packets']:c.assimilate(packet)
            if c.tick%10==0:print('STATUS',c.tick,'state',c.x,'battery',c.battery,'credit',c.credited,'next',c.route[:3],flush=True)
        with open('/app/controller.pkl','wb') as f:pickle.dump(c,f)
        print('STOP',c.tick,'COMPLETE',c.done,'CREDIT',c.credited,'STATE',c.x,'BATTERY',c.battery,flush=True)
        if c.done:
            print('FINAL_RESPONSE',json.dumps(out),flush=True)

if __name__=='__main__':main()
