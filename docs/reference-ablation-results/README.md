# Reference ablation results

Protocol: [component sweep](../reference-ablation.md). This package leaves the
frozen normal Traverse reference, rules and tasks unchanged.

The implementation passes seven focused tests: exact baseline command/trajectory
equivalence, cubature linear/zero-uncertainty limits and covariance stability,
process-noise identity, seed exclusions, selection constraints and matrix
completeness. All 15 quick smoke missions completed alive at home with no invalid
calls or exceptions. All 15 physics replays and diagnostics reproduce; the full
baseline and cubature controllers were also repeated exactly. Smoke uses an
already-used world and a reduced search budget; it is not evidence of improvement.

## Development: 12 matched worlds, 180 missions

All 180 missions ended alive at home, with no invalid calls or controller exceptions.
The complete physics trajectories, grades, stored diagnostics and paired statistics
were recomputed by the [audit](development/audit.json). Runtime was 1,077 seconds
(18 minutes) on six local workers. These maps were used for selection; gains
and intervals here are exploratory. No fresh-map result is available yet.

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

The cubature estimator slightly reduces position RMSE but leaves the score
unchanged on every development map. Increasing the search budget by 50%
costs 45% more CPU for a mean score gain of only 0.000109.
The largest gain, a higher path energy price, is 0.003105 reward; its
ordinary interval is [0.000063, 0.006481], before accounting for selection.

The [frozen selection](selection.json) advances `path_energy_high` and
`home_later` individually, plus the predeclared combination of the three
best eligible components: `energy_weight=0.5`, `home_margin=2.0`, `floor=3.5`.
The combination is the primary candidate. Baseline and these three candidates
will be evaluated on worlds 451000–451031 (128 missions), with no further tuning.

[Full report](development/report.json) · [Table CSV](development/table.csv) ·
[Per-world CSV](development/per-world.csv) · [Source freeze](development/freeze.json)

```sh
python3 -m unittest discover -s tests/reference_ablation -v
python3 -m tools.reference_ablation.run development --workers 6
python3 -m tools.reference_ablation.audit development --workers 6
python3 -m tools.reference_ablation.run select
python3 -m tools.reference_ablation.run confirmation --workers 6
python3 -m tools.reference_ablation.audit confirmation --workers 6 --full baseline,combined
```

The confirmation command requires the frozen selection. If only one component
qualifies, the full-repeat name is that individual, not `combined`. The outputs
are source-pinned; reproduce from the recorded commit rather than repinning old
results to a later reference.
