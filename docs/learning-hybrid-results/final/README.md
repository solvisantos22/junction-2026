# Final selection freeze — awaiting one-shot evaluation

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
