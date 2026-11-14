# Decision audit: overnight-a04-rush-seed501-r2-opus-5-5

- Model: anthropic/claude-opus-5-5
- Profile `rush`, seed 501, delay 3 ticks, horizon 50
- Agent: **10** of 12 (reward 0.833, reward.txt 0.833)
- Reference (`kf_mpc`) from the start: **10** (reward 0.833)
- Gap: 0 points = 0.000 reward. Decisions account for 0, stopping early for 0.
- Rebuild reproduces the saved run tick for tick: **yes**

## Main mistakes

None: no decision scored less than the reference would have from the same moment.

## Infrastructure (kept apart from reasoning)

None found: every agent call reached the simulator, Harbor recorded no exception, the rebuild matches the run and reward.txt matches the evaluator.

## Other reasoning findings (no points lost against the reference)

- call 10: **DISCOVERY_MISSED**: d2 (value 2, deadline tick 18) arrived in the packet for tick 6 at tick 9; never sampled

## Episode outcome

- **PERFECT**: scored 10, the reference scored 10 from the start
- **TARGETS_LEFT**: never sampled: d2
- superlog labels unavailable here (ModuleNotFoundError: No module named 'numpy')

## Every decision

| call | tick | what the agent did | reference before | reference after | points lost | tags |
|---:|---|---|---:|---:|---:|---|
| 3 | 0→0 | uplink [drive 357.4° 2.65 m, drive 357.4° 2.65 m, sample, drive 106.6° 4.69 m, drive 106.6° 4.69 m] | 10 | 10 | 0 |  |
| 4 | 0→0 | uplink [sample] | 10 | 10 | 0 |  |
| 5 | 0→5 | advance 5 | 10 | 10 | 0 |  |
| 6 | 5→5 | uplink [drive 216.6° 3.04 m, drive 216.6° 3.04 m, sample] | 10 | 10 | 0 |  |
| 7 | 5→8 | advance 3 | 10 | 10 | 0 |  |
| 8 | 8→8 | uplink [drive 259.7° 5 m, sample, drive 252.8° 3.87 m, drive 252.8° 3.87 m, sample] | 10 | 10 | 0 |  |
| 9 | 8→12 | advance 4 | 10 | 10 | 0 |  |
| 10 | 12→14 | advance 2 | 10 | 10 | 0 | DISCOVERY_MISSED |
| 11 | 14→14 | uplink [drive 91.1° 3.74 m, drive 91.1° 3.74 m, drive 91.1° 3.74 m, sample] | 10 | 10 | 0 |  |
| 12 | 14→19 | advance 5 | 10 | 10 | 0 |  |
| 13 | 19→19 | uplink [drive 324.2° 3.49 m, drive 324.2° 3.49 m] | 10 | 10 | 0 |  |
| 14 | 19→24 | advance 5 | 10 | 10 | 0 |  |
| 15 | 24→27 | advance 3 | 10 | 10 | 0 |  |
| 16 | 27→32 | advance 5 | 10 | 10 | 0 |  |
| 17 | 32→37 | advance 5 | 10 | 10 | 0 |  |
| 18 | 37→42 | advance 5 | 10 | 10 | 0 |  |
| 19 | 42→47 | advance 5 | 10 | 10 | 0 |  |
| 20 | 47→50 | advance 3 | 10 | 10 | 0 |  |

*Reference before/after*: the score if the reference took over just before or just after this call, knowing only what the agent knew then (delivered telemetry, rules, map, its own acknowledgements). *Points lost* = before − after; the column plus the stop loss adds up to the gap.
