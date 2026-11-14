# Decision audit: rush-seed501-delay3-opus-5-5

- Model: anthropic/claude-opus-5-5
- Profile `rush`, seed 501, delay 3 ticks, horizon 50
- Agent: **0** of 12 (reward 0.000, reward.txt 0.000)
- Reference (`kf_mpc`) from the start: **10** (reward 0.833)
- Gap: 10 points = 0.833 reward. Decisions account for 10, stopping early for 0.
- Rebuild reproduces the saved run tick for tick: **yes**

## Main mistakes

### 1. call 11, uplink [drive 73.2° 3.88 m, drive 73.2° 3.88 m, sample, drive 122.5° 4.55 m, sample] at tick 15: −10 points (−0.833 reward)

- **LATE_SAMPLE**: d1 sampled at tick 23, deadline tick 21. A target was sampled after its published deadline, for reduced value.
  - Information the agent had: acknowledgement of call 11: execute tick [23]; map target d1 (deadline tick 21, value 2); map(): targets[d1].deadline_tick
- Reference instead: at tick 15 uplink [drive 73.2° 3.88 m, drive 73.2° 3.88 m, sample]; then sample t4 (tick 18), t2 (tick 21); finish home, score 10
- Agent's own words: none recorded (trajectory step 13 holds the tool call but no message or reasoning text)

## Infrastructure (kept apart from reasoning)

None found: every agent call reached the simulator, Harbor recorded no exception, the rebuild matches the run and reward.txt matches the evaluator.

## Other reasoning findings (no points lost against the reference)

- call 10: **DISCOVERY_MISSED**: d1 (value 2, deadline tick 21) arrived in the packet for tick 11 at tick 14; sampled late

## Episode outcome

- **DEAD**: the rover died
- superlog labels unavailable here (ModuleNotFoundError: No module named 'numpy')

## Every decision

| call | tick | what the agent did | reference before | reference after | points lost | tags |
|---:|---|---|---:|---:|---:|---|
| 3 | 0→0 | uplink [drive 357.4° 2.65 m, drive 357.4° 2.65 m, sample, drive 106.6° 4.69 m, drive 106.6° 4.69 m] | 10 | 10 | 0 |  |
| 4 | 0→0 | uplink [sample, drive 216.6° 3.04 m, drive 216.6° 3.04 m, sample] | 10 | 10 | 0 |  |
| 5 | 0→5 | advance 5 | 10 | 10 | 0 |  |
| 6 | 5→9 | advance 4 | 10 | 10 | 0 |  |
| 7 | 9→9 | uplink [drive 278.1° 4.72 m, drive 278.1° 4.72 m, sample, drive 213.4° 2.72 m, drive 213.4° 2.72 m] | 10 | 10 | 0 |  |
| 8 | 9→9 | uplink [sample] | 10 | 10 | 0 |  |
| 9 | 9→14 | advance 5 | 10 | 10 | 0 |  |
| 10 | 14→15 | advance 1 | 10 | 10 | 0 | DISCOVERY_MISSED |
| 11 | 15→15 | uplink [drive 73.2° 3.88 m, drive 73.2° 3.88 m, sample, drive 122.5° 4.55 m, sample] | 10 | 0 | 10 | LATE_SAMPLE |
| 12 | 15→20 | advance 5 | 0 | 0 | 0 |  |
| 13 | 20→20 | uplink [drive 323.9° 3.51 m, drive 323.9° 3.51 m] | 0 | 0 | 0 |  |
| 14 | 20→25 | advance 5 | 0 | 0 | 0 |  |
| 15 | 25→30 | advance 5 | 0 | 0 | 0 |  |
| 16 | 30→35 | advance 5 | 0 | 0 | 0 |  |
| 17 | 35→40 | advance 5 | 0 | 0 | 0 |  |
| 18 | 40→45 | advance 5 | 0 | 0 | 0 |  |
| 19 | 45→50 | advance 5 | 0 | 0 | 0 |  |

*Reference before/after*: the score if the reference took over just before or just after this call, knowing only what the agent knew then (delivered telemetry, rules, map, its own acknowledgements). *Points lost* = before − after; the column plus the stop loss adds up to the gap.
