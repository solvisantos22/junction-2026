# Modal learned planner portfolio

[Protocol](../learned-portfolio.md). Three classical models will learn which
planner strategy to switch to once at tick 140, using 49 public-state features.
The frozen reference, task and teammate learners remain unchanged.

Seven focused tests pass, including training and checkpoint round trips for all
three algorithms. All 12 Modal smoke missions completed home/alive with no
invalid calls or controller errors. Their pre-switch commands and features match
exactly; the baseline's full replay matches a local run exactly. The independent
[smoke replay audit](smoke/audit.json) rebuilt all 12 trajectories, 4,874 commands
and 5,052 states. The Modal SDK emitted a stream-cleanup warning after all smoke
results completed; it is retained in [verification](smoke/verification.json).
Commit `eb4f9e2` fixed iterator exhaustion before production and disabled implicit
source discovery, retaining the explicit upload allowlist.
Smoke app: `ap-qApEtSS6Dc08zx9gzidYBn`.

Production: 192 training worlds and 48 validation worlds, each with 12 strategies
(2,880 missions). Three model fits run in parallel on Modal. After selection is
frozen, 96 fresh worlds compare baseline, best fixed strategy and two learners.
Data generation resumed in Modal app
[`ap-vmIsFVOKPZVhhmunxtJuuB`](https://modal.com/apps/kristjansolvi03/main/ap-vmIsFVOKPZVhhmunxtJuuB)
after the original app `ap-tctysvmd3CxtowroSpSlM0` lost its result stream during a
system DNS outage. All 833 archived outcomes were retained; only unarchived jobs
were resubmitted. A second attempt timed out before creating an app. The optional
`dns_run` launcher uses public DNS inside its own process with normal TLS hostname
verification; it changes no OS setting. [Attempt records](data/attempts/01/failure.json)
and the [original receipt](data/attempts/01/app.json) preserve the interruption.

The workspace reached 100 mission workers. The resumed function was later capped
at 96 to leave slots for independent verification. User-code retries remain zero;
Modal can still restart containers after platform preemption. Completed but
unreceived work may be duplicated after a lost stream. [Frozen jobs/source](data/freeze.json),
[current app receipt](data/app.json), [autoscaler change](data/autoscaler-override.json).

A first cross-platform replay mismatch was diagnosed on world 560007: one
illustrative terrain field differs by `1.11e-16` between macOS and Linux. Commands,
states, telemetry and score agree exactly, and a fresh Linux replay matches the
original full hash. [Diagnosis](data/cross-platform/diagnosis.json). The full batch
will receive a same-platform replay audit plus local grade/command checks.
All 2,880 missions are complete. The independent Linux audit reproduced every
full replay hash and score: **1,147,531 commands and 1,212,480 states**.
[Audit receipt](data/cloud-audit.json). All common-prefix features/commands match.
Three model fits actually ran on Modal; all three checkpoints reload and their
training predictions reproduce with local refits. [Fit receipt](fit-receipt.json),
[model audit](model-audit.json), [selection audit](selection-audit.json).

## Frozen model selection — fresh test pending

Every fit uses **192 training worlds**, 49 public features and 11 strategy-return
labels per world. The 48 validation worlds choose algorithms and thresholds;
they do not fit weights. Both selected thresholds are zero predicted gain.
Extra Trees is the predeclared primary; ridge is the second learner. All weights
and this choice are saved in [selection.json](selection.json) before opening
worlds 562000–562095. Gradient boosting remains available but was not selected.

| Validation method | Mean score | Gain vs reference | Home/alive |
|---|---:|---:|---:|
| Frozen reference | 50.1011% | — | 48/48 |
| Extra Trees, threshold 0 | 50.7287% | +0.6276 pp | 48/48 |
| Ridge, threshold 0 | 50.6527% | +0.5516 pp | 48/48 |
| Gradient boosting, best threshold .005 | 50.2483% | +0.1472 pp | 48/48 |
| Best fixed strategy: aggressive | 50.7567% | +0.6556 pp | 48/48 |

These are selection results, not fresh-test claims. Extra Trees chose the
aggressive strategy on 40/48 validation maps. Choosing the best strategy with
hindsight gains only 0.8634 pp on this validation set, a ceiling for this particular
12-strategy portfolio, not for other possible controllers. Detailed prediction
errors, all thresholds and strategy choices are in [diagnostics](diagnostics.json)
and [selection](selection.json). No reference promotion.
