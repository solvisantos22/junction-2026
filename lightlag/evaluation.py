"""Trusted episode execution and deterministic evaluation artifacts."""

from copy import deepcopy
from inspect import signature

from .controllers.api import PublicTools
from .environment import Environment


def run_episode(policy, seed=0, config=None, world=None, policy_name=None):
    """Run one policy through public tools, then finish and grade the episode.

    Exceptions propagate to the caller: an invalid action or broken policy is
    an execution failure, not a benchmark score. A policy that catches a tool
    failure still fails the run when it returns. Transcript records contain
    copied ``source``, ``tool``, ``request`` and ``result`` fields. ``source``
    distinguishes policy calls from the evaluator's initial rules read and
    any advances needed after the policy returns.
    """
    env = Environment(seed=seed, config=deepcopy(config), world=deepcopy(world))
    transcript = []
    tool_names = ("rules", "map", "telemetry_log", "uplink", "advance")
    methods = {name: getattr(env, name) for name in tool_names}
    signatures = {name: signature(method) for name, method in methods.items()}
    counts = {source: dict.fromkeys(tool_names, 0) for source in ("policy", "evaluator")}
    current_tick = 0
    first_policy_failure = None

    def call(source, tool, args, kwargs):
        nonlocal current_tick, first_policy_failure
        record = {"source": source, "tool": tool}
        transcript.append(record)
        counts[source][tool] += 1
        try:
            record["request"] = {"args": deepcopy(list(args)), "kwargs": deepcopy(kwargs)}
            bound = signatures[tool].bind(*args, **kwargs)
            bound.apply_defaults()
            record["request"] = deepcopy(dict(bound.arguments))
            result = methods[tool](**deepcopy(record["request"]))
            record["result"] = deepcopy(result)
            if tool == "advance":
                current_tick = result["current_tick"]
            return deepcopy(result)
        except Exception as failure:
            record["error"] = {"type": type(failure).__name__, "message": str(failure)}
            if source == "policy" and first_policy_failure is None:
                first_policy_failure = failure
            raise

    def public_callback(tool):
        def invoke(*args, **kwargs):
            return call("policy", tool, args, kwargs)
        return invoke

    public_rules = call("evaluator", "rules", (), {})
    tools = PublicTools(**{name: public_callback(name) for name in tool_names})
    policy(tools)
    if first_policy_failure is not None:
        raise first_policy_failure
    while current_tick < public_rules["max_ticks"]:
        remaining = public_rules["max_ticks"] - current_tick
        ticks = min(remaining, public_rules["max_advance_ticks"])
        call("evaluator", "advance", (), {"ticks": ticks})

    return {
        "policy": policy_name if policy_name is not None else getattr(policy, "__name__", type(policy).__name__),
        "seed": seed,
        "delay": public_rules["delay_ticks"],
        "rules": public_rules,
        "result": env.evaluate(),
        "replay": env.replay(),
        "transcript": deepcopy(transcript),
        "tool_calls": {
            "policy": sum(counts["policy"].values()),
            "evaluator": sum(counts["evaluator"].values()),
            "total": len(transcript),
            "by_tool": deepcopy(counts),
        },
    }
