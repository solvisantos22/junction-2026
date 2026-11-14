# Decision audit: overnight-b06-t-rush-seed501-r1-opus-5-5

- Model: anthropic/claude-opus-5-5
- Profile `rush`, seed 501, delay 3 ticks, horizon 50
- Agent: **11** of 12 (reward 0.917, reward.txt 0.917)
- Reference (`kf_mpc`) from the start: **10** (reward 0.833)
- Gap: -1 points = -0.083 reward. Decisions account for -1, stopping early for 0.
- Rebuild reproduces the saved run tick for tick: **yes**

## Main mistakes

None: the agent matched the reference's score. Some decisions below lost points against the reference's continuation and later decisions won them back; that measures the reference from states it would not have chosen, not an agent mistake.

## Where the agent did better than the reference

- call 7, advance 2 at tick 8: +2 points (the reference taking over before this call would have scored 9, after it 11)

## Infrastructure (kept apart from reasoning)

None found: every agent call reached the simulator, Harbor recorded no exception, the rebuild matches the run and reward.txt matches the evaluator.

## Episode outcome

- **PERFECT**: scored 11, the reference scored 10 from the start
- **TARGETS_LEFT**: never sampled: t1
- superlog labels unavailable here (ModuleNotFoundError: No module named 'numpy')

## Every decision

| call | tick | what the agent did | reference before | reference after | points lost | tags |
|---:|---|---|---:|---:|---:|---|
| 3 | 0→0 | uplink [drive 357.4° 2.65 m, drive 357.4° 2.65 m, sample, drive 213.1° 4.29 m, drive 213.1° 4.29 m] | 10 | 9 | 1 |  |
| 4 | 0→5 | advance 5 | 9 | 9 | 0 |  |
| 5 | 5→5 | uplink [drive 213.1° 4.29 m, sample, drive 72.8° 3.9 m] | 9 | 9 | 0 |  |
| 6 | 5→8 | advance 3 | 9 | 9 | 0 |  |
| 7 | 8→10 | advance 2 | 9 | 11 | -2 |  |
| 8 | 10→10 | uplink [drive 347.6° 3.42 m, sample, drive 117° 4.99 m, sample, drive 79.3° 5 m] | 11 | 11 | 0 |  |
| 9 | 10→13 | advance 3 | 11 | 11 | 0 |  |
| 10 | 13→15 | advance 2 | 11 | 11 | 0 |  |
| 11 | 15→15 | uplink [sample, drive 197.5° 3.54 m, sample, drive 324.4° 3.47 m, drive 324.4° 3.47 m] | 11 | 11 | 0 |  |
| 12 | 15→20 | advance 5 | 11 | 11 | 0 |  |
| 13 | 20→25 | advance 5 | 11 | 11 | 0 |  |
| 14 | 25→26 | advance 1 | 11 | 11 | 0 |  |
| 15 | 26→31 | advance 5 | 11 | 11 | 0 |  |
| 16 | 31→36 | advance 5 | 11 | 11 | 0 |  |
| 17 | 36→41 | advance 5 | 11 | 11 | 0 |  |
| 18 | 41→46 | advance 5 | 11 | 11 | 0 |  |
| 19 | 46→50 | advance 5 | 11 | 11 | 0 |  |

*Reference before/after*: the score if the reference took over just before or just after this call, knowing only what the agent knew then (delivered telemetry, rules, map, its own acknowledgements). *Points lost* = before − after; the column plus the stop loss adds up to the gap.
