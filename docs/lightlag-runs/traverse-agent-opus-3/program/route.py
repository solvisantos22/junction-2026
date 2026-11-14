import json,math,pickle,sys,time
sys.path.insert(0,'/tmp/ll')
from plan import *
T=[t for t in w['targets']]
pts=[('base',w['base'][0],w['base'][1])]+[(t['id'],t['x'],t['y']) for t in T]
D={}
t0=time.time()
for a,x,y in pts:
  dist,prev=dijkstra(x,y)
  for b,x2,y2 in pts:
    D[(a,b)]=dist.get(cellof(x2,y2),1e9)
print('dij',time.time()-t0)
pickle.dump(D,open('/tmp/ll/D.pkl','wb'))
for t in T: print(t['id'],round(D[('base',t['id'])],1),t['value'],t['deadline_tick'])
