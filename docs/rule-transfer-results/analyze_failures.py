import gzip,hashlib,json,math
from pathlib import Path
from statistics import mean
ROOT=Path(__file__).resolve().parents[2]; directory=ROOT/'docs/rule-transfer-results/free'
report=json.loads((directory/'report.json').read_text())
rows={(r['policy'],r['kind'],r['seed']):r for r in report['cases']}
def load(row): return json.loads(gzip.decompress((directory/row['artifact']).read_bytes()))
output={'schema':'rule-transfer-failure-analysis-v1','model_calls':0,'new_cases':0,'report_sha256':hashlib.sha256((directory/'report.json').read_bytes()).hexdigest(),'turning':[],'relay_invalid':[]}
for seed in range(3200,3240):
 row=rows['saved_opus','turning',seed];bundle=load(row);replay=bundle['replay'];states=replay['states'];change=replay['rule_change']; commands={c['command_id']:c for c in replay['commands']}; bytick={s['tick']:s for s in states}; turns=[];signals=[]
 for before,after in zip(states,states[1:]):
  executed=[e['command_id'] for e in after['events'] if e['type']=='command_executed']
  if not executed: continue
  ack=commands[executed[0]];cmd=ack['command']
  if cmd['action']!='drive' or after['tick']<change['tick']:continue
  angle=abs((cmd['heading_deg']-before['heading_deg']+180)%360-180)
  nominal=angle*change['energy_per_degree']*(2 if before['terrain']=='sand' else 1)
  spent=min(max(before['battery']-.5,0),nominal)
  excess=before['battery']-after['battery']-.5-2*after['wheel_odometry']
  item={'execute_tick':after['tick'],'sent_tick':ack['sent_tick'],'heading_change_deg':angle,'metres':cmd['metres'],'battery_before':before['battery'],'battery_after':after['battery'],'turn_energy_actual':spent,'baseline_worst_terrain_excess':excess,'packet_received_tick':after['received_tick'],'command_id':ack['command_id']}
  turns.append(item)
  if excess>.05 and after['received_tick']<=50:signals.append(item)
 first_signal=signals[0] if signals else None
 dead_tick=next((s['tick'] for s in states if not s['alive']),None)
 after_signal=[t for t in turns if first_signal and t['sent_tick']>=first_signal['packet_received_tick']]
 prevcontrol=rows['saved_opus','none',seed]['result'];prepared=rows['prepared','turning',seed]['result']
 base=replay['world']['base'];home_after_departure=[];departed=False
 for s in states:
  inside=math.dist(s['position'],base)<=.75
  if not inside: departed=True
  if departed and inside and s['alive']: home_after_departure.append(s['tick'])
 output['turning'].append({'seed':seed,'change':change,'alive':row['result']['evaluation']['alive'],'score':row['result']['normalized_score'],'sampled_value':row['result']['evaluation']['sampled_value'],'death_tick':dead_tick,'none_score':prevcontrol['normalized_score'],'none_alive':prevcontrol['evaluation']['alive'],'prepared_score':prepared['normalized_score'],'prepared_alive':prepared['evaluation']['alive'],'total_turn_energy_actual':sum(t['turn_energy_actual'] for t in turns),'first_public_strong_energy_signal':first_signal,'signal_before_death':bool(first_signal and dead_tick is not None and first_signal['packet_received_tick']<dead_tick),'post_signal_sent_turns':after_signal,'returned_home_alive_ticks_before_end':home_after_departure,'last_drives':turns[-4:]})
for seed in range(3200,3240):
 row=rows['saved_opus','relay',seed]
 if not row['result']['invalid_calls']:continue
 bundle=load(row);bad=[]
 for t in bundle['transcript']:
  if t['ok']:continue
  sent=t['tick_before'];tx=sent if sent%8<4 else sent+(8-sent%8)
  bad.append({'sent_tick':sent,'naive_earliest_execute':sent+4,'relay_transmit_tick':tx,'relay_earliest_execute':tx+4,'error':t['error'],'commands':t['arguments']['commands']})
 output['relay_invalid'].append({'seed':seed,'change':bundle['replay']['rule_change'],'score':row['result']['normalized_score'],'at_base':row['result']['evaluation']['at_base'],'alive':row['result']['evaluation']['alive'],'invalid':bad})
dead=[x for x in output['turning'] if not x['alive']]
output['summary']={'turning_deaths':len(dead),'dead_cases_with_earlier_strong_public_energy_signal':sum(x['signal_before_death'] for x in dead),'dead_cases_with_newly_sent_drives_after_signal':sum(bool(x['post_signal_sent_turns']) for x in dead),'dead_cases_previously_home_alive':sum(bool(x['returned_home_alive_ticks_before_end']) for x in dead),'dead_case_turn_energy_mean':mean(x['total_turn_energy_actual'] for x in dead),'death_tick_range':[min(x['death_tick'] for x in dead),max(x['death_tick'] for x in dead)],'paired_none_deaths':sum(not x['none_alive'] for x in output['turning']),'prepared_turning_deaths':sum(not x['prepared_alive'] for x in output['turning']),'relay_invalid_calls':sum(len(x['invalid']) for x in output['relay_invalid'])}
output['interpretation_limits']=['Hidden change time and coefficient are used only by this evaluator-side trace analysis, not available to the frozen policy or supplied as adaptation feedback.','Strong public energy signal means observed battery drop exceeds idle plus twice reported wheel distance by >0.05; it is a conservative inconsistency with all original terrain costs, not a claim that the policy diagnosed it.','New drives after signal show opportunities for revision, not that a specific unseen repair would save the episode.','This is failure of a frozen program written for original rules, not an evaluated coding agent failing after receiving the new rules.']
import argparse
parser=argparse.ArgumentParser(description='Reconstruct failure diagnostics from the retained free screen.')
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()

# Additional diagnostics only inspect retained public logs and evaluator state.
for item in output['turning']:
 bundle=load(rows['saved_opus','turning',item['seed']]); states=bundle['replay']['states']; base=bundle['replay']['world']['base']; departed=False; safe=[]
 for state in states:
  inside=math.dist(state['position'],base)<=.75
  if not inside: departed=True
  if departed and inside and state['alive'] and state['battery']>.5*(50-state['tick'])+1e-8:
   safe.append({'tick':state['tick'],'battery':state['battery'],'idle_to_horizon':.5*(50-state['tick']),'remaining_margin':state['battery']-.5*(50-state['tick']),'sampled_count':len(state['sampled_targets'])})
 item['first_safe_park_truth_diagnostic']=safe[0] if safe else None
 item['last_safe_park_truth_diagnostic']=safe[-1] if safe else None
 signal=item['first_public_strong_energy_signal']
 if signal:
  readings=[t['tick_before'] for t in bundle['transcript'] if t['ok'] and t['tool']=='telemetry_log' and any(p['tick']==signal['execute_tick'] for p in t['result'])]
  signal['first_policy_read_tick']=min(readings) if readings else None
  assert signal['first_policy_read_tick']==signal['packet_received_tick']
 if item['death_tick']:
  state=states[item['death_tick']]
  item['death_events']=state['events']
  item['death_while_idle']=not any(e['type']=='command_executed' for e in state['events'])
  item['final_distance_to_base']=math.dist(states[-1]['position'],base)
dead=[item for item in output['turning'] if not item['alive']]
output['summary'].update({'dead_cases_with_earlier_truth_safe_parking':sum(item['first_safe_park_truth_diagnostic'] is not None for item in dead),'dead_cases_depleting_on_idle_tick':sum(item['death_while_idle'] for item in dead),'dead_cases_final_position_inside_base':sum(item['final_distance_to_base']<=.75 for item in dead)})
output['interpretation_limits'].append('Safe-parking diagnostics use true evaluator position and actual remaining battery and assume future queued commands could be cancelled; actual API has no cancel tool. They are therefore not a demonstrated executable rescue policy. A prospective controller should avoid unnecessary queued corrections rather than assume it can cancel them.')
args.output.write_text(json.dumps(output,indent=2)+'\n')
print(json.dumps(output['summary'],indent=2))
