# Decision audit: opencode-opus-5-5-seed7-delay3

- Model: anthropic/claude-opus-5-5
- Profile `core`, seed 7, delay 3 ticks, horizon 80
- Agent: **4** of 4 (reward 1.000, reward.txt 1.000)
- Reference (`team`) from the start: **4** (reward 1.000)
- Gap: 0 points = 0.000 reward. Decisions account for 0, stopping early for 0.
- Rebuild reproduces the saved run tick for tick: **yes**

## Main mistakes

None: the agent matched the reference's score. Some decisions below lost points against the reference's continuation and later decisions won them back; that measures the reference from states it would not have chosen, not an agent mistake.

## Where the agent did better than the reference

- call 13, uplink [drive 3° 2.45 m, sample] at tick 28: +1 points (the reference taking over before this call would have scored 3, after it 4)

## Infrastructure (kept apart from reasoning)

None found: every agent call reached the simulator, Harbor recorded no exception, the rebuild matches the run and reward.txt matches the evaluator.

## Other reasoning findings (no points lost against the reference)

- call 6: **REJECTED_BY_RULES**: call 6 (uplink) was rejected: metres must be in (0, 5.0]

## Episode outcome

- **PERFECT**: scored 4, the reference scored 4 from the start

## Every decision

| call | tick | what the agent did | reference before | reference after | points lost | tags |
|---:|---|---|---:|---:|---:|---|
| 3 | 0→0 | uplink [drive 180° 5 m, drive 180° 1 m, sample] | 4 | 3 | 1 |  |
| 4 | 0→5 | advance 5 | 3 | 3 | 0 |  |
| 5 | 5→9 | advance 4 | 3 | 3 | 0 |  |
| 6 | 9→9 | uplink [drive 54° 5 m, drive 54° 5.25 m, sample] (rejected) | 3 | 3 | 0 | REJECTED_BY_RULES |
| 7 | 9→9 | uplink [drive 54° 5 m, drive 54° 5 m, drive 54° 0.25 m, sample] | 3 | 3 | 0 |  |
| 8 | 9→14 | advance 5 | 3 | 3 | 0 |  |
| 9 | 14→19 | advance 5 | 3 | 3 | 0 |  |
| 10 | 19→19 | uplink [drive 289.2° 5 m, drive 289.2° 3.84 m, drive 0° 1.5 m] | 3 | 3 | 0 |  |
| 11 | 19→24 | advance 5 | 3 | 3 | 0 |  |
| 12 | 24→28 | advance 4 | 3 | 3 | 0 |  |
| 13 | 28→28 | uplink [drive 3° 2.45 m, sample] | 3 | 4 | -1 |  |
| 14 | 28→33 | advance 5 | 4 | 4 | 0 |  |
| 15 | 33→34 | advance 1 | 4 | 4 | 0 |  |
| 16 | 34→36 | advance 2 | 4 | 4 | 0 |  |
| 17 | 36→36 | uplink [drive 180° 3.9 m, drive 180° 3 m] | 4 | 4 | 0 |  |
| 18 | 36→41 | advance 5 | 4 | 4 | 0 |  |
| 19 | 41→44 | advance 3 | 4 | 4 | 0 |  |
| 20 | 44→49 | advance 5 | 4 | 4 | 0 |  |
| 21 | 49→54 | advance 5 | 4 | 4 | 0 |  |
| 22 | 54→59 | advance 5 | 4 | 4 | 0 |  |
| 23 | 59→64 | advance 5 | 4 | 4 | 0 |  |
| 24 | 64→69 | advance 5 | 4 | 4 | 0 |  |
| 25 | 69→74 | advance 5 | 4 | 4 | 0 |  |
| 26 | 74→79 | advance 5 | 4 | 4 | 0 |  |
| 27 | 79→80 | advance 1 | 4 | 4 | 0 |  |

*Reference before/after*: the score if the reference took over just before or just after this call, knowing only what the agent knew then (delivered telemetry, rules, map, its own acknowledgements). *Points lost* = before − after; the column plus the stop loss adds up to the gap.
