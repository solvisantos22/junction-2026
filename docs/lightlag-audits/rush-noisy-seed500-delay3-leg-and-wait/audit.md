# Decision audit: rush-noisy-seed500-delay3-leg-and-wait

- Model: scripted (no agent trajectory)
- Profile `rush_noisy`, seed 500, delay 3 ticks, horizon 50
- Agent: **1.875** of 7 (reward 0.268, reward.txt 0.268)
- Reference (`kf_mpc`) from the start: **7** (reward 1.000)
- Gap: 5.125 points = 0.732 reward. Decisions account for 5.125, stopping early for 0.
- Rebuild reproduces the saved run tick for tick: **yes**

## Main mistakes

### 1. call 48, advance 1 at tick 38: −1.875 points (−0.268 reward)

- **QUEUE_RAN_DRY**: queue ends at tick 41; waiting until 39 means the next command cannot run before tick 43 (1 more idle ticks). Advanced instead of queuing the next leg; the queue emptied before new commands could arrive.
  - Information the agent had: telemetry packet for tick 35, delivered at tick 38 (position [21.09, 17.25], battery 46.8); rules(): first_execution_tick
- Reference instead: at tick 38 uplink [drive 357° 1.68 m, drive 32.4° 2.25 m]; then sample t2 (tick 41, late); finish home, score 3.75

### 2. call 53, advance 1 at tick 43: −1.875 points (−0.268 reward)

- **WAITED_WITH_EMPTY_QUEUE**: advanced 43->44 with nothing queued (last command ran at tick 41). Advanced the clock with nothing queued, so the rover stood idle.
  - Information the agent had: telemetry packet for tick 40, delivered at tick 43 (position [16.98, 18.52], battery 39.0); rules(): first_execution_tick
- Reference instead: at tick 43 uplink [drive 0.1° 1.42 m, drive 31.8° 2.26 m]; finish home, score 3.75

### 3. call 12, advance 1 at tick 7: −1.5 points (−0.214 reward)

- **WAITED_WITH_EMPTY_QUEUE**: advanced 7->8 with nothing queued (last command ran at tick 6). Advanced the clock with nothing queued, so the rover stood idle.
  - Information the agent had: telemetry packet for tick 4, delivered at tick 7 (position [20.66, 22.44], battery 95.5); rules(): first_execution_tick
- Reference instead: at tick 7 uplink [drive 248.7° 3.33 m, drive 248.7° 3.33 m, drive 161.2° 1.75 m, sample]; then sample t2 (tick 14), t4 (tick 17), d1 (tick 20), t5 (tick 22), t3 (tick 24); finish home, score 7

## Where the agent did better than the reference

- call 13, advance 1 at tick 8: +0.75 points (the reference taking over before this call would have scored 5.5, after it 6.25)
- call 34, advance 1 at tick 26: +0.25 points (the reference taking over before this call would have scored 3.75, after it 4)
- call 50, advance 1 at tick 40: +1.875 points (the reference taking over before this call would have scored 1.875, after it 3.75)

## Infrastructure (kept apart from reasoning)

None found: every agent call reached the simulator, Harbor recorded no exception, the rebuild matches the run and reward.txt matches the evaluator.

## Other reasoning findings (no points lost against the reference)

- call 19: **DISCOVERY_MISSED**: d1 (value 2, deadline tick 21) arrived in the packet for tick 9 at tick 12; sampled late
- call 35: **LATE_SAMPLE**: d1 sampled at tick 32, deadline tick 21
- call 44: **LATE_SAMPLE**: t2 sampled at tick 41, deadline tick 14

## Episode outcome

- **NOT_HOME**: alive but away from base at the horizon
- **TARGETS_LEFT**: never sampled: t4
- superlog labels (`lightlag_dynamic/manh_controllers/superlog.py`): NOT_HOME, LATE_SAMPLE, SKIPPED_WITH_ENERGY; share 0.268, 5 samples taken, 0 failed, 2 late, battery at the end 24.7

## Every decision

| call | tick | what the agent did | reference before | reference after | points lost | tags |
|---:|---|---|---:|---:|---:|---|
| 4 | 0→0 | uplink [drive 83.6° 2.52 m, drive 83.6° 2.52 m, sample] | 7 | 7 | 0 |  |
| 5 | 0→1 | advance 1 | 7 | 7 | 0 |  |
| 6 | 1→2 | advance 1 | 7 | 7 | 0 |  |
| 7 | 2→3 | advance 1 | 7 | 7 | 0 |  |
| 8 | 3→4 | advance 1 | 7 | 7 | 0 |  |
| 9 | 4→5 | advance 1 | 7 | 7 | 0 |  |
| 10 | 5→6 | advance 1 | 7 | 7 | 0 |  |
| 11 | 6→7 | advance 1 | 7 | 7 | 0 |  |
| 12 | 7→8 | advance 1 | 7 | 5.5 | 1.5 | WAITED_WITH_EMPTY_QUEUE |
| 13 | 8→9 | advance 1 | 5.5 | 6.25 | -0.75 |  |
| 14 | 9→9 | uplink [drive 290.1° 3.42 m, drive 290.1° 3.42 m, drive 290.1° 3.42 m, sample] | 6.25 | 5.5 | 0.75 | PLAN_WORSE_THAN_REFERENCE |
| 15 | 9→10 | advance 1 | 5.5 | 5.5 | 0 |  |
| 16 | 10→11 | advance 1 | 5.5 | 5.5 | 0 |  |
| 17 | 11→12 | advance 1 | 5.5 | 5.5 | 0 |  |
| 19 | 12→13 | advance 1 | 5.5 | 5.5 | 0 | DISCOVERY_MISSED |
| 20 | 13→14 | advance 1 | 5.5 | 5.5 | 0 |  |
| 21 | 14→15 | advance 1 | 5.5 | 5.5 | 0 |  |
| 22 | 15→16 | advance 1 | 5.5 | 5.5 | 0 |  |
| 23 | 16→17 | advance 1 | 5.5 | 4 | 1.5 | WAITED_WITH_EMPTY_QUEUE |
| 24 | 17→18 | advance 1 | 4 | 4 | 0 |  |
| 25 | 18→19 | advance 1 | 4 | 4 | 0 |  |
| 26 | 19→19 | uplink [drive 89.9° 4.24 m, sample] | 4 | 4 | 0 |  |
| 27 | 19→20 | advance 1 | 4 | 4 | 0 |  |
| 28 | 20→21 | advance 1 | 4 | 4 | 0 |  |
| 29 | 21→22 | advance 1 | 4 | 4 | 0 |  |
| 30 | 22→23 | advance 1 | 4 | 4 | 0 |  |
| 31 | 23→24 | advance 1 | 4 | 4 | 0 |  |
| 32 | 24→25 | advance 1 | 4 | 4 | 0 |  |
| 33 | 25→26 | advance 1 | 4 | 3.75 | 0.25 | WAITED_WITH_EMPTY_QUEUE |
| 34 | 26→27 | advance 1 | 3.75 | 4 | -0.25 |  |
| 35 | 27→27 | uplink [drive 222.9° 4.17 m, sample] | 4 | 4 | 0 | LATE_SAMPLE |
| 36 | 27→28 | advance 1 | 4 | 4 | 0 |  |
| 37 | 28→29 | advance 1 | 4 | 4 | 0 |  |
| 38 | 29→30 | advance 1 | 4 | 4 | 0 |  |
| 39 | 30→31 | advance 1 | 4 | 4 | 0 |  |
| 40 | 31→32 | advance 1 | 4 | 4 | 0 |  |
| 41 | 32→33 | advance 1 | 4 | 3.75 | 0.25 | WAITED_WITH_EMPTY_QUEUE |
| 42 | 33→34 | advance 1 | 3.75 | 3.75 | 0 |  |
| 43 | 34→35 | advance 1 | 3.75 | 3.75 | 0 |  |
| 44 | 35→35 | uplink [drive 156.8° 2.54 m, drive 156.8° 2.54 m, sample] | 3.75 | 3.75 | 0 | LATE_SAMPLE |
| 45 | 35→36 | advance 1 | 3.75 | 3.75 | 0 |  |
| 46 | 36→37 | advance 1 | 3.75 | 3.75 | 0 |  |
| 47 | 37→38 | advance 1 | 3.75 | 3.75 | 0 |  |
| 48 | 38→39 | advance 1 | 3.75 | 1.875 | 1.875 | QUEUE_RAN_DRY |
| 49 | 39→40 | advance 1 | 1.875 | 1.875 | 0 |  |
| 50 | 40→41 | advance 1 | 1.875 | 3.75 | -1.875 |  |
| 51 | 41→42 | advance 1 | 3.75 | 3.75 | 0 |  |
| 52 | 42→43 | advance 1 | 3.75 | 3.75 | 0 |  |
| 53 | 43→44 | advance 1 | 3.75 | 1.875 | 1.875 | WAITED_WITH_EMPTY_QUEUE |
| 54 | 44→44 | uplink [drive 0.9° 1.38 m, drive 31.8° 2.4 m] | 1.875 | 1.875 | 0 |  |
| 55 | 44→45 | advance 1 | 1.875 | 1.875 | 0 |  |
| 56 | 45→46 | advance 1 | 1.875 | 1.875 | 0 |  |
| 57 | 46→47 | advance 1 | 1.875 | 1.875 | 0 |  |
| 58 | 47→48 | advance 1 | 1.875 | 1.875 | 0 |  |
| 59 | 48→49 | advance 1 | 1.875 | 1.875 | 0 |  |
| 60 | 49→50 | advance 1 | 1.875 | 1.875 | 0 |  |

*Reference before/after*: the score if the reference took over just before or just after this call, knowing only what the agent knew then (delivered telemetry, rules, map, its own acknowledgements). *Points lost* = before − after; the column plus the stop loss adds up to the gap.
