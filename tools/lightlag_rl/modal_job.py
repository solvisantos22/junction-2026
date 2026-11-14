"""Prepare a frozen CPU training job locally; --launch is the only cloud path.

Use Python's CLI, not `modal run`: importing this module and its default dry run
do not import the Modal SDK, authenticate, build an image or create an App.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
PACKAGES = ("lightlag_rl", "lightlag_traverse", "lightlag", "lightlag_mcp")
LAUNCHER_FILES = ("tools/lightlag_rl/__init__.py", "tools/lightlag_rl/modal_job.py")
PUBLIC_PROTOCOL = "docs/lightlag-rl.md"
APP_NAME = VOLUME_NAME = "junction-lightlag-rl"
PROFILE = "solvi-junction"
TRAINING = {"updates": 16, "batch_size": 32, "workers": 4,
            "train_seed": 17, "max_seconds": 3000}
DATA = {"train_start": 71000, "train_count": 128, "fresh_evaluation": False}
RESOURCES = {"cpu_request": 4, "cpu_limit": 4, "memory_mib": 8192,
             "memory_limit_mib": 8192, "timeout_seconds": 3600,
             "startup_timeout_seconds": 120, "max_containers": 1,
             "min_containers": 0, "retries": 0, "gpu": None}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_manifest(root):
    root = Path(root).resolve()
    paths = []
    for package in PACKAGES:
        directory = root / package
        if not directory.is_dir() or directory.is_symlink():
            raise ValueError("missing or symlinked source package: " + package)
        paths.extend(directory.rglob("*.py"))
    paths.extend(root / name for name in LAUNCHER_FILES)
    paths.append(root / PUBLIC_PROTOCOL)
    required = root / "lightlag_rl/train.py"
    if not required.is_file():
        raise ValueError("training entrypoint is not prepared")
    for path in paths:
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
            raise ValueError("source file escapes repository or is unavailable")
    return {str(p.relative_to(root)): digest(p) for p in sorted(set(paths))}


def write_freeze(path, root=ROOT):
    """Write an immutable local manifest. This does not import Modal."""
    path, root = Path(path), Path(root)
    manifest = source_manifest(root)
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    freeze = {"schema": "lightlag-rl-modal-freeze-v1", "source_commit": revision,
              "source_sha256": manifest, "training": TRAINING, "data": DATA,
              "resources": RESOURCES, "python": "3.12", "numpy": "2.3.4",
              "modal_client": "1.6.4", "required_profile": PROFILE}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(freeze, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return freeze


def prepare(freeze_path, run_id, root=ROOT):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", run_id):
        raise ValueError("run_id must be 1–64 alphanumeric, hyphen or underscore characters")
    freeze_path = Path(freeze_path)
    freeze = json.loads(freeze_path.read_text())
    expected = {"schema": "lightlag-rl-modal-freeze-v1", "training": TRAINING,
                "data": DATA, "resources": RESOURCES, "python": "3.12",
                "numpy": "2.3.4", "modal_client": "1.6.4", "required_profile": PROFILE}
    if any(freeze.get(key) != value for key, value in expected.items()):
        raise ValueError("freeze does not match the declared single-job configuration")
    manifest = source_manifest(root)
    if freeze.get("source_sha256") != manifest:
        raise ValueError("source files changed or the freeze manifest is incomplete")
    return {"schema": "lightlag-rl-modal-job-v1", "run_id": run_id,
            "app_name": APP_NAME, "volume_name": VOLUME_NAME, "volume_version": 2,
            "freeze_sha256": digest(freeze_path), "freeze": freeze,
            "model_api_calls": 0, "fresh_cases": 0,
            "running_compute_estimate_usd_per_hour": (4 * .0000131 + 8 * .00000222) * 3600,
            "cost_note": "Running CPU/memory only; build, startup, storage and egress are additional. Not a billing cap."}


def copy_sources(plan, destination, root=ROOT):
    """Snapshot Python source and one public protocol; no private files or globs of docs."""
    destination, root = Path(destination), Path(root)
    if plan["freeze"]["source_sha256"] != source_manifest(root):
        raise ValueError("source changed before snapshot or manifest is invalid")
    copied = {}
    for name, expected in plan["freeze"]["source_sha256"].items():
        if name.split("/", 1)[0] not in PACKAGES and name != PUBLIC_PROTOCOL:
            continue  # Launcher is pinned locally and serialized; not mounted.
        source = root / name
        if digest(source) != expected or source.is_symlink():
            raise ValueError("source changed before snapshot")
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        if digest(target) != expected:
            raise ValueError("source changed while snapshotting")
        copied[name] = expected
    return copied


def make_remote_runner(volume):
    # Keep the serialized function self-contained; automatic source discovery
    # is disabled and only the explicit source snapshot enters the image.
    def remote_train(plan, source_root="/app", result_root="/results"):
        import hashlib
        import json
        import os
        from pathlib import Path
        import signal
        import subprocess
        import sys
        import threading
        import time

        root = Path(source_root)
        expected = {name: hashed for name, hashed in plan["freeze"]["source_sha256"].items()
                    if name.split("/", 1)[0] in ("lightlag_rl", "lightlag_traverse", "lightlag", "lightlag_mcp")
                    or name == "docs/lightlag-rl.md"}
        actual = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                  for package in ("lightlag_rl", "lightlag_traverse", "lightlag", "lightlag_mcp")
                  for p in (root / package).rglob("*.py")}
        protocol_path = root / "docs/lightlag-rl.md"
        if protocol_path.is_file():
            actual["docs/lightlag-rl.md"] = hashlib.sha256(protocol_path.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError("remote source snapshot does not match freeze")
        run_id = plan["run_id"]
        if not run_id or len(run_id) > 64 or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in run_id):
            raise ValueError("invalid run id")
        output = Path(result_root) / run_id
        output.mkdir(parents=True, exist_ok=False)
        command = [sys.executable, "-m", "lightlag_rl.train", "--output", str(output / "training"),
                   "--updates", "16", "--batch-size", "32", "--workers", "4",
                   "--train-seed", "17", "--max-seconds", "3000"]
        metadata = {**plan, "status": "running", "command": command,
                    "python_actual": sys.version, "started_unix": time.time(),
                    "source_snapshot_verified": True, "commit_errors": []}
        try:
            import modal
            metadata["modal_function_call_id"] = modal.current_function_call_id()
        except (ImportError, RuntimeError):
            metadata["modal_function_call_id"] = None
        try:
            import numpy
            metadata["numpy_actual"] = numpy.__version__
        except ImportError:
            metadata["numpy_actual"] = None

        def persist():
            temporary = output / "modal-job.json.tmp"
            temporary.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
            temporary.replace(output / "modal-job.json")

        persist()
        volume.commit()
        stop = threading.Event()

        def periodic_commit():
            while not stop.wait(120):
                try:
                    volume.commit()
                except Exception as error:
                    metadata["commit_errors"].append(type(error).__name__)

        thread = threading.Thread(target=periodic_commit, daemon=True)
        thread.start()
        process = None
        try:
            with (output / "train.stdout.txt").open("w") as stream:
                # The trainer receives no Modal token or other host credentials.
                child_env = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(root),
                             "PYTHONUNBUFFERED": "1", "PYTHONHASHSEED": "0",
                             "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
                process = subprocess.Popen(command, cwd=root, env=child_env,
                                           stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
                try:
                    returncode = process.wait(timeout=3300)
                    metadata.update(returncode=returncode, status="returned" if returncode == 0 else "training_error")
                except subprocess.TimeoutExpired:
                    metadata.update(status="process_timeout", returncode=None)
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait(timeout=5)
        except BaseException as error:
            metadata.update(status="wrapper_error", error_type=type(error).__name__)
            raise
        finally:
            if process is not None and process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
            stop.set()
            thread.join(timeout=10)
            metadata["finished_unix"] = time.time()
            metadata["elapsed_seconds"] = metadata["finished_unix"] - metadata["started_unix"]
            persist()
            volume.commit()
        return {"run_id": run_id, "status": metadata["status"],
                "returncode": metadata.get("returncode"), "volume_name": plan["volume_name"],
                "modal_app_id": plan.get("modal_app_id"),
                "modal_function_call_id": metadata["modal_function_call_id"],
                "elapsed_seconds": metadata["elapsed_seconds"], "fresh_cases": 0, "model_api_calls": 0}
    return remote_train


def launch(plan, root=ROOT):
    if os.environ.get("MODAL_PROFILE") != PROFILE:
        raise ValueError("set MODAL_PROFILE=solvi-junction explicitly after authenticating that profile")
    import modal
    if modal.__version__ != "1.6.4":
        raise ValueError("use the pinned modal==1.6.4 client")
    with tempfile.TemporaryDirectory(prefix="lightlag-rl-modal-source-") as temporary:
        copy_sources(plan, temporary, root)
        image = (modal.Image.debian_slim(python_version="3.12")
                 .pip_install("numpy==2.3.4")
                 .add_local_dir(temporary, remote_path="/app", copy=True))
        volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True, version=2)
        app = modal.App(APP_NAME)
        remote = app.function(image=image, cpu=(4, 4), memory=(8192, 8192),
                              timeout=3600, startup_timeout=120, max_containers=1,
                              min_containers=0, retries=0, volumes={"/results": volume},
                              serialized=True, include_source=False)(make_remote_runner(volume))
        with modal.enable_output(), app.run():
            return remote.remote({**plan, "modal_app_id": app.app_id})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--run-id", default="pilot-01")
    parser.add_argument("--write-freeze", action="store_true")
    parser.add_argument("--launch", action="store_true")
    args = parser.parse_args(argv)
    if args.write_freeze and args.launch:
        parser.error("write and publish the freeze before a separate --launch invocation")
    if args.write_freeze:
        write_freeze(args.freeze)
        print(json.dumps({"status": "freeze_written", "path": str(args.freeze), "cloud_calls": 0}))
        return 0
    plan = prepare(args.freeze, args.run_id)
    if args.launch:
        result = launch(plan)
        print(json.dumps(result, indent=2))
        return 0 if result["status"] == "returned" else 1
    print(json.dumps({"status": "dry_run", "cloud_calls": 0, "plan": plan}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
