# Decision audit: overnight-a07-rush-seed501-r3-opus-5-5

- Model: anthropic/claude-opus-5-5
- Profile `rush`, seed 501, delay 3 ticks, horizon 50
- Agent: **0** of 12 (reward 0.000, reward.txt 0.000)
- Reference (`kf_mpc`) from the start: **10** (reward 0.833)
- Gap: 10 points = 0.833 reward. Decisions account for 10, stopping early for 0.
- Rebuild reproduces the saved run tick for tick: **yes**

## Main mistakes

### 1. call 13, uplink [drive -60.4° 5 m, drive -60.4° 4.5 m, sample] at tick 17: −10 points (−0.833 reward)

- **LATE_SAMPLE**: d2 sampled at tick 24, deadline tick 18. A target was sampled after its published deadline, for reduced value.
  - Information the agent had: acknowledgement of call 13: execute tick [24]; map target d2 (deadline tick 18, value 2); map(): targets[d2].deadline_tick
- Reference instead: at tick 18 uplink [drive 323.2° 3.48 m, drive 323.2° 3.48 m]; then sample d1 (tick 21); finish home, score 10
- Agent's own words: none recorded (trajectory step 12 holds the tool call but no message or reasoning text)

### 2. call 6, uplink [drive -100.7° 5 m, sample] at tick 5: −1.5 points (−0.125 reward)

- **PLAN_WORSE_THAN_REFERENCE**: from the same information the reference scored 10 instead of 8.5. Legal and on time, but the reference's plan from the same information scored more.
  - Information the agent had: telemetry packet for tick 2, delivered at tick 5 (position [20.0, 20.0], battery 99.0)
- Reference instead: at tick 9 uplink [drive 278.1° 4.73 m, drive 278.1° 4.73 m, sample]; then sample t3 (tick 6), t1 (tick 9), t5 (tick 12), d2 (tick 15), t4 (tick 18), t2 (tick 21); finish home, score 10
- Agent's own words: none recorded (trajectory step 7 holds the tool call but no message or reasoning text)

## Where the agent did better than the reference

- call 8, uplink [drive -107.2° 5 m, drive -107.2° 2.77 m, sample] at tick 8: +1.5 points (the reference taking over before this call would have scored 8.5, after it 10)

## Infrastructure (kept apart from reasoning)

None found: every agent call reached the simulator, Harbor recorded no exception, the rebuild matches the run and reward.txt matches the evaluator.

## Other reasoning findings (no points lost against the reference)

- call 10: **DISCOVERY_MISSED**: d2 (value 2, deadline tick 18) arrived in the packet for tick 6 at tick 9; sampled late

## Episode outcome

- **DEAD**: the rover died
- superlog labels unavailable here (ModuleNotFoundError: No module named 'numpy')

## Every decision

| call | tick | what the agent did | reference before | reference after | points lost | tags |
|---:|---|---|---:|---:|---:|---|
| 3 | 0→0 | uplink [drive -2.5° 5 m, drive -2.5° 0.31 m, sample, drive 106.6° 4.7 m, drive 106.6° 4.69 m] | 10 | 10 | 0 |  |
| 4 | 0→0 | uplink [sample, drive -143.4° 5 m, drive -143.4° 1.08 m, sample] | 10 | 10 | 0 |  |
| 5 | 0→5 | advance 5 | 10 | 10 | 0 |  |
| 6 | 5→5 | uplink [drive -100.7° 5 m, sample] | 10 | 8.5 | 1.5 | PLAN_WORSE_THAN_REFERENCE |
| 7 | 5→8 | advance 3 | 8.5 | 8.5 | 0 |  |
| 8 | 8→8 | uplink [drive -107.2° 5 m, drive -107.2° 2.77 m, sample] | 8.5 | 10 | -1.5 |  |
| 9 | 8→11 | advance 3 | 10 | 10 | 0 |  |
| 10 | 11→14 | advance 3 | 10 | 10 | 0 | DISCOVERY_MISSED |
| 11 | 14→14 | uplink [drive 90.8° 5 m, drive 90.8° 5 m, drive 90.8° 1.25 m, sample] | 10 | 10 | 0 |  |
| 12 | 14→17 | advance 3 | 10 | 10 | 0 |  |
| 13 | 17→17 | uplink [drive -60.4° 5 m, drive -60.4° 4.5 m, sample] | 10 | 0 | 10 | LATE_SAMPLE |
| 14 | 17→20 | advance 3 | 0 | 0 | 0 |  |
| 15 | 20→25 | advance 5 | 0 | 0 | 0 |  |
| 16 | 25→30 | advance 5 | 0 | 0 | 0 |  |
| 17 | 30→35 | advance 5 | 0 | 0 | 0 |  |
| 18 | 35→40 | advance 5 | 0 | 0 | 0 |  |
| 19 | 40→45 | advance 5 | 0 | 0 | 0 |  |
| 20 | 45→50 | advance 5 | 0 | 0 | 0 |  |

*Reference before/after*: the score if the reference took over just before or just after this call, knowing only what the agent knew then (delivered telemetry, rules, map, its own acknowledgements). *Points lost* = before − after; the column plus the stop loss adds up to the gap.
