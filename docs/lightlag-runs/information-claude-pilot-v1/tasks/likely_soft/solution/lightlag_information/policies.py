"""Exact finite-strategy values and policies using only public callbacks.

These policies start from a fresh briefing. They are references for this small
route-choice abstraction, not controllers for the continuous rover.
"""


POLICIES = ("never_probe", "always_probe", "selective", "blind_probe")


def _route_value(rules, route, prior_firm, energy, execution_tick):
    trip = rules["routes"][route]
    completion_tick = execution_tick + trip["duration"]
    if completion_tick > rules["horizon"]:
        return 0.0
    reward = max(0.0, trip["target_value"] - rules["penalty_per_tick"] * completion_tick)
    reward /= rules["normalization"]
    return sum(
        probability * reward
        for terrain, probability in (("firm", prior_firm), ("soft", 1 - prior_firm))
        if trip["energy"][terrain] <= energy
    )


def _best_route(rules, prior_firm, energy, execution_tick):
    values = {
        route: _route_value(rules, route, prior_firm, energy, execution_tick)
        for route in rules["routes"]
    }
    # Stable route ties use lexical order (detour before shortcut).
    route = min(values, key=lambda name: (-values[name], name))
    return route, values[route]


def _signal_posterior(prior_firm, accuracy, signal):
    likelihood_firm = accuracy if signal == "firm" else 1 - accuracy
    likelihood_soft = 1 - accuracy if signal == "firm" else accuracy
    probability = prior_firm * likelihood_firm + (1 - prior_firm) * likelihood_soft
    posterior = prior_firm * likelihood_firm / probability if probability else prior_firm
    return probability, posterior


def expected_values(rules):
    """Return exact expected *realized* rewards for the four public strategies.

    The no-probe route departs at delay+1. A probe executes then, its signal
    arrives at 2*delay+1, and an adaptive or blind-control route departs at
    3*delay+2. Each terrain/signal outcome has its actual probability.
    """
    prior = rules["context"]["prior_firm"]
    energy = rules["initial_energy"]
    direct_tick = rules["delay"] + 1
    probed_tick = 3 * rules["delay"] + 2
    remaining = max(0, energy - rules["context"]["probe_energy"])
    never = _best_route(rules, prior, energy, direct_tick)[1]
    always = 0.0
    for signal in ("firm", "soft"):
        probability, posterior = _signal_posterior(prior, rules["signal_accuracy"], signal)
        always += probability * _best_route(rules, posterior, remaining, probed_tick)[1]
    blind = _best_route(rules, prior, remaining, probed_tick)[1]
    return {"never_probe": never, "always_probe": always,
            "selective": max(never, always), "blind_probe": blind}


def _advance_to(tools, target, tick, max_step):
    while tick < target:
        result = tools.advance(min(max_step, target - tick))
        following = result["current_tick"]
        if following <= tick:
            raise RuntimeError("Public clock did not advance toward the declared horizon")
        tick = following
    return tick


def run_policy(tools, name):
    """Run a named policy to horizon via public tools; return public decisions.

    ``tools`` supplies rules, map, telemetry_log, uplink and advance callbacks.
    No evaluator, seed, hidden terrain, future signal or environment attribute
    is consulted. blind_probe waits exactly as always_probe, ignoring signal.
    """
    if name not in POLICIES:
        raise ValueError("Unknown information policy: " + str(name))
    rules = tools.rules()
    tick = tools.telemetry_log()["current_tick"]
    if tick != 0:
        raise ValueError("Information policies require a fresh episode at tick 0")
    values = expected_values(rules)
    strategy = name
    if name == "selective":
        strategy = "always_probe" if values["always_probe"] > values["never_probe"] else "never_probe"
    probe = strategy != "never_probe"
    prior = rules["context"]["prior_firm"]
    posterior = prior
    energy = rules["initial_energy"]
    if probe:
        tools.uplink([{"action": "probe"}])
        arrival = 2 * rules["delay"] + 1
        tick = _advance_to(tools, min(arrival, rules["horizon"]), tick, rules["max_advance_ticks"])
        energy = max(0, energy - rules["context"]["probe_energy"])
        if strategy == "always_probe" and tick >= arrival:
            # A delivered probe is one fixed observation, even if logs repeat it.
            evidence = next(entry for entry in tools.telemetry_log()["entries"]
                            if entry["action"] == "probe")
            posterior = _signal_posterior(prior, rules["signal_accuracy"], evidence["signal"])[1]
    route = None
    commit_sent_tick = None
    if tick < rules["horizon"]:
        route = _best_route(rules, posterior, energy, tick + rules["delay"] + 1)[0]
        tools.uplink([{"action": "commit", "route": route}])
        commit_sent_tick = tick
    tick = _advance_to(tools, rules["horizon"], tick, rules["max_advance_ticks"])
    return {"policy": name, "strategy": strategy, "route": route,
            "probe_used": probe, "posterior_firm": posterior,
            "commit_sent_tick": commit_sent_tick, "final_tick": tick,
            "expected_reward": values[name]}
