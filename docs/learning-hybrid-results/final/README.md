# Final selection freeze — running

The [complete confirmation analysis](../confirmation/completed/README.md)
selects exactly **`ensemble-all-rho090`**, the rank ensemble of all six retained
policies with the fixed 90% greedy-efficiency shortlist. This is the sole
primary group. No training seed, checkpoint, threshold or selection rule
changed after seeing confirmation results.

[Stage matrix](stage.json), SHA256
`9f0f97312614ad9321e7284cef8dade52d9b2fde6948c019ffb5187c71b2df0a`:
**10 arms × 256 reserved worlds 612000–612255 = 2560 cases**. The controls are
unchanged greedy, the frozen beam reference, all six unmodified individual
policies (PPO/replay seeds 17/29/43), and the pure all-six rank ensemble. The
parent weights remain those in the original published policy freeze: PPO
17/29/43 and replay 17/29 at 8192 missions; replay 43 at its retained 2048 role.

[Operations/source/resource/lineage freeze](ops-freeze.json), SHA256
`f79ce4f9b42549aed0ccdfd53c6ce17da03e259a5c400323ab816ddc3892864d`,
binds the complete development and confirmation evidence, original receipts,
source/runtime, parent weights and previous failures. The existing allocation
ledger remains $65.443 under the $75 shared running-compute cap. All 64 workers
plus one coordinator retain one CPU/2 GiB, non-preemptible at 3× the original
rate, no GPU/retries and absolute **05:30 UTC** cutoff. No new budget envelope
is reset for this stage.

## Launch and completion handoff

Publish this exact freeze and the completed confirmation evidence to main
before launch. Use cwd and PYTHONPATH **`/tmp/junction-hybrid-recovery2-frozen`**;
mutable main's newer harness files must not enter this frozen experiment.

```sh
cd /tmp/junction-hybrid-recovery2-frozen
MODAL_PROFILE=solvi-junction PYTHONPATH=/tmp/junction-hybrid-recovery2-frozen /tmp/junction-learning-venv/bin/python -m tools.learning_hybrid_ops.stages2 --launch /tmp/junction-hybrid-final-ops-freeze-20261115.json --receipt /tmp/junction-learning-hybrid-monitor/final-receipt.json --root /tmp/junction-hybrid-recovery2-frozen
```

That launch is one-shot. Reconcile its saved original call before doing
anything after disconnect, timeout or error; never rerun completed jobs. The
existing read-only watcher already watches the final receipt path, respects
pause/stop markers and does not launch, download or select.

After the original call finishes, download final metadata and artifacts once
using `stages2 --download RECEIPT --output NEW_DIRECTORY --artifacts` from the
frozen snapshot. Every final case must already have passed physics, hybrid
choice and full controller-repeat audits. Verify all downloaded compressed
case and original worker-row hashes, saved calls and mapped rows, and reproduce
the unchanged final analysis. Preserve all safety failures and partial results;
diagnose errors before any new spend.

Success requires **at least 0.01 mean gain over greedy**, paired-map bootstrap
95% lower bound above zero, zero deaths/errors/invalid calls, and joint
home/alive rate at least greedy minus 1/256. Use the original 20,000 bootstrap
resamples, seed 612256. No tuning or selection follows these final worlds.
Publish positive or negative findings, all controls, a shareable figure and
paragraph, measured compute estimates and prize evidence. Reference promotion
is not automatic; **keep the current reference**.

At this freeze's creation, final worlds remain unopened. Greedy-prior's
629000–629127 range remains unopened and its interrupted six-run comparison
stays closed. No old training or recovery is resumed.


## Live handoff — 15 November 02:54 UTC

The complete confirmation evidence, selected group and exact final freeze
reached `origin/main` in **`67a9203f` before this single launch**. App
**`ap-GzqnjGbRi4h0x0SqO4xiQW`**, original coordinator call
**`fc-01M7EHYJ7272Q4Z5432990CT78`**; [durable receipt](receipt.json),
[first status](initial-status.json), [independent live audit](launch-verification.json).
The detached coordinator started at **02:53:09 UTC**. The launcher exited zero;
its final client log-stream timeout did not stop the submitted call. Never
relaunch this receipt or reservation.

The independent live check found **30/2560 complete** and the existing watcher
recognized the same receipt at **58/2560**, with zero read errors or pause/stop
markers. Source, parent weights, stage and operations freeze match. The original
confirmation terminal result and all 20 prior failure/recovery/confirmation
control records are unchanged. These are execution-health observations, not
final performance or safety claims.

The original watcher remains active at
`/Users/solvisantos/.codex/junction-learning-hybrid-watch-20261115`, PID **37521**.
It checks every 60 seconds and requests continuation at a terminal result or
repeated read failure, with the existing 05:35 UTC fallback. It was not rearmed
or replaced. Allow roughly **20–40 minutes from 02:53 UTC** for the compute
stage if health/throughput hold; full archive download and auditing follow.

This is the **last planned run of this experiment**. After completion, audit
and publish the frozen comparison, figure, paragraph and evidence. No new
training, retuning on final worlds, automatic extension or recovery follows.
Any infrastructure failure must be diagnosed before any separate action.
Greedy-prior remains closed and the current reference stays unchanged.


**Sölvi's submission direction, 15 November:** with roughly 3–4 hours left,
finish this number and then switch entirely to submission preparation. No
further experiments. Deliver the verified final comparison, a clean figure,
copy-ready README/presentation wording, limitations and prize evidence; hand
these to the submission owners without changing their video or task. A failed
performance gate must be reported plainly, not extended into another search.
