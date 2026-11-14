# RL–greedy hybrid experiment

Sölvi authorized this separate experiment on 15 November, with roughly eight
hours until submission and most team Modal credits remaining. The question is
whether combining the six retained learned policies with greedy improves on
greedy itself. The completed learning experiment remains immutable. This is
policy composition and development-set selection, not additional RL training.

## Fixed candidates and public information

The parent is `docs/learning-final-results/policy-freeze.json`, published before
its final evaluation. Use **all six latest-role policies**: PPO seeds 17/29/43
at 8192 missions, replay 17/29 at 8192 and replay 43 at 2048. Do not choose a
training seed or replace a checkpoint. Pin their complete weights and the
parent file hash. Simulator, option observations, feasibility model, navigator,
official reward and reference remain unchanged.

The development matrix contains 65 deterministic arms:

- Each of six policies with science shortlist thresholds 0, .5, .75, .9, .95,
  and 1 times the best feasible greedy efficiency: 36 arms. Threshold zero
  must reproduce the original deterministic policy. Home always remains legal.
- PPO-three, replay-three and all-six ensembles with the same six thresholds:
  18 arms. Each network ranks the original legal actions; average percentile
  ranks across members, then restrict the final choice to the shortlist.
- Each of those three ensembles blended with greedy percentile ranks at
  greedy weights .25, .5 and .75, without an additional shortlist: nine arms.
- Unmodified greedy and frozen beam reference: two controls.

Greedy efficiency is expected credited science divided by forecast visit time,
including charging, using the existing option features. Greedy ranks home
below any legal science target; no-target observations retain home. Tied neural
ranks use their average position, and final score ties follow the original
candidate order. Rank normalization uses the original legal set, not the
shortlist. Raw PPO logits and replay Q-values are never averaged together.
Observation values and candidate context are unchanged. Return feasibility is
an estimate, not a safety guarantee; all deaths and away endings count.

## Maps, selection and final gate

Use worlds 1 and 2 only for local/cloud smoke. The following ranges were
claimed on `main` before implementation or simulation:

| Stage | Worlds | Use |
|---|---|---|
| Development | 610000–610127 | All 65 arms: 8320 missions |
| Confirmation | 611000–611255 | Selected development groups and matched controls |
| Final | 612000–612255 | One frozen primary group and its controls, opened once |

Never train or tune on the prior final maps 82000–82039, submission worlds
2026–2029, MAX held-out pool 500–523, or teammates' claimed ranges. Optional
training reservation 620000–629999 is **inactive**; activating it would require
a new published protocol and resource freeze. This experiment does not restart
any earlier training or monitor.

Single-policy shortlist selection is grouped by method and threshold: average
the three training seeds **within each map**, then average maps. Ensembles and
blends each form one fixed group. Pure individual policies at threshold zero
are controls, not candidate shortlist improvements. Pure ensembles are valid
ensemble candidates. No per-world oracle switching or best-seed selection.

Development eligibility requires complete audited data, no controller errors,
invalid calls or deaths, and mean home rate at least greedy minus 1/128. Rank
eligible groups by mean reward, breaking exact ties by group ID. Advance at
most the top **two groups in each family** (single-policy shortlist, ensemble,
blend). This is a screening rule, not statistical evidence of improvement.
Retain greedy, beam, the six unmodified learned policies and relevant pure
ensembles as confirmation controls, deduplicating identical arm IDs.

On confirmation, require complete audited data, no errors/invalid calls/deaths,
home rate at least greedy minus 1/256, and positive mean paired reward gain
over greedy. Among eligible shortlisted groups choose **one primary group** by
mean reward, with the same fixed tie-break. If none qualifies, stop this
experiment, publish the negative result and leave final worlds unopened.

Publish the selected group, parent weights, source/runtime, development and
confirmation artifact hashes, controls and final manifest to `main` before
opening the final range. Include greedy, beam, the selected group's unmodified
constituent policies and (for a composed group) its pure rank ensemble. A
single-policy shortlist retains all three training seeds on final maps.

Final success requires mean gain over greedy **at least .01**, paired-map
bootstrap 95% lower bound above zero, no deaths/errors/invalid calls, and home
rate at least greedy minus 1/256. Bootstrap 20,000 map resamples with seed
612256, after averaging grouped training seeds within each map. Report all
arms and both positive and negative findings. Intervals are conditional on the
fixed learned seeds and the development selection. No tuning, seed replacement
or further selection after final worlds. Reference promotion is a separate
team decision, not an automatic consequence of beating greedy.

## Parallel execution and limits

Use an isolated `junction-learning-hybrid` Modal app/volume with Sölvi's
`solvi-junction` profile. Start up to **64 parallel episode workers**, each
requesting and limited to one physical CPU and 2 GiB memory, Torch threads one,
no GPU, retries zero and bounded per-call execution. A detached coordinator
retains call IDs and immutable per-job artifacts. A disconnect must not cause
automatic duplicate execution. An ambiguous launch reservation stops recovery
until diagnosed. Completed jobs are never resubmitted.

Freeze source, weights, runtime, resources, full job matrix and cost reservation
before launching each stage. Worker IDs and output hashes identify every
mission. Errors are retained and diagnosed before any new spend. Retain full
compressed trajectories on the volume; publish tables, manifests, audits,
selection evidence and reproducible commands in the repo. Retain/download the
selected final trajectories for the handoff. No secrets or private logs go in
the repo.

The initial running-compute ceiling is **$75**, not a spending target or a
verified balance. At current published rates, 64 workers plus one coordinator
at these hard limits cost at most approximately **$4.10436/hour**, or
**$24.62616 for six hours** of continuously allocated compute. The cap excludes
build/startup/storage/egress; retain measured estimates separately. All work
has an absolute compute cutoff **2026-11-15 05:30 UTC**, leaving roughly two
hours for final auditing and submission preparation. Measure smoke throughput
and storage before production. Scaling beyond these declared resources needs
a separate published resource revision within the authorized remaining credit.

Pricing and operational references checked for this experiment:
[Modal pricing](https://modal.com/pricing),
[resource requests and limits](https://modal.com/docs/guide/resources),
[durable function invocation](https://modal.com/docs/guide/function-invocation-methods),
[retry behavior](https://modal.com/docs/guide/retries), and
[Volume persistence](https://modal.com/docs/guide/volumes).

## Verification and handoff

Test threshold-zero equivalence, greedy endpoint/ties, masks/home handling,
rank invariance, all-seed membership, disjoint seed sets, complete group
selection, artifact/source integrity and duplicate-launch refusal. Each saved
case must pass reconstructed physics/grade and hybrid-choice audits. Final
cases also repeat the complete controller execution and compare observations,
choices and commands, excluding runtime measurements. No existing frozen file
is modified to make a test pass.

Publish progress after smoke, development, confirmation and final evaluation.
Leave exact app/call IDs, cost estimates, all failures, decisions and a concise
README/video handoff plus prize attribution. Kristján's independently claimed
strategy-switch learner and Manh's learner remain separate; this experiment
does not modify their code, results or jobs.
