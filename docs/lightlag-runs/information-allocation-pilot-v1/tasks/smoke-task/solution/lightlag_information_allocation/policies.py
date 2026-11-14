"""Public-information reference and controls for one inspection of two unknowns.

Each policy starts from a fresh briefing. The policy receives only public tool
callbacks. The value computation enumerates no hidden sampled episode state.
"""

POLICIES = ("selective", "never_probe", "probe_a", "probe_b",
            "least_useful_probe", "blind_selected_probe", "most_uncertain",
            "entropy_matched_gate", "least_useful_matched_gate")
PROBE_ROUTES = ("a", "b")


def _route_value(rules, route, probabilities, energy, execution_tick):
    trip = rules["routes"][route]
    completion = execution_tick + trip["duration"]
    if completion > rules["horizon"]:
        return 0.0
    reward = max(0.0, trip["target_value"] - rules["penalty_per_tick"] * completion)
    reward /= rules["normalization"]
    if route not in probabilities:
        # The detour's published cost is known and identical in both states.
        return reward if trip["energy"]["firm"] <= energy else 0.0
    prior = probabilities[route]
    return sum(probability * reward
               for state, probability in (("firm", prior), ("soft", 1 - prior))
               if trip["energy"][state] <= energy)


def _best_route(rules, probabilities, energy, execution_tick):
    values = {route: _route_value(rules, route, probabilities, energy, execution_tick)
              for route in rules["routes"]}
    route = min(values, key=lambda candidate: (-values[candidate], candidate))
    return route, values[route]


def _signal_posterior(prior, accuracy, signal):
    likelihood_firm = accuracy if signal == "firm" else 1 - accuracy
    likelihood_soft = 1 - accuracy if signal == "firm" else accuracy
    probability = prior * likelihood_firm + (1 - prior) * likelihood_soft
    posterior = prior * likelihood_firm / probability if probability else prior
    return probability, posterior


def acquisition_values(rules):
    """Expected realized reward of no inspection, inspection a, or inspection b.

    Probe signals update only the inspected route: the two terrain states are
    independent. Completion timing and remaining energy are charged before
    choosing each posterior-optimal route.
    """
    priors = rules["priors_firm"]
    direct_tick = rules["delay"] + 1
    probed_tick = 3 * rules["delay"] + 2
    energy = rules["initial_energy"]
    remaining = max(0, energy - rules["context"]["probe_energy"])
    values = {"none": _best_route(rules, priors, energy, direct_tick)[1]}
    for inspected in PROBE_ROUTES:
        expected = 0.0
        for signal in ("firm", "soft"):
            probability, posterior = _signal_posterior(
                priors[inspected], rules["signal_accuracy"], signal)
            updated = dict(priors, **{inspected: posterior})
            expected += probability * _best_route(rules, updated, remaining, probed_tick)[1]
        values[inspected] = expected
    return values


def choose_acquisition(rules):
    """Return None, 'a' or 'b'; ties prefer no inspection, then a, then b."""
    values = acquisition_values(rules)
    order = ("none", "a", "b")
    chosen = min(order, key=lambda action: (-values[action], order.index(action)))
    return None if chosen == "none" else chosen


def _probe_for_policy(rules, name, acquisition):
    if name == "never_probe":
        return None
    if name in ("entropy_matched_gate", "least_useful_matched_gate"):
        if _probe_for_policy(rules, "selective", acquisition) is None:
            return None
        name = "most_uncertain" if name == "entropy_matched_gate" else "least_useful_probe"
    if name in ("selective", "blind_selected_probe"):
        order = ("none", "a", "b")
        chosen = min(order, key=lambda action: (-acquisition[action], order.index(action)))
        return None if chosen == "none" else chosen
    if name in ("probe_a", "probe_b"):
        return name[-1]
    if name == "least_useful_probe":
        return min(PROBE_ROUTES, key=lambda route: (acquisition[route], route))
    if name == "most_uncertain":
        return min(PROBE_ROUTES, key=lambda route: (abs(rules["priors_firm"][route] - .5), route))
    raise ValueError("unknown allocation policy: " + str(name))


def expected_values(rules):
    """Values of the declared policies, including a timing-matched blind control."""
    acquisition = acquisition_values(rules)
    values = {}
    for name in POLICIES:
        inspected = _probe_for_policy(rules, name, acquisition)
        if name == "blind_selected_probe" and inspected is not None:
            remaining = max(0, rules["initial_energy"] - rules["context"]["probe_energy"])
            values[name] = _best_route(rules, rules["priors_firm"], remaining,
                                       3 * rules["delay"] + 2)[1]
        else:
            values[name] = acquisition[inspected or "none"]
    return values


def _advance_to(tools, target, tick, max_step):
    while tick < target:
        following = tools.advance(min(max_step, target - tick))["current_tick"]
        if following <= tick:
            raise RuntimeError("public clock did not advance toward the declared horizon")
        tick = following
    return tick


def run_policy(tools, name):
    """Run through the five public callbacks and finish at the public horizon."""
    if name not in POLICIES:
        raise ValueError("unknown allocation policy: " + str(name))
    rules = tools.rules()
    tick = tools.telemetry_log()["current_tick"]
    if tick != 0:
        raise ValueError("allocation policies require a fresh episode at tick 0")
    inspected = _probe_for_policy(rules, name, acquisition_values(rules))
    posterior = dict(rules["priors_firm"])
    energy = rules["initial_energy"]
    if inspected is not None:
        tools.uplink([{"action": "probe", "route": inspected}])
        arrival = 2 * rules["delay"] + 1
        tick = _advance_to(tools, min(arrival, rules["horizon"]), tick, rules["max_advance_ticks"])
        energy = max(0, energy - rules["context"]["probe_energy"])
        if tick >= arrival:
            evidence = next(entry for entry in tools.telemetry_log()["entries"]
                            if entry["action"] == "probe" and entry["probe_route"] == inspected)
            # Read the same single delivered event in the blind control, but
            # deliberately do not update from it. Repeated entries are not
            # additional independent observations.
            if name != "blind_selected_probe":
                posterior[inspected] = _signal_posterior(
                    posterior[inspected], rules["signal_accuracy"], evidence["signal"])[1]
    route = None
    commit_sent_tick = None
    if tick < rules["horizon"]:
        route = _best_route(rules, posterior, energy, tick + rules["delay"] + 1)[0]
        tools.uplink([{"action": "commit", "route": route}])
        commit_sent_tick = tick
    tick = _advance_to(tools, rules["horizon"], tick, rules["max_advance_ticks"])
    return {"policy": name, "probe_route": inspected, "probe_used": inspected is not None,
            "posterior_firm": posterior, "route": route, "commit_sent_tick": commit_sent_tick,
            "final_tick": tick, "expected_reward": expected_values(rules)[name]}
