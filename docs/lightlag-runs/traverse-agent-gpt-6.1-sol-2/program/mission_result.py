import json,math
from lightlag_client import connect
with connect('http://lightlag:8000/mcp') as t:
    packets=t.telemetry_log();w=t.map()
    json.dump(packets,open('/app/final_telemetry.json','w'))
    json.dump(w,open('/app/final_world.json','w'))
    targets={x['id']:x for x in w['targets']}
    seen=set();earned=0;late=[];samples=[]
    for p in packets:
        for id in p['sampled_targets']:
            if id in seen:continue
            seen.add(id);x=targets[id]
            islate=x['deadline_tick'] is not None and p['tick']>x['deadline_tick']
            v=x['late_value'] if islate else x['value'];earned+=v
            if islate:late.append(id)
            samples.append(dict(id=id,tick=p['tick'],value=v))
    p=packets[-1]
    eff=p['charge']/(2.8*math.sin(math.pi*(p['tick']+56)/532))
    final_battery=p['battery']+sum(2.8*eff*math.sin(math.pi*(k+56)/532)-.15 for k in range(p['tick']+1,421))
    stationary=[x['position'] for x in packets if x['tick']>=406]
    avg=[sum(x[i] for x in stationary)/len(stationary) for i in range(2)]
    result=dict(samples=len(seen),available=len(targets),earned=earned,total_value=sum(x['value'] for x in targets.values()),late_samples=late,estimated_final_position=avg,lander=w['base'],estimated_final_battery=final_battery,details=samples)
    result['score_if_at_base']=earned/result['total_value']
    json.dump(result,open('/app/mission_result.json','w'),indent=2)
    print(json.dumps(result,indent=2))
