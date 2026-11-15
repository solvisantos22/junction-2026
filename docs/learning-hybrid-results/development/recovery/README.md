# Development continuation after coordinator interruption

Only the **5175 never-submitted jobs** in the original 8320-case matrix may
run. The original 3145 submissions all completed and remain retained. The
original failed coordinator state and its call/owner keys are unchanged.
[Reconciliation](reconciliation.json) binds the original call IDs, the 15
retrieved completions and every remaining job. A complete 16,059-key inventory
found no prior intent, call, worker state, owner or execution key for any
remaining job.

The separately frozen operations wrapper uses the exact original 54 scientific
source pins, original parent weights, maps, controller, worker and audit logic.
Only its coordinator changes: it is non-preemptible, with one CPU and 2 GiB
and the documented 3× CPU/memory price. Workers retain the original cap of
64, each one CPU/2 GiB, with no user-code retries. The original 05:30 UTC cutoff
and shared $75 running-compute ceiling remain in force.

The launcher rechecks the complete remote key inventory and stop/deadline
before one-shot reservation; each job then needs a new atomic launch intent.
Ambiguous submissions stop for diagnosis. A separate recovery folder stores
its receipts and state. Only all 8320 unique original audited completions may
produce a new combined record with explicit recovery provenance. That record
will feed the unchanged development selection; no partial-result selection.

The [source/resource freeze](freeze.json) is now prepared for publication before launch. Fourteen recovery tests and 23 watcher tests pass, with independent review. The remaining allocation ceiling is approximately $19.80 through 05:30 UTC; exact creation time and estimate are in the freeze. The new watcher recognizes only this explicit recovery status module, retaining the existing pause/stop and at-most-once wake-up checks. The existing private watcher is unchanged. No confirmation or final maps have opened. The original stage
control record remains failed: later-stage orchestration must explicitly accept
the verified combined record rather than overwrite the original failure.

The original 3145 workers recorded $0.45894 estimated running CPU/memory, and
the original coordinator $0.03876. These figures exclude startup, idle time,
builds, storage and egress and are not an invoice. The 15 recovered episode
archives were downloaded and hash-verified; the other retained trajectories
remain on Modal with their previously recorded audits.

## Live execution and continuation

Freeze **`e098ade`** preceded launch; SHA256
`4c1c1d16cd54c754a81f7d1b984d4ed187706e6e41fd3c1068639819ee40906a`.
App **`ap-VMFyA1rZFxPhVr14SGth33`**, original recovery call
**`fc-01M7EB3DJ8C214Z7E14WCVVTNF`**.
[One-shot receipt](development-receipt.json), [first live status](initial-status.json),
[original failure preservation check](launch-verification.json).

Runtime source snapshot: `/tmp/junction-hybrid-recovery-frozen`; original
source snapshot `/tmp/junction-hybrid-frozen` is unchanged. Inspect from the
recovery snapshot with `python -m tools.learning_hybrid_ops.recovery --status
/tmp/junction-hybrid-recovery-monitor/development-receipt.json`. After terminal
completion, use `--download RECEIPT --output NEW_DIRECTORY`; keep both original
failed state and the separate combined result. Never invoke `--launch` again
for this receipt/reservation.

The new read-only watcher is PID **50211**, sleep guard **50212**, in
`/Users/solvisantos/.codex/junction-learning-hybrid-recovery-watch-20261115/`.
It polls this exact call every 60 seconds and queues at most one completion
wake, with a 05:35 UTC fallback. A live poll verified running state with 19
audited completions and no read errors. Its local pause/stop switches are
linked to the original watcher's switches: creating `wake-stop`, `pause.json`
or `stop` in the original watcher runtime also disables this watcher. Root
worktree pause/stop markers remain honored. These switches disable wake-ups;
they do not cancel already authorized cloud calls. No old watcher is restarted.

The next-stage operations adapter is being prepared separately because the
original development control record must remain failed. It must consume the
complete verified combined record, reproduce the unchanged group-selection
rules, and publish each selection/stage freeze before opening later maps.
