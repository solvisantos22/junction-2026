# Lightlag dynamic-rules pilot: deadlines, discoveries, time pressure and noisy sensing

14 November 2026. First increment about 01:45 Helsinki, second increment (noisy sensing, Kalman filter + MPC) about 02:20. Owner: Manh / Claude Code. Code: [`lightlag_dynamic/`](../lightlag_dynamic/README.md), tests: `tests/lightlag_dynamic/`. Runs on Sölvi's simulator in [`lightlag/`](../lightlag/README.md) and changes nothing in it, nor in `lightlag_controllers/` or `lightlag_mcp/`.

**No real agent has been run.** Everything below compares scripted controllers. It shows how the environment behaves under different rules, not whether a frontier agent struggles.

## Submission format: Harbor is required

AfterQuery's 14 November update ([summary](afterquery-update-2026-11-14.md)): every environment must be a [Harbor](https://github.com/harbor-framework/harbor) task (the `laude-institute/harbor` link redirects there), played with the OpenCode harness, writing one reward between 0 and 1 to `/logs/verifier/reward.txt`, with at least one Harbor run log of a real model and a short README. AfterQuery provides no inference credits.

For this pilot, that means nothing here reaches the submission except through Kristján's Harbor task ([`harbor/lightlag/`](../harbor/lightlag/), [notes](lightlag-harbor.md)). `python3 -m lightlag_dynamic.serve` is a drop-in for that task's simulator command: it accepts the same settings, including `LIGHTLAG_TOKEN_FILE`, answers `/healthz`, and was graded by `python -m lightlag_mcp.finish` over HTTP in a local test (`rush_noisy`, seed 7; result and replay written). Switching the task to a dynamic profile is a team rules decision and the task owner's change; nothing under `harbor/` is edited here.

## Second increment: noisy sensing and a Kalman filter + MPC reference

**Added**, all in `lightlag_dynamic/` ([details](../lightlag_dynamic/README.md)):
- **Profiles `noisy` and `rush_noisy`:** the `static` and `rush` maps with published, seeded sensing noise. A hidden heading bias (±5° at launch, 0.5° random walk per drive) plus 1.5° noise per drive; position fixes with 0.3 m noise per axis after the briefing; visual odometry with 5% error. Sampling and scoring use the true position.
- **A `noise_level` dial** that multiplies every sensing value, and an experimental, off-by-default **`bumpiness`** (rough cells that jolt the rover and can spin the wheels).
- **`kf_mpc`:** an extended Kalman filter (position, heading bias, slip per terrain) with delay compensation that carries the covariance forward, a receding-horizon planner, and chance constraints instead of fixed margins.
- **`compare.py`:** the three team references side by side. **`serve.py`:** the MCP entry point above.

### The three references on untouched seeds 400–419

Share of the best of the three on the same seed (home and alive in brackets where below 100%). `python3 -m lightlag_dynamic.compare --delays 0 3 5 --seeds 400-419`.

| Profile | Delay | Sölvi's reference | Kristján's reference | KF + MPC | Blind plan |
|---|---|---|---|---|---|
| `static` | 0 / 3 / 5 | 75% / 75% / 75% | 99% / 100% / 100% | 100% / 99% / 100% | 92% / 94% / 89% |
| `noisy` | 0 / 3 / 5 | 88% / 86% / 88% (95% home at 5) | 14% / 20% / 20% (0–20% home, 45–80% dead) | 100% / 100% / 100% | 76% / 68% / 77% |
| `rush` | 0 / 3 / 5 | 77% / 60% / 48% | 79% / 78% / 64% | 100% / 100% / 100% | 70% / 77% / 84% |
| `rush_noisy` | 0 / 3 / 5 | 57% / 47% / 43% (80–100% home) | 36% / 32% / 38% (40–50% home) | 100% / 99% / 100% | 67% / 76% / 96% |

- **KF + MPC got home alive in all 240 episodes** and is the best reference in every `noisy`, `rush` and `rush_noisy` cell (99–100%); on the noiseless `static` map it ties Kristján's.
- **Treating fixes as exact fails under noise.** Kristján's reference and this pilot's original reference learn slip from position differences; with 0.3 m fixes those estimates are wrong, and they die or end away from base. Sölvi's reference survives because its budgets are worst-case, at the cost of skipping targets.
- **At delay 5 with noise, the blind plan reaches 96% on `rush_noisy`.** Feedback is worth little there: by the time a noisy fix arrives the plan is mostly spent. That cell doesn't separate a feedback-using controller from a blind one, so it is a poor setting for testing an agent.

### How far the dials can go: the controller first, then the difficulty

The controller was upgraded and tuned on development seeds before the difficulty was raised. Then `noise_level` and `bumpiness` were swept on development seeds 0–19. Below: KF + MPC as a share of the maximum score, home and alive out of 20, and the best other reference.

| Setting | `noisy`, delay 0 / 3 / 5 | `rush_noisy`, delay 0 / 3 / 5 |
|---|---|---|
| noise 0 | 100% / 99% / 95%, all home | 86% / 78% / 70%, all home |
| noise 1 (default) | 90% / 94% / 86%, all home (Sölvi 73–75%) | 89% / 71% / 63%, all home (Sölvi 25–48%) |
| noise 1.5 | 82% / 82% / 81%, all home (Sölvi 56–67%) | 87% / 55% / 45%, all home (Sölvi 14–30%) |
| noise 2 | 76% / 74% / 71%, all home (Sölvi 31–34%, 14–19 home) | 82% / 50% / 35%, 19/20 home at delay 5 |
| noise 3 | 60% / 75% / 50%, all home (Sölvi 5–9%) | 76% / 32% / **11%, 18/20 home; blind 13%** |
| noise 1, bumpiness 0.1 / 0.2 / 0.3 | 72–78%, all home (Sölvi 71–75%) | 43–85%, all home (Sölvi 21–47%) |

- **Solvable range:** `noise_level` up to 1.5 at every delay, and up to 2 at delays 0 and 3: the KF + MPC reference gets home in every episode and keeps 45–100% of the maximum.
- **Overcooked:** noise 3 at delay 5 on `rush_noisy`. The best controller keeps 11%, loses 2 of 20 rovers, and the blind plan beats it. Noise 2 at delay 5 is borderline (35%, 19/20 home).
- **Raising noise widens the gap between references.** At noise 2–3, Sölvi's worst-case budgets stop protecting it (3–34% of the maximum, 5–19 of 20 home) while KF + MPC still gets home. Noise is a dial that rewards estimation, which is what it is meant to test.

### Controller changes this round, each measured on development and held-out seeds

| Change | Why | Effect |
|---|---|---|
| A failed sample is a measurement ("outside the radius"), applied as a moment-matched pseudo-measurement | With no delay the rover sampled 9 times from a spot 0.87 m from the target, sure it was inside | +3.1% total score on development seeds, +1.8% held-out; home rate up in the three hardest cells; nothing worse |
| Wait to see a sample land unless 97% sure, when there is time | A miss found out on the way home can't be retried | +0.4% development, +0.7% held-out on `noisy`; `rush` unaffected (always time-pressured) |
| Return-home slack under uncertainty; deadlines count as time pressure; visual-odometry outlier gate; spin feed-forward | Late spins stranded the rover; fixed-map score had dropped | All runs home; `rush_noisy` at delay 5 from 5.74 to 6.60 (seeds 300–319) |

**Filter consistency:** the normalized position error (NEES) averages 1.76–2.09 at the default noise level, against 2 for a consistent 2-D filter; 2.5 at noise level 2 (mildly overconfident). The 10% of samples that miss at a 90% threshold are expected 2σ events; the failed-sample update is what turns them into retries.

### Bumpy ground (pretest, not recommended yet)

- **It mostly changes the energy budget, not the delay skill.** On the fixed map, expected spin energy makes the three-target route unaffordable, so KF + MPC and Sölvi's reference both end with the same two targets (72–78% vs 71–75%). On `rush_noisy` it costs 4–20 points and KF + MPC keeps every rover home.
- **If adopted, use 0.1–0.2.** Rough cells are published in `map()`, so a controller can plan around them; the KF + MPC reference feeds the expected spin forward and gates the odometry it cannot explain.

### Limits of the second increment

- **Scripted controllers only.** These numbers say how much each dial separates estimation strategies, not how an LLM agent fares.
- **20 seeds per cell.** Differences of a few percent are noise.
- **The noise model is simple:** Gaussian, independent between fixes, with a single heading bias. Correlated or heavy-tailed noise is untested.
- **`serve.py` reads three private attributes** of `lightlag_mcp.service.EpisodeService`; a test guards them.
- Seeds used: development 0–19, tuning 0–9, comparison 300–319, held-out 400–419.

## First increment: deadlines, discoveries and time pressure

### Why

On the simulator's map the delay barely matters: there is plenty of time, and waiting costs clock rather than battery. Kristján's [pilot](lightlag-pilot.md) found that a plan that never reads telemetry scores 97–101% of the reference on varied maps. This pilot tests whether "varying samples" change that: targets with deadlines, targets discovered mid-mission (the controller learns about them through delayed telemetry), a fresh map every seed, and a time-pressured profile.

### The result in short

**Time pressure is what makes the delay matter.** On the `rush` profile (50 ticks, five targets plus one or two discoveries, tight windows), on 40 seeds (100–139) never used during development:

| Controller, as a share of the reference on the same seed | Delay 0 | Delay 3 | Delay 5 |
|---|---|---|---|
| Cautious: sends a whole leg, waits to see it land | 99% | 80% | 59% |
| Blind plan: plans once from the briefing, never reads telemetry | 71% | 81% | 86% |
| Ignores deadlines and discoveries | 79% | 83% | 83% |
| Treats old telemetry as the present | 99% | 1% (90% die) | 1% (88% die) |
| Do nothing | 0 | 0 | 0 |

The reference got home alive in every episode.

- **Neither shortcut closes the gap.** The blind plan misses discoveries, which arrive only through telemetry (71% even with no delay). Careful waiting runs out of clock (59% at delay 5). Matching the reference requires using late information without waiting for it, which is the skill Lightlag is meant to test.
- **The fairness check holds.** With no delay the cautious controller ties the reference (99%), so its loss at delays 3 and 5 comes from the delay itself.
- **Without time pressure there is no gap.** On the simulator's map, and on seeded maps with loose deadlines, the cautious controller scores 95–102% at every delay.
- **Deadlines change the plan.** A controller that ignores them loses 13–24% on `rush`, and 36–44% on the simulator's map with deadlines at delays 3 and 5.

### Cross-check with `lightlag_controllers` and tougher physics

Seeds 0–19 (`python3 -m lightlag_dynamic.crosscheck --hard`). Shares are of this pilot's reference on the same seed. "Tougher physics" is the variant recommended in the team pilot (sampling radius 0.4 m, slip noise ±0.08, sand slip 0.15–0.60), applied through `lightlag_controllers.pilot.physics_overrides()`. `lightlag.evaluation.run_episode` gave the same score as this pilot's runner on 5 of 5 seeds in all four settings.

**Rush, current physics**

| Controller | Delay 0 | Delay 3 | Delay 5 |
|---|---|---|---|
| Reference (this pilot), raw score | 8.95 | 7.97 | 7.05 |
| Cautious: whole leg, then wait | 100% | 77% | 59% |
| `team_move_and_wait`: one command, then wait | 76% | 20% | 13% |
| Blind plan (this pilot / `team_open_loop`) | 70% / 76% | 78% / 82% | 86% / 87% |
| `team_reference` (knows no deadlines or discoveries) | 76% | 76% | 68% |
| Old telemetry as the present (this pilot / `team_stale`) | 100% / 76% | 2% / 0% | 0% / 0% |

**Rush, tougher physics**

| Controller | Delay 0 | Delay 3 | Delay 5 |
|---|---|---|---|
| Reference (this pilot), raw score | 8.86 | 6.03 | 5.10 |
| Cautious: whole leg, then wait | 99% | 96% | 73% |
| Blind plan (this pilot / `team_open_loop`) | 46% / 57% | 78% / 78% | 67% / 88% |
| `team_reference` | 76% | 59% | 26% |

What this adds:
- **`move_and_wait` understates what a cautious agent can do.** Sending one command and then waiting loses heavily (20% on `rush`, 80% on the simulator's map at delay 3). Sending a whole leg and then waiting scores 95–98% on the simulator's map and 77% on `rush`. A leg-and-wait baseline would show the real cost of caution in the team pilot.
- **On `rush`, the team's blind plan beats the team reference** (82% vs 76% at delay 3, 87% vs 68% at delay 5). That reference was built for the plain map: it stops to confirm, and it knows nothing about deadlines or discoveries. A time-pressured rule set needs a reference built for it.
- **Tougher physics and `rush` don't simply add up yet.** With noise ±0.08 and a 0.4 m radius, this pilot's reference loses a quarter of its score at delay 3, and the cautious controller nearly catches up (96%). The reference has to handle noise better first, for example by aiming with a margin and confirming only near the target. This matches the team pilot's warning that a shorter horizon needs a faster reference.
- **On the plain map the team reference is stronger** (104–107% of this pilot's; 122–128% under tougher physics). This pilot's reference only earns its keep on the new rules.

### Limits

- **This pilot's reference is a stand-in and not optimal.** On the simulator's map with deadlines the blind plan beats it (120% at delay 3), because it stops to confirm the sand target before sampling.
- **The `rush` ranges and the fixed-map deadlines are hand-set difficulty dials.** `rush` was designed once and then checked on untouched seeds, not tuned per seed.
- **Exact visual odometry made slip easy to learn** in the first increment's profiles; the noisy profiles of the second increment add odometry error.
- **20–40 seeds per row.** Differences of a few percent are noise. Seed sets used: development 0–19, untouched check 100–139. Sölvi's frozen comparison uses 200–209 for its own check, so pick fresh seeds outside these for new checks.
- **`DynamicEnvironment` uses private hooks of `lightlag.Environment`** (`_sample`, `_snapshot` and a few fields); a test guards them.

## Suggested next steps

After the second increment:

1. **Rules decision (team):** whether the Harbor task should serve `rush` or `rush_noisy` at delay 3 (noise level 1). Both separate the references clearly, and the reference gets home in every episode. `python3 -m lightlag_dynamic.serve --profile rush_noisy` is the drop-in.
2. **A real Harbor run** of one model on the chosen profile, compared against KF + MPC, the blind plan and the cautious controller on the same seed.
3. **Avoid delay 5 with noise as a test setting:** the blind plan scores 96% there.

From the first increment:


1. **Rules decision (team):** the cleanest result is `rush`-style time pressure with deadlines and discoveries, on the current physics. Add the tougher physics only once a reference handles the noise.
2. **One reference:** port deadline and discovery handling into the team reference instead of keeping this stand-in.
3. **A fairer cautious baseline:** add "whole leg, then wait" next to `move_and_wait` in the shared comparison.
4. **Plumbing:** an environment-factory argument in `lightlag.evaluation.run_episode`, and the MCP server building `DynamicEnvironment` when a profile is chosen.
5. **Real agent runs** at delays 0 and 3 on `rush`, compared with the reference, the blind plan and the cautious controller. If the agent matches the blind plan, it isn't using feedback; if it matches the cautious one, it isn't predicting.
