# Fixed seed comparison: 501–504

14 November 2026. Sölvi / Codex orchestration of the team's delivered simulator,
Harbor task, KF + MPC reference and decision auditor.

## Predeclared protocol

The user approved the next comparison after Claude solved both seed-500 pilots.
This protocol and the claim in `TEAM_STATUS.md` were published as `02e4f70` before inspecting
any score on the new seed set. The choice is the next four consecutive seeds,
**501, 502, 503, 504**; no selection based on performance. Seed 501 was previously
used in a generator test at delay 5, not as a model outcome in this comparison.
Seed 500 remains pilot/development evidence and is excluded from these means.

Each seed is evaluated under **both `rush` and `rush_noisy`**, with delay **3**,
horizon **50**, noise level **1**, bumpiness **0** and the original **`kf_mpc`**
reference. No new Manh controller is substituted. Source and task hashes are
recorded before execution. All model sessions are fresh; no previous model
conversation, work files or reference implementation is given to the agent.

- Eight actual model attempts: OpenCode **1.19.5**,
  **`anthropic/claude-opus-5-5`**, one attempt per seed/profile, no retries,
  inherited 1,800-second agent timeout, at most two concurrent.
- Eight matched Harbor reference runs using the same generated task per cell.
  Check their scores against direct public-tool runs.
- Direct public-tool blind, whole-leg-waiting and no-op runs on every cell.
  These are supplemental controls, labelled direct rather than Harbor evidence.
- Run seeds in ascending order, both profiles per batch. Check completed-run
  API usage before each new batch; stop launching if cumulative reported cost
  reaches **$6** or a provider/authentication failure occurs. This is a launch
  guard, not a hard billing cap: calls already in progress can exceed it.
  Expected usage is roughly $4 based on the previous two attempts; grants and
  account balances are not independently verified.
- Retain every attempt, including low scores, timeouts and infrastructure
  failures. Do not retry or replace seeds after seeing their scores. Mark any
  unrun cells and the stopping reason explicitly.

## Verification and analysis

Generate all tasks at one clean source commit outside the checkout. Preserve
each `experiment.json`, Harbor lock/config, full agent trajectory and protected
replay/transcript, with credentials and machine paths excluded from the exports.
Check task hashes, source hashes, reference/model task-digest equality, rewards
across verifier/metadata/summary, and reported model identity/cost.

Use Manh's delivered decision auditor on every new model run. Its output goes
in an isolated `docs/lightlag-audits/fixed-seeds501-504/` directory, preserving
the existing audit index. Check replay reconstruction and distinguish
infrastructure faults from scored decisions. Interpret losses relative to
`kf_mpc`, not an optimal controller; retain negative gaps if Claude beats it.

Report all eight paired scores and per-profile means, model/reference gaps,
perfect-run counts, sample sizes, costs and any exceptions. This is four maps
and one model attempt per condition, not evidence of broad generalization or
run-to-run reliability. Difficulty tuning and final mission choice remain team
decisions. Do not change rules during this comparison.

## Reference verification

All eight generated tasks passed Harbor lint. They were generated from clean
commit `02e4f70`; every source-file hash matches the seed-500 pilots. Only the
predeclared seed/profile configuration and task name vary. Harbor **0.25.0**,
MCP **2.3.0**, Python **3.12.16**, Docker server **29.7.2**; container base tags
remain unpinned. No implementation code changed.

Eight Harbor reference runs reached tick 50, alive at base, with no execution
exceptions. All match their direct public-tool counterparts to reward-file
precision. The other three policies below were run directly, not in Harbor.

| Seed | Profile | KF + MPC (Harbor) | Blind (direct) | Whole-leg waiting (direct) | No-op (direct) |
|---|---|---:|---:|---:|---:|
| 501 | `rush` | [0.833333](lightlag-runs/rush-seed501-delay3-kf-mpc/) | 0.583333 | 0.583333 | 0.000000 |
| 501 | `rush_noisy` | [0.666667](lightlag-runs/rush-noisy-seed501-delay3-kf-mpc/) | 0.416667 | 0.541667 | 0.000000 |
| 502 | `rush` | [0.615385](lightlag-runs/rush-seed502-delay3-kf-mpc/) | 0.538462 | 0.538462 | 0.000000 |
| 502 | `rush_noisy` | [0.769231](lightlag-runs/rush-noisy-seed502-delay3-kf-mpc/) | 0.538462 | 0.269231 | 0.000000 |
| 503 | `rush` | [0.750000](lightlag-runs/rush-seed503-delay3-kf-mpc/) | 0.625000 | 0.593750 | 0.000000 |
| 503 | `rush_noisy` | [0.625000](lightlag-runs/rush-noisy-seed503-delay3-kf-mpc/) | 0.625000 | 0.406250 | 0.000000 |
| 504 | `rush` | [0.700000](lightlag-runs/rush-seed504-delay3-kf-mpc/) | 0.600000 | 0.575000 | 0.000000 |
| 504 | `rush_noisy` | [0.700000](lightlag-runs/rush-noisy-seed504-delay3-kf-mpc/) | 0.600000 | 0.275000 | 0.000000 |

These reference scores range from 0.615385 to 0.833333. A model score below 1.0
will not by itself demonstrate a model deficit: compare each with its matched
reference, and distinguish missed value from failures of the harness.
[Machine-readable reference and direct evidence](lightlag-runs/fixed-seeds501-504-summary.json).

## Execution status

Reference verification complete; **0 of 8 model attempts run**. Model outcomes
and audits will be published in ascending-seed batches. No model result is
inferred from these scripted controls.
