# Modal planner lab — next wave

The [fixed protocol](../planner-lab.md) tests 16 earlier/adaptive planner strategies
and four learned selector families, against both the canonical reference and the
previous frozen Extra Trees selector. Training, validation and fresh ranges are
new and disjoint from the prior study and teammate claims.

Eight local tests passed, covering deep-copy isolation, ordinary-run parity,
original-reference and prior-model parity, delayed activation/reset behavior,
public-data/seed boundaries, the complete job grid, and four model fits/checkpoint
round trips. The Modal smoke run is next; no production model/result yet.

The canonical simulator, reference, prior study and teammate learners are unchanged.
