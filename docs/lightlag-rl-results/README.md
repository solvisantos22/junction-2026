# Small-policy RL: results and handoff

This implements the user's chosen small-model training experiment under the
[fixed protocol](../lightlag-rl.md). It supports AfterQuery's optional learning
stretch. The model learns target selection; the existing Traverse navigator,
state estimator and safety rules remain fixed. No frontier-agent gap follows
from this experiment.

## Verified preparation

- **30 focused tests pass**: public-observation/action boundaries, full-horizon
  grading, numerical gradient checks, update direction, paired-map learning,
  checkpoints/timeouts/source drift and cloud-launch isolation.
- [Local smoke](local-smoke/training.json): eight actual episodes on already-used
  maps 1 and 2, two updates, completed in about four seconds. Batch mean rewards
  were .0258473 and .0183114. This is execution verification, not evidence of
  learning. The smoke weights are discarded.
- Independent review confirms correct policy-gradient/Adam ascent signs and no
  hidden simulator inputs to the actor. The full mission is graded at tick 420.
- Modal profile `solvi-junction` was configured by the user. Tokens are local,
  excluded from source snapshots and absent from the training subprocess.
- The first real job is one CPU-only run: 512 training episodes, explicit four
  core/8 GiB limits and a one-hour timeout. No GPU, model API or automatic retry.

Training worlds 71000–71127 and check worlds 72000–72039 were reserved before
use. Fresh evaluation remained unopened until the final weights froze. The completed
production run retains its source/configuration freeze and every checkpoint.

Reproduce preparation with Python 3.12, NumPy 2.3.4 and Modal client 1.6.4:

```sh
python -m unittest discover -s tests/lightlag_rl -v
python -m lightlag_rl.train --output /tmp/rl-smoke-new --updates 2 --batch-size 4 --workers 2 --train-seed 17 --max-seconds 120 --smoke
```

Use the pinned production source revision for the full experiment. The protocol
stays unchanged; completed results and decisions are appended here.


The independent evaluator is now verified on the two used smoke maps: all 12
policy/control episodes, their complete 420-tick replays and 428 retained goal
choices reconstruct. Its true do-nothing control sends no commands. This smoke
comparison does not pass the learning screen and is not used for tuning or model
selection. Production weights and all 40 fresh worlds remain separate.

## Completed Modal training

[Run ap-e9VDJ99Y3AAjaY30NcNemX](https://modal.com/apps/solvisantos22/main/ap-e9VDJ99Y3AAjaY30NcNemX)
completed all **512 missions and 16 updates** in 466.74 trainer seconds
(468.24 seconds including the function wrapper). The single four-core/8 GiB CPU
job returned successfully, with zero retries and no volume-commit errors.
[Job metadata](modal/pilot-01/modal-job.json), [metrics/checkpoints](modal/pilot-01/training/training.json)
and [stdout](modal/pilot-01/train.stdout.txt) retain the actual run.

Running CPU/memory is estimated at **$0.03285** from the recorded duration and
published $0.252576/hour resource rate. This is not an invoice and excludes
image build, startup, storage and egress. No Claude or other model API was used.

The [training audit](modal/pilot-01/training/audit.json) reconstructs all 16
updates, 512 episodes' recorded rewards and **21,078 sampled choices**, including
Adam and RNG state, against 34 source pins. There were zero retained invalid
calls. Its tolerance is 1e-9 for cross-CPU floating-point differences. This audit
checks the recorded learning calculation; it does not independently replay
training physics or reextract features. The separate fresh evaluation checks
physics and grades.

Initial policy SHA-256: `2ccca99c72e2302330f594ae03958ed1b8699dfa7fd92295675b5d59b94f431b`.
Final policy SHA-256: `3f636cac0bb774db76060004c04666eb41693f15acc766aca43a7e8942b5c33a`.
The final checkpoint was used without selection or tuning. Check maps
**72000–72039 are now consumed**; their independently audited comparison and
handoff will be published in the next increment. No further cloud run is queued.
