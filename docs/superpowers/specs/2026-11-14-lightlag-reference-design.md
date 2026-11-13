# Lightlag reference and evaluation slice

Approved direction: the user accepted the next development block on 14 November. This work owns the reference controller, scripted baselines and evaluation runner. The simulator service, official harness and viewer remain separate teammate scopes. Lightlag remains provisional.

## Objective and choices

Produce a reproducible controller comparison on the current simulator, using identical public information and episode budgets. The reference should learn terrain slip from delayed observations, predict the effect of queued commands, collect science and return to base. Its score is a demonstrated algorithmic result, not proof of optimality or a frontier-agent gap.

Use a controller that predicts queued motion and updates from telemetry. A full model-predictive optimizer would add optimization infrastructure before we have a useful baseline; a fixed command script would not generalize across hidden coefficients or demonstrate learning. A small waypoint planner with learned slip and conservative return budgeting is the first reference. Keep the simulator's existing physics and reward unchanged during this experiment.

## Public interface and evaluator boundary

Controllers receive a `PublicTools` object exposing only `rules`, `map`, `telemetry_log`, `uplink`, and `advance`. They receive neither an Environment instance nor a seed, true state, evaluator result, replay or hidden coefficients. Controllers read constants and terrain bounds from public rules/maps, not simulator internals. The object is an auditable dependency boundary, not a security sandbox against malicious Python introspection.

`run_episode(policy, seed=..., config=..., world=..., policy_name=...)` belongs to evaluator code. It constructs one fresh environment per run, invokes the policy through PublicTools, then advances any remaining ticks to the fixed horizon before grading. This prevents early returns from escaping idle drain. Invalid public requests and policy exceptions fail the run visibly; they must not become a low score misreported as agent weakness. Keep a transcript of public calls/results and counts, alongside the existing evaluator replay.

All policy state is fresh for each episode. No policy is told a seed or allowed to rehearse it. Evaluator result/replay can include seed and configuration for reproducibility, outside the controller boundary.

## Controller mechanics

The reference reads the public map, rule family and initial briefing. Start terrain-slip estimates at the midpoint of the published ranges. From received drive telemetry, estimate slip using wheel and visual distance only when the observed leg is entirely on one terrain and has no safety stop or energy truncation. Learn from ordinary useful movement first; this version does not require a separate calibration phase. Maintain a deterministic weighted estimate within the published range.

Keep acknowledged command IDs, sent ticks and execution ticks. Process every newly received packet for learning and safety events, then anchor the model at the most recent received state and replay still-unobserved commands up to the next command's execution slot. Include idle energy, terrain-dependent wheel energy and estimated sampling outcomes. Reconcile with actual telemetry when it arrives. On an observed safety stop at state tick `s`, cancel only outstanding commands with `sent_tick < s`; commands sent at `s` or later survive, even if they were sent before the stop telemetry arrived. Retain the public reserved schedule.

Plan routes around visible hazard rectangles with a small safety margin, using a visibility graph or comparably small deterministic path search. Choose useful targets using public values, travel/energy estimates and the cost of returning home. Reserve idle energy through the full horizon, not merely until arrival at base, and retain a strictly positive terminal energy margin. Include unobserved queued actions and avoid double-counting ticks already included in the predicted state. Use estimated slip to turn geometric distance into wheel distance, obey command limits, and correct from received packets. Near targets/base, aim inside the allowed radius with margin. Stop sending when no safe/feasible target remains, when return is necessary, or when the next execution slot exceeds the horizon.

The reference need not be optimal or solve every custom map. It must return useful science reliably on the current map over development seeds at delays 0 and 3, avoid hidden-state access, and handle no targets, low energy, short horizons and an obstructed route without crashing. Report poor performance honestly; do not tune reward/physics to manufacture an ordering.

## Baselines

| Policy | Difference from reference |
|---|---|
| `reference` | Learned slip, delayed-state correction, queued-command prediction and return budget |
| `move_and_wait` | Similar navigation, but wait for a command's telemetry before the next decision |
| `nominal_open_loop` | Published midpoint slip, planned motion without later telemetry correction; no hidden truth |
| `stale_telemetry` | Treat the last received position as current, ignoring pending motion; retain the same valid public actions |
| `do_nothing` | Issue no commands; evaluator still completes the horizon |
| `stop_early` | Follow the reference for the first quarter of the horizon, then return control; evaluator completes the rest |

Names must match behavior. The intentionally weaker policies are diagnostic ablations, not frontier models. Do not promise that every policy ordering will hold on every seed.

All surviving policies pay the same full-horizon idle drain. Move-and-wait therefore loses action opportunities before the deadline, not additional total idle energy. If the reference completes the mission before the quarter-horizon cutoff, `stop_early` may legitimately match it; label that probe uninformative rather than calling completed work a reward exploit.

## Evaluation and artifacts

### Integration decision after the overlapping controller work landed

Kristján's separately implemented controllers and `as_policy` adapter arrived while task 2 was in progress. Preserve both tested implementations; freeze further work on the conservative `lightlag/controllers/` planner. This slice owns the shared evaluator, not Kristján's controller package or pilot. Compare both families under identical default-map configurations before selecting a reference for subsequent experiments. His existing varied-map pilot is a separate study and must not be pooled with these default-map results.

The batch API accepts an ordered mapping of policy names to callables and an explicit `reference_policy` name. The CLI keeps the six existing local policy names for its default selection and also offers Kristján's six strategies under `team_` prefixes through `as_policy`. `--reference-policy` selects the denominator, defaulting to `reference`. Our published comparison selects all twelve and uses `team_reference` as the candidate stronger denominator. This naming preserves reproducible local commands while avoiding an implicit replacement of a library callable. All ratios identify their denominator; a higher score does not establish optimality. Stop-early policies use different cutoffs (quarter-horizon versus tick 5), so they are distinct probes, not matched ablations across families.

No rule changes are included. The pilot's suggested harder variants and the real-agent test need separate decisions and evidence after the service is available.

Provide `python3 -m lightlag.evaluation` with configurable integer seeds, delays, horizon, policy selection and an optional new output directory. Default comparison uses seeds 0–9 and delays 0 and 3 at horizon 80. Reject duplicate policies/seeds/delays and invalid configurations before running. No paid APIs or model credentials are involved.

Each run records policy, seed, delay, raw reward, sampled value, survival/return status and public tool-call count. Aggregate mean/min/max raw score and return/survival rates by policy and delay. If a matching positive reference score exists, report the per-seed raw-score ratio without clipping. A zero/missing reference denominator produces null with a reason, never a fabricated zero, infinity or silent omission. Keep raw results available.

The optional output directory must not already exist. Write `summary.json`, `scores.csv`, and one unchanged `lightlag-replay-v1` file per policy/seed/delay, plus public-call transcripts if useful for review. A manifest must identify the experiment configuration and simulator version. Deterministic inputs must yield deterministic scientific results; omit elapsed time from equality-sensitive results. Never overwrite earlier experiments.

After freezing the implementation, run a separate check on seeds 200–209 and report it separately from development seeds. The original 100–109 selection was replaced before this slice ran it because Manh's separately published dynamic pilot already used 100–139. This is a smoke test of generalization across hidden slip/noise on one fixed map, not a held-out map benchmark or a claim that no teammate has ever inspected these seeds elsewhere. If those results motivate changes, label subsequent runs as development rather than continuing to call them untouched check results.

Shared seeds preserve terrain coefficients and the temporal noise field. Because drive noise is keyed by execution tick, changing policy timing or delay changes which noise each drive encounters. Describe the experiment as paired-seed policy comparisons, not perfect isolation of delay from realized action noise.

## Acceptance and handoff

- A restricted fake public API can run the policies; controller files import no simulator Environment/model/evaluator and access no private state.
- Tests reproduce delayed prediction, slip updates and cancellation semantics from synthetic public packets; integration tests verify useful science and a return on representative seeds without asserting a universal baseline ordering.
- The evaluator reaches the horizon even if a policy stops early. Each run starts fresh. Errors remain visible.
- The command produces repeatable summaries and valid replay files consumable by the existing replay schema.
- Publish measured development and separate check results, exact commands, limitations and next integration points. Do not call scripted gaps real-agent evidence.

## Evaluator factory integration follow-up

Manh's published dynamic-pilot cross-check currently replaces `lightlag.evaluation.Environment` temporarily. Add an optional trusted `environment_factory` to `run_episode` so integrations can construct an episode explicitly instead. It receives the evaluator's `seed` plus deep-copied `config` and `world` keywords and returns a fresh environment supporting the five public methods and evaluator-only `evaluate`/`replay`. With no factory, resolve the existing `Environment` at call time for unchanged default behavior and compatibility with existing callers.

This is evaluator construction plumbing: policies still receive only the five callbacks, early returns still consume the full horizon read from public rules, and errors still propagate. A small wrapper can translate the generic factory arguments into `DynamicEnvironment(profile=...)`. Do not change the teammate's dynamic package, scoring, controllers or service in this increment. The batch API/CLI stays fixed-map; supporting varying maps would require per-run world metadata instead of implying one shared world. Providing this hook does not adopt a dynamic rule profile.
