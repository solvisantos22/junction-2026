import json, math, heapq, sys
sys.path.insert(0,'/app')
from lightlag_surface import Surface, PHYSICS
w=json.load(open('/tmp/map.json'))
S=Surface(w['cell_m'],w['elevation_cm'],w['terrain'])
NX,NY=S.nx-1,S.ny-1
SLIP={'b':0.03,'r':0.09,'s':0.27,'k':0.19}
GAIN={'b':0.8,'r':1.5,'s':3.5,'k':1.2}
COST={'b':0.3,'r':0.36,'s':0.5,'k':0.6}
blocked=[[S.cell_max_slope(i,j)>0.27 for i in range(NX)] for j in range(NY)]
# also block neighbors of very steep cells (margin)
bl2=[[blocked[j][i] for i in range(NX)] for j in range(NY)]
for j in range(NY):
  for i in range(NX):
    if blocked[j][i]:
      for dj in (-1,0,1):
        for di in (-1,0,1):
          a,b=j+dj,i+di
          if 0<=a<NY and 0<=b<NX and S.cell_max_slope(b,a)>0.2: bl2[a][b]=True
blocked=bl2
H=[[S.elevation(i*5+2.5,j*5+2.5) for i in range(NX)] for j in range(NY)]
DIRS=[(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1),(2,1),(1,2),(-2,1),(-1,2),(2,-1),(1,-2),(-2,-1),(-1,-2)]
def ecost(i,j,di,dj):
  d=5*math.hypot(di,dj)
  t=w['terrain'][j][i]; t2=w['terrain'][j+dj][i+di]
  grade=(H[j+dj][i+di]-H[j][i])/d
  sl=lambda c: min(0.95,SLIP[c]+GAIN[c]*max(0,grade))
  s=(sl(t)+sl(t2))/2
  wheel=d/(1-s)
  e=wheel*(COST[t]+COST[t2])/2+2*max(0,grade*d)
  return wheel/4.7 + 0.03*e   # ticks + small energy pen
def passable(i,j,di,dj):
  if not(0<=i+di<NX and 0<=j+dj<NY): return False
  if blocked[j+dj][i+di]: return False
  if abs(di)==2 or abs(dj)==2:
    # check intermediate cells
    for (a,b) in ((i+(di>0)-(di<0), j),(i, j+(dj>0)-(dj<0)),(i+(di>0)-(di<0), j+(dj>0)-(dj<0))):
      if blocked[b][a]: return False
  elif di and dj:
    if blocked[j][i+di] or blocked[j+dj][i]: return False
  return True
def cellof(x,y): return min(NX-1,max(0,int(x/5))), min(NY-1,max(0,int(y/5)))
def dijkstra(x,y):
  si,sj=cellof(x,y)
  dist={(si,sj):0.0}; prev={}
  pq=[(0.0,si,sj)]
  while pq:
    d,i,j=heapq.heappop(pq)
    if d>dist[(i,j)]: continue
    for di,dj in DIRS:
      if not passable(i,j,di,dj): continue
      nd=d+ecost(i,j,di,dj)
      k=(i+di,j+dj)
      if nd<dist.get(k,1e18): dist[k]=nd; prev[k]=(i,j); heapq.heappush(pq,(nd,i+di,j+dj))
  return dist,prev
def path(prev,src,x,y):
  k=cellof(x,y); out=[]
  while k in prev: out.append((k[0]*5+2.5,k[1]*5+2.5)); k=prev[k]
  return out[::-1]
