"""A trained policy as a player: a callable that gets the five public tools, like every other player.

    from lightlag_ppo_icm.player import load_player
    play = load_player("lightlag_ppo_icm/policies/max.npz")
    play(PublicTools(make_max_env(seed=7, delay=3)))      # then the evaluator runs out the horizon

Greedy by default (the most likely action at every slot); `sample_seed` draws the actions from
the policy instead, as in training. The home guard is on when the policy was trained with it;
`home_guard` switches it on or off whatever the training did. Two players without a network use
the same adapter, so that what the learning adds can be told apart from what the adapter gives:

    random_player   a uniform random action at every slot: where an untrained agent starts
    plain_player    a rule of a few lines on the observation: sample when the nearest open target
                    is in range, else drive at it, and turn for home when time or energy runs low

A policy trained in the target mode of the traverse (targets.py) plays that mode, mask included.
Its two players without a network:

    random_target_player    a random target among those the mask allows, never home by choice
    nearest_target_player   always the nearest target the mask allows (the first slot)
    cluster_target_player   the allowed target with the most value per tick of travel, counting a
                            quarter of what lies near it (a rule picked on development worlds, to
                            see whether choices beyond the nearest can pay)
"""

import dataclasses
import math

import numpy as np

from .agent import load_policy
from .targets import GLOBAL as TARGET_GLOBAL, PER_SLOT, TargetConfig, TargetTask, is_target_config
from .task import BASE, FIRST_DRIVE, GLOBAL, SAMPLE, WAIT, RoverTask, TaskConfig


def load_player(path, sample_seed=None, home_guard=None):
    policy, extra = load_policy(path)
    if is_target_config(extra["task"]):
        targets = TargetConfig.from_dict(extra["task"])

        def play_targets(tools, env=None):
            rng = None if sample_seed is None else np.random.default_rng(sample_seed)
            TargetTask(tools, targets).play(lambda observation, mask: policy.act(observation, rng, mask)[0])

        play_targets.extra = extra
        return play_targets
    config = TaskConfig.from_dict(extra["task"])
    if home_guard is not None:
        config = dataclasses.replace(config, home_guard=bool(home_guard))

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


def random_target_player(seed=0, config=None):
    config = config or TargetConfig()

    def play(tools, env=None):
        rng = np.random.default_rng(seed)

        def choose(observation, mask):
            allowed = np.flatnonzero(mask[:config.home_action])
            return int(rng.choice(allowed)) if len(allowed) else config.home_action

        TargetTask(tools, config).play(choose)

    return play


def nearest_target_player(config=None):
    config = config or TargetConfig()

    def play(tools, env=None):
        TargetTask(tools, config).play(lambda observation, mask: 0 if mask[0] else config.home_action)

    return play


def cluster_target_player(config=None):
    """(what a sample there credits + a quarter of the value of the targets within NEAR_TICKS of it)
    / (ticks to get there + 5), the highest of the allowed targets. Picked on the development worlds
    420000-420031 among six such rules, as a check that a choice other than the nearest can pay; it
    is a baseline, not tuned further."""
    config = config or TargetConfig()

    def choose(observation, mask):
        allowed = np.flatnonzero(mask[:config.slots])
        if not len(allowed):
            return config.home_action
        slots = np.asarray(observation[TARGET_GLOBAL:], dtype=np.float64).reshape(config.slots, PER_SLOT)
        score = (slots[allowed, 3] + slots[allowed, 9]) / (slots[allowed, 1] + 0.05)
        return int(allowed[np.argmax(score)])

    def play(tools, env=None):
        TargetTask(tools, config).play(choose)

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
