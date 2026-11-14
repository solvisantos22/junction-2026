"""One public-state decision at tick 140; the original pilot handles navigation.

No simulator import. Feature extraction consumes only the pilot's public-data
belief. A strategy is chosen once, so its exact outcome can be looked up in a
counterfactual validation table whose prefixes are identical.
"""

import math
import statistics

from lightlag_traverse.pilot import Pilot
from lightlag_traverse.surface import TERRAIN_CODES

SWITCH_TICK = 140
PROFILES = {
    "baseline": {},
    "refresh": {},
    "energy_path": {"energy_weight": .5},
    "energy_path_strong": {"energy_weight": 1.0},
    "aggressive": {"floor": 2., "home_floor": .5, "home_margin": 1., "home_slack": 1., "deadline_margin": 0},
    "reserve": {"floor": 8., "home_margin": 6., "home_slack": 1.15},
    "deadline_relaxed": {"deadline_margin": 0},
    "deadline_early": {"deadline_margin": 4},
    "legs_fast": {"leg_slack": .95},
    "legs_slow": {"leg_slack": 1.08},
    "arrival_wide": {"arrive_m": 1.5},
    "balanced": {"energy_weight": .5, "home_margin": 2., "floor": 3.5},
}
PROFILE_NAMES = tuple(PROFILES)


def features(pilot):
    """Stable named features; no seed, hidden state, or final grade is available."""
    p = pilot
    tick = max(p.now + p.delay + 1, p.reserved_until + 1)
    x, y, sigma, battery = p.predict(tick)
    left = p.horizon - tick
    home_t, home_e = p._to("base", x, y)
    finite = lambda value, scale: min(10., max(-10., value / scale)) if math.isfinite(value) else 10.
    f = {
        "tick": tick / p.horizon, "battery": battery / p.capacity,
        "x": x / ((p.surface.nx - 1) * p.surface.cell),
        "y": y / ((p.surface.ny - 1) * p.surface.cell),
        "sigma": sigma / 5., "bias": p.filter.bias / 10.,
        "home_time": finite(home_t, max(left, 1)), "home_energy": finite(home_e, p.capacity),
        "home_spare": finite(battery - home_e, p.capacity),
        "efficiency": p.efficiency, "sun_now": p.sun.rate[min(tick, p.horizon)] / p.rules["solar_peak"],
        "sampled": len(p.sampled) / max(1, len(p.targets)),
        "pending": len(p.pending) / 4., "route_length": len(p.route) / max(1, len(p.targets)),
    }
    for name in sorted(p.slip):
        f["slip_" + name] = p.slip[name]
        f["slip_observations_" + name] = min(1., p.slip_seen[name][0] / 50.)
    known = [t for t in p.targets if t not in p.sampled and t not in p.pending]
    times, energies, values, deadlines, ratios = [], [], [], [], []
    for name in known:
        t, e = p._to(name, x, y)
        if not math.isfinite(t) or t > 10000:
            continue
        target = p.targets[name]
        times.append(t); energies.append(e); values.append(target["value"])
        deadline = target["deadline_tick"]
        slack = (p.horizon if deadline is None else deadline) - tick - t - 1
        deadlines.append(slack)
        value = target["value"] if slack >= 0 else target["late_value"]
        ratios.append(value / (1 + t))
    f["reachable_fraction"] = len(times) / max(1, len(known))
    f["known_remaining_fraction"] = len(known) / max(1, len(p.targets))
    f["remaining_value"] = sum(values) / 300.
    for label, vector, scale in (("travel", times, 60.), ("energy", energies, 30.),
                                 ("value", values, 10.), ("slack", deadlines, 100.), ("rate", ratios, 1.)):
        for stat, fn in (("min", min), ("mean", statistics.mean), ("max", max)):
            f[label + "_" + stat] = finite(fn(vector), scale) if vector else 0.
    f["deadlines_missed"] = sum(d < 0 for d in deadlines) / max(1, len(deadlines))
    f["deadlines_close"] = sum(0 <= d < 20 for d in deadlines) / max(1, len(deadlines))
    for index, value in enumerate(sorted(ratios, reverse=True)[:3] + [0.] * 3):
        if index >= 3: break
        f["best_rate_" + str(index)] = value
    codes = [v for row in p.surface.codes for v in row]
    for code in sorted(TERRAIN_CODES):
        f["terrain_" + TERRAIN_CODES[code]] = codes.count(code) / max(1, len(codes))
    assert all(math.isfinite(v) for v in f.values())
    return f


def apply_profile(pilot, name):
    if name not in PROFILES:
        raise ValueError("unknown profile")
    if name == "baseline":
        return
    old_weight = pilot.opt["energy_weight"]
    pilot.opt.update(PROFILES[name])
    if pilot.opt["energy_weight"] != old_weight:
        pilot.ground.energy_weight = pilot.opt["energy_weight"]
        pilot._rebuild()
    pilot.need_plan = pilot.full_plan = True


def choose(model, state, threshold=0.):
    values = model.predict([[state[k] for k in model.feature_names_]])[0]
    index = max(range(len(values)), key=lambda i: (float(values[i]), -i))
    return (PROFILE_NAMES[index + 1] if float(values[index]) > threshold else "baseline"), list(map(float, values))


def play(tools, spec, model=None, options=None):
    pilot = Pilot(tools, options)
    decision = None
    while True:
        if pilot.now >= SWITCH_TICK and decision is None:
            state = features(pilot)
            if spec["kind"] == "fixed":
                name, scores = spec["profile"], None
            elif spec["kind"] == "learned":
                name, scores = choose(model, state, spec["threshold"])
            else:
                raise ValueError("unknown policy kind")
            decision = {"tick": pilot.now, "features": state, "profile": name, "predictions": scores}
            apply_profile(pilot, name)
        pilot.act()
        out = tools.advance(1)
        pilot.observe(out["packets"], out["current_tick"])
        if out["episode_complete"]:
            return pilot, decision
