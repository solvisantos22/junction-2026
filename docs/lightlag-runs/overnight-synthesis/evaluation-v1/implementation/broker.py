#!/usr/bin/env python3
"""Frozen one-shot synthesis experiment; prepare is offline and historical only.

Only synthesize may contact a provider, and only the root operator runs it.
Never import generated code on the host. All output directories are new-only.
"""

from __future__ import annotations

import argparse
import ast
from collections import Counter
from copy import deepcopy
import hashlib
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import selectors
import subprocess
import sys
import time
from types import SimpleNamespace
import uuid

sys.dont_write_bytecode = True
SOURCE_COMMIT = "02e4f7062ec3feaca14d9cc2eeb953af870ba769"
PROTOCOL_COMMIT = "7f9f57c63a9665cd158327eb7d46ac7f32cca571"
PROTOCOL_PATH = "docs/lightlag-synthesis-experiment.md"
SOURCE_PATHS = (
    "lightlag/__init__.py", "lightlag/environment.py", "lightlag/model.py",
    "lightlag_dynamic/__init__.py", "lightlag_dynamic/controllers.py",
    "lightlag_dynamic/environment.py", "lightlag_dynamic/kf_mpc.py",
    "lightlag_dynamic/missions.py", "lightlag_dynamic/tools.py", "lightlag_dynamic/serve.py",
    "lightlag_mcp/__init__.py", "lightlag_mcp/service.py",
)
PUBLIC_NAMES = ("rules", "map", "telemetry_log", "uplink", "advance")
PROFILES = ("rush", "rush_noisy")
LIMITS = {"policy_calls": 500, "seconds_after_launch": 60, "cpus": 1,
          "memory_bytes": 256 * 1024**2, "pids": 64, "tmp_bytes": 64 * 1024**2,
          "request_line_bytes": 65536, "stderr_bytes": 65536, "response_bytes": 1024**2,
          "python_hash_seed": 0, "python_random_seed": 0}


class GuardError(RuntimeError):
    pass


class ProtocolError(ValueError):
    pass


class PublicCallError(ValueError):
    pass


class CallLimit(PublicCallError):
    pass


class InfrastructureError(RuntimeError):
    pass


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode() + b"\n"


def write_json(path, value):
    with Path(path).open("xb") as stream:
        stream.write(canonical(value))


def read_json(path):
    return json.loads(Path(path).read_bytes())


def claim_output(path):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=False)
    return path


def git_bytes(repo, commit, path):
    return subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=repo)


def freeze_source(repo, destination):
    content = {name: git_bytes(repo, SOURCE_COMMIT, name) for name in SOURCE_PATHS}
    destination = claim_output(destination)
    for name, data in content.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        target.chmod(0o444)
    hashes = {name: sha256(data) for name, data in content.items()}
    verify_source(destination, hashes)
    return hashes


def verify_source(root, expected):
    root = Path(root).resolve()
    actual = {str(path.relative_to(root)) for path in root.rglob("*.py")}
    if actual != set(expected):
        raise GuardError("frozen source closure changed")
    for name, digest in expected.items():
        path = root / name
        if path.is_symlink() or not path.is_file() or sha256(path.read_bytes()) != digest:
            raise GuardError("frozen source bytes changed: " + name)


def load_runtime(root, hashes):
    """Imports must originate in the separately verified snapshot, never the checkout."""
    root = Path(root).resolve()
    verify_source(root, hashes)
    if os.environ.get("LIGHTLAG_REPO"):
        raise GuardError("LIGHTLAG_REPO injection is forbidden")
    for name, module in tuple(sys.modules.items()):
        if name.split(".")[0] in ("lightlag", "lightlag_dynamic", "lightlag_mcp"):
            if not getattr(module, "__file__", None) or root not in Path(module.__file__).resolve().parents:
                raise GuardError("a simulator package was already imported outside the frozen snapshot")
    sys.path.insert(0, str(root))
    core = importlib.import_module("lightlag")
    serving = importlib.import_module("lightlag_dynamic.serve")
    controllers = importlib.import_module("lightlag_dynamic.controllers")
    importlib.import_module("lightlag_dynamic.kf_mpc")
    service = importlib.import_module("lightlag_mcp.service")
    imported = {}
    for name, module in tuple(sys.modules.items()):
        if name.split(".")[0] in ("lightlag", "lightlag_dynamic", "lightlag_mcp"):
            path = Path(module.__file__).resolve()
            if root not in path.parents:
                raise GuardError("simulator import escaped its snapshot")
            relative = str(path.relative_to(root))
            if relative not in hashes or sha256(path.read_bytes()) != hashes[relative]:
                raise GuardError("unrecorded or changed imported simulator source")
            imported[relative] = hashes[relative]
    if set(imported) != set(hashes):
        raise GuardError("source closure includes an unverified import")
    return SimpleNamespace(Config=core.Config, Service=serving.DynamicEpisodeService,
                           ToolError=service.ToolError, reference=controllers.kf_mpc,
                           root=root, hashes=hashes, imported=imported)


def sanitize_text(message):
    return re.sub(r"/(?:Users|home|private/tmp|tmp|var/folders)/[^\s'\"]+", "<LOCAL_PATH>", message)


def error_record(error):
    return {"type": type(error).__name__, "message": sanitize_text(str(error))[:2048]}


class Broker:
    """Trusted wrapper: frozen service semantics, complete JSON requests/responses.

    The generated process never receives this instance, its service, seed or truth.
    Trusted KF uses the same call function via a five-method facade.
    """

    def __init__(self, runtime, seed, profile):
        self.runtime, self.seed, self.profile = runtime, seed, profile
        self.service = runtime.Service(seed, profile, runtime.Config(delay_ticks=3, max_ticks=50),
                                       noise_level=1.0, bumpiness=0.0)
        self.transcript = []
        self.policy_calls = 0

    def call(self, tool, arguments):
        self.policy_calls += 1
        record = {"n": self.policy_calls, "actor": "policy", "tool": tool,
                  "arguments": deepcopy(arguments), "tick_before": self.service._tick}
        try:
            if self.policy_calls > LIMITS["policy_calls"]:
                raise CallLimit("maximum of 500 public calls exceeded")
            if not isinstance(arguments, dict) or not isinstance(tool, str):
                raise PublicCallError("tool must be a string and arguments a JSON object")
            # JSON round trip also prevents a local reference from mutating service data.
            result = self.service.call(tool, json.loads(canonical(arguments)))
            result = json.loads(canonical(result))
        except (self.runtime.ToolError, PublicCallError) as error:
            record.update(ok=False, error=error_record(error), tick_after=self.service._tick)
            self.transcript.append(record)
            if isinstance(error, CallLimit):
                raise
            raise PublicCallError(str(error)) from None
        record.update(ok=True, response=deepcopy(result), tick_after=self.service._tick)
        self.transcript.append(record)
        return result

    def tools(self):
        call = self.call

        class Tools:
            __slots__ = ()

            def rules(self):
                return call("rules", {})

            def map(self):
                return call("map", {})

            def telemetry_log(self):
                return call("telemetry_log", {})

            def uplink(self, commands):
                return call("uplink", {"commands": commands})

            def advance(self, ticks=1):
                return call("advance", {"ticks": ticks})

        return Tools()

    def finish(self, execution):
        # Keep the original finish() path. Wrap only its advance to retain the
        # evaluator's full responses for independent transcript reconstruction.
        env = self.service._env
        original_advance = env.advance

        def recorded_advance(ticks):
            before = env._tick
            response = original_advance(ticks)
            self.transcript.append({"n": len(self.transcript) + 1, "actor": "evaluator",
                                    "tool": "advance", "arguments": {"ticks": ticks}, "ok": True,
                                    "response": deepcopy(response), "tick_before": before,
                                    "tick_after": env._tick})
            return response

        env.advance = recorded_advance
        try:
            result = self.service.finish()
            replay = env.replay()
        finally:
            env.advance = original_advance
        return {"seed": self.seed, "profile": self.profile, "delay": 3, "horizon": 50,
                "noise_level": 1.0, "bumpiness": 0.0, "execution": execution,
                "grading_status": "scored", "result": result, "replay": replay,
                "transcript": self.transcript, "policy_calls": self.policy_calls,
                "accepted_service_calls": result["tool_calls"]}


def replay_episode(runtime, episode):
    check = Broker(runtime, episode["seed"], episode["profile"])
    for record in episode["transcript"]:
        if record["actor"] != "policy":
            continue
        try:
            check.call(record["tool"], record["arguments"])
        except PublicCallError:
            pass
        if check.transcript[-1] != record:
            raise GuardError("public call failed exact reconstruction")
    rebuilt = check.finish(episode["execution"])
    for key in ("transcript", "result", "replay", "policy_calls", "accepted_service_calls"):
        if rebuilt[key] != episode[key]:
            raise GuardError("episode failed exact reconstruction: " + key)
    return {"exact": True, "calls": len(episode["transcript"]),
            "replay_sha256": sha256(canonical(episode["replay"])),
            "transcript_sha256": sha256(canonical(episode["transcript"]))}


def decode_message(data):
    try:
        value = json.loads(data, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
        canonical(value)  # Also rejects exponent overflow such as 1e9999.
    except (ValueError, UnicodeError, RecursionError, OverflowError) as error:
        raise ProtocolError("invalid or nonfinite JSON message") from error
    return value


def parse_call(data, next_id):
    value = decode_message(data)
    if not isinstance(value, dict) or set(value) != {"id", "tool", "arguments"}:
        raise ProtocolError("request must contain exactly id, tool and arguments")
    if type(value["id"]) is not int or value["id"] != next_id:
        raise ProtocolError("request sequence is invalid")
    if not isinstance(value["tool"], str) or not isinstance(value["arguments"], dict):
        raise ProtocolError("tool must be a string and arguments an object")
    return value


def extract_module(text):
    trimmed = text.rstrip()
    lines = trimmed.splitlines(keepends=True)
    if len(lines) >= 2 and re.fullmatch(r"```(?:python|py)?\s*", lines[0].rstrip("\r\n")):
        if lines[-1].strip() == "```" and not any(line.lstrip().startswith("```") for line in lines[1:-1]):
            return "".join(lines[1:-1]).rstrip()
    return trimmed


API_DOCUMENTATION = """The Python tools object has exactly these methods:
- rules() -> dict: the authoritative public rules shown below.
- map() -> dict: width:number, height:number, base:[x,y], default_terrain:string, hazards:[rect],
  sand:[rect], targets:[target]. A rect has x1,y1,x2,y2. A target has id:string,
  x:number,y:number,value:number,deadline_tick:integer|null,late_value:number,
  appear_tick:integer. Only announced targets appear; refresh after discovery.
- telemetry_log() -> [packet]: all delivered packets including the exact tick-0 briefing.
- uplink(commands:list[dict]) -> [ack]: accepts 1..5 drive/sample/wait commands.
  drive: {"action":"drive","heading_deg":number,"metres":number in (0,5]}.
  sample/wait: {"action":"sample"} or {"action":"wait"}.
  ack: command_id:integer,sent_tick:integer,execute_tick:integer,command:dict.
- advance(ticks:int=1) -> {current_tick:int,episode_complete:bool,packets:[packet]}.
  ticks is 1..5, clipped to the horizon. Only advance moves simulated time.
A packet has tick:int,received_tick:int,position:[x,y],heading_deg:number,
battery:number,terrain:string,wheel_odometry:number,visual_odometry:number,
sampled_targets:[string],alive:bool,events:[dict]. Events include command_executed
(command_id), sample_taken (target_id,on_time), sample_failed (reason),
safety_stop (reason), battery_depleted, and target_discovered (target).
Bad requests raise ValueError. Your process has no simulator, reset, grade or
hidden-state API. It starts with no map. Obtain observations from tools only.
"""


def build_request(instruction, aid, rules):
    system = (
        "Write one reusable, deterministic standard-library Python controller module. "
        "Return only its complete source, defining play(tools). Do not run experiments or "
        "request external tools. The same unedited module will operate on multiple new maps. "
        "It may retain state within each invocation, but each episode has a fresh process. "
        "Do not read files, environment variables, networks or subprocesses; interact only "
        "through the five supplied methods. No numeric library is installed."
    )
    user = (
        "Implement play(tools) to maximize protected terminal mission reward on both public profiles.\n\n"
        "Original public mission instruction (verbatim):\n" + instruction
        + "\n\nGeneric accounting aid (verbatim):\n" + aid
        + "\n\nInterface and clarification:\n" + API_DOCUMENTATION
        + "\nThe profiles' authoritative rules override general wording in the original instruction: "
        "map() includes only initially known or already announced targets. Position and visual "
        "odometry are noisy when sensing is enabled; wheel odometry and battery follow the rules. "
        "Returning from play or an uncaught error ends interaction, but accepted commands still "
        "execute and idle drain continues to tick 50 before grading. At most 500 public calls "
        "and 60 seconds of wall time are available per episode. Use deterministic computation. "
        "The module must be self-contained and use only the Python standard library.\n\n"
        "Public rules by profile (no episode map or observations supplied):\n"
        + json.dumps(rules, sort_keys=True, indent=2)
    )
    return {"model": "claude-opus-5-5", "max_tokens": 24000,
            "thinking": {"type": "adaptive"}, "output_config": {"effort": "high"},
            "speed": "standard", "service_tier": "standard_only",
            "system": system, "messages": [{"role": "user", "content": user}]}


def docker_command(docker, image, policy, worker, name):
    if not re.fullmatch(r"(?:docker.io/library/)?python(?:[^@\s]*)?@sha256:[0-9a-f]{64}", image):
        raise GuardError("worker requires a pinned official Python image digest")
    return [str(docker), "run", "--pull=never", "--rm", "-i", "--name=" + name,
            "--label=org.lightlag.synthesis=" + name,
            "--read-only", "--network=none", "--cap-drop=ALL", "--user=65534:65534",
            "--cpus=1", "--memory=256m", "--memory-swap=256m", "--pids-limit=64",
            "--security-opt=no-new-privileges", "--ulimit=nofile=128:128",
            "--tmpfs=/tmp:rw,noexec,nosuid,nodev,size=64m,mode=1777", "--workdir=/app",
            "--env=PYTHONHASHSEED=0", "--env=PYTHONDONTWRITEBYTECODE=1",
            "--mount", f"type=bind,source={Path(policy).resolve()},target=/app/policy.py,readonly",
            "--mount", f"type=bind,source={Path(worker).resolve()},target=/app/worker.py,readonly",
            image, "python", "-s", "-P", "-B", "/app/worker.py"]


def inspect_container(docker, name):
    item = json.loads(subprocess.check_output([docker, "inspect", name], timeout=10))[0]
    host = item["HostConfig"]
    # Publish only isolation configuration, never host paths or process environment.
    report = {key: host[key] for key in ("NetworkMode", "ReadonlyRootfs", "Memory", "MemorySwap",
                                         "NanoCpus", "PidsLimit", "CapDrop", "SecurityOpt", "Tmpfs")}
    report.update(user=item["Config"]["User"], image_id=item["Image"],
                  mounts=[{"destination": m["Destination"], "type": m["Type"], "writable": m["RW"]}
                          for m in item["Mounts"]])
    good = (report["NetworkMode"] == "none" and report["ReadonlyRootfs"]
            and report["Memory"] == report["MemorySwap"] == LIMITS["memory_bytes"]
            and report["NanoCpus"] == 10**9 and report["PidsLimit"] == 64
            and report["CapDrop"] == ["ALL"] and report["user"] == "65534:65534"
            and "no-new-privileges" in report["SecurityOpt"]
            and len(report["mounts"]) == 2
            and {m["destination"] for m in report["mounts"]} == {"/app/policy.py", "/app/worker.py"}
            and all(m["type"] == "bind" and not m["writable"] for m in report["mounts"]))
    if not good:
        raise InfrastructureError("actual container isolation differs from declared limits")
    return report


def remove_owned_container(docker, name):
    """Inspect the unique ownership label; never remove an unowned container."""
    query = [docker, "container", "inspect", "--format", '{{ index .Config.Labels "org.lightlag.synthesis" }}', name]
    try:
        check = subprocess.run(query, capture_output=True, timeout=10)
        if check.returncode:
            absent = b"No such container" in check.stderr or b"No such object" in check.stderr
            return {"confirmed_absent": absent, "removed_owned_container": False}
        if check.stdout.decode().strip() != name:
            return {"confirmed_absent": False, "error": "ownership label mismatch; container untouched"}
        removed = subprocess.run([docker, "rm", "-f", name], capture_output=True, timeout=10)
        check = subprocess.run(query, capture_output=True, timeout=10)
        absent = check.returncode != 0 and (b"No such container" in check.stderr or b"No such object" in check.stderr)
        return {"confirmed_absent": absent, "removed_owned_container": removed.returncode == 0}
    except Exception as error:
        return {"confirmed_absent": False, "error": error_record(error)}


def run_container(broker, policy, worker, image, docker, *, seconds=60):
    """Bound both pipes and wall time; never execute the returned module on the host."""
    name = "lightlag-synthesis-" + uuid.uuid4().hex
    command = docker_command(docker, image, policy, worker, name)
    started = time.monotonic()
    process = None
    selector = selectors.DefaultSelector()
    output, errors, pending = bytearray(), bytearray(), bytearray()
    ready, terminal, isolation = False, None, None
    next_id = 1
    status, failure, python_version, cleanup = None, None, None, None
    try:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for stream in (process.stdin, process.stdout, process.stderr):
            os.set_blocking(stream.fileno(), False)
        selector.register(process.stdout, selectors.EVENT_READ, "out")
        selector.register(process.stderr, selectors.EVENT_READ, "err")
        while True:
            left = seconds - (time.monotonic() - started)
            if left <= 0:
                status = "policy_timeout" if ready else "infrastructure_error"
                failure = {"type": "WallTimeLimit", "message": "worker exceeded its wall-clock limit"}
                break
            if process.poll() is not None and not selector.get_map():
                if terminal and process.returncode == 0:
                    status, failure = terminal["status"], terminal["error"]
                elif ready:
                    status = "policy_process_error"
                    failure = {"type": "WorkerExit", "message": f"worker exit {process.returncode}"}
                else:
                    status = "infrastructure_error"
                    failure = {"type": "ContainerLaunchError", "message": "worker did not become ready"}
                break
            for key, _ in selector.select(min(left, 0.1)):
                if key.data == "in":
                    try:
                        amount = os.write(key.fileobj.fileno(), pending)
                        del pending[:amount]
                    except BrokenPipeError:
                        pending.clear()
                    if not pending:
                        selector.unregister(key.fileobj)
                    continue
                data = os.read(key.fileobj.fileno(), 8192)
                if not data:
                    selector.unregister(key.fileobj)
                    continue
                if key.data == "err":
                    errors.extend(data)
                    if len(errors) > LIMITS["stderr_bytes"]:
                        raise ProtocolError("worker diagnostic output exceeded its limit")
                    continue
                output.extend(data)
                if len(output) > LIMITS["request_line_bytes"]:
                    raise ProtocolError("worker RPC line exceeded its limit")
                while b"\n" in output:
                    line, _, rest = output.partition(b"\n")
                    output = bytearray(rest)
                    if not ready:
                        hello = decode_message(line)
                        if not isinstance(hello, dict) or set(hello) != {"ready", "python"} or hello["ready"] is not True:
                            raise InfrastructureError("worker readiness handshake is invalid")
                        ready, python_version = True, hello["python"]
                        isolation = inspect_container(docker, name)
                        pending.extend(canonical({"start": True}))
                        selector.register(process.stdin, selectors.EVENT_WRITE, "in")
                        continue
                    value = decode_message(line)
                    if isinstance(value, dict) and value.get("done") is True:
                        if terminal or set(value) != {"done", "status", "error"} or value["status"] not in ("returned", "policy_error"):
                            raise ProtocolError("worker terminal envelope is invalid")
                        failure_detail = value["error"]
                        if value["status"] == "returned":
                            if failure_detail is not None:
                                raise ProtocolError("successful terminal envelope must have no error")
                        elif (not isinstance(failure_detail, dict) or set(failure_detail) != {"type", "message"}
                              or not all(isinstance(item, str) for item in failure_detail.values())):
                            raise ProtocolError("worker error must contain string type and message")
                        terminal = value
                        continue
                    if terminal:
                        raise ProtocolError("worker sent calls after termination")
                    request = parse_call(line, next_id)
                    next_id += 1
                    if broker is None:
                        raise ProtocolError("isolation canary may not call episode tools")
                    try:
                        response = broker.call(request["tool"], request["arguments"])
                        reply = {"id": request["id"], "ok": True, "response": response}
                    except CallLimit as error:
                        status, failure = "policy_call_limit", error_record(error)
                        break
                    except PublicCallError as error:
                        reply = {"id": request["id"], "ok": False, "error": error_record(error)}
                    except Exception as error:
                        raise InfrastructureError("trusted public service failed: " + type(error).__name__) from error
                    encoded = canonical(reply)
                    if len(encoded) > LIMITS["response_bytes"]:
                        raise InfrastructureError("public response exceeded the configured transport bound")
                    if pending:
                        raise ProtocolError("worker issued a call without consuming its previous response")
                    pending.extend(encoded)
                    selector.register(process.stdin, selectors.EVENT_WRITE, "in")
                if status:
                    break
            if status:
                break
    except (ProtocolError, ValueError, UnicodeError) as error:
        status = "policy_protocol_error" if ready else "infrastructure_error"
        failure = error_record(error)
    except Exception as error:
        status, failure = "infrastructure_error", error_record(error)
    finally:
        selector.close()
        if process is not None:
            cleanup = remove_owned_container(docker, name)
            if process.poll() is None:
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)
            for stream in (process.stdin, process.stdout, process.stderr):
                stream.close()
            if not cleanup["confirmed_absent"]:
                status, failure = "infrastructure_error", {"type": "ContainerCleanupError", "message": "owned container removal could not be confirmed"}
    return {"status": status, "error": failure, "elapsed_seconds": time.monotonic() - started,
            "wall_limit_seconds": seconds, "worker_ready": ready, "worker_python": python_version,
            "process_returncode": None if process is None else process.returncode,
            "stderr": sanitize_text(errors[:LIMITS["stderr_bytes"]].decode("utf-8", errors="replace")),
            "stderr_raw_sha256": sha256(bytes(errors)),
            "stderr_truncated": len(errors) > LIMITS["stderr_bytes"], "isolation": isolation, "cleanup": cleanup}


ISOLATION_CANARY = '''import errno, json, os, socket
from pathlib import Path
def play(tools):
    status = dict(line.split(":", 1) for line in Path("/proc/self/status").read_text().splitlines() if ":" in line)
    denied = {}
    for name in ("/forbidden-write", "/app/policy.py", "/app/worker.py"):
        try:
            with open(name, "ab") as stream: stream.write(b"x")
            denied[name] = False
        except OSError: denied[name] = True
    with open("/tmp/probe", "w") as stream: stream.write("temporary")
    sock = socket.socket()
    sock.settimeout(1)
    unreachable = sock.connect_ex(("192.0.2.1", 9)) in (errno.ENETUNREACH, errno.EHOSTUNREACH)
    sock.close()
    checks = {"nonroot": os.getuid() == 65534 and os.getgid() == 65534,
      "no_capabilities": int(status["CapEff"].strip(), 16) == 0,
      "no_new_privileges": status["NoNewPrivs"].strip() == "1",
      "network_unreachable": unreachable,
      "no_up_external_interfaces": all(name == "lo" or not int(Path("/sys/class/net", name, "flags").read_text(), 16) & 1 for _, name in socket.if_nameindex()),
      "read_only_files": all(denied.values()), "temporary_write": Path("/tmp/probe").read_text() == "temporary",
      "only_two_app_files": sorted(os.listdir("/app")) == ["policy.py", "worker.py"],
      "no_project_packages": not any(Path(p).exists() for p in ("/repo", "/workspace", "/evaluator", "/var/run/docker.sock")),
      "memory_limit": Path("/sys/fs/cgroup/memory.max").read_text().strip() == "268435456",
      "pids_limit": Path("/sys/fs/cgroup/pids.max").read_text().strip() == "64",
      "cpu_limit": Path("/sys/fs/cgroup/cpu.max").read_text().strip() == "100000 100000",
      "clean_environment": set(os.environ) <= {"PATH","HOSTNAME","LANG","GPG_KEY","PYTHON_VERSION","PYTHON_SHA256","PYTHONHASHSEED","PYTHONDONTWRITEBYTECODE","HOME"}}
    print("ISOLATION:" + json.dumps(checks, sort_keys=True))
'''


def isolation_probe(image, docker, worker, output):
    output = claim_output(output)
    canary = output / "isolation-canary.py"
    canary.write_text(ISOLATION_CANARY)
    execution = run_container(None, canary, worker, image, docker, seconds=10)
    lines = [line.removeprefix("ISOLATION:") for line in execution["stderr"].splitlines() if line.startswith("ISOLATION:")]
    checks = json.loads(lines[0]) if len(lines) == 1 else {}
    report = {"execution": execution, "checks": checks,
              "passed": execution["status"] == "returned" and bool(checks) and all(checks.values()),
              "canary_sha256": sha256(canary.read_bytes())}
    write_json(output / "isolation.json", report)
    if not report["passed"]:
        raise GuardError("actual Docker isolation canary failed; see retained report")
    return report


def run_reference(runtime, seed, profile):
    broker = Broker(runtime, seed, profile)
    started = time.monotonic()
    try:
        runtime.reference(broker.tools())
        execution = {"status": "returned", "error": None}
    except Exception as error:
        execution = {"status": "policy_error", "error": error_record(error)}
    execution.update(elapsed_seconds=time.monotonic() - started, runtime="trusted local Python",
                     wall_limit_seconds=None)
    return broker.finish(execution)


def historical_gate(repo, runtime, output):
    rows, inputs = [], {}
    for profile in PROFILES:
        for seed in range(501, 505):
            verify_source(runtime.root, runtime.hashes)
            relative = f"docs/lightlag-runs/{profile.replace('_', '-')}-seed{seed}-delay3-kf-mpc"
            directory = Path(repo) / relative
            names = ("experiment.json", "artifacts/evaluator/replay.json", "artifacts/evaluator/result.json", "verifier/reward.txt")
            for name in names:
                inputs[relative + "/" + name] = sha256((directory / name).read_bytes())
            manifest = read_json(directory / "experiment.json")
            if manifest["source_commit"] != SOURCE_COMMIT or manifest["source_dirty"]:
                raise GuardError("historical reference was not frozen cleanly")
            for name, digest in runtime.hashes.items():
                if manifest["source_sha256"].get(name) != digest:
                    raise GuardError("historical reference source differs: " + name)
            episode = run_reference(runtime, seed, profile)
            filename = f"historical-{profile}-{seed}.json"
            write_json(output / filename, episode)
            expected = read_json(directory / "artifacts/evaluator/result.json")
            score = episode["result"]["raw_score"] / episode["result"]["max_available_value"]
            checks = {"full_replay_exact": episode["replay"] == read_json(directory / "artifacts/evaluator/replay.json"),
                      "full_result_exact": episode["result"] == expected,
                      "public_call_count_exact": episode["policy_calls"] == expected["tool_calls"],
                      "rounded_reward_exact": f"{score:.6f}" == (directory / "verifier/reward.txt").read_text().strip(),
                      "reference_returned": episode["execution"]["status"] == "returned"}
            independent = replay_episode(runtime, episode)
            row = {"profile": profile, "seed": seed, "episode": filename, "reward": score,
                   "checks": checks, "independent_replay": independent, "passed": all(checks.values())}
            rows.append(row)
            if not row["passed"]:
                write_json(output / "historical-gate.json", {"passed": False, "rows": rows, "input_sha256": inputs})
                raise GuardError("historical gate failed; no fresh maps may run")
    report = {"passed": True, "rows": rows, "input_sha256": inputs}
    write_json(output / "historical-gate.json", report)
    return report


def original_instruction(repo):
    """Rebuild the frozen public task text without executing the task generator."""
    base_path, generator_path = "harbor/lightlag/instruction.md", "tools/lightlag_experiments/prepare.py"
    base, generator = (git_bytes(repo, SOURCE_COMMIT, path) for path in (base_path, generator_path))
    tree = ast.parse(generator)
    extras = [ast.literal_eval(node.value) for node in ast.walk(tree)
              if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "extra" for target in node.targets)]
    if len(extras) != 1 or base.decode().count("total value on the map") != 1:
        raise GuardError("frozen instruction reconstruction is ambiguous")
    instruction = base.decode().replace("total value on the map", "total maximum value generated for the mission") + extras[0]
    for profile in PROFILES:
        for seed in range(501, 505):
            path = Path(repo) / f"docs/lightlag-runs/{profile.replace('_', '-')}-seed{seed}-delay3-kf-mpc/experiment.json"
            if read_json(path)["task_sha256"]["instruction.md"] != sha256(instruction.encode()):
                raise GuardError("public instruction differs from a frozen historical task")
    return instruction, {base_path: sha256(base), generator_path: sha256(generator)}


def verify_preparation(root, manifest):
    root = Path(root)
    for name, expected in manifest["artifact_sha256"].items():
        path = root / name
        if Path(name).is_absolute() or ".." in Path(name).parts or path.is_symlink():
            raise GuardError("invalid prepared artifact path")
        if not path.is_file() or sha256(path.read_bytes()) != expected:
            raise GuardError("prepared artifact changed: " + name)


def verify_historical_inputs(repo, manifest):
    for name, expected in manifest["historical_input_sha256"].items():
        path = Path(repo) / name
        if not path.is_file() or sha256(path.read_bytes()) != expected:
            raise GuardError("historical evidence changed: " + name)


def container_error_probes(runtime, image, docker, worker, output):
    output.mkdir()
    cases = (
        ("accepted-then-error", "def play(t):\n t.uplink([{'action':'drive','heading_deg':0,'metres':1}])\n raise RuntimeError('transport canary')\n", 10, "policy_error"),
        ("syntax-error", "def play(:\n", 10, "policy_error"),
        ("deadline", "def play(t):\n t.rules()\n while True: pass\n", 1, "policy_timeout"),
        ("call-limit", "def play(t):\n for i in range(501): t.rules()\n", 10, "policy_call_limit"),
    )
    reports = []
    for name, content, seconds, expected in cases:
        path = output / (name + ".py")
        path.write_text(content)
        broker = Broker(runtime, 501, "rush")
        execution = run_container(broker, path, worker, image, docker, seconds=seconds)
        episode = broker.finish(execution)
        exact = replay_episode(runtime, episode)
        checks = {"expected_status": execution["status"] == expected,
                  "full_horizon": episode["result"]["tick"] == 50,
                  "container_removed": execution["cleanup"]["confirmed_absent"],
                  "exact_replay": exact["exact"]}
        if name == "accepted-then-error":
            checks["accepted_command_retained"] = len(episode["replay"]["commands"]) == 1
        write_json(output / (name + ".json"), episode)
        report = {"fixture": name, "checks": checks, "passed": all(checks.values())}
        reports.append(report)
        if not report["passed"]:
            raise GuardError("container error canary failed: " + name)
    return reports


def prepare(repo, output, source_root, image, docker):
    repo, source_root, output = Path(repo).resolve(), Path(source_root).resolve(), Path(output)
    if source_root == repo or repo in source_root.parents:
        raise GuardError("frozen source snapshot must be outside the mutable checkout")
    # Claim both destinations before any simulation. Existing evidence is never reused.
    output = claim_output(output)
    try:
        hashes = freeze_source(repo, source_root)
        runtime = load_runtime(source_root, hashes)
        worker_source = Path(__file__).with_name("overnight_synthesis_worker.py")
        (output / "worker.py").write_bytes(worker_source.read_bytes())
        (output / "runner.py").write_bytes(Path(__file__).read_bytes())
        (output / "protocol.md").write_bytes(git_bytes(repo, PROTOCOL_COMMIT, PROTOCOL_PATH))
        instruction, instruction_sources = original_instruction(repo)
        aid_path = "tools/lightlag_experiments/ledger_aid_v1.md"
        aid = git_bytes(repo, PROTOCOL_COMMIT, aid_path)
        (output / "instruction.md").write_text(instruction)
        (output / "accounting-aid.md").write_bytes(aid)
        rules = {}
        for profile in PROFILES:
            rules[profile] = Broker(runtime, 501, profile).call("rules", {})
            if rules[profile] != Broker(runtime, 502, profile).call("rules", {}):
                raise GuardError("public rules unexpectedly contain episode-dependent values")
        request = build_request(instruction, aid.decode(), rules)
        write_json(output / "request.json", request)
        write_json(output / "public-rules.json", rules)
        (output / "interface.md").write_text(API_DOCUMENTATION)
        write_json(output / "planned-cells.json", [{"profile": p, "seed": s, "status": "unrun"}
                                                    for p in PROFILES for s in range(60000, 60020)])
        image_info = json.loads(subprocess.check_output([docker, "image", "inspect", image], timeout=10))[0]
        if image not in image_info["RepoDigests"]:
            raise GuardError("pinned image is not locally resolved under the requested digest")
        isolation = isolation_probe(image, docker, output / "worker.py", output / "isolation")
        errors = container_error_probes(runtime, image, docker, output / "worker.py", output / "error-probes")
        gate_dir = output / "historical"
        gate_dir.mkdir()
        gate = historical_gate(repo, runtime, gate_dir)
        verify_source(source_root, hashes)
        sdk = importlib.metadata.version("anthropic")
        manifest = {
            "schema_version": 1, "status": "prepared_no_provider_calls_no_fresh_maps",
            "source_commit": SOURCE_COMMIT, "protocol_commit": PROTOCOL_COMMIT,
            "source_sha256": hashes, "imported_source_sha256": runtime.imported,
            "historical_input_sha256": gate["input_sha256"], "instruction_source_sha256": instruction_sources,
            "instruction_sha256": sha256(instruction.encode()), "accounting_aid_sha256": sha256(aid),
            "request_sha256": sha256(canonical(request)), "limits": LIMITS,
            "worker_image": {"reference": image, "id": image_info["Id"], "os": image_info["Os"],
                             "architecture": image_info["Architecture"], "python": isolation["execution"]["worker_python"]},
            "host_runtime": {"python": platform.python_version(), "implementation": platform.python_implementation(),
                             "system": platform.system(), "machine": platform.machine(), "anthropic_sdk": sdk,
                             "simulator_dependencies": "Python standard library only"},
            "transport": "newline-delimited JSON over Docker stdin/stdout; only five public methods",
            "sdk_max_retries": 0, "sampling_overrides": None, "prompt_caching": False,
            "pricing_usd_per_million": {"uncached_input": 4, "output_including_thinking": 20},
            "cost_preflight": {"input_allowance": "ceil(1.25 * estimated_input_tokens) + 1000",
                               "maximum_estimate_usd": 0.90, "reservation_usd": 1.00, "count_called": False},
            "historical_gate_passed": gate["passed"], "isolation_passed": isolation["passed"],
            "error_probes": errors,
            "runtime_asymmetry": "generated policy: fresh constrained Docker process; original KF: trusted local Python; no timing efficiency comparison",
            "artifact_sha256": {str(path.relative_to(output)): sha256(path.read_bytes())
                                for path in sorted(output.rglob("*")) if path.is_file()},
        }
        write_json(output / "preparation.json", manifest)
        verify_preparation(output, manifest)
        return manifest
    except Exception as error:
        write_json(output / "preparation-failure.json", {"status": "preparation_failed", "error": error_record(error),
                                                         "provider_calls": 0, "fresh_maps_constructed": 0})
        raise


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in ("synthesize", "evaluate"):
        suffix = "api" if argv[0] == "synthesize" else "evaluate"
        path = Path(__file__).with_name("overnight_synthesis_" + suffix + ".py")
        if not path.is_file():
            raise GuardError("requested phase is not implemented/reviewed; no provider request was made")
        spec = importlib.util.spec_from_file_location("overnight_synthesis_" + suffix, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.main(argv[1:], base=sys.modules[__name__])
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    phases = parser.add_subparsers(dest="phase", required=True)
    preparing = phases.add_parser("prepare", help="offline public request, historical gate and Docker probes")
    preparing.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    preparing.add_argument("--output", type=Path, required=True)
    preparing.add_argument("--source-root", type=Path, required=True)
    preparing.add_argument("--image", required=True)
    preparing.add_argument("--docker", default="/usr/local/bin/docker")
    phases.add_parser("synthesize", help="root only; API phase requires independent review")
    phases.add_parser("evaluate", help="requires frozen single response; unavailable before preparation review")
    args = parser.parse_args(argv)
    if args.phase == "prepare":
        data = prepare(args.repo, args.output, args.source_root, args.image, args.docker)
        print(json.dumps({"status": data["status"], "request_sha256": data["request_sha256"],
                          "historical_gate_passed": data["historical_gate_passed"], "isolation_passed": data["isolation_passed"]}))
    else:
        parser.error(f"{args.phase}: phase wiring is not released yet; no provider request was made")


if __name__ == "__main__":
    raise SystemExit(main())
