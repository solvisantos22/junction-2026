"""A rule changes: one of four published changes happens once, and nothing says which.

The second step after `ShiftEnvironment`, where only the ground changes. Here the agent is
told the whole menu and has to work out from telemetry which entry happened, because each
one calls for a different response:

    ground    the slip of every terrain changes         -> re-measure slip, re-budget the way home
    turning   turning starts to cost energy             -> plan straighter routes, re-budget
    link      telemetry packets start getting lost      -> act on older and fewer fixes
    relay     uplinks only go out during relay passes   -> send earlier, queue across the gap

Every change is an existing factor of Manh's scenario sandbox
(`lightlag_dynamic.manh_controllers.scenarios`, read only), switched on at a hidden tick.
`rules()` publishes the menu with its ranges and never changes afterwards, so asking again
does not reveal which change happened. A proposal, not a rules decision. Standard library only.
"""

import random

from lightlag_dynamic.manh_controllers.scenarios import ScenarioEnvironment

from .environment import CHANGE_WINDOW, SLIP_AFTER

# Published. The seed only picks one entry and values inside its ranges.
TURN_COST = (0.02, 0.04)        # energy per degree of heading change, times the drive cost
PACKET_LOSS = (0.25, 0.45)      # probability that a telemetry packet never arrives
RELAY = (8, 4)                  # relay overhead for the first 4 ticks of every 8, counted from tick 0
KINDS = ("ground", "turning", "link", "relay")


def draw_rule_change(seed, kind=None):
    """The hidden part of a mission. `kind` forces one entry of the menu, for studies only."""
    rng = random.Random("lightlag-rule-change:{}".format(seed))
    drawn = rng.choice(KINDS)
    change = {"kind": kind or drawn, "tick": rng.randint(*CHANGE_WINDOW)}
    # every value is drawn whatever the kind, so forcing a kind does not move the others
    slip_after = {terrain: round(rng.uniform(low, high), 6) for terrain, (low, high) in sorted(SLIP_AFTER.items())}
    turn_cost = round(rng.uniform(*TURN_COST), 6)
    loss = round(rng.uniform(*PACKET_LOSS), 6)
    if change["kind"] == "ground":
        change["slip_after"] = slip_after
    elif change["kind"] == "turning":
        change["energy_per_degree"] = turn_cost
    elif change["kind"] == "link":
        change["loss_probability"] = loss
    elif change["kind"] == "relay":
        change["period_ticks"], change["open_ticks"] = RELAY
    else:
        raise ValueError("unknown kind {!r}; use one of {}".format(kind, ", ".join(KINDS)))
    return change


class RuleChangeEnvironment(ScenarioEnvironment):
    """A dynamic-profile episode in which one published rule change happens at a hidden tick."""

    def __init__(self, seed=0, config=None, profile="rush_noisy", noise_level=1.0, kind=None):
        super().__init__(seed=seed, config=config, profile=profile, noise_level=noise_level)
        self._public = set(super().rules())          # what the tools say before anything changes
        self.change = draw_rule_change(seed, kind)
        self._changed = False
        if self.change["kind"] == "ground":
            # the sandbox applies this itself at the tick; expressed as a delta from today's ground
            after = self.change["slip_after"]
            self.factors["slip_change"] = {"tick": self.change["tick"],
                                           "delta": {t: after[t] - self._slip[t] for t in after}}

    def _step(self):
        if not self._changed and self._tick + 1 == self.change["tick"]:
            self._changed = True
            kind = self.change["kind"]
            if kind == "turning":
                self.factors["turn_cost"] = self.change["energy_per_degree"]
            elif kind == "link":
                self.factors["packet_loss"] = {"p": self.change["loss_probability"]}
            elif kind == "relay":
                self.factors["windows"] = (self.change["period_ticks"], self.change["open_ticks"])
        super()._step()

    def rules(self):
        # The sandbox adds a rules entry for each active factor. Those are dropped here: the
        # menu below is all the agent is told, before and after the change.
        rules = {key: value for key, value in super().rules().items() if key in self._public}
        rules["rule_change"] = {
            "happens": "exactly once per mission: one entry of `one_of`, from some tick in `tick_window` to the end",
            "tick_window": list(CHANGE_WINDOW),
            "announced": False,
            "this_entry": "never changes; no tool says which change happened or when",
            "one_of": {
                "ground": {
                    "what": "the slip coefficient of every terrain changes",
                    "slip_after": {terrain: list(bounds) for terrain, bounds in SLIP_AFTER.items()},
                    "shows_as": "a drive covers less ground than its wheel metres",
                },
                "turning": {
                    "what": ("turning costs energy: degrees of heading change at the start of a drive, times "
                             "`energy_per_degree`, times the drive cost per metre (doubled when starting on sand)"),
                    "energy_per_degree": list(TURN_COST),
                    "shows_as": "the battery falls faster than idle, drive and sample costs explain",
                },
                "link": {
                    "what": "each telemetry packet is lost with a fixed probability; a lost packet never arrives",
                    "loss_probability": list(PACKET_LOSS),
                    "shows_as": "ticks missing from the telemetry you receive",
                },
                "relay": {
                    "what": ("uplinks are transmitted only while a relay is overhead: the first `open_ticks` of every "
                             "`period_ticks`, counted from tick 0; one sent outside a pass waits for the next"),
                    "period_ticks": RELAY[0], "open_ticks": RELAY[1],
                    "shows_as": "an uplink acknowledgement whose transmit_tick is later than the tick it was sent",
                },
            },
        }
        return rules

    def replay(self):
        replay = super().replay()
        replay["rule_change"] = dict(self.change)    # evaluator-side: which change, when, how strong
        return replay
