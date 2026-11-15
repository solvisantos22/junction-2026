"""Explicit upload allowlist, pinned dependencies and bounded Modal workers."""

import os
from pathlib import Path
import modal

ROOT = Path(__file__).resolve().parents[2]


def skip(path): return "__pycache__" in Path(path).parts or Path(path).suffix == ".pyc"


image = (modal.Image.debian_slim(python_version="3.12")
    .pip_install("numpy==2.3.4", "scikit-learn==1.7.2", "scipy==1.18.1")
    .env({"PYTHONPATH":"/root/project", "PYTHONDONTWRITEBYTECODE":"1",
          "OMP_NUM_THREADS":"1", "OPENBLAS_NUM_THREADS":"1", "MKL_NUM_THREADS":"1"}))
for name in ("lightlag", "lightlag_traverse", "lightlag_planner_lab", "lightlag_learned_portfolio", "tools/planner_lab"):
    image = image.add_local_dir(ROOT/name, "/root/project/"+name, ignore=skip)
for name in ("lightlag_traverse_max/heldout.py", "docs/planner-lab.md",
             "docs/learned-portfolio-results/models/extra_trees.pkl"):
    image = image.add_local_file(ROOT/name, "/root/project/"+name)
models = ROOT/"docs/planner-lab-results/models"
if models.exists(): image = image.add_local_dir(models, "/root/project/models", ignore=skip)
app = modal.App("lightlag-planner-lab", image=image)
cache = {}


def metadata():
    return {"modal_call_id":modal.current_function_call_id(), "modal_task_id":os.environ.get("MODAL_TASK_ID")}


def model_for(arm):
    from lightlag_planner_lab.worker import LEGACY, LEGACY_SHA, load_model
    spec = arm["spec"]
    if spec["kind"] == "fixed": return None
    if spec["kind"] == "legacy": path, sha = LEGACY, LEGACY_SHA
    else: path, sha = Path("/root/project/models")/(spec["algorithm"]+".pkl"), spec["model_sha256"]
    key = (str(path), sha)
    if key not in cache: cache[key] = load_model(path, sha)
    return cache[key]


@app.function(cpu=1., memory=1536, timeout=900, max_containers=100, retries=0, scaledown_window=10, include_source=False)
def batch(job):
    from lightlag_planner_lab.worker import run_batch
    result = run_batch(job, {a["name"]:model_for(a) for a in job["arms"]})
    result.update(metadata()); return result


@app.function(cpu=2., memory=4096, timeout=1800, max_containers=4, retries=0, scaledown_window=10, include_source=False)
def train(algorithm, data):
    from lightlag_planner_lab.model import fit
    from lightlag_planner_lab.worker import digest, source_manifest
    result = fit(algorithm, data)
    result.update({**metadata(), "source_sha256":digest(source_manifest()), "training_data_sha256":digest(data)})
    return result


@app.function(cpu=1., memory=1536, timeout=900, max_containers=32, retries=0, scaledown_window=10, include_source=False)
def verify(bundles):
    from lightlag_planner_lab.worker import replay_episode, digest, source_manifest
    checked = []
    for bundle in bundles:
        assert bundle["source_sha256"] == digest(source_manifest())
        for episode in bundle["episodes"]:
            checked.append({"job_id":bundle["job"]["id"], "seed":bundle["job"]["seed"],
                "name":episode["arm"]["name"], **replay_episode(bundle["job"]["seed"], episode)})
    return {"checked":checked, **metadata()}


@app.function(cpu=1., memory=1536, timeout=900, max_containers=4, retries=0, scaledown_window=10, include_source=False)
def repeat(job, arm, original=False):
    from lightlag_planner_lab.worker import run_without_copy, digest, source_manifest, QUICK
    assert job["source"] == source_manifest()
    if original:
        from lightlag_traverse.environment import TraverseEnvironment
        from lightlag_traverse.pilot import fly
        from lightlag_traverse.play import PublicTools
        env = TraverseEnvironment(job["seed"])
        if original == "legacy":
            from lightlag_learned_portfolio.policy import play
            play(PublicTools(env), {"kind":"learned", "threshold":0.}, model_for(arm), QUICK if job.get("quick") else None)
        else: fly(PublicTools(env), QUICK if job.get("quick") else None)
        replay = env.replay()
        return {"replay_sha256":digest(replay), "result":replay["result"], **metadata()}
    result = run_without_copy(job, arm, model_for(arm))
    return {"replay_sha256":result["replay_sha256"], "result":result["result"],
            "decision":result["decision"], "legacy_decision":result["legacy_decision"], **metadata()}
