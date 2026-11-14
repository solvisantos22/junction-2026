"""Target-level choices for the PPO + ICM agent on Lightlag Traverse: the agent picks the next target,
or home, and Kristján's frozen reference pilot does the rest.

    task = TargetTask(PublicTools(TraverseEnvironment(seed)))
    task.play(choose)          # choose(observation, mask) -> action number, once per choice

Why. A traverse mission is 420 ticks over a 600 m by 400 m height map with craters and a scarp.
Learning to steer every command around them, from one score at the end, is out of reach for this
learner. So here the agent decides what the reference's route planner decides: which target to
go for next, and when to go home. The pilot (lightlag_traverse/pilot.py, imported, never edited)
keeps everything else: its position filter, the slip and panel estimates, the cost-to-go fields
over the height grid, steering around crater walls, the signal delay, sampling on arrival, waiting
for the sun, its battery floor, and its last-resort turn for home when the time left only just
covers the way home. Only its beam-search route planner is replaced, by the agent.

When the agent chooses: at the start, when its target has been sampled (or dropped), when a new
target is discovered, and when a check every `check_every` ticks finds its target no longer fits.
A choice of home is final: the rover drives home and parks. When nothing fits any more the rover
goes home without asking.

Actions: one of `slots` candidate targets, or home (the last action).
Candidates: the open targets the rover can still visit and then get home from, nearest first,
judged by the pilot's own route model (RouteProblem: the cost-to-go fields, the battery, the sun
forecast, its floor and its margins, with the same settings the reference plans with). Slots
without such a target are masked, so the agent can never send the rover somewhere it cannot come
back from: the home guard of the flat maps, as a mask.

Observation (obs_dim numbers): GLOBAL numbers about the mission, then PER_SLOT numbers per slot:

    global    clock, battery, sun still to come (in tens of batteries), ticks and energy home, time left, value sampled
              and value still open (shares of all value known), how many targets fit, whether
              the panels are known yet and how good they are, the position uncertainty
    per slot  is there a target; ticks and energy to it; what a sample there is worth when the
              rover gets there, and its full value; slack to its deadline; ticks and energy from
              it home; time to spare after it and the way home; open value within 25 ticks of it;
              whether it was discovered during the mission; whether it is the current target

Reward: the official score cut into pieces that add up to raw_score / max_available_value: half of
each sample's credited value to the choice that was in force when it was taken, and at the last
choice the rest (plus the other half at base, minus it if the rover died).
"""

from dataclasses import dataclass

import numpy as np

from lightlag_traverse.pilot import Pilot
from lightlag_traverse.planning import INF, RouteProblem

GLOBAL, PER_SLOT = 12, 12
NEAR_TICKS = 25          # "nearby" for the open value around a candidate

# Worlds of this mode, claimed in TEAM_STATUS.md before any run, and the Traverse worlds that other
# work uses or keeps untouched (docs/modal-playbook.md, AGENTS.md): no training, tuning or selection there.
TRAIN_WORLDS = (410000, 419999)
DEV_WORLDS = (420000, 420063)
CHECK_WORLDS = (430000, 430299)
RESERVED = (
    (1, 99, "the Traverse owner's development"),
    (100, 499, "the farm's option search and selection"),
    (500, 523, "Manh's MAX pool and its six held-out evaluation worlds"),
    (600, 899, "the farm's comparisons"),
    (1000, 1199, "the Traverse owner's fresh checks"),
    (1200, 4999, "integrity-review probes, and 2026-2029: the task's and the campaign's worlds"),
    (71000, 72039, "Sölvi's first RL worlds"),
    (80000, 82039, "Sölvi's final learning campaign, its untouched final worlds included"),
    (99991, 99991, "the example world"),
)


def check_worlds(low, high):
    """Refuse a training or development range that touches worlds other work uses or keeps untouched."""
    for first, last, what in RESERVED:
        if low <= last and first <= high:
            raise ValueError(f"worlds {low}-{high} touch {first}-{last} ({what}); train on "
                             f"{TRAIN_WORLDS[0]}-{TRAIN_WORLDS[1]} and develop on {DEV_WORLDS[0]}-{DEV_WORLDS[1]}")


@dataclass(frozen=True)
class TargetConfig:
    slots: int = 12           # candidate targets the agent sees, nearest first
    check_every: int = 12     # ticks between checks that the current target still fits
    energy_margin: float = 0.15   # the mask prices every leg this much dearer in energy than the map says
    floor_margin: float = 4.0     # ... and keeps this much more battery than the pilot's own floor

    @property
    def n_actions(self):
        return self.slots + 1

    @property
    def home_action(self):
        return self.slots

    @property
    def obs_dim(self):
        return GLOBAL + PER_SLOT * self.slots

    @property
    def curiosity_inputs(self):
        return tuple(range(self.obs_dim))

    def to_dict(self):
        return {"mode": "targets", "slots": self.slots, "check_every": self.check_every,
                "energy_margin": self.energy_margin, "floor_margin": self.floor_margin}

    @classmethod
    def from_dict(cls, data):
        return cls(slots=int(data["slots"]), check_every=int(data.get("check_every", 12)),
                   energy_margin=float(data.get("energy_margin", 0.15)),
                   floor_margin=float(data.get("floor_margin", 4.0)))


def is_target_config(data):
    return isinstance(data, TargetConfig) or (isinstance(data, dict) and data.get("mode") == "targets")


class TargetPilot(Pilot):
    """The reference pilot with its route planner replaced by `choose(observation, mask)`."""

    def __init__(self, tools, choose, config=None):
        super().__init__(tools)                 # the reference's own options, unchanged
        self.choose = choose
        self.config = config or TargetConfig()
        self.going_home = False                 # the agent chose home: final
        self.out_of_reach = False               # nothing fitted when last asked
        self.known = len(self.targets)
        self.checked = -999
        self.decisions = []                     # one entry per choice: tick, obs, mask, action, target

    # ---- when to ask ------------------------------------------------------------------------
    def _decide(self, tick, x, y, sigma, battery):
        self.route = [t for t in self.route if t not in self.sampled and t not in self.pending]
        if self.going_home:
            self.route = []
        elif self._needs_choice(tick, x, y, battery):
            self._choose(tick, x, y, sigma, battery)
        self.need_plan = False                  # the beam search never runs: the agent's choice is the route
        self.last_plan = tick
        return super()._decide(tick, x, y, sigma, battery)

    def _needs_choice(self, tick, x, y, battery):
        discovered = len(self.targets) > self.known
        if self.out_of_reach and not discovered:
            return False
        if not self.route or discovered:
            return True
        if tick - self.checked >= self.config.check_every:
            self.checked = tick
            problem, ids = self._problem(tick, x, y, battery, only=self.route[:1])
            return problem is None or problem.score([0])[0] < 0
        return False

    # ---- the choice -------------------------------------------------------------------------
    def _problem(self, tick, x, y, battery, only=None):
        """The pilot's own route model over the open targets (or `only` these), built as in Pilot._plan
        but with the guard's margins: every leg dearer in energy by energy_margin, and floor_margin
        more battery kept."""
        open_ids = [t for t in (only if only is not None else self._open(tick)) if self.nodes.get(t) is not None]
        if not open_ids:
            return None, []
        nodes = [self.nodes[t] for t in open_ids]
        start = [self._to(t, x, y) for t in open_ids]
        fields = [self.fields[t] for t in open_ids]
        dear = 1.0 + self.config.energy_margin
        ticks = [[fields[b].ticks[nodes[a]] for b in range(len(open_ids))] for a in range(len(open_ids))]
        energy = [[fields[b].energy[nodes[a]] * dear for b in range(len(open_ids))] for a in range(len(open_ids))]
        base = self.fields["base"]
        home_now = self._to("base", x, y)
        problem = RouteProblem(
            self.sun, float(tick), battery,
            [self.targets[t]["value"] for t in open_ids], [self.targets[t]["deadline_tick"] for t in open_ids],
            self.rules["sample_windows"]["late_fraction"],
            [s[0] for s in start], [s[1] * dear for s in start], ticks, energy,
            [base.ticks[n] * self.opt["home_slack"] for n in nodes], [base.energy[n] * dear for n in nodes],
            (home_now[0] * self.opt["home_slack"], home_now[1] * dear), self.rules["sample_cost"],
            stop_ticks=self.opt["stop_ticks"],
            home_margin=int(self.opt["home_margin"]), deadline_margin=self.opt["deadline_margin"],
            floor=self.opt["floor"] + 1.0 + self.config.floor_margin, slack=self.opt["leg_slack"])
        return problem, open_ids

    def _choose(self, tick, x, y, sigma, battery):
        self.known = len(self.targets)
        self.checked = tick
        problem, open_ids = self._problem(tick, x, y, battery)
        left = self.horizon - tick
        home_ticks, _ = self._to("base", x, y)
        candidates = []
        if home_ticks * self.opt["home_slack"] + self.opt["home_margin"] < left:   # else the pilot heads home anyway
            for i in range(len(open_ids)):
                value, finish = problem.score([i])
                there, _ = self._to(open_ids[i], x, y)
                back = self.fields["base"].ticks[self.nodes[open_ids[i]]]
                # the pilot's own test of a target (Pilot._decide), so that it never drops a chosen one at once
                fits = there + 1.0 + back * self.opt["home_slack"] + self.opt["home_margin"] <= left
                if value >= 0 and fits:
                    candidates.append((problem.start_t[i], i, finish))
        candidates.sort()
        candidates = candidates[:self.config.slots]
        if not candidates:
            self.route, self.out_of_reach = [], True
            return
        self.out_of_reach = False
        obs, mask = self._observe(tick, x, y, sigma, battery, problem, open_ids, candidates)
        action = int(self.choose(obs, mask))
        if not 0 <= action < self.config.n_actions or not mask[action]:
            raise ValueError(f"the agent chose action {action}, which is masked")
        chosen = None if action == self.config.home_action else open_ids[candidates[action][1]]
        self.decisions.append({"tick": tick, "obs": obs, "mask": mask, "action": action, "target": chosen})
        if chosen is None:
            self.going_home, self.route = True, []
        else:
            self.route = [chosen]

    def _observe(self, tick, x, y, sigma, battery, problem, open_ids, candidates):
        cfg = self.config
        horizon, capacity = float(self.horizon), float(self.capacity)
        values = [t["value"] for t in self.targets.values()]
        top = max(values) if values else 1.0
        known = sum(values) or 1.0
        sampled = sum(self.targets[t]["value"] for t in self.sampled if t in self.targets)
        still = sum(problem.values)
        home_t, home_e = self._to("base", x, y)
        low, high = self.rules["solar_efficiency_range"]
        current = self.route[0] if self.route else None
        g = [tick / horizon, battery / capacity, self.sun.gained(tick, horizon) / (10.0 * capacity),
             min(home_t, 999.0) / 100.0, min(home_e, 999.0) / capacity, (horizon - tick) / horizon,
             sampled / known, still / known, len(candidates) / cfg.slots, float(self.efficiency_known),
             (self.efficiency - low) / max(1e-9, high - low), min(sigma, 10.0) / 3.0]
        slots = np.zeros((cfg.slots, PER_SLOT))
        for k, (_, i, finish) in enumerate(candidates):
            target = self.targets[open_ids[i]]
            visit = problem.visit(problem.now, problem.battery, -1, i)
            done, credited = (visit[0], visit[2]) if visit is not None else (problem.now + problem.start_t[i], 0.0)
            deadline = target["deadline_tick"]
            slack = 2.0 if deadline is None else max(-1.0, min(2.0, (deadline - done) / 100.0))
            nearby = sum(problem.values[j] for j in range(problem.count)
                         if j != i and problem.t[i][j] <= NEAR_TICKS)
            slots[k] = [1.0, problem.start_t[i] / 100.0, problem.start_e[i] / capacity, credited / top,
                        problem.values[i] / top, slack, problem.home_t[i] / 100.0, problem.home_e[i] / capacity,
                        (problem.limit - finish) / 100.0, nearby / (4.0 * top),
                        float(target.get("appear_tick", 0) > 0), float(open_ids[i] == current)]
        obs = np.clip(np.concatenate([np.asarray(g), slots.ravel()]), -5.0, 5.0).astype(np.float32)
        mask = np.zeros(cfg.n_actions, dtype=bool)
        mask[:len(candidates)] = True
        mask[cfg.home_action] = True
        return obs, mask


class TargetTask:
    """One traverse mission (or a whole campaign) played by an agent that picks targets."""

    def __init__(self, tools, config=None):
        self.tools = tools
        self.config = config or TargetConfig()
        self.pilots = []

    def play(self, choose):
        """Every mission until the episode (or the campaign) is complete."""
        while True:
            pilot = TargetPilot(self.tools, choose, self.config)
            self.pilots.append(pilot)
            while True:
                pilot.act()
                out = self.tools.advance(1)
                pilot.observe(out["packets"], out["current_tick"])
                if out["episode_complete"]:
                    break
            if out.get("campaign_complete", True):
                return

    @property
    def decisions(self):
        return [d for pilot in self.pilots for d in pilot.decisions]

    def rewards(self, result):
        """Per-choice rewards of one mission that add up to raw_score / max_available_value."""
        decisions = self.decisions
        total = float(result["max_available_value"]) or 1.0
        rewards = np.zeros(len(decisions))
        if not decisions:
            return rewards
        ticks = [d["tick"] for d in decisions]
        earned = 0.0
        for sample in result.get("samples", []):
            credited = float(sample["credited_value"])
            earned += credited
            index = max(0, int(np.searchsorted(ticks, sample["tick"], side="right")) - 1)
            rewards[index] += 0.5 * credited / total
        if not result["alive"]:
            rewards[-1] -= 0.5 * earned / total
        elif result["at_base"]:
            rewards[-1] += 0.5 * earned / total
        return rewards
