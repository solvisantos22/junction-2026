# Decision audit: rocks-rush-noisy-seed1026-r3-opus-5-5

- Model: anthropic/claude-opus-5-5
- Profile `rush_noisy`, seed 1026, delay 3 ticks, horizon 50
- Agent: **9** of 13 (reward 0.692, reward.txt 0.692)
- Reference (`kf_mpc`) from the start: **10** (reward 0.769)
- Gap: 1 points = 0.077 reward. Decisions account for 1, stopping early for 0.
- Rebuild reproduces the saved run tick for tick: **yes**

## Main mistakes

### 1. call 7, advance 2 at tick 5: −4 points (−0.308 reward)

- **QUEUE_RAN_DRY**: queue ends at tick 9; waiting until 7 means the next command cannot run before tick 11 (1 more idle ticks). Advanced instead of queuing the next leg; the queue emptied before new commands could arrive.
  - Information the agent had: telemetry packet for tick 2, delivered at tick 5 (position [19.77, 19.67], battery 99.0); rules(): first_execution_tick
- Reference instead: at tick 6 uplink [drive 110.7° 3.82 m, drive 110.7° 3.82 m, sample]; then sample t5 (tick 6), t1 (tick 9), t4 (tick 12), t3 (tick 19), d2 (tick 21); finish home, score 10
- Agent's own words: none recorded (trajectory step 8 holds the tool call but no message or reasoning text)

### 2. call 13, advance 1 at tick 11: −1.25 points (−0.096 reward)

- **QUEUE_RAN_DRY**: queue ends at tick 14; waiting until 12 means the next command cannot run before tick 16 (1 more idle ticks). Advanced instead of queuing the next leg; the queue emptied before new commands could arrive.
  - Information the agent had: telemetry packet for tick 8, delivered at tick 11 (position [21.13, 22.86], battery 80.1); rules(): first_execution_tick
- Reference instead: at tick 11 uplink [drive 193.6° 4.66 m, drive 227.5° 3.38 m, sample]; then sample t4 (tick 14), d2 (tick 21); finish home, score 8
- Agent's own words: none recorded (trajectory step 13 holds the tool call but no message or reasoning text)

### 3. call 16, uplink [sample] at tick 14: −1.25 points (−0.096 reward)

- **PLAN_WORSE_THAN_REFERENCE**: from the same information the reference scored 8 instead of 6.75. Legal and on time, but the reference's plan from the same information scored more.
  - Information the agent had: telemetry packet for tick 11, delivered at tick 14 (position [19.72, 26.88], battery 69.1)
- **DISCOVERY_MISSED**: d1 (value 2, deadline tick 17) arrived in the packet for tick 10 at tick 13; never sampled. A discovered target arrived in telemetry and was never collected (or only late).
  - Information the agent had: telemetry packet for tick 10, delivered at tick 13; map target d1 (deadline tick 17, value 2)
- Reference instead: at tick 14 uplink [drive 320° 1.34 m, drive 286.3° 2.64 m, drive 286.3° 2.64 m, sample]; then sample d2 (tick 21); finish home, score 8
- Agent's own words: none recorded (trajectory step 16 holds the tool call but no message or reasoning text)

## Where the agent did better than the reference

- call 8, uplink [drive 110.7° 5 m] at tick 7: +1.75 points (the reference taking over before this call would have scored 6, after it 7.75)
- call 10, advance 1 at tick 8: +0.25 points (the reference taking over before this call would have scored 7.75, after it 8)
- call 14, uplink [drive 193.1° 3.57 m, drive 221.3° 3.62 m] at tick 12: +1.25 points (the reference taking over before this call would have scored 6.75, after it 8)
- call 18, uplink [drive 311.2° 2.41 m, drive 281.8° 4.26 m, sample] at tick 15: +2.25 points (the reference taking over before this call would have scored 6.75, after it 9)

## Infrastructure (kept apart from reasoning)

None found: every agent call reached the simulator, Harbor recorded no exception, the rebuild matches the run and reward.txt matches the evaluator.

## Other reasoning findings (no points lost against the reference)

- call 20: **SAMPLE_MISSED**: sample command 17 at tick 23 failed (aim)

## Episode outcome

- **TARGETS_LEFT**: never sampled: d1, t3
- superlog labels unavailable here (ModuleNotFoundError: No module named 'numpy')

## Every decision

| call | tick | what the agent did | reference before | reference after | points lost | tags |
|---:|---|---|---:|---:|---:|---|
| 3 | 0→0 | uplink [drive 19.5° 5 m, drive 19.5° 2.26 m, sample] | 10 | 10 | 0 |  |
| 4 | 0→0 | uplink [drive 171.1° 5 m, drive 171.1° 0.67 m] | 10 | 10 | 0 |  |
| 5 | 0→5 | advance 5 | 10 | 10 | 0 |  |
| 6 | 5→5 | uplink [sample] | 10 | 10 | 0 |  |
| 7 | 5→7 | advance 2 | 10 | 6 | 4 | QUEUE_RAN_DRY |
| 8 | 7→7 | uplink [drive 110.7° 5 m] | 6 | 7.75 | -1.75 |  |
| 9 | 7→8 | advance 1 | 7.75 | 7.75 | 0 |  |
| 10 | 8→9 | advance 1 | 7.75 | 8 | -0.25 |  |
| 11 | 9→9 | uplink [drive 110.7° 2.6 m, sample] | 8 | 8 | 0 |  |
| 12 | 9→11 | advance 2 | 8 | 8 | 0 |  |
| 13 | 11→12 | advance 1 | 8 | 6.75 | 1.25 | QUEUE_RAN_DRY |
| 14 | 12→12 | uplink [drive 193.1° 3.57 m, drive 221.3° 3.62 m] | 6.75 | 8 | -1.25 |  |
| 15 | 12→14 | advance 2 | 8 | 8 | 0 |  |
| 16 | 14→14 | uplink [sample] | 8 | 6.75 | 1.25 | DISCOVERY_MISSED, PLAN_WORSE_THAN_REFERENCE |
| 17 | 14→15 | advance 1 | 6.75 | 6.75 | 0 |  |
| 18 | 15→15 | uplink [drive 311.2° 2.41 m, drive 281.8° 4.26 m, sample] | 6.75 | 9 | -2.25 |  |
| 19 | 15→16 | advance 1 | 9 | 9 | 0 |  |
| 20 | 16→16 | uplink [drive 212.2° 4.17 m, sample] | 9 | 9 | 0 | SAMPLE_MISSED |
| 21 | 16→17 | advance 1 | 9 | 9 | 0 |  |
| 22 | 17→20 | advance 3 | 9 | 9 | 0 |  |
| 23 | 20→20 | uplink [drive 15.4° 5 m, drive 15.4° 2.86 m] | 9 | 9 | 0 |  |
| 24 | 20→21 | advance 1 | 9 | 9 | 0 |  |
| 25 | 21→24 | advance 3 | 9 | 9 | 0 |  |
| 26 | 24→26 | advance 2 | 9 | 9 | 0 |  |
| 27 | 26→31 | advance 5 | 9 | 9 | 0 |  |
| 28 | 31→36 | advance 5 | 9 | 9 | 0 |  |
| 29 | 36→41 | advance 5 | 9 | 9 | 0 |  |
| 30 | 41→46 | advance 5 | 9 | 9 | 0 |  |
| 31 | 46→50 | advance 4 | 9 | 9 | 0 |  |

*Reference before/after*: the score if the reference took over just before or just after this call, knowing only what the agent knew then (delivered telemetry, rules, map, its own acknowledgements). *Points lost* = before − after; the column plus the stop loss adds up to the gap.
