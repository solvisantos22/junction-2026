# Decision audit: rocks-rush-noisy-seed1026-r1-opus-5-5

- Model: anthropic/claude-opus-5-5
- Profile `rush_noisy`, seed 1026, delay 3 ticks, horizon 50
- Agent: **11** of 13 (reward 0.846, reward.txt 0.846)
- Reference (`kf_mpc`) from the start: **10** (reward 0.769)
- Gap: -1 points = -0.077 reward. Decisions account for -1, stopping early for 0.
- Rebuild reproduces the saved run tick for tick: **yes**

## Main mistakes

None: the agent matched the reference's score. Some decisions below lost points against the reference's continuation and later decisions won them back; that measures the reference from states it would not have chosen, not an agent mistake.

## Where the agent did better than the reference

- call 9, uplink [drive 186.8° 3.62 m, drive 225.9° 3.76 m, sample] at tick 12: +0.25 points (the reference taking over before this call would have scored 8.75, after it 9)
- call 14, uplink [drive 214.6° 4.28 m, sample] at tick 18: +2 points (the reference taking over before this call would have scored 9, after it 11)

## Infrastructure (kept apart from reasoning)

None found: every agent call reached the simulator, Harbor recorded no exception, the rebuild matches the run and reward.txt matches the evaluator.

## Other reasoning findings (no points lost against the reference)

- call 11: **DISCOVERY_MISSED**: d1 (value 2, deadline tick 17) arrived in the packet for tick 10 at tick 13; never sampled

## Episode outcome

- **PERFECT**: scored 11, the reference scored 10 from the start
- **TARGETS_LEFT**: never sampled: d1
- superlog labels unavailable here (ModuleNotFoundError: No module named 'numpy')

## Every decision

| call | tick | what the agent did | reference before | reference after | points lost | tags |
|---:|---|---|---:|---:|---:|---|
| 3 | 0→0 | uplink [drive 19.5° 5 m, drive 19.5° 2.26 m, sample] | 10 | 10 | 0 |  |
| 4 | 0→0 | uplink [drive 171.1° 5 m, drive 171.1° 0.67 m, sample] | 10 | 10 | 0 |  |
| 5 | 0→5 | advance 5 | 10 | 10 | 0 |  |
| 6 | 5→9 | advance 4 | 10 | 8.75 | 1.25 | QUEUE_RAN_DRY |
| 7 | 9→9 | uplink [drive 110.7° 3.21 m, drive 110.7° 4.41 m, sample] | 8.75 | 8.75 | 0 |  |
| 8 | 9→12 | advance 3 | 8.75 | 8.75 | 0 |  |
| 9 | 12→12 | uplink [drive 186.8° 3.62 m, drive 225.9° 3.76 m, sample] | 8.75 | 9 | -0.25 |  |
| 10 | 12→15 | advance 3 | 9 | 9 | 0 |  |
| 11 | 15→15 | uplink [drive 317.4° 2.27 m, drive 279.5° 4.02 m, sample] | 9 | 9 | 0 | DISCOVERY_MISSED |
| 12 | 15→17 | advance 2 | 9 | 9 | 0 |  |
| 13 | 17→18 | advance 1 | 9 | 9 | 0 |  |
| 14 | 18→18 | uplink [drive 214.6° 4.28 m, sample] | 9 | 11 | -2 |  |
| 15 | 18→21 | advance 3 | 11 | 11 | 0 |  |
| 16 | 21→21 | uplink [drive 15.4° 5 m, drive 15.4° 2.86 m] | 11 | 11 | 0 |  |
| 17 | 21→24 | advance 3 | 11 | 11 | 0 |  |
| 18 | 24→26 | advance 2 | 11 | 11 | 0 |  |
| 19 | 26→29 | advance 3 | 11 | 11 | 0 |  |
| 21 | 29→32 | advance 3 | 11 | 11 | 0 |  |
| 22 | 32→36 | advance 4 | 11 | 11 | 0 |  |
| 23 | 36→41 | advance 5 | 11 | 11 | 0 |  |
| 24 | 41→46 | advance 5 | 11 | 11 | 0 |  |
| 25 | 46→50 | advance 5 | 11 | 11 | 0 |  |

*Reference before/after*: the score if the reference took over just before or just after this call, knowing only what the agent knew then (delivered telemetry, rules, map, its own acknowledgements). *Points lost* = before − after; the column plus the stop loss adds up to the gap.
