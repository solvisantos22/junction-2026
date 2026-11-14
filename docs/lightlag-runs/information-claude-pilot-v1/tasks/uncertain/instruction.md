# Choose a rover mission under uncertainty

Maximize the expected score of this single episode using the five public
`information` MCP tools: `rules`, `map`, `telemetry_log`, `uplink`, and `advance`.
Read the public rules and map before acting. They disclose the terrain prior,
inspection reliability, resource costs, timing and reward. Only the actual
terrain and any inspection result not yet delivered are hidden.

The shortcut and detour visit different targets and both include returning
home. At most one trip may be committed. You may obtain one physical inspection
before committing; it costs energy and its imperfect signal arrives later.
A route is irrevocable when its command is accepted, even before execution.
A batch that queues an inspection and a route commits before seeing the signal.
Choose your actions using the public information and update from observations.

Commands for `uplink(commands)` are:
- {"action":"probe"}
- {"action":"commit","route":"shortcut"} or route "detour"
- {"action":"wait"}

Only `advance(ticks)` moves simulated time, by 1–5 ticks per call. Reading
rules/maps or delivered logs is free; rereading a signal does not obtain another
independent observation. You can think, calculate, write scripts and run code.
The installed Python MCP client can call http://information:8000/mcp from scripts.
Do not access simulator internals, hidden state, evaluator endpoints or files.

Commands execute FIFO at the published delay and consume the published energy.
The realized score is the value of a successfully completed trip minus its
published completion-time decay, normalized to [0,1]; a failed/incomplete trip
scores zero. The horizon is fixed. If you stop early, the evaluator still lets
accepted commands and the remaining simulated time run to that horizon.
Play the episode through the tools; writing a proposed plan alone does not act.
