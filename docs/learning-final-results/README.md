# Final Traverse learning campaign

**Training has settled; final evaluation is running.** Five runs completed 8,192 missions; replay seed 43 stopped at its deadline after 6,880. Neither method qualified for continuation. The [all-seed policy freeze](policy-freeze.json) reached main in `d81fa88` before any final world was opened. [Terminal evidence](fit/README.md) · [evaluation and exact-campaign plan](evaluation-plan.md). The operational notes below retain the earlier monitoring history and will be closed in the final handoff.

- [Protocol](../learning-final.md), [campaign manifest](campaign.json), [source/runtime freeze](freeze.json), [fit receipt](fit-receipt.json), [launch status](launch-status.json).
- Training source and supervisor commit **`becbf3e`**; freeze published in **`2257871`** before launch. Fixed local checkout: `/tmp/junction-learning-final-frozen`; runtime: `/tmp/junction-learning-venv`.
- New app, volume and control dictionary: **`junction-learning-final`**; profile `solvi-junction`. The old `junction-learning-campaign` supervisor remains stopped and its [completed pilot](../learning-campaign-results/pilot/README.md) retains its original hashes.
- First stage: PPO and Rainbow-inspired replay × initialization seeds 17, 29, 43, each targeting **8192 missions**. All six began together; stage cutoff **22:42 UTC**. Only entire methods passing the declared gain/reliability gate can extend toward **32768 missions per seed**, with a separate three-hour limit. Absolute stop **15 November 03:30 UTC / 05:30 Helsinki**.
- Maximum six 8-CPU/16-GiB containers and six rollout workers each. Running CPU/memory envelope **$18.185472**, below the $19 guard; image/startup/storage/egress are additional. No GPU or model API. This is not an invoice cap or verified credit balance.

Sölvi also authorized more containers when useful, within the user-reported $300 shared team budget. The current six-run source/resource freeze stays unchanged. Additional capacity can support a separately bounded parallel evaluation after training; no additional jobs or budget were allocated by that permission alone.

## Team checkpoints

Use the [shared progress page](progress.md) for checkpoint scores, home/survival counts, six-run progress and estimates. Every page has an explicit observation time. The publisher refreshes it every 15 minutes and, within its five-minute polling interval, when all three seeds of either method reach another declared checkpoint. It does not wake a model for routine updates or change training decisions.

| Missions per run | What the checkpoint is for |
|---:|---|
| 512 | Early learning and reliability check |
| 2048 | Same-budget checkpoint beside the earlier pilot |
| 8192 | Formal decision on whether the whole method may continue |
| 16384 and 24576 | Progress during the optional extension |
| 32768 | Extended target, if reached before the time limit |
| Final 40 worlds | Separate evaluation after all selected policy artifacts are frozen |

The page averages methods only at a checkpoint completed by all three seeds. Batch-file counts are progress indicators and may lag volume commits; they are not substitutes for validated milestone artifacts. Interim scores are from reused validation worlds, not the final test or submission campaign. Teammates should keep the frozen reference in the demo and submission until a separate, supported decision changes it. Complete checkpoint files remain available on Modal; reporting does not wait for the entire stage to finish.

### Progress publisher operation

The publisher is active, PID **92298**, with idle-sleep guard **92299**. Its fixed runtime and private configuration/state/logs live in `/Users/solvisantos/.codex/junction-learning-final-progress-20261114/`. Integration happens only in `/tmp/junction-learning-progress-publish`, branch `codex/learning-progress-20261114`. Implementation `73b84fc`; the first actual automatic update reached main as **`637764d`**, with both methods at their common 2048 checkpoint. All **24 collector/publisher tests pass**, including real temporary-Git push races and interruption recovery.

The publisher writes only `progress.md`, `progress.json` and timestamped `progress-snapshots/*.json` in this results directory. Each update is fetched/reconciled, checked and normally pushed; it never force-pushes or edits the training code. New same-budget method checkpoints and status changes trigger earlier updates; otherwise publication is every 15 minutes, with a five-minute polling cadence. Network downloads and Git operations can add delay. Full immutable policy/validation files are cached privately and remain on Modal; JSON snapshots retain their hashes and checked summaries.

To stop only progress publication, create `/tmp/junction-learning-final-monitor/progress-stop`. A training pause/stop also disables it. It publishes a last snapshot when training settles and independently stops at **15 November 03:40 UTC / 05:40 Helsinki**, even if the supervisor stalls. A dirty integration tree, workflow change, conflict or ambiguous commit halts publication for review; it preserves the pending work and logs an error rather than guessing. Check the page's observation timestamp and private `state.json`; publication is separate from the training supervisor and completion wake-up. Do not run a second publisher or edit its three output paths concurrently.

## Verification and interpretation

**51 focused tests pass**, with an independent code review finding no blocking issue. Both algorithms complete 32-mission local smoke runs on worlds 1/2. Complete reports, policies, batches, optimizer checkpoints and validation replays are retained under [preflight](preflight/). These are engineering checks.

The [matched compatibility check](compatibility/README.md) passes both method gates across 112 missions on reused worlds 80000–80007. All 56 paired grades and goal choices match. Home-return commands and trajectories differ in 28 pairs, so the controllers are not treated as identical and the six learners start afresh. Physics and controller replay audits are retained.

The historical `lightlag_rl` retained-smoke fixture remains pinned to its old source: its current-main source assertion fails after the controller/task change. Its original-source audit still passes. We did not rewrite historical hashes to conceal that mismatch; this experiment supplies a separately pinned final-version preflight. The 51-test result above is for the new suite, not a claim that every historical repository test passes against current source.

Training worlds **80000–80511** and validation **81000–81031** are reused development data. Final worlds **82000–82039 remain unopened**. Submission worlds **2026–2029 are excluded from training and selection**. No model, seed or checkpoint is selected by final results. Keep the frozen beam reference for submission unless the team separately approves a supported replacement.

## Monitor and stop

The continuation supervisor is running from the fixed checkout at `becbf3e`, PID **92082**; idle-sleep guard PID **92083** exits with it. Its state, heartbeat, events, terminal downloads and decisions live in `/tmp/junction-learning-final-monitor`. Cloud jobs continue independently of this local process. Automatic continuation requires the local supervisor to remain available.

Read `/tmp/junction-learning-final-monitor/state.json` and the stage's `status.json` for current progress. The supervisor polls every 30 seconds and downloads artifacts only after all stage functions have returned and committed their volume. A failed function, corrupt evidence or ambiguous launch stops progress; no automatic retry or extra budget allocation follows.

To pause **future stage launches** while letting current jobs finish, create `/tmp/junction-learning-final-monitor/pause.json`. The saved `user_paused` state remains durable; deleting the file alone does not resume it. To request a stop of **current jobs and all future stages**, run from the fixed checkout:

```sh
cd /tmp/junction-learning-final-frozen
MODAL_PROFILE=solvi-junction /tmp/junction-learning-venv/bin/python -m tools.learning_final.modal_job --stop --receipt /Users/solvisantos/.codex/worktrees/6974/Junction/docs/learning-final-results/fit-receipt.json
```

Do not relaunch `fit`, clear cloud reservations or resume the old supervisor. If this new local monitor stops unexpectedly, inspect `state.json` and any launch intent before restarting the same command recorded in `/tmp/junction-learning-final-monitor/process.json`. Use the existing output directory and unchanged fixed checkout; a saved error/pause requires deliberate reconciliation.

## Monitoring interruption and recovery, 21:00 UTC

Training continued through two local reporting interruptions. At 20:42 UTC the progress publisher stopped because `AGENTS.md` gained the approved MAX Harbor-task instructions; that change was reviewed before updating its workflow pin. At 21:00 UTC the supervisor stopped on a DNS `ConnectionError` during a read-only Modal poll. A direct 21:03 UTC check confirmed all six original cloud calls still running, no job errors and no stop marker. [Retained status and recovery record](monitoring-recovery-20261114/record.json).

The same supervisor and publisher were rearmed after preserving their error states and logs. Their frozen code, receipts, source pins, continuation gates, deadlines and cloud reservations are unchanged. No training was relaunched and no extra cloud job was created. Publication resumed in `a0e6f42`; the page now reflects current saved batches again. Read-only network failures remain fail-closed, so another connection failure can stop local monitoring while cloud jobs continue.

The first completion watcher had already queued its one error alert, so it was retained unchanged and a **second generation** was activated for completion. Its current runtime path and PID are listed below. The original runtime remains under `/Users/solvisantos/.codex/junction-learning-final-wake-20261114/`; do not restart or clear its queued reservation. The new generation's live local check reports waiting. Queue acceptance is not a guarantee that resumed work finishes if connectivity or Codex availability fails.

## Continue this chat when training settles

Sölvi asked for continued work after training. A separate one-time watcher is now active, PID **92085**, with idle-sleep guard **92086**. It polls the local monitor every 30 seconds and uses the installed `codex queue --thread … --message … --resume` command to resume this same chat when the monitor reaches final evaluation, reports an error/deadline, or has a heartbeat stale for 15 minutes. A final fallback fires at **03:40 UTC**, ten minutes after the training cutoff.

The queued instruction directs Codex to reconcile all runs, publish the all-seed policy freeze before opening final maps, evaluate and audit the learned policies beside greedy/beam, then publish findings and the handoff. It preserves the reference and original training freeze. An error wake-up requires diagnosis before new spend; it does not authorize repeating training. No cloud job is launched by this watcher.

Runtime code, configuration, state and logs are under `/Users/solvisantos/.codex/junction-learning-final-wake-20261114-generation-2/`. The private code copy is hash-bound and unaffected by later main commits. `state.json` reports `waiting`, `queued`, `uncertain` or `disabled`. Dispatch is reserved durably before the CLI call; an interrupted or ambiguous attempt is never automatically repeated. A `queued` state means the CLI reported acceptance, not that the follow-up work finished.

A training pause/stop suppresses the wake-up. To disable only this watcher, create `/tmp/junction-learning-final-monitor/wake-stop`; current training continues. A disabled watcher requires deliberate rearming. The Mac and Codex must remain available, and Codex usage limits can interrupt the resumed work. Thirteen synthetic tests cover dispatch, pauses, interruption, identity changes and duplicate prevention; a real local poll verified `waiting`. No test follow-up message was sent to the chat.

## Team delivery requested for 07:30 Helsinki

Sölvi relayed Kristján's requested morning handoff: by **15 November 07:30 Helsinki / 05:30 UTC**, provide one clean before/after on the final frozen source, averaged over all three initialization seeds, with greedy and the frozen reference on the same final worlds; one README/video paragraph; one learning-curve figure; and Modal app IDs with estimated cost in `docs/prize-evidence.md`. The active completion wake-up reads this handoff. Training's absolute 05:30 Helsinki cutoff leaves two hours for that work.

**Seed correction for the team:** worlds **72000–72039 were already consumed by the first small-policy RL experiment** ([retained result](../lightlag-rl-results/README.md)). They must not be reopened and described as fresh. This experiment's predeclared untouched final worlds are **82000–82039**, opened once only after policy freezing. Worlds 81000–81031 are held apart from training but repeatedly used for validation and continuation decisions; call them development validation, not an untouched test. Our 80000–80511 training range also avoids the newly reserved MAX pool 500–523, the team's farm/probe ranges, submission 2026–2029 and example 99991. The broad suggestion that any seed above 5000 is unused does not override prior experiment reservations.

If training hits its deadline, use each run's last completed declared milestone and state the attempted target separately. Retain the same-source matched 2048 comparison. The old pilot fallback remains initial .087395 → PPO .376800 at 2048, greedy .380555 and beam .514345, but it used the original navigator and must be labelled accordingly; it is not a completed result from this final-version training run. Current validation improvement alone does not establish a learned-policy win or a Claude gap.

The figure should clearly label the training checkpoints as development validation, retain all seeds, and pair any final before/after headline with the separately audited final-world comparison. Keep the current reference until the team separately decides otherwise. Current cloud allocation remains within its published running-compute envelope; no additional allocation should exceed the remaining authorized credit.

## Next handoff

1. Collect and publish the completed fit decision and, if launched, extend receipt. Keep every seed and failure. Full training batches, replay buffers and optimizer checkpoints stay on the unique Modal volume; download them for a separate optimizer/physics audit before making stronger reproducibility claims.
2. Once the supervisor reaches `ready_for_final_evaluation`, choose each run's **latest completed declared milestone by episode count**, retaining its initial and matched-2048 policies. For a method that did not extend, use its fit directory; for an extended method, use its extend directory. Supply exactly one terminal directory per identity. Report attempted targets separately from completed milestones.
3. From the frozen checkout, `tools.learning_final.evaluate --freeze <new-manifest> --runs <six-run-directories>` creates the self-contained final manifest without opening maps. Publish it before `--run`, then run and `--audit` all 40 final worlds. Include the same greedy and beam controls, every training seed, and paired-map intervals. The supervisor deliberately stops before this evaluation.
4. A campaign showcase comes only after policies are frozen: fresh pilot for each mission, stop at `campaign_complete`, and score `sum(raw)/sum(max)`. A single-mission learning improvement does not establish a campaign win or Claude failure. The task owner's real-agent evidence retains its EPIPE exits and length-censored attempt.

The canonical Traverse rules, reference, Harbor task and teammates' training packages are unchanged by this experiment.

### Completion-pass readiness check

The delayed error wake-up was reconciled again at **21:17 UTC on 14 November**: all six original call IDs still matched the fit receipt and were running, with no new job error, stop marker, pause or launch intent. All **46 frozen source hashes** matched and the fixed checkout was clean. This was the already-repaired 21:00 monitoring interruption; no recovery was repeated or new job launched. The second completion watcher remains responsible for the terminal-state wake-up.

The frozen evaluator covers every initialization's initial, matched-2048 and latest completed declared policy, plus greedy and beam on the same 40 worlds. Normally this is **20 arms / 800 missions**; a policy serving both matched-2048 and latest roles is evaluated once, so the total can be smaller. Do not freeze from a live `report.json`: wait for returned calls and terminal downloads, then supply exactly one directory per identity as described above. If a wrapper deadline leaves a report marked `running`, the freeze will reject it. Reconcile it with the terminal receipt and preserve the original evidence; do not relaunch training or silently rewrite its status.

Run from `/tmp/junction-learning-final-frozen` with `/tmp/junction-learning-venv/bin/python`, preserving Python 3.12.16, NumPy 2.3.4 and Torch 2.9.1. Evaluation accepts `--workers 6`; **the audit is serial and does not use that worker setting**. Limit numerical-library threads for the audit. After the policy freeze has reached `main` and the final evaluation has completed, the audit invocation is:

```sh
cd /tmp/junction-learning-final-frozen
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  /tmp/junction-learning-venv/bin/python -m tools.learning_final.evaluate \
  --audit /Users/solvisantos/.codex/worktrees/6974/Junction/docs/learning-final-results/evaluation/report.json \
  --output /Users/solvisantos/.codex/worktrees/6974/Junction/docs/learning-final-results/evaluation/audit.json
```

The audit reconstructs physics, grades and learned/greedy choices on saved observations, and recomputes the summaries. Observation reconstruction, choice-to-command linkage and beam decision logic remain source-pinned; optimizer learning is outside this audit. Retain those limits in the final write-up. **No final manifest or final-world evaluation has been created during this readiness check.**

Allow roughly **20–40 minutes for the final run and serial audit**, plus download, publication and figure time. This is a planning estimate based on the earlier 112-case compatibility workload, not a measurement on final worlds. All evaluation output paths must be new; the frozen runner has no resume option.
