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
| 19 | `EKF_aimdisc_turncost_window_MPC_manh_controller_19` | Controller 1 with 18, 14 and 13 together | Each addition helped on its own factor and is inactive when its rule is absent. Matches the best of the three on each factor. **Confirmed on held-out seeds 400–419:** +1.7 points over controller 1 (95% interval +1.4 to +2.0), and it needs no numpy. |
| 20 | `CKF_aimdisc_turncost_window_MPC_manh_controller_20` | As 19 on the cubature filter | Best on development seeds (77.5% averaged over the three suites). On held-out seeds 400–419 it ties 19 (+0.1 points, interval −0.2 to +0.4): the cubature filter adds nothing measurable. |
| 21 | `PF_aimdisc_turncost_window_MPC_manh_controller_21` | As 19 on the particle filter | 77.1%. Best at 1 m position noise: 89% (noisy, delay 3). Weak with two hidden sand patches: 38%, home 45% of the time (noisy, delay 3). |
| 22 | `EKF_sandodo_aimdisc_turncost_window_MPC_manh_controller_22` | 19 plus a battery sand odometer: unmapped sand read off the battery is added to its own map | Plans trust the published map. Battery telemetry is noise-free, so each drive's battery drop gives its sand wheel metres exactly. Held-out: +0.2 points over 19 (+0.1 to +0.3); two hidden patches on `noisy` 49% → 54%. |
| 23 | `EKF_stayalive_aimdisc_turncost_window_MPC_manh_controller_23` | 19 plus a stay-alive rule: never send a command expected to empty the battery before the horizon | Traces showed rovers dying on a last short drive home (score 0) instead of staying alive just outside (half score). Held-out: never worse than 19 (7 episodes better, 0 worse); +0.1 points. |
| 24 | `EKF_sandodo_stayalive_aimdisc_turncost_window_MPC_manh_controller_24` | 19 plus 22 and 23 | The odometer fixes legs once a patch is found; the stay-alive rule covers a patch found too late. **Best on held-out seeds:** +1.9 over controller 1 (+1.6 to +2.3), +0.2 over 19 (+0.1 to +0.4); identical to 19 on the published profiles. |
| 25 | `EKF_sandodo_mapdoubt_stayalive_aimdisc_turncost_window_MPC_manh_controller_25` | 24 plus map doubt: once the map is shown wrong, undriven bedrock on the way home is budgeted at the unmapped-sand rate seen so far | The remaining deaths of 24 come from the patch on the last route home. Cuts deaths with two patches from 20% to 12% but gains only 1 point there, and loses 0.4 points elsewhere: rare false odometer patches on clean maps switch the doubt on. |

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

## Where things stand (development seeds 0–19, delays 0/3/5; held-out check below)

Share of the maximum score, averaged over every cell of each suite:

| Controller | Base | Noise | Part B | Mean | Home |
|---|---|---|---|---|---|
| Bound 17 (no delay) | 95.9% | 93.8% | 78.1% | 89.3% | 95% |
| Bound 16 | 90.4% | 86.2% | 69.5% | 82.0% | 94% |
| **20** CKF + aim at disc + turn cost + windows | 86.7% | 77.0% | 68.7% | **77.5%** | 97% |
| 24 EKF + the same + sand odometer + stay alive | 86.5% | 76.5% | 68.8% | 77.3% | 97% |
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

**Held-out check (seeds 400–419, never used for development).** Paired by episode against controller 1, 3,840 episodes per controller; the 95% interval is a bootstrap over seeds:

| Controller | Development seeds 0–19 | Held-out seeds 400–419 | Home, held-out (1 → controller) |
|---|---|---|---|
| 18 aim at disc | +0.6 (+0.2 to +1.0) | +0.6 (+0.3 to +0.8) | 96% → 96% |
| 19 EKF + aim + turn cost + windows | +1.6 (+1.1 to +2.0) | **+1.7 (+1.4 to +2.0)** | 96% → 97% |
| 20 CKF + the same | +2.1 (+1.6 to +2.6) | **+1.8 (+1.4 to +2.2)** | 96% → 98% |
| 21 PF + the same | +1.8 (+0.9 to +2.6) | +1.4 (+0.8 to +1.9) | 96% → 96% |
| 22 19 + sand odometer | +1.7 (+1.2 to +2.2) | +1.8 (+1.5 to +2.2) | 96% → 98% |
| 23 19 + stay alive | +1.7 (+1.2 to +2.1) | +1.7 (+1.4 to +2.1) | 96% → 97% |
| 24 19 + sand odometer + stay alive | +1.8 (+1.3 to +2.3) | **+1.9 (+1.6 to +2.3)** | 96% → 98% |
| 25 24 + map doubt | +1.6 (+1.1 to +2.1) | +1.4 (+1.0 to +1.9) | 96% → 98% |
| Bound 16 | +8.0 (+6.5 to +9.6) | +9.8 (+8.5 to +11.1) | 96% → 95% |

- **The gain is real, and it comes from the planner additions, not the estimator.** 19 and 20 tie on held-out seeds: 20 vs 19 is +0.1 points (−0.2 to +0.4). The cubature filter's extra lead on development seeds did not replicate.
- **24 vs 19 on held-out seeds:** +0.2 points (+0.1 to +0.4), +0.6 on Part B (+0.3 to +0.9), and the same score on every published-profile episode. Its two additions are pure Python, like 19's.
- **Candidate for the repository reference:** 19, or 24 if the team wants the hidden-sand fixes too. It is `kf_mpc` plus three pure-Python mixins, so it needs no numpy and could run inside the Harbor task image.
- **Where 19–20 gain on held-out seeds:** turn cost +21 points; uplink windows +5 to +8. Where they lose: hidden sand, −2 to −4. Aiming at the disc removes slack that unmapped sand then needs.

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
- **Hidden sand patches.** Narrowed by 22–25, not closed. Held-out seeds, `noisy`, pooled delays (share / home / dead):

  | Controller | Clean map | 1 patch | 2 patches |
  |---|---|---|---|
  | 19 | 90% / 100% / 0% | 68% / 85% / 10% | 49% / 70% / 27% |
  | 24 | 90% / 100% / 0% | 69% / 90% / 10% | 54% / 77% / 20% |
  | 25 | 89% / 100% / 0% | 67% / 90% / 10% | 55% / 83% / 12% |
  | `solvi_reference` | 74% / 98% / 0% | 73% / 98% / 2% | 68% / 92% / 7% |

  - On `rush_noisy` ours win everywhere (two patches: 42–43% vs 27%), and on clean maps by 16 points on `noisy`.
  - **Why Sölvi's controller wins on `noisy`:** it never attempts the third target. Its slip learner requires position and odometry to agree exactly, which never happens under noise, so it always budgets the worst-case slip and keeps a 5-energy reserve. That slack absorbs unmapped sand.
  - **Why ours still die:** they take the third target with about 2 energy to spare. The patch that kills them lies on the last route home, so it is first crossed after the energy is spent. The battery sand odometer (22) reads it exactly (0.00 on every bedrock drive), but too late; the stay-alive rule (23) only turns some deaths into half scores.
  - **Map doubt (25) is the right idea with the wrong trigger.** Budgeting undriven bedrock once the map is shown wrong cuts deaths with two patches from 20% to 12%, but the odometer makes rare false patches on clean maps (0.1–0.2 per episode), and each one switches the doubt on.
  - **A bigger reserve is not the fix.** Controller 1 with a reserve of 5 scores 65% with hidden sand, but 75% instead of 94% without it.
  - Candidate: switch map doubt on only when the packet's `terrain` field confirms sand where the map says bedrock, so it costs nothing on clean maps.
  - Candidate: price the third target against the chance that the route home holds an unseen patch, instead of a fixed reserve.
- **Uplink windows 16/4 on `rush_noisy`.** At delay 3 every Manh controller and bound 16 get home only 15–35% of the time. `blind`, which sends its whole plan at tick 0, scores 54% and always gets home.
  - Candidate: a rollout planner that sends whole plans at window openings.
- **Heading noise of 6° on `rush_noisy`.** Bound 16 drops to the controllers' level (53% vs 52% at delay 3), so no controller can help: the setting is too hard.

## Discriminative seeds

On seed 500, the Harbor reference (`kf_mpc`) and Claude Opus 5.5 both score 1.000, on `rush` and on `rush_noisy`. That seed cannot show a gap between a model and the reference. `seeds.py` looks for seeds that a feedback controller using only the five public tools nearly solves, while each shortcut an agent might take falls well short.

```bash
python3 -m lightlag_dynamic.manh_controllers.seeds --seeds 1000-1499 --profiles rush rush_noisy --delay 3
```

The settings match Sölvi's Harbor experiments: horizon 50, noise level 1, bumpiness 0, delay 3. Each seed is played once per controller; the noise is seeded by the episode seed. The run takes about 80 s on 18 workers.

**Criteria**, declared in the module before the search range was played, per profile and seed:
- **Selectors:** controllers 19, 20, 21 and 24 must all end alive and home, with every score at least 0.90.
- **Tier 1, "needs feedback":** `blind` (plans once, never reads telemetry) and `cautious` (one leg, then waits for all its telemetry) both score at most 0.60.
- **Tier 2, "needs delay-aware, rule-aware feedback":** tier 1, plus `stale_telemetry` (treats the last packet as the present) and `window_blind` (ignores deadlines and discoveries) both score at most 0.60.
- **Ranking:** by the gap between the lowest selector and the highest shortcut.
- **Reported, never selected on:** `kf_mpc` (controller 1, the frozen Harbor reference) and bound 16. This avoids picking seeds where the reference happened to be lucky.
- **Also reported, never selected on: the no-drift proxy.** This is `kf_mpc` believing the heading bias is zero (bias variance at the floor, no bias walk). It re-plans from every fix, like Claude Opus on seed 500, but never models drift. It was added after the search; the selection did not change.

**Selection uses scripted controllers only, never a model's outcome.** A seed that every shortcut fails shows that it needs the behaviour, not that a model lacks it. Seed 500 passes tier 1 on both profiles, and Opus solved it.

Seeds 1000–1499, delay 3:

| Profile | Selectors ≥ 0.90 | Tier 1 | Tier 2 | 19 | `kf_mpc` | Bound 16 | No-drift | Blind | Cautious | Window-blind |
|---|---|---|---|---|---|---|---|---|---|---|
| `rush` | 139 | 34 | 14 | 81% | 78% | 82% | 78% | 60% | 59% | 64% |
| `rush_noisy` | 55 | 18 | 15 | 69% | 68% | 81% | 70% | 54% | 40% | 17% |

The last seven columns are mean scores. Below, the top tier-2 seeds per profile. Scores are shares of the maximum. Controllers 19–24 score the same on every row listed.

`rush` (no noise, so the no-drift proxy equals `kf_mpc`):

| Seed | Gap | 19–24 | `kf_mpc` (1) | Bound 16 | No-drift | Blind | Cautious | Window-blind | Targets (launch + found) |
|---|---|---|---|---|---|---|---|---|---|
| 1428 | +0.50 | 1.00 | 0.75 | 1.00 | 0.75 | 0.42 | 0.46 | 0.50 | 5 + 2 |
| 1295 | +0.48 | 1.00 | 0.88 | 0.83 | 0.88 | 0.50 | 0.50 | 0.52 | 5 + 2 |
| 1095 | +0.47 | 1.00 | 1.00 | 1.00 | 1.00 | 0.50 | 0.50 | 0.53 | 5 + 1 |
| 1100 | +0.44 | 1.00 | 0.67 | 1.00 | 0.67 | 0.56 | 0.56 | 0.50 | 5 + 1 |
| 1156 | +0.44 | 1.00 | 0.67 | 1.00 | 0.67 | 0.56 | 0.56 | 0.50 | 5 + 1 |
| 1001 | +0.42 | 1.00 | 1.00 | 1.00 | 1.00 | 0.56 | 0.56 | 0.58 | 5 + 1 |
| 1035 | +0.42 | 1.00 | 1.00 | 1.00 | 1.00 | 0.56 | 0.56 | 0.58 | 5 + 1 |
| 1155 | +0.42 | 1.00 | 1.00 | 1.00 | 1.00 | 0.50 | 0.56 | 0.58 | 5 + 2 |
| 1208 | +0.42 | 1.00 | 1.00 | 1.00 | 1.00 | 0.50 | 0.52 | 0.58 | 5 + 2 |
| 1390 | +0.42 | 1.00 | 1.00 | 1.00 | 1.00 | 0.56 | 0.56 | 0.58 | 5 + 1 |

`rush_noisy`:

| Seed | Gap | 19–24 | `kf_mpc` (1) | Bound 16 | No-drift | Blind | Cautious | Window-blind | Targets (launch + found) |
|---|---|---|---|---|---|---|---|---|---|
| 1165 | +0.80 | 1.00 | 1.00 | 1.00 | 0.20 | 0.05 | 0.20 | 0.00 | 5 + 1 |
| 1344 | +0.55 | 1.00 | 1.00 | 1.00 | 1.00 | 0.45 | 0.36 | 0.00 | 5 + 2 |
| 1458 | +0.52 | 1.00 | 1.00 | 1.00 | 1.00 | 0.23 | 0.48 | 0.00 | 5 + 1 |
| 1129 | +0.50 | 0.90 | 0.90 | 1.00 | 0.60 | 0.40 | 0.40 | 0.00 | 5 + 1 |
| 1460 | +0.50 | 1.00 | 1.00 | 1.00 | 0.80 | 0.50 | 0.45 | 0.45 | 5 + 1 |
| 1035 | +0.44 | 1.00 | 1.00 | 1.00 | 1.00 | 0.56 | 0.56 | 0.00 | 5 + 1 |
| 1155 | +0.42 | 1.00 | 1.00 | 1.00 | 1.00 | 0.50 | 0.42 | 0.58 | 5 + 2 |
| 1018 | +0.40 | 1.00 | 1.00 | 1.00 | 0.78 | 0.60 | 0.50 | 0.00 | 5 + 1 |
| 1318 | +0.40 | 1.00 | 1.00 | 0.72 | 0.62 | 0.60 | 0.45 | 0.00 | 5 + 1 |
| 1001 | +0.36 | 0.92 | 0.92 | 1.00 | 0.67 | 0.56 | 0.56 | 0.50 | 5 + 1 |

**Where not modelling drift costs points (`rush_noisy`, tier 2).**
- The no-drift proxy scores below `kf_mpc` on 9 of the 15 tier-2 seeds.
- It scores 0.60 or less on three: 1129, 1165 and 1302.
- **1165 is the sharpest seed found.** The reference scores 1.00 and every player that ignores feedback, the delay, the rules or the drift scores 0.20 or less.

**Tier 2 on both profiles: 1001, 1021, 1035, 1155, 1390.**
- `kf_mpc` scores 1.00 on all five on `rush`.
- On `rush_noisy` it scores 1.00 on 1035 and 1155, 0.92 on 1001 and 1390, and 0.90 on 1021.

Caveats:
- **For a Harbor comparison against `kf_mpc`, prefer seeds where it scores 1.00.** On 1428, 1295, 1100 and 1156 (`rush`), the frozen reference itself falls short, so a model could beat it there.
- **The agreement check is weak.** The four selectors share one planner, and 24 equals 19 on the published profiles. They score the same on 480 of 500 `rush` seeds and 434 of 500 `rush_noisy` seeds.
- **Tier 2 is in practice decided by `window_blind`.** `stale_telemetry` runs out of energy on nearly every seed: it scores above 0 on 31 `rush` seeds and 14 `rush_noisy` seeds, and never above 0.20.
- **Bound 16 is not a strict upper bound.** Its tight planner sometimes scores below the selectors, for example 0.83 on 1295 and 0.72 on 1318.
- **Passes are rare on `rush_noisy`:** 18 tier-1 seeds out of 500. On seeds 0–19 and 600–639 none of 60 pass; feedback controllers average 72% there and bound 16 averages 84%.
- **At the published heading bias of ±5°, ignoring drift costs little on average.** The no-drift proxy averages 70% on `rush_noisy` against 68% for `kf_mpc`. On `noisy` (seeds 0–19 and 600–639, horizon 80) it averages 86% against 92%. Seeds alone may therefore not open a gap. A drift the agent has to learn is the stronger lever. With a wider published bias range (`rush_noisy`, delay 3, seeds 0–19 and 600–639, `sensing` override in `scenarios.make_env`), the cost of ignoring drift grows from about 1 point to 28:

  | Heading bias | `kf_mpc` | No-drift | Blind | Leg-and-wait |
  |---|---|---|---|---|
  | ±5° (published) | 72% | 71% | 58% | 44% |
  | ±15° | 65% | 37% | 28% | 24% |

  Changing the published bias range is a rules decision for the team.
- **Do not pair uplink windows with `kf_mpc` as the reference.** It isn't window-aware. On `rush_noisy`, delay 3, seeds 1000–1019, it stops with "commands would execute beyond the episode horizon" in 9 of 20 episodes with 10/3 windows and 15 of 20 with 16/4. Controllers 19 and 24 never stop.
- **These seeds are reserved for this search.** 0–19, 100–139, 200–209, 300–319, 400–419 and 500–504 are taken by development, held-out checks and Sölvi's Harbor comparisons.

## Files

| File | Contents |
|---|---|
| `controllers.py` | Every controller, the mixins they combine (`_AimDisc`, `_TurnCost`, `_WindowAware`, `_Tight`), `REGISTRY`, `RETIRED` |
| `estimators.py` | Particle filter, cubature drive prediction, RTS smoother (numpy) |
| `scenarios.py` | `ScenarioEnvironment`: the dynamic environment plus separate noise dials, exact telemetry and a truth tap for bounds, and the Part B factors |
| `superlog.py` | Per-decision, per-packet and per-episode logging, with failure labels |
| `swarm.py` | Suites, the parallel runner, the report, the command line |
| `seeds.py` | Discriminative-seed finder: the declared criteria, the players and a ranked report |
| `mars.py` | Mars-operations tweaks (onboard slip check, relay passes; off by default) and the slip-check-aware layer for controllers 1 and 24 (not registered); see the pilot doc, "Mars-operations tweaks" |

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
