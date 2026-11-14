#!/usr/bin/env python3
"""Run free local Harbor nop/reference checks and retain every attempt and artifact.

This launches only nop and oracle agents. It does not load an API key or call a
model. The oracle is the public-tool reference, not privileged simulator access.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import uuid

from prepare import prepare


ISOLATION_CODE = '''import importlib.util,json,os,pathlib,urllib.request,urllib.error
paths=["/srv/lightlag", "/srv/lightlag_dynamic", "/srv/lightlag_expedition",
       "/app/lightlag", "/app/lightlag_dynamic", "/app/lightlag_expedition",
       "/evaluator", "/evaluator/result.json", "/run/expedition/token",
       "/solution", "/tests/grade.py"]
missing={p:not pathlib.Path(p).exists() for p in paths}
modules={p:importlib.util.find_spec(p) is None for p in
         ("lightlag", "lightlag_dynamic", "lightlag_expedition")}
private_environment_absent=all(k not in os.environ for k in
    ("EXPEDITION_SEED", "EXPEDITION_MISSION_SEED", "EXPEDITION_TOKEN_FILE", "EXPEDITION_ARTIFACT_DIR"))
assert all(missing.values()) and all(modules.values()) and private_environment_absent
try:
 urllib.request.urlopen(urllib.request.Request("http://expedition:8000/evaluator/finish",method="POST"),timeout=3)
 raise AssertionError("unauthenticated finish succeeded")
except urllib.error.HTTPError as e:
 assert e.code==404
 print(json.dumps({"paths_absent":missing,"modules_absent":modules,
   "private_environment_absent":private_environment_absent,"unauthenticated_finish_status":e.code}))
'''


def matching_main(name, task_directory_name):
    """Never inspect or change another Harbor task's container."""
    return name.startswith(task_directory_name.lower() + "__") and name.endswith("__env-main-1")


def sanitized_environment():
    # Docker and local Python setup need these; provider credentials do not.
    keep = ("HOME", "USER", "LOGNAME", "SHELL", "LANG", "LC_ALL", "TMPDIR",
            "DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_CONFIG", "SSL_CERT_FILE",
            "SSL_CERT_DIR", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "UV_CACHE_DIR")
    env = {key: os.environ[key] for key in keep if key in os.environ}
    env["PATH"] = os.environ.get("PATH", "/usr/bin:/bin")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def run_attempt(runtime, task, agent, harbor, docker, require_isolation):
    name = agent + "-attempt-1"
    command = [harbor, "run", "-p", str(task), "-a", agent, "-n", "1", "-k", "1",
               "--max-retries", "0", "--jobs-dir", str(runtime / "jobs"), "--job-name", name]
    log_path = runtime / (name + ".launcher.log")
    started = time.monotonic()
    proof, probe_attempts = None, []
    with log_path.open("x") as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                   env=sanitized_environment())
        while process.poll() is None:
            if require_isolation and proof is None:
                listed = subprocess.run([docker, "ps", "--filter", "label=com.docker.compose.service=main",
                                         "--format", "{{.Names}}"], capture_output=True, text=True, timeout=10)
                for container in listed.stdout.splitlines():
                    if not matching_main(container, task.name):
                        continue
                    probe = subprocess.run([docker, "exec", container, "python", "-c", ISOLATION_CODE],
                                           capture_output=True, text=True, timeout=10)
                    probe_attempts.append({"container": container, "returncode": probe.returncode,
                                           "stdout": probe.stdout, "stderr": probe.stderr})
                    if probe.returncode == 0:
                        proof = json.loads(probe.stdout)
                        proof["container"] = container
                        break
            time.sleep(.25)
        returncode = process.wait()
    return {"agent": agent, "policy": "nop" if agent == "nop" else "reference",
            "returncode": returncode, "elapsed_seconds": round(time.monotonic() - started, 3),
            "isolation_required": require_isolation, "isolation": proof,
            "isolation_probe_attempts": probe_attempts,
            "command": [part.replace(str(runtime), "<private-runtime>") for part in command]}


def copy_sanitized(source, destination, runtime):
    """Keep source/evidence bytes except private host paths in text logs/configs."""
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(source)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        data = path.read_bytes()
        for private in (str(runtime.resolve()), str(runtime)):
            data = data.replace(private.encode(), b"<private-runtime>")
        target.write_bytes(data)


def summarize_trials(job):
    rows = []
    for path in sorted(job.glob("*/result.json")):
        result = json.loads(path.read_text())
        evaluation = path.parent / "artifacts/evaluator/result.json"
        verifier = path.parent / "verifier/expedition-details.json"
        raw = json.loads(evaluation.read_text()) if evaluation.exists() else None
        details = json.loads(verifier.read_text()) if verifier.exists() else None
        exception = result.get("exception_info")
        row = {"trial": path.parent.name, "exception_info": exception,
               "rewards": (result.get("verifier_result") or {}).get("rewards"),
               "evaluator": raw, "verifier_matches_evaluator": raw == details if raw is not None else False}
        rows.append(row)
    return rows


def run(output, harbor, docker, mission_seed=0, seed=0):
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError("output already exists; choose a new directory")
    output.mkdir(parents=True, exist_ok=False)
    runtime = Path(tempfile.mkdtemp(prefix="lightlag-expedition-free-"))
    runtime.chmod(0o700)
    nonce = uuid.uuid4().hex[:10]
    attempts = []
    summary = {"schema_version": 1, "started_utc": datetime.now(timezone.utc).isoformat(),
               "kind": "free Harbor infrastructure preflight; no model-difficulty claim",
               "settings": {"mission_seed": mission_seed, "seed": seed, "visibility": "hidden"},
               "attempts": attempts, "all_checks_pass": False}
    try:
        for agent, policy in (("nop", "nop"), ("oracle", "reference")):
            task = runtime / ("expedition-free-" + agent + "-" + nonce)
            prepare(task, mission_seed=mission_seed, seed=seed, policy=policy)
            attempt = run_attempt(runtime, task, agent, harbor, docker, agent == "nop")
            attempt["trials"] = summarize_trials(runtime / "jobs" / (agent + "-attempt-1"))
            attempts.append(attempt)
        summary["all_checks_pass"] = all(
            a["returncode"] == 0 and (not a["isolation_required"] or a["isolation"] is not None)
            and len(a["trials"]) == 1 and a["trials"][0]["exception_info"] is None
            and a["trials"][0]["verifier_matches_evaluator"] for a in attempts)
    finally:
        # Retain failed attempts too; the private runtime is deliberately not removed.
        copy_sanitized(runtime, output / "retained", runtime)
        (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
        manifest = {path.relative_to(output).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in sorted(output.rglob("*")) if path.is_file()}
        provenance = {"artifact_sha256": manifest,
                      "runner_source": "tools/expedition_experiments/free_harbor_check.py",
                      "runner_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        (output / "artifact-manifest.json").write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--harbor", default="/tmp/lightlag-6974-tools/bin/harbor")
    parser.add_argument("--docker", default="/usr/local/bin/docker")
    parser.add_argument("--mission-seed", type=int, default=0)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    result = run(**vars(args))
    print(json.dumps({"output": str(args.output), "all_checks_pass": result["all_checks_pass"],
                      "attempts": [{"agent": a["agent"], "returncode": a["returncode"]} for a in result["attempts"]]}))
    return 0 if result["all_checks_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
