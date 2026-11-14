# Decision audit: do-nothing-seed7-delay3

- Model: scripted (no agent trajectory)
- Profile `core`, seed 7, delay 3 ticks, horizon 80
- Agent: **0** of 4 (reward 0.000, reward.txt 0.000)
- Reference (`team`) from the start: **4** (reward 1.000)
- Gap: 4 points = 1.000 reward. Decisions account for 0, stopping early for 4.
- Rebuild reproduces the saved run tick for tick: **yes**

## Main mistakes

### 1. stopped at tick 0: −4 points (−1.000 reward)

- **STOPPED_EARLY**: stopped at tick 0; the reference would have scored 4 from there, not 0. The agent stopped calling tools with time left that the reference would have used.
- Reference instead: at tick 0 uplink [drive 0° 5 m]; then sample east (tick 12), north (tick 20), west (tick 24); finish home, score 4

## Infrastructure (kept apart from reasoning)

None found: every agent call reached the simulator, Harbor recorded no exception, the rebuild matches the run and reward.txt matches the evaluator.

## Episode outcome

- **NOTHING_SAMPLED**: no sample was collected
- **STOPPED_EARLY**: stopped at tick 0; the reference would have scored 4 from there, not 0
- superlog labels (`lightlag_dynamic/manh_controllers/superlog.py`): SKIPPED_WITH_ENERGY; share 0.000, 0 samples taken, 0 failed, 0 late, battery at the end 60.0

## Every decision

| call | tick | what the agent did | reference before | reference after | points lost | tags |
|---:|---|---|---:|---:|---:|---|

*Reference before/after*: the score if the reference took over just before or just after this call, knowing only what the agent knew then (delivered telemetry, rules, map, its own acknowledgements). *Points lost* = before − after; the column plus the stop loss adds up to the gap.
