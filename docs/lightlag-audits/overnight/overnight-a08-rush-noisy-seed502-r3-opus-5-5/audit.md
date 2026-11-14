# Decision audit: overnight-a08-rush-noisy-seed502-r3-opus-5-5

- Model: anthropic/claude-opus-5-5
- Profile `rush_noisy`, seed 502, delay 3 ticks, horizon 50
- Agent: **10.5** of 13 (reward 0.808, reward.txt 0.808)
- Reference (`kf_mpc`) from the start: **10** (reward 0.769)
- Gap: -0.5 points = -0.038 reward. Decisions account for -0.5, stopping early for 0.
- Rebuild reproduces the saved run tick for tick: **yes**

## Main mistakes

None: the agent matched the reference's score. Some decisions below lost points against the reference's continuation and later decisions won them back; that measures the reference from states it would not have chosen, not an agent mistake.

## Where the agent did better than the reference

- call 3, uplink [drive 101.4° 4.18 m, sample, drive 139.5° 4.78 m, sample] at tick 0: +0.5 points (the reference taking over before this call would have scored 10, after it 10.5)
- call 7, advance 1 at tick 7: +2 points (the reference taking over before this call would have scored 6, after it 8)
- call 8, advance 2 at tick 8: +2 points (the reference taking over before this call would have scored 8, after it 10)
- call 17, advance 3 at tick 22: +0.5 points (the reference taking over before this call would have scored 10, after it 10.5)

## Infrastructure (kept apart from reasoning)

None found: every agent call reached the simulator, Harbor recorded no exception, the rebuild matches the run and reward.txt matches the evaluator.

## Other reasoning findings (no points lost against the reference)

- call 18: **LATE_SAMPLE**: d1 sampled at tick 30, deadline tick 28
- call 18: **DISCOVERY_MISSED**: d1 (value 2, deadline tick 28) arrived in the packet for tick 21 at tick 24; sampled late

## Episode outcome

- **PERFECT**: scored 10.5, the reference scored 10 from the start
- **TARGETS_LEFT**: never sampled: t4
- superlog labels unavailable here (ModuleNotFoundError: No module named 'numpy')

## Every decision

| call | tick | what the agent did | reference before | reference after | points lost | tags |
|---:|---|---|---:|---:|---:|---|
| 3 | 0→0 | uplink [drive 101.4° 4.18 m, sample, drive 139.5° 4.78 m, sample] | 10 | 10.5 | -0.5 |  |
| 4 | 0→3 | advance 3 | 10.5 | 10.5 | 0 |  |
| 5 | 3→3 | uplink [drive 320.7° 5 m, drive 320.7° 4.28 m, sample] | 10.5 | 6 | 4.5 |  |
| 6 | 3→7 | advance 4 | 6 | 6 | 0 |  |
| 7 | 7→8 | advance 1 | 6 | 8 | -2 |  |
| 8 | 8→10 | advance 2 | 8 | 10 | -2 |  |
| 10 | 10→12 | advance 2 | 10 | 10 | 0 |  |
| 11 | 12→13 | advance 1 | 10 | 10 | 0 |  |
| 12 | 13→13 | uplink [drive 273.6° 5 m, drive 273.6° 0.63 m, sample] | 10 | 10 | 0 |  |
| 13 | 13→13 | uplink [drive 173.4° 5 m, drive 173.4° 1.99 m, sample] | 10 | 10 | 0 |  |
| 14 | 13→18 | advance 5 | 10 | 10 | 0 |  |
| 15 | 18→22 | advance 4 | 10 | 10 | 0 |  |
| 17 | 22→25 | advance 3 | 10 | 10.5 | -0.5 |  |
| 18 | 25→25 | uplink [drive 143.1° 4.38 m, sample, drive 4.9° 5 m, drive 4.9° 2.28 m] | 10.5 | 10.5 | 0 | DISCOVERY_MISSED, LATE_SAMPLE |
| 19 | 25→30 | advance 5 | 10.5 | 10.5 | 0 |  |
| 20 | 30→33 | advance 3 | 10.5 | 10.5 | 0 |  |
| 21 | 33→38 | advance 5 | 10.5 | 10.5 | 0 |  |
| 22 | 38→43 | advance 5 | 10.5 | 10.5 | 0 |  |
| 23 | 43→48 | advance 5 | 10.5 | 10.5 | 0 |  |
| 24 | 48→50 | advance 2 | 10.5 | 10.5 | 0 |  |

*Reference before/after*: the score if the reference took over just before or just after this call, knowing only what the agent knew then (delivered telemetry, rules, map, its own acknowledgements). *Points lost* = before − after; the column plus the stop loss adds up to the gap.
