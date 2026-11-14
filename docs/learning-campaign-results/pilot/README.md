# Completed old-navigator pilot

All six scratch runs completed **2,048 missions each: 12,288 training missions in 384 batches** under the original freeze `e8a8acb`. This closure preserves that original navigator and protocol. The old continuation supervisor remains stopped; **do not resume it**. Work on the changed final navigator belongs to the [separate final experiment](../../learning-final.md).

## Recorded validation results

Each cell below averages the same 32 reusable validation worlds, 81000–81031. Values are official normalized terminal rewards. All three initialization seeds are retained; no best seed was selected.

| Run | Initial | 512 missions | 2,048 missions | Initial → 2,048 gain | 512 → 2,048 gain |
|---|---:|---:|---:|---:|---:|
| [ppo-17](runs/ppo-17/report.json) | 0.001886 | 0.349808 | 0.375898 | +0.374012 | +0.026090 |
| [ppo-29](runs/ppo-29/report.json) | 0.000000 | 0.339716 | 0.367047 | +0.367047 | +0.027330 |
| [ppo-43](runs/ppo-43/report.json) | 0.260298 | 0.342547 | 0.387457 | +0.127159 | +0.044910 |
| [replay-17](runs/replay-17/report.json) | 0.001886 | 0.309800 | 0.357154 | +0.355269 | +0.047355 |
| [replay-29](runs/replay-29/report.json) | 0.000000 | 0.228302 | 0.368244 | +0.368244 | +0.139942 |
| [replay-43](runs/replay-43/report.json) | 0.260298 | 0.291681 | 0.367034 | +0.106736 | +0.075352 |

Across the three seeds, initial reward was **.087395**, PPO reached **.376800** and replay **.364144**. The corresponding initial gains were **+.289406** and **+.276750**; latest 512→2048 gains were **+.032777** and **+.087550**. Every seed improved over both its initial and 512 checkpoint. Both methods pass the [old frozen pilot continuation gate](decision.json): all three complete, mean gain≥.03, at least two positive, no validation deaths or invalid calls. Passing this gate is a recorded eligibility result, not authorization to resume the stopped experiment.

All **576 retained validation episodes** (6 runs ×3 checkpoints ×32 maps) report home/alive and zero invalid calls. These include the identical initial policies evaluated separately for the two methods; they are not576 independent test worlds.

The previously measured [matched validation controls](../validation-controls/report.json) score **greedy .380555** and **original beam .514345**, each32/32 home/alive with zero invalid calls. Their64 saved physics replays were [independently checked](../validation-controls/verification.json). Neither learned method exceeds either control in aggregate recorded reward at 2048. No new significance comparison is claimed. Validation is development data; final worlds 82000–82039 remain unopened by this pilot and its closure.

## Reported training outcomes and compute

| Run | Training home / alive | Optimizer steps | Function elapsed, seconds | Running-compute estimate, USD |
|---|---:|---:|---:|---:|
| ppo-17 | 2048 / 2048 of 2,048 | 1,172 | 830.074 | 0.232952 |
| ppo-29 | 2047 / 2048 of 2,048 | 1,132 | 911.177 | 0.255713 |
| ppo-43 | 2048 / 2048 of 2,048 | 1,140 | 909.132 | 0.255139 |
| replay-17 | 2048 / 2048 of 2,048 | 5,278 | 1136.228 | 0.318871 |
| replay-29 | 2048 / 2048 of 2,048 | 4,586 | 963.195 | 0.270311 |
| replay-43 | 2047 / 2048 of 2,048 | 5,328 | 924.386 | 0.259420 |

Batch reports total **12,286 home, 12,288 alive, zero invalid calls**. The two away finishes occurred once each in PPO 29 and replay 43; they are retained failures to return. All six Modal functions returned completed; all six training reports are complete at 2048. These are reported training aggregates, not an independent reconstruction of the production trajectories. Replay used more optimizer updates than PPO despite the matched environment-episode budget.

Running CPU/memory estimate from the six [completed function returns](status.json): **$1.592405**. This uses actual returned elapsed durations and frozen resource rates; it is not an invoice and excludes image build/startup/storage/egress. There were no GPU jobs or model API calls in these returns.

## Evidence boundary and handoff

Copied unchanged: 42 report/policy/validation artifacts, the [download hash manifest](download-manifest.json), [stage decision](decision.json), [terminal function status](status.json) and [receipt](receipt.json). The decision retains its original temporary-directory provenance; portable copies are under `runs/`.

The [closure verification](verification.json) checks all 42 hashes, 41 source pins against the original freeze, all six completion/history counters, and 576 retained validation map identities, terminal reward arithmetic and safety totals. It does **not** independently replay the production validation physics or reconstruct the production learning updates. Full training batches and optimizer/replay checkpoints remain on Modal volume `junction-learning-campaign`; they were not downloaded or audited as part of this closure. The earlier smoke and control audits remain separate evidence.

Preserve all original policies, reports, source pins and the old archive interruption caveat. Do not interpret this result as an LLM-training result, a frontier-agent gap, a learned-policy win over the reference, or a result obtained with the newly merged navigator. The [final-version protocol](../../learning-final.md) starts fresh learners and uses its own source freeze.
