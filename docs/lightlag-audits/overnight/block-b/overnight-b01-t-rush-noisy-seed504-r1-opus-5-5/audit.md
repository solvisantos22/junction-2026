# Decision audit: overnight-b01-t-rush-noisy-seed504-r1-opus-5-5

- Model: anthropic/claude-opus-5-5
- Profile `rush_noisy`, seed 504, delay 3 ticks, horizon 50
- Agent: **3.25** of 10 (reward 0.325, reward.txt 0.325)
- Reference (`kf_mpc`) from the start: **7** (reward 0.700)
- Gap: 3.75 points = 0.375 reward. Decisions account for 3.75, stopping early for 0.
- Rebuild reproduces the saved run tick for tick: **yes**

## Main mistakes

### 1. call 6, advance 1 at tick 8: −2.75 points (−0.275 reward)

- **WAITED_WITH_EMPTY_QUEUE**: advanced 8->9 with nothing queued (last command ran at tick 6). Advanced the clock with nothing queued, so the rover stood idle.
  - Information the agent had: telemetry packet for tick 5, delivered at tick 8 (position [24.8, 13.47], battery 89.5); rules(): first_execution_tick
- Reference instead: at tick 8 uplink [drive 194° 4.33 m, drive 194° 4.33 m, sample]; then sample t1 (tick 14), t3 (tick 18), t4 (tick 21), t5 (tick 24); finish home, score 7
- Agent's own words: none recorded (trajectory step 7 holds the tool call but no message or reasoning text)

### 2. call 15, uplink [drive 254.4° 5 m, drive 254.4° 1.04 m, sample] at tick 23: −0.75 points (−0.075 reward)

- **SAMPLE_MISSED**: sample command 15 at tick 29 failed (aim). A sample command found no unsampled target in range (or not enough battery).
  - Information the agent had: telemetry packet for tick 20, delivered at tick 23 (position [17.26, 24.3], battery 55.6); acknowledgement of call 15: execute tick [29]
- Reference instead: at tick 23 uplink [drive 246.4° 2.87 m, drive 246.4° 2.87 m, sample]; then sample t5 (tick 24), t1 (tick 29); finish home, score 4
- Agent's own words: none recorded (trajectory step 14 holds the tool call but no message or reasoning text)

### 3. call 9, uplink [drive 179° 5 m, drive 179° 2.9 m, sample] at tick 14: −0.25 points (−0.025 reward)

- **STALE_AIM**: aimed at t1 from the position in packet tick 11, ignoring 3 commands in transit. Aimed from the last delivered position, ignoring drives still in transit.
  - Information the agent had: telemetry packet for tick 11, delivered at tick 14 (position [24.21, 13.91], battery 83.5); acknowledgements for commands still in transit, execute ticks 13, 14, 15; rules(): first_execution_tick / telemetry_arrival_tick
- **SAMPLE_MISSED**: sample command 9 at tick 20 failed (stale_aim). A sample command found no unsampled target in range (or not enough battery).
  - Information the agent had: telemetry packet for tick 11, delivered at tick 14 (position [24.21, 13.91], battery 83.5); acknowledgement of call 9: execute tick [20]
- Reference instead: at tick 14 uplink [drive 237.1° 4.58 m, drive 237.1° 4.58 m, drive 237.1° 4.58 m, sample]; then sample t1 (tick 21), t4 (tick 25, late), t5 (tick 28); finish home, score 4.5
- Agent's own words: none recorded (trajectory step 10 holds the tool call but no message or reasoning text)

## Where the agent did better than the reference

- call 8, advance 5 at tick 9: +0.25 points (the reference taking over before this call would have scored 4.25, after it 4.5)
- call 11, uplink [drive 291° 5 m, drive 291° 2.59 m, sample] at tick 18: +0.25 points (the reference taking over before this call would have scored 4, after it 4.25)

## Infrastructure (kept apart from reasoning)

None found: every agent call reached the simulator, Harbor recorded no exception, the rebuild matches the run and reward.txt matches the evaluator.

## Other reasoning findings (no points lost against the reference)

- call 7: **SAMPLE_MISSED**: sample command 6 at tick 15 failed (aim)
- call 17: **DISCOVERY_MISSED**: d1 (value 3, deadline tick 33) arrived in the packet for tick 21 at tick 24; never sampled
- call 20: **LATE_SAMPLE**: t1 sampled at tick 37, deadline tick 29

## Episode outcome

- **TARGETS_LEFT**: never sampled: d1, t3, t4
- superlog labels unavailable here (ModuleNotFoundError: No module named 'numpy')

## Every decision

| call | tick | what the agent did | reference before | reference after | points lost | tags |
|---:|---|---|---:|---:|---:|---|
| 3 | 0→0 | uplink [drive 309.1° 5 m, drive 309.1° 3.03 m, sample] | 7 | 7 | 0 |  |
| 4 | 0→5 | advance 5 | 7 | 7 | 0 |  |
| 5 | 5→8 | advance 3 | 7 | 7 | 0 |  |
| 6 | 8→9 | advance 1 | 7 | 4.25 | 2.75 | WAITED_WITH_EMPTY_QUEUE |
| 7 | 9→9 | uplink [drive 94.9° 5 m, drive 94.9° 4.42 m, sample] | 4.25 | 4.25 | 0 | SAMPLE_MISSED |
| 8 | 9→14 | advance 5 | 4.25 | 4.5 | -0.25 |  |
| 9 | 14→14 | uplink [drive 179° 5 m, drive 179° 2.9 m, sample] | 4.5 | 4.25 | 0.25 | SAMPLE_MISSED, STALE_AIM |
| 10 | 14→18 | advance 4 | 4.25 | 4 | 0.25 | QUEUE_RAN_DRY |
| 11 | 18→18 | uplink [drive 291° 5 m, drive 291° 2.59 m, sample] | 4 | 4.25 | -0.25 |  |
| 12 | 18→20 | advance 2 | 4.25 | 4.25 | 0 |  |
| 13 | 20→22 | advance 2 | 4.25 | 4 | 0.25 | QUEUE_RAN_DRY |
| 14 | 22→23 | advance 1 | 4 | 4 | 0 |  |
| 15 | 23→23 | uplink [drive 254.4° 5 m, drive 254.4° 1.04 m, sample] | 4 | 3.25 | 0.75 | SAMPLE_MISSED |
| 16 | 23→26 | advance 3 | 3.25 | 3.25 | 0 |  |
| 17 | 26→27 | advance 1 | 3.25 | 3.25 | 0 | DISCOVERY_MISSED |
| 18 | 27→31 | advance 4 | 3.25 | 3.25 | 0 |  |
| 19 | 31→32 | advance 1 | 3.25 | 3.25 | 0 |  |
| 20 | 32→32 | uplink [drive 152.3° 0.81 m, sample, drive 75° 5 m, drive 75° 4.04 m] | 3.25 | 3.25 | 0 | LATE_SAMPLE |
| 21 | 32→37 | advance 5 | 3.25 | 3.25 | 0 |  |
| 22 | 37→42 | advance 5 | 3.25 | 3.25 | 0 |  |
| 23 | 42→45 | advance 3 | 3.25 | 3.25 | 0 |  |
| 24 | 45→50 | advance 5 | 3.25 | 3.25 | 0 |  |
| 25 | 50→50 | advance 5 | 3.25 | 3.25 | 0 |  |

*Reference before/after*: the score if the reference took over just before or just after this call, knowing only what the agent knew then (delivered telemetry, rules, map, its own acknowledgements). *Points lost* = before − after; the column plus the stop loss adds up to the gap.
