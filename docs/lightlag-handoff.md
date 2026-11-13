# Lightlag development handoff

14 November 2026. Owner: Sölvi / Codex, worktree 6974. Check `TEAM_STATUS.md` for live ownership before extending a component.

## What is available

The [runnable prototype](../lightlag/README.md) contains a deterministic, headless rover simulation, a JSON-lines local runner, evaluator replay and a public-tool policy runner. The five public methods are `rules`, `map`, `telemetry_log`, `uplink` and `advance`. Sampling and reward use the simulator's true position. State reaches the controller only through delayed telemetry.

There are two tested controller families after overlapping claims reached `main`: the conservative implementation in `lightlag/controllers/` and Kristján's adaptive route planner in `lightlag_controllers/`. Both run through `lightlag.evaluation.run_episode`; use `lightlag_controllers.as_policy(strategy)` for the latter. Further development of the conservative planner is frozen. Preserve it as an independent diagnostic implementation, and build future reference improvements in one team-owned controller package after claiming them.

The user authorized development on the saved Lightlag draft. This implements the first bare-simulator slice of the existing brainstorm; it does not choose Lightlag for the team. The platform entry remains the editable draft recorded by Kristján in `TEAM_STATUS.md`. This work made no platform submission changes.

Published increments before the runner: task claim `e8461e9`, design/plan `475f5b1`, delay/movement core `d6de7ef`, mission/safety/scoring `6fad400`. Teammate research `d427ed7` was fast-forwarded into this worktree during development and preserved.

The public-tool runner was published as `73098c6`, conservative controllers as `6e580fc`, and the shared evaluation ownership decision as `ea0c353`. Kristján's controller/adapter and Manh's dynamic-pilot findings were integrated without replacing their files.

The batch CLI/API was published as `934735e`. The [shared comparison](lightlag-reference-results.md) records 480 episodes across both families, development seeds 0–9 and separate check seeds 200–209, with checked-in raw CSVs and a complete rules/map manifest. Use `team_reference` as the stronger current fixed-map denominator: it returned alive in all 40 reference episodes and averaged 3.8/3.9 on development delays 0/3, then 4/4 on the check. This selects a comparison baseline, not the final project or rules.

## Decisions to carry forward

- Python 3.9+ standard library; no credentials or installation needed. [Design](superpowers/specs/2026-11-13-lightlag-core-design.md) and [completed plan](superpowers/plans/2026-11-13-lightlag-core.md) record the rationale and scope.
- Constant one-way delay: sent at `t` → earliest execution at `t + k + 1`; state `s` → delivery at `s + k`. One execution per tick, initial launch state known at tick 0. Only `advance` moves time.
- Fixed episode horizon, including after battery death. Do not expose live termination or reclaim cancelled command reservations before telemetry reveals a stop.
- Flat 40 × 40 m fixed map, two terrain types, three targets. Hidden seeded terrain slip and tick-keyed noise. Exact visual odometry is a deliberate first-pilot simplification, not a claim about realistic sensing.
- Safety stops at hazards and map edges; no slope or embedding model yet. Samples collect the nearest unsampled target, once, within the configured radius. Sampling attempts and every tick cost energy.
- Raw score = sampled value × survival factor (1 at base, 0.5 alive elsewhere, 0 dead). No-op earns 0. Reference normalization requires a named reference on the same seed, delay, rules and map; maximum-map-value scaling is a different quantity. A zero or absent reference score has an undefined ratio.
- Scripts are allowed to call public tools. The difficulty must survive code access; the team's [Harbor research](../afterquery-brainstorm.md#harbor-tool-access) makes this assumption explicit.
- Controllers receive five callbacks, not the environment or seed. This is an auditable dependency boundary for trusted Python code, not protection against malicious introspection. `run_episode` finishes the horizon after an early return; it also fails visibly on invalid tool calls even when a controller catches the exception.
- Default physics remain unchanged. The conservative reference avoids sand and scores only partial science; its nominal-open-loop tie is a limitation of that planner, not proof that all telemetry is useless. Kristján's [pilot](lightlag-pilot.md) tests a stronger planner and separate varied-map/physics variants. Manh's dynamic-rules study adds a different information/time constraint. Keep these studies separate until their rules and controllers are compared explicitly.

## Verification evidence

Controller/evaluator continuation: 99 core/controller/evaluation tests pass under Python 3.9.6, including deterministic comparisons, reference-ratio edge cases, preflight validation and exclusive artifact exports. Kristján's 25 controller tests also pass. A separate CLI smoke run completed 48 full-horizon episodes across all twelve policies; every exported replay matched its score row. After integration, Manh's 12 dynamic tests and 10 dependency-free MCP service tests pass. Eight MCP transport tests were skipped in this Python environment because the optional SDK is absent; Kristján's handoff records his own SDK-backed verification.

Independent specification and quality review approved the batch implementation. Its full comparison completed 480 episodes without execution errors and verified every replay's schema, seed, delay, score and 81-frame horizon. No controller or rule tuning followed the separate check.

The later evaluator-factory integration brings the core/controller/evaluation suite to 105 tests, with independent specification and quality approval. Its dynamic `rush` example on development seed 3 agrees with the pilot runner's full result and replay; the documented example returns alive with raw score 8 at tick 50. Default-versus-explicit construction produces identical complete episode output. The batch contract and the frozen comparison data remain unchanged.

- 34 simulator/CLI tests passed with `python3 -m unittest discover -s tests/lightlag -v` under Python 3.9.6. Coverage includes delay 0/3, energy, atomic validation, hazard crossings, unseen queue cancellation, duplicate/false sampling, survival reward and malformed JSON recovery.
- Existing Junction Watch suite: 26 tests passed; its files were not changed.
- The documented CLI example completed: seed 7, delay 3, horizon 20; 8 successful protocol replies, 21 truth frames, last delivered state tick 17, sampled `west`, alive at base, raw score 1.0 and battery 75.0. Subprocess tests repeat the script at delays 0 and 3 and check identical replay output for repeated seed/script pairs.
- Independent review approved all three code increments. Two reproduced issues were corrected before publication: cardinal-direction floating-point drift at the map edge, and a deeply nested JSON request terminating the session. Both have regression tests.
- `git diff --check` passed. Generated telemetry/replay artifacts stayed outside the repository.

The example is an open-loop smoke test on one seed. It is not a reference controller, a baseline comparison or evidence that Lightlag exposes an agent weakness. No real-model calls have been made in this slice.

## Next work and ownership

1. **Service and real-agent pilot:** Kristján's first [MCP server](lightlag-mcp.md) is published; coordinate with his `lightlag_mcp/` claim. Keep one evaluator-seeded episode outside the agent container, expose only the five tools, and keep seed, hidden coefficients, score and replay private. At verification, freeze access and finish the horizon. His handoff records an unbuilt container and official Harbor wiring awaiting the organizers' starter kit; verify those separately before promising harness compatibility. First real runs should allow scripts and compare against a strong reference and blind planning at the same budgets.
2. **Dynamic-rules integration:** Manh's [dynamic pilot](lightlag-dynamic-pilot.md) is published under his `lightlag_dynamic/` claim. His findings favor testing deadlines/discoveries/time pressure before combining every harder-physics variant. Treat that as experimental evidence, not an adopted rule set. The shared `run_episode` now accepts an evaluator-only `environment_factory`; the [API example](../lightlag/README.md#run-a-policy-through-public-tools) runs a dynamic episode without replacing a module global. His package is preserved; its owner can migrate the existing cross-check to this hook. Deadline/discovery support in the team reference still needs a coordinated claim. Add a whole-leg-then-wait baseline: one-command-then-wait is a deliberately weak form of caution.
3. **Replay viewer:** claim a separate UI directory. The `lightlag-replay-v1` artifact contains `states`, `received_telemetry`, accepted `commands`, `world` and `result`. Show true rover position, last delivered position, pending commands and battery/science over time. A frame's `received_tick` is scheduled arrival, not proof of delivery before the horizon. Replays reveal hidden truth and belong only on the evaluator/viewer side.
4. **Rules and project decision:** compare real-agent traces, blind planning and a capable cautious controller before choosing a harder rule set or the final project. Exact visual odometry, a small fixed map and hand-picked difficulty parameters limit the current evidence. Keep the team's alternatives available.

Local use is unblocked. Transport isolation, official harness integration and real-model evidence remain unfinished project scope; no scripted pilot establishes a frontier-agent gap.

## Replay consumer contract

The batch summary's `replay_file` resolves relative to its output directory. Load the file as `lightlag-replay-v1`; no conversion is needed. At playback tick `t`, show the truth frame whose `tick` is `t` and the newest item in `received_telemetry` with `received_tick <= t`. Do not reveal a truth frame as telemetry merely because its scheduled arrival is recorded. Initial briefing tick 0 is available immediately.

`commands` records accepted acknowledgements, including commands that may later be cancelled. Confirm execution with a state's `command_executed` event and `command_id`; a reserved execution tick alone is not proof of execution. `safety_stop` and `battery_depleted` explain lost queued work. `sample_taken` records successful collection and `sample_failed` records unsuccessful attempts. The delayed observation track is available; a controller's private believed position is not currently exported, so label those two concepts distinctly.
