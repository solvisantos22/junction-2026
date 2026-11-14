# Decision audit: overnight-b02-c-rush-noisy-seed504-r1-opus-5-5

- Model: anthropic/claude-opus-5-5
- Profile `rush_noisy`, seed 504, delay 3 ticks, horizon 50
- Agent: **2.25** of 10 (reward 0.225, reward.txt 0.225)
- Reference (`kf_mpc`) from the start: **7** (reward 0.700)
- Gap: 4.75 points = 0.475 reward. Decisions account for 4.75, stopping early for 0.
- Rebuild reproduces the saved run tick for tick: **yes**

## Main mistakes

### 1. call 5, advance 3 at tick 5: −1.75 points (−0.175 reward)

- **WAITED_WITH_EMPTY_QUEUE**: advanced 5->8 with nothing queued (last command ran at tick 5). Advanced the clock with nothing queued, so the rover stood idle.
  - Information the agent had: telemetry packet for tick 2, delivered at tick 5 (position [19.98, 20.1], battery 99.0); rules(): first_execution_tick
- Reference instead: at tick 5 uplink [sample]; then sample t2 (tick 9), t4 (tick 18), t1 (tick 22), t5 (tick 25), t3 (tick 28, late); finish home, score 6.25
- Agent's own words: none recorded (trajectory step 5 holds the tool call but no message or reasoning text)

### 2. call 9, uplink [drive 294.5° 5 m, drive 294.5° 2.5 m, sample] at tick 13: −1 points (−0.100 reward)

- **SAMPLE_MISSED**: sample command 12 at tick 23 failed (aim). A sample command found no unsampled target in range (or not enough battery).
  - Information the agent had: telemetry packet for tick 10, delivered at tick 13 (position [24.57, 13.82], battery 87.1); acknowledgement of call 9: execute tick [23]
- Reference instead: at tick 17 uplink [drive 270.4° 3.95 m, drive 270.4° 3.95 m, drive 270.4° 3.95 m, sample]; then sample t1 (tick 24), t5 (tick 27), t3 (tick 30, late); finish home, score 4.25
- Agent's own words: none recorded (trajectory step 9 holds the tool call but no message or reasoning text)

### 3. call 15, uplink [drive 234.6° 1.32 m, sample] at tick 21: −1 points (−0.100 reward)

- **SAMPLE_MISSED**: sample command 15 at tick 26 failed (aim). A sample command found no unsampled target in range (or not enough battery).
  - Information the agent had: telemetry packet for tick 18, delivered at tick 21 (position [20.04, 23.36], battery 62.9); acknowledgement of call 15: execute tick [26]
- Reference instead: at tick 21 uplink [drive 227.2° 1.61 m, sample]; then sample t1 (tick 26), t3 (tick 30, late); finish home, score 3.25
- Agent's own words: none recorded (trajectory step 15 holds the tool call but no message or reasoning text)

## Where the agent did better than the reference

- call 19, advance 3 at tick 26: +0.25 points (the reference taking over before this call would have scored 2.25, after it 2.5)

## Infrastructure (kept apart from reasoning)

None found: every agent call reached the simulator, Harbor recorded no exception, the rebuild matches the run and reward.txt matches the evaluator.

## Other reasoning findings (no points lost against the reference)

- call 18: **DISCOVERY_MISSED**: d1 (value 3, deadline tick 33) arrived in the packet for tick 21 at tick 24; never sampled

## Episode outcome

- **TARGETS_LEFT**: never sampled: d1, t3, t4, t5
- superlog labels unavailable here (ModuleNotFoundError: No module named 'numpy')

## Every decision

| call | tick | what the agent did | reference before | reference after | points lost | tags |
|---:|---|---|---:|---:|---:|---|
| 3 | 0→0 | uplink [drive 309.1° 5 m, drive 309.1° 2.9 m] | 7 | 7 | 0 |  |
| 4 | 0→5 | advance 5 | 7 | 6.25 | 0.75 | QUEUE_RAN_DRY |
| 5 | 5→8 | advance 3 | 6.25 | 4.5 | 1.75 | WAITED_WITH_EMPTY_QUEUE |
| 6 | 8→8 | uplink [sample, drive 95.3° 5 m, drive 95.3° 4.19 m] | 4.5 | 4.5 | 0 |  |
| 7 | 8→13 | advance 5 | 4.5 | 4.5 | 0 |  |
| 8 | 13→13 | uplink [sample, drive 178.1° 5 m, drive 178.1° 2.63 m, sample] | 4.5 | 4.25 | 0.25 | SAMPLE_MISSED, STALE_AIM |
| 9 | 13→13 | uplink [drive 294.5° 5 m, drive 294.5° 2.5 m, sample] | 4.25 | 3.25 | 1 | SAMPLE_MISSED |
| 10 | 13→16 | advance 3 | 3.25 | 3.25 | 0 |  |
| 11 | 16→18 | advance 2 | 3.25 | 3.25 | 0 |  |
| 12 | 18→20 | advance 2 | 3.25 | 3.25 | 0 |  |
| 13 | 20→20 | uplink [drive 243.6° 4.5 m] | 3.25 | 3.25 | 0 |  |
| 14 | 20→21 | advance 1 | 3.25 | 3.25 | 0 |  |
| 15 | 21→21 | uplink [drive 234.6° 1.32 m, sample] | 3.25 | 2.25 | 1 | SAMPLE_MISSED |
| 16 | 21→23 | advance 2 | 2.25 | 2.25 | 0 |  |
| 17 | 23→25 | advance 2 | 2.25 | 2.25 | 0 |  |
| 18 | 25→26 | advance 1 | 2.25 | 2.25 | 0 | DISCOVERY_MISSED |
| 19 | 26→29 | advance 3 | 2.25 | 2.5 | -0.25 |  |
| 20 | 29→31 | advance 2 | 2.5 | 2.5 | 0 |  |
| 21 | 31→31 | uplink [drive 219° 0.83 m, sample, drive 72° 5 m, drive 72° 4.08 m] | 2.5 | 2.25 | 0.25 | LATE_SAMPLE |
| 22 | 31→36 | advance 5 | 2.25 | 2.25 | 0 |  |
| 23 | 36→40 | advance 4 | 2.25 | 2.25 | 0 |  |
| 24 | 40→44 | advance 4 | 2.25 | 2.25 | 0 |  |
| 25 | 44→44 | uplink [drive 285° 0.24 m] | 2.25 | 2.25 | 0 |  |
| 26 | 44→49 | advance 5 | 2.25 | 2.25 | 0 |  |
| 27 | 49→50 | advance 1 | 2.25 | 2.25 | 0 |  |

*Reference before/after*: the score if the reference took over just before or just after this call, knowing only what the agent knew then (delivered telemetry, rules, map, its own acknowledgements). *Points lost* = before − after; the column plus the stop loss adds up to the gap.
