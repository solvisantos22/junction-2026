# Final Traverse learning campaign

**All six fresh runs are running on Modal**, launched 2026-11-14 19:42 UTC. [Live app](https://modal.com/apps/solvisantos22/main/ap-GGkMI4eQi8N9MVVuTef5Au). The launch snapshot confirms six running wrappers, no returned errors and no stop marker. It is a timestamped snapshot, not a live results table.

- [Protocol](../learning-final.md), [campaign manifest](campaign.json), [source/runtime freeze](freeze.json), [fit receipt](fit-receipt.json), [launch status](launch-status.json).
- Training source and supervisor commit **`becbf3e`**; freeze published in **`2257871`** before launch. Fixed local checkout: `/tmp/junction-learning-final-frozen`; runtime: `/tmp/junction-learning-venv`.
- New app, volume and control dictionary: **`junction-learning-final`**; profile `solvi-junction`. The old `junction-learning-campaign` supervisor remains stopped and its [completed pilot](../learning-campaign-results/pilot/README.md) retains its original hashes.
- First stage: PPO and Rainbow-inspired replay × initialization seeds 17, 29, 43, each targeting **8192 missions**. All six began together; stage cutoff **22:42 UTC**. Only entire methods passing the declared gain/reliability gate can extend toward **32768 missions per seed**, with a separate three-hour limit. Absolute stop **15 November 03:30 UTC / 05:30 Helsinki**.
- Maximum six 8-CPU/16-GiB containers and six rollout workers each. Running CPU/memory envelope **$18.185472**, below the $19 guard; image/startup/storage/egress are additional. No GPU or model API. This is not an invoice cap or verified credit balance.

## Verification and interpretation

**51 focused tests pass**, with an independent code review finding no blocking issue. Both algorithms complete 32-mission local smoke runs on worlds 1/2. Complete reports, policies, batches, optimizer checkpoints and validation replays are retained under [preflight](preflight/). These are engineering checks.

The [matched compatibility check](compatibility/README.md) passes both method gates across 112 missions on reused worlds 80000–80007. All 56 paired grades and goal choices match. Home-return commands and trajectories differ in 28 pairs, so the controllers are not treated as identical and the six learners start afresh. Physics and controller replay audits are retained.

The historical `lightlag_rl` retained-smoke fixture remains pinned to its old source: its current-main source assertion fails after the controller/task change. Its original-source audit still passes. We did not rewrite historical hashes to conceal that mismatch; this experiment supplies a separately pinned final-version preflight. The 51-test result above is for the new suite, not a claim that every historical repository test passes against current source.

Training worlds **80000–80511** and validation **81000–81031** are reused development data. Final worlds **82000–82039 remain unopened**. Submission worlds **2026–2029 are excluded from training and selection**. No model, seed or checkpoint is selected by final results. Keep the frozen beam reference for submission unless the team separately approves a supported replacement.

## Monitor and stop

The continuation supervisor is running from the fixed checkout at `becbf3e`, PID **70439**; idle-sleep guard PID **70440** exits with it. Its state, heartbeat, events, terminal downloads and decisions live in `/tmp/junction-learning-final-monitor`. Cloud jobs continue independently of this local process. Automatic continuation requires the local supervisor to remain available.

Read `/tmp/junction-learning-final-monitor/state.json` and the stage's `status.json` for current progress. The supervisor polls every 30 seconds and downloads artifacts only after all stage functions have returned and committed their volume. A failed function, corrupt evidence or ambiguous launch stops progress; no automatic retry or extra budget allocation follows.

To pause **future stage launches** while letting current jobs finish, create `/tmp/junction-learning-final-monitor/pause.json`. The saved `user_paused` state remains durable; deleting the file alone does not resume it. To request a stop of **current jobs and all future stages**, run from the fixed checkout:

```sh
cd /tmp/junction-learning-final-frozen
MODAL_PROFILE=solvi-junction /tmp/junction-learning-venv/bin/python -m tools.learning_final.modal_job --stop --receipt /Users/solvisantos/.codex/worktrees/6974/Junction/docs/learning-final-results/fit-receipt.json
```

Do not relaunch `fit`, clear cloud reservations or resume the old supervisor. If this new local monitor stops unexpectedly, inspect `state.json` and any launch intent before restarting the same command recorded in `/tmp/junction-learning-final-monitor/process.json`. Use the existing output directory and unchanged fixed checkout; a saved error/pause requires deliberate reconciliation.

## Next handoff

1. Collect and publish the completed fit decision and, if launched, extend receipt. Keep every seed and failure. Full training batches, replay buffers and optimizer checkpoints stay on the unique Modal volume; download them for a separate optimizer/physics audit before making stronger reproducibility claims.
2. Once the supervisor reaches `ready_for_final_evaluation`, choose each run's **latest completed declared milestone by episode count**, retaining its initial and matched-2048 policies. For a method that did not extend, use its fit directory; for an extended method, use its extend directory. Supply exactly one terminal directory per identity. Report attempted targets separately from completed milestones.
3. From the frozen checkout, `tools.learning_final.evaluate --freeze <new-manifest> --runs <six-run-directories>` creates the self-contained final manifest without opening maps. Publish it before `--run`, then run and `--audit` all 40 final worlds. Include the same greedy and beam controls, every training seed, and paired-map intervals. The supervisor deliberately stops before this evaluation.
4. A campaign showcase comes only after policies are frozen: fresh pilot for each mission, stop at `campaign_complete`, and score `sum(raw)/sum(max)`. A single-mission learning improvement does not establish a campaign win or Claude failure. The task owner's real-agent evidence retains its EPIPE exits and length-censored attempt.

The canonical Traverse rules, reference, Harbor task and teammates' training packages are unchanged by this experiment.
