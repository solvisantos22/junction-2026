# Decision audit: reference-seed7-delay3

- Model: scripted (no agent trajectory)
- Profile `core`, seed 7, delay 3 ticks, horizon 80
- Agent: **4** of 4 (reward 1.000, reward.txt 1.000)
- Reference (`team`) from the start: **4** (reward 1.000)
- Gap: 0 points = 0.000 reward. Decisions account for 0, stopping early for 0.
- Rebuild reproduces the saved run tick for tick: **yes**

## Main mistakes

None: no decision scored less than the reference would have from the same moment.

## Infrastructure (kept apart from reasoning)

None found: every agent call reached the simulator, Harbor recorded no exception, the rebuild matches the run and reward.txt matches the evaluator.

## Other reasoning findings (no points lost against the reference)

- call 34: **REPEATED_IN_TRANSIT**: call 34 repeats the uplink sent at tick 16, still in transit (last packet shows tick 17)

## Episode outcome

- **PERFECT**: scored 4, the reference scored 4 from the start

## Every decision

| call | tick | what the agent did | reference before | reference after | points lost | tags |
|---:|---|---|---:|---:|---:|---|
| 4 | 0→0 | uplink [drive 0° 5 m] | 4 | 4 | 0 |  |
| 5 | 0→1 | advance 1 | 4 | 4 | 0 |  |
| 6 | 1→1 | uplink [drive 0° 2.51 m] | 4 | 4 | 0 |  |
| 7 | 1→2 | advance 1 | 4 | 4 | 0 |  |
| 8 | 2→3 | advance 1 | 4 | 4 | 0 |  |
| 9 | 3→4 | advance 1 | 4 | 4 | 0 |  |
| 10 | 4→5 | advance 1 | 4 | 4 | 0 |  |
| 11 | 5→6 | advance 1 | 4 | 4 | 0 |  |
| 12 | 6→7 | advance 1 | 4 | 4 | 0 |  |
| 13 | 7→8 | advance 1 | 4 | 4 | 0 |  |
| 14 | 8→8 | uplink [sample] | 4 | 4 | 0 |  |
| 15 | 8→9 | advance 1 | 4 | 4 | 0 |  |
| 16 | 9→9 | uplink [drive 151.2° 5 m] | 4 | 4 | 0 |  |
| 17 | 9→10 | advance 1 | 4 | 4 | 0 |  |
| 18 | 10→10 | uplink [drive 115.9° 5 m] | 4 | 4 | 0 |  |
| 19 | 10→11 | advance 1 | 4 | 4 | 0 |  |
| 20 | 11→11 | uplink [drive 115.9° 2.02 m] | 4 | 4 | 0 |  |
| 21 | 11→12 | advance 1 | 4 | 4 | 0 |  |
| 22 | 12→13 | advance 1 | 4 | 4 | 0 |  |
| 23 | 13→14 | advance 1 | 4 | 4 | 0 |  |
| 24 | 14→15 | advance 1 | 4 | 4 | 0 |  |
| 25 | 15→16 | advance 1 | 4 | 4 | 0 |  |
| 26 | 16→16 | uplink [sample] | 4 | 4 | 0 |  |
| 27 | 16→17 | advance 1 | 4 | 4 | 0 |  |
| 28 | 17→17 | uplink [drive 232.8° 5 m] | 4 | 4 | 0 |  |
| 29 | 17→18 | advance 1 | 4 | 4 | 0 |  |
| 30 | 18→18 | uplink [drive 232.6° 5 m] | 4 | 4 | 0 |  |
| 31 | 18→19 | advance 1 | 4 | 4 | 0 |  |
| 32 | 19→19 | uplink [drive 232.6° 0.32 m] | 4 | 4 | 0 |  |
| 33 | 19→20 | advance 1 | 4 | 4 | 0 |  |
| 34 | 20→20 | uplink [sample] | 4 | 4 | 0 | REPEATED_IN_TRANSIT |
| 35 | 20→21 | advance 1 | 4 | 4 | 0 |  |
| 36 | 21→21 | uplink [drive 0° 5 m] | 4 | 4 | 0 |  |
| 37 | 21→22 | advance 1 | 4 | 4 | 0 |  |
| 38 | 22→22 | uplink [drive 0° 1.21 m] | 4 | 4 | 0 |  |
| 39 | 22→23 | advance 1 | 4 | 4 | 0 |  |
| 40 | 23→24 | advance 1 | 4 | 4 | 0 |  |
| 41 | 24→24 | uplink [drive 82.6° 0.21 m] | 4 | 4 | 0 |  |
| 42 | 24→25 | advance 1 | 4 | 4 | 0 |  |
| 43 | 25→26 | advance 1 | 4 | 4 | 0 |  |
| 44 | 26→27 | advance 1 | 4 | 4 | 0 |  |
| 45 | 27→28 | advance 1 | 4 | 4 | 0 |  |
| 46 | 28→29 | advance 1 | 4 | 4 | 0 |  |
| 47 | 29→30 | advance 1 | 4 | 4 | 0 |  |
| 48 | 30→31 | advance 1 | 4 | 4 | 0 |  |
| 49 | 31→32 | advance 1 | 4 | 4 | 0 |  |
| 50 | 32→33 | advance 1 | 4 | 4 | 0 |  |
| 51 | 33→34 | advance 1 | 4 | 4 | 0 |  |
| 52 | 34→35 | advance 1 | 4 | 4 | 0 |  |
| 53 | 35→36 | advance 1 | 4 | 4 | 0 |  |
| 54 | 36→37 | advance 1 | 4 | 4 | 0 |  |
| 55 | 37→38 | advance 1 | 4 | 4 | 0 |  |
| 56 | 38→39 | advance 1 | 4 | 4 | 0 |  |
| 57 | 39→40 | advance 1 | 4 | 4 | 0 |  |
| 58 | 40→41 | advance 1 | 4 | 4 | 0 |  |
| 59 | 41→42 | advance 1 | 4 | 4 | 0 |  |
| 60 | 42→43 | advance 1 | 4 | 4 | 0 |  |
| 61 | 43→44 | advance 1 | 4 | 4 | 0 |  |
| 62 | 44→45 | advance 1 | 4 | 4 | 0 |  |
| 63 | 45→46 | advance 1 | 4 | 4 | 0 |  |
| 64 | 46→47 | advance 1 | 4 | 4 | 0 |  |
| 65 | 47→48 | advance 1 | 4 | 4 | 0 |  |
| 66 | 48→49 | advance 1 | 4 | 4 | 0 |  |
| 67 | 49→50 | advance 1 | 4 | 4 | 0 |  |
| 68 | 50→51 | advance 1 | 4 | 4 | 0 |  |
| 69 | 51→52 | advance 1 | 4 | 4 | 0 |  |
| 70 | 52→53 | advance 1 | 4 | 4 | 0 |  |
| 71 | 53→54 | advance 1 | 4 | 4 | 0 |  |
| 72 | 54→55 | advance 1 | 4 | 4 | 0 |  |
| 73 | 55→56 | advance 1 | 4 | 4 | 0 |  |
| 74 | 56→57 | advance 1 | 4 | 4 | 0 |  |
| 75 | 57→58 | advance 1 | 4 | 4 | 0 |  |
| 76 | 58→59 | advance 1 | 4 | 4 | 0 |  |
| 77 | 59→60 | advance 1 | 4 | 4 | 0 |  |
| 78 | 60→61 | advance 1 | 4 | 4 | 0 |  |
| 79 | 61→62 | advance 1 | 4 | 4 | 0 |  |
| 80 | 62→63 | advance 1 | 4 | 4 | 0 |  |
| 81 | 63→64 | advance 1 | 4 | 4 | 0 |  |
| 82 | 64→65 | advance 1 | 4 | 4 | 0 |  |
| 83 | 65→66 | advance 1 | 4 | 4 | 0 |  |
| 84 | 66→67 | advance 1 | 4 | 4 | 0 |  |
| 85 | 67→68 | advance 1 | 4 | 4 | 0 |  |
| 86 | 68→69 | advance 1 | 4 | 4 | 0 |  |
| 87 | 69→70 | advance 1 | 4 | 4 | 0 |  |
| 88 | 70→71 | advance 1 | 4 | 4 | 0 |  |
| 89 | 71→72 | advance 1 | 4 | 4 | 0 |  |
| 90 | 72→73 | advance 1 | 4 | 4 | 0 |  |
| 91 | 73→74 | advance 1 | 4 | 4 | 0 |  |
| 92 | 74→75 | advance 1 | 4 | 4 | 0 |  |
| 93 | 75→76 | advance 1 | 4 | 4 | 0 |  |
| 94 | 76→77 | advance 1 | 4 | 4 | 0 |  |
| 95 | 77→80 | advance 3 | 4 | 4 | 0 |  |

*Reference before/after*: the score if the reference took over just before or just after this call, knowing only what the agent knew then (delivered telemetry, rules, map, its own acknowledgements). *Points lost* = before − after; the column plus the stop loss adds up to the gap.
