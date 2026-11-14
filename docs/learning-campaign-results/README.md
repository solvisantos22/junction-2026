# Contextual learning campaign: completed old pilot

**All six original pilot runs completed at 2,048 missions each. The old supervisor remains stopped; do not resume its continuation commands.** The changed final navigator is handled by a [separate experiment](../learning-final.md), with fresh learners and new source pins. Original freeze `e8a8acb` and every historical artifact are preserved.

| Policy | Mean validation reward | Home / alive |
|---|---:|---:|
| Initial, average of 3 seeds per method | .087395 | 96/96 per method |
| PPO after 2,048, average of 3 seeds | .376800 | 96/96 |
| Replay after 2,048, average of 3 seeds | .364144 | 96/96 |
| Charge-aware greedy control | .380555 | 32/32 |
| Original beam control | .514345 | 32/32 |

Both methods passed their frozen pilot continuation gate, and every seed improved. All 576 retained validation episodes report home/alive with zero invalid calls. Across 12,288 training episodes, batch reports retain two away finishes and no deaths or invalid calls. Actual-duration running-compute estimate: **$1.592405**, not an invoice. Final worlds 82000–82039 remain unopened by this campaign.

[Completed results, all six seeds, compute and limitations](pilot/README.md) · [Decision](pilot/decision.json) · [Terminal status](pilot/status.json) · [Hash/counter/arithmetic verification](pilot/verification.json). All 42 downloaded artifact hashes match. Production optimizer updates and physics have not been independently reconstructed here; full training archives remain on Modal. These results describe the old navigator, not the new final version.

## Archived live handoff

The remainder preserves the earlier protocol, observations and operational history. **Its underway/active descriptions and continuation instructions are superseded by the closure above. No old continuation or final-map command is authorized by this archive.**

> **Latest user direction: larger training is paused.** Sölvi asked to wait for the team to finalize the map/task. The local continuation supervisor PID54377 was stopped and verified absent; current pilot jobs may finish. Do not use the resume command below until this pause is resolved. [Question for Kristján/Manh and reply template](team-training-readiness.md). Runtime pause record: `/tmp/junction-learning-monitor/user-pause.json`.

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

## Historical active-process handoff — now superseded

The bounded continuation supervisor previously ran from **`/tmp/junction-learning-supervisor` at `06979e7`**, using the original training checkout at `e8a8acb`; its launch PID was **54377**. It was stopped at Sölvi's request and must not be resumed. Its historical files remain under **`/tmp/junction-learning-monitor`**. All six pilot jobs have now completed independently. Closure used a separate, remote-read-only one-poll directory `/tmp/junction-learning-pilot-closure`; it launched no continuation. The completed evidence is published in [pilot/](pilot/README.md).

All **61 tests pass**. Smoke updates/actions reproduce exactly; full control physics audits pass. Work remains: collect completed pilot artifacts, let the fixed all-seed gate decide continued training, then publish the final policy/evaluation freeze and run/audit the40 untouched final maps. The supervisor stops at `ready_for_final_evaluation`; it never silently opens those maps or pushes new results. The next agent should publish stage receipts/decisions and update this handoff before interpreting final results.

Historical command retained for provenance only: **deprecated; do not run or resume this old supervisor**. The separate final-version experiment replaces this operational path:

```sh
cd /tmp/junction-learning-supervisor
MODAL_PROFILE=solvi-junction /tmp/junction-learning-venv/bin/python -m tools.learning_campaign.manage --freeze /tmp/junction-learning-frozen/docs/learning-campaign-results/freeze.json --pilot-receipt /tmp/junction-learning-supervisor/docs/learning-campaign-results/pilot-receipt.json --source-root /tmp/junction-learning-frozen --output /tmp/junction-learning-monitor --follow
```

If state is `error`, inspect its operation and retained artifacts; it intentionally does not retry an ambiguous launch or corrupt terminal download. Stopping the local PID prevents future local continuation decisions but does not cancel active cloud jobs; use the durable cloud stop command above to stop the campaign.

## What follows training; integration coordination

This experiment trains a small public-observation **goal selector** above the existing navigator. It does not fine-tune an LLM. Its deliverables are runnable policy checkpoints, audited before/after performance and learning curves; the team's strong-agent difficulty claim requires its own matched agent evidence.

1. Let the frozen all-seed validation gates finish selecting training budgets; retain failed and incomplete runs.
2. Freeze the specified initial/last/matched2048 checkpoints before opening final maps82000–82039. Run and audit all policies, the charge-aware greedy control and the unchanged beam reference on the same40 maps. Report official score, return/survival, every initialization and uncertainty. Do not choose a seed or retune after seeing final results.
3. Publish checkpoints, reproducible evaluation commands and learning results. Keep the existing planner as reference unless a separately justified change is supported by comparable performance and reliability; learning from a weak initial policy alone does not establish reference superiority.
4. In parallel, the task owner should finish the chosen runnable Harbor package and genuine full-agent comparison. The three-mission baseline evidence now on main is useful, but saved-program replays and oracle/nop baselines are distinct from an LLM agent playing the whole campaign. Submission/demo preparation need not wait for our final training phase.

**Our campaign does not require main to stay frozen.** Cloud training uses the source snapshot published at`e8a8acb`, and continuation builds read `/tmp/junction-learning-frozen`; supervisor code is fixed at`06979e7`. New task/reference/viewer changes may be integrated on main after their own ownership and verification requirements are satisfied, without modifying these snapshots. This statement applies to our campaign; it does not override another experiment's freeze.

For our final evaluation, use the original frozen training modules and source hashes. Copy only the published evaluator tool files into a matching evaluation checkout if needed; do not silently evaluate old weights with newly changed navigation or mission rules. A different final submission package gets its own labelled compatibility/comparison run. This keeps both the training evidence and the submission's version claims accurate.

Historical earlier snapshot, superseded by the completed closure above: all three2048-mission PPO pilot jobs completed; all three replay pilot jobs are running; the local continuation supervisor is healthy. Latest teammate publication`95102a1` retains the campaign oracle0.476257, nop0 and stop-after-first0.148743 baselines, with saved-artifact consistency checks. The actual campaign runtime/viewer and fresh full-agent campaign evidence remain separate outstanding work.
