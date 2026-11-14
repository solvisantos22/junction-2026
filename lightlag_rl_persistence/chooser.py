"""Retain an available science goal without changing the frozen navigator."""

from numbers import Integral

import numpy as np


class GoalChooser:
    """Wrap a frozen chooser and record proposals separately from held intentions.

    The underlying chooser runs at every ordinary planner invocation, including
    when its proposal will be overridden. Only non-base IDs can be held; a held
    ID is released when it disappears from the unchanged public candidate list.
    A new instance is required per episode. Navigation, sampling, safety and
    mission termination remain the original runner's responsibility.

    Records describe planner intentions, not commands actually executed. The
    navigator may still force home or wait despite a retained science goal.
    """

    def __init__(self, choose, persistent: bool):
        if not callable(choose):
            raise TypeError("choose must be callable")
        if type(persistent) is not bool:
            raise TypeError("persistent must be a bool")
        self.choose = choose
        self.persistent = persistent
        self.held_goal = None
        self.decisions = []

    def __call__(self, ids, features) -> int:
        ids = tuple(ids)
        # Retain an independent trace and protect the caller's candidate array.
        # No policy weights, navigator or simulator objects enter this wrapper.
        snapshot = np.array(features, dtype=float, copy=True)
        proposed = self.choose(ids, snapshot.copy())
        if (isinstance(proposed, bool) or not isinstance(proposed, Integral)
                or not 0 <= int(proposed) < len(ids)):
            raise ValueError("chooser must return a valid integer candidate index")
        proposed = int(proposed)
        prior = self.held_goal
        if not self.persistent:
            action, reason = proposed, "pass_through"
        elif prior is not None and prior in ids:
            action, reason = ids.index(prior), "retain"
        else:
            action = proposed
            if prior is not None:
                reason = "release_missing"
            else:
                reason = "unheld_select" if self.decisions else "initial_select"
        self.held_goal = ids[action] if self.persistent and ids[action] != "base" else None
        self.decisions.append({
            "ids": list(ids), "features": snapshot.tolist(),
            "proposed_action": proposed, "action": action,
            "prior_goal": prior, "held_goal": self.held_goal, "reason": reason,
        })
        return action
