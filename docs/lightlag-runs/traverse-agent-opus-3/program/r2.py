import pickle,json,sys
sys.path.insert(0,'/tmp/ll')
from opt import *
D=pickle.load(open('/tmp/ll/D.pkl','rb')); w=json.load(open('/tmp/map.json'))
info={t['id']:(t['value'],t['deadline_tick'],t['late_value']) for t in w['targets']}
for seed in range(4):
  s,b=optimize(D,info,'base',4,405,seed=seed)
  print(b,evaluate(s,D,info,'base',4,405),s)
