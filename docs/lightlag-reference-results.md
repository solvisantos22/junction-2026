# Lightlag shared comparison: two controller families

14 November 2026. Owner: Sölvi / Codex. **480 scripted episodes completed without execution errors; no real model was run.** Lightlag and its final rules remain provisional.

The adaptive controller in `lightlag_controllers/` is the stronger current fixed-map reference: mean raw score 3.8/4 at delay 0 and 3.9/4 at delay 3 on development seeds, then 4/4 at both delays on the separate check. It returned alive in all 40 reference episodes. The conservative `lightlag/controllers/` reference scored 3/4 throughout, tying both blind planners. Concentrate future reference work in the team package; retain the conservative implementation for diagnostics.

## Reproducible evidence

- Frozen code: `934735ea9f0222d5b5ab73aa021fabe3f0e7e313`, Python 3.9.6, standard library only.
- [Manifest, full rules/map and aggregates](lightlag-results/manifest.json).
- [Development raw rows](lightlag-results/development-scores.csv): seeds 0–9, 240 episodes.
- [Separate check raw rows](lightlag-results/frozen-check-scores.csv): seeds 200–209, 240 episodes.
- Default fixed 40 × 40 map, maximum science value 4, horizon 80, initial battery 100, idle drain 0.5/tick, sampling/base radii 0.75 m; delays 0 and 3. Physics and scoring were unchanged.

Each policy/seed/delay starts a fresh environment through `run_episode`, receives only the five public callbacks and is graded at tick 80 even after returning early or dying. Policy/tool errors fail the batch instead of becoming scores. All 480 evaluator replays were checked against their score rows, configuration, schema and 81-frame horizon.

The check set was first run in this slice after freezing the implementation. It replaces the originally planned 100–109 set because Manh's separate dynamic pilot already used 100–139. No controller, physics or reward changes followed these check results. This is another ten hidden-slip/noise seeds on the same map, not held-out map generalization or a claim of unseen seeds across every teammate's work.

## Raw scores

Means over ten seeds per column. `reference` and other unprefixed names are the conservative family; `team_` names adapt Kristján's policies into the shared runner.

| Policy | Development, delay 0 | Development, delay 3 | Check, delay 0 | Check, delay 3 |
|---|---:|---:|---:|---:|
| `reference` | 3.00 | 3.00 | 3.00 | 3.00 |
| `move_and_wait` | 3.00 | 2.60 | 3.00 | 2.90 |
| `nominal_open_loop` | 3.00 | 3.00 | 3.00 | 3.00 |
| `stale_telemetry` | 3.00 | 0.00 | 3.00 | 0.00 |
| `do_nothing` | 0.00 | 0.00 | 0.00 | 0.00 |
| `stop_early` | 3.00 | 2.85 | 3.00 | 2.85 |
| `team_reference` | 3.80 | 3.90 | 4.00 | 4.00 |
| `team_move_and_wait` | 3.80 | 3.00 | 4.00 | 3.00 |
| `team_stale_telemetry` | 3.80 | 0.00 | 4.00 | 0.00 |
| `team_open_loop_nominal` | 3.00 | 3.00 | 3.00 | 3.00 |
| `team_stop_early` | 0.50 | 0.00 | 0.50 | 0.00 |
| `team_no_op` | 0.00 | 0.00 | 0.00 | 0.00 |

The adaptive reference's three partial development runs were seed 2 at both delays and seed 6 at delay 0 (score 3 each); all other reference runs scored 4. It is a heuristic, not an optimum.

Reference ratios use **`team_reference` on the matching seed and delay**, then average those ratios. Both blind planners average 80% / 77.5% on development delays 0 / 3, and 75% / 75% on the check. Team move-and-wait averages 100% / 77.5% and 100% / 75%, respectively. Every group has ten defined ratios and zero undefined ratios. The runner retains null plus a reason for zero/missing reference scores and does not clip ratios above 1.

These ratios differ from the older [pilot's](lightlag-pilot.md) ratio-of-means metric. For example, development blind planning at delay 0 is a mean per-seed ratio of 80%, while 3.0 / 3.8 is about 78.9%. Raw scores match that pilot's default-map results; its varied-map and harder-physics studies are separate experiments.

## Survival, return and traces

Return rate means alive **and** at base; it does not itself imply any science was collected. Both references and both blind planners returned alive in every episode. The no-op policies also stayed alive at base while scoring zero.

- At delay 3, the conservative stale policy survived every run but returned in 0/10 development and 2/10 check runs, collecting no science. The team stale policy survived 0/10 development and 2/10 check runs, returned in none and also scored zero. All other policies survived every run.
- Local stop-early returned in 9/10 runs at delay 3 in each set; at delay 0 it completed its mission before stopping and tied the local reference. Team stop-early returned in none. These are different probes: local stops after the first quarter-horizon, team after tick 5, and already queued commands can still execute. A completed mission before a cutoff is not an early-exit exploit.
- Both move-and-wait policies returned alive in every run. They wait after **one command**; they do not establish what a capable controller that batches a whole leg can achieve. Manh's [dynamic pilot](lightlag-dynamic-pilot.md) supplies that stronger cautious comparison separately.

Representative development seed 0, delay 3 replays:

| Policy | What the trace shows | Replay basename in the generated `replays/` directory |
|---|---|---|
| `team_reference` | Samples east at tick 12, north at 21, west at 25; returns alive with score 4 and final battery about 3.80 | `000130__team_reference__seed-0__delay-3.json` |
| `team_stale_telemetry` | Hits the map boundary at tick 10, battery depletes at 22, no samples | `000170__team_stale_telemetry__seed-0__delay-3.json` |
| `stale_telemetry` | Repeated hazard stops; 65 accepted commands, no samples, alive elsewhere with about 1 battery | `000070__stale_telemetry__seed-0__delay-3.json` |
| `stop_early` | Samples north and west but ends away from base; sampled value 3 receives the alive-away factor 0.5, score 1.5 | `000110__stop_early__seed-0__delay-3.json` |

Every survivor pays the same full-horizon idle drain of 40. Waiting loses action opportunities, not additional total idle energy. Shared seeds preserve terrain coefficients and the temporal noise field, but changing execution ticks changes the noise each drive encounters; this is not perfect isolation of delay from realized action noise.

## Repeat the matrices

Run from the repository root at the frozen revision to reproduce these CSVs. Each output directory must be new. The checked-in manifest contains SHA-256 hashes of the exact exported CSV bytes; full replays are generated artifacts and are not checked in.

```sh
lightlag_results_parent="$(mktemp -d)"
python3 -m lightlag.evaluation \
  --seeds 0 1 2 3 4 5 6 7 8 9 --delays 0 3 --ticks 80 \
  --policies reference move_and_wait nominal_open_loop stale_telemetry do_nothing stop_early \
    team_reference team_move_and_wait team_stale_telemetry team_open_loop_nominal team_stop_early team_no_op \
  --reference-policy team_reference --output-dir "$lightlag_results_parent/development"
python3 -m lightlag.evaluation \
  --seeds 200 201 202 203 204 205 206 207 208 209 --delays 0 3 --ticks 80 \
  --policies reference move_and_wait nominal_open_loop stale_telemetry do_nothing stop_early \
    team_reference team_move_and_wait team_stale_telemetry team_open_loop_nominal team_stop_early team_no_op \
  --reference-policy team_reference --output-dir "$lightlag_results_parent/frozen-check"
```

The batch API/CLI passed 99 core/controller/evaluation tests and 25 teammate-controller tests, independent specification and quality review, and separate CLI smoke checks. [Run and API instructions](../lightlag/README.md) · [Handoff and replay contract](lightlag-handoff.md).

## Decisions and next experiment

Use the adaptive team controller as the current fixed-map denominator and freeze further conservative-planner development. Keep both implementations and the raw results. The CLI's original default names remain unchanged for reproducibility; select `--reference-policy team_reference` when comparing against this stronger candidate.

Do not infer frontier-agent difficulty from a deliberately stale or single-command-waiting policy. The useful next measurement is real agents through the [MCP service](lightlag-mcp.md), with scripting allowed, a strong reference, blind planning and whole-leg waiting. Manh's deadlines/discoveries/time-pressure variant is a promising separate candidate; it needs an explicit rules decision and an appropriate reference. A small fixed map and exact visual odometry remain major limits. The final project and rule set are still open.
