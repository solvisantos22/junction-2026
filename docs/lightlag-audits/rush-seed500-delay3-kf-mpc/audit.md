# Decision audit: rush-seed500-delay3-kf-mpc

- Model: scripted (no agent trajectory)
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

## Every decision

| call | tick | what the agent did | reference before | reference after | points lost | tags |
|---:|---|---|---:|---:|---:|---|
| 6 | 0→0 | uplink [drive 83.6° 2.52 m, drive 83.6° 2.52 m, sample] | 7 | 7 | 0 |  |
| 7 | 0→1 | advance 1 | 7 | 7 | 0 |  |
| 8 | 1→2 | advance 1 | 7 | 7 | 0 |  |
| 9 | 2→3 | advance 1 | 7 | 7 | 0 |  |
| 10 | 3→3 | uplink [drive 303.9° 3.38 m, drive 303.9° 3.38 m, sample] | 7 | 7 | 0 |  |
| 11 | 3→4 | advance 1 | 7 | 7 | 0 |  |
| 12 | 4→5 | advance 1 | 7 | 7 | 0 |  |
| 13 | 5→6 | advance 1 | 7 | 7 | 0 |  |
| 14 | 6→6 | uplink [drive 270.7° 3.61 m, sample] | 7 | 7 | 0 |  |
| 15 | 6→7 | advance 1 | 7 | 7 | 0 |  |
| 16 | 7→8 | advance 1 | 7 | 7 | 0 |  |
| 17 | 8→8 | uplink [drive 154.5° 4.3 m, drive 154.5° 4.3 m, sample] | 7 | 7 | 0 |  |
| 18 | 8→9 | advance 1 | 7 | 7 | 0 |  |
| 19 | 9→10 | advance 1 | 7 | 7 | 0 |  |
| 20 | 10→11 | advance 1 | 7 | 7 | 0 |  |
| 21 | 11→11 | uplink [drive 228.9° 2.69 m, drive 228.9° 2.69 m, sample] | 7 | 7 | 0 |  |
| 22 | 11→12 | advance 1 | 7 | 7 | 0 |  |
| 24 | 12→13 | advance 1 | 7 | 7 | 0 |  |
| 25 | 13→14 | advance 1 | 7 | 7 | 0 |  |
| 26 | 14→14 | uplink [drive 10.3° 3.99 m, drive 10.3° 3.99 m, sample] | 7 | 7 | 0 |  |
| 27 | 14→15 | advance 1 | 7 | 7 | 0 |  |
| 28 | 15→16 | advance 1 | 7 | 7 | 0 |  |
| 29 | 16→17 | advance 1 | 7 | 7 | 0 |  |
| 30 | 17→17 | uplink [drive 119.7° 3.55 m] | 7 | 7 | 0 |  |
| 31 | 17→18 | advance 1 | 7 | 7 | 0 |  |
| 32 | 18→19 | advance 1 | 7 | 7 | 0 |  |
| 33 | 19→20 | advance 1 | 7 | 7 | 0 |  |
| 34 | 20→21 | advance 1 | 7 | 7 | 0 |  |
| 35 | 21→22 | advance 1 | 7 | 7 | 0 |  |
| 36 | 22→23 | advance 1 | 7 | 7 | 0 |  |
| 37 | 23→24 | advance 1 | 7 | 7 | 0 |  |
| 38 | 24→25 | advance 1 | 7 | 7 | 0 |  |
| 39 | 25→26 | advance 1 | 7 | 7 | 0 |  |
| 40 | 26→27 | advance 1 | 7 | 7 | 0 |  |
| 41 | 27→28 | advance 1 | 7 | 7 | 0 |  |
| 42 | 28→29 | advance 1 | 7 | 7 | 0 |  |
| 43 | 29→30 | advance 1 | 7 | 7 | 0 |  |
| 44 | 30→31 | advance 1 | 7 | 7 | 0 |  |
| 45 | 31→32 | advance 1 | 7 | 7 | 0 |  |
| 46 | 32→33 | advance 1 | 7 | 7 | 0 |  |
| 47 | 33→34 | advance 1 | 7 | 7 | 0 |  |
| 48 | 34→35 | advance 1 | 7 | 7 | 0 |  |
| 49 | 35→36 | advance 1 | 7 | 7 | 0 |  |
| 50 | 36→37 | advance 1 | 7 | 7 | 0 |  |
| 51 | 37→38 | advance 1 | 7 | 7 | 0 |  |
| 52 | 38→39 | advance 1 | 7 | 7 | 0 |  |
| 53 | 39→40 | advance 1 | 7 | 7 | 0 |  |
| 54 | 40→41 | advance 1 | 7 | 7 | 0 |  |
| 55 | 41→42 | advance 1 | 7 | 7 | 0 |  |
| 56 | 42→43 | advance 1 | 7 | 7 | 0 |  |
| 57 | 43→44 | advance 1 | 7 | 7 | 0 |  |
| 58 | 44→45 | advance 1 | 7 | 7 | 0 |  |
| 59 | 45→46 | advance 1 | 7 | 7 | 0 |  |
| 60 | 46→47 | advance 1 | 7 | 7 | 0 |  |
| 61 | 47→48 | advance 1 | 7 | 7 | 0 |  |
| 62 | 48→49 | advance 1 | 7 | 7 | 0 |  |
| 63 | 49→50 | advance 1 | 7 | 7 | 0 |  |

*Reference before/after*: the score if the reference took over just before or just after this call, knowing only what the agent knew then (delivered telemetry, rules, map, its own acknowledgements). *Points lost* = before − after; the column plus the stop loss adds up to the gap.
