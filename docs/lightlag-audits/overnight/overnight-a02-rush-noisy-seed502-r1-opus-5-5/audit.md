# Decision audit: overnight-a02-rush-noisy-seed502-r1-opus-5-5

- Model: anthropic/claude-opus-5-5
- Profile `rush_noisy`, seed 502, delay 3 ticks, horizon 50
- Agent: **6** of 13 (reward 0.462, reward.txt 0.462)
- Reference (`kf_mpc`) from the start: **10** (reward 0.769)
- Gap: 4 points = 0.308 reward. Decisions account for 4, stopping early for 0.
- Rebuild reproduces the saved run tick for tick: **yes**

## Main mistakes

### 1. call 6, uplink [drive 5.6° 5 m] at tick 8: −3 points (−0.231 reward)

- **PLAN_WORSE_THAN_REFERENCE**: from the same information the reference scored 10 instead of 7. Legal and on time, but the reference's plan from the same information scored more.
  - Information the agent had: telemetry packet for tick 5, delivered at tick 8 (position [19.39, 23.87], battery 90.3)
- Reference instead: at tick 8 uplink [drive 253.9° 1.57 m, drive 272.1° 4.58 m, drive 272.1° 4.58 m, sample]; then sample t3 (tick 15), t2 (tick 18), d2 (tick 21); finish home, score 10
- Agent's own words: none recorded (trajectory step 7 holds the tool call but no message or reasoning text)

### 2. call 12, uplink [drive 257.4° 5 m, drive 257.4° 5 m, drive 257.4° 2.38 m, sample] at tick 15: −3 points (−0.231 reward)

- **STALE_AIM**: aimed at t3 from the position in packet tick 12, ignoring 3 commands in transit. Aimed from the last delivered position, ignoring drives still in transit.
  - Information the agent had: telemetry packet for tick 12, delivered at tick 15 (position [20.22, 26.75], battery 66.8); acknowledgements for commands still in transit, execute ticks 14, 15, 16; rules(): first_execution_tick / telemetry_arrival_tick
- **SAMPLE_MISSED**: sample command 12 at tick 22 failed (stale_aim). A sample command found no unsampled target in range (or not enough battery).
  - Information the agent had: telemetry packet for tick 12, delivered at tick 15 (position [20.22, 26.75], battery 66.8); acknowledgement of call 12: execute tick [22]
- **DISCOVERY_MISSED**: d2 (value 3, deadline tick 22) arrived in the packet for tick 10 at tick 13; never sampled. A discovered target arrived in telemetry and was never collected (or only late).
  - Information the agent had: telemetry packet for tick 10, delivered at tick 13; map target d2 (deadline tick 22, value 3)
- Reference instead: at tick 15 uplink [drive 260.6° 4.08 m, drive 260.6° 4.08 m, drive 260.6° 4.08 m, sample]; then sample d2 (tick 22), t2 (tick 25); finish home, score 9
- Agent's own words: none recorded (trajectory step 11 holds the tool call but no message or reasoning text)

### 3. call 10, uplink [drive 2.5° 1.55 m, sample] at tick 11: −1 points (−0.077 reward)

- **SAMPLE_MISSED**: sample command 8 at tick 16 failed (slip_not_corrected). A sample command found no unsampled target in range (or not enough battery).
  - Information the agent had: telemetry packet for tick 8, delivered at tick 11 (position [16.38, 27.27], battery 78.8); acknowledgement of call 10: execute tick [16]; packet for tick 15 (delivered tick 18): wheel 1.55 m vs visual 1.162 m on sand; rules(): slip_ranges / slip_model
- Reference instead: at tick 11 uplink [drive 17.6° 1.05 m, sample]; then sample t4 (tick 16), t2 (tick 25), t3 (tick 28); finish home, score 8
- Agent's own words: none recorded (trajectory step 10 holds the tool call but no message or reasoning text)

## Where the agent did better than the reference

- call 3, uplink [drive 101.4° 4.18 m, sample, drive 139.5° 4.7 m, sample] at tick 0: +0.5 points (the reference taking over before this call would have scored 10, after it 10.5)
- call 7, advance 2 at tick 8: +1 points (the reference taking over before this call would have scored 7, after it 8)
- call 11, advance 4 at tick 11: +2 points (the reference taking over before this call would have scored 7, after it 9)

## Infrastructure (kept apart from reasoning)

None found: every agent call reached the simulator, Harbor recorded no exception, the rebuild matches the run and reward.txt matches the evaluator.

## Other reasoning findings (no points lost against the reference)

- call 16: **DISCOVERY_MISSED**: d1 (value 2, deadline tick 28) arrived in the packet for tick 21 at tick 24; never sampled

## Episode outcome

- **TARGETS_LEFT**: never sampled: d1, d2, t3, t4
- superlog labels unavailable here (ModuleNotFoundError: No module named 'numpy')

## Every decision

| call | tick | what the agent did | reference before | reference after | points lost | tags |
|---:|---|---|---:|---:|---:|---|
| 3 | 0→0 | uplink [drive 101.4° 4.18 m, sample, drive 139.5° 4.7 m, sample] | 10 | 10.5 | -0.5 |  |
| 4 | 0→5 | advance 5 | 10.5 | 10 | 0.5 | QUEUE_RAN_DRY |
| 5 | 5→8 | advance 3 | 10 | 10 | 0 |  |
| 6 | 8→8 | uplink [drive 5.6° 5 m] | 10 | 7 | 3 | PLAN_WORSE_THAN_REFERENCE |
| 7 | 8→10 | advance 2 | 7 | 8 | -1 |  |
| 8 | 10→10 | uplink [drive 2.2° 5 m] | 8 | 8 | 0 |  |
| 9 | 10→11 | advance 1 | 8 | 8 | 0 |  |
| 10 | 11→11 | uplink [drive 2.5° 1.55 m, sample] | 8 | 7 | 1 | SAMPLE_MISSED |
| 11 | 11→15 | advance 4 | 7 | 9 | -2 |  |
| 12 | 15→15 | uplink [drive 257.4° 5 m, drive 257.4° 5 m, drive 257.4° 2.38 m, sample] | 9 | 6 | 3 | DISCOVERY_MISSED, SAMPLE_MISSED, STALE_AIM |
| 13 | 15→18 | advance 3 | 6 | 6 | 0 |  |
| 14 | 18→21 | advance 3 | 6 | 6 | 0 |  |
| 15 | 21→24 | advance 3 | 6 | 6 | 0 |  |
| 16 | 24→24 | uplink [drive 86.2° 5 m, drive 86.2° 1.2 m, sample, drive 209.1° 3.08 m] | 6 | 6 | 0 | DISCOVERY_MISSED |
| 17 | 24→29 | advance 5 | 6 | 6 | 0 |  |
| 18 | 29→34 | advance 5 | 6 | 6 | 0 |  |
| 19 | 34→38 | advance 4 | 6 | 6 | 0 |  |
| 20 | 38→43 | advance 5 | 6 | 6 | 0 |  |
| 21 | 43→48 | advance 5 | 6 | 6 | 0 |  |
| 22 | 48→50 | advance 2 | 6 | 6 | 0 |  |

*Reference before/after*: the score if the reference took over just before or just after this call, knowing only what the agent knew then (delivered telemetry, rules, map, its own acknowledgements). *Points lost* = before − after; the column plus the stop loss adds up to the gap.
