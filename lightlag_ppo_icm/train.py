"""Train the PPO + ICM tester on one environment (NumPy only; rollouts on several processes).

    python3 -m lightlag_ppo_icm.train --env max --out lightlag_ppo_icm/runs/max
    python3 -m lightlag_ppo_icm.train --env rush --updates 150 --out lightlag_ppo_icm/runs/rush
    python3 -m lightlag_ppo_icm.train --env max --int-coef 0 --out lightlag_ppo_icm/runs/max-plain   # PPO alone

Every episode is a new map: the training seeds are drawn from --train-seeds, so the agent
cannot memorise a mission. Every --eval-every updates the greedy policy plays the development
seeds; the best one so far is kept as best.npz and its actor alone as policy.npz, the file the
check and the player read. log.jsonl holds one line per update.
"""

import argparse
import json
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from .agent import Agent, AgentConfig, Policy
from .envs import make_env, run_episode
from .task import SAMPLE, WAIT, TaskConfig

TRAIN_SEEDS = (200000, 299999)
DEV_SEEDS = (300000, 300063)


def collect(job):
    """A worker's share of the rollouts: complete episodes played with the given actor."""
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

        episode = run_episode(job["env"], seed, choose, job["delay"], config, record=not job["greedy"])
        if not job["greedy"]:
            episode.update(obs=np.asarray(obs, dtype=np.float32), actions=np.asarray(actions, dtype=np.int16),
                           logp=np.asarray(logps, dtype=np.float32))
        out.append(episode)
    return out


def rollouts(pool, workers, actor, task, env, delay, episodes, greedy=False):
    """Episodes [(seed, sampling seed), ...] spread over the workers; results in the same order."""
    chunks = [episodes[i::workers] for i in range(workers) if episodes[i::workers]]
    jobs = [{"actor": actor, "task": task.to_dict(), "env": env, "delay": delay, "episodes": chunk,
             "greedy": greedy} for chunk in chunks]
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


def train(env="max", out="lightlag_ppo_icm/runs/max", updates=300, episodes=256, workers=8, delay=3, seed=0,
          int_coef=0.5, int_final=0.1, lr=3e-4, lr_final=0.3, icm_lr=1e-3, ent_coef=0.01, hidden=128, headings=16,
          wait_bias=4.0, sample_bias=2.0, eval_every=10, train_seeds=TRAIN_SEEDS, dev_seeds=DEV_SEEDS,
          max_minutes=None, quiet=False, metres="auto"):
    """Train once and return the summary that is also written to <out>/summary.json."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if (out / "log.jsonl").exists():
        raise ValueError(f"{out} already holds a run; give a new folder")
    task = TaskConfig(headings=headings, metres=drive_lengths(env, delay) if metres == "auto" else tuple(metres))
    agent = Agent(AgentConfig(obs_dim=task.obs_dim, n_actions=task.n_actions, hidden=hidden, lr=lr,
                              icm_lr=icm_lr, ent_coef=ent_coef, int_coef=int_coef, seed=seed,
                              icm_inputs=task.curiosity_inputs))
    # Where the untrained policy starts: with these it waits about half the time and tries a sample
    # now and then, instead of spending 96% of its commands on drives and the battery with them.
    agent.actor.params[-1][WAIT] = wait_bias
    agent.actor.params[-1][SAMPLE] = sample_bias
    rng = np.random.default_rng(seed)
    dev = [(s, 0) for s in range(dev_seeds[0], dev_seeds[1] + 1)]
    settings = {"env": env, "delay": delay, "updates": updates, "episodes": episodes, "seed": seed,
                "int_coef": int_coef, "int_final": int_final, "lr": lr, "lr_final": lr_final, "icm_lr": icm_lr,
                "ent_coef": ent_coef, "hidden": hidden, "wait_bias": wait_bias, "sample_bias": sample_bias,
                "train_seeds": list(train_seeds), "dev_seeds": list(dev_seeds)}
    extra = {"task": task.to_dict(), "env": env, "delay": delay, "settings": settings}
    best, started, steps, done = {"share": -1.0, "update": 0}, time.time(), 0, 0
    pool = Pool(workers) if workers > 1 else None
    try:
        with open(out / "log.jsonl", "a") as log:
            for update in range(1, updates + 1):
                progress = (update - 1) / max(1, updates - 1)
                now_int = int_coef * (1.0 - (1.0 - int_final) * progress)
                seeds = rng.integers(train_seeds[0], train_seeds[1] + 1, size=episodes)
                draws = rng.integers(0, 2 ** 62, size=episodes)
                played = rollouts(pool, workers, agent.actor.state(), task, env, delay,
                                  [(int(s), int(d)) for s, d in zip(seeds, draws)])
                batch, stats = agent.prepare(played, now_int)
                stats.update(agent.update(batch, 1.0 - (1.0 - lr_final) * progress))
                steps += stats["steps"]    # decisions played so far, all updates together
                stats["batch_steps"] = stats.pop("steps")
                row = {"update": update, "steps": steps, "minutes": round((time.time() - started) / 60.0, 2),
                       "int_coef": round(now_int, 4), **{f"train_{k}": v for k, v in summary(played).items()},
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
                if not quiet:
                    line = (f"update {update:4d}  steps {steps / 1e6:5.2f}M  {row['minutes']:6.1f} min  "
                            f"train {100 * row['train_share']:5.1f}%  alive {100 * row['train_alive']:3.0f}%  "
                            f"home {100 * row['train_home']:3.0f}%  samples {row['train_samples']:.2f}  "
                            f"entropy {row['entropy']:.2f}  curiosity {row['int_raw']:.4f}")
                    if "dev_share" in row:
                        line += f"  | dev {100 * row['dev_share']:5.1f}% (best {100 * best['share']:.1f}% at {best['update']})"
                    print(line, flush=True)
                if out_of_time:
                    break
    finally:
        if pool is not None:
            pool.close()
            pool.join()
    result = {"settings": settings, "updates_done": done, "steps": steps,
              "minutes": round((time.time() - started) / 60.0, 2), "best_dev": best}
    (out / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


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
    parser.add_argument("--updates", type=int, default=300)
    parser.add_argument("--episodes", type=int, default=256, help="episodes per update")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--delay", type=int, default=3)
    parser.add_argument("--seed", type=int, default=0, help="of the network weights and the training draws")
    parser.add_argument("--int-coef", type=float, default=0.5, help="weight of the curiosity reward; 0: plain PPO")
    parser.add_argument("--int-final", type=float, default=0.1, help="share of it left at the last update")
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--lr-final", type=float, default=0.3)
    parser.add_argument("--icm-lr", type=float, default=1e-3)
    parser.add_argument("--ent-coef", type=float, default=0.01)
    parser.add_argument("--hidden", type=int, default=128)
    parser.add_argument("--headings", type=int, default=16)
    parser.add_argument("--metres", type=lambda text: text if text == "auto" else tuple(float(m) for m in text.split(",")),
                        default="auto", help="drive lengths as shares of the longest drive allowed, e.g. 0.25,0.5,1; "
                                             "auto: 2/3, 4/3 and 8/3 of the sampling radius")
    parser.add_argument("--wait-bias", type=float, default=4.0, help="starting logit of wait (drives start at 0)")
    parser.add_argument("--sample-bias", type=float, default=2.0, help="starting logit of sample")
    parser.add_argument("--eval-every", type=int, default=10)
    parser.add_argument("--train-seeds", type=seed_pair, default=TRAIN_SEEDS, help="e.g. 200000-299999")
    parser.add_argument("--dev-seeds", type=seed_pair, default=DEV_SEEDS)
    parser.add_argument("--max-minutes", type=float, help="stop after the update that passes this")
    args = parser.parse_args(argv)
    result = train(**vars(args))
    print(json.dumps(result["best_dev"]))
    return result


if __name__ == "__main__":
    main()
