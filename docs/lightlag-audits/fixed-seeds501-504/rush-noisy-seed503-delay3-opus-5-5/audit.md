# Decision audit: rush-noisy-seed503-delay3-opus-5-5

- Model: anthropic/claude-opus-5-5
- Profile `rush_noisy`, seed 503, delay 3 ticks, horizon 50
- Agent: **6** of 8 (reward 0.750, reward.txt 0.750)
- Reference (`kf_mpc`) from the start: **5** (reward 0.625)
- Gap: -1 points = -0.125 reward. Decisions account for -1, stopping early for 0.
- Rebuild reproduces the saved run tick for tick: **yes**

## Main mistakes

None: no decision scored less than the reference would have from the same moment.

## Where the agent did better than the reference

- call 4, advance 5 at tick 0: +1 points (the reference taking over before this call would have scored 5, after it 6)

## Infrastructure (kept apart from reasoning)

None found: every agent call reached the simulator, Harbor recorded no exception, the rebuild matches the run and reward.txt matches the evaluator.

## Other reasoning findings (no points lost against the reference)

- call 22: **DISCOVERY_MISSED**: d1 (value 2, deadline tick 25) arrived in the packet for tick 18 at tick 21; never sampled

## Episode outcome

- **PERFECT**: scored 6, the reference scored 5 from the start
- **TARGETS_LEFT**: never sampled: d1
- superlog labels unavailable here (ModuleNotFoundError: No module named 'numpy')

## Every decision

| call | tick | what the agent did | reference before | reference after | points lost | tags |
|---:|---|---|---:|---:|---:|---|
| 3 | 0→0 | uplink [drive 75.6° 5 m, drive 75.6° 2.41 m, drive 34.4° 1.5 m, sample] | 5 | 5 | 0 |  |
| 4 | 0→5 | advance 5 | 5 | 6 | -1 |  |
| 5 | 5→5 | uplink [drive 219.6° 5 m, drive 219.6° 0.59 m, sample] | 6 | 6 | 0 |  |
| 6 | 5→7 | advance 2 | 6 | 6 | 0 |  |
| 7 | 7→8 | advance 1 | 6 | 6 | 0 |  |
| 8 | 8→8 | uplink [drive 278.8° 5 m, drive 278.8° 3.67 m, sample] | 6 | 6 | 0 |  |
| 9 | 8→9 | advance 1 | 6 | 6 | 0 |  |
| 10 | 9→10 | advance 1 | 6 | 6 | 0 |  |
| 11 | 10→11 | advance 1 | 6 | 6 | 0 |  |
| 13 | 11→11 | uplink [drive 35.8° 5 m, drive 35.8° 0.68 m, sample] | 6 | 6 | 0 |  |
| 14 | 11→13 | advance 2 | 6 | 6 | 0 |  |
| 15 | 13→14 | advance 1 | 6 | 6 | 0 |  |
| 16 | 14→14 | uplink [drive 257.3° 5 m, drive 257.3° 3.49 m, sample] | 6 | 6 | 0 |  |
| 17 | 14→16 | advance 2 | 6 | 6 | 0 |  |
| 18 | 16→17 | advance 1 | 6 | 6 | 0 |  |
| 20 | 17→19 | advance 2 | 6 | 6 | 0 |  |
| 21 | 19→22 | advance 3 | 6 | 6 | 0 |  |
| 22 | 22→23 | advance 1 | 6 | 6 | 0 | DISCOVERY_MISSED |
| 23 | 23→23 | uplink [drive 108.5° 5 m, drive 108.5° 5 m, drive 108.5° 0.43 m] | 6 | 6 | 0 |  |
| 24 | 23→28 | advance 5 | 6 | 6 | 0 |  |
| 25 | 28→32 | advance 4 | 6 | 6 | 0 |  |
| 27 | 32→35 | advance 3 | 6 | 6 | 0 |  |
| 28 | 35→35 | uplink [drive 282.5° 0.62 m] | 6 | 6 | 0 |  |
| 29 | 35→40 | advance 5 | 6 | 6 | 0 |  |
| 30 | 40→45 | advance 5 | 6 | 6 | 0 |  |
| 31 | 45→50 | advance 5 | 6 | 6 | 0 |  |

*Reference before/after*: the score if the reference took over just before or just after this call, knowing only what the agent knew then (delivered telemetry, rules, map, its own acknowledgements). *Points lost* = before − after; the column plus the stop loss adds up to the gap.
