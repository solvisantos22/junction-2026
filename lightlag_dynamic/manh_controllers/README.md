# Manh controllers

Every meaningful controller combination Manh has built for the Lightlag dynamic profiles, in one registry, so new ones can be added and ranked against the same seeds, scenarios and bounds. Owner: Manh / Claude Code (see `TEAM_STATUS.md`). The rest of `lightlag_dynamic/` does not depend on this package.

**Scripted controllers only; no real agent has been run.** All numbers below come from development seeds 0–19. Confirm a winner on untouched seeds (for example 400–419, as in [the pilot results](../../docs/lightlag-dynamic-pilot.md)) before claiming anything. Differences of 2–3 points are within noise.

## Naming

`<METHODS>_manh_controller_<N>`: methods joined by underscores in the order they act (estimator, additions, planner), for example `PF_MPC_manh_controller_2` or `CKF_aimdisc_turncost_window_MPC_manh_controller_20`. N counts up in build order and is never reused.

- A new number is only for a new model or a new combination. A parameter change to an existing controller (same model, different values) does not get one.
- Retired numbers are listed below with the reason.
- Every registry entry records what the controller is (`note`), why it was built and what it showed (`why`), and when (`built`). `--list` prints them.

## Run

From the repository root, with numpy installed (checked on Python 3.10 with numpy 1.26, 3.12, and 3.14 with numpy 2.5):

```sh
python3 -m lightlag_dynamic.manh_controllers --list                                  # what each controller is and why
python3 -m lightlag_dynamic.manh_controllers --suite base  --seeds 0-19              # every controller, 4 profiles x delays 0/3/5
python3 -m lightlag_dynamic.manh_controllers --suite noise --controllers 1 20 team   # names, numbers or kinds (manh, bound, team)
python3 -m lightlag_dynamic.manh_controllers --suite partb --controllers 22 --append  # add a new controller to existing results
python3 -m unittest tests.lightlag_dynamic.test_manh_controllers                     # 8 tests, about 10 seconds
```

- Results go to `~/lightlag-manh-results/<suite>/`, outside the repository; use `--out` to change this, and do not commit result rows.
- Each run writes `rows.jsonl` (one summary per episode), `decisions.jsonl` (per-decision logs for seeds 0–2) and `report.md`.
- The report contains a leaderboard, a table per scenario, a failure atlas, estimation quality, and the cells where controller 1 and the best real controller fail (gap to bound 16) and prevail (lead over the best team controller).
- One suite with every controller takes a few minutes on 18 workers.

## Controllers

| N | Name | What it is | Why it was built, and what it showed |
|---|---|---|---|
| 1 | `EKF_MPC_manh_controller_1` | The repository's `kf_mpc`: EKF over position, heading bias and slip; delay compensation; MPC with chance constraints | Noisy sensing with a hidden, drifting heading bias needs an estimator that learns bias and slip while commands are in flight. Home in all 240 repo episodes; 85.0% on base. |
| 2 | `PF_MPC_manh_controller_2` | Bootstrap particle filter (500 particles) feeding the same planner | Slip clipping, wheel spins and failed samples make the posterior non-Gaussian (SSY345 L8). Ties the EKF overall. Better with 1 m position noise: 84% vs 72% (noisy, delay 5). Worse after a slip jump: 68% vs 77%. |
| 8 | `CKF_MPC_manh_controller_8` | Cubature Kalman filter: sigma points through the drive kinematics | The EKF linearises the drive at the mean (SSY345 L6). Best estimator at high noise: 68% vs 50% at noise level 3 (noisy, delay 5). Otherwise within noise of the EKF. |
| 10 | `PF_forgetting_MPC_manh_controller_10` | Particle filter whose slips random-walk | Meant to follow a slip jump. Did not help: 65% vs 68% (slip jump, noisy, delay 3). |
| 11 | `EKF_forgetting_MPC_manh_controller_11` | Controller 1 plus process noise on slip | The same idea for the EKF. Best real controller with two hidden sand patches: 56% vs 46% (noisy, delay 3). Costs about 1 point elsewhere. |
| 12 | `EKF_IEKS_MPC_manh_controller_12` | Iterated extended Kalman smoother: history relinearised at smoothed states | Tests whether hindsight helps the present (SSY345 L6 + L7). No gain: the controller acts on predictions, which smoothing cannot improve. |
| 13 | `EKF_window_MPC_manh_controller_13` | Controller 1, aware of uplink windows | Controllers that ignore windows send commands that would execute beyond the horizon. No crashes; 50% vs 39% (windows 10/3, rush_noisy, delay 3). |
| 14 | `EKF_turncost_MPC_manh_controller_14` | Controller 1, budgets turn energy | Planners that ignore a turn cost run out of energy. 75% and always home vs 61% (turn cost 0.03, noisy, delay 3); every team controller collapses there. |
| 15 | `EKF_terrainVO_MPC_manh_controller_15` | Controller 1 with per-terrain odometry noise | Small effect: 91% vs 89% (noisy, delay 3). |
| 18 | `EKF_aimdisc_MPC_manh_controller_18` | Controller 1 aiming at the target disc instead of its centre | Bound 16 showed that aiming at the centre wastes about 0.5 m per leg. 86.5% vs 85.0% on base, always home. |
| 19 | `EKF_aimdisc_turncost_window_MPC_manh_controller_19` | Controller 1 with 18, 14 and 13 together | Each addition helped on its own factor and is inactive when its rule is absent. Matches the best of the three on each factor; 77.0% averaged over the three suites. |
| 20 | `CKF_aimdisc_turncost_window_MPC_manh_controller_20` | As 19 on the cubature filter | **Best real controller so far:** 77.5% averaged over the three suites, home in 97% of episodes. |
| 21 | `PF_aimdisc_turncost_window_MPC_manh_controller_21` | As 19 on the particle filter | 77.1%. Best at 1 m position noise: 89% (noisy, delay 3). Weak with two hidden sand patches: 38%, home 45% of the time (noisy, delay 3). |

**Bounds** use privileged information through `scenarios.ScenarioEnvironment`. They are yardsticks, not entries.

| N | Name | What it knows | Why |
|---|---|---|---|
| 3 | `Oracle_params_MPC_manh_controller_3` | True slip, bias and terrain; noisy fixes; real delay; stock planner | Measures what learning the parameters costs: 71% → 78% (rush_noisy, delay 3). |
| 16 | `Oracle_exact_tight_MPC_manh_controller_16` | True parameters and exact telemetry; real delay; reserve 0.5; aims at the disc | The honest bound with delay: 90.4% on base. It is not a bound on turn-cost or window scenarios, because its planner ignores those rules. |
| 17 | `Oracle_exact_nodelay_tight_MPC_manh_controller_17` | As 16 without delay | Isolates the cost of delay: 95.9% on base, so delay costs 5.5 points even with perfect information. |

**Team controllers** (`solvi_reference`, `kristjan_reference`, `blind`, `cautious`) are run unchanged, for comparison.

**Retired numbers**, never reused:
- **4, 5:** exact-information bounds on the stock planner. They scored below the EKF, so they were not bounds; replaced by 16 and 17.
- **6, 7:** controller 1 with the failed-sample update, or the 97% wait rule, switched off. These were ablations, not new controllers.
- **9:** controller 2 with 2000 particles. Same model, different value.

## Where things stand (seeds 0–19, delays 0/3/5)

Share of the maximum score, averaged over every cell of each suite:

| Controller | Base | Noise | Part B | Mean | Home |
|---|---|---|---|---|---|
| Bound 17 (no delay) | 95.9% | 93.8% | 78.1% | 89.3% | 95% |
| Bound 16 | 90.4% | 86.2% | 69.5% | 82.0% | 94% |
| **20** CKF + aim at disc + turn cost + windows | 86.7% | 77.0% | 68.7% | **77.5%** | 97% |
| 21 PF + the same | 86.7% | 77.2% | 67.4% | 77.1% | 96% |
| 19 EKF + the same | 86.5% | 76.5% | 68.2% | 77.0% | 97% |
| 14 EKF + turn cost | 85.0% | 75.6% | 67.8% | 76.1% | 97% |
| 18 EKF + aim at disc | 86.5% | 76.5% | 65.4% | 76.1% | 95% |
| 8 CKF | 85.5% | 76.4% | 65.3% | 75.7% | 96% |
| 1 EKF (repository `kf_mpc`) | 85.0% | 75.6% | 65.3% | 75.3% | 96% |
| 2 PF | 85.3% | 76.5% | 63.7% | 75.2% | 94% |
| `blind` | 66.6% | 46.6% | 45.3% | 52.8% | 73% |
| `solvi_reference` | 58.5% | 47.3% | 44.2% | 50.0% | 81% |
| `kristjan_reference` | 50.4% | 21.0% | 18.0% | 29.8% | 31% |

The suites:
- **base:** `static`, `noisy`, `rush` and `rush_noisy` as published.
- **noise:** one sensing dial at a time, on `noisy` and `rush_noisy`:
  - position noise 0.1 / 0.6 / 1 m;
  - heading bias 0 / 10 / 20°;
  - bias walk 0 / 1.5 / 3°;
  - heading noise 0 / 3 / 6°;
  - odometry noise 1 / 15 / 30%;
  - every dial scaled by 0.5 / 2 / 3.
- **partb:** candidate rule factors, one at a time:
  - 1 or 2 m per tick of driving;
  - per-terrain odometry noise;
  - uplink windows 10/3 and 16/4;
  - 1 or 2 hidden sand patches;
  - a slip jump at 35% of the horizon;
  - turn cost 0.01 or 0.03 per degree.

**Still unsolved, and where to build next:**
- **Hidden sand patches.** With two patches on `noisy` at delay 3, Manh controllers score 38–56% and get home 45–85% of the time. `solvi_reference` scores 68% and gets home 90% of the time.
  - Candidate: change detection, or a multiple-model filter, that treats a local slip surprise as unmapped sand.
- **Uplink windows 16/4 on `rush_noisy`.** At delay 3 every Manh controller and bound 16 get home only 15–35% of the time. `blind`, which sends its whole plan at tick 0, scores 54% and always gets home.
  - Candidate: a rollout planner that sends whole plans at window openings.
- **Heading noise of 6° on `rush_noisy`.** Bound 16 drops to the controllers' level (53% vs 52% at delay 3), so no controller can help: the setting is too hard.

## Files

| File | Contents |
|---|---|
| `controllers.py` | Every controller, the mixins they combine (`_AimDisc`, `_TurnCost`, `_WindowAware`, `_Tight`), `REGISTRY`, `RETIRED` |
| `estimators.py` | Particle filter, cubature drive prediction, RTS smoother (numpy) |
| `scenarios.py` | `ScenarioEnvironment`: the dynamic environment plus separate noise dials, exact telemetry and a truth tap for bounds, and the Part B factors |
| `superlog.py` | Per-decision, per-packet and per-episode logging, with failure labels |
| `swarm.py` | Suites, the parallel runner, the report, the command line |

Failure labels, per episode:

| Label | Meaning |
|---|---|
| `DEAD`, `NOT_HOME`, `CRASH` | Battery ran out; alive but outside the base radius at the horizon; the controller raised an error |
| `MISS_CONFIDENT` | A sample failed although the controller was at least 90% sure |
| `MISS_TRY` | A sample failed that was sent below 90% certainty |
| `RETRIED_OK` | A missed target was sampled later |
| `SAFETY_STOP` | The rover hit a hazard or the map edge |
| `LATE_SAMPLE` | A target was sampled after its deadline |
| `DISCOVERY_MISSED` | A discovered target was never sampled |
| `SKIPPED_WITH_ENERGY` | Targets were left unsampled with 15 or more energy remaining |
| `ENERGY_LIMITED` | Targets were left unsampled with less than 15 energy remaining |
| `FILTER_OVERCONFIDENT` | Mean NEES above 4 (2 is consistent) |
| `BIAS_LOST` | Final heading-bias error above 3° |
| `PERFECT` | Every target sampled, and home |

## Adding a controller

1. Combine existing pieces, or write a new estimator or mixin, in `controllers.py`.
2. Register it under the next free number. Give it a `note`, a `why` and a `built` date.
3. Run all three suites with `--controllers <N> --append` into your existing results.
4. Add its row to the two tables above, with what it showed.
5. Run the tests, then pull and push.
