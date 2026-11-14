# AfterQuery readiness — recovered morning checkpoint

Updated 14 November after syncing the team’s `5d01106` changes and publishing
all overnight A/B results (`6fb112f`). The shared tool descriptions are now
corrected (`64fe6db`); historical experiment packages remain frozen. See the
[morning brief](lightlag-morning-brief.md) for the direction recommendation.
Lightlag, the final mission and the reference choice remain provisional.

**The model/container path and auditable failures are demonstrated. The main
remaining gap is choosing and packaging the actual judge task.** Canonical
`harbor/lightlag` still runs the original core seed 7, which the model solved.
Generated dynamic experiments and demo changes do not automatically replace it.

## What is complete

| Evidence | Result and practical limit |
|---|---|
| Kristján’s original Harbor path | Reference 1.0, no-op 0.0, OpenCode / Claude Opus 5.5 1.0. Protected sidecar artifacts, early-stop collection and separate verifier worked. [Details](lightlag-harbor.md). |
| Two dynamic seed-500 pilots | Model and original KF both score 1.0 on rush and noisy missions. These examples establish execution, not a model deficit. [Rush](lightlag-experiments.md), [noisy](lightlag-noisy-experiment.md). |
| Original fixed comparison | Eight model attempts: 3 wins, 2 ties, 3 deficits against KF; two battery deaths drive much of the mean gap. All exact audits. [Full results](lightlag-fixed-seed-comparison.md). |
| Repeatability block A | Nine new attempts on three failure-selected cases: 2 wins, 2 ties, 5 deficits, including 3 deaths. All exact audits, no infrastructure findings. This is conditional recurrence, not a random-map failure rate. [Protocol/results](lightlag-overnight-evaluation.md). |
| Prompt-aid block B | All twelve attempts complete: mean original prompt 0.406571 / aid 0.732265; paired gain +0.325694, five improvements and one tie. Deaths 1/6 versus 0/6. Improvement gate passes; stricter gap-removal gate fails on noisy504. Combined guidance does not identify an energy-only mechanism. [Ledger](lightlag-runs/overnight-b-summary.json). |
| Reference strength | Candidate 24 gains only 0.007898 on fresh rush maps and ties every noisy score. Candidate 27 loses on the inspected plain-profile means. Preserve these negative findings and separate them from scenario-specific gains. [24](lightlag-runs/overnight-reference-study/README.md), [27](lightlag-runs/overnight-reference27-study/README.md). |
| Presentable evidence | Kristján’s [3D demo](../viewer/mars-demo.html) shows all three A attempts and a reference on each of two selected cases. The [decision demo](lightlag-decision-demo.md) and [62-second clip](lightlag-demo-media/README.md) show checked post-hoc continuations with clear labels. All 28 viewer tests pass after sync; the [3D reserve correction](superpowers/specs/2026-11-14-mars-reserve-correction.md) now passes independent Chrome review. |
| Public contract wording | Shared descriptions now accurately allow dynamic discoveries, noisy odometry and credited sampling value. Only three constants and their generated copy changed; 18 MCP + 11 Harbor checks pass. [Verification](superpowers/specs/2026-11-14-lightlag-interface-clarity.md). |

Manh’s morning [ablation](../lightlag_dynamic/manh_controllers/README.md#plain-profile-check-the-guarded-moves-are-the-whole-cost-saturday-about-1100-helsinki)
reports that controller 27’s guarded moves explain the plain-profile cost,
while helping under hidden sand. This coordinator read the commit and report,
but has not independently rerun that ablation. No canonical reference changed.

The separately predeclared [reusable-policy test](lightlag-synthesis-experiment.md)
has a reviewed offline preparation: isolated worker, public-only request and
exact historical reference gate. It has **no generated policy or fresh-map
result yet**. A one-response transfer experiment is a different condition from
an online OpenCode playthrough and cannot replace the required Harbor evidence.

## Remaining gates, in order

| Priority | Action | Completion evidence |
|---|---|---|
| 1 | Team chooses the objective, profile and one reference from the full evidence. | A versioned task contract, fair public instructions and a precise claim that retains model recoveries. Avoid adding mechanics solely to defeat saved traces. |
| 1 | Package that choice as the actual judge entry point. | Coordinate with Kristján; lint/build the selected Harbor task, record its exact hashes and run it from a clean checkout. Canonical seed7 is currently solved. |
| 1 | Validate the selected package and any material changes. | Matching real-model log and score, fixed reference, no-op and early-stop checks. Keep all predeclared attempts, errors and source versions; use fresh confirmation maps after tuning. |
| 2 | Rehearse the explanation with the final evidence. | One mission objective, a concrete commitment error, the protected terminal reward, mixed-results context and one reproducible command. A selected failure or post-hoc rescue is not a population claim. |
| 2 | Confirm submission and prize requirements. | Current authenticated organizer/platform read, final track/prize selections and any separate forms, team license decision, exact artifact links. The saved entry remains a recorded draft; no final submission has been made here. |

The maximum reward is total maximum value generated for the mission, including
later discoveries; late samples earn the published reduced value. The adapter
writes `raw_score / max_available_value`, validates finite values and rejects
malformed results. This is mission-value scaling, not reference normalization.
Keep any reference ratio separate. Grading continues to the horizon after the
agent stops; already accepted commands still execute and idle drain continues.

## Budget, sponsor evidence and source freshness

User-reported overnight starting budget: **$15.70**. Block A reports
**$3.9709816**, B **$5.4645252**, total **$9.4355068**. No paid attempts remained
running when the user returned. The nominal remainder is **$6.2644932**, not
an independently verified account balance; earlier $4.2977204 runs are separate.
Synthesis reserves at most $1 and has not made a provider call at this checkpoint.
No new launch after $12 cumulative overnight usage; no retries or replacement
outcomes. Codex itself hit a usage limit, interrupting final publication and
preparation review. That does not imply an Anthropic API error or lost run data.

[Prize evidence](prize-evidence.md) records actual Codex orchestration and
verification, Claude task execution, and teammate authorship. Modal’s confirmed
compute grant is separate and unused in these studies. Gemini application is
user-reported; available balance is unverified. Do not claim sponsor use or a
prize entry from credit redemption alone.

Requirements still come from the team’s [record of Ved’s 01:35 announcement](afterquery-update-2026-11-14.md):
Harbor task, a single normalized `/logs/verifier/reward.txt`, at least one actual
model log/score, and a short README; playthrough encouraged, training optional,
no AfterQuery inference credits. The exact judging model, effort and resource
limits remain unresolved. General [Harbor verifier documentation](https://docs.harborframework.com/tasks/verifier)
accepts other formats, but the recorded challenge asks for the single number.

The last successful authenticated watcher coverage was **04:29 Helsinki on
14 November**. Later checks through 05:58 could not read the browser/native
surfaces; after the usage interruption a queued check remained pending. These
are stale source checkpoints, not evidence that announcements stayed unchanged.
The last verified final deadline was **Sunday 15 November, 10:00 Helsinki**.
The previously checked [Junction schedule/FAQ](https://2026.hackjunction.com/)
described MIT submissions and tech prizes alongside a main track. Confirm
current terms, repository license treatment and entry forms before submitting.

Current ownership is in [TEAM_STATUS.md](../TEAM_STATUS.md). Historical B exports
must use the pre-description-fix checkout `6fb112f`; do not change their hashes
to fit the new package. Final project, rules and prize choices remain with the
team.
