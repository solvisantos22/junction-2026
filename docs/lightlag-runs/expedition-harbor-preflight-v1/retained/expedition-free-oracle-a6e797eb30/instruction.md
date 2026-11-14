# Explore, collect science and bring the rover home

Maximize expected normalized mission score in this single episode using the five
public `expedition` MCP tools: `rules`, `map`, `telemetry_log`, `uplink`, `advance`.
Read rules and map first. They specify the terrain, energy, wheel slip, sensing,
sample windows, discoveries, regional quality priors and observation reliability.

Drive to targets, sample within target_radius, and return within base_radius of
base. Credited sample value depends on its base value, regional quality and whether
the sample executes before its deadline. Quality is fixed across the mission and
shared by every target in the same region. Regions are independent at launch.
There are two inspections total, at most one per region, each costing energy and
one execution tick. An inspection gives one imperfect rich/poor signal through
delayed telemetry. Sample events also reveal science evidence. Rereading an event
is not a new observation. In public-quality episodes rules publish the actual
regional qualities; all other mechanics are the same.

Commands for `uplink(commands)` are:
- {"action":"drive","heading_deg":H,"metres":M}: 0 degrees east, 90 north;
  M is wheel distance in (0,5], not guaranteed ground distance.
- {"action":"sample"}: collect the nearest eligible target within target_radius;
  spends sampling energy even on a miss.
- {"action":"inspect","region":"r1"}: also accepts r2 or r3.
- {"action":"wait"}.

Send 1–5 commands per batch. Commands execute FIFO, one per tick, no earlier than
sent_tick + delay_ticks + 1 or the tick after the last reservation. Acknowledgements
give execute_tick. Invalid batches are rejected atomically. Telemetry is a list of
packets: each describes packet.tick and arrives at received_tick, delay_ticks
later. The initial briefing is exact; consult rules for subsequent sensing.
Compare wheel and visual odometry to estimate slip. Avoid hazards and map edges.

Only `advance(ticks)` moves simulated time, by 1–5 ticks per call. Reading, thinking,
calculating and writing/running scripts are free. The installed Python MCP client
can call http://expedition:8000/mcp. Do not access simulator internals, hidden state,
evaluator endpoints or evaluator files. There is no reset.

The fixed horizon is 60 simulated ticks. Grade is credited sample value divided
by the published maximum available value, multiplied by 1 at base, 0.5 if alive
elsewhere, or 0 if battery reached zero. If you stop early, the trusted evaluator
runs accepted commands and the remaining simulated time to the horizon. Optimize
expected reward using the evidence available; favorable quality and inspection
signals are not guaranteed. Play through the tools: writing a plan alone does
not act. Scripting is allowed; there is no thinking-time charge in simulated ticks.
