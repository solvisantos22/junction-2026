# Decision audit: rocks-rush-noisy-seed1026-r2-opus-5-5

- Model: anthropic/claude-opus-5-5
- Profile `rush_noisy`, seed 1026, delay 3 ticks, horizon 50
- Agent: **6.75** of 13 (reward 0.519, reward.txt 0.519)
- Reference (`kf_mpc`) from the start: **10** (reward 0.769)
- Gap: 3.25 points = 0.250 reward. Decisions account for 3.25, stopping early for 0.
- Rebuild reproduces the saved run tick for tick: **yes**

## Main mistakes

### 1. call 4, uplink [sample, drive 90° 4.57 m] at tick 0: −4.25 points (−0.327 reward)

- **PLAN_WORSE_THAN_REFERENCE**: from the same information the reference scored 10 instead of 5.75. Legal and on time, but the reference's plan from the same information scored more.
  - Information the agent had: telemetry packet for tick 0, delivered at tick 0 (position [20.0, 20.0], battery 100.0)
- Reference instead: at tick 5 uplink [sample]; then sample t5 (tick 6), t1 (tick 9), t4 (tick 12), t3 (tick 19), d2 (tick 21); finish home, score 10
- Agent's own words: none recorded (trajectory step 5 holds the tool call but no message or reasoning text)

### 2. call 12, uplink [drive 303.3° 3.64 m, drive 239.3° 5 m, drive 239.3° 1.01 m, sample] at tick 12: −2 points (−0.154 reward)

- **SAFETY_STOP**: drive 13 stopped at tick 17 (hazard); 3 queued commands cleared. A drive hit a hazard or the map edge; the queue behind it was cleared.
  - Information the agent had: map hazard {'x1': 11.71, 'y1': 22.44, 'x2': 14.15, 'y2': 24.58}; rules(): safety_stop
- Reference instead: at tick 13 uplink [drive 204.5° 1.95 m, drive 271.8° 3.38 m, drive 292.9° 4.21 m, sample]; then sample t4 (tick 13), t3 (tick 20), d2 (tick 22, late); finish home, score 7.75
- Agent's own words: none recorded (trajectory step 13 holds the tool call but no message or reasoning text)

## Where the agent did better than the reference

- call 6, advance 3 at tick 5: +2 points (the reference taking over before this call would have scored 5.75, after it 7.75)
- call 18, advance 1 at tick 19: +1 points (the reference taking over before this call would have scored 5.75, after it 6.75)

## Infrastructure (kept apart from reasoning)

None found: every agent call reached the simulator, Harbor recorded no exception, the rebuild matches the run and reward.txt matches the evaluator.

## Other reasoning findings (no points lost against the reference)

- call 10: **SAMPLE_MISSED**: sample command 12 at tick 16 failed (slip_not_corrected)
- call 14: **DISCOVERY_MISSED**: d1 (value 2, deadline tick 17) arrived in the packet for tick 10 at tick 13; never sampled
- call 15: **DISCOVERY_MISSED**: d2 (value 3, deadline tick 21) arrived in the packet for tick 11 at tick 14; sampled late
- call 23: **LATE_SAMPLE**: d2 sampled at tick 37, deadline tick 21

## Episode outcome

- **TARGETS_LEFT**: never sampled: d1, t3
- superlog labels unavailable here (ModuleNotFoundError: No module named 'numpy')

## Every decision

| call | tick | what the agent did | reference before | reference after | points lost | tags |
|---:|---|---|---:|---:|---:|---|
| 3 | 0→0 | uplink [drive 19.5° 5 m, drive 19.5° 2.26 m, sample, drive 171.1° 5 m, drive 171.1° 0.67 m] | 10 | 10 | 0 |  |
| 4 | 0→0 | uplink [sample, drive 90° 4.57 m] | 10 | 5.75 | 4.25 | PLAN_WORSE_THAN_REFERENCE |
| 5 | 0→5 | advance 5 | 5.75 | 5.75 | 0 |  |
| 6 | 5→8 | advance 3 | 5.75 | 7.75 | -2 |  |
| 7 | 8→8 | uplink [drive 150.7° 4.8 m, sample] | 7.75 | 7.75 | 0 |  |
| 8 | 8→9 | advance 1 | 7.75 | 7.75 | 0 |  |
| 9 | 9→10 | advance 1 | 7.75 | 7.75 | 0 |  |
| 10 | 10→10 | uplink [drive 187° 3.5 m, drive 224.8° 3.83 m, sample] | 7.75 | 7.75 | 0 | SAMPLE_MISSED |
| 11 | 10→12 | advance 2 | 7.75 | 7.75 | 0 |  |
| 12 | 12→12 | uplink [drive 303.3° 3.64 m, drive 239.3° 5 m, drive 239.3° 1.01 m, sample] | 7.75 | 5.75 | 2 | SAFETY_STOP |
| 13 | 12→13 | advance 1 | 5.75 | 5.75 | 0 |  |
| 14 | 13→15 | advance 2 | 5.75 | 5.75 | 0 | DISCOVERY_MISSED |
| 15 | 15→16 | advance 1 | 5.75 | 5.75 | 0 | DISCOVERY_MISSED |
| 16 | 16→17 | advance 1 | 5.75 | 5.75 | 0 |  |
| 17 | 17→19 | advance 2 | 5.75 | 5.75 | 0 |  |
| 18 | 19→20 | advance 1 | 5.75 | 6.75 | -1 |  |
| 19 | 20→20 | uplink [drive 90° 1.35 m, sample, drive 345.7° 1.96 m, drive 275.8° 4.6 m] | 6.75 | 6.75 | 0 |  |
| 20 | 20→25 | advance 5 | 6.75 | 6.75 | 0 |  |
| 21 | 25→30 | advance 5 | 6.75 | 6.75 | 0 |  |
| 22 | 30→32 | advance 2 | 6.75 | 6.75 | 0 |  |
| 23 | 32→32 | uplink [drive 300.1° 0.96 m, sample, drive 358.1° 4.05 m] | 6.75 | 6.75 | 0 | LATE_SAMPLE |
| 24 | 32→37 | advance 5 | 6.75 | 6.75 | 0 |  |
| 25 | 37→42 | advance 5 | 6.75 | 6.75 | 0 |  |
| 26 | 42→45 | advance 3 | 6.75 | 6.75 | 0 |  |
| 27 | 45→50 | advance 5 | 6.75 | 6.75 | 0 |  |

*Reference before/after*: the score if the reference took over just before or just after this call, knowing only what the agent knew then (delivered telemetry, rules, map, its own acknowledgements). *Points lost* = before − after; the column plus the stop loss adds up to the gap.
