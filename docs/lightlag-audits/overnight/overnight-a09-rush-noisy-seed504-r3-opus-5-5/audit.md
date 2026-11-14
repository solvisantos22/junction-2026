# Decision audit: overnight-a09-rush-noisy-seed504-r3-opus-5-5

- Model: anthropic/claude-opus-5-5
- Profile `rush_noisy`, seed 504, delay 3 ticks, horizon 50
- Agent: **6** of 10 (reward 0.600, reward.txt 0.600)
- Reference (`kf_mpc`) from the start: **7** (reward 0.700)
- Gap: 1 points = 0.100 reward. Decisions account for 1, stopping early for 0.
- Rebuild reproduces the saved run tick for tick: **yes**

## Main mistakes

### 1. call 9, uplink [drive 175.8° 5 m, drive 175.8° 2.74 m, sample] at tick 9: −1 points (−0.100 reward)

- **STALE_AIM**: aimed at t1 from the position in packet tick 6, ignoring 3 commands in transit. Aimed from the last delivered position, ignoring drives still in transit.
  - Information the agent had: telemetry packet for tick 6, delivered at tick 9 (position [24.95, 13.23], battery 86.0); acknowledgements for commands still in transit, execute ticks 12, 13, 14; rules(): first_execution_tick / telemetry_arrival_tick
- **SAMPLE_MISSED**: sample command 9 at tick 17 failed (stale_aim). A sample command found no unsampled target in range (or not enough battery).
  - Information the agent had: telemetry packet for tick 6, delivered at tick 9 (position [24.95, 13.23], battery 86.0); acknowledgement of call 9: execute tick [17]
- Reference instead: at tick 11 uplink [drive 178.6° 3.93 m, drive 178.6° 3.93 m, sample]; then sample t4 (tick 14), t3 (tick 17), t1 (tick 21), t5 (tick 24); finish home, score 7
- Agent's own words: none recorded (trajectory step 9 holds the tool call but no message or reasoning text)

### 2. call 20, uplink [drive 328.7° 0.78 m, sample, drive 71.5° 5 m, drive 71.5° 4.13 m] at tick 24: −0.25 points (−0.025 reward)

- **SAMPLE_MISSED**: sample command 17 at tick 29 failed (already_sampled). A sample command found no unsampled target in range (or not enough battery).
  - Information the agent had: telemetry packet for tick 21, delivered at tick 24 (position [16.04, 12.64], battery 39.5); acknowledgement of call 20: execute tick [29]
- **DISCOVERY_MISSED**: d1 (value 3, deadline tick 33) arrived in the packet for tick 21 at tick 24; never sampled. A discovered target arrived in telemetry and was never collected (or only late).
  - Information the agent had: telemetry packet for tick 21, delivered at tick 24; map target d1 (deadline tick 33, value 3)
- Reference instead: at tick 24 uplink [drive 92.7° 3.78 m, drive 92.7° 3.78 m, drive 92.7° 3.78 m, sample]; then sample t3 (tick 31, late); finish home, score 6.25
- Agent's own words: none recorded (trajectory step 20 holds the tool call but no message or reasoning text)

## Where the agent did better than the reference

- call 18, advance 1 at tick 22: +0.25 points (the reference taking over before this call would have scored 6, after it 6.25)

## Infrastructure (kept apart from reasoning)

None found: every agent call reached the simulator, Harbor recorded no exception, the rebuild matches the run and reward.txt matches the evaluator.

## Episode outcome

- **TARGETS_LEFT**: never sampled: d1, t3
- superlog labels unavailable here (ModuleNotFoundError: No module named 'numpy')

## Every decision

| call | tick | what the agent did | reference before | reference after | points lost | tags |
|---:|---|---|---:|---:|---:|---|
| 3 | 0→0 | uplink [drive 309.1° 5 m, drive 309.1° 3.02 m, sample] | 7 | 7 | 0 |  |
| 4 | 0→5 | advance 5 | 7 | 7 | 0 |  |
| 5 | 5→7 | advance 2 | 7 | 7 | 0 |  |
| 6 | 7→8 | advance 1 | 7 | 7 | 0 |  |
| 7 | 8→8 | uplink [drive 94.8° 5 m, drive 94.8° 4.42 m, sample] | 7 | 7 | 0 |  |
| 8 | 8→9 | advance 1 | 7 | 7 | 0 |  |
| 9 | 9→9 | uplink [drive 175.8° 5 m, drive 175.8° 2.74 m, sample] | 7 | 6 | 1 | SAMPLE_MISSED, STALE_AIM |
| 10 | 9→13 | advance 4 | 6 | 6 | 0 |  |
| 11 | 13→14 | advance 1 | 6 | 6 | 0 |  |
| 12 | 14→14 | uplink [drive 292.2° 5 m, drive 292.2° 2.87 m, sample] | 6 | 6 | 0 |  |
| 13 | 14→17 | advance 3 | 6 | 6 | 0 |  |
| 14 | 17→17 | uplink [drive 241.2° 5 m, drive 241.2° 0.55 m, sample] | 6 | 6 | 0 |  |
| 15 | 17→20 | advance 3 | 6 | 6 | 0 |  |
| 17 | 20→22 | advance 2 | 6 | 6 | 0 |  |
| 18 | 22→23 | advance 1 | 6 | 6.25 | -0.25 |  |
| 19 | 23→24 | advance 1 | 6.25 | 6.25 | 0 |  |
| 20 | 24→24 | uplink [drive 328.7° 0.78 m, sample, drive 71.5° 5 m, drive 71.5° 4.13 m] | 6.25 | 6 | 0.25 | DISCOVERY_MISSED, SAMPLE_MISSED |
| 21 | 24→26 | advance 2 | 6 | 6 | 0 |  |
| 22 | 26→31 | advance 5 | 6 | 6 | 0 |  |
| 23 | 31→36 | advance 5 | 6 | 6 | 0 |  |
| 24 | 36→36 | uplink [drive 163.9° 0.8 m] | 6 | 6 | 0 |  |
| 25 | 36→41 | advance 5 | 6 | 6 | 0 |  |
| 26 | 41→45 | advance 4 | 6 | 6 | 0 |  |
| 27 | 45→50 | advance 5 | 6 | 6 | 0 |  |

*Reference before/after*: the score if the reference took over just before or just after this call, knowing only what the agent knew then (delivered telemetry, rules, map, its own acknowledgements). *Points lost* = before − after; the column plus the stop loss adds up to the gap.
