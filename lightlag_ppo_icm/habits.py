"""What a trained policy does with its commands and its battery (needs numpy).

    python3 -m lightlag_ppo_icm.habits --policy lightlag_ppo_icm/policies/max.npz --seeds 300000-300031

Prints, per mission on average: how many of its decisions are drives, samples and waits, how
many commands the battery guard replaced by a wait and from which decision on, the same for the
home guard when the policy plays with it, the battery left at the horizon and the distance from
the base there. The score table says how well a policy
did; this says how, which is where a learned policy's faults show.

A target-mode policy (targets.py, on the traverse) gets its own report: how many choices a mission,
how often it took the nearest target the mask allowed and which slot on average, whether and when
it chose to go home, and the battery and the distance from the lander at the end.
"""

import argparse
import math
import statistics

from lightlag_dynamic.biomes.max_check import seed_range

from .agent import load_policy
from .envs import FiveTools, finish, make_env, share
from .targets import TargetConfig, TargetTask, is_target_config
from .task import FIRST_DRIVE, SAMPLE, WAIT, RoverTask, TaskConfig


def mission(policy, config, spec, seed, delay):
    """One greedy mission: the result and how the commands were spent."""
    env = make_env(spec, seed, delay)
    task = RoverTask(FiveTools(env), config)
    actions, guard_from, home_from = [], [], []

    def choose(observation):
        action = policy.act(observation)[0]
        actions.append(action)
        guard_from.append(task.guarded)
        home_from.append(task.homed)
        return action

    task.play(choose)
    result = finish(env)
    last = env.replay()["states"][-1]
    replaced = [i for i in range(len(actions))
                if (guard_from[i + 1] if i + 1 < len(actions) else task.guarded) > guard_from[i]]
    homed = [i for i in range(len(actions))
             if (home_from[i + 1] if i + 1 < len(actions) else task.homed) > home_from[i]]
    return {"share": share(result), "home": bool(result["alive"] and result["at_base"]),
            "drives": sum(a >= FIRST_DRIVE for a in actions), "samples": actions.count(SAMPLE),
            "waits": actions.count(WAIT), "replaced": len(replaced), "first_replaced": replaced[0] if replaced else None,
            "home_guard": config.home_guard, "homed": len(homed), "first_homed": homed[0] if homed else None,
            "decisions": len(actions), "battery": last["battery"],
            "from_base": math.hypot(last["position"][0] - task.base[0], last["position"][1] - task.base[1])}


def target_mission(policy, config, seed):
    """One greedy traverse mission in the target mode: the result and how the choices went."""
    env = make_env("traverse", seed)
    picks = []

    def choose(observation, mask):
        action = policy.act(observation, None, mask)[0]
        picks.append((action, int(observation[0] * 420 + 0.5)))
        return action

    task = TargetTask(FiveTools(env), config)
    task.play(choose)
    result = finish(env)
    last = env.replay()["states"][-1]
    targets = [a for a, _ in picks if a != config.home_action]
    home = [tick for a, tick in picks if a == config.home_action]
    base = task.pilots[0].base
    return {"share": share(result), "home": bool(result["alive"] and result["at_base"]), "alive": bool(result["alive"]),
            "choices": len(picks), "nearest": sum(a == 0 for a in targets), "slots": sum(targets), "targets": len(targets),
            "home_tick": home[0] if home else None, "samples": len(result.get("samples", [])),
            "battery": last["battery"],
            "from_base": math.hypot(last["position"][0] - base[0], last["position"][1] - base[1])}


def target_report(rows):
    mean = statistics.fmean
    picked = sum(r["targets"] for r in rows) or 1
    homes = [r["home_tick"] for r in rows if r["home_tick"] is not None]
    return "\n".join([
        f"share {100 * mean(r['share'] for r in rows):.1f}%, home {sum(r['home'] for r in rows)} of {len(rows)}, "
        f"dead {sum(not r['alive'] for r in rows)}, samples {mean(r['samples'] for r in rows):.1f} a mission",
        f"{mean(r['choices'] for r in rows):.1f} choices a mission; of the targets chosen, "
        f"{100 * sum(r['nearest'] for r in rows) / picked:.0f}% the nearest allowed, mean slot "
        f"{sum(r['slots'] for r in rows) / picked:.2f} (0 is the nearest)",
        f"chose home itself in {len(homes)} of {len(rows)} missions"
        + (f", at tick {mean(homes):.0f} on average" if homes else "; the pilot turned for home otherwise"),
        f"at the end: {mean(r['battery'] for r in rows):.1f} battery left, "
        f"{mean(r['from_base'] for r in rows):.1f} m from the lander"])


def report(rows):
    mean = statistics.fmean
    held = [r["first_replaced"] + 1 for r in rows if r["first_replaced"] is not None]
    lines = [f"share {100 * mean(r['share'] for r in rows):.1f}%, home {sum(r['home'] for r in rows)} of {len(rows)}",
             f"of {mean(r['decisions'] for r in rows):.0f} decisions a mission: drive {mean(r['drives'] for r in rows):.1f}, "
             f"sample {mean(r['samples'] for r in rows):.1f}, wait {mean(r['waits'] for r in rows):.1f}",
             f"the battery guard replaced {mean(r['replaced'] for r in rows):.1f} of them by a wait"
             + (f", from decision {mean(held):.0f} on average, in {len(held)} of {len(rows)} missions" if held else "")]
    if any(r.get("home_guard") for r in rows):
        sent = [r["first_homed"] + 1 for r in rows if r["first_homed"] is not None]
        lines.append(f"the home guard replaced {mean(r['homed'] for r in rows):.1f} of them by its own command"
                     + (f", from decision {mean(sent):.0f} on average, in {len(sent)} of {len(rows)} missions"
                        if sent else ""))
    lines.append(f"at the horizon: {mean(r['battery'] for r in rows):.1f} battery left, "
                 f"{mean(r['from_base'] for r in rows):.1f} m from the base")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--policy", required=True)
    parser.add_argument("--seeds", default="300000-300031")
    parser.add_argument("--env", help="default: the environment the policy was trained on")
    args = parser.parse_args(argv)
    policy, extra = load_policy(args.policy)
    if is_target_config(extra["task"]):
        config = TargetConfig.from_dict(extra["task"])
        rows = [target_mission(policy, config, seed) for seed in seed_range(args.seeds)]
        print(f"traverse (target mode), seeds {args.seeds}")
        print(target_report(rows))
        return rows
    config = TaskConfig.from_dict(extra["task"])
    spec = args.env or extra["env"]
    rows = [mission(policy, config, spec, seed, extra["delay"]) for seed in seed_range(args.seeds)]
    print(f"{spec}, seeds {args.seeds}")
    print(report(rows))
    return rows


if __name__ == "__main__":
    main()
