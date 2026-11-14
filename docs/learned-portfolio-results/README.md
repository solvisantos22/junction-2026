# Modal learned planner portfolio

[Protocol](../learned-portfolio.md). Three classical models will learn which
planner strategy to switch to once at tick 140, using 49 public-state features.
The frozen reference, task and teammate learners remain unchanged.

Six focused tests pass. All 12 Modal smoke missions completed home/alive with no
invalid calls or controller errors. Their pre-switch commands and features match
exactly; the baseline's full replay matches a local run exactly. The Modal SDK
emitted a stream-cleanup warning after all results completed; it is retained in
[smoke verification](smoke/verification.json), and the iterator will be fixed
before production. Smoke app: `ap-qApEtSS6Dc08zx9gzidYBn`.

Production: 192 training worlds and 48 validation worlds, each with 12 strategies
(2,880 missions). Three model fits run in parallel on Modal. After selection is
frozen, 96 fresh worlds compare baseline, best fixed strategy and two learners.
Results will be appended after the declared stages complete.
