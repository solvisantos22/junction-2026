# Greedy-prior PPO: fixed parallel training experiment

Sölvi authorized aggressive parallel work with roughly eight hours remaining.
This separately claimed experiment follows the [hybrid search](learning-hybrid.md)
but does not reuse its fresh maps or modify its frozen sources. It tests a
specific response to the original PPO plateau: begin exploration around useful
greedy choices and learn when to depart from them. This is a hypothesis, not a
promised improvement. No previous training run is resumed.

## Intervention and matched control

Use the frozen public option observations, navigator, feasibility logic and
official terminal reward. All legal actions remain available, including home.
For each observation with `n` legal actions, define

`q(action) = 0.8 * [action == greedy(observation)] + 0.2 / n`.

The **prior** policy uses learned residual logits plus `log(q)`. The **plain**
control uses the same architecture and initialization without this prior. Zero
the final actor head at scratch initialization in both variants. Thus initial
prior inference is exactly greedy, while the plain control initially samples
uniformly and its deterministic argmax follows the original candidate order.
That initial behavioral difference is part of the intervention and must be
reported; it is not learning. Improvement after training must be compared with
greedy as well as the matched plain PPO control.

Compute greedy's index from the original public observation, preserving its
floating-point/tie behavior. Apply the same effective logits during stochastic
collection, old/current PPO log probabilities, entropy, deterministic
validation and exported-policy inference. The frozen PPO loss/advantage/update
implementation may be reused through a wrapper, but neither its source nor the
original policy files may be edited. Retain original candidate context and
masks. No hidden state, reward shaping, teacher trajectory or map oracle.

## Fixed training and maps

Six new runs: variants `prior` and `plain`, each with seeds **17, 29, 43**.
Each receives exactly **4096 missions**, batches of 32, six rollout processes,
the original learning rate .0003, four PPO epochs, clip .2, entropy coefficient
.01, gamma 1 and original value/gradient settings. Use the same deterministic
map order and rollout action-seed convention for all runs. No hyperparameter
search, best-seed choice, checkpoint selection or automatic extension.

| Use | Worlds | Treatment |
|---|---|---|
| Smoke | 1, 2 | Already used; local/cloud verification only |
| Training | 620000–622047 | 2048 worlds, deterministic shuffle, two passes |
| Development | 628000–628063 | Fixed 64 worlds at 0, 512, 2048 and 4096 missions |
| Fresh final | 629000–629127 | Unopened until all-seed policy freeze is published |

All ranges were reserved before execution. The prior experiment's final worlds,
current hybrid search maps, campaign worlds 2026–2029, MAX pool 500–523 and all
teammates' ranges remain excluded. Save initial and milestone policy weights,
optimizer/RNG state, training metrics and validation episodes with source and
policy hashes. Failure/deadline reports retain actual counts and completed
milestones. They do not substitute a favorable checkpoint or silently restart.

## Evaluation and success rules

Only if **all six runs complete 4096 missions and required validations** may the
fresh evaluation open. First publish the exact initial/final policies for every
seed, source/runtime and final job matrix on `main`. If any run is incomplete,
publish the development evidence and failure diagnosis; do not substitute a
seed or spend the fresh maps on an incomplete primary comparison.

On all 128 fresh maps evaluate each of the six final policies plus greedy and
the frozen beam reference. Initial prior is provably the same greedy chooser;
retain the initial weights and equivalence verification rather than invent a
separate learned-before gain. Initial plain policies share identical zero-head
behavior and can be reported separately if explicitly frozen before evaluation.
Report each seed and the three-seed mean for both variants, all deaths/away
endings, invalid calls and incomplete outcomes.

Primary contrast: average the three prior seeds within each map, then compare
with greedy on that map. A useful final gain requires **at least .01** mean
reward improvement, paired-map bootstrap 95% lower bound above zero, zero
deaths/errors/invalid calls and home rate at least greedy minus 1/128.
Bootstrap 20,000 resamples with seed **629128**. The predeclared secondary
contrast is prior versus plain, averaged across their three seeds within each
map; also report both versus beam. Intervals are conditional on these fixed
initializations. No further tuning or selection after opening final worlds.

Every retained fresh case must pass physics/grade and effective-policy-choice
audits; repeat the complete controller to verify observation/command linkage.
All policies and baselines use the same frozen environment. Any exact campaign
showcase is a separate post-freeze descriptive comparison, not a selection set
or evidence of general superiority over LLMs. Keep the current team reference.

## Compute, recovery and handoff

Use a new `junction-greedy-prior` Modal app, volume and control store in Sölvi's
`solvi-junction` workspace. Exactly six training containers, each requesting and
limited to **8 CPUs and 16 GiB**, with six rollout processes and Torch threads
one. No GPUs or model API calls. Each job is bounded to **three hours**, with
absolute cutoff **2026-11-15 05:30 UTC**. Freeze and publish resources, source,
weights/initialization rules and complete six-job identity list before launch.
Persist call IDs and checkpoint files. No automatic retries, resume or repeated
completed training. Diagnose an ambiguous launch or failure before new spend.

At the documented CPU/memory rates, six containers at full declared allocation
for three hours cost approximately **$9.092736**. Reserve at most **$15** for
running compute, within the earlier **$75 combined initial-wave ceiling**; the
hybrid search's frozen maximum allocation is about $24.11. These are estimates
excluding build/startup/storage/egress, not account balance or invoices.
The two experiments use at most 71 containers together. Original PPO timings
suggest roughly 1–1.5 hours for 4096 missions, with a conservative 2–3 hour
allowance for validation and auditing. Measure and update this estimate.

Publish each completed milestone's evidence promptly. Handoff must include the
initial-versus-final learning story, matched controls, full limitations, app
IDs/cost, source freezes, audits and a figure if results merit one. Negative
findings remain useful and must be retained. This scope does not modify or
duplicate Kristján's strategy-switch learner or Manh's PPO experiments.
