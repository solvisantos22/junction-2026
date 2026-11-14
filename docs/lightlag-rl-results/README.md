# Small-policy RL: results and handoff

This implements the user's chosen small-model training experiment under the
[fixed protocol](../lightlag-rl.md). It supports AfterQuery's optional learning
stretch. The model learns target selection; the existing Traverse navigator,
state estimator and safety rules remain fixed. No frontier-agent gap follows
from this experiment.

## Verified preparation

- **22 focused tests pass**: public-observation/action boundaries, full-horizon
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
use. Fresh evaluation remains unopened during preparation. The production run
will retain its own source/configuration freeze and every training checkpoint.

Reproduce preparation with Python 3.12, NumPy 2.3.4 and Modal client 1.6.4:

```sh
python -m unittest discover -s tests/lightlag_rl -v
python -m lightlag_rl.train --output /tmp/rl-smoke-new --updates 2 --batch-size 4 --workers 2 --train-seed 17 --max-seconds 120 --smoke
```

Use the pinned production source revision for the full experiment. The protocol
stays unchanged; completed results and decisions are appended here.
