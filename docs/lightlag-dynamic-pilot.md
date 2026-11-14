# Lightlag dynamic-rules pilot: deadlines, discoveries, time pressure and noisy sensing

14 November 2026. First increment about 01:45 Helsinki, second increment (noisy sensing, Kalman filter + MPC) about 02:20, third increment (Manh controllers and swarm testing) about 03:30, real-time clock about 03:45. Owner: Manh / Claude Code. Code: [`lightlag_dynamic/`](../lightlag_dynamic/README.md), tests: `tests/lightlag_dynamic/`. Runs on Sölvi's simulator in [`lightlag/`](../lightlag/README.md) and changes nothing in it, nor in `lightlag_controllers/` or `lightlag_mcp/`.

**This pilot's own comparisons are all scripted controllers.** They show how the environment behaves under different rules, not whether a frontier agent struggles. The only real agent runs so far are Sölvi's [Harbor experiments](lightlag-experiments.md), which serve this package's `rush` profile: Claude Opus 5.5 scored 1.000 on seed 500 at delay 3, both on `rush` and on `rush_noisy`. The [Harbor reward check](#harbor-reward-check-what-the-model-is-graded-on) below confirms how that number is computed.

## Submission format: Harbor is required

AfterQuery's 14 November update ([summary](afterquery-update-2026-11-14.md)): every environment must be a [Harbor](https://github.com/harbor-framework/harbor) task (the `laude-institute/harbor` link redirects there), played with the OpenCode harness, writing one reward between 0 and 1 to `/logs/verifier/reward.txt`, with at least one Harbor run log of a real model and a short README. AfterQuery provides no inference credits.

For this pilot, that means nothing here reaches the submission except through Kristján's Harbor task ([`harbor/lightlag/`](../harbor/lightlag/), [notes](lightlag-harbor.md)). `python3 -m lightlag_dynamic.serve` is a drop-in for that task's simulator command: it accepts the same settings, including `LIGHTLAG_TOKEN_FILE`, answers `/healthz`, and was graded by `python -m lightlag_mcp.finish` over HTTP in a local test (`rush_noisy`, seed 7; result and replay written). Switching the task to a dynamic profile is a team rules decision and the task owner's change; nothing under `harbor/` is edited here.

## Real-time clock: thinking costs ticks

[`lightlag_dynamic/realtime.py`](../lightlag_dynamic/realtime.py), added about 03:45 Helsinki. Run it with `python3 -m lightlag_dynamic.realtime --seconds-per-tick 5 --profile rush_noisy --seed 7 --delay 3`. The flags and settings are the same as `serve`, plus `LIGHTLAG_SECONDS_PER_TICK`.

**Why.** In the turn-based episode only `advance` moves the clock, so an agent can think for as long as it likes between ticks. Mission control has no pause button. The recorded Opus 5.5 runs show how much free time that is:
- each 50-tick mission took 61–126 s of wall time;
- the median gap between game calls was 3–4 s;
- single planning pauses lasted up to 32 s.

None of that cost a tick.

**What changes.**
- One tick passes every `seconds_per_tick` seconds from the agent's first tool call. Starting at the first call means container and harness start-up never cost ticks.
- Before any tool answers, the episode catches up to the wall clock. Commands are stamped with the tick at which they arrive.
- `advance(n)` no longer moves the clock. It waits until n more ticks have passed, and returns every packet received since the previous `advance`, including those that arrived while the agent was thinking.
- `rules()` reports the clock: tick length, current tick and seconds elapsed. The MCP tool texts describe the real-time clock instead of "only `advance` moves the clock".
- Physics, scoring and `replay.json` are unchanged.
- The transcript records each catch-up as a `"tool": "clock"` record, and every record carries `wall_seconds`.
- It is a separate module, so `serve.py`, which Sölvi's experiments copy and hash, is untouched.

Tested with a fake clock (9 tests) and live over HTTP with a 0.5 s tick, including the evaluator's finish hook.

**Calibration with scripted controllers.** `rush_noisy`, delay 3, development seeds 0–19. Each tool call first spends a simulated thinking time, given in ticks:

| Thinking time per call (ticks) | 0 (= turn-based) | 0.25 | 0.5 | 0.75 | 1.0 | 1.5 |
|---|---|---|---|---|---|---|
| `kf_mpc`, share of maximum | 0.707 | 0.739 | 0.692 | 0.633 | 0.486 | 0.420 |
| Blind plan, sends everything first | 0.539 | 0.539 | 0.537 | 0.522 | 0.508 | 0.499 |
| Whole leg, then wait | 0.418 | 0.418 | 0.307 | 0.371 | 0.224 | 0.207 |

*Correction.* The first version of this table, pushed in 2a07048, was measured with an early build whose `advance` dropped the packets that arrived while the controller was thinking. That bug was fixed before the push, but the table was not re-measured. It showed `kf_mpc` collapsing to 0.204 at 0.5 ticks per call. The numbers above are re-measured with the published build.

- **A controller that answers instantly loses nothing.** On the same seed its commands and score are identical to turn-based (tested). So the scripted reference keeps its score under real time, and the gap to an agent then includes the agent's thinking time.
- **`kf_mpc` degrades gracefully up to 0.75 ticks of thinking per call (0.707 to 0.633) and drops at 1 tick per call (0.486).** The earlier claim that it collapses between 0.25 and 0.5 was wrong. It decides from the tick it last saw, so with long thinking its commands land late and the rover idles. Batch planning (the blind plan) barely notices. Whole-leg-then-wait crashes on late uplinks near the horizon at 1 tick per call and more.
- **Choosing the tick length.** Opus spent 3–4 s per game call, about 30 calls per mission. At **3.5–5 s per tick** that is 0.7–1 tick of thinking per call, the region where thinking costs. At 10 s per tick (about 0.35 ticks per call) it costs almost nothing. A 50-tick mission lasts 175 s at 3.5 s per tick and 250 s at 5 s, both well inside Harbor's 1,800 s agent timeout.
- **Caveat: scores now depend on API latency and provider load, not only on reasoning.** Report `wall_seconds` and the model's per-call latency with every real-time score, and run each paired reference in the same task.

**What switching an experiment needs (team decisions; nothing changed here):**
1. Sölvi's `prepare.py` would copy `realtime.py`, start `python -m lightlag_dynamic.realtime` and set `LIGHTLAG_SECONDS_PER_TICK`.
2. The task's `instruction.md` says `advance` "is the only tool that moves the clock". Replace that with, for example: "The clock runs in real time: one tick every S seconds from your first tool call, whether or not you call tools. `advance(n)` waits until n more ticks have passed."
3. The decision auditor replays `advance` arguments, so on a real-time transcript it would report a rebuild mismatch rather than a wrong audit. It needs to step the clock by `clock` records.
4. Optionally, a real-time-aware reference as the matched bound for an agent that needs time to think: see [Real-time-aware reference](#real-time-aware-reference-optional-extra-awaiting-team-decision) below. `kf_mpc` still answers instantly, so it remains a valid instant reference.

### Real-time-aware reference (optional extra, awaiting team decision)

**Status for agents and teammates: proposal by Manh; do not switch any reference to it without team agreement.** Nothing imports it. `kf_mpc` stays the reference everywhere it is used today.

**What.** [`lightlag_dynamic/kf_mpc_rt.py`](../lightlag_dynamic/kf_mpc_rt.py), policy `kf_mpc_rt`. In the Manh registry it is `EKF_latencyaware_MPC_manh_controller_29` (the swarm plays turn-based, where 29 equals controller 1). It is `kf_mpc` with three changes:
- It measures its lag: the ticks between the tick it decided on and its uplink's `sent_tick`, as the median of its last five uplinks.
- It decides that much earlier, so its next commands arrive just as the queue empties and the rover does not idle while it thinks. The plan itself is `kf_mpc`'s.
- Commands that no longer fit before the horizon are dropped instead of crashing the controller.

Turn-based, or when it answers instantly, it sends exactly `kf_mpc`'s commands, so it only differs on the real-time clock.

**Design evidence, development seeds 0–39.** Two alternatives did worse than `kf_mpc` at small lags: also moving the planning slot by the lag, and planning with the largest recent lag. While a controller thinks, the rover usually stands still, so a late plan is still geometrically right; what costs score is the idle queue, and deciding early fixes that.

**Held-out check, fresh seeds 600–639.** `rush` and `rush_noisy`, delay 3, paired by episode against `kf_mpc` (95% interval from a bootstrap over seeds). Share of maximum by thinking time per call:

| Profile | Controller | 0 | 0.25 | 0.5 | 0.75 | 1.0 | 1.5 |
|---|---|---|---|---|---|---|---|
| `rush_noisy` | `kf_mpc` | 0.724 | 0.701 | 0.701 | 0.692 | 0.551 | 0.506 |
| `rush_noisy` | `kf_mpc_rt` | 0.724 | 0.701 | 0.701 | 0.692 | **0.590** | **0.522** |
| `rush` | `kf_mpc` | 0.819 | 0.815 | 0.793 | 0.782 | 0.599 | 0.506 |
| `rush` | `kf_mpc_rt` | 0.819 | 0.815 | 0.793 | **0.792** | **0.688** | **0.519** |

- **At 1 tick per call:** +4.0 points on `rush_noisy` (+1.4 to +6.8) and +8.9 on `rush` (+5.3 to +13.0).
- **Pooled over all thinking times above zero:** +1.1 (+0.5 to +1.8) and +2.2 (+1.4 to +3.2).
- **Never worse.** At zero thinking it sends identical commands on every seed.
- **Baselines on the same seeds, `rush_noisy`, from no thinking to 1.5 ticks per call:** the blind plan falls from 0.597 to 0.545, and whole-leg-then-wait from 0.444 to 0.227.

Re-run: the comparison scripts were scratch and are not in the repository. `tests/lightlag_dynamic/test_kf_mpc_rt.py` holds the same harness: `RealTimeEpisodeService` on a fake clock, plus a `Thinking` wrapper that spends a fixed time before every tool call. Looping it over seeds 600–639, both profiles and the six thinking times rebuilds the table.

**How to adopt (team decision).** These are teammates' files, so the steps are described here, not made:
1. Sölvi's `tools/lightlag_experiments/prepare.py` copies `lightlag_dynamic/kf_mpc_rt.py` into the task's `solution/lightlag_dynamic/`, next to `kf_mpc.py`.
2. `tools/lightlag_experiments/play_policy.py` accepts `"kf_mpc_rt"` (`from lightlag_dynamic.kf_mpc_rt import kf_mpc_rt`).
3. The generated `solution/solve.sh` passes `--policy kf_mpc_rt`.
4. Use it as the matched reference **only in real-time runs** (`python -m lightlag_dynamic.realtime`). Turn-based it is identical to `kf_mpc`.

**How to decline.** Do nothing: nothing imports it. Optionally delete `lightlag_dynamic/kf_mpc_rt.py`, `tests/lightlag_dynamic/test_kf_mpc_rt.py` and registry entry 29.

## Harbor reward check: what the model is graded on

This was checked against Harbor's own documentation ([docs.harborframework.com](https://docs.harborframework.com/tasks/verifier)) and every recorded run, at commit ad406ae. Nothing has been tweaked.

- **The task follows Harbor's conventions.** It uses only documented features:
  - one number written to `/logs/verifier/reward.txt`;
  - a separate verifier container (`environment_mode = "separate"`), so the agent cannot touch the grader;
  - the evaluator's files collected from the `lightlag` service through `artifacts` and a `[[verifier.collect]]` hook;
  - the game server declared under `[[environment.mcp_servers]]`.
- **The grader is unchanged** since Kristján's first commit (d2dee96).
  - reward = raw_score / max_available_value, clamped to 0–1.
  - A malformed result fails the verifier instead of scoring zero.
  - The simulator and MCP copies inside the task match their originals (`python3 harbor/sync_task.py --check`).
- **Sölvi's rush experiments are graded through this package.**
  - `tools/lightlag_experiments/prepare.py` builds a copy of the task outside the checkout. The copy serves `python -m lightlag_dynamic.serve`; the grader is not edited.
  - The rush reward therefore comes from `DynamicEnvironment.evaluate`. A late sample earns 0.25 of its value, and discovered targets count in the maximum.
  - All five rush runs were prepared from a clean checkout at 0bc0d43, and every source file they used is byte-identical to today's.
- **Every recorded reward reproduces exactly.** Re-sending each run's logged commands to a fresh `DynamicEnvironment` gives the same true trajectory and the same reward:

  | Run | Reward |
  |---|---|
  | `kf_mpc` | 1.000 |
  | Opus 5.5 | 1.000 |
  | Open loop | 0.571 |
  | Leg and wait | 0.536 |
  | Do nothing | 0.000 |

  The decision auditor (`python3 -m lightlag_audit`) makes the same check from the agent's transcript. It flags `INFRA_REWARD_MISMATCH` if `reward.txt` ever disagrees with the evaluator.
- **Our controllers optimise the graded number.**
  - The swarm's `share` equals `grade.py`'s reward on all 13 recorded runs (seed 7, `rush` and `rush_noisy` seed 500) and on a fresh `rush_noisy` episode. `tests/lightlag_dynamic/test_harbor_reward.py` fails if the two drift apart.
  - The swarm plays the experiment's settings: horizon 50, noise level 1, bumpiness 0.
- **The noisy pilot matched the offline prediction** (`rush_noisy`, seed 500, delay 3).
  - Before Sölvi's container results were pushed (db11c45), the swarm played the same episode offline through the public tools. `kf_mpc` (controller 1), controllers 18–21 and bound 16 were each predicted to score 1.000.
  - The container runs then scored exactly as predicted:

    | Policy | Predicted offline | Harbor |
    |---|---|---|
    | `kf_mpc` | 1.000 | 1.000 |
    | Blind plan | 0.571 | 0.571 |
    | Whole leg, then wait | 0.268 | 0.268 |

    Claude Opus 5.5 also scored 1.000.
  - So the container path adds nothing to the score. This is one seed, so it says nothing general about noise.

## Mars-operations tweaks (sandbox, off by default)

**Status:** a lab experiment, NOT a rules decision and not used by the Harbor task. The code is [`manh_controllers/mars.py`](../lightlag_dynamic/manh_controllers/mars.py) and the tests are `tests/lightlag_dynamic/test_mars.py`. Two small factors move the environment toward how Curiosity and Perseverance are actually driven. Both are published in `rules()`. With them off, or at an inert value, the episode is identical to `ScenarioEnvironment` (tested).

| Factor | Effect | Basis |
|---|---|---|
| `slip_check {"limit": L}` | If a drive step slips more than L, the rover stops that drive and discards every queued command. Telemetry reports `safety_stop` / `slip_limit`. | Onboard fault protection. Curiosity backed out of Hidden Valley's sand in 2014 this way. |
| `downlink_passes {"period": P}` | A packet for tick t arrives at the first multiple of P at or after t + delay. | Telemetry comes down through orbiter relay passes. |

**Keep rule, declared before measuring.** Our best controller keeps at least 90% of its untweaked score, and its gap to the best baseline (Sölvi's and Kristján's references, `blind`, `cautious`) shrinks by at most 2 points. The rule was checked on development seeds 0–39, then on fresh seeds 700–779 and 800–879, on `rush_noisy` and `noisy`, delay 3.

| Setting | `rush_noisy` (50 ticks) | `noisy` (80 ticks) | Decision |
|---|---|---|---|
| slip check 0.45 | pass | pass | keep (mildest; few trips) |
| slip check 0.40–0.42 | pass (≥ 93.8%, gap −1.9 at most) | fail: the gap to `solvi_reference` drops from +16.6 to +5.2 (0.42) and −0.2 (0.40) | rush profiles only |
| slip check 0.35 | fail on development seeds (87%) | fail | reverted |
| passes P = 2 | pass | pass | keep |
| passes P = 3 | fail on seeds 700–779 (gap −2.7) | pass | softened to P = 2 |

`solvi_reference` never drives on sand, so the slip check never touches it (75.0% on `noisy` at every limit). This is the same worst-case-avoidance effect as with hidden sand.

**Co-designed controller layer (a proposal, like `kf_mpc_rt`).** Without it, controller 1 replans straight back into the sand that stopped it: 6–9 stops per episode, and it ends outside the base. `slip_aware(parent)` adds three things to any `KalmanMPCController`:

- **Trip chance per terrain.** The filter's slip belief, truncated to the published range, is updated by Bayes on every stop. A drive trips with q(s) = P(noise > L − s).
- **Routing.** While the chance is above 10%, routes pay to cross that terrain.
- **Dropping targets.** While it is above 30%, a target reachable only through it is dropped.

Without a slip check the layer is its parent, command for command (tested on controllers 1 and 24). Fresh seeds 800–879, share with rovers home out of 80:

| | c1 → c1 + layer | c24 → c24 + layer |
|---|---|---|
| `rush_noisy` 0.40 | 64.9 → 64.2 (74 → 73 home) | 65.1 → 64.7 |
| `rush_noisy` 0.35 | 61.6 → 65.0 (71 → 77) | 61.8 → 65.1 |
| `noisy` 0.42 | 78.8 → 78.8 (73 → 76) | 80.2 → 83.4 (72 → 77) |
| `noisy` 0.40 | 72.8 → 75.0 (66 → 73) | 74.8 → 78.8 (67 → 74) |
| `noisy` 0.35 | 54.1 → 75.0 (51 → 80) | 55.3 → 75.0 (51 → 80) |

It gains a lot where the check bites hard. It loses at most 1.5 points where the check hardly bites, because it detours around sand that would only trip now and then.

Tried and dropped:

- **Avoiding a terrain only after a stop:** the first stop is the expensive one.
- **Penalties scaled by the trip chance.**
- **Charging each leg its expected delay instead of dropping targets:** it also padded the legs home and gave up most targets.

**An executive on top (a proposal too): explicit modes switched by telemetry events,** like the rovers' fault protection or a behaviour tree's fallback node. The code is `executive(parent)` in `mars.py`. It has two modes:

- **`nominal`:** the slip-aware MPC, with one change. A target is dropped only once there is evidence about its terrain: a stop seen there, or a slip estimate with spread below 0.03. Before that, going for it is the cheapest probe.
- **`recover`:** entered after a slip stop when backing out is expected to be quicker than driving on.
  - **How it backs out:** one-segment drives, each uplinked only once the previous one has executed, so no stop can discard them. n steps cost n × (delay + 1) ticks.
  - **The alternative it compares against:** driving on costs (2 × delay + 1) × p / (1 − p) ticks with trip chance p.
  - **Where it goes:** the noise is drawn once per drive, so a drive that started outside the sand stopped at its first step inside. It backs out along its own tracks, 2 steps. A drive that started inside leaves through the nearest edge of the patch on the map.

  It returns to `nominal` when telemetry puts the rover on terrain that cannot trip. Every switch is logged in `mode_log` with its reason.

The failure this fixes: without it, a rover stopped at a sand edge replans along the edge. Position noise of 0.3 m and heading bias clip the sand again and again, 12 stops for nothing on noisy seeds 8 and 23. Development seeds also ruled out three alternatives:

- **A fixed trip-chance threshold for backing out:** it lost on seeds where the rover was metres inside.
- **A route clearance around avoided sand:** it cost up to 1.5 points on `rush_noisy` and gained nothing once backing out was right.
- **Treating cancelled commands as already free:** no effect.

Fresh seeds 900–979, controller 24 with the layer → with the executive (rovers home of 80):

| | 0.45 | 0.42 | 0.40 | 0.35 |
|---|---|---|---|---|
| `rush_noisy` | 72.5 → 72.5 | 70.7 → 71.4 (79 → 80) | 70.8 → 71.4 (77 → 80) | 68.4 → 69.1 (78 → 79) |
| `noisy` | 89.7 → 89.7 | 85.0 → 87.2 (79 → 80) | 80.3 → 88.8 (77 → 80) | 75.0 → 85.9 (80 → 80) |

- **Never worse than the layer.** Against plain controller 24 on `noisy`, it gains 11.5 points at 0.40 and 25.4 at 0.35.
- **What makes the gain:** at 0.40 and 0.42 it is all recovery (recovery alone: 88.8 and 87.2). At 0.35 it is all the evidence rule (recovery alone: 75.0, the same as the layer).
- **The keep-rule decisions above stand.** On `noisy` at 0.40 the gap to `solvi_reference` now shrinks by 2.4 points instead of 16.9, still just over the 2-point limit.
- **Controller 1 with the executive** scores within 0.3 points of controller 24 with it on `rush_noisy`. On `noisy` it is 1–3 points lower, the gap the two plain controllers already have.

Seeds 700–779, 800–879 and 900–979 are now used for these checks; don't reuse them as fresh seeds.

## Third increment: Manh controllers and swarm testing

[`lightlag_dynamic/manh_controllers/`](../lightlag_dynamic/manh_controllers/README.md) collects every meaningful controller combination built so far, named `<METHODS>_manh_controller_<N>`. Each entry records what the controller is, why it was built and what it showed. It also contains privileged-information bounds, candidate rule factors, a per-episode failure logger and a parallel swarm runner, so new controllers can be ranked on the same seeds.

About 90,000 scripted episodes were run on development seeds 0–19 at delays 0, 3 and 5, in three suites: the four profiles; one noise dial at a time; one candidate rule factor at a time. The scores are the share of the maximum, averaged over each suite.

- **Honest bounds.** A bound needs margins matched to its information. The first exact-information oracle used the stock planner (2.0 energy reserve, aiming at target centres) and scored below the Kalman filter. With a reserve of 0.5 and aiming at the disc it reaches 90.4% on the profiles, and 95.9% without delay, against 85.0% for `kf_mpc`.
  - Delay alone costs about 5.5 points even with perfect information.
- **Best real controller so far:** `CKF_aimdisc_turncost_window_MPC_manh_controller_20`. It averages 77.5% over the three suites, against 75.3% for `kf_mpc` (controller 1), and gets home in 97% of episodes. It combines:
  - a cubature Kalman filter;
  - legs aimed at the target disc;
  - turn energy in the budget;
  - decisions taken only inside uplink windows.
- **The estimator matters less than the planner.** On the plain profiles the EKF, particle filter, cubature filter and iterated smoother are within about 1 point of each other.
  - The particle and cubature filters pull ahead only at large position noise or noise level 3: 84% and 68% against 72% and 50% at delay 5.
  - Smoothing halves the error on past states but cannot improve the prediction a delayed command acts on.
- **The team references fall behind as noise rises.** Averaged over the noise suite, Sölvi's reference scores 47%, the blind plan 47% and Kristján's 21%; every Manh controller scores 74–77%.
  - Heading bias is the dial that best separates feedback from open-loop control: at a 20° bias the blind plan scores 6–9%.
- **Rule factors that break everything we have:**
  - **Hidden sand patches:** on `noisy`, Sölvi's worst-case budgets beat every Manh controller (68% vs at most 56% at delay 3).
  - **Uplink windows of 4 ticks in 16 on `rush_noisy`:** at delays 3 and 5 the blind plan, which sends everything at tick 0, wins (54–55% vs at most 45%).
  - **Turn cost:** at 0.03 per degree on `noisy`, delay 3, all three team references score 0%. Controllers 14 and 19–21, which budget turn energy, keep 75%.

**Held-out check, seeds 400–419.** Paired by episode against `kf_mpc`, with 95% intervals from a bootstrap over seeds:
- `EKF_aimdisc_turncost_window_MPC_manh_controller_19` gains +1.7 points (+1.4 to +2.0).
- Controller 20 gains +1.8 points (+1.4 to +2.2).
- 19 and 20 tie each other, so the gain comes from the planner additions, not the cubature filter.
- 19 needs no numpy, which makes it the candidate to replace `kf_mpc` as the reference. That is a team decision.

**Why Sölvi's reference wins with hidden sand.**
- It never attempts the third target: under noise its slip learner never fires, so it budgets the worst-case slip and keeps a 5-energy reserve.
- Ours take the third target with about 2 energy to spare, on a plan that trusts the published map, so a quarter of them die.
- Battery telemetry is noise-free and sand doubles the cost per wheel metre, so the battery reading measures exactly how many wheel metres each drive spent on sand.

**Hidden-sand fixes, controllers 22–25** ([details](../lightlag_dynamic/manh_controllers/README.md)). Built on 19, checked on held-out seeds 400–419:
- **22** reads unmapped sand off the battery and adds it to its own map. **23** never sends a command expected to empty the battery before the horizon, since alive away from base scores half and dead scores 0. **24** combines both. **25** adds map doubt: once the map is shown wrong, undriven bedrock on the way home is budgeted as possible sand.
- 24 is the best Manh controller on held-out seeds: +1.9 points over `kf_mpc` (+1.6 to +2.3), +0.2 over 19 (+0.1 to +0.4), and the same score as 19 on every published-profile episode.
- With two hidden patches on `noisy` it lifts 19 from 49% to 54% and cuts deaths from 27% to 20%. `solvi_reference` still wins there (68%, deaths 7%); ours win on `rush_noisy` and on clean maps.
- 25 cuts those deaths to 12% but gains only one point, and costs 0.4 points elsewhere: rare false odometer patches on clean maps switch the doubt on.

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
