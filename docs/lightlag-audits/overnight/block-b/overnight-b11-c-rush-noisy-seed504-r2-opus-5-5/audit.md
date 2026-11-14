# Decision audit: overnight-b11-c-rush-noisy-seed504-r2-opus-5-5

- Model: anthropic/claude-opus-5-5
- Profile `rush_noisy`, seed 504, delay 3 ticks, horizon 50
- Agent: **7** of 10 (reward 0.700, reward.txt 0.700)
- Reference (`kf_mpc`) from the start: **7** (reward 0.700)
- Gap: 0 points = 0.000 reward. Decisions account for 0, stopping early for 0.
- Rebuild reproduces the saved run tick for tick: **yes**

## Main mistakes

None: the agent matched the reference's score. Some decisions below lost points against the reference's continuation and later decisions won them back; that measures the reference from states it would not have chosen, not an agent mistake.

## Where the agent did better than the reference

- call 6, advance 4 at tick 5: +1 points (the reference taking over before this call would have scored 4.25, after it 5.25)
- call 7, advance 3 at tick 9: +1.75 points (the reference taking over before this call would have scored 5.25, after it 7)

## Infrastructure (kept apart from reasoning)

None found: every agent call reached the simulator, Harbor recorded no exception, the rebuild matches the run and reward.txt matches the evaluator.

## Other reasoning findings (no points lost against the reference)

- call 18: **DISCOVERY_MISSED**: d1 (value 3, deadline tick 33) arrived in the packet for tick 21 at tick 24; never sampled

## Episode outcome

- **PERFECT**: scored 7, the reference scored 7 from the start
- **TARGETS_LEFT**: never sampled: d1
- superlog labels unavailable here (ModuleNotFoundError: No module named 'numpy')

## Every decision

| call | tick | what the agent did | reference before | reference after | points lost | tags |
|---:|---|---|---:|---:|---:|---|
| 3 | 0→0 | uplink [drive 309.1° 4 m, drive 309.1° 4.03 m, sample] | 7 | 7 | 0 |  |
| 4 | 0→0 | uplink [drive 95.3° 4.6 m, drive 95.3° 4.59 m, sample] | 7 | 4.25 | 2.75 |  |
| 5 | 0→5 | advance 5 | 4.25 | 4.25 | 0 |  |
| 6 | 5→9 | advance 4 | 4.25 | 5.25 | -1 |  |
| 7 | 9→12 | advance 3 | 5.25 | 7 | -1.75 |  |
| 8 | 12→12 | uplink [drive 179.6° 4.02 m, drive 179.6° 4.02 m, sample] | 7 | 7 | 0 |  |
| 9 | 12→16 | advance 4 | 7 | 7 | 0 |  |
| 11 | 16→16 | uplink [drive 294.2° 3.82 m, drive 294.2° 3.81 m, sample] | 7 | 7 | 0 |  |
| 12 | 16→19 | advance 3 | 7 | 7 | 0 |  |
| 13 | 19→21 | advance 2 | 7 | 7 | 0 |  |
| 15 | 21→21 | uplink [drive 241.9° 2.78 m, drive 241.9° 2.78 m, sample] | 7 | 7 | 0 |  |
| 16 | 21→23 | advance 2 | 7 | 7 | 0 |  |
| 17 | 23→25 | advance 2 | 7 | 7 | 0 |  |
| 18 | 25→25 | uplink [drive 70.3° 4.52 m, drive 70.3° 4.52 m] | 7 | 7 | 0 | DISCOVERY_MISSED |
| 19 | 25→30 | advance 5 | 7 | 7 | 0 |  |
| 20 | 30→33 | advance 3 | 7 | 7 | 0 |  |
| 21 | 33→37 | advance 4 | 7 | 7 | 0 |  |
| 22 | 37→37 | uplink [drive 65.5° 0.43 m] | 7 | 7 | 0 |  |
| 23 | 37→42 | advance 5 | 7 | 7 | 0 |  |
| 25 | 42→47 | advance 5 | 7 | 7 | 0 |  |
| 26 | 47→50 | advance 3 | 7 | 7 | 0 |  |

*Reference before/after*: the score if the reference took over just before or just after this call, knowing only what the agent knew then (delivered telemetry, rules, map, its own acknowledgements). *Points lost* = before − after; the column plus the stop loss adds up to the gap.
