"""Freeze and launch a bounded CPU campaign; default operation is offline.

Write/publish a freeze, then --launch one declared stage. --status polls the
saved call IDs; --stop sets a durable marker requesting graceful shutdown.
Download retained files with `modal volume get junction-learning-campaign
<run_id> <new-local-directory> --profile solvi-junction`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
APP_NAME = VOLUME_NAME = CONTROL_NAME = "junction-learning-campaign"
PROFILE = "solvi-junction"
PACKAGES = ("lightlag_learning", "lightlag_traverse", "lightlag", "lightlag_mcp", "lightlag_rl",
            "lightlag_rl_feasible")
PROTOCOL = "docs/learning-campaign.md"
LAUNCHER_FILES = ("tools/learning_campaign/__init__.py", "tools/learning_campaign/modal_job.py")
ABSOLUTE_DEADLINE = 1794713400.0  # 2026-11-15T03:30:00Z
RATE_PER_SECOND = 16 * .0000131 + 32 * .00000222
MAX_COMPUTE_ESTIMATE = 31.0
RESOURCES = {"cpu_request": 16, "cpu_limit": 16, "memory_mib": 32768,
             "memory_limit_mib": 32768, "max_containers": 3, "min_containers": 0,
             "buffer_containers": 0, "retries": 0, "startup_timeout_seconds": 120,
             "function_timeout_seconds": 10920, "workers": 14, "gpu": None}
RUNTIME = {"python": "3.12", "numpy": "2.3.4", "torch": "2.9.1",
           "torch_index": "https://download.pytorch.org/whl/cpu", "modal_client": "1.6.4"}
TERMINAL = {"completed", "training_incomplete", "training_error", "stopped_deadline",
            "stopped_marker", "wrapper_error", "cancelled", "launch_error"}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")
    temporary.replace(path)


def identifier(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", value) is not None


def validate_campaign(campaign, now=None):
    now = time.time() if now is None else now
    if set(campaign) != {"campaign_id", "deadline_unix", "stages"} or not identifier(campaign["campaign_id"]):
        raise ValueError("campaign requires campaign_id, deadline_unix and stages")
    deadline = campaign["deadline_unix"]
    if (type(deadline) not in (int, float) or not math.isfinite(deadline)
            or not now < deadline <= ABSOLUTE_DEADLINE):
        raise ValueError("campaign deadline must be future and no later than 2026-11-15T03:30:00Z")
    stages = campaign["stages"]
    if not isinstance(stages, list) or not 1 <= len(stages) <= 3:
        raise ValueError("declare one to three stages before launch")
    names, identities, targets = set(), {}, {}
    for index, stage in enumerate(stages):
        if (set(stage) != {"name", "max_seconds", "jobs"} or not identifier(stage["name"])
                or stage["name"] in names):
            raise ValueError("stage names must be unique identifiers")
        names.add(stage["name"])
        limit = 5400 if index == 0 else 10800
        if type(stage["max_seconds"]) is not int or not 1 <= stage["max_seconds"] <= limit:
            raise ValueError("stage runtime exceeds its fixed pilot/continuation limit")
        if not isinstance(stage["jobs"], list) or not 1 <= len(stage["jobs"]) <= 6:
            raise ValueError("each stage requires at most six fixed jobs")
        seen = set()
        for job in stage["jobs"]:
            if (set(job) != {"run_id", "algorithm", "seed", "episodes"}
                    or not identifier(job["run_id"]) or job["run_id"] in seen
                    or job["algorithm"] not in ("ppo", "replay")
                    or type(job["seed"]) is not int or not 0 <= job["seed"] < 2**31
                    or type(job["episodes"]) is not int or not 1 <= job["episodes"] <= 32768):
                raise ValueError("invalid, duplicate or oversized training job")
            seen.add(job["run_id"])
            identity = (job["algorithm"], job["seed"])
            if index == 0:
                if identity in identities.values():
                    raise ValueError("duplicate algorithm/seed identity")
                identities[job["run_id"]] = identity
            elif identities.get(job["run_id"]) != identity:
                raise ValueError("continuation must reuse original run IDs, algorithms and seeds")
            if job["episodes"] <= targets.get(job["run_id"], 0):
                raise ValueError("continuation target must increase")
            targets[job["run_id"]] = job["episodes"]
    envelope = min(deadline - now, sum(s["max_seconds"] for s in stages)) * 3 * RATE_PER_SECOND
    if envelope > MAX_COMPUTE_ESTIMATE:
        raise ValueError("campaign running-compute envelope exceeds $31")
    return envelope


def source_manifest(root=ROOT):
    root = Path(root).resolve()
    files = [root / PROTOCOL, *(root / n for n in LAUNCHER_FILES)]
    for package in PACKAGES:
        directory = root / package
        if not directory.is_dir() or directory.is_symlink():
            raise ValueError("required source package missing or symlinked: " + package)
        files.extend(directory.rglob("*.py"))
    if not (root / "lightlag_learning/train.py").is_file():
        raise ValueError("training entrypoint is not ready")
    for path in files:
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError("source allowlist contains a missing or escaping file")
    return {str(p.relative_to(root)): digest(p) for p in sorted(set(files))}


def write_freeze(path, campaign, root=ROOT, now=None):
    now = time.time() if now is None else now
    envelope = validate_campaign(campaign, now)
    sources = source_manifest(root)
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    freeze = {"schema": "learning-campaign-freeze-v1", "campaign": campaign,
              "source_sha256": sources, "source_commit": revision,
              "uploaded_sha256": {n: h for n, h in sources.items() if n not in LAUNCHER_FILES},
              "created_unix": now, "resources": RESOURCES, "runtime": RUNTIME,
              "required_profile": PROFILE, "running_compute_envelope_usd": envelope,
              "cost_note": "CPU/memory estimate only; build, startup, storage and egress additional. Not an invoice cap.",
              "model_api_calls": 0, "gpu_jobs": 0}
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(freeze, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    return freeze


def prepare(freeze_path, stage_name, root=ROOT, now=None, algorithms=None):
    now = time.time() if now is None else now
    freeze = json.loads(Path(freeze_path).read_text())
    if (freeze.get("schema") != "learning-campaign-freeze-v1" or freeze.get("resources") != RESOURCES
            or freeze.get("runtime") != RUNTIME or freeze.get("required_profile") != PROFILE):
        raise ValueError("freeze runtime/resources/profile mismatch")
    envelope = validate_campaign(freeze["campaign"], freeze["created_unix"])
    if freeze["running_compute_envelope_usd"] != envelope or freeze["campaign"]["deadline_unix"] <= now:
        raise ValueError("campaign envelope changed or deadline expired")
    sources = source_manifest(root)
    if (freeze["source_sha256"] != sources
            or freeze["uploaded_sha256"] != {n: h for n, h in sources.items() if n not in LAUNCHER_FILES}):
        raise ValueError("source changed since freeze")
    matches = [s for s in freeze["campaign"]["stages"] if s["name"] == stage_name]
    if len(matches) != 1:
        raise ValueError("requested stage is not in the frozen campaign")
    stage = matches[0]
    allowed = {j["algorithm"] for j in stage["jobs"]}
    selected = allowed if algorithms is None else set(algorithms)
    if not selected or not selected <= allowed:
        raise ValueError("selected algorithms must be a nonempty subset of the frozen stage")
    if stage is freeze["campaign"]["stages"][0] and selected != allowed:
        raise ValueError("the pilot must run every declared algorithm")
    return {"schema": "learning-campaign-plan-v1", "freeze": freeze,
            "freeze_sha256": digest(freeze_path), "stage": stage,
            "selected_jobs": [j for j in stage["jobs"] if j["algorithm"] in selected],
            "app_name": APP_NAME, "volume_name": VOLUME_NAME,
            "model_api_calls": 0, "gpu_jobs": 0}


def copy_sources(plan, destination, root=ROOT):
    root, destination = Path(root).resolve(), Path(destination)
    if source_manifest(root) != plan["freeze"]["source_sha256"]:
        raise ValueError("source changed before image snapshot")
    for name, expected in plan["freeze"]["uploaded_sha256"].items():
        source, target = root / name, destination / name
        if source.is_symlink() or digest(source) != expected:
            raise ValueError("source changed while snapshotting")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        if digest(target) != expected:
            raise ValueError("source changed while copying")


def reserve_stage(control, plan, now=None, completed=None):
    """Atomic server-side reservations: another client cannot multiply apps."""
    now = time.time() if now is None else now
    campaign, stage = plan["freeze"]["campaign"], plan["stage"]
    identity = {"campaign_id": campaign["campaign_id"], "freeze_sha256": plan["freeze_sha256"],
                "deadline_unix": campaign["deadline_unix"]}
    control.put("campaign", identity, skip_if_exists=True)
    if control.get("campaign") != identity:
        raise ValueError("this launcher already owns a different frozen campaign; refusing another app")
    if control.get("stop"):
        raise ValueError("campaign has a durable stop marker")
    stage_index = campaign["stages"].index(stage)
    for previous in campaign["stages"][:stage_index]:
        previous_reservation = control.get("stage:" + previous["name"])
        if not previous_reservation:
            raise ValueError("previous stage has not been launched")
        for job in previous_reservation["jobs"]:
            state = control.get("job:" + previous["name"] + ":" + job["run_id"], {})
            if state.get("status") not in TERMINAL:
                raise ValueError("previous stage is not terminal; refusing overlapping apps")
            if completed is not None:
                completed(state["call_id"])
    if stage_index:
        previous_ids = {j["run_id"] for j in previous_reservation["jobs"]}
        if not {j["run_id"] for j in plan["selected_jobs"]} <= previous_ids:
            raise ValueError("later stages cannot reintroduce previously unselected runs")
    deadline = min(campaign["deadline_unix"], now + stage["max_seconds"])
    if deadline <= now:
        raise ValueError("stage deadline expired")
    reservation = {"stage": stage["name"], "freeze_sha256": plan["freeze_sha256"],
                   "reserved_unix": now, "deadline_unix": deadline, "jobs": plan["selected_jobs"]}
    if not control.put("stage:" + stage["name"], reservation, skip_if_exists=True):
        raise ValueError("stage already reserved; inspect its receipt instead of launching again")
    return reservation


def make_remote_runner(volume, control):
    # Self-contained serialized closure; no automatic repository/source upload.
    def remote_train(plan, job, source_root="/app", result_root="/results"):
        import hashlib
        import json
        import os
        from pathlib import Path
        import signal
        import subprocess
        import sys
        import threading
        import time

        import modal

        freeze, stage = plan["freeze"], plan["stage"]
        campaign, run_id = freeze["campaign"], job["run_id"]
        stage_name = stage["name"]
        call_id = modal.current_function_call_id()
        expected_identity = {"campaign_id": campaign["campaign_id"],
                             "freeze_sha256": plan["freeze_sha256"],
                             "deadline_unix": campaign["deadline_unix"]}
        if control.get("campaign") != expected_identity:
            raise ValueError("remote campaign identity mismatch")
        reserved = control.get("stage:" + stage_name)
        if (not reserved or reserved["freeze_sha256"] != plan["freeze_sha256"]
                or reserved["jobs"] != plan["selected_jobs"] or job not in reserved["jobs"]):
            raise ValueError("remote job not in reserved stage")
        deadline = min(reserved["deadline_unix"], campaign["deadline_unix"], 1794713400.0)
        key = "job:" + stage_name + ":" + run_id
        owner = "owner:" + stage_name + ":" + run_id
        control.put(owner, call_id, skip_if_exists=True)
        if control.get(owner) != call_id:
            raise ValueError("job already belongs to another invocation")
        prior = control.get(key, {})
        if prior.get("status") in ("completed", "training_incomplete", "training_error", "stopped_deadline", "stopped_marker", "wrapper_error"):
            return prior

        root = Path(source_root)
        expected = freeze["uploaded_sha256"]
        packages = ("lightlag_learning", "lightlag_traverse", "lightlag", "lightlag_mcp", "lightlag_rl",
                    "lightlag_rl_feasible")
        actual = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                  for package in packages for p in (root / package).rglob("*.py")}
        protocol = root / "docs/learning-campaign.md"
        actual["docs/learning-campaign.md"] = hashlib.sha256(protocol.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError("remote image does not match frozen source")
        metadata_root = Path(result_root) / "_campaign" / campaign["campaign_id"] / stage_name / run_id
        metadata_root.mkdir(parents=True, exist_ok=True)
        attempt = str(time.time_ns())
        metadata_path = metadata_root / ("attempt-" + attempt + ".json")
        log_path = metadata_root / ("attempt-" + attempt + ".stdout.txt")
        command = [sys.executable, "-m", "lightlag_learning.train", "--algorithm", job["algorithm"],
                   "--seed", str(job["seed"]), "--episodes", str(job["episodes"]),
                   "--output", str(Path(result_root) / run_id), "--workers", "14",
                   "--deadline-unix", str(deadline)]
        import numpy
        import torch
        if (sys.version_info[:2] != (3, 12) or numpy.__version__ != "2.3.4"
                or torch.__version__.split("+")[0] != "2.9.1" or torch.version.cuda is not None):
            raise ValueError("runtime differs from frozen CPU image")
        metadata = {"schema": "learning-campaign-attempt-v1", "job": job,
                    "campaign_id": campaign["campaign_id"], "stage": stage_name,
                    "freeze_sha256": plan["freeze_sha256"], "source_sha256": actual,
                    "call_id": call_id, "app_id": plan["app_id"], "started_unix": time.time(),
                    "deadline_unix": deadline, "command": command, "status": "running",
                    "python_actual": sys.version, "numpy_actual": numpy.__version__,
                    "torch_actual": torch.__version__, "model_api_calls": 0, "gpu_jobs": 0,
                    "commit_errors": []}

        def persist():
            temporary = metadata_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
            temporary.replace(metadata_path)
            control.put(key, {k: metadata[k] for k in ("status", "call_id", "app_id", "started_unix", "deadline_unix")})

        process, done = None, threading.Event()

        def terminate():
            if process is not None and process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
                except ProcessLookupError:
                    pass

        def watchdog():
            if not done.wait(max(0., deadline - time.time())):
                terminate()

        def commit_loop():
            while not done.wait(120):
                try:
                    volume.commit()
                except Exception as error:
                    metadata["commit_errors"].append(type(error).__name__)

        persist()
        volume.commit()
        commit_thread = threading.Thread(target=commit_loop, daemon=True)
        commit_thread.start()
        try:
            if time.time() >= deadline:
                metadata["status"] = "stopped_deadline"
            elif control.get("stop"):
                metadata["status"] = "stopped_marker"
            else:
                child_env = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(root),
                             "PYTHONUNBUFFERED": "1", "PYTHONHASHSEED": "0",
                             "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
                with log_path.open("w") as stream:
                    process = subprocess.Popen(command, cwd=root, env=child_env,
                                               stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
                    threading.Thread(target=watchdog, daemon=True).start()
                    next_control_poll = 0.
                    while process.poll() is None:
                        if time.time() >= deadline:
                            metadata["status"] = "stopped_deadline"
                            terminate()
                            break
                        if time.monotonic() >= next_control_poll:
                            next_control_poll = time.monotonic() + 10
                            if control.get("stop"):
                                metadata["status"] = "stopped_marker"
                                terminate()
                                break
                        try:
                            process.wait(timeout=min(1., max(.01, deadline - time.time())))
                        except subprocess.TimeoutExpired:
                            pass
                    metadata["returncode"] = process.returncode
                    if metadata["status"] == "running":
                        metadata["status"] = "stopped_deadline" if time.time() >= deadline else "training_error"
                        report_path = Path(result_root) / run_id / "report.json"
                        if process.returncode == 0 and report_path.is_file():
                            report = json.loads(report_path.read_text())
                            metadata["trainer_report"] = report
                            metadata["trainer_report_sha256"] = hashlib.sha256(report_path.read_bytes()).hexdigest()
                            matches = (report.get("schema") == "learning-training-report-v1"
                                       and report.get("algorithm") == job["algorithm"] and report.get("seed") == job["seed"]
                                       and report.get("episodes_target") == job["episodes"])
                            if matches:
                                metadata["status"] = (
                                    "completed" if report.get("status") == "complete" and report.get("episodes_completed") == job["episodes"]
                                    else "stopped_deadline" if report.get("status") == "deadline"
                                    else "training_incomplete")
        except BaseException as error:
            metadata.update(status="wrapper_error", error_type=type(error).__name__)
            raise
        finally:
            terminate()
            done.set()
            commit_thread.join(timeout=10)
            metadata["finished_unix"] = time.time()
            metadata["elapsed_seconds"] = metadata["finished_unix"] - metadata["started_unix"]
            metadata["running_compute_estimate_usd"] = metadata["elapsed_seconds"] * (16*.0000131 + 32*.00000222)
            persist()
            volume.commit()
        return {k: metadata[k] for k in ("status", "job", "call_id", "app_id", "deadline_unix", "elapsed_seconds",
                                         "running_compute_estimate_usd", "model_api_calls", "gpu_jobs")}
    return remote_train


def modal_sdk():
    if os.environ.get("MODAL_PROFILE") != PROFILE:
        raise ValueError("set MODAL_PROFILE=solvi-junction explicitly")
    import modal
    if modal.__version__ != RUNTIME["modal_client"]:
        raise ValueError("use pinned modal==1.6.4")
    return modal


def launch(plan, receipt_path, root=ROOT, *, sdk=None, now=None):
    now = time.time() if now is None else now
    sdk = modal_sdk() if sdk is None else sdk
    receipt_path = Path(receipt_path)
    # Receipt exists before any cloud resource or invocation, including failed launches.
    receipt = {"schema": "learning-campaign-receipt-v1", "status": "preparing",
               "campaign_id": plan["freeze"]["campaign"]["campaign_id"],
               "freeze_sha256": plan["freeze_sha256"], "stage": plan["stage"]["name"],
               "jobs": [], "resources": RESOURCES, "created_unix": now}
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    with receipt_path.open("x") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True)
        stream.write("\n")
    try:
        with tempfile.TemporaryDirectory(prefix="learning-campaign-source-") as temporary:
            copy_sources(plan, temporary, root)
            control = sdk.Dict.from_name(CONTROL_NAME, create_if_missing=True)
            reservation = reserve_stage(control, plan, now,
                completed=lambda call_id: sdk.FunctionCall.from_id(call_id).get(timeout=0))
            receipt["reservation"] = reservation
            atomic_json(receipt_path, receipt)
            image = (sdk.Image.debian_slim(python_version="3.12")
                     .pip_install("torch==2.9.1", index_url=RUNTIME["torch_index"])
                     .pip_install("numpy==2.3.4")
                     .add_local_dir(temporary, remote_path="/app", copy=True))
            volume = sdk.Volume.from_name(VOLUME_NAME, create_if_missing=True, version=2)
            app = sdk.App(APP_NAME)
            remote = app.function(image=image, cpu=(16, 16), memory=(32768, 32768),
                                  max_containers=3, min_containers=0, buffer_containers=0,
                                  retries=0, timeout=10920, startup_timeout=120,
                                  single_use_containers=True, volumes={"/results": volume},
                                  serialized=True, include_source=False)(make_remote_runner(volume, control))
            with sdk.enable_output(), app.run(detach=True):
                receipt.update(status="launching", app_id=app.app_id,
                               dashboard_url="https://modal.com/apps/" + app.app_id)
                atomic_json(receipt_path, receipt)
                for job in plan["selected_jobs"]:
                    if time.time() >= reservation["deadline_unix"] or control.get("stop"):
                        raise RuntimeError("stage deadline/stop marker reached before all jobs were submitted")
                    call = remote.spawn({**plan, "app_id": app.app_id}, job)
                    receipt["jobs"].append({**job, "call_id": call.object_id})
                    atomic_json(receipt_path, receipt)
                receipt["status"] = "submitted"
                atomic_json(receipt_path, receipt)
        return receipt
    except BaseException as error:
        receipt.update(status="launch_error", error_type=type(error).__name__)
        atomic_json(receipt_path, receipt)
        raise


def status(receipt_path, *, sdk=None):
    sdk = modal_sdk() if sdk is None else sdk
    receipt = json.loads(Path(receipt_path).read_text())
    control = sdk.Dict.from_name(CONTROL_NAME)
    results = []
    for job in receipt["jobs"]:
        state = control.get("job:" + receipt["stage"] + ":" + job["run_id"], {})
        try:
            result = sdk.FunctionCall.from_id(job["call_id"]).get(timeout=0)
            results.append({"run_id": job["run_id"], "state": state, "result": result})
        except TimeoutError:
            results.append({"run_id": job["run_id"], "state": state, "pending": True})
        except Exception as error:
            results.append({"run_id": job["run_id"], "state": state, "error_type": type(error).__name__})
    return {"campaign_id": receipt["campaign_id"], "stage": receipt["stage"],
            "app_id": receipt.get("app_id"), "stop_marker": bool(control.get("stop")), "jobs": results}


def stop(receipt_path, *, sdk=None):
    sdk = modal_sdk() if sdk is None else sdk
    receipt = json.loads(Path(receipt_path).read_text())
    control = sdk.Dict.from_name(CONTROL_NAME)
    identity = control.get("campaign", {})
    if identity.get("campaign_id") != receipt["campaign_id"] or identity.get("freeze_sha256") != receipt["freeze_sha256"]:
        raise ValueError("receipt does not own the active campaign")
    control.put("stop", {"requested_unix": time.time(), "campaign_id": receipt["campaign_id"]})
    # Running wrappers observe the marker and persist logs/checkpoints; queued
    # invocations also check it before starting the trainer.
    return {"campaign_id": receipt["campaign_id"], "status": "stop_requested"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", type=Path)
    parser.add_argument("--campaign", type=Path, help="JSON manifest, only needed with --write-freeze")
    parser.add_argument("--stage")
    parser.add_argument("--algorithms", help="later-stage subset, e.g. ppo or ppo,replay")
    parser.add_argument("--receipt", type=Path)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--write-freeze", action="store_true")
    actions.add_argument("--launch", action="store_true")
    actions.add_argument("--status", action="store_true")
    actions.add_argument("--stop", action="store_true")
    args = parser.parse_args(argv)
    if args.status or args.stop:
        if not args.receipt:
            parser.error("--receipt is required")
        result = stop(args.receipt) if args.stop else status(args.receipt)
    elif args.write_freeze:
        if not args.campaign or not args.freeze:
            parser.error("--campaign and --freeze are required")
        freeze = write_freeze(args.freeze, json.loads(args.campaign.read_text()))
        result = {"status": "freeze_written", "cloud_calls": 0,
                  "running_compute_envelope_usd": freeze["running_compute_envelope_usd"]}
    else:
        if not args.freeze or not args.stage:
            parser.error("--freeze and --stage are required")
        algorithms = args.algorithms.split(",") if args.algorithms is not None else None
        plan = prepare(args.freeze, args.stage, algorithms=algorithms)
        if args.launch:
            if not args.receipt:
                parser.error("--receipt must be a new stage receipt path")
            result = launch(plan, args.receipt)
        else:
            result = {"status": "dry_run", "cloud_calls": 0, "plan": plan}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
