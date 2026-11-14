# Decision audit: rush-noisy-seed500-delay3-nop

- Model: scripted (no agent trajectory)
- Profile `rush_noisy`, seed 500, delay 3 ticks, horizon 50
- Agent: **0** of 7 (reward 0.000, reward.txt 0.000)
- Reference (`kf_mpc`) from the start: **7** (reward 1.000)
- Gap: 7 points = 1.000 reward. Decisions account for 0, stopping early for 7.
- Rebuild reproduces the saved run tick for tick: **yes**

## Main mistakes

### 1. stopped at tick 0: −7 points (−1.000 reward)

- **STOPPED_EARLY**: stopped at tick 0; the reference would have scored 7 from there, not 0. The agent stopped calling tools with time left that the reference would have used.
- Reference instead: at tick 0 uplink [drive 83.6° 2.52 m, drive 83.6° 2.52 m, sample]; then sample t1 (tick 6), t3 (tick 9), t5 (tick 11), t2 (tick 14), t4 (tick 17), d1 (tick 20); finish home, score 7

## Infrastructure (kept apart from reasoning)

None found: every agent call reached the simulator, Harbor recorded no exception, the rebuild matches the run and reward.txt matches the evaluator.

## Episode outcome

- **NOTHING_SAMPLED**: no sample was collected
- **STOPPED_EARLY**: stopped at tick 0; the reference would have scored 7 from there, not 0
- superlog labels (`lightlag_dynamic/manh_controllers/superlog.py`): DISCOVERY_MISSED, SKIPPED_WITH_ENERGY; share 0.000, 0 samples taken, 0 failed, 0 late, battery at the end 75.0

## Every decision

| call | tick | what the agent did | reference before | reference after | points lost | tags |
|---:|---|---|---:|---:|---:|---|

*Reference before/after*: the score if the reference took over just before or just after this call, knowing only what the agent knew then (delivered telemetry, rules, map, its own acknowledgements). *Points lost* = before − after; the column plus the stop loss adds up to the gap.
