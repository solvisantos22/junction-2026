# Second development recovery: verified freeze, not yet launched

The first recovery stopped at **01:12:02 UTC on 15 November** after collecting
all 2667 calls it had submitted: 2665 complete and two failed. Together with
the original 3145 completions, **5810 of 8320 unique cases are verified**.
There are **2508 never-submitted cases** and two failed cases without a saved
completed episode. No training is resumed; this is fixed-policy inference.

[Diagnosis](diagnosis.json) · [both original failed attempts](failed-attempts.json) ·
[stable second reads](stable-failure-recheck.json) ·
[terminal call metadata](terminal-output-metadata.json) · [stopped app](app-status.json).
The original recovery app is `ap-VMFyA1rZFxPhVr14SGth33`, call
`fc-01M7EB3DJ8C214Z7E14WCVVTNF`. Its source, freeze, state, ownership and worker
guards remain unchanged.

One failed call returned `KeyboardInterrupt`; the other returned
`AmbiguousExecutionRequiresDiagnosis`, meaning its original execution guard
prevented an infrastructure re-entry from repeating work silently. Both calls
have zero unfinished inputs. The app has stopped with zero tasks. Reads more
than 180 seconds after execution found only the original failed row in each
folder; repeat reads 109.6 seconds apart were unchanged. A complete inventory
of **29,398 control keys** found none of the five launch/execution keys for any
of the 2508 unstarted jobs. Independent review reproduced that absence check.
An [app-level preemption event](platform-event.json) occurred in this window,
but the available task IDs do not establish that it caused either failure.
Lost, uncommitted simulation work cannot be excluded.

The authorized continuation is being implemented as a separate, one-shot
attempt: **exactly 2510 cases**, preserving all 5810 completed rows and both
failed attempts. The same 8320 scientific job identities, maps, weights,
controllers and audits apply. New attempt namespaces must leave old guards
and artifact paths intact. All 64 workers and the coordinator will be
non-preemptible, one CPU and 2 GiB each, with the 3× CPU/memory rate recorded
separately from the frozen worker's original estimate. There is no automatic
retry after another failure.

A new source/resource/lineage freeze and independent code review are required
before this continuation launches. The **05:30 UTC cutoff and shared $75
running-compute ceiling** remain unchanged. At 01:22 UTC, allocating all 65
non-preemptible containers continuously to the cutoff would cost approximately
$50.81; recorded earlier hybrid/prior compute is approximately $3.34. These
are running-compute estimates, not invoices or credit balances; startup,
storage, builds, egress and lost unrecorded invocation time are not included.
Actual prior compute plus a conservative historical allowance must fit the cap.

**No partial-result selection.** Only the full 8320-case audited aggregate may
feed the original development selection. The old `stages.py` adapter requires
a successful first recovery and therefore cannot advance this failed lineage.
A separately frozen `stages2.py` must bind the new lineage and reproduce the
unchanged selection gates. Confirmation 611000–611255 and final
612000–612255 remain unopened. The team reference remains unchanged.

The separate greedy-prior training experiment is closed and published; its
late watcher alert was reconciled against all six original calls in
`88279ee`. It requires no launch, restart, new download or final evaluation.

## Verified execution freeze — 15 November 01:36 UTC

[Freeze](freeze.json), SHA256
`953247698699653d4ea3a8800e3e0710097be4d1f6fd784e3f184393d44f7527`,
was created with full source checks in `/tmp/junction-hybrid-recovery2-frozen`.
[Verification](prelaunch-verification.json): 16 recovery, nine later-stage and
25 watcher tests pass; independent code review cleared. All 54 original
scientific source files and the parent-policy file match their protected pins.
New teammate one-shot harness changes on `main` are preserved; this experiment
uses its earlier frozen snapshot. Neither the science nor the weights changed.

The new operations code rejects completed development cases at the worker
boundary, binds each permitted attempt to its one-shot intent, checks both
failed original calls and late case/temp artifacts before reservation, and
rechecks the global stop/deadline before spawning. Original rows and guards
are never reset. Attempt storage and raw-row hashes are explicit; worker
costs use the non-preemptible 3× rate. No automatic further recovery.

The conservative combined running-allocation ledger is **$65.443 maximum**:
$9.092736 for the entire earlier training allowance, $8.360583 for the prior
hybrid allocation allowance and $47.989679 for all 65 non-preemptible
containers continuously through 05:30 UTC. It excludes ancillary charges and
is not a predicted bill. Actual recorded usage is much smaller.

Execute only once, after this freeze reaches `origin/main`, from the snapshot:

```sh
MODAL_PROFILE=solvi-junction PYTHONPATH=/tmp/junction-hybrid-recovery2-frozen /tmp/junction-learning-venv/bin/python -m tools.learning_hybrid_ops.recovery2 --launch docs/learning-hybrid-results/development/recovery2/freeze.json --receipt /tmp/junction-hybrid-recovery2-monitor/development-receipt.json --root /tmp/junction-hybrid-recovery2-frozen
```

Inspect that original receipt with `--status`; after terminal completion use
`--download RECEIPT --output NEW_DIRECTORY`. Never reuse the launch command
for an existing reservation. The complete aggregate retains the 5810 previous
rows exactly and explicitly binds both earlier failures.

For later stages, use **`tools.learning_hybrid_ops.stages2`** from this same
snapshot, with the unchanged `experiment analyze` / `experiment prepare`
selection commands. Confirmation requires its complete development aggregate,
this recovery freeze and original receipt. Final requires the original
confirmation state/analysis, its operations freeze and receipt. Each selection
and stage freeze must reach `main` before its new maps open. Standard receipts
remain compatible with the original watcher at
`/tmp/junction-learning-hybrid-monitor/{confirmation,final}-receipt.json`.
The adapter checks the actual original terminal FunctionCall results before
launch and remotely; final downloads verify both raw worker rows and mapped
artifact paths. No confirmation/final selection or execution has occurred.
