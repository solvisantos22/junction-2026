"""Exhaustive bounded-instance reference and deliberately generic controls.

The exact solver branches on each job's complete feasible schedules or skipping
that job. Its upper bound sums all remaining individually compatible values,
ignoring their mutual conflicts; therefore it cannot underestimate the optimum.
Exhausting that tree proves the optimum. A node cap is reported as incomplete.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Choice:
    job: str
    collect: int
    process: int
    transmit: int
    unary: int
    power: int
    cold: int
    data: int

    def action(self):
        return {k: getattr(self, k) for k in ("job", "collect", "process", "transmit")}


EMPTY = (0, 0, 0, 0, 0, 0, 0)


def interval(start, end):
    return ((1 << (end - start)) - 1) << start


def compile_choices(mission):
    expected = {"rover": 1, "lab": 1, "radio": 1, "power": 2, "cold": 2, "data": 2}
    if mission["capacities"] != expected:
        raise ValueError("this probe's bit-mask solver supports only the published capacities")
    horizon = mission["horizon"]
    result = {}
    for job in mission["jobs"]:
        choices = []
        for collect in job["collect_slots"]:
            collected = collect + job["collect_duration"]
            for process in range(collected, min(collected + job["shelf_life"], horizon) - job["process_duration"] + 1):
                processed = process + job["process_duration"]
                for transmit in mission["downlink_slots"]:
                    if not (processed <= transmit and transmit + 1 <= min(horizon, job["deadline"])):
                        continue
                    rover = interval(collect, collected)
                    lab = interval(process, processed)
                    radio = interval(transmit, transmit + 1)
                    choices.append(Choice(
                        job["id"], collect, process, transmit,
                        rover | (lab << horizon) | (radio << (2 * horizon)),
                        rover | lab | radio,
                        interval(collected, process), interval(processed, transmit + 1),
                    ))
        result[job["id"]] = sorted(choices, key=lambda c: (c.transmit, c.data.bit_count() + c.cold.bit_count(), c.collect, c.process))
    return result


def fits(state, choice):
    return not (state[0] & choice.unary or state[2] & choice.power
                or state[4] & choice.cold or state[6] & choice.data)


def add(state, choice):
    return (state[0] | choice.unary,
            state[1] | choice.power, state[2] | (state[1] & choice.power),
            state[3] | choice.cold, state[4] | (state[3] & choice.cold),
            state[5] | choice.data, state[6] | (state[5] & choice.data))


def greedy(mission, choices, rule="value"):
    def key(job):
        density = job["value"] / (job["collect_duration"] + job["process_duration"] + 1)
        if rule == "deadline":
            return (job["deadline"], -job["value"], job["id"])
        if rule == "density":
            return (-density, job["deadline"], job["id"])
        if rule == "scarcity":
            return (len(choices[job["id"]]), -job["value"], job["id"])
        return (-job["value"], job["deadline"], job["id"])
    state, value, plan = EMPTY, 0, []
    for job in sorted(mission["jobs"], key=key):
        feasible = [c for c in choices[job["id"]] if fits(state, c)]
        if feasible:
            chosen = feasible[0]
            state = add(state, chosen)
            value += job["value"]
            plan.append(chosen.action())
    return {"value": value, "plan": plan}


def ordered_jobs(mission, choices):
    return sorted(mission["jobs"], key=lambda j: (-j["value"], len(choices[j["id"]]), j["id"]))


def exact(mission, choices=None, max_nodes=250_000):
    choices = compile_choices(mission) if choices is None else choices
    jobs = ordered_jobs(mission, choices)
    portfolio = [greedy(mission, choices, r) for r in ("value", "deadline", "density", "scarcity")]
    incumbent = max(portfolio, key=lambda x: x["value"])
    best_value, best_plan = incumbent["value"], incumbent["plan"]
    nodes, incomplete = 0, False
    visited = {}

    def visit(index, state, value, plan):
        nonlocal best_value, best_plan, nodes, incomplete
        if nodes >= max_nodes:
            incomplete = True
            return
        nodes += 1
        if value > best_value:
            best_value, best_plan = value, [c.action() for c in plan]
        if index == len(jobs):
            return
        cache_key = (index, state)
        if visited.get(cache_key, -1) >= value:
            return
        visited[cache_key] = value
        # Removing impossible jobs only tightens a valid optimistic upper bound.
        upper = value + sum(j["value"] for j in jobs[index:]
                            if any(fits(state, c) for c in choices[j["id"]]))
        if upper <= best_value:
            return
        job = jobs[index]
        for choice in choices[job["id"]]:
            if fits(state, choice):
                visit(index + 1, add(state, choice), value + job["value"], plan + [choice])
                if incomplete:
                    return
        visit(index + 1, state, value, plan)

    visit(0, EMPTY, 0, [])
    return {"value": best_value, "plan": best_plan, "proven_optimal": not incomplete, "nodes": nodes}


def beam(mission, choices=None, width=64):
    """Generic bounded search, ordered by optimistic value then earned value."""
    choices = compile_choices(mission) if choices is None else choices
    jobs = ordered_jobs(mission, choices)
    states = [(EMPTY, 0, [])]
    expanded = 0
    for index, job in enumerate(jobs):
        candidates = {}
        for state, value, plan in states:
            options = [(state, value, plan)]
            options.extend((add(state, c), value + job["value"], plan + [c])
                           for c in choices[job["id"]] if fits(state, c))
            for new_state, new_value, new_plan in options:
                expanded += 1
                if new_state not in candidates or new_value > candidates[new_state][0]:
                    candidates[new_state] = (new_value, new_plan)
        def rank(item):
            state, (value, _) = item
            upper = value + sum(j["value"] for j in jobs[index + 1:]
                                if any(fits(state, c) for c in choices[j["id"]]))
            return upper, value, -sum(x.bit_count() for x in state)
        states = [(state, value, plan) for state, (value, plan)
                  in sorted(candidates.items(), key=rank, reverse=True)[:width]]
    _, value, plan = max(states, key=lambda x: x[1])
    return {"value": value, "plan": [c.action() for c in plan], "expanded": expanded}
