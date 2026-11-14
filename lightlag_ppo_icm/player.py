"""A trained policy as a player: a callable that gets the five public tools, like every other player.

    from lightlag_ppo_icm.player import load_player
    play = load_player("lightlag_ppo_icm/policies/max.npz")
    play(PublicTools(make_max_env(seed=7, delay=3)))      # then the evaluator runs out the horizon

Greedy by default (the most likely action at every slot); `sample_seed` draws the actions from
the policy instead, as in training. `random_player` is the same adapter with a uniform random
action at every slot: the floor an untrained agent starts from.
"""

import numpy as np

from .agent import load_policy
from .task import RoverTask, TaskConfig


def load_player(path, sample_seed=None):
    policy, extra = load_policy(path)
    config = TaskConfig.from_dict(extra["task"])

    def play(tools, env=None):
        rng = None if sample_seed is None else np.random.default_rng(sample_seed)
        RoverTask(tools, config).play(lambda observation: policy.act(observation, rng)[0])

    play.extra = extra
    return play


def random_player(seed=0, config=None):
    config = config or TaskConfig()

    def play(tools, env=None):
        rng = np.random.default_rng(seed)
        RoverTask(tools, config).play(lambda observation: int(rng.integers(config.n_actions)))

    return play
