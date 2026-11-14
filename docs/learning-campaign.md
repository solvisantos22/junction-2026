# Contextual learning campaign — frozen protocol

Sölvi authorized actual Modal training, with about 14 hours to submission and $300 reported **shared team credit**. This campaign uses a small bounded part of that pool. Kristján owns the complementary charging-feasibility ablation and planner-imitation branch. This campaign trains **from scratch**, and does not change Traverse physics, the official reward, the reference, the canonical task or the team's provisional project choice.

## Why these methods

[Rainbow](https://arxiv.org/abs/1710.02298) combines six DQN improvements; its Atari ablation makes prioritized replay and multi-step learning useful candidates, not a promise for Traverse. We compare [PPO](https://arxiv.org/abs/1707.06347) with **Rainbow-inspired Double DQN, prioritized replay and three-option-step returns**. The latter is not full Rainbow: it omits distributional C51, noisy layers and a dueling head. [Demonstration learning](https://arxiv.org/abs/1704.03732) is a sensible alternative, owned by Kristján's branch. GPU/LLM fine-tuning is deferred: these small networks and simulator rollouts are CPU work; timing will tell us whether this changes.

## Public interface and objective

Both algorithms share a 64-wide candidate encoder, mean/max candidate-set context, 20 candidate features, 14 global features, and the inherited navigator. Invalid candidates remain visible to pooling but cannot be selected. IDs are bookkeeping, never embeddings. Public observations include charging, accrued credited science and remaining options. No hidden position, map seed or future-value denominator enters the network. The trusted runner alone supplies the unchanged normalized official terminal score, including its return/survival factor.

Actions select persistent target options. A queued sample ends an option and allows the next goal decision while the sample is in flight. Home is absorbing return-and-park. Kristján’s shared `lightlag_rl_feasible.adapter.visit_return` helper supplies the public RouteProblem visit-plus-home estimate. That estimate includes sample cost and charging waits; the navigator/return guard can terminate an infeasible option. This model uses approximate energy and four-tick waits, so masks are estimates, not a guarantee. Every episode runs all 420 ticks. Only actual decisions become transitions. Intermediate reward is zero and gamma is one, preserving the official undiscounted finite-horizon objective. Duration and termination reason are retained.

## Fixed training design

- Algorithms: scratch PPO and scratch replay learner; initialization seeds **17, 29, 43**, all retained.
- Training maps **80000–80511** (512), common seeded permutation per pass, repeat as needed. Validation **81000–81031** (32). Final check **82000–82039** (40), unopened until all policies are frozen. Local engineering smoke uses only worlds 1 and 2.
- Batches: 32 completed episodes under one frozen behavior policy. PPO: full-episode Monte Carlo returns, learned baseline, normalized advantages, four epochs, minibatch128, clip.2, entropy.01, value coefficient.5. Adam3e-4; gradient norm cap.5.
- Replay: Double DQN, three-option-step returns, capacity50000, minibatch128, PER alpha.6, beta.4→1, epsilon1→.05. Both schedules reach their endpoint at2048 episodes then hold. One gradient update per four new options (rounded up), capped128 per batch, after128 stored options; target sync every100 gradient updates. Report actual optimization work; equal missions do not imply equal compute.
- Initial and milestone validation at 0, 512, 2048, 8192, 32768 episodes. Evaluation uses deterministic argmax, not exploratory sampling. No hyperparameter or interface changes after production data opens.

## Staging and stopping decisions

Pilot: all six runs to **2048 episodes**, common stage deadline90 minutes. A method qualifies for continuation only if all three runs complete with no validation deaths/invalid calls, at least two of three have positive paired mean validation gain over their own initial policy, and the method's mean gain is at least **.03**. All three initialization seeds of a qualifying method continue to8192; never select only the best seed. This phase has a common three-hour deadline. A method qualifies for the optional32768 phase only if all three8192 runs complete without validation deaths/invalid calls and its across-seed mean validation reward improves at least **.01** over2048. This phase also has a common three-hour deadline. A declining home rate is reported alongside the official reward; no additional home threshold is silently imported or retroactively waived from earlier frozen studies. Incomplete runs remain incomplete and do not qualify by extrapolation.

The last completed milestone is retained if a deadline stops a run. All algorithms are compared at their matched2048 budget; later unequal-budget results are labelled. No auto-relaunch, algorithm substitution, extra tuning or fresh check retry. A failed pilot is a useful negative result; the separately owned imitation branch is then the natural next hypothesis.

## Final evaluation and interpretation

Before opening final maps, publish hashes of every included initial and last completed milestone policy and the evaluation manifest. Evaluate each on the same40 maps, plus the charge-aware greedy option control and unchanged original beam pilot. Keep every initialization, death and failure. Report all per-seed means, home counts and paired map differences; bootstrap maps with10000 draws, explicitly conditional on three training initializations. Validation comparisons guide staging only; final maps are used once for confirmation, never to choose weights. A learning improvement is distinct from beating the beam reference, and neither alone establishes a frontier-language-model gap or an AfterQuery submission success.

## Cloud limits and evidence

[Modal resources](https://modal.com/docs/guide/resources) and [pricing](https://modal.com/pricing) checked before launch. At most3 containers, each16 CPU and32 GiB memory,14 rollout workers, no GPU, no model API. CPU+memory estimate is $1.010304/container-hour; summed phase envelope22.5 container-hours is **$22.73184**, further bounded by absolute **2026-11-15 03:30 UTC** campaign deadline. Launcher also rejects an envelope above$31. Builds/startup/storage/egress are additional; this is not an invoice/balance cap. The remaining shared team credit is not claimed by this experiment.

One-time durable campaign/stage reservations prevent concurrent duplicate apps. Per-stage and absolute deadlines survive container rescheduling, with a subprocess watchdog and stop marker. Every continuation checks matching source/runtime/seed and resumes model, target, Adam, replay, counters and RNG. Every training batch retains behavior weights, observations, choices, terminal results and metrics; full optimizer/replay checkpoints at milestones and latest. Validation/final episodes retain complete physics replays. Policy checkpoints, source pins, receipts, results and audit evidence are linked in the repo; large optimizer/replay archives stay on the dedicated Modal volume. No credentials or private logs are committed.
