"""A trained policy beside the scripted players, on the same seeds (needs numpy).

    python3 -m lightlag_ppo_icm.check --policy lightlag_ppo_icm/policies/max.npz --seeds 2700-2739
    python3 -m lightlag_ppo_icm.check --policy lightlag_ppo_icm/policies/rush.npz --seeds 2700-2739 \
        --players ppo_icm,kf_mpc,blind,random,nothing
    python3 -m lightlag_ppo_icm.check --policy lightlag_ppo_icm/policies/max.npz \
        --also ppo_alone=lightlag_ppo_icm/policies/max-ppo-alone.npz           # a second policy in the same table
    python3 -m lightlag_ppo_icm.check --policy lightlag_ppo_icm/policies/max-home-guard.npz \
        --also-home max_guarded=lightlag_ppo_icm/policies/max.npz              # an older policy with the home guard on

The environment and the delay are the ones the policy was trained on unless --env says
otherwise. A policy of the traverse's target mode (targets.py) plays that mode; beside it
random_targets, nearest_targets and cluster_targets (the same adapter without a network, see
player.py) and the traverse's
scripted players, the reference `pilot` when named. Players: ppo_icm (greedy), ppo_icm_sampled (actions drawn as in training), plain
(a hand-written rule on the same observation), random (the same adapter with random actions),
nothing, plain_home, random_home and ppo_icm_home (plain, random and the policy with the home guard
of task.py on; plain_home plays by default when the policy was trained with the guard), and the
scripted players of the environment:
max_navigator, fused, c37, kf_mpc, blind on the max env; kf_mpc, blind, reference, leg_and_wait on
a profile or biome; pilot, pilot_fast, greedy, straight on the traverse, and manh_max,
manh_max_fast besides on its MAX map (the full-search pilot and manh_max are slow, so they play
only when named).

Prints each player's mean share of the available value, deaths and returns home, and its paired
difference to the first player with a 95% bootstrap interval over the seeds.
"""

import argparse
import json
from multiprocessing import Pool

from lightlag_dynamic.biomes.max_check import seed_range, table

from .envs import FiveTools, finish, make_env, share
from .player import (cluster_target_player, load_player, nearest_target_player, plain_player, random_player,
                     random_target_player)
from .targets import is_target_config
from .task import TaskConfig


def scripted(spec):
    """The scripted players of an environment, each called as player(tools, env)."""
    if spec in ("max", "max_rocks"):
        from lightlag_dynamic.biomes.max_check import players
        return players()
    if spec == "traverse_max":
        from lightlag_traverse_max.players import POLICIES
        return {name: (lambda tools, env, play=play: play(tools)) for name, play in POLICIES.items()}
    if spec == "traverse":
        from lightlag_traverse.play import POLICIES
        return {name: (lambda tools, env, play=play: play(tools)) for name, play in POLICIES.items()}
    from lightlag_dynamic.controllers import POLICIES
    names = {"kf_mpc": "kf_mpc", "blind": "open_loop", "reference": "reference", "leg_and_wait": "leg_and_wait"}
    return {name: (lambda tools, env, play=POLICIES[policy]: play(tools)) for name, policy in names.items()}


def player(name, policy, spec):
    if name == "ppo_icm":
        return load_player(policy)
    if name == "ppo_icm_sampled":
        return load_player(policy, sample_seed=0)
    if name == "ppo_icm_home":
        return load_player(policy, home_guard=True)
    if name == "random":
        return random_player()
    if name == "random_home":
        return random_player(config=TaskConfig(home_guard=True))
    if name == "plain":
        return plain_player()
    if name == "plain_home":
        return plain_player(TaskConfig(home_guard=True))
    if name == "random_targets":
        return random_target_player()
    if name == "nearest_targets":
        return nearest_target_player()
    if name == "cluster_targets":
        return cluster_target_player()
    if name == "nothing":
        return lambda tools, env=None: None
    players = scripted(spec)
    if name not in players:
        raise ValueError(f"no player {name!r} for {spec}; there are ppo_icm, ppo_icm_sampled, ppo_icm_home, plain, "
                         "plain_home, random, random_home, random_targets, nearest_targets, cluster_targets, "
                         "nothing, "
                         + ", ".join(players))
    return players[name]


def default_players(extra, spec):
    """ppo_icm, plain (and plain_home when the policy plays with the home guard), random, nothing,
    then the scripted players of the environment but the slow ones. In the target mode: ppo_icm,
    nearest_targets, cluster_targets, random_targets, nothing and the traverse's scripted players but
    the pilot."""
    if is_target_config(extra["task"]):
        builtin = ["ppo_icm", "nearest_targets", "cluster_targets", "random_targets", "nothing"]
        return builtin + [n for n in scripted(spec) if n not in builtin + ["pilot"]]
    builtin = ["ppo_icm", "plain"] + (["plain_home"] if extra["task"].get("home_guard") else []) + ["random", "nothing"]
    return builtin + [n for n in scripted(spec) if n not in builtin + ["pilot", "manh_max"]]


def episode(job):
    """One episode: {player, seed, delay, share, alive, at_base, crash}."""
    label, name, policy, spec, seed, delay = job
    env = make_env(spec, seed, delay)
    crash = None
    try:
        player(name, policy, spec)(FiveTools(env), env)
    except Exception as error:  # a player's error is a result, not a harness failure
        crash = f"{type(error).__name__}: {error}"[:160]
    result = finish(env)
    return {"player": label, "seed": seed, "delay": delay, "share": share(result), "alive": result["alive"],
            "at_base": result["at_base"], "crash": crash}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--policy", required=True, help="policy.npz or best.npz of a training run")
    parser.add_argument("--seeds", default="2700-2739", help="e.g. 2700-2739")
    parser.add_argument("--env", help="default: the environment the policy was trained on")
    parser.add_argument("--delay", type=int, help="default: the delay the policy was trained with")
    parser.add_argument("--players", help="default: ppo_icm, plain, random, nothing and every scripted player")
    parser.add_argument("--also", action="append", default=[], metavar="NAME=POLICY",
                        help="another trained policy to play (greedy) under this name; may be repeated")
    parser.add_argument("--also-home", action="append", default=[], metavar="NAME=POLICY",
                        help="the same, with the home guard on whatever the policy was trained with")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--out", help="write the rows as JSON here")
    args = parser.parse_args(argv)
    extra = load_player(args.policy).extra
    spec = args.env or extra["env"]
    delay = extra["delay"] if args.delay is None else args.delay
    names = args.players.split(",") if args.players else default_players(extra, spec)
    entries = [(name, name, args.policy) for name in names]
    for flag, kind, given in (("--also", "ppo_icm", args.also), ("--also-home", "ppo_icm_home", args.also_home)):
        for extra_policy in given:
            label, _, path = extra_policy.partition("=")
            if not label or not path or label in [e[0] for e in entries]:
                raise ValueError(f"{flag} takes NAME=POLICY with a name no other player has")
            entries.insert(1, (label, kind, path))
    for _, name, path in entries:
        player(name, path, spec)     # an unknown player is an error here, not forty crashed episodes
    jobs = [(label, name, path, spec, seed, delay) for label, name, path in entries for seed in seed_range(args.seeds)]
    with Pool(args.workers) as pool:
        rows = pool.map(episode, jobs, chunksize=1)
    if args.out:
        with open(args.out, "w") as handle:
            json.dump({"env": spec, "delay": delay, "seeds": args.seeds, "policy": extra, "rows": rows}, handle)
    print(f"{spec}, delay {delay}, seeds {args.seeds}")
    print(table(rows))
    return rows


if __name__ == "__main__":
    main()
