#!/usr/bin/env python3
"""Dispatch one Junction check at a time. Python 3.9+, macOS, stdlib only."""

import argparse
from datetime import datetime, timezone
import fcntl
import json
import math
import os
from pathlib import Path
import plistlib
import re
import subprocess
import tempfile
import time


def read_json(path):
    try:
        with path.open(encoding="utf-8") as stream:
            value = json.load(stream)
    except FileNotFoundError:
        return {}
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value


def write_json(path, value):
    """Replace in the same directory so readers never see partial JSON."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=".{}-".format(path.name), delete=False,
        ) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(str(temporary), str(path))
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def epoch(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("State timestamps must be numeric UTC epochs")
    if not math.isfinite(value) or value < 0:
        raise ValueError("Invalid state timestamp")
    return value


def utc(value):
    return datetime.fromtimestamp(epoch(value), timezone.utc).isoformat() if value else None


def queue(config, thread_id, message, runner):
    """Return a safe error summary; an error may still have enqueued work."""
    try:
        result = runner(
            [config["codex_path"], "queue", "--thread", thread_id,
             "--message", message, "--resume"],
            cwd=config["working_directory"], capture_output=True,
            text=True, timeout=45,
        )
    except subprocess.TimeoutExpired:
        return "Codex queue timed out; dispatch outcome is uncertain"
    except OSError:
        return "Codex queue could not run; dispatch outcome is uncertain"
    if result.returncode:
        return "Codex exited with status {}; dispatch outcome is uncertain".format(result.returncode)
    for line in (result.stdout + "\n" + result.stderr).lower().splitlines():
        if "resum" in line and re.search(r"fail|error|unable|cannot|can't|could not|couldn't|warning", line):
            return "Codex reported a resume failure; dispatch outcome is uncertain"
    return None


def remove_timer(config, config_path, scheduler, runner, now):
    """Disable and unlink before bootout, which can terminate this process."""
    config["enabled"] = False
    write_json(config_path, config)
    timer = Path(config["launch_agent_path"])
    if timer.exists():
        with timer.open("rb") as stream:
            if plistlib.load(stream).get("Label") != config["launch_agent_label"]:
                raise ValueError("Configured LaunchAgent label does not match its plist")
        timer.unlink()
    elif scheduler.get("timer_status") == "removed":
        return None
    scheduler.update(timer_status="unloading", timer_removal_attempted_at=now)
    state_path = config_path.parent / "scheduler.json"
    write_json(state_path, scheduler)
    try:
        result = runner(
            ["launchctl", "bootout", "gui/{}/{}".format(os.getuid(), config["launch_agent_label"])],
            cwd=config["working_directory"], capture_output=True, text=True, timeout=45,
        )
        error = None if result.returncode == 0 else "LaunchAgent unload returned status {}".format(result.returncode)
    except (OSError, subprocess.TimeoutExpired):
        error = "LaunchAgent unload could not be confirmed"
    scheduler.update(timer_status="uncertain" if error else "removed", last_timer_error=error)
    write_json(state_path, scheduler)
    return error


def tick(config, config_path, scheduler, run, runner, now):
    queued = epoch(scheduler.get("last_queued_at", 0))
    finished = epoch(run.get("last_finished_at", 0))
    interval = config["interval_seconds"]
    state_path = config_path.parent / "scheduler.json"
    if queued > finished:
        if now - queued >= interval and scheduler.get("stalled_alert_for") != queued:
            # Reserve before sending, including when delivery cannot be confirmed.
            scheduler.update(stalled_alert_for=queued, last_alert_at=now, alert_status="dispatching")
            write_json(state_path, scheduler)
            error = queue(
                config, config["parent_thread_id"],
                "[Junction Watch health alert] The check queued at {} has no completion "
                "acknowledgement after at least {} seconds. Further checks are blocked "
                "until the watcher writes last_finished_at in run.json. Inspect the "
                "watcher and scheduler state; source coverage may have a gap.".format(utc(queued), interval),
                runner,
            )
            scheduler.update(alert_status="uncertain" if error else "sent", last_alert_error=error)
            write_json(state_path, scheduler)
            return int(bool(error)), {"state": "pending", "health_alert": scheduler["alert_status"]}
        return 0, {"state": "pending"}
    if queued and now - queued < interval:
        return 0, {"state": "waiting"}
    # A crash, timeout, or CLI warning must not permit a duplicate queue.
    scheduler.update(last_queued_at=now, queue_status="dispatching", last_queue_error=None,
                     stalled_alert_for=None, alert_status=None, last_alert_error=None)
    write_json(state_path, scheduler)
    error = queue(
        config, config["thread_id"],
        "Read {} and perform exactly one Junction Watch check. Record numeric UTC epoch "
        "last_started_at and last_finished_at, status, and per-source results in {}. "
        "Atomically replace run.json after this attempt, including partial or blocked "
        "attempts, to acknowledge completion. The scheduler queued this check at {}. "
        "Do not edit scheduler.json or config.json.".format(
            config["instructions_path"], config_path.parent / "run.json", now
        ),
        runner,
    )
    scheduler.update(queue_status="uncertain" if error else "queued", last_queue_error=error)
    if not error:
        scheduler["last_successful_queue_at"] = now
    write_json(state_path, scheduler)
    return int(bool(error)), {"state": scheduler["queue_status"], "error": error}


def execute(config_path, command, runner, now):
    config = read_json(config_path)
    deadline = datetime.fromisoformat(config["ends_at"])
    if deadline.utcoffset() is None:
        raise ValueError("ends_at must include a timezone offset")
    expired = now >= deadline.timestamp()
    if command == "stop" or (expired and command != "status"):
        try:
            scheduler = read_json(config_path.parent / "scheduler.json")
        except ValueError:
            # Broken bookkeeping must not prevent the user from stopping checks.
            scheduler = {}
        error = remove_timer(config, config_path, scheduler, runner, now)
        return int(bool(error) or command == "resume"), {
            "state": "stopped" if command == "stop" else "expired", "error": error,
        }
    if command != "pause" and (
        not isinstance(config["enabled"], bool) or epoch(config["interval_seconds"]) <= 0
    ):
        raise ValueError("enabled must be boolean and interval_seconds must be positive")
    if command in ("pause", "resume"):
        config["enabled"] = command == "resume"
        write_json(config_path, config)
        return 0, {"state": "enabled" if config["enabled"] else "paused"}
    if command == "tick" and not config["enabled"]:
        return 0, {"state": "paused"}
    scheduler = read_json(config_path.parent / "scheduler.json")
    run = read_json(config_path.parent / "run.json")
    if command == "status":
        queued = epoch(scheduler.get("last_queued_at", 0))
        finished = epoch(run.get("last_finished_at", 0))
        return 0, {
            "enabled": config["enabled"], "expired": expired,
            "ends_at": config["ends_at"], "interval_seconds": config["interval_seconds"],
            "pending": queued > finished, "last_queued_at": utc(queued),
            "last_finished_at": utc(finished), "queue_status": scheduler.get("queue_status", "idle"),
            "queue_error": scheduler.get("last_queue_error"),
            "health_alert_status": scheduler.get("alert_status"),
            "health_alert_error": scheduler.get("last_alert_error"),
            "timer_status": scheduler.get("timer_status"),
            "timer_error": scheduler.get("last_timer_error"),
        }
    return tick(config, config_path, scheduler, run, runner, now)


def main(argv=None, *, runner=subprocess.run, now=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("command", choices=("tick", "status", "pause", "resume", "stop"))
    args = parser.parse_args(argv)
    args.config = Path(os.path.abspath(args.config.expanduser()))
    try:
        with (args.config.parent / "watch.lock").open("a") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            code, result = execute(args.config, args.command, runner, time.time() if now is None else now)
    except (OSError, ValueError, KeyError, TypeError, plistlib.InvalidFileException) as error:
        code, result = 1, {"state": "error", "error": "Cannot read or update watcher configuration/state ({})".format(type(error).__name__)}
    print(json.dumps(result, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
