#!/usr/bin/env python3
"""Run a model-written traverse controller through one mission without trusting it.

    python3 -m lightlag_traverse.sandbox <policy.py> <new-out-dir> [--seed 2026]
    python3 -m lightlag_traverse.sandbox --program <folder> --entry rover.py <new-out-dir>

`policy.py` must define `play(tools)`. With `--program`, the folder holds an agent's own
program as it ran in the task; it is started as a script with a stand-in `lightlag_client`
beside it. Either way the code never runs on this machine directly: it runs in a throwaway
Docker container with no network, a read-only filesystem, no capabilities, a non-root user
and memory, CPU and process limits. The mission itself (seed, hidden values, truth) stays in
this process; the container sees only the five public calls.

Writes what a Harbor run writes: `<out>/artifacts/evaluator/{result,replay}.json` and
`transcript.jsonl`, plus `<out>/sandbox.json`. Standard library only; needs Docker.
"""

from __future__ import annotations

import argparse
import json
import queue
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from lightlag_live.sandbox import PROGRAM_MAIN, PROGRAM_SHIM

from .make_task import SEED
from .server import TraverseEpisodeService

IMAGE = "python:3.12-slim"
FIRST_CALL_TIMEOUT = 180.0   # seconds to load and make the first call
CALL_TIMEOUT = 180.0         # seconds the program may think between two calls
RUN_TIMEOUT = 1500.0         # seconds of real time for the whole mission
CALL_CAP = 30000


def run(policy: Path, out: Path, seed: int, program: bool = False, entry: str = "autopilot.py",
        image: str = IMAGE) -> Dict[str, Any]:
    service = TraverseEpisodeService(seed, artifact_dir=str(out / "artifacts" / "evaluator"))
    surface = Path(__file__).with_name("surface.py")
    name = "lightlag-sandbox-" + uuid.uuid4().hex[:12]
    with tempfile.TemporaryDirectory() as folder:
        work = Path(folder)
        # mkdtemp makes the folder 0700; on Linux the container's user 65534 could not read it
        # (Docker Desktop on macOS ignores this). Read-only for others, as the :ro mount is.
        os.chmod(folder, 0o755)
        shutil.copyfile(surface, work / "lightlag_surface.py")
        if program:
            for path in Path(policy).glob("*.py"):
                if path.name not in ("lightlag_client.py", "lightlag_surface.py", "detach.py"):
                    shutil.copyfile(path, work / path.name)
            (work / "lightlag_client.py").write_text(PROGRAM_SHIM, encoding="utf-8")
            (work / "sandbox_main.py").write_text(PROGRAM_MAIN.format(entry=entry), encoding="utf-8")
            command_in = ["sh", "-c", "cp /w/*.py /app/ && cd /app && exec python sandbox_main.py"]
            extra = ["--tmpfs", "/app:rw,size=64m,mode=1777", "-e", "HOME=/app"]
        else:
            shutil.copyfile(policy, work / "policy.py")
            shutil.copyfile(Path(__file__).with_name("sandbox_worker.py"), work / "worker.py")
            command_in = ["python", "-I", "/w/worker.py"]
            extra = []
        command = ["docker", "run", "--rm", "-i", "--name", name, "--network", "none", "--cap-drop", "ALL",
                   "--security-opt", "no-new-privileges", "--user", "65534:65534", "--memory", "1g",
                   "--cpus", "1", "--pids-limit", "64", "--read-only", "--tmpfs", "/tmp:rw,size=32m",
                   *extra, "-v", "{}:/w:ro".format(folder), image, *command_in]
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, bufsize=1)
        lines: "queue.Queue[Optional[str]]" = queue.Queue()

        def reader() -> None:
            assert process.stdout is not None
            for line in process.stdout:
                lines.put(line)
            lines.put(None)

        stderr: List[str] = []
        threading.Thread(target=reader, daemon=True).start()
        threading.Thread(target=lambda: stderr.append(process.stderr.read()), daemon=True).start()
        started = time.time()
        status, errors, calls, think_max, last = "timeout", [], 0, 0.0, None
        try:
            while True:
                budget = min(CALL_TIMEOUT if last else FIRST_CALL_TIMEOUT, RUN_TIMEOUT - (time.time() - started))
                try:
                    line = lines.get(timeout=max(0.01, budget))
                except queue.Empty:
                    status = "timeout"
                    break
                if line is None:
                    status = "died"
                    break
                if last is not None:
                    think_max = max(think_max, time.time() - last)
                try:
                    request = json.loads(line)
                except ValueError:
                    status = "protocol"
                    break
                if request.get("method") == "done":
                    status, errors = "returned", request.get("errors") or []
                    break
                calls += 1
                if calls > CALL_CAP:
                    status = "call_cap"
                    break
                try:
                    reply = {"ok": True, "result": service.call(request.get("method"), request.get("params"))}
                except ValueError as failure:
                    reply = {"ok": False, "error": str(failure)}
                try:
                    assert process.stdin is not None
                    process.stdin.write(json.dumps(reply) + "\n")
                    process.stdin.flush()
                except (BrokenPipeError, OSError):
                    status = "died"
                    break
                last = time.time()
        finally:
            subprocess.run(["docker", "kill", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                process.kill()
            except OSError:
                pass
    result = service.finish()
    return {"kind": "sandboxed-program" if program else "sandboxed-policy", "status": status, "errors": errors,
            "calls": calls, "think_max_seconds": round(think_max, 3), "seconds": round(time.time() - started, 1),
            "stderr_tail": (stderr[0] if stderr else "")[-1500:] if (errors or status != "returned") else "",
            "seed": seed, "reward": result["raw_score"] / result["max_available_value"],
            "samples": len(result["sampled_targets"]), "alive": result["alive"], "at_base": result["at_base"]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("policy", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--program", action="store_true",
                        help="`policy` is a folder holding an agent's own program, run as it ran in the task")
    parser.add_argument("--entry", default="autopilot.py", help="with --program: the script to start")
    parser.add_argument("--image", default=IMAGE,
                        help="container image; an agent that installed a package needs an image that has it")
    args = parser.parse_args(argv)
    if args.out.exists():
        parser.error("the output directory already exists; results are never overwritten")
    args.out.mkdir(parents=True)
    summary = run(args.policy, args.out, args.seed, args.program, args.entry, args.image)
    (args.out / "sandbox.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("{}: seed {} reward {:.3f}, {} samples, alive {}, at base {}, status {}{}".format(
        args.out.name, args.seed, summary["reward"], summary["samples"], summary["alive"], summary["at_base"],
        summary["status"], ", errors {}".format(summary["errors"]) if summary["errors"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
