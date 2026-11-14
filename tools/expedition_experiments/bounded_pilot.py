"""Launch one frozen assignment with reported-usage guards; never retry a run.

Private runtime: assignments.private.json, tasks/<id>, opencode-config.json.
Only step-finish cost fields are inspected. Provider text stays private. Guards
are not provider caps: a response already in flight can exceed them.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import time

from tools.lightlag_experiments.overnight_runs import read_key

LAUNCH_GUARD = 1.50
INFLIGHT_GUARD = 2.25


def valid_cost(value):
    return type(value) in (float, int) and math.isfinite(value) and value >= 0


def reported_usage(path, final=False):
    """Read complete JSONL events; reject unknown cost, ignore an unfinished line."""
    if not path.exists():
        return {"cost_usd": 0.0, "finished_steps": 0, "unknown": False}
    seen, cost, unknown = set(), 0.0, False
    try:
        data = path.read_bytes()
    except OSError:
        return {"cost_usd": 0.0, "finished_steps": 0, "unknown": True}
    lines = data.splitlines(keepends=True)
    for line in lines:
        try:
            event = json.loads(line)
        except (ValueError, UnicodeDecodeError):
            # A live writer can stop in the middle of UTF-8 or a JSON object.
            if final or line.endswith(b"\n"):
                unknown = True
            continue
        if not isinstance(event, dict):
            unknown = True
            continue
        if event.get("type") != "step_finish":
            continue
        part = event.get("part")
        if not isinstance(part, dict):
            unknown = True
            continue
        identity = (event.get("sessionID"), part.get("id"))
        if not all(isinstance(value, str) for value in identity):
            unknown = True
            continue
        if identity in seen:
            continue
        seen.add(identity)
        if valid_cost(part.get("cost")):
            cost += part["cost"]
        else:
            unknown = True
    return {"cost_usd": cost, "finished_steps": len(seen), "unknown": unknown}


def previous_usage(runtime, assignment_id):
    assignments = json.loads((runtime / "assignments.private.json").read_text())
    order = [row["assignment_id"] for row in assignments]
    started = {p.stem.removeprefix("started-") for p in runtime.glob("started-*.json")}
    if assignment_id != next((aid for aid in order if aid not in started), None):
        raise ValueError("unexpected launch order or assignment already started")
    total = 0.0
    for aid in started:
        results = list((runtime / "jobs" / ("model-" + aid)).glob("*/result.json"))
        if len(results) != 1:
            raise ValueError("previous assignment unfinished or ambiguous; stop launches")
        result = json.loads(results[0].read_text())
        value = (result.get("agent_result") or {}).get("cost_usd")
        if not result.get("finished_at") or not valid_cost(value):
            raise ValueError("previous assignment unfinished or usage unknown; stop launches")
        monitor = runtime / ("monitor-" + aid + ".json")
        if not monitor.exists() or json.loads(monitor.read_text()).get("censored_reason"):
            raise ValueError("previous assignment monitoring incomplete or censored; stop launches")
        if result.get("exception_info"):
            raise ValueError("previous assignment failed; preserve it and stop launches")
        total += value
    if total >= LAUNCH_GUARD:
        raise ValueError("reported pilot launch guard reached")
    return total


def write_new(path, data):
    with path.open("x") as stream:
        json.dump(data, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def run(runtime, assignment_id, env_file, harbor):
    runtime = Path(runtime).resolve()
    prior = previous_usage(runtime, assignment_id)
    task = runtime / "tasks" / assignment_id
    manifest = json.loads((task / "experiment.json").read_text())
    for name, digest in manifest["task_sha256"].items():
        if hashlib.sha256((task / name).read_bytes()).hexdigest() != digest:
            raise ValueError("frozen task bytes changed: " + name)
    config = json.loads((runtime / "opencode-config.json").read_text())
    env = dict(os.environ)
    env["ANTHROPIC_API_KEY"] = read_key(Path(env_file))
    if "ANTHROPIC_CUSTOM_HEADERS" in env:
        raise ValueError("unexpected provider headers")
    write_new(runtime / ("started-" + assignment_id + ".json"), {
        "assignment_id": assignment_id, "at": datetime.now(timezone.utc).isoformat(),
        "prior_model_reported_cost": prior, "launch_guard_usd": LAUNCH_GUARD,
        "inflight_guard_usd": INFLIGHT_GUARD})
    command = [str(harbor), "run", "-p", str(task), "-a", "opencode", "-m",
               "anthropic/claude-opus-5-5", "--ak", "version=1.19.5", "--ak",
               "opencode_config=" + json.dumps(config, separators=(",", ":")),
               "-n", "1", "-k", "1", "--max-retries", "0", "--jobs-dir",
               str(runtime / "jobs"), "--job-name", "model-" + assignment_id]
    usage, reason, interrupted_at = {}, None, None
    with (runtime / ("model-" + assignment_id + ".launcher.log")).open("x") as log:
        process = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT)
        while process.poll() is None:
            paths = list((runtime / "jobs" / ("model-" + assignment_id)).glob("*/agent/opencode.txt"))
            if len(paths) == 1:
                try:
                    usage = reported_usage(paths[0])
                except Exception:
                    usage = {"cost_usd": 0.0, "finished_steps": 0, "unknown": True}
                if usage["unknown"]:
                    reason = reason or "unknown_inflight_usage"
                elif prior + usage["cost_usd"] >= INFLIGHT_GUARD:
                    reason = reason or "reported_usage_guard"
            elif len(paths) > 1:
                reason = reason or "unexpected_multiple_trials"
            if reason and interrupted_at is None:
                process.send_signal(signal.SIGINT)
                interrupted_at = time.monotonic()
            elif interrupted_at and time.monotonic() - interrupted_at > 60:
                process.terminate()
            time.sleep(2)
        code = process.wait()
    paths = list((runtime / "jobs" / ("model-" + assignment_id)).glob("*/agent/opencode.txt"))
    usage = {"cost_usd": 0.0, "finished_steps": 0, "unknown": True}
    if len(paths) == 1:
        try:
            usage = reported_usage(paths[0], final=True)
        except Exception:
            pass
    if not usage or usage.get("unknown") or not usage.get("finished_steps"):
        reason = reason or "unknown_final_usage"
    report = {"assignment_id": assignment_id, "harbor_returncode": code,
              "censored_reason": reason, "final_stream_usage": usage,
              "prior_reported_cost_usd": prior,
              "guard_crossed_at_completion": prior + usage.get("cost_usd", 0) >= INFLIGHT_GUARD,
              "note": "Reported completed-response usage; not a provider cap or live account balance."}
    write_new(runtime / ("monitor-" + assignment_id + ".json"), report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runtime", type=Path)
    parser.add_argument("assignment_id")
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--harbor", type=Path, required=True)
    report = run(**vars(parser.parse_args()))
    print(json.dumps(report, sort_keys=True))
    return report["harbor_returncode"] or int(bool(report["censored_reason"]))


if __name__ == "__main__":
    raise SystemExit(main())
