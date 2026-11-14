"""The farm on Modal: one container per Traverse mission, many at once.

    modal setup                                                       # once, in your own terminal
    modal run tools/traverse_farm/modal_app.py::smoke                 # 8 worlds, Modal against this laptop
    modal run tools/traverse_farm/modal_app.py::evaluate --policies pilot,greedy,straight --seeds 600-799
    modal run tools/traverse_farm/modal_app.py::search --out docs/traverse-farm/search-1

Run from the repository root. Compute is billed to the Modal account that is logged in; a pilot
mission takes about 25 CPU-seconds. Nothing here calls a model API. TRAVERSE_SOURCE=<checkout>
plays another version of lightlag_traverse; every row records a hash of the code that played.

Each container gets three folders and nothing else: `lightlag_traverse/` (read, never edited),
`lightlag/` (its command model) and this folder. Model-written programs (`program:` policies) run only here, where the image sets
TRAVERSE_FARM_ALLOW_PROGRAMS=1; locally they are refused.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import modal

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
# The Traverse code that plays: the repository's, or another checkout given in TRAVERSE_SOURCE.
SOURCE = Path(os.environ.get("TRAVERSE_SOURCE") or REPO).resolve()
if modal.is_local():   # the Traverse source, then tools/ (traverse_farm), then the repository
    for path in (str(REPO), str(HERE.parent), str(SOURCE)):
        if path in sys.path:
            sys.path.remove(path)
        sys.path.insert(0, path)


def _skip(path) -> bool:
    path = Path(path)
    return "__pycache__" in path.parts or path.suffix == ".pyc"


image = (
    modal.Image.debian_slim(python_version="3.12")
    .env({"PYTHONPATH": "/root/farm", "TRAVERSE_FARM_ALLOW_PROGRAMS": "1", "PYTHONDONTWRITEBYTECODE": "1"})
    .add_local_dir(REPO / "lightlag", "/root/farm/lightlag", ignore=_skip)       # lightlag.model, used by Traverse
    .add_local_dir(SOURCE / "lightlag_traverse", "/root/farm/lightlag_traverse", ignore=_skip)
    .add_local_dir(HERE, "/root/farm/traverse_farm", ignore=_skip)
)
app = modal.App("lightlag-traverse-farm", image=image)
MAX_CONTAINERS = 100


@app.function(cpu=1.0, memory=1024, timeout=1800, max_containers=MAX_CONTAINERS)
def mission(job: dict) -> dict:
    from traverse_farm.jobs import run_job
    return run_job(job)


def _run_many(batch):
    """Play a batch on Modal; a job that raised comes back as a row with `crash`, never dropped."""
    from traverse_farm.jobs import program_id

    if not batch:
        return []
    started = time.time()
    rows = []
    results = list(mission.map(batch, order_outputs=True, return_exceptions=True))   # read it all, then pair
    for job, result in zip(batch, results):
        if isinstance(result, BaseException):
            row = {k: job[k] for k in ("candidate", "label", "generation", "block") if k in job}
            row.update(seed=job.get("seed"), policy=job.get("policy"), options=job.get("options") or {},
                       crash="{}: {}".format(type(result).__name__, result)[:400])
            if job.get("policy") == "program":   # so the crash is reported under its own job
                row["program_id"] = program_id(job)
            if job.get("mission"):
                row["mission"] = job["mission"]
            rows.append(row)
        else:
            rows.append(result)
    print("  {} missions on Modal in {:.0f} s".format(len(batch), time.time() - started))
    return rows


@app.local_entrypoint()
def smoke(seeds: str = "600-607", policies: str = "pilot,greedy"):
    """The same missions here and on Modal: same scores expected, and a time per mission."""
    from traverse_farm import jobs, search
    from traverse_farm.common import format_table, parse_policies, parse_seeds

    chosen, worlds = parse_policies(policies), parse_seeds(seeds)
    batch = [dict(spec, candidate=name, seed=seed) for name, spec in chosen.items() for seed in worlds]
    # Modal first: a first attempt that ran the busy local pool first timed out reconnecting to Modal.
    print("{} missions on Modal ...".format(len(batch)))
    there = _run_many(batch)
    print("{} missions locally ...".format(len(batch)))
    here = jobs.local_map(batch, workers=4)
    mismatches = [(a.get("candidate"), a.get("seed"), a.get("reward"), b.get("reward"))
                  for a, b in zip(here, there) if a.get("reward") is None or abs(a.get("reward", 0) - b.get("reward", -9)) > 1e-9]
    print("local:\n" + format_table({n: search.summarise(here, n) for n in chosen}))
    print("Modal:\n" + format_table({n: search.summarise(there, n) for n in chosen}))
    print("hosts: local {} | Modal {}".format(here[0].get("host"), there[0].get("host")))
    print("identical scores on every mission" if not mismatches else "MISMATCHES (policy, seed, local, Modal): {}".format(mismatches))


@app.local_entrypoint()
def evaluate(policies: str = "pilot,greedy,straight", seeds: str = "600-799", out: str = "", baseline: str = "pilot",
             mission: str = ""):
    """Several policies on the same worlds, each also compared world by world with `baseline`.
    `program:<path>` plays a model-written file defining play(tools); `agent:<folder>/<entry.py>` an agent's script.
    `mission` changes the rules for every mission, as JSON: '{"sun_margin_ticks": 0}'."""
    import json

    from traverse_farm import search
    from traverse_farm.common import format_table, format_versus, parse_policies, parse_seeds

    result = search.evaluate(_run_many, parse_policies(policies), parse_seeds(seeds), out=Path(out) if out else None,
                             baseline=baseline, mission=json.loads(mission) if mission else None)
    print(format_table(result["table"]))
    if result["versus"]:
        print(format_versus(baseline, result["versus"]))


@app.local_entrypoint()
def search(out: str = "docs/traverse-farm/search-1", generations: int = 6, population: int = 24, block: int = 40,
           search_seeds: str = "100-399", select: str = "400-499", confirm: str = "600-799", max_slowdown: float = 2.0,
           mission: str = ""):
    """Cross-entropy search over the pilot's options, then selection and confirmation on unseen worlds.
    `mission` searches on changed rules, as JSON: '{"sun_margin_ticks": 0}'."""
    import json

    from traverse_farm import jobs
    from traverse_farm import search as farm_search
    from traverse_farm.common import parse_seeds

    farm_search.search(_run_many, jobs.pilot_defaults(), search_seeds=parse_seeds(search_seeds),
                       select_seeds=parse_seeds(select), confirm_seeds=parse_seeds(confirm),
                       generations=generations, population=population, block=block,
                       max_slowdown=max_slowdown, out=Path(out), mission=json.loads(mission) if mission else None)
