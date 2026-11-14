"""The environments the tester can be pointed at, by name, and one episode through the public tools.

    max                         the max env (lightlag_dynamic/biomes/maxenv.py): every mechanic on
    max_rocks                   the same with Gale Rock Field in place of Hidden Valley
    rush, rush_noisy, ...       a plain profile of lightlag_dynamic
    rush_noisy@troy_crust       a profile in a biome; biomes mix with "+"
    traverse                    Lightlag Traverse (lightlag_traverse/)
    traverse_max                its MAX map (lightlag_traverse_max/), once that package is there

The agent only ever gets the five public tools of the environment; evaluate() is the evaluator's.
"""

import numpy as np

from .task import RoverTask


class FiveTools:
    """rules, map, telemetry_log, uplink, advance, and nothing else of the environment."""

    def __init__(self, env):
        self.rules, self.map, self.telemetry_log = env.rules, env.map, env.telemetry_log
        self.uplink, self.advance = env.uplink, env.advance


def make_env(spec, seed, delay=3):
    """One fresh episode of the environment called `spec`."""
    if spec in ("max", "max_rocks"):
        from lightlag_dynamic.biomes.maxenv import make_max_env
        return make_max_env(seed=seed, delay=delay, rocks=spec == "max_rocks")
    if spec in ("traverse", "traverse_max"):
        if delay != 3:
            raise ValueError("the traverse fixes its own signal delay")
        if spec == "traverse":
            from lightlag_traverse.environment import TraverseEnvironment
            return TraverseEnvironment(seed)
        try:
            from lightlag_traverse_max.environment import make_env as make_traverse_max
        except ImportError as error:
            raise ValueError("traverse_max needs the lightlag_traverse_max package, which is not in "
                             "this checkout yet") from error
        return make_traverse_max(seed=seed, option="max")
    from lightlag_dynamic.missions import PROFILES
    profile, _, biome = spec.partition("@")
    if profile not in PROFILES:
        raise ValueError(f"unknown environment {spec!r}: use max, max_rocks, traverse, traverse_max, or a "
                         f"profile ({', '.join(PROFILES)}), optionally followed by @biome")
    if biome:
        from lightlag_dynamic.biomes import make_biome_env
        return make_biome_env(biome, seed=seed, delay=delay, profile=profile)
    from lightlag import Config
    from lightlag_dynamic import DynamicEnvironment
    return DynamicEnvironment(seed=seed, config=Config(delay_ticks=delay, max_ticks=PROFILES[profile][4]),
                              profile=profile)


def finish(env):
    """The evaluator runs out the horizon and scores, whatever the player did."""
    while not env.advance(5)["episode_complete"]:
        pass
    return env.evaluate()


def share(result):
    return result["raw_score"] / result["max_available_value"] if result["max_available_value"] else 0.0


def run_episode(spec, seed, choose, delay=3, config=None, record=False, home_pull=False):
    """Play one episode with `choose(observation) -> action`. Returns the score and, with `record`,
    the per-decision rewards. The chooser sees observations only: no environment, no seed."""
    env = make_env(spec, seed, delay)
    task = RoverTask(FiveTools(env), config)
    task.play(choose)
    result = finish(env)
    out = {"seed": seed, "share": share(result), "alive": bool(result["alive"]), "at_base": bool(result["at_base"]),
           "samples": len(result.get("samples", [])), "decisions": len(task.decisions)}
    if record:
        out["ext"] = task.rewards(result, home_pull).astype(np.float32)
    return out
