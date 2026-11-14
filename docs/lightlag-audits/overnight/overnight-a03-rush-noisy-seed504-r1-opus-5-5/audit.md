# Decision audit: overnight-a03-rush-noisy-seed504-r1-opus-5-5

- Model: anthropic/claude-opus-5-5
- Profile `rush_noisy`, seed 504, delay 3 ticks, horizon 50
- Agent: **7.5** of 10 (reward 0.750, reward.txt 0.750)
- Reference (`kf_mpc`) from the start: **7** (reward 0.700)
- Gap: -0.5 points = -0.050 reward. Decisions account for -0.5, stopping early for 0.
- Rebuild reproduces the saved run tick for tick: **yes**

## Main mistakes

None: the agent matched the reference's score. Some decisions below lost points against the reference's continuation and later decisions won them back; that measures the reference from states it would not have chosen, not an agent mistake.

## Where the agent did better than the reference

- call 6, advance 2 at tick 5: +0.75 points (the reference taking over before this call would have scored 6.25, after it 7)
- call 16, uplink [drive 294.4° 5 m, drive 294.4° 2.61 m, sample] at tick 22: +2.75 points (the reference taking over before this call would have scored 4.75, after it 7.5)
- call 24, uplink [drive 307.9° 5 m, drive 307.9° 1.12 m, sample] at tick 35: +0.5 points (the reference taking over before this call would have scored 7, after it 7.5)

## Infrastructure (kept apart from reasoning)

None found: every agent call reached the simulator, Harbor recorded no exception, the rebuild matches the run and reward.txt matches the evaluator.

## Other reasoning findings (no points lost against the reference)

- call 24: **LATE_SAMPLE**: t4 sampled at tick 41, deadline tick 21

## Episode outcome

- **PERFECT**: scored 7.5, the reference scored 7 from the start
- **TARGETS_LEFT**: never sampled: t1
- superlog labels unavailable here (ModuleNotFoundError: No module named 'numpy')

## Every decision

| call | tick | what the agent did | reference before | reference after | points lost | tags |
|---:|---|---|---:|---:|---:|---|
| 4 | 0→0 | uplink [drive 309.1° 5 m, drive 309.1° 2.9 m] | 7 | 7 | 0 |  |
| 5 | 0→5 | advance 5 | 7 | 6.25 | 0.75 | QUEUE_RAN_DRY |
| 6 | 5→7 | advance 2 | 6.25 | 7 | -0.75 |  |
| 7 | 7→9 | advance 2 | 7 | 7 | 0 |  |
| 8 | 9→9 | uplink [drive 74° 0.5 m, sample] | 7 | 7 | 0 |  |
| 9 | 9→12 | advance 3 | 7 | 6.25 | 0.75 | QUEUE_RAN_DRY |
| 10 | 12→12 | uplink [drive 134.3° 5 m, drive 134.3° 5 m, drive 134.3° 2.54 m, sample] | 6.25 | 5.5 | 0.75 |  |
| 11 | 12→15 | advance 3 | 5.5 | 5.5 | 0 |  |
| 13 | 15→19 | advance 4 | 5.5 | 5.5 | 0 |  |
| 14 | 19→22 | advance 3 | 5.5 | 4.75 | 0.75 | WAITED_WITH_EMPTY_QUEUE |
| 16 | 22→22 | uplink [drive 294.4° 5 m, drive 294.4° 2.61 m, sample] | 4.75 | 7.5 | -2.75 |  |
| 17 | 22→25 | advance 3 | 7.5 | 7.5 | 0 |  |
| 18 | 25→25 | uplink [drive 85.8° 5 m, drive 85.8° 5 m, drive 85.8° 1.59 m, sample] | 7.5 | 7.5 | 0 |  |
| 19 | 25→28 | advance 3 | 7.5 | 7.5 | 0 |  |
| 20 | 28→31 | advance 3 | 7.5 | 7.5 | 0 |  |
| 22 | 31→33 | advance 2 | 7.5 | 7.5 | 0 |  |
| 23 | 33→35 | advance 2 | 7.5 | 7 | 0.5 | WAITED_WITH_EMPTY_QUEUE |
| 24 | 35→35 | uplink [drive 307.9° 5 m, drive 307.9° 1.12 m, sample] | 7 | 7.5 | -0.5 | LATE_SAMPLE |
| 25 | 35→38 | advance 3 | 7.5 | 7.5 | 0 |  |
| 26 | 38→43 | advance 5 | 7.5 | 7.5 | 0 |  |
| 27 | 43→44 | advance 1 | 7.5 | 7.5 | 0 |  |
| 28 | 44→44 | uplink [drive 216.8° 4 m, drive 216.8° 1.07 m] | 7.5 | 7.5 | 0 |  |
| 29 | 44→49 | advance 5 | 7.5 | 7.5 | 0 |  |
| 30 | 49→50 | advance 1 | 7.5 | 7.5 | 0 |  |

*Reference before/after*: the score if the reference took over just before or just after this call, knowing only what the agent knew then (delivered telemetry, rules, map, its own acknowledgements). *Points lost* = before − after; the column plus the stop loss adds up to the gap.
