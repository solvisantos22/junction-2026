# Decision audit: rush-noisy-seed500-delay3-open-loop

- Model: scripted (no agent trajectory)
- Profile `rush_noisy`, seed 500, delay 3 ticks, horizon 50
- Agent: **4** of 7 (reward 0.571, reward.txt 0.571)
- Reference (`kf_mpc`) from the start: **7** (reward 1.000)
- Gap: 3 points = 0.429 reward. Decisions account for 3, stopping early for 0.
- Rebuild reproduces the saved run tick for tick: **yes**

## Main mistakes

### 1. call 5, uplink [sample, drive 270.7° 3.61 m, sample, drive 154.8° 4.3 m, drive 154.8° 4.3 m] at tick 0: −1.75 points (−0.250 reward)

- **PLAN_WORSE_THAN_REFERENCE**: from the same information the reference scored 7 instead of 5.25. Legal and on time, but the reference's plan from the same information scored more.
  - Information the agent had: telemetry packet for tick 0, delivered at tick 0 (position [20.0, 20.0], battery 100.0)
- Reference instead: at tick 5 uplink [sample]; then sample t1 (tick 6), t3 (tick 9), t5 (tick 11), t2 (tick 14), t4 (tick 17), d1 (tick 20); finish home, score 7

### 2. call 10, advance 5 at tick 15: −1.5 points (−0.214 reward)

- **WAITED_WITH_EMPTY_QUEUE**: advanced 15->20 with nothing queued (last command ran at tick 15). Advanced the clock with nothing queued, so the rover stood idle.
  - Information the agent had: telemetry packet for tick 12, delivered at tick 15 (position [20.8, 17.59], battery 65.3); rules(): first_execution_tick
- **DISCOVERY_MISSED**: d1 (value 2, deadline tick 21) arrived in the packet for tick 9 at tick 12; never sampled. A discovered target arrived in telemetry and was never collected (or only late).
  - Information the agent had: telemetry packet for tick 9, delivered at tick 12; map target d1 (deadline tick 21, value 2)
- Reference instead: at tick 15 uplink [drive 297.9° 3.27 m, sample]; then sample d1 (tick 20), t4 (tick 23, late); finish home, score 6.25

### 3. call 14, advance 5 at tick 35: −0.5 points (−0.071 reward)

- **WAITED_WITH_EMPTY_QUEUE**: advanced 35->40 with nothing queued (last command ran at tick 15). Advanced the clock with nothing queued, so the rover stood idle.
  - Information the agent had: telemetry packet for tick 32, delivered at tick 35 (position [19.97, 20.65], battery 41.6); rules(): first_execution_tick
- Reference instead: at tick 35 uplink [drive 295.2° 3.36 m, sample]; then sample d1 (tick 40, late); finish home, score 4.5

## Where the agent did better than the reference

- call 6, uplink [sample, drive 13.4° 3.65 m] at tick 0: +1 points (the reference taking over before this call would have scored 5.25, after it 6.25)

## Infrastructure (kept apart from reasoning)

None found: every agent call reached the simulator, Harbor recorded no exception, the rebuild matches the run and reward.txt matches the evaluator.

## Episode outcome

- **TARGETS_LEFT**: never sampled: d1, t4
- superlog labels (`lightlag_dynamic/manh_controllers/superlog.py`): DISCOVERY_MISSED, SKIPPED_WITH_ENERGY; share 0.571, 4 samples taken, 0 failed, 0 late, battery at the end 32.6

## Every decision

| call | tick | what the agent did | reference before | reference after | points lost | tags |
|---:|---|---|---:|---:|---:|---|
| 4 | 0→0 | uplink [drive 83.6° 2.52 m, drive 83.6° 2.52 m, sample, drive 303.9° 3.38 m, drive 303.9° 3.38 m] | 7 | 7 | 0 |  |
| 5 | 0→0 | uplink [sample, drive 270.7° 3.61 m, sample, drive 154.8° 4.3 m, drive 154.8° 4.3 m] | 7 | 5.25 | 1.75 | PLAN_WORSE_THAN_REFERENCE |
| 6 | 0→0 | uplink [sample, drive 13.4° 3.65 m] | 5.25 | 6.25 | -1 |  |
| 7 | 0→5 | advance 5 | 6.25 | 6.25 | 0 |  |
| 8 | 5→10 | advance 5 | 6.25 | 6.25 | 0 |  |
| 9 | 10→15 | advance 5 | 6.25 | 6.25 | 0 |  |
| 10 | 15→20 | advance 5 | 6.25 | 4.75 | 1.5 | DISCOVERY_MISSED, WAITED_WITH_EMPTY_QUEUE |
| 11 | 20→25 | advance 5 | 4.75 | 4.75 | 0 |  |
| 12 | 25→30 | advance 5 | 4.75 | 4.75 | 0 |  |
| 13 | 30→35 | advance 5 | 4.75 | 4.5 | 0.25 | WAITED_WITH_EMPTY_QUEUE |
| 14 | 35→40 | advance 5 | 4.5 | 4 | 0.5 | WAITED_WITH_EMPTY_QUEUE |
| 15 | 40→45 | advance 5 | 4 | 4 | 0 |  |
| 16 | 45→50 | advance 5 | 4 | 4 | 0 |  |

*Reference before/after*: the score if the reference took over just before or just after this call, knowing only what the agent knew then (delivered telemetry, rules, map, its own acknowledgements). *Points lost* = before − after; the column plus the stop loss adds up to the gap.
