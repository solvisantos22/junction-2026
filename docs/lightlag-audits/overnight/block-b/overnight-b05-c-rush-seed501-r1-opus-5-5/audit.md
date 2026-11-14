# Decision audit: overnight-b05-c-rush-seed501-r1-opus-5-5

- Model: anthropic/claude-opus-5-5
- Profile `rush`, seed 501, delay 3 ticks, horizon 50
- Agent: **0** of 12 (reward 0.000, reward.txt 0.000)
- Reference (`kf_mpc`) from the start: **10** (reward 0.833)
- Gap: 10 points = 0.833 reward. Decisions account for 10, stopping early for 0.
- Rebuild reproduces the saved run tick for tick: **yes**

## Main mistakes

### 1. call 12, uplink [drive -105° 3.5 m, sample, drive 119.6° 5 m] at tick 16: −8.5 points (−0.708 reward)

- **STALE_AIM**: aimed at t2 from the position in packet tick 13, ignoring 6 commands in transit. Aimed from the last delivered position, ignoring drives still in transit.
  - Information the agent had: telemetry packet for tick 13, delivered at tick 16 (position [17.84, 24.94], battery 54.0); acknowledgements for commands still in transit, execute ticks 14, 15, 16, 17, 18, 19; rules(): first_execution_tick / telemetry_arrival_tick
- **LATE_SAMPLE**: d2 sampled at tick 21, deadline tick 18. A target was sampled after its published deadline, for reduced value.
  - Information the agent had: acknowledgement of call 12: execute tick [21]; map target d2 (deadline tick 18, value 2); map(): targets[d2].deadline_tick
- **DISCOVERY_MISSED**: d1 (value 2, deadline tick 21) arrived in the packet for tick 11 at tick 14; sampled late. A discovered target arrived in telemetry and was never collected (or only late).
  - Information the agent had: telemetry packet for tick 11, delivered at tick 14; map target d1 (deadline tick 21, value 2)
- Reference instead: at tick 16 uplink [drive 254.3° 3.4 m, sample]; then sample t1 (tick 17), d2 (tick 21, late); finish home, score 8.5
- Agent's own words: none recorded (trajectory step 17 holds the tool call but no message or reasoning text)

### 2. call 10, uplink [drive 39.2° 1.06 m, sample, drive -105.2° 5 m, drive -105.2° 5 m] at tick 12: −1.5 points (−0.125 reward)

- **STALE_AIM**: aimed at t4 from the position in packet tick 9, ignoring 6 commands in transit. Aimed from the last delivered position, ignoring drives still in transit.
  - Information the agent had: telemetry packet for tick 9, delivered at tick 12 (position [14.67, 12.91], battery 71.9); acknowledgements for commands still in transit, execute ticks 10, 11, 12, 13, 14, 15; rules(): first_execution_tick / telemetry_arrival_tick
- Reference instead: at tick 12 uplink [drive 36.7° 0.97 m, sample]; then sample t5 (tick 14), t1 (tick 17), d1 (tick 20); finish home, score 10
- Agent's own words: none recorded (trajectory step 14 holds the tool call but no message or reasoning text)

### 3. call 7, uplink [drive 72.4° 2.82 m, sample, drive 79.3° 5 m, sample, drive 36.6° 5 m] at tick 7: −1 points (−0.083 reward)

- **PLAN_WORSE_THAN_REFERENCE**: from the same information the reference scored 11 instead of 10. Legal and on time, but the reference's plan from the same information scored more.
  - Information the agent had: telemetry packet for tick 4, delivered at tick 7 (position [24.9, 19.78], battery 93.0)
- Reference instead: at tick 7 uplink [drive 72.4° 2.82 m, sample]; then sample t4 (tick 9), t2 (tick 12), d2 (tick 14), t5 (tick 17), d1 (tick 19); finish home, score 11
- Agent's own words: none recorded (trajectory step 10 holds the tool call but no message or reasoning text)

## Where the agent did better than the reference

- call 3, uplink [drive -2.5° 5 m, sample, drive -146.1° 5 m, drive -146.1° 5 m, drive -146.1° 2.64 m] at tick 0: +1 points (the reference taking over before this call would have scored 10, after it 11)

## Infrastructure (kept apart from reasoning)

None found: every agent call reached the simulator, Harbor recorded no exception, the rebuild matches the run and reward.txt matches the evaluator.

## Other reasoning findings (no points lost against the reference)

- call 9: **DISCOVERY_MISSED**: d2 (value 2, deadline tick 18) arrived in the packet for tick 6 at tick 9; sampled late
- call 14: **LATE_SAMPLE**: d1 sampled at tick 25, deadline tick 21

## Episode outcome

- **DEAD**: the rover died
- superlog labels unavailable here (ModuleNotFoundError: No module named 'numpy')

## Every decision

| call | tick | what the agent did | reference before | reference after | points lost | tags |
|---:|---|---|---:|---:|---:|---|
| 3 | 0→0 | uplink [drive -2.5° 5 m, sample, drive -146.1° 5 m, drive -146.1° 5 m, drive -146.1° 2.64 m] | 10 | 11 | -1 |  |
| 4 | 0→0 | uplink [sample, drive 72.8° 5 m] | 11 | 11 | 0 |  |
| 5 | 0→5 | advance 5 | 11 | 11 | 0 |  |
| 6 | 5→7 | advance 2 | 11 | 11 | 0 |  |
| 7 | 7→7 | uplink [drive 72.4° 2.82 m, sample, drive 79.3° 5 m, sample, drive 36.6° 5 m] | 11 | 10 | 1 | PLAN_WORSE_THAN_REFERENCE |
| 8 | 7→10 | advance 3 | 10 | 10 | 0 |  |
| 9 | 10→12 | advance 2 | 10 | 10 | 0 | DISCOVERY_MISSED |
| 10 | 12→12 | uplink [drive 39.2° 1.06 m, sample, drive -105.2° 5 m, drive -105.2° 5 m] | 10 | 8.5 | 1.5 | STALE_AIM |
| 11 | 12→16 | advance 4 | 8.5 | 8.5 | 0 |  |
| 12 | 16→16 | uplink [drive -105° 3.5 m, sample, drive 119.6° 5 m] | 8.5 | 0 | 8.5 | DISCOVERY_MISSED, LATE_SAMPLE, STALE_AIM |
| 13 | 16→20 | advance 4 | 0 | 0 | 0 |  |
| 14 | 20→20 | uplink [drive 119.8° 4.6 m, sample, drive -35.6° 5 m] | 0 | 0 | 0 | LATE_SAMPLE |
| 15 | 20→24 | advance 4 | 0 | 0 | 0 |  |
| 16 | 24→29 | advance 5 | 0 | 0 | 0 |  |
| 17 | 29→34 | advance 5 | 0 | 0 | 0 |  |
| 18 | 34→39 | advance 5 | 0 | 0 | 0 |  |
| 19 | 39→44 | advance 5 | 0 | 0 | 0 |  |
| 20 | 44→49 | advance 5 | 0 | 0 | 0 |  |
| 21 | 49→50 | advance 1 | 0 | 0 | 0 |  |

*Reference before/after*: the score if the reference took over just before or just after this call, knowing only what the agent knew then (delivered telemetry, rules, map, its own acknowledgements). *Points lost* = before − after; the column plus the stop loss adds up to the gap.
