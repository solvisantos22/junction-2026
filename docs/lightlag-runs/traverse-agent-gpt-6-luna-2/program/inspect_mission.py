import math
import heapq
from lightlag_client import connect
from lightlag_surface import Surface

with connect("http://lightlag:8000/mcp") as tools:
    world = tools.map()
    print("base", world.get("lander", world.get("base")))
    print("keys", world.keys())
    for target in world["targets"]:
        print(target)
    surface = Surface(world["cell_m"], world["elevation_cm"], world["terrain"])
    print("SLOPE MAP, y descending; each char 10m x 10m (#>0.36, ^>0.25, .=safe)")
    for y in range(390, -1, -10):
        row = []
        for x in range(0, 600, 10):
            s = max(surface.cell_max_slope(i, j) for i in range(x//5, min(x//5+2, surface.nx-1)) for j in range(y//5, min(y//5+2, surface.ny-1)))
            row.append('#' if s > .36 else '^' if s > .25 else '.')
        print(f"{y:3}", ''.join(row))
    print("TARGET REACHABILITY / COST")
    start = (60, 53)  # 5 m raster node nearest the base
    dist = {start: 0.0}
    prev = {}
    heap = [(0.0, start)]
    while heap:
        d, (ix, iy) = heapq.heappop(heap)
        if d != dist[(ix, iy)]:
            continue
        x, y = ix*5.0, iy*5.0
        for dx, dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
            nx, ny = ix+dx, iy+dy
            if not (0 <= nx <= 120 and 0 <= ny <= 80):
                continue
            xx, yy = nx*5.0, ny*5.0
            length = math.hypot(xx-x, yy-y)
            safe = True
            steps = int(length*2)
            for k in range(steps+1):
                q = k/steps
                if surface.slope(x+(xx-x)*q, y+(yy-y)*q) > .30:
                    safe = False
                    break
            if not safe:
                continue
            nd = d + length
            node=(nx,ny)
            if nd < dist.get(node, 1e9):
                dist[node]=nd
                prev[node]=(ix,iy)
                heapq.heappush(heap,(nd,node))
    for t in world["targets"]:
        node=(round(t["x"]/5),round(t["y"]/5))
        print(t["id"], round(dist.get(node, float('inf')),1), "slope", round(surface.slope(t["x"],t["y"]),3))
    byid={t['id']:t for t in world['targets']}
    route=['t37','t2','t30','t6','t38','t23','t11','t31','t1','t28','t34','t25','t12','t32','t33','t3']
    route_nodes=[start]+[(round(byid[k]['x']/5),round(byid[k]['y']/5)) for k in route]+[start]
    print('ROUTE',route)
    for a,b in zip(route_nodes,route_nodes[1:]):
        dd={a:0.0}; hh=[(0.0,a)]
        while hh:
            d,(ix,iy)=heapq.heappop(hh)
            if d!=dd[(ix,iy)]: continue
            if (ix,iy)==b: break
            x,y=ix*5.0,iy*5.0
            for dx,dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
                nx,ny=ix+dx,iy+dy
                if not(0<=nx<=120 and 0<=ny<=80):continue
                xx,yy=nx*5.,ny*5.; length=math.hypot(xx-x,yy-y)
                if any(surface.slope(x+(xx-x)*k/10,y+(yy-y)*k/10)>.30 for k in range(11)):continue
                nd=d+length; n=(nx,ny)
                if nd<dd.get(n,1e9):dd[n]=nd;heapq.heappush(hh,(nd,n))
        print(a,b,round(dd.get(b,float('inf')),1))
