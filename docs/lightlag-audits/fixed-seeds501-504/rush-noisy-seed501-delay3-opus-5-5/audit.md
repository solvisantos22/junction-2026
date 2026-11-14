# Decision audit: rush-noisy-seed501-delay3-opus-5-5

- Model: anthropic/claude-opus-5-5
- Profile `rush_noisy`, seed 501, delay 3 ticks, horizon 50
- Agent: **9.5** of 12 (reward 0.792, reward.txt 0.792)
- Reference (`kf_mpc`) from the start: **8** (reward 0.667)
- Gap: -1.5 points = -0.125 reward. Decisions account for -1.5, stopping early for 0.
- Rebuild reproduces the saved run tick for tick: **yes**

## Main mistakes

None: the agent matched the reference's score. Some decisions below lost points against the reference's continuation and later decisions won them back; that measures the reference from states it would not have chosen, not an agent mistake.

## Where the agent did better than the reference

- call 3, uplink [drive 357.5° 5 m, drive 357.5° 0.18 m, sample] at tick 0: +1 points (the reference taking over before this call would have scored 8, after it 9)
- call 6, uplink [drive 216.6° 5 m] at tick 5: +1 points (the reference taking over before this call would have scored 8, after it 9)
- call 14, uplink [drive 291.7° 4.63 m, sample, drive 208.4° 5 m, sample] at tick 11: +1.5 points (the reference taking over before this call would have scored 7.5, after it 9)
- call 21, uplink [drive 117.9° 4.46 m, sample] at tick 19: +0.5 points (the reference taking over before this call would have scored 9, after it 9.5)

## Infrastructure (kept apart from reasoning)

None found: every agent call reached the simulator, Harbor recorded no exception, the rebuild matches the run and reward.txt matches the evaluator.

## Other reasoning findings (no points lost against the reference)

- call 17: **DISCOVERY_MISSED**: d1 (value 2, deadline tick 21) arrived in the packet for tick 11 at tick 14; sampled late
- call 21: **LATE_SAMPLE**: d1 sampled at tick 24, deadline tick 21

## Episode outcome

- **PERFECT**: scored 9.5, the reference scored 8 from the start
- **TARGETS_LEFT**: never sampled: t1
- superlog labels unavailable here (ModuleNotFoundError: No module named 'numpy')

## Every decision

| call | tick | what the agent did | reference before | reference after | points lost | tags |
|---:|---|---|---:|---:|---:|---|
| 3 | 0→0 | uplink [drive 357.5° 5 m, drive 357.5° 0.18 m, sample] | 8 | 9 | -1 |  |
| 4 | 0→0 | uplink [drive 106.6° 5 m, drive 106.6° 4.15 m, sample] | 9 | 8 | 1 | SAMPLE_MISSED |
| 5 | 0→5 | advance 5 | 8 | 8 | 0 |  |
| 6 | 5→5 | uplink [drive 216.6° 5 m] | 8 | 9 | -1 |  |
| 7 | 5→7 | advance 2 | 9 | 9 | 0 |  |
| 8 | 7→8 | advance 1 | 9 | 9 | 0 |  |
| 9 | 8→8 | uplink [drive 212.7° 0.5 m, sample] | 9 | 9 | 0 |  |
| 10 | 8→9 | advance 1 | 9 | 9 | 0 |  |
| 11 | 9→10 | advance 1 | 9 | 9 | 0 |  |
| 12 | 10→10 | uplink [drive 255° 4.95 m] | 9 | 7.5 | 1.5 |  |
| 13 | 10→11 | advance 1 | 7.5 | 7.5 | 0 |  |
| 14 | 11→11 | uplink [drive 291.7° 4.63 m, sample, drive 208.4° 5 m, sample] | 7.5 | 9 | -1.5 |  |
| 15 | 11→12 | advance 1 | 9 | 9 | 0 |  |
| 16 | 12→14 | advance 2 | 9 | 9 | 0 |  |
| 17 | 14→16 | advance 2 | 9 | 9 | 0 | DISCOVERY_MISSED |
| 18 | 16→16 | uplink [drive 67° 5 m, drive 67° 2.63 m, sample] | 9 | 9 | 0 |  |
| 19 | 16→18 | advance 2 | 9 | 9 | 0 |  |
| 20 | 18→19 | advance 1 | 9 | 9 | 0 |  |
| 21 | 19→19 | uplink [drive 117.9° 4.46 m, sample] | 9 | 9.5 | -0.5 | LATE_SAMPLE |
| 22 | 19→21 | advance 2 | 9.5 | 9.5 | 0 |  |
| 23 | 21→26 | advance 5 | 9.5 | 9.5 | 0 |  |
| 24 | 26→29 | advance 3 | 9.5 | 9.5 | 0 |  |
| 25 | 29→32 | advance 3 | 9.5 | 9.5 | 0 |  |
| 26 | 32→32 | uplink [drive 315.1° 5 m, drive 315.1° 1.5 m] | 9.5 | 9.5 | 0 |  |
| 27 | 32→37 | advance 5 | 9.5 | 9.5 | 0 |  |
| 28 | 37→42 | advance 5 | 9.5 | 9.5 | 0 |  |
| 29 | 42→43 | advance 1 | 9.5 | 9.5 | 0 |  |
| 30 | 43→43 | uplink [drive 11.5° 0.4 m] | 9.5 | 9.5 | 0 |  |
| 31 | 43→48 | advance 5 | 9.5 | 9.5 | 0 |  |
| 32 | 48→50 | advance 2 | 9.5 | 9.5 | 0 |  |

*Reference before/after*: the score if the reference took over just before or just after this call, knowing only what the agent knew then (delivered telemetry, rules, map, its own acknowledgements). *Points lost* = before − after; the column plus the stop loss adds up to the gap.
