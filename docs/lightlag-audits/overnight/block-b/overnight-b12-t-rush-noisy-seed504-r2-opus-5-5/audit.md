# Decision audit: overnight-b12-t-rush-noisy-seed504-r2-opus-5-5

- Model: anthropic/claude-opus-5-5
- Profile `rush_noisy`, seed 504, delay 3 ticks, horizon 50
- Agent: **7** of 10 (reward 0.700, reward.txt 0.700)
- Reference (`kf_mpc`) from the start: **7** (reward 0.700)
- Gap: 0 points = 0.000 reward. Decisions account for 0, stopping early for 0.
- Rebuild reproduces the saved run tick for tick: **yes**

## Main mistakes

None: the agent matched the reference's score. Some decisions below lost points against the reference's continuation and later decisions won them back; that measures the reference from states it would not have chosen, not an agent mistake.

## Where the agent did better than the reference

- call 7, advance 2 at tick 6: +2.75 points (the reference taking over before this call would have scored 4.25, after it 7)
- call 9, advance 2 at tick 9: +1.75 points (the reference taking over before this call would have scored 5.25, after it 7)

## Infrastructure (kept apart from reasoning)

None found: every agent call reached the simulator, Harbor recorded no exception, the rebuild matches the run and reward.txt matches the evaluator.

## Other reasoning findings (no points lost against the reference)

- call 20: **DISCOVERY_MISSED**: d1 (value 3, deadline tick 33) arrived in the packet for tick 21 at tick 24; never sampled

## Episode outcome

- **PERFECT**: scored 7, the reference scored 7 from the start
- **TARGETS_LEFT**: never sampled: d1
- superlog labels unavailable here (ModuleNotFoundError: No module named 'numpy')

## Every decision

| call | tick | what the agent did | reference before | reference after | points lost | tags |
|---:|---|---|---:|---:|---:|---|
| 3 | 0→0 | uplink [drive 309.1° 5 m, drive 309.1° 3.03 m, sample] | 7 | 7 | 0 |  |
| 4 | 0→0 | uplink [drive 95.3° 5 m, drive 95.3° 4.18 m, sample] | 7 | 4.25 | 2.75 |  |
| 5 | 0→5 | advance 5 | 4.25 | 4.25 | 0 |  |
| 6 | 5→6 | advance 1 | 4.25 | 4.25 | 0 |  |
| 7 | 6→8 | advance 2 | 4.25 | 7 | -2.75 |  |
| 8 | 8→9 | advance 1 | 7 | 5.25 | 1.75 | QUEUE_RAN_DRY |
| 9 | 9→11 | advance 2 | 5.25 | 7 | -1.75 |  |
| 10 | 11→12 | advance 1 | 7 | 7 | 0 |  |
| 11 | 12→12 | uplink [drive 178.2° 5 m, drive 178.2° 2.97 m, sample] | 7 | 7 | 0 |  |
| 12 | 12→15 | advance 3 | 7 | 7 | 0 |  |
| 14 | 15→20 | advance 5 | 7 | 7 | 0 |  |
| 16 | 20→20 | uplink [drive 294° 5 m, drive 294° 2.6 m, sample] | 7 | 7 | 0 |  |
| 17 | 20→20 | uplink [drive 240.8° 5 m, drive 240.8° 0.48 m, sample] | 7 | 7 | 0 |  |
| 18 | 20→21 | advance 1 | 7 | 7 | 0 |  |
| 19 | 21→24 | advance 3 | 7 | 7 | 0 |  |
| 20 | 24→28 | advance 4 | 7 | 7 | 0 | DISCOVERY_MISSED |
| 22 | 28→31 | advance 3 | 7 | 7 | 0 |  |
| 23 | 31→32 | advance 1 | 7 | 7 | 0 |  |
| 24 | 32→32 | uplink [drive 67.5° 5 m, drive 67.5° 3.96 m] | 7 | 7 | 0 |  |
| 25 | 32→37 | advance 5 | 7 | 7 | 0 |  |
| 26 | 37→42 | advance 5 | 7 | 7 | 0 |  |
| 27 | 42→47 | advance 5 | 7 | 7 | 0 |  |
| 28 | 47→50 | advance 5 | 7 | 7 | 0 |  |

*Reference before/after*: the score if the reference took over just before or just after this call, knowing only what the agent knew then (delivered telemetry, rules, map, its own acknowledgements). *Points lost* = before − after; the column plus the stop loss adds up to the gap.
