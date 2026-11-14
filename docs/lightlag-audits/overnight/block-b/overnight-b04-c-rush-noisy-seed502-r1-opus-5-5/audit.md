# Decision audit: overnight-b04-c-rush-noisy-seed502-r1-opus-5-5

- Model: anthropic/claude-opus-5-5
- Profile `rush_noisy`, seed 502, delay 3 ticks, horizon 50
- Agent: **8** of 13 (reward 0.615, reward.txt 0.615)
- Reference (`kf_mpc`) from the start: **10** (reward 0.769)
- Gap: 2 points = 0.154 reward. Decisions account for 2, stopping early for 0.
- Rebuild reproduces the saved run tick for tick: **yes**

## Main mistakes

### 1. call 10, advance 4 at tick 11: −2 points (−0.154 reward)

- **QUEUE_RAN_DRY**: queue ends at tick 16; waiting until 15 means the next command cannot run before tick 19 (2 more idle ticks). Advanced instead of queuing the next leg; the queue emptied before new commands could arrive.
  - Information the agent had: telemetry packet for tick 8, delivered at tick 11 (position [16.08, 27.17], battery 79.7); rules(): first_execution_tick
- Reference instead: at tick 13 uplink [drive 255.9° 3.92 m, drive 255.9° 3.92 m, sample]; then sample t4 (tick 16), t2 (tick 19), d2 (tick 22); finish home, score 10
- Agent's own words: none recorded (trajectory step 9 holds the tool call but no message or reasoning text)

## Infrastructure (kept apart from reasoning)

None found: every agent call reached the simulator, Harbor recorded no exception, the rebuild matches the run and reward.txt matches the evaluator.

## Other reasoning findings (no points lost against the reference)

- call 11: **REJECTED_BY_RULES**: call 11 (uplink) was rejected: metres must be in (0, 5.0]
- call 11: **DISCOVERY_MISSED**: d2 (value 3, deadline tick 22) arrived in the packet for tick 10 at tick 13; never sampled
- call 18: **DISCOVERY_MISSED**: d1 (value 2, deadline tick 28) arrived in the packet for tick 21 at tick 24; never sampled

## Episode outcome

- **TARGETS_LEFT**: never sampled: d1, d2
- superlog labels unavailable here (ModuleNotFoundError: No module named 'numpy')

## Every decision

| call | tick | what the agent did | reference before | reference after | points lost | tags |
|---:|---|---|---:|---:|---:|---|
| 3 | 0→0 | uplink [drive 101.4° 4.29 m, sample] | 10 | 10 | 0 |  |
| 4 | 0→0 | uplink [drive 161.4° 3.86 m, drive 81.8° 1.43 m, sample] | 10 | 10 | 0 |  |
| 5 | 0→5 | advance 5 | 10 | 10 | 0 |  |
| 6 | 5→8 | advance 3 | 10 | 10 | 0 |  |
| 7 | 8→8 | uplink [drive 270° 1.5 m, drive 0° 4.4 m, drive 0° 4.37 m] | 10 | 10 | 0 |  |
| 8 | 8→11 | advance 3 | 10 | 10 | 0 |  |
| 9 | 11→11 | uplink [drive 92° 3.6 m, sample] | 10 | 10 | 0 |  |
| 10 | 11→15 | advance 4 | 10 | 8 | 2 | QUEUE_RAN_DRY |
| 11 | 15→15 | uplink [drive 264.2° 2.6 m, drive 264.2° 5 m, drive 264.2° 5.1 m, sample] (rejected) | 8 | 8 | 0 | DISCOVERY_MISSED, REJECTED_BY_RULES |
| 12 | 15→17 | advance 2 | 8 | 8 | 0 |  |
| 13 | 17→17 | uplink [drive 254.7° 3.55 m, drive 254.7° 3.5 m, sample] | 8 | 8 | 0 |  |
| 14 | 17→19 | advance 2 | 8 | 8 | 0 |  |
| 15 | 19→19 | uplink [drive 216.5° 4.15 m, drive 216.5° 4.12 m, sample] | 8 | 8 | 0 |  |
| 16 | 19→23 | advance 4 | 8 | 8 | 0 |  |
| 17 | 23→26 | advance 3 | 8 | 8 | 0 |  |
| 18 | 26→29 | advance 3 | 8 | 8 | 0 | DISCOVERY_MISSED |
| 19 | 29→29 | uplink [drive 40.3° 4.9 m] | 8 | 8 | 0 |  |
| 20 | 29→34 | advance 5 | 8 | 8 | 0 |  |
| 21 | 34→39 | advance 5 | 8 | 8 | 0 |  |
| 22 | 39→44 | advance 5 | 8 | 8 | 0 |  |
| 23 | 44→49 | advance 5 | 8 | 8 | 0 |  |
| 24 | 49→50 | advance 1 | 8 | 8 | 0 |  |

*Reference before/after*: the score if the reference took over just before or just after this call, knowing only what the agent knew then (delivered telemetry, rules, map, its own acknowledgements). *Points lost* = before − after; the column plus the stop loss adds up to the gap.
