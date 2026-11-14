"""Scratch PPO and a Rainbow-inspired Double-DQN/n-step/PER comparison.

The replay learner is not full Rainbow: no C51, noisy layers or dueling head.
Both optimize the undiscounted official terminal reward at actual option choices.
Neither forced holds nor hidden simulator state enter the learning transitions.
"""

from __future__ import annotations

import copy
import math
from numbers import Integral

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from .models import CandidateNetwork, batch_observations, json_state, restore_json_state


DEFAULT_CONFIG = {
    "hidden": 64, "gamma": 1.0, "learning_rate": 3e-4, "gradient_clip": .5,
    "ppo_clip": .2, "ppo_epochs": 4, "batch_size": 128,
    "entropy_coefficient": .01, "value_coefficient": .5,
    "n_steps": 3, "replay_capacity": 50000, "priority_alpha": .6,
    "priority_beta_start": .4, "priority_epsilon": 1e-6,
    "target_sync_steps": 100, "new_transitions_per_gradient": 4,
    "maximum_replay_gradients": 128, "epsilon_start": 1.0, "epsilon_end": .05,
}


def ppo_surrogate(log_probability, old_log_probability, advantage, clip=.2):
    """Clipped ascent objective; min also handles negative advantages correctly."""
    ratio = torch.exp(log_probability - old_log_probability)
    return torch.minimum(ratio * advantage, ratio.clamp(1 - clip, 1 + clip) * advantage).mean()


def n_step_transitions(episode, steps=3):
    """One aggregate per real option choice; terminal boundaries never bootstrap."""
    transitions = episode["transitions"]
    aggregates = []
    for index, first in enumerate(transitions):
        window = []
        for transition in transitions[index:index + steps]:
            window.append(transition)
            if transition["done"]:
                break
        last = window[-1]
        aggregates.append({"obs": first["obs"], "action": first["action"],
                           "reward": sum(t["reward"] for t in window),
                           "next_obs": last["next_obs"], "done": last["done"],
                           "elapsed_ticks": sum(t["elapsed_ticks"] for t in window),
                           "steps": len(window)})
    return aggregates


def _stored_observation(observation):
    """Keep replay arrays compact; JSON checkpoints encode their typed bytes."""
    if observation is None:
        return None
    out = copy.deepcopy(observation)
    out["candidates"] = np.asarray(out["candidates"], dtype=np.float32)
    out["global"] = np.asarray(out["global"], dtype=np.float32)
    out["mask"] = np.asarray(out["mask"], dtype=bool)
    return out


class PrioritizedReplay:
    def __init__(self, capacity=50000, alpha=.6, epsilon=1e-6):
        self.capacity, self.alpha, self.epsilon = capacity, alpha, epsilon
        self.rows, self.priorities = [], []
        self.position, self.maximum_priority = 0, 1.0

    def __len__(self):
        return len(self.rows)

    def append(self, row):
        row = {**row, "obs": _stored_observation(row["obs"]),
               "next_obs": _stored_observation(row["next_obs"])}
        if len(self.rows) < self.capacity:
            self.rows.append(row)
            self.priorities.append(self.maximum_priority)
        else:
            self.rows[self.position], self.priorities[self.position] = row, self.maximum_priority
        self.position = (self.position + 1) % self.capacity

    def probabilities(self):
        if not self.rows:
            raise ValueError("cannot sample empty replay")
        priorities = np.asarray(self.priorities, dtype=float)
        if not np.isfinite(priorities).all() or np.any(priorities <= 0):
            raise ValueError("replay priorities must be positive and finite")
        powered = priorities ** self.alpha
        return powered / powered.sum()

    def sample(self, size, beta, rng):
        probabilities = self.probabilities()
        indices = rng.choice(len(self), size=size, replace=True, p=probabilities)
        # Normalize against the entire buffer, not the random minibatch maximum.
        weights = (len(self) * probabilities[indices]) ** (-beta)
        weights /= (len(self) * probabilities.min()) ** (-beta)
        return indices, [self.rows[index] for index in indices], weights.astype(np.float32)

    def update_priorities(self, indices, errors):
        for index, error in zip(indices, errors):
            priority = abs(float(error)) + self.epsilon
            if not math.isfinite(priority):
                raise ValueError("nonfinite TD error")
            self.priorities[int(index)] = priority
            self.maximum_priority = max(self.maximum_priority, priority)

    def state_dict(self):
        return {"capacity": self.capacity, "alpha": self.alpha, "epsilon": self.epsilon,
                "rows": self.rows, "priorities": self.priorities,
                "position": self.position, "maximum_priority": self.maximum_priority}

    @classmethod
    def from_state(cls, state):
        replay = cls(state["capacity"], state["alpha"], state["epsilon"])
        replay.rows, replay.priorities = state["rows"], state["priorities"]
        replay.position, replay.maximum_priority = state["position"], state["maximum_priority"]
        if (len(replay.rows) != len(replay.priorities) or len(replay) > replay.capacity
                or not 0 <= replay.position < replay.capacity
                or not math.isfinite(replay.maximum_priority) or replay.maximum_priority <= 0):
            raise ValueError("invalid replay checkpoint")
        if len(replay):
            replay.probabilities()
        return replay


def double_dqn_targets(online, target, rows):
    """Online selects a valid next action; frozen target evaluates that action."""
    result = torch.tensor([row["reward"] for row in rows], dtype=torch.float32)
    continuing = [index for index, row in enumerate(rows) if not row["done"]]
    if continuing:
        observations = [rows[index]["next_obs"] for index in continuing]
        with torch.no_grad():
            online_scores, _ = online.observations(observations)
            target_scores, _ = target.observations(observations)
            actions = online_scores.argmax(dim=-1)
            bootstrap = target_scores.gather(1, actions[:, None]).squeeze(1)
        result[continuing] += bootstrap  # gamma=1, independently of option duration
    return result


def _act(model, algorithm, observation, rng, explore, epsilon):
    if not isinstance(rng, np.random.Generator):
        raise TypeError("action RNG must be an explicit numpy Generator")
    with torch.no_grad():
        scores, _ = model.observations([observation])
    if not explore:
        return int(scores[0].argmax())
    if algorithm == "ppo":
        probabilities = scores[0].softmax(-1).cpu().numpy().astype(float)
        probabilities /= probabilities.sum()
        return int(rng.choice(len(probabilities), p=probabilities))
    if rng.random() < epsilon:
        return int(rng.choice(np.flatnonzero(observation["mask"])))
    return int(scores[0].argmax())


def chooser_from_state(state, rng, explore=False):
    """Build inference-only callable(obs)->action; caller retains action RNG state."""
    if state["schema"] != "lightlag-learning-policy-v1" or state["algorithm"] not in ("ppo", "replay"):
        raise ValueError("unrecognized inference state")
    model = CandidateNetwork.from_export(state["model"])
    model.eval()

    def choose(observation):
        return _act(model, state["algorithm"], observation, rng, explore, state["epsilon"])

    return choose


class Learner:
    """All mutable update state is checkpointed; action RNG belongs to the caller.

    PPO batches must be collected with one unchanged inference state. Returns
    are full-episode Monte Carlo targets. Replay uses four option transitions
    per gradient step, capped at 128 steps per incoming episode batch.
    """

    def __init__(self, algorithm, candidate_dim, global_dim, seed, total_episodes=2048):
        if algorithm not in ("ppo", "replay"):
            raise ValueError("algorithm must be ppo or replay")
        if type(total_episodes) is not int or total_episodes < 1 or type(seed) is not int:
            raise ValueError("invalid schedule or training seed")
        self.algorithm, self.seed = algorithm, seed
        self.config = {**DEFAULT_CONFIG, "schedule_episodes": total_episodes}
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(seed)
            self.model = CandidateNetwork(candidate_dim, global_dim, self.config["hidden"])
        self.target = CandidateNetwork.from_export(self.model.export()) if algorithm == "replay" else None
        if self.target is not None:
            self.target.eval()
            self.target.requires_grad_(False)
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=self.config["learning_rate"])
        self.rng = np.random.default_rng(seed)
        self.replay = PrioritizedReplay(self.config["replay_capacity"], self.config["priority_alpha"],
                                        self.config["priority_epsilon"]) if algorithm == "replay" else None
        self.episodes_seen = self.transitions_seen = self.gradient_steps = self.updates = 0

    @property
    def epsilon(self):
        fraction = min(self.episodes_seen / self.config["schedule_episodes"], 1.0)
        return self.config["epsilon_start"] + fraction * (self.config["epsilon_end"] - self.config["epsilon_start"])

    @property
    def beta(self):
        fraction = min(self.episodes_seen / self.config["schedule_episodes"], 1.0)
        return self.config["priority_beta_start"] + fraction * (1 - self.config["priority_beta_start"])

    def act(self, observation, rng, explore=True):
        return _act(self.model, self.algorithm, observation, rng, explore, self.epsilon)

    def inference_state(self):
        return {"schema": "lightlag-learning-policy-v1", "algorithm": self.algorithm,
                "model": self.model.export(), "epsilon": self.epsilon,
                "episodes_seen": self.episodes_seen, "config": dict(self.config)}

    def _validate(self, episodes):
        if not episodes:
            raise ValueError("an update needs completed episodes")
        observations, terminal_observations = [], []
        for episode in episodes:
            transitions = episode["transitions"]
            if not transitions or not math.isfinite(episode["reward"]) or not 0 <= episode["reward"] <= 1:
                raise ValueError("invalid completed episode")
            for index, transition in enumerate(transitions):
                observation, action = transition["obs"], transition["action"]
                last = index == len(transitions) - 1
                if (isinstance(action, bool) or not isinstance(action, Integral)
                        or not 0 <= action < len(observation["ids"]) or not observation["mask"][action]
                        or type(transition["done"]) is not bool or transition["done"] is not last
                        or type(transition["elapsed_ticks"]) is not int or transition["elapsed_ticks"] <= 0
                        or (not last and transition["next_obs"] != transitions[index + 1]["obs"])
                        or transition["reward"] != (episode["reward"] if last else 0.0)):
                    raise ValueError("invalid option transition or terminal reward")
                observations.append(observation)
                if last and transition["next_obs"] is not None:
                    terminal_observations.append(transition["next_obs"])
        # Validation uses exactly the same public observation boundary as inference.
        batch_observations(observations + terminal_observations,
                           self.model.candidate_dim, self.model.global_dim)
        return observations

    def _step(self, loss):
        if not torch.isfinite(loss):
            raise ValueError("nonfinite learner loss")
        self.optimizer.zero_grad(set_to_none=True)
        loss.backward()
        norm = nn.utils.clip_grad_norm_(self.model.parameters(), self.config["gradient_clip"], error_if_nonfinite=True)
        self.optimizer.step()
        self.gradient_steps += 1
        if self.target is not None and self.gradient_steps % self.config["target_sync_steps"] == 0:
            self.target.load_state_dict(self.model.state_dict())
        return float(norm)

    def _ppo_update(self, episodes, observations):
        transitions = [transition for episode in episodes for transition in episode["transitions"]]
        actions = torch.tensor([transition["action"] for transition in transitions], dtype=torch.long)
        returns = torch.tensor([episode["reward"] for episode in episodes for _ in episode["transitions"]], dtype=torch.float32)
        with torch.no_grad():
            scores, baseline = self.model.observations(observations)
            old_log = torch.distributions.Categorical(logits=scores).log_prob(actions)
            advantages = returns - baseline
            advantages = (advantages - advantages.mean()) / advantages.std(unbiased=False).clamp_min(1e-8)
        metrics = []
        for _ in range(self.config["ppo_epochs"]):
            permutation = self.rng.permutation(len(observations))
            for start in range(0, len(observations), self.config["batch_size"]):
                indices = permutation[start:start + self.config["batch_size"]]
                scores, values = self.model.observations([observations[index] for index in indices])
                distribution = torch.distributions.Categorical(logits=scores)
                log_probability = distribution.log_prob(actions[indices])
                policy_loss = -ppo_surrogate(log_probability, old_log[indices], advantages[indices], self.config["ppo_clip"])
                value_loss = F.mse_loss(values, returns[indices])
                entropy = distribution.entropy().mean()
                loss = policy_loss + self.config["value_coefficient"] * value_loss - self.config["entropy_coefficient"] * entropy
                norm = self._step(loss)
                with torch.no_grad():
                    log_ratio = log_probability - old_log[indices]
                    kl = (log_ratio.exp() - 1 - log_ratio).mean()
                metrics.append({"loss": float(loss.detach()), "policy_loss": float(policy_loss.detach()),
                                "value_loss": float(value_loss.detach()), "entropy": float(entropy.detach()),
                                "approx_kl": float(kl), "gradient_norm": norm})
        return {key: float(np.mean([row[key] for row in metrics])) for key in metrics[0]}

    def _replay_update(self, episodes):
        added = 0
        for episode in episodes:
            for row in n_step_transitions(episode, self.config["n_steps"]):
                self.replay.append(row)
                added += 1
        steps = (min(self.config["maximum_replay_gradients"],
                     math.ceil(added / self.config["new_transitions_per_gradient"]))
                 if len(self.replay) >= self.config["batch_size"] else 0)
        metrics = []
        for _ in range(steps):
            indices, rows, weights = self.replay.sample(self.config["batch_size"], self.beta, self.rng)
            targets = double_dqn_targets(self.model, self.target, rows)
            scores, _ = self.model.observations([row["obs"] for row in rows])
            actions = torch.tensor([row["action"] for row in rows], dtype=torch.long)
            values = scores.gather(1, actions[:, None]).squeeze(1)
            errors = targets - values
            loss = (F.smooth_l1_loss(values, targets, reduction="none") * torch.from_numpy(weights)).mean()
            norm = self._step(loss)
            self.replay.update_priorities(indices, errors.detach().cpu().numpy())
            metrics.append({"loss": float(loss.detach()), "mean_absolute_td_error": float(errors.detach().abs().mean()),
                            "gradient_norm": norm, "mean_importance_weight": float(weights.mean())})
        summary = {key: float(np.mean([row[key] for row in metrics])) for key in metrics[0]} if metrics else {}
        return {**summary, "replay_size": len(self.replay), "replay_added": added, "beta": self.beta}

    def update(self, episodes):
        observations = self._validate(episodes)
        before = self.gradient_steps
        self.episodes_seen += len(episodes)
        self.transitions_seen += len(observations)
        result = self._ppo_update(episodes, observations) if self.algorithm == "ppo" else self._replay_update(episodes)
        self.updates += 1
        return {"algorithm": self.algorithm, "episodes_seen": self.episodes_seen,
                "transitions_seen": self.transitions_seen, "updates": self.updates,
                "gradient_steps": self.gradient_steps, "batch_gradient_steps": self.gradient_steps - before,
                "mean_episode_reward": float(np.mean([episode["reward"] for episode in episodes])),
                "epsilon": self.epsilon, **result}

    def state_dict(self):
        return {"schema": "lightlag-learning-checkpoint-v1", "algorithm": self.algorithm,
                "seed": self.seed, "config": dict(self.config), "model": self.model.export(),
                "target": self.target.export() if self.target is not None else None,
                "optimizer": json_state(self.optimizer.state_dict()),
                "rng": copy.deepcopy(self.rng.bit_generator.state),
                "replay": json_state(self.replay.state_dict()) if self.replay is not None else None,
                "episodes_seen": self.episodes_seen, "transitions_seen": self.transitions_seen,
                "gradient_steps": self.gradient_steps, "updates": self.updates}

    @classmethod
    def from_state(cls, state):
        if state["schema"] != "lightlag-learning-checkpoint-v1":
            raise ValueError("unrecognized learner checkpoint")
        config = state["config"]
        if config != {**DEFAULT_CONFIG, "schedule_episodes": config["schedule_episodes"]}:
            raise ValueError("checkpoint hyperparameters differ from the frozen learner")
        model = state["model"]
        learner = cls(state["algorithm"], model["candidate_dim"], model["global_dim"],
                      state["seed"], config["schedule_episodes"])
        learner.model.load_state_dict(CandidateNetwork.from_export(model).state_dict())
        learner.optimizer.load_state_dict(restore_json_state(state["optimizer"]))
        learner.rng.bit_generator.state = copy.deepcopy(state["rng"])
        if learner.algorithm == "replay":
            learner.target.load_state_dict(CandidateNetwork.from_export(state["target"]).state_dict())
            learner.replay = PrioritizedReplay.from_state(restore_json_state(state["replay"]))
            if (learner.replay.capacity != config["replay_capacity"] or learner.replay.alpha != config["priority_alpha"]
                    or learner.replay.epsilon != config["priority_epsilon"]):
                raise ValueError("replay checkpoint configuration changed")
        elif state["target"] is not None or state["replay"] is not None:
            raise ValueError("PPO checkpoint unexpectedly contains replay state")
        for name in ("episodes_seen", "transitions_seen", "gradient_steps", "updates"):
            value = state[name]
            if type(value) is not int or value < 0:
                raise ValueError("invalid checkpoint counter")
            setattr(learner, name, value)
        return learner

    def load_state_dict(self, state):
        restored = self.from_state(state)
        if (restored.algorithm != self.algorithm or restored.model.candidate_dim != self.model.candidate_dim
                or restored.model.global_dim != self.model.global_dim):
            raise ValueError("checkpoint belongs to a different learner")
        self.__dict__.update(restored.__dict__)


def build_policy_state(learner):
    return learner.inference_state()
