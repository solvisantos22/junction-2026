"""Publish bounded checkpoint updates from a dedicated, clean Git checkout.

No training, model API calls or final-map evaluation. --follow polls every five
minutes; publications happen every fifteen minutes or when checkpoints/status change.
A dirty tree, changed workflow, ambiguous commit or conflict stops this publisher.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import time

from . import decide, progress

POLL_SECONDS = 300
PUBLISH_SECONDS = 900
BASE = "docs/learning-final-results"
LATEST = BASE + "/progress.json"
WORKFLOW = ".agents/skills/junction-team-workflow/SKILL.md"
VOLUME = "junction-learning-final"
TERMINAL = {"ready_for_final_evaluation", "error", "campaign_deadline"}
FINISHED = {"complete", "disabled", "error", "deadline"}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(str(path) + ".tmp")
    with temporary.open("w") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git(root, *arguments, check=True, options=()):
    result = subprocess.run(["git", *options, *arguments], cwd=root, capture_output=True,
                            text=True, timeout=60)
    if check and result.returncode:
        # Do not retain raw Git output: it may contain credential-bearing URLs.
        raise RuntimeError("git operation failed: " + arguments[0])
    return result.stdout.strip() if check else result


def identity(config):
    required = {"freeze_path", "monitor_directory", "cache_directory", "publish_root", "state_path", "agents_sha256"}
    require(required <= set(config) <= required | {"git_options"}
            and all(isinstance(config[k], str) and config[k] for k in required),
            "invalid publisher configuration")
    options = config.get("git_options", [])
    require(isinstance(options, list) and len(options) % 2 == 0
            and all(options[i] == "-c" and isinstance(options[i + 1], str)
                    and options[i + 1].split("=", 1)[0] in ("http.curloptResolve", "http.version")
                    for i in range(0, len(options), 2)), "unsupported Git network options")
    root = Path(config["publish_root"]).resolve()
    require(Path(git(root, "rev-parse", "--show-toplevel")).resolve() == root, "publish_root must be the checkout root")
    require(not Path(__file__).resolve().is_relative_to(root), "run publisher code outside its integration checkout")
    for name in ("state_path", "cache_directory", "monitor_directory"):
        require(not Path(config[name]).resolve().is_relative_to(root), "private runtime data must remain outside Git checkout")
    branch = git(root, "branch", "--show-current")
    require(branch not in ("", "main", "master"), "a dedicated publisher branch is required")
    require(digest(root / "AGENTS.md") == config["agents_sha256"], "AGENTS.md changed; review workflow before proceeding")
    campaign = read(config["freeze_path"])["campaign"]
    require(type(campaign["deadline_unix"]) in (int, float) and math.isfinite(campaign["deadline_unix"]),
            "invalid frozen campaign deadline")
    return {"config": config, "branch": branch, "remote": git(root, "remote", "get-url", "origin"),
            "freeze_sha256": digest(config["freeze_path"]),
            "campaign_id": campaign["campaign_id"], "publisher_deadline_unix": campaign["deadline_unix"] + 600,
            "workflow_sha256": digest(root / WORKFLOW),
            "code_sha256": {"publisher": digest(__file__), "collector": digest(progress.__file__),
                            "decision": digest(decide.__file__)}}


def stopped(config):
    directory = Path(config["monitor_directory"])
    if any((directory / name).exists() for name in ("progress-stop", "pause.json")):
        return True
    path = directory / "state.json"
    return path.exists() and read(path).get("status") in ("user_paused", "stopped_marker")


def clean(root):
    require(not git(root, "status", "--porcelain", "--untracked-files=all"), "publisher checkout is dirty")
    for name in ("rebase-merge", "rebase-apply", "MERGE_HEAD"):
        path = Path(git(root, "rev-parse", "--git-path", name))
        require(not (path if path.is_absolute() else root / path).exists(), "unfinished Git operation requires review")


def check_workflow(root, state, revision=None):
    expected = {"AGENTS.md": state["identity"]["config"]["agents_sha256"],
                WORKFLOW: state["identity"]["workflow_sha256"]}
    for path, value in expected.items():
        if revision:
            result = subprocess.run(["git", "show", revision + ":" + path], cwd=root,
                                    capture_output=True, timeout=60)
            require(result.returncode == 0 and hashlib.sha256(result.stdout).hexdigest() == value,
                    "remote workflow changed; manual review required")
        else:
            require(digest(root / path) == value, "local workflow changed; manual review required")


def fetch(root, state):
    git(root, "fetch", "origin", options=state["identity"]["config"].get("git_options", []))
    check_workflow(root, state, "origin/main")


def marker(snapshot):
    return [snapshot.get("monitor_status"), snapshot.get("stage"),
            [[key, value.get("status")] for key, value in sorted(snapshot.get("runs", {}).items())],
            snapshot.get("errors", [])]


def published_metadata(snapshot, commit=None):
    return {"unix": snapshot["created_unix"], "checkpoint_key": progress.checkpoint_key(snapshot),
            "status_key": marker(snapshot), "commit": commit}


def verify_pending(root, pending):
    clean(root)
    head = git(root, "rev-parse", "HEAD")
    parent = git(root, "rev-list", "--parents", "-n", "1", "HEAD").split()
    require(len(parent) == 2 and parent[1] in pending["bases"], "unexpected unpublished commit ancestry")
    require(git(root, "log", "-1", "--format=%s") == pending["message"], "unexpected unpublished commit identity")
    changed = sorted(git(root, "diff", "--name-only", parent[1], head).splitlines())
    require(changed == pending["changed_paths"], "unpublished commit contains unexpected paths")
    require(all(digest(root / name) == sha for name, sha in pending["files"].items()),
            "unpublished progress content changed")
    return head, parent[1]


def finish_publication(state, state_path, commit):
    pending = state["pending"]
    state["last_published"] = {**pending["publication"], "commit": commit}
    state["pending"] = None
    state["status"] = pending["finish_status"]
    if state["status"] == "deadline":
        state["reason"] = "publisher_deadline"
    atomic_json(state_path, state)


def push_pending(config, state, state_path):
    """Only the one verified publisher commit may be rebased after a push race."""
    root = Path(config["publish_root"]).resolve()
    pending = state["pending"]
    for attempt in range(3):
        head, parent = verify_pending(root, pending)
        if stopped(config):
            state["status"] = "disabled"
            atomic_json(state_path, state)
            return
        check_workflow(root, state)
        fetch(root, state)
        if git(root, "merge-base", "--is-ancestor", head, "origin/main", check=False).returncode == 0:
            finish_publication(state, state_path, head)
            return
        remote = git(root, "rev-parse", "origin/main")
        if remote != parent:
            require(git(root, "merge-base", "--is-ancestor", parent, remote, check=False).returncode == 0,
                    "remote history diverged from the recorded base")
            pending["bases"] = list(dict.fromkeys([*pending["bases"], remote]))
            atomic_json(state_path, state)
            git(root, "rebase", "--onto", remote, parent)
            head, parent = verify_pending(root, pending)
        if stopped(config):
            state["status"] = "disabled"
            atomic_json(state_path, state)
            return
        if git(root, "push", "origin", "HEAD:main", check=False,
               options=config.get("git_options", [])).returncode == 0:
            finish_publication(state, state_path, head)
            return
    raise RuntimeError("three normal push attempts failed; retained commit needs review")


def synchronize(root, state):
    clean(root)
    check_workflow(root, state)
    fetch(root, state)
    require(git(root, "merge-base", "--is-ancestor", "HEAD", "origin/main", check=False).returncode == 0,
            "unrecorded local commits require review")
    git(root, "merge", "--ff-only", "origin/main")
    check_workflow(root, state)


def publish(config, state, state_path, snapshot):
    root = Path(config["publish_root"]).resolve()
    synchronize(root, state)
    if stopped(config):
        state["status"] = "disabled"
        atomic_json(state_path, state)
        return
    timestamp = datetime.fromtimestamp(snapshot["created_unix"], timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    archive = BASE + "/progress-snapshots/" + timestamp + ".json"
    require(not (root / archive).exists(), "progress snapshot filename already exists")
    serialized = json.dumps(snapshot, indent=2, sort_keys=True, allow_nan=False) + "\n"
    note = "\n\n" + snapshot["publisher_note"] if snapshot.get("publisher_note") else ""
    files = {BASE + "/progress.md": progress.render(snapshot).rstrip() + note + "\n", LATEST: serialized, archive: serialized}
    changed = sorted(name for name, content in files.items()
                     if not (root / name).exists() or (root / name).read_text() != content)
    pending = {"bases": [git(root, "rev-parse", "HEAD")],
               "message": "docs: publish final learning progress " + timestamp,
               "files": {name: hashlib.sha256(content.encode()).hexdigest() for name, content in files.items()},
               "changed_paths": changed, "publication": published_metadata(snapshot),
               "finish_status": ("deadline" if snapshot.get("publisher_note") else
                                 "complete" if snapshot.get("monitor_status") in TERMINAL else "monitoring")}
    state["pending"] = pending
    atomic_json(state_path, state)
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    git(root, "add", "--", *changed)
    require(sorted(git(root, "diff", "--cached", "--name-only").splitlines()) == changed,
            "staged paths changed outside publisher scope")
    git(root, "diff", "--cached", "--check")
    git(root, "commit", "-m", pending["message"])
    push_pending(config, state, state_path)


def default_volume():
    require(os.environ.get("MODAL_PROFILE") == "solvi-junction", "set MODAL_PROFILE=solvi-junction explicitly")
    import modal
    require(modal.__version__ == "1.6.4", "use pinned modal==1.6.4")
    return modal.Volume.from_name(VOLUME)


def tick(config, *, volume=None, collector=None, now=None):
    now = time.time() if now is None else now
    state_path = Path(config["state_path"])
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with Path(str(state_path) + ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state = read(state_path) if state_path.exists() else {}
        # A retained conflict can leave Git detached; do not touch it again.
        if state.get("status") in FINISHED:
            return state
        try:
            expected = identity(config)
            if not state:
                state.update(schema="learning-final-progress-publisher-v1", identity=expected, status="monitoring",
                             last_published=None, pending=None)
            require(state.get("schema") == "learning-final-progress-publisher-v1" and state["identity"] == expected,
                    "publisher code/config/checkout identity changed")
            if state["status"] in FINISHED:
                return state
            if stopped(config):
                state["status"] = "disabled"
            elif state["pending"]:
                if now >= expected["publisher_deadline_unix"]:
                    state.update(status="deadline", reason="publisher_deadline_pending_review")
                else:
                    push_pending(config, state, state_path)
            else:
                root = Path(config["publish_root"]).resolve()
                clean(root)
                if state["last_published"] is None:
                    synchronize(root, state)
                if state["last_published"] is None and (root / LATEST).is_file():
                    previous = read(root / LATEST)
                    if (previous.get("freeze_sha256") == expected["freeze_sha256"]
                            and previous.get("campaign_id") == expected["campaign_id"]):
                        state["last_published"] = published_metadata(previous, git(root, "rev-parse", "HEAD"))
                collect = progress.collect if collector is None else collector
                snapshot = collect(config["freeze_path"], config["monitor_directory"], config["cache_directory"],
                                   default_volume() if volume is None else volume, now=now)
                require(snapshot.get("freeze_sha256") == expected["freeze_sha256"]
                        and snapshot.get("campaign_id") == expected["campaign_id"], "collector freeze identity differs")
                expired = now >= expected["publisher_deadline_unix"]
                if expired:
                    snapshot["publisher_note"] = (
                        "The progress publisher reached its fixed cutoff and stopped. "
                        "The supervisor status above is retained and may be stale; this does not establish training completion.")
                last = state["last_published"]
                due = (expired or last is None or now - last["unix"] >= PUBLISH_SECONDS
                       or progress.checkpoint_key(snapshot) != last["checkpoint_key"]
                       or marker(snapshot) != last["status_key"])
                if due:
                    publish(config, state, state_path, snapshot)
                elif snapshot.get("monitor_status") in TERMINAL:
                    state["status"] = "complete"
            state["updated_unix"] = now
            atomic_json(state_path, state)
            return state
        except Exception as error:
            state.update(status="error", updated_unix=now, error_type=type(error).__name__)
            atomic_json(state_path, state)
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--follow", action="store_true")
    args = parser.parse_args()
    config = read(args.config)
    while True:
        started = time.monotonic()
        state = tick(config)
        if not args.follow or state["status"] in FINISHED:
            print(json.dumps({"status": state["status"], "last_published": state["last_published"]}))
            return
        time.sleep(min(max(0., POLL_SECONDS - (time.monotonic() - started)),
                       max(0., state["identity"]["publisher_deadline_unix"] - time.time())))


if __name__ == "__main__":
    main()
