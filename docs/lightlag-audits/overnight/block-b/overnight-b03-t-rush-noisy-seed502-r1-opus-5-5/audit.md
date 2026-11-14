# Decision audit: overnight-b03-t-rush-noisy-seed502-r1-opus-5-5

- Model: anthropic/claude-opus-5-5
- Profile `rush_noisy`, seed 502, delay 3 ticks, horizon 50
- Agent: **10.5** of 13 (reward 0.808, reward.txt 0.808)
- Reference (`kf_mpc`) from the start: **10** (reward 0.769)
- Gap: -0.5 points = -0.038 reward. Decisions account for -0.5, stopping early for 0.
- Rebuild reproduces the saved run tick for tick: **yes**

## Main mistakes

None: the agent matched the reference's score. Some decisions below lost points against the reference's continuation and later decisions won them back; that measures the reference from states it would not have chosen, not an agent mistake.

## Where the agent did better than the reference

- call 3, uplink [drive 101.4° 4.18 m, sample, drive 139.5° 4.7 m, sample] at tick 0: +0.5 points (the reference taking over before this call would have scored 10, after it 10.5)
- call 6, advance 2 at tick 8: +0.5 points (the reference taking over before this call would have scored 10, after it 10.5)
- call 20, uplink [sample, drive 4.3° 5 m, drive 4.3° 2.4 m] at tick 41: +0.5 points (the reference taking over before this call would have scored 10, after it 10.5)

## Infrastructure (kept apart from reasoning)

None found: every agent call reached the simulator, Harbor recorded no exception, the rebuild matches the run and reward.txt matches the evaluator.

## Other reasoning findings (no points lost against the reference)

- call 15: **DISCOVERY_MISSED**: d1 (value 2, deadline tick 28) arrived in the packet for tick 21 at tick 24; sampled late
- call 20: **LATE_SAMPLE**: d1 sampled at tick 45, deadline tick 28

## Episode outcome

- **PERFECT**: scored 10.5, the reference scored 10 from the start
- **TARGETS_LEFT**: never sampled: t4
- superlog labels unavailable here (ModuleNotFoundError: No module named 'numpy')

## Every decision

| call | tick | what the agent did | reference before | reference after | points lost | tags |
|---:|---|---|---:|---:|---:|---|
| 3 | 0→0 | uplink [drive 101.4° 4.18 m, sample, drive 139.5° 4.7 m, sample] | 10 | 10.5 | -0.5 |  |
| 4 | 0→5 | advance 5 | 10.5 | 10 | 0.5 | QUEUE_RAN_DRY |
| 5 | 5→8 | advance 3 | 10 | 10 | 0 |  |
| 6 | 8→10 | advance 2 | 10 | 10.5 | -0.5 |  |
| 8 | 10→10 | uplink [drive 271.2° 5 m, drive 271.2° 5 m, drive 271.2° 0.89 m, sample] | 10.5 | 10.5 | 0 |  |
| 9 | 10→15 | advance 5 | 10.5 | 10.5 | 0 |  |
| 10 | 15→15 | uplink [drive 353.2° 5 m, drive 353.2° 1.85 m, sample] | 10.5 | 10.5 | 0 |  |
| 11 | 15→19 | advance 4 | 10.5 | 10.5 | 0 |  |
| 12 | 19→20 | advance 1 | 10.5 | 10.5 | 0 |  |
| 13 | 20→20 | uplink [drive 94.7° 5 m, drive 94.7° 0.7 m, sample] | 10.5 | 10.5 | 0 |  |
| 14 | 20→24 | advance 4 | 10.5 | 10.5 | 0 |  |
| 15 | 24→29 | advance 5 | 10.5 | 10.5 | 0 | DISCOVERY_MISSED |
| 16 | 29→29 | uplink [drive 191.3° 5 m, drive 191.3° 5 m, drive 191.3° 0.3 m] | 10.5 | 10.5 | 0 |  |
| 17 | 29→34 | advance 5 | 10.5 | 10.5 | 0 |  |
| 18 | 34→38 | advance 4 | 10.5 | 10 | 0.5 | QUEUE_RAN_DRY |
| 19 | 38→41 | advance 3 | 10 | 10 | 0 |  |
| 20 | 41→41 | uplink [sample, drive 4.3° 5 m, drive 4.3° 2.4 m] | 10 | 10.5 | -0.5 | LATE_SAMPLE |
| 21 | 41→44 | advance 3 | 10.5 | 10.5 | 0 |  |
| 22 | 44→44 | uplink [drive 0° 0.2 m] | 10.5 | 10.5 | 0 |  |
| 23 | 44→49 | advance 5 | 10.5 | 10.5 | 0 |  |
| 24 | 49→50 | advance 2 | 10.5 | 10.5 | 0 |  |

*Reference before/after*: the score if the reference took over just before or just after this call, knowing only what the agent knew then (delivered telemetry, rules, map, its own acknowledgements). *Points lost* = before − after; the column plus the stop loss adds up to the gap.
