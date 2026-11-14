"""Players on Kristján's three-mission campaign, scored as the Harbor task scores it.

    python3 -m lightlag_ppo_icm.campaign --policy lightlag_ppo_icm/policies/traverse-targets.npz \
        --players ppo_icm,pilot,greedy,nearest_targets,random_targets

The campaign is `harbor/lightlag-traverse-campaign/`: worlds 2027, 2028 and 2029, one 420-tick
mission each, played one after another with no reset (lightlag_traverse/campaign.py, the same
code the task's simulator runs). The score is the value earned in all three missions over the
value of every target of all of them. The reference pilot plays it with `fly_campaign`, a fresh
pilot per mission, as in the task's own solution; a target-mode policy plays it with a fresh
TargetPilot per mission. These worlds are the submission's: play a policy here only once it is
frozen, as a showcase, never to choose between policies.
"""

import argparse
import json
from multiprocessing import Pool

WORLDS = (2027, 2028, 2029)


def campaign_player(name, policy):
    """A player of the whole campaign, called with the five tools."""
    if name in ("pilot", "greedy"):
        from lightlag_traverse.pilot import fly_campaign
        options = {} if name == "pilot" else {"route": "greedy"}
        return lambda tools: fly_campaign(tools, options)
    from .player import cluster_target_player, load_player, nearest_target_player, random_target_player
    if name == "ppo_icm":
        play = load_player(policy)
        if play.extra["task"].get("mode") != "targets":
            raise ValueError("only a target-mode policy can play the campaign")
        return lambda tools: play(tools)
    if name == "nearest_targets":
        return lambda tools: nearest_target_player()(tools)
    if name == "random_targets":
        return lambda tools: random_target_player()(tools)
    if name == "cluster_targets":
        return lambda tools: cluster_target_player()(tools)
    raise ValueError(f"no campaign player {name!r}: use ppo_icm, pilot, greedy, nearest_targets, cluster_targets, "
                     "random_targets")


def play_campaign(job):
    label, name, policy, worlds = job
    from lightlag_traverse.campaign import TraverseCampaign
    from .envs import FiveTools
    campaign = TraverseCampaign(tuple(worlds))
    campaign_player(name, policy)(FiveTools(campaign))
    campaign.run_out()
    result = campaign.evaluate()
    return {"player": label, "score": result["raw_score"] / result["max_available_value"],
            "missions": [{"seed": m["seed"], "reward": m["reward"], "alive": m["alive"], "at_base": m["at_base"]}
                         for m in result["missions"]],
            "raw_score": result["raw_score"], "max_available_value": result["max_available_value"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--policy", help="a target-mode policy.npz (for the ppo_icm player)")
    parser.add_argument("--players", default="ppo_icm,pilot,greedy,nearest_targets,random_targets")
    parser.add_argument("--also", action="append", default=[], metavar="NAME=POLICY",
                        help="another target-mode policy under this name; may be repeated")
    parser.add_argument("--worlds", default=",".join(str(w) for w in WORLDS))
    parser.add_argument("--out", help="write the results as JSON here")
    args = parser.parse_args(argv)
    worlds = [int(w) for w in args.worlds.split(",")]
    jobs = [(name, name, args.policy, worlds) for name in args.players.split(",")]
    for item in args.also:
        label, _, path = item.partition("=")
        jobs.insert(1, (label, "ppo_icm", path, worlds))
    with Pool(min(8, len(jobs))) as pool:
        results = pool.map(play_campaign, jobs, chunksize=1)
    if args.out:
        with open(args.out, "w") as handle:
            json.dump({"worlds": worlds, "policy": args.policy, "results": results}, handle, indent=1)
    print(f"campaign on worlds {', '.join(map(str, worlds))}")
    for r in results:
        missions = "  ".join(f"{m['seed']}: {m['reward']:.3f} {'home' if m['at_base'] else ('away' if m['alive'] else 'lost')}"
                             for m in r["missions"])
        print(f"{r['player']:<16} {r['score']:.3f}   {missions}")
    return results


if __name__ == "__main__":
    main()
