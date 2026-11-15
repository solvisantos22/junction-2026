import json
from lightlag_client import connect
with connect('http://lightlag:8000/mcp') as t:
    r=t.rules(); w=t.map(); p=t.telemetry_log()
    with open('/app/mission.json','w') as f: json.dump({'rules':r,'world':w,'packets':p},f)
    print(json.dumps({k:v for k,v in w.items() if k not in ('elevation_cm','terrain')},indent=2))
    print(p)
