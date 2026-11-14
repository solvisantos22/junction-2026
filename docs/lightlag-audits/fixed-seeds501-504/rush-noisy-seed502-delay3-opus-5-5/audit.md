# Decision audit: rush-noisy-seed502-delay3-opus-5-5

- Model: anthropic/claude-opus-5-5
- Profile `rush_noisy`, seed 502, delay 3 ticks, horizon 50
- Agent: **8.25** of 13 (reward 0.635, reward.txt 0.635)
- Reference (`kf_mpc`) from the start: **10** (reward 0.769)
- Gap: 1.75 points = 0.135 reward. Decisions account for 1.75, stopping early for 0.
- Rebuild reproduces the saved run tick for tick: **yes**

## Main mistakes

### 1. call 10, advance 5 at tick 12: −2.25 points (−0.173 reward)

- **QUEUE_RAN_DRY**: queue ends at tick 14; waiting until 17 means the next command cannot run before tick 21 (5 more idle ticks). Advanced instead of queuing the next leg; the queue emptied before new commands could arrive.
  - Information the agent had: telemetry packet for tick 9, delivered at tick 12 (position [16.49, 26.88], battery 77.8); rules(): first_execution_tick
- Reference instead: at tick 12 uplink [sample]; then sample t2 (tick 16), d2 (tick 19), t3 (tick 22); finish home, score 10
- Agent's own words: none recorded (trajectory step 8 holds the tool call but no message or reasoning text)

## Where the agent did better than the reference

- call 11, uplink [drive 96.5° 0.54 m, sample, drive -85.3° 5 m, drive -85.3° 0.76 m, sample] at tick 17: +0.5 points (the reference taking over before this call would have scored 7.75, after it 8.25)

## Infrastructure (kept apart from reasoning)

None found: every agent call reached the simulator, Harbor recorded no exception, the rebuild matches the run and reward.txt matches the evaluator.

## Other reasoning findings (no points lost against the reference)

- call 11: **LATE_SAMPLE**: d2 sampled at tick 25, deadline tick 22
- call 11: **DISCOVERY_MISSED**: d2 (value 3, deadline tick 22) arrived in the packet for tick 10 at tick 13; sampled late
- call 14: **DISCOVERY_MISSED**: d1 (value 2, deadline tick 28) arrived in the packet for tick 21 at tick 24; sampled late
- call 16: **LATE_SAMPLE**: d1 sampled at tick 33, deadline tick 28

## Episode outcome

- **TARGETS_LEFT**: never sampled: t4
- superlog labels unavailable here (ModuleNotFoundError: No module named 'numpy')

## Every decision

| call | tick | what the agent did | reference before | reference after | points lost | tags |
|---:|---|---|---:|---:|---:|---|
| 3 | 0→0 | uplink [drive 101.4° 4.29 m, sample, drive 139.5° 4.85 m] | 10 | 10 | 0 |  |
| 4 | 0→5 | advance 5 | 10 | 10 | 0 |  |
| 5 | 5→5 | uplink [sample] | 10 | 10 | 0 |  |
| 6 | 5→9 | advance 4 | 10 | 10 | 0 |  |
| 8 | 9→9 | uplink [drive -39.6° 5 m, drive -39.6° 4.6 m] | 10 | 10 | 0 |  |
| 9 | 9→12 | advance 3 | 10 | 10 | 0 |  |
| 10 | 12→17 | advance 5 | 10 | 7.75 | 2.25 | QUEUE_RAN_DRY |
| 11 | 17→17 | uplink [drive 96.5° 0.54 m, sample, drive -85.3° 5 m, drive -85.3° 0.76 m, sample] | 7.75 | 8.25 | -0.5 | DISCOVERY_MISSED, LATE_SAMPLE |
| 12 | 17→22 | advance 5 | 8.25 | 8.25 | 0 |  |
| 13 | 22→25 | advance 3 | 8.25 | 8.25 | 0 |  |
| 14 | 25→25 | uplink [drive 173.4° 5 m, drive 173.4° 2.17 m, sample] | 8.25 | 8.25 | 0 | DISCOVERY_MISSED |
| 15 | 25→28 | advance 3 | 8.25 | 8.25 | 0 |  |
| 16 | 28→28 | uplink [drive 140.5° 4.6 m, sample, drive 4.9° 5 m, drive 4.9° 2.47 m] | 8.25 | 8.25 | 0 | LATE_SAMPLE |
| 17 | 28→33 | advance 5 | 8.25 | 8.25 | 0 |  |
| 18 | 33→36 | advance 3 | 8.25 | 8.25 | 0 |  |
| 19 | 36→39 | advance 3 | 8.25 | 8.25 | 0 |  |
| 21 | 39→43 | advance 4 | 8.25 | 8.25 | 0 |  |
| 22 | 43→48 | advance 5 | 8.25 | 8.25 | 0 |  |
| 23 | 48→50 | advance 5 | 8.25 | 8.25 | 0 |  |

*Reference before/after*: the score if the reference took over just before or just after this call, knowing only what the agent knew then (delivered telemetry, rules, map, its own acknowledgements). *Points lost* = before − after; the column plus the stop loss adds up to the gap.
