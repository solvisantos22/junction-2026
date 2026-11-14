"""Isolated Modal workers; upload only explicit code, protocol and owned checkpoints."""

from pathlib import Path
import modal

ROOT = Path(__file__).resolve().parents[2]
APP_NAME = "lightlag-learned-portfolio"


def skip(path):
    p = Path(path)
    return "__pycache__" in p.parts or p.suffix == ".pyc"


image = (modal.Image.debian_slim(python_version="3.12")
         .pip_install("numpy==2.3.4", "scikit-learn==1.7.2", "scipy==1.18.1")
         .env({"PYTHONPATH": "/root/project", "PYTHONDONTWRITEBYTECODE": "1",
               "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}))
for package in ("lightlag", "lightlag_traverse", "lightlag_learned_portfolio", "tools/learned_portfolio"):
    image = image.add_local_dir(ROOT / package, "/root/project/" + package, ignore=skip)
image = image.add_local_file(ROOT / "lightlag_traverse_max/heldout.py", "/root/project/lightlag_traverse_max/heldout.py")
image = image.add_local_file(ROOT / "docs/learned-portfolio.md", "/root/project/docs/learned-portfolio.md")
MODEL_DIR = ROOT / "docs/learned-portfolio-results/models"
if MODEL_DIR.exists() and list(MODEL_DIR.glob("*.pkl")):
    image = image.add_local_dir(MODEL_DIR, "/root/project/models", ignore=skip)
app = modal.App(APP_NAME, image=image)
_models = {}


@app.function(cpu=1., memory=1024, timeout=600, max_containers=100, retries=0, scaledown_window=10)
def mission(job):
    from lightlag_learned_portfolio.worker import load_model, run_episode
    model = None
    if job["spec"]["kind"] == "learned":
        name = job["spec"]["algorithm"]
        key = (name, job["spec"]["model_sha256"])
        if key not in _models:
            _models[key] = load_model("/root/project/models/" + name + ".pkl", key[1])
        model = _models[key]
    result = run_episode(job, model)
    result["modal_call_id"] = modal.current_function_call_id()
    return result


@app.function(cpu=2., memory=4096, timeout=1800, max_containers=3, retries=0, scaledown_window=10)
def train(algorithm, data):
    from lightlag_learned_portfolio.model import fit
    result = fit(algorithm, data)
    result["modal_call_id"] = modal.current_function_call_id()
    return result
