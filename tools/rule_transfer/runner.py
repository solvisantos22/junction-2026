"""Run one unchanged saved policy against one mission in an isolated Docker process.

Only advance moves simulation time. Wall-time and call ceilings protect the
runner; hitting them is recorded as a harness limit, never a capability score.
All outcomes are graded at tick 50, including early returns and policy errors.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import queue
import select
import shutil
import subprocess
import tempfile
import threading
import time
import uuid

from lightlag import Config
from lightlag_dynamic.environment import DynamicEnvironment
from lightlag_mcp.service import EpisodeService, ToolError
from lightlag_shift.rule_change import KINDS, RuleChangeEnvironment


IMAGE = "python:3.12-slim"
MAX_LINE_BYTES = 1_000_000
MAX_STDERR_BYTES = 1_000_000


def _digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def make_service(seed, kind):
    """Trusted evaluator factory; never passed into the policy container."""
    config = Config(delay_ticks=3, max_ticks=50)
    if kind in (None, "none", "unchanged"):
        env = DynamicEnvironment(seed=seed, config=config, profile="rush_noisy", noise_level=1.0)
    elif kind in KINDS:
        env = RuleChangeEnvironment(seed=seed, config=config, profile="rush_noisy", noise_level=1.0, kind=kind)
    else:
        raise ValueError("unknown change kind: {!r}".format(kind))
    service = EpisodeService(seed=seed, config=config)
    service._env = env
    return service


def docker_command(image_id, mount, name):
    """No host repository, network, evaluator artifact, key or seed enters the container."""
    return ["docker", "run", "--rm", "-i", "--name", name,
            "--network", "none", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--user", "65534:65534", "--memory", "512m", "--cpus", "1", "--pids-limit", "64",
            "--read-only", "--tmpfs", "/tmp:rw,size=16m,mode=1777", "--workdir", "/tmp",
            "--mount", "type=bind,src={},dst=/w,readonly".format(mount),
            image_id, "python", "-I", "-B", "/w/worker.py"]


def _stdout_reader(stream, messages, stop):
    def put(item):
        while not stop.is_set():
            try:
                messages.put(item, timeout=0.1)
                return
            except queue.Full:
                pass
    try:
        while not stop.is_set():
            line = stream.readline(MAX_LINE_BYTES + 1)
            if not line:
                put(("eof", None))
                return
            if len(line) > MAX_LINE_BYTES:
                put(("error", "worker protocol line exceeds byte limit"))
                return
            put(("line", line))
    except (OSError, ValueError) as failure:
        put(("error", str(failure)))


def _stderr_reader(stream, path):
    remaining = MAX_STDERR_BYTES
    truncated = False
    with path.open("wb") as output:
        while True:
            block = stream.read(65536)
            if not block:
                break
            excess = len(block) > remaining
            output.write(block[:remaining])
            remaining -= min(remaining, len(block))
            if excess and not truncated:
                output.write(b"\n[stderr truncated by evaluator]\n")
                truncated = True


def _reply(stream, payload, deadline):
    data = memoryview((json.dumps(payload, separators=(",", ":")) + "\n").encode())
    fd = stream.fileno()
    while data:
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not select.select([], [fd], [], max(0.0, remaining))[1]:
            raise TimeoutError("worker stopped reading tool replies")
        try:
            written = os.write(fd, data)
        except BlockingIOError:
            continue
        data = data[written:]


def run_case(policy_path, seed, kind, out_dir, *, image=IMAGE,
             call_timeout=30.0, run_timeout=180.0, call_cap=20000):
    """Return a summary and retain evaluator evidence in a new or empty directory.

Each call starts a fresh container/module/episode. The same fixed policy bytes
are copied without edits. Policy errors and invalid public calls are retained;
the evaluator runs out the mission afterward. Limits protect the local runner.
"""
    if call_timeout <= 0 or run_timeout <= 0 or type(call_cap) is not int or call_cap < 1:
        raise ValueError("timeouts and call_cap must be positive")
    policy_path, out_dir = Path(policy_path).resolve(), Path(out_dir).resolve()
    if out_dir.exists() and any(out_dir.iterdir()):
        raise FileExistsError("refusing to overwrite nonempty output directory")
    policy_bytes = policy_path.read_bytes()
    service = make_service(seed, kind)
    image_id = subprocess.check_output(
        ["docker", "image", "inspect", image, "--format", "{{.Id}}"], text=True, timeout=15).strip()
    out_dir.mkdir(parents=True, exist_ok=True)
    name = "rule-transfer-" + uuid.uuid4().hex
    started = time.monotonic()
    errors, calls, invalid_calls = [], 0, 0
    status, return_code = "container_error", None
    stop = threading.Event()
    messages = queue.Queue(maxsize=8)
    worker_path = Path(__file__).with_name("worker.py")
    with tempfile.TemporaryDirectory(prefix="rule-transfer-") as temporary:
        mount = Path(temporary)
        mount.chmod(0o755)
        (mount / "policy.py").write_bytes(policy_bytes)
        shutil.copyfile(worker_path, mount / "worker.py")
        for item in mount.iterdir():
            item.chmod(0o644)
        proc = subprocess.Popen(docker_command(image_id, mount, name), stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        os.set_blocking(proc.stdin.fileno(), False)
        readers = [threading.Thread(target=_stdout_reader, args=(proc.stdout, messages, stop), daemon=True),
                   threading.Thread(target=_stderr_reader, args=(proc.stderr, out_dir / "stderr.txt"), daemon=True)]
        for reader in readers:
            reader.start()
        try:
            with (out_dir / "transcript.jsonl").open("w", encoding="utf-8") as transcript:
                while True:
                    remaining = run_timeout - (time.monotonic() - started)
                    if remaining <= 0:
                        status = "run_timeout"
                        break
                    try:
                        event, value = messages.get(timeout=min(call_timeout, remaining))
                    except queue.Empty:
                        status = "run_timeout" if time.monotonic() - started >= run_timeout else "call_timeout"
                        break
                    if event != "line":
                        errors.append(value or "container exited without a completion message")
                        status = "protocol_error" if event == "error" else "container_error"
                        break
                    try:
                        message = json.loads(value)
                    except (ValueError, UnicodeError):
                        status = "protocol_error"
                        errors.append("worker sent non-JSON output")
                        break
                    if not isinstance(message, dict):
                        status = "protocol_error"
                        errors.append("worker protocol requires an object")
                        break
                    if message.get("method") == "done":
                        if message.get("status") not in ("returned", "policy_error"):
                            status = "protocol_error"
                        else:
                            status = message["status"]
                            if status == "policy_error":
                                errors.append(str(message.get("error", "unspecified policy error"))[:2000])
                        break
                    if set(message) != {"method", "params"} or not isinstance(message["method"], str) or not isinstance(message["params"], dict):
                        status = "protocol_error"
                        errors.append("invalid worker tool-call schema")
                        break
                    if calls >= call_cap:
                        status = "call_cap"
                        break
                    calls += 1
                    record = {"n": calls, "tool": message["method"], "arguments": message["params"],
                              "tick_before": service._tick}
                    try:
                        result = service.call(message["method"], message["params"])
                        reply = {"ok": True, "result": result}
                        record.update(reply)
                    except ToolError as failure:
                        invalid_calls += 1
                        reply = {"ok": False, "error": str(failure)}
                        record.update(reply)
                    record["tick_after"] = service._tick
                    transcript.write(json.dumps(record, separators=(",", ":")) + "\n")
                    transcript.flush()
                    try:
                        _reply(proc.stdin, reply, min(started + run_timeout, time.monotonic() + call_timeout))
                    except (OSError, TimeoutError) as failure:
                        status = "container_error" if isinstance(failure, OSError) else "call_timeout"
                        errors.append(str(failure))
                        break
            if status in ("returned", "policy_error"):
                try:
                    return_code = proc.wait(timeout=3)
                    if return_code != 0:
                        errors.append("container exited with code {}".format(return_code))
                        status = "container_error"
                except subprocess.TimeoutExpired:
                    status = "container_error"
                    errors.append("worker did not exit after reporting completion")
        finally:
            stop.set()
            try:
                subprocess.run(["docker", "rm", "-f", name], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, timeout=15, check=False)
            except (OSError, subprocess.TimeoutExpired) as failure:
                errors.append("container cleanup failed: {}".format(failure))
                status = "container_error"
            if proc.poll() is None:
                proc.kill()
            return_code = proc.wait(timeout=5)
            for reader in readers:
                reader.join(timeout=2)
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                stream.close()
    if status == "returned" and invalid_calls:
        status = "invalid_calls"
    evaluation = service.finish()
    replay = service._env.replay()
    summary = {"schema": "rule-transfer-case-v1", "seed": seed, "kind": kind or "none",
               "status": status, "errors": errors, "invalid_calls": invalid_calls, "public_calls": calls,
               "evaluation": evaluation, "normalized_score": evaluation["raw_score"] / evaluation["max_available_value"],
               "final_tick": replay["states"][-1]["tick"], "policy_sha256": hashlib.sha256(policy_bytes).hexdigest(),
               "worker_sha256": _digest(worker_path), "runner_sha256": _digest(__file__),
               "image_requested": image, "image_id": image_id, "container_name": name,
               "container_exit_code": return_code, "elapsed_seconds": time.monotonic() - started,
               "limits": {"call_timeout": call_timeout, "run_timeout": run_timeout, "call_cap": call_cap},
               "model_calls": 0}
    (out_dir / "replay.json").write_text(json.dumps(replay, separators=(",", ":")) + "\n")
    (out_dir / "result.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary
