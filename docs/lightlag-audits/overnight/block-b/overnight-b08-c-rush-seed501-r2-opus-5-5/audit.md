# Decision audit: overnight-b08-c-rush-seed501-r2-opus-5-5

- Model: anthropic/claude-opus-5-5
- Profile `rush`, seed 501, delay 3 ticks, horizon 50
- Agent: **5.25** of 12 (reward 0.438, reward.txt 0.438)
- Reference (`kf_mpc`) from the start: **10** (reward 0.833)
- Gap: 4.75 points = 0.396 reward. Decisions account for 4.75, stopping early for 0.
- Rebuild reproduces the saved run tick for tick: **yes**

## Main mistakes

### 1. call 13, uplink [drive 122.5° 4.54 m, sample] at tick 15: −10 points (−0.833 reward)

- **LATE_SAMPLE**: d1 sampled at tick 23, deadline tick 21. A target was sampled after its published deadline, for reduced value.
  - Information the agent had: acknowledgement of call 13: execute tick [23]; map target d1 (deadline tick 21, value 2); map(): targets[d1].deadline_tick
- Reference instead: at tick 18 uplink [drive 352.6° 3.18 m]; then sample t4 (tick 18), t2 (tick 21); finish home, score 10
- Agent's own words: none recorded (trajectory step 11 holds the tool call but no message or reasoning text)

## Where the agent did better than the reference

- call 21, advance 5 at tick 45: +5.25 points (the reference taking over before this call would have scored 0, after it 5.25)

## Infrastructure (kept apart from reasoning)

None found: every agent call reached the simulator, Harbor recorded no exception, the rebuild matches the run and reward.txt matches the evaluator.

## Other reasoning findings (no points lost against the reference)

- call 12: **DISCOVERY_MISSED**: d1 (value 2, deadline tick 21) arrived in the packet for tick 11 at tick 14; sampled late

## Episode outcome

- **NOT_HOME**: alive but away from base at the horizon
- superlog labels unavailable here (ModuleNotFoundError: No module named 'numpy')

## Every decision

| call | tick | what the agent did | reference before | reference after | points lost | tags |
|---:|---|---|---:|---:|---:|---|
| 3 | 0→0 | uplink [drive 357.4° 2.65 m, drive 357.4° 2.65 m, sample, drive 106.6° 4.69 m, drive 106.6° 4.69 m] | 10 | 10 | 0 |  |
| 4 | 0→0 | uplink [sample] | 10 | 10 | 0 |  |
| 5 | 0→5 | advance 5 | 10 | 10 | 0 |  |
| 6 | 5→5 | uplink [drive 216.6° 3.04 m, drive 216.6° 3.04 m, sample] | 10 | 10 | 0 |  |
| 7 | 5→9 | advance 4 | 10 | 10 | 0 |  |
| 8 | 9→9 | uplink [drive 278.1° 4.7 m, drive 278.1° 4.7 m, sample, drive 213.4° 2.72 m, drive 213.4° 2.72 m] | 10 | 10 | 0 |  |
| 9 | 9→9 | uplink [sample] | 10 | 10 | 0 |  |
| 10 | 9→12 | advance 3 | 10 | 10 | 0 |  |
| 11 | 12→15 | advance 3 | 10 | 10 | 0 |  |
| 12 | 15→15 | uplink [drive 72.8° 3.88 m, drive 72.8° 3.88 m, sample] | 10 | 10 | 0 | DISCOVERY_MISSED |
| 13 | 15→15 | uplink [drive 122.5° 4.54 m, sample] | 10 | 0 | 10 | LATE_SAMPLE |
| 14 | 15→19 | advance 4 | 0 | 0 | 0 |  |
| 15 | 19→22 | advance 3 | 0 | 0 | 0 |  |
| 16 | 22→25 | advance 3 | 0 | 0 | 0 |  |
| 17 | 25→30 | advance 5 | 0 | 0 | 0 |  |
| 18 | 30→35 | advance 5 | 0 | 0 | 0 |  |
| 19 | 35→40 | advance 5 | 0 | 0 | 0 |  |
| 20 | 40→45 | advance 5 | 0 | 0 | 0 |  |
| 21 | 45→50 | advance 5 | 0 | 5.25 | -5.25 |  |

*Reference before/after*: the score if the reference took over just before or just after this call, knowing only what the agent knew then (delivered telemetry, rules, map, its own acknowledgements). *Points lost* = before − after; the column plus the stop loss adds up to the gap.
