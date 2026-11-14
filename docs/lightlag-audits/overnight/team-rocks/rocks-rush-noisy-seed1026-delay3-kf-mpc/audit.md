# Decision audit: rocks-rush-noisy-seed1026-delay3-kf-mpc

- Model: scripted (no agent trajectory)
- Profile `rush_noisy`, seed 1026, delay 3 ticks, horizon 50
- Agent: **10** of 13 (reward 0.769, reward.txt 0.769)
- Reference (`kf_mpc`) from the start: **10** (reward 0.769)
- Gap: 0 points = 0.000 reward. Decisions account for 0, stopping early for 0.
- Rebuild reproduces the saved run tick for tick: **yes**

## Main mistakes

None: no decision scored less than the reference would have from the same moment.

## Infrastructure (kept apart from reasoning)

None found: every agent call reached the simulator, Harbor recorded no exception, the rebuild matches the run and reward.txt matches the evaluator.

## Other reasoning findings (no points lost against the reference)

- call 18: **SAMPLE_MISSED**: sample command 12 at tick 15 failed (slip_not_corrected)
- call 25: **DISCOVERY_MISSED**: d1 (value 2, deadline tick 17) arrived in the packet for tick 10 at tick 13; never sampled

## Episode outcome

- **PERFECT**: scored 10, the reference scored 10 from the start
- **TARGETS_LEFT**: never sampled: d1, t2
- superlog labels unavailable here (ModuleNotFoundError: No module named 'numpy')

## Every decision

| call | tick | what the agent did | reference before | reference after | points lost | tags |
|---:|---|---|---:|---:|---:|---|
| 6 | 0→0 | uplink [drive 19.5° 3.63 m, drive 19.5° 3.63 m, sample] | 10 | 10 | 0 |  |
| 7 | 0→1 | advance 1 | 10 | 10 | 0 |  |
| 8 | 1→2 | advance 1 | 10 | 10 | 0 |  |
| 9 | 2→3 | advance 1 | 10 | 10 | 0 |  |
| 10 | 3→3 | uplink [drive 171° 2.83 m, drive 171° 2.83 m, sample] | 10 | 10 | 0 |  |
| 11 | 3→4 | advance 1 | 10 | 10 | 0 |  |
| 12 | 4→5 | advance 1 | 10 | 10 | 0 |  |
| 13 | 5→6 | advance 1 | 10 | 10 | 0 |  |
| 14 | 6→6 | uplink [drive 110.7° 3.82 m, drive 110.7° 3.82 m, sample] | 10 | 10 | 0 |  |
| 15 | 6→7 | advance 1 | 10 | 10 | 0 |  |
| 16 | 7→8 | advance 1 | 10 | 10 | 0 |  |
| 17 | 8→9 | advance 1 | 10 | 10 | 0 |  |
| 18 | 9→9 | uplink [drive 195.1° 4.75 m, drive 227.8° 3.37 m, sample] | 10 | 10 | 0 | SAMPLE_MISSED |
| 19 | 9→10 | advance 1 | 10 | 10 | 0 |  |
| 20 | 10→11 | advance 1 | 10 | 10 | 0 |  |
| 21 | 11→12 | advance 1 | 10 | 10 | 0 |  |
| 22 | 12→12 | uplink [drive 338.2° 1.41 m, drive 272.5° 3.38 m, drive 243.7° 4.48 m, sample] | 10 | 10 | 0 |  |
| 23 | 12→13 | advance 1 | 10 | 10 | 0 |  |
| 25 | 13→14 | advance 1 | 10 | 10 | 0 | DISCOVERY_MISSED |
| 27 | 14→15 | advance 1 | 10 | 10 | 0 |  |
| 28 | 15→16 | advance 1 | 10 | 10 | 0 |  |
| 29 | 16→16 | uplink [drive 31.7° 4.51 m, sample] | 10 | 10 | 0 |  |
| 30 | 16→17 | advance 1 | 10 | 10 | 0 |  |
| 31 | 17→18 | advance 1 | 10 | 10 | 0 |  |
| 32 | 18→18 | uplink [drive 0.4° 3.97 m] | 10 | 10 | 0 |  |
| 33 | 18→19 | advance 1 | 10 | 10 | 0 |  |
| 34 | 19→20 | advance 1 | 10 | 10 | 0 |  |
| 35 | 20→21 | advance 1 | 10 | 10 | 0 |  |
| 36 | 21→22 | advance 1 | 10 | 10 | 0 |  |
| 37 | 22→23 | advance 1 | 10 | 10 | 0 |  |
| 38 | 23→24 | advance 1 | 10 | 10 | 0 |  |
| 39 | 24→25 | advance 1 | 10 | 10 | 0 |  |
| 40 | 25→26 | advance 1 | 10 | 10 | 0 |  |
| 41 | 26→27 | advance 1 | 10 | 10 | 0 |  |
| 42 | 27→28 | advance 1 | 10 | 10 | 0 |  |
| 43 | 28→29 | advance 1 | 10 | 10 | 0 |  |
| 44 | 29→30 | advance 1 | 10 | 10 | 0 |  |
| 45 | 30→31 | advance 1 | 10 | 10 | 0 |  |
| 46 | 31→32 | advance 1 | 10 | 10 | 0 |  |
| 47 | 32→33 | advance 1 | 10 | 10 | 0 |  |
| 48 | 33→34 | advance 1 | 10 | 10 | 0 |  |
| 49 | 34→35 | advance 1 | 10 | 10 | 0 |  |
| 50 | 35→36 | advance 1 | 10 | 10 | 0 |  |
| 51 | 36→37 | advance 1 | 10 | 10 | 0 |  |
| 52 | 37→38 | advance 1 | 10 | 10 | 0 |  |
| 53 | 38→39 | advance 1 | 10 | 10 | 0 |  |
| 54 | 39→40 | advance 1 | 10 | 10 | 0 |  |
| 55 | 40→41 | advance 1 | 10 | 10 | 0 |  |
| 56 | 41→42 | advance 1 | 10 | 10 | 0 |  |
| 57 | 42→43 | advance 1 | 10 | 10 | 0 |  |
| 58 | 43→44 | advance 1 | 10 | 10 | 0 |  |
| 59 | 44→45 | advance 1 | 10 | 10 | 0 |  |
| 60 | 45→46 | advance 1 | 10 | 10 | 0 |  |
| 61 | 46→47 | advance 1 | 10 | 10 | 0 |  |
| 62 | 47→48 | advance 1 | 10 | 10 | 0 |  |
| 63 | 48→49 | advance 1 | 10 | 10 | 0 |  |
| 64 | 49→50 | advance 1 | 10 | 10 | 0 |  |

*Reference before/after*: the score if the reference took over just before or just after this call, knowing only what the agent knew then (delivered telemetry, rules, map, its own acknowledgements). *Points lost* = before − after; the column plus the stop loss adds up to the gap.
