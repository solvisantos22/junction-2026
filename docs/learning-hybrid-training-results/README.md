# Greedy-prior PPO training

Preparation is complete; launch is pending the published source freeze.
[Protocol](../learning-hybrid-training.md) · [six-run configuration](campaign.json).

The new learner starts with greedy as its most likely action and learns
residual preferences using the original PPO objective and official mission
reward. Three matched plain-PPO runs use identical residual-network
initialization without the greedy prior. Both keep every legal action. This is
a new experiment from scratch; the original training and the parallel
[hybrid composition search](../learning-hybrid-results/README.md) stay unchanged.

The declared target is 4096 missions per run, with all six seeds retained and
development checkpoints at 0, 512, 2048 and 4096. Training uses worlds
620000–622047, development 628000–628063, and the still-unopened final range
629000–629127. All six must complete before the final policy freeze and fresh
comparison. No best seed, checkpoint substitution or automatic extension.

Prior inference at initialization is exactly greedy. Therefore any useful
learning claim must show improvement over greedy after training, alongside the
matched plain-PPO control and reference. The prior-versus-plain initial behavior
differs by design; that difference is not itself learning.

All **35 focused tests pass**, with independent model, trainer, launcher and evaluator reviews. [Prelaunch verification](verification.json). Verification includes real 32-mission prior/plain smoke runs on already-used
worlds 1/2, exact initial greedy command/reward equivalence, matched plain PPO
gradient equivalence, checkpoint/optimizer/RNG restoration, hard-deadline and
failure retention tests, and fresh-evaluation physics/choice/controller replay
checks on world 1. Those checks are preparation evidence, not a measured
production improvement.

Six Modal containers each have hard limits of 8 CPUs and 16 GiB, with six
rollout processes. The fixed three-hour allocation envelope is approximately
$9.09, below the $15 reservation and within the combined $75 initial-wave
ceiling. Build/startup/storage/egress are additional. Absolute compute cutoff:
15 November 05:30 UTC. No GPU or model API calls.

## Run and inspect

The pinned local runtime is `/tmp/junction-learning-venv`, with Python 3.12,
NumPy 2.3.4, Torch 2.9.1 and Modal 1.6.4. Explicitly set
`MODAL_PROFILE=solvi-junction` for cloud commands.

```sh
python -m tools.learning_hybrid_train.modal_job --write-freeze FREEZE --campaign docs/learning-hybrid-training-results/campaign.json
python -m tools.learning_hybrid_train.modal_job --prepare FREEZE
# Publish the freeze and source before this one-shot launch:
python -m tools.learning_hybrid_train.modal_job --launch FREEZE --receipt NEW_RECEIPT
python -m tools.learning_hybrid_train.modal_job --status RECEIPT
```

Status includes compact reports and checkpoint scores when their committed
volume files are available. The saved receipt retains the six original call
IDs; never launch again merely because the local client disconnects. A terminal
failure or ambiguous launch requires diagnosis. `--stop RECEIPT` requests the
new jobs stop; it does not touch either older experiment.

After all calls are terminal, use `--download RECEIPT --output NEW_DIRECTORY
--archives` to retain reports, policy/validation files and milestone optimizer
checkpoints. Full training batches remain on the Modal volume. Then:

```sh
python -m tools.learning_hybrid_train.evaluate --freeze POLICY_FREEZE --runs RUN_DIRECTORY_1 RUN_DIRECTORY_2 RUN_DIRECTORY_3 RUN_DIRECTORY_4 RUN_DIRECTORY_5 RUN_DIRECTORY_6
# Publish this all-seed policy freeze before opening final worlds:
python -m tools.learning_hybrid_train.evaluate --run POLICY_FREEZE --output NEW_EVALUATION --workers 8
python -m tools.learning_hybrid_train.evaluate --audit NEW_EVALUATION/report.json --workers 8
```

The final matrix contains the six trained policies, greedy, beam and one
deduplicated initial plain policy: 1152 missions. Initial priors equal greedy;
initial plain policies all choose home under deterministic inference. All 12
initial/final weight sets remain in the freeze, with an explicit equivalence
proof. Final audits repeat complete controller execution. Production optimizer
updates and full training batch bytes are retained but not independently
reconstructed by the final evaluator.

App IDs, progress, measured estimates, results and submission copy will follow.
The existing reference stays in place regardless of this experiment's result.
