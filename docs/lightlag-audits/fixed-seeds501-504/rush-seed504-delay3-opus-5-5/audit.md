# Decision audit: rush-seed504-delay3-opus-5-5

- Model: anthropic/claude-opus-5-5
- Profile `rush`, seed 504, delay 3 ticks, horizon 50
- Agent: **7** of 10 (reward 0.700, reward.txt 0.700)
- Reference (`kf_mpc`) from the start: **7** (reward 0.700)
- Gap: 0 points = 0.000 reward. Decisions account for 0, stopping early for 0.
- Rebuild reproduces the saved run tick for tick: **yes**

## Main mistakes

None: no decision scored less than the reference would have from the same moment.

## Infrastructure (kept apart from reasoning)

None found: every agent call reached the simulator, Harbor recorded no exception, the rebuild matches the run and reward.txt matches the evaluator.

## Other reasoning findings (no points lost against the reference)

- call 22: **DISCOVERY_MISSED**: d1 (value 3, deadline tick 33) arrived in the packet for tick 21 at tick 24; never sampled

## Episode outcome

- **PERFECT**: scored 7, the reference scored 7 from the start
- **TARGETS_LEFT**: never sampled: d1
- superlog labels unavailable here (ModuleNotFoundError: No module named 'numpy')

## Every decision

| call | tick | what the agent did | reference before | reference after | points lost | tags |
|---:|---|---|---:|---:|---:|---|
| 3 | 0→0 | uplink [drive -50.9° 4 m, drive -50.9° 4.03 m, sample, drive 95.3° 4.6 m, drive 95.3° 4.59 m] | 7 | 7 | 0 |  |
| 4 | 0→5 | advance 5 | 7 | 7 | 0 |  |
| 5 | 5→5 | uplink [sample] | 7 | 7 | 0 |  |
| 6 | 5→7 | advance 2 | 7 | 7 | 0 |  |
| 7 | 7→7 | uplink [drive 175.8° 3.9 m, drive 175.8° 3.84 m, sample] | 7 | 7 | 0 |  |
| 8 | 7→9 | advance 2 | 7 | 7 | 0 |  |
| 10 | 9→10 | advance 1 | 7 | 7 | 0 |  |
| 11 | 10→10 | uplink [drive -67.8° 3.8 m, drive -67.8° 3.75 m, sample] | 7 | 7 | 0 |  |
| 12 | 10→12 | advance 2 | 7 | 7 | 0 |  |
| 13 | 12→14 | advance 2 | 7 | 7 | 0 |  |
| 14 | 14→16 | advance 2 | 7 | 7 | 0 |  |
| 16 | 16→16 | uplink [drive -121.4° 2.8 m, drive -121.4° 2.8 m, sample] | 7 | 7 | 0 |  |
| 17 | 16→18 | advance 2 | 7 | 7 | 0 |  |
| 18 | 18→21 | advance 3 | 7 | 7 | 0 |  |
| 20 | 21→23 | advance 2 | 7 | 7 | 0 |  |
| 21 | 23→25 | advance 2 | 7 | 7 | 0 |  |
| 22 | 25→25 | uplink [drive 66.6° 4.45 m, drive 66.6° 4.42 m] | 7 | 7 | 0 | DISCOVERY_MISSED |
| 23 | 25→30 | advance 5 | 7 | 7 | 0 |  |
| 24 | 30→33 | advance 3 | 7 | 7 | 0 |  |
| 26 | 33→38 | advance 5 | 7 | 7 | 0 |  |
| 27 | 38→43 | advance 5 | 7 | 7 | 0 |  |
| 28 | 43→48 | advance 5 | 7 | 7 | 0 |  |
| 29 | 48→50 | advance 2 | 7 | 7 | 0 |  |

*Reference before/after*: the score if the reference took over just before or just after this call, knowing only what the agent knew then (delivered telemetry, rules, map, its own acknowledgements). *Points lost* = before − after; the column plus the stop loss adds up to the gap.
