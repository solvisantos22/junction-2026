"""Frozen-policy goal selection; observations and the navigator stay unchanged.

Scores from different networks are never compared in raw units. Ensembles use
mean tied percentile ranks on the original legal candidate set. A shortlist is
applied only after inference, preserving the networks' candidate-set context.
"""

from __future__ import annotations

from copy import deepcopy
import math

import numpy as np
import torch

from lightlag_learning.environment import CANDIDATE_FEATURES, GLOBAL_FEATURES, greedy_choice
from lightlag_learning.models import CandidateNetwork, batch_observations


SCHEMA = "learning-hybrid-spec-v1"
RHOS = (0.0, 0.5, 0.75, 0.9, 0.95, 1.0)
GREEDY_WEIGHTS = (0.25, 0.5, 0.75)
TRAINING_SEEDS = (17, 29, 43)
FEATURE_CREDIT = CANDIDATE_FEATURES.index("charge_aware_credit")
FEATURE_DURATION = CANDIDATE_FEATURES.index("visit_duration_with_charge")


def _label(value):
    return f"{round(100 * value):03d}"


def build_specs(parent_freeze):
    """Return the predeclared 65 arms, using every latest retained training seed.

Single-network arms share an algorithm/rho group across all three seeds. This
is the unit of selection, so callers must not select the best individual seed.
The replay seed-43 last checkpoint may also carry the matched2048 role.
"""
    arms = parent_freeze["arms"]
    if len({arm["id"] for arm in arms}) != len(arms):
        raise ValueError("duplicate parent arm id")
    latest = [arm for arm in arms
              if arm["kind"] == "policy" and "last" in arm.get("roles", [])]
    expected = {(algorithm, seed) for algorithm in ("ppo", "replay")
                for seed in TRAINING_SEEDS}
    keys = [(arm["algorithm"], arm["training_seed"]) for arm in latest]
    if len(keys) != 6 or set(keys) != expected:
        raise ValueError("require exactly three latest PPO and replay seeds")
    by_key = dict(zip(keys, latest))
    pools = {algorithm: [by_key[algorithm, seed]["id"] for seed in TRAINING_SEEDS]
             for algorithm in ("ppo", "replay")}
    pools["all"] = pools["ppo"] + pools["replay"]
    specs = []

    def add(identifier, kind, family, group, pool=None, members=(), rho=0.0,
            greedy_weight=0.0, training_seed=None):
        spec = {"schema": SCHEMA, "id": identifier, "kind": kind,
                "family": family, "group": group, "pool": pool,
                "members": list(members), "rho": rho,
                "greedy_weight": greedy_weight, "training_seed": training_seed}
        validate_spec(spec)
        specs.append(spec)

    for name in ("greedy", "beam"):
        add(name, name, "control", name)
    for algorithm in ("ppo", "replay"):
        for seed in TRAINING_SEEDS:
            for rho in RHOS:
                group = f"single-{algorithm}-rho{_label(rho)}"
                add(f"single-{algorithm}-{seed}-rho{_label(rho)}", "single",
                    "single_shortlist", group, algorithm,
                    [by_key[algorithm, seed]["id"]], rho, training_seed=seed)
    for pool, members in pools.items():
        for rho in RHOS:
            identifier = f"ensemble-{pool}-rho{_label(rho)}"
            add(identifier, "ensemble", "rank_ensemble", identifier, pool, members, rho)
    for pool, members in pools.items():
        for weight in GREEDY_WEIGHTS:
            identifier = f"blend-{pool}-greedy{_label(weight)}"
            add(identifier, "blend", "rank_blend", identifier, pool, members,
                greedy_weight=weight)
    return specs


def validate_spec(spec, policies=None):
    """Validate structural rules; a frozen manifest separately binds the grid."""
    expected_fields = {"schema", "id", "kind", "family", "group", "pool",
                       "members", "rho", "greedy_weight", "training_seed"}
    if set(spec) != expected_fields or spec["schema"] != SCHEMA:
        raise ValueError("unrecognized hybrid spec")
    if not all(isinstance(spec[key], str) and spec[key] for key in ("id", "group")):
        raise ValueError("invalid spec identity")
    kind, members = spec["kind"], spec["members"]
    families = {"single": "single_shortlist", "ensemble": "rank_ensemble",
                "blend": "rank_blend", "greedy": "control", "beam": "control"}
    if kind not in families or spec["family"] != families[kind]:
        raise ValueError("invalid kind/family")
    if (not isinstance(members, list) or any(not isinstance(m, str) for m in members)
            or len(set(members)) != len(members)):
        raise ValueError("invalid policy members")
    for key in ("rho", "greedy_weight"):
        if (type(spec[key]) not in (float, int) or not math.isfinite(spec[key])
                or not 0 <= spec[key] <= 1):
            raise ValueError(f"invalid {key}")
    control = kind in ("greedy", "beam")
    if control:
        if (members or spec["pool"] is not None or spec["rho"] != 0
                or spec["greedy_weight"] != 0 or spec["training_seed"] is not None):
            raise ValueError("controls cannot contain a learned selection rule")
    else:
        pool = spec["pool"]
        if pool not in ("ppo", "replay", "all"):
            raise ValueError("invalid policy pool")
        if kind == "single":
            if len(members) != 1 or pool == "all" or spec["training_seed"] not in TRAINING_SEEDS:
                raise ValueError("invalid single-policy membership")
        elif (len(members) != (6 if pool == "all" else 3)
              or spec["training_seed"] is not None):
            raise ValueError("invalid ensemble membership")
        if kind != "blend" and spec["greedy_weight"] != 0:
            raise ValueError("only blends may set greedy_weight")
        if kind == "blend" and spec["rho"] != 0:
            raise ValueError("blends do not also shortlist")
    if policies is not None:
        for member in members:
            if member not in policies:
                raise ValueError(f"missing policy: {member}")
            state = policies[member]
            if (state.get("schema") != "lightlag-learning-policy-v1"
                    or state.get("algorithm") not in ("ppo", "replay")
                    or (spec["pool"] != "all" and state["algorithm"] != spec["pool"])):
                raise ValueError("unrecognized policy or pool mismatch")
            if (state["model"]["candidate_dim"] != len(CANDIDATE_FEATURES)
                    or state["model"]["global_dim"] != len(GLOBAL_FEATURES)):
                raise ValueError("policy feature dimensions differ from frozen interface")
    return None


def legal_ranks(values, mask):
    """Mean tied zero-based rank/(n-1); sole legal action is 1, all ties .5.

Only legal entries participate. Illegal entries are NaN internally and become
JSON null in retained diagnostics. Exact score ties receive equal ranks.
"""
    values, mask = np.asarray(values, dtype=float), np.asarray(mask)
    if (values.ndim != 1 or mask.shape != values.shape or mask.dtype != np.bool_
            or not mask.any() or not np.isfinite(values[mask]).all()):
        raise ValueError("invalid rank inputs")
    indices = np.flatnonzero(mask)
    result = np.full(len(values), np.nan)
    if len(indices) == 1:
        result[indices[0]] = 1.0
        return result
    ordered = indices[np.argsort(values[indices], kind="stable")]
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and values[ordered[end]] == values[ordered[start]]:
            end += 1
        result[ordered[start:end]] = (start + end - 1) / (2 * (len(ordered) - 1))
        start = end
    return result


def _json_vector(values, mask):
    return [float(value) if legal else None for value, legal in zip(values, mask)]


class HybridChooser:
    """Inference-only public observation callback with retained decision traces."""

    def __init__(self, spec, policies):
        validate_spec(spec, policies)
        if spec["kind"] == "beam":
            raise ValueError("beam uses the unchanged reference runner, not an option chooser")
        self.spec = deepcopy(spec)
        self.models = {member: CandidateNetwork.from_export(policies[member]["model"]).eval()
                       for member in spec["members"]}
        self.diagnostics = []

    def __call__(self, obs):
        # Validate even greedy-only calls; this consumes public data only.
        batch = batch_observations([obs], len(CANDIDATE_FEATURES), len(GLOBAL_FEATURES))
        if obs["ids"][0] != "base" or not obs["mask"][0]:
            raise ValueError("frozen option interface requires legal base at index zero")
        mask = np.asarray(obs["mask"], dtype=bool)
        rows = np.asarray(obs["candidates"], dtype=float)
        science = mask & np.array([name != "base" for name in obs["ids"]])
        density = np.zeros(len(mask))
        density[science] = rows[science, FEATURE_CREDIT] / np.maximum(
            rows[science, FEATURE_DURATION], 1 / 420)
        if (density[science] < 0).any():
            raise ValueError("credited science density must be nonnegative")
        best_density = float(density[science].max()) if science.any() else 0.0
        greedy = greedy_choice(obs)
        # The stock greedy prefers every feasible science goal to base, including
        # zero-credit ties. A strict lower base score preserves that ordering.
        greedy_values = density.copy()
        greedy_values[0] = -1.0
        greedy_ranks = legal_ranks(greedy_values, mask)
        eligible = mask.copy()
        if self.spec["rho"] > 0 and science.any():
            eligible[science] = density[science] >= self.spec["rho"] * best_density
        scores, ranks = {}, {}
        with torch.inference_mode():
            for member, model in self.models.items():
                raw, _ = model(batch)
                scores[member] = raw[0].cpu().numpy().astype(float)
                ranks[member] = legal_ranks(scores[member], mask)
        if scores:
            learned = np.mean(list(ranks.values()), axis=0)
            combined = learned.copy()
            if self.spec["kind"] == "blend":
                weight = self.spec["greedy_weight"]
                combined = (1 - weight) * learned + weight * greedy_ranks
            # Ranks preserve a single model's argmax and first-index tie rule.
            action = int(np.argmax(np.where(eligible, combined, -np.inf)))
        else:
            learned = np.full(len(mask), np.nan)
            combined = greedy_ranks.copy()
            action = int(greedy)
        ratio = (float(density[action] / best_density)
                 if science[action] and best_density > 0 else None)
        self.diagnostics.append({
            "tick": int(obs["tick"]), "ids": list(obs["ids"]), "mask": mask.tolist(),
            "greedy_action": int(greedy), "action": action, "eligible": eligible.tolist(),
            "greedy_density": _json_vector(density, mask),
            "member_scores": {m: _json_vector(values, mask) for m, values in scores.items()},
            "member_ranks": {m: _json_vector(values, mask) for m, values in ranks.items()},
            "learned_rank": (_json_vector(learned, mask) if scores else [None] * len(mask)),
            "greedy_rank": _json_vector(greedy_ranks, mask),
            "combined_score": _json_vector(combined, mask), "chosen_density_ratio": ratio,
        })
        return action


def make_chooser(spec, policies):
    return HybridChooser(spec, policies)
