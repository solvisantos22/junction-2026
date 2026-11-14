# Persistent goals: results and handoff

This is the user-approved local diagnostic under the
[fixed protocol](../lightlag-rl-persistence.md), following the
[first RL pilot](../lightlag-rl-results/README.md). It tests a commitment rule on
previously visited training maps using unchanged weights and navigation.

## Verified preparation

All **21 focused tests pass**: exact pass-through replay/RNG equivalence,
commitment/release behavior, full-horizon grading, immutable inputs, paired
summary/gates, partial failures, source drift and tamper detection.

The [20-case smoke comparison](smoke/report.json) on used maps 1/2 completed.
Its [audit](smoke/audit.json) reproduces all physics replays and grades, plus
877 proposals/effective choices (306 retentions, 243 overrides) against 42 source
pins. Smoke results are execution verification, not the primary result or an
input to tuning. No production diagnostic cases have run at this increment.

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

The production diagnostic uses the 24 predeclared already-visited training maps
and 240 missions. No fresh check maps, retraining, model API or cloud job are
part of this diagnostic. Record its completed result and decision here.
