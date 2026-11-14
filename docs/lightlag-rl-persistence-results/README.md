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
read-only review recomputes the comparison. The final-policy and greedy arms
remain descriptive; they do not replace the failed primary return check.

**Decision:** preserve the useful science gain and the failed overall screen.
Do not promote this exact wrapper or start a large training run. Inspect the
saved missed returns before defining a separate commitment/return experiment.
Previously trained weights were optimized under frequent reselection, so this
is not a measurement of new RL learning. Reused training maps do not establish
generalization or a frontier-agent gap.

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
Post hoc saved-trace return diagnosis and final handoff follow separately.
