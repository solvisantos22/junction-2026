# Modal planner lab — next wave

The [fixed protocol](../planner-lab.md) tests 16 earlier/adaptive planner strategies
and four learned selector families, against both the canonical reference and the
previous frozen Extra Trees selector. Training, validation and fresh ranges are
new and disjoint from the prior study and teammate claims.

Eight local tests passed, covering deep-copy isolation, ordinary-run parity,
original-reference and prior-model parity, delayed activation/reset behavior,
public-data/seed boundaries, the complete job grid, and four model fits/checkpoint
round trips. [Test output](local-tests.txt).

The Modal smoke completed all 34 missions on used implementation worlds 1/2
with no controller errors or invalid calls. All 34 replay exactly on both Linux
and this Mac. Three full Linux controller reruns match the archived trajectories:
the actual original reference, the actual prior Extra Trees policy, and a new
guarded strategy run without prefix copying.
[Inventory](smoke/inventory-audit.json), [Linux replay](smoke/cloud-audit.json),
[local replay](smoke/local-audit.json), [full repeats](smoke/repeat-audit.json).

Production will collect 7,232 training/validation missions, fit all four models,
and publish the selection before opening the 960-mission fresh comparison.
No new performance claim yet. The canonical simulator, reference, prior study
and teammate learners are unchanged.
