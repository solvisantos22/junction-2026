import json,math
from lightlag_client import connect
with connect('http://lightlag:8000/mcp') as tools:
    w=tools.map();p=tools.telemetry_log();targets={t['id']:t for t in w['targets']}
    taken={e['target_id']:(q['tick'],e['on_time']) for q in p for e in q['events'] if e.get('type')=='sample_taken'}
    earned=sum(targets[id]['value'] if timely else targets[id]['late_value'] for id,(tick,timely) in taken.items())
    total=sum(t['value'] for t in w['targets'])
    end=p[-1];recent=p[-12:];pos=[sum(q['position'][i] for q in recent)/len(recent) for i in (0,1)]
    result={'sample_count':len(taken),'on_time':sum(timely for tick,timely in taken.values()),'science_value':earned,'total_value':total,'score_with_base_multiplier':earned/total,'last_packet':end,'stationary_position_average':pos,'estimated_distance_to_base':math.dist(pos,w['base']),'sample_ticks':taken}
    json.dump(result,open('/app/mission_result.json','w'),indent=2);print(json.dumps(result,indent=2))
