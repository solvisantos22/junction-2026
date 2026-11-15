# Confirmation selection freeze — not yet launched

The [complete development analysis](../development/completed/analysis.json)
selects exactly six groups using the original rule: the top two safe groups
in each of the single-policy shortlist, ensemble and blend families. No seed,
checkpoint, threshold or score rule changed after seeing the development data.
The development results are screening evidence, not a confirmed improvement.

[Stage matrix](stage.json): **21 deterministic arms × 256 maps = 5376 cases**,
worlds **611000–611255**. The ten selected individual arms include all three
training seeds for each of the two single-policy groups. Eleven matched
controls retain greedy, the frozen beam reference, all six pure individual
policies and the three pure ensembles. Full membership is in the stage file.

[Operations/source/resource/lineage freeze](ops-freeze.json), SHA256
`9e638ba0decb6e712ff903ca7f213d2fbb13f5f2360b6431b6ab930968e9e87e`,
binds the exact completed development aggregate, original analysis, all parent
weights, prior recovery receipts and immutable source snapshots. It retains
the original 05:30 UTC cutoff, 64 one-CPU/2-GiB workers plus one coordinator,
all non-preemptible at the documented 3× CPU/memory rate. The conservative
shared running-allocation ledger remains $65.443 under the $75 cap; this is
not a predicted bill or credit balance.

Only execute after all evidence and this freeze reach `origin/main`. Use
`/tmp/junction-hybrid-recovery2-frozen` as cwd and PYTHONPATH; mutable main now
contains newer teammate harness files. The already-reviewed `stages2` adapter
checks actual original terminal results and live receipt identities locally
and remotely before the new stage. The original failed states remain intact.

```sh
cd /tmp/junction-hybrid-recovery2-frozen
MODAL_PROFILE=solvi-junction PYTHONPATH=/tmp/junction-hybrid-recovery2-frozen /tmp/junction-learning-venv/bin/python -m tools.learning_hybrid_ops.stages2 --launch /tmp/junction-hybrid-confirmation-ops-freeze-20261115.json --receipt /tmp/junction-learning-hybrid-monitor/confirmation-receipt.json --root /tmp/junction-hybrid-recovery2-frozen
```

Never repeat that one-shot launch. The original read-only watcher already
watches the standard confirmation receipt path; it does not launch or select.
After terminal completion, download metadata once and reproduce the original
analysis. Among only these six shortlisted groups, require zero deaths/errors/
invalid calls, home rate at least greedy minus 1/256, and positive paired mean
gain over greedy. Choose the eligible group with highest mean reward, breaking
exact ties by group ID. If none qualifies, publish the negative result and
leave final maps unopened. Otherwise publish its final stage/operations freeze
before opening **612000–612255**. The final success gate remains at least one
percentage point over greedy with positive paired 95% lower bound and the
predeclared safety checks. Keep the current reference.
