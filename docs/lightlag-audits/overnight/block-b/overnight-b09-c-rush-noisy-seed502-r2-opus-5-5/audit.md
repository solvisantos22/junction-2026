# Decision audit: overnight-b09-c-rush-noisy-seed502-r2-opus-5-5

- Model: anthropic/claude-opus-5-5
- Profile `rush_noisy`, seed 502, delay 3 ticks, horizon 50
- Agent: **6** of 13 (reward 0.462, reward.txt 0.462)
- Reference (`kf_mpc`) from the start: **10** (reward 0.769)
- Gap: 4 points = 0.308 reward. Decisions account for 4, stopping early for 0.
- Rebuild reproduces the saved run tick for tick: **yes**

## Main mistakes

### 1. call 7, uplink [drive 5.6° 2.2 m, sample] at tick 7: −2.25 points (−0.173 reward)

- **SAMPLE_MISSED**: sample command 8 at tick 12 failed (slip_not_corrected). A sample command found no unsampled target in range (or not enough battery).
  - Information the agent had: telemetry packet for tick 4, delivered at tick 7 (position [18.96, 24.26], battery 93.7); acknowledgement of call 7: execute tick [12]; packet for tick 11 (delivered tick 14): wheel 2.2 m vs visual 1.671 m on sand; rules(): slip_ranges / slip_model
- Reference instead: at tick 7 uplink [drive 268.8° 3.53 m, drive 268.8° 3.53 m]; then sample d2 (tick 21), t2 (tick 24); finish home, score 9
- Agent's own words: none recorded (trajectory step 7 holds the tool call but no message or reasoning text)

### 2. call 5, uplink [drive 5.6° 5 m, drive 5.6° 5 m] at tick 4: −1 points (−0.077 reward)

- **PLAN_WORSE_THAN_REFERENCE**: from the same information the reference scored 10 instead of 9. Legal and on time, but the reference's plan from the same information scored more.
  - Information the agent had: telemetry packet for tick 1, delivered at tick 4 (position [20.62, 20.24], battery 99.5)
- Reference instead: at tick 4 uplink [drive 257.9° 1.68 m, drive 272.1° 4.61 m, drive 272.1° 4.61 m]; then sample t1 (tick 5), t5 (tick 7), t3 (tick 17), d2 (tick 20), t2 (tick 23); finish home, score 10
- Agent's own words: none recorded (trajectory step 5 holds the tool call but no message or reasoning text)

### 3. call 10, uplink [drive 216.8° 2.28 m, sample] at tick 11: −1 points (−0.077 reward)

- **SAMPLE_MISSED**: sample command 10 at tick 16 failed (slip_not_corrected). A sample command found no unsampled target in range (or not enough battery).
  - Information the agent had: telemetry packet for tick 8, delivered at tick 11 (position [20.08, 27.92], battery 68.3); acknowledgement of call 10: execute tick [16]; packet for tick 15 (delivered tick 18): wheel 2.28 m vs visual 1.71 m on sand; rules(): slip_ranges / slip_model
- Reference instead: at tick 11 uplink [drive 203.6° 1.74 m, sample]; then sample t4 (tick 16), t2 (tick 19); finish home, score 7
- Agent's own words: none recorded (trajectory step 10 holds the tool call but no message or reasoning text)

## Where the agent did better than the reference

- call 9, advance 2 at tick 9: +0.25 points (the reference taking over before this call would have scored 6.75, after it 7)

## Infrastructure (kept apart from reasoning)

None found: every agent call reached the simulator, Harbor recorded no exception, the rebuild matches the run and reward.txt matches the evaluator.

## Other reasoning findings (no points lost against the reference)

- call 13: **DISCOVERY_MISSED**: d2 (value 3, deadline tick 22) arrived in the packet for tick 10 at tick 13; never sampled
- call 19: **DISCOVERY_MISSED**: d1 (value 2, deadline tick 28) arrived in the packet for tick 21 at tick 24; never sampled

## Episode outcome

- **TARGETS_LEFT**: never sampled: d1, d2, t3, t4
- superlog labels unavailable here (ModuleNotFoundError: No module named 'numpy')

## Every decision

| call | tick | what the agent did | reference before | reference after | points lost | tags |
|---:|---|---|---:|---:|---:|---|
| 3 | 0→0 | uplink [drive 101.4° 4.29 m, sample, drive 139.5° 4.85 m, sample] | 10 | 10 | 0 |  |
| 4 | 0→4 | advance 4 | 10 | 10 | 0 |  |
| 5 | 4→4 | uplink [drive 5.6° 5 m, drive 5.6° 5 m] | 10 | 9 | 1 | PLAN_WORSE_THAN_REFERENCE |
| 6 | 4→7 | advance 3 | 9 | 9 | 0 |  |
| 7 | 7→7 | uplink [drive 5.6° 2.2 m, sample] | 9 | 6.75 | 2.25 | SAMPLE_MISSED |
| 8 | 7→9 | advance 2 | 6.75 | 6.75 | 0 |  |
| 9 | 9→11 | advance 2 | 6.75 | 7 | -0.25 |  |
| 10 | 11→11 | uplink [drive 216.8° 2.28 m, sample] | 7 | 6 | 1 | SAMPLE_MISSED |
| 11 | 11→12 | advance 1 | 6 | 6 | 0 |  |
| 12 | 12→13 | advance 1 | 6 | 6 | 0 |  |
| 13 | 13→14 | advance 1 | 6 | 6 | 0 | DISCOVERY_MISSED |
| 14 | 14→14 | uplink [drive 253° 5 m] | 6 | 6 | 0 |  |
| 15 | 14→19 | advance 5 | 6 | 6 | 0 |  |
| 16 | 19→21 | advance 2 | 6 | 6 | 0 |  |
| 17 | 21→21 | uplink [drive 266.5° 1 m, sample] | 6 | 6 | 0 |  |
| 18 | 21→25 | advance 4 | 6 | 6 | 0 |  |
| 19 | 25→25 | uplink [drive 210.1° 3.12 m] | 6 | 6 | 0 | DISCOVERY_MISSED |
| 20 | 25→30 | advance 5 | 6 | 6 | 0 |  |
| 21 | 30→35 | advance 5 | 6 | 6 | 0 |  |
| 22 | 35→40 | advance 5 | 6 | 6 | 0 |  |
| 23 | 40→45 | advance 5 | 6 | 6 | 0 |  |
| 24 | 45→50 | advance 5 | 6 | 6 | 0 |  |

*Reference before/after*: the score if the reference took over just before or just after this call, knowing only what the agent knew then (delivered telemetry, rules, map, its own acknowledgements). *Points lost* = before − after; the column plus the stop loss adds up to the gap.
