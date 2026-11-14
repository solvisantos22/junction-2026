"""Permutation-equivariant candidate scoring with public set context only."""

from __future__ import annotations

import base64
from collections.abc import Mapping

import numpy as np
import torch
from torch import nn


def batch_observations(observations, candidate_dim, global_dim):
    """Pad candidate rows; presence and action validity have distinct meanings.

    An unavailable but observed candidate still contributes to set context.
    Artificial padding never contributes to either mean or maximum pooling.
    """
    if not observations:
        raise ValueError("an observation batch must be nonempty")
    checked = []
    for observation in observations:
        ids = observation["ids"]
        candidates = np.asarray(observation["candidates"], dtype=np.float32)
        context = np.asarray(observation["global"], dtype=np.float32)
        mask = np.asarray(observation["mask"])
        if (not ids or any(not isinstance(name, str) for name in ids)
                or len(set(ids)) != len(ids)
                or candidates.shape != (len(ids), candidate_dim)
                or context.shape != (global_dim,)
                or mask.shape != (len(ids),) or mask.dtype != np.bool_
                or not mask.any() or not np.isfinite(candidates).all()
                or not np.isfinite(context).all()):
            raise ValueError("invalid candidate observation or all actions masked")
        checked.append((candidates, context, mask))
    width = max(len(item[0]) for item in checked)
    rows = np.zeros((len(checked), width, candidate_dim), dtype=np.float32)
    present = np.zeros((len(checked), width), dtype=bool)
    valid = np.zeros_like(present)
    contexts = np.zeros((len(checked), global_dim), dtype=np.float32)
    for index, (candidates, context, mask) in enumerate(checked):
        size = len(candidates)
        rows[index, :size], contexts[index] = candidates, context
        present[index, :size], valid[index, :size] = True, mask
    return {"candidates": torch.from_numpy(rows), "global": torch.from_numpy(contexts),
            "present": torch.from_numpy(present), "mask": torch.from_numpy(valid)}


class CandidateNetwork(nn.Module):
    """Shared candidate encoder, mean/max context, action score and state value."""

    def __init__(self, candidate_dim, global_dim, hidden=64):
        super().__init__()
        if (type(candidate_dim) is not int or candidate_dim < 1
                or type(global_dim) is not int or global_dim < 0 or hidden != 64):
            raise ValueError("invalid feature dimensions or hidden width")
        self.candidate_dim, self.global_dim, self.hidden = candidate_dim, global_dim, hidden
        self.encoder = nn.Sequential(nn.Linear(candidate_dim, hidden), nn.Tanh(),
                                     nn.Linear(hidden, hidden), nn.Tanh())
        self.context = nn.Sequential(nn.Linear(2 * hidden + global_dim, hidden), nn.Tanh())
        self.score = nn.Sequential(nn.Linear(2 * hidden, hidden), nn.Tanh(), nn.Linear(hidden, 1))
        self.value = nn.Linear(hidden, 1)

    def forward(self, batch):
        encoded = self.encoder(batch["candidates"])
        presence = batch["present"].unsqueeze(-1)
        mean = (encoded * presence).sum(1) / presence.sum(1).clamp_min(1)
        maximum = encoded.masked_fill(~presence, torch.finfo(encoded.dtype).min).max(1).values
        context = self.context(torch.cat((mean, maximum, batch["global"]), dim=-1))
        expanded = context[:, None, :].expand(-1, encoded.shape[1], -1)
        scores = self.score(torch.cat((encoded, expanded), dim=-1)).squeeze(-1)
        scores = scores.masked_fill(~batch["mask"], torch.finfo(scores.dtype).min)
        return scores, self.value(context).squeeze(-1)

    def observations(self, observations):
        return self(batch_observations(observations, self.candidate_dim, self.global_dim))

    def export(self):
        return {"candidate_dim": self.candidate_dim, "global_dim": self.global_dim,
                "hidden": self.hidden,
                "weights": {name: tensor.detach().cpu().tolist()
                            for name, tensor in super().state_dict().items()}}

    @classmethod
    def from_export(cls, state):
        # Do not perturb process-global torch randomness just to load weights.
        with torch.random.fork_rng(devices=[]):
            model = cls(state["candidate_dim"], state["global_dim"], state["hidden"])
        model.load_state_dict({name: torch.tensor(value, dtype=torch.float32)
                               for name, value in state["weights"].items()}, strict=True)
        if not all(torch.isfinite(parameter).all() for parameter in model.parameters()):
            raise ValueError("nonfinite policy weights")
        return model


def json_state(value):
    """Encode optimizer tensors without pickle; retain dtype and integer keys."""
    if isinstance(value, torch.Tensor):
        return {"__tensor__": value.detach().cpu().tolist(), "dtype": str(value.dtype).split(".")[-1]}
    if isinstance(value, np.ndarray):
        array = np.ascontiguousarray(value)
        return {"__array__": base64.b64encode(array.tobytes()).decode("ascii"),
                "dtype": array.dtype.str, "shape": list(array.shape)}
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Mapping):
        return {"__mapping__": [[json_state(key), json_state(item)] for key, item in value.items()]}
    if isinstance(value, tuple):
        return {"__tuple__": [json_state(item) for item in value]}
    if isinstance(value, list):
        return [json_state(item) for item in value]
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    raise TypeError(f"unsupported checkpoint type: {type(value).__name__}")


def restore_json_state(value):
    if isinstance(value, dict):
        if "__array__" in value:
            dtype = np.dtype(value["dtype"])
            if dtype.kind not in "bifu" or dtype.itemsize > 8:
                raise ValueError("unsupported checkpoint array dtype")
            data = base64.b64decode(value["__array__"], validate=True)
            return np.frombuffer(data, dtype=dtype).reshape(value["shape"]).copy()
        if "__tensor__" in value:
            dtype = {"float32": torch.float32, "float64": torch.float64,
                     "int64": torch.int64, "int32": torch.int32}[value["dtype"]]
            return torch.tensor(value["__tensor__"], dtype=dtype)
        if "__mapping__" in value:
            return {restore_json_state(key): restore_json_state(item) for key, item in value["__mapping__"]}
        if "__tuple__" in value:
            return tuple(restore_json_state(item) for item in value["__tuple__"])
        raise ValueError("unrecognized checkpoint object")
    if isinstance(value, list):
        return [restore_json_state(item) for item in value]
    return value


# Short name for callers that prefer the architecture-neutral API.
Model = CandidateNetwork
