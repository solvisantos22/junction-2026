"""The ground changes: one unannounced change of the slip coefficients, mid-mission.

A proposal, not a rules decision. Everything else is the team's dynamic mission, unchanged:
this class only chooses when the change happens and what the ground is like afterwards, and
says so in rules(). The change itself is the `slip_change` factor of Manh's scenario sandbox
(`lightlag_dynamic.manh_controllers.scenarios`), which this module reads and does not edit.

What the agent is told (rules()["ground_change"]): that the ground changes exactly once, the
window of ticks it can happen in, the range each terrain's slip is drawn from afterwards, and
that nothing announces it. What it is not told: the tick, and the new values. Both show up in
telemetry, three ticks late like everything else: drives start covering less ground than the
wheels turned.

Standard library only.
"""

import random

from lightlag_dynamic.manh_controllers.scenarios import ScenarioEnvironment

# Published. The seed only picks values inside these.
CHANGE_WINDOW = (12, 30)                                   # ticks, inclusive
SLIP_AFTER = {"bedrock": (0.10, 0.25), "sand": (0.45, 0.70)}


def draw_change(seed):
    """The hidden part of a mission: when the ground changes and what it becomes."""
    rng = random.Random("lightlag-shift:{}".format(seed))
    tick = rng.randint(*CHANGE_WINDOW)
    after = {terrain: round(rng.uniform(low, high), 6) for terrain, (low, high) in sorted(SLIP_AFTER.items())}
    return tick, after


class ShiftEnvironment(ScenarioEnvironment):
    """A dynamic-profile episode whose slip coefficients change once at a hidden tick."""

    def __init__(self, seed=0, config=None, profile="rush_noisy", noise_level=1.0):
        super().__init__(seed=seed, config=config, profile=profile, noise_level=noise_level)
        if self._config.max_ticks <= CHANGE_WINDOW[1]:
            raise ValueError("the horizon must run past the change window ({}-{} ticks)".format(*CHANGE_WINDOW))
        tick, after = draw_change(seed)
        before = {terrain: self._slip[terrain] for terrain in after}
        self.shift = {"tick": tick, "slip_before": before, "slip_after": after}
        # The sandbox applies `delta` at `tick`; expressed this way the result is exactly `after`.
        self.factors["slip_change"] = {"tick": tick, "delta": {t: after[t] - before[t] for t in after}}

    def rules(self):
        rules = super().rules()
        rules.pop("slip_may_change", None)   # replaced by the fuller statement below
        rules["ground_change"] = {
            "happens": "exactly once per mission",
            "tick_window": list(CHANGE_WINDOW),
            "what_changes": "the slip coefficient of every terrain, from that tick on",
            "slip_after": {terrain: list(bounds) for terrain, bounds in SLIP_AFTER.items()},
            "announced": False,
            "how_it_shows": ("no event reports it; from that tick a drive covers less ground than its wheel "
                             "metres, which the position fixes and visual odometry in telemetry show"),
        }
        return rules

    def replay(self):
        replay = super().replay()
        replay["ground_change"] = dict(self.shift)   # evaluator-side: the hidden tick and values
        return replay
