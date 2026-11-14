"""Public greedy-prior residual logits over the frozen candidate network."""

from __future__ import annotations

import torch
from torch import nn

from lightlag_learning.environment import CANDIDATE_FEATURES, GLOBAL_FEATURES, greedy_choice
from lightlag_learning.models import CandidateNetwork, batch_observations


SCHEMA = "lightlag-hybrid-train-model-v1"
VARIANTS = ("prior", "plain")
GREEDY_MASS = 0.8


class PriorNetwork(nn.Module):
    """One effective-logit path for action sampling, PPO ratios, and entropy.

The public greedy action is computed before float32 feature conversion. It is
an extra batch index, never a new learned feature or simulator-state input.
Both variants retain every action allowed by the original observation mask.
"""

    def __init__(self, residual, variant):
        super().__init__()
        if variant not in VARIANTS:
            raise ValueError("variant must be prior or plain")
        if (residual.candidate_dim != len(CANDIDATE_FEATURES)
                or residual.global_dim != len(GLOBAL_FEATURES)):
            raise ValueError("feature dimensions differ from the frozen interface")
        self.residual = residual
        self.variant = variant
        self.candidate_dim = residual.candidate_dim
        self.global_dim = residual.global_dim
        self.hidden = residual.hidden

    def forward(self, batch):
        scores, values = self.residual(batch)
        mask = batch["mask"]
        # A uniform reference for plain PPO subtracts only a statewise constant.
        # Keeping it explicit makes both variants use exactly the same code.
        uniform = mask.to(scores.dtype) / mask.sum(1, keepdim=True)
        if self.variant == "prior":
            greedy = batch["greedy_actions"]
            if (greedy.dtype != torch.long or greedy.shape != (len(scores),)
                    or ((greedy < 0) | (greedy >= scores.shape[1])).any()
                    or not mask.gather(1, greedy[:, None]).all()):
                raise ValueError("invalid public greedy action index")
            prior = (1 - GREEDY_MASS) * uniform
            prior = prior.scatter_add(1, greedy[:, None],
                                      torch.full((len(scores), 1), GREEDY_MASS,
                                                 dtype=scores.dtype, device=scores.device))
        else:
            prior = uniform
        # Avoid log(0) even for masked actions, then restore the original mask.
        log_prior = torch.log(prior.clamp_min(torch.finfo(scores.dtype).tiny))
        effective = (scores + log_prior).masked_fill(~mask, torch.finfo(scores.dtype).min)
        return effective, values

    def observations(self, observations):
        batch = batch_observations(observations, self.candidate_dim, self.global_dim)
        for obs in observations:
            if obs["ids"][0] != "base" or not obs["mask"][0]:
                raise ValueError("frozen option interface requires legal base at index zero")
        batch["greedy_actions"] = torch.tensor(
            [greedy_choice(obs) for obs in observations], dtype=torch.long)
        return self(batch)

    def export(self):
        return {"schema": SCHEMA, "variant": self.variant, "greedy_mass": GREEDY_MASS,
                "residual": self.residual.export()}

    @classmethod
    def from_export(cls, state):
        if (set(state) != {"schema", "variant", "greedy_mass", "residual"}
                or state["schema"] != SCHEMA or state["greedy_mass"] != GREEDY_MASS):
            raise ValueError("unrecognized residual-prior model")
        return cls(CandidateNetwork.from_export(state["residual"]), state["variant"])
