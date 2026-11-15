# RL–greedy hybrid search

**Development is complete:** all 8320 cases on 128 maps are audited, with 8300 home/alive, 20 rover deaths and zero invalid calls. The fixed rule selects six groups for [confirmation](confirmation/README.md). The best development group scores 39.4404%, versus greedy 38.3869% and reference 50.1834%; this is screening evidence, not a confirmed gain. [Full results and preserved execution failures](development/completed/README.md). Confirmation is now running under the selection/operations freeze published in `2256f63`; final maps remain unopened. [Fixed protocol](../learning-hybrid.md).

The 65-arm development search compares individual-policy shortlists, rank
ensembles across all retained seeds, and RL–greedy rank blends. It uses new
maps and leaves the completed [learning evidence](../learning-final-results/README.md)
and the team reference unchanged. This is a composition experiment using
existing trained weights, not another RL training run.

Nineteen policy/selection/worker tests and thirteen orchestration tests pass. All 65 cloud smoke cases passed physics/choice audits, returned alive at home and had no invalid calls.
Checks include original-policy equivalence, whole-group selection, safety
gates, tamper detection, complete controller replay, source/weight integrity,
deadlines and duplicate-launch refusal. Only used smoke worlds 1/2 have been
opened locally. No hybrid performance claim is available yet.

The experiment uses 64 single-CPU, 2-GiB Modal workers plus one coordinator,
with an absolute 05:30 UTC cutoff and a $75 running-compute ceiling. The
declared six-hour maximum allocation is about $24.63, excluding ancillary
costs. Sölvi's workspace was read-only checked before launch: the old training
app was stopped with zero tasks. This is not a live credit balance.

## Reproduction and stage gates

Use the pinned Python 3.12 / NumPy 2.3.4 / Torch 2.9.1 / Modal 1.6.4 runtime.
The local runtime for this worktree is `/tmp/junction-learning-venv`.

1. Write the master source/resource/weight freeze with
   `python -m tools.learning_hybrid.manage --write-freeze FREEZE --campaign docs/learning-hybrid-results/campaign.json`.
2. Prepare a stage with
   `python -m tools.learning_hybrid.experiment prepare --freeze FREEZE --stage smoke --output STAGE`.
   Publish source, freeze and stage before explicit launch.
3. Set `MODAL_PROFILE=solvi-junction`; run
   `python -m tools.learning_hybrid.manage --launch FREEZE --stage STAGE --receipt NEW_RECEIPT`.
   The coordinator continues after client disconnect. Do not submit a second
   receipt for an existing stage. Inspect with `--status RECEIPT`.
4. After completion, `--download RECEIPT --output NEW_DIRECTORY` retrieves
   metadata. Full trajectories remain on the volume; `--artifacts` also
   downloads retained cases. Report errors before any recovery or new spend.
5. Analyze with
   `python -m tools.learning_hybrid.experiment analyze --stage-file STAGE --status DOWNLOADED_STAGE_STATE --output NEW_ANALYSIS`.
   Development has 8320 missions. Confirmation retains at most two eligible
   groups per family and matched controls. Final evaluation requires one
   qualified confirmation winner and a published selection freeze.

Every source change requires a newly published freeze. Final worlds
612000–612255 remain unopened until the frozen selection is published.
No prior supervisor is restarted. App IDs, progress, costs and final handoff
will be appended here as stages complete.

Smoke app: [`ap-SiN8z0aHUAlm2IPQLFEXoU`](https://modal.com/apps/solvisantos22/main/ap-SiN8z0aHUAlm2IPQLFEXoU). [Durable launch receipt](smoke/receipt.json). Source/weights and both smoke/development matrices were published in `4f203d4` before launch. The client log-stream timeout occurred after the detached call was submitted; a read-only status poll confirms the coordinator is running, with no reported error.

[Smoke summary](smoke/summary.json) · [audited rows](smoke/state.json). All 65 cases completed in 63.26 seconds of coordinator time, 589.59 summed worker seconds and $0.01034 estimated worker compute. This used world 1 only and is an execution check, not evidence of performance gains. Production remains the predeclared 8320-mission matrix; estimated 20–40 minutes based on smoke throughput, to be revised from live progress.

Development app: [`ap-ggXtMuvzfCF8qtxLc2Aghg`](https://modal.com/apps/solvisantos22/main/ap-ggXtMuvzfCF8qtxLc2Aghg), [receipt](development/receipt.json). Initial production observation: 249/8320 audited completions, no reported failures, roughly 73 missions/minute including startup. The earlier 20–40 minute estimate underestimated coordination overhead; allow about two hours for development at this observed rate. This is an initial estimate, not a completion promise. A separate read-only continuation watcher is being prepared in the claimed `tools/learning_hybrid_ops/` scope, outside both frozen source closures; it will request this chat to resume at terminal stages and respect pause/stop markers.

The [shared completion watcher](../learning-hybrid-training-results/README.md#completion-watcher-and-first-checkpoints) is now active for development, confirmation, final evaluation and the six new training calls. It preserves pause/stop behavior and never launches work itself. The first healthy watcher snapshot showed 2075/8320 development cases audited, no reported job failure.

## Interruption and recovery decision — 15 November 00:33 UTC

The original coordinator returned terminal `failed` / `KeyboardInterrupt` at
00:21:37 UTC. Its final snapshot contained 3130 completed rows and 15
submitted calls without collected results. Read-only reconciliation retrieved
all 15 original results: **3145 submitted missions completed**, with no failed
worker among them. The original failed state and every call identity remain
retained. An operations-only continuation will be published before launching
the remaining **5175 never-submitted cases**. It must verify absence of prior
launch intents/calls for every case, preserve the frozen worker/source/weights,
and produce a separately identified combined record only after all 8320
original cases satisfy their audits. No partial-data selection is permitted.

Both this coordinator and the separate `prior-29` training wrapper received
`KeyboardInterrupt` within about 24 seconds. The observed exception does not
establish its external cause. Modal documents interruption on
[container preemption](https://modal.com/docs/guide/preemption); that is a
plausible explanation, not a confirmed diagnosis. The continuation will use
a non-preemptible coordinator under a separately published resource freeze.
No completed mission, existing training run, or protected source is restarted.
Confirmation **611000–611255** and final **612000–612255** remain unopened.

[Retained failure, original coordinator result and retrieved call evidence](development/interruption/diagnosis.json). An independent metadata/source audit verified every submitted row and the 54 source pins; full episode archives remain on Modal and were not re-downloaded or replayed in this diagnosis.

[Verified continuation protocol, complete absence check and source/resource freeze](development/recovery/README.md). This is restricted to the original unstarted development suffix; no training resumes or policy changes.

Recovery app [`ap-VMFyA1rZFxPhVr14SGth33`](https://modal.com/apps/solvisantos22/main/ap-VMFyA1rZFxPhVr14SGth33),
call `fc-01M7EB3DJ8C214Z7E14WCVVTNF`, was submitted once after freeze
**`e098ade`** reached `main`. [Receipt, source freeze and live handoff](development/recovery/README.md).
A live check confirms the original failed coordinator state and owner are
unchanged. The continuation has successful audited completions and no reported
error. Allow roughly one hour from its 00:53 UTC start at the earlier measured
rate; this will be revised from actual recovery throughput.
