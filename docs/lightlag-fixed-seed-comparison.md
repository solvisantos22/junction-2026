# Fixed seed comparison: 501–504

14 November 2026. Sölvi / Codex orchestration of the team's delivered simulator,
Harbor task, KF + MPC reference and decision auditor.

## Predeclared protocol

The user approved the next comparison after Claude solved both seed-500 pilots.
This protocol and the claim in `TEAM_STATUS.md` are published before inspecting
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

## Execution status

Predeclared; no new outcomes yet. Publish verified reference evidence first,
then model results and audits in small increments. Final handoff will state
what the measured gaps support and which decisions remain open.
