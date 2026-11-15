"""Reproduce sponsor timing evidence and figure from saved records; no jobs run.

Run from any directory: python docs/modal-parallelism/generate.py
Requires matplotlib. All inputs are committed results, not a live Modal query.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
SOURCES: dict[str, str] = {}


def read_json(name: str):
    data = (ROOT / name).read_bytes()
    SOURCES[name] = hashlib.sha256(data).hexdigest()
    return json.loads(data)


def utc(value: float) -> str:
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


def main() -> None:
    status = read_json("docs/learning-final-results/fit/status.json")
    receipt = read_json("docs/learning-final-results/fit/receipt.json")
    runs = []
    for job in status["jobs"]:
        result, state = job["result"], job["state"]
        assert result["call_id"] == state["call_id"]
        report = read_json(f"docs/learning-final-results/fit/runs/{job['run_id']}/report.json")
        start = state["started_unix"]
        elapsed = result["elapsed_seconds"]
        runs.append({
            "run_id": job["run_id"], "call_id": result["call_id"],
            "started_unix": start, "started_utc": utc(start),
            "elapsed_seconds": elapsed, "derived_ended_unix": start + elapsed,
            "derived_ended_utc": utc(start + elapsed),
            "missions": report["episodes_completed"], "status": report["status"],
            "wrapper_status": result["status"],
        })
    assert len(runs) == 6 and sum(r["missions"] for r in runs) == 47840
    first = min(r["started_unix"] for r in runs)
    last = max(r["derived_ended_unix"] for r in runs)
    total = sum(r["elapsed_seconds"] for r in runs)
    span = last - first
    common = min(r["derived_ended_unix"] for r in runs) - max(r["started_unix"] for r in runs)
    assert common > 0

    farm_path = "docs/traverse-farm/programs-1/rows.jsonl"
    farm_bytes = (ROOT / farm_path).read_bytes()
    SOURCES[farm_path] = hashlib.sha256(farm_bytes).hexdigest()
    farm = [json.loads(line) for line in farm_bytes.splitlines()][:1500]
    assert len(farm) == 1500 and {r["seed"] for r in farm} == set(range(600, 900))
    groups = Counter((r["policy"], r["candidate"]) for r in farm)
    assert len(groups) == 5 and set(groups.values()) == {300}
    farm_seconds = sum(r["seconds"] for r in farm)
    evidence = {
        "schema": "modal-parallelism-evidence-v1",
        "method": "Read-only arithmetic on existing records; no training, evaluation or cloud job.",
        "training": {
            "app_id": status["app_id"], "runs": runs,
            "missions": sum(r["missions"] for r in runs),
            "sum_recorded_wrapper_seconds": total,
            "observed_wrapper_window_seconds": span,
            "sum_to_window_ratio": total / span,
            "serial_same_duration_minus_window_seconds": total - span,
            "all_six_overlap_seconds": common,
            "launch_spread_seconds": max(r["started_unix"] for r in runs) - first,
            "resources_per_run": receipt["resources"],
            "limitations": [
                "Window is first saved wrapper start to last derived wrapper end; excludes pre-wrapper deployment/queue time.",
                "End is saved start plus returned elapsed_seconds; wrapper time includes validation and bookkeeping.",
                "Summed durations give a same-duration serial scenario, not a measured laptop runtime or CPU-hours total.",
                "Allocations are requested resources, not measured CPU utilization. Five runs reached 8192; one stopped at deadline after 6880.",
            ],
        },
        "farm": {
            "app_id": "ap-gBRd5446NAlbSopK5sdrI4", "missions": 1500,
            "worlds": [600, 899],
            "groups": [{"policy": p, "candidate": c, "count": n} for (p, c), n in groups.items()],
            "sum_recorded_execution_seconds": farm_seconds,
            "documented_approximate_batch_minutes": 7,
            "documented_container_limit_reached": 100,
            "duration_source": "docs/traverse-farm.md and docs/prize-evidence.md",
            "historical_rows_checked_at_commit": "b980ec2a",
            "limitations": [
                "First 1500 rows match the original five-controller comparison; later 600 rows excluded.",
                "Seconds are controller/program wall time, not CPU time; exclude startup and evaluator horizon-fill/final grading.",
                "Seven minutes is the owner's approximate recorded duration; exact batch timestamps were not retained.",
                "No measured laptop benchmark or exact end-to-end speedup is claimed.",
            ],
        },
        "source_sha256": SOURCES,
    }
    (ROOT / "docs/modal-parallelism-evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")

    plt.rcParams.update({"font.family": "DejaVu Sans", "svg.fonttype": "none",
                         "svg.hashsalt": "junction-modal-parallelism-v1"})
    bg, ink, muted, green, secondary = "#101c19", "#f6f4e9", "#adbcb5", "#91ed93", "#56ac8d"
    fig = plt.figure(figsize=(16, 9), dpi=120, facecolor=bg)
    fig.text(.075, .91, "14.4 run-hours. 2h 58m elapsed.", color=ink, fontsize=31, weight="bold")
    fig.text(.075, .85, "Six RL jobs on Modal  ·  47,840 training missions", color=green, fontsize=20)
    ax = fig.add_axes([.16, .25, .73, .51], facecolor=bg)
    for i, run in enumerate(runs):
        y = 5 - i
        offset = (run["started_unix"] - first) / 60
        minutes = run["elapsed_seconds"] / 60
        ax.barh(y, minutes, left=offset, height=.6, color=green if i < 3 else secondary)
        note = f"{run['missions']:,} missions" + (" · deadline" if run["status"] == "deadline" else "")
        ax.text(offset + minutes - 2, y, note, ha="right", va="center", color=bg, fontsize=12, weight="bold")
    ax.set_yticks(list(range(6)), [r["run_id"].upper().replace("-", " ") for r in runs[::-1]])
    ax.set_xlim(0, 185)
    ax.set_xticks([0, 30, 60, 90, 120, 150, 180])
    ax.set_xlabel("Minutes since the first recorded job started", color=muted, fontsize=12, labelpad=12)
    ax.tick_params(colors=ink, labelsize=13, length=0, pad=9)
    ax.xaxis.grid(True, color="#30463c", linewidth=.7)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.text(.075, .14, "All six jobs overlapped for 1h 57m; their starts were less than four seconds apart.", color=ink, fontsize=14)
    fig.text(.075, .09, "14.4h sums recorded job durations, including validation. It is a serial-duration comparison, not a laptop benchmark.", color=muted, fontsize=11)
    fig.text(.075, .055, "Each job requested 8 CPUs / 16 GiB. Source: saved Modal receipts and terminal records · docs/modal-parallelism-evidence.json", color=muted, fontsize=10)
    fig.savefig(OUT / "training-overlap.png", dpi=120, facecolor=bg)
    fig.savefig(OUT / "training-overlap.svg", facecolor=bg, metadata={"Date": None})
    plt.close(fig)
    svg = OUT / "training-overlap.svg"
    svg.write_text("\n".join(line.rstrip() for line in svg.read_text().splitlines()) + "\n")
    print(json.dumps({"training_run_hours": total / 3600, "elapsed_hours": span / 3600,
                      "ratio": total / span, "farm_execution_hours": farm_seconds / 3600}))


if __name__ == "__main__":
    main()
