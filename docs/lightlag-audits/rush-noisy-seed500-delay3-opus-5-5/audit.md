# Decision audit: rush-noisy-seed500-delay3-opus-5-5

- Model: anthropic/claude-opus-5-5
- Profile `rush_noisy`, seed 500, delay 3 ticks, horizon 50
- Agent: **7** of 7 (reward 1.000, reward.txt 1.000)
- Reference (`kf_mpc`) from the start: **7** (reward 1.000)
- Gap: 0 points = 0.000 reward. Decisions account for 0, stopping early for 0.
- Rebuild reproduces the saved run tick for tick: **yes**

## Main mistakes

None: the agent matched the reference's score. Some decisions below lost points against the reference's continuation and later decisions won them back; that measures the reference from states it would not have chosen, not an agent mistake.

## Where the agent did better than the reference

- call 6, advance 2 at tick 5: +1.5 points (the reference taking over before this call would have scored 4.5, after it 6)
- call 10, advance 2 at tick 9: +1 points (the reference taking over before this call would have scored 6, after it 7)

## Infrastructure (kept apart from reasoning)

None found: every agent call reached the simulator, Harbor recorded no exception, the rebuild matches the run and reward.txt matches the evaluator.

## Episode outcome

- **PERFECT**: scored 7, the reference scored 7 from the start
- superlog labels (`lightlag_dynamic/manh_controllers/superlog.py`): PERFECT; share 1.000, 6 samples taken, 0 failed, 0 late, battery at the end 10.1

## Every decision

| call | tick | what the agent did | reference before | reference after | points lost | tags |
|---:|---|---|---:|---:|---:|---|
| 3 | 0→0 | uplink [drive 83.6° 5 m, sample, drive 237.8° 4.54 m] | 7 | 7 | 0 |  |
| 4 | 0→0 | uplink [drive 237.8° 3.07 m, sample] | 7 | 4.5 | 2.5 |  |
| 5 | 0→5 | advance 5 | 4.5 | 4.5 | 0 |  |
| 6 | 5→7 | advance 2 | 4.5 | 6 | -1.5 |  |
| 7 | 7→8 | advance 1 | 6 | 6 | 0 |  |
| 8 | 8→8 | uplink [drive 234° 5 m] | 6 | 6 | 0 |  |
| 9 | 8→9 | advance 1 | 6 | 6 | 0 |  |
| 10 | 9→11 | advance 2 | 6 | 7 | -1 |  |
| 11 | 11→11 | uplink [drive 231° 1.3 m, sample, drive 5.7° 5 m, drive 5.7° 5 m] | 7 | 7 | 0 |  |
| 12 | 11→13 | advance 2 | 7 | 7 | 0 |  |
| 13 | 13→15 | advance 2 | 7 | 7 | 0 |  |
| 14 | 15→15 | uplink [drive 158.4° 2.52 m, sample] | 7 | 7 | 0 |  |
| 15 | 15→17 | advance 2 | 7 | 7 | 0 |  |
| 16 | 17→17 | uplink [drive 341.6° 3.08 m, sample] | 7 | 7 | 0 |  |
| 17 | 17→19 | advance 2 | 7 | 7 | 0 |  |
| 18 | 19→19 | uplink [drive 94.7° 3.6 m, sample] | 7 | 7 | 0 |  |
| 19 | 19→21 | advance 2 | 7 | 7 | 0 |  |
| 20 | 21→23 | advance 2 | 7 | 7 | 0 |  |
| 21 | 23→25 | advance 2 | 7 | 7 | 0 |  |
| 22 | 25→27 | advance 2 | 7 | 7 | 0 |  |
| 24 | 27→27 | uplink [drive 177.5° 3.9 m] | 7 | 7 | 0 |  |
| 25 | 27→32 | advance 5 | 7 | 7 | 0 |  |
| 26 | 32→37 | advance 5 | 7 | 7 | 0 |  |
| 27 | 37→42 | advance 5 | 7 | 7 | 0 |  |
| 28 | 42→47 | advance 5 | 7 | 7 | 0 |  |
| 29 | 47→50 | advance 5 | 7 | 7 | 0 |  |

*Reference before/after*: the score if the reference took over just before or just after this call, knowing only what the agent knew then (delivered telemetry, rules, map, its own acknowledgements). *Points lost* = before − after; the column plus the stop loss adds up to the gap.
