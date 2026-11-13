# Lightlag starter handoff

14 November 2026. Owner: Sölvi / Codex, worktree 6974. The first simulator slice is complete; claim a new scope in `TEAM_STATUS.md` before extending it.

## What is available

The [runnable prototype](../lightlag/README.md) contains a deterministic, headless rover simulation, a JSON-lines local runner and evaluator replay. The five public methods are `rules`, `map`, `telemetry_log`, `uplink` and `advance`. Sampling and reward use the simulator's true position. State reaches the controller only through delayed telemetry.

The user authorized development on the saved Lightlag draft. This implements the first bare-simulator slice of the existing brainstorm; it does not choose Lightlag for the team. The platform entry remains the editable draft recorded by Kristján in `TEAM_STATUS.md`. This work made no platform submission changes.

Published increments before the runner: task claim `e8461e9`, design/plan `475f5b1`, delay/movement core `d6de7ef`, mission/safety/scoring `6fad400`. Teammate research `d427ed7` was fast-forwarded into this worktree during development and preserved.

## Decisions to carry forward

- Python 3.9+ standard library; no credentials or installation needed. [Design](superpowers/specs/2026-11-13-lightlag-core-design.md) and [completed plan](superpowers/plans/2026-11-13-lightlag-core.md) record the rationale and scope.
- Constant one-way delay: sent at `t` → earliest execution at `t + k + 1`; state `s` → delivery at `s + k`. One execution per tick, initial launch state known at tick 0. Only `advance` moves time.
- Fixed episode horizon, including after battery death. Do not expose live termination or reclaim cancelled command reservations before telemetry reveals a stop.
- Flat 40 × 40 m fixed map, two terrain types, three targets. Hidden seeded terrain slip and tick-keyed noise. Exact visual odometry is a deliberate first-pilot simplification, not a claim about realistic sensing.
- Safety stops at hazards and map edges; no slope or embedding model yet. Samples collect the nearest unsampled target, once, within the configured radius. Sampling attempts and every tick cost energy.
- Raw score = sampled value × survival factor (1 at base, 0.5 alive elsewhere, 0 dead). No-op earns 0. Do not label maximum-map-value scaling as reference normalization; no reference score exists yet.
- Scripts are allowed to call public tools. The difficulty must survive code access; the team's [Harbor research](../afterquery-brainstorm.md#harbor-tool-access) makes this assumption explicit.

## Verification evidence

- 34 simulator/CLI tests passed with `python3 -m unittest discover -s tests/lightlag -v` under Python 3.9.6. Coverage includes delay 0/3, energy, atomic validation, hazard crossings, unseen queue cancellation, duplicate/false sampling, survival reward and malformed JSON recovery.
- Existing Junction Watch suite: 26 tests passed; its files were not changed.
- The documented CLI example completed: seed 7, delay 3, horizon 20; 8 successful protocol replies, 21 truth frames, last delivered state tick 17, sampled `west`, alive at base, raw score 1.0 and battery 75.0. Subprocess tests repeat the script at delays 0 and 3 and check identical replay output for repeated seed/script pairs.
- Independent review approved all three code increments. Two reproduced issues were corrected before publication: cardinal-direction floating-point drift at the map edge, and a deeply nested JSON request terminating the session. Both have regression tests.
- `git diff --check` passed. Generated telemetry/replay artifacts stayed outside the repository.

The example is an open-loop smoke test on one seed. It is not a reference controller, a baseline comparison or evidence that Lightlag exposes an agent weakness. No real-model calls have been made in this slice.

## Suggested next claims

1. **Honest reference and baselines** (`lightlag/controllers/`, a new evaluation script and tests). Consume only the five public methods; estimate slip from received wheel/visual odometry and track in-flight commands. Compare move-and-wait, nominal open-loop and stale-telemetry baselines over shared seeds. The shipped example does not fill this role.
2. **Simulator service / Harbor adapter** (a separately claimed adapter directory). Keep one persistent evaluator-seeded episode in a separate container; no agent reset or seed-selection method. Serialize calls, expose only the five public methods and keep replay, seed and coefficients out of the agent container. At verification, freeze agent access and advance the remaining horizon before scoring. Check the event starter kit's actual service/verifier connectivity; the teammate's Harbor findings are documentation-based, not yet a hands-on result.
3. **Replay viewer** (a separately claimed UI directory). The `lightlag-replay-v1` artifact contains `states`, `received_telemetry`, accepted `commands`, `world` and `result`. Show the current rover, last delivered position and commands in transit. A frame's `received_tick` is scheduled arrival, not proof that it was delivered before the horizon.
4. **Pilot and project decision**, after the service/reference exist. Run the zero/three-delay comparison on shared seeds with code access allowed, then real agent runs. Exact visual odometry makes slip identification easy in this slice; investigate noisy sensing or slope-dependent physics only with an explicit new design and fair ablations. Retain the team's provisional go/no-go criteria and alternatives.

No blocker prevents local simulator use. Reference quality, transport isolation, harness integration and real model evaluation remain unfinished project scope and must precede benchmark claims or final project selection.
