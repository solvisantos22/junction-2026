# Fixed seed comparison: 501–504

14 November 2026. Sölvi / Codex orchestration of the team's delivered simulator,
Harbor task, KF + MPC reference and decision auditor.

**All eight attempts completed: three model wins, two ties and three deficits
against the frozen reference.** Two battery-exhaustion failures and one
queue-management deficit are supported by exact replay audits; no infrastructure
faults were found. Mean reward favors the reference in both profiles, although
it does not consistently beat Claude. Reported API usage: **$3.3513574**.

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

An independent Codex reviewer reproduced all 32 direct controls exactly and
checked the eight Harbor exports against raw artifacts, source/task hashes,
score records and credential/path scans. Reference evidence was published as
`5925236` before starting the model attempts.

## Reproduce

For each seed in 501–504 and each profile in `rush`, `rush_noisy`, generate a
fresh task outside the checkout. The commands below illustrate one cell;
repeat with distinct task/job directories. Use the task's recorded source
commit when reproducing this comparison, and pass your local credentials-file
path in place of `.env`. Never commit that file.

```sh
python3 tools/lightlag_experiments/prepare.py /tmp/lightlag-rush-501 \
  --profile rush --seed 501 --delay 3 --policy kf_mpc
harbor lint /tmp/lightlag-rush-501
harbor run -p /tmp/lightlag-rush-501 -a oracle \
  --jobs-dir /tmp/lightlag-fixed-jobs --job-name rush-501-reference \
  --n-concurrent 1 --n-attempts 1 --max-retries 0
harbor run -p /tmp/lightlag-rush-501 -a opencode \
  -m anthropic/claude-opus-5-5 --ak version=1.19.5 --env-file .env \
  --jobs-dir /tmp/lightlag-fixed-jobs --job-name rush-501-opus \
  --n-concurrent 1 --n-attempts 1 --max-retries 0
```

The supplemental direct rows use `lightlag_dynamic.tools.run_episode` and
`lightlag_dynamic.controllers.POLICIES` for `kf_mpc`, `open_loop`, `leg_and_wait`
and `do_nothing`, with the exact settings above. Full result dictionaries and
public tool-call counts are retained in the summary JSON.

After sanitizing a completed model run into its evidence folder, audit that
folder with `python3 -m lightlag_audit <run-folder> --out <separate-audit-dir>`.
The auditor's index contains the supplied runs only, so this comparison uses
its own directory and retains the team's existing audit index.

## Complete model results

**8 of 8** predeclared attempts complete, with no retries, replaced seeds,
unrun cells or execution exceptions. Each used the pinned agent/model and the
same task digest and manifest as its matched reference. All eight sessions are
distinct and fresh. The reported-cost launch guard was never reached.

| Seed | Profile | Claude reward | Reference reward | Reference − Claude | Rover calls | Reported USD | Audit |
|---|---|---:|---:|---:|---:|---:|---|
| 501 | `rush` | [0.000000](lightlag-runs/rush-seed501-delay3-opus-5-5/) | 0.833333 | +0.833333 | 19 | 0.4185480 | [Report](lightlag-audits/fixed-seeds501-504/rush-seed501-delay3-opus-5-5/audit.md) |
| 501 | `rush_noisy` | [0.791667](lightlag-runs/rush-noisy-seed501-delay3-opus-5-5/) | 0.666667 | -0.125000 | 32 | 0.7105792 | [Report](lightlag-audits/fixed-seeds501-504/rush-noisy-seed501-delay3-opus-5-5/audit.md) |
| 502 | `rush` | [0.769231](lightlag-runs/rush-seed502-delay3-opus-5-5/) | 0.615385 | -0.153846 | 22 | 0.2967346 | [Report](lightlag-audits/fixed-seeds501-504/rush-seed502-delay3-opus-5-5/audit.md) |
| 502 | `rush_noisy` | [0.634615](lightlag-runs/rush-noisy-seed502-delay3-opus-5-5/) | 0.769231 | +0.134615 | 23 | 0.3621726 | [Report](lightlag-audits/fixed-seeds501-504/rush-noisy-seed502-delay3-opus-5-5/audit.md) |
| 503 | `rush` | [0.750000](lightlag-runs/rush-seed503-delay3-opus-5-5/) | 0.750000 | +0.000000 | 28 | 0.3497882 | [Report](lightlag-audits/fixed-seeds501-504/rush-seed503-delay3-opus-5-5/audit.md) |
| 503 | `rush_noisy` | [0.750000](lightlag-runs/rush-noisy-seed503-delay3-opus-5-5/) | 0.625000 | -0.125000 | 31 | 0.4802570 | [Report](lightlag-audits/fixed-seeds501-504/rush-noisy-seed503-delay3-opus-5-5/audit.md) |
| 504 | `rush` | [0.700000](lightlag-runs/rush-seed504-delay3-opus-5-5/) | 0.700000 | +0.000000 | 29 | 0.3154634 | [Report](lightlag-audits/fixed-seeds501-504/rush-seed504-delay3-opus-5-5/audit.md) |
| 504 | `rush_noisy` | [0.000000](lightlag-runs/rush-noisy-seed504-delay3-opus-5-5/) | 0.700000 | +0.700000 | 27 | 0.4178144 | [Report](lightlag-audits/fixed-seeds501-504/rush-noisy-seed504-delay3-opus-5-5/audit.md) |

Positive gaps favor the reference; negative gaps favor Claude. Means below use
unrounded raw score / maximum, with equal weight per map. Each profile has four
maps and one fresh model attempt per map; there are no repeated model trials.

| Profile | Attempts | Mean Claude | Mean reference | Mean reference − Claude | Model wins / ties / deficits | Perfect model runs |
|---|---:|---:|---:|---:|---|---:|
| `rush` | 4 | 0.554808 | 0.724679 | +0.169872 | 1 / 2 / 1 | 0 |
| `rush_noisy` | 4 | 0.544071 | 0.690224 | +0.146154 | 2 / 0 / 2 | 0 |

Reported API cost for these eight attempts is **$3.3513574**. Including the two
previous seed-500 pilots (**$0.946363**), this chat's ten recorded model attempts
report **$4.2977204**. These are saved agent usage reports, not independently
checked invoices or credit balances; Kristján's earlier seed-7 run is separate.

## Decision-audit observations

On **rush seed 501**, Claude collected all seven targets (10.5 of 12 available
points before the survival multiplier), returned home at tick 25 with battery
11.521, and exhausted the battery at tick **49**. The published idle drain is
0.5 per tick through horizon 50; stopping at base does not stop that drain.
The final reward is therefore **0.0**, versus KF + MPC's **10/12**.

The auditor localizes the reference-relative 10-point loss to **call 11 at tick
15**, which committed to a detour for discovery d1. Its sample executed at tick
23, after deadline 21. The audit labels that late sample; the terminal zero is
caused by exhaustion of the full-horizon energy budget, not by lateness alone.
Its alternative skips d1 and finishes alive at home with 10 points. This is
attribution under the KF + MPC continuation, not proof that zero reward became
irreversible at call 11. A [post-hoc salvage check](lightlag-audits/fixed-seeds501-504/rush-seed501-delay3-opus-5-5/salvage-check.json)
replays through call 11 or 12 and sends nothing further: the rover survives
away from base with 6.041 battery and **5.25/12** after the away-from-base
multiplier. After call 13's homeward uplink, the same continuation dies. The replay
shows battery 0.021 at tick 48 and zero at 49. Claude's final self-report admits
the missing energy budget but misstates target totals as 11.5/14; this report
uses the protected evaluator's **10.5/12**, not that arithmetic.

On **rush_noisy seed 501**, Claude scored **9.5/12**, above the reference's **8/12**,
and survived at base. The auditor lists no main mistakes relative to that
reference. The noise condition is a separate fresh model attempt; this pair
alone does not show that noise improves performance or isolate stochastic
model behavior from profile effects.

On **rush seed 502**, Claude scored **10/13**, above KF + MPC's **8/13**,
finishing alive at home. On **rush_noisy seed 502**, it scored **8.25/13** against
**10/13**, again alive at home. The noisy audit identifies **call 10**, an
`advance(5)` from tick 12 to 17: the existing queue ends at tick 14, so waiting
pushes the next possible execution to tick 21. The reference could queue a
sample at tick 12 and execute it at 16. Under that reference continuation the
wait loses 2.25 raw points; call 11 recovers 0.5, for a net **1.75/13** deficit.
Discovery d2 is sampled at tick 25 after deadline 22. This is a specific delayed
command/queue-management failure, with the needed timing rules available.

On **seed 503**, Claude scores **6/8** in both profiles, alive at home. This
matches the rush reference and exceeds the noisy reference's **5/8**. Neither
audit assigns main mistakes relative to its reference.

On **rush seed 504**, Claude scores **7/10**, tying the reference and surviving
at home. On **rush_noisy seed 504**, it earns 9 sample points but exhausts its
battery at tick **47**, away from base, for reward **0.0** against **7/10**.
The dominant reference-relative loss is **call 21 at tick 25**: an extra 8.1 m
of driving plus a sample, adding 11.1 energy expenditure. The existing queue
would already bring the rover home at tick 27. A [post-hoc stop check](lightlag-audits/fixed-seeds501-504/rush-noisy-seed504-delay3-opus-5-5/stop-check.json)
replays through call 20 and sends no further commands: it finishes alive at
home with **6/10** and battery **9.33**. Including call 21 instead causes the
observed exhaustion. The new discovery is sampled on time at tick 31, but that
extra value is lost through the zero survival multiplier. Earlier decisions
account for the remaining one-point net gap; individual positive and negative
attributions are retained in the audit rather than summed selectively.

All eight audits reconstruct the saved runs exactly, have zero infrastructure
findings, and their per-decision losses sum to the reference/model gap. Optional
`superlog` labels are unavailable because numpy is absent in this local audit
interpreter; the core replay checks and decision audit completed normally.

## Decision and handoff

There are now **concrete model failures under unchanged rules**, and they are
explained by available task information: full-horizon energy budgeting,
in-transit commands and keeping the queue supplied. The reference has higher
mean reward on this fixed set. It also loses three comparisons and ties two;
its continuation-based audit is not an optimality proof. The two zero-reward
battery failures have a large effect on the means.

Keep this completed set intact. No rule, controller or canonical Harbor-task
change was made. The new real-time-clock and real-time-aware reference modules
landed during these runs and remain separate proposals; all source/auditor
hashes used here stayed fixed. Lightlag and final mission/profile choice remain
team decisions.

Recommended next work:

1. Check **repeatability** on the two energy-failure cases and the queue case,
   with a fixed number of fresh attempts and a declared budget before running.
   Retain recoveries as well as repeat failures. This comparison stops after
   its eight predeclared attempts; no additional paid runs were started.
2. Compare the team's newer capable reference on the same seeds as a separately
   labelled reference study. Do not rewrite this frozen reference or its scores.
3. Build the demo around an auditable decision: the seed-501 homeward drive
   versus staying alive away from base, or seed-504's extra excursion versus
   keeping the already queued return. Show the published rule, delayed packet,
   pending commands, energy forecast and final reward, including the limits of
   the counterfactual. The noisy seed-502 queue wait provides another example.

This is a small fixed-set comparison, not a general reliability estimate or a
controlled causal estimate of noise effects. If its cases influence future
rules or controller tuning, they become development data; use fresh predeclared
confirmation data for later claims. All eight complete traces and every success,
tie and failure remain available to the team and judges. Independent Codex
reviews approved the reference increment, every model batch and the complete
comparison, including the final aggregate and counterfactual checks. No blocking
findings remain.
