"""Read immutable final-training milestones; never read live training reports."""

from datetime import datetime, timezone
import json
from pathlib import Path, PurePosixPath
import time
from zoneinfo import ZoneInfo

from . import decide as evidence

MILESTONES = (0, 512, 2048, 8192, 16384, 24576, 32768)
RUNS = tuple(f"{algorithm}-{seed}" for algorithm in evidence.ALGORITHMS for seed in evidence.SEEDS)


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def checked_local(root, relative):
    path = (root / relative).resolve()
    evidence.require(path.is_relative_to(root.resolve()), "local evidence path escapes its directory")
    return path


def inputs(freeze_path, monitor):
    freeze, state = evidence.read(freeze_path), evidence.read(monitor / "state.json")
    frozen_hash = evidence.digest(freeze_path)
    campaign = freeze["campaign"]
    evidence.require(freeze["schema"] == "learning-final-freeze-v1"
                     and campaign["campaign_id"] == evidence.EXPERIMENT
                     and state["schema"] == "learning-final-supervisor-v1"
                     and state["campaign_id"] == campaign["campaign_id"]
                     and state["identity"]["freeze_sha256"] == frozen_hash,
                     "monitor and freeze identity differ")
    stages = {stage["name"]: stage for stage in campaign["stages"]}
    evidence.require(set(stages) == {"fit", "extend"} and state["stage"] in stages
                     and "fit" in state["receipts"] and set(state["receipts"]) <= set(stages),
                     "unexpected monitor stages")
    receipts = {}
    for name in ("fit", "extend"):
        expected = [{"run_id": run_id, "algorithm": run_id.split("-")[0],
                     "seed": int(run_id.split("-")[1]), "episodes": 8192 if name == "fit" else 32768}
                    for run_id in RUNS]
        evidence.require(stages[name]["jobs"] == expected, "frozen six-run matrix differs")
        if name not in state["receipts"]:
            continue
        item = state["receipts"][name]
        path = checked_local(monitor, item["path"])
        evidence.require(evidence.digest(path) == item["sha256"], "receipt hash differs")
        receipt = evidence.read(path)
        jobs = [{key: job[key] for key in ("run_id", "algorithm", "seed", "episodes")}
                for job in receipt["jobs"]]
        algorithms = {job["algorithm"] for job in jobs}
        selected = [job for job in expected if job["algorithm"] in algorithms]
        reservation = receipt["reservation"]
        evidence.require(receipt["schema"] == "learning-final-receipt-v1"
                         and receipt["status"] == "submitted" and receipt["stage"] == name
                         and receipt["campaign_id"] == campaign["campaign_id"]
                         and receipt["freeze_sha256"] == frozen_hash and jobs == selected and jobs
                         and (name != "fit" or jobs == expected)
                         and all(isinstance(job["call_id"], str) and job["call_id"] for job in receipt["jobs"])
                         and reservation["stage"] == name and reservation["jobs"] == jobs
                         and reservation["freeze_sha256"] == frozen_hash
                         and receipt["created_unix"] <= reservation["deadline_unix"] <= campaign["deadline_unix"],
                         "receipt differs from its frozen whole-method stage")
        receipts[name] = receipt
    evidence.require(state["stage"] in receipts
                     and state["identity"]["fit_receipt_sha256"] == state["receipts"]["fit"]["sha256"],
                     "monitor receipt identity differs")
    return freeze, state, receipts, frozen_hash


def entries(volume, directory):
    """Accept direct children only; never follow arbitrary volume paths."""
    names = set()
    for entry in volume.iterdir(directory, recursive=False):
        path = PurePosixPath(entry.path.lstrip("/"))
        if str(path.parent) == directory:
            names.add(path.name)
    return names


def collect(freeze_path, monitor_dir, cache_dir, volume, now=None):
    """Collect six-run status and checked milestones from the isolated final volume.

    Caller supplies the read-only junction-learning-final Volume. Files do not
    contain source pins themselves: provenance is the frozen launch receipt and
    this isolated volume. Only validated immutable pairs enter the private cache.
    """
    now = time.time() if now is None else float(now)
    monitor, cache = Path(monitor_dir).resolve(), Path(cache_dir).resolve()
    freeze, state, receipts, frozen_hash = inputs(Path(freeze_path), monitor)
    identity = {"campaign_id": state["campaign_id"], "freeze_sha256": frozen_hash}
    cache_identity = {**identity, "fit_receipt_sha256": state["receipts"]["fit"]["sha256"],
                      "volume_name": "junction-learning-final"}
    cache.mkdir(parents=True, exist_ok=True)
    if (cache / "identity.json").exists():
        evidence.require(evidence.read(cache / "identity.json") == cache_identity, "cache belongs to another freeze/receipt")
    else:
        atomic_json(cache / "identity.json", cache_identity)
    index_path = cache / "index.json"
    index = evidence.read(index_path) if index_path.exists() else {"runs": {}, "config": None}
    errors, statuses = [], {}

    def error(run_id, operation, exception):
        errors.append({"run_id": run_id, "operation": operation, "type": type(exception).__name__})

    for stage, receipt in receipts.items():
        try:
            status = evidence.read(monitor / stage / "status.json")
            evidence.require(status["campaign_id"] == state["campaign_id"] and status["stage"] == stage
                             and status["app_id"] == receipt["app_id"]
                             and {job["run_id"] for job in status["jobs"]} == {job["run_id"] for job in receipt["jobs"]}
                             and len(status["jobs"]) == len(receipt["jobs"]), "local status identity differs")
            for job in status["jobs"]:
                expected = next(item for item in receipt["jobs"] if item["run_id"] == job["run_id"])
                for metadata in (job.get("state", {}), job.get("result", {})):
                    evidence.require("call_id" not in metadata or metadata["call_id"] == expected["call_id"],
                                     "status call identity differs")
            statuses[stage] = {job["run_id"]: job for job in status["jobs"]}
        except Exception as exception:
            error(None, f"read_{stage}_status", exception)
            statuses[stage] = {}

    runs = {}
    for run_id in RUNS:
        algorithm, seed_text = run_id.split("-")
        seed = int(seed_text)
        stage = next(name for name in reversed(receipts) if any(j["run_id"] == run_id for j in receipts[name]["jobs"]))
        receipt = receipts[stage]
        target = next(j["episodes"] for j in receipt["jobs"] if j["run_id"] == run_id)
        job = statuses[stage].get(run_id, {})
        metadata, result = job.get("state", {}), job.get("result", {})
        status = result.get("status", metadata.get("status", "pending" if job.get("pending") else "unknown"))
        if "error_type" in job:
            status = "error"
        started = metadata.get("started_unix")
        elapsed = result.get("elapsed_seconds", max(0., now-started) if started is not None else None)
        run_cache = cache / "runs" / run_id
        retained, known = {}, index["runs"].setdefault(run_id, {})
        try:
            remote = entries(volume, run_id)
        except Exception as exception:
            error(run_id, "list_milestones", exception)
            remote = set()
        try:
            batches = entries(volume, f"{run_id}/batches")
            count = 0
            while count < target and f"batch-{count:05d}.json.gz" in batches:
                count += 32
        except Exception as exception:
            error(run_id, "list_batches", exception)
            count = None
        for milestone in MILESTONES:
            if milestone > target:
                continue
            names = (f"policy-{milestone:05d}.json", f"validation-{milestone:05d}.json.gz")
            local = all((run_cache / name).exists() for name in names)
            if not local and not all(name in remote for name in names):
                if str(milestone) in known:
                    error(run_id, f"checkpoint_{milestone}", FileNotFoundError())
                continue
            try:
                directory = run_cache if local else cache / ".pending" / run_id / str(milestone)
                if not local:
                    directory.mkdir(parents=True, exist_ok=True)
                    for name in names:
                        with (directory / name).open("wb") as stream:
                            for chunk in volume.read_file(f"{run_id}/{name}"):
                                stream.write(chunk)
                previous = known.get(str(milestone))
                if previous is not None:
                    evidence.require(evidence.digest(directory / names[0]) == previous["policy_sha256"]
                                     and evidence.digest(directory / names[1]) == previous["sha256"],
                                     "cached immutable checkpoint changed")
                summary, config = evidence.validation(directory, milestone, algorithm, seed, report_summary=None)
                evidence.require(index["config"] is None or index["config"] == config,
                                 "configuration differs across immutable milestones")
                if not local:
                    run_cache.mkdir(parents=True, exist_ok=True)
                    for name in names:
                        (directory / name).replace(run_cache / name)
                index["config"] = config
                summary.update(milestone=milestone, first_checked_unix=previous["first_checked_unix"] if previous else now)
                known[str(milestone)] = summary
                retained[str(milestone)] = summary
            except Exception as exception:
                error(run_id, f"checkpoint_{milestone}", exception)
        latest = retained[str(max(map(int, retained)))] if retained else None
        lower = max(count or 0, latest["milestone"] if latest else 0)
        base = 0 if stage == "fit" else 8192
        eta = None
        if status == "running" and elapsed and lower > base:
            eta = elapsed * max(0, target-lower) / (lower-base)
        runs[run_id] = {"algorithm": algorithm, "seed": seed, "stage": stage, "status": status,
                        "target_episodes": target, "batch_episodes_at_least": count, "episodes_at_least": lower,
                        "batch_files_contiguous": count//32 if count is not None else None,
                        "milestones": retained, "latest_checkpoint": latest,
                        "started_unix": started, "elapsed_seconds": elapsed,
                        "rough_eta_seconds": eta, "rough_finish_unix": now+eta if eta is not None else None,
                        "stage_cutoff_unix": receipt["reservation"]["deadline_unix"],
                        "stage_seconds_remaining": max(0., receipt["reservation"]["deadline_unix"]-now)}
    atomic_json(index_path, index)
    algorithms = {}
    for algorithm in evidence.ALGORITHMS:
        members = [runs[f"{algorithm}-{seed}"] for seed in evidence.SEEDS]
        common = set.intersection(*(set(run["milestones"]) for run in members))
        milestone = max(map(int, common)) if common else None
        checks = [run["milestones"][str(milestone)] for run in members] if milestone is not None else []
        algorithms[algorithm] = {"common_milestone": milestone, "seeds": list(evidence.SEEDS),
                                 "mean_reward": sum(c["mean_reward"] for c in checks)/3 if checks else None,
                                 "home": sum(c["home"] for c in checks) if checks else None,
                                 "alive": sum(c["alive"] for c in checks) if checks else None,
                                 "invalid_calls": sum(c["invalid_calls"] for c in checks) if checks else None,
                                 "count": sum(c["count"] for c in checks),
                                 "initial_mean_reward": sum(run["milestones"]["0"]["mean_reward"] for run in members)/3
                                 if all("0" in run["milestones"] for run in members) else None}
    return {"schema": "learning-final-progress-v1", "created_unix": now, **identity,
            "monitor_status": state["status"], "monitor_updated_unix": state.get("updated_unix"),
            "receipt_sha256": {stage: entry["sha256"] for stage, entry in state["receipts"].items()},
            "stage": state["stage"], "runs": runs, "algorithms": algorithms, "errors": errors,
            "limit": "Read-only reused-validation progress. Contiguous batch filenames show artifact coverage, not committed checkpoint state; volume visibility may lag. "
                     "ETA is a rough linear extrapolation, separate from the hard stage cutoff. "
                     "No production physics or optimizer audit; no final-world or reference-superiority claim."}


def checkpoint_key(snapshot):
    key = []
    for algorithm in evidence.ALGORITHMS:
        milestone = snapshot["algorithms"][algorithm]["common_milestone"]
        hashes = [] if milestone is None else [
            [snapshot["runs"][f"{algorithm}-{seed}"]["milestones"][str(milestone)][field]
             for field in ("policy_sha256", "sha256")] for seed in evidence.SEEDS]
        key.append([algorithm, milestone, hashes])
    return key


def stamp(unix, zone=timezone.utc):
    return datetime.fromtimestamp(unix, zone).strftime("%Y-%m-%d %H:%M:%S %Z")


def duration(seconds):
    return "unknown" if seconds is None else f"{seconds/60:.0f} min"


def render(snapshot):
    lines = ["# Final Traverse training progress", "",
             f"As of **{stamp(snapshot['created_unix'])}** / **{stamp(snapshot['created_unix'], ZoneInfo('Europe/Helsinki'))}**.", "",
             f"Stage: **{snapshot['stage']}**. Supervisor: **{snapshot['monitor_status']}**.", "",
             "These are reused validation worlds, not the untouched final check. All three seeds are retained; this does not promote a learned policy over the reference.", "",
             "| Run | Stage / status | Batch-file mission coverage / target | Latest validated milestone | Score | Home / alive | Invalid | Elapsed | Rough time remaining | Hard cutoff UTC |",
             "|---|---|---:|---:|---:|---|---:|---:|---:|---|"]
    for name, run in snapshot["runs"].items():
        check = run["latest_checkpoint"]
        milestone, score, safety = (str(check["milestone"]), f"{check['mean_reward']:.6f}", f"{check['home']}/{check['count']} · {check['alive']}/{check['count']}") if check else ("pending", "—", "—")
        coverage = "unknown" if run['batch_episodes_at_least'] is None else f"{run['batch_episodes_at_least']:,}"
        invalid = str(check['invalid_calls']) if check else "—"
        lines.append(f"| {name} | {run['stage']} / {run['status']} | {coverage} / {run['target_episodes']:,} | {milestone} | {score} | {safety} | {invalid} | {duration(run['elapsed_seconds'])} | {duration(run['rough_eta_seconds'])} | {stamp(run['stage_cutoff_unix'])} |")
    lines += ["", "Method means use the highest checkpoint available for **all three seeds at the same training budget**:", "",
              "| Method | Common milestone | Initial mean | Current mean | Home / alive | Invalid calls |",
              "|---|---:|---:|---:|---|---:|"]
    for name, group in snapshot["algorithms"].items():
        if group["common_milestone"] is None:
            lines.append(f"| {name} | pending | — | — | — | — |")
        else:
            initial = "—" if group["initial_mean_reward"] is None else f"{group['initial_mean_reward']:.6f}"
            lines.append(f"| {name} | {group['common_milestone']:,} | {initial} | {group['mean_reward']:.6f} | {group['home']}/{group['count']} · {group['alive']}/{group['count']} | {group['invalid_calls']} |")
    lines += ["", snapshot["limit"], ""]
    if snapshot["errors"]:
        lines += ["Some reads could not be verified; earlier valid cached checkpoints remain visible. Errors:", ""]
        lines += [f"- {item['run_id'] or 'monitor'}: {item['operation']} ({item['type']})." for item in snapshot["errors"]]
        lines.append("")
    return "\n".join(lines)
