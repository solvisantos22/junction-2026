"""The target mode of the PPO + ICM agent, trained and checked on Modal.

    pip install modal && modal setup        # once, with your own Modal workspace (it bills that workspace)
    modal run --detach lightlag_ppo_icm/modal_train.py::fit --out traverse-targets-ppo --int-coef 0
    modal volume get lightlag-ppo-icm-runs traverse-targets-ppo lightlag_ppo_icm/runs/
    modal run lightlag_ppo_icm/modal_train.py::check --policy traverse-targets-ppo/policy.npz \
        --seeds 430000-430299 --players ppo_icm,pilot,greedy,nearest_targets,random_targets --out rows.json

`fit` runs train.train() in one container (the learner, 2 cores) and sends its rollouts
to up to MAX_CONTAINERS one-core containers, one mission per call: a target-mode mission takes a
few seconds, so an update of 128 missions on 64 containers, two missions each, takes about as long
as the slowest pair. Containers stay up (and billed) while the learner updates between rollouts, so
more of them cost more without being faster: with 100, a 200-update run cost $2.70 (PPO alone)
and $5.20 (with curiosity, whose learner is slower), measured on 14 November. The run folder
(log.jsonl, best.npz, policy.npz, summary.json) lives in the Modal volume `lightlag-ppo-icm-runs`,
committed after every development check, so a run that stops early keeps its best policy, and
`fit` with the same `--out` continues it from there.

`check` plays every player on every world, one mission per call, and prints the same table as
check.py. Policies are read from the volume (paths inside it); `--upload` puts a local policy file
there first. Model API calls: none. Stopping the local `modal run` may not stop its app:
`modal app list`, then `modal app stop <app id>`.
"""

import json
from pathlib import Path

import modal

MAX_CONTAINERS = 64
VOLUME = "lightlag-ppo-icm-runs"

image = (modal.Image.debian_slim(python_version="3.12")
         .pip_install("numpy==2.2.6")
         .add_local_python_source("lightlag", "lightlag_traverse", "lightlag_mcp", "lightlag_dynamic",
                                  "lightlag_ppo_icm"))
app = modal.App("lightlag-ppo-icm-targets", image=image)
runs = modal.Volume.from_name(VOLUME, create_if_missing=True)


@app.function(cpu=1.0, memory=1536, timeout=1200, max_containers=MAX_CONTAINERS, retries=2)
def rollout(job: dict) -> list:
    from lightlag_ppo_icm.train import collect
    return collect(job)


class ModalPool:
    """What train() needs of a process pool, map(function, jobs, chunksize), with every job played
    by `rollout` on Modal (the function given is train.collect, which `rollout` runs remotely)."""

    def map(self, function, jobs, chunksize=1):
        return list(rollout.map(jobs, order_outputs=True))


# The learner holds the whole run, so it is not preemptible; if it is restarted anyway, it resumes
# from its last checkpoint in the volume. Rollout containers may be preempted: their missions are
# simply played again (retries).
@app.function(cpu=2.0, memory=4096, timeout=6 * 3600, volumes={"/runs": runs}, nonpreemptible=True)
def learn(settings: dict) -> dict:
    from lightlag_ppo_icm.train import train

    def commit(update, row):
        if "dev_share" in row:
            runs.commit()

    out = Path("/runs") / settings.pop("out")
    runs.reload()
    result = train(out=str(out), pool=ModalPool(), callback=commit, resume=True, **settings)
    runs.commit()
    return result


@app.function(cpu=1.0, memory=1536, timeout=1800, max_containers=MAX_CONTAINERS, retries=1,
              volumes={"/runs": runs})
def episode(job: list) -> dict:
    from lightlag_ppo_icm.check import episode as play
    label, name, policy, spec, seed, delay = job
    return play((label, name, f"/runs/{policy}" if policy else policy, spec, seed, delay))


@app.local_entrypoint()
def fit(out: str, updates: int = 200, episodes: int = 128, int_coef: float = 0.0, seed: int = 0,
        eval_every: int = 10, max_minutes: float = 240.0, hidden: int = 128, slots: int = 12,
        ent_coef: float = 0.01, ent_final: float = 1.0, lr: float = 3e-4, gamma: float = 0.999):
    """Train the target mode on the traverse; the run folder ends up in the volume under `out`."""
    settings = dict(env="traverse", targets=True, out=out, updates=updates, episodes=episodes,
                    workers=episodes, int_coef=int_coef, seed=seed, eval_every=eval_every,
                    max_minutes=max_minutes, hidden=hidden, slots=slots, ent_coef=ent_coef, ent_final=ent_final,
                    lr=lr, gamma=gamma)
    result = learn.remote(settings)
    print(json.dumps(result, indent=2))


@app.local_entrypoint()
def check(policy: str, seeds: str, players: str = "ppo_icm,pilot,greedy,nearest_targets,random_targets",
          also: str = "", out: str = "", upload: str = ""):
    """Every player on every world, paired; `also` is NAME=PATH[,NAME=PATH] of more policies in the volume."""
    from lightlag_dynamic.biomes.max_check import seed_range, table

    if upload:
        with runs.batch_upload(force=True) as batch:
            batch.put_file(upload, policy)
    entries = [(name, name, policy) for name in players.split(",")]
    for item in filter(None, also.split(",")):
        label, _, path = item.partition("=")
        entries.insert(1, (label, "ppo_icm", path))
    jobs = [[label, name, path, "traverse", seed, 3] for label, name, path in entries for seed in seed_range(seeds)]
    rows = list(episode.map(jobs, order_outputs=True))
    if out:
        Path(out).write_text(json.dumps({"env": "traverse", "delay": 3, "seeds": seeds, "policy": policy,
                                         "rows": rows}) + "\n")
    print(f"traverse, delay 3, seeds {seeds}")
    print(table(rows))
