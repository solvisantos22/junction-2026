#!/usr/bin/env python3
"""Run a model-written traverse program through one mission, on the MAX map or the normal one, without trusting it.

    python3 -m lightlag_traverse_max.sandbox <policy.py> <new-out-dir> --seed 515            # the MAX map
    python3 -m lightlag_traverse_max.sandbox <policy.py> <new-out-dir> --seed 2026 --map normal

Kristján's sandbox (lightlag_traverse/sandbox.py) runs the program in Docker. This machine has no
Docker, so this one runs his worker (lightlag_traverse/sandbox_worker.py, unchanged) under
bubblewrap instead: no network, the system's files read-only, the program's folder read-only, a
private /tmp, its own process tree and session, no environment but PATH and HOME, at most 2 GB of
address space, and Python 3.12, the version in his container. The timeouts and the call cap are
his, imported from his module. The mission (seed, hidden values, truth) stays in this process
behind the team's episode service; the program sees only the five public calls.

Writes what Kristján's sandbox writes: `<out>/artifacts/evaluator/{result,replay}.json` and
`transcript.jsonl`, and `<out>/sandbox.json`. Standard library only; needs `bwrap` and `prlimit`.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from lightlag_traverse import sandbox as kristjans
from lightlag_traverse.server import TraverseEpisodeService

from .environment import OPTIONS, make_env

PYTHON = "/usr/bin/python3.12"
ADDRESS_SPACE = 2 * 1024 ** 3
WORKER = Path(kristjans.__file__).with_name("sandbox_worker.py")
SURFACE = Path(kristjans.__file__).with_name("surface.py")


class MaxEpisodeService(TraverseEpisodeService):
    """The team's episode service (lock, transcript, grading), with a mission of either map behind it."""

    def __init__(self, seed: int, artifact_dir: Optional[str] = None, option: str = "max") -> None:
        super().__init__(seed, artifact_dir=artifact_dir)
        # Swap the episode before any tool call, as TraverseEpisodeService does.
        self._env = make_env(seed, option)
        rules = self._env.rules()
        self._max_ticks = rules["max_ticks"]
        self._max_advance = rules["max_advance_ticks"]


def available(python: str = PYTHON) -> bool:
    """Whether this machine can run the sandbox."""
    return bool(shutil.which("bwrap") and shutil.which("prlimit") and Path(python).exists())


def isolated(folder: Path, python: str = PYTHON) -> List[str]:
    """The command that runs the worker in `folder` under bubblewrap."""
    return ["prlimit", "--as={}".format(ADDRESS_SPACE), "--",
            "bwrap", "--ro-bind", "/usr", "/usr", "--symlink", "usr/lib", "/lib", "--symlink", "usr/lib64", "/lib64",
            "--symlink", "usr/bin", "/bin", "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
            "--ro-bind", str(folder), "/w", "--chdir", "/w", "--unshare-all", "--die-with-parent", "--new-session",
            "--uid", "65534", "--gid", "65534", "--clearenv", "--setenv", "PATH", "/usr/bin", "--setenv", "HOME", "/tmp",
            python, "-I", "/w/worker.py"]


def run(policy: Path, out: Path, seed: int, option: str = "max", python: str = PYTHON) -> Dict[str, Any]:
    """One whole mission played by the module at `policy`; returns the summary Kristján's sandbox returns."""
    service = MaxEpisodeService(seed, artifact_dir=str(Path(out) / "artifacts" / "evaluator"), option=option)
    with tempfile.TemporaryDirectory(prefix="lightlag-max-sandbox-") as folder:
        work = Path(folder)
        shutil.copyfile(policy, work / "policy.py")
        shutil.copyfile(WORKER, work / "worker.py")
        shutil.copyfile(SURFACE, work / "lightlag_surface.py")
        process = subprocess.Popen(isolated(work, python), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, bufsize=1, start_new_session=True)
        lines: "queue.Queue[Optional[str]]" = queue.Queue()

        def reader() -> None:
            assert process.stdout is not None
            for line in process.stdout:
                lines.put(line)
            lines.put(None)

        stderr: List[str] = []
        readers = [threading.Thread(target=reader, daemon=True),
                   threading.Thread(target=lambda: stderr.append(process.stderr.read()), daemon=True)]
        for thread in readers:
            thread.start()
        started = time.time()
        status, errors, calls, think_max, last = "timeout", [], 0, 0.0, None
        try:
            while True:
                budget = min(kristjans.CALL_TIMEOUT if last else kristjans.FIRST_CALL_TIMEOUT,
                             kristjans.RUN_TIMEOUT - (time.time() - started))
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
                if calls > kristjans.CALL_CAP:
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
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except OSError:
                pass
            process.wait()
            for thread in readers:
                thread.join(timeout=5)
            for stream in (process.stdin, process.stdout, process.stderr):
                try:
                    stream.close()
                except OSError:
                    pass
    result = service.finish()
    return {"kind": "sandboxed-policy", "status": status, "errors": errors, "calls": calls,
            "think_max_seconds": round(think_max, 3), "seconds": round(time.time() - started, 1),
            "stderr_tail": (stderr[0] if stderr else "")[-1500:] if (errors or status != "returned") else "",
            "seed": seed, "map": option, "isolation": "bubblewrap",
            "reward": result["raw_score"] / result["max_available_value"],
            "samples": len(result["sampled_targets"]), "alive": result["alive"], "at_base": result["at_base"]}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("policy", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--map", default="max", choices=OPTIONS)
    args = parser.parse_args(argv)
    if not available():
        parser.error("needs bwrap, prlimit and {}".format(PYTHON))
    if args.out.exists():
        parser.error("the output directory already exists; results are never overwritten")
    args.out.mkdir(parents=True)
    summary = run(args.policy, args.out, args.seed, args.map)
    (args.out / "sandbox.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("{}: seed {} {} map, reward {:.3f}, {} samples, alive {}, at base {}, status {}{}".format(
        args.out.name, args.seed, args.map, summary["reward"], summary["samples"], summary["alive"],
        summary["at_base"], summary["status"], ", errors {}".format(summary["errors"]) if summary["errors"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
