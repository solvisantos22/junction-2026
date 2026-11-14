# Decision audit: overnight-b10-t-rush-noisy-seed502-r2-opus-5-5

- Model: anthropic/claude-opus-5-5
- Profile `rush_noisy`, seed 502, delay 3 ticks, horizon 50
- Agent: **10** of 13 (reward 0.769, reward.txt 0.769)
- Reference (`kf_mpc`) from the start: **10** (reward 0.769)
- Gap: 0 points = 0.000 reward. Decisions account for 0, stopping early for 0.
- Rebuild reproduces the saved run tick for tick: **yes**

## Main mistakes

None: the agent matched the reference's score. Some decisions below lost points against the reference's continuation and later decisions won them back; that measures the reference from states it would not have chosen, not an agent mistake.

## Where the agent did better than the reference

- call 3, uplink [drive 101.4° 4.25 m, sample, drive 139.5° 4.75 m, sample] at tick 0: +0.5 points (the reference taking over before this call would have scored 10, after it 10.5)
- call 8, uplink [drive 5.6° 1.1 m, sample] at tick 9: +2 points (the reference taking over before this call would have scored 8, after it 10)

## Infrastructure (kept apart from reasoning)

None found: every agent call reached the simulator, Harbor recorded no exception, the rebuild matches the run and reward.txt matches the evaluator.

## Other reasoning findings (no points lost against the reference)

- call 19: **DISCOVERY_MISSED**: d1 (value 2, deadline tick 28) arrived in the packet for tick 21 at tick 24; never sampled

## Episode outcome

- **PERFECT**: scored 10, the reference scored 10 from the start
- **TARGETS_LEFT**: never sampled: d1, t3
- superlog labels unavailable here (ModuleNotFoundError: No module named 'numpy')

## Every decision

| call | tick | what the agent did | reference before | reference after | points lost | tags |
|---:|---|---|---:|---:|---:|---|
| 3 | 0→0 | uplink [drive 101.4° 4.25 m, sample, drive 139.5° 4.75 m, sample] | 10 | 10.5 | -0.5 |  |
| 4 | 0→0 | uplink [drive 5.6° 5 m, drive 5.6° 5 m] | 10.5 | 9 | 1.5 |  |
| 5 | 0→5 | advance 5 | 9 | 9 | 0 |  |
| 6 | 5→8 | advance 3 | 9 | 9 | 0 |  |
| 7 | 8→9 | advance 1 | 9 | 8 | 1 | QUEUE_RAN_DRY |
| 8 | 9→9 | uplink [drive 5.6° 1.1 m, sample] | 8 | 10 | -2 |  |
| 9 | 9→12 | advance 3 | 10 | 10 | 0 |  |
| 10 | 12→12 | uplink [drive 251.9° 5 m, drive 251.9° 2.4 m, sample] | 10 | 10 | 0 |  |
| 11 | 12→15 | advance 3 | 10 | 10 | 0 |  |
| 12 | 15→15 | uplink [drive 274.7° 5 m, drive 274.7° 0.76 m, sample] | 10 | 10 | 0 |  |
| 13 | 15→17 | advance 2 | 10 | 10 | 0 |  |
| 14 | 17→17 | uplink [drive 126.4° 5 m] | 10 | 10 | 0 |  |
| 15 | 17→20 | advance 3 | 10 | 10 | 0 |  |
| 16 | 20→23 | advance 3 | 10 | 10 | 0 |  |
| 17 | 23→25 | advance 2 | 10 | 10 | 0 |  |
| 19 | 25→30 | advance 5 | 10 | 10 | 0 | DISCOVERY_MISSED |
| 20 | 30→35 | advance 5 | 10 | 10 | 0 |  |
| 21 | 35→40 | advance 5 | 10 | 10 | 0 |  |
| 22 | 40→45 | advance 5 | 10 | 10 | 0 |  |
| 23 | 45→50 | advance 5 | 10 | 10 | 0 |  |

*Reference before/after*: the score if the reference took over just before or just after this call, knowing only what the agent knew then (delivered telemetry, rules, map, its own acknowledgements). *Points lost* = before − after; the column plus the stop loss adds up to the gap.
