"""Matched prior/plain PPO using the unchanged, source-pinned PPO update math."""

from __future__ import annotations

from copy import deepcopy

import numpy as np
import torch

from lightlag_learning.learners import DEFAULT_CONFIG, Learner as FrozenLearner, _act
from lightlag_learning.models import json_state, restore_json_state

from .model import GREEDY_MASS, PriorNetwork, VARIANTS


POLICY_SCHEMA = "lightlag-hybrid-train-policy-v1"
CHECKPOINT_SCHEMA = "lightlag-hybrid-train-checkpoint-v1"
INITIALIZATION = "zero-final-actor-linear-weight-and-bias"


class Learner(FrozenLearner):
    """The original encoder, value model, optimizer and PPO objective are reused.

Only the new model wrapper changes action logits. The inherited PPO update
calls model.observations for both old and current probabilities, ensuring the
same fixed prior is used by collection, importance ratios, and entropy.
"""

    def __init__(self, algorithm, candidate_dim, global_dim, seed, total_episodes=4096):
        if algorithm not in VARIANTS:
            raise ValueError("algorithm must be prior or plain")
        super().__init__("ppo", candidate_dim, global_dim, seed, total_episodes)
        self.algorithm = algorithm
        # Same residual network and same zero actor head in both variants.
        # Adam was created on these exact Parameter objects and has no state yet.
        with torch.no_grad():
            self.model.score[-1].weight.zero_()
            self.model.score[-1].bias.zero_()
        self.model = PriorNetwork(self.model, algorithm)

    def act(self, observation, rng, explore=True):
        return _act(self.model, "ppo", observation, rng, explore, 0.0)

    def inference_state(self):
        return {"schema": POLICY_SCHEMA, "algorithm": self.algorithm,
                "optimizer_algorithm": "ppo", "initialization": INITIALIZATION,
                "greedy_mass": GREEDY_MASS, "model": self.model.export(),
                "episodes_seen": self.episodes_seen, "config": dict(self.config)}

    def update(self, episodes):
        # The superclass dispatch distinguishes PPO from replay by its algorithm
        # name, so retain only its bookkeeping here and invoke its PPO math.
        observations = self._validate(episodes)
        before = self.gradient_steps
        self.episodes_seen += len(episodes)
        self.transitions_seen += len(observations)
        result = self._ppo_update(episodes, observations)
        self.updates += 1
        return {"algorithm": self.algorithm, "optimizer_algorithm": "ppo",
                "episodes_seen": self.episodes_seen, "transitions_seen": self.transitions_seen,
                "updates": self.updates, "gradient_steps": self.gradient_steps,
                "batch_gradient_steps": self.gradient_steps - before,
                "mean_episode_reward": float(np.mean([episode["reward"] for episode in episodes])),
                **result}

    def state_dict(self):
        return {"schema": CHECKPOINT_SCHEMA, "algorithm": self.algorithm,
                "optimizer_algorithm": "ppo", "initialization": INITIALIZATION,
                "greedy_mass": GREEDY_MASS, "seed": self.seed, "config": dict(self.config),
                "model": self.model.export(), "optimizer": json_state(self.optimizer.state_dict()),
                "rng": deepcopy(self.rng.bit_generator.state),
                "episodes_seen": self.episodes_seen, "transitions_seen": self.transitions_seen,
                "gradient_steps": self.gradient_steps, "updates": self.updates}

    @classmethod
    def from_state(cls, state):
        _validate_identity(state, CHECKPOINT_SCHEMA)
        model = state["model"]["residual"]
        learner = cls(state["algorithm"], model["candidate_dim"], model["global_dim"],
                      state["seed"], state["config"]["schedule_episodes"])
        restored = PriorNetwork.from_export(state["model"])
        learner.model.load_state_dict(restored.state_dict())
        learner.optimizer.load_state_dict(restore_json_state(state["optimizer"]))
        learner.rng.bit_generator.state = deepcopy(state["rng"])
        for name in ("episodes_seen", "transitions_seen", "gradient_steps", "updates"):
            value = state[name]
            if type(value) is not int or value < 0:
                raise ValueError("invalid checkpoint counter")
            setattr(learner, name, value)
        return learner

    def load_state_dict(self, state):
        restored = self.from_state(state)
        if (restored.algorithm != self.algorithm or restored.seed != self.seed
                or restored.model.candidate_dim != self.model.candidate_dim
                or restored.model.global_dim != self.model.global_dim):
            raise ValueError("checkpoint belongs to a different learner")
        self.__dict__.update(restored.__dict__)


def _validate_identity(state, schema):
    if (state.get("schema") != schema or state.get("algorithm") not in VARIANTS
            or state.get("optimizer_algorithm") != "ppo"
            or state.get("initialization") != INITIALIZATION
            or state.get("greedy_mass") != GREEDY_MASS
            or state["model"].get("variant") != state["algorithm"]):
        raise ValueError("unrecognized prior/plain learner state")
    config = state["config"]
    if (type(config.get("schedule_episodes")) is not int or config["schedule_episodes"] < 1
            or config != {**DEFAULT_CONFIG, "schedule_episodes": config["schedule_episodes"]}):
        raise ValueError("PPO hyperparameters differ from frozen configuration")
    if type(state.get("episodes_seen")) is not int or state["episodes_seen"] < 0:
        raise ValueError("invalid policy episode count")


def chooser_from_state(state, rng, explore=False):
    """Inference callback(obs)->int, with caller-owned exploration RNG."""
    _validate_identity(state, POLICY_SCHEMA)
    if not isinstance(rng, np.random.Generator):
        raise TypeError("action RNG must be an explicit numpy Generator")
    model = PriorNetwork.from_export(state["model"]).eval()

    def choose(observation):
        return _act(model, "ppo", observation, rng, explore, 0.0)

    return choose


def build_policy_state(learner):
    return learner.inference_state()
