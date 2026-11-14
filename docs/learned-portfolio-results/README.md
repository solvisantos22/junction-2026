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
No model has been selected yet; results follow after each declared stage completes.
