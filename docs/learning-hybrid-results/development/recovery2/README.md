# Second development recovery: diagnosed, not yet launched

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
