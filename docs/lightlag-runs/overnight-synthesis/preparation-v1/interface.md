The Python tools object has exactly these methods:
- rules() -> dict: the authoritative public rules shown below.
- map() -> dict: width:number, height:number, base:[x,y], hazards:[rect],
  sand:[rect], targets:[target]. A rect has x1,y1,x2,y2. A target has id:string,
  x:number,y:number,value:number,deadline_tick:integer|null,late_value:number,
  appear_tick:integer. Only announced targets appear; refresh after discovery.
- telemetry_log() -> [packet]: all delivered packets including the exact tick-0 briefing.
- uplink(commands:list[dict]) -> [ack]: accepts 1..5 drive/sample/wait commands.
  drive: {"action":"drive","heading_deg":number,"metres":number in (0,5]}.
  sample/wait: {"action":"sample"} or {"action":"wait"}.
  ack: command_id:integer,sent_tick:integer,execute_tick:integer,command:dict.
- advance(ticks:int=1) -> {current_tick:int,episode_complete:bool,packets:[packet]}.
  ticks is 1..5, clipped to the horizon. Only advance moves simulated time.
A packet has tick:int,received_tick:int,position:[x,y],heading_deg:number,
battery:number,terrain:string,wheel_odometry:number,visual_odometry:number,
sampled_targets:[string],alive:bool,events:[dict]. Events include command_executed
(command_id), sample_taken (target_id,on_time), sample_failed (reason),
safety_stop (reason), battery_depleted, and target_discovered (target).
Bad requests raise ValueError. Your process has no simulator, reset, grade or
hidden-state API. It starts with no map. Obtain observations from tools only.
