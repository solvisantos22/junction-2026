import math,random
def evaluate(seq,D,info,start,t0,limit,fac=1.08,ov=2.0):
  t=t0; cur=start; val=0
  for s in seq:
    t+=D[(cur,s)]*fac+ov
    v,dl,lv=info[s]
    val+= v if (dl is None or t<=dl) else lv
    cur=s
  t+=D[(cur,'base')]*fac
  if t>limit: return -1e9+val-(t-limit), t
  return val - 0.001*t, t
def optimize(D,info,start,t0,limit,init=None,iters=60000,seed=0):
  rnd=random.Random(seed)
  ids=list(info)
  seq=list(init or [])
  seq=[s for s in seq if s in info]
  best=cur=evaluate(seq,D,info,start,t0,limit)[0]; bseq=seq[:]
  T0=2.0
  for it in range(iters):
    T=T0*(1-it/iters)+0.01
    s=seq[:]
    r=rnd.random()
    out=[i for i in ids if i not in s]
    if r<0.35 and out:
      s.insert(rnd.randint(0,len(s)),rnd.choice(out))
    elif r<0.5 and s:
      s.pop(rnd.randrange(len(s)))
    elif r<0.7 and len(s)>1:
      i,j=sorted(rnd.sample(range(len(s)),2)); s[i:j+1]=s[i:j+1][::-1]
    elif r<0.85 and len(s)>1:
      i=rnd.randrange(len(s)); x=s.pop(i); s.insert(rnd.randint(0,len(s)),x)
    elif s and out:
      s[rnd.randrange(len(s))]=rnd.choice(out)
    else: continue
    v=evaluate(s,D,info,start,t0,limit)[0]
    if v>=cur or rnd.random()<math.exp((v-cur)/T):
      seq,cur=s,v
      if v>best: best,bseq=v,s[:]
  return bseq,best
