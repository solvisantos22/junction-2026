# Contextual learning campaign: live handoff

The six-job Modal pilot was submitted on **14 November 2026, 18:02 UTC**. Three scratch PPO runs are running and three Rainbow-inspired replay runs are queued behind them. No production result or learning success is claimed yet.

- [Frozen protocol](../learning-campaign.md), [campaign manifest](campaign.json), [source/runtime freeze](freeze.json), [pilot call IDs and receipt](pilot-receipt.json).
- [Live Modal app](https://modal.com/apps/solvisantos22/main/ap-rogIzhog6ZpkrAeb474Z11).
- Source implementation `d13bcd7`; published freeze `e8a8acb`. Local frozen checkout: `/tmp/junction-learning-frozen`; runtime `/tmp/junction-learning-venv`. Use that checkout for cloud continuations so teammates' new main commits cannot alter this experiment.
- Dedicated Modal volume: `junction-learning-campaign`; profile `solvi-junction`, workspace `solvisantos22`. Credentials stay outside the repo. Full training batches and optimizer/replay checkpoints stay on this volume.

## What is being tested

Scratch PPO against Double DQN with prioritized replay and three-option-step returns. This is **Rainbow-inspired**, not the full six-component Rainbow algorithm. Both share the same contextual candidate model, charging-aware persistent options, original navigator, official terminal reward and training maps. Kristján's complementary imitation-plus-RL experiment remains independent; his published feasibility helper is reused and pinned here.

Six fixed identities: `ppo-17`, `ppo-29`, `ppo-43`, `replay-17`, `replay-29`, `replay-43`. Initial target2048 missions each. Methods can continue, with all three seeds, only under the frozen validation thresholds. Training worlds80000–80511 and validation81000–81031 are now assigned to this production run. Final-check worlds82000–82039 remain unopened.

The maximum summed phase running CPU/memory estimate is **$22.73184**, plus image build/startup/storage/egress. This is not an invoice cap or a verified remaining-credit balance. Sölvi reported **$300 shared team credit**; this campaign does not reserve the whole pool. At most three16-CPU/32-GiB containers, no GPU/model API. Absolute stop **15 November03:30 UTC**; pilot's separate deadline is retained in its receipt.

## Verification already performed

36 focused tests passed before launch. Both algorithms trained32 missions on already-used worlds1/2; replay then resumed to64 with its full state. [Retained preflight reports and validation replays](preflight/). These are engineering checks, not held-out learning evidence. Model, target, optimizer, replay and RNG continuation were checked independently; saved actor choices reproduce.

A known archive-only interruption window remains: if a process dies after recording milestone validation but before copying its full milestone checkpoint, a resume can retain a valid atomic `checkpoint-latest.json.gz` without the separate milestone archive. Checkpoint existence is checked before relying on an archive; no weights or results may be invented to fill a gap. The immutable training image is not patched after production begins. Also, `batch_seconds` excludes the subsequent full-checkpoint write; use wrapper elapsed time and actual completed missions for compute throughput/cost.

## Operations

From the frozen checkout, with the isolated runtime:

```sh
MODAL_PROFILE=solvi-junction /tmp/junction-learning-venv/bin/python -m tools.learning_campaign.modal_job --status --receipt /Users/solvisantos/.codex/worktrees/6974/Junction/docs/learning-campaign-results/pilot-receipt.json
MODAL_PROFILE=solvi-junction /tmp/junction-learning-venv/bin/python -m tools.learning_campaign.modal_job --stop --receipt /Users/solvisantos/.codex/worktrees/6974/Junction/docs/learning-campaign-results/pilot-receipt.json
```

The stop marker is durable and prevents further stage launches. Do not relaunch the pilot or clear its reservation. Every stage has a one-time lock, and later phases cannot overlap earlier jobs. Retain negative/incomplete results. Before final-check evaluation, freeze every included initial/last completed policy and include matched2048 snapshots, charge-aware greedy and the unchanged beam reference. Report all three training seeds and every failure; a learning gain is not itself a frontier-agent gap.
