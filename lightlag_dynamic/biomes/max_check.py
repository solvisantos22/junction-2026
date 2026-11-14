"""Players on the max env (maxenv.py), compared on the same seeds (needs numpy).

    python3 -m lightlag_dynamic.biomes.max_check --seeds 2600-2639
    python3 -m lightlag_dynamic.biomes.max_check --seeds 0-59 --players max_navigator,fused --delay 3

Prints each player's mean share of the available value, deaths and returns home, and its paired
difference to the first player with a 95% bootstrap interval over the seeds.
"""

import argparse
import json
import random
import statistics
from multiprocessing import Pool

from .maxenv import make_max_env

DEFAULT_PLAYERS = ("max_navigator", "fused", "c37", "kf_mpc", "blind")


def players():
    from lightlag_dynamic.controllers import POLICIES
    from lightlag_dynamic.manh_controllers import controllers as zoo

    from .max_players import max_navigator
    from .nogps_players import navigator
    c37 = next(name for name in zoo.REGISTRY if zoo.number(name) == 37)
    return {"max_navigator": lambda tools, env: max_navigator()(tools).run(),
            "fused": lambda tools, env: navigator()(tools).run(),
            "c37": zoo.REGISTRY[c37]["play"],
            "kf_mpc": lambda tools, env: POLICIES["kf_mpc"](tools),
            "blind": lambda tools, env: POLICIES["open_loop"](tools)}


def episode(job):
    """One episode: {player, seed, delay, share, alive, at_base, crash}."""
    from lightlag_dynamic.tools import PublicTools
    name, seed, delay = job
    env = make_max_env(seed=seed, delay=delay)
    crash = None
    try:
        players()[name](PublicTools(env), env)
    except Exception as error:  # a player's error is a result, not a harness failure
        crash = f"{type(error).__name__}: {error}"[:160]
    while not env.advance(5)["episode_complete"]:
        pass
    result = env.evaluate()
    return {"player": name, "seed": seed, "delay": delay,
            "share": result["raw_score"] / result["max_available_value"] if result["max_available_value"] else 0.0,
            "alive": result["alive"], "at_base": result["at_base"], "crash": crash}


def paired(a, b, draws=10000, seed=1):
    """Mean of a - b over common seeds, with a 95% bootstrap interval (shares, not percent)."""
    seeds = sorted(set(a) & set(b))
    d = [a[s] - b[s] for s in seeds]
    rng = random.Random(seed)
    means = sorted(statistics.fmean(rng.choice(d) for _ in d) for _ in range(draws))
    return statistics.fmean(d), means[int(0.025 * draws)], means[int(0.975 * draws)]


def table(rows):
    names = list(dict.fromkeys(r["player"] for r in rows))
    shares = {n: {r["seed"]: r["share"] for r in rows if r["player"] == n} for n in names}
    lines = []
    for n in names:
        rs = [r for r in rows if r["player"] == n]
        line = (f"{n:14s} {100 * statistics.fmean(shares[n].values()):5.1f}%  dead {sum(not r['alive'] for r in rs)}"
                f"/{len(rs)}  home {sum(bool(r['alive'] and r['at_base']) for r in rs)}  crashes {sum(bool(r['crash']) for r in rs)}")
        if n != names[0]:
            m, lo, hi = paired(shares[names[0]], shares[n])
            line += f"  {names[0]} - {n}: {100 * m:+.1f} (95% {100 * lo:+.1f} to {100 * hi:+.1f})"
        lines.append(line)
    return "\n".join(lines)


def seed_range(text):
    return [s for part in text.split(",") for s in range(int(part.split("-")[0]), int(part.split("-")[-1]) + 1)]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seeds", default="0-19", help="e.g. 2600-2639 or 0-59,1100-1299")
    parser.add_argument("--delay", type=int, default=3)
    parser.add_argument("--players", default=",".join(DEFAULT_PLAYERS))
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--out", help="write the rows as JSON here")
    args = parser.parse_args(argv)
    jobs = [(n, s, args.delay) for n in args.players.split(",") for s in seed_range(args.seeds)]
    with Pool(args.workers) as pool:
        rows = pool.map(episode, jobs, chunksize=1)
    if args.out:
        with open(args.out, "w") as handle:
            json.dump(rows, handle)
    print(table(rows))
    return rows


if __name__ == "__main__":
    main()
