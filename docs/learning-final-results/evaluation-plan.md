# Frozen final evaluation

This selection is published before opening worlds **82000–82039**. Training source remains `becbf3e`; the original source/resource freeze and six Modal calls are unchanged. No new training or cloud allocation is required for this evaluation.

The self-contained [policy freeze](policy-freeze.json) has SHA-256 `78db73d1afb6ce2dd2c51a9597c14abcaeddd01e7331bf95ca297664fddd1fb7`. It contains every initialization's initial policy, matched-2048 policy and latest completed declared checkpoint, plus greedy and the frozen beam reference. There are **19 distinct arms × 40 maps = 760 cases**. Every policy is deterministic during evaluation.

| Method | Training seed | Training missions completed / attempted | Terminal status | Latest declared checkpoint |
|---|---:|---:|---|---:|
| PPO | 17 | 8192 / 8192 | Complete | 8192 |
| PPO | 29 | 8192 / 8192 | Complete | 8192 |
| PPO | 43 | 8192 / 8192 | Complete | 8192 |
| Replay | 17 | 8192 / 8192 | Complete | 8192 |
| Replay | 29 | 8192 / 8192 | Complete | 8192 |
| Replay | 43 | 6880 / 8192 | Deadline | 2048 |

Replay seed 43's latest and matched-2048 roles share one artifact and are evaluated once per map. Its partial training is retained, but there is no declared 6880 checkpoint. Neither method passed the unchanged continuation gate: [decision](fit/decision.json), [terminal call status](fit/status.json), [download manifest](fit/download-manifest.json). No seed is dropped and no policy is chosen by validation or final score. The deadline report is already terminal; no status reconciliation or evidence rewrite was needed.

Run the frozen `tools.learning_final.evaluate` from `/tmp/junction-learning-final-frozen` using `/tmp/junction-learning-venv/bin/python`, with six local workers. Runtime remains Python 3.12.16 / NumPy 2.3.4 / Torch 2.9.1. The original evaluator and training source stay unchanged. Store complete cases under `evaluation/`, then audit the physics, scores, saved policy choices and summary arithmetic. Bootstrap units are maps, with 10,000 draws and seed 17, conditional on the three retained training initializations. Report both the equal-budget 2048 comparison and the latest-checkpoint comparison; the latter has unequal replay budgets.

## Direct comparison with the recorded LLM campaign

Sölvi requested this additional comparison before deciding whether learning merits prominence in the submission. After the policy freeze is published, use **the same frozen arms** on the exact campaign worlds **2027, 2028, 2029**. Publish the campaign runner's source/configuration freeze before opening those cases. Each mission starts a fresh navigation policy; continue to campaign completion and aggregate `sum(raw_score) / sum(max_available_value)`.

Retain all three training seeds, initial and matched-2048 results, greedy and beam. Do not choose a model or checkpoint using these submission worlds. Compare with all recorded campaign attempts, including Opus's mean and best, and disclose EPIPE/NonZeroExit errors and the length-censored Haiku attempt. This is a fixed submission showcase, not a new independent generalization test. The learned system includes a hand-written navigator and safety scaffold; outperforming a recorded agent would establish a task-performance comparison, not independent neural reasoning superiority or matched training/inference budgets.

Keep the current reference regardless of this showcase. Training improvement, superiority over greedy, and superiority over recorded LLM runs are separate claims. The untouched-world evaluation remains the original predeclared experiment; this additional campaign comparison does not replace it or alter checkpoint selection.
