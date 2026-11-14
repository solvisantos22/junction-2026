# Lightlag decision audit

This tool serves the rubric line *"Meaningful difficulty: you can explain the agent's main mistakes and connect them to decisions in the task; the information and tools needed to do better are available to it."*

For any saved Harbor run it answers four questions:

1. What did the agent decide? Every `uplink` and `advance` call is rebuilt from the simulator's transcript, and the rebuild is checked tick by tick against the saved replay.
2. How many points did each decision lose? Each decision is compared with the reference controller taking over at that exact moment.
3. Where was the information it needed? Each finding points to a telemetry packet (its state tick and the tick it arrived), an acknowledgement, a published rule key or a map item.
4. Was it reasoning or infrastructure? Tool and harness failures are reported in their own section and never counted as the agent's mistakes.

```bash
python3 -m lightlag_audit docs/lightlag-runs/*/ --out docs/lightlag-audits
```

This writes `docs/lightlag-audits/<run>/audit.md` (the part people read), `audit.json` (the same audit, machine-readable) and an index at `docs/lightlag-audits/README.md`. It never writes to the run folders. A core run takes about a second. A `rush` run takes 3–5 seconds, because KF+MPC replans at every decision. Standard library only, plus the repo's own packages.

After the judges' reruns (reference, three agent runs, do-nothing, stop-early), point the same command at the new run folders.

## How points lost are computed

- **The rebuild is exact.** The simulator is deterministic given its seed. Repeating the transcript's calls in a fresh environment reproduces the run, and the audit checks every state's tick, position and battery, plus the final score, against `replay.json`. If they differ, the run is flagged as infrastructure (`INFRA_REBUILD_MISMATCH`) and its points are not trusted.
- **V(k)** is the final score when the reference takes over just before the agent's k-th state-changing call. The reference knows exactly what the agent knew then: the rules, the map, the telemetry delivered so far, and the acknowledgements of every command already sent, including the ones still in transit. It never sees the hidden truth.
- **Points lost by decision k** = V(k) − V(k+1). These numbers add up exactly to *reference from the start − agent's final score*. The last term, *stop loss*, is what the reference would still have gained after the agent's last call (the do-nothing and stop-early baselines lose everything here).
- **Reward units** = points / `max_available_value`, which is what `verifier/reward.txt` holds.
- **Which reference:**
  - `team` on the core task: Kristján's `lightlag_controllers` reference, the one `harbor/.../solution/solve.sh` runs.
  - `kf_mpc` on dynamic profiles such as `rush`.
  - `mission` (Sölvi's `lightlag.controllers` reference) is available with `--reference mission` for comparison. It is weaker on seed 7: 3 against 4.

A decision can have *negative* points lost. That happens when the reference, taking over from the state the agent created, does worse than the agent actually went on to do. When the agent matches the reference overall, the audit lists no main mistakes. Such pairs, where one decision loses points and a later one wins them back, show where the reference is weak from states it would not have chosen. They are not agent errors. The Opus seed-7 run is the example: call 3 shows −1 and call 13 shows +1, so the net is 0.

## Tags

**Reasoning**: the tools worked and the information was available.

| tag | when | evidence it points to |
|---|---|---|
| `STALE_AIM` | An uplink that ends in a sample lands on a known target only if the drives still in transit are ignored. | The last delivered packet; the acknowledgements of the in-transit commands; `first_execution_tick` and `telemetry_arrival_tick` |
| `REPEATED_IN_TRANSIT` | The same commands are sent again while the first copy is still invisible in telemetry. | The earlier acknowledgement; the last packet |
| `SAMPLE_MISSED` | A sample command failed. The cause is one of: `stale_aim`, `slip_not_corrected` (the drive ran on sand, or wheel and visual odometry disagreed), `already_sampled`, `battery`, or plain `aim`. | The packet planned from; the true position at execution; the packet that showed the slip |
| `SAFETY_STOP` | A drive hit a hazard or the map edge, which cleared the queue. | The map's hazard rectangle; the cleared command ids |
| `BATTERY_DEPLETED` | The battery ran out during this uplink's commands. | The last packet's battery; the energy rules |
| `LATE_SAMPLE` | A sample was taken after the target's published deadline. | The map target's `deadline_tick` |
| `DISCOVERY_MISSED` | A `target_discovered` packet arrived, and the target was never sampled or was sampled late. The finding is attached to the first decision after the packet arrived. | The packet's state tick and arrival tick; the target |
| `WAITED_WITH_EMPTY_QUEUE` | The agent advanced with nothing queued, and it cost points. | When the queue ended; the earliest tick a new command could run; `first_execution_tick` |
| `QUEUE_RAN_DRY` | The agent advanced instead of queuing the next leg, and the queue emptied before new commands could arrive. | The same as above, with the number of extra idle ticks |
| `REJECTED_BY_RULES` | The call broke a published limit (for example a drive over 5 m, or more than 5 commands). It costs 0 points but wastes a turn. | The error text and the `rules()` key |
| `PLAN_WORSE_THAN_REFERENCE` / `COSTLY_WAIT` | A decision lost points but no specific pattern above matched. | The packet; the reference's alternative plan |
| `STOPPED_EARLY` | The agent stopped calling tools while the reference would still have scored. | The stop tick; the reference's plan from there |

**Infrastructure**: kept apart from reasoning.

| tag | when |
|---|---|
| `INFRA_CALL_NOT_RECORDED` | The agent's trajectory has a tool call that the simulator never recorded, so it never reached the simulator. |
| `INFRA_TOOL_ERROR` | A read-only tool (`rules`, `map`, `telemetry_log`) returned an error. |
| `INFRA_HARBOR_EXCEPTION` | Harbor's `result.json` has `exception_info`, such as a timeout or a crashed container. |
| `INFRA_NO_TRANSCRIPT` | The transcript is missing, or it is empty while the replay has commands. |
| `INFRA_REBUILD_MISMATCH` | The rebuild does not reproduce the saved run. |
| `INFRA_REWARD_MISMATCH` | `reward.txt` does not equal raw score / maximum. |

**Outcome**: `PERFECT`, `DEAD`, `NOT_HOME`, `NOTHING_SAMPLED`, `TARGETS_LEFT`. These use the same names as `lightlag_dynamic/manh_controllers/superlog.py`.

Every main mistake also shows the reference's alternative: what it would have sent first, which samples it would have taken from that point, and its final score. It also quotes the agent's own words from the same trajectory step when the trajectory recorded any. OpenCode's Opus trajectory records reasoning token counts but no reasoning text for most steps, and the report says so instead of guessing.

## Limits

- Points lost are measured against one reference, not the true optimum. A stronger reference would assign more of the gap. The opposite, negative points, shows where this reference is weak (see above).
- `STALE_AIM` uses nominal dead reckoning (no slip) with a tolerance of 0.15 m per metre driven, and only considers targets the agent knew about at that tick.
- The audit needs `artifacts/evaluator/replay.json` and `transcript.jsonl`. Without `agent/trajectory.json`, it still audits the decisions but cannot quote the agent or detect calls that never reached the simulator.

Tests (13; about 70 seconds, most of it the reference replanning at every decision):

```bash
python3 -m unittest discover -s tests/lightlag_audit -v
```

These cover scripted episodes with a known mistake each (stale aim, a chained plan that is *not* stale, a repeat in transit, a rule rejection, a safety stop, idle waiting, stopping without a call, and the reference itself), plus the saved runs and a copy of the Opus run with an injected tool failure. That injected failure must show up only under infrastructure.
