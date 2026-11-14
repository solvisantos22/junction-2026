"""Train the PPO + ICM tester on one environment (NumPy only; rollouts on several processes).

    python3 -m lightlag_ppo_icm.train --env max --out lightlag_ppo_icm/runs/max
    python3 -m lightlag_ppo_icm.train --env rush --updates 150 --out lightlag_ppo_icm/runs/rush
    python3 -m lightlag_ppo_icm.train --env max --int-coef 0 --out lightlag_ppo_icm/runs/max-plain   # PPO alone
    python3 -m lightlag_ppo_icm.train --env max --home-guard --out lightlag_ppo_icm/runs/max-home-guard
    python3 -m lightlag_ppo_icm.train --env traverse --targets --int-coef 0 --out lightlag_ppo_icm/runs/traverse

Every episode is a new map: the training seeds are drawn from --train-seeds, so the agent
cannot memorise a mission. Every --eval-every updates the greedy policy plays the development
seeds; the best one so far is kept as best.npz and its actor alone as policy.npz, the file the
check and the player read. log.jsonl holds one line per update. With --home-guard the agent
trains and plays with the home guard of task.py on (flat 40 m family only); the policy file
records it, so the check and the player switch it on too.

With --targets (traverse only) the agent picks the next target or home and Kristján's frozen pilot
drives (targets.py); the training and development worlds then default to the ones claimed for it,
and a range that touches worlds other work keeps is refused. modal_train.py runs the same training
with the rollouts on Modal.
"""

import argparse
import json
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from .agent import Agent, AgentConfig, Policy
from .envs import make_env, run_episode, run_target_episode
from .targets import DEV_WORLDS, TRAIN_WORLDS, TargetConfig, check_worlds, is_target_config
from .task import SAMPLE, WAIT, TaskConfig

TRAIN_SEEDS = (200000, 299999)
DEV_SEEDS = (300000, 300063)


def collect(job):
    """A worker's share of the rollouts: complete episodes played with the given actor."""
    if is_target_config(job["task"]):
        return collect_targets(job)
    policy = Policy(job["actor"])
    config = TaskConfig.from_dict(job["task"])
    out = []
    for seed, draw in job["episodes"]:
        rng = None if job["greedy"] else np.random.default_rng(draw)
        obs, actions, logps = [], [], []

        def choose(observation):
            action, logp = policy.act(observation, rng)
            obs.append(observation)
            actions.append(action)
            logps.append(logp)
            return action

        episode = run_episode(job["env"], seed, choose, job["delay"], config, record=not job["greedy"],
                              home_pull=job.get("home_pull", 0.0))
        if not job["greedy"]:
            episode.update(obs=np.asarray(obs, dtype=np.float32), actions=np.asarray(actions, dtype=np.int16),
                           logp=np.asarray(logps, dtype=np.float32))
        out.append(episode)
    return out


def collect_targets(job):
    """collect() for the target mode: the chooser also gets the mask, and the masks are kept."""
    policy = Policy(job["actor"])
    config = TargetConfig.from_dict(job["task"])
    out = []
    for seed, draw in job["episodes"]:
        rng = None if job["greedy"] else np.random.default_rng(draw)
        obs, masks, actions, logps = [], [], [], []

        def choose(observation, mask):
            action, logp = policy.act(observation, rng, mask)
            obs.append(observation)
            masks.append(mask)
            actions.append(action)
            logps.append(logp)
            return action

        episode = run_target_episode(job["env"], seed, choose, config, record=not job["greedy"])
        if not job["greedy"]:
            episode.update(obs=np.asarray(obs, dtype=np.float32).reshape(len(obs), config.obs_dim),
                           masks=np.asarray(masks, dtype=bool).reshape(len(masks), config.n_actions),
                           actions=np.asarray(actions, dtype=np.int16), logp=np.asarray(logps, dtype=np.float32))
        out.append(episode)
    return out


def rollouts(pool, workers, actor, task, env, delay, episodes, greedy=False, home_pull=0.0):
    """Episodes [(seed, sampling seed), ...] spread over the workers; results in the same order."""
    chunks = [episodes[i::workers] for i in range(workers) if episodes[i::workers]]
    jobs = [{"actor": actor, "task": task.to_dict(), "env": env, "delay": delay, "episodes": chunk,
             "greedy": greedy, "home_pull": home_pull} for chunk in chunks]
    results = pool.map(collect, jobs, chunksize=1) if pool is not None else [collect(job) for job in jobs]
    by_key = {}
    for chunk, played in zip(chunks, results):
        for key, episode in zip(chunk, played):
            by_key[key] = episode
    return [by_key[key] for key in episodes]


def summary(episodes):
    return {"share": float(np.mean([e["share"] for e in episodes])),
            "alive": float(np.mean([e["alive"] for e in episodes])),
            "home": float(np.mean([e["alive"] and e["at_base"] for e in episodes])),
            "samples": float(np.mean([e["samples"] for e in episodes]))}


def train(env="max", out="lightlag_ppo_icm/runs/max", updates=600, episodes=128, workers=8, delay=3, seed=0,
          int_coef=0.5, int_final=0.1, lr=3e-4, lr_final=0.3, icm_lr=1e-3, ent_coef=0.005, ent_final=1.0,
          hidden=128, headings=16, wait_bias=4.0, sample_bias=2.0, eval_every=20, train_seeds=None, dev_seeds=None,
          max_minutes=None, quiet=False, metres="auto", home_pull=0.0, home_guard=False,
          targets=False, slots=12, home_bias=-4.0, gamma=None, pool=None, callback=None, resume=False):
    """Train once and return the summary that is also written to <out>/summary.json. `pool`: anything
    with map(function, jobs, chunksize) to play the rollouts on (modal_train.py passes Modal's); by
    default a process pool of `workers`. `callback(update, row)` runs after every update's log line.
    With `resume`, a folder that already holds a run continues from its last checkpoint (last.npz,
    written at every development check): the log is cut back to it and the same training draws
    follow. The optimiser's moments and the minibatch order start afresh. The entropy bonus falls
    linearly from `ent_coef` to `ent_final` times it by the last update, as the learning rate does
    to `lr_final` times its own."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    resumed = None
    if (out / "log.jsonl").exists():
        if not resume:
            raise ValueError(f"{out} already holds a run; give a new folder")
        resumed = resume_point(out)
        if resumed is None:
            (out / "log.jsonl").unlink()     # no checkpoint yet: start over
    if targets:
        if env != "traverse":
            raise ValueError("--targets is built for the traverse (normal map) only")
        train_seeds, dev_seeds = tuple(train_seeds or TRAIN_WORLDS), tuple(dev_seeds or DEV_WORLDS)
        check_worlds(*train_seeds)
        check_worlds(*dev_seeds)
        task = TargetConfig(slots=slots)
    else:
        train_seeds, dev_seeds = tuple(train_seeds or TRAIN_SEEDS), tuple(dev_seeds or DEV_SEEDS)
        lengths = drive_lengths(env, delay) if metres == "auto" else tuple(metres)
        task = TaskConfig(headings=headings, metres=lengths, home_guard=home_guard)
    extra_config = {} if gamma is None else {"gamma": gamma}
    agent = Agent(AgentConfig(obs_dim=task.obs_dim, n_actions=task.n_actions, hidden=hidden, lr=lr,
                              icm_lr=icm_lr, ent_coef=ent_coef, int_coef=int_coef, seed=seed,
                              icm_inputs=task.curiosity_inputs, **extra_config))
    if targets:
        # Where the untrained policy starts: home is final, so it starts unlikely (about 0.2% a choice
        # against 12 open slots), and the agent learns when to take it.
        agent.actor.params[-1][task.home_action] = home_bias
    else:
        # Where the untrained policy starts: with these it waits about half the time and tries a sample
        # now and then, instead of spending 96% of its commands on drives and the battery with them.
        agent.actor.params[-1][WAIT] = wait_bias
        agent.actor.params[-1][SAMPLE] = sample_bias
    rng = np.random.default_rng(seed)
    first = 1
    if resumed is not None:
        agent, last_update, last_steps, last_best, last_minutes = resumed
        for _ in range(last_update):     # the draws the first attempt made, so the same ones follow
            rng.integers(train_seeds[0], train_seeds[1] + 1, size=episodes)
            rng.integers(0, 2 ** 62, size=episodes)
        first = last_update + 1
    dev = [(s, 0) for s in range(dev_seeds[0], dev_seeds[1] + 1)]
    settings = {"env": env, "delay": delay, "updates": updates, "episodes": episodes, "seed": seed,
                "int_coef": int_coef, "int_final": int_final, "lr": lr, "lr_final": lr_final, "icm_lr": icm_lr,
                "ent_coef": ent_coef, "ent_final": ent_final, "hidden": hidden, "wait_bias": wait_bias, "sample_bias": sample_bias,
                "home_pull": home_pull, "home_guard": home_guard,
                "metres": list(task.metres) if not targets else None, "targets": targets,
                "slots": slots if targets else None, "home_bias": home_bias if targets else None,
                "gamma": agent.config.gamma, "train_seeds": list(train_seeds), "dev_seeds": list(dev_seeds)}
    extra = {"task": task.to_dict(), "env": env, "delay": delay, "settings": settings}
    best, started, steps, done = {"share": -1.0, "update": 0}, time.time(), 0, 0
    if resumed is not None:
        if agent.config.obs_dim != task.obs_dim or agent.config.n_actions != task.n_actions:
            raise ValueError(f"the checkpoint in {out} is for another task")
        best, steps, done, started = last_best, last_steps, first - 1, time.time() - 60.0 * last_minutes
    own_pool = pool is None and workers > 1
    if own_pool:
        pool = Pool(workers)
    try:
        with open(out / "log.jsonl", "a") as log:
            for update in range(first, updates + 1):
                progress = (update - 1) / max(1, updates - 1)
                now_int = int_coef * (1.0 - (1.0 - int_final) * progress)
                agent.config.ent_coef = ent_coef * (1.0 - (1.0 - ent_final) * progress)
                seeds = rng.integers(train_seeds[0], train_seeds[1] + 1, size=episodes)
                draws = rng.integers(0, 2 ** 62, size=episodes)
                played = rollouts(pool, workers, agent.actor.state(), task, env, delay,
                                  [(int(s), int(d)) for s, d in zip(seeds, draws)], home_pull=home_pull)
                batch, stats = agent.prepare(played, now_int)
                stats.update(agent.update(batch, 1.0 - (1.0 - lr_final) * progress))
                steps += stats["steps"]    # decisions played so far, all updates together
                stats["batch_steps"] = stats.pop("steps")
                row = {"update": update, "steps": steps, "minutes": round((time.time() - started) / 60.0, 2),
                       "int_coef": round(now_int, 4), "ent_coef": round(agent.config.ent_coef, 5),
                       **{f"train_{k}": v for k, v in summary(played).items()},
                       **stats}
                done = update
                out_of_time = max_minutes is not None and (time.time() - started) / 60.0 >= max_minutes
                if update % eval_every == 0 or update == updates or out_of_time:
                    score = summary(rollouts(pool, workers, agent.actor.state(), task, env, delay, dev, greedy=True))
                    row.update({f"dev_{k}": v for k, v in score.items()})
                    agent.save(out / "last.npz", {**extra, "update": update, "dev": score})
                    if score["share"] > best["share"]:
                        best = {**score, "update": update}
                        agent.save(out / "best.npz", {**extra, "update": update, "dev": score})
                        save_policy(out / "policy.npz", agent, {**extra, "update": update, "dev": score})
                log.write(json.dumps({k: (round(v, 5) if isinstance(v, float) else v) for k, v in row.items()}) + "\n")
                log.flush()
                if callback is not None:
                    callback(update, row)
                if not quiet:
                    line = (f"update {update:4d}  steps {steps / 1e6:5.2f}M  {row['minutes']:6.1f} min  "
                            f"train {100 * row['train_share']:5.1f}%  alive {100 * row['train_alive']:3.0f}%  "
                            f"home {100 * row['train_home']:3.0f}%  samples {row['train_samples']:.2f}  "
                            f"entropy {row['entropy']:.2f}  curiosity {row['int_raw']:.4f}")
                    if "dev_share" in row:
                        line += (f"  | dev {100 * row['dev_share']:5.1f}% "
                                 f"(best {100 * best['share']:.1f}% at {best['update']})")
                    print(line, flush=True)
                if out_of_time:
                    break
    finally:
        if own_pool:
            pool.close()
            pool.join()
    result = {"settings": settings, "updates_done": done, "steps": steps,
              "minutes": round((time.time() - started) / 60.0, 2), "best_dev": best}
    (out / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def resume_point(out):
    """(agent, update, steps, best, minutes) at the last checkpoint of a run folder, with its log cut
    back to that update; None when it has no checkpoint yet."""
    if not (out / "last.npz").exists():
        return None
    agent, extra = Agent.load(out / "last.npz")
    update = int(extra["update"])
    rows = [json.loads(line) for line in (out / "log.jsonl").read_text().splitlines() if line.strip()]
    rows = [row for row in rows if row["update"] <= update]
    (out / "log.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    best = {"share": -1.0, "update": 0}
    if (out / "best.npz").exists():
        _, best_extra = Agent.load(out / "best.npz")
        best = {**best_extra["dev"], "update": best_extra["update"]}
    return agent, update, (rows[-1]["steps"] if rows else 0), best, (rows[-1]["minutes"] if rows else 0.0)


def drive_lengths(env, delay=3):
    """Drive lengths that fit the environment, as shares of its longest drive: 2/3, 4/3 and 8/3 of the
    sampling radius, capped at the longest drive. An agent whose shortest drive is longer than the
    sampling disc is wide can hardly land on a target (on `rush`, where a drive may be 5 m and the
    disc is 1.5 m across, a quarter, a half and a full drive learned almost nothing)."""
    rules = make_env(env, TRAIN_SEEDS[0], delay).rules()
    radius, longest = float(rules["target_radius"]), float(rules["max_metres_per_drive"])
    lengths = sorted({min(1.0, round(k * radius / longest, 4)) for k in (2.0 / 3.0, 4.0 / 3.0, 8.0 / 3.0)})
    return tuple(lengths)


def save_policy(path, agent, extra):
    """The actor alone, in single precision: the small file a player needs."""
    arrays = {f"actor_{i}": p.astype(np.float32) for i, p in enumerate(agent.actor.params)}
    meta = {"format": "lightlag-ppo-icm-v1", "extra": extra}
    np.savez(path, meta=np.array(json.dumps(meta)), **arrays)


def seed_pair(text):
    low, _, high = text.partition("-")
    return int(low), int(high or low)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--env", default="max", help="max, max_rocks, a profile (rush, rush_noisy, ...), "
                                                     "profile@biome, traverse, traverse_max")
    parser.add_argument("--out", required=True, help="a new folder for the log and the checkpoints")
    parser.add_argument("--updates", type=int, default=600)
    parser.add_argument("--episodes", type=int, default=128, help="episodes per update")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--delay", type=int, default=3)
    parser.add_argument("--seed", type=int, default=0, help="of the network weights and the training draws")
    parser.add_argument("--int-coef", type=float, default=0.5, help="weight of the curiosity reward; 0: plain PPO")
    parser.add_argument("--int-final", type=float, default=0.1, help="share of it left at the last update")
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--lr-final", type=float, default=0.3)
    parser.add_argument("--icm-lr", type=float, default=1e-3)
    parser.add_argument("--ent-coef", type=float, default=0.005, help="weight of the entropy bonus")
    parser.add_argument("--ent-final", type=float, default=1.0, help="share of it left at the last update; 1: constant")
    parser.add_argument("--hidden", type=int, default=128)
    parser.add_argument("--headings", type=int, default=16)
    parser.add_argument("--metres", type=lambda text: text if text == "auto" else tuple(float(m) for m in text.split(",")),
                        default="auto", help="drive lengths as shares of the longest drive allowed, e.g. 0.25,0.5,1; "
                                             "auto: 2/3, 4/3 and 8/3 of the sampling radius")
    parser.add_argument("--wait-bias", type=float, default=4.0, help="starting logit of wait (drives start at 0)")
    parser.add_argument("--sample-bias", type=float, default=2.0, help="starting logit of sample")
    parser.add_argument("--home-pull", type=float, default=0.0, metavar="K",
                        help="pay what being home is worth along the way: a potential K times the bonus for "
                             "being home, so the pieces still add up to the official score; 0: off")
    parser.add_argument("--home-guard", action="store_true",
                        help="keep the energy and time to get home, and drive home when they run out "
                             "(task.py; flat 40 m family only)")
    parser.add_argument("--targets", action="store_true",
                        help="traverse only: pick the next target or home; Kristján's pilot drives (targets.py)")
    parser.add_argument("--slots", type=int, default=12, help="with --targets: candidate targets per choice")
    parser.add_argument("--home-bias", type=float, default=-4.0, help="with --targets: starting logit of home")
    parser.add_argument("--gamma", type=float, help="discount per decision (default: the agent's, 0.995)")
    parser.add_argument("--eval-every", type=int, default=20)
    parser.add_argument("--train-seeds", type=seed_pair, help="e.g. 200000-299999 (default: the mode's own)")
    parser.add_argument("--dev-seeds", type=seed_pair)
    parser.add_argument("--max-minutes", type=float, help="stop after the update that passes this")
    parser.add_argument("--resume", action="store_true", help="continue a run folder from its last checkpoint")
    args = parser.parse_args(argv)
    result = train(**vars(args))
    print(json.dumps(result["best_dev"]))
    return result


if __name__ == "__main__":
    main()
