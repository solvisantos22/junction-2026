# Reference ablation results

**No clear reference upgrade was found. Keep the frozen reference.** Fourteen
changes were compared with the unchanged pilot on 12 development worlds, then
a frozen selection was checked on 32 new worlds. The primary combination gains
only **0.001023 reward (0.102 percentage points)** on fresh maps; its paired 95%
interval is **[-0.003556, +0.005227]**, which includes zero. It fails the
predeclared 0.01 improvement and positive-interval criteria. This is evidence
about these tested changes, not proof that the reference cannot be improved.

All **308 benchmark missions** (180 development + 128 confirmation) finished
alive at home, with no invalid calls or controller exceptions. The 15 smoke
missions also finished alive at home. No simulator, canonical pilot, task,
viewer or teammate learning package was changed. No cloud job or model API call.

## Fresh confirmation: 32 paired worlds

| Configuration | Mean score | Change (percentage points) | Paired 95% interval (points) | Home/alive | CPU vs baseline |
|---|---:|---:|---:|---:|---:|
| Unchanged reference | 0.523064 | — | — | 32/32 | 1.00x |
| Higher path energy price | 0.523814 | +0.075 | [-0.398, +0.516] | 32/32 | 0.99x |
| Return two ticks later | 0.523264 | +0.020 | [-0.343, +0.351] | 32/32 | 1.00x |
| Combined changes | 0.524087 | +0.102 | [-0.356, +0.523] | 32/32 | 0.99x |

The primary combination is exactly `energy_weight=0.5`, `home_margin=2.0`,
`floor=3.5`; other settings retain the reference defaults. The individual
changes are secondary comparisons. Their multiplicity-adjusted intervals also
include zero; ordinary and family-adjusted intervals are retained in the
[full report](confirmation/report.json) and [table CSV](confirmation/table.csv).

The combination wins on 18 worlds, ties on 8 and loses on 6. The gains contribute
+0.004483 to the overall mean; the losses subtract 0.003460. Two illustrative
extremes, selected only after the experiment: world 451026 gains 0.035377 with
28 rather than 26 samples; world 451011 loses 0.039583 with the same sample count
but different sample value/timing. These examples do not establish the mechanism
of every difference. [All paired outcomes and extreme cases](confirmation/posthoc-analysis.json).

## What changed inside the primary candidate

These are averages across the same 32 confirmation worlds. Every rover survives
and returns, so score differences arise from credited sample value. The small
increase in sample count does not translate into a reliable reward improvement.

| Diagnostic | Baseline | Combination |
|---|---:|---:|
| Samples collected | 24.5000 | 24.6875 |
| Late samples | 2.6875 | 2.7500 |
| Failed sampling attempts | 0.1562 | 0.1875 |
| Pose RMSE at telemetry timestamp (m) | 0.5927 | 0.5996 |
| Queued-position prediction RMSE (m) | 0.9012 | 0.9138 |
| Minimum battery during mission | 13.0365 | 11.7390 |
| Controller CPU seconds | 29.4382 | 29.1349 |

Position diagnostics are calculated after the episode from saved truth, never
provided to a controller. RMSE columns average per-mission RMSE, and the queued
prediction is aligned with the true state immediately before its execution tick.

## Development: every tested change

All configurations below played worlds 450000–450011. These data were used to
select candidates; they are exploratory. The original full search budget was
retained except for the explicitly larger-search variant.

| Variant | Mean score | Change (percentage points) | Home/alive | Pose RMSE (m) | CPU vs baseline |
|---|---:|---:|---:|---:|---:|
| `path_energy_high` | 0.516507 | +0.311 | 12/12 | 0.5871 | 0.99x |
| `home_later` | 0.514241 | +0.084 | 12/12 | 0.5849 | 1.00x |
| `energy_reserve_lower` | 0.513914 | +0.051 | 12/12 | 0.5869 | 0.97x |
| `search_frequent` | 0.513742 | +0.034 | 12/12 | 0.5884 | 1.28x |
| `search_more` | 0.513511 | +0.011 | 12/12 | 0.5864 | 1.45x |
| `baseline` | 0.513402 | — | 12/12 | 0.5855 | 1.00x |
| `est_cubature` | 0.513402 | +0.000 | 12/12 | 0.5846 | 1.00x |
| `est_process_double` | 0.511722 | -0.168 | 12/12 | 0.6208 | 1.02x |
| `slip_fast` | 0.511719 | -0.168 | 12/12 | 0.5813 | 1.03x |
| `arrival_wider` | 0.511638 | -0.176 | 12/12 | 0.5816 | 0.99x |
| `solar_prior_mid` | 0.510839 | -0.256 | 12/12 | 0.5867 | 1.02x |
| `path_energy_low` | 0.507810 | -0.559 | 12/12 | 0.5822 | 1.05x |
| `deadline_earlier` | 0.507709 | -0.569 | 12/12 | 0.5864 | 0.99x |
| `legs_cautious` | 0.506508 | -0.689 | 12/12 | 0.5805 | 0.95x |
| `slip_cautious` | 0.500904 | -1.250 | 12/12 | 0.5873 | 1.06x |

- **Estimator:** cubature heading propagation leaves the score unchanged on all
  12 maps, while mean pose RMSE moves from 0.5855 m to 0.5846 m. This small
  estimator change was not selected for fresh confirmation. Doubling process
  noise increases pose RMSE to 0.6208 m and lowers mean reward by 0.001680.
- **Search:** 50% more steps/beam costs 45% more controller CPU for a reward gain
  of only 0.000109; replanning twice as often costs 28% more CPU for +0.000339.
- **Path costs:** doubling the energy price was the best development change
  (+0.003105); its fresh-map gain shrinks to +0.000750 and is uncertain.
- **Conservative assumptions:** the pessimistic slip prior loses 0.012498,
  5% longer predicted legs lose 0.006895, and earlier deadline margins lose
  0.005693 in development. These are not fresh-confirmed comparisons.

[Development report](development/report.json) · [Table CSV](development/table.csv) ·
[Development per-world CSV](development/per-world.csv) ·
[Confirmation per-world CSV](confirmation/per-world.csv)

## Verification and reproduction

Protocol and exact changes: [predeclared protocol](../reference-ablation.md),
[variant implementation](../../tools/reference_ablation/variants.py). Development
code was frozen at `93118be`; all 180 results and the candidate selection were
published in `ca558c9` before confirmation began. Runtime source hashes are
identical across smoke, development, selection and confirmation. Both map ranges
are now consumed and must not be called unseen in later work. Submission worlds
2026–2029, example 99991 and the MAX reserved pool were untouched.

Seven focused tests pass, including exact wrapper/original-pilot equivalence,
cubature limiting cases and covariance stability, seed separation and selection
constraints. All **323 archived physics trajectories**, grades, diagnostics and
matrices were recomputed. The baseline and cubature controllers were repeated
exactly on the smoke world; the full-budget baseline and combination were
repeated exactly on confirmation world 451000. This verifies four controller
repeats, not an independent controller rerun for every archived mission.

Benchmark stages took 1077.1 seconds for development and 649.0
seconds for confirmation on six local workers (about 29 minutes combined).
These times exclude implementation, publication and the separately recorded audits.

[Smoke audit](smoke/audit.json) · [Development audit](development/audit.json) ·
[Confirmation audit](confirmation/audit.json) · [Candidate freeze](selection.json)

From a checkout with the recorded source hashes, verify saved results with:

```sh
python3 -m unittest discover -s tests/reference_ablation -v
python3 -m tools.reference_ablation.audit development --workers 6
python3 -m tools.reference_ablation.audit confirmation --workers 6 --full baseline,combined
```

To reproduce the experiment, use a **new output directory** and run `development`,
`select`, then `confirmation`, each through `python3 -m tools.reference_ablation.run`
with the same `--out` path. Existing archives are the original evidence. Audits
refuse changed source inputs; do not repin old results to a newer controller.
