# RL–greedy hybrid search

The 65-mission smoke stage is running on Modal; production results are pending. [Fixed protocol](../learning-hybrid.md).

The 65-arm development search compares individual-policy shortlists, rank
ensembles across all retained seeds, and RL–greedy rank blends. It uses new
maps and leaves the completed [learning evidence](../learning-final-results/README.md)
and the team reference unchanged. This is a composition experiment using
existing trained weights, not another RL training run.

Nineteen policy/selection/worker tests and thirteen orchestration tests pass.
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
