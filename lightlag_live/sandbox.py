#!/usr/bin/env python3
"""Run a model-written autopilot through a campaign without trusting it.

    python3 -m lightlag_live.sandbox <policy.py> <new-out-dir> [--missions ...] [--noise-level 2]
    python3 -m lightlag_live.sandbox --reference <new-out-dir>      # the frozen KF + MPC, in-process

`policy.py` must define `play(tools)` for one mission; it is called once per mission. The
code never runs on this machine directly: it runs in a throwaway Docker container with no
network, a read-only filesystem, no capabilities, a non-root user and tight memory, CPU and
process limits. The campaign itself (seeds, hidden slip, truth) stays in this process; the
container sees only the five public calls.

The clock is simulated: the campaign's wall clock advances only while `advance` waits, so
the program's own thinking costs no ticks. That is the best case for the program, and for a
controller that answers within a tick it is identical to the real clock.

Writes the same artifacts as a Harbor run: `<out>/artifacts/evaluator/result.json` and one
replay and transcript per mission under `missions/NN/`, plus `<out>/sandbox.json`.
Standard library only; needs Docker for model-written code.
"""

from __future__ import annotations

import argparse
import json
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from .campaign import CampaignService, ToolError
from .make_task import MISSIONS, SETTINGS
from .reference import play_campaign

IMAGE = "python:3.12-slim"
CALL_TIMEOUT = 20.0       # seconds the program may think between two calls
RUN_TIMEOUT = 600.0       # seconds of real time for the whole campaign
CALL_CAP = 20000


class SimulatedClock:
    """Wall time that moves only when the service waits."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def parse_missions(text: str) -> List[Dict[str, Any]]:
    return [{"seed": int(part.split(":")[0]), "profile": part.split(":")[1]} for part in text.split(",")]


def new_campaign(out: Path, missions: str, noise_level: float) -> CampaignService:
    clock = SimulatedClock()
    return CampaignService(parse_missions(missions), delay=SETTINGS["delay"], ticks=SETTINGS["ticks"],
                           seconds_per_tick=SETTINGS["seconds_per_tick"], noise_level=noise_level,
                           artifact_dir=str(out / "artifacts" / "evaluator"), clock=clock, sleep=clock.sleep)


def run_reference(out: Path, missions: str, noise_level: float) -> Dict[str, Any]:
    from lightlag_dynamic.controllers import POLICIES
    campaign = new_campaign(out, missions, noise_level)
    play_campaign(campaign, POLICIES["kf_mpc"])
    return {"kind": "reference", "controller": "lightlag_dynamic kf_mpc", "status": "returned", "errors": [],
            "result": campaign.finish()}


def run_policy(policy: Path, out: Path, missions: str, noise_level: float) -> Dict[str, Any]:
    campaign = new_campaign(out, missions, noise_level)
    name = "lightlag-sandbox-" + uuid.uuid4().hex[:12]
    with tempfile.TemporaryDirectory() as folder:
        shutil.copyfile(policy, Path(folder) / "policy.py")
        shutil.copyfile(Path(__file__).with_name("sandbox_worker.py"), Path(folder) / "worker.py")
        command = ["docker", "run", "--rm", "-i", "--name", name, "--network", "none", "--cap-drop", "ALL",
                   "--security-opt", "no-new-privileges", "--user", "65534:65534", "--memory", "512m",
                   "--cpus", "1", "--pids-limit", "64", "--read-only", "--tmpfs", "/tmp:rw,size=16m",
                   "-v", "{}:/w:ro".format(folder), IMAGE, "python", "-I", "/w/worker.py"]
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
                budget = min(CALL_TIMEOUT if last else 60.0, RUN_TIMEOUT - (time.time() - started))
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
                    reply = {"ok": True, "result": campaign.call(request.get("method"), request.get("params"))}
                except ToolError as failure:
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
    return {"kind": "sandboxed-policy", "status": status, "errors": errors, "calls": calls,
            "think_max_seconds": round(think_max, 3), "seconds": round(time.time() - started, 1),
            "stderr_tail": (stderr[0] if stderr else "")[-1500:] if (errors or status != "returned") else "",
            "result": campaign.finish()}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("policy", nargs="?", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--reference", action="store_true", help="play the frozen KF + MPC instead of a policy file")
    parser.add_argument("--missions", default=MISSIONS)
    parser.add_argument("--noise-level", type=float, default=SETTINGS["noise_level"])
    args = parser.parse_args(argv)
    if args.out.exists():
        parser.error("the output directory already exists; results are never overwritten")
    if not args.reference and args.policy is None:
        parser.error("give a policy file or --reference")
    args.out.mkdir(parents=True)
    if args.reference:
        summary = run_reference(args.out, args.missions, args.noise_level)
    else:
        summary = run_policy(args.policy, args.out, args.missions, args.noise_level)
    result = summary.pop("result")
    summary.update(reward=result["reward"], missions=[round(m["reward"], 6) for m in result["missions"]],
                   rovers_lost=sum(not m["alive"] for m in result["missions"]),
                   settings={"missions": args.missions, "noise_level": args.noise_level, "clock": "simulated"})
    (args.out / "sandbox.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("{}: reward {:.3f} missions {} lost {} status {}{}".format(
        args.out.name, summary["reward"], " ".join("{:.2f}".format(m) for m in summary["missions"]),
        summary["rovers_lost"], summary["status"], " errors {}".format(len(summary["errors"])) if summary["errors"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
