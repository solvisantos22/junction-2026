"""A trained policy as a player: a callable that gets the five public tools, like every other player.

    from lightlag_ppo_icm.player import load_player
    play = load_player("lightlag_ppo_icm/policies/max.npz")
    play(PublicTools(make_max_env(seed=7, delay=3)))      # then the evaluator runs out the horizon

Greedy by default (the most likely action at every slot); `sample_seed` draws the actions from
the policy instead, as in training. Two players without a network use the same adapter, so that
what the learning adds can be told apart from what the adapter gives:

    random_player   a uniform random action at every slot: where an untrained agent starts
    plain_player    a rule of a few lines on the observation: sample when the nearest open target
                    is in range, else drive at it, and turn for home when time or energy runs low
"""

import math

import numpy as np

from .agent import load_policy
from .task import BASE, FIRST_DRIVE, GLOBAL, SAMPLE, WAIT, RoverTask, TaskConfig


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


def plain_chooser(config):
    """observation -> action, by a hand-written rule that reads the observation only."""
    sizes = len(config.metres)

    def drive(cos, sin, near):
        heading = int(round(math.degrees(math.atan2(sin, cos)) / (360.0 / config.headings))) % config.headings
        size = sizes - 1 if near > 0.45 else (1 if near > 0.2 else 0)
        return FIRST_DRIVE + heading * sizes + size

    def choose(obs):
        base = obs[GLOBAL:GLOBAL + BASE]
        target = obs[GLOBAL + BASE:]
        if target[0] > 0 and base[5] > 0.15 and base[6] > 0.12:      # a target is open; margins to get home
            return SAMPLE if target[5] > 0 else drive(target[1], target[2], target[4])
        return WAIT if base[4] > 0 else drive(base[0], base[1], base[3])

    return choose


def plain_player(config=None):
    config = config or TaskConfig()

    def play(tools, env=None):
        RoverTask(tools, config).play(plain_chooser(config))

    return play
