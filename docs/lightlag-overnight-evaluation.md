# Overnight evaluation and research protocol

Started 14 November 2026, approximately 04:25 Helsinki. The user asked Codex to
repeat the observed failures, build a decision-focused demo, broaden research,
challenge the current direction and leave a morning handoff after roughly six
hours. The user reports **$15.70** of Claude credit remaining and authorizes its
use for this work. This is a new overnight budget, not a total including the
earlier $4.2977204 of reported runs.

## Spending and evidence rules

- Track every new paid attempt and its reported cost. Do not launch another
  paid block when cumulative overnight reported cost reaches **$12**; retain
  $3.70 of headroom for calls already running and follow-up decisions. The
  user's overall spending limit is **$15.70**. Usage reports are not invoices
  or independently checked credit balances.
- At most two model attempts run concurrently. Check completed costs and
  provider errors before each new batch. No retries or replacement of poor
  results. Keep all artifacts, including infrastructure failures, and distinguish
  those from scored behavior. Stop paid launches on a provider/authentication
  failure pending diagnosis.
- Every later paid experiment needs its own fixed settings and sample count
  recorded and pushed before outcomes are inspected. Do not spend the remainder
  merely because it is available.
- Existing canonical task, simulator, model prompt and frozen reference are
  not changed by this first block. Project and final rules stay provisional.

## Block A: failure-selected repeatability

Run three additional fresh attempts on each of these exact tasks:

| Case | Frozen task | Original model / reference | Diagnostic question |
|---|---|---|---|
| Energy at home | `rush`, seed 501 | 0 / 0.833333 | Does full-horizon battery budgeting fail again, or was the original a one-off? |
| Queue timing | `rush_noisy`, seed 502 | 0.634615 / 0.769231 | Does the delayed queue-management deficit recur? |
| Extra excursion | `rush_noisy`, seed 504 | 0 / 0.7 | Does the optional late excursion repeatedly sacrifice survival? |

Nine new attempts total, in round order: round 1 cases 501, 502, 504; then round
2 in the same order; then round 3. Use the exact generated tasks frozen at
`02e4f70`, OpenCode **1.19.5**, `anthropic/claude-opus-5-5`, one attempt per job,
no retries, original 1,800-second agent timeout, delay 3, horizon 50, noise level
1, bumpiness 0. New sessions receive no previous transcripts or hints.

These cases were selected **because they previously failed**. The repeats can
measure conditional reproducibility on these cases; they cannot estimate an
unbiased failure rate across maps. Show the original exploratory result
separately from the three prospective repeats. Report all scores, sample counts,
costs, execution exceptions and per-case distributions. Reuse the unchanged
matched reference scores and manifests rather than silently replacing them.

Export sanitized logs and run the delivered decision auditor on every attempt.
Verify source/task hashes, matched task digests, provider/agent identity, exact
replay, reward/cost consistency and absence of credentials or personal paths.
Keep reference-relative mistake labels separate from causal or optimality claims.

## Independent work while runs execute

1. Reassess scientific validity and related agent benchmarks from primary sources.
   Look for reasons the current interpretation could be wrong, not just supporting
   examples. Preserve source dates and evaluation conditions.
2. Compare the current direction with meaningful adjacent tasks and the saved
   fallback ideas. Consider judging fit, realism, learnability, reproducibility,
   capable controls, demo clarity and the remaining development effort.
3. Build an offline decision demo from existing verified artifacts, with actual
   and counterfactual traces clearly labelled. Link the complete mixed results.
4. Compare newer team reference policies separately on the unchanged fixed seed
   set. This is a labelled reference-strength study, not a rewrite of the earlier
   comparison. Define the policies before measuring them.

## Morning deliverable

`docs/lightlag-morning-brief.md` will lead with the recommended direction, the
strongest evidence and counterevidence, what changed overnight, exact reported
spend, outstanding uncertainties, and a short ranked plan for the team. It must
distinguish completed work from proposals and leave final project/rules choices
to the team. Verified increments and prize evidence are pushed throughout.

## Reference-strength study: declared before controller outcomes

Compare exactly two policies: the original `kf_mpc` and Manh's
`EKF_sandodo_stayalive_aimdisc_turncost_window_MPC_manh_controller_24`.
The latter is chosen from the team's existing held-out study, before this
study's scores; do not choose a different policy separately for each map.
Use the code at `5ff2ca2`, with its source hashes recorded in the output.

Run both policies on `rush` and `rush_noisy`, delay 3, horizon 50, noise level 1,
bumpiness 0, using the unchanged `DynamicEnvironment` through the shared
`lightlag.evaluation.run_episode` public-callback boundary. The candidate's
class receives only those callbacks; no oracle, scenario factors, privileged
logger or real-time clock. Preserve complete replays and public transcripts.

Two sets are distinct:

- **Historical eight cells:** seeds 501–504 on both profiles, to determine
  whether reference choice changes the comparison. Verify the original policy
  reproduces each frozen Harbor reference exactly; never replace the earlier
  reference table or audit attribution.
- **Fresh controller-only set:** seeds **3000–3019**, both profiles, selected
  before scores. Repository search found no previous use of this range. These
  40 cells compare policy strength, not model performance; no model has been
  evaluated on them. There are 96 deterministic controller episodes total
  across the two sets, no paid inference.

Report all per-cell scores, survival/home status, tool calls, execution errors,
and paired differences separately by set/profile. Deterministic reruns check
reproduction, not independent samples. Keep exceptions as failed executions;
do not convert them to a fabricated score or replace the seed. A better
candidate would support a team decision to adopt it in a future version, not
a retroactive change to the original experiment.

## Block B: a prospective procedural-aid comparison

Declared after six A outcomes, before any B attempt. Start only after A finishes
and its cost/error ledger is reconciled. Use **12 new attempts**, original
prompt (C) versus the exact [energy/queue appendix](../tools/lightlag_experiments/ledger_aid_v1.md)
(T), two attempts per condition per selected case. The appendix is a combined
procedural prompt intervention: it asks the agent to maintain its own ledger;
it does not supply a persistent ledger, reference route or automatic filter.
All treatment attempts count whether or not they visibly adopt the advice.

Only `instruction.md` changes: append one newline and the appendix bytes to the
frozen instruction. Keep the simulator, map, tools, verifier, original reference,
model/harness versions, provider defaults and 1,800-second timeout unchanged.
Record the original and treatment instruction/task hashes. Use fresh sessions
without earlier transcripts, no retries or replacement seeds.

The case/condition ordering was generated independently of outcomes from the
seed `lightlag-ledger-B-2026-11-14` and then counterbalanced by reversing case
and condition order in repetition two:

| Pair | Case | Repetition | Launch order |
|---|---|---:|---|
| 1 | rush_noisy 504 | 1 | T, C |
| 2 | rush_noisy 502 | 1 | T, C |
| 3 | rush 501 | 1 | C, T |
| 4 | rush 501 | 2 | T, C |
| 5 | rush_noisy 502 | 2 | C, T |
| 6 | rush_noisy 504 | 2 | C, T |

Launch pair members close together in that order, at most two concurrently.
Complete and reconcile each pair before starting another. Pairing controls the
map and execution period, not model randomness. Keep A outside B's primary
comparison: historical controls do not exclude period effects.

Primary performance measure: **mean T-minus-C terminal reward over all six
pairs**, weighting each selected case equally. Primary safety measure:
**battery-death counts out of six per condition**. Also report every paired
difference, per-case means/reference gaps, alive/home status, credited science
before the survival multiplier, late samples, audit findings, calls, duration
and cost. Observable accounting behavior is secondary, not an inclusion rule.

Retain every assigned attempt. Missing/invalid grading is not a valid zero;
report incomplete pairs and bounds using missing rewards' possible [0,1]
range. Finish the declared sample without efficacy stopping. The original
provider/error rules, **$12 cumulative launch guard** and **$15.70 overall
ceiling** still apply; list unrun rows if those prevent completion. The current
six-A average projects roughly $9.26 for A+B, an estimate rather than a charge
or commitment to spend the limit.

Predeclared engineering interpretation: call the gap *provisionally removable
on these selected cases* if all six T attempts survive and each T case mean
lies no more than 0.05 below its frozen reference. Support for an improvement
is stronger if the paired mean gain is at least 0.10 and positive in at least
two cases. These are practical decision thresholds, not significance tests.
If fresh controls also perform well, the result weakens repeatability instead
of demonstrating a treatment effect.

The intervention cannot separate energy guidance, queue guidance, added
attention or extra deliberation; establish ledger mediation; prove a
specifically delay-caused problem; or estimate map-wide reliability. These
maps inspired the advice and remain diagnostic/development cases. Any later
confirmation needs fresh predeclared maps and a frozen agent condition.

## Independent reviews

The [evaluation review](research/2026-11-14-lightlag-evaluation-review.md) and
[direction review](research/2026-11-14-lightlag-direction-review.md) use the
original eight attempts, independently of the overnight outcomes. Both
recommend testing a generic public energy/command-accounting aid before adding
mechanics. The exact intervention and fresh paired baseline budget will be
declared separately before any such paid run. A reminder is not an implemented
automatic ledger or safety filter.

## Block A interim checkpoint: four of nine attempts

This is a partial checkpoint, not a stopping rule or the final block. All four
exports replay exactly; no infrastructure findings or provider exceptions.
Reported new usage: **$1.849386**. Originals remain outside these repeat counts.

| Attempt | Case / repetition | New reward | Original reference | Alive / home |
|---|---|---:|---:|---|
| A01 | rush 501 / 1 | 0 | 0.833333 | no / yes |
| A02 | noisy 502 / 1 | 0.461538 | 0.769231 | yes / yes |
| A03 | noisy 504 / 1 | 0.75 | 0.7 | yes / yes |
| A04 | rush 501 / 2 | 0.833333 | 0.833333 | yes / yes |

A01 repeats terminal energy exhaustion: home at tick 25, first dead at 49.
Its main audited loss remains reference-continuation dependent, not proof that
loss was already inevitable. A02 has failed sampling and lower science value;
the auditor's `STALE_AIM`/intended-target explanation is a geometric heuristic,
not established model intent. Its final report names another target, and the
actual sample position is compatible with a near miss of that target. Do not
call it an exact replication of the original queue-wait failure. The two
subsequent attempts show recovery without a prompt change: A03 beats and A04
matches the frozen reference.

Independent review checked fresh sessions, identities, source/task/prompt
matching, costs, protected scores, raw-to-sanitized exports and exact audit
reproduction. [All checkpoint audits](lightlag-audits/overnight/README.md) and
[all run rows](lightlag-runs/overnight-a-summary.json) retain the evidence.

## Status

Block A protocol was published at `253b263` before new attempts. The live
[summary](lightlag-runs/overnight-a-summary.json) records completed attempts,
pending cases and reported usage; partial results are not the finished block.
