# Choose what to learn before choosing a rover mission

Maximize expected score in this single episode using the five public `allocation`
MCP tools: `rules`, `map`, `telemetry_log`, `uplink`, and `advance`. Read the rules
and map: they publish all priors, sensor reliability, costs, timing and rewards.

Routes a and b lead to different targets and each crosses its own independently
sampled firm or soft ground. The detour leads to a third target with known energy
cost. All three trips include returning home. Route values and priors can differ.
The actual two ground states are hidden and stay fixed throughout the episode.

There is ONE inspection available in total, shared across a and b. You may use it
on either route or skip it. Inspection costs energy and yields one delayed,
imperfect signal about the inspected route only. It does not change or reveal the
other route's ground. You may still choose any route after inspecting. Repeated
log reads are not fresh observations. A route becomes irreversible when its
commit command is accepted, even before execution. A batch queuing a probe and
commit therefore commits before observing the result.

Commands for `uplink(commands)` are:
- {"action":"probe","route":"a"} or route "b"
- {"action":"commit","route":"a"}, route "b", or route "detour"
- {"action":"wait"}

Only `advance(ticks)` moves simulated time, by 1–5 ticks per call. Reading public
information is free. You may think, calculate, write scripts and run code; the
installed Python MCP client can call http://allocation:8000/mcp. Do not access
simulator internals, hidden state, evaluator endpoints or evaluator files.

Accepted commands execute FIFO at the published delay. A completed trip earns
its target value minus the published completion-time decay, normalized to [0,1].
Failed or incomplete trips score zero. Optimize expected reward using available
information; favorable terrain is not guaranteed. If you stop early, accepted
commands and remaining simulated time run to the fixed horizon under the trusted
evaluator. Play through the tools: writing a plan alone does not act.
