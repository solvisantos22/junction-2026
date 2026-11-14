# Decision audit: overnight-a06-rush-noisy-seed504-r2-opus-5-5

- Model: anthropic/claude-opus-5-5
- Profile `rush_noisy`, seed 504, delay 3 ticks, horizon 50
- Agent: **0** of 10 (reward 0.000, reward.txt 0.000)
- Reference (`kf_mpc`) from the start: **7** (reward 0.700)
- Gap: 7 points = 0.700 reward. Decisions account for 7, stopping early for 0.
- Rebuild reproduces the saved run tick for tick: **yes**

## Main mistakes

### 1. call 22, uplink [drive 79.6° 4.15 m, drive 79.6° 4.15 m, drive 79.6° 4.15 m, drive 79.6° 4.15 m, sample] at tick 26: −6.25 points (−0.625 reward)

- **LATE_SAMPLE**: d1 sampled at tick 34, deadline tick 33. A target was sampled after its published deadline, for reduced value.
  - Information the agent had: acknowledgement of call 22: execute tick [34]; map target d1 (deadline tick 33, value 3); map(): targets[d1].deadline_tick
- Reference instead: at tick 26 uplink [drive 70.9° 4.39 m, drive 70.9° 4.39 m]; then sample t1 (tick 29); finish home, score 6.25
- Agent's own words: none recorded (trajectory step 17 holds the tool call but no message or reasoning text)

### 2. call 10, uplink [drive 173.2° 3.8 m, drive 173.2° 3.8 m, sample] at tick 13: −0.75 points (−0.075 reward)

- **SAMPLE_MISSED**: sample command 9 at tick 19 failed (aim). A sample command found no unsampled target in range (or not enough battery).
  - Information the agent had: telemetry packet for tick 10, delivered at tick 13 (position [24.64, 13.68], battery 84.0); acknowledgement of call 10: execute tick [19]
- Reference instead: at tick 13 uplink [drive 176.8° 3.9 m, drive 176.8° 3.9 m, sample]; then sample t4 (tick 14), t3 (tick 19), t1 (tick 23), t5 (tick 26); finish home, score 7
- Agent's own words: none recorded (trajectory step 9 holds the tool call but no message or reasoning text)

## Infrastructure (kept apart from reasoning)

None found: every agent call reached the simulator, Harbor recorded no exception, the rebuild matches the run and reward.txt matches the evaluator.

## Other reasoning findings (no points lost against the reference)

- call 13: **LATE_SAMPLE**: t3 sampled at tick 22, deadline tick 19
- call 21: **DISCOVERY_MISSED**: d1 (value 3, deadline tick 33) arrived in the packet for tick 21 at tick 24; sampled late

## Episode outcome

- **DEAD**: the rover died
- superlog labels unavailable here (ModuleNotFoundError: No module named 'numpy')

## Every decision

| call | tick | what the agent did | reference before | reference after | points lost | tags |
|---:|---|---|---:|---:|---:|---|
| 3 | 0→0 | uplink [drive 309.1° 4.02 m, drive 309.1° 4.01 m, sample] | 7 | 7 | 0 |  |
| 4 | 0→5 | advance 5 | 7 | 7 | 0 |  |
| 5 | 5→8 | advance 3 | 7 | 7 | 0 |  |
| 6 | 8→8 | uplink [drive 95.3° 4.6 m, drive 95.3° 4.6 m, sample] | 7 | 7 | 0 |  |
| 7 | 8→9 | advance 1 | 7 | 7 | 0 |  |
| 8 | 9→13 | advance 4 | 7 | 7 | 0 |  |
| 10 | 13→13 | uplink [drive 173.2° 3.8 m, drive 173.2° 3.8 m, sample] | 7 | 6.25 | 0.75 | SAMPLE_MISSED |
| 11 | 13→16 | advance 3 | 6.25 | 6.25 | 0 |  |
| 12 | 16→17 | advance 1 | 6.25 | 6.25 | 0 |  |
| 13 | 17→17 | uplink [drive 237.5° 1 m, sample] | 6.25 | 6.25 | 0 | LATE_SAMPLE |
| 14 | 17→19 | advance 2 | 6.25 | 6.25 | 0 |  |
| 15 | 19→19 | uplink [drive 296.2° 3.73 m, drive 296.2° 3.72 m, sample] | 6.25 | 6.25 | 0 |  |
| 16 | 19→22 | advance 3 | 6.25 | 6.25 | 0 |  |
| 18 | 22→23 | advance 1 | 6.25 | 6.25 | 0 |  |
| 19 | 23→23 | uplink [drive 243° 2.68 m, drive 243° 2.67 m, sample] | 6.25 | 6.25 | 0 |  |
| 20 | 23→25 | advance 2 | 6.25 | 6.25 | 0 |  |
| 21 | 25→26 | advance 1 | 6.25 | 6.25 | 0 | DISCOVERY_MISSED |
| 22 | 26→26 | uplink [drive 79.6° 4.15 m, drive 79.6° 4.15 m, drive 79.6° 4.15 m, drive 79.6° 4.15 m, sample] | 6.25 | 0 | 6.25 | LATE_SAMPLE |
| 23 | 26→28 | advance 2 | 0 | 0 | 0 |  |
| 24 | 28→33 | advance 5 | 0 | 0 | 0 |  |
| 25 | 33→38 | advance 5 | 0 | 0 | 0 |  |
| 26 | 38→43 | advance 5 | 0 | 0 | 0 |  |
| 27 | 43→48 | advance 5 | 0 | 0 | 0 |  |
| 28 | 48→50 | advance 2 | 0 | 0 | 0 |  |

*Reference before/after*: the score if the reference took over just before or just after this call, knowing only what the agent knew then (delivered telemetry, rules, map, its own acknowledgements). *Points lost* = before − after; the column plus the stop loss adds up to the gap.
