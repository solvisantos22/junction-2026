"""Resume the existing Codex chat once final training settles; never launch training."""
import argparse
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import time

STALE_SECONDS = 900
FINISHED = {"queued", "uncertain", "reserved", "disabled"}


def read(path):
    value = json.loads(Path(path).read_text())
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return value


def save(path, value):
    temporary = Path(str(path) + ".tmp")
    with temporary.open("w") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def identity(config):
    required = {"monitor_directory", "thread_id", "codex_path", "working_directory", "deadline_unix"}
    if set(config) != required or any(not isinstance(config[k], str) or not config[k]
                                    for k in required - {"deadline_unix"}):
        raise ValueError("invalid wake configuration")
    if (type(config["deadline_unix"]) not in (int, float)
            or not math.isfinite(config["deadline_unix"]) or config["deadline_unix"] <= 0):
        raise ValueError("invalid wake deadline")
    return {"config": config, "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


def pause_reason(directory, monitor):
    if (directory / "wake-stop").exists():
        return "wake_stop_file"
    if (directory / "pause.json").exists() or monitor.get("status") in ("user_paused", "stopped_marker"):
        return "training_paused_or_stopped"
    return None


def message(config, reason):
    return ("Automatic final-training wake-up requested by Sölvi; reason: " + reason + ". "
            "Continue this task. Read AGENTS.md, junction-team-workflow, TEAM_STATUS.md, "
            "docs/learning-final-results/README.md and " + config["monitor_directory"] + "/state.json. "
            "Reconcile all six runs and failures. Preserve the frozen training source. "
            "Publish the all-seed initial/matched2048/latest policy freeze before opening final worlds "
            "82000–82039; run and audit the matched greedy/beam evaluation, then publish findings, "
            "prize evidence and handoff to main. Keep the current reference. Diagnose errors before "
            "new spend; never resume the old campaign or repeat completed training. No Superpowers. "
            "This is a one-time wake-up, not permission to bypass a user pause or stop.")


def tick(config, state_path, runner=subprocess.run, now=None):
    """Poll local state and at most once queue a resume; ambiguous dispatch is final."""
    now = time.time() if now is None else now
    state_path = Path(state_path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with Path(str(state_path) + ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        expected = identity(config)
        state = read(state_path) if state_path.exists() else {
            "schema": "learning-final-wake-v1", "identity": expected,
            "status": "waiting", "started_unix": now,
        }
        if state.get("schema") != "learning-final-wake-v1" or state.get("identity") != expected:
            raise ValueError("wake code/config identity changed")
        if state["status"] in FINISHED:
            return state
        if state["status"] != "waiting":
            raise ValueError("unknown wake status")
        directory = Path(config["monitor_directory"])
        reason, monitor = None, {}
        try:
            monitor = read(directory / "state.json")
        except FileNotFoundError:
            if now - state["started_unix"] > STALE_SECONDS:
                reason = "missing_monitor_state"
        except (ValueError, OSError):
            reason = "unreadable_monitor_state"
        paused = pause_reason(directory, monitor)
        if paused:
            state.update(status="disabled", reason=paused, updated_unix=now)
            save(state_path, state)
            return state
        status = monitor.get("status")
        if status in ("ready_for_final_evaluation", "error", "campaign_deadline"):
            reason = status
        elif now >= config["deadline_unix"]:
            reason = "wake_deadline"
        elif monitor:
            updated = monitor.get("updated_unix")
            if type(updated) not in (int, float) or not math.isfinite(updated):
                reason = "invalid_monitor_heartbeat"
            elif now - updated > STALE_SECONDS:
                reason = "stale_monitor"
        state.update(updated_unix=now, monitor_status=status)
        if reason is None:
            save(state_path, state)
            return state
        # Reserve before any external dispatch. A crash/timeout may have queued work.
        state.update(status="reserved", reason=reason, reserved_unix=now)
        save(state_path, state)
        try:
            latest = read(directory / "state.json")
        except (ValueError, OSError):
            latest = monitor
        paused = pause_reason(directory, latest)
        if paused:
            state.update(status="disabled", reason=paused)
            save(state_path, state)
            return state
        command = [config["codex_path"], "queue", "--thread", config["thread_id"],
                   "--message", message(config, reason), "--resume"]
        try:
            result = runner(command, cwd=config["working_directory"], capture_output=True,
                            text=True, timeout=45)
            output = (result.stdout + "\n" + result.stderr).lower()
            warning = any("resum" in line and re.search(r"fail|error|unable|cannot|can't|could not|warning", line)
                          for line in output.splitlines())
            if result.returncode or warning:
                state.update(status="uncertain", error="queue_failed_or_resume_unconfirmed",
                             returncode=result.returncode)
            else:
                state.update(status="queued", returncode=0)
        except (subprocess.TimeoutExpired, OSError) as error:
            state.update(status="uncertain", error=type(error).__name__)
        save(state_path, state)
        return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--follow", action="store_true")
    args = parser.parse_args()
    config = read(args.config)
    while True:
        state = tick(config, args.state)
        if not args.follow or state["status"] in FINISHED:
            print(json.dumps({"status": state["status"], "reason": state.get("reason")}))
            return
        time.sleep(30)


if __name__ == "__main__":
    main()
