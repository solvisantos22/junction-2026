# Modal planner lab — selection frozen

The [fixed protocol](../planner-lab.md) tested 16 earlier/adaptive planner strategies and four learned selector families. All **7,232 training/validation missions** completed with zero controller errors or invalid calls. Poor scores and deaths remain in the data.

**Random Forest is the primary selected model**, with the pooled forest as the second family. Checkpoints and settings are published before opening fresh worlds **572000–572191**. Both canonical reference and previous frozen Extra Trees are retained as controls; best fixed strategy is `balanced_early`.

## Validation selection (64 worlds)

| Policy | Mean score | Gain vs reference | Home/alive | Deaths | Eligible |
|---|---:|---:|---:|---:|---|
| Frozen reference | 51.6814% | +0.0000 pp | 64/64 | 0 | yes |
| Previous Extra Trees | 51.4077% | -0.2737 pp | 63/64 | 1 | no |
| extra_trees | 51.6814% | +0.0000 pp | 64/64 | 0 | yes |
| mlp | 50.4235% | -1.2579 pp | 63/64 | 1 | no |
| pooled_forest | 51.6883% | +0.0069 pp | 64/64 | 0 | yes |
| random_forest | 52.0685% | +0.3871 pp | 64/64 | 0 | yes |

These are selection results, not fresh confirmation. Random Forest uses threshold .002 and tree-disagreement penalty .5. Pooled forest uses threshold .005 and failure penalty .3. Extra Trees’ best eligible setting always keeps the baseline; the MLP fails validation eligibility. All four original weights are retained.

Even a chooser that knew the outcomes in advance could gain only **1.1429 points** on validation with this strategy set. This is a descriptive ceiling, not an executable policy. The original >=1 point practical-upgrade criterion remains unchanged.

## Verification before fresh evaluation

- All **7,232 Linux replays match exactly**, including commands, trajectories and grades. The independent Mac physics audit is still running.
- Two full production controllers reproduce the saved first training-world trajectories: actual original reference and a new guarded strategy without prefix copying.
- All 64 prior-model validation choices reproduce; all 24 candidate settings, rankings, four checkpoint hashes/training predictions, label matrices and selected controls independently verified.
- Earlier smoke: 34 exact Linux/Mac replays, three full controller parity checks; eight controller/model tests pass. An additional concurrent-report test passes after making audit-file writes use unique temporary files. Controller/model source remains unchanged.

[Selection](selection.json) · [selection audit](selection-audit.json) · [development diagnostics](development-diagnostics.json) · [Linux audit](data/cloud-audit.json) · [controller repeats](data/repeat-audit.json) · [decisions](data/decision-audit.json) · [models](models/) · [raw receipts](data/receipts.jsonl) · [original tests](local-tests.txt) · [concurrent report test](archive-tests.txt)

## Execution

The data app used up to 100 Modal workers: [run](https://modal.com/apps/kristjansolvi03/main/ap-TtfKs4QfMlfHhGfWIsbP7n). Four logged platform preemptions restarted the same inputs automatically; no completed archived batch was rerun. All source/job hashes remain fixed. First/second progress snapshots preserved 1,308 and 3,964 missions. Fitting used four parallel calls, with checkpoint metadata and call IDs saved in [fit receipt](fit-receipt.json). No GPU or LLM calls.

The fresh stage will evaluate five policies on 192 matched worlds, **960 missions**, with frozen settings and paired confidence intervals. The canonical reference, simulator, tasks and teammate learners remain unchanged.
