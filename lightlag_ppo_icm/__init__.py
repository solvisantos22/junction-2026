"""PPO + ICM baseline tester for the Lightlag environments (see README.md).

    python3 -m lightlag_ppo_icm.train --env max --out lightlag_ppo_icm/runs/max
    python3 -m lightlag_ppo_icm.check --policy lightlag_ppo_icm/policies/max.npz --seeds 2700-2739
"""

import os

# The networks are tiny, and the rollouts run on several processes. One maths thread per process
# is much faster here than a thread pool in every process fighting for the same cores. Only a
# default: set the variable yourself to override it. It has to be set before numpy is loaded.
for _name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_name, "1")
