# Confirmation selection freeze — complete

**Completed and independently audited:** 5376/5376 cases, 5372 jointly home/alive, 3 deaths, zero invalid calls. The unchanged rule selects `ensemble-all-rho090`: 0.380209 versus greedy 0.375202 and reference 0.500510. Its gain interval includes zero; this remains selection evidence. [Complete results](completed/README.md) and [final selection freeze](../final/README.md). Earlier launch/status records below are retained as history.

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

## Live handoff — 15 November 02:09 UTC

The complete development data, selection, matrix and operations freeze reached
`origin/main` in **`2256f63` before this single launch**. App
**`ap-mAROrYr7XrA7sT2t7Z5zMI`**, original coordinator call
**`fc-01M7EFBZEQXETSYPQH3PCREV4D`**. [Durable receipt](receipt.json),
[first status](initial-status.json), [independent live audit](launch-verification.json).
The launcher exited normally; a final client log-stream timeout did not stop
the detached call. Do not relaunch this receipt or reservation.

First status: 88/5376 complete. The independent live check confirms
**265/5376 completed**, no reported errors or pause/stop markers, correct
source/freeze/stage/receipt identities, and all earlier failure/recovery
control records unchanged. All scientific outcomes, including future deaths
or unsuccessful missions, remain part of the stage; a healthy execution status
is not a claim about performance or safety results.

The original read-only watcher is active at
`/Users/solvisantos/.codex/junction-learning-hybrid-watch-20261115`, PID **37521**.
It recognized this standard receipt with zero read errors; it was not rearmed
or replaced. It checks every 60 seconds and requests continuation on a terminal
result or repeated read failure, with the existing 05:35 UTC fallback and shared
pause/stop behavior. No old training or failed recovery is restarted.

Allow roughly **30–45 minutes from the 02:08 UTC start** at observed throughput,
conditional on continued health. The next checkpoint is complete confirmation,
followed by all-row audit and the unchanged one-group selection. Execute
`tools.learning_hybrid_ops.stages2 --download RECEIPT --output NEW_DIRECTORY`
from the frozen snapshot after the original call is terminal. Analyze saved
confirmation metadata with the unchanged experiment tool. If no group
qualifies, close the experiment without opening final maps. Otherwise publish
the final manifest and operations freeze before its one-shot launch at
`/tmp/junction-learning-hybrid-monitor/final-receipt.json`. For that freeze pass
this operations freeze and original receipt as `--previous-ops-freeze` and
`--previous-receipt`. Preserve all outcomes and keep the reference unchanged.

**612000–612255 remain unopened.** Greedy-prior training is closed and its
fresh 629000–629127 range also remains unopened. The immutable source snapshot
is `/tmp/junction-hybrid-recovery2-frozen`; do not use mutable main imports for
analysis or launch.
