# Decision audit: overnight-b07-t-rush-seed501-r2-opus-5-5

- Model: anthropic/claude-opus-5-5
- Profile `rush`, seed 501, delay 3 ticks, horizon 50
- Agent: **10.5** of 12 (reward 0.875, reward.txt 0.875)
- Reference (`kf_mpc`) from the start: **10** (reward 0.833)
- Gap: -0.5 points = -0.042 reward. Decisions account for -0.5, stopping early for 0.
- Rebuild reproduces the saved run tick for tick: **yes**

## Main mistakes

None: the agent matched the reference's score. Some decisions below lost points against the reference's continuation and later decisions won them back; that measures the reference from states it would not have chosen, not an agent mistake.

## Where the agent did better than the reference

- call 12, uplink [drive 213.6° 5 m, sample] at tick 13: +1.5 points (the reference taking over before this call would have scored 8.5, after it 10)
- call 17, uplink [drive 123.8° 3.78 m, sample] at tick 18: +0.5 points (the reference taking over before this call would have scored 10, after it 10.5)

## Infrastructure (kept apart from reasoning)

None found: every agent call reached the simulator, Harbor recorded no exception, the rebuild matches the run and reward.txt matches the evaluator.

## Other reasoning findings (no points lost against the reference)

- call 14: **DISCOVERY_MISSED**: d1 (value 2, deadline tick 21) arrived in the packet for tick 11 at tick 14; sampled late
- call 17: **LATE_SAMPLE**: d1 sampled at tick 23, deadline tick 21

## Episode outcome

- **PERFECT**: scored 10.5, the reference scored 10 from the start
- superlog labels unavailable here (ModuleNotFoundError: No module named 'numpy')

## Every decision

| call | tick | what the agent did | reference before | reference after | points lost | tags |
|---:|---|---|---:|---:|---:|---|
| 3 | 0→0 | uplink [drive 357.4° 2.67 m, drive 357.4° 2.67 m, sample, drive 106.6° 4.72 m, drive 106.6° 4.72 m] | 10 | 10 | 0 |  |
| 4 | 0→5 | advance 5 | 10 | 10 | 0 |  |
| 5 | 5→5 | uplink [sample] | 10 | 10 | 0 |  |
| 6 | 5→7 | advance 2 | 10 | 10 | 0 |  |
| 7 | 7→7 | uplink [drive 216.6° 3.03 m, drive 216.6° 3.03 m, sample] | 10 | 10 | 0 |  |
| 8 | 7→9 | advance 2 | 10 | 10 | 0 |  |
| 9 | 9→9 | uplink [drive 275.4° 4.83 m, drive 275.4° 4.83 m, sample] | 10 | 8.5 | 1.5 |  |
| 10 | 9→11 | advance 2 | 8.5 | 8.5 | 0 |  |
| 11 | 11→13 | advance 2 | 8.5 | 8.5 | 0 |  |
| 12 | 13→13 | uplink [drive 213.6° 5 m, sample] | 8.5 | 10 | -1.5 |  |
| 13 | 13→15 | advance 2 | 10 | 10 | 0 |  |
| 14 | 15→15 | uplink [drive 74.9° 4 m, drive 74.9° 4 m, sample] | 10 | 10 | 0 | DISCOVERY_MISSED |
| 15 | 15→16 | advance 1 | 10 | 10 | 0 |  |
| 16 | 16→18 | advance 2 | 10 | 10 | 0 |  |
| 17 | 18→18 | uplink [drive 123.8° 3.78 m, sample] | 10 | 10.5 | -0.5 | LATE_SAMPLE |
| 18 | 18→20 | advance 2 | 10.5 | 10.5 | 0 |  |
| 19 | 20→20 | uplink [drive 325.4° 3.19 m] | 10.5 | 10.5 | 0 |  |
| 20 | 20→21 | advance 1 | 10.5 | 10.5 | 0 |  |
| 21 | 21→25 | advance 4 | 10.5 | 10.5 | 0 |  |
| 22 | 25→27 | advance 2 | 10.5 | 10.5 | 0 |  |
| 23 | 27→27 | uplink [drive 326.6° 3.4 m] | 10.5 | 10.5 | 0 |  |
| 24 | 27→32 | advance 5 | 10.5 | 10.5 | 0 |  |
| 25 | 32→34 | advance 2 | 10.5 | 10.5 | 0 |  |
| 26 | 34→39 | advance 5 | 10.5 | 10.5 | 0 |  |
| 27 | 39→44 | advance 5 | 10.5 | 10.5 | 0 |  |
| 28 | 44→49 | advance 5 | 10.5 | 10.5 | 0 |  |
| 29 | 49→50 | advance 1 | 10.5 | 10.5 | 0 |  |

*Reference before/after*: the score if the reference took over just before or just after this call, knowing only what the agent knew then (delivered telemetry, rules, map, its own acknowledgements). *Points lost* = before − after; the column plus the stop loss adds up to the gap.
