"""Public mission generator and an event-by-event verifier, with no solver imports.

Integer intervals are half open. A sample occupies cold storage after collection
until lab processing starts; data occupies memory from lab completion through
transmission. Each active machine draws one of two available power units.
"""

import random


VERSION = "sample-chain-v1"


def generate(seed, jobs=8):
    """Generate public opportunities, without filtering on any policy's score."""
    if jobs < 1 or jobs > 16:
        raise ValueError("probe supports 1–16 jobs")
    rng = random.Random(seed)
    horizon = 2 * jobs + 8
    passes = list(range(5, horizon, 4))
    result = {
        "version": VERSION,
        "horizon": horizon,
        "capacities": {"rover": 1, "lab": 1, "radio": 1,
                       "power": 2, "cold": 2, "data": 2},
        "downlink_slots": passes,
        "jobs": [],
    }
    for index in range(jobs):
        collect_duration = rng.randint(1, 2)
        process_duration = rng.randint(1, 3)
        anchor_pass = rng.choice(passes)
        anchor_process = anchor_pass - process_duration
        anchor_collect = max(0, anchor_process - collect_duration - rng.randint(0, 3))
        slots = {anchor_collect}
        slots.update(rng.sample(range(horizon - 4), min(2, horizon - 4)))
        result["jobs"].append({
            "id": f"sample-{index:02d}",
            "value": rng.randint(4, 20),
            "collect_duration": collect_duration,
            "process_duration": process_duration,
            "shelf_life": process_duration + rng.randint(1, 4),
            "collect_slots": sorted(slots),
            "deadline": min(horizon, anchor_pass + 1 + rng.randint(0, 4)),
        })
    return result


def verify(mission, plan):
    """Reconstruct resource usage directly; never trust compiled solver masks.

The plan contains only complete collection/process/transmission chains. Empty
or partial-job-set plans are valid and earn only their actual delivered value.
An invalid plan earns zero; this is a research checker, not a security boundary.
"""
    if not isinstance(plan, list):
        return {"valid": False, "value": 0, "errors": ["plan must be a list"]}
    horizon = mission["horizon"]
    usage = {name: [0] * horizon for name in mission["capacities"]}
    jobs = {job["id"]: job for job in mission["jobs"]}
    seen = set()
    errors = []
    value = 0
    for action in plan:
        if (not isinstance(action, dict)
                or set(action) != {"job", "collect", "process", "transmit"}
                or not isinstance(action["job"], str)
                or any(type(action[k]) is not int for k in ("collect", "process", "transmit"))):
            errors.append("invalid chain schema")
            continue
        identity = action["job"]
        if identity not in jobs or identity in seen:
            errors.append(f"unknown or duplicate job: {identity}")
            continue
        seen.add(identity)
        job = jobs[identity]
        collect, process, transmit = (action[k] for k in ("collect", "process", "transmit"))
        collected = collect + job["collect_duration"]
        processed = process + job["process_duration"]
        delivered = transmit + 1
        if not (0 <= collect < collected <= process < processed <= transmit < delivered <= horizon):
            errors.append(f"precedence/horizon: {identity}")
            continue
        if collect not in job["collect_slots"] or transmit not in mission["downlink_slots"]:
            errors.append(f"opportunity: {identity}")
        if processed - collected > job["shelf_life"]:
            errors.append(f"expired sample: {identity}")
        if delivered > job["deadline"]:
            errors.append(f"delivery deadline: {identity}")
        for resource, start, end in (
            ("rover", collect, collected), ("lab", process, processed),
            ("radio", transmit, delivered), ("cold", collected, process),
            ("data", processed, delivered),
        ):
            for tick in range(start, end):
                usage[resource][tick] += 1
                if resource in ("rover", "lab", "radio"):
                    usage["power"][tick] += 1
        value += job["value"]
    for resource, timeline in usage.items():
        for tick, used in enumerate(timeline):
            if used > mission["capacities"][resource]:
                errors.append(f"{resource} capacity at {tick}: {used}")
    return {"valid": not errors, "value": 0 if errors else value,
            "errors": errors, "delivered": len(seen), "usage": usage}
