import json
from lightlag_client import connect
with connect('http://lightlag:8000/mcp') as t:
    w=t.map(); r=t.rules(); p=t.telemetry_log()
    json.dump(w,open('/app/world.json','w')); json.dump(r,open('/app/rules.json','w'))
    print(json.dumps({k:v for k,v in w.items() if k not in ('elevation_cm','terrain')},indent=2))
    print('PACKETS',p)
