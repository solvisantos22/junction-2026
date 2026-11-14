# Decision audit: overnight-a01-rush-seed501-r1-opus-5-5

- Model: anthropic/claude-opus-5-5
- Profile `rush`, seed 501, delay 3 ticks, horizon 50
- Agent: **0** of 12 (reward 0.000, reward.txt 0.000)
- Reference (`kf_mpc`) from the start: **10** (reward 0.833)
- Gap: 10 points = 0.833 reward. Decisions account for 10, stopping early for 0.
- Rebuild reproduces the saved run tick for tick: **yes**

## Main mistakes

### 1. call 12, uplink [drive 72.9° 5 m, drive 72.9° 2.77 m, sample, drive 122.5° 4.54 m, sample] at tick 15: −10 points (−0.833 reward)

- **LATE_SAMPLE**: d1 sampled at tick 23, deadline tick 21. A target was sampled after its published deadline, for reduced value.
  - Information the agent had: acknowledgement of call 12: execute tick [23]; map target d1 (deadline tick 21, value 2); map(): targets[d1].deadline_tick
- **DISCOVERY_MISSED**: d1 (value 2, deadline tick 21) arrived in the packet for tick 11 at tick 14; sampled late. A discovered target arrived in telemetry and was never collected (or only late).
  - Information the agent had: telemetry packet for tick 11, delivered at tick 14; map target d1 (deadline tick 21, value 2)
- Reference instead: at tick 15 uplink [drive 72.9° 3.89 m, drive 72.9° 3.89 m, sample]; then sample t4 (tick 18), t2 (tick 21); finish home, score 10
- Agent's own words: none recorded (trajectory step 16 holds the tool call but no message or reasoning text)

## Infrastructure (kept apart from reasoning)

None found: every agent call reached the simulator, Harbor recorded no exception, the rebuild matches the run and reward.txt matches the evaluator.

## Episode outcome

- **DEAD**: the rover died
- superlog labels unavailable here (ModuleNotFoundError: No module named 'numpy')

## Every decision

| call | tick | what the agent did | reference before | reference after | points lost | tags |
|---:|---|---|---:|---:|---:|---|
| 3 | 0→0 | uplink [drive -2.5° 5 m, drive -2.5° 0.31 m, sample, drive 106.6° 5 m, drive 106.6° 4.39 m] | 10 | 10 | 0 |  |
| 4 | 0→0 | uplink [sample, drive -143.4° 5 m, drive -143.4° 1.08 m, sample] | 10 | 10 | 0 |  |
| 5 | 0→5 | advance 5 | 10 | 10 | 0 |  |
| 6 | 5→8 | advance 3 | 10 | 10 | 0 |  |
| 7 | 8→9 | advance 1 | 10 | 10 | 0 |  |
| 8 | 9→9 | uplink [drive -81.8° 5 m, drive -81.8° 4.45 m, sample] | 10 | 10 | 0 |  |
| 9 | 9→11 | advance 2 | 10 | 10 | 0 |  |
| 10 | 11→11 | uplink [drive -147° 5 m, drive -147° 0.46 m, sample] | 10 | 10 | 0 |  |
| 11 | 11→15 | advance 4 | 10 | 10 | 0 |  |
| 12 | 15→15 | uplink [drive 72.9° 5 m, drive 72.9° 2.77 m, sample, drive 122.5° 4.54 m, sample] | 10 | 0 | 10 | DISCOVERY_MISSED, LATE_SAMPLE |
| 13 | 15→19 | advance 4 | 0 | 0 | 0 |  |
| 14 | 19→19 | uplink [drive -36.2° 5 m, drive -36.2° 1.97 m] | 0 | 0 | 0 |  |
| 15 | 19→24 | advance 5 | 0 | 0 | 0 |  |
| 16 | 24→28 | advance 4 | 0 | 0 | 0 |  |
| 17 | 28→33 | advance 5 | 0 | 0 | 0 |  |
| 18 | 33→38 | advance 5 | 0 | 0 | 0 |  |
| 19 | 38→43 | advance 5 | 0 | 0 | 0 |  |
| 20 | 43→48 | advance 5 | 0 | 0 | 0 |  |
| 21 | 48→50 | advance 2 | 0 | 0 | 0 |  |

*Reference before/after*: the score if the reference took over just before or just after this call, knowing only what the agent knew then (delivered telemetry, rules, map, its own acknowledgements). *Points lost* = before − after; the column plus the stop loss adds up to the gap.
