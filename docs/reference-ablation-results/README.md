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

Development and confirmation results will be added here after their predeclared
stages finish. Every result and failure remains in the archives.

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
