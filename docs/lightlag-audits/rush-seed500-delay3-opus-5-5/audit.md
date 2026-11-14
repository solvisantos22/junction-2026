# Decision audit: rush-seed500-delay3-opus-5-5

- Model: anthropic/claude-opus-5-5
- Profile `rush`, seed 500, delay 3 ticks, horizon 50
- Agent: **7** of 7 (reward 1.000, reward.txt 1.000)
- Reference (`kf_mpc`) from the start: **7** (reward 1.000)
- Gap: 0 points = 0.000 reward. Decisions account for 0, stopping early for 0.
- Rebuild reproduces the saved run tick for tick: **yes**

## Main mistakes

None: no decision scored less than the reference would have from the same moment.

## Infrastructure (kept apart from reasoning)

None found: every agent call reached the simulator, Harbor recorded no exception, the rebuild matches the run and reward.txt matches the evaluator.

## Episode outcome

- **PERFECT**: scored 7, the reference scored 7 from the start
- superlog labels (`lightlag_dynamic/manh_controllers/superlog.py`): PERFECT; share 1.000, 6 samples taken, 0 failed, 0 late, battery at the end 12.4

## Every decision

| call | tick | what the agent did | reference before | reference after | points lost | tags |
|---:|---|---|---:|---:|---:|---|
| 3 | 0→0 | uplink [drive -166.6° 3.63 m, sample, drive -131.8° 5 m, drive -131.8° 0.36 m, sample] | 7 | 7 | 0 |  |
| 4 | 0→0 | uplink [drive 1.7° 5 m, drive 1.7° 5 m] | 7 | 7 | 0 |  |
| 5 | 0→5 | advance 5 | 7 | 7 | 0 |  |
| 6 | 5→7 | advance 2 | 7 | 7 | 0 |  |
| 7 | 7→7 | uplink [drive -9.5° 0.76 m, sample] | 7 | 7 | 0 |  |
| 8 | 7→8 | advance 1 | 7 | 7 | 0 |  |
| 9 | 8→9 | advance 1 | 7 | 7 | 0 |  |
| 10 | 9→9 | uplink [drive 90.6° 3.63 m, sample] | 7 | 7 | 0 |  |
| 11 | 9→10 | advance 1 | 7 | 7 | 0 |  |
| 12 | 10→11 | advance 1 | 7 | 7 | 0 |  |
| 14 | 11→11 | uplink [drive 123.9° 5 m, drive 123.9° 1.9 m, sample] | 7 | 7 | 0 |  |
| 15 | 11→14 | advance 3 | 7 | 7 | 0 |  |
| 16 | 14→14 | uplink [drive -83.7° 5 m] | 7 | 7 | 0 |  |
| 17 | 14→15 | advance 1 | 7 | 7 | 0 |  |
| 18 | 15→15 | uplink [drive -83.7° 3.27 m, sample] | 7 | 7 | 0 |  |
| 19 | 15→16 | advance 1 | 7 | 7 | 0 |  |
| 20 | 16→16 | uplink [drive 116.7° 3.36 m] | 7 | 7 | 0 |  |
| 21 | 16→19 | advance 3 | 7 | 7 | 0 |  |
| 22 | 19→22 | advance 3 | 7 | 7 | 0 |  |
| 23 | 22→25 | advance 3 | 7 | 7 | 0 |  |
| 24 | 25→28 | advance 3 | 7 | 7 | 0 |  |
| 26 | 28→33 | advance 5 | 7 | 7 | 0 |  |
| 27 | 33→38 | advance 5 | 7 | 7 | 0 |  |
| 28 | 38→43 | advance 5 | 7 | 7 | 0 |  |
| 29 | 43→48 | advance 5 | 7 | 7 | 0 |  |
| 30 | 48→50 | advance 2 | 7 | 7 | 0 |  |

*Reference before/after*: the score if the reference took over just before or just after this call, knowing only what the agent knew then (delivered telemetry, rules, map, its own acknowledgements). *Points lost* = before − after; the column plus the stop loss adds up to the gap.
