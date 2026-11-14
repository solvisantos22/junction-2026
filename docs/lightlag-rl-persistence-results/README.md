# Persistent goals: results and handoff

This is the user-approved local diagnostic under the
[fixed protocol](../lightlag-rl-persistence.md), following the
[first RL pilot](../lightlag-rl-results/README.md). It tests a commitment rule on
previously visited training maps using unchanged weights and navigation.

## Completed development result

**Persistence improves science collection, but the declared screen fails on
home returns.** No training occurred: this is the effect of a fixed commitment
rule on existing weights, using the same 24 previously visited training maps.

| Fixed chooser | Frequent: score / home | Persistent: score / home |
|---|---:|---:|
| Initial neural policy (48 missions per arm) | 1.85% / 33 of 48 | 7.76% / 29 of 48 |
| Previously trained neural policy (48 per arm) | 2.81% / 33 of 48 | 9.37% / 28 of 48 |
| Greedy (24 per arm) | 20.41% / 10 of 24 | 22.62% / 13 of 24 |

The primary initial-policy gain is **0.059166**, or **5.92 percentage points**,
with a paired-map bootstrap 95% interval **[0.048852, 0.069154]**. All 24
map-average differences are positive. The .03 gain and positive-interval
requirements pass; the return-count requirement fails because returns fall by
four, more than the permitted two. All 240 missions finish alive with no invalid
calls. The observed return difference is not a claim of a statistically proven
population decline.

[Full report](development/report.json), [frozen inputs](development/freeze.json)
and [audit](development/audit.json) retain all 240 cases. The audit reconstructs
all physics replays/grades and **10,479 proposals/effective choices**: 3,764 held
intentions and 2,942 overridden proposals, against 42 source pins. A separate
read-only review independently reproduced the comparison and artifact hashes. The final-policy and greedy arms
remain descriptive; they do not replace the failed primary return check.

**Decision:** preserve the useful science gain and the failed overall screen.
Do not promote this exact wrapper or start a large training run. Define the
return-feasibility follow-up below as a separate experiment.
Previously trained weights were optimized under frequent reselection, so this
is not a measurement of new RL learning. Reused training maps do not establish
generalization or a frontier-agent gap.

The official evaluator already multiplies sampled value by 0.5 when the living
rover finishes away, versus 1.0 at base. The reported score gain therefore
includes the existing return penalty. Our additional home-count threshold is a
predeclared engineering screen, not an official AfterQuery requirement. It
cannot be silently waived after these results.

## Saved-return diagnosis and recommendation

[Reproducible post hoc inspection](diagnosis.json) uses only retained cases.
For the initial policy, paired outcomes include 12 returns lost and 8 gained,
producing the net loss of four. Persistent initial-policy misses are substantial:
19 away cases finish a median 36.30 metres from base; 14 are more than 25 metres
away, and none are within 6 metres (the grading radius is 4 metres).

Across all six groups, every one of the 94 away cases ends below 10 battery.
Initial-policy persistent misses have median final battery 6.74 and median
25 executed wait commands in ticks 361–420. Low final battery and late waits
are consistent with underestimated charging delays; they do not prove the
cause or show that every wait was for charging. Final battery is also affected
by whether the rover arrived early and had time to recharge at base.

Holding goals also blocks some proposed returns home. The initial persistent
arm overrides 73 home proposals in 36 episodes, including both 17 of its 19
away cases and 19 of its 29 returns. That association does not isolate the
cause of missed returns.

**Recommended next experiment:** test one-goal visit-and-return feasibility
using public battery, solar and travel estimates, explicitly including charging
waits. The existing `RouteProblem._leg` already models these waits for the
reference planner; the RL candidate mask currently checks travel time only.
Apply an identical feasibility rule to every policy/control and preserve the
existing reward, navigator and mission. Reused training maps are appropriate
for development; reserve new maps before any generalization claim.

**Rainbow remains a reasonable next learner to compare after this interface
check.** Record transitions at actual goal selections, mask unavailable actions,
and include the public information needed to evaluate future target choices.
Use several training seeds and learning curves against simpler controls with
matched budgets. A proposed first cloud comparison should have a small explicit
cap (for example $5) and expand only with evidence. Sölvi reports $300 shared
team Modal credit; no balance was verified or credit allocated by this task.
No Rainbow code, follow-up training or additional cloud job was launched.

Kristján's [independent RL/reference review](../research/2026-11-14-rl-reference-and-failures.md)
landed during this task and agrees on completing the return diagnosis first.
It also identifies a representation limit: our scorer evaluates each target
independently, so it cannot properly compare onward target clusters. A future
learner needs candidate-set or route context; changing only the algorithm does
not supply it. The review proposes planner imitation as a starting baseline,
with an imitation-only checkpoint so its gains are not misattributed to RL.
That is a proposal to compare, not an experiment performed here.

## Verified preparation

All **21 focused tests pass**: exact pass-through replay/RNG equivalence,
commitment/release behavior, full-horizon grading, immutable inputs, paired
summary/gates, partial failures, source drift and tamper detection.

The [20-case smoke comparison](smoke/report.json) on used maps 1/2 completed.
Its [audit](smoke/audit.json) reproduces all physics replays and grades, plus
877 proposals/effective choices (306 retentions, 243 overrides) against 42 source
pins. Smoke results are execution verification, not the primary result or an
input to tuning. The smoke preceded the production diagnostic; its results did not change the protocol.

Candidate/feature reconstruction and the link from chosen goals to commands are
source-pinned rather than independently rerun by the auditor. The pass-through
integration test separately proves exact equivalence with the original runner
on used seed 1. Weights, reward and the original navigator remain unchanged.

Use Python 3.12 and NumPy 2.3.4. Commands from the pinned experiment source:

```sh
python -m unittest discover -s tests/rl_persistence -v
python -m tools.rl_persistence.run --output /tmp/persistence-new --workers 4
python -m tools.rl_persistence.audit /tmp/persistence-new/report.json --output /tmp/persistence-new/audit.json
```

The production diagnostic ran from detached revision **`e1661e7`**, published
before its first mission. All 240 missions and the audit use that checkout,
isolated from concurrent main changes. No fresh check maps, retraining, model
API or cloud job were used; **Modal spend for this diagnostic is zero**.

To audit retained results from the current repository checkout:

```sh
artifact_root="$(pwd)/docs/lightlag-rl-persistence-results"
git worktree add --detach /tmp/persistence-audit-01 e1661e7
cd /tmp/persistence-audit-01
python -m tools.rl_persistence.audit "$artifact_root/development/report.json"
```

The preceding code-only increment also retains a fully audited smoke run. The
original RL experiment, its consumed check maps and protocol remain unchanged.
This diagnostic and saved-trace diagnosis are complete; the scope is released.
The next owner should preserve both the protocol and its failed screen, read the
separate teammate RL/reference and Traverse-integrity reviews, and claim a new
follow-up before changing the action interface or training method. No team
project/rules choice, canonical Harbor update or prize submission follows.
