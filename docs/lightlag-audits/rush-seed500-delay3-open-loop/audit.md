# Decision audit: rush-seed500-delay3-open-loop

- Model: scripted (no agent trajectory)
- Profile `rush`, seed 500, delay 3 ticks, horizon 50
- Agent: **4** of 7 (reward 0.571, reward.txt 0.571)
- Reference (`kf_mpc`) from the start: **7** (reward 1.000)
- Gap: 3 points = 0.429 reward. Decisions account for 3, stopping early for 0.
- Rebuild reproduces the saved run tick for tick: **yes**

## Main mistakes

### 1. call 10, advance 5 at tick 15: −1.5 points (−0.214 reward)

- **WAITED_WITH_EMPTY_QUEUE**: advanced 15->20 with nothing queued (last command ran at tick 15). Advanced the clock with nothing queued, so the rover stood idle.
  - Information the agent had: telemetry packet for tick 12, delivered at tick 15 (position [20.57, 17.69], battery 65.3); rules(): first_execution_tick
- **DISCOVERY_MISSED**: d1 (value 2, deadline tick 21) arrived in the packet for tick 9 at tick 12; never sampled. A discovered target arrived in telemetry and was never collected (or only late).
  - Information the agent had: telemetry packet for tick 9, delivered at tick 12; map target d1 (deadline tick 21, value 2)
- Reference instead: at tick 15 uplink [drive 294.6° 3.36 m, sample]; then sample d1 (tick 20), t4 (tick 23, late); finish home, score 6.25

### 2. call 5, uplink [sample, drive 270.7° 3.61 m, sample, drive 154.8° 4.3 m, drive 154.8° 4.3 m] at tick 0: −0.75 points (−0.107 reward)

- **PLAN_WORSE_THAN_REFERENCE**: from the same information the reference scored 7 instead of 6.25. Legal and on time, but the reference's plan from the same information scored more.
  - Information the agent had: telemetry packet for tick 0, delivered at tick 0 (position [20.0, 20.0], battery 100.0)
- Reference instead: at tick 5 uplink [sample]; then sample t1 (tick 6), t3 (tick 9), t5 (tick 11), t2 (tick 14), t4 (tick 17), d1 (tick 20); finish home, score 7

### 3. call 15, advance 5 at tick 40: −0.75 points (−0.107 reward)

- **WAITED_WITH_EMPTY_QUEUE**: advanced 40->45 with nothing queued (last command ran at tick 15). Advanced the clock with nothing queued, so the rover stood idle.
  - Information the agent had: telemetry packet for tick 37, delivered at tick 40 (position [19.87, 19.9], battery 38.7); rules(): first_execution_tick
- Reference instead: at tick 40 uplink [drive 299.5° 3.35 m, sample]; then sample d1 (tick 45, late), t4 (tick 48, late); finish home, score 4.75

## Infrastructure (kept apart from reasoning)

None found: every agent call reached the simulator, Harbor recorded no exception, the rebuild matches the run and reward.txt matches the evaluator.

## Episode outcome

- **TARGETS_LEFT**: never sampled: d1, t4

## Every decision

| call | tick | what the agent did | reference before | reference after | points lost | tags |
|---:|---|---|---:|---:|---:|---|
| 4 | 0→0 | uplink [drive 83.6° 2.52 m, drive 83.6° 2.52 m, sample, drive 303.9° 3.38 m, drive 303.9° 3.38 m] | 7 | 7 | 0 |  |
| 5 | 0→0 | uplink [sample, drive 270.7° 3.61 m, sample, drive 154.8° 4.3 m, drive 154.8° 4.3 m] | 7 | 6.25 | 0.75 | PLAN_WORSE_THAN_REFERENCE |
| 6 | 0→0 | uplink [sample, drive 13.4° 3.65 m] | 6.25 | 6.25 | 0 |  |
| 7 | 0→5 | advance 5 | 6.25 | 6.25 | 0 |  |
| 8 | 5→10 | advance 5 | 6.25 | 6.25 | 0 |  |
| 9 | 10→15 | advance 5 | 6.25 | 6.25 | 0 |  |
| 10 | 15→20 | advance 5 | 6.25 | 4.75 | 1.5 | DISCOVERY_MISSED, WAITED_WITH_EMPTY_QUEUE |
| 11 | 20→25 | advance 5 | 4.75 | 4.75 | 0 |  |
| 12 | 25→30 | advance 5 | 4.75 | 4.75 | 0 |  |
| 13 | 30→35 | advance 5 | 4.75 | 4.75 | 0 |  |
| 14 | 35→40 | advance 5 | 4.75 | 4.75 | 0 |  |
| 15 | 40→45 | advance 5 | 4.75 | 4 | 0.75 | WAITED_WITH_EMPTY_QUEUE |
| 16 | 45→50 | advance 5 | 4 | 4 | 0 |  |

*Reference before/after*: the score if the reference took over just before or just after this call, knowing only what the agent knew then (delivered telemetry, rules, map, its own acknowledgements). *Points lost* = before − after; the column plus the stop loss adds up to the gap.
