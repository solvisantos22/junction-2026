# Decision audit: overnight-a05-rush-noisy-seed502-r2-opus-5-5

- Model: anthropic/claude-opus-5-5
- Profile `rush_noisy`, seed 502, delay 3 ticks, horizon 50
- Agent: **10** of 13 (reward 0.769, reward.txt 0.769)
- Reference (`kf_mpc`) from the start: **10** (reward 0.769)
- Gap: 0 points = 0.000 reward. Decisions account for 0, stopping early for 0.
- Rebuild reproduces the saved run tick for tick: **yes**

## Main mistakes

None: no decision scored less than the reference would have from the same moment.

## Infrastructure (kept apart from reasoning)

None found: every agent call reached the simulator, Harbor recorded no exception, the rebuild matches the run and reward.txt matches the evaluator.

## Other reasoning findings (no points lost against the reference)

- call 17: **DISCOVERY_MISSED**: d1 (value 2, deadline tick 28) arrived in the packet for tick 21 at tick 24; never sampled

## Episode outcome

- **PERFECT**: scored 10, the reference scored 10 from the start
- **TARGETS_LEFT**: never sampled: d1, t4
- superlog labels unavailable here (ModuleNotFoundError: No module named 'numpy')

## Every decision

| call | tick | what the agent did | reference before | reference after | points lost | tags |
|---:|---|---|---:|---:|---:|---|
| 3 | 0→0 | uplink [drive 101.4° 4.29 m, sample, drive 139.5° 4.85 m, sample] | 10 | 10 | 0 |  |
| 4 | 0→5 | advance 5 | 10 | 10 | 0 |  |
| 5 | 5→8 | advance 3 | 10 | 10 | 0 |  |
| 6 | 8→10 | advance 2 | 10 | 10 | 0 |  |
| 8 | 10→10 | uplink [drive -39.4° 4.85 m, drive -39.4° 4.85 m, sample] | 10 | 10 | 0 |  |
| 9 | 10→10 | uplink [drive -143.5° 4.11 m, drive -143.5° 4.11 m, sample] | 10 | 10 | 0 |  |
| 10 | 10→15 | advance 5 | 10 | 10 | 0 |  |
| 11 | 15→15 | uplink [drive -7.9° 3.45 m, drive -7.9° 3.45 m, sample] | 10 | 10 | 0 |  |
| 12 | 15→19 | advance 4 | 10 | 10 | 0 |  |
| 14 | 19→19 | uplink [drive 125.2° 2.76 m, drive 125.2° 2.76 m] | 10 | 10 | 0 |  |
| 15 | 19→23 | advance 4 | 10 | 10 | 0 |  |
| 16 | 23→25 | advance 2 | 10 | 10 | 0 |  |
| 17 | 25→30 | advance 5 | 10 | 10 | 0 | DISCOVERY_MISSED |
| 18 | 30→34 | advance 4 | 10 | 10 | 0 |  |
| 19 | 34→34 | uplink [drive 190° 0.29 m] | 10 | 10 | 0 |  |
| 20 | 34→39 | advance 5 | 10 | 10 | 0 |  |
| 21 | 39→44 | advance 5 | 10 | 10 | 0 |  |
| 22 | 44→49 | advance 5 | 10 | 10 | 0 |  |
| 23 | 49→50 | advance 1 | 10 | 10 | 0 |  |

*Reference before/after*: the score if the reference took over just before or just after this call, knowing only what the agent knew then (delivered telemetry, rules, map, its own acknowledgements). *Points lost* = before − after; the column plus the stop loss adds up to the gap.
