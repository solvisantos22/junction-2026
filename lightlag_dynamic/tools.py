"""Public-tool boundary and an evaluator-owned episode runner.

Mirrors the team's planned design (docs/superpowers/specs/2026-11-14-lightlag-reference-design.md):
a policy is a callable that receives only the five public tools; the evaluator builds a
fresh environment, runs the policy, then completes the horizon itself before scoring.
"""

from lightlag import Config

from .environment import DynamicEnvironment
from .missions import PROFILES


class PublicTools:
    """Exactly the five public methods. An auditable boundary, not a security sandbox."""

    def __init__(self, env):
        self._env = env
        self.calls = 0

    def _count(self):
        self.calls += 1

    def rules(self):
        self._count()
        return self._env.rules()

    def map(self):
        self._count()
        return self._env.map()

    def telemetry_log(self):
        self._count()
        return self._env.telemetry_log()

    def uplink(self, commands):
        self._count()
        return self._env.uplink(commands)

    def advance(self, ticks=1):
        self._count()
        return self._env.advance(ticks)


def run_episode(policy, seed, delay=3, profile="dynamic", horizon=None, policy_name=None,
                keep_replay=False, config_overrides=None):
    horizon = PROFILES[profile][4] if horizon is None else horizon
    config = Config(delay_ticks=delay, max_ticks=horizon, **(config_overrides or {}))
    env = DynamicEnvironment(seed=seed, config=config, profile=profile)
    tools = PublicTools(env)
    policy(tools)  # policy errors propagate: they must not turn into a low score
    while not env.advance(5)["episode_complete"]:
        pass  # the evaluator, not the policy, finishes the horizon
    run = {"policy": policy_name or getattr(policy, "__name__", "policy"), "seed": seed,
           "delay": delay, "profile": profile, "result": env.evaluate(),
           "public_calls": tools.calls}
    if keep_replay:
        run["replay"] = env.replay()
    return run
