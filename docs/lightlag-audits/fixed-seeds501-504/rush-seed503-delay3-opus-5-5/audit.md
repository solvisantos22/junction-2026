# Decision audit: rush-seed503-delay3-opus-5-5

- Model: anthropic/claude-opus-5-5
- Profile `rush`, seed 503, delay 3 ticks, horizon 50
- Agent: **6** of 8 (reward 0.750, reward.txt 0.750)
- Reference (`kf_mpc`) from the start: **6** (reward 0.750)
- Gap: 0 points = 0.000 reward. Decisions account for 0, stopping early for 0.
- Rebuild reproduces the saved run tick for tick: **yes**

## Main mistakes

None: no decision scored less than the reference would have from the same moment.

## Infrastructure (kept apart from reasoning)

None found: every agent call reached the simulator, Harbor recorded no exception, the rebuild matches the run and reward.txt matches the evaluator.

## Other reasoning findings (no points lost against the reference)

- call 20: **DISCOVERY_MISSED**: d1 (value 2, deadline tick 25) arrived in the packet for tick 18 at tick 21; never sampled

## Episode outcome

- **PERFECT**: scored 6, the reference scored 6 from the start
- **TARGETS_LEFT**: never sampled: d1
- superlog labels unavailable here (ModuleNotFoundError: No module named 'numpy')

## Every decision

| call | tick | what the agent did | reference before | reference after | points lost | tags |
|---:|---|---|---:|---:|---:|---|
| 3 | 0→0 | uplink [drive 105.3° 4.64 m, sample, drive 39.6° 5 m] | 6 | 6 | 0 |  |
| 4 | 0→0 | uplink [drive 39.6° 0.59 m, sample] | 6 | 6 | 0 |  |
| 5 | 0→4 | advance 4 | 6 | 6 | 0 |  |
| 6 | 4→4 | uplink [drive 238.8° 2.19 m, drive 258.9° 5 m] | 6 | 6 | 0 |  |
| 7 | 4→7 | advance 3 | 6 | 6 | 0 |  |
| 8 | 7→7 | uplink [drive 258.6° 5 m, drive 258.6° 0.53 m, sample] | 6 | 6 | 0 |  |
| 9 | 7→9 | advance 2 | 6 | 6 | 0 |  |
| 10 | 9→9 | uplink [drive 34.3° 5 m, drive 34.3° 0.66 m, sample] | 6 | 6 | 0 |  |
| 11 | 9→11 | advance 2 | 6 | 6 | 0 |  |
| 13 | 11→13 | advance 2 | 6 | 6 | 0 |  |
| 14 | 13→13 | uplink [drive 255.8° 5 m, drive 255.8° 3.45 m, sample] | 6 | 6 | 0 |  |
| 15 | 13→16 | advance 3 | 6 | 6 | 0 |  |
| 17 | 16→19 | advance 3 | 6 | 6 | 0 |  |
| 19 | 19→21 | advance 2 | 6 | 6 | 0 |  |
| 20 | 21→21 | uplink [drive 108.8° 5 m, drive 108.8° 4.58 m] | 6 | 6 | 0 | DISCOVERY_MISSED |
| 21 | 21→24 | advance 3 | 6 | 6 | 0 |  |
| 22 | 24→29 | advance 5 | 6 | 6 | 0 |  |
| 23 | 29→34 | advance 5 | 6 | 6 | 0 |  |
| 25 | 34→39 | advance 5 | 6 | 6 | 0 |  |
| 26 | 39→44 | advance 5 | 6 | 6 | 0 |  |
| 27 | 44→49 | advance 5 | 6 | 6 | 0 |  |
| 28 | 49→50 | advance 1 | 6 | 6 | 0 |  |

*Reference before/after*: the score if the reference took over just before or just after this call, knowing only what the agent knew then (delivered telemetry, rules, map, its own acknowledgements). *Points lost* = before − after; the column plus the stop loss adds up to the gap.
