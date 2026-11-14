# RL reference and Traverse failures: independent review

14 November 2026. Kristján asked whether to train an RL reference, inspect
Sölvi's work, and continue finding realistic mechanisms that a reference handles
more reliably than Claude. This review reads the existing experiments, rebuilds
their retained evidence and proposes the next experiment. It does not change
the mission, train a competing policy or launch a model/cloud job.

**Recommendation:** continue Sölvi's return diagnosis after the persistence
result, keep the current beam-search pilot as the reference, and target a learned scheduler that can
understand whole routes. The existing task already exposes route-value and
energy/return failures. Confirm those mechanisms before adding more rules.

## What Sölvi has actually delivered

The [first experiment](../lightlag-rl-results/README.md) trains a 256-parameter
neural next-target scorer above the existing navigator. It does not learn
steering or replace the reference's whole-route search. One Modal CPU job ran
512 missions and 16 REINFORCE updates, using only the terminal mission reward.

I reran the existing training and evaluation auditors from the shared sources:

- **Training:** all 16 optimizer updates, 512 retained episode records and
  21,078 action draws reconstruct against 34 source pins.
- **Evaluation:** all 240 saved physics replays, grades and 8,559 choices from
  retained features reconstruct. This does not independently reextract features.
- **Persistence wrapper:** all eight existing tests pass, including exact
  replay/RNG equivalence for its unchanged frequent-reselection arm.

| Policy, same 40 check maps | Mean official score | Alive and home |
|---|---:|---:|
| Initial neural selector | 0.016744 | 62/80 |
| Trained neural selector | 0.024835 | 58/80 |
| Same-navigator greedy selector | 0.232840 | 18/40 |
| Do nothing | 0 | 40/40 |

The learned gain is 0.008091, with the original paired-map 95% interval
[0.004038, 0.012592]. It fails the declared minimum gain of 0.03 and the return
count condition. There were no deaths or invalid calls. The greedy comparison
is paired on the same maps; the farm's approximately 0.5 beam-pilot score is on
a different set and must not be presented as a paired RL comparison.

This is a verified, weak first learning result, not a reference ready to replace
the planner. These auditors verify the recorded implementation; they do not
establish that the chosen architecture or optimization method is adequate.

## Why more training alone is a weak next bet

An independent pass through the training records reproduces Sölvi's diagnosis:
**16,410 switches in 17,265 opportunities (95.05%)** when the previous science
goal remained available. Of those switches, 99.43% occur before its earlier
estimated arrival. Median decision spacing is 12 ticks, while mean selected
science travel is about 49 ticks. These are intentions and estimates; the
navigator can override them, so this is not proof that switching caused failure.

The implementation also has a structural limit: each candidate is scored as
`tanh(features @ W + b) @ v`, independently of the other candidates. Holding
two candidates' feature rows fixed, changing a third candidate cannot change
their relative ranking. The shared open-target count is not a representation
of which valuable clusters or onward routes exist. There is no explicit previous
goal, planned sequence, estimated panel efficiency or along-route battery
trajectory in the scorer's inputs. More parameters in this same independent
scorer would not by itself supply those missing inputs.

The reward signal is not entirely absent: only 19 of 256 same-map training
pairs have equal rewards, including five pairs where both rewards are zero.
Equal pairs have no reward advantage under the current centering, although
entropy gradients can remain. The negative result therefore does not establish
that sparse rewards alone are the cause either.

Sölvi's [persistence protocol](../lightlag-rl-persistence.md) is the correct next
diagnostic and remains his scope. It holds an available target while keeping
the policies, navigator and reward fixed. The wrapper was initially reviewed with eight tests. While this review was
being prepared, Sölvi published the completed diagnostic at `972bfd9`. The wrapper also overrides a newly proposed voluntary
home choice while a science target remains available. That is an explicit
commitment rule, not just added memory. The published outcome checks must
therefore include home returns and deaths, as they already do.


**Newly landed result:** on the same 24 reused training maps, initial weights
improve from 1.85% to 7.76% with persistence; previously trained weights improve
from 2.81% to 9.37%. The primary gain is 5.92 percentage points with interval
[4.89, 6.92], but initial-policy home returns fall from 33/48 to 29/48. Trained
policy returns fall from 33/48 to 28/48. All missions remain alive. The fixed
screen fails its return condition. These are gains from a commitment rule, not
new learning, and are separate from the original 40-map fresh comparison above.
[Result and full limits](../lightlag-rl-persistence-results/README.md). Sölvi is
already inspecting the saved missed returns. His new report records 21 tests
and an audit of all 240 missions; this review initially reran only the earlier
eight wrapper tests. The next independent check will cover the newly landed data.

## What the saved full-agent failures show

The new [read-only auditor](../../tools/reference_gap_review/audit.py) reproduces
all **11 retained missions** here: eight model runs, the reference, do nothing
and the reference stopped at tick 105. It executes only accepted command records
through the trusted simulator, never a model-written program. Every complete
physics replay and verifier grade matches.

| Run on world 2026 | Score | Observed outcome |
|---|---:|---|
| Reference | 0.564655 | 29 samples, home; minimum battery 7.38 |
| Sonnet 1 | 0.528017 | 26 samples, home |
| Opus 3 | 0.515086 | 24 samples, home; minimum battery 0.67 |
| Opus 4 | 0.340517 | 15 samples, home |
| Opus 1 | 0.215517 | Last-tick drive moves from 0.29 m to 4.59 m from base, beyond its 4 m radius; half credit |
| Sonnet 2 | 0.146552 | Eight samples, home; battery never below 77.70 |
| Sonnet 3 | 0.059267 | Nine samples, ends 69.27 m from base; battery never below 82.81 |
| Opus 2 | 0 | Battery exhausts at tick 372, 142.89 m from base, after 17 samples |
| Haiku 1 | 0 | Agent stops at tick 8 with final generation reason `length`; no samples |
| Do nothing | 0 | No agent calls; evaluator completes the horizon |
| Reference stopped at tick 105 | 0.073276 | Evaluator completes the remaining horizon |

The seven Opus/Sonnet attempts average 0.257851, versus 0.564655 for the reference.
For each run, the reference gap can be written exactly as:

`(reference sampled value - agent sampled value + agent terminal-factor loss) / 116`.

The average 0.306804 gap consists of **0.212131 from lower credited sample value
(69.14%)** and **0.094674 from terminal penalties (30.86%)**. This is arithmetic,
not a causal allocation or a claim that returning home would have been free.
Changing the route to get home could change its science value. Still, it shows
why investigating route selection is useful alongside energy/return safeguards.

All eight model runs record `NonZeroAgentExitCodeError`. Preserve that fact.
The seven Opus/Sonnet transcripts reach tick 420 and end with a generation
`stop`; their physical outcomes are reproduced. This does not explain the
process-exit error or prove it had no earlier effect. Haiku stops at tick 8 and
exhausts its output allowance, so its zero is not a completed planning comparison.
Fix or explain the runner errors before claiming a clean fresh agent study.

These results concern **one world**, and the reference was improved after
earlier model outcomes. They motivate development; they are not an independent
confirmation that the current frozen reference reliably beats full agents on
new worlds. The farm's saved-program transfer results answer a different
question, especially when a successful agent changed programs mid-mission.

## The next training experiment I recommend

This is a proposal for Sölvi's existing learning effort, not a second active
training scope. A persistence pass is necessary evidence about the interface,
not evidence that the resulting policy will beat the beam reference.

1. The fixed persistence comparison fails its return condition. Let Sölvi
   finish inspecting the retained navigation/termination behavior before
   launching more unchanged training. Preserve commitment when useful, but
   define an explicit, publicly observable return/termination condition in a
   separately frozen interface experiment.
2. Use persistent goal decisions and a policy with candidate-set/route context.
   Include the current commitment, elapsed time, estimated charging, and route
   feasibility derived from the same public observations. Keep the navigator
   and its safety rules matched across learned controls.
3. As a pragmatic next baseline, teach the policy from the existing planner's
   decisions on training maps, then run bounded RL fine-tuning. Record the
   teacher, training data and cost. An imitation-only checkpoint is essential:
   imitation gains must not be credited to RL. If the learner cannot imitate
   the planner on development data, fix representation before scaling rollouts.
4. Compare untrained, imitation-only, RL-fine-tuned, same-interface greedy and
   the frozen beam pilot on the **same** maps. Use three fixed training seeds,
   retain every final checkpoint and report all seeds rather than selecting
   the best. A first stage of 512 RL episodes per seed is a screening budget,
   not a promise of convergence. Measure local rollout time before fixing the
   cloud runtime and spend ceiling. Allocate new check IDs with the existing
   owner immediately before freezing the protocol; none are reserved here.
5. Evaluate on a fixed 40-map unused check block with paired action draws where
   stochastic. Separate two decisions: does RL improve its imitation-only
   starting point, and does it improve the existing beam reference? Promote it
   as the reference only with a positive paired margin and no deterioration in
   safety/home outcomes under the prospectively chosen criteria. A useful
   learning demonstration can still fall short of reference promotion.

[Rainbow](https://arxiv.org/abs/1710.02298) is a legitimate candidate learner: its
paper combines six DQN improvements and demonstrates their benefit on Atari.
It does not establish that Rainbow fixes this action interface. Persistent
decisions also have unequal durations, so transition records and discounting
must match the mission objective. Sölvi should compare learning methods after
the interface works, rather than replacing the whole stack at once.

Teacher initialization is my practical recommendation, not a proven Traverse
result. [DAgger](https://proceedings.mlr.press/v15/ross11a.html) explains why
imitation must account for states induced by the learner's own actions rather
than relying only on expert trajectories. [Neural combinatorial
optimization](https://arxiv.org/abs/1611.09940) provides precedent for learning
route construction from reward, but its TSP/knapsack results do not predict
success on our partially observed rover task.

## Which failure mechanisms to investigate next

| Priority | Mechanism and evidence | Next discriminating test |
|---|---|---|
| 1 | Route value under travel cost and deadlines: most of the recorded gap is uncollected or discounted science; even safe runs can do little work. | Keep current rules. Freeze reference and run full coding agents on predeclared new maps, including a route-search hint. Check whether the gap remains after agents can build and debug a planner. |
| 1 | Energy feasibility throughout the route: one completed Opus run exhausts its battery; another comes within 0.67 of zero. | Compare the existing reference's per-leg reserve with a disclosed simpler energy control on development worlds. Any daylight change needs a reference reliability check first; the separately owned harsher-day farm already reports two stranded reference rovers. |
| 2 | Ending safely despite queued commands and noisy position: Opus 1 leaves base on the last tick; Sonnet 3 misses the return with ample battery. | Test a public queue/return strategy hint with unchanged rules. If the hint removes the gap, report that result. A tiny boundary mistake is weak justification for a new mechanic by itself. |
| Later | Sensor fusion or changed dynamics from teammates' prototypes. | Reuse their declared candidates only after a full-agent comparison. Existing negative model results and scripted-only gains do not justify adding all mechanics together. |

Designing from development failures is reasonable. Once a candidate is chosen,
freeze rules, references, instructions, budgets and a new evaluation set. Give
agents the same public information, code access, clear examples and adequate
resources, and retain improvements as well as failures. A reference with broad
offline training or tuning must disclose that preparation. A robust fresh gap
is the desired result; larger penalties or harder terrain alone do not create it.

## Evidence, reproduction and handoff

- [Review data and hashes](../reference-gap-review/review.json),
  [rerun training audit](../reference-gap-review/rl-training-audit.json),
  [rerun evaluation audit](../reference-gap-review/rl-check-audit.json).
- Reviewed shared commit `b7dd2f5`, including Sölvi's protocol/wrapper `9a4a4d9`
  and the Traverse runs at `f88d455`. The review artifact records actual source
  hashes, so later shared-branch edits cannot silently redefine this result.
- Local verification used Python 3.13.7 / NumPy 2.2.5. The original production
  job used Python 3.12 / NumPy 2.3.4. The training audit's declared 1e-9 tolerance
  passed; complete evaluation replays and summaries match.

From the repository root, writing to new temporary output paths:

```sh
python3 -m tools.reference_gap_review.audit --output /tmp/traverse-reference-review-new.json
python3 -m tools.lightlag_rl.audit_training --training docs/lightlag-rl-results/modal/pilot-01/training
python3 -m tools.lightlag_rl.check --audit docs/lightlag-rl-results/check/report.json
python3 -m unittest discover -s tests/rl_persistence -v
```

Sölvi retains ownership of the persistence/training decision; the Traverse and
farm owners retain their existing implementation scopes. The original RL/Traverse audit is
delivered; the newly landed persistence data are being checked. No new model generation, cloud spend, training weights, fresh check
map, environment edit, canonical promotion or final project decision occurred.
