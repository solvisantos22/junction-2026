# Contextual learning campaign: live handoff

The six-job Modal pilot was submitted on **14 November 2026, 18:02 UTC**. At the first live snapshot, three scratch PPO runs were running and three Rainbow-inspired replay runs were queued behind them. Training and reused validation are underway; final-check generalization is still untested.

- [Frozen protocol](../learning-campaign.md), [campaign manifest](campaign.json), [source/runtime freeze](freeze.json), [pilot call IDs and receipt](pilot-receipt.json).
- [Live Modal app](https://modal.com/apps/solvisantos22/main/ap-rogIzhog6ZpkrAeb474Z11).
- Source implementation `d13bcd7`; published freeze `e8a8acb`. Local frozen checkout: `/tmp/junction-learning-frozen`; runtime `/tmp/junction-learning-venv`. Use that checkout for cloud continuations so teammates' new main commits cannot alter this experiment.
- Dedicated Modal volume: `junction-learning-campaign`; profile `solvi-junction`, workspace `solvisantos22`. Credentials stay outside the repo. Full training batches and optimizer/replay checkpoints stay on this volume.

## What is being tested

Scratch PPO against Double DQN with prioritized replay and three-option-step returns. This is **Rainbow-inspired**, not the full six-component Rainbow algorithm. Both share the same contextual candidate model, charging-aware persistent options, original navigator, official terminal reward and training maps. Kristján's complementary imitation-plus-RL experiment remains independent; his published feasibility helper is reused and pinned here.

Six fixed identities: `ppo-17`, `ppo-29`, `ppo-43`, `replay-17`, `replay-29`, `replay-43`. Initial target2048 missions each. Methods can continue, with all three seeds, only under the frozen validation thresholds. Training worlds80000–80511 and validation81000–81031 are now assigned to this production run. Final-check worlds82000–82039 remain unopened.

The maximum summed phase running CPU/memory estimate is **$22.73184**, plus image build/startup/storage/egress. This is not an invoice cap or a verified remaining-credit balance. Sölvi reported **$300 shared team credit**; this campaign does not reserve the whole pool. At most three16-CPU/32-GiB containers, no GPU/model API. Absolute stop **15 November03:30 UTC**; pilot's separate deadline is retained in its receipt.

## Verification already performed

36 core tests passed before launch; subsequent staging, evaluation, supervisor and audit tests are retained alongside them. Both algorithms trained32 missions on already-used worlds1/2; replay then resumed to64 with its full state. [Retained preflight reports and validation replays](preflight/). These are engineering checks, not held-out learning evidence. The [independent audit](preflight/audit.json) reconstructs all three updates over96 smoke missions,705 training choices and88 validation choices, with exact model/target/optimizer/replay/RNG continuation and zero numeric deviation. Complete smoke batch/checkpoint archives are retained so this can be reproduced.

A known archive-only interruption window remains: if a process dies after recording milestone validation but before copying its full milestone checkpoint, a resume can retain a valid atomic `checkpoint-latest.json.gz` without the separate milestone archive. Checkpoint existence is checked before relying on an archive; no weights or results may be invented to fill a gap. The immutable training image is not patched after production begins. Also, `batch_seconds` excludes the subsequent full-checkpoint write; use wrapper elapsed time and actual completed missions for compute throughput/cost.

## Operations

From the frozen checkout, with the isolated runtime:

```sh
MODAL_PROFILE=solvi-junction /tmp/junction-learning-venv/bin/python -m tools.learning_campaign.modal_job --status --receipt /Users/solvisantos/.codex/worktrees/6974/Junction/docs/learning-campaign-results/pilot-receipt.json
MODAL_PROFILE=solvi-junction /tmp/junction-learning-venv/bin/python -m tools.learning_campaign.modal_job --stop --receipt /Users/solvisantos/.codex/worktrees/6974/Junction/docs/learning-campaign-results/pilot-receipt.json
```

The stop marker is durable and prevents further stage launches. Do not relaunch the pilot or clear its reservation. Every stage has a one-time lock, and later phases cannot overlap earlier jobs. Retain negative/incomplete results. Before final-check evaluation, freeze every included initial/last completed policy and include matched2048 snapshots, charge-aware greedy and the unchanged beam reference. Report all three training seeds and every failure; a learning gain is not itself a frontier-agent gap.

## Continuation supervisor and final confirmation

`tools.learning_campaign.manage` monitors only this campaign. Without `--follow` it performs one remote read-only poll. With `--follow` it may launch only the frozen expanded/extended stages for entire qualifying methods, checks the unchanged frozen source, and stops on any ambiguous receipt, remote exception or corrupt download. It downloads report/policy/validation artifacts only after every stage function has returned and committed its volume. It does not open final-check maps.

After training has settled, `tools.learning_campaign.evaluate --freeze ... --runs ...` creates a self-contained final manifest without constructing any environments. Publish that manifest before `--run`; audit the resulting complete physics replays with `--audit`. Include all six run identities, initial/last completed policies, matched2048 policies, greedy and beam. Never select the best initialization.

## First validation checkpoint and interpretation

[Immutable512-mission PPO validation summaries](early-validation.json): all three training seeds improve; mean initial score0.087395 →0.344024. All96 initial and all96 checkpoint validation outcomes return alive/home, with zero invalid calls. These are reusable validation maps, not the final check, and do not trigger continuation before the2048-mission pilot completes.

[Matched validation controls](validation-controls/report.json), independently checked through all64 physics replays/grades and greedy choices ([verification](validation-controls/verification.json)):

| Policy | Mean official reward | Alive/home |
|---|---:|---:|
| PPO after512, average of3 training seeds | 0.344024 | 96/96 |
| Charge-aware greedy | 0.380555 | 32/32 |
| Unchanged original beam | 0.514345 | 32/32 |

The early learning gain is real in these recorded validation scores; it has not reached either control. Keep training under the declared gates. The controls were measured as context after validation had opened, with no tuning or change to staging thresholds. They establish neither a final learned-policy win nor a language-model failure.

## Active process and next handoff

The bounded continuation supervisor is running from its own fixed checkout **`/tmp/junction-learning-supervisor` at `06979e7`**, using the original training checkout at `e8a8acb`. PID at launch: **54377**. Its heartbeat, receipts, downloaded stage artifacts, decisions and append-only events are under **`/tmp/junction-learning-monitor`**; read `state.json` for current status. An idle-sleep guard watches this process and exits with it. Current cloud jobs keep running independently of the local supervisor.

All **61 tests pass**. Smoke updates/actions reproduce exactly; full control physics audits pass. Work remains: collect completed pilot artifacts, let the fixed all-seed gate decide continued training, then publish the final policy/evaluation freeze and run/audit the40 untouched final maps. The supervisor stops at `ready_for_final_evaluation`; it never silently opens those maps or pushes new results. The next agent should publish stage receipts/decisions and update this handoff before interpreting final results.

To inspect local progress: `cat /tmp/junction-learning-monitor/state.json`. To resume a stopped local supervisor without duplicating submitted jobs, use the exact fixed code and existing output directory:

```sh
cd /tmp/junction-learning-supervisor
MODAL_PROFILE=solvi-junction /tmp/junction-learning-venv/bin/python -m tools.learning_campaign.manage --freeze /tmp/junction-learning-frozen/docs/learning-campaign-results/freeze.json --pilot-receipt /tmp/junction-learning-supervisor/docs/learning-campaign-results/pilot-receipt.json --source-root /tmp/junction-learning-frozen --output /tmp/junction-learning-monitor --follow
```

If state is `error`, inspect its operation and retained artifacts; it intentionally does not retry an ambiguous launch or corrupt terminal download. Stopping the local PID prevents future local continuation decisions but does not cancel active cloud jobs; use the durable cloud stop command above to stop the campaign.
