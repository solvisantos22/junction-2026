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
Data generation is running in Modal app
[`ap-tctysvmd3CxtowroSpSlM0`](https://modal.com/apps/kristjansolvi03/main/ap-tctysvmd3CxtowroSpSlM0),
launched 14 November at 23:14 UTC. The workspace reached 97 simultaneous workers
for this run. [Frozen jobs/source](data/freeze.json) and [app receipt](data/app.json)
were recorded before results. Results will be appended after each declared stage
completes; no model has been selected yet.
