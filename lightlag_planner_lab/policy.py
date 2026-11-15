"""Public-data strategies and forecasts, selected once after a common prefix."""

import math

from lightlag_traverse.pilot import DEFAULTS, Pilot as ReferencePilot
from lightlag_traverse.planning import RouteProblem, plan_route
from lightlag_learned_portfolio.policy import features as previous_features

SWITCH_TICK = 70
AGGRESSIVE = dict(floor=2., home_floor=.5, home_margin=1., home_slack=1., deadline_margin=0)
BALANCED = dict(energy_weight=.5, home_margin=2., floor=3.5)
PROFILES = {
    "baseline": {},
    "refresh": {"options": {}},
    "aggressive_early": {"options": AGGRESSIVE},
    "aggressive_late": {"options": AGGRESSIVE, "activate": 140},
    "balanced_early": {"options": BALANCED},
    "energy_strong": {"options": dict(energy_weight=1., home_margin=2., floor=3.5)},
    "deadline_push": {"options": dict(deadline_margin=0, leg_slack=.95)},
    "fast_guarded": {"options": dict(leg_slack=.9, deadline_margin=0), "guard": True},
    "aggressive_guarded": {"options": AGGRESSIVE, "guard": True},
    "aggressive_safe300": {"options": AGGRESSIVE, "reset": 300},
    "aggressive_safe340": {"options": AGGRESSIVE, "reset": 340},
    "deadline_focus": {"options": {}, "late_fraction": 0.},
    "late_value_optimist": {"options": {}, "late_fraction": .5},
    "arrival_wide": {"options": dict(arrive_m=1.5)},
    "energy_conservative": {"options": dict(energy_weight=.5, floor=8., home_slack=1.15)},
    "multistart": {"options": {}, "searches": 2},
}
PROFILE_NAMES = tuple(PROFILES)


def descriptors():
    """Known strategy parameters for the pooled model; no outcome information."""
    keys = ("energy_weight", "floor", "home_floor", "home_margin", "home_slack",
            "deadline_margin", "leg_slack", "arrive_m")
    rows = []
    for name in PROFILE_NAMES[1:]:
        spec = PROFILES[name]; opt = dict(DEFAULTS, **spec.get("options", {}))
        rows.append([float(opt[k]) for k in keys] +
                    [float(spec.get("guard", False)), spec.get("activate", 70)/420.,
                     spec.get("reset", 0)/420., spec.get("late_fraction", .25),
                     float(spec.get("searches", 1))])
    return rows


def problem_for(p, tick, x, y, battery, late_fraction=None):
    """Construct the original pilot's route model from its public-data belief."""
    ids = p._open(tick); nodes = [p.nodes[t] for t in ids]
    start = [p._to(t, x, y) for t in ids]; fields = [p.fields[t] for t in ids]
    home = p._to("base", x, y); base = p.fields["base"]
    problem = RouteProblem(
        p.sun, float(tick), battery, [p.targets[t]["value"] for t in ids],
        [p.targets[t]["deadline_tick"] for t in ids],
        p.rules["sample_windows"]["late_fraction"] if late_fraction is None else late_fraction,
        [s[0] for s in start], [s[1] for s in start],
        [[fields[b].ticks[nodes[a]] for b in range(len(ids))] for a in range(len(ids))],
        [[fields[b].energy[nodes[a]] for b in range(len(ids))] for a in range(len(ids))],
        [base.ticks[n]*p.opt["home_slack"] for n in nodes], [base.energy[n] for n in nodes],
        (home[0]*p.opt["home_slack"], home[1]), p.rules["sample_cost"],
        stop_ticks=p.opt["stop_ticks"], home_margin=int(p.opt["home_margin"]),
        deadline_margin=p.opt["deadline_margin"], floor=p.opt["floor"]+1., slack=p.opt["leg_slack"])
    return ids, problem


def return_forecast(p, tick, x, y, battery):
    """Conservative uniform-rate return estimate; an estimate, not a guarantee."""
    dt, energy = p._to("base", x, y)
    if not math.isfinite(dt) or dt > p.horizon:
        return -1000., -1000., 1000
    duration = max(1, int(math.ceil(dt*1.12)))
    b = low = battery
    for offset in range(1, duration+1):
        b = min(p.capacity, b+p.sun.rate[min(tick+offset, p.horizon)])
        b -= p.sun.idle + energy*1.10/duration
        low = min(low, b)
    return b, low, duration


def features(p):
    f = previous_features(p)
    tick = max(p.now+p.delay+1, p.reserved_until+1)
    x, y, _, battery = p.predict(tick)
    end, low, duration = return_forecast(p, tick, x, y, battery)
    ids, problem = problem_for(p, tick, x, y, battery)
    order = [ids.index(t) for t in p.route if t in ids]
    value, finish = problem.score(order)
    t, b, last, minimum = problem.now, problem.battery, -1, battery
    first_b, first_slack, deadlines = battery, 0., 0
    for i, site in enumerate(order):
        visited = problem.visit(t, b, last, site)
        if visited is None: break
        t, b, _ = visited; minimum = min(minimum, b)
        if i == 0: first_b, first_slack = b, problem.deadlines[site]-t
        deadlines += int(t <= problem.deadlines[site]); last = site
    home_tick = problem.home(t, b, last)
    bounded = lambda v, scale: max(-10., min(10., v/scale)) if math.isfinite(v) else 10.
    f.update({
        "forecast_home_end": bounded(end, p.capacity),
        "forecast_home_min": bounded(low, p.capacity),
        "forecast_home_ticks": bounded(duration, p.horizon),
        "solar_remaining": bounded(p.sun.gained(tick, p.horizon), p.capacity),
        "route_model_value": bounded(value, 300.),
        "route_model_finish": bounded(finish, p.horizon),
        "route_model_feasible": float(value >= 0),
        "route_min_battery": bounded(minimum, p.capacity),
        "route_deadline_fraction": deadlines/max(1, len(order)),
        "next_battery": bounded(first_b, p.capacity),
        "next_slack": bounded(first_slack, 100.),
        "route_home_margin": bounded(p.horizon-(home_tick if home_tick is not None else 1000), p.horizon),
    })
    assert len(f) == 61 and all(math.isfinite(v) for v in f.values())
    return f


class Pilot(ReferencePilot):
    def __init__(self, tools, options=None):
        super().__init__(tools, options)
        self.initial_options = dict(self.opt)
        self.profile = "baseline"
        self.strategy = {}
        self.activated = self.reset_done = self.retreat = False
        self.events = []

    def configure(self, name):
        if name not in PROFILES: raise ValueError("unknown strategy")
        self.profile, self.strategy = name, PROFILES[name]

    def before_step(self):
        if not self.strategy: return
        if not self.activated and self.now >= self.strategy.get("activate", SWITCH_TICK):
            old = self.opt["energy_weight"]
            self.opt = dict(self.initial_options, **self.strategy.get("options", {}))
            self.activated = True
            if old != self.opt["energy_weight"]:
                self.ground.energy_weight = self.opt["energy_weight"]; self._rebuild()
            self.need_plan = self.full_plan = True
            self.events.append({"tick": self.now, "kind": "activate", "profile": self.profile})
        if self.activated and not self.reset_done and self.now >= self.strategy.get("reset", 10000):
            old = self.opt["energy_weight"]; self.opt = dict(self.initial_options)
            self.reset_done = True
            if old != self.opt["energy_weight"]:
                self.ground.energy_weight = self.opt["energy_weight"]; self._rebuild()
            self.need_plan = self.full_plan = True
            self.events.append({"tick": self.now, "kind": "reset_to_reference"})

    def _plan(self, tick, x, y, battery, steps):
        if self.retreat:
            self.route = []; self.need_plan = False; self.last_plan = tick; return
        special = self.activated and not self.reset_done and (
            "late_fraction" in self.strategy or self.strategy.get("searches", 1) > 1)
        if not special: return super()._plan(tick, x, y, battery, steps)
        ids, problem = problem_for(self, tick, x, y, battery, self.strategy.get("late_fraction"))
        if not ids:
            self.route = []
        else:
            order = [ids.index(t) for t in self.route if t in ids]
            beam = self.opt["beam"] if steps >= self.opt["plan_steps"] else self.opt["rebeam"]
            best = None
            for _ in range(self.strategy.get("searches", 1)):
                candidate, _ = plan_route(problem, steps, order, self.rng, beam=beam)
                value, finish = problem.score(candidate)
                merit = value-1e-4*finish if value >= 0 else -1.
                if best is None or merit > best[0]: best = (merit, candidate)
                order = best[1]
            self.route = [ids[i] for i in best[1]]
        self.need_plan = False; self.last_plan = tick

    def _decide(self, tick, x, y, sigma, battery):
        if self.activated and self.strategy.get("guard") and not self.retreat:
            end, low, duration = return_forecast(self, tick, x, y, battery)
            if low < 6. or tick+duration+5 >= self.horizon:
                self.retreat = True
                self.opt["home_floor"] = self.initial_options["home_floor"]
                self.events.append({"tick": self.now, "kind": "return_guard", "estimated_min_battery": low,
                                    "estimated_end_battery": end, "estimated_ticks": duration})
        if self.retreat:
            self.route = []; self.need_plan = False; self.last_plan = tick
        return super()._decide(tick, x, y, sigma, battery)


def step(p):
    p.before_step(); p.act()
    result = p.tools.advance(1)
    p.observe(result["packets"], result["current_tick"])
    return result["episode_complete"]
