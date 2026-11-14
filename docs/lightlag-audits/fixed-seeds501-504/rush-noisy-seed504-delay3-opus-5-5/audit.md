# Decision audit: rush-noisy-seed504-delay3-opus-5-5

- Model: anthropic/claude-opus-5-5
- Profile `rush_noisy`, seed 504, delay 3 ticks, horizon 50
- Agent: **0** of 10 (reward 0.000, reward.txt 0.000)
- Reference (`kf_mpc`) from the start: **7** (reward 0.700)
- Gap: 7 points = 0.700 reward. Decisions account for 7, stopping early for 0.
- Rebuild reproduces the saved run tick for tick: **yes**

## Main mistakes

### 1. call 21, uplink [drive 91.1° 5 m, drive 91.1° 3.1 m, sample] at tick 25: −6 points (−0.600 reward)

- **PLAN_WORSE_THAN_REFERENCE**: from the same information the reference scored 6 instead of 0. Legal and on time, but the reference's plan from the same information scored more.
  - Information the agent had: telemetry packet for tick 22, delivered at tick 25 (position [19.67, 15.87], battery 40.8)
- Reference instead: send nothing more; finish home, score 6
- Agent's own words: none recorded (trajectory step 17 holds the tool call but no message or reasoning text)

### 2. call 4, uplink [drive 95.3° 5 m, drive 95.3° 4.1 m, sample] at tick 0: −2.75 points (−0.275 reward)

- **PLAN_WORSE_THAN_REFERENCE**: from the same information the reference scored 7 instead of 4.25. Legal and on time, but the reference's plan from the same information scored more.
  - Information the agent had: telemetry packet for tick 0, delivered at tick 0 (position [20.0, 20.0], battery 100.0)
- Reference instead: at tick 3 uplink [drive 155.3° 3.11 m, drive 155.3° 3.11 m, sample]; then sample t2 (tick 6), t5 (tick 9), t3 (tick 12), t4 (tick 15), t1 (tick 19); finish home, score 7
- Agent's own words: none recorded (trajectory step 4 holds the tool call but no message or reasoning text)

### 3. call 7, advance 2 at tick 7: −1.75 points (−0.175 reward)

- **QUEUE_RAN_DRY**: queue ends at tick 9; waiting until 9 means the next command cannot run before tick 13 (2 more idle ticks). Advanced instead of queuing the next leg; the queue emptied before new commands could arrive.
  - Information the agent had: telemetry packet for tick 4, delivered at tick 7 (position [23.05, 16.51], battery 93.0); rules(): first_execution_tick
- Reference instead: at tick 7 uplink [drive 175.5° 3.83 m, drive 175.5° 3.83 m, sample]; then sample t4 (tick 9), t3 (tick 13), t1 (tick 17), t5 (tick 20); finish home, score 7
- Agent's own words: none recorded (trajectory step 7 holds the tool call but no message or reasoning text)

## Where the agent did better than the reference

- call 6, advance 2 at tick 5: +2.75 points (the reference taking over before this call would have scored 4.25, after it 7)
- call 13, advance 2 at tick 15: +1 points (the reference taking over before this call would have scored 4.25, after it 5.25)
- call 14, uplink [drive 316.5° 0.92 m, sample, drive 244.6° 5 m, drive 244.6° 0.55 m, sample] at tick 17: +0.75 points (the reference taking over before this call would have scored 5.25, after it 6)

## Infrastructure (kept apart from reasoning)

None found: every agent call reached the simulator, Harbor recorded no exception, the rebuild matches the run and reward.txt matches the evaluator.

## Other reasoning findings (no points lost against the reference)

- call 8: **STALE_AIM**: aimed at t1 from the position in packet tick 6, ignoring 3 commands in transit
- call 8: **SAMPLE_MISSED**: sample command 9 at tick 15 failed (stale_aim)

## Episode outcome

- **DEAD**: the rover died
- **TARGETS_LEFT**: never sampled: t3
- superlog labels unavailable here (ModuleNotFoundError: No module named 'numpy')

## Every decision

| call | tick | what the agent did | reference before | reference after | points lost | tags |
|---:|---|---|---:|---:|---:|---|
| 3 | 0→0 | uplink [drive 309.1° 5 m, drive 309.1° 2.95 m, sample] | 7 | 7 | 0 |  |
| 4 | 0→0 | uplink [drive 95.3° 5 m, drive 95.3° 4.1 m, sample] | 7 | 4.25 | 2.75 | PLAN_WORSE_THAN_REFERENCE |
| 5 | 0→5 | advance 5 | 4.25 | 4.25 | 0 |  |
| 6 | 5→7 | advance 2 | 4.25 | 7 | -2.75 |  |
| 7 | 7→9 | advance 2 | 7 | 5.25 | 1.75 | QUEUE_RAN_DRY |
| 8 | 9→9 | uplink [drive 175.8° 5 m, drive 175.8° 2.65 m, sample] | 5.25 | 5.25 | 0 | SAMPLE_MISSED, STALE_AIM |
| 9 | 9→12 | advance 3 | 5.25 | 5.25 | 0 |  |
| 10 | 12→12 | uplink [drive 289.8° 5 m, drive 289.8° 2.55 m, sample] | 5.25 | 4.25 | 1 | SAMPLE_MISSED |
| 11 | 12→15 | advance 3 | 4.25 | 4.25 | 0 |  |
| 13 | 15→17 | advance 2 | 4.25 | 5.25 | -1 |  |
| 14 | 17→17 | uplink [drive 316.5° 0.92 m, sample, drive 244.6° 5 m, drive 244.6° 0.55 m, sample] | 5.25 | 6 | -0.75 |  |
| 15 | 17→19 | advance 2 | 6 | 6 | 0 |  |
| 16 | 19→21 | advance 2 | 6 | 6 | 0 |  |
| 18 | 21→21 | uplink [drive 73° 5 m, drive 73° 3.95 m] | 6 | 6 | 0 |  |
| 19 | 21→23 | advance 2 | 6 | 6 | 0 |  |
| 20 | 23→25 | advance 2 | 6 | 6 | 0 |  |
| 21 | 25→25 | uplink [drive 91.1° 5 m, drive 91.1° 3.1 m, sample] | 6 | 0 | 6 | PLAN_WORSE_THAN_REFERENCE |
| 22 | 25→27 | advance 2 | 0 | 0 | 0 |  |
| 23 | 27→32 | advance 5 | 0 | 0 | 0 |  |
| 24 | 32→37 | advance 5 | 0 | 0 | 0 |  |
| 25 | 37→42 | advance 5 | 0 | 0 | 0 |  |
| 26 | 42→47 | advance 5 | 0 | 0 | 0 |  |
| 27 | 47→50 | advance 5 | 0 | 0 | 0 |  |

*Reference before/after*: the score if the reference took over just before or just after this call, knowing only what the agent knew then (delivered telemetry, rules, map, its own acknowledgements). *Points lost* = before − after; the column plus the stop loss adds up to the gap.
