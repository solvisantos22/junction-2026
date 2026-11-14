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

## Status

Protocol published before new attempts. No overnight results yet.
