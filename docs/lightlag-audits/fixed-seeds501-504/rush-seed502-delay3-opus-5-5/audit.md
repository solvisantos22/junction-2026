# Decision audit: rush-seed502-delay3-opus-5-5

- Model: anthropic/claude-opus-5-5
- Profile `rush`, seed 502, delay 3 ticks, horizon 50
- Agent: **10** of 13 (reward 0.769, reward.txt 0.769)
- Reference (`kf_mpc`) from the start: **8** (reward 0.615)
- Gap: -2 points = -0.154 reward. Decisions account for -2, stopping early for 0.
- Rebuild reproduces the saved run tick for tick: **yes**

## Main mistakes

None: the agent matched the reference's score. Some decisions below lost points against the reference's continuation and later decisions won them back; that measures the reference from states it would not have chosen, not an agent mistake.

## Where the agent did better than the reference

- call 3, uplink [drive 101.4° 4.29 m, sample, drive 139.5° 4.86 m, sample, drive 5.6° 5 m] at tick 0: +2 points (the reference taking over before this call would have scored 8, after it 10)
- call 7, advance 2 at tick 7: +3 points (the reference taking over before this call would have scored 7, after it 10)

## Infrastructure (kept apart from reasoning)

None found: every agent call reached the simulator, Harbor recorded no exception, the rebuild matches the run and reward.txt matches the evaluator.

## Other reasoning findings (no points lost against the reference)

- call 18: **DISCOVERY_MISSED**: d1 (value 2, deadline tick 28) arrived in the packet for tick 21 at tick 24; never sampled

## Episode outcome

- **PERFECT**: scored 10, the reference scored 8 from the start
- **TARGETS_LEFT**: never sampled: d1, t3
- superlog labels unavailable here (ModuleNotFoundError: No module named 'numpy')

## Every decision

| call | tick | what the agent did | reference before | reference after | points lost | tags |
|---:|---|---|---:|---:|---:|---|
| 3 | 0→0 | uplink [drive 101.4° 4.29 m, sample, drive 139.5° 4.86 m, sample, drive 5.6° 5 m] | 8 | 10 | -2 |  |
| 4 | 0→5 | advance 5 | 10 | 10 | 0 |  |
| 5 | 5→7 | advance 2 | 10 | 10 | 0 |  |
| 6 | 7→7 | uplink [drive 5.6° 4 m] | 10 | 7 | 3 |  |
| 7 | 7→9 | advance 2 | 7 | 10 | -3 |  |
| 8 | 9→9 | uplink [drive -0.3° 2 m, sample] | 10 | 10 | 0 |  |
| 9 | 9→11 | advance 2 | 10 | 10 | 0 |  |
| 11 | 11→11 | uplink [drive -105.1° 5 m, drive -105.1° 2.13 m, sample] | 10 | 10 | 0 |  |
| 12 | 11→14 | advance 3 | 10 | 10 | 0 |  |
| 13 | 14→14 | uplink [drive -85.3° 5 m, drive -85.3° 0.77 m, sample] | 10 | 10 | 0 |  |
| 14 | 14→17 | advance 3 | 10 | 10 | 0 |  |
| 15 | 17→17 | uplink [drive 126.4° 5 m, drive 126.4° 0.45 m] | 10 | 10 | 0 |  |
| 16 | 17→20 | advance 3 | 10 | 10 | 0 |  |
| 17 | 20→25 | advance 5 | 10 | 10 | 0 |  |
| 18 | 25→30 | advance 5 | 10 | 10 | 0 | DISCOVERY_MISSED |
| 19 | 30→35 | advance 5 | 10 | 10 | 0 |  |
| 20 | 35→40 | advance 5 | 10 | 10 | 0 |  |
| 21 | 40→45 | advance 5 | 10 | 10 | 0 |  |
| 22 | 45→50 | advance 5 | 10 | 10 | 0 |  |

*Reference before/after*: the score if the reference took over just before or just after this call, knowing only what the agent knew then (delivered telemetry, rules, map, its own acknowledgements). *Points lost* = before − after; the column plus the stop loss adds up to the gap.
